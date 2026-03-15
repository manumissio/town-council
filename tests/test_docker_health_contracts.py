from pathlib import Path


def test_compose_uses_explicit_local_healthchecks():
    source = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "http://127.0.0.1:9998/tika" in source
    assert "python scripts/worker_healthcheck.py" in source
    assert "http://127.0.0.1:3000/" in source
