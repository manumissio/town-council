import logging

from meilisearch.errors import MeilisearchError

logger = logging.getLogger("indexer")


def _flush_batch(index, documents_batch, count, label):
    """Send one batch to Meilisearch and update the indexed count."""
    if not documents_batch:
        return count
    try:
        index.add_documents(documents_batch)
        return count + len(documents_batch)
    except MeilisearchError as exc:
        print(f"Error indexing {label} batch: {exc}")
        return count


def _task_uid(task_result) -> int | None:
    if isinstance(task_result, dict):
        return task_result.get("taskUid") or task_result.get("uid")
    return None


def _delete_documents_by_filter(index, filter_expr: str):
    """
    Meilisearch SDK compatibility wrapper for filtered deletes.

    Why this exists:
    The repo pins meilisearch==0.31.0, whose Python client supports
    `delete_documents(filter=...)` but does not expose
    `delete_documents_by_filter(...)`. Centralizing the compatibility branch keeps
    targeted reindexing durable across minor SDK surface differences.
    """
    if hasattr(index, "delete_documents"):
        return index.delete_documents(filter=filter_expr)
    if hasattr(index, "delete_documents_by_filter"):
        return index.delete_documents_by_filter([filter_expr])
    raise RuntimeError("Meilisearch client does not support filtered document deletion")


def _apply_index_settings(client, index) -> None:
    """
    Apply Meilisearch index settings and wait for completion.

    Why:
    Settings updates are asynchronous in Meilisearch. If we don't wait, users can
    observe confusing behavior (for example, sort being rejected immediately after reindex).
    """
    task_ids = []

    task_ids.append(
        _task_uid(
            index.update_filterable_attributes(
                [
                    "city",
                    "meeting_type",
                    "meeting_category",
                    "organization",
                    "people",
                    "date",
                    "organizations",
                    "result_type",
                    "topics",
                    "lineage_id",
                    "catalog_id",
                ]
            )
        )
    )
    task_ids.append(_task_uid(index.update_sortable_attributes(["date"])))
    task_ids.append(
        _task_uid(
            index.update_searchable_attributes(
                [
                    "content",
                    "event_name",
                    "title",
                    "description",
                    "filename",
                    "summary",
                    "organizations",
                    "locations",
                    "meeting_category",
                    "organization",
                    "people",
                ]
            )
        )
    )
    task_ids.append(
        _task_uid(index.update_ranking_rules(["sort", "words", "typo", "proximity", "attribute", "exactness"]))
    )

    for uid in [task_id for task_id in task_ids if isinstance(task_id, int)]:
        try:
            client.wait_for_task(uid)
        except Exception as settings_wait_error:
            # Settings still apply asynchronously; this wait improves deterministic maintenance paths.
            logger.warning("search_index.settings_wait_failed task_id=%s error=%s", uid, settings_wait_error)
