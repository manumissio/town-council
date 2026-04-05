from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count
from datetime import datetime
import os
import logging
import sys
import subprocess
import time
from sqlalchemy import Text, cast, or_
from sqlalchemy.exc import SQLAlchemyError

from pipeline.config import (
    AGENDA_SEGMENT_MAINTENANCE_TIMEOUT_SECONDS,
    DOCUMENT_CHUNK_SIZE,
    MAX_WORKERS,
    PIPELINE_CPU_FRACTION,
    PIPELINE_ONBOARDING_CITY,
    PIPELINE_ONBOARDING_STARTED_AT_UTC,
    PIPELINE_ONBOARDING_DOCUMENT_CHUNK_SIZE,
    PIPELINE_ONBOARDING_MAX_WORKERS,
    PIPELINE_RUNTIME_PROFILE,
    SUMMARY_HYDRATION_MAINTENANCE_TIMEOUT_SECONDS,
    TIKA_OCR_FALLBACK_ENABLED,
    DB_RETRY_DELAY_MIN,
    DB_RETRY_DELAY_MAX,
    EXTRACTION_TERMINAL_FAILURE_MAX_ATTEMPTS,
)
from pipeline.startup_purge import run_startup_purge_if_enabled
from pipeline.metrics import record_pipeline_phase_duration
from pipeline.profiling import apply_catalog_id_scope, profile_span, workload_only_profile
from pipeline.extraction_state import mark_extraction_complete, mark_extraction_failure

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("pipeline-manager")


def _catalog_entities_need_nlp(catalog_model):
    # Postgres `json` columns do not support equality, so JSON null checks must
    # compare the serialized value instead of using `= 'null'`.
    return or_(
        catalog_model.entities.is_(None),
        cast(catalog_model.entities, Text) == "null",
        catalog_model.content_hash.is_(None),
        catalog_model.entities_source_hash.is_(None),
        catalog_model.entities_source_hash != catalog_model.content_hash,
    )


def _scope_catalog_query_for_onboarding(db, query):
    from pipeline.models import Catalog

    if not PIPELINE_ONBOARDING_CITY:
        return query, None

    onboarding_started_at = _parse_onboarding_started_at(PIPELINE_ONBOARDING_STARTED_AT_UTC)
    if onboarding_started_at is None:
        logger.warning(
            "onboarding_scope city=%s missing valid started_at; falling back to global selection",
            PIPELINE_ONBOARDING_CITY,
        )
        return query.distinct(), None

    ocd_division_id = _onboarding_ocd_division_id(PIPELINE_ONBOARDING_CITY)
    touched_hashes = _build_onboarding_touched_hashes_subquery(
        db,
        onboarding_started_at,
        ocd_division_id,
    )
    touched_hash_count = db.query(touched_hashes.c.url_hash).distinct().count()
    scoped = query.join(touched_hashes, touched_hashes.c.url_hash == Catalog.url_hash).distinct()
    logger.info(
        "onboarding_scope city=%s ocd_division_id=%s touched_hashes=%s source=url_stage_hist+url_stage",
        PIPELINE_ONBOARDING_CITY,
        ocd_division_id,
        touched_hash_count,
    )
    return scoped, touched_hash_count

def run_step(name, command):
    """Helper to run a shell command step."""
    logger.info(f"Step: {name}")
    phase = _phase_name_for_step(name)
    with profile_span(
        phase=phase,
        component="subprocess",
        metadata={"command": list(command)},
    ):
        start_perf = time.perf_counter()
        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError:
            logger.error(f"Step {name} failed.")
            record_pipeline_phase_duration(
                phase,
                "subprocess",
                _current_profile_mode(),
                "failure",
                time.perf_counter() - start_perf,
            )
            sys.exit(1)
        duration_s = time.perf_counter() - start_perf
        record_pipeline_phase_duration(phase, "subprocess", _current_profile_mode(), "success", duration_s)


def run_callable_step(name, func, *, component="pipeline"):
    """Run an in-process orchestration step with the same profiling semantics as run_step."""
    logger.info("Step: %s", name)
    phase = _phase_name_for_step(name)
    with profile_span(phase=phase, component=component):
        start_perf = time.perf_counter()
        try:
            result = func()
        except Exception:
            logger.error("Step %s failed.", name)
            record_pipeline_phase_duration(
                phase,
                component,
                _current_profile_mode(),
                "failure",
                time.perf_counter() - start_perf,
            )
            sys.exit(1)
        duration_s = time.perf_counter() - start_perf
        record_pipeline_phase_duration(
            phase,
            component,
            _current_profile_mode(),
            "success",
            duration_s,
        )
        return result


