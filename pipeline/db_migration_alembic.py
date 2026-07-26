from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Literal
from uuid import uuid4

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import func, inspect, select, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.schema import CreateSchema, DropSchema

from pipeline.db_migration_runner import run_migrations
from pipeline.db_schema_contracts import (
    SchemaDifference,
    capture_schema_contract,
    compare_schema_contracts,
    format_schema_differences,
)


POSTGRESQL_DIALECT = "postgresql"
PUBLIC_SCHEMA = "public"
BASELINE_REVISION = "0001_v10_baseline"
HEAD_REVISION = "head"
MIGRATION_LOCK_ID = 8_490_716_003
REFERENCE_SCHEMA_PREFIX = "tc_alembic_reference_"
ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger("db-migrate")


class MigrationLockError(RuntimeError):
    """Another migration process already owns the database migration lock."""


class MigrationStateError(RuntimeError):
    """The stored Alembic state cannot be advanced safely."""


class SchemaDriftError(RuntimeError):
    """An unversioned database differs from the frozen v10 baseline."""

    def __init__(self, schema_differences: tuple[SchemaDifference, ...]) -> None:
        self.schema_differences = schema_differences
        super().__init__(
            "Existing database does not match the v10 baseline:\n"
            f"{format_schema_differences(schema_differences)}"
        )


@dataclass(frozen=True, slots=True)
class MigrationOutcome:
    status: Literal["not_applicable", "current", "upgraded", "adopted"]
    revision: str | None
    retired_vector_count: int = 0


def _alembic_config(
    connection: Connection,
    version_table_schema: str | None = None,
) -> Config:
    config = Config(ROOT / "alembic.ini")
    config.attributes["connection"] = connection
    if version_table_schema is not None:
        config.attributes["version_table_schema"] = version_table_schema
    return config


def _head_revision(connection: Connection) -> str:
    script_directory = ScriptDirectory.from_config(_alembic_config(connection))
    heads = script_directory.get_heads()
    if len(heads) != 1:
        raise MigrationStateError(
            f"Expected one Alembic head, found {len(heads)}: {heads}"
        )
    return heads[0]


def _current_revisions(connection: Connection) -> tuple[str, ...]:
    if not inspect(connection).has_table("alembic_version", schema=PUBLIC_SCHEMA):
        return ()
    revision_rows = connection.execute(
        text("SELECT version_num FROM public.alembic_version ORDER BY version_num")
    ).scalars()
    return tuple(str(revision) for revision in revision_rows)


def _has_application_tables(connection: Connection) -> bool:
    return bool(
        connection.scalar(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = :schema_name
                      AND table_type = 'BASE TABLE'
                      AND table_name <> 'alembic_version'
                )
                """
            ),
            {"schema_name": PUBLIC_SCHEMA},
        )
    )


def _acquire_migration_lock(connection: Connection) -> None:
    acquired = connection.scalar(
        text("SELECT pg_try_advisory_xact_lock(:lock_id)"),
        {"lock_id": MIGRATION_LOCK_ID},
    )
    if acquired is not True:
        raise MigrationLockError("Another database migration is already running.")


def _set_search_path(connection: Connection, search_path: str) -> None:
    connection.execute(select(func.set_config("search_path", search_path, True)))


def _reference_schema_name() -> str:
    return f"{REFERENCE_SCHEMA_PREFIX}{uuid4().hex}"


def _build_reference_contract(
    connection: Connection,
    reference_schema: str,
    target_revision: str,
) -> tuple[SchemaDifference, ...]:
    connection.execute(CreateSchema(reference_schema))
    _set_search_path(connection, f"{reference_schema}, {PUBLIC_SCHEMA}")
    command.upgrade(
        _alembic_config(connection, reference_schema),
        target_revision,
    )
    expected_contract = capture_schema_contract(connection, reference_schema)
    _set_search_path(connection, PUBLIC_SCHEMA)
    actual_contract = capture_schema_contract(connection, PUBLIC_SCHEMA)
    differences = compare_schema_contracts(expected_contract, actual_contract)
    connection.execute(DropSchema(reference_schema, cascade=True))
    return differences


def _upgrade_versioned_database(
    connection: Connection,
    current_revisions: tuple[str, ...],
) -> MigrationOutcome:
    if len(current_revisions) != 1:
        raise MigrationStateError(
            "Expected one stored Alembic revision, "
            f"found {len(current_revisions)}: {current_revisions}"
        )
    head_revision = _head_revision(connection)
    if current_revisions == (head_revision,):
        return MigrationOutcome("current", head_revision)
    command.upgrade(_alembic_config(connection), HEAD_REVISION)
    return MigrationOutcome("upgraded", head_revision)


def _upgrade_fresh_database(connection: Connection) -> MigrationOutcome:
    command.upgrade(_alembic_config(connection), HEAD_REVISION)
    return MigrationOutcome("upgraded", _head_revision(connection))


def _adopt_unversioned_database(connection: Connection) -> MigrationOutcome:
    legacy_report = run_migrations(connection, LOGGER)
    reference_schema = _reference_schema_name()
    schema_differences = _build_reference_contract(
        connection,
        reference_schema,
        BASELINE_REVISION,
    )
    if schema_differences:
        raise SchemaDriftError(schema_differences)
    command.stamp(_alembic_config(connection), BASELINE_REVISION)
    command.upgrade(_alembic_config(connection), HEAD_REVISION)
    return MigrationOutcome(
        "adopted",
        _head_revision(connection),
        legacy_report.retired_catalog_vector_count,
    )


def _migrate_postgres(connection: Connection) -> MigrationOutcome:
    _set_search_path(connection, PUBLIC_SCHEMA)
    _acquire_migration_lock(connection)
    current_revisions = _current_revisions(connection)
    if current_revisions:
        return _upgrade_versioned_database(connection, current_revisions)
    if not _has_application_tables(connection):
        return _upgrade_fresh_database(connection)
    return _adopt_unversioned_database(connection)


def migrate_database(engine: Engine) -> MigrationOutcome:
    if engine.dialect.name != POSTGRESQL_DIALECT:
        return MigrationOutcome("not_applicable", None)
    with engine.begin() as connection:
        return _migrate_postgres(connection)


def check_database_parity(engine: Engine) -> tuple[SchemaDifference, ...]:
    if engine.dialect.name != POSTGRESQL_DIALECT:
        raise MigrationStateError("Schema parity requires PostgreSQL.")
    with engine.begin() as connection:
        _set_search_path(connection, PUBLIC_SCHEMA)
        _acquire_migration_lock(connection)
        reference_schema = _reference_schema_name()
        return _build_reference_contract(
            connection,
            reference_schema,
            HEAD_REVISION,
        )
