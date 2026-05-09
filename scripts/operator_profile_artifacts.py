from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def json_dump(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def load_manifest_catalog_ids(path: Path) -> list[int]:
    out: list[int] = []
    seen: set[int] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        cid = int(line)
        if cid in seen:
            continue
        seen.add(cid)
        out.append(cid)
    return out


def write_catalog_manifest(path: Path, catalog_ids: list[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{cid}\n" for cid in catalog_ids), encoding="utf-8")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_dump(payload), encoding="utf-8")


def path_for_profile_env(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        # Prefer repo-relative paths so compose-run containers can see the same
        # files, but keep the CLI testable with temporary directories.
        return str(path)


def build_result_payload(
    *,
    run_id: str,
    status: str,
    started_at: str,
    finished_at: str,
    elapsed_seconds: float,
    include_batch: bool,
    segments: list[dict],
    error_message: str | None,
    quality: dict,
) -> dict:
    core_elapsed = next((float(item["elapsed_seconds"]) for item in segments if item["name"] == "pipeline"), None)
    batch_elapsed = next((float(item["elapsed_seconds"]) for item in segments if item["name"] == "pipeline-batch"), None)
    combined_elapsed = sum(float(item["elapsed_seconds"]) for item in segments if item.get("status") == "completed")
    return {
        "run_id": run_id,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "elapsed_seconds": round(float(elapsed_seconds), 3),
        "include_batch": include_batch,
        "segments": segments,
        "totals": {
            "core_elapsed_seconds": round(core_elapsed, 3) if core_elapsed is not None else None,
            "batch_elapsed_seconds": round(batch_elapsed, 3) if batch_elapsed is not None else None,
            "combined_elapsed_seconds": round(combined_elapsed, 3),
        },
        "profile": {
            "workload_only": True,
        },
        "quality": quality,
        "error": error_message,
    }


def segment_status_from_log(command_log: Path) -> dict:
    if not command_log.exists():
        return {"notes": [], "flags": {}}
    lines = command_log.read_text(encoding="utf-8", errors="ignore").splitlines()
    notes: list[str] = []
    flags: dict[str, bool] = {}

    skip_lines = [line for line in lines if "Skipping file:" in line]
    failed_downloads = [line for line in lines if "Failed to download:" in line]
    if skip_lines and all("too large" in line for line in skip_lines) and len(failed_downloads) == len(skip_lines):
        notes.append("downloader_only_encountered_oversized_file_skips")
        flags["oversized_download_skips_only"] = True

    for idx, line in enumerate(lines):
        if "Agenda Segmentation Backfill" not in line:
            continue
        window = lines[idx:idx + 12]
        metrics: dict[str, int] = {}
        for entry in window:
            if ":" not in entry:
                continue
            key, value = entry.split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            if key in {"selected", "complete", "empty", "failed", "other"}:
                try:
                    metrics[key] = int(value)
                except ValueError:
                    pass
        if metrics.get("selected", 0) > 0 and metrics.get("failed") == metrics.get("selected") and metrics.get("complete", 0) == 0:
            notes.append("all_selected_docs_already_in_failed_segmentation_bucket")
            flags["all_failed_segmentation_bucket"] = True
            break

    return {"notes": notes, "flags": flags}
