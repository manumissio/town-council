from __future__ import annotations

from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from pipeline.profile_manifest_builder import build_manifest_package as _build_manifest_package_impl
from pipeline.profile_manifest_candidates import (
    entity_reset_candidates as _entity_reset_candidates_impl,
    extract_candidates as _extract_candidates_impl,
    org_reset_candidates as _org_reset_candidates_impl,
    segment_reset_candidates as _segment_reset_candidates_impl,
    summary_reset_candidates as _summary_reset_candidates_impl,
)
from pipeline.profile_manifest_contracts import (
    DEFAULT_PHASE_QUOTAS,
    MANIFEST_PACKAGE_SCHEMA_VERSION,
    JsonPayload,
    ManifestCandidate,
    PHASE_ENTITY,
    PHASE_EXTRACT,
    PHASE_ORG,
    PHASE_SEGMENT,
    PHASE_SUMMARY,
    OrmSession,
)
from pipeline.profile_manifest_io import (
    load_manifest_package as _load_manifest_package_impl,
    sidecar_path_for_manifest as _sidecar_path_for_manifest_impl,
    utc_now_iso as _utc_now_iso_impl,
    validate_manifest_package as _validate_manifest_package_impl,
)
from pipeline.profile_manifest_preconditioning import (
    apply_preconditioning as _apply_preconditioning_impl,
    preconditioning_report as _preconditioning_report_impl,
)


def _default_db_session() -> Any:
    return import_module("pipeline.db_session").db_session  # Public facade keeps existing monkeypatch seam.


def _facade_models() -> SimpleNamespace:
    return SimpleNamespace(
        AgendaItem=AgendaItem,
        Catalog=Catalog,
        Document=Document,
        Event=Event,
    )


_models = import_module("pipeline.models")
AgendaItem = _models.AgendaItem
Catalog = _models.Catalog
Document = _models.Document
Event = _models.Event
_run_pipeline = import_module("pipeline.run_pipeline")
select_catalog_ids_for_entity_backfill = _run_pipeline.select_catalog_ids_for_entity_backfill
select_catalog_ids_for_processing = _run_pipeline.select_catalog_ids_for_processing

db_session = _default_db_session()

__all__ = (
    "MANIFEST_PACKAGE_SCHEMA_VERSION",
    "DEFAULT_PHASE_QUOTAS",
    "utc_now_iso",
    "sidecar_path_for_manifest",
    "load_manifest_package",
    "validate_manifest_package",
    "build_manifest_package",
    "preconditioning_report",
    "apply_preconditioning",
    "_extract_candidates",
    "_segment_reset_candidates",
    "_summary_reset_candidates",
    "_entity_reset_candidates",
    "_org_reset_candidates",
    "db_session",
    "AgendaItem",
    "Catalog",
    "Document",
    "Event",
    "select_catalog_ids_for_entity_backfill",
    "select_catalog_ids_for_processing",
)


def utc_now_iso() -> str:
    return _utc_now_iso_impl()


def sidecar_path_for_manifest(manifest_path: Path) -> Path:
    return _sidecar_path_for_manifest_impl(manifest_path)


def load_manifest_package(manifest_path: Path) -> JsonPayload | None:
    return _load_manifest_package_impl(manifest_path)


def validate_manifest_package(catalog_ids: list[int], package: JsonPayload) -> None:
    _validate_manifest_package_impl(catalog_ids, package)


def build_manifest_package(name: str, *, quotas: dict[str, int] | None = None) -> JsonPayload:
    return _build_manifest_package_impl(
        name,
        quotas=quotas,
        session_factory=db_session,
        candidate_loaders={
            PHASE_EXTRACT: _extract_candidates,
            PHASE_SEGMENT: _segment_reset_candidates,
            PHASE_SUMMARY: _summary_reset_candidates,
            PHASE_ENTITY: _entity_reset_candidates,
            PHASE_ORG: _org_reset_candidates,
        },
        generated_at_factory=utc_now_iso,
    )


def preconditioning_report(package: JsonPayload) -> JsonPayload:
    return _preconditioning_report_impl(package)


def apply_preconditioning(package: JsonPayload, *, dry_run: bool = False) -> JsonPayload:
    return _apply_preconditioning_impl(package, dry_run=dry_run, session_factory=db_session)


def _extract_candidates(session: OrmSession) -> list[ManifestCandidate]:
    return _extract_candidates_impl(
        session,
        models_module=_facade_models(),
        processing_selector=select_catalog_ids_for_processing,
    )


def _segment_reset_candidates(session: OrmSession) -> list[ManifestCandidate]:
    return _segment_reset_candidates_impl(session, models_module=_facade_models())


def _summary_reset_candidates(session: OrmSession) -> list[ManifestCandidate]:
    return _summary_reset_candidates_impl(session, models_module=_facade_models())


def _entity_reset_candidates(session: OrmSession) -> list[ManifestCandidate]:
    return _entity_reset_candidates_impl(
        session,
        models_module=_facade_models(),
        entity_selector=select_catalog_ids_for_entity_backfill,
    )


def _org_reset_candidates(session: OrmSession) -> list[ManifestCandidate]:
    return _org_reset_candidates_impl(session, models_module=_facade_models())
