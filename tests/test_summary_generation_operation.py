from __future__ import annotations

import inspect
import sys
from unittest.mock import MagicMock

sys.modules["llama_cpp"] = MagicMock()

from pipeline import config, indexer, llm as llm_module, semantic_tasks, task_summary_generation
from pipeline import tasks
from pipeline.llm import LocalAIConfigError
from pipeline.models import AgendaItem, Document


class SummaryProvider:
    def __init__(self, summary: str) -> None:
        self.summary = summary
        self.summary_prompt = ""

    def health_check(self) -> bool:
        return True

    def extract_agenda(self, prompt: str, *, temperature: float, max_tokens: int) -> str | None:
        raise AssertionError("Agenda extraction is outside summary generation")

    def summarize_agenda_items(self, prompt: str, *, temperature: float, max_tokens: int) -> str | None:
        self.summary_prompt = prompt
        return self.summary

    def summarize_text(self, prompt: str, *, temperature: float, max_tokens: int) -> str | None:
        self.summary_prompt = prompt
        return self.summary

    def generate_topics(self, prompt: str, *, temperature: float, max_tokens: int) -> str | None:
        raise AssertionError("Topic generation is outside summary generation")

    def generate_json(self, prompt: str, *, max_tokens: int) -> str | None:
        raise AssertionError("JSON generation is outside summary generation")


def _catalog(*, content: str | None) -> MagicMock:
    return MagicMock(
        id=1,
        content=content,
        summary=None,
        content_hash=None,
        summary_source_hash=None,
        agenda_items_hash=None,
        agenda_segmentation_status=None,
        location="/tmp/minutes.pdf",
        url="https://example.test/minutes.pdf",
    )


def _summary_db(
    catalog: MagicMock | None,
    document: MagicMock | None,
    agenda_items: list[MagicMock] | None = None,
) -> MagicMock:
    summary_db = MagicMock()
    summary_db.get.return_value = catalog
    document_query = MagicMock()
    document_query.filter_by.return_value.first.return_value = document
    agenda_items_query = MagicMock()
    agenda_items_query.filter_by.return_value.order_by.return_value.all.return_value = agenda_items or []

    def query_for_model(model: object) -> MagicMock:
        if model is Document:
            return document_query
        if model is AgendaItem:
            return agenda_items_query
        return MagicMock()

    summary_db.query.side_effect = query_for_model
    return summary_db


def _install_summary_boundaries(mocker, provider: SummaryProvider) -> None:
    llm_module.LocalAI._instance = None
    mocker.patch.object(llm_module, "get_runtime_provider", return_value=provider)
    mocker.patch.object(indexer.meilisearch, "Client", side_effect=RuntimeError("search unavailable"))
    mocker.patch.object(semantic_tasks.embed_catalog_task, "delay", return_value=None)


def test_generate_catalog_summary_returns_error_when_catalog_is_missing(mocker):
    provider = SummaryProvider("BLUF: Council discussed housing and budget policy.")
    _install_summary_boundaries(mocker, provider)

    summary_payload = task_summary_generation.generate_catalog_summary(
        _summary_db(None, None),
        404,
        force=True,
    )

    assert summary_payload == {"error": "Catalog not found"}
    assert provider.summary_prompt == ""


def test_generate_catalog_summary_rejects_empty_content_before_inference(mocker):
    provider = SummaryProvider("BLUF: This response must not be used.")
    _install_summary_boundaries(mocker, provider)
    catalog = _catalog(content=None)
    summary_db = _summary_db(catalog, MagicMock(category="minutes"))

    summary_payload = task_summary_generation.generate_catalog_summary(
        summary_db,
        1,
        force=True,
    )

    assert summary_payload == {"error": "No content to summarize"}
    assert provider.summary_prompt == ""
    summary_db.commit.assert_not_called()


def test_generate_catalog_summary_completes_when_document_is_missing(mocker):
    provider = SummaryProvider(
        "BLUF: Council discussed housing budget public safety transportation priorities."
    )
    _install_summary_boundaries(mocker, provider)
    catalog = _catalog(
        content=(
            "Council discussed housing budget public safety transportation priorities "
            "and committee recommendations during the local government meeting."
        )
    )
    summary_db = _summary_db(catalog, None)

    summary_payload = task_summary_generation.generate_catalog_summary(
        summary_db,
        1,
        force=True,
    )

    assert summary_payload["status"] == "complete"
    assert provider.summary_prompt
    assert catalog.summary == summary_payload["summary"]
    summary_db.commit.assert_called_once()


def test_generate_summary_task_applies_configured_agenda_payload_budget(mocker):
    provider = SummaryProvider("BLUF: Council agenda covers policy and operations.")
    _install_summary_boundaries(mocker, provider)
    catalog = _catalog(
        content=(
            "City Council agenda includes housing policy, budget review, public safety, "
            "transportation, and committee reports for public discussion."
        )
    )
    document = MagicMock(category="agenda")
    document.event = MagicMock()
    document.event.name = "City Council"
    document.event.record_date = "2026-07-25"
    agenda_items = [
        MagicMock(
            title=f"Agenda Item {agenda_item_number}",
            description="Detailed agenda description " * 30,
            classification="Agenda Item",
            result="",
            page_number=agenda_item_number,
        )
        for agenda_item_number in range(1, 25)
    ]
    summary_db = _summary_db(catalog, document, agenda_items)
    mocker.patch.object(tasks, "SessionLocal", return_value=summary_db)
    mocker.patch.object(config, "AGENDA_SUMMARY_MAX_INPUT_CHARS", 1200)
    mocker.patch.object(config, "AGENDA_SUMMARY_MIN_RESERVED_OUTPUT_CHARS", 200)

    summary_payload = tasks.generate_summary_task.run(1, force=True)

    assert summary_payload["status"] == "complete"
    assert "Input truncation: included 1 of 2 items." in provider.summary_prompt
    assert "Agenda Item 1" in provider.summary_prompt
    assert "Agenda Item 2" not in provider.summary_prompt
    summary_db.close.assert_called_once()


def test_generate_summary_task_keeps_registered_contract():
    task_signature = inspect.signature(tasks.generate_summary_task.run)

    assert tasks.generate_summary_task.name == "pipeline.tasks.generate_summary_task"
    assert tasks.generate_summary_task.max_retries == 3
    assert list(task_signature.parameters) == ["catalog_id", "force"]
    assert task_signature.parameters["force"].default is False


def test_generate_summary_task_rolls_back_and_closes_on_provider_configuration_error(
    mocker,
):
    catalog = _catalog(
        content=(
            "Council discussed housing budget public safety transportation priorities "
            "and committee recommendations during the local government meeting."
        )
    )
    summary_db = _summary_db(catalog, MagicMock(category="minutes"))
    mocker.patch.object(tasks, "SessionLocal", return_value=summary_db)
    mocker.patch.object(
        llm_module,
        "get_runtime_provider",
        side_effect=LocalAIConfigError("invalid provider configuration"),
    )

    summary_payload = tasks.generate_summary_task.run(1, force=True)

    assert summary_payload == {
        "status": "error",
        "error": "invalid provider configuration",
    }
    summary_db.rollback.assert_called_once()
    summary_db.close.assert_called_once()
