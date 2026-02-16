import re
from dataclasses import dataclass
from typing import List, Tuple

from pipeline.config import (
    SUMMARY_GROUNDING_MIN_COVERAGE,
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
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is",
    "it", "of", "on", "or", "that", "the", "to", "was", "were", "with", "this",
    "these", "those", "will", "would", "can", "could", "may", "might",
}
_SECTION_HEADERS = {
    "why this matters:",
    "top actions:",
    "potential impacts:",
    "unknowns:",
    "major themes:",
    "decision/action requested:",
}


@dataclass(frozen=True)
class SourceQualityResult:
    char_count: int
    token_count: int
    distinct_token_count: int
    alpha_ratio: float
    line_count: int
    unique_line_ratio: float
    boilerplate_line_ratio: float


@dataclass(frozen=True)
class GroundingResult:
    is_grounded: bool
    coverage: float
    unsupported_claims: List[str]


def _tokenize(text: str) -> List[str]:
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
    tokens = _tokenize(raw)
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


def extract_claim_lines(summary: str) -> List[str]:
    if not summary:
        return []
    lines = []
    for raw in summary.splitlines():
        # Normalize whitespace so simple substring checks work even with NBSPs, etc.
        line = " ".join((raw or "").strip().split())
        if not line:
            continue
        # Strip common bullet markers before any content-based filtering.
        line = re.sub(r"^\s*[\*\-\u2022]+\s*", "", line).strip()
        # Models sometimes wrap preambles in quotes or punctuation; drop leading non-alphanumerics
        # so "Here’s ..." is detected reliably.
        line = re.sub(r"^[^A-Za-z0-9]+", "", line).strip()
        if not line:
            continue
        # BLUF is a synthesis line and often paraphrases the source.
        # Our grounding check is intentionally conservative and lexical, so we
        # validate only the bullet "claims" instead of blocking on an abstract BLUF.
        lowered = line.lower()
        if lowered.startswith("bluf:"):
            continue
        if lowered in _SECTION_HEADERS:
            continue
        if lowered.endswith(":") and len(_WORD_RE.findall(lowered)) <= 6:
            # Section labels are structural hints, not factual claims.
            continue
        # Drop generic preambles that models often add before actual claims.
        if lowered.startswith("here") and "summary" in lowered:
            continue
        if "executive summary" in lowered or ("summary" in lowered and lowered.endswith(":")):
            continue
        if lowered.startswith("here's a summary") or lowered.startswith("here is a summary"):
            continue
        if lowered.startswith("summary of the meeting"):
            continue
        if len(line) < 5:
            continue
        lines.append(line)
    return lines


def prune_unsupported_summary_lines(summary: str, source_text: str) -> Tuple[str, int]:
    """
    Remove unsupported claim lines while preserving BLUF/section structure.

    Returns:
      (pruned_summary, removed_count)
    """
    if not (summary or "").strip():
        return "", 0

    source_tokens = set(_tokenize(source_text or ""))
    if not source_tokens:
        return summary.strip(), 0
    source_prefixes = {tok[:5] for tok in source_tokens if len(tok) >= 5}

    removed = 0
    kept_lines: List[str] = []
    for raw in (summary or "").splitlines():
        line = (raw or "").rstrip()
        stripped = line.strip()
        lowered = stripped.lower()
        if not stripped:
            kept_lines.append(line)
            continue
        if lowered.startswith("bluf:") or lowered in _SECTION_HEADERS:
            kept_lines.append(line)
            continue

        candidate = re.sub(r"^\s*[\*\-\u2022]+\s*", "", stripped).strip()
        if not candidate:
            kept_lines.append(line)
            continue
        coverage = _claim_coverage(candidate, source_tokens, source_prefixes)
        if coverage < SUMMARY_GROUNDING_MIN_COVERAGE:
            removed += 1
            continue
        kept_lines.append(line)

    return "\n".join(kept_lines).strip(), removed


def _claim_coverage(claim: str, source_tokens: set, source_prefixes: set) -> float:
    claim_tokens = [t for t in _tokenize(claim) if len(t) >= 3 and t not in _STOPWORDS]
    if not claim_tokens:
        return 1.0
    # Allow a small amount of morphological drift (employee vs employment, appointments vs appoint)
    # using a fixed-length prefix match. This stays deterministic and bounded.
    matched = 0
    for t in claim_tokens:
        if t in source_tokens:
            matched += 1
            continue
        if len(t) >= 5 and t[:5] in source_prefixes:
            matched += 1
            continue
    return matched / len(claim_tokens)


def is_summary_grounded(summary: str, source_text: str) -> GroundingResult:
    claims = extract_claim_lines(summary)
    if not claims:
        # Fallback: if the summary has only a BLUF line, use it as a single claim.
        # This prevents blanket blocks when the model returns a short, high-level takeaway.
        bluf = None
        for raw in (summary or "").splitlines():
            line = " ".join((raw or "").strip().split())
            if line.lower().startswith("bluf:"):
                bluf = line.split(":", 1)[1].strip()
                break
        if bluf and len(bluf) >= 5:
            claims = [bluf]
        else:
            return GroundingResult(is_grounded=False, coverage=0.0, unsupported_claims=["No summary claims found"])

    source_tokens = set(_tokenize(source_text or ""))
    if not source_tokens:
        return GroundingResult(is_grounded=False, coverage=0.0, unsupported_claims=claims[:3])
    source_prefixes = {tok[:5] for tok in source_tokens if len(tok) >= 5}

    claim_coverages = []
    unsupported = []
    for claim in claims:
        coverage = _claim_coverage(claim, source_tokens, source_prefixes)
        claim_coverages.append(coverage)
        if coverage < SUMMARY_GROUNDING_MIN_COVERAGE:
            unsupported.append(claim)

    avg_coverage = sum(claim_coverages) / len(claim_coverages)
    return GroundingResult(
        is_grounded=(len(unsupported) == 0),
        coverage=avg_coverage,
        unsupported_claims=unsupported,
    )
