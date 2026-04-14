import csv
import io
import logging
import os
import re
from datetime import date, datetime, timedelta
from typing import Any, Optional

import httpx
import meilisearch
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from meilisearch.errors import MeilisearchCommunicationError, MeilisearchError, MeilisearchTimeoutError

from api.app_setup import SEMANTIC_SERVICE_URL, limiter
from api.cache import cached
from api.search.query_builder import build_meili_filter_clauses, normalize_city_filter, normalize_filters
from pipeline.config import FEATURE_TRENDS_DASHBOARD, SEMANTIC_ENABLED
from pipeline.lexicon import is_trend_noise_topic

MEILI_HOST = os.getenv("MEILI_HOST", "http://meilisearch:7700")
MEILI_MASTER_KEY = os.getenv("MEILI_MASTER_KEY", "masterKey")
SEARCH_ENGINE_TIMEOUT_DETAIL = "Search engine timed out"
SEARCH_ENGINE_UNAVAILABLE_DETAIL = "Search engine unavailable"
INTERNAL_SEARCH_ENGINE_ERROR_DETAIL = "Internal search engine error"
SEMANTIC_DISABLED_DETAIL = "Semantic search is disabled. Set SEMANTIC_ENABLED=true and build artifacts."

router = APIRouter()
logger = logging.getLogger("town-council-api")

# Search routes read this through api.main at runtime so existing tests can patch
# the facade without knowing about this extracted module.
client = meilisearch.Client(MEILI_HOST, MEILI_MASTER_KEY, timeout=5)


def _api_main() -> Any:
    from api import main as api_main

    return api_main


def _facade_value(name: str, fallback: Any) -> Any:
    return getattr(_api_main(), name, fallback)


def _facade_callable(name: str, fallback: Any) -> Any:
    return getattr(_api_main(), name, fallback)


def _search_client() -> Any:
    return _facade_value("client", client)


def validate_date_format(date_str: str) -> None:
    """Ensures date is YYYY-MM-DD."""
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")


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
    # Single shared QueryBuilder contract keeps /search and /trends in sync.
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
    if not _facade_value("FEATURE_TRENDS_DASHBOARD", FEATURE_TRENDS_DASHBOARD):
        raise HTTPException(status_code=503, detail="Trends dashboard is disabled")


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
    index = _search_client().index("documents")
    filter_builder = _facade_callable("_build_meilisearch_filter_clauses", _build_meilisearch_filter_clauses)
    filters = filter_builder(
        city=city,
        meeting_type=None,
        org=None,
        date_from=date_from,
        date_to=date_to,
        include_agenda_items=False,
    )
    params: dict[str, Any] = {
        "limit": 0,
        "facets": ["topics"],
    }
    if filters:
        params["filter"] = filters
    result = index.search("", params)
    return result.get("facetDistribution", {}).get("topics", {}) or {}


def _parse_iso_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _collect_meeting_docs(city: Optional[str], scan_limit: int = 2000) -> list[dict[str, Any]]:
    index = _search_client().index("documents")
    filter_builder = _facade_callable("_build_meilisearch_filter_clauses", _build_meilisearch_filter_clauses)
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
    page_size = 200
    while offset < scan_limit:
        params: dict[str, Any] = {
            "limit": min(page_size, scan_limit - offset),
            "offset": offset,
            "attributesToRetrieve": ["topics", "date", "city"],
            "filter": filters,
        }
        if not filters:
            del params["filter"]
        page = index.search("", params)
        hits = page.get("hits", []) or []
        meeting_docs.extend(hits)
        if len(hits) < page_size:
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
        topics = row.get("topics") or []
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
        response = httpx.get(f"{SEMANTIC_SERVICE_URL}/health", timeout=5.0)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeError(f"Semantic service unavailable: {exc}") from exc


def _semantic_service_get_json(path: str, params: dict[str, Any]) -> dict[str, Any]:
    try:
        response = httpx.get(f"{SEMANTIC_SERVICE_URL}{path}", params=params, timeout=60.0)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"Semantic service unavailable: {exc}") from exc

    if response.status_code >= 400:
        try:
            payload = response.json()
            detail = payload.get("detail", payload) if isinstance(payload, dict) else payload
        except ValueError:
            detail = response.text or "Semantic service error"
        raise HTTPException(status_code=response.status_code, detail=detail)
    return response.json()


