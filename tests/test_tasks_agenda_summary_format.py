import sys
from unittest.mock import MagicMock

# Prevent importing llama-cpp during unit tests.
sys.modules["llama_cpp"] = MagicMock()

from pipeline import backlog_maintenance
from pipeline import tasks
from pipeline.models import AgendaItem, Document
from pipeline.summary_freshness import compute_agenda_items_hash


def test_generate_summary_task_agenda_requires_segmentation_and_calls_agenda_items_summarizer(mocker):
    mock_db = MagicMock()
    catalog = MagicMock()
    # Make the content pass the low-signal quality gate (>=80 chars and enough distinct tokens).
    catalog.content = (
        "City Council agenda includes housing policy updates, budget review, "
        "public safety briefing, and committee reports. Discussion and votes may occur."
    )
    catalog.summary = None
    catalog.content_hash = "h1"
    catalog.summary_source_hash = None
    mock_db.get.return_value = catalog

    doc_query = MagicMock()
    doc_query.filter_by.return_value.first.return_value = MagicMock(category="agenda")

    items_query = MagicMock()
    items_query.filter_by.return_value.order_by.return_value.all.return_value = [
        MagicMock(title="Item One", description="Description one", classification="Agenda Item", result="", page_number=1),
        MagicMock(title="Item Two", description="Description two", classification="Agenda Item", result="", page_number=2),
        MagicMock(title="Item Three", description="Description three", classification="Agenda Item", result="", page_number=3),
    ]

    def _query_side_effect(model):
        if model is Document:
            return doc_query
        if model is AgendaItem:
            return items_query
        return MagicMock()

    mock_db.query.side_effect = _query_side_effect

    mocker.patch.object(tasks, "SessionLocal", return_value=mock_db)
    mock_ai = MagicMock()
    mock_ai.summarize_agenda_items.return_value = "BLUF: Agenda focuses on core policy and operational items."
    mocker.patch.object(tasks, "LocalAI", return_value=mock_ai)

    result = tasks.generate_summary_task.run(1, force=True)
    assert result["status"] == "complete"
    summary = result["summary"]
    assert summary.startswith("BLUF:")
    expected_hash = compute_agenda_items_hash(items_query.filter_by.return_value.order_by.return_value.all.return_value)
    assert catalog.summary_source_hash == expected_hash
    assert catalog.agenda_items_hash == expected_hash
    mock_ai.summarize_agenda_items.assert_called_once()
    kwargs = mock_ai.summarize_agenda_items.call_args.kwargs
    assert isinstance(kwargs["items"], list)
    assert kwargs["items"][0]["title"] == "Item One"
    assert kwargs["items"][0]["description"] == "Description one"
    assert kwargs["truncation_meta"]["items_total"] == 3


def test_generate_summary_task_agenda_returns_not_generated_yet_when_no_items(mocker):
    mock_db = MagicMock()
    catalog = MagicMock()
    catalog.content = (
        "Agenda text exists but segmentation has not run yet, so we should block."
        " This content is long enough to pass the quality gate."
    )
    catalog.summary = None
    catalog.content_hash = "h1"
    catalog.summary_source_hash = None
    mock_db.get.return_value = catalog

    doc_query = MagicMock()
    doc_query.filter_by.return_value.first.return_value = MagicMock(category="agenda")

    items_query = MagicMock()
    items_query.filter_by.return_value.order_by.return_value.all.return_value = []

    def _query_side_effect(model):
        if model is Document:
            return doc_query
        if model is AgendaItem:
            return items_query
        return MagicMock()

    mock_db.query.side_effect = _query_side_effect

    mocker.patch.object(tasks, "SessionLocal", return_value=mock_db)
    mock_ai = MagicMock()
    mocker.patch.object(tasks, "LocalAI", return_value=mock_ai)

    result = tasks.generate_summary_task.run(1, force=True)
    assert result["status"] == "not_generated_yet"
    assert "segmentation" in (result.get("reason") or "").lower()


def test_generate_summary_task_agenda_html_returns_not_generated_yet_when_no_items(mocker):
    mock_db = MagicMock()
    catalog = MagicMock()
    catalog.content = (
        "Agenda HTML text exists but segmentation has not run yet, so we should block."
        " This content is long enough to pass the quality gate."
    )
    catalog.summary = None
    catalog.content_hash = "h1"
    catalog.summary_source_hash = None
    mock_db.get.return_value = catalog

    doc_query = MagicMock()
    doc_query.filter_by.return_value.first.return_value = MagicMock(category="agenda_html")

    items_query = MagicMock()
    items_query.filter_by.return_value.order_by.return_value.all.return_value = []

    def _query_side_effect(model):
        if model is Document:
            return doc_query
        if model is AgendaItem:
            return items_query
        return MagicMock()

    mock_db.query.side_effect = _query_side_effect

    mocker.patch.object(tasks, "SessionLocal", return_value=mock_db)
    mock_ai = MagicMock()
    mocker.patch.object(tasks, "LocalAI", return_value=mock_ai)

    result = tasks.generate_summary_task.run(1, force=True)
    assert result["status"] == "not_generated_yet"
    assert "segmentation" in (result.get("reason") or "").lower()


