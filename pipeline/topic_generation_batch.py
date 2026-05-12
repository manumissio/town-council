from __future__ import annotations

from typing import Any, cast

from pipeline.topic_generation_contracts import (
    MAX_CONTENT_LENGTH,
    PROGRESS_LOG_INTERVAL,
    TFIDF_MAX_DF,
    TFIDF_MIN_DF,
    TOP_KEYWORDS_PER_DOC,
    TopicWorkerServices,
)
from pipeline.topic_generation_keywords import _tfidf_vectorizer
from pipeline.topic_generation_text import _normal_topic_title, _sanitize_text_for_topics, _topic_stop_words


def _batch_records(session: Any, services: TopicWorkerServices) -> list[Any]:
    records = session.query(services.catalog_model).filter(
        services.catalog_model.content != None,  # noqa: E711
        services.catalog_model.content != "",
    )
    return cast(list[Any], services.apply_catalog_id_scope(records, services.catalog_model.id).all())


def _reindex_touched_catalogs(touched_catalog_ids: set[int], services: TopicWorkerServices) -> None:
    summary = services.reindex_catalogs(touched_catalog_ids)
    services.logger.info(
        "topic_reindex_summary considered=%s reindexed=%s failed=%s",
        summary["catalogs_considered"],
        summary["catalogs_reindexed"],
        summary["catalogs_failed"],
    )


def _initialize_topic_records(records: list[Any], services: TopicWorkerServices) -> set[int]:
    touched_catalog_ids: set[int] = set()
    for catalog in records:
        if catalog.content and not getattr(catalog, "content_hash", None):
            catalog.content_hash = services.compute_content_hash(catalog.content)
        catalog.topics = []
        touched_catalog_ids.add(catalog.id)
    return touched_catalog_ids


def _keywords_for_document_vector(document_vector: Any, feature_names: Any) -> list[str]:
    top_indices = document_vector.argsort()[-TOP_KEYWORDS_PER_DOC:][::-1]
    return [feature_names[index] for index in top_indices if document_vector[index] > 0]


def _assign_batch_topics(
    records: list[Any], tfidf_matrix: Any, feature_names: Any, services: TopicWorkerServices
) -> None:
    for record_index, catalog in enumerate(records):
        catalog.topics = []
        catalog.topics_source_hash = catalog.content_hash
        try:
            document_vector = tfidf_matrix[record_index].toarray()[0]
            keywords = _keywords_for_document_vector(document_vector, feature_names)
            catalog.topics = [_normal_topic_title(keyword) for keyword in keywords]
            catalog.topics_source_hash = catalog.content_hash
        except (IndexError, ValueError):
            catalog.topics_source_hash = catalog.content_hash
            continue

        if record_index % PROGRESS_LOG_INTERVAL == 0:
            services.logger.info("Processed %s/%s documents...", record_index, len(records))


def run_topic_tagger_family(session: Any, *, services: TopicWorkerServices) -> None:
    services.logger.info("Fetching documents for topic analysis...")
    records = _batch_records(session, services)
    touched_catalog_ids = _initialize_topic_records(records, services)

    if len(records) < 2:
        services.logger.warning("Not enough documents to perform TF-IDF analysis.")
        session.commit()
        return

    corpus = [_sanitize_text_for_topics(catalog.content[:MAX_CONTENT_LENGTH]) for catalog in records]
    services.logger.info("Analyzing %s documents...", len(corpus))

    vectorizer = _tfidf_vectorizer(max_df=TFIDF_MAX_DF, min_df=TFIDF_MIN_DF, stop_words=_topic_stop_words())
    try:
        tfidf_matrix = vectorizer.fit_transform(corpus)
        feature_names = vectorizer.get_feature_names_out()
    except (ValueError, MemoryError) as tfidf_error:
        services.logger.error("TF-IDF math failed: %s", tfidf_error)
        session.commit()
        _reindex_touched_catalogs(touched_catalog_ids, services)
        return

    _assign_batch_topics(records, tfidf_matrix, feature_names, services)
    session.commit()
    _reindex_touched_catalogs(touched_catalog_ids, services)
    services.logger.info("Topic tagging complete and saved to database.")
