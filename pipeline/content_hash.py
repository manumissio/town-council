import hashlib
import re
from typing import Optional


_WS_RE = re.compile(r"\s+")


def normalize_text_for_hash(text: str) -> str:
    """
    Normalize extracted text before hashing.

    Why:
    Extraction can change whitespace without changing meaning (different OCR runs,
    different PDF text layer quirks). Normalization keeps our "stale" detection
    focused on meaningful changes, not formatting noise.
    """
    if text is None:
        return ""
    return _WS_RE.sub(" ", text.strip())


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_content_hash(text: Optional[str]) -> Optional[str]:
    """
    Return a SHA-256 hash for extracted content, or None when there is no content.
    """
    if not text:
        return None
    normalized = normalize_text_for_hash(text)
    if not normalized:
        return None
    return sha256_text(normalized)

