from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count, get_context
import logging

from pipeline.config import ENTITY_BACKFILL_IN_PROCESS_THRESHOLD, MAX_WORKERS, PIPELINE_CPU_FRACTION
from pipeline.content_hash import compute_content_hash
from pipeline.db_session import db_session
from pipeline.run_pipeline import (
    PIPELINE_ONBOARDING_CITY,
    _resolve_parallel_processing_settings,
    select_catalog_ids_for_entity_backfill,
)


LOGGER_NAME = "entity-backfill"
LOGGER_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

logger = logging.getLogger(LOGGER_NAME)


def _configure_cli_logging() -> None:
    """Keep logging setup in the CLI path so imports remain side-effect free."""
    logging.basicConfig(level=logging.INFO, format=LOGGER_FORMAT)


def _empty_counts():
    return {
        "selected": 0,
        "complete": 0,
        "changed_catalogs": 0,
        "updated_catalog_ids": [],
        "execution_mode": "noop",
        "chunks": 0,
        "ner_processed": 0,
        "ner_skipped_low_signal": 0,
        "freshness_advanced": 0,
        "candidate_slice_fallback_prefix": 0,
    }


def process_entity_chunk(catalog_ids):
    from pipeline.db_session import db_session
    from pipeline.models import Catalog
    from pipeline.nlp_worker import build_entity_candidate_text, empty_entities_payload, extract_entities

    processed = 0
    updated_catalog_ids = []
    ner_processed = 0
    ner_skipped_low_signal = 0
    freshness_advanced = 0
    candidate_slice_fallback_prefix = 0
    with db_session() as session:
        for catalog_id in catalog_ids:
            record = session.get(Catalog, catalog_id)
            if not record or not record.content:
                continue
            content_hash = record.content_hash or compute_content_hash(record.content)
            if content_hash and content_hash != record.content_hash:
                record.content_hash = content_hash

            if record.entities is not None and record.entities_source_hash == content_hash:
                continue

            if record.entities is not None and record.entities_source_hash is None and content_hash:
                record.entities_source_hash = content_hash
                freshness_advanced += 1
                processed += 1
                continue

            category = getattr(record.document, "category", None) if getattr(record, "document", None) else None
            candidate_text, candidate_meta = build_entity_candidate_text(record.content, category=category)
            if candidate_meta["used_prefix_fallback"]:
                candidate_slice_fallback_prefix += 1
            if candidate_meta["skip_low_signal"]:
                extracted_entities = empty_entities_payload()
                ner_skipped_low_signal += 1
            else:
                extracted_entities = extract_entities(candidate_text)
                ner_processed += 1

            entity_changed = extracted_entities != record.entities
            freshness_changed = bool(content_hash and record.entities_source_hash != content_hash)
            if not entity_changed and not freshness_changed:
                continue
            record.entities = extracted_entities
            record.entities_source_hash = content_hash
            if freshness_changed:
                freshness_advanced += 1
            updated_catalog_ids.append(catalog_id)
            processed += 1
        if updated_catalog_ids or freshness_advanced:
            session.commit()
    return {
        "complete": processed,
        "updated_catalog_ids": updated_catalog_ids,
        "ner_processed": ner_processed,
        "ner_skipped_low_signal": ner_skipped_low_signal,
        "freshness_advanced": freshness_advanced,
        "candidate_slice_fallback_prefix": candidate_slice_fallback_prefix,
    }


def run_entity_backfill():
    with db_session() as db:
        catalog_ids = select_catalog_ids_for_entity_backfill(db)

    counts = _empty_counts()
    counts["selected"] = len(catalog_ids)

    if not catalog_ids:
        logger.info("No documents need entity enrichment.")
        return counts

    settings = _resolve_parallel_processing_settings()
    chunks = [
        catalog_ids[i:i + settings["chunk_size"]]
        for i in range(0, len(catalog_ids), settings["chunk_size"])
    ]
    cpu_limit = int(cpu_count() * PIPELINE_CPU_FRACTION)
    workers = max(1, min(cpu_limit, MAX_WORKERS))
    if settings["workers_override"] is not None:
        workers = max(1, min(settings["workers_override"], MAX_WORKERS))

    logger.info(
        "Starting entity backfill mode=%s city=%s documents=%s chunks=%s worker_count=%s",
        settings["mode"],
        PIPELINE_ONBOARDING_CITY or "-",
        len(catalog_ids),
        len(chunks),
        workers,
    )

    completed = 0
    updated_catalog_ids = []
    ner_processed = 0
    ner_skipped_low_signal = 0
    freshness_advanced = 0
    candidate_slice_fallback_prefix = 0
    execution_mode = "in_process" if len(catalog_ids) <= ENTITY_BACKFILL_IN_PROCESS_THRESHOLD else "process_pool"
    if execution_mode == "in_process":
        for chunk in chunks:
            chunk_result = process_entity_chunk(chunk)
            count = int(chunk_result.get("complete", 0))
            ner_processed += int(chunk_result.get("ner_processed", 0))
            ner_skipped_low_signal += int(chunk_result.get("ner_skipped_low_signal", 0))
            freshness_advanced += int(chunk_result.get("freshness_advanced", 0))
            candidate_slice_fallback_prefix += int(chunk_result.get("candidate_slice_fallback_prefix", 0))
            if count:
                completed += count
                updated_catalog_ids.extend(int(cid) for cid in chunk_result.get("updated_catalog_ids", []))
                logger.info("Entity backfill progress: %s/%s", completed, len(catalog_ids))
    else:
        with ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn")) as executor:
            futures = {executor.submit(process_entity_chunk, chunk): chunk for chunk in chunks}
            for future in as_completed(futures):
                chunk_result = future.result()
                count = int(chunk_result.get("complete", 0))
                ner_processed += int(chunk_result.get("ner_processed", 0))
                ner_skipped_low_signal += int(chunk_result.get("ner_skipped_low_signal", 0))
                freshness_advanced += int(chunk_result.get("freshness_advanced", 0))
                candidate_slice_fallback_prefix += int(chunk_result.get("candidate_slice_fallback_prefix", 0))
                if count:
                    completed += count
                    updated_catalog_ids.extend(int(cid) for cid in chunk_result.get("updated_catalog_ids", []))
                    logger.info("Entity backfill progress: %s/%s", completed, len(catalog_ids))
    counts["complete"] = completed
    counts["updated_catalog_ids"] = sorted(set(updated_catalog_ids))
    counts["changed_catalogs"] = len(counts["updated_catalog_ids"])
    counts["execution_mode"] = execution_mode
    counts["chunks"] = len(chunks)
    counts["ner_processed"] = ner_processed
    counts["ner_skipped_low_signal"] = ner_skipped_low_signal
    counts["freshness_advanced"] = freshness_advanced
    counts["candidate_slice_fallback_prefix"] = candidate_slice_fallback_prefix
    logger.info(
        "entity_backfill selected=%s complete=%s changed_catalogs=%s execution_mode=%s chunks=%s ner_processed=%s ner_skipped_low_signal=%s freshness_advanced=%s candidate_slice_fallback_prefix=%s",
        counts["selected"],
        counts["complete"],
        counts["changed_catalogs"],
        counts["execution_mode"],
        counts["chunks"],
        counts["ner_processed"],
        counts["ner_skipped_low_signal"],
        counts["freshness_advanced"],
        counts["candidate_slice_fallback_prefix"],
    )
    return counts


def main() -> int:
    _configure_cli_logging()
    run_entity_backfill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
