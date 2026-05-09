from pipeline.semantic_tasks import embed_catalog_task
from pipeline.task_runtime import logger


def enqueue_embed_catalogs(catalog_ids: list[int]) -> dict[str, object]:
    deduped_ids = sorted({int(catalog_id) for catalog_id in catalog_ids if catalog_id is not None})
    failed_catalog_ids: list[int] = []
    enqueued = 0
    for catalog_id in deduped_ids:
        try:
            embed_catalog_task.delay(catalog_id)
            enqueued += 1
        except Exception as exc:
            # Embed dispatch is best-effort here because summary writes are already durable.
            logger.warning("embed_catalog_task.dispatch_failed catalog_id=%s error=%s", catalog_id, exc)
            failed_catalog_ids.append(catalog_id)
    return {
        "catalogs_considered": len(deduped_ids),
        "embed_enqueued": enqueued,
        "embed_dispatch_failed": len(failed_catalog_ids),
        "failed_catalog_ids": failed_catalog_ids,
    }