@router.get("/search")
def search_documents(
    q: str = Query(..., min_length=1, description="The search query (e.g., 'zoning')"),
    semantic: bool = Query(False, description="Enable semantic rerank (hybrid lexical + vector)"),
    city: Optional[str] = Query(None),
    include_agenda_items: bool = Query(False, description="Include individual agenda items in search hits"),
    sort: Optional[str] = Query(None, description="Sort mode: newest|oldest|relevance"),
    meeting_type: Optional[str] = Query(None),
    org: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    if date_from:
        validate_date_format(date_from)
    if date_to:
        validate_date_format(date_to)

    if semantic:
        semantic_search = _facade_callable("search_documents_semantic", search_documents_semantic)
        return semantic_search(
            q=q,
            city=city,
            include_agenda_items=include_agenda_items,
            meeting_type=meeting_type,
            org=org,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )

    try:
        index = _search_client().index("documents")
        search_params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "attributesToRetrieve": [
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
            ],
            "attributesToCrop": ["content", "description"],
            "cropLength": 50,
            "attributesToHighlight": ["content", "title", "description"],
            "highlightPreTag": '<em class="bg-yellow-200 not-italic font-semibold px-0.5 rounded">',
            "highlightPostTag": "</em>",
            "filter": [],
        }

        if sort is not None:
            sort_mode = (sort or "").strip().lower()
            if sort_mode in {"", "relevance"}:
                pass
            elif sort_mode == "newest":
                search_params["sort"] = ["date:desc"]
            elif sort_mode == "oldest":
                search_params["sort"] = ["date:asc"]
            else:
                raise HTTPException(status_code=400, detail="Invalid sort mode. Use newest|oldest|relevance.")

        filter_builder = _facade_callable("_build_meilisearch_filter_clauses", _build_meilisearch_filter_clauses)
        search_params["filter"] = filter_builder(
            city=city,
            meeting_type=meeting_type,
            org=org,
            date_from=date_from,
            date_to=date_to,
            include_agenda_items=include_agenda_items,
        )

        if not search_params["filter"]:
            del search_params["filter"]

        try:
            results = index.search(q, search_params)
        except MeilisearchTimeoutError as exc:
            logger.error("Search failed (Meilisearch timeout): %s", exc)
            raise HTTPException(status_code=503, detail=SEARCH_ENGINE_TIMEOUT_DETAIL) from exc
        except MeilisearchCommunicationError as exc:
            logger.error("Search failed (Meilisearch unavailable): %s", exc)
            raise HTTPException(status_code=503, detail=SEARCH_ENGINE_UNAVAILABLE_DETAIL) from exc
        except MeilisearchError as exc:
            message = str(exc)
            lowered = message.lower()
            if "sort" in lowered and ("sortable" in lowered or "attribute" in lowered):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Meilisearch is not configured to sort by `date`. "
                        "Run `docker compose run --rm pipeline python reindex_only.py` and retry."
                    ),
                ) from exc
            logger.error("Search failed (Meilisearch error): %s", exc)
            raise HTTPException(status_code=500, detail=INTERNAL_SEARCH_ENGINE_ERROR_DETAIL) from exc

        for hit in results["hits"]:
            if "people_metadata" in hit and isinstance(hit["people_metadata"], list):
                hit["people_metadata"] = hit["people_metadata"][:10]
            if (
                "_formatted" in hit
                and "people_metadata" in hit["_formatted"]
                and isinstance(hit["_formatted"]["people_metadata"], list)
            ):
                hit["_formatted"]["people_metadata"] = hit["_formatted"]["people_metadata"][:10]

        logger.info("Search query=%r city=%r returned %s hits", q, city, len(results["hits"]))
        return results
    except HTTPException:
        raise
    except (KeyError, RuntimeError, TypeError, ValueError) as exc:
        logger.error("Search failed: %s", exc)
        raise HTTPException(status_code=500, detail=INTERNAL_SEARCH_ENGINE_ERROR_DETAIL) from exc


