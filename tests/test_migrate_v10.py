from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
import importlib
import os
from typing import Protocol
from types import ModuleType
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine, event, inspect, text


LEGACY_UTC_WALL_CLOCK = datetime(2024, 2, 3, 4, 5, 6, 789012)
NON_UTC_SESSION_TIMEZONE = "America/Los_Angeles"
POSTGRES_TEST_URL_ENV = "TEST_POSTGRES_DATABASE_URL"


class TimestampColumnSpecContract(Protocol):
    table_name: str
    column_name: str
    has_server_default: bool


def _migration_module() -> ModuleType:
    return importlib.import_module("pipeline.migrate_v10")


def _postgres_test_url() -> str:
    postgres_test_url = os.getenv(POSTGRES_TEST_URL_ENV)
    if postgres_test_url:
        return postgres_test_url
    if os.getenv("CI", "").lower() == "true":
        pytest.fail(f"{POSTGRES_TEST_URL_ENV} is required in CI")
    pytest.skip(f"{POSTGRES_TEST_URL_ENV} is not configured")


@pytest.fixture
def postgres_schema_engine() -> Iterator[Engine]:
    postgres_test_url = _postgres_test_url()
    administration_engine = create_engine(postgres_test_url)
    schema_name = f"tc_timestamp_{uuid4().hex}"

    with administration_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))

    schema_engine = create_engine(
        postgres_test_url,
        connect_args={"options": f"-csearch_path={schema_name}"},
    )
    try:
        yield schema_engine
    finally:
        schema_engine.dispose()
        with administration_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
        administration_engine.dispose()


def _timestamp_specs(migration_module: ModuleType) -> Sequence[TimestampColumnSpecContract]:
    return migration_module.TIMESTAMP_COLUMNS


def _timestamp_columns_by_table(migration_module: ModuleType) -> dict[str, list[str]]:
    timestamp_columns: dict[str, list[str]] = {}
    for timestamp_spec in _timestamp_specs(migration_module):
        timestamp_columns.setdefault(timestamp_spec.table_name, []).append(timestamp_spec.column_name)
    return timestamp_columns


def _create_legacy_timestamp_schema(engine: Engine, migration_module: ModuleType) -> None:
    with engine.begin() as connection:
        for table_name, column_names in _timestamp_columns_by_table(migration_module).items():
            timestamp_definitions = ", ".join(
                f'"{column_name}" TIMESTAMP WITHOUT TIME ZONE DEFAULT TIMESTAMP \'2000-01-01 00:00:00\''
                for column_name in column_names
            )
            connection.execute(
                text(f'CREATE TABLE "{table_name}" (id INTEGER PRIMARY KEY, {timestamp_definitions})')
            )
            inserted_columns = ", ".join(f'"{column_name}"' for column_name in column_names)
            inserted_values = ", ".join(f":{column_name}" for column_name in column_names)
            connection.execute(
                text(f'INSERT INTO "{table_name}" (id, {inserted_columns}) VALUES (1, {inserted_values})'),
                {"id": 1, **dict.fromkeys(column_names, LEGACY_UTC_WALL_CLOCK)},
            )


def _run_migration(monkeypatch: pytest.MonkeyPatch, engine: Engine, migration_module: ModuleType) -> None:
    monkeypatch.setattr(migration_module, "db_connect", lambda: engine)
    migration_module.migrate()


def _physical_timestamp_contract(engine: Engine) -> dict[tuple[str, str], tuple[str, str | None]]:
    with engine.connect() as connection:
        timestamp_rows = connection.execute(
            text(
                """
                SELECT table_name, column_name, data_type, column_default
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                ORDER BY table_name, ordinal_position
                """
            )
        ).mappings()
        return {
            (timestamp_row["table_name"], timestamp_row["column_name"]): (
                timestamp_row["data_type"],
                timestamp_row["column_default"],
            )
            for timestamp_row in timestamp_rows
            if timestamp_row["column_name"] != "id"
        }


def _expected_physical_contract(migration_module: ModuleType) -> dict[tuple[str, str], bool]:
    return {
        (timestamp_spec.table_name, timestamp_spec.column_name): timestamp_spec.has_server_default
        for timestamp_spec in _timestamp_specs(migration_module)
    }


def test_migrate_converts_all_timestamps_and_enforces_physical_defaults(
    monkeypatch: pytest.MonkeyPatch,
    postgres_schema_engine: Engine,
) -> None:
    migration_module = _migration_module()
    _create_legacy_timestamp_schema(postgres_schema_engine, migration_module)

    _run_migration(monkeypatch, postgres_schema_engine, migration_module)

    physical_contract = _physical_timestamp_contract(postgres_schema_engine)
    expected_contract = _expected_physical_contract(migration_module)
    assert set(physical_contract) == set(expected_contract)
    for timestamp_identity, has_server_default in expected_contract.items():
        data_type, physical_default = physical_contract[timestamp_identity]
        assert data_type == "timestamp with time zone"
        assert (physical_default is not None) is has_server_default
        if physical_default is not None:
            assert physical_default.lower() in {"now()", "current_timestamp"}


