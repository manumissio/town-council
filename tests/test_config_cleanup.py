import ast
import importlib
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType

import pytest


EXPECTED_CONFIG_EXPORTS = {
    "AGENDA_BATCH_SIZE",
    "AGENDA_FALLBACK_MAX_CONSECUTIVE_REJECTS_PER_PAGE",
    "AGENDA_FALLBACK_MAX_ITEMS_PER_DOC",
    "AGENDA_FALLBACK_MAX_ITEMS_PER_PAGE_PARAGRAPH",
    "AGENDA_MIN_SUBSTANTIVE_DESC_CHARS",
    "AGENDA_MIN_TITLE_CHARS",
    "AGENDA_PROCEDURAL_REJECT_ENABLED",
    "AGENDA_SEGMENTATION_MODE",
    "AGENDA_SEGMENT_MAINTENANCE_TIMEOUT_SECONDS",
    "AGENDA_SUMMARY_MAX_BULLETS",
    "AGENDA_SUMMARY_MAX_INPUT_CHARS",
    "AGENDA_SUMMARY_MIN_ITEM_DESC_CHARS",
    "AGENDA_SUMMARY_MIN_RESERVED_OUTPUT_CHARS",
    "AGENDA_SUMMARY_PROFILE",
    "AGENDA_SUMMARY_SINGLE_ITEM_MODE",
    "AGENDA_SUMMARY_TEMPERATURE",
    "AGENDA_TOC_DEDUP_FUZZ",
    "APP_ENV",
    "CITY_SEGMENTATION_WORKERS",
    "DB_RETRY_DELAY_MAX",
    "DB_RETRY_DELAY_MIN",
    "DOCUMENT_CHUNK_SIZE",
    "DOWNLOAD_TIMEOUT_SECONDS",
    "DOWNLOAD_WORKERS",
    "EMBEDDING_BATCH_SIZE",
    "ENABLE_VOTE_EXTRACTION",
    "ENTITY_BACKFILL_IN_PROCESS_THRESHOLD",
    "EXTRACTION_BATCH_SIZE",
    "EXTRACTION_TERMINAL_FAILURE_MAX_ATTEMPTS",
    "FAISS_TOP_NEIGHBORS",
    "FEATURE_TRENDS_DASHBOARD",
    "FILE_WRITE_CHUNK_SIZE",
    "LEGISTAR_EVENT_ITEMS_CAPABILITY_TTL_SECONDS",
    "LINEAGE_MIN_EDGE_CONFIDENCE",
    "LINEAGE_REQUIRE_MUTUAL_EDGES",
    "LLM_AGENDA_MAX_TEXT",
    "LLM_AGENDA_MAX_TOKENS",
    "LLM_CONTEXT_WINDOW",
    "LLM_SUMMARY_MAX_TEXT",
    "LLM_SUMMARY_MAX_TOKENS",
    "LOCAL_AI_ALLOW_MULTIPROCESS",
    "LOCAL_AI_BACKEND",
    "LOCAL_AI_HTTP_API",
    "LOCAL_AI_HTTP_BASE_URL",
    "LOCAL_AI_HTTP_MAX_RETRIES",
    "LOCAL_AI_HTTP_MODEL",
    "LOCAL_AI_HTTP_PROFILE",
    "LOCAL_AI_HTTP_TIMEOUT_SECONDS",
    "LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS",
    "LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS",
    "LOCAL_AI_HTTP_TIMEOUT_TOPICS_SECONDS",
    "LOCAL_AI_REQUIRE_SOLO_POOL",
    "MAX_CONTENT_LENGTH",
    "MAX_FILE_SIZE_BYTES",
    "MAX_RELATED_DOCS",
    "MAX_SUMMARY_TEXT_LENGTH",
    "MAX_WORKERS",
    "MEILISEARCH_BATCH_SIZE",
    "NLP_ENTITY_AGENDA_MAX_TEXT",
    "NLP_ENTITY_MIN_CAPITALIZED_NAME_CUES",
    "NLP_ENTITY_NONAGENDA_MAX_TEXT",
    "NLP_ENTITY_PREFIX_FALLBACK_TEXT",
    "NLP_MAX_TEXT_LENGTH",
    "PIPELINE_CPU_FRACTION",
    "PIPELINE_ONBOARDING_CITY",
    "PIPELINE_ONBOARDING_DOCUMENT_CHUNK_SIZE",
    "PIPELINE_ONBOARDING_MAX_WORKERS",
    "PIPELINE_ONBOARDING_STARTED_AT_UTC",
    "PIPELINE_RUNTIME_PROFILE",
    "PROGRESS_LOG_INTERVAL",
    "SEMANTIC_ALLOW_MULTIPROCESS",
    "SEMANTIC_BACKEND",
    "SEMANTIC_BASE_TOP_K",
    "SEMANTIC_CONTENT_MAX_CHARS",
    "SEMANTIC_ENABLED",
    "SEMANTIC_FILTER_EXPANSION_FACTOR",
    "SEMANTIC_INDEX_DIR",
    "SEMANTIC_MAX_TOP_K",
    "SEMANTIC_MODEL_NAME",
    "SEMANTIC_RERANK_CANDIDATE_LIMIT",
    "SEMANTIC_REQUIRE_FAISS",
    "SEMANTIC_REQUIRE_SINGLE_PROCESS",
    "SIMILARITY_CONTENT_LENGTH",
    "SIMILARITY_THRESHOLD",
    "STARTUP_PURGE_ALLOW_NON_DEV",
    "STARTUP_PURGE_DERIVED",
    "SUMMARY_GROUNDING_MIN_COVERAGE",
    "SUMMARY_HYDRATION_MAINTENANCE_TIMEOUT_SECONDS",
    "SUMMARY_MAX_BOILERPLATE_RATIO",
    "SUMMARY_MIN_CHARS",
    "SUMMARY_MIN_DISTINCT_TOKENS",
    "TABLE_ACCURACY_MIN",
    "TABLE_PROGRESS_LOG_INTERVAL",
    "TABLE_SCAN_MAX_PAGES",
    "TABLE_WORKER_CPU_FRACTION",
    "TEXT_REPAIR_ENABLE_LLM_ESCALATION",
    "TEXT_REPAIR_LLM_MAX_LINES_PER_DOC",
    "TEXT_REPAIR_MIN_IMPLAUSIBILITY_SCORE",
    "TFIDF_MAX_DF",
    "TFIDF_MAX_FEATURES",
    "TFIDF_MIN_DF",
    "TFIDF_NGRAM_RANGE",
    "TIKA_MIN_EXTRACTED_CHARS_FOR_NO_OCR",
    "TIKA_OCR_FALLBACK_ENABLED",
    "TIKA_PDF_AVG_CHAR_TOLERANCE",
    "TIKA_PDF_SPACING_TOLERANCE",
    "TIKA_RETRY_BACKOFF_MULTIPLIER",
    "TIKA_TIMEOUT_SECONDS",
    "TOPICS_MIN_CHARS",
    "TOPICS_MIN_DISTINCT_TOKENS",
    "TOP_KEYWORDS_PER_DOC",
    "VOTE_EXTRACTION_CONFIDENCE_THRESHOLD",
    "VOTE_EXTRACTION_CONTEXT_AFTER_CHARS",
    "VOTE_EXTRACTION_CONTEXT_BEFORE_CHARS",
    "VOTE_EXTRACTION_MAX_TOKENS",
    "VOTE_EXTRACTION_MIN_TEXT_CHARS",
}
CONFIG_TEST_ENV_KEYS = {
    "AGENDA_SUMMARY_PROFILE",
    "AGENDA_SUMMARY_SINGLE_ITEM_MODE",
    "CITY_SEGMENTATION_WORKERS",
    "FEATURE_TRENDS_DASHBOARD",
    "LOCAL_AI_BACKEND",
    "LOCAL_AI_HTTP_API",
    "LOCAL_AI_HTTP_MODEL",
    "LOCAL_AI_HTTP_PROFILE",
    "LOCAL_AI_HTTP_TIMEOUT_SECONDS",
    "LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS",
    "PIPELINE_RUNTIME_PROFILE",
    "SEMANTIC_ENABLED",
}


