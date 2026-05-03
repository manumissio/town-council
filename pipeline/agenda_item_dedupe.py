from __future__ import annotations

from typing import SupportsInt

from rapidfuzz import fuzz

from pipeline.agenda_item_acceptance import llm_item_substance_score
from pipeline.agenda_text_normalization import normalize_spaces, normalized_title_key
from pipeline.config import AGENDA_TOC_DEDUP_FUZZ


AgendaItemPayload = dict[str, object]


def dedupe_agenda_items_for_document(items: list[AgendaItemPayload]) -> tuple[list[AgendaItemPayload], int]:
    """
    Collapse near-duplicate agenda titles within one document.
    """
    if not items:
        return items, 0

    groups = _group_duplicate_agenda_items(items)
    winners: list[tuple[int, AgendaItemPayload]] = []
    duplicates_removed = 0
    for group in groups:
        if len(group) > 1:
            duplicates_removed += len(group) - 1
        winners.append(_winning_agenda_item(group))

    winners.sort(key=lambda pair: pair[0])
    return [item for _, item in winners], duplicates_removed


def _group_duplicate_agenda_items(
    items: list[AgendaItemPayload],
) -> list[list[tuple[int, AgendaItemPayload]]]:
    groups: list[list[tuple[int, AgendaItemPayload]]] = []
    for index, agenda_item in enumerate(items):
        title_key = normalized_title_key(agenda_item.get("title", ""))
        if not title_key:
            continue
        matched = _matching_group_index(groups, title_key)
        if matched is None:
            groups.append([(index, agenda_item)])
        else:
            groups[matched].append((index, agenda_item))
    return groups


def _matching_group_index(groups: list[list[tuple[int, AgendaItemPayload]]], title_key: str) -> int | None:
    for group_index, group in enumerate(groups):
        reference_key = normalized_title_key(group[0][1].get("title", ""))
        if fuzz.token_sort_ratio(title_key, reference_key) >= AGENDA_TOC_DEDUP_FUZZ:
            return group_index
    return None


def _winning_agenda_item(group: list[tuple[int, AgendaItemPayload]]) -> tuple[int, AgendaItemPayload]:
    return max(
        group,
        key=lambda pair: (
            _page_number_sort_value(pair[1].get("page_number")),
            llm_item_substance_score(pair[1].get("title", ""), pair[1].get("description", "")),
            len(normalize_spaces(pair[1].get("description", ""))),
            -pair[0],
        ),
    )


def _page_number_sort_value(value: object) -> int:
    if not value:
        return 0
    if isinstance(value, str):
        return int(value)
    if isinstance(value, SupportsInt):
        return int(value)
    return 0
