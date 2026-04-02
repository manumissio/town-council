from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count, get_context
import logging

from pipeline.config import MAX_WORKERS, PIPELINE_CPU_FRACTION
from pipeline.db_session import db_session
from pipeline.models import Catalog
from pipeline.run_pipeline import (
    PIPELINE_ONBOARDING_CITY,
    _resolve_parallel_processing_settings,
    select_catalog_ids_for_entity_backfill,
)


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("entity-backfill")


def process_entity_chunk(catalog_ids):
    from pipeline.db_session import db_session
    from pipeline.models import Catalog
    from pipeline.nlp_worker import extract_entities

    processed = 0
    with db_session() as session:
        for catalog_id in catalog_ids:
            record = session.get(Catalog, catalog_id)
            if not record or not record.content:
                continue
            if record.entities is not None:
                continue
            record.entities = extract_entities(record.content)
            session.commit()
            processed += 1
    return processed


def run_entity_backfill():
    with db_session() as db:
        catalog_ids = select_catalog_ids_for_entity_backfill(db)

    counts = {
        "selected": len(catalog_ids),
        "complete": 0,
    }

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
    with ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn")) as executor:
        futures = {executor.submit(process_entity_chunk, chunk): chunk for chunk in chunks}
        for future in as_completed(futures):
            count = future.result()
            if count:
                completed += count
                logger.info("Entity backfill progress: %s/%s", completed, len(catalog_ids))
    counts["complete"] = completed
    logger.info(
        "entity_backfill selected=%s complete=%s",
        counts["selected"],
        counts["complete"],
    )
    return counts


if __name__ == "__main__":
    run_entity_backfill()
