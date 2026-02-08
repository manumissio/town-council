from pipeline import db_init


def test_init_db_calls_connect_and_create_tables(mocker):
    engine = object()
    connect = mocker.patch.object(db_init, "db_connect", return_value=engine)
    create = mocker.patch.object(db_init, "create_tables")

    db_init.init_db()

    connect.assert_called_once()
    create.assert_called_once_with(engine)
