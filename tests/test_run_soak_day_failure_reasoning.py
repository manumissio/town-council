from pathlib import Path


def test_run_soak_day_has_refined_failure_reasons():
    text = Path("scripts/run_soak_day.sh").read_text(encoding="utf-8")
    assert 'LAST_FAILURE_REASON="task_submission_failure"' in text
    assert 'LAST_FAILURE_REASON="task_poll_timeout"' in text
    assert 'failure_reason = "task_submission_failures"' in text
    assert 'failure_reason = "task_poll_timeout"' in text
    assert 'failure_reason = "gating_phase_failures"' in text
