import logging
import os
from collections.abc import Iterable

import meilisearch
from meilisearch.errors import MeilisearchError
from meilisearch.index import Index
from sqlalchemy.orm import Session, selectinload

from pipeline.config import MEILISEARCH_BATCH_SIZE
from pipeline.db_session import db_session
from pipeline.indexer_documents import (
    _build_agenda_item_search_doc as _build_agenda_item_search_doc_impl,
    _build_meeting_search_doc as _build_meeting_search_doc_impl,
    _meeting_category as _meeting_category,
    _select_official_memberships_for_event as _select_official_memberships_for_event,
    _strip_any_html as _strip_any_html,
    _truncate_content_for_index,
)
from pipeline.indexer_meilisearch import (
    _apply_index_settings,
    _clear_documents_index,
    _delete_documents_by_filter,
    _flush_batch,
    INDEX_ALREADY_EXISTS_ERROR_CODE,
    _task_uid,
    _verify_documents_index_settings,
    _wait_for_documents_index_idle,
    _wait_for_task_success,
)
from pipeline.models import AgendaItem, Catalog, Document, Event, Membership, Organization, Place

# Configuration for connecting to the Meilisearch search engine.
MEILI_HOST = os.getenv("MEILI_HOST", "http://meilisearch:7700")
MEILI_MASTER_KEY = os.getenv("MEILI_MASTER_KEY", "masterKey")

logger = logging.getLogger("indexer")
MEILISEARCH_MAINTENANCE_REQUEST_TIMEOUT_SECONDS = 30


def _report_document_truncation(
    source_document_count: int,
    truncated_document_count: int,
) -> None:
    """Expose truncation coverage without affecting recovery count checks."""
    if not source_document_count:
        return
    truncation_rate = truncated_document_count / source_document_count * 100
    print(
        "Document truncation summary: "
        f"{truncated_document_count}/{source_document_count} "
        f"({truncation_rate:.1f}%) meeting docs truncated"
    )


def _build_meeting_search_doc(doc, catalog, event, place, organization) -> dict:
    # Resolve helpers through this facade so existing monkeypatch seams stay live.
    return _build_meeting_search_doc_impl(
        doc,
        catalog,
        event,
        place,
        organization,
        content_truncator=_truncate_content_for_index,
        membership_selector=_select_official_memberships_for_event,
        meeting_category_resolver=_meeting_category,
    )


def _build_agenda_item_search_doc(item, event, place, organization) -> dict:
    # Resolve helpers through this facade so existing monkeypatch seams stay live.
    return _build_agenda_item_search_doc_impl(
        item,
        event,
        place,
        organization,
        html_stripper=_strip_any_html,
        meeting_category_resolver=_meeting_category,
    )


def _ensure_documents_index(
    client,
    *,
    apply_settings: bool,
    wait_for_creation: bool = False,
):
    try:
        creation_task = client.create_index("documents", {"primaryKey": "id"})
    except MeilisearchError:
        if wait_for_creation:
            raise
    else:
        if wait_for_creation:
            _wait_for_task_success(
                client,
                creation_task.task_uid,
                "index creation",
                accepted_failure_code=INDEX_ALREADY_EXISTS_ERROR_CODE,
            )
    index = client.index("documents")
    if apply_settings:
        _apply_index_settings(client, index)
    return index


def _document_rows(session):
    return (
        session.query(Document, Catalog, Event, Place, Organization)
        .join(Catalog, Document.catalog_id == Catalog.id)
        .join(Event, Document.event_id == Event.id)
        .join(Place, Document.place_id == Place.id)
        .outerjoin(Organization, Event.organization_id == Organization.id)
        .filter(Catalog.content.isnot(None), Catalog.content != "")
        .options(selectinload(Organization.memberships).selectinload(Membership.person))
        .yield_per(20)
    )


