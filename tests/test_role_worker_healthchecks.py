from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


ROLE_HEALTHCHECK_PATHS = (
    Path("scripts/enrichment_worker_healthcheck.py"),
    Path("scripts/semantic_worker_healthcheck.py"),
)


@pytest.mark.parametrize("healthcheck_path", ROLE_HEALTHCHECK_PATHS)
def test_role_healthcheck_runs_without_pythonpath_and_aggregates_missing_targets(
    healthcheck_path: Path,
    tmp_path: Path,
) -> None:
    healthcheck_environment = os.environ.copy()
    healthcheck_environment.pop("PYTHONPATH", None)
    healthcheck_environment["CELERY_BROKER_URL"] = ""
    healthcheck_environment["DATABASE_URL"] = ""
    healthcheck_environment["REDIS_HOST"] = "town-council-invalid.invalid"
    healthcheck_environment["SEMANTIC_INDEX_DIR"] = str(tmp_path / "semantic")

    healthcheck = subprocess.run(
        [sys.executable, str(healthcheck_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        env=healthcheck_environment,
    )

    assert healthcheck.returncode == 1
    assert "redis broker target is not configured" in healthcheck.stderr
    assert "postgres target is not configured" in healthcheck.stderr
    assert "redis broker probe failed:" not in healthcheck.stderr
    assert "task registration probe failed:" not in healthcheck.stderr
