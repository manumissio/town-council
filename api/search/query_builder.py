from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional


def sanitize_filter(val: str) -> str:
    return str(val).replace('"', '\\"')


def _collapse_spaces(val: str) -> str:
    return re.sub(r"\s+", " ", str(val or "")).strip()


def normalize_city_filter(val: str) -> str:
    raw = _collapse_spaces(val)
    if not raw:
        raise ValueError("City filter cannot be empty")

    normalized = unicodedata.normalize("NFKD", raw)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_only.lower()
    if re.search(r"[^a-z0-9_\-\s]", lowered):
        raise ValueError("City filter contains unsupported characters")
    slug = re.sub(r"[\s\-]+", "_", lowered).strip("_")
    slug = re.sub(r"_+", "_", slug).strip("_")
    if not slug:
        raise ValueError("City filter must contain letters or numbers")
    if re.match(r"^[a-z]{2}_.+", slug):
        return slug
    return f"ca_{slug}"


def normalize_meeting_type_filter(val: Optional[str]) -> Optional[str]:
    if val is None:
        return None
    normalized = _collapse_spaces(val)
    return normalized or None


def normalize_org_filter(val: Optional[str]) -> Optional[str]:
    if val is None:
        return None
    normalized = _collapse_spaces(val)
    return normalized or None


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
        meeting_type=normalize_meeting_type_filter(meeting_type),
        org=normalize_org_filter(org),
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
