import re
from typing import Callable

from pipeline.agenda_text_heuristics import (
    dedupe_lines_preserve_order,
    looks_like_attendance_boilerplate,
)
from pipeline.config import LLM_SUMMARY_MAX_TEXT
from pipeline.document_kinds import normalize_summary_doc_kind


_SUMMARY_DOC_KINDS = {"minutes", "agenda", "unknown"}
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


def strip_summary_output_boilerplate(summary: str) -> str:
    """
    Backwards-compatible wrapper for summary cleanup.
    """
    return summary


def strip_summary_boilerplate(text: str) -> str:
    """
    Remove common meeting boilerplate that pollutes both summaries and topic extraction.
    """
    if not text:
        return text

    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if looks_like_attendance_boilerplate(line):
            continue
        lines.append(line)
    return "\n".join(dedupe_lines_preserve_order(lines)).strip()


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


def normalize_summary_output_to_bluf(summary: str, source_text: str = "") -> str:
    """
    Normalize summary output into a BLUF-first, plain-text format.
    """
    if not summary:
        return summary

    from pipeline.config import SUMMARY_GROUNDING_MIN_COVERAGE

    source_tokens = set(_tokenize(source_text or ""))
    source_prefixes = {token[:5] for token in source_tokens if len(token) >= 5}

    raw_lines = [line.rstrip() for line in summary.splitlines()]
    cleaned_lines = []
    for raw in raw_lines:
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
        if not line:
            continue

        line = re.sub(r"^\s*\d+\s*[\.\)]\s*", "", line).strip()
        if not line:
            continue
        if looks_like_attendance_boilerplate(line):
            continue
        cleaned_lines.append(line)

    cleaned_lines = dedupe_lines_preserve_order(cleaned_lines)
    if not cleaned_lines:
        return _fallback_summary_snippet(source_text)

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
    bullets = dedupe_lines_preserve_order(bullets)
    if source_tokens:
        bullets = [
            bullet
            for bullet in bullets
            if _grounding_coverage(bullet, source_tokens, source_prefixes) >= SUMMARY_GROUNDING_MIN_COVERAGE
        ]
    bullets = bullets[:7]

    if len(bullets) < 3 and len(cleaned_lines) >= 3:
        for extra in cleaned_lines:
            if extra.lower().startswith("bluf:"):
                continue
            if extra in bullets:
                continue
            if looks_like_attendance_boilerplate(extra):
                continue
            bullets.append(extra)
            if len(bullets) >= 3:
                break
        if source_tokens:
            bullets = [
                bullet
                for bullet in bullets
                if _grounding_coverage(bullet, source_tokens, source_prefixes) >= SUMMARY_GROUNDING_MIN_COVERAGE
            ]
        bullets = bullets[:7]

    if len(bullets) == 0 and source_text:
        text = re.sub(r"\[PAGE\s+\d+\]\s*", "\n", source_text or "", flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text).replace(" \n ", "\n")
        raw_chunks = []
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            parts = re.split(r"\b\d+\.\s+", line)
            for part in parts:
                part = part.strip()
                if part:
                    raw_chunks.append(part)

        candidates = []
        for chunk in raw_chunks:
            if looks_like_attendance_boilerplate(chunk):
                continue
            if len(chunk) < 12:
                continue
            candidates.append(chunk)
            if len(candidates) >= 7:
                break
        bullets = dedupe_lines_preserve_order(candidates)[:7]
        if len(bullets) == 0:
            snippet = re.sub(r"\[PAGE\s+\d+\]\s*", " ", (source_text or ""), flags=re.IGNORECASE).strip()
            snippet = " ".join(snippet.split())
            if snippet:
                bullets = [snippet[:200]]

    if len(bullets) == 0:
        bullets = ["Summary unavailable from extracted text."]

    output_lines = [f"BLUF: {bluf_text}".strip()]
    for bullet in bullets:
        output_lines.append(f"- {bullet.strip()}")
    return "\n".join(output_lines).strip()


