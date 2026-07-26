from pathlib import Path

import pytest
from sqlalchemy import create_engine

from pipeline import migrate_v8


class _FakeConn:
    def __init__(
        self,
        log: list[str],
        *,
        retired_catalog_vector_count: int = 0,
    ) -> None:
        self.log = log
        self.retired_catalog_vector_count = retired_catalog_vector_count
        self.dialect = type("Dialect", (), {"name": "postgresql"})()

    def execute(
        self,
        statement: object,
        _params: dict[str, str] | None = None,
    ) -> "_ScalarResult":
        sql = str(statement)
        self.log.append(sql.strip().lower())
        if "information_schema.columns" in sql:
            return _ScalarResult(1)
        if "count(*)" in sql:
            return _ScalarResult(self.retired_catalog_vector_count)
        return _ScalarResult(None)


class _ScalarResult:
    def __init__(self, value: object | None) -> None:
        self.value = value

    def scalar_one(self) -> object:
        assert self.value is not None
        return self.value

    def scalar(self) -> object | None:
        return self.value


def test_migrate_v8_uses_frozen_ddl_on_caller_owned_connection() -> None:
    log: list[str] = []
    migration_connection = _FakeConn(log)

    migrate_v8.migrate(migration_connection)

    create_ext_idx = next(i for i, s in enumerate(log) if "create extension if not exists vector" in s)
    create_table_idx = next(i for i, s in enumerate(log) if "create table if not exists semantic_embedding" in s)
    drop_idx = next(i for i, s in enumerate(log) if "alter table catalog drop column if exists semantic_embedding" in s)
    index_idx = next(i for i, s in enumerate(log) if "create index if not exists ix_semantic_embedding_hnsw" in s)

    assert create_ext_idx < create_table_idx < drop_idx < index_idx
    assert any(
        "create unique index if not exists ix_semantic_embedding_catalog_model"
        in statement
        for statement in log
    )
    assert any(
        "create unique index if not exists ix_semantic_embedding_item_model"
        in statement
        for statement in log
    )


def test_migrate_v8_returns_retired_catalog_vector_count_before_drop() -> None:
    log: list[str] = []
    migration_connection = _FakeConn(
        log,
        retired_catalog_vector_count=11,
    )

    retired_catalog_vector_count = migrate_v8.migrate(migration_connection)

    count_idx = next(
        index for index, statement in enumerate(log) if "count(*)" in statement
    )
    drop_idx = next(
        index
        for index, statement in enumerate(log)
        if "alter table catalog drop column if exists semantic_embedding" in statement
    )
    assert retired_catalog_vector_count == 11
    assert count_idx < drop_idx


def test_migrate_v8_does_not_depend_on_current_model_metadata() -> None:
    migration_source = Path("pipeline/migration_pgvector_semantic_embeddings.py").read_text(
        encoding="utf-8"
    )

    assert "pipeline.models" not in migration_source
    assert "Base.metadata" not in migration_source


def test_migrate_v8_preserves_historical_cli_entrypoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sqlite_engine = create_engine("sqlite:///:memory:")
    monkeypatch.setattr(migrate_v8, "db_connect", lambda: sqlite_engine)

    migrate_v8.migrate()

    sqlite_engine.dispose()
