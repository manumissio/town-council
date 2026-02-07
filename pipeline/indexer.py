import os
import meilisearch
from sqlalchemy.orm import sessionmaker
from pipeline.models import Document, Catalog, Event, Place, Organization, AgendaItem, db_connect

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
    index = client.index('documents', {'primaryKey': 'id'})
    
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

    engine = db_connect()
    Session = sessionmaker(bind=engine)
    session = Session()

    batch_size = 20
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
            # PERFORMANCE: Truncate content to avoid payload limits. 
            # 50k chars is enough for search relevance.
            'content': catalog.content[:50000], 
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
        if len(documents_batch) >= batch_size:
            try:
                task = index.add_documents(documents_batch)
                # Wait for Meilisearch to acknowledge receipt
                print(f"Sent batch to Meilisearch. Task ID: {task.task_uid}")
                count += len(documents_batch)
            except Exception as e:
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
        if len(documents_batch) >= batch_size:
            index.add_documents(documents_batch)
            count += len(documents_batch)
            documents_batch = []

    if documents_batch:
        index.add_documents(documents_batch)
        count += len(documents_batch)

    session.close()
    print(f"Indexing complete. Total records indexed: {count}")

if __name__ == "__main__":
    index_documents()