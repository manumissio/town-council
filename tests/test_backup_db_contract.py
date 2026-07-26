from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKUP_SCRIPT = REPO_ROOT / "scripts" / "backup_db.sh"
OPERATIONS_RUNBOOK = REPO_ROOT / "docs" / "OPERATIONS.md"
PRE_DOCKER_PATH = "/usr/bin:/bin"


def _run_backup_preflight(*arguments: str) -> subprocess.CompletedProcess[str]:
    backup_environment = {**os.environ, "PATH": PRE_DOCKER_PATH}
    return subprocess.run(
        ["bash", str(BACKUP_SCRIPT), *arguments],
        cwd=REPO_ROOT,
        env=backup_environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_backup_db_script_has_valid_bash_syntax() -> None:
    syntax_check = subprocess.run(
        ["bash", "-n", str(BACKUP_SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert syntax_check.returncode == 0, syntax_check.stderr


def test_backup_db_cli_requires_one_output_path() -> None:
    missing_destination = _run_backup_preflight()
    extra_destination = _run_backup_preflight("first.dump", "second.dump")

    assert missing_destination.returncode != 0
    assert "usage:" in missing_destination.stderr.lower()
    assert extra_destination.returncode != 0
    assert "usage:" in extra_destination.stderr.lower()


def test_backup_db_cli_prints_help_without_docker() -> None:
    help_result = _run_backup_preflight("--help")

    assert help_result.returncode == 0
    assert "usage:" in help_result.stdout.lower()


def test_backup_db_cli_refuses_existing_destination(tmp_path: Path) -> None:
    backup_destination = tmp_path / "existing.dump"
    original_contents = b"keep-this-content"
    backup_destination.write_bytes(original_contents)

    backup_result = _run_backup_preflight(str(backup_destination))

    assert backup_result.returncode != 0
    assert "already exists" in backup_result.stderr.lower()
    assert backup_destination.read_bytes() == original_contents


def test_backup_db_cli_rejects_missing_parent(tmp_path: Path) -> None:
    missing_parent = tmp_path / "missing" / "town-council.dump"

    backup_result = _run_backup_preflight(str(missing_parent))

    assert backup_result.returncode != 0
    assert "parent directory" in backup_result.stderr.lower()
    assert not missing_parent.parent.exists()


def test_backup_db_script_secures_and_atomically_publishes_archive() -> None:
    backup_source = BACKUP_SCRIPT.read_text(encoding="utf-8")

    assert "umask 077" in backup_source
    assert "mktemp" in backup_source
    assert "trap cleanup_backup" in backup_source
    assert "--format=custom" in backup_source
    assert "--no-owner" in backup_source
    assert "--no-privileges" in backup_source
    assert "pg_restore --list" in backup_source
    assert '\"$POSTGRES_USER\"' in backup_source
    assert '\"$POSTGRES_DB\"' in backup_source
    assert "POSTGRES_PASSWORD" not in backup_source
    assert backup_source.index("pg_restore --list") < backup_source.index("ln ")
    assert backup_source.index("ln ") < backup_source.index("unlink ")


def test_backup_runbook_documents_recovery_contract() -> None:
    operations = OPERATIONS_RUNBOOK.read_text(encoding="utf-8")
    routine_backup_start = operations.index("#### Routine database backup and recovery")
    migration_start = operations.index("#### Schema migration workflow")
    recovery_guidance = operations[routine_backup_start:migration_start]

    assert "scripts/backup_db.sh" in recovery_guidance
    assert "daily" in recovery_guidance
    assert "weekly" in recovery_guidance
    assert "encrypted" in recovery_guidance
    assert "template0" in recovery_guidance
    assert "--exit-on-error" in recovery_guidance
    assert "RESTORE_DB_CREATED=false" in recovery_guidance
    assert "trap cleanup_restore_drill EXIT" in recovery_guidance
    assert "createdb" in recovery_guidance
    assert "pg_restore" in recovery_guidance
    assert "dropdb" in recovery_guidance
    assert "select 'catalog' as relation" in recovery_guidance
    assert "select 'event' as relation" in recovery_guidance
    assert "STARTUP_PURGE_DERIVED=false" in recovery_guidance
    assert "reindex_only.py --replace-all" in recovery_guidance
    assert "reindex_semantic.py" in recovery_guidance
    assert recovery_guidance.index("createdb") < recovery_guidance.index(
        "RESTORE_DB_CREATED=true"
    )


def test_migration_rollback_selects_previous_release_before_schema_tools() -> None:
    operations = OPERATIONS_RUNBOOK.read_text(encoding="utf-8")
    rollback_start = operations.index("##### Roll back a failed schema release")
    historical_migration_start = operations.index("#### Historical timezone migration v10")
    rollback_guidance = operations[rollback_start:historical_migration_start]

    assert 'git switch --detach "$ROLLBACK_REF"' in rollback_guidance
    assert "before running `db_migrate.py`" in rollback_guidance
    assert "Do not run `db_migrate.py` from the failed release" in rollback_guidance
