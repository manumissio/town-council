from __future__ import annotations

import logging
from typing import Any, cast

from pipeline.task_side_effects import REINDEX_FAILURE_EXCEPTIONS
from pipeline.topic_generation_contracts import (
    DOCUMENT_NOT_LINKED_ERROR,
    MAX_CONTENT_LENGTH,
    NO_CONTENT_TO_TAG_ERROR,
    NO_TOPIC_CORPUS_ERROR,
    NOT_ENOUGH_USABLE_TEXT_REASON,
    SMALL_CORPUS_DOC_THRESHOLD,
    TOPIC_BLOCKED_LOW_SIGNAL_STATUS,
    TOPIC_CACHED_STATUS,
    TOPIC_COMPLETE_STATUS,
    TOPIC_STALE_STATUS,
    TopicGenerationTaskServices,
)
from pipeline.topic_generation_keywords import _small_corpus_keywords, _tfidf_keywords_for_target
from pipeline.topic_generation_text import _place_tokens, _sanitize_text_for_topics, _topic_stop_words


logger = logging.getLogger(__name__)


def _persist_topics(catalog: Any, *, topics: list[str], content_hash: str) -> None:
    catalog.topics = topics
    catalog.content_hash = content_hash
    catalog.topics_source_hash = content_hash


def _reindex_single_catalog(catalog_id: int, services: TopicGenerationTaskServices) -> None:
    try:
        services.reindex_catalog(catalog_id)
    except REINDEX_FAILURE_EXCEPTIONS as reindex_error:
        # Topic extraction is already persisted, so search reindex remains best-effort.
        logger.warning(
            "topic_extraction.reindex_failed catalog_id=%s error=%s",
            catalog_id,
            reindex_error,
        )


def _catalog_content_hash(catalog: Any, services: TopicGenerationTaskServices) -> str:
    return catalog.content_hash or services.compute_content_hash(catalog.content)


def _topics_are_fresh(catalog: Any, content_hash: str) -> bool:
    return bool(
        catalog.topics is not None
        and content_hash
        and catalog.topics_source_hash
        and catalog.topics_source_hash == content_hash
    )


def _corpus_rows_for_document(
    db: Any,
    document: Any,
    *,
    max_corpus_docs: int,
    services: TopicGenerationTaskServices,
) -> list[tuple[int, str]]:
    rows = (
        db.query(services.catalog_model.id, services.catalog_model.content)
        .join(services.document_model, services.document_model.catalog_id == services.catalog_model.id)
        .filter(
            services.document_model.place_id == document.place_id,
            services.catalog_model.content.isnot(None),
            services.catalog_model.content != "",
        )
        .order_by(services.catalog_model.id.desc())
        .limit(max_corpus_docs)
        .all()
    )
    return cast(list[tuple[int, str]], rows)


def _topic_keywords(
    *,
    catalog_id: int,
    catalog_content: str,
    corpus_rows: list[tuple[int, str]],
    document: Any,
    db: Any,
    services: TopicGenerationTaskServices,
) -> list[str]:
    stop_words = _topic_stop_words(_place_tokens(db, getattr(document, "place_id", None), services.place_model))
    if len(corpus_rows) < SMALL_CORPUS_DOC_THRESHOLD:
        return _small_corpus_keywords(text=catalog_content, stop_words=stop_words, services=services)
    return _tfidf_keywords_for_target(
        catalog_id=catalog_id,
        catalog_content=catalog_content,
        corpus_rows=corpus_rows,
        stop_words=stop_words,
    )


def _should_block_empty_topics(corpus_rows: list[tuple[int, str]]) -> bool:
    return len(corpus_rows) < SMALL_CORPUS_DOC_THRESHOLD


def run_generate_topics_task_family(
    db: Any,
    catalog_id: int,
    *,
    force: bool,
    max_corpus_docs: int,
    services: TopicGenerationTaskServices,
) -> dict[str, Any]:
    catalog = db.get(services.catalog_model, catalog_id)
    if not catalog or not catalog.content:
        return {"error": NO_CONTENT_TO_TAG_ERROR}

    content_hash = _catalog_content_hash(catalog, services)
    quality = services.analyze_source_text(catalog.content)
    if not services.is_source_topicable(quality):
        return {
            "status": TOPIC_BLOCKED_LOW_SIGNAL_STATUS,
            "reason": services.build_low_signal_message(quality),
            "topics": [],
        }

    if (not force) and _topics_are_fresh(catalog, content_hash):
        return {"status": TOPIC_CACHED_STATUS, "topics": catalog.topics}
    if (not force) and catalog.topics is not None:
        return {"status": TOPIC_STALE_STATUS, "topics": catalog.topics}

    document = db.query(services.document_model).filter_by(catalog_id=catalog_id).first()
    if not document:
        return {"error": DOCUMENT_NOT_LINKED_ERROR}

    corpus_rows = _corpus_rows_for_document(db, document, max_corpus_docs=max_corpus_docs, services=services)
    if not corpus_rows:
        return {"error": NO_TOPIC_CORPUS_ERROR}

    sanitized_corpus = [_sanitize_text_for_topics((row[1] or "")[:MAX_CONTENT_LENGTH]) for row in corpus_rows]
    if not any(text.strip() for text in sanitized_corpus):
        return {
            "status": TOPIC_BLOCKED_LOW_SIGNAL_STATUS,
            "reason": NOT_ENOUGH_USABLE_TEXT_REASON,
            "topics": [],
        }

    keywords = _topic_keywords(
        catalog_id=catalog_id,
        catalog_content=catalog.content,
        corpus_rows=corpus_rows,
        document=document,
        db=db,
        services=services,
    )
    if not keywords and _should_block_empty_topics(corpus_rows):
        return {
            "status": TOPIC_BLOCKED_LOW_SIGNAL_STATUS,
            "reason": NOT_ENOUGH_USABLE_TEXT_REASON,
            "topics": [],
        }

    _persist_topics(catalog, topics=keywords, content_hash=content_hash)
    db.commit()
    _reindex_single_catalog(catalog_id, services)
    return {"status": TOPIC_COMPLETE_STATUS, "topics": keywords}
