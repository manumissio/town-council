import pytest

from pipeline.llm import _agenda_items_summary_is_too_short, _deterministic_agenda_items_summary


def test_agenda_items_summary_is_too_short_flags_empty_and_tiny():
    assert _agenda_items_summary_is_too_short("") is True
    assert _agenda_items_summary_is_too_short("BLUF: Hi.") is True


def test_agenda_items_summary_is_too_short_accepts_reasonable_output():
    text = (
        "BLUF: Agenda includes key land use and budget items.\n"
        "This meeting is scheduled to consider multiple proposals and updates.\n"
        "- Corridors Zoning Update\n"
        "- San Pablo Avenue Specific Plan\n"
        "- Budget Amendment\n"
    )
    assert _agenda_items_summary_is_too_short(text) is False


def test_deterministic_agenda_items_summary_includes_all_items_up_to_cap():
    items = [f"Item {i}" for i in range(1, 31)]
    out = _deterministic_agenda_items_summary(items, max_bullets=25)
    assert out.startswith("BLUF:")
    assert "Extracted 30 items from the document" in out
    assert "- Item 1" in out
    assert "- Item 25" in out
    assert "- Item 26" not in out
    assert "(+5 more)" in out


def _render_source_extract(renderer: str, items: list[object], truncation_meta: dict[str, int] | None = None) -> str:
    if renderer == "maintenance":
        from pipeline.local_ai_agenda_compat import deterministic_agenda_items_summary

        return deterministic_agenda_items_summary(items, max_bullets=25, truncation_meta=truncation_meta)
    from pipeline.agenda_summary_rendering import deterministic_agenda_items_summary

    return deterministic_agenda_items_summary(
        items, max_bullets=25, truncation_meta=truncation_meta, profile="decision_brief",
        min_item_desc_chars=20, single_item_mode="deep_brief",
    )


@pytest.mark.parametrize("renderer", ["runtime", "maintenance"])
def test_fallback_webinar_does_not_invent_priority_or_impacts(renderer: str):
    title = "Less Traffic, Better Places: How Do We Get There?"
    description = "Webinar registration and a sustainability presentation."
    summary = _render_source_extract(renderer, [{"title": title, "description": description}])
    assert title in summary
    assert description in summary
    for invented_claim in (
        "high-priority", "upcoming decisions", "scheduled consideration",
        "fiscal, policy, or procedural effects", "substantive item",
    ):
        assert invented_claim not in summary


@pytest.mark.parametrize("renderer", ["runtime", "maintenance"])
def test_fallback_preserves_approval_text_without_inventing_impacts(renderer: str):
    title = "Approve public works contract"
    description = "Authorize the contract extension for street repairs."
    summary = _render_source_extract(renderer, [{"title": title, "description": description}])
    assert title in summary
    assert description in summary
    assert "appear likely" not in summary
    assert "formal review/consideration" not in summary
    assert "Unknowns:" in summary


@pytest.mark.parametrize("renderer", ["runtime", "maintenance"])
def test_fallback_supplied_results_do_not_claim_outcomes_are_missing(renderer: str):
    summary = _render_source_extract(renderer, [
        {"title": "Approve public works contract", "result": "Approved 5-0"},
    ])
    assert "Vote outcomes are not provided" not in summary
    assert "No result was supplied" not in summary


@pytest.mark.parametrize("renderer", ["runtime", "maintenance"])
def test_fallback_missing_fields_do_not_certify_source_document_omissions(renderer: str):
    summary = _render_source_extract(renderer, [{"title": "Approve public works contract"}])
    assert "not clearly disclosed" not in summary
    assert "not provided in agenda-stage records" not in summary
    assert "Unknowns:" in summary


@pytest.mark.parametrize("renderer", ["runtime", "maintenance"])
def test_fallback_empty_input_does_not_infer_council_actions(renderer: str):
    summary = _render_source_extract(renderer, [])
    assert "Extracted 0 items" in summary
    assert "upcoming decisions" not in summary
    assert "scheduled consideration" not in summary


@pytest.mark.parametrize("renderer", ["runtime", "maintenance"])
def test_fallback_truncation_remains_explicit(renderer: str):
    summary = _render_source_extract(
        renderer, [{"title": "Approve public works contract"}],
        {"items_total": 7, "items_included": 1, "items_truncated": 6},
    )
    assert "first 1 of 7 agenda items" in summary


@pytest.mark.parametrize(("renderer", "last_shown"), [("runtime", 6), ("maintenance", 25)])
def test_fallback_rendering_limits_stay_unchanged(renderer: str, last_shown: int):
    summary = _render_source_extract(renderer, [f"Budget record {index:02d}" for index in range(1, 31)])
    assert f"\n- Budget record {last_shown:02d}" in summary
    assert f"\n- Budget record {last_shown + 1:02d}" not in summary

