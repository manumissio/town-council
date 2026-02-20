from pathlib import Path


def test_run_soak_day_script_contract():
    text = Path("scripts/run_soak_day.sh").read_text(encoding="utf-8")

    assert "health_ok()" in text
    assert "HEALTH_TIMEOUT_SECONDS" in text
    assert "scripts/dev_up.sh" in text
    assert "stack_offline" in text
    assert "extract/$cid?force=true&ocr_fallback=false" in text
    assert "segment/$cid?force=true" in text
    assert "summarize/$cid?force=true" in text
    assert "continue" not in text or "failures" in text

