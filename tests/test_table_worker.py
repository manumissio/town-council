import importlib
import sys
from types import SimpleNamespace


class _Ctx:
    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, *_):
        return False


def _load_table_worker(mocker):
    fake_camelot = SimpleNamespace(read_pdf=mocker.MagicMock())
    mocker.patch.dict(sys.modules, {"camelot": fake_camelot})
    module = importlib.import_module("pipeline.table_worker")
    return module, fake_camelot


def test_process_single_pdf_marks_non_pdf_as_empty_tables(mocker):
    tw, _camelot = _load_table_worker(mocker)
    record = SimpleNamespace(id=1, location="/tmp/doc.txt", filename="doc.txt", tables=None)
    session = mocker.MagicMock()
    session.get.return_value = record
    mocker.patch.object(tw, "db_session", return_value=_Ctx(session))
    mocker.patch.object(tw.os.path, "exists", return_value=True)

    result = tw.process_single_pdf(1)

    assert result == 1
    assert record.tables == []
    session.commit.assert_called_once()


def test_process_single_pdf_uses_stream_fallback_when_lattice_fails(mocker):
    tw, camelot = _load_table_worker(mocker)
    record = SimpleNamespace(id=2, location="/tmp/doc.pdf", filename="doc.pdf", tables=None)
    session = mocker.MagicMock()
    session.get.return_value = record

    table = SimpleNamespace(
        accuracy=99,
        df=SimpleNamespace(fillna=lambda _v: SimpleNamespace(values=SimpleNamespace(tolist=lambda: [["A", "B"]]))),
    )
    camelot.read_pdf.side_effect = [ValueError("lattice failed"), [table]]

    mocker.patch.object(tw, "db_session", return_value=_Ctx(session))
    mocker.patch.object(tw.os.path, "exists", return_value=True)

    result = tw.process_single_pdf(2)

    assert result == 1
    assert record.tables == [[["A", "B"]]]
    assert camelot.read_pdf.call_count == 2
    session.commit.assert_called_once()


def test_process_single_pdf_handles_indexerror_as_broken_pdf(mocker):
    tw, camelot = _load_table_worker(mocker)
    record = SimpleNamespace(id=3, location="/tmp/broken.pdf", filename="broken.pdf", tables=None)
    session = mocker.MagicMock()
    session.get.return_value = record
    # Both parser strategies fail on malformed page metadata.
    camelot.read_pdf.side_effect = [IndexError("bad page tree"), IndexError("bad page tree")]

    mocker.patch.object(tw, "db_session", return_value=_Ctx(session))
    mocker.patch.object(tw.os.path, "exists", return_value=True)

    result = tw.process_single_pdf(3)

    assert result == 1
    assert record.tables == []
    assert camelot.read_pdf.call_count == 2
    session.commit.assert_called_once()


def test_run_table_pipeline_returns_when_nothing_to_process(mocker):
    tw, _camelot = _load_table_worker(mocker)
    session = mocker.MagicMock()
    session.query.return_value.filter.return_value.all.return_value = []
    mocker.patch.object(tw, "db_session", return_value=_Ctx(session))
    executor_spy = mocker.patch.object(tw, "ProcessPoolExecutor")

    tw.run_table_pipeline()

    executor_spy.assert_not_called()


def test_run_table_pipeline_submits_jobs_and_counts_progress(mocker):
    tw, _camelot = _load_table_worker(mocker)
    docs = [SimpleNamespace(id=1), SimpleNamespace(id=2)]
    session = mocker.MagicMock()
    session.query.return_value.filter.return_value.all.return_value = docs
    mocker.patch.object(tw, "db_session", return_value=_Ctx(session))
    mocker.patch.object(tw, "TABLE_PROGRESS_LOG_INTERVAL", 1)

    future1 = mocker.MagicMock()
    future1.result.return_value = 1
    future2 = mocker.MagicMock()
    future2.result.return_value = 1

    class ExecCtx:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def submit(self, *_):
            return future1 if not hasattr(self, "_seen") else future2

    exec_obj = ExecCtx()
    exec_obj._seen = False

    def submit_side_effect(fn, cid):
        if cid == 1:
            exec_obj._seen = True
            return future1
        return future2

    mocker.patch.object(exec_obj, "submit", side_effect=submit_side_effect)
    mocker.patch.object(tw, "ProcessPoolExecutor", return_value=exec_obj)
    mocker.patch.object(tw, "as_completed", return_value=[future1, future2])

    tw.run_table_pipeline()

    assert future1.result.called
    assert future2.result.called