def _agenda_item_rows(session):
    return (
        session.query(AgendaItem, Event, Place, Organization)
        .join(Event, AgendaItem.event_id == Event.id)
        .join(Place, Event.place_id == Place.id)
        .outerjoin(Organization, Event.organization_id == Organization.id)
        .yield_per(100)
    )


def _catalog_document_rows(session, catalog_id: int):
    return (
        session.query(Document, Catalog, Event, Place, Organization)
        .join(Catalog, Document.catalog_id == Catalog.id)
        .join(Event, Document.event_id == Event.id)
        .join(Place, Document.place_id == Place.id)
        .outerjoin(Organization, Event.organization_id == Organization.id)
        .filter(Catalog.id == catalog_id)
        .options(selectinload(Organization.memberships).selectinload(Membership.person))
        .all()
    )


def _catalog_agenda_item_rows(session, catalog_id: int):
    return (
        session.query(AgendaItem, Event, Place, Organization)
        .join(Event, AgendaItem.event_id == Event.id)
        .join(Place, Event.place_id == Place.id)
        .outerjoin(Organization, Event.organization_id == Organization.id)
        .filter(AgendaItem.catalog_id == catalog_id)
        .all()
    )


def _index_meeting_documents(session: Session, index: Index) -> tuple[int, int]:
    """Index meeting records and retain the source count for recovery checks."""
    documents_batch = []
    submitted_document_count = 0
    source_document_count = 0
    truncated_document_count = 0

    print("Step 1: Indexing Full Meeting Documents...")
    for document, catalog, event, place, organization in _document_rows(session):
        source_document_count += 1
        _, content_truncated, _, _ = _truncate_content_for_index(catalog.content)
        truncated_document_count += int(content_truncated)
        documents_batch.append(
            _build_meeting_search_doc(
                document,
                catalog,
                event,
                place,
                organization,
            )
        )
        if len(documents_batch) >= MEILISEARCH_BATCH_SIZE:
            submitted_document_count = _flush_batch(
                index,
                documents_batch,
                submitted_document_count,
                "document",
            )
            documents_batch = []

    submitted_document_count = _flush_batch(
        index,
        documents_batch,
        submitted_document_count,
        "document",
    )
    _report_document_truncation(source_document_count, truncated_document_count)
    return submitted_document_count, source_document_count


def _index_agenda_items(session: Session, index: Index) -> tuple[int, int]:
    """Index agenda items and retain the source count for recovery checks."""
    agenda_batch = []
    submitted_agenda_count = 0
    source_agenda_count = 0

    print("Step 2: Indexing Individual Agenda Items...")
    for agenda_item, event, place, organization in _agenda_item_rows(session):
        source_agenda_count += 1
        agenda_batch.append(
            _build_agenda_item_search_doc(
                agenda_item,
                event,
                place,
                organization,
            )
        )
        if len(agenda_batch) >= MEILISEARCH_BATCH_SIZE:
            submitted_agenda_count = _flush_batch(
                index,
                agenda_batch,
                submitted_agenda_count,
                "agenda item",
            )
            agenda_batch = []

    submitted_agenda_count = _flush_batch(
        index,
        agenda_batch,
        submitted_agenda_count,
        "agenda item",
    )
    return submitted_agenda_count, source_agenda_count


def _index_documents_with_client(client: meilisearch.Client) -> int:
    """Index the PostgreSQL corpus through the caller's Meilisearch policy."""
    index = _ensure_documents_index(client, apply_settings=True)
    with db_session() as session:
        submitted_document_count, source_document_count = (
            _index_meeting_documents(session, index)
        )
        submitted_agenda_count, source_agenda_count = _index_agenda_items(
            session,
            index,
        )

    submitted_record_count = submitted_document_count + submitted_agenda_count
    print(f"Indexing complete. Total records indexed: {submitted_record_count}")
    return source_document_count + source_agenda_count


