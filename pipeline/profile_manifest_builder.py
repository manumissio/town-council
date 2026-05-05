from __future__ import annotations

from collections.abc import Callable

from pipeline.profile_manifest_contracts import (
    CandidateLoader,
    DEFAULT_PHASE_QUOTAS,
    JsonPayload,
    MANIFEST_PACKAGE_SCHEMA_VERSION,
    ManifestCandidate,
    PHASE_ENTITY,
    PHASE_EXTRACT,
    PHASE_ORG,
    PHASE_PEOPLE,
    PHASE_SEGMENT,
    PHASE_SUMMARY,
    PROFILE_MANIFEST_PHASES,
    SessionFactory,
)


def build_manifest_package(
    name: str,
    *,
    quotas: dict[str, int] | None,
    session_factory: SessionFactory,
    candidate_loaders: dict[str, CandidateLoader],
    generated_at_factory: Callable[[], str],
) -> JsonPayload:
    target_quotas = _normalized_phase_quotas(quotas)
    candidates = _load_phase_candidates(session_factory, candidate_loaders)
    selected_ids, picked_by_phase = _pick_phase_candidates(candidates, target_quotas)
    _raise_for_shortages(target_quotas, picked_by_phase)
    return _build_package_payload(
        name, generated_at_factory(), selected_ids, target_quotas, candidates, picked_by_phase
    )


def _normalized_phase_quotas(quotas: dict[str, int] | None) -> dict[str, int]:
    target_quotas = {**DEFAULT_PHASE_QUOTAS, **(quotas or {})}
    for phase, value in target_quotas.items():
        target_quotas[phase] = max(0, int(value))
    return target_quotas


def _load_phase_candidates(
    session_factory: SessionFactory,
    candidate_loaders: dict[str, CandidateLoader],
) -> dict[str, list[ManifestCandidate]]:
    with session_factory() as session:
        return {phase: candidate_loaders[phase](session) for phase in PROFILE_MANIFEST_PHASES}


def _pick_phase_candidates(
    candidates_by_phase: dict[str, list[ManifestCandidate]],
    target_quotas: dict[str, int],
) -> tuple[list[int], dict[str, list[ManifestCandidate]]]:
    selected_ids: list[int] = []
    selected_set: set[int] = set()
    picked_by_phase: dict[str, list[ManifestCandidate]] = {}
    for phase in PROFILE_MANIFEST_PHASES:
        picked_by_phase[phase] = _pick_candidates(
            candidates_by_phase[phase],
            target_quotas[phase],
            selected_ids,
            selected_set,
        )
    return selected_ids, picked_by_phase


def _pick_candidates(
    candidates: list[ManifestCandidate],
    quota: int,
    selected_ids: list[int],
    selected_set: set[int],
) -> list[ManifestCandidate]:
    picked: list[ManifestCandidate] = []
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


def _raise_for_shortages(
    target_quotas: dict[str, int],
    picked_by_phase: dict[str, list[ManifestCandidate]],
) -> None:
    shortages = {
        phase: target_quotas[phase] - len(picked_by_phase[phase])
        for phase in PROFILE_MANIFEST_PHASES
        if target_quotas[phase] > len(picked_by_phase[phase])
    }
    if not shortages:
        return
    shortage_text = ", ".join(f"{phase}={count}" for phase, count in sorted(shortages.items()))
    raise ValueError(f"unable to satisfy manifest phase quotas safely: {shortage_text}")


def _build_package_payload(
    name: str,
    generated_at: str,
    selected_ids: list[int],
    target_quotas: dict[str, int],
    candidates_by_phase: dict[str, list[ManifestCandidate]],
    picked_by_phase: dict[str, list[ManifestCandidate]],
) -> JsonPayload:
    picked_entity = picked_by_phase[PHASE_ENTITY]
    picked_people = picked_by_phase[PHASE_PEOPLE]
    return {
        "schema_version": MANIFEST_PACKAGE_SCHEMA_VERSION,
        "manifest_name": name,
        "generated_at": generated_at,
        "catalog_ids": selected_ids,
        "phase_quotas": target_quotas,
        "phase_candidates": {phase: len(candidates_by_phase[phase]) for phase in PROFILE_MANIFEST_PHASES},
        "strata": {
            phase: [int(candidate["catalog_id"]) for candidate in picked_by_phase[phase]]
            for phase in PROFILE_MANIFEST_PHASES
        },
        "org_event_resets": [
            {"catalog_id": int(candidate["catalog_id"]), "event_id": int(candidate["event_id"])}
            for candidate in picked_by_phase[PHASE_ORG]
        ],
        "people_reset_names": [
            {
                "catalog_id": int(candidate["catalog_id"]),
                "names": list(candidate["reset_names"]),
            }
            for candidate in picked_people
        ],
        "expected_phase_coverage": {
            PHASE_EXTRACT: len(picked_by_phase[PHASE_EXTRACT]),
            PHASE_SEGMENT: len(picked_by_phase[PHASE_SEGMENT]),
            PHASE_SUMMARY: len(picked_by_phase[PHASE_SUMMARY]),
            PHASE_ENTITY: len(picked_entity) + len(picked_people),
            PHASE_ORG: len(picked_by_phase[PHASE_ORG]),
            PHASE_PEOPLE: len(picked_people),
        },
        "safety": {
            "org_reset_requires_single_document_event": True,
            "people_reset_mode": "mentioned_exact_name_without_memberships",
        },
    }
