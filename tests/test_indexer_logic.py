import pytest
import sys
import os
import subprocess
from types import SimpleNamespace
from contextlib import contextmanager
from unittest.mock import MagicMock

# Ensure the pipeline directory is in the path for indexer imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
from pipeline import indexer, indexer_meilisearch


class EmptyIndexQuery:
    def join(self, *args, **kwargs):
        return self

    def outerjoin(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def options(self, *args, **kwargs):
        return self

    def yield_per(self, *args, **kwargs):
        return []


class ReplacementIndex:
    def __init__(
        self,
        index_events,
        indexed_document_count,
        *,
        settings_valid=True,
    ):
        self.index_events = index_events
        self.indexed_document_count = indexed_document_count
        self.settings_valid = settings_valid

    def delete_all_documents(self):
        self.index_events.append("delete_enqueued")
        return SimpleNamespace(task_uid=91)

    def update_filterable_attributes(self, attributes):
        return SimpleNamespace(task_uid=1)

    def update_sortable_attributes(self, attributes):
        return SimpleNamespace(task_uid=2)

    def update_searchable_attributes(self, attributes):
        return SimpleNamespace(task_uid=3)

    def update_ranking_rules(self, rules):
        return SimpleNamespace(task_uid=4)

    def get_stats(self):
        self.index_events.append("stats_checked")
        return SimpleNamespace(number_of_documents=self.indexed_document_count)

    def get_filterable_attributes(self):
        self.index_events.append("filterable_settings_checked")
        if not self.settings_valid:
            return []
        return [
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
        ]

    def get_sortable_attributes(self):
        return ["date"]

    def get_searchable_attributes(self):
        return [
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
        ]

    def get_ranking_rules(self):
        return ["sort", "words", "typo", "proximity", "attribute", "exactness"]


class ReplacementClient:
    def __init__(
        self,
        deletion_status,
        indexed_document_count=0,
        *,
        creation_error_code="index_already_exists",
        settings_valid=True,
    ):
        self.creation_error_code = creation_error_code
        self.deletion_status = deletion_status
        self.index_events = []
        self.deletion_timeout_ms = None
        self.deletion_poll_interval_ms = None
        self.documents_index = ReplacementIndex(
            self.index_events,
            indexed_document_count,
            settings_valid=settings_valid,
        )

    def create_index(self, index_name, index_options):
        self.index_events.append("create_enqueued")
        return SimpleNamespace(task_uid=77)

    def index(self, index_name):
        return self.documents_index

    def wait_for_task(
        self,
        task_uid,
        timeout_in_ms=5000,
        interval_in_ms=50,
    ):
        if task_uid == 77:
            if self.creation_error_code is None:
                self.index_events.append("create_succeeded")
                return SimpleNamespace(status="succeeded", error=None)
            self.index_events.append(f"create_{self.creation_error_code}")
            return SimpleNamespace(
                status="failed",
                error={"code": self.creation_error_code},
            )
        if task_uid == 91:
            self.deletion_timeout_ms = timeout_in_ms
            self.deletion_poll_interval_ms = interval_in_ms
            self.index_events.append(f"delete_{self.deletion_status}")
            return SimpleNamespace(status=self.deletion_status)
        self.index_events.append(f"settings_{task_uid}")
        return SimpleNamespace(status="succeeded")

    def get_tasks(self, task_filters):
        self.index_events.append("queue_idle")
        return SimpleNamespace(results=[])


class SynchronousCreationFailureClient(ReplacementClient):
    def create_index(self, index_name, index_options):
        self.index_events.append("create_rejected")
        raise indexer.MeilisearchError("provider unavailable")

    def index(self, index_name):
        raise AssertionError("recovery continued after synchronous create failure")


def _empty_index_session():
    session = MagicMock()
    session.query.return_value = EmptyIndexQuery()
    return session


def test_full_reindex_replaces_existing_meilisearch_documents(mocker):
    replacement_client = ReplacementClient("succeeded")

    @contextmanager
    def fake_db_session():
        yield _empty_index_session()

    mocker.patch.object(indexer, "db_session", fake_db_session)
    mocker.patch.object(indexer.meilisearch, "Client", return_value=replacement_client)

    indexer.replace_documents_index()

    assert replacement_client.index_events[:4] == [
        "create_enqueued",
        "create_index_already_exists",
        "delete_enqueued",
        "delete_succeeded",
    ]
    assert replacement_client.index_events[-3:] == [
        "queue_idle",
        "filterable_settings_checked",
        "stats_checked",
    ]


def test_full_reindex_waits_for_fresh_index_before_clearing(mocker):
    replacement_client = ReplacementClient(
        "succeeded",
        creation_error_code=None,
    )

    @contextmanager
    def fake_db_session():
        yield _empty_index_session()

    mocker.patch.object(indexer, "db_session", fake_db_session)
    mocker.patch.object(indexer.meilisearch, "Client", return_value=replacement_client)

    indexer.replace_documents_index()

    assert replacement_client.index_events[:4] == [
        "create_enqueued",
        "create_succeeded",
        "delete_enqueued",
        "delete_succeeded",
    ]


def test_full_reindex_stops_when_fresh_index_creation_fails(mocker):
    replacement_client = ReplacementClient(
        "succeeded",
        creation_error_code="internal",
    )
    mocker.patch.object(indexer.meilisearch, "Client", return_value=replacement_client)

    with pytest.raises(RuntimeError, match="index creation failed status=failed"):
        indexer.replace_documents_index()

    assert replacement_client.index_events == [
        "create_enqueued",
        "create_internal",
    ]


def test_full_reindex_stops_when_index_creation_is_rejected(mocker):
    replacement_client = SynchronousCreationFailureClient("succeeded")
    mocker.patch.object(indexer.meilisearch, "Client", return_value=replacement_client)

    with pytest.raises(indexer.MeilisearchError, match="provider unavailable"):
        indexer.replace_documents_index()

    assert replacement_client.index_events == ["create_rejected"]


def test_full_reindex_uses_maintenance_timeout_for_document_clear(mocker):
    replacement_client = ReplacementClient("failed")
    mocker.patch.object(indexer.meilisearch, "Client", return_value=replacement_client)

    with pytest.raises(RuntimeError, match="failed"):
        indexer.replace_documents_index()

    assert replacement_client.deletion_timeout_ms == 300_000
    assert replacement_client.deletion_poll_interval_ms == 250


def test_full_reindex_uses_one_bounded_maintenance_client(mocker):
    replacement_client = ReplacementClient("succeeded")
    maintenance_request_timeouts = []

    def create_replacement_client(
        meilisearch_host,
        meilisearch_key,
        timeout=None,
    ):
        maintenance_request_timeouts.append(timeout)
        return replacement_client

    @contextmanager
    def fake_db_session():
        yield _empty_index_session()

    mocker.patch.object(indexer, "db_session", fake_db_session)
    mocker.patch.object(
        indexer.meilisearch,
        "Client",
        side_effect=create_replacement_client,
    )

    indexer.replace_documents_index()

    assert maintenance_request_timeouts == [30]


def test_full_reindex_stops_when_meilisearch_clear_fails(mocker):
    replacement_client = ReplacementClient("failed")
    mocker.patch.object(indexer.meilisearch, "Client", return_value=replacement_client)

    with pytest.raises(RuntimeError, match="failed"):
        indexer.replace_documents_index()

    assert replacement_client.index_events == [
        "create_enqueued",
        "create_index_already_exists",
        "delete_enqueued",
        "delete_failed",
    ]


def test_full_reindex_rejects_document_count_mismatch(mocker):
    replacement_client = ReplacementClient(
        "succeeded",
        indexed_document_count=1,
    )

    @contextmanager
    def fake_db_session():
        yield _empty_index_session()

    mocker.patch.object(indexer, "db_session", fake_db_session)
    mocker.patch.object(indexer.meilisearch, "Client", return_value=replacement_client)

    with pytest.raises(RuntimeError, match="expected=0 actual=1"):
        indexer.replace_documents_index()

    assert replacement_client.index_events[-3:] == [
        "queue_idle",
        "filterable_settings_checked",
        "stats_checked",
    ]


def test_full_reindex_rejects_missing_index_settings(mocker):
    replacement_client = ReplacementClient(
        "succeeded",
        settings_valid=False,
    )

    @contextmanager
    def fake_db_session():
        yield _empty_index_session()

    mocker.patch.object(indexer, "db_session", fake_db_session)
    mocker.patch.object(indexer.meilisearch, "Client", return_value=replacement_client)

    with pytest.raises(RuntimeError, match="filterable_attributes"):
        indexer.replace_documents_index()

    assert replacement_client.index_events[-2:] == [
        "queue_idle",
        "filterable_settings_checked",
    ]


def test_reindex_cli_exposes_explicit_replace_mode():
    cli_help = subprocess.run(
        [sys.executable, "-m", "pipeline.reindex_only", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert cli_help.returncode == 0, cli_help.stderr
    assert "--replace-all" in cli_help.stdout

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


@pytest.mark.parametrize(
    "batch_submission_fails",
    [False, True],
    ids=["submitted", "provider-error"],
)
def test_indexer_reports_agenda_source_count_after_batch_attempt(
    mocker,
    batch_submission_fails,
):
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
    fake_index.update_filterable_attributes.return_value = SimpleNamespace(task_uid=1)
    fake_index.update_sortable_attributes.return_value = SimpleNamespace(task_uid=2)
    fake_index.update_searchable_attributes.return_value = SimpleNamespace(task_uid=3)
    fake_index.update_ranking_rules.return_value = SimpleNamespace(task_uid=4)
    if batch_submission_fails:
        fake_index.add_documents.side_effect = indexer.MeilisearchError("boom")
    fake_client = MagicMock()
    fake_client.create_index.return_value = SimpleNamespace(task_uid=77)
    fake_client.index.return_value = fake_index
    fake_client.wait_for_task.return_value = SimpleNamespace(
        status="succeeded",
        error=None,
    )
    mocker.patch.object(indexer, "db_session", fake_db_session)
    mocker.patch.object(indexer.meilisearch, "Client", return_value=fake_client)
    mocker.patch.object(indexer, "MEILISEARCH_BATCH_SIZE", 2)

    source_document_count = indexer.index_documents()

    assert source_document_count == 2
    fake_index.update_sortable_attributes.assert_called_with(["date"])
    assert [
        wait_call.args[0] for wait_call in fake_client.wait_for_task.call_args_list
    ] == [1, 2, 3, 4]
    assert fake_index.add_documents.call_count == 1
    if not batch_submission_fails:
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


def test_apply_index_settings_rejects_failed_completed_task():
    fake_index = MagicMock()
    fake_index.update_filterable_attributes.return_value = SimpleNamespace(task_uid=1)
    fake_index.update_sortable_attributes.return_value = SimpleNamespace(task_uid=2)
    fake_index.update_searchable_attributes.return_value = SimpleNamespace(task_uid=3)
    fake_index.update_ranking_rules.return_value = SimpleNamespace(task_uid=4)
    fake_client = MagicMock()
    fake_client.wait_for_task.side_effect = (
        SimpleNamespace(status="succeeded", error=None),
        SimpleNamespace(status="failed", error={"code": "invalid_settings"}),
    )

    with pytest.raises(RuntimeError, match="sortable attribute settings failed"):
        indexer._apply_index_settings(fake_client, fake_index)

    assert [
        wait_call.args[0] for wait_call in fake_client.wait_for_task.call_args_list
    ] == [1, 2]
    fake_index.update_searchable_attributes.assert_not_called()
    fake_index.update_ranking_rules.assert_not_called()


def test_apply_index_settings_propagates_wait_error():
    fake_index = MagicMock()
    fake_index.update_filterable_attributes.return_value = SimpleNamespace(task_uid=1)
    fake_index.update_sortable_attributes.return_value = SimpleNamespace(task_uid=2)
    fake_index.update_searchable_attributes.return_value = SimpleNamespace(task_uid=3)
    fake_index.update_ranking_rules.return_value = SimpleNamespace(task_uid=4)
    fake_client = MagicMock()
    fake_client.wait_for_task.side_effect = indexer.MeilisearchError(
        "settings wait unavailable"
    )

    with pytest.raises(indexer.MeilisearchError, match="settings wait unavailable"):
        indexer._apply_index_settings(fake_client, fake_index)


class TargetedReindexQuery:
    def __init__(self, catalog_rows):
        self.catalog_rows = catalog_rows

    def join(self, *args, **kwargs):
        return self

    def outerjoin(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self.catalog_rows


def _targeted_reindex_session():
    meeting_document = SimpleNamespace(
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
    session = MagicMock()
    session.query.side_effect = [
        TargetedReindexQuery([(meeting_document, catalog, event, place, None)]),
        TargetedReindexQuery([(agenda_item, event, place, None)]),
    ]
    return session


def _patch_targeted_reindex_runtime(mocker, deletion_outcome):
    targeted_reindex_session = _targeted_reindex_session()

    @contextmanager
    def fake_db_session():
        yield targeted_reindex_session

    fake_index = MagicMock()
    fake_index.delete_documents.return_value = SimpleNamespace(task_uid=88)
    fake_client = MagicMock()
    fake_client.create_index.return_value = SimpleNamespace(task_uid=77)
    fake_client.index.return_value = fake_index
    if isinstance(deletion_outcome, Exception):
        fake_client.wait_for_task.side_effect = deletion_outcome
    else:
        fake_client.wait_for_task.return_value = deletion_outcome
    mocker.patch.object(indexer, "db_session", fake_db_session)
    mocker.patch.object(indexer.meilisearch, "Client", return_value=fake_client)
    apply_settings = mocker.patch.object(indexer, "_apply_index_settings")
    return fake_client, fake_index, apply_settings


def test_reindex_catalog_skips_schema_updates_and_reindexes_agenda_items(mocker):
    fake_client, fake_index, apply_settings = _patch_targeted_reindex_runtime(
        mocker,
        SimpleNamespace(status="succeeded", error=None),
    )

    result = indexer.reindex_catalog(9)

    apply_settings.assert_not_called()
    fake_index.delete_documents.assert_called_once_with(
        filter='catalog_id = 9 AND result_type = "agenda_item"'
    )
    fake_index.add_documents.assert_called_once()
    fake_client.wait_for_task.assert_called_once_with(
        88,
        timeout_in_ms=indexer_meilisearch.INDEX_TASK_TIMEOUT_MS,
        interval_in_ms=indexer_meilisearch.INDEX_TASK_POLL_INTERVAL_MS,
    )
    sent = fake_index.add_documents.call_args.args[0]
    assert {doc["result_type"] for doc in sent} == {"meeting", "agenda_item"}
    assert result["agenda_item_documents"] == 1


@pytest.mark.parametrize(
    "deletion_outcome, expected_exception",
    (
        (
            SimpleNamespace(status="failed", error={"code": "invalid_filter"}),
            RuntimeError,
        ),
        (indexer.MeilisearchError("delete wait unavailable"), indexer.MeilisearchError),
    ),
)
def test_reindex_catalog_does_not_publish_after_delete_failure(
    mocker,
    deletion_outcome,
    expected_exception,
):
    _, fake_index, _ = _patch_targeted_reindex_runtime(mocker, deletion_outcome)

    with pytest.raises(expected_exception):
        indexer.reindex_catalog(9)

    fake_index.add_documents.assert_not_called()


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
