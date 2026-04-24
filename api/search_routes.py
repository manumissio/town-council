from fastapi import APIRouter

from api import search_support
from api.search.query_builder import normalize_city_filter
from api.search_read_routes import get_metadata, router as search_read_router, search_documents
from api.search_semantic_routes import router as search_semantic_router, search_documents_semantic
from api.trends_routes import export_trends, get_trends_compare, get_trends_topics, router as trends_router

MEILI_HOST = search_support.MEILI_HOST
MEILI_MASTER_KEY = search_support.MEILI_MASTER_KEY

client = search_support.client
httpx = search_support.httpx

_build_filter_values = search_support._build_filter_values
_build_meilisearch_filter_clauses = search_support._build_meilisearch_filter_clauses
_collect_meeting_docs = search_support._collect_meeting_docs
_count_topics_from_docs = search_support._count_topics_from_docs
_facet_topics = search_support._facet_topics
_iter_time_buckets = search_support._iter_time_buckets
_normalize_city_or_400 = search_support._normalize_city_or_400
_normalize_filters_or_400 = search_support._normalize_filters_or_400
_parse_iso_date = search_support._parse_iso_date
_require_trends_feature = search_support._require_trends_feature
_semantic_service_get_json = search_support._semantic_service_get_json
_semantic_service_healthcheck = search_support._semantic_service_healthcheck
validate_date_format = search_support.validate_date_format

router = APIRouter()
router.include_router(search_read_router)
router.include_router(search_semantic_router)
router.include_router(trends_router)

__all__ = [
    "MEILI_HOST",
    "MEILI_MASTER_KEY",
    "client",
    "httpx",
    "normalize_city_filter",
    "validate_date_format",
    "_build_filter_values",
    "_build_meilisearch_filter_clauses",
    "_collect_meeting_docs",
    "_count_topics_from_docs",
    "_facet_topics",
    "_iter_time_buckets",
    "_normalize_city_or_400",
    "_normalize_filters_or_400",
    "_parse_iso_date",
    "_require_trends_feature",
    "_semantic_service_get_json",
    "_semantic_service_healthcheck",
    "search_documents",
    "search_documents_semantic",
    "get_metadata",
    "get_trends_topics",
    "get_trends_compare",
    "export_trends",
    "router",
]
