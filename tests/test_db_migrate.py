from pipeline import db_migrate


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


def test_db_migrate_adds_legacy_columns_and_backfills(mocker):
    conn = _FakeConn()
    engine = _FakeEngine(conn)
    mocker.patch.object(db_migrate, "db_connect", return_value=engine)
    migrate_v8_spy = mocker.patch.object(db_migrate.migrate_v8, "migrate")
    migrate_v9_spy = mocker.patch.object(db_migrate.migrate_v9, "migrate")

    db_migrate.migrate()

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
    migrate_v8_spy.assert_called_once_with()
    migrate_v9_spy.assert_called_once_with()


def test_db_migrate_skips_existing_columns_but_keeps_backfills(mocker):
    existing_columns = {
        ("event", "organization_id"),
        ("event_stage", "organization_name"),
        ("catalog", "related_ids"),
        ("place", "legistar_client"),
        ("person", "is_elected"),
        ("person", "person_type"),
        ("catalog", "content_hash"),
        ("catalog", "summary_source_hash"),
        ("catalog", "topics_source_hash"),
        ("agenda_item", "page_number"),
        ("agenda_item", "text_offset"),
        ("agenda_item", "votes"),
        ("agenda_item", "raw_history"),
        ("agenda_item", "legistar_matter_id"),
        ("agenda_item", "spatial_coords"),
        ("catalog", "agenda_segmentation_status"),
        ("catalog", "agenda_segmentation_attempted_at"),
        ("catalog", "agenda_segmentation_item_count"),
        ("catalog", "agenda_segmentation_error"),
        ("catalog", "extraction_status"),
        ("catalog", "extraction_attempted_at"),
        ("catalog", "extraction_attempt_count"),
        ("catalog", "extraction_error"),
        ("catalog", "entities_source_hash"),
        ("catalog", "agenda_items_hash"),
    }
    conn = _FakeConn(existing_columns=existing_columns)
    engine = _FakeEngine(conn)
    mocker.patch.object(db_migrate, "db_connect", return_value=engine)
    migrate_v8_spy = mocker.patch.object(db_migrate.migrate_v8, "migrate")
    migrate_v9_spy = mocker.patch.object(db_migrate.migrate_v9, "migrate")

    db_migrate.migrate()

    calls = _sql_calls(conn)
    assert not any("alter table" in c and "add column" in c for c in calls)
    assert any("update catalog" in c and "set extraction_status" in c for c in calls)
    assert any("update person" in c and "set person_type = 'official'" in c for c in calls)
    migrate_v8_spy.assert_called_once_with()
    migrate_v9_spy.assert_called_once_with()


def test_db_migrate_skips_sqlite_and_runtime_submigrations(mocker):
    conn = _FakeConn()
    engine = _FakeEngine(conn, dialect_name="sqlite")
    mocker.patch.object(db_migrate, "db_connect", return_value=engine)
    migrate_v8_spy = mocker.patch.object(db_migrate.migrate_v8, "migrate")
    migrate_v9_spy = mocker.patch.object(db_migrate.migrate_v9, "migrate")

    db_migrate.migrate()

    assert conn.calls == []
    migrate_v8_spy.assert_not_called()
    migrate_v9_spy.assert_not_called()
