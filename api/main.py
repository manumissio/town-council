import sys
import os
import meilisearch
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional

# Add the project root to the python path so we can import from pipeline
# In Docker, this maps to /app
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from pipeline.models import db_connect, Document, Event, Place
    from sqlalchemy.orm import sessionmaker
except ImportError:
    # Fallback for local development if not running in Docker or root context
    print("Warning: Could not import pipeline models. Database features may be limited.")

app = FastAPI(title="Town Council Search API", description="Search and retrieve local government meeting minutes.")

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
    meeting_type: Optional[str] = Query(None, description="Filter results by meeting type"),
    date_from: Optional[str] = Query(None, description="Filter results from date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter results to date (YYYY-MM-DD)"),
    limit: int = 20,
    offset: int = 0
):
    """
    Search for text within meeting minutes using Meilisearch.
    Supports advanced filtering and pagination.
    """
    try:
        index = client.index('documents')
        
        search_params = {
            'limit': limit,
            'offset': offset,
            'attributesToHighlight': ['content'],  # Return snippets with <em>query</em>
            'highlightPreTag': '<em class="bg-yellow-200 not-italic font-semibold px-0.5 rounded">',
            'highlightPostTag': '</em>',
            'filter': []
        }
        
        # Build filter array for Meilisearch
        if city:
            search_params['filter'].append(f'city = "{city}"')
        
        if meeting_type:
            search_params['filter'].append(f'meeting_type = "{meeting_type}"')

        if date_from and date_to:
            search_params['filter'].append(f'date >= "{date_from}" AND date <= "{date_to}"')
        elif date_from:
            search_params['filter'].append(f'date >= "{date_from}"')
        elif date_to:
            search_params['filter'].append(f'date <= "{date_to}"')

        # If no filters, remove the key to avoid empty filter error
        if not search_params['filter']:
            del search_params['filter']

        results = index.search(q, search_params)
        print(f"Search for '{q}' (offset {offset}) returned {len(results['hits'])} hits")
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
