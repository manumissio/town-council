from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass
from typing import TypeVar

from sqlalchemy import text
from sqlalchemy.engine import Connection


REQUIRED_EXTENSIONS = ("vector",)
SCHEMA_QUALIFIER_PLACEHOLDER = "<schema>."
ABSENT_CONTRACT_VALUE = "<absent>"
MISSING_CONTRACT_VALUE = "<missing>"
ContractRecord = TypeVar("ContractRecord")


@dataclass(frozen=True, slots=True, order=True)
class ColumnContract:
    table_name: str
    column_name: str
    type_sql: str
    nullable: bool
    default_sql: str | None


@dataclass(frozen=True, slots=True, order=True)
class ConstraintContract:
    table_name: str
    constraint_name: str
    constraint_kind: str
    definition_sql: str


@dataclass(frozen=True, slots=True, order=True)
class IndexContract:
    table_name: str
    index_name: str
    definition_sql: str
    predicate_sql: str | None


@dataclass(frozen=True, slots=True, order=True)
class SequenceContract:
    sequence_name: str
    owner_table: str | None
    owner_column: str | None
    data_type: str
    start_value: int
    minimum_value: int
    maximum_value: int
    increment_by: int
    cycle: bool
    cache_size: int


@dataclass(frozen=True, slots=True)
class DatabaseSchemaContract:
    schema_name: str
    table_names: tuple[str, ...]
    columns: tuple[ColumnContract, ...]
    constraints: tuple[ConstraintContract, ...]
    indexes: tuple[IndexContract, ...]
    sequences: tuple[SequenceContract, ...]
    extensions: tuple[str, ...]


@dataclass(frozen=True, slots=True, order=True)
class SchemaDifference:
    contract_part: str
    expected: str
    actual: str


def _normalize_schema_sql(sql_value: str | None, schema_name: str) -> str | None:
    if sql_value is None:
        return None
    normalized_sql = sql_value.replace(f'"{schema_name}".', SCHEMA_QUALIFIER_PLACEHOLDER)
    return normalized_sql.replace(f"{schema_name}.", SCHEMA_QUALIFIER_PLACEHOLDER)


