import logging

from sqlalchemy import or_

from pipeline.config import PROGRESS_LOG_INTERVAL
from pipeline.content_hash import compute_content_hash
from pipeline.db_session import db_session
from pipeline.models import Catalog, Document
from pipeline.profiling import apply_catalog_id_scope
from pipeline.topic_generation import (
    CITY_STOP_WORDS,
    TopicWorkerServices,
    _sanitize_text_for_topics,
    run_topic_tagger_family,
)


LOGGER_NAME = "topic-worker"
LOGGER_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

logger = logging.getLogger(LOGGER_NAME)

__all__ = [
    "CITY_STOP_WORDS",
    "_sanitize_text_for_topics",
    "run_keyword_tagger",
    "run_topic_tagger",
    "run_topic_hydration_backfill",
    "select_catalog_ids_for_topic_hydration",
]


def _configure_cli_logging() -> None:
    """Keep logging setup at the entrypoint so imports stay side-effect free."""
    logging.basicConfig(level=logging.INFO, format=LOGGER_FORMAT)


def _topic_worker_services() -> TopicWorkerServices:
    from pipeline import indexer

    return TopicWorkerServices(
        catalog_model=Catalog,
        compute_content_hash=compute_content_hash,
        apply_catalog_id_scope=apply_catalog_id_scope,
        reindex_catalogs=indexer.reindex_catalogs,
        logger=logger,
    )


def run_keyword_tagger():
    """
    Alias for run_topic_tagger to match test expectations.
    """
    run_topic_tagger()


def select_catalog_ids_for_topic_hydration(session, limit: int | None = None) -> list[int]:
    query = (
        session.query(Catalog.id)
        .join(Document, Document.catalog_id == Catalog.id)
        .filter(Catalog.content.isnot(None), Catalog.content != "")
        .filter(
            or_(
                Catalog.topics.is_(None),
                Catalog.content_hash.is_(None),
                Catalog.topics_source_hash.is_(None),
                Catalog.topics_source_hash != Catalog.content_hash,
            )
        )
        .order_by(Catalog.id)
        .distinct()
    )
    query = apply_catalog_id_scope(query, Catalog.id)
    if limit is not None:
        query = query.limit(limit)
    return [int(row[0]) for row in query.all()]


def run_topic_hydration_backfill(
    *,
    force: bool = True,
    limit: int | None = None,
    max_corpus_docs: int = 600,
    catalog_ids: list[int] | None = None,
) -> dict[str, int]:
    if catalog_ids is None:
        with db_session() as session:
            catalog_ids = select_catalog_ids_for_topic_hydration(session, limit=limit)

    catalog_ids = [int(catalog_id) for catalog_id in catalog_ids]
    counts = {
        "selected": len(catalog_ids),
        "complete": 0,
        "cached": 0,
        "stale": 0,
        "blocked_low_signal": 0,
        "error": 0,
        "other": 0,
    }
    if not catalog_ids:
        logger.info("topic_hydration_backfill selected=0")
        return counts

    from pipeline.enrichment_tasks import generate_topics_task

    for index, catalog_id in enumerate(catalog_ids, start=1):
        try:
            topic_payload = generate_topics_task.run(
                catalog_id,
                force=force,
                max_corpus_docs=max_corpus_docs,
            )
        except Exception as topic_error:
            # One failed catalog should not block hydration for the rest of the backlog.
            counts["error"] += 1
            logger.warning(
                "topic_hydration catalog_id=%s status=error error=%s",
                catalog_id,
                topic_error,
                exc_info=True,
            )
            continue

        status = str((topic_payload or {}).get("status") or "").strip() or (
            "error" if (topic_payload or {}).get("error") else "other"
        )
        if status in counts:
            counts[status] += 1
        else:
            counts["other"] += 1
        if index == 1 or index % PROGRESS_LOG_INTERVAL == 0 or index == len(catalog_ids):
            logger.info(
                "topic_hydration_backfill progress=%s/%s last_catalog_id=%s last_status=%s",
                index,
                len(catalog_ids),
                catalog_id,
                status,
            )

    logger.info(
        "topic_hydration_backfill selected=%s complete=%s cached=%s stale=%s blocked_low_signal=%s error=%s other=%s",
        counts["selected"],
        counts["complete"],
        counts["cached"],
        counts["stale"],
        counts["blocked_low_signal"],
        counts["error"],
        counts["other"],
    )
    return counts


def run_topic_tagger():
    """
    Automated Topic Discovery using TF-IDF.
    """
    with db_session() as session:
        run_topic_tagger_family(session, services=_topic_worker_services())


def main() -> int:
    _configure_cli_logging()
    run_topic_tagger()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
