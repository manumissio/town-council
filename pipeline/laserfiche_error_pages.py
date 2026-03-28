from __future__ import annotations

from dataclasses import dataclass
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
_DOCUMENT_SHAPE_STRONG_NEEDLES = (
    "agenda report",
    "to:",
    "from:",
    "subject:",
    "recommendation:",
)
_DOCUMENT_SHAPE_SUPPORTING_NEEDLES = (
    "agenda number:",
    "section name:",
    "{{ section",
    "{{ item.tracking",
)
_MULTI_ITEM_AGENDA_PATTERNS = (
    re.compile(r"(?im)^\s*(?:item\s*)?\d{1,2}(?:\.\d+)?[\.\):]\s+.{6,}$"),
    re.compile(r"(?im)^\s*(?:call to order|public comment|consent calendar|adjournment)\s*$"),
    re.compile(r"(?im)^\s*subject\s*:\s+.{6,}$"),
)

LASERFICHE_ERROR_PAGE_REASON = "laserfiche_error_page_detected"
LASERFICHE_LOADING_SHELL_REASON = "laserfiche_loading_shell_detected"
LASERFICHE_FAMILY = "laserfiche"
DOCUMENT_SHAPE_FAMILY = "document_shape"
SINGLE_ITEM_STAFF_REPORT_REASON = "single_item_staff_report_detected"


@dataclass(frozen=True)
class BadContentClassification:
    family: str
    reason: str


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


def _count_multi_item_agenda_signals(text: str) -> int:
    return sum(len(pattern.findall(text)) for pattern in _MULTI_ITEM_AGENDA_PATTERNS)


def is_single_item_staff_report_text(text: str | None) -> bool:
    value = (text or "").strip()
    if not value:
        return False

    lowered = value.lower()
    strong_hits = sum(1 for needle in _DOCUMENT_SHAPE_STRONG_NEEDLES if needle in lowered)
    supporting_hits = sum(1 for needle in _DOCUMENT_SHAPE_SUPPORTING_NEEDLES if needle in lowered)
    multi_item_signals = _count_multi_item_agenda_signals(value)
    has_report_heading = "agenda report" in lowered or "administrative report" in lowered

    if not has_report_heading:
        return False
    if strong_hits < 4:
        return False
    if multi_item_signals >= 3:
        return False
    return supporting_hits >= 1 or "administrative report" in lowered


def _classify_laserfiche_text(text: str | None) -> BadContentClassification | None:
    if is_laserfiche_error_text(text):
        return BadContentClassification(
            family=LASERFICHE_FAMILY,
            reason=LASERFICHE_ERROR_PAGE_REASON,
        )
    if is_laserfiche_loading_shell_text(text):
        return BadContentClassification(
            family=LASERFICHE_FAMILY,
            reason=LASERFICHE_LOADING_SHELL_REASON,
        )
    return None


def classify_text_bad_content(
    text: str | None,
    *,
    location: str | None = None,
    url: str | None = None,
    document_category: str | None = None,
    include_document_shape: bool = False,
    has_viable_structured_source: bool = False,
) -> BadContentClassification | None:
    if location is not None or url is not None:
        if not (is_laserfiche_html_location(location) and is_laserfiche_portal_url(url)):
            classification = None
        else:
            classification = _classify_laserfiche_text(text)
    else:
        classification = _classify_laserfiche_text(text)

    if classification is not None:
        return classification

    if (
        include_document_shape
        and (document_category or "").strip().lower() == "agenda"
        and not has_viable_structured_source
        and is_single_item_staff_report_text(text)
    ):
        return BadContentClassification(
            family=DOCUMENT_SHAPE_FAMILY,
            reason=SINGLE_ITEM_STAFF_REPORT_REASON,
        )
    return None


def classify_catalog_bad_content(
    catalog,
    *,
    document_category: str | None = None,
    include_document_shape: bool = False,
    has_viable_structured_source: bool = False,
) -> BadContentClassification | None:
    return classify_text_bad_content(
        getattr(catalog, "content", None),
        location=getattr(catalog, "location", None),
        url=getattr(catalog, "url", None),
        document_category=document_category,
        include_document_shape=include_document_shape,
        has_viable_structured_source=has_viable_structured_source,
    )


def detect_laserfiche_bad_text_reason(text: str | None) -> str | None:
    classification = classify_text_bad_content(text)
    return classification.reason if classification else None


def detect_laserfiche_bad_content_reason(catalog) -> str | None:
    classification = classify_catalog_bad_content(catalog)
    return classification.reason if classification else None


def catalog_has_laserfiche_error_content(catalog) -> bool:
    classification = classify_catalog_bad_content(catalog)
    return bool(classification and classification.reason == LASERFICHE_ERROR_PAGE_REASON)


def catalog_has_laserfiche_loading_shell_content(catalog) -> bool:
    classification = classify_catalog_bad_content(catalog)
    return bool(classification and classification.reason == LASERFICHE_LOADING_SHELL_REASON)


def catalog_has_poisoned_laserfiche_content(catalog) -> bool:
    return classify_catalog_bad_content(catalog) is not None
