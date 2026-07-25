from __future__ import annotations

from typing import Any

from pipeline.task_summary_generation_contracts import SummaryTaskContext
from pipeline.task_summary_generation_flow import (
    _cached_summary_payload,
    _load_summary_record,
    _prepare_summary_input,
)
from pipeline.task_summary_generation_persistence import generate_and_persist_summary
from sqlalchemy.orm import Session


def generate_catalog_summary(
    db: Session,
    catalog_id: int,
    *,
    force: bool,
) -> dict[str, Any]:
    context = SummaryTaskContext(db, catalog_id, force)
    record = _load_summary_record(context)
    if isinstance(record, dict):
        return record

    prepared = _prepare_summary_input(context, record)
    if isinstance(prepared, dict):
        return prepared

    cached_payload = _cached_summary_payload(context, record, prepared)
    if cached_payload is not None:
        return cached_payload

    return generate_and_persist_summary(context, record, prepared)
