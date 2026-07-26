from collections.abc import Callable
import logging
from pathlib import Path

import pytest

from pipeline import db_migration_runner
from pipeline.db_migration_backfills import run_core_backfills
from pipeline.db_migration_columns import (
    CORE_COLUMN_MIGRATIONS,
    apply_core_column_migrations,
    apply_core_constraint_repairs,
)


class _ScalarResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar(self) -> object | None:
        return self._value


class _FakeConn:
    def __init__(
        self,
        existing_columns: set[tuple[str, str]] | None = None,
    ) -> None:
        self.existing_columns = set(existing_columns or [])
        self.calls: list[tuple[str, dict[str, str] | None]] = []
        self.dialect = type("Dialect", (), {"name": "postgresql"})()

    def execute(
        self,
        statement: object,
        params: dict[str, str] | None = None,
    ) -> _ScalarResult:
        sql = str(statement)
        self.calls.append((sql, params))
        if "information_schema.columns" in sql:
            assert params is not None
            table = params["table"]
            column = params["column"]
            return _ScalarResult(1 if (table, column) in self.existing_columns else None)
        return _ScalarResult(None)


def _sql_calls(conn: _FakeConn) -> list[str]:
    return [sql.lower() for sql, _ in conn.calls]


def test_core_migrations_add_legacy_columns_and_backfill_values() -> None:
    conn = _FakeConn()

    apply_core_column_migrations(conn, logging.getLogger("test-core-migrations"))
    run_core_backfills(conn)

    calls = _sql_calls(conn)
    assert any("alter table event add column organization_id" in c for c in calls)
    assert any("alter table event_stage add column organization_name" in c for c in calls)
    assert any("alter table catalog add column related_ids" in c for c in calls)
    assert any("alter table place add column legistar_client" in c for c in calls)
    assert any("alter table person add column is_elected" in c for c in calls)
    assert any("alter table person add column person_type" in c for c in calls)
    assert any("alter table catalog add column content_hash" in c for c in calls)
    assert any("alter table catalog add column summary_source_hash" in c for c in calls)
    assert any("alter table catalog add column topics_source_hash" in c for c in calls)
    assert any("alter table agenda_item add column page_number" in c for c in calls)
    assert any("alter table agenda_item add column legistar_matter_id" in c for c in calls)
    assert any("create index if not exists ix_person_is_elected" in c for c in calls)
    assert any("create index if not exists ix_agenda_item_legistar_matter_id" in c for c in calls)
    assert any("update person" in c and "set person_type = 'mentioned'" in c for c in calls)
    assert any("update person" in c and "set person_type = 'official'" in c for c in calls)


def test_core_migrations_skip_existing_columns_but_keep_indexes_and_backfills() -> None:
    existing_columns = {
        (column_migration.table, column_migration.column)
        for column_migration in CORE_COLUMN_MIGRATIONS
    }
    conn = _FakeConn(existing_columns=existing_columns)

    apply_core_column_migrations(conn, logging.getLogger("test-core-migrations"))
    run_core_backfills(conn)

    calls = _sql_calls(conn)
    assert not any("alter table" in c and "add column" in c for c in calls)
    assert any("create index if not exists ix_person_is_elected" in c for c in calls)
    assert any("update catalog" in c and "set extraction_status" in c for c in calls)
    assert any("update person" in c and "set person_type = 'official'" in c for c in calls)


def test_strict_legacy_runner_skips_sqlite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = _FakeConn()
    conn.dialect.name = "sqlite"
    migration_events: list[str] = []
    monkeypatch.setattr(
        db_migration_runner,
        "migrate_v8",
        lambda _connection: migration_events.append("v8"),
    )

    db_migration_runner.run_migrations(
        conn,
        logging.getLogger("test-strict-legacy-runner"),
    )

    assert conn.calls == []
    assert migration_events == []


def test_db_migration_implementation_modules_do_not_import_facade() -> None:
    module_paths = [
        "pipeline/db_migration_columns.py",
        "pipeline/db_migration_backfills.py",
        "pipeline/db_migration_runner.py",
        "pipeline/migration_pgvector_semantic_embeddings.py",
        "pipeline/migration_catalog_lineage_columns.py",
    ]

    for module_path in module_paths:
        assert "pipeline.db_migrate" not in Path(module_path).read_text(encoding="utf-8")


