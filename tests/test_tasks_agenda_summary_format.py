import logging
import sys
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import sessionmaker

sys.modules["llama_cpp"] = MagicMock()

from pipeline import agenda_segmentation_maintenance
from pipeline import agenda_summary_fallback
from pipeline import agenda_summary_inputs
from pipeline import indexer, llm as llm_module, semantic_tasks, task_runtime
from pipeline import task_summary_generation
from pipeline.inference_provider_contract import (
    InferenceProvider,
    ProviderResponseError,
    ProviderTimeoutError,
)
from pipeline.models import AgendaItem, Catalog, Document, Event, Place
from pipeline.non_agenda_summary_fallback import (
    NON_AGENDA_FALLBACK_NOTE_PREFIX,
)
from pipeline.summary_freshness import compute_agenda_items_hash


def _seed_summary_catalog(
    db_session,
    *,
    category: str,
    content: str,
    agenda_items: list[tuple[str, str, str]] | None = None,
    url: str = "https://example.com/meeting",
    location: str = "/tmp/meeting.pdf",
) -> Catalog:
    place = Place(
        name="Sample",
        state="CA",
        ocd_division_id="ocd-division/country:us/state:ca/place:sample",
        crawler_name="sample",
    )
    db_session.add(place)
    db_session.flush()
    event = Event(
        place_id=place.id,
        ocd_division_id=place.ocd_division_id,
        name="Sample City Council",
        record_date=date(2026, 2, 10),
        source="sample",
    )
    db_session.add(event)
    db_session.flush()
    catalog = Catalog(
        url_hash=f"{category}-{db_session.query(Catalog).count()}",
        location=location,
        url=url,
        content=content,
        agenda_segmentation_status="complete" if agenda_items else None,
    )
    db_session.add(catalog)
    db_session.flush()
    db_session.add(
        Document(
            place_id=place.id,
            event_id=event.id,
            catalog_id=catalog.id,
            category=category,
            url=catalog.url,
        )
    )
    for order, (title, description, agenda_result) in enumerate(
        agenda_items or [],
        start=1,
    ):
        db_session.add(
            AgendaItem(
                catalog_id=catalog.id,
                event_id=event.id,
                order=order,
                title=title,
                description=description,
                classification="Action",
                result=agenda_result,
                page_number=order,
            )
        )
    db_session.commit()
    return catalog


def _install_summary_boundaries(mocker, db_session, summary_provider):
    mocker.patch.object(
        task_runtime,
        "_session_factory",
        sessionmaker(bind=db_session.get_bind()),
    )
    mocker.patch.object(llm_module.LocalAI, "_instance", None)
    mocker.patch.object(
        llm_module,
        "get_runtime_provider",
        return_value=summary_provider,
    )
    meili_client = MagicMock()
    documents_index = MagicMock()
    indexed_document_batches: list[list[dict[str, object]]] = []
    documents_index.delete_documents.return_value = SimpleNamespace(task_uid=71)
    documents_index.add_documents.side_effect = indexed_document_batches.append
    meili_client.index.return_value = documents_index
    meili_client.wait_for_task.return_value = SimpleNamespace(
        status="succeeded",
        error=None,
    )
    mocker.patch.object(indexer.meilisearch, "Client", return_value=meili_client)
    enqueued_catalog_ids: list[int] = []
    mocker.patch.object(
        semantic_tasks.embed_catalog_task,
        "delay",
        side_effect=enqueued_catalog_ids.append,
    )
    return indexed_document_batches, enqueued_catalog_ids


def _minutes_content() -> str:
    return (
        "Council reviewed housing funding and the annual budget. Members approved "
        "transportation priorities after public comment and staff recommendations. "
        "The council requested a follow-up report for the next meeting."
    )


