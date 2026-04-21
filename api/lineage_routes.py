from typing import Any, Callable, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy.orm import Session as SQLAlchemySession

from pipeline.models import Catalog, Document, Event, Place

LINEAGE_RATE_LIMIT = "60/minute"
LINEAGE_NOT_FOUND_DETAIL = "Lineage not found"
CATALOG_NOT_FOUND_DETAIL = "Catalog not found"


def _lineage_rows(
    db: SQLAlchemySession,
    lineage_id: str,
    min_confidence: Optional[float] = None,
) -> list[Any]:
    query = (
        db.query(Catalog, Document, Event, Place)
        .join(Document, Document.catalog_id == Catalog.id)
        .join(Event, Event.id == Document.event_id)
        .join(Place, Place.id == Event.place_id)
        .filter(Catalog.lineage_id == lineage_id)
    )
    if min_confidence is not None:
        query = query.filter(Catalog.lineage_confidence >= float(min_confidence))
    return query.order_by(Event.record_date.desc(), Catalog.id.desc()).all()


def _lineage_meeting_summary(catalog: Catalog, event: Event, place: Place) -> dict[str, Any]:
    return {
        "catalog_id": catalog.id,
        "lineage_id": catalog.lineage_id,
        "lineage_confidence": float(catalog.lineage_confidence or 0.0),
        "lineage_updated_at": catalog.lineage_updated_at.isoformat() if catalog.lineage_updated_at else None,
        "event_name": event.name,
        "date": event.record_date.isoformat() if event.record_date else None,
        "city": place.display_name or place.name,
        "summary": catalog.summary,
    }


def _catalog_lineage_meeting_summary(catalog: Catalog, event: Event, place: Place) -> dict[str, Any]:
    return {
        "catalog_id": catalog.id,
        "lineage_confidence": float(catalog.lineage_confidence or 0.0),
        "date": event.record_date.isoformat() if event.record_date else None,
        "event_name": event.name,
        "city": place.display_name or place.name,
    }


def build_lineage_router(
    limiter: Any,
    get_db_dependency: Callable[..., Any],
    lineage_facade: Any,
) -> APIRouter:
    router = APIRouter()

    @router.get("/lineage/{lineage_id}")
    @limiter.limit(LINEAGE_RATE_LIMIT)
    def get_lineage(
        request: Request,
        lineage_id: str,
        min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
        db: SQLAlchemySession = Depends(get_db_dependency),
    ) -> dict[str, Any]:
        _ = request
        rows = lineage_facade._lineage_rows(db, lineage_id=lineage_id, min_confidence=min_confidence)
        if not rows:
            raise HTTPException(status_code=404, detail=LINEAGE_NOT_FOUND_DETAIL)
        meetings = [_lineage_meeting_summary(catalog, event, place) for catalog, _doc, event, place in rows]
        return {"lineage_id": lineage_id, "count": len(meetings), "meetings": meetings}

    @router.get("/catalog/{catalog_id}/lineage")
    @limiter.limit(LINEAGE_RATE_LIMIT)
    def get_catalog_lineage(
        request: Request,
        catalog_id: int = Path(..., ge=1),
        min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
        db: SQLAlchemySession = Depends(get_db_dependency),
    ) -> dict[str, Any]:
        _ = request
        catalog = db.get(Catalog, catalog_id)
        if not catalog:
            raise HTTPException(status_code=404, detail=CATALOG_NOT_FOUND_DETAIL)
        if not catalog.lineage_id:
            return {
                "catalog_id": catalog_id,
                "lineage_id": None,
                "count": 0,
                "meetings": [],
            }
        rows = lineage_facade._lineage_rows(db, lineage_id=catalog.lineage_id, min_confidence=min_confidence)
        meetings = [_catalog_lineage_meeting_summary(catalog_row, event, place) for catalog_row, _doc, event, place in rows]
        return {
            "catalog_id": catalog_id,
            "lineage_id": catalog.lineage_id,
            "lineage_confidence": float(catalog.lineage_confidence or 0.0),
            "count": len(meetings),
            "meetings": meetings,
        }

    return router
