from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import cast

from pipeline.profile_manifest_contracts import JsonPayload, MANIFEST_PACKAGE_SCHEMA_VERSION


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sidecar_path_for_manifest(manifest_path: Path) -> Path:
    return manifest_path.with_suffix(".json")


def load_manifest_package(manifest_path: Path) -> JsonPayload | None:
    sidecar_path = sidecar_path_for_manifest(manifest_path)
    if not sidecar_path.exists():
        return None
    return cast(JsonPayload, json.loads(sidecar_path.read_text(encoding="utf-8")))


def validate_manifest_package(catalog_ids: list[int], package: JsonPayload) -> None:
    if int(package.get("schema_version") or 0) != MANIFEST_PACKAGE_SCHEMA_VERSION:
        raise ValueError("unsupported manifest package schema_version")
    package_ids = [int(cid) for cid in package.get("catalog_ids") or []]
    if package_ids != [int(cid) for cid in catalog_ids]:
        raise ValueError("manifest package catalog_ids do not match manifest text file")
