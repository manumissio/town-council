from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import importlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import time
from types import ModuleType
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import DDL, Engine, create_engine, inspect, select, text
from sqlalchemy.engine import URL, make_url

from pipeline.db_schema_contracts import (
    ColumnContract,
    DatabaseSchemaContract,
    compare_schema_contracts,
    format_schema_differences,
)


ROOT = Path(__file__).resolve().parents[1]
POSTGRES_TEST_URL_ENV = "TEST_POSTGRES_DATABASE_URL"
PGVECTOR_CONTRACT_DIMENSION = 384
PGVECTOR_CONTRACT_VALUE = 0.125
BASELINE_REVISION = "0001_v10_baseline"
ROSTER_GATED_REVISION = "0002_roster_gated_people"
POST_BASELINE_REVISION = "0002_test_head"
POST_BASELINE_REVISION_SOURCE = f'''"""Test-only revision after the v10 baseline."""

from alembic import op
import sqlalchemy as sa

revision = "{POST_BASELINE_REVISION}"
down_revision = "{BASELINE_REVISION}"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "post_baseline_probe",
        sa.Column("id", sa.Integer(), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("post_baseline_probe")
'''
LEGACY_ONLY_INDEXES = {
    "ix_catalog_agenda_segmentation_attempted_at",
    "ix_catalog_agenda_segmentation_status",
    "ix_catalog_lineage_updated_at",
    "ix_semantic_embedding_hnsw",
}
APPLICATION_TABLES = {
    "agenda_item",
    "catalog",
    "data_issue",
    "document",
    "event",
    "event_stage",
    "membership",
    "organization",
    "person",
    "place",
    "semantic_embedding",
    "url_stage",
    "url_stage_hist",
}


def _migration_module() -> ModuleType:
    return importlib.import_module("pipeline.db_migration_alembic")


def _roster_migration_module() -> ModuleType:
    migration_path = (
        ROOT / "alembic" / "versions" / f"{ROSTER_GATED_REVISION}.py"
    )
    module_spec = importlib.util.spec_from_file_location(
        ROSTER_GATED_REVISION,
        migration_path,
    )
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError(f"cannot load migration module: {migration_path}")
    migration_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(migration_module)
    return migration_module


def _postgres_test_url() -> URL:
    postgres_test_url = os.getenv(POSTGRES_TEST_URL_ENV)
    if postgres_test_url:
        return make_url(postgres_test_url)
    if os.getenv("CI", "").lower() == "true":
        pytest.fail(f"{POSTGRES_TEST_URL_ENV} is required in CI")
    pytest.skip(f"{POSTGRES_TEST_URL_ENV} is not configured")


def _quote_database_name(engine: Engine, database_name: str) -> str:
    return engine.dialect.identifier_preparer.quote_identifier(database_name)


@contextmanager
def _isolated_postgres_database() -> Iterator[Engine]:
    base_url = _postgres_test_url()
    administration_url = base_url.set(database="postgres")
    administration_engine = create_engine(
        administration_url,
        isolation_level="AUTOCOMMIT",
    )
    database_name = f"tc_alembic_{uuid4().hex}"
    database_ddl_context = {
        "database_identifier": _quote_database_name(
            administration_engine,
            database_name,
        )
    }
    with administration_engine.connect() as connection:
        connection.execute(
            DDL(
                "CREATE DATABASE %(database_identifier)s",
                context=database_ddl_context,
            )
        )

    database_engine = create_engine(base_url.set(database=database_name))
    try:
        yield database_engine
    finally:
        database_engine.dispose()
        with administration_engine.connect() as connection:
            connection.execute(
                text(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = :database_name
                      AND pid <> pg_backend_pid()
                    """
                ),
                {"database_name": database_name},
            )
            connection.execute(
                DDL(
                    "DROP DATABASE %(database_identifier)s",
                    context=database_ddl_context,
                )
            )
        administration_engine.dispose()


def _current_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        if not inspect(connection).has_table("alembic_version"):
            return None
        return connection.scalar(text("SELECT version_num FROM alembic_version"))


def _all_index_names(engine: Engine) -> set[str]:
    with engine.connect() as connection:
        index_rows = connection.execute(
            text(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = current_schema()
                """
            )
        )
        return {index_name for (index_name,) in index_rows}


def _reference_schema_names(engine: Engine) -> set[str]:
    with engine.connect() as connection:
        schema_rows = connection.execute(
            text(
                """
                SELECT nspname
                FROM pg_namespace
                WHERE nspname LIKE 'tc_alembic_reference_%'
                """
            )
        )
        return {schema_name for (schema_name,) in schema_rows}


