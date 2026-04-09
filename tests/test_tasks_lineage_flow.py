from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from pipeline import tasks


def _postgres_db(first_row):
    db = MagicMock()
    db.get_bind.return_value.dialect.name = "postgresql"
    db.execute.return_value.first.return_value = first_row
    return db


def test_compute_lineage_task_skips_when_recompute_already_running(mocker):
    mock_db = _postgres_db((False,))
    mocker.patch.object(tasks, "SessionLocal", return_value=mock_db)

    result = tasks.compute_lineage_task.run()

    assert result == {"status": "skipped", "reason": "lineage_recompute_in_progress"}


def test_compute_lineage_task_retries_on_retryable_errors(mocker):
    mock_db = MagicMock()
    mocker.patch.object(tasks, "SessionLocal", return_value=mock_db)
    mocker.patch.object(tasks, "run_lineage_recompute", side_effect=ValueError("broken lineage"))
    retry_exc = RuntimeError("retry-called")
    mocker.patch.object(tasks.compute_lineage_task, "retry", side_effect=retry_exc)

    with pytest.raises(RuntimeError, match="retry-called"):
        tasks.compute_lineage_task.run()

    mock_db.rollback.assert_called_once()


def test_compute_lineage_for_catalog_task_preserves_full_recompute_wrapper(mocker):
    payload = {
        "status": "complete",
        "catalog_count": 5,
        "component_count": 2,
        "merge_count": 1,
        "updated_count": 3,
    }
    mocker.patch.object(tasks.compute_lineage_task, "run", return_value=payload)

    result = tasks.compute_lineage_for_catalog_task.run(101)

    assert result == payload


def test_run_lineage_recompute_returns_complete_payload_and_records_metrics(mocker):
    from pipeline import lineage_task_support as support

    recompute_result = SimpleNamespace(
        catalog_count=7,
        component_count=3,
        merge_count=2,
        updated_count=4,
    )
    mock_db = _postgres_db((True,))
    mocker.patch.object(support, "compute_lineage_assignments", return_value=recompute_result)
    metric_spy = mocker.patch.object(support, "record_lineage_recompute")

    result = support.run_lineage_recompute(mock_db)

    assert result == {
        "status": "complete",
        "catalog_count": 7,
        "component_count": 3,
        "merge_count": 2,
        "updated_count": 4,
    }
    metric_spy.assert_called_once_with(updated_count=4, merge_count=2)


def test_run_lineage_recompute_rolls_back_when_unlock_cleanup_hits_db_error(mocker):
    from pipeline import lineage_task_support as support

    recompute_result = SimpleNamespace(
        catalog_count=7,
        component_count=3,
        merge_count=2,
        updated_count=4,
    )
    mock_db = _postgres_db((True,))
    mock_db.execute.side_effect = [
        MagicMock(first=MagicMock(return_value=(True,))),
        SQLAlchemyError("unlock failed"),
    ]
    mocker.patch.object(support, "compute_lineage_assignments", return_value=recompute_result)
    mocker.patch.object(support, "record_lineage_recompute")

    result = support.run_lineage_recompute(mock_db)

    assert result["status"] == "complete"
    mock_db.rollback.assert_called_once()
