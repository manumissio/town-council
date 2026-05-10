from datetime import date, datetime, timedelta
from typing import Any, Optional

from fastapi import HTTPException

from api.search.filter_support import _build_meilisearch_filter_clauses
from api.search.support_core import (
    DOCUMENT_INDEX_NAME,
    FEATURE_TRENDS_DASHBOARD,
    MEETING_DOC_PAGE_SIZE,
    MEETING_DOC_SCAN_LIMIT,
    TOPICS_FACET_NAME,
    TRENDS_DASHBOARD_DISABLED_DETAIL,
    facade_callable,
    facade_value,
    search_client,
)
from pipeline.lexicon import is_trend_noise_topic


def _require_trends_feature() -> None:
    if not facade_value("FEATURE_TRENDS_DASHBOARD", FEATURE_TRENDS_DASHBOARD):
        raise HTTPException(status_code=503, detail=TRENDS_DASHBOARD_DISABLED_DETAIL)


def _bucket_start(value: date, granularity: str) -> date:
    if granularity == "quarter":
        q_month = ((value.month - 1) // 3) * 3 + 1
        return date(value.year, q_month, 1)
    return date(value.year, value.month, 1)


def _next_bucket_start(value: date, granularity: str) -> date:
    if granularity == "quarter":
        month = value.month + 3
    else:
        month = value.month + 1
    year = value.year
    while month > 12:
        month -= 12
        year += 1
    return date(year, month, 1)


def _iter_time_buckets(start: date, end: date, granularity: str) -> list[tuple[date, date]]:
    cursor = _bucket_start(start, granularity)
    buckets: list[tuple[date, date]] = []
    while cursor <= end:
        next_bucket = _next_bucket_start(cursor, granularity)
        bucket_end = min(end, next_bucket - timedelta(days=1))
        buckets.append((cursor, bucket_end))
        cursor = next_bucket
    return buckets


def _facet_topics(city: Optional[str], date_from: Optional[str], date_to: Optional[str]) -> dict[str, int]:
    index = search_client().index(DOCUMENT_INDEX_NAME)
    filter_builder = facade_callable("_build_meilisearch_filter_clauses", _build_meilisearch_filter_clauses)
    filters = filter_builder(
        city=city,
        meeting_type=None,
        org=None,
        date_from=date_from,
        date_to=date_to,
        include_agenda_items=False,
    )
    params: dict[str, Any] = {"limit": 0, "facets": [TOPICS_FACET_NAME]}
    if filters:
        params["filter"] = filters
    result = index.search("", params)
    return result.get("facetDistribution", {}).get(TOPICS_FACET_NAME, {}) or {}


def _parse_iso_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _collect_meeting_docs(city: Optional[str], scan_limit: int = MEETING_DOC_SCAN_LIMIT) -> list[dict[str, Any]]:
    index = search_client().index(DOCUMENT_INDEX_NAME)
    filter_builder = facade_callable("_build_meilisearch_filter_clauses", _build_meilisearch_filter_clauses)
    filters = filter_builder(
        city=city,
        meeting_type=None,
        org=None,
        date_from=None,
        date_to=None,
        include_agenda_items=False,
    )
    meeting_docs: list[dict[str, Any]] = []
    offset = 0
    while offset < scan_limit:
        params: dict[str, Any] = {
            "limit": min(MEETING_DOC_PAGE_SIZE, scan_limit - offset),
            "offset": offset,
            "attributesToRetrieve": [TOPICS_FACET_NAME, "date", "city"],
            "filter": filters,
        }
        if not filters:
            del params["filter"]
        page = index.search("", params)
        hits = page.get("hits", []) or []
        meeting_docs.extend(hits)
        if len(hits) < MEETING_DOC_PAGE_SIZE:
            break
        offset += len(hits)
    return meeting_docs


def _count_topics_from_docs(
    docs: list[dict[str, Any]],
    date_from: Optional[str],
    date_to: Optional[str],
) -> dict[str, int]:
    start = _parse_iso_date(date_from)
    end = _parse_iso_date(date_to)
    counts: dict[str, int] = {}
    for row in docs:
        row_date = _parse_iso_date(row.get("date"))
        if start and (row_date is None or row_date < start):
            continue
        if end and (row_date is None or row_date > end):
            continue
        topics = row.get(TOPICS_FACET_NAME) or []
        if isinstance(topics, list):
            for topic in topics:
                topic_name = str(topic).strip()
                if not topic_name:
                    continue
                if is_trend_noise_topic(topic_name):
                    continue
                counts[topic_name] = counts.get(topic_name, 0) + 1
    return counts