def _table_names(connection: Connection, schema_name: str) -> tuple[str, ...]:
    table_rows = connection.execute(
        text(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = :schema_name
              AND table_type = 'BASE TABLE'
              AND table_name <> 'alembic_version'
            ORDER BY table_name
            """
        ),
        {"schema_name": schema_name},
    ).tuples()
    return tuple(str(table_name) for (table_name,) in table_rows)


def _columns(connection: Connection, schema_name: str) -> tuple[ColumnContract, ...]:
    column_rows = connection.execute(
        text(
            """
            SELECT table_rel.relname, column_attr.attname,
                   pg_catalog.format_type(column_attr.atttypid, column_attr.atttypmod),
                   NOT column_attr.attnotnull,
                   pg_catalog.pg_get_expr(column_default.adbin, column_default.adrelid)
            FROM pg_catalog.pg_attribute AS column_attr
            JOIN pg_catalog.pg_class AS table_rel
              ON table_rel.oid = column_attr.attrelid
            JOIN pg_catalog.pg_namespace AS table_namespace
              ON table_namespace.oid = table_rel.relnamespace
            LEFT JOIN pg_catalog.pg_attrdef AS column_default
              ON column_default.adrelid = table_rel.oid
             AND column_default.adnum = column_attr.attnum
            WHERE table_namespace.nspname = :schema_name
              AND table_rel.relkind IN ('r', 'p')
              AND column_attr.attnum > 0
              AND NOT column_attr.attisdropped
              AND table_rel.relname <> 'alembic_version'
            ORDER BY table_rel.relname, column_attr.attnum
            """
        ),
        {"schema_name": schema_name},
    ).tuples()
    return tuple(
        ColumnContract(
            table_name=str(table_name),
            column_name=str(column_name),
            type_sql=str(type_sql),
            nullable=bool(nullable),
            default_sql=_normalize_schema_sql(
                None if default_sql is None else str(default_sql),
                schema_name,
            ),
        )
        for table_name, column_name, type_sql, nullable, default_sql in column_rows
    )


def _constraints(
    connection: Connection,
    schema_name: str,
) -> tuple[ConstraintContract, ...]:
    constraint_rows = connection.execute(
        text(
            """
            SELECT table_rel.relname, table_constraint.conname,
                   table_constraint.contype,
                   pg_catalog.pg_get_constraintdef(table_constraint.oid, true)
            FROM pg_catalog.pg_constraint AS table_constraint
            JOIN pg_catalog.pg_class AS table_rel
              ON table_rel.oid = table_constraint.conrelid
            JOIN pg_catalog.pg_namespace AS table_namespace
              ON table_namespace.oid = table_rel.relnamespace
            WHERE table_namespace.nspname = :schema_name
              AND table_rel.relname <> 'alembic_version'
            ORDER BY table_rel.relname, table_constraint.conname
            """
        ),
        {"schema_name": schema_name},
    ).tuples()
    return tuple(
        ConstraintContract(
            table_name=str(table_name),
            constraint_name=str(constraint_name),
            constraint_kind=str(constraint_kind),
            definition_sql=_normalize_schema_sql(str(definition_sql), schema_name) or "",
        )
        for table_name, constraint_name, constraint_kind, definition_sql in constraint_rows
    )


def _indexes(connection: Connection, schema_name: str) -> tuple[IndexContract, ...]:
    index_rows = connection.execute(
        text(
            """
            SELECT table_rel.relname, index_rel.relname,
                   pg_catalog.pg_get_indexdef(index_rel.oid),
                   pg_catalog.pg_get_expr(index_meta.indpred, index_meta.indrelid)
            FROM pg_catalog.pg_index AS index_meta
            JOIN pg_catalog.pg_class AS index_rel
              ON index_rel.oid = index_meta.indexrelid
            JOIN pg_catalog.pg_class AS table_rel
              ON table_rel.oid = index_meta.indrelid
            JOIN pg_catalog.pg_namespace AS table_namespace
              ON table_namespace.oid = table_rel.relnamespace
            LEFT JOIN pg_catalog.pg_constraint AS table_constraint
              ON table_constraint.conindid = index_rel.oid
            WHERE table_namespace.nspname = :schema_name
              AND table_constraint.oid IS NULL
              AND table_rel.relname <> 'alembic_version'
            ORDER BY table_rel.relname, index_rel.relname
            """
        ),
        {"schema_name": schema_name},
    ).tuples()
    return tuple(
        IndexContract(
            table_name=str(table_name),
            index_name=str(index_name),
            definition_sql=_normalize_schema_sql(str(definition_sql), schema_name) or "",
            predicate_sql=_normalize_schema_sql(
                None if predicate_sql is None else str(predicate_sql),
                schema_name,
            ),
        )
        for table_name, index_name, definition_sql, predicate_sql in index_rows
    )


def _sequences(
    connection: Connection,
    schema_name: str,
) -> tuple[SequenceContract, ...]:
    sequence_rows = connection.execute(
        text(
            """
            SELECT sequence_rel.relname, owner_table.relname, owner_column.attname,
                   sequence_meta.data_type, sequence_meta.start_value,
                   sequence_meta.min_value, sequence_meta.max_value,
                   sequence_meta.increment_by, sequence_meta.cycle,
                   sequence_meta.cache_size
            FROM pg_catalog.pg_sequences AS sequence_meta
            JOIN pg_catalog.pg_class AS sequence_rel
              ON sequence_rel.relname = sequence_meta.sequencename
            JOIN pg_catalog.pg_namespace AS sequence_namespace
              ON sequence_namespace.oid = sequence_rel.relnamespace
             AND sequence_namespace.nspname = sequence_meta.schemaname
            LEFT JOIN pg_catalog.pg_depend AS sequence_dependency
              ON sequence_dependency.objid = sequence_rel.oid
             AND sequence_dependency.deptype IN ('a', 'i')
            LEFT JOIN pg_catalog.pg_class AS owner_table
              ON owner_table.oid = sequence_dependency.refobjid
            LEFT JOIN pg_catalog.pg_attribute AS owner_column
              ON owner_column.attrelid = owner_table.oid
             AND owner_column.attnum = sequence_dependency.refobjsubid
            WHERE sequence_namespace.nspname = :schema_name
              AND sequence_rel.relkind = 'S'
            ORDER BY sequence_rel.relname
            """
        ),
        {"schema_name": schema_name},
    ).tuples()
    return tuple(
            SequenceContract(
                sequence_name=str(sequence_name),
                owner_table=None if owner_table is None else str(owner_table),
                owner_column=None if owner_column is None else str(owner_column),
                data_type=str(data_type),
                start_value=int(start_value),
                minimum_value=int(minimum_value),
                maximum_value=int(maximum_value),
                increment_by=int(increment_by),
                cycle=bool(cycle),
                cache_size=int(cache_size),
            )
        for (
            sequence_name,
            owner_table,
            owner_column,
            data_type,
            start_value,
            minimum_value,
            maximum_value,
            increment_by,
            cycle,
            cache_size,
        ) in sequence_rows
    )


def _extensions(connection: Connection) -> tuple[str, ...]:
    extension_rows = connection.execute(
        text(
            """
            SELECT extname
            FROM pg_catalog.pg_extension
            WHERE extname = ANY(:extension_names)
            ORDER BY extname
            """
        ),
        {"extension_names": list(REQUIRED_EXTENSIONS)},
    ).tuples()
    return tuple(str(extension_name) for (extension_name,) in extension_rows)


def capture_schema_contract(
    connection: Connection,
    schema_name: str,
) -> DatabaseSchemaContract:
    return DatabaseSchemaContract(
        schema_name=schema_name,
        table_names=_table_names(connection, schema_name),
        columns=_columns(connection, schema_name),
        constraints=_constraints(connection, schema_name),
        indexes=_indexes(connection, schema_name),
        sequences=_sequences(connection, schema_name),
        extensions=_extensions(connection),
    )


def _compare_records(
    contract_part: str,
    expected_records: tuple[ContractRecord, ...],
    actual_records: tuple[ContractRecord, ...],
    record_key: Callable[[ContractRecord], Hashable],
) -> tuple[SchemaDifference, ...]:
    expected_by_key = {record_key(record): record for record in expected_records}
    actual_by_key = {record_key(record): record for record in actual_records}
    record_differences = []
    for key in sorted(expected_by_key.keys() | actual_by_key.keys(), key=str):
        expected_record = expected_by_key.get(key)
        actual_record = actual_by_key.get(key)
        if expected_record == actual_record:
            continue
        record_differences.append(
            SchemaDifference(
                contract_part=f"{contract_part}[{key!r}]",
                expected=(
                    ABSENT_CONTRACT_VALUE
                    if expected_record is None
                    else repr(expected_record)
                ),
                actual=(
                    MISSING_CONTRACT_VALUE
                    if actual_record is None
                    else repr(actual_record)
                ),
            )
        )
    return tuple(record_differences)


def compare_schema_contracts(
    expected_contract: DatabaseSchemaContract,
    actual_contract: DatabaseSchemaContract,
) -> tuple[SchemaDifference, ...]:
    return (
        *_compare_records(
            "tables",
            expected_contract.table_names,
            actual_contract.table_names,
            lambda table_name: table_name,
        ),
        *_compare_records(
            "columns",
            expected_contract.columns,
            actual_contract.columns,
            lambda column: (column.table_name, column.column_name),
        ),
        *_compare_records(
            "constraints",
            expected_contract.constraints,
            actual_contract.constraints,
            lambda constraint: (
                constraint.table_name,
                constraint.constraint_name,
            ),
        ),
        *_compare_records(
            "indexes",
            expected_contract.indexes,
            actual_contract.indexes,
            lambda index: (index.table_name, index.index_name),
        ),
        *_compare_records(
            "sequences",
            expected_contract.sequences,
            actual_contract.sequences,
            lambda sequence: sequence.sequence_name,
        ),
        *_compare_records(
            "extensions",
            expected_contract.extensions,
            actual_contract.extensions,
            lambda extension_name: extension_name,
        ),
    )


def format_schema_differences(
    schema_differences: tuple[SchemaDifference, ...],
) -> str:
    return "\n".join(
        (
            f"{schema_difference.contract_part}: "
            f"expected={schema_difference.expected} "
            f"actual={schema_difference.actual}"
        )
        for schema_difference in schema_differences
    )
