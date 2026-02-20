from pathlib import Path


def test_run_soak_day_script_contract():
    text = Path("scripts/run_soak_day.sh").read_text(encoding="utf-8")

    assert "health_ok()" in text
    assert "HEALTH_TIMEOUT_SECONDS" in text
    assert "TASK_MAX_WAIT_SECONDS" in text
    assert "scripts/dev_up.sh" in text
    assert "[[ -f \"scripts/dev_up.sh\" ]]" in text
    assert "docker compose up -d --build inference worker api pipeline frontend" in text
    assert "stack_offline" in text
    assert "task_poll_timeout" in text
    assert "extract/$cid?force=true&ocr_fallback=false" in text
    assert "segment/$cid?force=true" in text
    assert "summarize/$cid?force=true" in text
    assert "extract_failures" in text
    assert "segment_failures" in text
    assert "summarize_failures" in text
    assert "gating_failures" in text
    assert "non-gating extract_failures" in text
