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


def test_predict_summary_path_treats_agenda_html_without_items_as_needing_segmentation():
    result = predict_summary_path(
        "agenda_html",
        has_content=True,
        has_agenda_items=False,
        content="Agenda HTML text exists but segmentation has not run yet.",
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
        city=None,
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


def test_snapshot_to_dict_exposes_cumulative_and_unresolved_aliases():
    snapshot = SummaryHydrationSnapshot(
        city="san_mateo",
        catalogs_with_content=100,
        catalogs_with_summary=25,
        missing_summary_total=75,
        agenda_missing_summary_total=70,
        agenda_missing_summary_with_items=10,
        agenda_missing_summary_without_items=60,
        non_agenda_missing_summary_total=5,
        non_agenda_summarizable=5,
        non_agenda_blocked_low_signal=0,
        agenda_segmentation_status_counts={"<null>": 55, "complete": 10, "empty": 5},
        sample_catalog_ids={
            "non_agenda_missing_summary": [1],
            "agenda_missing_summary_with_items": [2],
            "agenda_missing_summary_without_items": [3],
        },
        likely_root_cause="agenda_summaries_blocked_on_segmentation",
        cumulative_catalogs_with_content=100,
        cumulative_catalogs_with_summary=25,
        unresolved_missing_summary_total=75,
        agenda_missing_summary_total_unresolved=70,
        agenda_missing_summary_with_items_unresolved=10,
        agenda_missing_summary_without_items_unresolved=60,
        non_agenda_missing_summary_total_unresolved=5,
        agenda_unresolved_segmentation_status_counts={"<null>": 55, "complete": 10, "empty": 5},
    )

    payload = snapshot.to_dict()

    assert payload["catalogs_with_summary"] == 25
    assert payload["cumulative_catalogs_with_summary"] == 25
    assert payload["missing_summary_total"] == 75
    assert payload["unresolved_missing_summary_total"] == 75
    assert payload["agenda_unresolved_segmentation_status_counts"]["<null>"] == 55
    assert payload["metric_semantics"]["catalogs_with_summary"] == "cumulative_total"
    assert payload["metric_semantics"]["agenda_segmentation_status_counts"] == "unresolved_backlog_only"
