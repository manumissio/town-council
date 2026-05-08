from __future__ import annotations

import re
from typing import Any, cast

from pipeline.topic_generation_contracts import (
    FALLBACK_TOPIC_TOKEN_PATTERN,
    MAX_CONTENT_LENGTH,
    SMALL_CORPUS_DOC_THRESHOLD,
    TFIDF_MAX_DF,
    TFIDF_MAX_FEATURES,
    TFIDF_MIN_DF,
    TFIDF_NGRAM_RANGE,
    TOP_KEYWORDS_PER_DOC,
    TOPIC_SOURCE_TITLE_LIMIT,
    TOPIC_TOKEN_PATTERN,
    TopicGenerationTaskServices,
)
from pipeline.topic_generation_text import _normal_topic_title, _sanitize_text_for_topics


def _tfidf_vectorizer(*, max_df: float, min_df: int, stop_words: list[str]) -> Any:
    from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore[import-untyped]

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


def _normalized_small_corpus_candidates(text: str, services: TopicGenerationTaskServices) -> str:
    cleaned = services.postprocess_extracted_text(text)
    titles = services.extract_agenda_titles_from_text(cleaned, max_titles=TOPIC_SOURCE_TITLE_LIMIT)
    if not titles:
        return cleaned

    normalized_titles: list[str] = []
    for title in titles:
        value = re.sub(r"\([^)]*\)", " ", title)
        value = re.sub(r"^\s*subject\s*:\s*", "", value, flags=re.IGNORECASE)
        value = re.sub(r"^\s*recommended\s+action\s*:\s*", "", value, flags=re.IGNORECASE)
        normalized_titles.append(value.strip())
    return " ".join(normalized_titles)


def _filtered_fallback_tokens(candidates: str, stop_words: list[str]) -> list[str]:
    stop_word_set = set(stop_words)
    tokens = [token.lower() for token in re.findall(FALLBACK_TOPIC_TOKEN_PATTERN, candidates)]
    return [token for token in tokens if token not in stop_word_set]


def _count_phrases(tokens: list[str]) -> dict[str, int]:
    phrase_counts: dict[str, int] = {}
    for phrase_length in (3, 2):
        for token_index in range(0, max(0, len(tokens) - phrase_length + 1)):
            phrase = " ".join(tokens[token_index : token_index + phrase_length])
            phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1
    return phrase_counts


def _count_unigrams(tokens: list[str]) -> dict[str, int]:
    unigram_counts: dict[str, int] = {}
    for token in tokens:
        unigram_counts[token] = unigram_counts.get(token, 0) + 1
    return unigram_counts


def _append_ranked_topics(
    keywords: list[str],
    seen: set[str],
    ranked_topics: list[tuple[str, int]],
) -> None:
    for topic, _count in ranked_topics:
        topic_key = topic.lower()
        if topic_key in seen:
            continue
        seen.add(topic_key)
        keywords.append(_normal_topic_title(topic))
        if len(keywords) >= TOP_KEYWORDS_PER_DOC:
            return


def _small_corpus_keywords(
    *,
    text: str,
    stop_words: list[str],
    services: TopicGenerationTaskServices,
) -> list[str]:
    candidates = _normalized_small_corpus_candidates(text, services)
    filtered = _filtered_fallback_tokens(candidates, stop_words)
    if not filtered:
        return []

    ranked_phrases = sorted(_count_phrases(filtered).items(), key=lambda topic_count: (-topic_count[1], topic_count[0]))
    ranked_unigrams = sorted(
        _count_unigrams(filtered).items(),
        key=lambda topic_count: (-topic_count[1], topic_count[0]),
    )

    keywords: list[str] = []
    seen: set[str] = set()
    _append_ranked_topics(keywords, seen, ranked_phrases)
    if len(keywords) < TOP_KEYWORDS_PER_DOC:
        _append_ranked_topics(keywords, seen, ranked_unigrams)
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
    return [
        _normal_topic_title(cast(str, feature_names[index]))
        for index in _top_indices(row, TOP_KEYWORDS_PER_DOC)
        if row[index] > 0
    ]