def _should_skip_non_gating_onboarding_steps() -> bool:
    # Onboarding decisions only gate on crawl, extraction, segmentation, and searchability.
    # Keep enrichment steps out of the hot path when the runner explicitly requests the fast profile.
    return bool(PIPELINE_ONBOARDING_CITY) and PIPELINE_RUNTIME_PROFILE == "onboarding_fast"


def _run_post_processing_steps():
    logger.info("post_processing_search_indexing skipped=1 mode=targeted_only")


def _run_ingest_prelude_steps():
    # Profiling selected-manifest runs should measure only the chosen workload,
    # not unrelated global staging activity.
    if workload_only_profile():
        logger.info("profiling_workload_only enabled=1 skipped_prelude=db_migrate,seed_places,promote_stage,downloader")
        return
    run_step("DB Migrate", ["python", "db_migrate.py"])
    run_step("Seed Places", ["python", "seed_places.py"])
    run_step("Promote Staged Events", ["python", "promote_stage.py"])
    run_step("Downloader", ["python", "downloader.py"])


def _run_generation_backfill_steps():
    from functools import partial

    from pipeline.agenda_worker import run_agenda_segmentation_backfill
    from pipeline.tasks import run_summary_hydration_backfill

    # Agenda summaries depend on structured agenda items, so segmentation must
    # run before summary hydration in the canonical batch pipeline.
    run_callable_step(
        "Agenda Segmentation",
        partial(
            run_agenda_segmentation_backfill,
            segment_mode="maintenance",
            agenda_timeout_seconds=AGENDA_SEGMENT_MAINTENANCE_TIMEOUT_SECONDS,
        ),
    )
    # Reuse the same summary-task rules as the interactive path instead of
    # duplicating prompt, grounding, or caching behavior in the pipeline.
    run_callable_step(
        "Summary Hydration",
        partial(
            run_summary_hydration_backfill,
            summary_timeout_seconds=SUMMARY_HYDRATION_MAINTENANCE_TIMEOUT_SECONDS,
            summary_fallback_mode="deterministic",
        ),
    )


def _should_skip_generation_backfill_steps() -> bool:
    # The onboarding runner already does city-scoped segmentation after the
    # extraction subprocess returns. Skipping the global backfills here keeps
    # first-time onboarding from waking unrelated city backlog.
    return bool(PIPELINE_ONBOARDING_CITY) and PIPELINE_RUNTIME_PROFILE == "onboarding_fast"