def prepare_summary_prompt(text: str, doc_kind: str = "unknown") -> str:
    """
    Build a summarization prompt that matches the document type.
    """
    kind = normalize_summary_doc_kind(doc_kind)
    if kind not in _SUMMARY_DOC_KINDS:
        kind = "unknown"

    safe_text = (text or "")[:LLM_SUMMARY_MAX_TEXT]
    stripped = strip_summary_boilerplate(safe_text)
    if stripped and len(stripped) >= max(200, int(0.2 * len(safe_text))):
        safe_text = stripped

    if kind == "minutes":
        instruction = (
            "Write a plain-text executive summary of these meeting minutes. "
            "Format requirements:\n"
            "1) First line must be: BLUF: <one-sentence takeaway>\n"
            "2) Then write 3 to 7 bullets, one per line, each starting with '- '\n"
            "3) Plain text only. Do not use Markdown (*, **, headings).\n"
            "Content requirements:\n"
            "- Focus on decisions, actions taken, and vote outcomes.\n"
            "- Do NOT summarize teleconference/Zoom/ADA/how-to-attend details."
        )
    elif kind == "agenda":
        instruction = (
            "Write a plain-text executive summary of this meeting agenda. "
            "Format requirements:\n"
            "1) First line must be: BLUF: <one-sentence takeaway>\n"
            "2) Then write 3 to 7 bullets, one per line, each starting with '- '\n"
            "3) Plain text only. Do not use Markdown (*, **, headings).\n"
            "Content requirements:\n"
            "- Focus on the main scheduled items and expected actions.\n"
            "- Do NOT summarize teleconference/Zoom/ADA/how-to-attend details."
        )
    else:
        instruction = (
            "Write a plain-text executive summary of this meeting document. "
            "Format requirements:\n"
            "1) First line must be: BLUF: <one-sentence takeaway>\n"
            "2) Then write 3 to 7 bullets, one per line, each starting with '- '\n"
            "3) Plain text only. Do not use Markdown (*, **, headings).\n"
            "Content requirements:\n"
            "- Do NOT summarize teleconference/Zoom/ADA/how-to-attend details."
        )

    return (
        "<start_of_turn>user\n"
        f"{instruction}\n"
        "Return only the BLUF line and the bullet lines. No extra text.\n"
        f"{safe_text}<end_of_turn>\n"
        "<start_of_turn>model\n"
    )


def build_title_spacing_prompt(raw_line: str) -> str:
    source = (raw_line or "").strip()
    return (
        "<start_of_turn>user\n"
        "Fix spacing/kerning errors in this ALL-CAPS meeting heading.\n"
        "Rules:\n"
        "- Do not change words.\n"
        "- Do not add or remove punctuation.\n"
        "- Only fix spaces between letters/words.\n"
        "- Output one plain-text line only.\n\n"
        f"Input: {source}\n"
        "<end_of_turn>\n"
        "<start_of_turn>model\n"
    )


def normalize_title_spacing_output(text: str) -> str | None:
    if not text:
        return None
    return " ".join(text.splitlines()).strip() or None


def normalize_json_response(text: str) -> str | None:
    if not text:
        return None
    if text.startswith("{"):
        return text
    return "{" + text


def run_summary_text_pipeline(
    provider,
    *,
    text: str,
    doc_kind: str,
    call_provider_text_or_none: Callable[..., str | None],
) -> str | None:
    from pipeline.config import LLM_SUMMARY_MAX_TOKENS

    prompt = prepare_summary_prompt(text, doc_kind=doc_kind)
    raw = call_provider_text_or_none(
        lambda: (
            provider.summarize_text(
                prompt,
                max_tokens=LLM_SUMMARY_MAX_TOKENS,
                temperature=0.1,
            )
            or ""
        ).strip(),
        operation_label="AI Summarization",
    )
    if not raw:
        return None
    normalized = normalize_summary_output_to_bluf(raw, source_text=text)
    return normalized or raw
