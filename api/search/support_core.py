import logging
from typing import Any

import meilisearch

from pipeline import config as pipeline_config
from pipeline.config_env import env_lower, env_raw
from pipeline.meilisearch_credentials import DEVELOPMENT_APP_ENV, resolve_meilisearch_reader_key

MEILI_HOST = env_raw("MEILI_HOST", "http://meilisearch:7700")
APP_ENV = env_lower("APP_ENV", DEVELOPMENT_APP_ENV)
MEILI_SEARCH_KEY = env_raw("MEILI_SEARCH_KEY", "")
# G3 defers facade removal; the legacy export now carries reader privilege only.
MEILI_MASTER_KEY = resolve_meilisearch_reader_key(
    APP_ENV,
    MEILI_SEARCH_KEY,
)

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

FEATURE_TRENDS_DASHBOARD = pipeline_config.FEATURE_TRENDS_DASHBOARD
SEMANTIC_ENABLED = pipeline_config.SEMANTIC_ENABLED

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
