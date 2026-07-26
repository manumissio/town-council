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

    full_recovery_guidance = recovery_guidance[
        recovery_guidance.index("For full recovery") :
    ]
    restore_guidance = full_recovery_guidance[
        : full_recovery_guidance.index("Confirm those counts")
    ]
    external_search_guidance = full_recovery_guidance[
        full_recovery_guidance.index("restored snapshot:") :
    ]
    writers_stopped = full_recovery_guidance.index(
        "docker compose -f docker-compose.yml -f docker-compose.dev.yml stop"
    )
    restore_fail_fast_enabled = restore_guidance.index("set -euo pipefail")
    postgres_started = full_recovery_guidance.index(
        "docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres"
    )
    postgres_environment_read = full_recovery_guidance.index(
        'POSTGRES_USER="$(docker compose exec -T postgres printenv POSTGRES_USER)"'
    )
    external_search_fail_fast_enabled = external_search_guidance.index(
        "set -euo pipefail"
    )
    meilisearch_started = external_search_guidance.index(
        "up -d postgres redis meilisearch"
    )
    assert restore_fail_fast_enabled < writers_stopped < postgres_started
    assert postgres_started < postgres_environment_read
    assert external_search_fail_fast_enabled < meilisearch_started
    assert "--rm --build --no-deps semantic python ../pipeline/reindex_semantic.py" in (
        full_recovery_guidance
    )


def test_migration_rollback_selects_previous_release_before_schema_tools() -> None:
    operations = OPERATIONS_RUNBOOK.read_text(encoding="utf-8")
    rollback_start = operations.index("##### Roll back a failed schema release")
    historical_migration_start = operations.index("#### Historical timezone migration v10")
    rollback_guidance = operations[rollback_start:historical_migration_start]

    assert 'git switch --detach "$ROLLBACK_REF"' in rollback_guidance
    assert "before running `db_migrate.py`" in rollback_guidance
    assert "Do not run `db_migrate.py` from the failed release" in rollback_guidance
    assert "rollback release" in rollback_guidance
    assert "Checkout-based rollback" in rollback_guidance
    assert "--replace-all" not in rollback_guidance
    assert "from urllib.request import Request, urlopen" in rollback_guidance
    assert '"/indexes/documents/documents"' in rollback_guidance
    rollback_index_clear = rollback_guidance.index('"/indexes/documents/documents"')
    rollback_additive_reindex = rollback_guidance.index("python reindex_only.py")
    assert rollback_index_clear < rollback_additive_reindex
    rollback_task_wait = rollback_guidance.index(
        "Meilisearch rollback reindex completed"
    )
    assert rollback_additive_reindex < rollback_task_wait
    assert 'in {"failed", "canceled"}' in rollback_guidance
    assert 'task["type"] == "indexCreation"' in rollback_guidance
    assert 'task["error"]["code"] == "index_already_exists"' in rollback_guidance
    assert "TASK_TIMEOUT_SECONDS" in rollback_guidance
    checkout_image_guidance = rollback_guidance[
        rollback_guidance.index("Checkout-based rollback") :
        rollback_guidance.index("Prebuilt-image rollback")
    ]
    assert (
        'docker compose "${ROLLBACK_COMPOSE_FILES[@]}" build\n'
        in checkout_image_guidance
    )
    prebuilt_image_guidance = rollback_guidance[
        rollback_guidance.index("Prebuilt-image rollback") :
    ]
    assert 'ROLLBACK_COMPOSE_FILE="<ROLLBACK_COMPOSE_FILE>"' in (
        prebuilt_image_guidance
    )
    assert 'ROLLBACK_COMPOSE_FILES=(-f "$ROLLBACK_COMPOSE_FILE")' in (
        prebuilt_image_guidance
    )
    assert "--rm --no-deps pipeline python db_migrate.py" in prebuilt_image_guidance
    assert (
        "--rm --no-deps semantic python ../pipeline/reindex_semantic.py"
        in prebuilt_image_guidance
    )
    prebuilt_image_commands = prebuilt_image_guidance.split("```bash", maxsplit=1)[
        1
    ].split("```", maxsplit=1)[0]
    rollback_compose_command = 'docker compose "${ROLLBACK_COMPOSE_FILES[@]}"'
    assert "set -euo pipefail" in prebuilt_image_commands
    assert prebuilt_image_guidance.count("set -euo pipefail") == 2
    assert "--build" not in prebuilt_image_guidance
    assert prebuilt_image_guidance.count(
        rollback_compose_command
    ) == prebuilt_image_guidance.count("docker compose")


def test_rollback_task_classifier_accepts_only_existing_index_failure() -> None:
    operations = OPERATIONS_RUNBOOK.read_text(encoding="utf-8")
    classifier_start = operations.index("def task_allows_rollback_reindex")
    classifier_end = operations.index("\n\ndef request_json", classifier_start)
    classifier_source = operations[classifier_start:classifier_end]
    classifier_contract = """
assert task_allows_rollback_reindex({"status": "succeeded"})
assert task_allows_rollback_reindex({
    "status": "failed",
    "type": "indexCreation",
    "error": {"code": "index_already_exists"},
})
assert not task_allows_rollback_reindex({
    "status": "failed",
    "type": "indexCreation",
    "error": {"code": "internal_error"},
})
assert not task_allows_rollback_reindex({
    "status": "failed",
    "type": "documentAdditionOrUpdate",
    "error": {"code": "index_already_exists"},
})
assert not task_allows_rollback_reindex({"status": "canceled"})
assert not task_allows_rollback_reindex({"status": "processing"})
"""
    classifier_check = subprocess.run(
        [str(REPO_ROOT / ".venv" / "bin" / "python"), "-"],
        cwd=REPO_ROOT,
        input=f"{classifier_source}\n{classifier_contract}",
        capture_output=True,
        text=True,
        check=False,
    )

    assert classifier_check.returncode == 0, classifier_check.stderr
