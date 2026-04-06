from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

from sqlalchemy import func

from pipeline.db_session import db_session
from pipeline.models import AgendaItem, Catalog, Document, Event, Membership, Person
from pipeline.person_linker import has_official_title_context, normalize_person_name
from pipeline.run_pipeline import select_catalog_ids_for_entity_backfill, select_catalog_ids_for_processing
from pipeline.utils import is_likely_human_name


MANIFEST_PACKAGE_SCHEMA_VERSION = 1
DEFAULT_PHASE_QUOTAS = {
    "extract": 8,
    "segment": 6,
    "summary": 6,
    "entity": 4,
    "org": 2,
    "people": 4,
}

_PEOPLE_RESET_BLOCKED_TOKENS = {
    "agency",
    "automated",
    "board",
    "camera",
    "cameras",
    "carbon",
    "city",
    "climate",
    "coalition",
    "committee",
    "commission",
    "community",
    "director",
    "council",
    "county",
    "district",
    "free",
    "license",
    "manager",
    "mayor",
    "monoxide",
    "plate",
    "program",
    "project",
    "readers",
    "chair",
    "skills",
    "supervisory",
    "vice",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sidecar_path_for_manifest(manifest_path: Path) -> Path:
    return manifest_path.with_suffix(".json")


def load_manifest_package(manifest_path: Path) -> dict[str, Any] | None:
    sidecar_path = sidecar_path_for_manifest(manifest_path)
    if not sidecar_path.exists():
        return None
    return json.loads(sidecar_path.read_text(encoding="utf-8"))


def validate_manifest_package(catalog_ids: list[int], package: dict[str, Any]) -> None:
    if int(package.get("schema_version") or 0) != MANIFEST_PACKAGE_SCHEMA_VERSION:
        raise ValueError("unsupported manifest package schema_version")
    package_ids = [int(cid) for cid in package.get("catalog_ids") or []]
    if package_ids != [int(cid) for cid in catalog_ids]:
        raise ValueError("manifest package catalog_ids do not match manifest text file")


def build_manifest_package(name: str, *, quotas: dict[str, int] | None = None) -> dict[str, Any]:
    target_quotas = {**DEFAULT_PHASE_QUOTAS, **(quotas or {})}
    for key, value in target_quotas.items():
        target_quotas[key] = max(0, int(value))

    with db_session() as session:
        extract_candidates = _extract_candidates(session)
        segment_candidates = _segment_reset_candidates(session)
        summary_candidates = _summary_reset_candidates(session)
        entity_candidates = _entity_reset_candidates(session)
        org_candidates = _org_reset_candidates(session)
        people_candidates = _people_reset_candidates(session)

    selected_ids: list[int] = []
    selected_set: set[int] = set()

    def pick(candidates: list[dict[str, Any]], quota: int) -> list[dict[str, Any]]:
        picked: list[dict[str, Any]] = []
        if quota <= 0:
            return picked
        for candidate in candidates:
            cid = int(candidate["catalog_id"])
            if cid in selected_set:
                continue
            selected_set.add(cid)
            selected_ids.append(cid)
            picked.append(candidate)
            if len(picked) >= quota:
                break
        return picked

    picked_extract = pick(extract_candidates, target_quotas["extract"])
    picked_segment = pick(segment_candidates, target_quotas["segment"])
    picked_summary = pick(summary_candidates, target_quotas["summary"])
    picked_entity = pick(entity_candidates, target_quotas["entity"])
    picked_org = pick(org_candidates, target_quotas["org"])
    picked_people = pick(people_candidates, target_quotas["people"])

    shortages = {
        phase: target_quotas[phase] - len(picked)
        for phase, picked in (
            ("extract", picked_extract),
            ("segment", picked_segment),
            ("summary", picked_summary),
            ("entity", picked_entity),
            ("org", picked_org),
            ("people", picked_people),
        )
        if target_quotas[phase] > len(picked)
    }
    if shortages:
        shortage_text = ", ".join(f"{phase}={count}" for phase, count in sorted(shortages.items()))
        raise ValueError(f"unable to satisfy manifest phase quotas safely: {shortage_text}")

    package = {
        "schema_version": MANIFEST_PACKAGE_SCHEMA_VERSION,
        "manifest_name": name,
        "generated_at": utc_now_iso(),
        "catalog_ids": selected_ids,
        "phase_quotas": target_quotas,
        "phase_candidates": {
            "extract": len(extract_candidates),
            "segment": len(segment_candidates),
            "summary": len(summary_candidates),
            "entity": len(entity_candidates),
            "org": len(org_candidates),
            "people": len(people_candidates),
        },
        "strata": {
            "extract": [int(item["catalog_id"]) for item in picked_extract],
            "segment": [int(item["catalog_id"]) for item in picked_segment],
            "summary": [int(item["catalog_id"]) for item in picked_summary],
            "entity": [int(item["catalog_id"]) for item in picked_entity],
            "org": [int(item["catalog_id"]) for item in picked_org],
            "people": [int(item["catalog_id"]) for item in picked_people],
        },
        "org_event_resets": [
            {"catalog_id": int(item["catalog_id"]), "event_id": int(item["event_id"])}
            for item in picked_org
        ],
        "people_reset_names": [
            {
                "catalog_id": int(item["catalog_id"]),
                "names": list(item["reset_names"]),
            }
            for item in picked_people
        ],
        "expected_phase_coverage": {
            "extract": len(picked_extract),
            "segment": len(picked_segment),
            "summary": len(picked_summary),
            "entity": len(picked_entity) + len(picked_people),
            "org": len(picked_org),
            "people": len(picked_people),
        },
        "safety": {
            "org_reset_requires_single_document_event": True,
            "people_reset_mode": "mentioned_exact_name_without_memberships",
        },
    }
    return package


def preconditioning_report(package: dict[str, Any]) -> dict[str, Any]:
    catalog_ids = [int(cid) for cid in package.get("catalog_ids") or []]
    strata = {
        key: [int(cid) for cid in value]
        for key, value in (package.get("strata") or {}).items()
    }
    entity_targets = sorted(set(strata.get("entity", []) + strata.get("people", [])))
    return {
        "schema_version": int(package.get("schema_version") or 0),
        "manifest_name": package.get("manifest_name"),
        "catalog_count": len(catalog_ids),
        "phase_selected_counts": {key: len(value) for key, value in strata.items()},
        "reset_actions": {
            "segment_catalogs": len(strata.get("segment", [])),
            "summary_catalogs": len(strata.get("summary", [])),
            "entity_catalogs": len(entity_targets),
            "org_events": len(package.get("org_event_resets") or []),
            "people_name_groups": len(package.get("people_reset_names") or []),
        },
        "expected_phase_coverage": dict(package.get("expected_phase_coverage") or {}),
    }


def apply_preconditioning(package: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
    report = preconditioning_report(package)
    strata = {
        key: [int(cid) for cid in value]
        for key, value in (package.get("strata") or {}).items()
    }
    segment_ids = strata.get("segment", [])
    summary_ids = strata.get("summary", [])
    entity_ids = sorted(set(strata.get("entity", []) + strata.get("people", [])))
    org_event_ids = [int(item["event_id"]) for item in package.get("org_event_resets") or []]
    people_reset_names = {
        int(item["catalog_id"]): [str(name) for name in item.get("names") or []]
        for item in package.get("people_reset_names") or []
    }

    applied = {
        "deleted_agenda_items": 0,
        "cleared_segment_catalogs": 0,
        "cleared_summary_catalogs": 0,
        "cleared_entity_catalogs": 0,
        "cleared_org_events": 0,
        "deleted_people": 0,
    }
    if dry_run:
        return {"dry_run": True, "report": report, "applied": applied}

    with db_session() as session:
        if segment_ids:
            applied["deleted_agenda_items"] = int(
                session.query(AgendaItem)
                .filter(AgendaItem.catalog_id.in_(segment_ids))
                .delete(synchronize_session=False)
                or 0
            )
            applied["cleared_segment_catalogs"] = int(
                session.query(Catalog)
                .filter(Catalog.id.in_(segment_ids))
                .update(
                    {
                        Catalog.agenda_segmentation_status: None,
                        Catalog.agenda_segmentation_attempted_at: None,
                        Catalog.agenda_segmentation_item_count: None,
                        Catalog.agenda_segmentation_error: None,
                        Catalog.agenda_items_hash: None,
                        Catalog.summary: None,
                        Catalog.summary_source_hash: None,
                        Catalog.summary_extractive: None,
                    },
                    synchronize_session=False,
                )
                or 0
            )

        if summary_ids:
            applied["cleared_summary_catalogs"] = int(
                session.query(Catalog)
                .filter(Catalog.id.in_(summary_ids))
                .update(
                    {
                        Catalog.agenda_items_hash: None,
                        Catalog.summary: None,
                        Catalog.summary_source_hash: None,
                        Catalog.summary_extractive: None,
                    },
                    synchronize_session=False,
                )
                or 0
            )

        if entity_ids:
            applied["cleared_entity_catalogs"] = int(
                session.query(Catalog)
                .filter(Catalog.id.in_(entity_ids))
                .update(
                    {
                        Catalog.entities: None,
                        Catalog.entities_source_hash: None,
                        Catalog.related_ids: None,
                    },
                    synchronize_session=False,
                )
                or 0
            )

        if org_event_ids:
            applied["cleared_org_events"] = int(
                session.query(Event)
                .filter(Event.id.in_(org_event_ids))
                .update({Event.organization_id: None}, synchronize_session=False)
                or 0
            )

        deleted_people = 0
        for names in people_reset_names.values():
            for name in names:
                matching_people = session.query(Person).filter(Person.name == name).all()
                for person in matching_people:
                    has_membership = (
                        session.query(Membership.id)
                        .filter(Membership.person_id == person.id)
                        .first()
                        is not None
                    )
                    if person.person_type == "mentioned" and not has_membership:
                        session.delete(person)
                        deleted_people += 1
        applied["deleted_people"] = deleted_people
        session.commit()

    return {"dry_run": False, "report": report, "applied": applied}


def _is_safe_people_reset_name(name: str) -> bool:
    if not name or not is_likely_human_name(name):
        return False

    parts = name.split()
    if len(parts) < 2 or len(parts) > 4:
        return False

    # Preconditioning should only remove rows that look strongly like person
    # mentions, not civic groups or policy phrases that slipped into entities.
    for part in parts:
        plain = re.sub(r"[^A-Za-z'.-]", "", part)
        if not plain:
            return False
        token = plain.strip(".").lower()
        if token in _PEOPLE_RESET_BLOCKED_TOKENS:
            return False
        if len(plain) == 1 and plain.isalpha():
            continue
        if len(plain) == 2 and plain.endswith(".") and plain[0].isalpha():
            continue
        if plain.isupper() and len(plain) > 2:
            continue
        if not plain[0].isupper():
            return False
    return True


def _extract_candidates(session) -> list[dict[str, Any]]:
    ids = [int(cid) for cid in select_catalog_ids_for_processing(session)]
    if not ids:
        return []
    rows = (
        session.query(Catalog.id)
        .join(Document, Document.catalog_id == Catalog.id)
        .filter(Catalog.id.in_(ids), Document.category == "agenda")
        .order_by(Catalog.id)
        .distinct()
        .all()
    )
    return [{"catalog_id": int(row[0])} for row in rows]


def _segment_reset_candidates(session) -> list[dict[str, Any]]:
    rows = (
        session.query(Catalog.id)
        .join(Document, Document.catalog_id == Catalog.id)
        .filter(
            Document.category == "agenda",
            Catalog.content.is_not(None),
            Catalog.agenda_segmentation_status == "complete",
        )
        .order_by(Catalog.id)
        .distinct()
        .all()
    )
    return [{"catalog_id": int(row[0])} for row in rows]


def _summary_reset_candidates(session) -> list[dict[str, Any]]:
    agenda_item_catalog_ids = {
        int(row[0])
        for row in session.query(AgendaItem.catalog_id).distinct().all()
        if row[0] is not None
    }
    rows = (
        session.query(Catalog.id, Document.category)
        .join(Document, Document.catalog_id == Catalog.id)
        .filter(Catalog.content.is_not(None), Catalog.summary.is_not(None))
        .order_by(Catalog.id)
        .distinct()
        .all()
    )
    candidates: list[dict[str, Any]] = []
    for catalog_id, category in rows:
        cid = int(catalog_id)
        if category in {"agenda", "agenda_html"} and cid not in agenda_item_catalog_ids:
            continue
        candidates.append({"catalog_id": cid})
    return candidates


def _entity_reset_candidates(session) -> list[dict[str, Any]]:
    ids = [int(cid) for cid in select_catalog_ids_for_entity_backfill(session)]
    if ids:
        return [{"catalog_id": cid} for cid in ids]

    rows = (
        session.query(Catalog.id)
        .join(Document, Document.catalog_id == Catalog.id)
        .filter(Catalog.content.is_not(None), Catalog.entities.is_not(None))
        .order_by(Catalog.id)
        .distinct()
        .all()
    )
    return [{"catalog_id": int(row[0])} for row in rows]


def _org_reset_candidates(session) -> list[dict[str, Any]]:
    event_doc_counts = {
        int(event_id): int(count)
        for event_id, count in (
            session.query(Event.id, func.count(Document.id))
            .join(Document, Document.event_id == Event.id)
            .filter(Event.organization_id.is_not(None))
            .group_by(Event.id)
            .all()
        )
    }
    rows = (
        session.query(Catalog.id, Event.id)
        .join(Document, Document.catalog_id == Catalog.id)
        .join(Event, Event.id == Document.event_id)
        .filter(Event.organization_id.is_not(None))
        .order_by(Catalog.id)
        .all()
    )
    candidates: list[dict[str, Any]] = []
    for catalog_id, event_id in rows:
        eid = int(event_id)
        if event_doc_counts.get(eid) != 1:
            continue
        candidates.append({"catalog_id": int(catalog_id), "event_id": eid})
    return candidates


def _people_reset_candidates(session) -> list[dict[str, Any]]:
    rows = (
        session.query(Catalog.id, Catalog.entities)
        .join(Document, Document.catalog_id == Catalog.id)
        .join(Event, Event.id == Document.event_id)
        .filter(Event.organization_id.is_not(None), Catalog.entities.is_not(None))
        .order_by(Catalog.id)
        .all()
    )
    candidates: list[dict[str, Any]] = []
    safe_names_by_catalog: dict[int, list[str]] = {}
    unique_names: set[str] = set()
    for catalog_id, entities in rows:
        reset_names: list[str] = []
        for raw_name in list((entities or {}).get("persons") or []):
            if has_official_title_context(raw_name):
                continue
            name = normalize_person_name(raw_name)
            if not _is_safe_people_reset_name(name):
                continue
            reset_names.append(name)
        if reset_names:
            deduped_names = sorted(set(reset_names))
            safe_names_by_catalog[int(catalog_id)] = deduped_names
            unique_names.update(deduped_names)

    people_by_name: dict[str, list[Person]] = {}
    if unique_names:
        people_rows = session.query(Person).filter(Person.name.in_(sorted(unique_names))).all()
        people_by_name = {}
        mentioned_person_ids = []
        for person in people_rows:
            people_by_name.setdefault(person.name, []).append(person)
            if person.person_type == "mentioned":
                mentioned_person_ids.append(int(person.id))

        membership_person_ids: set[int] = set()
        if mentioned_person_ids:
            membership_rows = (
                session.query(Membership.person_id)
                .filter(Membership.person_id.in_(mentioned_person_ids))
                .distinct()
                .all()
            )
            membership_person_ids = {
                int(row[0]) for row in membership_rows if row[0] is not None
            }
    else:
        membership_person_ids = set()

    for catalog_id, candidate_names in safe_names_by_catalog.items():
        reset_names = []
        for name in candidate_names:
            people = people_by_name.get(name) or []
            if not people:
                reset_names.append(name)
                continue
            if any(
                person.person_type == "mentioned" and int(person.id) not in membership_person_ids
                for person in people
            ):
                reset_names.append(name)
        if reset_names:
            candidates.append({"catalog_id": int(catalog_id), "reset_names": reset_names})
    return candidates