def _alembic_config(connection: object) -> Config:
    config = Config(ROOT / "alembic.ini")
    config.attributes["connection"] = connection
    return config


def _install_post_baseline_test_runtime(temporary_root: Path) -> None:
    runtime_paths = (
        Path("alembic.ini"),
        Path("alembic/env.py"),
        Path("alembic/script.py.mako"),
        Path("alembic/versions/0001_v10_baseline.py"),
    )
    for runtime_path in runtime_paths:
        destination_path = temporary_root / runtime_path
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_text(
            (ROOT / runtime_path).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    (
        temporary_root
        / "alembic"
        / "versions"
        / f"{POST_BASELINE_REVISION}.py"
    ).write_text(POST_BASELINE_REVISION_SOURCE, encoding="utf-8")


def test_alembic_runtime_contract_is_checked_in() -> None:
    assert (ROOT / "alembic.ini").is_file()
    assert (ROOT / "alembic" / "env.py").is_file()
    assert (ROOT / "alembic" / "versions" / f"{BASELINE_REVISION}.py").is_file()
    assert (
        ROOT / "alembic" / "versions" / f"{ROSTER_GATED_REVISION}.py"
    ).is_file()
    assert "alembic==1.18.5" in (
        ROOT / "pipeline" / "requirements.txt"
    ).read_text(encoding="utf-8").splitlines()
    assert not list((ROOT / "pipeline").glob("migrate_v1[1-9]*.py"))


def test_migration_facade_keeps_sqlite_as_no_op() -> None:
    migration_module = _migration_module()
    sqlite_engine = create_engine("sqlite:///:memory:")

    migration_outcome = migration_module.migrate_database(sqlite_engine)

    assert migration_outcome.status == "not_applicable"
    assert inspect(sqlite_engine).get_table_names() == []
    sqlite_engine.dispose()


def test_schema_differences_identify_exact_drifted_objects() -> None:
    expected_contract = DatabaseSchemaContract(
        schema_name="reference",
        table_names=("catalog",),
        columns=(ColumnContract("catalog", "summary", "text", True, None),),
        constraints=(),
        indexes=(),
        sequences=(),
        extensions=("vector",),
    )
    actual_contract = DatabaseSchemaContract(
        schema_name="public",
        table_names=("catalog", "unexpected_table"),
        columns=(ColumnContract("catalog", "summary", "text", False, None),),
        constraints=(),
        indexes=(),
        sequences=(),
        extensions=("vector",),
    )

    schema_differences = compare_schema_contracts(
        expected_contract,
        actual_contract,
    )
    rendered_differences = format_schema_differences(schema_differences)

    assert [difference.contract_part for difference in schema_differences] == [
        "tables['unexpected_table']",
        "columns[('catalog', 'summary')]",
    ]
    assert "actual=ColumnContract" in rendered_differences
    assert "expected=<absent>" in rendered_differences


def test_fresh_postgres_upgrade_creates_complete_head() -> None:
    migration_module = _migration_module()
    with _isolated_postgres_database() as database_engine:
        migration_outcome = migration_module.migrate_database(database_engine)

        assert migration_outcome.status == "upgraded"
        assert _current_revision(database_engine) == ROSTER_GATED_REVISION
        assert migration_module.check_database_parity(database_engine) == ()
        assert APPLICATION_TABLES <= set(inspect(database_engine).get_table_names())
        assert LEGACY_ONLY_INDEXES <= _all_index_names(database_engine)
        with database_engine.connect() as connection:
            assert connection.scalar(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM pg_extension WHERE extname = 'vector'
                    )
                    """
                )
            )
        assert _reference_schema_names(database_engine) == set()


def test_fresh_upgrade_is_idempotent() -> None:
    migration_module = _migration_module()
    with _isolated_postgres_database() as database_engine:
        first_outcome = migration_module.migrate_database(database_engine)
        first_indexes = _all_index_names(database_engine)

        second_outcome = migration_module.migrate_database(database_engine)

        assert first_outcome.status == "upgraded"
        assert second_outcome.status == "current"
        assert _current_revision(database_engine) == ROSTER_GATED_REVISION
        assert _all_index_names(database_engine) == first_indexes


def test_operator_parity_compares_against_current_head(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration_module = _migration_module()
    _install_post_baseline_test_runtime(tmp_path)
    monkeypatch.setattr(migration_module, "ROOT", tmp_path)

    with _isolated_postgres_database() as database_engine:
        migration_outcome = migration_module.migrate_database(database_engine)

        assert migration_outcome.revision == POST_BASELINE_REVISION
        assert migration_module.check_database_parity(database_engine) == ()


def test_delayed_unversioned_adopter_compares_baseline_then_reaches_head(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration_module = _migration_module()
    with _isolated_postgres_database() as database_engine:
        with database_engine.begin() as connection:
            command.upgrade(_alembic_config(connection), BASELINE_REVISION)
            connection.execute(text("DROP TABLE alembic_version"))

        _install_post_baseline_test_runtime(tmp_path)
        monkeypatch.setattr(migration_module, "ROOT", tmp_path)
        migration_outcome = migration_module.migrate_database(database_engine)

        assert migration_outcome.status == "adopted"
        assert migration_outcome.revision == POST_BASELINE_REVISION
        assert _current_revision(database_engine) == POST_BASELINE_REVISION
        assert inspect(database_engine).has_table("post_baseline_probe")
        assert migration_module.check_database_parity(database_engine) == ()


def test_sequence_settings_are_part_of_schema_parity() -> None:
    migration_module = _migration_module()
    with _isolated_postgres_database() as database_engine:
        migration_module.migrate_database(database_engine)
        with database_engine.begin() as connection:
            connection.execute(text("ALTER SEQUENCE place_id_seq INCREMENT BY 2"))

        schema_differences = migration_module.check_database_parity(database_engine)

        assert [
            difference.contract_part for difference in schema_differences
        ] == ["sequences['place_id_seq']"]


def test_baseline_unversioned_schema_is_repaired_and_adopted() -> None:
    migration_module = _migration_module()
    with _isolated_postgres_database() as database_engine:
        with database_engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION vector"))
            command.upgrade(_alembic_config(connection), BASELINE_REVISION)
            connection.execute(text("DROP TABLE alembic_version"))

        migration_outcome = migration_module.migrate_database(database_engine)

        assert migration_outcome.status == "adopted"
        assert _current_revision(database_engine) == ROSTER_GATED_REVISION
        assert _reference_schema_names(database_engine) == set()


def test_pgvector_sqlalchemy_round_trip_returns_list() -> None:
    migration_module = _migration_module()
    expected_embedding = [PGVECTOR_CONTRACT_VALUE] * PGVECTOR_CONTRACT_DIMENSION
    with _isolated_postgres_database() as database_engine:
        from pipeline.models import Base

        migration_module.migrate_database(database_engine)
        catalog_table = Base.metadata.tables["catalog"]
        semantic_embedding_table = Base.metadata.tables["semantic_embedding"]
        with database_engine.begin() as connection:
            catalog_id = connection.scalar(
                catalog_table.insert()
                .values(url_hash="pgvector-round-trip")
                .returning(catalog_table.c.id)
            )
            connection.execute(
                semantic_embedding_table.insert().values(
                    catalog_id=catalog_id,
                    model_name="pgvector-contract",
                    embedding_dim=len(expected_embedding),
                    embedding=expected_embedding,
                )
            )
            stored_embedding = connection.scalar(
                select(semantic_embedding_table.c.embedding).where(
                    semantic_embedding_table.c.catalog_id == catalog_id
                )
            )

        assert isinstance(stored_embedding, list)
        assert stored_embedding == pytest.approx(expected_embedding)


def test_direct_migration_cli_reports_retired_catalog_vectors() -> None:
    with _isolated_postgres_database() as database_engine:
        with database_engine.begin() as connection:
            command.upgrade(_alembic_config(connection), BASELINE_REVISION)
            connection.execute(text("DROP TABLE alembic_version"))
            connection.execute(
                text("ALTER TABLE catalog ADD COLUMN semantic_embedding VECTOR(384)")
            )
            connection.execute(
                text(
                    """
                    INSERT INTO catalog (url_hash, semantic_embedding)
                    VALUES (
                        'retired-vector-sentinel',
                        array_fill(0.5, ARRAY[384])::vector
                    )
                    """
                )
            )

        cli_environment = os.environ.copy()
        cli_environment["DATABASE_URL"] = database_engine.url.render_as_string(
            hide_password=False
        )
        cli_environment["PYTHONPATH"] = str(ROOT)
        completed_cli = subprocess.run(
            [sys.executable, str(ROOT / "pipeline" / "db_migrate.py")],
            cwd=ROOT,
            env=cli_environment,
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed_cli.returncode == 0
        assert "database_migration_complete" in completed_cli.stderr
        assert "status=adopted" in completed_cli.stderr
        assert f"revision={ROSTER_GATED_REVISION}" in completed_cli.stderr
        assert "retired_catalog_vector_count=1" in completed_cli.stderr
        assert _current_revision(database_engine) == ROSTER_GATED_REVISION
        assert not any(
            column["name"] == "semantic_embedding"
            for column in inspect(database_engine).get_columns("catalog")
        )


def test_unversioned_drift_aborts_without_stamp_or_data_loss() -> None:
    migration_module = _migration_module()
    with _isolated_postgres_database() as database_engine:
        with database_engine.begin() as connection:
            command.upgrade(_alembic_config(connection), BASELINE_REVISION)
            connection.execute(
                text(
                    """
                    INSERT INTO place (name, state, ocd_division_id)
                    VALUES ('Drift Sentinel', 'CA', 'ocd-division/test:drift')
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO catalog (url_hash)
                    VALUES ('drift-sentinel')
                    """
                )
            )
            connection.execute(text("DROP TABLE alembic_version"))
            connection.execute(
                text("ALTER TABLE catalog ADD COLUMN semantic_embedding VECTOR(384)")
            )
            connection.execute(
                text(
                    """
                    UPDATE catalog
                    SET semantic_embedding = array_fill(0.5, ARRAY[384])::vector
                    WHERE id = (
                        SELECT id FROM catalog ORDER BY id LIMIT 1
                    )
                    """
                )
            )
            connection.execute(text("CREATE TABLE unexpected_drift (id INTEGER PRIMARY KEY)"))

        with pytest.raises(migration_module.SchemaDriftError):
            migration_module.migrate_database(database_engine)

        assert _current_revision(database_engine) is None
        with database_engine.connect() as connection:
            assert connection.scalar(
                text(
                    """
                    SELECT count(*) FROM place
                    WHERE ocd_division_id = 'ocd-division/test:drift'
                    """
                )
            ) == 1
            assert inspect(connection).has_table("unexpected_drift")
            assert connection.scalar(
                text(
                    """
                    SELECT count(*)
                    FROM catalog
                    WHERE semantic_embedding IS NOT NULL
                    """
                )
            ) == 1
        assert _reference_schema_names(database_engine) == set()


def test_unversioned_adoption_repairs_legacy_indexes_before_stamp() -> None:
    migration_module = _migration_module()
    with _isolated_postgres_database() as database_engine:
        with database_engine.begin() as connection:
            command.upgrade(_alembic_config(connection), BASELINE_REVISION)
            connection.execute(text("DROP TABLE alembic_version"))
            for index_name in sorted(LEGACY_ONLY_INDEXES):
                quoted_index = connection.dialect.identifier_preparer.quote_identifier(
                    index_name
                )
                connection.execute(text(f"DROP INDEX {quoted_index}"))

        migration_outcome = migration_module.migrate_database(database_engine)

        assert migration_outcome.status == "adopted"
        assert _current_revision(database_engine) == ROSTER_GATED_REVISION
        assert LEGACY_ONLY_INDEXES <= _all_index_names(database_engine)


def test_second_migrator_fails_fast_when_transaction_lock_is_held() -> None:
    migration_module = _migration_module()
    with _isolated_postgres_database() as database_engine:
        with database_engine.begin() as lock_connection:
            assert lock_connection.scalar(
                text("SELECT pg_try_advisory_xact_lock(:lock_id)"),
                {"lock_id": migration_module.MIGRATION_LOCK_ID},
            )
            started_at = time.monotonic()
            with pytest.raises(migration_module.MigrationLockError):
                migration_module.migrate_database(database_engine)
            elapsed_seconds = time.monotonic() - started_at

        assert elapsed_seconds < 2
        assert _current_revision(database_engine) is None


def test_baseline_downgrade_fails_before_schema_or_data_changes() -> None:
    migration_module = _migration_module()
    with _isolated_postgres_database() as database_engine:
        migration_module.migrate_database(database_engine)
        with database_engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO place (name, state, ocd_division_id)
                    VALUES ('Downgrade Sentinel', 'CA', 'ocd-division/test:downgrade')
                    """
                )
            )

        with database_engine.begin() as connection:
            with pytest.raises(RuntimeError, match="baseline"):
                command.downgrade(_alembic_config(connection), "base")

        assert _current_revision(database_engine) == ROSTER_GATED_REVISION
        assert APPLICATION_TABLES <= set(inspect(database_engine).get_table_names())
        with database_engine.connect() as connection:
            assert connection.scalar(
                text(
                    """
                    SELECT count(*) FROM place
                    WHERE ocd_division_id = 'ocd-division/test:downgrade'
                    """
                )
            ) == 1


