from pipeline import migrate_v9


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class _FakeConn:
    def __init__(self, existing_columns=None):
        self.existing_columns = set(existing_columns or [])
        self.calls = []

    def execute(self, stmt, params=None):
        sql = str(stmt)
        self.calls.append((sql, params))
        if "information_schema.columns" in sql:
            table = params["table"]
            column = params["column"]
            return _ScalarResult(1 if (table, column) in self.existing_columns else None)
        return _ScalarResult(None)


class _BeginCtx:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeEngine:
    def __init__(self, conn, dialect_name="postgresql"):
        self.conn = conn
        self.dialect = type("Dialect", (), {"name": dialect_name})()

    def begin(self):
        return _BeginCtx(self.conn)


def _sql_calls(conn):
    return [sql.lower() for sql, _ in conn.calls]


def test_migrate_v9_adds_missing_lineage_columns(mocker):
    conn = _FakeConn()
    engine = _FakeEngine(conn)
    mocker.patch.object(migrate_v9, "db_connect", return_value=engine)

    migrate_v9.migrate()

    calls = _sql_calls(conn)
    assert any("alter table catalog add column lineage_id" in c for c in calls)
    assert any("alter table catalog add column lineage_confidence" in c for c in calls)
    assert any("alter table catalog add column lineage_updated_at" in c for c in calls)
    assert any("create index if not exists ix_catalog_lineage_id" in c for c in calls)


def test_migrate_v9_is_idempotent_when_columns_exist(mocker):
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
