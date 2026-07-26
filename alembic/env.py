from alembic import context
from sqlalchemy.engine import Connection

from pipeline.models import Base, db_connect


config = context.config

target_metadata = Base.metadata
VERSION_TABLE_SCHEMA_ATTRIBUTE = "version_table_schema"
CONNECTION_ATTRIBUTE = "connection"


def run_migrations_offline() -> None:
    raise RuntimeError(
        "Town Council migrations require an online database connection."
    )


def _configure_connection(connection: Connection) -> None:
    version_table_schema = config.attributes.get(VERSION_TABLE_SCHEMA_ATTRIBUTE)
    if version_table_schema is not None and not isinstance(version_table_schema, str):
        raise TypeError("Alembic version_table_schema must be a string.")
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        version_table_schema=version_table_schema,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    supplied_connection = config.attributes.get(CONNECTION_ATTRIBUTE)
    if supplied_connection is not None:
        if not isinstance(supplied_connection, Connection):
            raise TypeError("Alembic connection attribute must be a Connection.")
        _configure_connection(supplied_connection)
        return

    engine = db_connect()
    try:
        with engine.begin() as connection:
            _configure_connection(connection)
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