@contextmanager
def _config_with_env(monkeypatch: pytest.MonkeyPatch, values: dict[str, str]) -> Iterator[ModuleType]:
    import pipeline.config as config_module

    with monkeypatch.context() as patch_context:
        for name in CONFIG_TEST_ENV_KEYS:
            patch_context.delenv(name, raising=False)
        for name, value in values.items():
            patch_context.setenv(name, value)
        yield importlib.reload(config_module)
    importlib.reload(config_module)


def test_config_facade_exports_legacy_constants():
    import pipeline.config as config_module

    exported_names = {name for name in dir(config_module) if name.isupper() and not name.startswith("_")}

    assert exported_names == EXPECTED_CONFIG_EXPORTS
    assert set(config_module.__all__) == EXPECTED_CONFIG_EXPORTS


def test_config_helper_modules_do_not_import_facade():
    module_paths = [
        Path("pipeline/config_env.py"),
        Path("pipeline/config_startup.py"),
        Path("pipeline/config_inference.py"),
        Path("pipeline/config_semantic.py"),
        Path("pipeline/config_processing.py"),
        Path("pipeline/config_topic_similarity.py"),
        Path("pipeline/config_table.py"),
    ]
    offenders: list[str] = []

    for module_path in module_paths:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "pipeline.config":
                offenders.append(str(module_path))
            if isinstance(node, ast.Import):
                offenders.extend(str(module_path) for alias in node.names if alias.name == "pipeline.config")

    assert offenders == []


