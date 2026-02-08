import os
import meilisearch
from pipeline.models import Document, Catalog, Event, Place, Organization, AgendaItem
from pipeline.db_session import db_session
from pipeline.config import MAX_CONTENT_LENGTH, MEILISEARCH_BATCH_SIZE

# Configuration for connecting to the Meilisearch search engine.
MEILI_HOST = os.getenv('MEILI_HOST', 'http://meilisearch:7700')
MEILI_MASTER_KEY = os.getenv('MEILI_MASTER_KEY', 'masterKey')

def index_documents():
    """
    Syncs processed documents and agenda items from the main database into the Search Engine.
    
    Why this is needed:
    Databases like Postgres are great for storage, but slow for full-text search.
    We copy the data into Meilisearch, which is optimized for instant, 
    typo-tolerant searching (like Google).
    """
    print(f"Connecting to Meilisearch at {MEILI_HOST}...")
    client = meilisearch.Client(MEILI_HOST, MEILI_MASTER_KEY)
    
    # Create the 'documents' index if it doesn't exist.
    # Explicitly set the primary key to 'id' to avoid ambiguity errors.
    try:
        client.create_index('documents', {'primaryKey': 'id'})
    except Exception:
        # Index likely already exists
        pass
        
    index = client.index('documents')
    
    # Configure Filters: These fields can be used to narrow down results.
    index.update_filterable_attributes([
        'city', 'meeting_type', 'meeting_category', 'organization', 
        'people', 'date', 'organizations', 'result_type'
    ])
    
    # Configure Searchable Fields: Added 'title' and 'description' for Agenda Items.
    index.update_searchable_attributes([
        'content', 'event_name', 'title', 'description', 'filename', 
        'summary', 'organizations', 'locations', 'meeting_category', 
        'organization', 'people'
    ])

    # Use context manager for automatic session cleanup
    # The "with" statement ensures the database session closes properly
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
        Catalog.content != None,
        Catalog.content != ""
    ).yield_per(20)

    for doc, catalog, event, place, organization in doc_query:
        entities = catalog.entities or {}
        orgs = entities.get('orgs', [])
        
        people_list = []
        if organization:
            people_list = [
                {"id": m.person.id, "ocd_id": m.person.ocd_id, "name": m.person.name} 
                for m in organization.memberships
            ]

        raw_type = (event.meeting_type or "").lower()
        category = "Other"
        if "regular" in raw_type: category = "Regular"
        elif "special" in raw_type: category = "Special"
        elif "closed" in raw_type: category = "Closed"

        search_doc = {
            'id': f"doc_{doc.id}", # String ID for Meilisearch
            'db_id': doc.id,
            'ocd_id': event.ocd_id,
            'result_type': 'meeting',
            'catalog_id': catalog.id,
            'filename': catalog.filename,
            'url': catalog.url,
            # PERFORMANCE: Truncate content to avoid payload limits
            # MAX_CONTENT_LENGTH chars is enough for search relevance without slowing down Meilisearch
            'content': catalog.content[:MAX_CONTENT_LENGTH] if catalog.content else None, 
            'summary': catalog.summary,
            'summary_extractive': catalog.summary_extractive,
            'topics': catalog.topics,
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

        # Send documents to Meilisearch in batches to improve performance
        # Batching = sending multiple items at once instead of one-by-one
        if len(documents_batch) >= MEILISEARCH_BATCH_SIZE:
            try:
                task = index.add_documents(documents_batch)
                # Wait for Meilisearch to acknowledge receipt
                print(f"Sent batch to Meilisearch. Task ID: {task.task_uid}")
                count += len(documents_batch)
            except Exception as e:
                # If Meilisearch fails, log the error but continue processing
                # We don't want one batch failure to stop the entire indexing run
                print(f"Error sending batch to Meilisearch: {e}")
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
        if "regular" in raw_type: category = "Regular"
        elif "special" in raw_type: category = "Special"
        
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
            # Link back to the parent document for context
            'catalog_id': item.catalog_id,
            'url': item.catalog.url if item.catalog else None
        }
        
        documents_batch.append(search_item)

        # Same batching logic for agenda items
        if len(documents_batch) >= MEILISEARCH_BATCH_SIZE:
            try:
                index.add_documents(documents_batch)
                count += len(documents_batch)
            except Exception as e:
                print(f"Error indexing agenda items batch: {e}")
            documents_batch = []

        # Send any remaining documents in the last batch
        # This runs AFTER the for loop completes
        if documents_batch:
            try:
                index.add_documents(documents_batch)
                count += len(documents_batch)
            except Exception as e:
                print(f"Error indexing final batch: {e}")

    # Session automatically closes when we exit the "with" block above
    print(f"Indexing complete. Total records indexed: {count}")

if __name__ == "__main__":
    index_documents()