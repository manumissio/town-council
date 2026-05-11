from __future__ import annotations

from fastapi import HTTPException
from meilisearch.errors import MeilisearchCommunicationError, MeilisearchError, MeilisearchTimeoutError

from api import search_support

SORTABLE_DATE_REINDEX_DETAIL = (
    "Meilisearch is not configured to sort by `date`. "
    "Run `docker compose run --rm pipeline python reindex_only.py` and retry."
)


def run_lexical_search(index: object, query: str, search_params: dict[str, object]) -> dict[str, object]:
    try:
        return index.search(query, search_params)
    except MeilisearchTimeoutError as exc:
        search_support.logger.error("Search failed (Meilisearch timeout): %s", exc)
        raise HTTPException(status_code=503, detail=search_support.SEARCH_ENGINE_TIMEOUT_DETAIL) from exc
    except MeilisearchCommunicationError as exc:
        search_support.logger.error("Search failed (Meilisearch unavailable): %s", exc)
        raise HTTPException(status_code=503, detail=search_support.SEARCH_ENGINE_UNAVAILABLE_DETAIL) from exc
    except MeilisearchError as exc:
        raise map_meilisearch_error(exc) from exc


def map_meilisearch_error(exc: MeilisearchError) -> HTTPException:
    message = str(exc)
    lowered = message.lower()
    if "sort" in lowered and ("sortable" in lowered or "attribute" in lowered):
        return HTTPException(status_code=400, detail=SORTABLE_DATE_REINDEX_DETAIL)
    search_support.logger.error("Search failed (Meilisearch error): %s", exc)
    return HTTPException(status_code=500, detail=search_support.INTERNAL_SEARCH_ENGINE_ERROR_DETAIL)
