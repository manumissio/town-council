from unittest.mock import MagicMock

from pipeline import startup_purge


def test_run_startup_purge_skips_when_lock_not_acquired(monkeypatch):
    monkeypatch.setenv("STARTUP_PURGE_DERIVED", "true")
    monkeypatch.setenv("APP_ENV", "dev")

    fake_engine = MagicMock()
    fake_engine.dialect.name = "postgresql"

    fake_session = MagicMock()
    fake_query = MagicMock()
    fake_query.delete.return_value = 3
    fake_query.update.return_value = 2
    fake_session.query.return_value = fake_query
    fake_session.execute.return_value.scalar.return_value = False

    monkeypatch.setattr(startup_purge, "db_connect", lambda: fake_engine)
    monkeypatch.setattr(startup_purge, "sessionmaker", lambda bind: lambda: fake_session)

    result = startup_purge.run_startup_purge_if_enabled()
    assert result["status"] == "skipped"
    assert result["reason"] == "lock_not_acquired"


def test_run_startup_purge_runs_when_lock_acquired(monkeypatch):
    monkeypatch.setenv("STARTUP_PURGE_DERIVED", "true")
    monkeypatch.setenv("APP_ENV", "dev")

    fake_engine = MagicMock()
    fake_engine.dialect.name = "postgresql"

    fake_session = MagicMock()
    # First execute call = try lock True, second = unlock
    fake_session.execute.side_effect = [
        MagicMock(scalar=lambda: True),
        MagicMock(scalar=lambda: True),
    ]

    fake_query = MagicMock()
    fake_query.delete.return_value = 5
    fake_query.update.return_value = 7
    fake_session.query.return_value = fake_query

    monkeypatch.setattr(startup_purge, "db_connect", lambda: fake_engine)
    monkeypatch.setattr(startup_purge, "sessionmaker", lambda bind: lambda: fake_session)

    result = startup_purge.run_startup_purge_if_enabled()
    assert result["status"] == "completed"
    assert result["deleted_agenda_items"] == 5
    assert result["cleared_catalog_rows"] == 7
