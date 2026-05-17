from __future__ import annotations

from pipeline.models import AgendaItem, Catalog

EMPTY_AGENDA_SEGMENTATION_STATUS = "empty"
EMPTY_AGENDA_COMPLETION_MODE = "agenda_empty_deterministic"
EMPTY_AGENDA_SUMMARY_TEXT = (
    "Agenda segmentation completed, but no substantive agenda items were detected in the extracted text."
)


def is_empty_agenda_without_items(catalog: Catalog, agenda_items: list[AgendaItem]) -> bool:
    return (
        getattr(catalog, "agenda_segmentation_status", None) == EMPTY_AGENDA_SEGMENTATION_STATUS
        and not agenda_items
    )


def build_empty_agenda_summary_text() -> str:
    return EMPTY_AGENDA_SUMMARY_TEXT
