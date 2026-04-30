import re
import logging
from collections.abc import Callable
from dataclasses import dataclass
from logging import Logger
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from pipeline.config import (
    MAX_CONTENT_LENGTH,
    PROGRESS_LOG_INTERVAL,
    TFIDF_MAX_DF,
    TFIDF_MAX_FEATURES,
    TFIDF_MIN_DF,
    TFIDF_NGRAM_RANGE,
    TOP_KEYWORDS_PER_DOC,
)
from pipeline.task_side_effects import REINDEX_FAILURE_EXCEPTIONS
from pipeline.text_cleaning import postprocess_extracted_text


logger = logging.getLogger(__name__)

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

# These words appear constantly in city documents but are not useful topics.
CITY_STOP_WORDS = [
    "meeting",
    "council",
    "city",
    "minutes",
    "agenda",
    "present",
    "absent",
    "motion",
    "seconded",
    "voted",
    "item",
    "resolution",
    "ordinance",
    "approved",
    "unanimous",
    "quorum",
    "adjourned",
    "p.m.",
    "a.m.",
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "hereby",
    "thereof",
    "therein",
    "clerk",
    "mayor",
    "councilmember",
    "commission",
    "committee",
    "commissioner",
    "members",
    "teleconference",
    "staff",
    "report",
    "public",
    "comment",
    "called",
    "order",
    "action",
    "discussion",
    "held",
    "held",
    "carried",
    "aye",
    "noes",
    "abstain",
    "subject",
    "recommended",
    "recommendation",
    "http",
    "https",
    "www",
]


@dataclass(frozen=True)
class TopicGenerationTaskServices:
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
    catalog_model: Any
    compute_content_hash: Callable[[str], str]
    apply_catalog_id_scope: Callable[[Any, Any], Any]
    reindex_catalogs: Callable[[set[int]], dict[str, int]]
    logger: Logger


