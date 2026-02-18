import logging
import re
from difflib import SequenceMatcher

from pipeline.config import (
    TEXT_REPAIR_ENABLE_LLM_ESCALATION,
    TEXT_REPAIR_LLM_MAX_LINES_PER_DOC,
    TEXT_REPAIR_MIN_IMPLAUSIBILITY_SCORE,
)
from pipeline.lexicon import TEXT_REPAIR_CIVIC_LEXICON


logger = logging.getLogger("text-cleaning")

_SPACED_ALLCAPS_RE = re.compile(r"\b(?:[A-Z]\s+){2,}[A-Z]\b")
_ALLCAPS_TOKEN_RE = re.compile(r"^[A-Z]{1,6}$")
_SAFE_LINE_BLOCKERS = (
    re.compile(r"https?://|www\.|@"),
    re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"),
    re.compile(r"\b\d{3}[-\.\s]?\d{3}[-\.\s]?\d{4}\b"),
    re.compile(r"\b(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\b"),
    re.compile(r"\b\d{1,2}[:/]\d{1,2}\b"),
)

def _collapse_spaced_allcaps(text: str) -> str:
    """
    Collapse spaced-out ALLCAPS words like:
    "P R O C L A M A T I O N" -> "PROCLAMATION"
    """
    if not text:
        return ""

    def _join(match: re.Match) -> str:
        raw = match.group(0)
        raw = raw.replace("\n", "  ")
        raw = re.sub(r"\s{2,}", "|", raw)
        raw = re.sub(r"\s+", "", raw)
        raw = raw.replace("|", " ")
        return raw.strip()

    return _SPACED_ALLCAPS_RE.sub(_join, text)


def _is_line_safe_for_repair(line: str) -> bool:
    """
    Restrict deterministic repair to probable header lines.
    We avoid metadata-heavy lines so we don't rewrite IDs/URLs/phone numbers.
    """
    if not line or len(line) > 220:
        return False
    if any(rx.search(line) for rx in _SAFE_LINE_BLOCKERS):
        return False
    letters = re.sub(r"[^A-Za-z]", "", line)
    if len(letters) < 8:
        return False
    uppercase_ratio = sum(1 for ch in letters if ch.isupper()) / max(1, len(letters))
    return uppercase_ratio >= 0.8


def _line_fragmentation_score(line: str) -> float:
    """
    Score how likely a line is a broken ALL-CAPS header.
    Higher is worse; threshold-based escalation keeps repairs conservative.
    """
    tokens = [t for t in line.split() if t]
    if len(tokens) < 3:
        return 0.0
    caps_tokens = [t for t in tokens if _ALLCAPS_TOKEN_RE.match(t)]
    if len(caps_tokens) < 3:
        return 0.0
    short_ratio = sum(1 for t in caps_tokens if len(t) <= 2) / len(caps_tokens)
    single_ratio = sum(1 for t in caps_tokens if len(t) == 1) / len(caps_tokens)
    caps_ratio = len(caps_tokens) / len(tokens)
    run_boost = 0.2 if len(caps_tokens) >= 6 else 0.0
    score = (0.45 * short_ratio) + (0.25 * single_ratio) + (0.30 * caps_ratio) + run_boost
    return max(0.0, min(score, 1.0))


def _split_with_lexicon(joined: str) -> list[str]:
    """
    Deterministically split merged uppercase text using a small civic lexicon.
    Unknown spans are allowed but penalized, so we avoid aggressive rewriting.
    """
    n = len(joined)
    if n == 0:
        return []

    max_word = min(20, n)
    # dp[i] -> (cost, parts to i)
    dp: list[tuple[float, list[str]] | None] = [None] * (n + 1)
    dp[0] = (0.0, [])
    for i in range(n):
        if dp[i] is None:
            continue
        base_cost, base_parts = dp[i]
        for j in range(i + 1, min(n, i + max_word) + 1):
            part = joined[i:j]
            if part in TEXT_REPAIR_CIVIC_LEXICON:
                cost = base_cost + 0.1
            elif len(part) == 1:
                cost = base_cost + 2.0
            else:
                # Unknown chunks are allowed but penalized by length.
                cost = base_cost + 1.0 + (len(part) / 10.0)
            cand = (cost, base_parts + [part])
            if dp[j] is None or cand[0] < dp[j][0]:
                dp[j] = cand
    return dp[n][1] if dp[n] else [joined]


