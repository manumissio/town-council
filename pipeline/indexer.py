import os
import meilisearch
from sqlalchemy.orm import sessionmaker
from models import Document, Catalog, Event, Place, db_connect

# Configuration for connecting to the Meilisearch search engine.
MEILI_HOST = os.getenv('MEILI_HOST', 'http://meilisearch:7700')
MEILI_MASTER_KEY = os.getenv('MEILI_MASTER_KEY', 'masterKey')

def index_documents():
    """
    Syncs processed documents from the main database into the Search Engine.
    
    Why this is needed:
    Databases like Postgres are great for storage, but slow for full-text search.
    We copy the data into Meilisearch, which is optimized for instant, 
    typo-tolerant searching (like Google).
    """
    print(f"Connecting to Meilisearch at {MEILI_HOST}...")
    client = meilisearch.Client(MEILI_HOST, MEILI_MASTER_KEY)
    
    # Create the 'documents' index if it doesn't exist.
    # The 'id' field is used to uniquely identify each search result.
    index = client.index('documents')
    
    # Configure Filters: These fields can be used to narrow down results.
    # Added 'meeting_category' for normalized radio-button filtering.
    index.update_filterable_attributes(['city', 'meeting_type', 'meeting_category', 'date', 'organizations'])
    
    # Configure Searchable Fields
    index.update_searchable_attributes(['content', 'event_name', 'filename', 'summary', 'organizations', 'locations', 'meeting_category'])

    engine = db_connect()
    Session = sessionmaker(bind=engine)
    session = Session()

    print("Fetching documents with extracted content from database...")
    
    # Join tables to create a "flat" document for Meilisearch.
    query = session.query(Document, Catalog, Event, Place).join(
        Catalog, Document.catalog_id == Catalog.id
    ).join(
        Event, Document.event_id == Event.id
    ).join(
        Place, Document.place_id == Place.id
    ).filter(
        Catalog.content != None,
        Catalog.content != ""
    )

    batch_size = 50
    documents_batch = []
    count = 0

    for doc, catalog, event, place in query:
        # Extract helpful lists for filtering.
        entities = catalog.entities or {}
        orgs = entities.get('orgs', [])
        locs = entities.get('locs', [])

        # Normalize Meeting Type into a Category for the UI radio buttons.
        # e.g. "City Council Regular Meeting" -> "Regular"
        raw_type = (event.meeting_type or "").lower()
        category = "Other"
        if "regular" in raw_type:
            category = "Regular"
        elif "special" in raw_type:
            category = "Special"
        elif "closed" in raw_type:
            category = "Closed"

        # Build the search object.
        search_doc = {
            'id': doc.id,
            'filename': catalog.filename,
            'url': catalog.url,
            'content': catalog.content, 
            'summary': catalog.summary,
            'entities': entities,
            'topics': catalog.topics,
            'tables': catalog.tables,
            'organizations': orgs,
            'locations': locs,
            'event_name': event.name,
            'meeting_type': event.meeting_type,
            'meeting_category': category,
            'date': event.record_date.isoformat() if event.record_date else None,
            'city': place.display_name or place.name,
            'state': place.state
        }
        
        documents_batch.append(search_doc)

        # Send data in batches of 50 to be efficient.
        if len(documents_batch) >= batch_size:
            index.add_documents(documents_batch)
            count += len(documents_batch)
            print(f"Indexed {count} documents...")
            documents_batch = []

    # Send any remaining documents in the last batch.
    if documents_batch:
        index.add_documents(documents_batch)
        count += len(documents_batch)

    session.close()
    print(f"Indexing complete. Total documents indexed: {count}")

if __name__ == "__main__":
    index_documents()