def test_agenda_summary_generation_uses_structured_items_and_persists_hashes(
    db_session,
    mocker,
):
    catalog = _seed_summary_catalog(
        db_session,
        category="agenda",
        content=(
            "City Council agenda includes housing policy updates, budget review, "
            "public safety briefing, and committee reports."
        ),
        agenda_items=[
            (
                "Housing Update",
                "Review housing funding and authorize the proposed budget.",
                "Approved",
            ),
            (
                "Transportation Plan",
                "Consider transportation priorities after public comment.",
                "",
            ),
        ],
    )
    summary_provider = MagicMock(spec=InferenceProvider)
    provider_prompts: list[str] = []
    provider_summary = (
        "BLUF: Council reviewed housing funding and transportation priorities.\n"
        "- Council authorized the proposed housing budget.\n"
        "- Transportation priorities followed public comment."
    )

    def summarize_agenda_items(
        prompt: str,
        *,
        temperature: float,
        max_tokens: int,
    ) -> str:
        provider_prompts.append(prompt)
        return provider_summary

    summary_provider.summarize_agenda_items.side_effect = summarize_agenda_items
    _indexed_document_batches, enqueued_catalog_ids = _install_summary_boundaries(
        mocker,
        db_session,
        summary_provider,
    )

    summary_result = task_summary_generation.generate_catalog_summary(
        db_session,
        catalog.id,
        force=True,
    )

    agenda_items = (
        db_session.query(AgendaItem)
        .filter_by(catalog_id=catalog.id)
        .order_by(AgendaItem.order)
        .all()
    )
    expected_hash = compute_agenda_items_hash(agenda_items)
    assert summary_result["status"] == "complete"
    assert summary_result["summary"].startswith("BLUF:")
    assert catalog.summary_source_hash == expected_hash
    assert catalog.agenda_items_hash == expected_hash
    provider_prompt = provider_prompts[0]
    assert "Housing Update" in provider_prompt
    assert "Transportation Plan" in provider_prompt
    assert enqueued_catalog_ids == [catalog.id]


@pytest.mark.parametrize("category", ["agenda", "agenda_html"])
def test_agenda_summary_generation_waits_for_segmentation(
    db_session,
    category,
):
    catalog = _seed_summary_catalog(
        db_session,
        category=category,
        content=(
            "Agenda text exists but segmentation has not run yet. This source contains "
            "enough substantive council meeting language to pass the quality gate."
        ),
    )

    summary_result = task_summary_generation.generate_catalog_summary(
        db_session,
        catalog.id,
        force=True,
    )

    assert summary_result["status"] == "not_generated_yet"
    assert "segmentation" in str(summary_result.get("reason") or "").lower()
    assert catalog.summary is None


@pytest.mark.parametrize(
    ("content", "expected_error"),
    [
        (
            "The system has encountered an error and could not complete your request. "
            "If the problem persists, please contact the site administrator.",
            "laserfiche_error_page_detected",
        ),
        (
            "[PAGE 1] Loading... The URL can be used to link to this page "
            "Your browser does not support the video tag.",
            "laserfiche_loading_shell_detected",
        ),
    ],
)
def test_summary_generation_blocks_laserfiche_placeholder_content(
    db_session,
    content,
    expected_error,
):
    catalog = _seed_summary_catalog(
        db_session,
        category="agenda",
        content=content,
        url="https://portal.laserfiche.com/Portal/DocView.aspx?id=1",
        location="/tmp/agenda.html",
    )

    summary_result = task_summary_generation.generate_catalog_summary(
        db_session,
        catalog.id,
        force=True,
    )

    assert summary_result == {"status": "error", "error": expected_error}
    assert catalog.summary is None


def test_maintenance_agenda_summary_is_deterministic_and_runs_side_effects(
    db_session,
    mocker,
):
    catalog = _seed_summary_catalog(
        db_session,
        category="agenda_html",
        content="Agenda with housing and budget actions for the City Council.",
        agenda_items=[
            (
                "Housing Budget",
                "Review housing funding and authorize the annual budget.",
                "Approved",
            )
        ],
    )
    summary_provider = MagicMock(spec=InferenceProvider)
    summary_provider.summarize_agenda_items.side_effect = AssertionError(
        "Deterministic agenda maintenance must not invoke inference"
    )
    summary_provider.summarize_text.side_effect = AssertionError(
        "Deterministic agenda maintenance must not invoke inference"
    )
    indexed_document_batches, enqueued_catalog_ids = _install_summary_boundaries(
        mocker,
        db_session,
        summary_provider,
    )

    summary_result = agenda_summary_fallback.summarize_catalog_with_maintenance_mode(
        catalog.id,
        summary_fallback_mode="deterministic",
    )

    assert summary_result["status"] == "complete"
    assert summary_result["completion_mode"] == "agenda_deterministic"
    db_session.expire_all()
    refreshed = db_session.get(Catalog, catalog.id)
    assert refreshed.summary.startswith("BLUF:")
    assert refreshed.summary_source_hash == refreshed.agenda_items_hash
    indexed_catalog_ids = {
        document["catalog_id"]
        for indexed_documents in indexed_document_batches
        for document in indexed_documents
    }
    assert indexed_catalog_ids == {catalog.id}
    assert enqueued_catalog_ids == [catalog.id]


