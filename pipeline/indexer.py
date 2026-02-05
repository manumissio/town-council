import os
import meilisearch
from sqlalchemy.orm import sessionmaker
from models import Document, Catalog, Event, Place, db_connect

# Configuration for connecting to the Meilisearch container
MEILI_HOST = os.getenv('MEILI_HOST', 'http://meilisearch:7700')
MEILI_MASTER_KEY = os.getenv('MEILI_MASTER_KEY', 'masterKey')

def index_documents():
    """
    Reads processed documents from the SQL database and uploads them to the Meilisearch index.
    This makes the text searchable with typo-tolerance and highlighting.
    """
    print(f"Connecting to Meilisearch at {MEILI_HOST}...")
    client = meilisearch.Client(MEILI_HOST, MEILI_MASTER_KEY)
    
    # Create or update the 'documents' index
    # We set 'id' as the primary key
    index = client.index('documents')
    
    # Define which attributes can be filtered/faceted in the UI
    index.update_filterable_attributes(['city', 'meeting_type', 'date', 'organizations'])
    # Define which attributes we can search text within
    index.update_searchable_attributes(['content', 'event_name', 'filename', 'summary', 'organizations', 'locations'])

    engine = db_connect()
    Session = sessionmaker(bind=engine)
    session = Session()

    print("Fetching documents with extracted content from database...")
    
    # We join across tables to create a "flat" document for search.
    # We want: Text Content + Metadata + AI Summary + NLP Entities
    query = session.query(Document, Catalog, Event, Place).join(
        Catalog, Document.catalog_id == Catalog.id
    ).join(
        Event, Document.event_id == Event.id
    ).join(
        Place, Document.place_id == Place.id
    ).filter(
        Catalog.content != None,  # Only index docs with text
        Catalog.content != ""
    )

    batch_size = 50
    documents_batch = []
    count = 0

    for doc, catalog, event, place in query:
        # Extract lists for faceting
        entities = catalog.entities or {}
        orgs = entities.get('orgs', [])
        locs = entities.get('locs', [])

        # Construct the search document
        search_doc = {
            'id': doc.id,
            'filename': catalog.filename,
            'url': catalog.url,
            'content': catalog.content, 
            'summary': catalog.summary,
            'entities': entities,     # Store full object for display
            'tables': catalog.tables, # Include extracted structured tables
            'organizations': orgs,    # Store flat list for filtering/search
            'locations': locs,        # Store flat list for search
            'event_name': event.name,
            'meeting_type': event.meeting_type,
            'date': event.record_date.isoformat() if event.record_date else None,
            'city': place.display_name or place.name,
            'state': place.state
        }
        
        documents_batch.append(search_doc)

        # Send to Meilisearch in batches
        if len(documents_batch) >= batch_size:
            index.add_documents(documents_batch)
            count += len(documents_batch)
            print(f"Indexed {count} documents...")
            documents_batch = []

    # Send any remaining documents
    if documents_batch:
        index.add_documents(documents_batch)
        count += len(documents_batch)

    session.close()
    print(f"Indexing complete. Total documents indexed: {count}")

if __name__ == "__main__":
    index_documents()
