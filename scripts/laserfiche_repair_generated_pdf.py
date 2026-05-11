from __future__ import annotations

import time

import requests

from scripts.laserfiche_repair_contracts import (
    GENERATED_PDF_FETCH_RETRIES,
    GENERATED_PDF_FETCH_RETRY_DELAY_SECONDS,
    PDF_TRANSITION_POLL_INTERVAL_SECONDS,
    RepairNonRetryableError,
    RepairRetryableError,
    THREAD_STATE,
)
from scripts.laserfiche_repair_pdf_io import laserfiche_headers, write_validated_pdf_response


def wait_for_generated_pdf(
    session: requests.Session,
    *,
    token: str,
    catalog_id: int,
    timeout_seconds: int,
    request_timeout_seconds: int,
    poll_interval_seconds: int = PDF_TRANSITION_POLL_INTERVAL_SECONDS,
) -> None:
    deadline = time.time() + timeout_seconds
    while True:
        progress = session.post(
            "https://portal.laserfiche.com/Portal/DocumentService.aspx/PDFTransition",
            headers=laserfiche_headers(),
            json={"Key": token},
            timeout=request_timeout_seconds,
        )
        progress.raise_for_status()
        progress_payload = progress.json().get("data") or {}
        if progress_payload.get("finished"):
            if not progress_payload.get("success"):
                message = progress_payload.get("errMsg") or "unknown error"
                raise RepairNonRetryableError(
                    "generated_pdf_failed",
                    f"Laserfiche PDF generation failed for catalog {catalog_id}: {message}",
                )
            return
        if time.time() >= deadline:
            raise ValueError(f"Laserfiche PDF generation timed out for catalog {catalog_id}")
        time.sleep(poll_interval_seconds)


def fetch_generated_pdf(
    session: requests.Session,
    *,
    token: str,
    entry_id: int,
    temp_path: str,
    final_path: str,
    catalog_id: int,
    request_timeout_seconds: int,
    fetch_retries: int = GENERATED_PDF_FETCH_RETRIES,
    retry_delay_seconds: int = GENERATED_PDF_FETCH_RETRY_DELAY_SECONDS,
) -> int:
    last_error: Exception | None = None
    for attempt in range(1, fetch_retries + 1):
        try:
            download = session.get(
                f"https://portal.laserfiche.com/Portal/PDF10/{token}/{entry_id}",
                stream=True,
                timeout=request_timeout_seconds,
            )
            download.raise_for_status()
            size = write_validated_pdf_response(
                download,
                temp_path=temp_path,
                final_path=final_path,
                catalog_id=catalog_id,
            )
            setattr(THREAD_STATE, "last_generated_pdf_fetch_retries", attempt - 1)
            return size
        except requests.exceptions.ReadTimeout as exc:
            last_error = RepairRetryableError("read_timeout", f"Read timeout while fetching generated PDF: {exc}")
        except requests.exceptions.ConnectionError as exc:
            last_error = classify_fetch_connection_error(exc)
        except RepairRetryableError as exc:
            last_error = exc
        if attempt < fetch_retries:
            time.sleep(retry_delay_seconds * attempt)
    assert last_error is not None
    raise last_error


def classify_fetch_connection_error(exc: requests.exceptions.ConnectionError) -> RepairRetryableError:
    message = str(exc).lower()
    if "remotedisconnected" in message:
        return RepairRetryableError("remote_disconnected", f"Remote disconnected while fetching generated PDF: {exc}")
    if "incompleteread" in message:
        return RepairRetryableError("incomplete_read", f"Incomplete generated PDF response: {exc}")
    return RepairRetryableError("connection_error", f"Connection error while fetching generated PDF: {exc}")
