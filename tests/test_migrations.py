from types import SimpleNamespace

from pipeline import migrate_v2, migrate_v3, migrate_v4, migrate_v5, migrate_v6


class _Conn:
    def __init__(self, responses=None):
        self.responses = responses or []
        self.calls = []
        self.commits = 0
        self._idx = 0

    def execute(self, stmt):
        self.calls.append(str(stmt))
        if self._idx < len(self.responses):
            out = self.responses[self._idx]
            self._idx += 1
            if isinstance(out, Exception):
                raise out
            return out
        self._idx += 1
        return SimpleNamespace(fetchone=lambda: None)

    def commit(self):
        self.commits += 1

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class _Engine:
    def __init__(self, conn):
        self.conn = conn

    def connect(self):
        return self.conn


def test_migrate_v2_runs_schema_and_alters(mocker):
    conn = _Conn()
    engine = _Engine(conn)
    create_all = mocker.patch.object(migrate_v2.Base.metadata, "create_all")
    mocker.patch.object(migrate_v2, "db_connect", return_value=engine)

    migrate_v2.migrate_db()

    create_all.assert_called_once_with(engine)
    assert any("ALTER TABLE event ADD COLUMN organization_id" in c for c in conn.calls)
    assert any("ALTER TABLE event_stage ADD COLUMN organization_name" in c for c in conn.calls)


def test_migrate_v3_creates_tables(mocker):
    engine = _Engine(_Conn())
    create_all = mocker.patch.object(migrate_v3.Base.metadata, "create_all")
    mocker.patch.object(migrate_v3, "db_connect", return_value=engine)

    migrate_v3.migrate_v3()

    create_all.assert_called_once_with(engine)


def test_migrate_v4_adds_column_when_missing(mocker):
    first_select = SimpleNamespace(fetchone=lambda: None)
    conn = _Conn(responses=[first_select, None])
    mocker.patch.object(migrate_v4, "db_connect", return_value=_Engine(conn))

    migrate_v4.migrate()

    assert any("SELECT column_name" in c for c in conn.calls)
    assert any("ALTER TABLE catalog ADD COLUMN related_ids" in c for c in conn.calls)


def test_migrate_v4_skips_column_when_present(mocker):
    first_select = SimpleNamespace(fetchone=lambda: ("related_ids",))
    conn = _Conn(responses=[first_select])
    mocker.patch.object(migrate_v4, "db_connect", return_value=_Engine(conn))

    migrate_v4.migrate()

    assert not any("ALTER TABLE catalog ADD COLUMN related_ids" in c for c in conn.calls)


def test_migrate_v5_is_idempotent_on_duplicate_columns(mocker):
    duplicate = Exception("duplicate column")
    responses = [duplicate, duplicate] + [duplicate] * 6
    conn = _Conn(responses=responses)
    mocker.patch.object(migrate_v5, "db_connect", return_value=_Engine(conn))

    migrate_v5.migrate()

    # Should complete without raising even when all ALTERs report duplicates.
    assert any("ALTER TABLE person ADD COLUMN is_elected" in c for c in conn.calls)


def test_migrate_v6_runs_backfill_and_index_creation(mocker):
    conn = _Conn()
    mocker.patch.object(migrate_v6, "db_connect", return_value=_Engine(conn))

    migrate_v6.migrate()

    assert any("ALTER TABLE person ADD COLUMN person_type" in c for c in conn.calls)
    assert any("CREATE INDEX IF NOT EXISTS ix_person_person_type" in c for c in conn.calls)
    assert any("UPDATE person SET person_type = 'mentioned'" in c for c in conn.calls)
    assert any("UPDATE person" in c and "SET person_type = 'official'" in c for c in conn.calls)
