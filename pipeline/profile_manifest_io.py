from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import cast

from pipeline.profile_manifest_contracts import (
    JsonPayload,
    MANIFEST_PACKAGE_SCHEMA_VERSION,
    PHASE_EXTRACT,
    PHASE_ORG,
    PROFILE_MANIFEST_PHASES,
)


SHA256_HEX_PATTERN = re.compile(r"[0-9a-f]{64}")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sidecar_path_for_manifest(manifest_path: Path) -> Path:
    return manifest_path.with_suffix(".json")


def load_manifest_package(manifest_path: Path) -> JsonPayload | None:
    sidecar_path = sidecar_path_for_manifest(manifest_path)
    if not sidecar_path.exists():
        return None
    return cast(JsonPayload, json.loads(sidecar_path.read_text(encoding="utf-8")))


def sha256_file(source_path: Path) -> str:
    with source_path.open("rb") as source_file:
        return hashlib.file_digest(source_file, "sha256").hexdigest()


def extract_source_digests(package: JsonPayload) -> dict[str, str]:
    extract_ids = {str(catalog_id) for catalog_id in (package.get("strata") or {}).get(PHASE_EXTRACT) or []}
    source_digests = package.get("extract_source_sha256")
    if not isinstance(source_digests, dict) or set(source_digests) != extract_ids:
        raise ValueError("manifest package extract_source_sha256 keys do not match extract stratum")
    if not all(isinstance(value, str) and SHA256_HEX_PATTERN.fullmatch(value) for value in source_digests.values()):
        raise ValueError("manifest package extract_source_sha256 values must be lowercase SHA-256 hex")
    return cast(dict[str, str], source_digests)


def validate_manifest_package(catalog_ids: list[int], package: JsonPayload) -> None:
    schema_version = package.get("schema_version")
    if not _is_json_integer(schema_version) or schema_version != MANIFEST_PACKAGE_SCHEMA_VERSION:
        raise ValueError("unsupported manifest package schema_version")
    package_ids = _json_integer_list(package.get("catalog_ids"), "catalog_ids")
    if len(package_ids) != len(set(package_ids)):
        raise ValueError("manifest package catalog_ids must be unique")
    if package_ids != catalog_ids:
        raise ValueError("manifest package catalog_ids do not match manifest text file")
    strata = _validated_strata(package)
    _validate_strata_partition(package_ids, strata)
    extract_source_digests(package)
    _validate_phase_coverage(package, strata)
    _validate_org_resets(package, strata[PHASE_ORG])


def _is_json_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _json_integer_list(value: object, field_name: str) -> list[int]:
    if not isinstance(value, list) or not all(_is_json_integer(entry) for entry in value):
        raise ValueError(f"manifest package {field_name} must contain JSON integers")
    return cast(list[int], value)


def _validated_strata(package: JsonPayload) -> dict[str, list[int]]:
    raw_strata = package.get("strata")
    if not isinstance(raw_strata, dict) or set(raw_strata) != set(PROFILE_MANIFEST_PHASES):
        raise ValueError("manifest package strata must contain exactly the supported phases")
    return {phase: _json_integer_list(raw_strata[phase], f"strata.{phase}") for phase in PROFILE_MANIFEST_PHASES}


def _validate_strata_partition(package_ids: list[int], strata: dict[str, list[int]]) -> None:
    partition_ids = [catalog_id for phase in PROFILE_MANIFEST_PHASES for catalog_id in strata[phase]]
    if any(catalog_id not in package_ids for catalog_id in partition_ids):
        raise ValueError("manifest package strata contain catalog_ids outside manifest workload")
    if len(partition_ids) != len(set(partition_ids)):
        raise ValueError("manifest package strata must not overlap")
    if set(partition_ids) != set(package_ids):
        raise ValueError("manifest package strata must exactly partition the manifest workload")


def _validate_phase_coverage(package: JsonPayload, strata: dict[str, list[int]]) -> None:
    expected_coverage = package.get("expected_phase_coverage")
    actual_coverage = {phase: len(strata[phase]) for phase in PROFILE_MANIFEST_PHASES}
    if not isinstance(expected_coverage, dict) or set(expected_coverage) != set(PROFILE_MANIFEST_PHASES):
        raise ValueError("manifest package expected_phase_coverage must contain exactly the supported phases")
    if any(not _is_json_integer(expected_coverage[phase]) for phase in PROFILE_MANIFEST_PHASES):
        raise ValueError("manifest package expected_phase_coverage values must be JSON integers")
    if expected_coverage != actual_coverage:
        raise ValueError("manifest package expected_phase_coverage does not match strata")


def _validate_org_resets(package: JsonPayload, org_ids: list[int]) -> None:
    raw_resets = package.get("org_event_resets", [])
    if not isinstance(raw_resets, list):
        raise ValueError("manifest package org_event_resets must be a list")
    reset_pairs: list[tuple[int, int]] = []
    for reset in raw_resets:
        if not isinstance(reset, dict) or set(reset) != {"catalog_id", "event_id"}:
            raise ValueError("manifest package org_event_resets entries must map catalog_id to event_id")
        catalog_id = reset.get("catalog_id")
        event_id = reset.get("event_id")
        if not _is_json_integer(catalog_id) or not _is_json_integer(event_id):
            raise ValueError("manifest package org_event_resets IDs must be JSON integers")
        reset_pairs.append((cast(int, catalog_id), cast(int, event_id)))
    reset_catalog_ids = [catalog_id for catalog_id, _event_id in reset_pairs]
    reset_event_ids = [event_id for _catalog_id, event_id in reset_pairs]
    if reset_catalog_ids != org_ids or len(reset_event_ids) != len(set(reset_event_ids)):
        raise ValueError("manifest package org_event_resets must uniquely map every org catalog")
    safety = package.get("safety")
    if not isinstance(safety, dict) or safety.get("org_reset_requires_single_document_event") is not True:
        raise ValueError("manifest package org reset safety must require single-document events")