def test_migrate_preserves_utc_instant_under_non_utc_session(
    monkeypatch: pytest.MonkeyPatch,
    postgres_schema_engine: Engine,
) -> None:
    migration_module = _migration_module()
    _create_legacy_timestamp_schema(postgres_schema_engine, migration_module)
    _run_migration(monkeypatch, postgres_schema_engine, migration_module)

    with postgres_schema_engine.connect() as connection:
        connection.execute(text(f"SET TIME ZONE '{NON_UTC_SESSION_TIMEZONE}'"))
        migrated_timestamp = connection.scalar(text('SELECT "created_at" FROM "person" WHERE id = 1'))

    assert isinstance(migrated_timestamp, datetime)
    assert migrated_timestamp.tzinfo is not None
    assert migrated_timestamp.astimezone(UTC) == LEGACY_UTC_WALL_CLOCK.replace(tzinfo=UTC)


def test_migrate_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
    postgres_schema_engine: Engine,
) -> None:
    migration_module = _migration_module()
    _create_legacy_timestamp_schema(postgres_schema_engine, migration_module)
    _run_migration(monkeypatch, postgres_schema_engine, migration_module)
    first_contract = _physical_timestamp_contract(postgres_schema_engine)
    rerun_statements: list[str] = []

    def capture_rerun_statement(statement: str, **_event_fields: object) -> None:
        rerun_statements.append(statement)

    event.listen(
        postgres_schema_engine,
        "before_cursor_execute",
        capture_rerun_statement,
        named=True,
    )
    try:
        _run_migration(monkeypatch, postgres_schema_engine, migration_module)
    finally:
        event.remove(postgres_schema_engine, "before_cursor_execute", capture_rerun_statement)

    assert _physical_timestamp_contract(postgres_schema_engine) == first_contract
    assert not any(statement.lstrip().upper().startswith("ALTER TABLE") for statement in rerun_statements)
    assert not any(statement.lstrip().upper().startswith("ANALYZE") for statement in rerun_statements)


def test_migrate_converges_mixed_timestamp_schema(
    monkeypatch: pytest.MonkeyPatch,
    postgres_schema_engine: Engine,
) -> None:
    migration_module = _migration_module()
    _create_legacy_timestamp_schema(postgres_schema_engine, migration_module)
    first_spec = _timestamp_specs(migration_module)[0]
    with postgres_schema_engine.begin() as connection:
        connection.execute(
            text(
                f'ALTER TABLE "{first_spec.table_name}" '
                f'ALTER COLUMN "{first_spec.column_name}" DROP DEFAULT'
            )
        )
        connection.execute(
            text(
                f'ALTER TABLE "{first_spec.table_name}" '
                f'ALTER COLUMN "{first_spec.column_name}" TYPE TIMESTAMP WITH TIME ZONE '
                f'USING "{first_spec.column_name}" AT TIME ZONE \'UTC\''
            )
        )

    _run_migration(monkeypatch, postgres_schema_engine, migration_module)

    physical_contract = _physical_timestamp_contract(postgres_schema_engine)
    assert all(data_type == "timestamp with time zone" for data_type, _ in physical_contract.values())


@pytest.mark.parametrize("schema_defect", ["missing", "unsupported"])
def test_migrate_rolls_back_when_schema_is_not_supported(
    monkeypatch: pytest.MonkeyPatch,
    postgres_schema_engine: Engine,
    schema_defect: str,
) -> None:
    migration_module = _migration_module()
    _create_legacy_timestamp_schema(postgres_schema_engine, migration_module)
    final_spec = _timestamp_specs(migration_module)[-1]
    with postgres_schema_engine.begin() as connection:
        if schema_defect == "missing":
            connection.execute(
                text(
                    f'ALTER TABLE "{final_spec.table_name}" '
                    f'DROP COLUMN "{final_spec.column_name}"'
                )
            )
        else:
            connection.execute(
                text(
                    f'ALTER TABLE "{final_spec.table_name}" '
                    f'ALTER COLUMN "{final_spec.column_name}" DROP DEFAULT'
                )
            )
            connection.execute(
                text(
                    f'ALTER TABLE "{final_spec.table_name}" '
                    f'ALTER COLUMN "{final_spec.column_name}" TYPE TEXT '
                    f'USING "{final_spec.column_name}"::TEXT'
                )
            )

    migration_statements: list[str] = []

    def capture_migration_statement(statement: str, **_event_fields: object) -> None:
        migration_statements.append(statement)

    event.listen(
        postgres_schema_engine,
        "before_cursor_execute",
        capture_migration_statement,
        named=True,
    )
    try:
        with pytest.raises(migration_module.TimestampMigrationError):
            _run_migration(monkeypatch, postgres_schema_engine, migration_module)
    finally:
        event.remove(postgres_schema_engine, "before_cursor_execute", capture_migration_statement)

    first_spec = _timestamp_specs(migration_module)[0]
    first_type, _ = _physical_timestamp_contract(postgres_schema_engine)[
        (first_spec.table_name, first_spec.column_name)
    ]
    assert first_type == "timestamp without time zone"
    assert not any(statement.lstrip().upper().startswith("ALTER TABLE") for statement in migration_statements)


def test_migrate_is_no_op_for_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    migration_module = _migration_module()
    sqlite_engine = create_engine("sqlite:///:memory:")
    with sqlite_engine.begin() as connection:
        connection.execute(text("CREATE TABLE migration_sentinel (id INTEGER PRIMARY KEY)"))

    _run_migration(monkeypatch, sqlite_engine, migration_module)

    assert inspect(sqlite_engine).has_table("migration_sentinel")
    sqlite_engine.dispose()
