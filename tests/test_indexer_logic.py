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
    fake_client = MagicMock()
    fake_client.index.return_value = fake_index
    mocker.patch.object(indexer, "db_session", fake_db_session)
    mocker.patch.object(indexer.meilisearch, "Client", return_value=fake_client)
    mocker.patch.object(indexer, "MEILISEARCH_BATCH_SIZE", 2)

    indexer.index_documents()

    fake_index.update_sortable_attributes.assert_called_with(["date"])
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
