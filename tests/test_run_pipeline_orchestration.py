import sys
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from pipeline import run_pipeline


def test_run_step_exits_on_subprocess_failure(mocker):
    mocker.patch("subprocess.run", side_effect=run_pipeline.subprocess.CalledProcessError(1, ["cmd"]))
    with pytest.raises(SystemExit):
        run_pipeline.run_step("bad", ["cmd"])


def test_process_document_chunk_returns_zero_when_db_unavailable(mocker):
    mocker.patch.dict(
        sys.modules,
        {"pipeline.extractor": MagicMock(), "pipeline.nlp_worker": MagicMock()},
    )
    mocker.patch("pipeline.models.db_connect", side_effect=SQLAlchemyError("db down"))
    sleep_spy = mocker.patch("time.sleep")

    processed = run_pipeline.process_document_chunk([1, 2])

    assert processed == 0
    assert sleep_spy.call_count == 3


def test_run_parallel_processing_returns_when_no_unprocessed_docs(mocker):
    fake_db = mocker.MagicMock()
    fake_db.query.return_value.filter.return_value.all.return_value = []

    class _Cond:
        def is_(self, _):
            return self

        def __or__(self, other):
            return self

    class _Catalog:
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


def test_main_runs_steps_in_expected_order(mocker):
    calls = []
    mocker.patch("pipeline.run_pipeline.run_parallel_processing", side_effect=lambda: calls.append("parallel"))

    def fake_run_step(name, command):
        calls.append((name, tuple(command)))

    mocker.patch("pipeline.run_pipeline.run_step", side_effect=fake_run_step)

    run_pipeline.main()

    assert calls[0][0] == "Seed Places"
    assert calls[1][0] == "Promote Staged Events"
    assert calls[2][0] == "Downloader"
    assert calls[3] == "parallel"
    assert calls[-1][0] == "Search Indexing"


def test_process_document_chunk_returns_count_for_missing_rows(mocker):
    db = MagicMock()
    db.get.side_effect = [None]
    db.execute.return_value = None
    mocker.patch("pipeline.models.db_connect")
    mocker.patch("sqlalchemy.orm.sessionmaker", return_value=lambda: db)
    mocker.patch.dict(sys.modules, {"pipeline.extractor": MagicMock(), "pipeline.nlp_worker": MagicMock()})

    count = run_pipeline.process_document_chunk([999])

    assert count == 0
    db.close.assert_called_once()
