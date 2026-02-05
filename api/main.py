import sys
import os
import meilisearch
from google import genai
from fastapi import FastAPI, HTTPException, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from sqlalchemy.orm import sessionmaker

# Add the project root to the python path so we can import from pipeline
# In Docker, this maps to /app
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from pipeline.models import db_connect, Document, Event, Place, Catalog
    # Set up database session
    engine = db_connect()
    Session = sessionmaker(bind=engine)
except ImportError:
    # Fallback for local development if not running in Docker or root context
    print("Warning: Could not import pipeline models. Database features may be limited.")

app = FastAPI(title="Town Council Search API", description="Search and retrieve local government meeting minutes.")

# AI Configuration
# We use 'gemini-2.0-flash' for high-speed, reliable summaries.
api_key = os.getenv('GEMINI_API_KEY')
ai_client = genai.Client(api_key=api_key) if api_key else None

# SECURITY: Enable CORS (Cross-Origin Resource Sharing)
# This allows the frontend (running on a different port like 3000) to 
# securely make requests to this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, you would list your specific domains here
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Meilisearch Config
MEILI_HOST = os.getenv('MEILI_HOST', 'http://meilisearch:7700')
MEILI_MASTER_KEY = os.getenv('MEILI_MASTER_KEY', 'masterKey')
client = meilisearch.Client(MEILI_HOST, MEILI_MASTER_KEY)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Town Council API is running. Go to /docs for the Swagger UI."}

@app.get("/search")
def search_documents(
    q: str = Query(..., description="The search query (e.g., 'zoning', 'police budget')"),
    city: Optional[str] = Query(None, description="Filter results by city name"),
    meeting_type: Optional[str] = Query(None, description="Filter results by meeting type (Regular, Special, etc.)"),
    org: Optional[str] = Query(None, description="Filter results by legislative body (e.g., 'Planning Commission')"),
    date_from: Optional[str] = Query(None, description="Filter results from date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter results to date (YYYY-MM-DD)"),
    limit: int = 20,
    offset: int = 0
):
    """
    Search for text within meeting minutes using Meilisearch.
    
    How this works for a developer:
    1. It connects to Meilisearch (our high-speed search engine).
    2. It builds a 'filter' list based on the city, type, body, and date you picked in the UI.
    3. It asks Meilisearch to find the most relevant 20 documents (limit).
    4. It returns the results along with 'highlights' (snippets showing where the words were found).
    """
    try:
        index = client.index('documents')
        
        # Configuration for Meilisearch
        search_params = {
            'limit': limit,
            'offset': offset,
            'attributesToHighlight': ['content'],  # This tells the engine to return snippets of text
            'highlightPreTag': '<em class="bg-yellow-200 not-italic font-semibold px-0.5 rounded">',
            'highlightPostTag': '</em>',
            'filter': []
        }
        
        # 1. City Filter: Narrow results to a specific city like 'Berkeley'
        if city:
            search_params['filter'].append(f'city = "{city}"')
        
        # 2. Meeting Type Filter: Only show 'Regular', 'Special' or 'Closed' meetings.
        # We use the 'meeting_category' field which is normalized in indexer.py.
        if meeting_type:
            search_params['filter'].append(f'meeting_category = "{meeting_type}"')

        # 3. Organization Filter: Narrow results to a specific body like 'Planning Commission'
        if org:
            search_params['filter'].append(f'organization = "{org}"')

        # 4. Date Range Filter: Find meetings between two specific days
        if date_from and date_to:
            search_params['filter'].append(f'date >= "{date_from}" AND date <= "{date_to}"')
        elif date_from:
            search_params['filter'].append(f'date >= "{date_from}"')
        elif date_to:
            search_params['filter'].append(f'date <= "{date_to}"')

        # Cleanup: If the user didn't pick any filters, we must remove the empty list
        if not search_params['filter']:
            del search_params['filter']

        # Perform the actual search
        results = index.search(q, search_params)
        print(f"Search for '{q}' (offset {offset}) returned {len(results['hits'])} hits")
        return results
    except Exception as e:
        # If something goes wrong (like Meilisearch is down), return a 500 error
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/metadata")
def get_metadata():
    """
    Returns unique cities and organizations present in the search index.
    
    How this works for a developer:
    1. It asks Meilisearch for 'facets' (counts of all unique values).
    2. It extracts just the names of the cities and bodies that actually have data.
    3. This ensures the frontend dropdowns always stay up-to-date automatically!
    """
    try:
        index = client.index('documents')
        # We perform an empty search (*) to get the list of all available filters (facets)
        res = index.search("*", {
            'facets': ['city', 'organization']
        })
        
        # Pull the specific list of keys (names) from the search engine's response
        facet_dist = res.get('facetDistribution', {})
        cities = sorted(list(facet_dist.get('city', {}).keys()))
        orgs = sorted(list(facet_dist.get('organization', {}).keys()))
        
        return {
            "cities": [c.title() for c in cities], # We capitalize 'berkeley' to 'Berkeley' for the UI
            "organizations": orgs
        }
    except Exception as e:
        # Return empty lists if the search engine is unreachable
        return {"cities": [], "organizations": []}