def _repair_chunked_allcaps_line(line: str) -> str:
    """
    Repair chunked ALL-CAPS artifacts while rejecting risky merges.
    """
    if not _is_line_safe_for_repair(line):
        return line
    before_score = _line_fragmentation_score(line)
    # Deterministic repair should run on moderately-fragmented lines.
    # LLM escalation uses a stricter threshold configured separately.
    if before_score < 0.50:
        return line

    tokens = line.split()
    out: list[str] = []
    i = 0
    while i < len(tokens):
        if not _ALLCAPS_TOKEN_RE.match(tokens[i]):
            out.append(tokens[i])
            i += 1
            continue

        j = i
        while j < len(tokens) and _ALLCAPS_TOKEN_RE.match(tokens[j]):
            j += 1
        run = tokens[i:j]
        if len(run) < 3:
            out.extend(run)
            i = j
            continue

        joined = "".join(run)
        # Lexicon split avoids mega-token gibberish and can recover merged boundaries
        # like ANNOTATEDAGENDA -> ANNOTATED AGENDA.
        split_parts = _split_with_lexicon(joined)
        if len(joined) <= 20 and len(split_parts) == 1 and len(run) <= 3:
            # Keep short all-caps phrases conservative unless we can split confidently.
            out.extend(run)
        else:
            out.extend(split_parts)
        i = j

    candidate = " ".join(out)
    # Reject changes that do not materially improve fragmentation.
    after_score = _line_fragmentation_score(candidate)
    if after_score > (before_score - 0.15):
        return line
    # Guardrail: avoid giant merged tokens that are usually wrong.
    if any(len(tok) > 26 for tok in candidate.split()):
        return line
    return candidate


def _default_llm_repair(line: str) -> str | None:
    try:
        from pipeline.llm import LocalAI

        return LocalAI().repair_title_spacing(line)
    except Exception:
        return None


def _is_valid_spacing_only_repair(source: str, candidate: str) -> bool:
    if not candidate:
        return False
    src = re.sub(r"\s+", "", source or "")
    dst = re.sub(r"\s+", "", candidate or "")
    # Spacing-only means same non-space content.
    if src != dst:
        return False
    # Guard against pathological retokenization.
    src_tokens = max(1, len((source or "").split()))
    dst_tokens = len((candidate or "").split())
    if dst_tokens > (src_tokens * 2):
        return False
    # Similarity guard keeps accidental formatting noise low.
    ratio = SequenceMatcher(None, source, candidate).ratio()
    return ratio >= 0.55


def postprocess_extracted_text(text: str, llm_repair_fn=None) -> str:
    """
    Clean extracted text for downstream NLP without changing semantics.
    """
    if not text:
        return ""

    value = _collapse_spaced_allcaps(text)
    lines = value.splitlines()
    counters = {
        "lines_scanned": 0,
        "lines_repaired_deterministic": 0,
        "lines_escalated_llm": 0,
        "lines_repair_rejected": 0,
    }
    llm_budget = TEXT_REPAIR_LLM_MAX_LINES_PER_DOC
    repair_callable = llm_repair_fn or _default_llm_repair

    repaired_lines: list[str] = []
    for line in lines:
        counters["lines_scanned"] += 1
        repaired = _repair_chunked_allcaps_line(line)
        if repaired != line:
            counters["lines_repaired_deterministic"] += 1

        # LLM escalation is opt-in and capped for throughput predictability.
        if (
            TEXT_REPAIR_ENABLE_LLM_ESCALATION
            and llm_budget > 0
            and _line_fragmentation_score(repaired) >= TEXT_REPAIR_MIN_IMPLAUSIBILITY_SCORE
        ):
            llm_candidate = repair_callable(repaired)
            if _is_valid_spacing_only_repair(repaired, llm_candidate or ""):
                repaired = (llm_candidate or "").strip()
                counters["lines_escalated_llm"] += 1
                llm_budget -= 1
            else:
                counters["lines_repair_rejected"] += 1

        repaired_lines.append(repaired)

    value = "\n".join(repaired_lines)
    value = re.sub(r"[ \t]+\n", "\n", value)
    value = re.sub(r"\n{4,}", "\n\n\n", value)
    logger.debug("text_cleaning.counters=%s", counters)
    return value.strip()
