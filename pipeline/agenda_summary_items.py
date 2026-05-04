from typing import TypeAlias

from pipeline.agenda_text_heuristics import (
    is_contact_or_letterhead_noise,
    is_probable_line_fragment_title,
    is_procedural_noise_title,
    looks_like_agenda_segmentation_boilerplate,
    normalize_spaces,
)


AgendaSummaryItem: TypeAlias = dict[str, object]


def serialize_item_for_filtering(item: AgendaSummaryItem) -> str:
    serialized = str(item.get("title", ""))
    if item.get("description"):
        serialized = f"{serialized} - {item['description']}"
    return serialized


def split_agenda_summary_item(value: str) -> tuple[str, str]:
    text = normalize_spaces(value)
    if not text:
        return "", ""
    if " - " in text:
        left, right = text.split(" - ", 1)
        return left.strip(), right.strip()
    return text, ""


def _coerced_page_number(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def coerce_agenda_summary_item(item: object, idx: int = 0) -> AgendaSummaryItem:
    if isinstance(item, dict):
        return {
            "order": idx + 1,
            "title": normalize_spaces(item.get("title", "")),
            "description": normalize_spaces(item.get("description", "")),
            "classification": normalize_spaces(item.get("classification", "")),
            "result": normalize_spaces(item.get("result", "")),
            "page_number": _coerced_page_number(item.get("page_number")),
        }

    title, desc = split_agenda_summary_item(normalize_spaces(item or ""))
    return {
        "order": idx + 1,
        "title": title,
        "description": desc,
        "classification": "",
        "result": "",
        "page_number": 0,
    }


def agenda_items_source_text(items: list[AgendaSummaryItem]) -> str:
    lines = []
    for item in items:
        bits = [f"Title: {item.get('title', '')}"]
        if item.get("description"):
            bits.append(f"Description: {item['description']}")
        if item.get("classification"):
            bits.append(f"Classification: {item['classification']}")
        if item.get("result"):
            bits.append(f"Result: {item['result']}")
        if item.get("page_number"):
            bits.append(f"Page: {item['page_number']}")
        lines.append(" | ".join(bits))
    return "\n".join(lines).strip()


def should_drop_from_agenda_summary(item_text: str, *, min_substantive_desc_chars: int) -> bool:
    title, desc = split_agenda_summary_item(item_text)
    if not title:
        return True
    title_looks_noisy = (
        looks_like_agenda_segmentation_boilerplate(title)
        or is_procedural_noise_title(title)
        or is_contact_or_letterhead_noise(title, desc)
        or is_probable_line_fragment_title(title)
    )
    if not title_looks_noisy:
        return False
    return len(normalize_spaces(desc)) < min_substantive_desc_chars
