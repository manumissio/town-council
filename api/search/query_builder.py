from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


def sanitize_filter(val: str) -> str:
    return str(val).replace('"', '\\"')


def normalize_city_filter(val: str) -> str:
    raw = (val or "").strip()
    lowered = raw.lower()
    if re.search(r"[^a-z0-9_\-\s]", lowered):
        return lowered
    slug = re.sub(r"[\s\-]+", "_", lowered).strip("_")
    if re.match(r"^[a-z]{2}_.+", slug):
        return slug
    return f"ca_{slug}" if slug else lowered


@dataclass(frozen=True)
class NormalizedFilters:
    city: Optional[str]
    meeting_type: Optional[str]
    org: Optional[str]
    date_from: Optional[str]
    date_to: Optional[str]
    include_agenda_items: bool


def normalize_filters(
    city: Optional[str],
    meeting_type: Optional[str],
    org: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    include_agenda_items: bool,
) -> NormalizedFilters:
    normalized_city = normalize_city_filter(city) if city else None
    return NormalizedFilters(
        city=normalized_city,
        meeting_type=meeting_type,
        org=org,
        date_from=date_from,
        date_to=date_to,
        include_agenda_items=include_agenda_items,
    )


def build_meili_filter_clauses(filters: NormalizedFilters) -> list[str]:
    # Shared builder keeps search and trends semantics aligned.
    clauses: list[str] = []
    if not filters.include_agenda_items:
        clauses.append('result_type = "meeting"')
    if filters.city:
        clauses.append(f'city = "{sanitize_filter(filters.city)}"')
    if filters.meeting_type:
        clauses.append(f'meeting_category = "{sanitize_filter(filters.meeting_type)}"')
    if filters.org:
        clauses.append(f'organization = "{sanitize_filter(filters.org)}"')
    if filters.date_from and filters.date_to:
        clauses.append(
            f'date >= "{sanitize_filter(filters.date_from)}" AND date <= "{sanitize_filter(filters.date_to)}"'
        )
    elif filters.date_from:
        clauses.append(f'date >= "{sanitize_filter(filters.date_from)}"')
    elif filters.date_to:
        clauses.append(f'date <= "{sanitize_filter(filters.date_to)}"')
    return clauses

