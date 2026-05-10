import re
from typing import Any, Optional

from fastapi import HTTPException

from api.search.query_builder import build_meili_filter_clauses, normalize_city_filter, normalize_filters
from api.search.support_core import INVALID_DATE_FORMAT_DETAIL


def validate_date_format(date_str: str) -> None:
    """Ensures date is YYYY-MM-DD before forwarding it downstream."""
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        raise HTTPException(status_code=400, detail=INVALID_DATE_FORMAT_DETAIL)


def _normalize_filters_or_400(
    city: Optional[str],
    meeting_type: Optional[str],
    org: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    include_agenda_items: bool,
) -> Any:
    try:
        return normalize_filters(
            city=city,
            meeting_type=meeting_type,
            org=org,
            date_from=date_from,
            date_to=date_to,
            include_agenda_items=include_agenda_items,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _normalize_city_or_400(city: str) -> str:
    try:
        return normalize_city_filter(city)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _build_filter_values(
    city: Optional[str],
    meeting_type: Optional[str],
    org: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    include_agenda_items: bool,
) -> dict[str, Any]:
    filters = _normalize_filters_or_400(
        city=city,
        meeting_type=meeting_type,
        org=org,
        date_from=date_from,
        date_to=date_to,
        include_agenda_items=include_agenda_items,
    )
    return {
        "city": filters.city,
        "meeting_type": filters.meeting_type,
        "org": filters.org,
        "date_from": filters.date_from,
        "date_to": filters.date_to,
        "include_agenda_items": filters.include_agenda_items,
    }


def _build_meilisearch_filter_clauses(
    city: Optional[str],
    meeting_type: Optional[str],
    org: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    include_agenda_items: bool,
) -> list[str]:
    # One shared QueryBuilder contract keeps /search and /trends in sync.
    return build_meili_filter_clauses(
        _normalize_filters_or_400(
            city=city,
            meeting_type=meeting_type,
            org=org,
            date_from=date_from,
            date_to=date_to,
            include_agenda_items=include_agenda_items,
        )
    )
