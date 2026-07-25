from __future__ import annotations

from typing import Any

from pipeline import agenda_segmentation_maintenance as agenda_segmentation_maintenance_mod
from pipeline.agenda_resolver import has_viable_structured_agenda_source
from pipeline.db_session import db_session

provider_timeout_override = agenda_segmentation_maintenance_mod.provider_timeout_override
segment_timeout_override = agenda_segmentation_maintenance_mod.segment_timeout_override
summary_timeout_override = agenda_segmentation_maintenance_mod.summary_timeout_override
capture_agenda_fallback_events = agenda_segmentation_maintenance_mod.capture_agenda_fallback_events
looks_structured_enough_for_heuristic_segmentation = (
    agenda_segmentation_maintenance_mod.looks_structured_enough_for_heuristic_segmentation
)
HeuristicOnlyLocalAI = agenda_segmentation_maintenance_mod.HeuristicOnlyLocalAI
persist_segmented_agenda = agenda_segmentation_maintenance_mod.persist_segmented_agenda


def segment_catalog_with_mode(catalog_id: int, *, segment_mode: str = "normal") -> dict[str, Any]:
    return agenda_segmentation_maintenance_mod.segment_catalog_with_mode(
        catalog_id,
        segment_mode=segment_mode,
        session_factory=db_session,
        has_viable_structured_source=has_viable_structured_agenda_source,
    )
