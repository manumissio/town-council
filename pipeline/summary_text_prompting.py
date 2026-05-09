from typing import Callable

from pipeline.agenda_text_heuristics import (
    dedupe_lines_preserve_order,
    looks_like_attendance_boilerplate,
)
from pipeline.config import LLM_SUMMARY_MAX_TEXT
from pipeline.document_kinds import normalize_summary_doc_kind
from pipeline.summary_text_formatting import normalize_summary_output_to_bluf


_SUMMARY_DOC_KINDS = {"minutes", "agenda", "unknown"}


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

    return (
        "<start_of_turn>user\n"
        f"{_summary_instruction(kind)}\n"
        "Return only the BLUF line and the bullet lines. No extra text.\n"
        f"{safe_text}<end_of_turn>\n"
        "<start_of_turn>model\n"
    )


def _summary_instruction(kind: str) -> str:
    if kind == "minutes":
        return (
            "Write a plain-text executive summary of these meeting minutes. "
            "Format requirements:\n"
            "1) First line must be: BLUF: <one-sentence takeaway>\n"
            "2) Then write 3 to 7 bullets, one per line, each starting with '- '\n"
            "3) Plain text only. Do not use Markdown (*, **, headings).\n"
            "Content requirements:\n"
            "- Focus on decisions, actions taken, and vote outcomes.\n"
            "- Do NOT summarize teleconference/Zoom/ADA/how-to-attend details."
        )
    if kind == "agenda":
        return (
            "Write a plain-text executive summary of this meeting agenda. "
            "Format requirements:\n"
            "1) First line must be: BLUF: <one-sentence takeaway>\n"
            "2) Then write 3 to 7 bullets, one per line, each starting with '- '\n"
            "3) Plain text only. Do not use Markdown (*, **, headings).\n"
            "Content requirements:\n"
            "- Focus on the main scheduled items and expected actions.\n"
            "- Do NOT summarize teleconference/Zoom/ADA/how-to-attend details."
        )
    return (
        "Write a plain-text executive summary of this meeting document. "
        "Format requirements:\n"
        "1) First line must be: BLUF: <one-sentence takeaway>\n"
        "2) Then write 3 to 7 bullets, one per line, each starting with '- '\n"
        "3) Plain text only. Do not use Markdown (*, **, headings).\n"
        "Content requirements:\n"
        "- Do NOT summarize teleconference/Zoom/ADA/how-to-attend details."
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
