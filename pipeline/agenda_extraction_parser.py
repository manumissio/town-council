from __future__ import annotations

import re

from pipeline.config import LLM_AGENDA_MAX_TEXT


AgendaItemPayload = dict[str, object]

_ITEM_HEADER_RE = re.compile(r"(?im)^\s*ITEM\s+(?P<order>\d+)\s*:\s*")
_FALLBACK_PARAGRAPH_BOUNDARY_RE = re.compile(
    r"(?i)^\s*("
    r"subject\s*:"
    r"|item\s*#?\s*\d{1,3}\b"
    r"|#?\s*\d{1,2}(?:\.\d+)?[\.\):]\s+"
    r"|[A-Z][A-Z\s]{12,}"
    r")"
)


def build_agenda_extraction_prompt(text: str, *, max_text: int = LLM_AGENDA_MAX_TEXT) -> str:
    """
    Preserve the current extraction prompt contract while centralizing prompt assembly.
    """
    safe_text = (text or "")[:max_text]
    return (
        "<start_of_turn>user\n"
        "Extract ONLY the real agenda items from this meeting document. "
        "Include the page number where each item starts. "
        "Format: ITEM [Order]: [Title] (Page [X]) - [Brief Summary]\n"
        "Rules:\n"
        "- Do NOT extract procedural placeholders (Call to Order, Roll Call, Adjournment, Public Comment).\n"
        "- Do NOT extract teleconference/Zoom/ADA/how-to-attend instructions.\n"
        "- Do NOT extract Table of Contents entries.\n"
        "- Do NOT extract contact/letterhead metadata (addresses, phone/fax, email, website, From:/To: lines).\n\n"
        "- HIERARCHY RULE: If a primary item contains a table/list/subparts, extract ONLY the parent item. "
        "Do not emit each row/sub-part as a separate item.\n\n"
        f"Text:\n{safe_text}<end_of_turn>\n"
        "<start_of_turn>model\n"
        "ITEM 1:"
    )


def reconstruct_llm_agenda_content(raw_content: str) -> str:
    """
    Restore the leading ITEM marker only when the continuation clearly followed the prompt shape.
    """
    if (
        "(page" in raw_content.lower()
        or re.search(r"(?im)^\s*ITEM\s+\d+\s*:", raw_content)
        or re.search(r"(?im)\n\s*ITEM\s+\d+\s*:", raw_content)
    ):
        return "ITEM 1:" + raw_content
    return raw_content


def parse_llm_agenda_items(llm_text: str) -> list[AgendaItemPayload]:
    """
    Parse agenda items from the provider text while preserving multiline descriptions.
    """
    text = (llm_text or "").strip()
    if not text:
        return []

    headers = list(_ITEM_HEADER_RE.finditer(text))
    if not headers:
        return []

    parsed_items: list[AgendaItemPayload] = []
    for index, match in enumerate(headers):
        item_payload = _parse_llm_item_body(text, headers, index, match)
        if item_payload is not None:
            parsed_items.append(item_payload)

    return _dedupe_llm_items(parsed_items)


def iter_fallback_paragraphs(page_content: str) -> list[str]:
    """
    Build paragraph-like chunks for the weakest heuristic fallback.
    """
    raw = (page_content or "").replace("\r\n", "\n").replace("\r", "\n")
    if not raw.strip():
        return []

    blank_paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n+", raw) if paragraph.strip()]
    if len(blank_paragraphs) >= 3:
        return blank_paragraphs

    paragraphs: list[str] = []
    current_lines: list[str] = []
    for line in [line.strip() for line in raw.splitlines()]:
        if not line:
            if current_lines:
                paragraphs.append("\n".join(current_lines).strip())
                current_lines = []
            continue
        if _FALLBACK_PARAGRAPH_BOUNDARY_RE.match(line) and current_lines:
            paragraphs.append("\n".join(current_lines).strip())
            current_lines = [line]
            continue
        current_lines.append(line)
    if current_lines:
        paragraphs.append("\n".join(current_lines).strip())
    return [paragraph for paragraph in paragraphs if paragraph]


def _parse_llm_item_body(
    text: str,
    headers: list[re.Match[str]],
    index: int,
    match: re.Match[str],
) -> AgendaItemPayload | None:
    try:
        order = int(match.group("order"))
    except (TypeError, ValueError):
        return None

    end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
    body = text[match.end() : end].strip()
    if not body:
        return None

    page_number, title_part, description_part = _split_llm_item_body(body)
    title = " ".join((title_part or "").split())
    if not title:
        return None

    description = re.sub(r"^[-\u2013\u2014:]\s*", "", (description_part or "").strip())
    return {
        "order": order,
        "title": title,
        "page_number": page_number,
        "description": " ".join(description.split()),
    }


def _split_llm_item_body(body: str) -> tuple[int, str, str]:
    page_match = re.search(r"(?i)\(\s*page\s*(\d+)\s*\)", body)
    if page_match:
        try:
            page_number = int(page_match.group(1))
        except (TypeError, ValueError):
            page_number = 1
        return page_number, body[: page_match.start()].strip(), body[page_match.end() :].strip()

    separator = re.search(r"\s+[-\u2013\u2014:]\s+", body)
    if separator:
        return 1, body[: separator.start()].strip(), body[separator.end() :].strip()

    first_line, *rest = body.splitlines()
    return 1, first_line.strip(), " ".join(line.strip() for line in rest).strip()


def _dedupe_llm_items(items: list[AgendaItemPayload]) -> list[AgendaItemPayload]:
    seen: set[tuple[int, str]] = set()
    deduped: list[AgendaItemPayload] = []
    for agenda_item in items:
        key = (int(agenda_item["order"]), str(agenda_item["title"]).lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(agenda_item)
    return deduped
