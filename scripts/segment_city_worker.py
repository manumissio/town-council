from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any

from pipeline.config import CITY_SEGMENTATION_WORKERS, LOCAL_AI_ALLOW_MULTIPROCESS, LOCAL_AI_BACKEND, LOCAL_AI_REQUIRE_SOLO_POOL
from pipeline.models import Catalog
from scripts.segment_city_contracts import (
    DEFAULT_CATALOG_TIMEOUT_SECONDS,
    SegmentPayload,
    SegmentWorkerServices,
)


def catalog_status(services: SegmentWorkerServices, catalog_id: int) -> str | None:
    with services.db_session() as session:
        catalog = session.get(Catalog, catalog_id)
        if catalog is None:
            return None
        return catalog.agenda_segmentation_status


def mark_catalog_failed(services: SegmentWorkerServices, catalog_id: int, message: str) -> None:
    with services.db_session() as session:
        catalog = session.get(Catalog, catalog_id)
        if catalog is None:
            return
        catalog.agenda_segmentation_status = "failed"
        catalog.agenda_segmentation_item_count = 0
        catalog.agenda_segmentation_attempted_at = datetime.now(timezone.utc)
        catalog.agenda_segmentation_error = message[:500]
        session.commit()


def catalog_timeout_seconds() -> int:
    raw_timeout = os.getenv("CITY_SEGMENTATION_TIMEOUT_SECONDS", str(DEFAULT_CATALOG_TIMEOUT_SECONDS))
    try:
        return max(1, int(raw_timeout))
    except ValueError as exc:
        raise ValueError(f"invalid CITY_SEGMENTATION_TIMEOUT_SECONDS: {raw_timeout}") from exc


def catalog_worker_count(requested_workers: int | None = None) -> int:
    raw_workers = requested_workers if requested_workers is not None else CITY_SEGMENTATION_WORKERS
    try:
        workers = max(1, int(raw_workers))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid CITY_SEGMENTATION_WORKERS: {raw_workers}") from exc

    if (LOCAL_AI_BACKEND or "http").strip().lower() == "inprocess" and (
        not LOCAL_AI_ALLOW_MULTIPROCESS or LOCAL_AI_REQUIRE_SOLO_POOL
    ):
        return 1
    return workers


def segment_catalog_inline(
    services: SegmentWorkerServices,
    catalog_id: int,
    *,
    segment_mode: str = "normal",
    agenda_timeout_seconds: int | None = None,
) -> SegmentPayload:
    with services.segment_timeout_override(agenda_timeout_seconds), services.capture_agenda_fallback_events() as fallback_counts:
        segment_payload = services.segment_catalog_with_mode(catalog_id, segment_mode=segment_mode)
    segment_payload["timeout_fallbacks"] = int(fallback_counts.get("timeout", 0))
    segment_payload["empty_response_fallbacks"] = int(fallback_counts.get("empty_response", 0))
    segment_payload["llm_timeout_then_fallback"] = int(fallback_counts.get("timeout", 0))
    return segment_payload


def segment_catalog_subprocess(
    services: SegmentWorkerServices,
    catalog_id: int,
    timeout_seconds: int,
    *,
    segment_mode: str = "normal",
    agenda_timeout_seconds: int | None = None,
) -> tuple[str, float, SegmentPayload]:
    started_at = time.monotonic()
    command = _segment_command(catalog_id, segment_mode, agenda_timeout_seconds)
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True, timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        return _record_subprocess_failure(services, catalog_id, started_at, "timed_out", _timeout_message(timeout_seconds), exc)
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or f"agenda_segmentation_subprocess_failed:{exc.returncode}").strip()
        return _record_subprocess_failure(services, catalog_id, started_at, "failed", message, exc)

    return _payload_outcome(services, catalog_id, started_at, completed.stdout)


def _segment_command(catalog_id: int, segment_mode: str, agenda_timeout_seconds: int | None) -> list[str]:
    inline_call = (
        "import json; "
        "from scripts.segment_city_corpus import _segment_catalog_inline; "
        f"print(json.dumps(_segment_catalog_inline({catalog_id}, segment_mode={segment_mode!r}, agenda_timeout_seconds={agenda_timeout_seconds!r})))"
    )
    return [sys.executable, "-c", inline_call]


def _timeout_message(timeout_seconds: int) -> str:
    return f"agenda_segmentation_timeout:{timeout_seconds}s"


def _record_subprocess_failure(
    services: SegmentWorkerServices,
    catalog_id: int,
    started_at: float,
    outcome: str,
    message: str,
    exc: subprocess.TimeoutExpired | subprocess.CalledProcessError,
) -> tuple[str, float, SegmentPayload]:
    if services.mark_catalog_failed is not None:
        services.mark_catalog_failed(catalog_id, message)
    duration_seconds = time.monotonic() - started_at
    detail = (exc.stderr or exc.stdout or message).strip() or message
    return outcome, duration_seconds, {"status": outcome, "detail": detail}


def _payload_outcome(
    services: SegmentWorkerServices,
    catalog_id: int,
    started_at: float,
    stdout_text: str,
) -> tuple[str, float, SegmentPayload]:
    duration_seconds = time.monotonic() - started_at
    try:
        payload: dict[str, Any] = json.loads((stdout_text or "").strip() or "{}")
    except json.JSONDecodeError:
        message = "agenda_segmentation_invalid_subprocess_payload"
        if services.mark_catalog_failed is not None:
            services.mark_catalog_failed(catalog_id, message)
        return "failed", duration_seconds, {"status": "failed", "detail": message}

    status = str(payload.get("status") or "failed")
    if status in {"complete", "empty", "failed", "other"}:
        return status, duration_seconds, payload
    message = "agenda_segmentation_missing_terminal_status"
    if services.mark_catalog_failed is not None:
        services.mark_catalog_failed(catalog_id, message)
    return "failed", duration_seconds, {"status": "failed", "detail": message}
