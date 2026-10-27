from __future__ import annotations

from fastapi import HTTPException
from meilisearch.errors import MeilisearchApiError, MeilisearchCommunicationError, MeilisearchError, MeilisearchTimeoutError

from api.search import support_core

SORTABLE_DATE_REINDEX_DETAIL = (
    "Meilisearch is not configured to sort by `date`. "
    "Run `docker compose run --rm pipeline python reindex_only.py` and retry."
)
INDEX_NOT_FOUND_CODE = "index_not_found"


def run_lexical_search(index: object, query: str, search_params: dict[str, object]) -> dict[str, object]:
    try:
        return index.search(query, search_params)
    except MeilisearchTimeoutError as exc:
        support_core.logger.error("Search failed (Meilisearch timeout): %s", exc)
        raise HTTPException(status_code=503, detail=support_core.SEARCH_ENGINE_TIMEOUT_DETAIL) from exc
    except MeilisearchCommunicationError as exc:
        support_core.logger.error("Search failed (Meilisearch unavailable): %s", exc)
        raise HTTPException(status_code=503, detail=support_core.SEARCH_ENGINE_UNAVAILABLE_DETAIL) from exc
    except MeilisearchError as exc:
        if isinstance(exc, MeilisearchApiError) and exc.code == INDEX_NOT_FOUND_CODE:
            # A fresh installation has no searchable records until indexing creates this index.
            return {"hits": [], "estimatedTotalHits": 0}
        raise map_meilisearch_error(exc) from exc


def map_meilisearch_error(exc: MeilisearchError) -> HTTPException:
    message = str(exc)
    lowered = message.lower()
    if "sort" in lowered and ("sortable" in lowered or "attribute" in lowered):
        return HTTPException(status_code=400, detail=SORTABLE_DATE_REINDEX_DETAIL)
    support_core.logger.error("Search failed (Meilisearch error): %s", exc)
    return HTTPException(status_code=500, detail=support_core.INTERNAL_SEARCH_ENGINE_ERROR_DETAIL)
