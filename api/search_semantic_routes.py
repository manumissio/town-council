from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from api import search_support

SEMANTIC_SEARCH_LIMIT_DEFAULT = 20
SEMANTIC_SEARCH_LIMIT_MAX = 100

router = APIRouter()


@router.get("/search/semantic")
def search_documents_semantic(
    q: str = Query(..., min_length=1, description="The semantic search query (e.g., 'housing density')"),
    city: Optional[str] = Query(None),
    include_agenda_items: bool = Query(False, description="Include individual agenda items in search hits"),
    meeting_type: Optional[str] = Query(None),
    org: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(SEMANTIC_SEARCH_LIMIT_DEFAULT, ge=1, le=SEMANTIC_SEARCH_LIMIT_MAX),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    if not search_support.facade_value("SEMANTIC_ENABLED", search_support.SEMANTIC_ENABLED):
        raise HTTPException(status_code=503, detail=search_support.SEMANTIC_DISABLED_DETAIL)
    semantic_get_json = search_support.facade_callable(
        "_semantic_service_get_json",
        search_support._semantic_service_get_json,
    )
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
