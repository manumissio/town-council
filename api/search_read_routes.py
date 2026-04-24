from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from meilisearch.errors import MeilisearchCommunicationError, MeilisearchError, MeilisearchTimeoutError

from api.cache import cached
from api import search_support
from api.search_semantic_routes import search_documents_semantic

SEARCH_LIMIT_DEFAULT = 20
SEARCH_LIMIT_MAX = 100
SEARCH_METADATA_CACHE_SECONDS = 3600
SEARCH_METADATA_CACHE_KEY = "metadata"
SORT_MODE_RELEVANCE = "relevance"
SORT_MODE_NEWEST = "newest"
SORT_MODE_OLDEST = "oldest"
INVALID_SORT_MODE_DETAIL = "Invalid sort mode. Use newest|oldest|relevance."
SORTABLE_DATE_REINDEX_DETAIL = (
    "Meilisearch is not configured to sort by `date`. "
    "Run `docker compose run --rm pipeline python reindex_only.py` and retry."
)
PEOPLE_METADATA_MAX_ITEMS = 10

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
    if date_from:
        search_support.validate_date_format(date_from)
    if date_to:
        search_support.validate_date_format(date_to)

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
        search_params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "attributesToRetrieve": search_support.SEARCH_RESULT_ATTRIBUTES_TO_RETRIEVE,
            "attributesToCrop": search_support.SEARCH_RESULT_ATTRIBUTES_TO_CROP,
            "cropLength": search_support.SEARCH_RESULT_CROP_LENGTH,
            "attributesToHighlight": search_support.SEARCH_RESULT_ATTRIBUTES_TO_HIGHLIGHT,
            "highlightPreTag": search_support.SEARCH_HIGHLIGHT_PRE_TAG,
            "highlightPostTag": search_support.SEARCH_HIGHLIGHT_POST_TAG,
            "filter": [],
        }

        if sort is not None:
            sort_mode = (sort or "").strip().lower()
            if sort_mode in {"", SORT_MODE_RELEVANCE}:
                pass
            elif sort_mode == SORT_MODE_NEWEST:
                search_params["sort"] = ["date:desc"]
            elif sort_mode == SORT_MODE_OLDEST:
                search_params["sort"] = ["date:asc"]
            else:
                raise HTTPException(status_code=400, detail=INVALID_SORT_MODE_DETAIL)

        filter_builder = search_support.facade_callable(
            "_build_meilisearch_filter_clauses",
            search_support._build_meilisearch_filter_clauses,
        )
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
            search_support.logger.error("Search failed (Meilisearch timeout): %s", exc)
            raise HTTPException(status_code=503, detail=search_support.SEARCH_ENGINE_TIMEOUT_DETAIL) from exc
        except MeilisearchCommunicationError as exc:
            search_support.logger.error("Search failed (Meilisearch unavailable): %s", exc)
            raise HTTPException(status_code=503, detail=search_support.SEARCH_ENGINE_UNAVAILABLE_DETAIL) from exc
        except MeilisearchError as exc:
            message = str(exc)
            lowered = message.lower()
            if "sort" in lowered and ("sortable" in lowered or "attribute" in lowered):
                raise HTTPException(status_code=400, detail=SORTABLE_DATE_REINDEX_DETAIL) from exc
            search_support.logger.error("Search failed (Meilisearch error): %s", exc)
            raise HTTPException(status_code=500, detail=search_support.INTERNAL_SEARCH_ENGINE_ERROR_DETAIL) from exc

        for hit in results["hits"]:
            if "people_metadata" in hit and isinstance(hit["people_metadata"], list):
                hit["people_metadata"] = hit["people_metadata"][:PEOPLE_METADATA_MAX_ITEMS]
            if (
                "_formatted" in hit
                and "people_metadata" in hit["_formatted"]
                and isinstance(hit["_formatted"]["people_metadata"], list)
            ):
                hit["_formatted"]["people_metadata"] = hit["_formatted"]["people_metadata"][:PEOPLE_METADATA_MAX_ITEMS]

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
