from pathlib import Path


def test_run_soak_day_script_contract():
    text = Path("scripts/run_soak_day.sh").read_text(encoding="utf-8")

    assert "health_ok()" in text
    assert "HEALTH_TIMEOUT_SECONDS" in text
    assert "TASK_MAX_WAIT_SECONDS" in text
    assert "scripts/dev_up.sh" in text
    assert "[[ -f \"scripts/dev_up.sh\" ]]" in text
    assert "docker compose up -d inference worker api pipeline frontend" in text
    assert "stack_offline" in text
    assert "task_poll_timeout" in text
    assert "scripts/parse_task_launch.py" in text
    assert "invalid_task_id" in text
    assert "task_id_valid" in text
    assert "extract/$cid?force=true&ocr_fallback=false" in text
    assert "segment/$cid?force=true" in text
    assert "summarize/$cid?force=true" in text
    assert "extract_failures" in text
    assert "segment_failures" in text
    assert "summarize_failures" in text
    assert "gating_failures" in text
    assert "task_submission_failures" in text
    assert "task_poll_timeouts" in text
    assert "phase_duration_p95_s_capped" in text
    assert "run_manifest.json" in text
    assert "provider_counters_before_run" in text
    assert "provider_counters_before_run_source" in text
    assert "zero_baseline_no_provider_series" in text
    assert "worker_registry" in text
    assert "RedisProviderMetricsCollector" in text
    assert "OLLAMA_NUM_PARALLEL" in text
    assert "preflight_recovery_attempted" in text
    assert "preflight_recovery_result" in text
    assert "preflight_recovery_output" in text
    assert "non-gating extract_failures" in text
