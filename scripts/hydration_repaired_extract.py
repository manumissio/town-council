from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from pipeline.models import Catalog
from scripts.hydration_counts import ProgressCallback
from scripts.hydration_output import emit_progress
from scripts.hydration_repaired_selectors import selector_mode


def extract_one_catalog(
    catalog_id: int,
    *,
    db_session,
    reextract_catalog_content,
    min_extracted_chars: int,
) -> tuple[str, dict[str, Any]]:
    with db_session() as session:
        catalog = session.get(Catalog, catalog_id)
        if not catalog:
            return "missing_catalog", {"error": "Catalog not found"}
        artifact_error = _artifact_error(catalog.location)
        if artifact_error is not None:
            return artifact_error
        result = reextract_catalog_content(
            catalog,
            force=True,
            ocr_fallback=True,
            min_chars=min_extracted_chars,
        )
        session.commit()
    return _extract_status(result)


def run_extract_city(
    city: str,
    *,
    limit: int | None,
    resume_after_id: int | None,
    url_substring: str | None,
    emit_progress_enabled: bool,
    progress_every: int,
    workers: int,
    select_extract_catalog_ids,
    extract_one_catalog,
    status_callback: ProgressCallback | None = None,
) -> tuple[dict[str, int], list[int]]:
    catalog_ids, precheck_counts = select_extract_catalog_ids(
        city,
        limit=limit,
        resume_after_id=resume_after_id,
        url_substring=url_substring,
    )
    counts = _initial_extract_counts(catalog_ids, precheck_counts)
    ready_catalog_ids: list[int] = []
    _emit_extract_start(city, counts, limit, resume_after_id, url_substring, emit_progress_enabled, status_callback)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(extract_one_catalog, catalog_id): catalog_id for catalog_id in catalog_ids}
        for index, future in enumerate(as_completed(futures), start=1):
            catalog_id = futures[future]
            status, detail = future.result()
            counts[status] = counts.get(status, 0) + 1
            if status in {"updated", "cached"}:
                ready_catalog_ids.append(catalog_id)
            _emit_extract_progress(city, index, catalog_ids, catalog_id, status, detail, counts, emit_progress_enabled, progress_every, status_callback)
    ready_catalog_ids.sort()
    emit_progress(emit_progress_enabled, f"[{city}] extract_finish counts={counts}")
    if status_callback:
        status_callback({"event_type": "stage_finish", "stage": "extract", "counts": counts.copy()})
    return counts, ready_catalog_ids


def _artifact_error(location: str | None) -> tuple[str, dict[str, Any]] | None:
    if not location:
        return "missing_file", {"error": "Catalog has no file location"}
    artifact_path = Path(location)
    if not artifact_path.exists():
        return "missing_file", {"error": "File not found on disk", "location": location}
    if artifact_path.stat().st_size <= 0:
        return "zero_byte", {"error": "Zero-byte file on disk", "location": location}
    return None


def _extract_status(result: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if "error" in result:
        return "failed", result
    status = str(result.get("status") or "other")
    if status in {"updated", "cached"}:
        return status, result
    return "other", result


def _initial_extract_counts(catalog_ids: list[int], precheck_counts: dict[str, int]) -> dict[str, int]:
    return {
        "selected": len(catalog_ids),
        "updated": 0,
        "cached": 0,
        "missing_file": precheck_counts["missing_file"],
        "zero_byte": precheck_counts["zero_byte"],
        "missing_catalog": 0,
        "failed": 0,
        "other": 0,
    }


def _emit_extract_start(
    city: str,
    counts: dict[str, int],
    limit: int | None,
    resume_after_id: int | None,
    url_substring: str | None,
    emit_progress_enabled: bool,
    status_callback: ProgressCallback | None,
) -> None:
    emit_progress(
        emit_progress_enabled,
        f"[{city}] extract_start selected={counts['selected']} limit={limit} resume_after_id={resume_after_id} "
        f"selector={selector_mode(url_substring)!r}",
    )
    if status_callback:
        status_callback({"event_type": "stage_start", "stage": "extract", "counts": counts.copy(), "detail": {"selector_mode": selector_mode(url_substring)}})


def _emit_extract_progress(
    city: str,
    index: int,
    catalog_ids: list[int],
    catalog_id: int,
    status: str,
    detail: dict[str, Any],
    counts: dict[str, int],
    emit_progress_enabled: bool,
    progress_every: int,
    status_callback: ProgressCallback | None,
) -> None:
    should_emit = index == 1 or index % progress_every == 0 or index == len(catalog_ids)
    if not should_emit:
        return
    extra = f" last_error={detail['error']!r}" if "error" in detail else ""
    emit_progress(
        emit_progress_enabled,
        f"[{city}] extract_progress done={index}/{len(catalog_ids)} last_catalog_id={catalog_id} "
        f"last_status={status} counts={counts}{extra}",
    )
    if status_callback:
        status_callback(
            {
                "event_type": "progress",
                "stage": "extract",
                "counts": counts.copy(),
                "last_catalog_id": catalog_id,
                "detail": {"done": index, "total": len(catalog_ids), "last_status": status},
            }
        )
