from __future__ import annotations

import os
from http.client import IncompleteRead, RemoteDisconnected
from typing import Iterator

import requests

from pipeline.config import DOWNLOAD_TIMEOUT_SECONDS
from scripts.laserfiche_repair_contracts import RepairNonRetryableError, RepairRetryableError, THREAD_STATE


def file_has_pdf_signature(path: str) -> bool:
    try:
        with open(path, "rb") as fh:
            return fh.read(5) == b"%PDF-"
    except OSError:
        return False


def file_has_pdf_eof_marker(path: str) -> bool:
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - 2048))
            tail = fh.read()
        return b"%%EOF" in tail
    except OSError:
        return False


def is_valid_pdf_artifact(path: str | None) -> bool:
    if not path or not os.path.exists(path):
        return False
    try:
        if os.path.getsize(path) <= 0:
            return False
    except OSError:
        return False
    return file_has_pdf_signature(path)


def laserfiche_headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Lf-Suppress-Login-Redirect": "1",
    }


def worker_session() -> requests.Session:
    session = getattr(THREAD_STATE, "session", None)
    if session is None:
        session = requests.Session()
        session.trust_env = False
        THREAD_STATE.session = session
    return session


def raise_for_invalid_pdf_response(response: requests.Response, *, catalog_id: int) -> None:
    content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if content_type and content_type != "application/pdf":
        body = (response.text or "")[:2000]
        lowered = body.lower()
        if "laserfiche" in lowered or "docview" in lowered or "electronicfile" in lowered or "portal" in lowered:
            raise RepairRetryableError(
                "generated_pdf_html_retryable",
                f"Retryable HTML interstitial returned for catalog {catalog_id}",
            )
        raise RepairNonRetryableError(
            "unexpected_content_type",
            f"Unexpected content type {content_type!r} for catalog {catalog_id}",
        )


def iter_pdf_chunks(response: requests.Response) -> Iterator[bytes]:
    try:
        yield from response.iter_content(chunk_size=1024 * 256)
    except requests.exceptions.ReadTimeout as exc:
        raise RepairRetryableError("read_timeout", f"Read timeout while downloading generated PDF: {exc}") from exc
    except requests.exceptions.ChunkedEncodingError as exc:
        message = str(exc).lower()
        if "incompleteread" in message:
            raise RepairRetryableError("incomplete_read", f"Incomplete generated PDF response: {exc}") from exc
        raise RepairRetryableError("connection_error", f"Chunked response failed for generated PDF: {exc}") from exc
    except requests.exceptions.ConnectionError as exc:
        message = str(exc).lower()
        cause = getattr(exc, "__cause__", None)
        if "remotedisconnected" in message or isinstance(cause, RemoteDisconnected):
            raise RepairRetryableError("remote_disconnected", f"Remote disconnected during generated PDF fetch: {exc}") from exc
        if "incompleteread" in message or isinstance(cause, IncompleteRead):
            raise RepairRetryableError("incomplete_read", f"Incomplete generated PDF response: {exc}") from exc
        raise RepairRetryableError("connection_error", f"Connection failed during generated PDF fetch: {exc}") from exc


def write_validated_pdf_response(
    response: requests.Response,
    *,
    temp_path: str,
    final_path: str,
    catalog_id: int,
) -> int:
    raise_for_invalid_pdf_response(response, catalog_id=catalog_id)
    try:
        with open(temp_path, "wb") as fh:
            for chunk in iter_pdf_chunks(response):
                if chunk:
                    fh.write(chunk)

        size = os.path.getsize(temp_path)
        if size <= 0:
            raise RepairRetryableError("invalid_partial_pdf", f"Downloaded zero-byte PDF for catalog {catalog_id}")
        if not file_has_pdf_signature(temp_path):
            raise RepairRetryableError("invalid_partial_pdf", f"Downloaded invalid PDF bytes for catalog {catalog_id}")
        if not file_has_pdf_eof_marker(temp_path):
            raise RepairRetryableError("invalid_partial_pdf", f"Downloaded truncated PDF for catalog {catalog_id}")

        os.replace(temp_path, final_path)
        return size
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
