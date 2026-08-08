from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import cast

from pipeline.profile_manifest_contracts import JsonPayload, MANIFEST_PACKAGE_SCHEMA_VERSION


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
    extract_ids = {str(catalog_id) for catalog_id in (package.get("strata") or {}).get("extract") or []}
    source_digests = package.get("extract_source_sha256")
    if not isinstance(source_digests, dict) or set(source_digests) != extract_ids:
        raise ValueError("manifest package extract_source_sha256 keys do not match extract stratum")
    if not all(isinstance(value, str) and SHA256_HEX_PATTERN.fullmatch(value) for value in source_digests.values()):
        raise ValueError("manifest package extract_source_sha256 values must be lowercase SHA-256 hex")
    return cast(dict[str, str], source_digests)


def validate_manifest_package(catalog_ids: list[int], package: JsonPayload) -> None:
    if int(package.get("schema_version") or 0) != MANIFEST_PACKAGE_SCHEMA_VERSION:
        raise ValueError("unsupported manifest package schema_version")
    package_ids = [int(cid) for cid in package.get("catalog_ids") or []]
    if package_ids != [int(cid) for cid in catalog_ids]:
        raise ValueError("manifest package catalog_ids do not match manifest text file")
    stratum_ids = {
        int(catalog_id)
        for phase_catalog_ids in (package.get("strata") or {}).values()
        for catalog_id in phase_catalog_ids
    }
    if not stratum_ids.issubset(package_ids):
        raise ValueError("manifest package strata contain catalog_ids outside manifest workload")
    extract_source_digests(package)
