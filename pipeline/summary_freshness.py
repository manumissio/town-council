from __future__ import annotations

import json
from typing import Any, Iterable

from pipeline.content_hash import compute_content_hash, normalize_text_for_hash
from pipeline.document_kinds import normalize_summary_doc_kind


def _agenda_item_value(item: Any, field: str) -> Any:
    if isinstance(item, dict):
        return item.get(field)
    return getattr(item, field, None)


def _agenda_item_int(item: Any, field: str) -> int | None:
    value = _agenda_item_value(item, field)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def compute_agenda_items_hash(items: Iterable[Any]) -> str | None:
    """
    Agenda summaries are derived from structured rows, not raw extracted text. We
    hash only the fields that can affect deterministic summary output so batch
    hydration can cheaply skip catalogs whose agenda payload is already current.
    """
    normalized_items: list[dict[str, Any]] = []
    for item in items or []:
        normalized_items.append(
            {
                "order": _agenda_item_int(item, "order"),
                "title": normalize_text_for_hash(str(_agenda_item_value(item, "title") or "")),
                "description": normalize_text_for_hash(str(_agenda_item_value(item, "description") or "")),
                "classification": normalize_text_for_hash(str(_agenda_item_value(item, "classification") or "")),
                "result": normalize_text_for_hash(str(_agenda_item_value(item, "result") or "")),
                "page_number": _agenda_item_int(item, "page_number"),
            }
        )
    if not normalized_items:
        return None
    payload = json.dumps(normalized_items, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return compute_content_hash(payload)


def compute_summary_source_hash(
    doc_kind: str | None,
    *,
    content_hash: str | None,
    agenda_items_hash: str | None,
) -> str | None:
    normalized_kind = normalize_summary_doc_kind(doc_kind)
    if normalized_kind == "agenda":
        return agenda_items_hash
    return content_hash


def is_summary_fresh(
    doc_kind: str | None,
    *,
    summary: str | None,
    summary_source_hash: str | None,
    content_hash: str | None,
    agenda_items_hash: str | None,
) -> bool:
    expected_source_hash = compute_summary_source_hash(
        doc_kind,
        content_hash=content_hash,
        agenda_items_hash=agenda_items_hash,
    )
    return bool(summary and expected_source_hash and summary_source_hash == expected_source_hash)


def is_summary_stale(
    doc_kind: str | None,
    *,
    summary: str | None,
    summary_source_hash: str | None,
    content_hash: str | None,
    agenda_items_hash: str | None,
) -> bool:
    return bool(
        summary
        and not is_summary_fresh(
            doc_kind,
            summary=summary,
            summary_source_hash=summary_source_hash,
            content_hash=content_hash,
            agenda_items_hash=agenda_items_hash,
        )
    )
