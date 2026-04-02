from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count, get_context
import logging

from pipeline.config import ENTITY_BACKFILL_IN_PROCESS_THRESHOLD, MAX_WORKERS, PIPELINE_CPU_FRACTION
from pipeline.db_session import db_session
from pipeline.run_pipeline import (
    PIPELINE_ONBOARDING_CITY,
    _resolve_parallel_processing_settings,
    select_catalog_ids_for_entity_backfill,
)


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("entity-backfill")


def _empty_counts():
    return {
        "selected": 0,
        "complete": 0,
        "changed_catalogs": 0,
        "updated_catalog_ids": [],
        "execution_mode": "noop",
        "chunks": 0,
    }


def process_entity_chunk(catalog_ids):
    from pipeline.db_session import db_session
    from pipeline.models import Catalog
    from pipeline.nlp_worker import extract_entities

    processed = 0
    updated_catalog_ids = []
    with db_session() as session:
        for catalog_id in catalog_ids:
            record = session.get(Catalog, catalog_id)
            if not record or not record.content:
                continue
            if record.entities is not None:
                continue
            extracted_entities = extract_entities(record.content)
            if extracted_entities == record.entities:
                continue
            record.entities = extracted_entities
            updated_catalog_ids.append(catalog_id)
            processed += 1
        if updated_catalog_ids:
            session.commit()
    return {
        "complete": processed,
        "updated_catalog_ids": updated_catalog_ids,
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
    execution_mode = "in_process" if len(catalog_ids) <= ENTITY_BACKFILL_IN_PROCESS_THRESHOLD else "process_pool"
    if execution_mode == "in_process":
        for chunk in chunks:
            chunk_result = process_entity_chunk(chunk)
            count = int(chunk_result.get("complete", 0))
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
                if count:
                    completed += count
                    updated_catalog_ids.extend(int(cid) for cid in chunk_result.get("updated_catalog_ids", []))
                    logger.info("Entity backfill progress: %s/%s", completed, len(catalog_ids))
    counts["complete"] = completed
    counts["updated_catalog_ids"] = sorted(set(updated_catalog_ids))
    counts["changed_catalogs"] = len(counts["updated_catalog_ids"])
    counts["execution_mode"] = execution_mode
    counts["chunks"] = len(chunks)
    logger.info(
        "entity_backfill selected=%s complete=%s changed_catalogs=%s execution_mode=%s chunks=%s",
        counts["selected"],
        counts["complete"],
        counts["changed_catalogs"],
        counts["execution_mode"],
        counts["chunks"],
    )
    return counts


if __name__ == "__main__":
    run_entity_backfill()