def _sanitize_text_for_topics(text: str) -> str:
    """
    Remove obvious extraction and URL noise before topic discovery.
    """
    if not text:
        return ""

    value = postprocess_extracted_text(text)
    value = re.sub(r"https?://\S+", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"www\.\S+", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\bhttps?\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\bwww\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\[PAGE\s+\d+\]", " ", value, flags=re.IGNORECASE)
    return value


def _english_stop_words() -> frozenset[str]:
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

    return ENGLISH_STOP_WORDS


def _tfidf_vectorizer(*, max_df: float, min_df: int, stop_words: list[str]):
    from sklearn.feature_extraction.text import TfidfVectorizer

    return TfidfVectorizer(
        max_df=max_df,
        min_df=min_df,
        ngram_range=TFIDF_NGRAM_RANGE,
        max_features=TFIDF_MAX_FEATURES,
        stop_words=stop_words,
        token_pattern=TOPIC_TOKEN_PATTERN,
    )


def _top_indices(row: Any, limit: int) -> Any:
    import numpy as np

    return np.argsort(row)[::-1][:limit]


def _place_tokens(db: Any, place_id: int | None, place_model: Any) -> set[str]:
    if place_id is None:
        return set()
    try:
        place = db.get(place_model, place_id)
    except (SQLAlchemyError, RuntimeError, ValueError, AttributeError):
        return set()

    display = (getattr(place, "display_name", "") or getattr(place, "name", "") or "").lower()
    return set(re.findall(PLACE_TOKEN_PATTERN, display))


def _topic_stop_words(place_tokens: set[str] | None = None) -> list[str]:
    return sorted(set(CITY_STOP_WORDS).union(_english_stop_words()).union(place_tokens or set()))


def _normal_topic_title(topic: str) -> str:
    return topic.title()


def _small_corpus_keywords(
    *,
    text: str,
    stop_words: list[str],
    services: TopicGenerationTaskServices,
) -> list[str]:
    cleaned = services.postprocess_extracted_text(text)
    titles = services.extract_agenda_titles_from_text(cleaned, max_titles=TOPIC_SOURCE_TITLE_LIMIT)
    if titles:
        normalized_titles = []
        for title in titles:
            value = re.sub(r"\([^)]*\)", " ", title)
            value = re.sub(r"^\s*subject\s*:\s*", "", value, flags=re.IGNORECASE)
            value = re.sub(r"^\s*recommended\s+action\s*:\s*", "", value, flags=re.IGNORECASE)
            normalized_titles.append(value.strip())
        candidates = " ".join(normalized_titles)
    else:
        candidates = cleaned

    tokens = [token.lower() for token in re.findall(FALLBACK_TOPIC_TOKEN_PATTERN, candidates)]
    filtered = [token for token in tokens if token not in set(stop_words)]
    if not filtered:
        return []

    phrase_counts: dict[str, int] = {}
    for phrase_length in (3, 2):
        for token_index in range(0, max(0, len(filtered) - phrase_length + 1)):
            phrase = " ".join(filtered[token_index : token_index + phrase_length])
            phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1

    unigram_counts: dict[str, int] = {}
    for token in filtered:
        unigram_counts[token] = unigram_counts.get(token, 0) + 1

    ranked_phrases = sorted(phrase_counts.items(), key=lambda topic_count: (-topic_count[1], topic_count[0]))
    ranked_unigrams = sorted(unigram_counts.items(), key=lambda topic_count: (-topic_count[1], topic_count[0]))

    keywords: list[str] = []
    seen: set[str] = set()
    for phrase, _count in ranked_phrases:
        topic_key = phrase.lower()
        if topic_key in seen:
            continue
        seen.add(topic_key)
        keywords.append(_normal_topic_title(phrase))
        if len(keywords) >= TOP_KEYWORDS_PER_DOC:
            break

    if len(keywords) < TOP_KEYWORDS_PER_DOC:
        for word, _count in ranked_unigrams:
            topic_key = word.lower()
            if topic_key in seen:
                continue
            seen.add(topic_key)
            keywords.append(_normal_topic_title(word))
            if len(keywords) >= TOP_KEYWORDS_PER_DOC:
                break

    return keywords


def _tfidf_keywords_for_target(
    *,
    catalog_id: int,
    catalog_content: str,
    corpus_rows: list[tuple[int, str]],
    stop_words: list[str],
) -> list[str]:
    catalog_ids = [row[0] for row in corpus_rows]
    corpus = [_sanitize_text_for_topics((row[1] or "")[:MAX_CONTENT_LENGTH]) for row in corpus_rows]

    max_df = 1.0 if len(corpus) < 2 else TFIDF_MAX_DF
    min_df = 1 if len(corpus) < SMALL_CORPUS_DOC_THRESHOLD else TFIDF_MIN_DF
    vectorizer = _tfidf_vectorizer(max_df=max_df, min_df=min_df, stop_words=stop_words)
    tfidf = vectorizer.fit_transform(corpus)
    feature_names = vectorizer.get_feature_names_out()

    try:
        target_index = catalog_ids.index(catalog_id)
    except ValueError:
        target_text = _sanitize_text_for_topics((catalog_content or "")[:MAX_CONTENT_LENGTH])
        corpus.insert(0, target_text)
        catalog_ids.insert(0, catalog_id)
        tfidf = vectorizer.fit_transform(corpus)
        feature_names = vectorizer.get_feature_names_out()
        target_index = 0

    row = tfidf[target_index].toarray().ravel()
    if row.size == 0:
        return []
    return [_normal_topic_title(feature_names[index]) for index in _top_indices(row, TOP_KEYWORDS_PER_DOC) if row[index] > 0]


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

    content_hash = catalog.content_hash or services.compute_content_hash(catalog.content)
    quality = services.analyze_source_text(catalog.content)
    if not services.is_source_topicable(quality):
        return {
            "status": TOPIC_BLOCKED_LOW_SIGNAL_STATUS,
            "reason": services.build_low_signal_message(quality),
            "topics": [],
        }

    is_fresh = bool(
        catalog.topics is not None
        and content_hash
        and catalog.topics_source_hash
        and catalog.topics_source_hash == content_hash
    )
    if (not force) and is_fresh:
        return {"status": TOPIC_CACHED_STATUS, "topics": catalog.topics}
    if (not force) and catalog.topics is not None and not is_fresh:
        return {"status": TOPIC_STALE_STATUS, "topics": catalog.topics}

    document = db.query(services.document_model).filter_by(catalog_id=catalog_id).first()
    if not document:
        return {"error": DOCUMENT_NOT_LINKED_ERROR}

    corpus_rows = (
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
    if not corpus_rows:
        return {"error": NO_TOPIC_CORPUS_ERROR}

    sanitized_corpus = [_sanitize_text_for_topics((row[1] or "")[:MAX_CONTENT_LENGTH]) for row in corpus_rows]
    if not any(text.strip() for text in sanitized_corpus):
        return {
            "status": TOPIC_BLOCKED_LOW_SIGNAL_STATUS,
            "reason": NOT_ENOUGH_USABLE_TEXT_REASON,
            "topics": [],
        }

    stop_words = _topic_stop_words(_place_tokens(db, getattr(document, "place_id", None), services.place_model))
    if len(sanitized_corpus) < SMALL_CORPUS_DOC_THRESHOLD:
        keywords = _small_corpus_keywords(text=catalog.content, stop_words=stop_words, services=services)
        if not keywords:
            return {
                "status": TOPIC_BLOCKED_LOW_SIGNAL_STATUS,
                "reason": NOT_ENOUGH_USABLE_TEXT_REASON,
                "topics": [],
            }
    else:
        keywords = _tfidf_keywords_for_target(
            catalog_id=catalog_id,
            catalog_content=catalog.content,
            corpus_rows=corpus_rows,
            stop_words=stop_words,
        )

    _persist_topics(catalog, topics=keywords, content_hash=content_hash)
    db.commit()
    _reindex_single_catalog(catalog_id, services)
    return {"status": TOPIC_COMPLETE_STATUS, "topics": keywords}


def _batch_records(session: Any, services: TopicWorkerServices) -> list[Any]:
    records = session.query(services.catalog_model).filter(
        services.catalog_model.content != None,  # noqa: E711
        services.catalog_model.content != "",
    )
    return services.apply_catalog_id_scope(records, services.catalog_model.id).all()


def _reindex_touched_catalogs(touched_catalog_ids: set[int], services: TopicWorkerServices) -> None:
    summary = services.reindex_catalogs(touched_catalog_ids)
    services.logger.info(
        "topic_reindex_summary considered=%s reindexed=%s failed=%s",
        summary["catalogs_considered"],
        summary["catalogs_reindexed"],
        summary["catalogs_failed"],
    )


def run_topic_tagger_family(session: Any, *, services: TopicWorkerServices) -> None:
    services.logger.info("Fetching documents for topic analysis...")
    records = _batch_records(session, services)

    touched_catalog_ids: set[int] = set()
    for catalog in records:
        if catalog.content and not getattr(catalog, "content_hash", None):
            catalog.content_hash = services.compute_content_hash(catalog.content)
        catalog.topics = []
        touched_catalog_ids.add(catalog.id)

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

    for record_index, catalog in enumerate(records):
        catalog.topics = []
        catalog.topics_source_hash = catalog.content_hash
        try:
            document_vector = tfidf_matrix[record_index].toarray()[0]
            top_indices = document_vector.argsort()[-TOP_KEYWORDS_PER_DOC:][::-1]
            keywords = [feature_names[index] for index in top_indices if document_vector[index] > 0]
            catalog.topics = [_normal_topic_title(keyword) for keyword in keywords]
            catalog.topics_source_hash = catalog.content_hash
        except (IndexError, ValueError):
            catalog.topics_source_hash = catalog.content_hash
            continue

        if record_index % PROGRESS_LOG_INTERVAL == 0:
            services.logger.info("Processed %s/%s documents...", record_index, len(records))

    session.commit()
    _reindex_touched_catalogs(touched_catalog_ids, services)
    services.logger.info("Topic tagging complete and saved to database.")
