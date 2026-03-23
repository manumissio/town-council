from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count
from datetime import datetime
import logging
import sys
import subprocess
from sqlalchemy import Text, cast, or_
from sqlalchemy.exc import SQLAlchemyError

from pipeline.config import (
    DOCUMENT_CHUNK_SIZE,
    MAX_WORKERS,
    PIPELINE_CPU_FRACTION,
    PIPELINE_ONBOARDING_CITY,
    PIPELINE_ONBOARDING_STARTED_AT_UTC,
    PIPELINE_ONBOARDING_DOCUMENT_CHUNK_SIZE,
    PIPELINE_ONBOARDING_MAX_WORKERS,
    PIPELINE_RUNTIME_PROFILE,
    TIKA_OCR_FALLBACK_ENABLED,
    DB_RETRY_DELAY_MIN,
    DB_RETRY_DELAY_MAX,
    EXTRACTION_TERMINAL_FAILURE_MAX_ATTEMPTS,
)
from pipeline.startup_purge import run_startup_purge_if_enabled

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("pipeline-manager")


def _catalog_entities_need_nlp(catalog_model):
    # Postgres `json` columns do not support equality, so JSON null checks must
    # compare the serialized value instead of using `= 'null'`.
    return or_(
        catalog_model.entities.is_(None),
        cast(catalog_model.entities, Text) == "null",
    )

def run_step(name, command):
    """Helper to run a shell command step."""
    logger.info(f"Step: {name}")
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError:
        logger.error(f"Step {name} failed.")
        sys.exit(1)


def _should_skip_non_gating_onboarding_steps() -> bool:
    # Onboarding decisions only gate on crawl, extraction, segmentation, and searchability.
    # Keep enrichment steps out of the hot path when the runner explicitly requests the fast profile.
    return bool(PIPELINE_ONBOARDING_CITY) and PIPELINE_RUNTIME_PROFILE == "onboarding_fast"


def _run_post_processing_steps():
    if _should_skip_non_gating_onboarding_steps():
        logger.info(
            "onboarding_fast_profile city=%s executed_steps=Search Indexing skipped_steps=Table Extraction, Backfill Organizations, Topic Modeling, People Linking",
            PIPELINE_ONBOARDING_CITY,
        )
        run_step("Search Indexing", ["python", "indexer.py"])
        return

    # These steps depend on the global dataset, so they run sequentially after processing.
    run_step("Table Extraction", ["python", "table_worker.py"])  # Can fail safely
    run_step("Backfill Organizations", ["python", "backfill_orgs.py"])
    run_step("Topic Modeling", ["python", "topic_worker.py"])
    run_step("People Linking", ["python", "person_linker.py"])
    run_step("Search Indexing", ["python", "indexer.py"])


def _run_generation_backfill_steps():
    # Agenda summaries depend on structured agenda items, so segmentation must
    # run before summary hydration in the canonical batch pipeline.
    run_step("Agenda Segmentation", ["python", "../scripts/backfill_agenda_segmentation.py"])
    # Reuse the same summary-task rules as the interactive path instead of
    # duplicating prompt, grounding, or caching behavior in the pipeline.
    run_step("Summary Hydration", ["python", "../scripts/backfill_summaries.py"])

def _mark_extraction_complete(catalog, content_hash):
    catalog.content_hash = content_hash
    catalog.extraction_status = "complete"
    catalog.extraction_attempt_count = max(1, int(catalog.extraction_attempt_count or 0))
    catalog.extraction_attempted_at = datetime.utcnow()
    catalog.extraction_error = None


def _mark_extraction_failure(catalog, error_message: str):
    attempts = int(catalog.extraction_attempt_count or 0) + 1
    catalog.extraction_attempt_count = attempts
    catalog.extraction_attempted_at = datetime.utcnow()
    catalog.extraction_error = (error_message or "Extraction returned empty text")[:500]
    catalog.extraction_status = (
        "failed_terminal"
        if attempts >= EXTRACTION_TERMINAL_FAILURE_MAX_ATTEMPTS
        else "pending"
    )


