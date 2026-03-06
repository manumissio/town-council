import sys
from unittest.mock import MagicMock

import pytest

# Avoid loading llama-cpp during unit tests.
sys.modules["llama_cpp"] = MagicMock()

from pipeline import llm as llm_mod
from pipeline import tasks
from pipeline.llm_provider import ProviderResponseError, ProviderTimeoutError
from pipeline.models import AgendaItem, Document


class _AgendaResponseErrorProvider:
    def summarize_agenda_items(self, prompt, *, temperature, max_tokens):
        _ = (prompt, temperature, max_tokens)
        raise ProviderResponseError("bad payload")


class _AgendaTimeoutProvider:
    def summarize_agenda_items(self, prompt, *, temperature, max_tokens):
        _ = (prompt, temperature, max_tokens)
        raise ProviderTimeoutError("timeout")


def _mock_agenda_summary_db():
    mock_db = MagicMock()
    catalog = MagicMock()
    catalog.id = 1
    catalog.content = (
        "City Council agenda includes housing policy updates, budget review, "
        "public safety briefing, and committee reports."
    )
    catalog.summary = None
    catalog.content_hash = "h1"
    catalog.summary_source_hash = None
    mock_db.get.return_value = catalog

    doc_query = MagicMock()
    doc_query.filter_by.return_value.first.return_value = MagicMock(category="agenda", event=None)

    items_query = MagicMock()
    items_query.filter_by.return_value.order_by.return_value.all.return_value = [
        MagicMock(title="Item One", description="Description one", classification="Agenda Item", result="", page_number=1),
        MagicMock(title="Item Two", description="Description two", classification="Agenda Item", result="", page_number=2),
    ]

    def _query_side_effect(model):
        if model is Document:
            return doc_query
        if model is AgendaItem:
            return items_query
        return MagicMock()

    mock_db.query.side_effect = _query_side_effect
    return mock_db


def test_generate_summary_task_uses_deterministic_fallback_for_provider_response_errors(mocker):
    mock_db = _mock_agenda_summary_db()
    mocker.patch.object(tasks, "SessionLocal", return_value=mock_db)
    mocker.patch.object(tasks, "reindex_catalog", lambda _catalog_id: None)
    mocker.patch.object(tasks.embed_catalog_task, "delay", return_value=None)

    llm_mod.LocalAI._instance = None
    ai = llm_mod.LocalAI()
    mocker.patch.object(ai, "_get_provider", return_value=_AgendaResponseErrorProvider())
    mocker.patch.object(tasks, "LocalAI", return_value=ai)

    retry_mock = mocker.patch.object(tasks.generate_summary_task, "retry")
    result = tasks.generate_summary_task.run(1, force=True)

    assert result["status"] == "complete"
    assert (result.get("summary") or "").startswith("BLUF:")
    retry_mock.assert_not_called()


def test_generate_summary_task_retries_for_provider_timeout_errors(mocker):
    mock_db = _mock_agenda_summary_db()
    mocker.patch.object(tasks, "SessionLocal", return_value=mock_db)
    mocker.patch.object(tasks, "reindex_catalog", lambda _catalog_id: None)
    mocker.patch.object(tasks.embed_catalog_task, "delay", return_value=None)

    llm_mod.LocalAI._instance = None
    ai = llm_mod.LocalAI()
    mocker.patch.object(ai, "_get_provider", return_value=_AgendaTimeoutProvider())
    mocker.patch.object(tasks, "LocalAI", return_value=ai)

    retry_exc = RuntimeError("retry-called")
    retry_mock = mocker.patch.object(tasks.generate_summary_task, "retry", side_effect=retry_exc)

    with pytest.raises(RuntimeError, match="retry-called"):
        tasks.generate_summary_task.run(1, force=True)

    retry_mock.assert_called_once()
    mock_db.rollback.assert_called_once()


def test_generate_topics_task_retries_on_transient_generation_errors(mocker):
    """
    Topics task should keep retry semantics for transient runtime/value errors.
    """
    mock_db = MagicMock()
    catalog = MagicMock()
    catalog.id = 1
    catalog.content = (
        "Council considered housing affordability policies and zoning updates with "
        "public comments and budget discussion."
    )
    catalog.content_hash = "h1"
    catalog.topics = None
    catalog.topics_source_hash = None

    place = MagicMock()
    place.display_name = "Berkeley"
    mock_db.get.side_effect = [catalog, place]

    doc = MagicMock()
    doc.place_id = 7
    doc_query = MagicMock()
    doc_query.filter_by.return_value.first.return_value = doc

    rows_query = MagicMock()
    rows_query.join.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
        (1, catalog.content),
        (2, "Transportation and roadway maintenance were discussed in detail."),
        (3, "Budget amendments and staffing priorities were reviewed by council."),
    ]

    def _query_side_effect(*args, **kwargs):
        _ = kwargs
        if len(args) == 1 and args[0] is tasks.Document:
            return doc_query
        return rows_query

    mock_db.query.side_effect = _query_side_effect
    mocker.patch.object(tasks, "SessionLocal", return_value=mock_db)

    class _BoomVectorizer:
        def __init__(self, *args, **kwargs):
            _ = (args, kwargs)

        def fit_transform(self, corpus):
            _ = corpus
            raise ValueError("tfidf exploded")

    mocker.patch("sklearn.feature_extraction.text.TfidfVectorizer", _BoomVectorizer)

    retry_exc = RuntimeError("retry-called")
    retry_mock = mocker.patch.object(tasks.generate_topics_task, "retry", side_effect=retry_exc)
    with pytest.raises(RuntimeError, match="retry-called"):
        tasks.generate_topics_task.run(1, force=True)

    retry_mock.assert_called_once()
    mock_db.rollback.assert_called_once()

