from __future__ import annotations

from fastapi import HTTPException

from api import search_support

SEARCH_LIMIT_DEFAULT = 20
SEARCH_LIMIT_MAX = 100
SORT_MODE_RELEVANCE = "relevance"
SORT_MODE_NEWEST = "newest"
SORT_MODE_OLDEST = "oldest"
INVALID_SORT_MODE_DETAIL = "Invalid sort mode. Use newest|oldest|relevance."


def validate_search_date_range(date_from: str | None, date_to: str | None) -> None:
    if date_from:
        search_support.validate_date_format(date_from)
    if date_to:
        search_support.validate_date_format(date_to)


def build_lexical_search_params(
    *,
    city: str | None,
    include_agenda_items: bool,
    sort: str | None,
    meeting_type: str | None,
    org: str | None,
    date_from: str | None,
    date_to: str | None,
    limit: int,
    offset: int,
) -> dict[str, object]:
    search_params: dict[str, object] = {
        "limit": limit,
        "offset": offset,
        "attributesToRetrieve": search_support.SEARCH_RESULT_ATTRIBUTES_TO_RETRIEVE,
        "attributesToCrop": search_support.SEARCH_RESULT_ATTRIBUTES_TO_CROP,
        "cropLength": search_support.SEARCH_RESULT_CROP_LENGTH,
        "attributesToHighlight": search_support.SEARCH_RESULT_ATTRIBUTES_TO_HIGHLIGHT,
        "highlightPreTag": search_support.SEARCH_HIGHLIGHT_PRE_TAG,
        "highlightPostTag": search_support.SEARCH_HIGHLIGHT_POST_TAG,
    }
    apply_sort(search_params, sort)
    apply_filters(
        search_params,
        city=city,
        meeting_type=meeting_type,
        org=org,
        date_from=date_from,
        date_to=date_to,
        include_agenda_items=include_agenda_items,
    )
    return search_params


def apply_sort(search_params: dict[str, object], sort: str | None) -> None:
    if sort is None:
        return
    sort_mode = (sort or "").strip().lower()
    if sort_mode in {"", SORT_MODE_RELEVANCE}:
        return
    if sort_mode == SORT_MODE_NEWEST:
        search_params["sort"] = ["date:desc"]
        return
    if sort_mode == SORT_MODE_OLDEST:
        search_params["sort"] = ["date:asc"]
        return
    raise HTTPException(status_code=400, detail=INVALID_SORT_MODE_DETAIL)


def apply_filters(
    search_params: dict[str, object],
    *,
    city: str | None,
    meeting_type: str | None,
    org: str | None,
    date_from: str | None,
    date_to: str | None,
    include_agenda_items: bool,
) -> None:
    filter_builder = search_support.facade_callable(
        "_build_meilisearch_filter_clauses",
        search_support._build_meilisearch_filter_clauses,
    )
    filter_clauses = filter_builder(
        city=city,
        meeting_type=meeting_type,
        org=org,
        date_from=date_from,
        date_to=date_to,
        include_agenda_items=include_agenda_items,
    )
    if filter_clauses:
        search_params["filter"] = filter_clauses
