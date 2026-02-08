from types import SimpleNamespace

import pytest

from pipeline import db_utils


def test_setup_db_uses_database_url(monkeypatch):
    captured = {}
    monkeypatch.setenv("DATABASE_URL", "sqlite:///tmp/custom.sqlite")
    monkeypatch.setattr(db_utils, "create_engine", lambda url: captured.setdefault("url", url) or object())

    engine, metadata = db_utils.setup_db()

    assert captured["url"] == "sqlite:///tmp/custom.sqlite"
    assert metadata.bind == engine


def test_setup_db_falls_back_to_project_sqlite(monkeypatch):
    captured = {}
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(db_utils, "create_engine", lambda url: captured.setdefault("url", url) or object())

    db_utils.setup_db()

    assert captured["url"].startswith("sqlite:///")
    assert captured["url"].endswith("test_db.sqlite")


def test_get_event_id_returns_existing_id(monkeypatch):
    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, *_args, **_kwargs):
            return SimpleNamespace(first=lambda: SimpleNamespace(id=42))

    engine = SimpleNamespace(connect=lambda: Conn())

    event_id = db_utils.get_event_id("Council", "2026-01-01", 1, engine)
    assert event_id == 42


def test_get_event_id_returns_none_when_missing():
    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, *_args, **_kwargs):
            return SimpleNamespace(first=lambda: None)

    engine = SimpleNamespace(connect=lambda: Conn())
    assert db_utils.get_event_id("Council", "2026-01-01", 1, engine) is None


def test_get_place_id_returns_value(monkeypatch):
    class FakeSelect:
        def where(self, *_):
            return self

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, _stmt):
            return SimpleNamespace(first=lambda: SimpleNamespace(id=9))

    fake_engine = SimpleNamespace(connect=lambda: FakeConn())
    fake_place = SimpleNamespace(c=SimpleNamespace(id="id_col", ocd_division_id="ocd_col"))

    monkeypatch.setattr(db_utils, "setup_db", lambda: (fake_engine, None))
    monkeypatch.setattr(db_utils, "get_place", lambda: fake_place)
    monkeypatch.setattr(db_utils.sql, "select", lambda _cols: FakeSelect())

    assert db_utils.get_place_id("ocd-division/country:us/state:ca/place:test") == 9


def test_create_tables_creates_only_missing(monkeypatch):
    created = []

    class FakeTable:
        def __init__(self, name):
            self.name = name

        def create(self):
            created.append(self.name)

    url_stage = FakeTable("url_stage")
    catalog = FakeTable("catalog")
    url_stage_hist = FakeTable("url_stage_hist")
    place = FakeTable("place")
    event = FakeTable("event")
    document = FakeTable("document")

    class FakeDialect:
        def has_table(self, _engine, table):
            return table.name in {"catalog", "place"}

    engine = SimpleNamespace(dialect=FakeDialect())
    monkeypatch.setattr(db_utils, "setup_db", lambda: (engine, None))
    monkeypatch.setattr(db_utils, "get_url_stage", lambda: url_stage)
    monkeypatch.setattr(db_utils, "get_catalog", lambda: catalog)
    monkeypatch.setattr(db_utils, "get_url_stage_hist", lambda: url_stage_hist)
    monkeypatch.setattr(db_utils, "get_place", lambda: place)
    monkeypatch.setattr(db_utils, "get_event", lambda: event)
    monkeypatch.setattr(db_utils, "get_document", lambda: document)

    db_utils.create_tables()

    assert set(created) == {"url_stage", "url_stage_hist", "event", "document"}
