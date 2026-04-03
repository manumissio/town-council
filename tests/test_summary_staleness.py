import sys
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

# Mock heavy dependency before importing api.main
sys.modules["llama_cpp"] = MagicMock()

from api.main import app
from pipeline.summary_freshness import compute_agenda_items_hash


client = TestClient(app)
VALID_KEY = "dev_secret_key_change_me"


def test_summarize_returns_cached_only_when_source_hash_matches(mocker):
    from api.main import get_db
    from pipeline.models import Document

    catalog = MagicMock(
        id=1,
        content="City council meeting discussed budget updates and adopted multiple motions after public comment.",
        summary="cached summary",
        content_hash="abc",
        summary_source_hash="abc",
    )

    db = MagicMock()
    db.get.return_value = catalog
    db.query.return_value.filter_by.return_value.first.return_value = MagicMock(category="minutes")

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    delay = mocker.patch("api.main.generate_summary_task.delay")
    try:
        resp = client.post("/summarize/1", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "cached"
        delay.assert_not_called()
    finally:
        del app.dependency_overrides[get_db]


def test_summarize_returns_stale_when_hash_mismatches(mocker):
    from api.main import get_db
    from pipeline.models import Document

    catalog = MagicMock(
        id=1,
        content="City council meeting discussed budget updates and adopted multiple motions after public comment.",
        summary="old summary",
        content_hash="newhash",
        summary_source_hash="oldhash",
    )

    db = MagicMock()
    db.get.return_value = catalog
    db.query.return_value.filter_by.return_value.first.return_value = MagicMock(category="minutes")

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    delay = mocker.patch("api.main.generate_summary_task.delay")
    try:
        resp = client.post("/summarize/1", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "stale"
        assert payload["summary"] == "old summary"
        delay.assert_not_called()
    finally:
        del app.dependency_overrides[get_db]


def test_summarize_returns_cached_for_fresh_agenda_summary_hash(mocker):
    from api.main import get_db
    from pipeline.models import AgendaItem, Document

    agenda_items = [
        MagicMock(order=1, title="Item 1", description="Desc", classification="Agenda", result="", page_number=1)
    ]
    agenda_hash = compute_agenda_items_hash(agenda_items)
    catalog = MagicMock(
        id=1,
        content=(
            "City council agenda includes housing, transportation, fiscal updates, public comment, "
            "and multiple action items for adoption and review."
        ),
        summary="cached agenda summary",
        content_hash="content-hash",
        summary_source_hash=agenda_hash,
        agenda_items_hash=agenda_hash,
    )

    db = MagicMock()
    db.get.return_value = catalog

    def _query_side_effect(model):
        query = MagicMock()
        if model is Document:
            query.filter_by.return_value.first.return_value = MagicMock(category="agenda")
        elif model is AgendaItem:
            query.filter_by.return_value.order_by.return_value.all.return_value = agenda_items
        return query

    db.query.side_effect = _query_side_effect

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    delay = mocker.patch("api.main.generate_summary_task.delay")
    try:
        resp = client.post("/summarize/1", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "cached"
        delay.assert_not_called()
    finally:
        del app.dependency_overrides[get_db]


def test_summarize_returns_stale_for_agenda_when_summary_hash_lags_structured_items(mocker):
    from api.main import get_db
    from pipeline.models import AgendaItem, Document

    catalog = MagicMock(
        id=1,
        content=(
            "City council agenda includes housing, transportation, fiscal updates, public comment, "
            "and multiple action items for adoption and review."
        ),
        summary="old agenda summary",
        content_hash="content-hash",
        summary_source_hash="old-hash",
        agenda_items_hash="different-stored-hash",
    )

    agenda_item = MagicMock(order=1, title="Item 1", description="Desc", classification="Agenda", result="", page_number=1)
    db = MagicMock()
    db.get.return_value = catalog

    def _query_side_effect(model):
        query = MagicMock()
        if model is Document:
            query.filter_by.return_value.first.return_value = MagicMock(category="agenda")
        elif model is AgendaItem:
            query.filter_by.return_value.order_by.return_value.all.return_value = [agenda_item]
        return query

    db.query.side_effect = _query_side_effect

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    delay = mocker.patch("api.main.generate_summary_task.delay")
    try:
        resp = client.post("/summarize/1", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "stale"
        assert payload["summary"] == "old agenda summary"
        delay.assert_not_called()
    finally:
        del app.dependency_overrides[get_db]


def test_summarize_returns_stale_for_agenda_when_agenda_items_hash_is_missing(mocker):
    from api.main import get_db
    from pipeline.models import AgendaItem, Document

    catalog = MagicMock(
        id=1,
        content=(
            "City council agenda includes housing, transportation, fiscal updates, public comment, "
            "and multiple action items for adoption and review."
        ),
        summary="old agenda summary",
        content_hash="content-hash",
        summary_source_hash="some-hash",
        agenda_items_hash=None,
    )

    db = MagicMock()
    db.get.return_value = catalog

    def _query_side_effect(model):
        query = MagicMock()
        if model is Document:
            query.filter_by.return_value.first.return_value = MagicMock(category="agenda")
        elif model is AgendaItem:
            query.filter_by.return_value.order_by.return_value.all.return_value = []
        return query

    db.query.side_effect = _query_side_effect

    def _mock_get_db():
        yield db

    app.dependency_overrides[get_db] = _mock_get_db
    delay = mocker.patch("api.main.generate_summary_task.delay")
    try:
        resp = client.post("/summarize/1", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "stale"
        delay.assert_not_called()
    finally:
        del app.dependency_overrides[get_db]