def process_document_chunk(catalog_ids, ocr_fallback_enabled=None):
    """
    Process a chunk of catalog IDs in one worker process.
    Reuses one DB session for the chunk and commits per document.
    """
    from pipeline.models import db_connect, Catalog
    from pipeline.extractor import extract_text
    from pipeline.content_hash import compute_content_hash
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text
    import time
    import random
    import sys

    chunk_catalog_ids = [int(cid) for cid in catalog_ids]
    with profile_span(
        phase="extract_chunk",
        component="pipeline",
        metadata={"catalog_count": len(chunk_catalog_ids)},
    ) as span_meta:
        # Open one DB session for the chunk. Retry with jitter if DB is busy.
        chunk_started = time.perf_counter()
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
                if db:
                    db.close()
                time.sleep(random.uniform(DB_RETRY_DELAY_MIN, DB_RETRY_DELAY_MAX))
                continue

        if not db:
            span_meta["db_connect"] = "failed"
            record_pipeline_phase_duration(
                "extract_chunk",
                "pipeline",
                _current_profile_mode(),
                "failure",
                time.perf_counter() - chunk_started,
            )
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
                        mark_extraction_complete(catalog, compute_content_hash(catalog.content))
                    else:
                        mark_extraction_failure(catalog, "Extraction returned empty text")
                elif catalog.content and not getattr(catalog, "content_hash", None):
                    # Older rows may predate content hashing.
                    mark_extraction_complete(catalog, compute_content_hash(catalog.content))
                elif catalog.content:
                    catalog.extraction_status = catalog.extraction_status or "complete"
                    catalog.extraction_attempt_count = int(catalog.extraction_attempt_count or 0)

                # Commit per document to keep partial progress.
                db.commit()
                processed_count += 1

            span_meta["processed_count"] = processed_count
            record_pipeline_phase_duration(
                "extract_chunk",
                "pipeline",
                _current_profile_mode(),
                "success",
                time.perf_counter() - chunk_started,
            )
            return processed_count
        except SQLAlchemyError as e:
            db.rollback()
            span_meta["error"] = e.__class__.__name__
            record_pipeline_phase_duration(
                "extract_chunk",
                "pipeline",
                _current_profile_mode(),
                "failure",
                time.perf_counter() - chunk_started,
            )
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
    Select catalog IDs that still need extraction work.
    """
    from pipeline.models import Catalog

    extraction_query = db.query(Catalog.id).filter(
        Catalog.content.is_(None),
        (Catalog.extraction_status.is_(None)) | (Catalog.extraction_status != "failed_terminal"),
    )
    extraction_query = apply_catalog_id_scope(extraction_query, Catalog.id)
    extraction_query, _touched_hash_count = _scope_catalog_query_for_onboarding(db, extraction_query)

    extraction_ids = [row[0] for row in extraction_query.yield_per(1000)]

    terminal_failures = (
        db.query(Catalog.id)
        .filter(Catalog.content.is_(None), Catalog.extraction_status == "failed_terminal")
        .count()
    )
    if PIPELINE_ONBOARDING_CITY:
        logger.info(
            "onboarding_scope city=%s selected_missing_work_catalogs=%s extraction_needed=%s excluded_terminal_failures=%s",
            PIPELINE_ONBOARDING_CITY,
            len(extraction_ids),
            len(extraction_ids),
            terminal_failures,
        )
    else:
        logger.info(
            "global_scope selected_missing_work_catalogs=%s extraction_needed=%s excluded_terminal_failures=%s",
            len(extraction_ids),
            len(extraction_ids),
            terminal_failures,
        )

    return extraction_ids


def select_catalog_ids_for_entity_backfill(db):
    """
    Select catalog IDs that already have content but still need entity enrichment.
    """
    from pipeline.models import Catalog

    query = db.query(Catalog.id).filter(
        Catalog.content.isnot(None),
        Catalog.content != "",
        _catalog_entities_need_nlp(Catalog),
    )
    query = apply_catalog_id_scope(query, Catalog.id)
    query, _touched_hash_count = _scope_catalog_query_for_onboarding(db, query)
    return [row[0] for row in query.yield_per(1000)]


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

    with profile_span(
        phase="extract_parallel",
        component="pipeline",
        metadata={
            "catalog_count": len(catalog_ids),
            "chunk_count": len(chunks),
            "worker_count": workers,
        },
    ):
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
    with profile_span(phase="pipeline_total", component="pipeline"):
        # Optional startup purge for derived fields. Safe to call repeatedly.
        purge_result = run_startup_purge_if_enabled()
        logger.info(f"startup_purge_result={purge_result}")

        # 1. Setup & Ingest
        _run_ingest_prelude_steps()

        # 2. Parallel Processing (Replaces extractor.py and nlp_worker.py)
        logger.info(">>> Starting Parallel Processing (OCR + NLP)")
        run_parallel_processing()

        # 3. Derived-generation backfills
        if _should_skip_generation_backfill_steps():
            logger.info(
                "generation_backfills skipped=1 mode=onboarding_fast city=%s handled_by=city_runner",
                PIPELINE_ONBOARDING_CITY,
            )
        else:
            _run_generation_backfill_steps()

        # 4. Post-Processing
        _run_post_processing_steps()

    logger.info("<<< Pipeline Complete")


def _phase_name_for_step(step_name: str) -> str:
    mapping = {
        "DB Migrate": "db_migrate",
        "Seed Places": "seed_places",
        "Promote Staged Events": "promote_stage",
        "Downloader": "download",
        "Agenda Segmentation": "segment_agenda",
        "Summary Hydration": "summarize",
        "Search Indexing": "index_search",
        "Entity Backfill": "entity_backfill",
        "Table Extraction": "table_extraction",
        "Backfill Organizations": "org_backfill",
        "Topic Modeling": "topic_modeling",
        "People Linking": "people_linking",
    }
    return mapping.get(step_name, step_name.lower().replace(" ", "_"))


def _current_profile_mode() -> str:
    return str(os.getenv("TC_PROFILE_MODE", "triage") or "triage")

if __name__ == "__main__":
    main()