def test_maintenance_minutes_summary_uses_provider_and_persists_freshness(
    db_session,
    mocker,
):
    catalog = _seed_summary_catalog(
        db_session,
        category="minutes",
        content=_minutes_content(),
    )
    summary_provider = MagicMock(spec=InferenceProvider)
    provider_prompts: list[str] = []
    provider_summary = (
        "BLUF: Council reviewed housing funding and the annual budget.\n"
        "- Members approved transportation priorities.\n"
        "- Public comment preceded staff recommendations."
    )

    def summarize_text(
        prompt: str,
        *,
        temperature: float,
        max_tokens: int,
    ) -> str:
        provider_prompts.append(prompt)
        return provider_summary

    summary_provider.summarize_text.side_effect = summarize_text
    _indexed_document_batches, enqueued_catalog_ids = _install_summary_boundaries(
        mocker,
        db_session,
        summary_provider,
    )

    summary_result = agenda_summary_fallback.summarize_catalog_with_maintenance_mode(
        catalog.id,
        force=True,
        summary_fallback_mode="deterministic",
    )

    assert summary_result["status"] == "complete"
    assert summary_result["completion_mode"] == "llm"
    db_session.expire_all()
    refreshed = db_session.get(Catalog, catalog.id)
    assert refreshed.summary.startswith("BLUF:")
    assert refreshed.summary_source_hash == refreshed.content_hash
    assert "Council reviewed housing funding" in provider_prompts[0]
    assert enqueued_catalog_ids == [catalog.id]


@pytest.mark.parametrize(
    ("provider_error", "expected_note"),
    [
        (
            ProviderTimeoutError("provider timed out"),
            "timed out while generating the summary",
        ),
        (
            ProviderResponseError("Empty response payload"),
            "returned an empty summary response",
        ),
    ],
)
def test_maintenance_minutes_uses_deterministic_fallback_for_provider_failures(
    db_session,
    mocker,
    provider_error,
    expected_note,
):
    catalog = _seed_summary_catalog(
        db_session,
        category="minutes",
        content=_minutes_content(),
    )
    summary_provider = MagicMock(spec=InferenceProvider)
    summary_provider.summarize_text.side_effect = provider_error
    _indexed_document_batches, enqueued_catalog_ids = _install_summary_boundaries(
        mocker,
        db_session,
        summary_provider,
    )

    summary_result = agenda_summary_fallback.summarize_catalog_with_optional_fallback(
        catalog.id,
        force=True,
        summary_fallback_mode="deterministic",
    )

    assert summary_result["status"] == "complete"
    assert summary_result["completion_mode"] == "deterministic_fallback"
    assert expected_note in summary_result["summary"]
    assert summary_result["reindexed"] == 1
    assert summary_result["embed_enqueued"] == 1
    db_session.expire_all()
    refreshed = db_session.get(Catalog, catalog.id)
    assert refreshed.summary_source_hash == refreshed.content_hash
    assert enqueued_catalog_ids == [catalog.id]


def test_maintenance_minutes_keeps_provider_error_when_fallback_is_disabled(
    db_session,
    mocker,
):
    catalog = _seed_summary_catalog(
        db_session,
        category="minutes",
        content=_minutes_content(),
    )
    summary_provider = MagicMock(spec=InferenceProvider)
    summary_provider.summarize_text.side_effect = ProviderResponseError(
        "Empty response payload"
    )
    indexed_document_batches, enqueued_catalog_ids = _install_summary_boundaries(
        mocker,
        db_session,
        summary_provider,
    )

    summary_result = agenda_summary_fallback.summarize_catalog_with_optional_fallback(
        catalog.id,
        force=True,
        summary_fallback_mode="none",
    )

    assert summary_result["status"] == "error"
    assert "AI Summarization returned None" in summary_result["error"]
    db_session.expire_all()
    assert db_session.get(Catalog, catalog.id).summary is None
    assert indexed_document_batches == []
    assert enqueued_catalog_ids == []