@pytest.mark.parametrize(
    ("legacy_counts", "expected_detail"),
    [
        (
            {
                "person": 1,
                "membership": 0,
                "catalog": 0,
            },
            "person_rows=1",
        ),
        (
            {
                "person": 0,
                "membership": 1,
                "catalog": 0,
            },
            "membership_rows=1",
        ),
        (
            {
                "person": 0,
                "membership": 0,
                "catalog": 1,
            },
            "catalogs_with_person_entities=1",
        ),
    ],
)
def test_roster_migration_refuses_each_legacy_person_source(
    monkeypatch: pytest.MonkeyPatch,
    legacy_counts: dict[str, int],
    expected_detail: str,
) -> None:
    migration = _roster_migration_module()

    class LegacyCountConnection:
        def execute(self, statement: object) -> None:
            assert "LOCK TABLE" in str(statement)

        def scalar(self, statement: object) -> int:
            statement_text = str(statement)
            if "FROM person" in statement_text:
                return legacy_counts["person"]
            if "FROM membership" in statement_text:
                return legacy_counts["membership"]
            if "FROM catalog" in statement_text:
                return legacy_counts["catalog"]
            raise AssertionError(f"unexpected migration query: {statement_text}")

    monkeypatch.setattr(migration.op, "get_bind", LegacyCountConnection)

    with pytest.raises(
        RuntimeError,
        match=(
            "T-GOV-2A migration blocked.*"
            f"{expected_detail}.*"
            "remediate_legacy_people.py --apply"
        ),
    ):
        migration.upgrade()


