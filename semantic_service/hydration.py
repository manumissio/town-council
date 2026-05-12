from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from sqlalchemy.orm import Session as SQLAlchemySession

from pipeline.models import AgendaItem, Catalog, Document, Event, Organization, Place
from semantic_service.retrieval import SemanticRetrievalResult


class SemanticCandidateLike(Protocol):
    score: float
    metadata: dict[str, Any]


HydrateCandidates = Callable[[SQLAlchemySession, list[SemanticCandidateLike]], list[dict[str, Any]]]


@dataclass(frozen=True)
class SemanticResponseTiming:
    started_at: float
    engine: str | None
    clock: Callable[[], float] = time.perf_counter


def hydrate_meeting_hits(db: SQLAlchemySession, candidates: list[SemanticCandidateLike]) -> list[dict[str, Any]]:
    doc_ids = _positive_candidate_db_ids(candidates)
    if not doc_ids:
        return []
    by_doc_id = _meeting_hits_by_doc_id(db, doc_ids)
    return _hydrate_candidates(candidates, by_doc_id)


def hydrate_agenda_hits(db: SQLAlchemySession, candidates: list[SemanticCandidateLike]) -> list[dict[str, Any]]:
    item_ids = _positive_candidate_db_ids(candidates)
    if not item_ids:
        return []
    by_item_id = _agenda_hits_by_item_id(db, item_ids)
    return _hydrate_candidates(candidates, by_item_id)


def build_semantic_search_response(
    *,
    db: SQLAlchemySession,
    retrieval_result: SemanticRetrievalResult,
    limit: int,
    offset: int,
    timing: SemanticResponseTiming,
    hydrate_meetings: HydrateCandidates,
    hydrate_agenda_items: HydrateCandidates,
) -> dict[str, Any]:
    deduped = retrieval_result.deduped
    page_candidates = deduped[offset : offset + limit]
    meeting_candidates = _candidates_by_type(page_candidates, result_type="meeting")
    agenda_candidates = _candidates_by_type(page_candidates, result_type="agenda_item")
    meeting_hits = hydrate_meetings(db, meeting_candidates)
    agenda_hits = hydrate_agenda_items(db, agenda_candidates)
    hits = _ordered_hydrated_hits(page_candidates, meeting_hits, agenda_hits)
    elapsed_ms = round((timing.clock() - timing.started_at) * 1000.0, 2)
    return {
        "hits": hits,
        "estimatedTotalHits": len(deduped),
        "limit": limit,
        "offset": offset,
        "semantic_diagnostics": {
            "raw_candidates": retrieval_result.raw_count,
            "filtered_candidates": retrieval_result.filtered_count,
            "dedup_candidates": len(deduped),
            "k_used": retrieval_result.k_used,
            "expansion_steps": retrieval_result.expansion_steps,
            "latency_ms": elapsed_ms,
            "engine": timing.engine,
            **retrieval_result.diagnostics_extra,
        },
    }


def _positive_candidate_db_ids(candidates: list[SemanticCandidateLike]) -> list[int]:
    return [int(candidate.metadata.get("db_id") or 0) for candidate in candidates if int(candidate.metadata.get("db_id") or 0) > 0]


def _meeting_hits_by_doc_id(db: SQLAlchemySession, doc_ids: list[int]) -> dict[int, dict[str, Any]]:
    rows = (
        db.query(Document, Catalog, Event, Place, Organization)
        .join(Catalog, Document.catalog_id == Catalog.id)
        .join(Event, Document.event_id == Event.id)
        .join(Place, Document.place_id == Place.id)
        .outerjoin(Organization, Event.organization_id == Organization.id)
        .filter(Document.id.in_(doc_ids))
        .all()
    )
    return {_doc_id(doc): _meeting_hit(doc, catalog, event, place, organization) for doc, catalog, event, place, organization in rows}


