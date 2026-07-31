import re

from pipeline.config import MAX_CONTENT_LENGTH
from pipeline.summary_freshness import is_summary_stale

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_any_html(value: str | None) -> str | None:
    """
    Defense-in-depth: Meilisearch highlights should be the only markup the UI sees.
    Agenda items may originate from Legistar APIs that sometimes include HTML.
    """
    if value is None:
        return None
    if "<" not in value and ">" not in value:
        return value
    cleaned = _TAG_RE.sub(" ", value)
    cleaned = re.sub(r"\\s+", " ", cleaned).strip()
    return cleaned


def _select_official_memberships_for_event(organization, record_date):
    # Event.organization_id is heuristic, so it cannot authorize people in search results.
    return []


def _truncate_content_for_index(content: str | None) -> tuple[str | None, bool, int, int]:
    """
    Truncate content for search indexing and return observability metadata.
    """
    if not content:
        return None, False, 0, 0

    original_chars = len(content)
    indexed_content = content[:MAX_CONTENT_LENGTH]
    indexed_chars = len(indexed_content)
    return indexed_content, original_chars > indexed_chars, original_chars, indexed_chars


def _meeting_category(event) -> str:
    raw_type = (event.meeting_type or "").lower()
    if "regular" in raw_type:
        return "Regular"
    if "special" in raw_type:
        return "Special"
    if "closed" in raw_type:
        return "Closed"
    return "Other"


def _build_meeting_search_doc(
    doc,
    catalog,
    event,
    place,
    organization,
    *,
    content_truncator=_truncate_content_for_index,
    membership_selector=_select_official_memberships_for_event,
    meeting_category_resolver=_meeting_category,
) -> dict:
    indexed_content, is_content_truncated, original_chars, indexed_chars = content_truncator(catalog.content)

    return {
        "id": f"doc_{doc.id}",
        "db_id": doc.id,
        "ocd_id": event.ocd_id,
        "result_type": "meeting",
        "catalog_id": catalog.id,
        "filename": catalog.filename,
        "url": catalog.url,
        "content": indexed_content,
        "content_truncated": is_content_truncated,
        "original_content_chars": original_chars,
        "indexed_content_chars": indexed_chars,
        "summary": catalog.summary,
        "summary_extractive": catalog.summary_extractive,
        "topics": catalog.topics,
        "summary_is_stale": is_summary_stale(
            getattr(doc, "category", "unknown"),
            summary=catalog.summary,
            summary_source_hash=catalog.summary_source_hash,
            content_hash=catalog.content_hash,
            agenda_items_hash=getattr(catalog, "agenda_items_hash", None),
            agenda_segmentation_status=getattr(catalog, "agenda_segmentation_status", None),
        ),
        "topics_is_stale": bool(
            catalog.topics is not None
            and (not catalog.content_hash or catalog.topics_source_hash != catalog.content_hash)
        ),
        "related_ids": catalog.related_ids,
        "lineage_id": catalog.lineage_id,
        "lineage_confidence": catalog.lineage_confidence,
        "event_name": event.name,
        "meeting_category": meeting_category_resolver(event),
        "organization": organization.name if organization else "City Council",
        "date": event.record_date.isoformat() if event.record_date else None,
        "city": place.display_name or place.name,
        "state": place.state,
    }


def _build_agenda_item_search_doc(
    item,
    event,
    place,
    organization,
    *,
    html_stripper=_strip_any_html,
    meeting_category_resolver=_meeting_category,
) -> dict:
    return {
        "id": f"item_{item.id}",
        "db_id": item.id,
        "ocd_id": item.ocd_id,
        "result_type": "agenda_item",
        "title": html_stripper(item.title),
        "description": html_stripper(item.description),
        "classification": item.classification,
        "result": item.result,
        "page_number": item.page_number,
        "event_name": event.name,
        "date": event.record_date.isoformat() if event.record_date else None,
        "city": place.display_name or place.name,
        "organization": organization.name if organization else "City Council",
        "meeting_category": meeting_category_resolver(event),
        "catalog_id": item.catalog_id,
        "url": item.catalog.url if item.catalog else None,
    }
