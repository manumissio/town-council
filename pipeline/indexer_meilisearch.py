import time

from meilisearch import Client
from meilisearch.errors import MeilisearchError
from meilisearch.index import Index

DOCUMENTS_INDEX_UID = "documents"
INDEX_IDLE_TIMEOUT_SECONDS = 300.0
INDEX_IDLE_POLL_SECONDS = 0.25
INDEX_TASK_TIMEOUT_MS = 300_000
INDEX_TASK_POLL_INTERVAL_MS = 250
INDEX_ALREADY_EXISTS_ERROR_CODE = "index_already_exists"
FILTERABLE_ATTRIBUTES = (
    "city",
    "meeting_type",
    "meeting_category",
    "organization",
    "date",
    "organizations",
    "result_type",
    "topics",
    "lineage_id",
    "catalog_id",
)
SORTABLE_ATTRIBUTES = ("date",)
SEARCHABLE_ATTRIBUTES = (
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
)
RANKING_RULES = ("sort", "words", "typo", "proximity", "attribute", "exactness")


def _wait_for_task_success(
    client: Client,
    task_uid: int,
    operation: str,
    *,
    accepted_failure_code: str | None = None,
) -> None:
    """Keep recovery steps ordered and reject failed asynchronous work."""
    completed_task = client.wait_for_task(
        task_uid,
        timeout_in_ms=INDEX_TASK_TIMEOUT_MS,
        interval_in_ms=INDEX_TASK_POLL_INTERVAL_MS,
    )
    if completed_task.status == "succeeded":
        return
    if accepted_failure_code is not None:
        completed_error = completed_task.error or {}
        if completed_error.get("code") == accepted_failure_code:
            return
    raise RuntimeError(
        f"Meilisearch {operation} failed status={completed_task.status}"
    )


def _clear_documents_index(client: Client, index: Index) -> None:
    """Remove the old corpus before a recovery rebuild can publish new rows."""
    deletion_task = index.delete_all_documents()
    _wait_for_task_success(
        client,
        deletion_task.task_uid,
        "document deletion",
    )


def _wait_for_documents_index_idle(client: Client) -> None:
    """Keep recovery traffic stopped until every documents-index task finishes."""
    deadline = time.monotonic() + INDEX_IDLE_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        pending_tasks = client.get_tasks(
            {
                "statuses": ["enqueued", "processing"],
                "indexUids": [DOCUMENTS_INDEX_UID],
            }
        )
        if not pending_tasks.results:
            return
        time.sleep(INDEX_IDLE_POLL_SECONDS)
    raise TimeoutError("Meilisearch documents index did not become idle")


def _verify_documents_index_settings(index: Index) -> None:
    """Reject a recovery rebuild that lacks the search contract users rely on."""
    documents_index_settings = (
        (
            "filterable_attributes",
            list(FILTERABLE_ATTRIBUTES),
            index.get_filterable_attributes(),
        ),
        (
            "sortable_attributes",
            list(SORTABLE_ATTRIBUTES),
            index.get_sortable_attributes(),
        ),
        (
            "searchable_attributes",
            list(SEARCHABLE_ATTRIBUTES),
            index.get_searchable_attributes(),
        ),
        ("ranking_rules", list(RANKING_RULES), index.get_ranking_rules()),
    )
    setting_mismatches = [
        f"{setting_name}=expected:{expected_value!r},actual:{actual_value!r}"
        for setting_name, expected_value, actual_value in documents_index_settings
        if actual_value != expected_value
    ]
    if setting_mismatches:
        raise RuntimeError(
            "Meilisearch replacement settings mismatch "
            + "; ".join(setting_mismatches)
        )


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


def _apply_index_settings(client: Client, index: Index) -> None:
    """Publish each search setting only after Meilisearch confirms success."""
    filterable_task = index.update_filterable_attributes(
        list(FILTERABLE_ATTRIBUTES)
    )
    _wait_for_task_success(
        client,
        filterable_task.task_uid,
        "filterable attribute settings",
    )

    sortable_task = index.update_sortable_attributes(list(SORTABLE_ATTRIBUTES))
    _wait_for_task_success(
        client,
        sortable_task.task_uid,
        "sortable attribute settings",
    )

    searchable_task = index.update_searchable_attributes(
        list(SEARCHABLE_ATTRIBUTES)
    )
    _wait_for_task_success(
        client,
        searchable_task.task_uid,
        "searchable attribute settings",
    )

    ranking_task = index.update_ranking_rules(list(RANKING_RULES))
    _wait_for_task_success(
        client,
        ranking_task.task_uid,
        "ranking rule settings",
    )
