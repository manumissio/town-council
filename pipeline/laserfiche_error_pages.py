from __future__ import annotations

import re


_LASERFICHE_ERROR_PAGE_PATTERNS = (
    re.compile(r"the system has encountered an error and could not complete your request", re.IGNORECASE),
    re.compile(r"if the problem persists,\s*please contact the site administrator", re.IGNORECASE),
)
_LASERFICHE_LOADING_SHELL_PATTERNS = (
    re.compile(r"\bloading\.\.\.", re.IGNORECASE),
    re.compile(r"the url can be used to link to this page", re.IGNORECASE),
    re.compile(r"your browser does not support the video tag", re.IGNORECASE),
)

LASERFICHE_ERROR_PAGE_REASON = "laserfiche_error_page_detected"
LASERFICHE_LOADING_SHELL_REASON = "laserfiche_loading_shell_detected"


def is_laserfiche_html_location(location: str | None) -> bool:
    value = (location or "").strip().lower()
    return value.endswith(".html") or value.endswith(".htm")


def is_laserfiche_portal_url(url: str | None) -> bool:
    lowered = (url or "").strip().lower()
    return "portal.laserfiche.com/portal/" in lowered and (
        "docview.aspx" in lowered or "electronicfile.aspx" in lowered
    )


def is_laserfiche_error_text(text: str | None) -> bool:
    value = (text or "").strip()
    if not value:
        return False
    return all(pattern.search(value) for pattern in _LASERFICHE_ERROR_PAGE_PATTERNS)


def is_laserfiche_loading_shell_text(text: str | None) -> bool:
    value = (text or "").strip()
    if not value:
        return False
    return all(pattern.search(value) for pattern in _LASERFICHE_LOADING_SHELL_PATTERNS)


def detect_laserfiche_bad_text_reason(text: str | None) -> str | None:
    if is_laserfiche_error_text(text):
        return LASERFICHE_ERROR_PAGE_REASON
    if is_laserfiche_loading_shell_text(text):
        return LASERFICHE_LOADING_SHELL_REASON
    return None


def detect_laserfiche_bad_content_reason(catalog) -> str | None:
    if not (
        is_laserfiche_html_location(getattr(catalog, "location", None))
        and is_laserfiche_portal_url(getattr(catalog, "url", None))
    ):
        return None
    return detect_laserfiche_bad_text_reason(getattr(catalog, "content", None))


def catalog_has_laserfiche_error_content(catalog) -> bool:
    return detect_laserfiche_bad_content_reason(catalog) == LASERFICHE_ERROR_PAGE_REASON


def catalog_has_laserfiche_loading_shell_content(catalog) -> bool:
    return detect_laserfiche_bad_content_reason(catalog) == LASERFICHE_LOADING_SHELL_REASON


def catalog_has_poisoned_laserfiche_content(catalog) -> bool:
    return detect_laserfiche_bad_content_reason(catalog) is not None