def test_generate_summary_task_blocks_laserfiche_error_page_content(mocker):
    mock_db = MagicMock()
    catalog = MagicMock()
    catalog.location = "/tmp/agenda.html"
    catalog.url = "https://portal.laserfiche.com/Portal/DocView.aspx?id=1"
    catalog.content = (
        "The system has encountered an error and could not complete your request. "
        "If the problem persists, please contact the site administrator."
    )
    mock_db.get.return_value = catalog

    mocker.patch.object(tasks, "SessionLocal", return_value=mock_db)
    mock_ai = MagicMock()
    mocker.patch.object(tasks, "LocalAI", return_value=mock_ai)

    result = tasks.generate_summary_task.run(1, force=True)

    assert result == {"status": "error", "error": "laserfiche_error_page_detected"}
    mock_ai.summarize.assert_not_called()
    mock_ai.summarize_agenda_items.assert_not_called()
    mock_db.commit.assert_not_called()


def test_generate_summary_task_blocks_laserfiche_loading_shell_content(mocker):
    mock_db = MagicMock()
    catalog = MagicMock()
    catalog.location = "/tmp/agenda.html"
    catalog.url = "https://portal.laserfiche.com/Portal/DocView.aspx?id=2"
    catalog.content = (
        "[PAGE 1] Loading... The URL can be used to link to this page "
        "Your browser does not support the video tag."
    )
    mock_db.get.return_value = catalog

    mocker.patch.object(tasks, "SessionLocal", return_value=mock_db)
    mock_ai = MagicMock()
    mocker.patch.object(tasks, "LocalAI", return_value=mock_ai)

    result = tasks.generate_summary_task.run(1, force=True)

    assert result == {"status": "error", "error": "laserfiche_loading_shell_detected"}
    mock_ai.summarize.assert_not_called()
    mock_ai.summarize_agenda_items.assert_not_called()
    mock_db.commit.assert_not_called()


def test_run_summary_hydration_backfill_uses_deterministic_fallback_for_provider_errors(mocker):
    mock_db = MagicMock()
    mock_db.close.return_value = None
    mocker.patch.object(tasks, "SessionLocal", return_value=mock_db)
    mocker.patch.object(tasks, "select_catalog_ids_for_summary_hydration", return_value=[101, 102])

    summarize_spy = mocker.patch.object(
        tasks,
        "summarize_catalog_with_maintenance_mode",
        side_effect=[
            {"status": "complete", "completion_mode": "llm"},
            {"status": "complete", "completion_mode": "deterministic_fallback"},
        ],
    )

    counts = tasks.run_summary_hydration_backfill(
        city="san_mateo",
        limit=2,
        summary_timeout_seconds=90,
        summary_fallback_mode="deterministic",
    )

    assert counts["selected"] == 2
    assert counts["complete"] == 2
    assert counts["llm_complete"] == 1
    assert counts["deterministic_fallback_complete"] == 1
    assert summarize_spy.call_count == 2


def test_summarize_catalog_with_maintenance_mode_prefers_deterministic_for_agenda(mocker):
    mock_session = MagicMock()
    mock_session.__enter__.return_value = mock_session
    mock_session.__exit__.return_value = False
    mock_session.query.return_value.filter_by.return_value.first.return_value = MagicMock(category="agenda_html")
    mocker.patch.object(backlog_maintenance, "db_session", return_value=mock_session)

    generate_spy = MagicMock()
    deterministic_spy = MagicMock(return_value={"status": "complete", "summary": "agenda summary"})

    result = backlog_maintenance.summarize_catalog_with_maintenance_mode(
        101,
        summary_fallback_mode="deterministic",
        generate_summary_callable=generate_spy,
        deterministic_summary_callable=deterministic_spy,
    )

    assert result["status"] == "complete"
    assert result["completion_mode"] == "agenda_deterministic"
    generate_spy.assert_not_called()
    deterministic_spy.assert_called_once_with(101)


