from __future__ import annotations

import hashlib
import os
import re
import threading
from dataclasses import dataclass


DOCVIEW_RE = re.compile(r"/DocView\.aspx\?id=(?P<entry_id>\d+)&repo=(?P<repo>[^&]+)", re.IGNORECASE)
ELECTRONIC_FILE_RE = re.compile(
    r"/ElectronicFile\.aspx\?docid=(?P<entry_id>\d+)&repo=(?P<repo>[^&]+)",
    re.IGNORECASE,
)
PDF_TRANSITION_TIMEOUT_SECONDS = 30
PDF_TRANSITION_POLL_INTERVAL_SECONDS = 1
GENERATED_PDF_FETCH_RETRIES = 3
GENERATED_PDF_FETCH_RETRY_DELAY_SECONDS = 1
RETRYABLE_FAILURE_REASONS = {
    "timed_out",
    "token_missing",
    "remote_disconnected",
    "incomplete_read",
    "connection_error",
    "read_timeout",
    "generated_pdf_html_retryable",
    "invalid_partial_pdf",
}
THREAD_STATE = threading.local()


@dataclass(frozen=True)
class RepairTarget:
    catalog_id: int
    old_url: str
    location: str | None
    mode: str = "docview"
    entry_id: int | None = None
    repo: str | None = None
    new_url: str | None = None
    preferred_method: str = "electronic_file"
    page_count: int | None = None


class RepairRetryableError(RuntimeError):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


class RepairNonRetryableError(RuntimeError):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


def url_to_md5(value: str) -> str:
    return hashlib.md5((value or "").encode("utf-8")).hexdigest()


def parse_docview_url(url: str) -> tuple[int, str]:
    match = DOCVIEW_RE.search(url or "")
    if not match:
        raise ValueError(f"Unsupported Laserfiche DocView URL: {url!r}")
    return int(match.group("entry_id")), match.group("repo")


def parse_electronic_file_url(url: str) -> tuple[int, str]:
    match = ELECTRONIC_FILE_RE.search(url or "")
    if not match:
        raise ValueError(f"Unsupported Laserfiche ElectronicFile URL: {url!r}")
    return int(match.group("entry_id")), match.group("repo")


def electronic_file_url(entry_id: int, repo: str) -> str:
    return f"https://portal.laserfiche.com/Portal/ElectronicFile.aspx?docid={entry_id}&repo={repo}"


def target_path(existing_location: str | None, url_hash: str) -> tuple[str, str]:
    base_dir = os.path.dirname(existing_location) if existing_location else ""
    if not base_dir:
        raise ValueError("Catalog has no existing directory to store repaired PDF")
    filename = f"{url_hash}.pdf"
    return os.path.join(base_dir, filename), filename


def coerce_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y"}:
            return True
        if lowered in {"0", "false", "no", "n"}:
            return False
    return None


def failure_reason(exc: Exception) -> str:
    explicit_reason = getattr(exc, "reason", None)
    if isinstance(explicit_reason, str) and explicit_reason:
        return explicit_reason
    lowered = str(exc).strip().lower()
    if "timed out" in lowered:
        return "timed_out"
    if "token missing" in lowered:
        return "token_missing"
    if "unexpected content type" in lowered:
        return "unexpected_content_type"
    if "zero-byte" in lowered:
        return "zero_byte"
    if "invalid pdf" in lowered:
        return "invalid_pdf"
    return re.sub(r"[^a-z0-9]+", "_", lowered).strip("_") or type(exc).__name__.lower()
