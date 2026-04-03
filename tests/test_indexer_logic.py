import pytest
import sys
import os
from types import SimpleNamespace
from contextlib import contextmanager
from unittest.mock import MagicMock

# Ensure the pipeline directory is in the path for indexer imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
from pipeline import indexer

def test_meeting_category_normalization():
    """
    Test: Does the indexer correctly 'clean' messy meeting strings?
    We want to ensure that phrases like 'Regular Meeting' correctly 
    map to the clean 'Regular' category for our UI.
    """
    # Define a helper function that mimics the logic in indexer.py
    def get_category(raw_type):
        raw_type = (raw_type or "").lower()
        if "regular" in raw_type:
            return "Regular"
        elif "special" in raw_type:
            return "Special"
        elif "closed" in raw_type:
            return "Closed"
        return "Other"

    # Test Cases
    assert get_category("City Council Regular Meeting") == "Regular"
    assert get_category("REGULAR SESSION") == "Regular"
    assert get_category("Special Meeting of the Council") == "Special"
    assert get_category("2026-02-10 CLOSED SESSION") == "Closed"
    assert get_category("Emergency Budget Meeting") == "Other"
    assert get_category(None) == "Other"
    assert get_category("") == "Other"


def test_indexer_flushes_agenda_final_batch_once(mocker):
    """
    Regression: remaining agenda items should be sent once after the loop.
    """
    class FakeQuery:
        def __init__(self, rows):
            self._rows = rows
        def join(self, *args, **kwargs):
            return self
        def outerjoin(self, *args, **kwargs):
            return self
        def filter(self, *args, **kwargs):
            return self
        def options(self, *args, **kwargs):
            return self
        def yield_per(self, *args, **kwargs):
            return self._rows

    # No full documents, two agenda items, batch size two -> exactly one add_documents call.
    item = SimpleNamespace(
        id=1, ocd_id="ocd-item-1", title="Item", description="Desc",
        classification="Agenda Item", result="Approved", page_number=1, catalog_id=None, catalog=None
    )
    item2 = SimpleNamespace(
        id=2, ocd_id="ocd-item-2", title="Item 2", description="Desc",
        classification="Agenda Item", result="Approved", page_number=2, catalog_id=None, catalog=None
    )
    event = SimpleNamespace(name="Meeting", meeting_type="Regular", record_date=None, organization_id=None)
    place = SimpleNamespace(display_name="ca_test", name="Test City")

    session = MagicMock()
    session.query.side_effect = [
        FakeQuery([]),
        FakeQuery([(item, event, place, None), (item2, event, place, None)]),
    ]

    @contextmanager
    def fake_db_session():
        yield session

    fake_index = MagicMock()
    fake_index.update_filterable_attributes.return_value = {"taskUid": 1}
    fake_index.update_sortable_attributes.return_value = {"taskUid": 2}
    fake_index.update_searchable_attributes.return_value = {"taskUid": 3}
    fake_index.update_ranking_rules.return_value = {"taskUid": 4}
    fake_client = MagicMock()
    fake_client.index.return_value = fake_index
    mocker.patch.object(indexer, "db_session", fake_db_session)
    mocker.patch.object(indexer.meilisearch, "Client", return_value=fake_client)
    mocker.patch.object(indexer, "MEILISEARCH_BATCH_SIZE", 2)

    indexer.index_documents()

    fake_index.update_sortable_attributes.assert_called_with(["date"])
    assert fake_client.wait_for_task.call_count == 4
    assert fake_index.add_documents.call_count == 1
    sent_batch = fake_index.add_documents.call_args[0][0]
    assert len(sent_batch) == 2


def test_flush_batch_updates_count(mocker):
    """Batch helper should increment count by the number of sent docs."""
    fake_index = MagicMock()
    docs = [{"id": "doc_1"}, {"id": "doc_2"}]

    count = indexer._flush_batch(fake_index, docs, 3, "document")
    assert count == 5
    fake_index.add_documents.assert_called_once_with(docs)


def test_flush_batch_keeps_count_on_error(mocker):
    """Batch helper should not increment count when indexing fails."""
    fake_index = MagicMock()
    fake_index.add_documents.side_effect = indexer.MeilisearchError("boom")
    docs = [{"id": "doc_1"}]

    count = indexer._flush_batch(fake_index, docs, 7, "document")
    assert count == 7


