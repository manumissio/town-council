from pathlib import Path


def test_run_ab_eval_script_contract():
    path = Path("scripts/run_ab_eval.sh")
    text = path.read_text(encoding="utf-8")

    assert "--arm <A|B>" in text
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
