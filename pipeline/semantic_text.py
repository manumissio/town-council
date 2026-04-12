from __future__ import annotations

from pipeline.config import SEMANTIC_CONTENT_MAX_CHARS
from pipeline.content_hash import compute_content_hash

MIN_SEMANTIC_SOURCE_HASH_CHARS = 20
MAX_FALLBACK_CONTENT_SCAN_MULTIPLIER = 3
MAX_FALLBACK_CONTENT_CHUNKS = 5


def _safe_text(value: str | None) -> str:
    return " ".join((value or "").split()).strip()


def catalog_semantic_text(value: str | None) -> str:
    """
    Canonicalize summary text so batch builds, task refreshes, and staleness checks
    all agree on the exact payload we expect to be embedded for meetings.
    """
    return _safe_text(value)[:SEMANTIC_CONTENT_MAX_CHARS]


def catalog_semantic_source_hash(value: str | None) -> str | None:
    semantic_payload = catalog_semantic_text(value)
    if len(semantic_payload) < MIN_SEMANTIC_SOURCE_HASH_CHARS:
        return None
    return compute_content_hash(semantic_payload)


def _build_chunks_from_content(content: str, max_chars: int) -> list[str]:
    """
    We chunk fallback text instead of embedding only the first N chars.
    That keeps later meeting sections searchable when summaries are missing.
    """
    semantic_text = _safe_text(content)
    if not semantic_text:
        return []
    hard_limited_text = semantic_text[: max_chars * MAX_FALLBACK_CONTENT_SCAN_MULTIPLIER]
    words = hard_limited_text.split()
    if not words:
        return []
    chunks: list[str] = []
    current_chunk_words: list[str] = []
    current_chunk_len = 0
    for word in words:
        word_len = len(word) + (1 if current_chunk_words else 0)
        if current_chunk_words and current_chunk_len + word_len > max_chars:
            chunks.append(" ".join(current_chunk_words))
            current_chunk_words = [word]
            current_chunk_len = len(word)
            continue
        current_chunk_words.append(word)
        current_chunk_len += word_len
    if current_chunk_words:
        chunks.append(" ".join(current_chunk_words))
    return chunks[:MAX_FALLBACK_CONTENT_CHUNKS]
