from __future__ import annotations

from rapidfuzz import fuzz, process

from pipeline.agenda_resolver_contracts import AgendaItemRecord
from pipeline.agenda_resolver_quality import _normalize_title


PAGE_NUMBER_MATCH_THRESHOLD = 88


def _apply_page_numbers_from_reference(
    primary_items: list[AgendaItemRecord],
    reference_items: list[AgendaItemRecord],
) -> list[AgendaItemRecord]:
    """
    Preserve deep-link quality by reusing page numbers from local extraction when possible.
    """
    if not primary_items or not reference_items:
        return primary_items

    title_to_page = {
        _normalize_title(str(item.get("title") or "")): item.get("page_number")
        for item in reference_items
        if _normalize_title(str(item.get("title") or "")) and item.get("page_number") not in (None, 0)
    }
    if not title_to_page:
        return primary_items

    for item in primary_items:
        if item.get("page_number") not in (None, 0):
            continue
        title = _normalize_title(str(item.get("title") or ""))
        if not title:
            continue
        match = process.extractOne(title, list(title_to_page.keys()), scorer=fuzz.token_sort_ratio)
        if match and match[1] >= PAGE_NUMBER_MATCH_THRESHOLD:
            item["page_number"] = title_to_page[match[0]]

    return primary_items
