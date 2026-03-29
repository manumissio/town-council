from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from typing import Any
import uuid


_SAFE_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_REPO_ROOT = Path(__file__).resolve().parents[1]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(path)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True))
        handle.write("\n")


def _default_run_id(tool_name: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    return f"{tool_name}_{stamp}_{suffix}"


def validate_run_id(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError("run_id must not be empty")
    if "/" in normalized or "\\" in normalized or ".." in normalized:
        raise ValueError("run_id must be a safe path component")
    if not _SAFE_RUN_ID_RE.match(normalized):
        raise ValueError("run_id may contain only letters, numbers, '.', '_' and '-'")
    return normalized


@dataclass(frozen=True)
class MaintenanceRunPaths:
    run_dir: Path
    manifest_path: Path
    heartbeat_path: Path
    events_path: Path
    result_path: Path


class MaintenanceRunStatus:
    """Durable local run artifacts help operators distinguish slow progress from a stuck job."""

    def __init__(
        self,
        *,
        tool_name: str,
        output_dir: str,
        run_id: str | None,
        metadata: dict[str, Any],
    ) -> None:
        normalized_run_id = validate_run_id(run_id) if run_id else _default_run_id(tool_name)
        root = Path(output_dir)
        if not root.is_absolute():
            root = _REPO_ROOT / root
        run_dir = root / tool_name / normalized_run_id
        if run_dir.exists():
            raise ValueError(f"run directory already exists: {run_dir}")

        self.tool_name = tool_name
        self.run_id = normalized_run_id
        self.started_at = _utc_now_iso()
        self.paths = MaintenanceRunPaths(
            run_dir=run_dir,
            manifest_path=run_dir / "run_manifest.json",
            heartbeat_path=run_dir / "heartbeat.json",
            events_path=run_dir / "events.jsonl",
            result_path=run_dir / "result.json",
        )
        self.paths.run_dir.mkdir(parents=True, exist_ok=False)
        self._write_manifest(metadata)

    def _write_manifest(self, metadata: dict[str, Any]) -> None:
        _atomic_write_json(
            self.paths.manifest_path,
            {
                "tool": self.tool_name,
                "run_id": self.run_id,
                "started_at": self.started_at,
                "metadata": metadata,
            },
        )

    def heartbeat(
        self,
        *,
        status: str,
        stage: str,
        counts: dict[str, Any],
        last_catalog_id: int | None = None,
        progress: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "tool": self.tool_name,
            "run_id": self.run_id,
            "status": status,
            "stage": stage,
            "updated_at": _utc_now_iso(),
            "counts": counts,
        }
        if last_catalog_id is not None:
            payload["last_catalog_id"] = int(last_catalog_id)
        if progress:
            payload["progress"] = progress
        _atomic_write_json(self.paths.heartbeat_path, payload)

    def event(
        self,
        *,
        event_type: str,
        stage: str,
        counts: dict[str, Any],
        last_catalog_id: int | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "tool": self.tool_name,
            "run_id": self.run_id,
            "event_type": event_type,
            "stage": stage,
            "timestamp": _utc_now_iso(),
            "counts": counts,
        }
        if last_catalog_id is not None:
            payload["last_catalog_id"] = int(last_catalog_id)
        if detail:
            payload["detail"] = detail
        _append_jsonl(self.paths.events_path, payload)

    def result(
        self,
        *,
        status: str,
        counts: dict[str, Any],
        elapsed_seconds: float,
        error: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "tool": self.tool_name,
            "run_id": self.run_id,
            "status": status,
            "finished_at": _utc_now_iso(),
            "elapsed_seconds": round(float(elapsed_seconds), 3),
            "counts": counts,
        }
        if error:
            payload["error"] = error
        _atomic_write_json(self.paths.result_path, payload)
