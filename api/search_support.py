import logging
import os
import re
from datetime import date, datetime, timedelta
from typing import Any, Optional

import httpx
import meilisearch
from fastapi import HTTPException

from api.app_setup import SEMANTIC_SERVICE_URL
from api.search.query_builder import build_meili_filter_clauses, normalize_city_filter, normalize_filters
from pipeline import config as pipeline_config
from pipeline.lexicon import is_trend_noise_topic

MEILI_HOST = os.getenv("MEILI_HOST", "http://meilisearch:7700")
MEILI_MASTER_KEY = os.getenv("MEILI_MASTER_KEY", "masterKey")

DOCUMENT_INDEX_NAME = "documents"
TOPICS_FACET_NAME = "topics"

SEARCH_ENGINE_TIMEOUT_DETAIL = "Search engine timed out"
SEARCH_ENGINE_UNAVAILABLE_DETAIL = "Search engine unavailable"
INTERNAL_SEARCH_ENGINE_ERROR_DETAIL = "Internal search engine error"
SEMANTIC_DISABLED_DETAIL = "Semantic search is disabled. Set SEMANTIC_ENABLED=true and build artifacts."
TRENDS_DASHBOARD_DISABLED_DETAIL = "Trends dashboard is disabled"
INVALID_DATE_FORMAT_DETAIL = "Invalid date format. Use YYYY-MM-DD."
SEMANTIC_SERVICE_ERROR_DETAIL = "Semantic service error"

SEMANTIC_HEALTHCHECK_TIMEOUT_SECONDS = 5.0
SEMANTIC_SEARCH_TIMEOUT_SECONDS = 60.0
MEETING_DOC_SCAN_LIMIT = 2000
MEETING_DOC_PAGE_SIZE = 200

SEARCH_RESULT_ATTRIBUTES_TO_RETRIEVE = [
    "id",
    "title",
    "event_name",
    "city",
    "date",
    "filename",
    "url",
    "result_type",
    "event_id",
    "catalog_id",
    "classification",
    "result",
    "summary",
    "summary_extractive",
    "entities",
    "topics",
    "related_ids",
    "summary_is_stale",
    "topics_is_stale",
    "people_metadata",
]
SEARCH_RESULT_ATTRIBUTES_TO_CROP = ["content", "description"]
SEARCH_RESULT_ATTRIBUTES_TO_HIGHLIGHT = ["content", "title", "description"]
SEARCH_RESULT_CROP_LENGTH = 50
SEARCH_HIGHLIGHT_PRE_TAG = '<em class="bg-yellow-200 not-italic font-semibold px-0.5 rounded">'
SEARCH_HIGHLIGHT_POST_TAG = "</em>"
METADATA_FACETS = ["city", "organization", "meeting_category"]
TOPICS_CSV_HEADER = ["topic", "count", "city", "date_from", "date_to"]

logger = logging.getLogger("town-council-api")

# Search helpers read this through api.main at runtime so existing tests can patch
# the facade without knowing about the extracted modules.
client = meilisearch.Client(MEILI_HOST, MEILI_MASTER_KEY, timeout=5)


def _api_main() -> Any:
    from api import main as api_main

    return api_main


def facade_value(name: str, fallback: Any) -> Any:
    return getattr(_api_main(), name, fallback)


def facade_callable(name: str, fallback: Any) -> Any:
    return getattr(_api_main(), name, fallback)


def search_client() -> Any:
    return facade_value("client", client)


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


def _semantic_service_healthcheck() -> dict[str, Any]:
    try:
        response = httpx.get(f"{SEMANTIC_SERVICE_URL}/health", timeout=SEMANTIC_HEALTHCHECK_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeError(f"Semantic service unavailable: {exc}") from exc


def _semantic_service_get_json(path: str, params: dict[str, Any]) -> dict[str, Any]:
    try:
        response = httpx.get(f"{SEMANTIC_SERVICE_URL}{path}", params=params, timeout=SEMANTIC_SEARCH_TIMEOUT_SECONDS)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Semantic service unavailable: {exc}") from exc

    if response.status_code >= 400:
        try:
            payload = response.json()
            detail = payload.get("detail", payload) if isinstance(payload, dict) else payload
        except ValueError:
            detail = response.text or SEMANTIC_SERVICE_ERROR_DETAIL
        raise HTTPException(status_code=response.status_code, detail=detail)
    return response.json()
FEATURE_TRENDS_DASHBOARD = pipeline_config.FEATURE_TRENDS_DASHBOARD
SEMANTIC_ENABLED = pipeline_config.SEMANTIC_ENABLED