def test_strict_legacy_runner_uses_one_caller_owned_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration_connection = _FakeConn()
    migration_events: list[tuple[str, object]] = []

    monkeypatch.setattr(
        db_migration_runner,
        "apply_core_column_migrations",
        lambda connection, _logger: migration_events.append(("columns", connection)),
    )
    monkeypatch.setattr(
        db_migration_runner,
        "run_core_backfills",
        lambda connection: migration_events.append(("backfills", connection)),
    )
    monkeypatch.setattr(
        db_migration_runner,
        "apply_core_constraint_repairs",
        lambda connection: migration_events.append(("constraints", connection)),
    )

    def run_v8(connection: object) -> int:
        migration_events.append(("v8", connection))
        return 7

    monkeypatch.setattr(db_migration_runner, "migrate_v8", run_v8)
    monkeypatch.setattr(
        db_migration_runner,
        "migrate_v9",
        lambda connection: migration_events.append(("v9", connection)),
    )
    monkeypatch.setattr(
        db_migration_runner,
        "migrate_v10",
        lambda connection: migration_events.append(("v10", connection)),
    )

    migration_report = db_migration_runner.run_migrations(
        migration_connection,
        logging.getLogger("test-strict-legacy-runner"),
    )

    assert [migration_name for migration_name, _ in migration_events] == [
        "columns",
        "backfills",
        "constraints",
        "v8",
        "v9",
        "v10",
    ]
    assert all(connection is migration_connection for _, connection in migration_events)
    assert migration_report.retired_catalog_vector_count == 7


@pytest.mark.parametrize(
    ("failing_migration", "expected_events"),
    [
        ("migrate_v8", ["columns", "backfills", "constraints", "migrate_v8"]),
        (
            "migrate_v9",
            ["columns", "backfills", "constraints", "migrate_v8", "migrate_v9"],
        ),
        (
            "migrate_v10",
            [
                "columns",
                "backfills",
                "constraints",
                "migrate_v8",
                "migrate_v9",
                "migrate_v10",
            ],
        ),
    ],
)
def test_strict_legacy_runner_propagates_failure_and_stops(
    monkeypatch: pytest.MonkeyPatch,
    failing_migration: str,
    expected_events: list[str],
) -> None:
    migration_connection = _FakeConn()
    migration_events: list[str] = []

    monkeypatch.setattr(
        db_migration_runner,
        "apply_core_column_migrations",
        lambda _connection, _logger: migration_events.append("columns"),
    )
    monkeypatch.setattr(
        db_migration_runner,
        "run_core_backfills",
        lambda _connection: migration_events.append("backfills"),
    )
    monkeypatch.setattr(
        db_migration_runner,
        "apply_core_constraint_repairs",
        lambda _connection: migration_events.append("constraints"),
    )

    def record_migration(migration_name: str) -> Callable[[object], None]:
        def run_migration(_connection: object) -> None:
            migration_events.append(migration_name)
            if migration_name == failing_migration:
                raise RuntimeError(f"{migration_name} failed")

        return run_migration

    for migration_name in ("migrate_v8", "migrate_v9", "migrate_v10"):
        monkeypatch.setattr(
            db_migration_runner,
            migration_name,
            record_migration(migration_name),
        )

    with pytest.raises(RuntimeError, match=f"{failing_migration} failed"):
        db_migration_runner.run_migrations(
            migration_connection,
            logging.getLogger("test-strict-legacy-runner"),
        )

    assert migration_events == expected_events


def test_core_migrations_repair_indexes_for_existing_columns() -> None:
    existing_columns = {
        (column_migration.table, column_migration.column)
        for column_migration in CORE_COLUMN_MIGRATIONS
    }
    migration_connection = _FakeConn(existing_columns=existing_columns)

    apply_core_column_migrations(
        migration_connection,
        logging.getLogger("test-core-index-repair"),
    )

    migration_sql = _sql_calls(migration_connection)
    assert not any("alter table" in statement for statement in migration_sql)
    expected_indexes = {
        column_migration.index_sql.lower()
        for column_migration in CORE_COLUMN_MIGRATIONS
        if column_migration.index_sql is not None
    }
    assert expected_indexes <= set(migration_sql)


def test_core_constraint_repairs_converge_person_defaults() -> None:
    migration_connection = _FakeConn(
        existing_columns={
            ("person", "is_elected"),
            ("person", "person_type"),
        }
    )

    apply_core_constraint_repairs(migration_connection)

    migration_sql = _sql_calls(migration_connection)
    assert (
        "alter table person alter column is_elected set default false"
        in migration_sql
    )
    assert (
        "alter table person alter column person_type set default 'mentioned'"
        in migration_sql
    )
    assert (
        "alter table person alter column person_type set not null"
        in migration_sql
    )
