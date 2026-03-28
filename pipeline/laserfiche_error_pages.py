from __future__ import annotations

import re


_LASERFICHE_ERROR_PAGE_PATTERNS = (
    re.compile(r"the system has encountered an error and could not complete your request", re.IGNORECASE),
    re.compile(r"if the problem persists,\s*please contact the site administrator", re.IGNORECASE),
)


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


def catalog_has_laserfiche_error_content(catalog) -> bool:
    return (
        is_laserfiche_html_location(getattr(catalog, "location", None))
        and is_laserfiche_portal_url(getattr(catalog, "url", None))
        and is_laserfiche_error_text(getattr(catalog, "content", None))
    )
