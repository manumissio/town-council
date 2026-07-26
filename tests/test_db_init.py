import pytest
from sqlalchemy import create_engine

from pipeline import db_init


def test_init_db_propagates_canonical_migration_failure(mocker):
    migration_failure = RuntimeError("migration failed")
    database_engine = create_engine("sqlite:///:memory:")
    mocker.patch("pipeline.db_migrate.db_connect", return_value=database_engine)
    mocker.patch(
        "pipeline.db_migration_alembic.migrate_database",
        side_effect=migration_failure,
    )

    with pytest.raises(RuntimeError) as raised:
        db_init.init_db()

    assert raised.value is migration_failure
