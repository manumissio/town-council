from pipeline.vote_extractor import prepare_vote_extraction_prompt


def test_vote_extractor_prompt_requires_json_only():
    prompt = prepare_vote_extraction_prompt(
        "Budget Adoption",
        "Motion was seconded and passed 5-0.",
        meeting_context="City Council - 2026-01-10",
    )
    assert "Return JSON only. No prose. No markdown." in prompt
    assert '"outcome_label": "passed|failed|deferred|continued|tabled|withdrawn|no_action|unknown"' in prompt
    assert "<start_of_turn>model\n{" in prompt
