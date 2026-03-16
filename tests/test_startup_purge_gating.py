from unittest.mock import MagicMock
from pathlib import Path

from pipeline import startup_purge


def test_run_startup_purge_skips_when_disabled(monkeypatch):
    monkeypatch.delenv("STARTUP_PURGE_DERIVED", raising=False)
    result = startup_purge.run_startup_purge_if_enabled()
    assert result["status"] == "skipped"
    assert result["reason"] == "disabled"


def test_run_startup_purge_skips_non_dev_without_override(monkeypatch):
    monkeypatch.setenv("STARTUP_PURGE_DERIVED", "true")
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.delenv("STARTUP_PURGE_ALLOW_NON_DEV", raising=False)
    monkeypatch.delenv("STARTUP_PURGE_REQUIRED_TOKEN", raising=False)
    monkeypatch.delenv("STARTUP_PURGE_CONFIRM_TOKEN", raising=False)

    result = startup_purge.run_startup_purge_if_enabled()
    assert result["status"] == "skipped"
    assert result["reason"] == "blocked_non_dev"


def test_run_startup_purge_allows_non_dev_with_override(monkeypatch):
    monkeypatch.setenv("STARTUP_PURGE_DERIVED", "true")
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("STARTUP_PURGE_ALLOW_NON_DEV", "true")

    fake_engine = MagicMock()
    fake_engine.dialect.name = "sqlite"
    fake_session = MagicMock()
    fake_session.query.return_value.delete.return_value = 0
    fake_session.query.return_value.update.return_value = 0

    monkeypatch.setattr(startup_purge, "db_connect", lambda: fake_engine)
    monkeypatch.setattr(startup_purge, "sessionmaker", lambda bind: lambda: fake_session)

    result = startup_purge.run_startup_purge_if_enabled()
    assert result["status"] == "completed"


def test_base_compose_defaults_are_safe_and_dev_override_restores_convenience():
    compose_source = Path("docker-compose.yml").read_text(encoding="utf-8")
    dev_compose_source = Path("docker-compose.dev.yml").read_text(encoding="utf-8")
    dockerfile_source = Path("Dockerfile").read_text(encoding="utf-8")

    assert "${STARTUP_PURGE_DERIVED:-false}" in compose_source
    assert "command: uvicorn main:app --host 0.0.0.0 --port 8000\n" in compose_source
    assert "healthcheck:" in compose_source.split("redis:", 1)[1]
    assert "restart: unless-stopped" in compose_source.split("api:", 1)[1]
    assert "--reload" in dev_compose_source
    assert "STARTUP_PURGE_DERIVED=true" in dev_compose_source
    assert "sys.exit(1)" in dockerfile_source
