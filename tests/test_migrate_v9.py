from contextlib import AbstractContextManager
from types import TracebackType

from pytest_mock import MockerFixture

from pipeline import migrate_v9


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


class _BeginCtx:
    def __init__(self, conn: _FakeConn) -> None:
        self.conn = conn

    def __enter__(self) -> _FakeConn:
        return self.conn

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: TracebackType | None,
    ) -> bool:
        return False


class _FakeEngine:
    def __init__(self, conn: _FakeConn, dialect_name: str = "postgresql") -> None:
        self.conn = conn
        self.dialect = type("Dialect", (), {"name": dialect_name})()

    def begin(self) -> AbstractContextManager[_FakeConn]:
        return _BeginCtx(self.conn)


def _sql_calls(conn: _FakeConn) -> list[str]:
    return [sql.lower() for sql, _ in conn.calls]


def test_migrate_v9_adds_missing_lineage_columns(mocker: MockerFixture) -> None:
    conn = _FakeConn()
    engine = _FakeEngine(conn)
    mocker.patch.object(migrate_v9, "db_connect", return_value=engine)

    migrate_v9.migrate()

    calls = _sql_calls(conn)
    assert any("alter table catalog add column lineage_id" in c for c in calls)
    assert any("alter table catalog add column lineage_confidence" in c for c in calls)
    assert any("alter table catalog add column lineage_updated_at" in c for c in calls)
    assert any("create index if not exists ix_catalog_lineage_id" in c for c in calls)


def test_migrate_v9_is_idempotent_when_columns_exist(mocker: MockerFixture) -> None:
    conn = _FakeConn(
        existing_columns={
            ("catalog", "lineage_id"),
            ("catalog", "lineage_confidence"),
            ("catalog", "lineage_updated_at"),
        }
    )
    engine = _FakeEngine(conn)
    mocker.patch.object(migrate_v9, "db_connect", return_value=engine)

    migrate_v9.migrate()

    calls = _sql_calls(conn)
    assert not any("alter table" in c and "lineage_" in c for c in calls)
    assert any("create index if not exists ix_catalog_lineage_id" in c for c in calls)
    assert any("create index if not exists ix_catalog_lineage_confidence" in c for c in calls)
    assert any("create index if not exists ix_catalog_lineage_updated_at" in c for c in calls)


def test_migrate_v9_uses_caller_owned_connection() -> None:
    conn = _FakeConn()

    migrate_v9.migrate(conn)

    calls = _sql_calls(conn)
    assert any("alter table catalog add column lineage_id" in c for c in calls)
