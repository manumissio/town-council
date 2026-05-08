import re
from dataclasses import dataclass

from pipeline.config import (
    SUMMARY_MAX_BOILERPLATE_RATIO,
    SUMMARY_MIN_CHARS,
    SUMMARY_MIN_DISTINCT_TOKENS,
    TOPICS_MIN_CHARS,
    TOPICS_MIN_DISTINCT_TOKENS,
)


_WORD_RE = re.compile(r"[a-z0-9']+")
_LINE_BOILERPLATE_FRAGMENTS = (
    "zoom",
    "webinar",
    "teleconference",
    "livestream",
    "live stream",
    "register in advance",
    "meeting link",
    "join by phone",
    "public comment",
    "public participation",
    "written communications",
    "members of the public",
    "email comments",
    "americans with disabilities act",
    "ada",
    "accommodation",
    "communication access",
)


@dataclass(frozen=True)
class SourceQualityResult:
    char_count: int
    token_count: int
    distinct_token_count: int
    alpha_ratio: float
    line_count: int
    unique_line_ratio: float
    boilerplate_line_ratio: float


def tokenize_summary_quality_text(text: str) -> list[str]:
    return _WORD_RE.findall((text or "").lower())


def _looks_like_boilerplate_line(line: str) -> bool:
    lowered = (line or "").strip().lower()
    if not lowered:
        return False
    if "http://" in lowered or "https://" in lowered or "www." in lowered:
        return True
    if "@" in lowered and "." in lowered:
        return True
    fragment_hits = sum(1 for fragment in _LINE_BOILERPLATE_FRAGMENTS if fragment in lowered)
    if fragment_hits == 0:
        return False

    # A single mention like "public comment" can appear in real agenda text.
    # Treat it as boilerplate only when the line is otherwise short/template-like.
    token_count = len(_WORD_RE.findall(lowered))
    return fragment_hits >= 2 or token_count <= 12


def analyze_source_text(text: str) -> SourceQualityResult:
    raw = text or ""
    stripped = raw.strip()
    tokens = tokenize_summary_quality_text(raw)
    distinct_tokens = set(tokens)
    alpha_chars = sum(ch.isalpha() for ch in raw)
    total_chars = max(len(raw), 1)

    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if not lines and stripped:
        lines = [stripped]
    unique_line_ratio = (len(set(lines)) / len(lines)) if lines else 0.0
    boilerplate_lines = sum(1 for ln in lines if _looks_like_boilerplate_line(ln))
    boilerplate_line_ratio = (boilerplate_lines / len(lines)) if lines else 0.0

    return SourceQualityResult(
        char_count=len(stripped),
        token_count=len(tokens),
        distinct_token_count=len(distinct_tokens),
        alpha_ratio=alpha_chars / total_chars,
        line_count=len(lines),
        unique_line_ratio=unique_line_ratio,
        boilerplate_line_ratio=boilerplate_line_ratio,
    )


def build_low_signal_message(quality: SourceQualityResult) -> str:
    return (
        "Not enough extracted text to generate a reliable result. "
        f"(chars={quality.char_count}, distinct_tokens={quality.distinct_token_count}, "
        f"boilerplate_ratio={quality.boilerplate_line_ratio:.2f})"
    )


def is_source_summarizable(quality: SourceQualityResult) -> bool:
    if quality.char_count < SUMMARY_MIN_CHARS:
        return False
    if quality.distinct_token_count < SUMMARY_MIN_DISTINCT_TOKENS:
        return False
    if quality.alpha_ratio < 0.35:
        return False
    if quality.boilerplate_line_ratio > SUMMARY_MAX_BOILERPLATE_RATIO:
        return False
    return True


def is_source_topicable(quality: SourceQualityResult) -> bool:
    if quality.char_count < TOPICS_MIN_CHARS:
        return False
    if quality.distinct_token_count < TOPICS_MIN_DISTINCT_TOKENS:
        return False
    if quality.alpha_ratio < 0.35:
        return False
    if quality.boilerplate_line_ratio > SUMMARY_MAX_BOILERPLATE_RATIO:
        return False
    return True
