from __future__ import annotations

import re
from collections.abc import Iterable
from typing import cast

from pipeline.lexicon import normalize_title_key as lexicon_normalize_title_key


def dedupe_lines_preserve_order(lines: Iterable[str]) -> list[str]:
    """Return unique lines while keeping the first occurrence order."""
    deduped_lines: list[str] = []
    seen_keys: set[str] = set()
    for line in lines:
        key = line.strip().lower()
        if not key:
            continue
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped_lines.append(line)
    return deduped_lines


def normalize_spaces(value: object) -> str:
    if value is None:
        raw = ""
    elif isinstance(value, str):
        raw = value
    else:
        # Some tests use MagicMock placeholders for optional fields.
        raw = str(value)
    return re.sub(r"\s+", " ", raw).strip()


def normalized_title_key(value: object) -> str:
    # Single lexicon source keeps normalization consistent across pipeline/API.
    return cast(str, lexicon_normalize_title_key(normalize_spaces(value)))


def first_alpha_char(value: str) -> str | None:
    """
    Return the first alphabetical character in a string, or None when absent.
    """
    match = re.search(r"[a-zA-Z]", value or "")
    return match.group(0) if match else None
