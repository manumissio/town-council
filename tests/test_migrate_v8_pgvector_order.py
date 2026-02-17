from sqlalchemy import text

from pipeline import migrate_v8


class _FakeConn:
    def __init__(self, log):
        self.log = log

    def execute(self, stmt, *args, **kwargs):
        if isinstance(stmt, str):
            sql = stmt
        elif isinstance(stmt, type(text("x"))):
            sql = str(stmt)
        else:
            sql = str(stmt)
        self.log.append(sql.strip().lower())
        return None


class _BeginCtx:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeEngine:
    def __init__(self, log):
        self.log = log
        self.dialect = type("D", (), {"name": "postgresql"})()
        self.conn = _FakeConn(log)

    def begin(self):
        return _BeginCtx(self.conn)


def test_migrate_v8_orders_extension_before_create_all(monkeypatch):
    log = []
    engine = _FakeEngine(log)

    monkeypatch.setattr(migrate_v8, "db_connect", lambda: engine)

    def _fake_create_all(_engine):
        log.append("__create_all__")

    monkeypatch.setattr(migrate_v8.Base.metadata, "create_all", _fake_create_all)

    migrate_v8.migrate()

    create_ext_idx = next(i for i, s in enumerate(log) if "create extension if not exists vector" in s)
    create_all_idx = next(i for i, s in enumerate(log) if s == "__create_all__")
    drop_idx = next(i for i, s in enumerate(log) if "alter table catalog drop column if exists semantic_embedding" in s)
    index_idx = next(i for i, s in enumerate(log) if "create index if not exists ix_semantic_embedding_hnsw" in s)

    assert create_ext_idx < create_all_idx < drop_idx < index_idx