def test_summarize_catalog_with_maintenance_mode_keeps_llm_path_for_non_agenda(mocker):
    mock_session = MagicMock()
    mock_session.__enter__.return_value = mock_session
    mock_session.__exit__.return_value = False
    mock_session.query.return_value.filter_by.return_value.first.return_value = MagicMock(category="minutes")
    mocker.patch.object(backlog_maintenance, "db_session", return_value=mock_session)

    fallback_spy = mocker.patch.object(
        backlog_maintenance,
        "summarize_catalog_with_optional_fallback",
        return_value={"status": "complete", "completion_mode": "llm"},
    )
    generate_spy = MagicMock()
    deterministic_spy = MagicMock()

    result = backlog_maintenance.summarize_catalog_with_maintenance_mode(
        202,
        summary_fallback_mode="deterministic",
        generate_summary_callable=generate_spy,
        deterministic_summary_callable=deterministic_spy,
    )

    assert result["completion_mode"] == "llm"
    fallback_spy.assert_called_once_with(
        202,
        summary_fallback_mode="deterministic",
        generate_summary_callable=generate_spy,
        deterministic_summary_callable=deterministic_spy,
    )


def test_generate_summary_task_agenda_matches_maintenance_summary_inputs(mocker):
    mock_db = MagicMock()
    catalog = MagicMock()
    catalog.content = (
        "City council agenda includes zoning updates, budget adoption, public hearings, "
        "and transportation decisions with multiple action items."
    )
    catalog.summary = None
    catalog.content_hash = None
    catalog.summary_source_hash = None
    catalog.agenda_items_hash = None
    mock_db.get.return_value = catalog

    doc = MagicMock(category="agenda")
    doc.event = MagicMock(name="City Council", record_date="2026-02-10")

    agenda_items = [
        MagicMock(title="Housing Update", description="Discuss housing pipeline.", classification="Agenda Item", result="", page_number=1),
        MagicMock(title="Public Comment", description="Take public comment.", classification="Agenda Item", result="", page_number=2),
        MagicMock(title="Budget Adoption", description="Adopt the annual budget.", classification="Agenda Item", result="Approved", page_number=3),
    ]

    def _query_side_effect(model):
        query = MagicMock()
        if model is Document:
            query.filter_by.return_value.first.return_value = doc
        elif model is AgendaItem:
            query.filter_by.return_value.order_by.return_value.all.return_value = agenda_items
        return query

    mock_db.query.side_effect = _query_side_effect
    mocker.patch.object(tasks, "SessionLocal", return_value=mock_db)
    mocker.patch.object(tasks, "classify_catalog_bad_content", return_value=None)
    mocker.patch.object(tasks, "reindex_catalog")
    mocker.patch.object(tasks.embed_catalog_task, "delay")

    agenda_bundle = backlog_maintenance.build_agenda_summary_input_bundle(
        catalog=catalog,
        document=doc,
        agenda_items=agenda_items,
    )
    expected_summary = backlog_maintenance.llm_mod._deterministic_agenda_items_summary(
        agenda_bundle["summary_items"],
        truncation_meta=agenda_bundle["truncation_meta"],
    )

    fake_ai = MagicMock()
    fake_ai.summarize_agenda_items.side_effect = (
        lambda *, meeting_title, meeting_date, items, truncation_meta: backlog_maintenance.llm_mod._deterministic_agenda_items_summary(
            items,
            truncation_meta=truncation_meta,
        )
    )
    mocker.patch.object(tasks, "LocalAI", return_value=fake_ai)

    result = tasks.generate_summary_task.run(1, force=True)

    assert result["status"] == "complete"
    assert result["summary"] == expected_summary
    assert catalog.summary == expected_summary
    assert catalog.agenda_items_hash == agenda_bundle["agenda_items_hash"]
    assert catalog.summary_source_hash == agenda_bundle["agenda_items_hash"]


def test_build_agenda_summary_input_bundle_preserves_truncation_disclosure(monkeypatch):
    catalog = MagicMock(content="Agenda content")
    doc = MagicMock(category="agenda")
    doc.event = MagicMock(name="Council", record_date="2026-02-10")
    agenda_items = [
        MagicMock(
            title=f"Long Agenda Item {index}",
            description="Detailed description " * 6,
            classification="Agenda Item",
            result="",
            page_number=index,
        )
        for index in range(1, 7)
    ]

    monkeypatch.setattr(backlog_maintenance, "AGENDA_SUMMARY_MAX_INPUT_CHARS", 220)
    monkeypatch.setattr(backlog_maintenance, "AGENDA_SUMMARY_MIN_RESERVED_OUTPUT_CHARS", 100)

    agenda_bundle = backlog_maintenance.build_agenda_summary_input_bundle(
        catalog=catalog,
        document=doc,
        agenda_items=agenda_items,
    )
    summary = backlog_maintenance.llm_mod._deterministic_agenda_items_summary(
        agenda_bundle["summary_items"],
        truncation_meta=agenda_bundle["truncation_meta"],
    )

    assert agenda_bundle["status"] == "ready"
    assert agenda_bundle["truncation_meta"]["items_truncated"] > 0
    assert f"first {agenda_bundle['truncation_meta']['items_included']} of {agenda_bundle['truncation_meta']['items_total']} agenda items" in summary.lower()