def test_maintenance_minutes_does_not_fallback_for_low_signal_content(
    db_session,
    mocker,
):
    catalog = _seed_summary_catalog(
        db_session,
        category="minutes",
        content="Minutes",
    )
    summary_provider = MagicMock(spec=InferenceProvider)
    summary_provider.summarize_text.side_effect = AssertionError(
        "Low-signal content must not invoke inference"
    )
    indexed_document_batches, enqueued_catalog_ids = _install_summary_boundaries(
        mocker,
        db_session,
        summary_provider,
    )

    summary_result = agenda_summary_fallback.summarize_catalog_with_optional_fallback(
        catalog.id,
        force=True,
        summary_fallback_mode="deterministic",
    )

    assert summary_result["status"] == "blocked_low_signal"
    db_session.expire_all()
    assert db_session.get(Catalog, catalog.id).summary is None
    assert indexed_document_batches == []
    assert enqueued_catalog_ids == []


def test_summary_fallback_event_capture_counts_non_agenda_empty_response():
    local_ai_logger = logging.getLogger("local-ai")

    with agenda_segmentation_maintenance.capture_summary_fallback_events() as events:
        local_ai_logger.error("AI Summarization failed: Empty response payload")

    assert events["empty_response"] == 1


def test_maintenance_agenda_summary_returns_bad_content_error_without_provider(
    db_session,
    mocker,
):
    catalog = _seed_summary_catalog(
        db_session,
        category="agenda",
        content=(
            "The system has encountered an error and could not complete your request. "
            "If the problem persists, please contact the site administrator."
        ),
        url="https://portal.laserfiche.com/Portal/DocView.aspx?id=2",
        location="/tmp/agenda.html",
    )
    summary_provider = MagicMock(spec=InferenceProvider)
    summary_provider.summarize_agenda_items.side_effect = AssertionError(
        "Bad agenda content must not invoke inference"
    )
    summary_provider.summarize_text.side_effect = AssertionError(
        "Bad agenda content must not invoke inference"
    )
    indexed_document_batches, enqueued_catalog_ids = _install_summary_boundaries(
        mocker,
        db_session,
        summary_provider,
    )

    summary_result = agenda_summary_fallback.summarize_catalog_with_maintenance_mode(
        catalog.id,
        summary_fallback_mode="deterministic",
    )

    assert summary_result == {
        "status": "error",
        "error": "laserfiche_error_page_detected",
    }
    assert indexed_document_batches == []
    assert enqueued_catalog_ids == []


def test_agenda_summary_input_bundle_preserves_truncation_disclosure():
    catalog = MagicMock(content="Agenda content")
    document = MagicMock(category="agenda")
    document.event = MagicMock(
        name="Council",
        record_date=date(2026, 2, 10),
    )
    agenda_items = [
        MagicMock(
            title=f"Long Agenda Item {index}",
            description="Detailed description " * 10,
            classification="Agenda Item",
            result="",
            page_number=index,
        )
        for index in range(1, 7)
    ]

    agenda_bundle = agenda_summary_inputs.build_agenda_summary_input_bundle(
        catalog=catalog,
        document=document,
        agenda_items=agenda_items,
        max_input_chars=1200,
        min_reserved_output_chars=100,
    )
    summary = llm_module._deterministic_agenda_items_summary(
        agenda_bundle["summary_items"],
        truncation_meta=agenda_bundle["truncation_meta"],
    )

    assert agenda_bundle["status"] == "ready"
    assert agenda_bundle["truncation_meta"]["items_truncated"] > 0
    disclosure = (
        f"first {agenda_bundle['truncation_meta']['items_included']} of "
        f"{agenda_bundle['truncation_meta']['items_total']} agenda items"
    )
    assert disclosure in summary.lower()
    assert NON_AGENDA_FALLBACK_NOTE_PREFIX not in summary
