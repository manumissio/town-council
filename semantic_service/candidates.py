from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Protocol, TypeVar


class SemanticCandidateLike(Protocol):
    score: float
    metadata: dict[str, Any]


CandidateT = TypeVar("CandidateT", bound=SemanticCandidateLike)


@dataclass
class FallbackCandidate:
    row_id: int
    score: float
    metadata: dict[str, Any]


def semantic_candidate_matches_filters(meta: Mapping[str, Any], filters: Mapping[str, Any]) -> bool:
    result_type = str(meta.get("result_type") or "")
    if not filters.get("include_agenda_items") and result_type != "meeting":
        return False
    city = filters.get("city")
    if city and str(meta.get("city") or "").lower() != str(city).lower():
        return False
    meeting_type = filters.get("meeting_type")
    if meeting_type and str(meta.get("meeting_category") or "").lower() != str(meeting_type).lower():
        return False
    org = filters.get("org")
    if org and str(meta.get("organization") or "").lower() != str(org).lower():
        return False
    date_val = str(meta.get("date") or "")
    date_from = filters.get("date_from")
    date_to = filters.get("date_to")
    if date_from and (not date_val or date_val < date_from):
        return False
    if date_to and (not date_val or date_val > date_to):
        return False
    return True


def dedupe_semantic_candidates(candidates: Iterable[CandidateT]) -> list[CandidateT]:
    best_by_key: dict[tuple[str, int], CandidateT] = {}
    for candidate in candidates:
        key = semantic_candidate_key(candidate)
        existing = best_by_key.get(key)
        if existing is None or candidate.score > existing.score:
            best_by_key[key] = candidate
    deduped = list(best_by_key.values())
    deduped.sort(key=lambda candidate: candidate.score, reverse=True)
    return deduped


def semantic_candidate_key(candidate: SemanticCandidateLike) -> tuple[str, int]:
    meta = candidate.metadata
    result_type = str(meta.get("result_type") or "meeting")
    if result_type == "meeting":
        return ("meeting", int(meta.get("catalog_id") or 0))
    return ("agenda_item", int(meta.get("db_id") or 0))


def lexical_hit_to_candidate(hit: Mapping[str, Any], order_idx: int) -> FallbackCandidate | None:
    result_type = str(hit.get("result_type") or "meeting")
    if result_type == "meeting":
        metadata = _meeting_candidate_metadata(hit)
    elif result_type == "agenda_item":
        metadata = _agenda_candidate_metadata(hit)
    else:
        return None
    if metadata is None:
        return None
    return FallbackCandidate(row_id=order_idx, score=-float(order_idx + 1), metadata=metadata)


def _meeting_candidate_metadata(hit: Mapping[str, Any]) -> dict[str, Any] | None:
    db_id = _candidate_db_id(hit, prefix="doc_")
    catalog_id = hit.get("catalog_id")
    if db_id is None or catalog_id is None:
        return None
    return {
        "result_type": "meeting",
        "catalog_id": int(catalog_id),
        "db_id": int(db_id),
        "event_id": hit.get("event_id"),
        "city": str(hit.get("city") or "").lower(),
        "meeting_category": hit.get("meeting_category") or "Other",
        "organization": hit.get("organization") or "City Council",
        "date": hit.get("date"),
        "source_type": "lexical_fallback",
    }


def _agenda_candidate_metadata(hit: Mapping[str, Any]) -> dict[str, Any] | None:
    db_id = _candidate_db_id(hit, prefix="item_")
    if db_id is None:
        return None
    return {
        "result_type": "agenda_item",
        "catalog_id": hit.get("catalog_id"),
        "db_id": int(db_id),
        "event_id": hit.get("event_id"),
        "city": str(hit.get("city") or "").lower(),
        "meeting_category": hit.get("meeting_category") or "Other",
        "organization": hit.get("organization") or "City Council",
        "date": hit.get("date"),
        "source_type": "lexical_fallback",
    }


def _candidate_db_id(hit: Mapping[str, Any], *, prefix: str) -> int | None:
    db_id = hit.get("db_id")
    if db_id is not None:
        return int(db_id)
    raw_id = str(hit.get("id") or "")
    if not raw_id.startswith(prefix):
        return None
    try:
        return int(raw_id.split("_", 1)[1])
    except (IndexError, ValueError):
        return None
