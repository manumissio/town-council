from __future__ import annotations

from pipeline.agenda_summary_contracts import (
    AGENDA_SUMMARY_BLOCKED_LOW_SIGNAL_REASON,
    AGENDA_SUMMARY_CATALOG_NOT_FOUND_ERROR,
    AGENDA_SUMMARY_DOCUMENT_NOT_FOUND_ERROR,
    AGENDA_SUMMARY_READY_STATUS,
    AGENDA_SUMMARY_SEGMENTATION_REQUIRED_REASON,
    AgendaSummaryPayload,
)
from pipeline.agenda_summary_items import should_drop_from_agenda_summary
from pipeline.agenda_text_heuristics import looks_like_agenda_segmentation_boilerplate
from pipeline.config import AGENDA_MIN_SUBSTANTIVE_DESC_CHARS
from pipeline.config import AGENDA_SUMMARY_MAX_INPUT_CHARS, AGENDA_SUMMARY_MIN_RESERVED_OUTPUT_CHARS
from pipeline.content_hash import compute_content_hash
from pipeline.models import AgendaItem, Catalog, Document
from pipeline.summary_freshness import compute_agenda_items_hash


def build_agenda_summary_input_bundle(
    *,
    catalog: Catalog | None,
    document: Document | None,
    agenda_items: list[AgendaItem],
    include_meeting_context: bool = False,
    max_input_chars: int = AGENDA_SUMMARY_MAX_INPUT_CHARS,
    min_reserved_output_chars: int = AGENDA_SUMMARY_MIN_RESERVED_OUTPUT_CHARS,
) -> AgendaSummaryPayload:
    if catalog is None:
        return {"status": "error", "error": AGENDA_SUMMARY_CATALOG_NOT_FOUND_ERROR}
    if document is None:
        return {"status": "error", "error": AGENDA_SUMMARY_DOCUMENT_NOT_FOUND_ERROR}
    if not agenda_items:
        return {
            "status": "not_generated_yet",
            "reason": AGENDA_SUMMARY_SEGMENTATION_REQUIRED_REASON,
            "summary": None,
        }

    summary_items, candidate_items_total, input_chars = _summary_items_within_budget(
        agenda_items,
        max_input_chars=max_input_chars,
        min_reserved_output_chars=min_reserved_output_chars,
    )
    if not summary_items:
        return {
            "status": "blocked_low_signal",
            "reason": AGENDA_SUMMARY_BLOCKED_LOW_SIGNAL_REASON,
            "summary": None,
        }

    return _agenda_summary_ready_payload(
        catalog=catalog,
        content_hash=compute_content_hash(catalog.content) if (catalog.content or "") else None,
        agenda_items_hash=compute_agenda_items_hash(agenda_items),
        summary_items=summary_items,
        truncation_meta={
            "items_total": candidate_items_total,
            "items_included": len(summary_items),
            "items_truncated": max(0, candidate_items_total - len(summary_items)),
            "input_chars": input_chars,
        },
        meeting_context=_meeting_context(document, include_meeting_context),
    )


def _summary_items_within_budget(
    agenda_items: list[AgendaItem],
    *,
    max_input_chars: int,
    min_reserved_output_chars: int,
) -> tuple[list[AgendaSummaryPayload], int, int]:
    summary_items: list[AgendaSummaryPayload] = []
    candidate_items_total = 0
    input_chars = 0
    summary_payload_budget = max(1000, int(max_input_chars) - int(min_reserved_output_chars))
    for agenda_item in agenda_items:
        summary_item = _agenda_summary_item_payload(agenda_item)
        if summary_item is None:
            continue
        candidate_items_total += 1
        item_block = _agenda_summary_item_block(summary_item)
        if (input_chars + len(item_block)) > summary_payload_budget:
            break
        summary_items.append(summary_item)
        input_chars += len(item_block)
    return summary_items, candidate_items_total, input_chars


def _agenda_summary_item_payload(item: AgendaItem) -> AgendaSummaryPayload | None:
    title = (item.title or "").strip()
    if not title or looks_like_agenda_segmentation_boilerplate(title):
        return None

    description = (item.description or "").strip()
    serialized = title if not description else f"{title} - {description}"
    if should_drop_from_agenda_summary(
        serialized,
        min_substantive_desc_chars=AGENDA_MIN_SUBSTANTIVE_DESC_CHARS,
    ):
        return None

    return {
        "title": title,
        "description": description,
        "classification": (item.classification or "").strip(),
        "result": (item.result or "").strip(),
        "page_number": int(item.page_number or 0),
    }


def _agenda_summary_item_block(summary_item: AgendaSummaryPayload) -> str:
    return (
        f"Title: {summary_item['title']}\n"
        f"Description: {summary_item['description']}\n"
        f"Classification: {summary_item['classification']}\n"
        f"Result: {summary_item['result']}\n"
        f"Page: {summary_item['page_number']}\n\n"
    )


def _meeting_context(document: Document, include_meeting_context: bool) -> dict[str, str]:
    if not include_meeting_context:
        return {"meeting_title": "", "meeting_date": ""}
    event = getattr(document, "event", None)
    return {
        "meeting_title": event.name if event and event.name else "",
        "meeting_date": str(event.record_date) if event and event.record_date else "",
    }


def _agenda_summary_ready_payload(
    *,
    catalog: Catalog,
    content_hash: str | None,
    agenda_items_hash: str | None,
    summary_items: list[AgendaSummaryPayload],
    truncation_meta: dict[str, int],
    meeting_context: dict[str, str],
) -> AgendaSummaryPayload:
    return {
        "status": AGENDA_SUMMARY_READY_STATUS,
        "catalog": catalog,
        "content_hash": content_hash,
        "agenda_items_hash": agenda_items_hash,
        "summary_items": summary_items,
        "truncation_meta": truncation_meta,
        "meeting_title": meeting_context["meeting_title"],
        "meeting_date": meeting_context["meeting_date"],
    }
