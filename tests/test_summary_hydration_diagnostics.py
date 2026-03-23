from pipeline.summary_hydration_diagnostics import (
    SummaryHydrationSnapshot,
    infer_primary_root_cause,
    predict_summary_path,
)


def test_predict_summary_path_marks_agenda_without_items_as_needing_segmentation():
    result = predict_summary_path(
        "agenda",
        has_content=True,
        has_agenda_items=False,
        content="Agenda text exists but segmentation has not run yet.",
    )
    assert result == "not_generated_yet_needs_segmentation"


def test_predict_summary_path_marks_minutes_with_good_text_as_eligible():
    result = predict_summary_path(
        "minutes",
        has_content=True,
        has_agenda_items=False,
        content=(
            "The council discussed housing policy, budget updates, public works priorities, "
            "committee reports, and voted on next steps for the downtown plan."
        ),
    )
    assert result == "eligible_non_agenda_summary"


def test_infer_primary_root_cause_prefers_segmentation_when_agenda_backlog_dominates():
    snapshot = SummaryHydrationSnapshot(
        catalogs_with_content=9690,
        catalogs_with_summary=2,
        missing_summary_total=9688,
        agenda_missing_summary_total=9663,
        agenda_missing_summary_with_items=0,
        agenda_missing_summary_without_items=9663,
        non_agenda_missing_summary_total=28,
        non_agenda_summarizable=28,
        non_agenda_blocked_low_signal=0,
        agenda_segmentation_status_counts={"<null>": 9340, "empty": 325, "complete": 23},
        sample_catalog_ids={
            "non_agenda_missing_summary": [997, 998],
            "agenda_missing_summary_with_items": [],
            "agenda_missing_summary_without_items": [1, 2],
        },
        likely_root_cause="pending",
    )
    assert infer_primary_root_cause(snapshot) == "agenda_summaries_blocked_on_segmentation"
