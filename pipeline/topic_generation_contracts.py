from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from logging import Logger
from typing import Any

from pipeline import config as _config


TOPIC_COMPLETE_STATUS = "complete"
TOPIC_CACHED_STATUS = "cached"
TOPIC_STALE_STATUS = "stale"
TOPIC_BLOCKED_LOW_SIGNAL_STATUS = "blocked_low_signal"
NO_CONTENT_TO_TAG_ERROR = "No content to tag"
DOCUMENT_NOT_LINKED_ERROR = "Document not linked to catalog"
NO_TOPIC_CORPUS_ERROR = "No corpus available for topic tagging"
NOT_ENOUGH_USABLE_TEXT_REASON = "Not enough usable text to generate topics."
TOPIC_TOKEN_PATTERN = r"(?u)\b[a-zA-Z][a-zA-Z']{2,}\b"
PLACE_TOKEN_PATTERN = r"[a-zA-Z]{3,}"
FALLBACK_TOPIC_TOKEN_PATTERN = r"[a-zA-Z][a-zA-Z'-]{2,}"
TOPIC_SOURCE_TITLE_LIMIT = 8
SMALL_CORPUS_DOC_THRESHOLD = 3
MAX_CONTENT_LENGTH = _config.MAX_CONTENT_LENGTH
PROGRESS_LOG_INTERVAL = _config.PROGRESS_LOG_INTERVAL
TFIDF_MAX_DF = _config.TFIDF_MAX_DF
TFIDF_MAX_FEATURES = _config.TFIDF_MAX_FEATURES
TFIDF_MIN_DF = _config.TFIDF_MIN_DF
TFIDF_NGRAM_RANGE = _config.TFIDF_NGRAM_RANGE
TOP_KEYWORDS_PER_DOC = _config.TOP_KEYWORDS_PER_DOC


@dataclass(frozen=True)
class TopicGenerationTaskServices:
    # SQLAlchemy models/query collaborators are dynamic at this boundary.
    catalog_model: Any
    document_model: Any
    place_model: Any
    compute_content_hash: Callable[[str], str]
    analyze_source_text: Callable[[str], object]
    is_source_topicable: Callable[[object], bool]
    build_low_signal_message: Callable[[object], str]
    postprocess_extracted_text: Callable[[str], str]
    extract_agenda_titles_from_text: Callable[..., list[str]]
    reindex_catalog: Callable[[int], object]


@dataclass(frozen=True)
class TopicWorkerServices:
    # SQLAlchemy models/query collaborators are dynamic at this boundary.
    catalog_model: Any
    compute_content_hash: Callable[[str], str]
    apply_catalog_id_scope: Callable[[Any, Any], Any]
    reindex_catalogs: Callable[[set[int]], dict[str, int]]
    logger: Logger