@router.get("/search/semantic")
def search_documents_semantic(
    q: str = Query(..., min_length=1, description="The semantic search query (e.g., 'housing density')"),
    city: Optional[str] = Query(None),
    include_agenda_items: bool = Query(False, description="Include individual agenda items in search hits"),
    meeting_type: Optional[str] = Query(None),
    org: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    if not _facade_value("SEMANTIC_ENABLED", SEMANTIC_ENABLED):
        raise HTTPException(status_code=503, detail=SEMANTIC_DISABLED_DETAIL)
    semantic_get_json = _facade_callable("_semantic_service_get_json", _semantic_service_get_json)
    return semantic_get_json(
        "/search/semantic",
        {
            "q": q,
            "city": city,
            "include_agenda_items": include_agenda_items,
            "meeting_type": meeting_type,
            "org": org,
            "date_from": date_from,
            "date_to": date_to,
            "limit": limit,
            "offset": offset,
        },
    )


@router.get("/metadata")
@cached(expire=3600, key_prefix="metadata")
def get_metadata() -> dict[str, list[str]]:
    try:
        index = _search_client().index("documents")
        metadata_response = index.search(
            "",
            {
                "facets": ["city", "organization", "meeting_category"],
                "limit": 0,
            },
        )

        facets = metadata_response.get("facetDistribution", {})
        cities = sorted([city.replace("ca_", "").replace("_", " ").title() for city in facets.get("city", {}).keys()])
        orgs = sorted(list(facets.get("organization", {}).keys()))
        meeting_types = sorted(list(facets.get("meeting_category", {}).keys()))

        return {
            "cities": cities,
            "organizations": orgs,
            "meeting_types": meeting_types,
        }
    except (MeilisearchCommunicationError, MeilisearchTimeoutError, MeilisearchError, RuntimeError, ValueError) as exc:
        logger.error("Metadata retrieval failed: %s", exc)
        return {"cities": [], "organizations": [], "meeting_types": []}


@router.get("/trends/topics")
@limiter.limit("60/minute")
def get_trends_topics(
    request: Request,
    city: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
) -> dict[str, Any]:
    _ = request
    _require_trends_feature()
    if date_from:
        validate_date_format(date_from)
    if date_to:
        validate_date_format(date_to)
    if date_from or date_to:
        collect_meeting_docs = _facade_callable("_collect_meeting_docs", _collect_meeting_docs)
        docs = collect_meeting_docs(city=city)
        topic_counts = _count_topics_from_docs(docs, date_from=date_from, date_to=date_to)
    else:
        topic_counts = _facet_topics(city=city, date_from=date_from, date_to=date_to)
    rows = sorted(
        [(topic, count) for topic, count in topic_counts.items() if not is_trend_noise_topic(topic)],
        key=lambda topic_count: (-int(topic_count[1]), str(topic_count[0]).lower()),
    )[:limit]
    return {
        "city": _normalize_city_or_400(city) if city else None,
        "date_from": date_from,
        "date_to": date_to,
        "items": [{"topic": topic, "count": int(count)} for topic, count in rows],
    }


@router.get("/trends/compare")
@limiter.limit("30/minute")
def get_trends_compare(
    request: Request,
    cities: list[str] = Query(...),
    date_from: str = Query(...),
    date_to: str = Query(...),
    granularity: str = Query("month", pattern="^(month|quarter)$"),
    limit: int = Query(5, ge=1, le=20),
) -> dict[str, Any]:
    _ = request
    _require_trends_feature()
    validate_date_format(date_from)
    validate_date_format(date_to)
    start = datetime.strptime(date_from, "%Y-%m-%d").date()
    end = datetime.strptime(date_to, "%Y-%m-%d").date()
    if end < start:
        raise HTTPException(status_code=400, detail="date_to must be >= date_from")
    if len(cities) < 2:
        raise HTTPException(status_code=400, detail="Provide at least two cities")

    normalized_cities = [_normalize_city_or_400(city) for city in cities]
    buckets = _iter_time_buckets(start=start, end=end, granularity=granularity)
    collect_meeting_docs = _facade_callable("_collect_meeting_docs", _collect_meeting_docs)
    docs_by_city = {city: collect_meeting_docs(city=city) for city in normalized_cities}

    pooled: dict[str, int] = {}
    for meeting_docs in docs_by_city.values():
        counts = _count_topics_from_docs(meeting_docs, date_from=date_from, date_to=date_to)
        for topic, count in counts.items():
            pooled[topic] = pooled.get(topic, 0) + int(count)
    top_topics = [name for name, _ in sorted(pooled.items(), key=lambda topic_count: (-topic_count[1], topic_count[0].lower()))[:limit]]

    series = []
    for city in normalized_cities:
        meeting_docs = docs_by_city.get(city, [])
        for bucket_start, bucket_end in buckets:
            counts = _count_topics_from_docs(
                meeting_docs,
                date_from=bucket_start.isoformat(),
                date_to=bucket_end.isoformat(),
            )
            series.append(
                {
                    "city": city,
                    "bucket": bucket_start.isoformat(),
                    "topics": {topic: int(counts.get(topic, 0)) for topic in top_topics},
                }
            )
    return {
        "granularity": granularity,
        "date_from": date_from,
        "date_to": date_to,
        "topics": top_topics,
        "series": series,
    }


@router.get("/trends/export", response_model=None)
@limiter.limit("10/minute")
def export_trends(
    request: Request,
    city: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    format: str = Query("json", pattern="^(json|csv)$"),
    limit: int = Query(50, ge=1, le=500),
) -> Response | dict[str, Any]:
    _ = request
    _require_trends_feature()
    if date_from:
        validate_date_format(date_from)
    if date_to:
        validate_date_format(date_to)
    if date_from or date_to:
        collect_meeting_docs = _facade_callable("_collect_meeting_docs", _collect_meeting_docs)
        docs = collect_meeting_docs(city=city)
        topic_counts = _count_topics_from_docs(docs, date_from=date_from, date_to=date_to)
    else:
        topic_counts = _facet_topics(city=city, date_from=date_from, date_to=date_to)
    rows = sorted(
        [(topic, count) for topic, count in topic_counts.items() if not is_trend_noise_topic(topic)],
        key=lambda topic_count: (-int(topic_count[1]), str(topic_count[0]).lower()),
    )[:limit]

    if format == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["topic", "count", "city", "date_from", "date_to"])
        normalized_city = _normalize_city_or_400(city) if city else ""
        for topic, count in rows:
            writer.writerow([topic, int(count), normalized_city, date_from or "", date_to or ""])
        return Response(content=buffer.getvalue(), media_type="text/csv")

    return {
        "city": _normalize_city_or_400(city) if city else None,
        "date_from": date_from,
        "date_to": date_to,
        "items": [{"topic": topic, "count": int(count)} for topic, count in rows],
    }
