from __future__ import annotations


def test_agenda_text_heuristics_facade_preserves_public_imports() -> None:
    from pipeline import agenda_text_heuristics

    public_names = (
        "dedupe_agenda_items_for_document",
        "dedupe_lines_preserve_order",
        "first_alpha_char",
        "is_contact_or_letterhead_noise",
        "is_probable_line_fragment_title",
        "is_procedural_noise_title",
        "is_tabular_fragment",
        "llm_item_substance_score",
        "looks_like_agenda_segmentation_boilerplate",
        "looks_like_attendance_boilerplate",
        "looks_like_end_marker_line",
        "looks_like_sub_marker_title",
        "looks_like_teleconference_endpoint_line",
        "normalize_spaces",
        "normalized_title_key",
        "should_accept_llm_item",
        "should_stop_after_marker",
    )

    assert all(callable(getattr(agenda_text_heuristics, public_name)) for public_name in public_names)


def test_llm_agenda_text_heuristic_aliases_preserve_behavior() -> None:
    from pipeline.llm import _is_tabular_fragment, _looks_like_agenda_segmentation_boilerplate

    assert _looks_like_agenda_segmentation_boilerplate(
        "PUBLIC ADVISORY: THIS MEETING WILL BE CONDUCTED EXCLUSIVELY THROUGH VIDEOCONFERENCE"
    )
    assert _is_tabular_fragment(
        "Grant #44 | $125,000 | 02/10/2026",
        "Acct 230-99 4.5%",
        context={"has_active_parent": False},
    )