@app.get("/stats")
def get_stats():
    """
    Returns basic statistics about the indexed data.
    """
    try:
        index = client.index('documents')
        stats = index.get_stats()
        return stats
    except Exception as e:
        return {"error": "Could not connect to search index", "details": str(e)}

@app.post("/summarize/{catalog_id}")
def generate_summary(catalog_id: int = Path(..., description="The ID of the document file")):
    """
    Requests an AI-generated summary for a specific document.
    
    How this works for a developer:
    1. It checks the database to see if we already have a summary (Caching).
    2. If not, it sends the full document text to Google Gemini.
    3. It saves the AI's response back to the 'Catalog' table.
    4. Future requests for this document will be instant and free!
    """
    if not ai_client:
        raise HTTPException(status_code=503, detail="Gemini API is not configured on the server.")

    session = Session()
    try:
        # 1. Look up the document in the library
        catalog = session.get(Catalog, catalog_id)
        if not catalog:
            raise HTTPException(status_code=404, detail="Document not found in library.")

        # 2. Return cached summary if it exists
        if catalog.summary:
            return {"summary": catalog.summary, "cached": True}

        # 3. Check if document has text to read
        if not catalog.content:
            raise HTTPException(status_code=400, detail="Document has no extracted text to summarize.")

        # 4. Ask Gemini to read and summarize (On-Demand)
        prompt = (
            "You are a helpful assistant for civic transparency. "
            "Read the following town council meeting minutes and provide a summary. "
            "IMPORTANT: ONLY use information explicitly stated in the provided text. "
            "Format your response as 3 clear, concise bullet points highlighting the most important decisions. "
            "Do not include preamble or fluff.\n\n"
            f"TEXT: {catalog.content[:100000]}..." # 100k char limit for safety
        )

        response = ai_client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
            config={"temperature": 0.0, "max_output_tokens": 500}
        )

        if response and response.text:
            # 5. Save the summary back to the permanent library
            catalog.summary = response.text.strip()
            session.commit()
            
            # 6. Also update the Search Index so it's searchable immediately
            try:
                meili_index = client.index('documents')
                # Find all documents linked to this catalog ID
                docs_to_update = session.query(Document).filter_by(catalog_id=catalog_id).all()
                for d in docs_to_update:
                    meili_index.update_documents([{
                        "id": d.id,
                        "summary": catalog.summary
                    }])
            except Exception as e:
                print(f"Meilisearch update failed: {e}")

            return {"summary": catalog.summary, "cached": False}
        else:
            raise HTTPException(status_code=500, detail="AI returned an empty response.")

    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
