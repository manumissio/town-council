import csv
import io
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from api.app_setup import limiter
from api import search_support
from pipeline.lexicon import is_trend_noise_topic

TRENDS_TOPICS_RATE_LIMIT = "60/minute"
TRENDS_COMPARE_RATE_LIMIT = "30/minute"
TRENDS_EXPORT_RATE_LIMIT = "10/minute"
TRENDS_TOPICS_LIMIT_DEFAULT = 10
TRENDS_TOPICS_LIMIT_MAX = 50
TRENDS_COMPARE_LIMIT_DEFAULT = 5
TRENDS_COMPARE_LIMIT_MAX = 20
TRENDS_EXPORT_LIMIT_DEFAULT = 50
TRENDS_EXPORT_LIMIT_MAX = 500
TRENDS_FORMAT_DEFAULT = "json"
TRENDS_DATE_ORDER_DETAIL = "date_to must be >= date_from"
TRENDS_MINIMUM_CITIES_DETAIL = "Provide at least two cities"

router = APIRouter()


def _sorted_topic_rows(topic_counts: dict[str, int], limit: int) -> list[tuple[str, int]]:
    return sorted(
        [(topic, count) for topic, count in topic_counts.items() if not is_trend_noise_topic(topic)],
        key=lambda topic_count: (-int(topic_count[1]), str(topic_count[0]).lower()),
    )[:limit]


@router.get("/trends/topics")
@limiter.limit(TRENDS_TOPICS_RATE_LIMIT)
def get_trends_topics(
    request: Request,
    city: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(TRENDS_TOPICS_LIMIT_DEFAULT, ge=1, le=TRENDS_TOPICS_LIMIT_MAX),
) -> dict[str, Any]:
    _ = request
    search_support._require_trends_feature()
    if date_from:
        search_support.validate_date_format(date_from)
    if date_to:
        search_support.validate_date_format(date_to)
    if date_from or date_to:
        collect_meeting_docs = search_support.facade_callable("_collect_meeting_docs", search_support._collect_meeting_docs)
        docs = collect_meeting_docs(city=city)
        topic_counts = search_support._count_topics_from_docs(docs, date_from=date_from, date_to=date_to)
    else:
        topic_counts = search_support._facet_topics(city=city, date_from=date_from, date_to=date_to)
    rows = _sorted_topic_rows(topic_counts, limit)
    return {
        "city": search_support._normalize_city_or_400(city) if city else None,
        "date_from": date_from,
        "date_to": date_to,
        "items": [{"topic": topic, "count": int(count)} for topic, count in rows],
    }


@router.get("/trends/compare")
@limiter.limit(TRENDS_COMPARE_RATE_LIMIT)
def get_trends_compare(
    request: Request,
    cities: list[str] = Query(...),
    date_from: str = Query(...),
    date_to: str = Query(...),
    granularity: str = Query("month", pattern="^(month|quarter)$"),
    limit: int = Query(TRENDS_COMPARE_LIMIT_DEFAULT, ge=1, le=TRENDS_COMPARE_LIMIT_MAX),
) -> dict[str, Any]:
    _ = request
    search_support._require_trends_feature()
    search_support.validate_date_format(date_from)
    search_support.validate_date_format(date_to)
    start = datetime.strptime(date_from, "%Y-%m-%d").date()
    end = datetime.strptime(date_to, "%Y-%m-%d").date()
    if end < start:
        raise HTTPException(status_code=400, detail=TRENDS_DATE_ORDER_DETAIL)
    if len(cities) < 2:
        raise HTTPException(status_code=400, detail=TRENDS_MINIMUM_CITIES_DETAIL)

    normalized_cities = [search_support._normalize_city_or_400(city) for city in cities]
    buckets = search_support._iter_time_buckets(start=start, end=end, granularity=granularity)
    collect_meeting_docs = search_support.facade_callable("_collect_meeting_docs", search_support._collect_meeting_docs)
    docs_by_city = {city: collect_meeting_docs(city=city) for city in normalized_cities}

    pooled: dict[str, int] = {}
    for meeting_docs in docs_by_city.values():
        counts = search_support._count_topics_from_docs(meeting_docs, date_from=date_from, date_to=date_to)
        for topic, count in counts.items():
            pooled[topic] = pooled.get(topic, 0) + int(count)
    top_topics = [
        name
        for name, _ in sorted(pooled.items(), key=lambda topic_count: (-topic_count[1], topic_count[0].lower()))[:limit]
    ]

    series = []
    for city in normalized_cities:
        meeting_docs = docs_by_city.get(city, [])
        for bucket_start, bucket_end in buckets:
            counts = search_support._count_topics_from_docs(
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
@limiter.limit(TRENDS_EXPORT_RATE_LIMIT)
def export_trends(
    request: Request,
    city: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    format: str = Query(TRENDS_FORMAT_DEFAULT, pattern="^(json|csv)$"),
    limit: int = Query(TRENDS_EXPORT_LIMIT_DEFAULT, ge=1, le=TRENDS_EXPORT_LIMIT_MAX),
) -> Response | dict[str, Any]:
    _ = request
    search_support._require_trends_feature()
    if date_from:
        search_support.validate_date_format(date_from)
    if date_to:
        search_support.validate_date_format(date_to)
    if date_from or date_to:
        collect_meeting_docs = search_support.facade_callable("_collect_meeting_docs", search_support._collect_meeting_docs)
        docs = collect_meeting_docs(city=city)
        topic_counts = search_support._count_topics_from_docs(docs, date_from=date_from, date_to=date_to)
    else:
        topic_counts = search_support._facet_topics(city=city, date_from=date_from, date_to=date_to)
    rows = _sorted_topic_rows(topic_counts, limit)

    if format == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(search_support.TOPICS_CSV_HEADER)
        normalized_city = search_support._normalize_city_or_400(city) if city else ""
        for topic, count in rows:
            writer.writerow([topic, int(count), normalized_city, date_from or "", date_to or ""])
        return Response(content=buffer.getvalue(), media_type="text/csv")

    return {
        "city": search_support._normalize_city_or_400(city) if city else None,
        "date_from": date_from,
        "date_to": date_to,
        "items": [{"topic": topic, "count": int(count)} for topic, count in rows],
    }