def _agenda_hits_by_item_id(db: SQLAlchemySession, item_ids: list[int]) -> dict[int, dict[str, Any]]:
    rows = (
        db.query(AgendaItem, Event, Place, Organization)
        .join(Event, AgendaItem.event_id == Event.id)
        .join(Place, Event.place_id == Place.id)
        .outerjoin(Organization, Event.organization_id == Organization.id)
        .filter(AgendaItem.id.in_(item_ids))
        .all()
    )
    return {int(item.id): _agenda_hit(item, event, place, org) for item, event, place, org in rows}


def _meeting_hit(doc: Document, catalog: Catalog, event: Event, place: Place, organization: Organization | None) -> dict[str, Any]:
    return {
        "id": f"doc_{doc.id}",
        "db_id": doc.id,
        "ocd_id": event.ocd_id,
        "result_type": "meeting",
        "catalog_id": catalog.id,
        "filename": catalog.filename,
        "url": catalog.url,
        "content": (catalog.content or "")[:5000] if catalog.content else None,
        "summary": catalog.summary,
        "summary_extractive": catalog.summary_extractive,
        "topics": catalog.topics,
        "related_ids": catalog.related_ids,
        "summary_is_stale": bool(
            catalog.summary and (not catalog.content_hash or catalog.summary_source_hash != catalog.content_hash)
        ),
        "topics_is_stale": bool(
            catalog.topics is not None and (not catalog.content_hash or catalog.topics_source_hash != catalog.content_hash)
        ),
        "people_metadata": [],
        "event_name": event.name,
        "meeting_category": event.meeting_type or "Other",
        "organization": organization.name if organization else "City Council",
        "date": event.record_date.isoformat() if event.record_date else None,
        "city": place.display_name or place.name,
        "state": place.state,
    }


def _agenda_hit(item: AgendaItem, event: Event, place: Place, org: Organization | None) -> dict[str, Any]:
    return {
        "id": f"item_{item.id}",
        "db_id": item.id,
        "ocd_id": item.ocd_id,
        "result_type": "agenda_item",
        "title": item.title,
        "description": item.description,
        "classification": item.classification,
        "result": item.result,
        "page_number": item.page_number,
        "event_name": event.name,
        "date": event.record_date.isoformat() if event.record_date else None,
        "city": place.display_name or place.name,
        "organization": org.name if org else "City Council",
        "meeting_category": event.meeting_type or "Other",
        "catalog_id": item.catalog_id,
        "url": item.catalog.url if item.catalog else None,
    }


def _hydrate_candidates(candidates: list[SemanticCandidateLike], hits_by_db_id: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    hydrated = []
    for candidate in candidates:
        hit = hits_by_db_id.get(int(candidate.metadata.get("db_id") or 0))
        if hit:
            enriched = dict(hit)
            enriched["semantic_score"] = round(float(candidate.score), 6)
            hydrated.append(enriched)
    return hydrated


def _candidates_by_type(candidates: list[SemanticCandidateLike], *, result_type: str) -> list[SemanticCandidateLike]:
    if result_type == "meeting":
        return [candidate for candidate in candidates if str(candidate.metadata.get("result_type") or "meeting") == "meeting"]
    return [candidate for candidate in candidates if str(candidate.metadata.get("result_type")) == result_type]


def _ordered_hydrated_hits(
    page_candidates: list[SemanticCandidateLike],
    meeting_hits: list[dict[str, Any]],
    agenda_hits: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    meeting_by_db = {hit["db_id"]: hit for hit in meeting_hits}
    agenda_by_db = {hit["db_id"]: hit for hit in agenda_hits}
    hits = []
    for candidate in page_candidates:
        result_type = str(candidate.metadata.get("result_type") or "meeting")
        db_id = int(candidate.metadata.get("db_id") or 0)
        hit = meeting_by_db.get(db_id) if result_type == "meeting" else agenda_by_db.get(db_id)
        if hit:
            hits.append(hit)
    return hits


def _doc_id(doc: Document) -> int:
    return int(doc.id)
