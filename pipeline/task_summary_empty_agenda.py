from __future__ import annotations

from dataclasses import dataclass

from pipeline.agenda_summary_batch import persist_agenda_summary
from pipeline.agenda_summary_empty import (
    EMPTY_AGENDA_SEGMENTATION_STATUS,
    build_empty_agenda_summary_text,
)
from pipeline.models import Catalog
from pipeline.summary_freshness import is_summary_fresh
from pipeline.task_summary_side_effects import run_summary_generation_side_effects
from sqlalchemy.orm import Session

AGENDA_DOC_KIND = "agenda"
SUMMARY_CACHED_STATUS = "cached"
SUMMARY_COMPLETE_STATUS = "complete"
SUMMARY_STALE_STATUS = "stale"


@dataclass(frozen=True)
class EmptyAgendaGenerationContext:
    db: Session
    catalog_id: int
    force: bool
    catalog: Catalog
    content_hash: str | None


def run_empty_agenda_generation(context: EmptyAgendaGenerationContext) -> dict[str, object]:
    summary = build_empty_agenda_summary_text()
    summary_is_fresh = is_summary_fresh(
        AGENDA_DOC_KIND,
        summary=context.catalog.summary,
        summary_source_hash=context.catalog.summary_source_hash,
        content_hash=context.content_hash,
        agenda_items_hash=None,
        agenda_segmentation_status=EMPTY_AGENDA_SEGMENTATION_STATUS,
    )
    if (not context.force) and summary_is_fresh:
        return {"status": SUMMARY_CACHED_STATUS, "summary": context.catalog.summary, "changed": False}
    if (not context.force) and context.catalog.summary and not summary_is_fresh:
        return {"status": SUMMARY_STALE_STATUS, "summary": context.catalog.summary, "changed": False}

    persisted_summary = persist_agenda_summary(
        catalog=context.catalog,
        summary=summary,
        content_hash=context.content_hash,
        agenda_items_hash=None,
        agenda_segmentation_status=EMPTY_AGENDA_SEGMENTATION_STATUS,
    )
    context.db.commit()
    side_effects = run_summary_generation_side_effects(context.catalog_id)
    return {
        "status": SUMMARY_COMPLETE_STATUS,
        "summary": summary,
        "changed": bool(persisted_summary["changed"]),
        **side_effects,
    }
