import ast
from pathlib import Path
from types import SimpleNamespace

from pipeline import topic_generation
from pipeline import topic_generation_task
from pipeline.topic_generation import TopicGenerationTaskServices


def test_topic_generation_facade_exports_current_contract():
    expected_names = [
        "CITY_STOP_WORDS",
        "TopicGenerationTaskServices",
        "TopicWorkerServices",
        "_sanitize_text_for_topics",
        "_english_stop_words",
        "_tfidf_vectorizer",
        "_top_indices",
        "_place_tokens",
        "_topic_stop_words",
        "_normal_topic_title",
        "_small_corpus_keywords",
        "_tfidf_keywords_for_target",
        "_persist_topics",
        "_reindex_single_catalog",
        "run_generate_topics_task_family",
        "_batch_records",
        "_reindex_touched_catalogs",
        "run_topic_tagger_family",
    ]

    missing_names = [name for name in expected_names if not hasattr(topic_generation, name)]

    assert missing_names == []


def test_topic_generation_modules_do_not_import_facade():
    module_paths = [
        Path("pipeline/topic_generation_contracts.py"),
        Path("pipeline/topic_generation_text.py"),
        Path("pipeline/topic_generation_keywords.py"),
        Path("pipeline/topic_generation_task.py"),
        Path("pipeline/topic_generation_batch.py"),
    ]
    offenders: list[str] = []

    for module_path in module_paths:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "pipeline.topic_generation":
                offenders.append(str(module_path))
            if isinstance(node, ast.Import):
                offenders.extend(str(module_path) for alias in node.names if alias.name == "pipeline.topic_generation")

    assert offenders == []


def test_place_name_tokens_remain_topic_stop_words():
    class _TopicSession:
        def get(self, _model, _place_id):
            return SimpleNamespace(display_name="San Leandro City Council")

    stop_words = topic_generation._topic_stop_words(topic_generation._place_tokens(_TopicSession(), 7, SimpleNamespace))

    assert "leandro" in stop_words


def test_single_catalog_reindex_failure_is_non_gating(caplog):
    def _failing_reindex(_catalog_id: int) -> None:
        raise RuntimeError("search unavailable")

    services = TopicGenerationTaskServices(
        catalog_model=SimpleNamespace,
        document_model=SimpleNamespace,
        place_model=SimpleNamespace,
        compute_content_hash=lambda content: content,
        analyze_source_text=lambda content: content,
        is_source_topicable=lambda quality: True,
        build_low_signal_message=lambda quality: str(quality),
        postprocess_extracted_text=lambda text: text,
        extract_agenda_titles_from_text=lambda text, **kwargs: [],
        reindex_catalog=_failing_reindex,
    )

    topic_generation._reindex_single_catalog(42, services)

    assert "topic_extraction.reindex_failed catalog_id=42 error=search unavailable" in caplog.text


def test_empty_tfidf_topics_still_mark_catalog_complete(monkeypatch):
    class _CatalogModel:
        id = "catalog_id"
        content = "catalog_content"

    class _DocumentModel:
        __name__ = "Document"

    catalog_id = 42
    catalog = SimpleNamespace(
        content="unique target words",
        content_hash=None,
        topics=None,
        topics_source_hash=None,
    )
    document = SimpleNamespace(catalog_id=catalog_id, place_id=None)

    class _TopicQuery:
        def filter_by(self, **_kwargs):
            return self

        def first(self):
            return document

    class _TopicSession:
        committed = False

        def get(self, model, _id):
            if model is _CatalogModel:
                return catalog
            return None

        def query(self, *_models):
            return _TopicQuery()

        def commit(self):
            self.committed = True

    services = TopicGenerationTaskServices(
        catalog_model=_CatalogModel,
        document_model=_DocumentModel,
        place_model=SimpleNamespace,
        compute_content_hash=lambda content: f"hash:{content}",
        analyze_source_text=lambda content: content,
        is_source_topicable=lambda quality: True,
        build_low_signal_message=lambda quality: str(quality),
        postprocess_extracted_text=lambda text: text,
        extract_agenda_titles_from_text=lambda text, **kwargs: [],
        reindex_catalog=lambda _catalog_id: None,
    )
    session = _TopicSession()
    monkeypatch.setattr(
        topic_generation_task,
        "_corpus_rows_for_document",
        lambda *_args, **_kwargs: [
            (catalog_id, catalog.content),
            (catalog_id + 1, "budget hearing"),
            (catalog_id + 2, "zoning appeal"),
        ],
    )
    monkeypatch.setattr(topic_generation_task, "_topic_keywords", lambda **_kwargs: [])

    outcome = topic_generation.run_generate_topics_task_family(
        session,
        catalog_id,
        force=True,
        max_corpus_docs=10,
        services=services,
    )

    assert outcome == {"status": "complete", "topics": []}
    assert catalog.topics == []
    assert catalog.topics_source_hash == "hash:unique target words"
    assert session.committed is True
