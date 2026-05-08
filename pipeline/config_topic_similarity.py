from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TopicSimilarityConfig:
    tfidf_max_df: float
    tfidf_min_df: int
    tfidf_ngram_range: tuple[int, int]
    tfidf_max_features: int
    top_keywords_per_doc: int
    progress_log_interval: int
    similarity_content_length: int
    embedding_batch_size: int
    similarity_threshold: float
    faiss_top_neighbors: int
    max_related_docs: int


def load_topic_similarity_config() -> TopicSimilarityConfig:
    return TopicSimilarityConfig(
        tfidf_max_df=0.8,
        tfidf_min_df=1,
        tfidf_ngram_range=(1, 2),
        tfidf_max_features=5000,
        top_keywords_per_doc=5,
        progress_log_interval=50,
        similarity_content_length=5000,
        embedding_batch_size=32,
        similarity_threshold=0.35,
        faiss_top_neighbors=4,
        max_related_docs=3,
    )