def index_documents() -> int:
    """Sync processed meetings and agenda items into Meilisearch."""
    print(f"Connecting to Meilisearch at {MEILI_HOST}...")
    client = meilisearch.Client(MEILI_HOST, MEILI_MASTER_KEY)
    return _index_documents_with_client(client)


def replace_documents_index() -> None:
    """Replace search state from PostgreSQL and reject incomplete rebuilds."""
    client = meilisearch.Client(
        MEILI_HOST,
        MEILI_MASTER_KEY,
        timeout=MEILISEARCH_MAINTENANCE_REQUEST_TIMEOUT_SECONDS,
    )
    index = _ensure_documents_index(
        client,
        apply_settings=False,
        wait_for_creation=True,
    )
    _clear_documents_index(client, index)
    expected_document_count = _index_documents_with_client(client)
    _wait_for_documents_index_idle(client)
    _verify_documents_index_settings(index)
    actual_document_count = int(index.get_stats().number_of_documents)
    if actual_document_count != expected_document_count:
        raise RuntimeError(
            "Meilisearch replacement count mismatch "
            f"expected={expected_document_count} actual={actual_document_count}"
        )


def reindex_catalog(catalog_id: int) -> dict:
    """
    Reindex a single catalog into Meilisearch.

    Why this exists:
    Some operations (like re-extracting text for one PDF) should update search
    without reindexing the entire dataset.
    """
    client = meilisearch.Client(MEILI_HOST, MEILI_MASTER_KEY)
    index = _ensure_documents_index(client, apply_settings=False)

    with db_session() as session:
        docs = _catalog_document_rows(session, catalog_id)
        if not docs:
            return {"status": "skipped", "reason": "No documents linked to catalog", "catalog_id": catalog_id}

        payload = [
            _build_meeting_search_doc(doc, catalog, event, place, org) for doc, catalog, event, place, org in docs
        ]
        item_docs = _catalog_agenda_item_rows(session, catalog_id)
        for item, event, place, organization in item_docs:
            payload.append(_build_agenda_item_search_doc(item, event, place, organization))

        delete_task = _delete_documents_by_filter(
            index, f'catalog_id = {int(catalog_id)} AND result_type = "agenda_item"'
        )
        delete_uid = _task_uid(delete_task)
        if isinstance(delete_uid, int):
            client.wait_for_task(delete_uid)
        if payload:
            index.add_documents(payload)

    return {
        "status": "ok",
        "catalog_id": catalog_id,
        "documents_reindexed": len(payload),
        "agenda_item_documents": len(item_docs),
    }


def reindex_catalogs(catalog_ids: Iterable[int] | int | None) -> dict[str, object]:
    """
    Best-effort helper for backlog/batch flows that touch many catalogs.

    Why this exists:
    Batch writers often mutate search-visible fields for a bounded set of catalogs.
    Reindexing only those catalogs keeps search fresh without forcing a full rebuild.
    """
    if catalog_ids is None:
        return {"catalogs_considered": 0, "catalogs_reindexed": 0, "catalogs_failed": 0, "failed_catalog_ids": []}

    if isinstance(catalog_ids, int):
        deduped_ids = [int(catalog_ids)]
    else:
        deduped_ids = sorted({int(cid) for cid in catalog_ids if cid is not None})

    failed_catalog_ids: list[int] = []
    reindexed = 0
    for catalog_id in deduped_ids:
        try:
            result = reindex_catalog(catalog_id)
            if result.get("status") == "ok":
                reindexed += 1
            else:
                failed_catalog_ids.append(catalog_id)
        except Exception as exc:
            logger.warning("targeted_reindex_failed catalog_id=%s error=%s", catalog_id, exc)
            failed_catalog_ids.append(catalog_id)

    return {
        "catalogs_considered": len(deduped_ids),
        "catalogs_reindexed": reindexed,
        "catalogs_failed": len(failed_catalog_ids),
        "failed_catalog_ids": failed_catalog_ids,
    }


if __name__ == "__main__":
    index_documents()
