from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from meilisearch.errors import MeilisearchCommunicationError, MeilisearchError, MeilisearchTimeoutError

from api.cache import cached
from api import search_support
from api.search_read_meilisearch import run_lexical_search
from api.search_read_params import SEARCH_LIMIT_DEFAULT, SEARCH_LIMIT_MAX, build_lexical_search_params, validate_search_date_range
from api.search_read_results import truncate_people_metadata
from api.search_semantic_routes import search_documents_semantic

SEARCH_METADATA_CACHE_SECONDS = 3600
SEARCH_METADATA_CACHE_KEY = "metadata"

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
        semantic_search = search_support.facade_callable("search_documents_semantic", search_documents_semantic)
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
        index = search_support.search_client().index(search_support.DOCUMENT_INDEX_NAME)
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

        search_support.logger.info("Search query=%r city=%r returned %s hits", q, city, len(results["hits"]))
        return results
    except HTTPException:
        raise
    except (KeyError, RuntimeError, TypeError, ValueError) as exc:
        search_support.logger.error("Search failed: %s", exc)
        raise HTTPException(status_code=500, detail=search_support.INTERNAL_SEARCH_ENGINE_ERROR_DETAIL) from exc


@router.get("/metadata")
@cached(expire=SEARCH_METADATA_CACHE_SECONDS, key_prefix=SEARCH_METADATA_CACHE_KEY)
def get_metadata() -> dict[str, list[str]]:
    try:
        index = search_support.search_client().index(search_support.DOCUMENT_INDEX_NAME)
        metadata_response = index.search("", {"facets": search_support.METADATA_FACETS, "limit": 0})

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
        search_support.logger.error("Metadata retrieval failed: %s", exc)
        return {"cities": [], "organizations": [], "meeting_types": []}
