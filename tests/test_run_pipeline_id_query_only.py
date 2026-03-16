from unittest.mock import MagicMock

from pipeline import run_pipeline


def test_run_parallel_processing_queries_catalog_ids_only(mocker):
    selector = mocker.patch("pipeline.run_pipeline.select_catalog_ids_for_processing", return_value=[])
    executor_spy = mocker.patch("pipeline.run_pipeline.ProcessPoolExecutor")

    run_pipeline.run_parallel_processing()

    selector.assert_called_once()
    executor_spy.assert_not_called()