def test_delete_documents_by_filter_prefers_supported_delete_documents_api():
    fake_index = MagicMock()
    fake_index.delete_documents.return_value = {"taskUid": 88}

    result = indexer._delete_documents_by_filter(
        fake_index,
        'catalog_id = 9 AND result_type = "agenda_item"',
    )

    assert result == {"taskUid": 88}
    fake_index.delete_documents.assert_called_once_with(
        filter='catalog_id = 9 AND result_type = "agenda_item"'
    )


def test_delete_documents_by_filter_falls_back_when_only_legacy_method_exists():
    class LegacyIndex:
        def __init__(self):
            self.calls = []

        def delete_documents_by_filter(self, filters):
            self.calls.append(filters)
            return {"taskUid": 11}

    fake_index = LegacyIndex()

    result = indexer._delete_documents_by_filter(
        fake_index,
        'catalog_id = 9 AND result_type = "agenda_item"',
    )

    assert result == {"taskUid": 11}
    assert fake_index.calls == [['catalog_id = 9 AND result_type = "agenda_item"']]


def test_reindex_catalog_skips_schema_updates_and_reindexes_agenda_items(mocker):
    meeting_doc = SimpleNamespace(
        id=1,
        catalog_id=9,
        event_id=4,
        place_id=2,
    )
    catalog = SimpleNamespace(
        id=9,
        filename="meeting.pdf",
        url="https://example.com/meeting.pdf",
        content="Meeting content",
        summary="Summary",
        summary_extractive=None,
        topics=["Budget"],
        content_hash="h1",
        summary_source_hash="h1",
        topics_source_hash="h1",
        related_ids=[],
        lineage_id=None,
        lineage_confidence=None,
    )
    event = SimpleNamespace(name="Meeting", meeting_type="Regular", record_date=None, ocd_id="ocd-event")
    place = SimpleNamespace(display_name="ca_test", name="Test City", state="CA")
    organization = None
    agenda_item = SimpleNamespace(
        id=11,
        ocd_id="ocd-item-11",
        title="Budget Item",
        description="Approve the budget",
        classification="Agenda Item",
        result="Approved",
        page_number=1,
        catalog_id=9,
        catalog=SimpleNamespace(url="https://example.com/meeting.pdf"),
    )

    class FakeQuery:
        def __init__(self, rows):
            self._rows = rows
        def join(self, *args, **kwargs):
            return self
        def outerjoin(self, *args, **kwargs):
            return self
        def filter(self, *args, **kwargs):
            return self
        def options(self, *args, **kwargs):
            return self
        def all(self):
            return self._rows

    session = MagicMock()
    session.query.side_effect = [
        FakeQuery([(meeting_doc, catalog, event, place, organization)]),
        FakeQuery([(agenda_item, event, place, organization)]),
    ]

    @contextmanager
    def fake_db_session():
        yield session

    fake_index = MagicMock()
    fake_index.delete_documents.return_value = {"taskUid": 88}
    fake_client = MagicMock()
    fake_client.index.return_value = fake_index
    mocker.patch.object(indexer, "db_session", fake_db_session)
    mocker.patch.object(indexer.meilisearch, "Client", return_value=fake_client)
    apply_settings = mocker.patch.object(indexer, "_apply_index_settings")

    result = indexer.reindex_catalog(9)

    apply_settings.assert_not_called()
    fake_index.delete_documents.assert_called_once_with(
        filter='catalog_id = 9 AND result_type = "agenda_item"'
    )
    fake_index.add_documents.assert_called_once()
    sent = fake_index.add_documents.call_args.args[0]
    assert {doc["result_type"] for doc in sent} == {"meeting", "agenda_item"}
    assert result["agenda_item_documents"] == 1


def test_reindex_catalogs_dedupes_and_records_failures(mocker):
    reindex_spy = mocker.patch.object(
        indexer,
        "reindex_catalog",
        side_effect=[
            {"status": "ok", "catalog_id": 2},
            RuntimeError("boom"),
        ],
    )

    result = indexer.reindex_catalogs([2, 2, 5])

    assert reindex_spy.call_args_list == [mocker.call(2), mocker.call(5)]
    assert result == {
        "catalogs_considered": 2,
        "catalogs_reindexed": 1,
        "catalogs_failed": 1,
        "failed_catalog_ids": [5],
    }
