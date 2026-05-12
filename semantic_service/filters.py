from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException

from api.search.query_builder import build_meili_filter_clauses, normalize_filters


def validate_date_format(date_str: str) -> None:
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")


def build_filter_values(
    city: str | None,
    meeting_type: str | None,
    org: str | None,
    date_from: str | None,
    date_to: str | None,
    include_agenda_items: bool,
) -> dict[str, Any]:
    try:
        filters = normalize_filters(
            city=city,
            meeting_type=meeting_type,
            org=org,
            date_from=date_from,
            date_to=date_to,
            include_agenda_items=include_agenda_items,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "city": filters.city,
        "meeting_type": filters.meeting_type,
        "org": filters.org,
        "date_from": filters.date_from,
        "date_to": filters.date_to,
        "include_agenda_items": filters.include_agenda_items,
    }


def build_meilisearch_filter_clauses(
    city: str | None,
    meeting_type: str | None,
    org: str | None,
    date_from: str | None,
    date_to: str | None,
    include_agenda_items: bool,
) -> list[str]:
    try:
        return build_meili_filter_clauses(
            normalize_filters(
                city=city,
                meeting_type=meeting_type,
                org=org,
                date_from=date_from,
                date_to=date_to,
                include_agenda_items=include_agenda_items,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