def test_config_reload_preserves_inference_env_normalization(monkeypatch):
    with _config_with_env(
        monkeypatch,
        {
            "LOCAL_AI_BACKEND": "bogus",
            "LOCAL_AI_HTTP_PROFILE": "weird",
            "LOCAL_AI_HTTP_TIMEOUT_SECONDS": "77",
            "LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS": "88",
            "LOCAL_AI_HTTP_MODEL": "",
            "CITY_SEGMENTATION_WORKERS": "6",
        },
    ) as config_module:
        assert config_module.LOCAL_AI_BACKEND == "http"
        assert config_module.LOCAL_AI_HTTP_API == "ollama"
        assert config_module.LOCAL_AI_HTTP_PROFILE == "conservative"
        assert config_module.LOCAL_AI_HTTP_TIMEOUT_SECONDS == 77
        assert config_module.LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS == 88
        assert config_module.LOCAL_AI_HTTP_MODEL == "gemma-3-270m-custom"
        assert config_module.CITY_SEGMENTATION_WORKERS == 6


def test_config_reload_rejects_invalid_http_api(monkeypatch):
    with pytest.raises(ValueError, match="LOCAL_AI_HTTP_API"):
        with _config_with_env(monkeypatch, {"LOCAL_AI_HTTP_API": "bad-api"}):
            pass


def test_config_reload_preserves_backend_dependent_worker_default(monkeypatch):
    with _config_with_env(monkeypatch, {"LOCAL_AI_BACKEND": "inprocess"}) as config_module:
        assert config_module.CITY_SEGMENTATION_WORKERS == 1

    with _config_with_env(monkeypatch, {"LOCAL_AI_BACKEND": "http"}) as config_module:
        assert config_module.CITY_SEGMENTATION_WORKERS == 2


def test_config_reload_preserves_choice_and_alias_values(monkeypatch):
    with _config_with_env(
        monkeypatch,
        {
            "PIPELINE_RUNTIME_PROFILE": "nonsense",
            "AGENDA_SUMMARY_PROFILE": "risk_first",
            "AGENDA_SUMMARY_SINGLE_ITEM_MODE": "bad",
            "SEMANTIC_ENABLED": "yes",
            "FEATURE_TRENDS_DASHBOARD": "1",
        },
    ) as config_module:
        assert config_module.PIPELINE_RUNTIME_PROFILE == ""
        assert config_module.AGENDA_SUMMARY_PROFILE == "risk_first"
        assert config_module.AGENDA_SUMMARY_SINGLE_ITEM_MODE == "deep_brief"
        assert config_module.SEMANTIC_ENABLED is True
        assert config_module.FEATURE_TRENDS_DASHBOARD is True
