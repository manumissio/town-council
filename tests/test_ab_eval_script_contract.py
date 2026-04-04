from pathlib import Path


def test_run_ab_eval_script_contract():
    path = Path("scripts/run_ab_eval.sh")
    text = path.read_text(encoding="utf-8")

    assert "--arm <A|B>" in text
    assert "run_config.json" in text
    assert '"commit_sha"' in text
    assert '"model"' in text
    assert '"LOCAL_AI_HTTP_BASE_URL"' in text
    assert '"LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS"' in text
    assert '"INFERENCE_MEM_LIMIT"' in text
    assert "extract/$cid?force=true&ocr_fallback=false" in text
    assert "segment/$cid?force=true" in text
    assert "summarize/$cid?force=true" in text
    assert "AB_REQUIRE_60" in text
    assert "failures >5% in first 15" in text or "first-15 threshold" in text


def test_collect_script_emits_required_fields():
    path = Path("scripts/collect_ab_results.py")
    text = path.read_text(encoding="utf-8")

    for field in [
        "run_id",
        "arm",
        "model",
        "catalog_id",
        "doc_kind",
        "segment_duration_s",
        "summary_duration_s",
        "task_failed",
        "agenda_items_count",
        "summary_chars",
        "section_compliance_pass",
        "grounding_pass",
        "fallback_used",
        "partial_coverage_disclosed",
    ]:
        assert field in text


def test_collect_script_avoids_db_summary_for_failed_rows():
    path = Path("scripts/collect_ab_results.py")
    text = path.read_text(encoding="utf-8")

    assert "_summary_text_from_sources" in text
    assert 'if summarize_row.get("task_failed")' in text
    assert 'return ""' in text


def test_gemma4_profile_verification_script_contract():
    path = Path("scripts/run_gemma4_profile_verification.py")
    text = path.read_text(encoding="utf-8")

    assert "env/profiles/gemma4_e2b_second_tier.env" in text
    assert "experiment_manifest.json" in text
    assert "control_snapshot.json" in text
    assert "treatment_snapshot.json" in text
    assert "scripts/probe_local_model_candidate.py" in text
    assert "--force-recreate" in text
    assert "_assert_inference_memory" in text


def test_gemma4_host_metal_strict_swap_script_contract():
    path = Path("scripts/run_gemma4_host_metal_strict_swap.py")
    text = path.read_text(encoding="utf-8")

    assert "env/profiles/gemma4_e2b_host_metal_strict.env" in text
    assert "LOCAL_AI_HTTP_BASE_URL" in text
    assert "HOST_OLLAMA_BASE_URL" in text
    assert "docker compose stop inference" not in text  # command is structured, not shell-concatenated
    assert '"docker", "compose", "stop", "inference"' in text
    assert "--no-deps" in text
    assert "scripts/worker_healthcheck.py" in text
    assert '"docker_inference_expected_running": False' in text
    assert "_host_ollama_ps" in text
