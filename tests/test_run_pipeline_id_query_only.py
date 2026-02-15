from unittest.mock import MagicMock

from pipeline import run_pipeline


def test_run_parallel_processing_queries_catalog_ids_only(mocker):
    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.yield_per.return_value = []

    class _Cond:
        def is_(self, _):
            return self

        def __or__(self, other):
            return self

    class _Catalog:
        id = object()
        content = _Cond()
        entities = _Cond()

    class Ctx:
        def __enter__(self):
            return fake_db

        def __exit__(self, *_):
            return False

    mocker.patch("pipeline.db_session.db_session", return_value=Ctx())
    mocker.patch("pipeline.models.Catalog", _Catalog)
    executor_spy = mocker.patch("pipeline.run_pipeline.ProcessPoolExecutor")

    run_pipeline.run_parallel_processing()

    executor_spy.assert_not_called()
    fake_db.query.assert_called_once_with(_Catalog.id)