def process_document_chunk(catalog_ids, ocr_fallback_enabled=None):
    """
    Process a chunk of catalog IDs in one worker process.
    Reuses one DB session for the chunk and commits per document.
    """
    from pipeline.models import db_connect, Catalog
    from pipeline.extractor import extract_text
    from pipeline.content_hash import compute_content_hash
    from pipeline.nlp_worker import extract_entities
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text
    import time
    import random
    import sys

    # Open one DB session for the chunk. Retry with jitter if DB is busy.
    db = None
    for attempt in range(3):
        try:
            engine = db_connect()
            Session = sessionmaker(bind=engine)
            db = Session()
            # Health check: verify the connection works
            db.execute(text("SELECT 1"))
            break
        except SQLAlchemyError:
            if db: db.close()
            time.sleep(random.uniform(DB_RETRY_DELAY_MIN, DB_RETRY_DELAY_MAX))
            continue

    if not db:
        print(f"Error: Could not connect to database for chunk {catalog_ids[:2]}...", file=sys.stderr)
        return 0

    processed_count = 0
    try:
        for cid in catalog_ids:
            catalog = db.get(Catalog, cid)
            if not catalog:
                continue

            # Extract text only when needed.
            if not catalog.content and catalog.location:
                extracted = extract_text(
                    catalog.location,
                    ocr_fallback_enabled=ocr_fallback_enabled,
                )
                if extracted:
                    catalog.content = extracted
                    _mark_extraction_complete(catalog, compute_content_hash(catalog.content))
                else:
                    _mark_extraction_failure(catalog, "Extraction returned empty text")
            elif catalog.content and not getattr(catalog, "content_hash", None):
                # Older rows may predate content hashing.
                _mark_extraction_complete(catalog, compute_content_hash(catalog.content))
            elif catalog.content:
                catalog.extraction_status = catalog.extraction_status or "complete"
                catalog.extraction_attempt_count = int(catalog.extraction_attempt_count or 0)

            # Extract entities only when needed.
            if catalog.content and not catalog.entities:
                catalog.entities = extract_entities(catalog.content)

            # Commit per document to keep partial progress.
            db.commit()
            processed_count += 1

        return processed_count
    except SQLAlchemyError as e:
        db.rollback()
        print(f"Error processing batch: {e}", file=sys.stderr)
        return processed_count
    finally:
        db.close()

