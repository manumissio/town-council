import re
from dataclasses import dataclass

from pipeline.config import SUMMARY_GROUNDING_MIN_COVERAGE
from pipeline.summary_source_quality import tokenize_summary_quality_text


_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "was",
    "were",
    "with",
    "this",
    "these",
    "those",
    "will",
    "would",
    "can",
    "could",
    "may",
    "might",
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
class GroundingResult:
    is_grounded: bool
    coverage: float
    unsupported_claims: list[str]


def extract_claim_lines(summary: str) -> list[str]:
    if not summary:
        return []
    lines = []
    for raw in summary.splitlines():
        line = " ".join((raw or "").strip().split())
        if not line:
            continue
        line = re.sub(r"^\s*[\*\-\u2022]+\s*", "", line).strip()
        line = re.sub(r"^[^A-Za-z0-9]+", "", line).strip()
        if _is_non_claim_line(line):
            continue
        lines.append(line)
    return lines


def _is_non_claim_line(line: str) -> bool:
    if not line:
        return True
    lowered = line.lower()
    if lowered.startswith("bluf:"):
        return True
    if lowered in _SECTION_HEADERS:
        return True
    if lowered.endswith(":") and len(tokenize_summary_quality_text(lowered)) <= 6:
        return True
    if lowered.startswith("here") and "summary" in lowered:
        return True
    if "executive summary" in lowered or ("summary" in lowered and lowered.endswith(":")):
        return True
    if lowered.startswith("here's a summary") or lowered.startswith("here is a summary"):
        return True
    if lowered.startswith("summary of the meeting"):
        return True
    return len(line) < 5


def prune_unsupported_summary_lines(summary: str, source_text: str) -> tuple[str, int]:
    """
    Remove unsupported claim lines while preserving BLUF/section structure.

    Returns:
      (pruned_summary, removed_count)
    """
    if not (summary or "").strip():
        return "", 0

    source_tokens = set(tokenize_summary_quality_text(source_text or ""))
    if not source_tokens:
        return summary.strip(), 0
    source_prefixes = {tok[:5] for tok in source_tokens if len(tok) >= 5}

    removed = 0
    kept_lines: list[str] = []
    for raw in (summary or "").splitlines():
        line = (raw or "").rstrip()
        stripped = line.strip()
        lowered = stripped.lower()
        if not stripped or lowered.startswith("bluf:") or lowered in _SECTION_HEADERS:
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


def _claim_coverage(claim: str, source_tokens: set[str], source_prefixes: set[str]) -> float:
    claim_tokens = [
        token for token in tokenize_summary_quality_text(claim) if len(token) >= 3 and token not in _STOPWORDS
    ]
    if not claim_tokens:
        return 1.0
    matched = 0
    for token in claim_tokens:
        if token in source_tokens:
            matched += 1
            continue
        if len(token) >= 5 and token[:5] in source_prefixes:
            matched += 1
            continue
    return matched / len(claim_tokens)


def is_summary_grounded(summary: str, source_text: str) -> GroundingResult:
    claims = extract_claim_lines(summary)
    if not claims:
        claims = _fallback_bluf_claims(summary)
        if not claims:
            return GroundingResult(is_grounded=False, coverage=0.0, unsupported_claims=["No summary claims found"])

    source_tokens = set(tokenize_summary_quality_text(source_text or ""))
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


def _fallback_bluf_claims(summary: str) -> list[str]:
    for raw in (summary or "").splitlines():
        line = " ".join((raw or "").strip().split())
        if line.lower().startswith("bluf:"):
            bluf = line.split(":", 1)[1].strip()
            return [bluf] if len(bluf) >= 5 else []
    return []
