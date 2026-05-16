from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from pipeline.agenda_summary_empty import (
    EMPTY_AGENDA_SEGMENTATION_STATUS,
    build_empty_agenda_summary_text,
)
from pipeline.models import Catalog

AGENDA_DOC_KIND = "agenda"
SUMMARY_CACHED_STATUS = "cached"
SUMMARY_COMPLETE_STATUS = "complete"
SUMMARY_STALE_STATUS = "stale"


class EmptyAgendaSummaryServices(Protocol):
    is_summary_fresh: Callable[..., bool]
    persist_agenda_summary: Callable[..., dict[str, object]]


@dataclass(frozen=True)
class EmptyAgendaGenerationContext:
    db: object
    catalog_id: int
    force: bool
    catalog: Catalog
    content_hash: str | None
    services: EmptyAgendaSummaryServices
    side_effects_runner: Callable[[int], dict[str, int]]


def run_empty_agenda_generation(context: EmptyAgendaGenerationContext) -> dict[str, object]:
    summary = build_empty_agenda_summary_text()
    is_fresh = context.services.is_summary_fresh(
        AGENDA_DOC_KIND,
        summary=context.catalog.summary,
        summary_source_hash=context.catalog.summary_source_hash,
        content_hash=context.content_hash,
        agenda_items_hash=None,
        agenda_segmentation_status=EMPTY_AGENDA_SEGMENTATION_STATUS,
    )
    if (not context.force) and is_fresh:
        return {"status": SUMMARY_CACHED_STATUS, "summary": context.catalog.summary, "changed": False}
    if (not context.force) and context.catalog.summary and not is_fresh:
        return {"status": SUMMARY_STALE_STATUS, "summary": context.catalog.summary, "changed": False}

    persisted_summary = context.services.persist_agenda_summary(
        catalog=context.catalog,
        summary=summary,
        content_hash=context.content_hash,
        agenda_items_hash=None,
        agenda_segmentation_status=EMPTY_AGENDA_SEGMENTATION_STATUS,
    )
    context.db.commit()
    side_effects = context.side_effects_runner(context.catalog_id)
    return {
        "status": SUMMARY_COMPLETE_STATUS,
        "summary": summary,
        "changed": bool(persisted_summary["changed"]),
        **side_effects,
    }