def _parse_onboarding_started_at(raw_value):
    if not raw_value:
        return None
    try:
        return datetime.strptime(raw_value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        logger.warning(
            "Invalid PIPELINE_ONBOARDING_STARTED_AT_UTC=%r; falling back to city-wide scope.",
            raw_value,
        )
        return None


def _onboarding_ocd_division_id(city_slug):
    return f"ocd-division/country:us/state:ca/place:{city_slug}"


def _build_onboarding_touched_hashes_subquery(db, onboarding_started_at, ocd_division_id):
    from pipeline.models import UrlStage, UrlStageHist

    hist_hashes = (
        db.query(UrlStageHist.url_hash.label("url_hash"))
        .filter(
            UrlStageHist.ocd_division_id == ocd_division_id,
            UrlStageHist.created_at >= onboarding_started_at,
        )
    )
    live_hashes = (
        db.query(UrlStage.url_hash.label("url_hash"))
        .filter(
            UrlStage.ocd_division_id == ocd_division_id,
            UrlStage.created_at >= onboarding_started_at,
        )
    )
    return hist_hashes.union(live_hashes).subquery()


def select_catalog_ids_for_processing(db):
    """
    Select catalog IDs that still need extraction/NLP work.
    """
    from pipeline.models import Catalog

    extraction_query = db.query(Catalog.id).filter(
        Catalog.content.is_(None),
        (Catalog.extraction_status.is_(None)) | (Catalog.extraction_status != "failed_terminal"),
    )
    nlp_only_query = db.query(Catalog.id).filter(
        Catalog.content.isnot(None),
        Catalog.content != "",
        _catalog_entities_need_nlp(Catalog),
    )

    if PIPELINE_ONBOARDING_CITY:
        onboarding_started_at = _parse_onboarding_started_at(PIPELINE_ONBOARDING_STARTED_AT_UTC)
        if onboarding_started_at is not None:
            ocd_division_id = _onboarding_ocd_division_id(PIPELINE_ONBOARDING_CITY)
            # Onboarding runs often reuse historical catalog rows, so scope extraction
            # by the run's touched URL hashes instead of newly created document rows.
            touched_hashes = _build_onboarding_touched_hashes_subquery(
                db,
                onboarding_started_at,
                ocd_division_id,
            )
            touched_hash_count = db.query(touched_hashes.c.url_hash).distinct().count()
            extraction_query = extraction_query.join(touched_hashes, touched_hashes.c.url_hash == Catalog.url_hash)
            nlp_only_query = nlp_only_query.join(touched_hashes, touched_hashes.c.url_hash == Catalog.url_hash)
            logger.info(
                "onboarding_scope city=%s ocd_division_id=%s touched_hashes=%s source=url_stage_hist+url_stage",
                PIPELINE_ONBOARDING_CITY,
                ocd_division_id,
                touched_hash_count,
            )
        else:
            logger.warning(
                "onboarding_scope city=%s missing valid started_at; falling back to global selection",
                PIPELINE_ONBOARDING_CITY,
            )
        extraction_query = extraction_query.distinct()
        nlp_only_query = nlp_only_query.distinct()

    extraction_ids = [row[0] for row in extraction_query.yield_per(1000)]
    nlp_only_ids = [row[0] for row in nlp_only_query.yield_per(1000)]
    catalog_ids = list(dict.fromkeys(extraction_ids + nlp_only_ids))

    terminal_failures = (
        db.query(Catalog.id)
        .filter(Catalog.content.is_(None), Catalog.extraction_status == "failed_terminal")
        .count()
    )
    if PIPELINE_ONBOARDING_CITY:
        logger.info(
            "onboarding_scope city=%s selected_missing_work_catalogs=%s extraction_needed=%s nlp_only=%s excluded_terminal_failures=%s",
            PIPELINE_ONBOARDING_CITY,
            len(catalog_ids),
            len(extraction_ids),
            len(nlp_only_ids),
            terminal_failures,
        )
    else:
        logger.info(
            "global_scope selected_missing_work_catalogs=%s extraction_needed=%s nlp_only=%s excluded_terminal_failures=%s",
            len(catalog_ids),
            len(extraction_ids),
            len(nlp_only_ids),
            terminal_failures,
        )

    return catalog_ids


def _resolve_parallel_processing_settings():
    chunk_size = DOCUMENT_CHUNK_SIZE
    workers_override = None
    ocr_fallback_enabled = TIKA_OCR_FALLBACK_ENABLED
    mode = "global"

    if PIPELINE_ONBOARDING_CITY:
        mode = "onboarding_scoped"
        if PIPELINE_ONBOARDING_DOCUMENT_CHUNK_SIZE > 0:
            chunk_size = PIPELINE_ONBOARDING_DOCUMENT_CHUNK_SIZE
        if PIPELINE_ONBOARDING_MAX_WORKERS > 0:
            workers_override = PIPELINE_ONBOARDING_MAX_WORKERS

    return {
        "mode": mode,
        "chunk_size": chunk_size,
        "workers_override": workers_override,
        "ocr_fallback_enabled": ocr_fallback_enabled,
    }


def run_parallel_processing():
    """
    Find unprocessed docs and process them in parallel chunks.
    """
    from pipeline.db_session import db_session

    # Use context manager for automatic session cleanup
    with db_session() as db:
        catalog_ids = select_catalog_ids_for_processing(db)

    if not catalog_ids:
        logger.info("No documents need processing.")
        return

    settings = _resolve_parallel_processing_settings()

    # Split IDs into fixed-size chunks.
    chunks = [
        catalog_ids[i:i + settings["chunk_size"]]
        for i in range(0, len(catalog_ids), settings["chunk_size"])
    ]

    logger.info(
        "Starting parallel processing mode=%s city=%s documents=%s chunks=%s "
        "chunk_size=%s onboarding_started_at=%s ocr_fallback_enabled=%s",
        settings["mode"],
        PIPELINE_ONBOARDING_CITY or "-",
        len(catalog_ids),
        len(chunks),
        settings["chunk_size"],
        PIPELINE_ONBOARDING_STARTED_AT_UTC or "-",
        settings["ocr_fallback_enabled"],
    )

    # Use a CPU fraction, capped for safety.
    cpu_limit = int(cpu_count() * PIPELINE_CPU_FRACTION)
    workers = max(1, min(cpu_limit, MAX_WORKERS))
    if settings["workers_override"] is not None:
        workers = max(1, min(settings["workers_override"], MAX_WORKERS))

    logger.info("Parallel processing worker_count=%s", workers)

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                process_document_chunk,
                chunk,
                settings["ocr_fallback_enabled"],
            ): chunk
            for chunk in chunks
        }

        # Track completed documents across chunks.
        completed_docs = 0
        for future in as_completed(futures):
            count = future.result()
            if count:
                completed_docs += count
                logger.info(f"Progress: {completed_docs}/{len(catalog_ids)}")

def main():
    """
    Main pipeline entrypoint.
    """
    logger.info(">>> Starting High-Performance Pipeline")
    # Optional startup purge for derived fields. Safe to call repeatedly.
    purge_result = run_startup_purge_if_enabled()
    logger.info(f"startup_purge_result={purge_result}")
    
    # 1. Setup & Ingest
    # Keep dev databases compatible with the current SQLAlchemy models.
    run_step("DB Migrate", ["python", "db_migrate.py"])
    run_step("Seed Places", ["python", "seed_places.py"])
    run_step("Promote Staged Events", ["python", "promote_stage.py"])
    run_step("Downloader", ["python", "downloader.py"])
    
    # 2. Parallel Processing (Replaces extractor.py and nlp_worker.py)
    logger.info(">>> Starting Parallel Processing (OCR + NLP)")
    run_parallel_processing()

    # 3. Derived-generation backfills
    _run_generation_backfill_steps()

    # 4. Post-Processing
    _run_post_processing_steps()
    
    logger.info("<<< Pipeline Complete")

if __name__ == "__main__":
    main()
