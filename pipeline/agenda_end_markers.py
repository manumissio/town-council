from __future__ import annotations

import re

from pipeline.agenda_text_normalization import normalize_spaces


_LEGAL_TAIL_MARKERS = (
    "attest",
    "in witness whereof",
    "official seal",
    "notice concerning your legal rights",
    "cause personal notice",
    "city clerk",
    "date:",
    "public notice",
)
_SUBSTANTIVE_AFTER_MARKER_SIGNALS = (
    "subject:",
    "recommendation:",
    "action calendar",
    "financial implications",
    "conduct a public hearing",
)


def looks_like_end_marker_line(line: str) -> bool:
    lowered = normalize_spaces(line).lower()
    if not lowered:
        return False
    marker_patterns = (
        r"^adjournment$",
        r"^attest\b",
        r"^notice concerning your legal rights\b",
        r"\bin witness whereof\b",
        r"\bofficial seal\b",
        r"public notice.*official agenda",
    )
    return any(re.search(pattern, lowered) for pattern in marker_patterns)


def should_stop_after_marker(current_line: str, lookahead_window: str) -> bool:
    """
    Composite end-of-agenda detector.
    """
    line = normalize_spaces(current_line).lower()
    window = (lookahead_window or "").lower()
    if not line:
        return False

    legal_hits = sum(1 for marker in _LEGAL_TAIL_MARKERS if marker in window)
    has_substantive_after = any(signal in window for signal in _SUBSTANTIVE_AFTER_MARKER_SIGNALS)

    if "adjournment" in line:
        return legal_hits >= 2 and not has_substantive_after
    return legal_hits >= 2