def test_roster_migration_rejects_unsafe_downgrade() -> None:
    migration = _roster_migration_module()

    with pytest.raises(RuntimeError, match="Roll forward"):
        migration.downgrade()


def test_roster_migration_refuses_legacy_data_before_schema_changes() -> None:
    with _isolated_postgres_database() as database_engine:
        with database_engine.begin() as connection:
            command.upgrade(_alembic_config(connection), BASELINE_REVISION)
            connection.execute(
                text(
                    """
                    INSERT INTO person (name)
                    VALUES ('Legacy Person')
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO catalog (url_hash, entities)
                    VALUES (
                        'legacy-person-entities',
                        '{"persons": ["Legacy Person"], "orgs": ["Council"]}'::json
                    )
                    """
                )
            )

        with database_engine.begin() as connection:
            with pytest.raises(
                RuntimeError,
                match=(
                    "T-GOV-2A migration blocked.*"
                    "person_rows=1.*"
                    "catalogs_with_person_entities=1.*"
                    "remediate_legacy_people.py --apply"
                ),
            ):
                command.upgrade(
                    _alembic_config(connection),
                    ROSTER_GATED_REVISION,
                )

        assert _current_revision(database_engine) == BASELINE_REVISION
        assert "legistar_client" not in {
            column["name"]
            for column in inspect(database_engine).get_columns("person")
        }


