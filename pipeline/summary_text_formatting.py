import re

from pipeline.agenda_text_heuristics import (
    dedupe_lines_preserve_order,
    looks_like_attendance_boilerplate,
)


_WORD_RE = re.compile(r"[a-z0-9']+")
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
_BLUF_UNAVAILABLE = "BLUF: Summary unavailable from extracted text.\n- Summary unavailable."


def strip_markdown_emphasis(text: str) -> str:
    """
    Remove common Markdown emphasis markers from model output.
    """
    if not text:
        return text
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text


def strip_llm_acknowledgements(text: str) -> str:
    """
    Remove common acknowledgement preambles from LLM output.
    """
    if not text:
        return ""

    lines = [line.rstrip() for line in text.splitlines()]
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue

        lowered = line.lower()
        if "bluf:" in lowered:
            bluf_index = lowered.index("bluf:")
            suffix = "\n".join(lines[index + 1 :]).strip()
            value = line[bluf_index:].strip()
            return value if not suffix else f"{value}\n{suffix}"
        if (
            lowered.startswith("okay")
            or lowered.startswith("sure")
            or lowered.startswith("certainly")
            or lowered.startswith("got it")
            or lowered.startswith("understood")
            or "i understand" in lowered
            or lowered.startswith("i will")
            or lowered.startswith("i'll")
        ):
            index += 1
            continue
        break

    return "\n".join(lines[index:]).strip()


def normalize_bullets_to_dash(text: str) -> str:
    """
    Normalize bullet markers to "- " (plain text).
    """
    if not text:
        return ""
    text = re.sub(r"(?m)^\s*[\*\u2022]\s+", "- ", text)
    text = re.sub(r"(?m)^\s+-\s+", "- ", text)
    return text


def _first_sentence(value: str) -> str:
    if not value:
        return value
    value = value.strip()
    match = re.search(r"^(.+?[\.!\?])(\s|$)", value)
    return (match.group(1) if match else value).strip()


def _cap_words(value: str, max_words: int = 30) -> str:
    if not value:
        return value
    words = value.strip().split()
    if len(words) <= max_words:
        return value.strip()
    return " ".join(words[:max_words]).rstrip(".,;:") + "."


def _tokenize(value: str) -> list[str]:
    return _WORD_RE.findall((value or "").lower())


def _grounding_coverage(claim: str, source_tokens: set[str], source_prefixes: set[str]) -> float:
    claim_tokens = [token for token in _tokenize(claim) if len(token) >= 3 and token not in _STOPWORDS]
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


def _fallback_summary_snippet(source_text: str) -> str:
    snippet = re.sub(r"\[PAGE\s+\d+\]\s*", " ", (source_text or ""), flags=re.IGNORECASE).strip()
    snippet = " ".join(snippet.split())
    if snippet:
        return f"BLUF: Summary unavailable from extracted text.\n- {snippet[:200]}"
    return _BLUF_UNAVAILABLE


def _grounded_bullets(bullets: list[str], source_tokens: set[str], source_prefixes: set[str]) -> list[str]:
    from pipeline.config import SUMMARY_GROUNDING_MIN_COVERAGE

    if not source_tokens:
        return bullets
    return [
        bullet
        for bullet in bullets
        if _grounding_coverage(bullet, source_tokens, source_prefixes) >= SUMMARY_GROUNDING_MIN_COVERAGE
    ]


def _fallback_bullets_from_source(source_text: str) -> list[str]:
    text = re.sub(r"\[PAGE\s+\d+\]\s*", "\n", source_text or "", flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).replace(" \n ", "\n")
    raw_chunks = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        raw_chunks.extend(part.strip() for part in re.split(r"\b\d+\.\s+", line) if part.strip())

    candidates = []
    for chunk in raw_chunks:
        if looks_like_attendance_boilerplate(chunk) or len(chunk) < 12:
            continue
        candidates.append(chunk)
        if len(candidates) >= 7:
            break
    bullets = dedupe_lines_preserve_order(candidates)[:7]
    if bullets:
        return bullets

    snippet = re.sub(r"\[PAGE\s+\d+\]\s*", " ", (source_text or ""), flags=re.IGNORECASE).strip()
    snippet = " ".join(snippet.split())
    return [snippet[:200]] if snippet else []


def normalize_summary_output_to_bluf(summary: str, source_text: str = "") -> str:
    """
    Normalize summary output into a BLUF-first, plain-text format.
    """
    if not summary:
        return summary

    source_tokens = set(_tokenize(source_text or ""))
    source_prefixes = {token[:5] for token in source_tokens if len(token) >= 5}
    cleaned_lines = _clean_summary_lines(summary)
    if not cleaned_lines:
        return _fallback_summary_snippet(source_text)

    bluf_text, bullets = _split_bluf_and_bullets(cleaned_lines)
    bullets = _grounded_bullets(bullets[:7], source_tokens, source_prefixes)
    if len(bullets) < 3 and len(cleaned_lines) >= 3:
        bullets = _add_extra_bullets(cleaned_lines, bullets)
        bullets = _grounded_bullets(bullets, source_tokens, source_prefixes)[:7]

    if len(bullets) == 0 and source_text:
        bullets = _fallback_bullets_from_source(source_text)
    if len(bullets) == 0:
        bullets = ["Summary unavailable from extracted text."]

    output_lines = [f"BLUF: {bluf_text}".strip()]
    output_lines.extend(f"- {bullet.strip()}" for bullet in bullets)
    return "\n".join(output_lines).strip()


def _clean_summary_lines(summary: str) -> list[str]:
    cleaned_lines = []
    for raw in [line.rstrip() for line in summary.splitlines()]:
        line = (raw or "").strip()
        if not line:
            continue
        lowered = line.lower()
        if (lowered.startswith("here") and "summary" in lowered) or ("executive summary" in lowered):
            continue
        if lowered.startswith("summary of the meeting"):
            continue
        line = strip_markdown_emphasis(line).strip()
        line = re.sub(r"^\s*[\*\-\u2022]+\s*", "", line).strip()
        line = re.sub(r"^\s*\d+\s*[\.\)]\s*", "", line).strip()
        if line and not looks_like_attendance_boilerplate(line):
            cleaned_lines.append(line)
    return dedupe_lines_preserve_order(cleaned_lines)


def _split_bluf_and_bullets(cleaned_lines: list[str]) -> tuple[str, list[str]]:
    bluf_text = None
    bullets = []
    for line in cleaned_lines:
        if line.lower().startswith("bluf:"):
            bluf_text = line.split(":", 1)[1].strip()
            continue
        bullets.append(line)

    if not bluf_text:
        bluf_text = bullets[0] if bullets else cleaned_lines[0]
    bluf_text = _cap_words(_first_sentence(bluf_text), max_words=30)
    if bluf_text and not bluf_text.endswith((".", "!", "?")):
        bluf_text = bluf_text.rstrip(".,;:") + "."
    if looks_like_attendance_boilerplate(bluf_text):
        bluf_text = "Key meeting takeaway is unclear from extracted text."

    bullets = [bullet for bullet in bullets if bullet and not looks_like_attendance_boilerplate(bullet)]
    return bluf_text, dedupe_lines_preserve_order(bullets)


def _add_extra_bullets(cleaned_lines: list[str], bullets: list[str]) -> list[str]:
    for extra in cleaned_lines:
        if extra.lower().startswith("bluf:") or extra in bullets:
            continue
        if looks_like_attendance_boilerplate(extra):
            continue
        bullets.append(extra)
        if len(bullets) >= 3:
            break
    return bullets
