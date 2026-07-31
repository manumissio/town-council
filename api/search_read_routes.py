from time import monotonic
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from meilisearch.errors import MeilisearchCommunicationError, MeilisearchError, MeilisearchTimeoutError

from api.search import support_core
from api.search_read_meilisearch import run_lexical_search
from api.search_read_params import SEARCH_LIMIT_DEFAULT, SEARCH_LIMIT_MAX, build_lexical_search_params, validate_search_date_range
from api.search_read_results import truncate_people_metadata
from api.search_semantic_routes import search_documents_semantic

SEARCH_METADATA_CACHE_SECONDS = 3600
EMPTY_SEARCH_METADATA = {"cities": [], "organizations": [], "meeting_types": []}

MetadataPayload = dict[str, list[str]]
MetadataCacheEntry = tuple[float, MetadataPayload]

_metadata_cache_entry: MetadataCacheEntry | None = None

router = APIRouter()


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
    limit: int = Query(SEARCH_LIMIT_DEFAULT, ge=1, le=SEARCH_LIMIT_MAX),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    validate_search_date_range(date_from, date_to)

    if semantic:
        return search_documents_semantic(
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
        index = support_core.client.index(support_core.DOCUMENT_INDEX_NAME)
        search_params = build_lexical_search_params(
            city=city,
            include_agenda_items=include_agenda_items,
            sort=sort,
            meeting_type=meeting_type,
            org=org,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )
        results = run_lexical_search(index, q, search_params)
        truncate_people_metadata(results)

        support_core.logger.info("Search query=%r city=%r returned %s hits", q, city, len(results["hits"]))
        return results
    except HTTPException:
        raise
    except (KeyError, RuntimeError, TypeError, ValueError) as exc:
        support_core.logger.error("Search failed: %s", exc)
        raise HTTPException(status_code=500, detail=support_core.INTERNAL_SEARCH_ENGINE_ERROR_DETAIL) from exc


@router.get("/metadata")
def get_metadata() -> MetadataPayload:
    global _metadata_cache_entry

    cache_entry = _metadata_cache_entry
    if cache_entry is not None and monotonic() < cache_entry[0]:
        return cache_entry[1]

    metadata_payload = _load_search_metadata()
    _metadata_cache_entry = (monotonic() + SEARCH_METADATA_CACHE_SECONDS, metadata_payload)
    return metadata_payload


def _load_search_metadata() -> MetadataPayload:
    try:
        index = support_core.client.index(support_core.DOCUMENT_INDEX_NAME)
        metadata_response = index.search("", {"facets": support_core.METADATA_FACETS, "limit": 0})

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
        support_core.logger.error("Metadata retrieval failed: %s", exc)
        return EMPTY_SEARCH_METADATA
