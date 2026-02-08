import datetime

from sqlalchemy.exc import SQLAlchemyError

import pytest

pytest.importorskip("prometheus_client")
from pipeline import monitor


def test_update_metrics_populates_gauges_and_alerts_when_stale(mocker):
    stale_dt = datetime.datetime.now() - datetime.timedelta(days=8)
    scalar_values = iter([10, 7, 5, 3, stale_dt])

    class FakeResult:
        def scalar(self):
            return next(scalar_values)

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, _query):
            return FakeResult()

    fake_engine = mocker.Mock()
    fake_engine.connect.return_value = FakeConn()
    mocker.patch.object(monitor, "db_connect", return_value=fake_engine)
    print_spy = mocker.patch("builtins.print")

    monitor.update_metrics()

    assert monitor.DOCUMENTS_TOTAL._value.get() == 10
    assert monitor.DOCUMENTS_PROCESSED._value.get() == 7
    assert monitor.DOCUMENTS_SUMMARIZED._value.get() == 5
    assert monitor.EVENTS_TOTAL._value.get() == 3
    assert monitor.LAST_CRAWL_TIMESTAMP._value.get() == stale_dt.timestamp()
    assert any("ALERT: No new scraping data" in str(call.args[0]) for call in print_spy.call_args_list)


def test_update_metrics_handles_sql_errors(mocker):
    mocker.patch.object(monitor, "db_connect", side_effect=SQLAlchemyError("db down"))
    print_spy = mocker.patch("builtins.print")

    monitor.update_metrics()

    assert any("Error updating metrics" in str(call.args[0]) for call in print_spy.call_args_list)
