import os
import meilisearch
from meilisearch.errors import MeilisearchError

from pipeline.models import Document, Catalog, Event, Place, Organization, AgendaItem, Membership
from pipeline.db_session import db_session
from pipeline.config import MAX_CONTENT_LENGTH, MEILISEARCH_BATCH_SIZE
from sqlalchemy.orm import selectinload

# Configuration for connecting to the Meilisearch search engine.
MEILI_HOST = os.getenv('MEILI_HOST', 'http://meilisearch:7700')
MEILI_MASTER_KEY = os.getenv('MEILI_MASTER_KEY', 'masterKey')

def _select_official_memberships_for_event(organization, record_date):
    """
    Choose which officials to show for a meeting.

    Rule:
    - If membership term dates are present, prefer the roster active on record_date.
    - If term dates are missing, fall back to all official memberships so the UI
      doesn't show an empty list.
    """
    if not organization:
        return []

    eligible = []
    undated_fallback = []
    for m in (getattr(organization, "memberships", None) or []):
        person = getattr(m, "person", None)
        if not person:
            continue
        if getattr(person, "person_type", None) != "official":
            continue

        has_term_dates = bool(getattr(m, "start_date", None) or getattr(m, "end_date", None))
        if record_date and has_term_dates:
            if (m.start_date is None or m.start_date <= record_date) and (m.end_date is None or record_date <= m.end_date):
                eligible.append(m)
        else:
            undated_fallback.append(m)

    return eligible or undated_fallback


def _flush_batch(index, documents_batch, count, label):
    """Send one batch to Meilisearch and update the indexed count."""
    if not documents_batch:
        return count
    try:
        index.add_documents(documents_batch)
        return count + len(documents_batch)
    except MeilisearchError as e:
        print(f"Error indexing {label} batch: {e}")
        return count

def index_documents():
    """
    Sync processed meetings and agenda items into Meilisearch.
    """
    print(f"Connecting to Meilisearch at {MEILI_HOST}...")
    client = meilisearch.Client(MEILI_HOST, MEILI_MASTER_KEY)
    
    # Create the index once; ignore "already exists" errors.
    try:
        client.create_index('documents', {'primaryKey': 'id'})
    except MeilisearchError:
        pass
        
    index = client.index('documents')
    
    # Fields usable in filter queries.
    index.update_filterable_attributes([
        'city', 'meeting_type', 'meeting_category', 'organization', 
        'people', 'date', 'organizations', 'result_type'
    ])
    
    # Fields used for full-text search ranking.
    index.update_searchable_attributes([
        'content', 'event_name', 'title', 'description', 'filename', 
        'summary', 'organizations', 'locations', 'meeting_category', 
        'organization', 'people'
    ])

    with db_session() as session:
        documents_batch = []
        count = 0

        print("Step 1: Indexing Full Meeting Documents...")
        doc_query = session.query(Document, Catalog, Event, Place, Organization).join(
            Catalog, Document.catalog_id == Catalog.id
        ).join(
            Event, Document.event_id == Event.id
        ).join(
            Place, Document.place_id == Place.id
        ).outerjoin(
            Organization, Event.organization_id == Organization.id
        ).filter(
            Catalog.content.isnot(None),
            Catalog.content != ""
        ).options(
            # Avoid N+1 queries when building people_metadata for each document.
            selectinload(Organization.memberships).selectinload(Membership.person)
        ).yield_per(20)

        for doc, catalog, event, place, organization in doc_query:
            people_list = []
            if organization:
                chosen = _select_official_memberships_for_event(organization, event.record_date)
                people_list = [
                    {"id": m.person.id, "ocd_id": m.person.ocd_id, "name": m.person.name}
                    for m in chosen
                ]

            raw_type = (event.meeting_type or "").lower()
            category = "Other"
            if "regular" in raw_type:
                category = "Regular"
            elif "special" in raw_type:
                category = "Special"
            elif "closed" in raw_type:
                category = "Closed"

            search_doc = {
                'id': f"doc_{doc.id}",
                'db_id': doc.id,
                'ocd_id': event.ocd_id,
                'result_type': 'meeting',
                'catalog_id': catalog.id,
                'filename': catalog.filename,
                'url': catalog.url,
                'content': catalog.content[:MAX_CONTENT_LENGTH] if catalog.content else None,
                'summary': catalog.summary,
                'summary_extractive': catalog.summary_extractive,
                'topics': catalog.topics,
                # Derived-field staleness: if extracted text changes, cached summary/topics
                # may no longer match the current content.
                'summary_is_stale': bool(
                    catalog.summary
                    and (not catalog.content_hash or catalog.summary_source_hash != catalog.content_hash)
                ),
                'topics_is_stale': bool(
                    catalog.topics is not None
                    and (not catalog.content_hash or catalog.topics_source_hash != catalog.content_hash)
                ),
                'related_ids': catalog.related_ids,
                'people_metadata': people_list,
                'people': [p['name'] for p in people_list],
                'event_name': event.name,
                'meeting_category': category,
                'organization': organization.name if organization else "City Council",
                'date': event.record_date.isoformat() if event.record_date else None,
                'city': place.display_name or place.name,
                'state': place.state
            }
            documents_batch.append(search_doc)
            if len(documents_batch) >= MEILISEARCH_BATCH_SIZE:
                count = _flush_batch(index, documents_batch, count, "document")
                documents_batch = []

        count = _flush_batch(index, documents_batch, count, "document")
        documents_batch = []

        print("Step 2: Indexing Individual Agenda Items...")

        item_query = session.query(AgendaItem, Event, Place, Organization).join(
            Event, AgendaItem.event_id == Event.id
        ).join(
            Place, Event.place_id == Place.id
        ).outerjoin(
            Organization, Event.organization_id == Organization.id
        ).yield_per(100)

        for item, event, place, organization in item_query:
            raw_type = (event.meeting_type or "").lower()
            category = "Other"
            if "regular" in raw_type:
                category = "Regular"
            elif "special" in raw_type:
                category = "Special"

            search_item = {
                'id': f"item_{item.id}",
                'db_id': item.id,
                'ocd_id': item.ocd_id,
                'result_type': 'agenda_item',
                'title': item.title,
                'description': item.description,
                'classification': item.classification,
                'result': item.result,
                'page_number': item.page_number,
                'event_name': event.name,
                'date': event.record_date.isoformat() if event.record_date else None,
                'city': place.display_name or place.name,
                'organization': organization.name if organization else "City Council",
                'meeting_category': category,
                'catalog_id': item.catalog_id,
                'url': item.catalog.url if item.catalog else None
            }

            documents_batch.append(search_item)
            if len(documents_batch) >= MEILISEARCH_BATCH_SIZE:
                count = _flush_batch(index, documents_batch, count, "agenda item")
                documents_batch = []

        count = _flush_batch(index, documents_batch, count, "agenda item")

    print(f"Indexing complete. Total records indexed: {count}")


