from typing import Protocol

from pipeline.agenda_summary_maintenance import AGENDA_SUMMARY_EMBED_DISPATCH_ERRORS
from pipeline.task_runtime import logger
from pipeline.task_side_effects import REINDEX_FAILURE_EXCEPTIONS


class SummarySideEffectServices(Protocol):
    def reindex_catalog(self, catalog_id: int) -> object: ...

    def embed_catalog(self, catalog_id: int) -> object: ...


def run_summary_generation_side_effects(
    catalog_id: int,
    *,
    services: SummarySideEffectServices,
) -> dict[str, int]:
    """
    Summary persistence is authoritative; search and embedding updates are best-effort.
    """
    reindexed = 0
    reindex_failed = 0
    try:
        services.reindex_catalog(catalog_id)
        reindexed = 1
    except REINDEX_FAILURE_EXCEPTIONS as reindex_error:
        reindex_failed = 1
        logger.warning("summary_generation.reindex_failed catalog_id=%s error=%s", catalog_id, reindex_error)

    embed_enqueued = 0
    embed_dispatch_failed = 0
    try:
        services.embed_catalog(catalog_id)
        embed_enqueued = 1
    except AGENDA_SUMMARY_EMBED_DISPATCH_ERRORS as dispatch_error:
        logger.warning("embed_catalog_task.dispatch_failed catalog_id=%s error=%s", catalog_id, dispatch_error)
        embed_dispatch_failed = 1

    return {
        "reindexed": reindexed,
        "reindex_failed": reindex_failed,
        "embed_enqueued": embed_enqueued,
        "embed_dispatch_failed": embed_dispatch_failed,
    }
