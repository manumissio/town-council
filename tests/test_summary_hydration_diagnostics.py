from pipeline.summary_hydration_diagnostics import (
    SummaryHydrationSnapshot,
    infer_primary_root_cause,
    predict_summary_path,
)


def test_summary_hydration_diagnostics_facade_preserves_operator_exports():
    import pipeline.summary_hydration_diagnostics as diagnostics

    expected_names = (
        "SummaryHydrationSnapshot",
        "build_summary_hydration_snapshot",
        "predict_summary_path",
        "infer_primary_root_cause",
        "MISSING_CONTENT_PATH",
        "NEEDS_SEGMENTATION_PATH",
        "ELIGIBLE_AGENDA_SUMMARY_PATH",
        "ELIGIBLE_NON_AGENDA_SUMMARY_PATH",
        "BLOCKED_LOW_SIGNAL_PATH",
    )

    missing_names = [name for name in expected_names if not hasattr(diagnostics, name)]

    assert missing_names == []


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


def test_predict_summary_path_marks_missing_content_explicitly():
    result = predict_summary_path(
        "minutes",
        has_content=False,
        has_agenda_items=False,
        content=None,
    )
    assert result == "missing_content"


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


def test_infer_primary_root_cause_prefers_quality_gate_after_unscheduled_non_agenda_is_cleared():
    snapshot = SummaryHydrationSnapshot(
        city="berkeley",
        catalogs_with_content=42,
        catalogs_with_summary=30,
        missing_summary_total=12,
        agenda_missing_summary_total=0,
        agenda_missing_summary_with_items=0,
        agenda_missing_summary_without_items=0,
        non_agenda_missing_summary_total=12,
        non_agenda_summarizable=0,
        non_agenda_blocked_low_signal=12,
        agenda_segmentation_status_counts={},
        sample_catalog_ids={
            "non_agenda_missing_summary": [5, 6],
            "agenda_missing_summary_with_items": [],
            "agenda_missing_summary_without_items": [],
        },
        likely_root_cause="pending",
    )

    assert infer_primary_root_cause(snapshot) == "summary_quality_gate_blocking_non_agenda"


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


def test_load_sample_catalog_ids_preserves_scope_order_limits_and_distinct(db_session):
    from sqlalchemy import case

    from pipeline.models import AgendaItem, Catalog, Event, Place
    from pipeline.summary_hydration_diagnostic_samples import load_sample_catalog_ids

    place = Place(
        id=1,
        name="San Mateo",
        state="CA",
        ocd_division_id="ocd-division/country:us/state:ca/place:san_mateo",
    )
    event = Event(id=1, place_id=1, name="Council Meeting")
    catalogs = [
        Catalog(id=1, url_hash="non-agenda-earliest", content="minutes text", summary=None),
        Catalog(id=2, url_hash="agenda-with-items-earliest", content="agenda text", summary=None),
        Catalog(id=3, url_hash="agenda-without-items-earliest", content="agenda text", summary=None),
        Catalog(id=4, url_hash="agenda-with-items-out-of-scope", content="agenda text", summary=None),
        Catalog(id=5, url_hash="non-agenda-later", content="minutes text", summary=None),
        Catalog(id=6, url_hash="agenda-without-items-later", content="agenda text", summary=None),
    ]
    agenda_items = [
        AgendaItem(id=1, event_id=1, catalog_id=2, order=1, title="Budget"),
        AgendaItem(id=2, event_id=1, catalog_id=2, order=2, title="Housing"),
        AgendaItem(id=3, event_id=1, catalog_id=4, order=1, title="Outside scope"),
    ]
    db_session.add(place)
    db_session.add(event)
    db_session.add_all(catalogs)
    db_session.add_all(agenda_items)
    db_session.commit()

    scoped_catalog_ids = db_session.query(Catalog.id.label("id")).filter(Catalog.id.in_([1, 2, 3, 5, 6])).subquery()
    doc_kind_subquery = db_session.query(
        Catalog.id.label("catalog_id"),
        case((Catalog.id.in_([2, 3, 4, 6]), "agenda"), else_="minutes").label("doc_kind"),
    ).subquery()

    sample_catalog_ids = load_sample_catalog_ids(
        db_session,
        catalog_model=Catalog,
        agenda_item_model=AgendaItem,
        doc_kind_subquery=doc_kind_subquery,
        scoped_catalog_ids=scoped_catalog_ids,
        sample_limit=1,
    )

    assert sample_catalog_ids == {
        "non_agenda_missing_summary": [1],
        "agenda_missing_summary_with_items": [2],
        "agenda_missing_summary_without_items": [3],
    }