def test_roster_migration_matches_authoritative_person_schema() -> None:
    migration_module = _migration_module()
    with _isolated_postgres_database() as database_engine:
        migration_outcome = migration_module.migrate_database(database_engine)

        assert migration_outcome.revision == ROSTER_GATED_REVISION
        database_inspector = inspect(database_engine)
        organization_columns = {
            column["name"]: column
            for column in database_inspector.get_columns("organization")
        }
        person_columns = {
            column["name"]: column
            for column in database_inspector.get_columns("person")
        }
        membership_columns = {
            column["name"]: column
            for column in database_inspector.get_columns("membership")
        }
        unique_constraints = {
            constraint["name"]
            for table_name in ("organization", "person", "membership")
            for constraint in database_inspector.get_unique_constraints(
                table_name
            )
        }

        assert {
            "legistar_body_id",
            "legistar_body_guid",
            "roster_source_url",
            "roster_synced_at",
        } <= organization_columns.keys()
        assert {
            "legistar_client",
            "legistar_person_id",
            "roster_source_url",
            "roster_synced_at",
        } <= person_columns.keys()
        assert {
            "legistar_client",
            "legistar_office_record_id",
            "legistar_office_record_guid",
            "roster_source_url",
            "roster_last_modified_at",
            "roster_synced_at",
        } <= membership_columns.keys()
        assert person_columns["legistar_client"]["nullable"] is False
        assert person_columns["legistar_person_id"]["nullable"] is False
        assert membership_columns["start_date"]["nullable"] is False
        assert {
            "image_url",
            "biography",
            "current_role",
            "is_elected",
            "person_type",
        }.isdisjoint(person_columns)
        assert {
            "uq_organization_place_legistar_body",
            "uq_person_legistar_identity",
            "uq_membership_legistar_identity",
        } <= unique_constraints
        assert migration_module.check_database_parity(database_engine) == ()