def reindex_catalog(catalog_id: int) -> dict:
    """
    Reindex a single catalog into Meilisearch.

    Why this exists:
    Some operations (like re-extracting text for one PDF) should update search
    without reindexing the entire dataset.
    """
    client = meilisearch.Client(MEILI_HOST, MEILI_MASTER_KEY)
    try:
        client.create_index('documents', {'primaryKey': 'id'})
    except MeilisearchError:
        pass

    index = client.index('documents')
    # Keep index settings consistent. These calls are idempotent in Meilisearch.
    index.update_filterable_attributes([
        'city', 'meeting_type', 'meeting_category', 'organization',
        'people', 'date', 'organizations', 'result_type'
    ])
    index.update_searchable_attributes([
        'content', 'event_name', 'title', 'description', 'filename',
        'summary', 'organizations', 'locations', 'meeting_category',
        'organization', 'people'
    ])

    with db_session() as session:
        docs = session.query(Document, Catalog, Event, Place, Organization).join(
            Catalog, Document.catalog_id == Catalog.id
        ).join(
            Event, Document.event_id == Event.id
        ).join(
            Place, Document.place_id == Place.id
        ).outerjoin(
            Organization, Event.organization_id == Organization.id
        ).filter(Catalog.id == catalog_id).options(
            selectinload(Organization.memberships).selectinload(Membership.person)
        ).all()

        if not docs:
            return {"status": "skipped", "reason": "No documents linked to catalog", "catalog_id": catalog_id}

        payload = []
        for doc, catalog, event, place, organization in docs:
            people_list = []
            if organization:
                chosen = _select_official_memberships_for_event(organization, event.record_date)
                people_list = [
                    {"id": m.person.id, "ocd_id": m.person.ocd_id, "name": m.person.name}
                    for m in chosen
                ]

            raw_type = (event.meeting_type or "").lower()
            category = "Other"
            if "regular" in raw_type:
                category = "Regular"
            elif "special" in raw_type:
                category = "Special"
            elif "closed" in raw_type:
                category = "Closed"

            payload.append({
                'id': f"doc_{doc.id}",
                'db_id': doc.id,
                'ocd_id': event.ocd_id,
                'result_type': 'meeting',
                'catalog_id': catalog.id,
                'filename': catalog.filename,
                'url': catalog.url,
                'content': catalog.content[:MAX_CONTENT_LENGTH] if catalog.content else None,
                'summary': catalog.summary,
                'summary_extractive': catalog.summary_extractive,
                'topics': catalog.topics,
                'summary_is_stale': bool(
                    catalog.summary
                    and (not catalog.content_hash or catalog.summary_source_hash != catalog.content_hash)
                ),
                'topics_is_stale': bool(
                    catalog.topics is not None
                    and (not catalog.content_hash or catalog.topics_source_hash != catalog.content_hash)
                ),
                'related_ids': catalog.related_ids,
                'people_metadata': people_list,
                'people': [p['name'] for p in people_list],
                'event_name': event.name,
                'meeting_category': category,
                'organization': organization.name if organization else "City Council",
                'date': event.record_date.isoformat() if event.record_date else None,
                'city': place.display_name or place.name,
                'state': place.state
            })

        index.add_documents(payload)

    return {"status": "ok", "catalog_id": catalog_id, "documents_reindexed": len(payload)}

if __name__ == "__main__":
    index_documents()
