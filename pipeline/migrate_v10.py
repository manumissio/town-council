from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import DDL, text
from sqlalchemy.engine import Connection

from pipeline.models import db_connect


POSTGRESQL_DIALECT = "postgresql"
NAIVE_TIMESTAMP_TYPE = "timestamp without time zone"
AWARE_TIMESTAMP_TYPE = "timestamp with time zone"
GENERATED_DEFAULTS = {"now()", "current_timestamp"}
DROP_DEFAULT_DDL = (
    "ALTER TABLE %(table_identifier)s "
    "ALTER COLUMN %(column_identifier)s DROP DEFAULT"
)
CONVERT_TO_UTC_DDL = (
    "ALTER TABLE %(table_identifier)s "
    "ALTER COLUMN %(column_identifier)s TYPE TIMESTAMP WITH TIME ZONE "
    "USING %(column_identifier)s AT TIME ZONE 'UTC'"
)
RESTORE_DEFAULT_DDL = (
    "ALTER TABLE %(table_identifier)s "
    "ALTER COLUMN %(column_identifier)s SET DEFAULT now()"
)
ANALYZE_TABLE_DDL = "ANALYZE %(table_identifier)s"


@dataclass(frozen=True, slots=True)
class TimestampColumnSpec:
    table_name: str
    column_name: str
    has_server_default: bool


class TimestampMigrationError(RuntimeError):
    """The stored timestamp schema cannot be migrated safely."""


TIMESTAMP_COLUMNS = (
    TimestampColumnSpec("person", "created_at", True),
    TimestampColumnSpec("data_issue", "created_at", True),
    TimestampColumnSpec("url_stage", "created_at", True),
    TimestampColumnSpec("event_stage", "scraped_datetime", True),
    TimestampColumnSpec("event", "scraped_datetime", True),
    TimestampColumnSpec("url_stage_hist", "created_at", True),
    TimestampColumnSpec("semantic_embedding", "updated_at", True),
    TimestampColumnSpec("catalog", "extraction_attempted_at", False),
    TimestampColumnSpec("catalog", "lineage_updated_at", False),
    TimestampColumnSpec("catalog", "agenda_segmentation_attempted_at", False),
    TimestampColumnSpec("catalog", "created_at", True),
    TimestampColumnSpec("catalog", "uploaded_at", True),
    TimestampColumnSpec("document", "created_at", True),
)


def _read_timestamp_contract(
    connection: Connection,
    timestamp_spec: TimestampColumnSpec,
) -> tuple[str, str | None]:
    timestamp_row = connection.execute(
        text(
            """
            SELECT data_type, column_default
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = :table_name
              AND column_name = :column_name
            """
        ),
        {
            "table_name": timestamp_spec.table_name,
            "column_name": timestamp_spec.column_name,
        },
    ).one_or_none()
    if timestamp_row is None:
        raise TimestampMigrationError(
            f"Missing timestamp column: {timestamp_spec.table_name}.{timestamp_spec.column_name}"
        )

    timestamp_type, timestamp_default = timestamp_row
    if not isinstance(timestamp_type, str):
        raise TimestampMigrationError(
            f"Invalid timestamp metadata: {timestamp_spec.table_name}.{timestamp_spec.column_name}"
        )
    if timestamp_type not in {NAIVE_TIMESTAMP_TYPE, AWARE_TIMESTAMP_TYPE}:
        raise TimestampMigrationError(
            f"Unsupported timestamp type for {timestamp_spec.table_name}."
            f"{timestamp_spec.column_name}: {timestamp_type}"
        )
    if timestamp_default is not None and not isinstance(timestamp_default, str):
        raise TimestampMigrationError(
            f"Invalid timestamp default: {timestamp_spec.table_name}.{timestamp_spec.column_name}"
        )
    return timestamp_type, timestamp_default


def _execute_timestamp_ddl(
    connection: Connection,
    timestamp_spec: TimestampColumnSpec,
    ddl_statement: str,
) -> None:
    identifier_preparer = connection.dialect.identifier_preparer
    ddl_context = {
        "table_identifier": identifier_preparer.quote_identifier(
            timestamp_spec.table_name
        ),
        "column_identifier": identifier_preparer.quote_identifier(
            timestamp_spec.column_name
        ),
    }
    connection.execute(DDL(ddl_statement, context=ddl_context))


def _drop_timestamp_default(
    connection: Connection,
    timestamp_spec: TimestampColumnSpec,
) -> None:
    _execute_timestamp_ddl(connection, timestamp_spec, DROP_DEFAULT_DDL)


def _convert_timestamp_to_utc(
    connection: Connection,
    timestamp_spec: TimestampColumnSpec,
) -> None:
    _execute_timestamp_ddl(connection, timestamp_spec, CONVERT_TO_UTC_DDL)


def _restore_generated_default(connection: Connection, timestamp_spec: TimestampColumnSpec) -> None:
    if not timestamp_spec.has_server_default:
        return
    _execute_timestamp_ddl(connection, timestamp_spec, RESTORE_DEFAULT_DDL)


def _migrate_timestamp_column(
    connection: Connection,
    timestamp_spec: TimestampColumnSpec,
    timestamp_contract: tuple[str, str | None],
) -> bool:
    timestamp_type, timestamp_default = timestamp_contract
    default_matches = (
        timestamp_default is not None
        and timestamp_default.lower() in GENERATED_DEFAULTS
        and timestamp_spec.has_server_default
    ) or (timestamp_default is None and not timestamp_spec.has_server_default)
    if timestamp_type == AWARE_TIMESTAMP_TYPE and default_matches:
        return False

    _drop_timestamp_default(connection, timestamp_spec)
    if timestamp_type == NAIVE_TIMESTAMP_TYPE:
        _convert_timestamp_to_utc(connection, timestamp_spec)
    _restore_generated_default(connection, timestamp_spec)
    return timestamp_type == NAIVE_TIMESTAMP_TYPE


def _analyze_changed_tables(connection: Connection, changed_tables: set[str]) -> None:
    identifier_preparer = connection.dialect.identifier_preparer
    for table_name in sorted(changed_tables):
        connection.execute(
            DDL(
                ANALYZE_TABLE_DDL,
                context={
                    "table_identifier": identifier_preparer.quote_identifier(
                        table_name
                    )
                },
            )
        )


def migrate(connection: Connection | None = None) -> None:
    if connection is not None:
        _migrate_connection(connection)
        return

    engine = db_connect()
    with engine.begin() as owned_connection:
        _migrate_connection(owned_connection)


def _migrate_connection(connection: Connection) -> None:
    if connection.dialect.name != POSTGRESQL_DIALECT:
        return

    timestamp_contracts = {
        timestamp_spec: _read_timestamp_contract(connection, timestamp_spec)
        for timestamp_spec in TIMESTAMP_COLUMNS
    }
    changed_tables = {
        timestamp_spec.table_name
        for timestamp_spec in TIMESTAMP_COLUMNS
        if _migrate_timestamp_column(
            connection,
            timestamp_spec,
            timestamp_contracts[timestamp_spec],
        )
    }
    _analyze_changed_tables(connection, changed_tables)


if __name__ == "__main__":
    migrate()
