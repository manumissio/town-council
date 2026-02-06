import sys
import os
import logging
import meilisearch
from google import genai
from fastapi import FastAPI, HTTPException, Query, Path, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from sqlalchemy.orm import Session as SQLAlchemySession, sessionmaker

# Set up structured logging for production observability
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("town-council-api")

# Add the project root to the python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from pipeline.models import db_connect, Document, Event, Place, Catalog, Person
    engine = db_connect()
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
except ImportError:
    logger.error("Could not import pipeline models. Database features will be unavailable.")

# Security & Reliability: Dependency Injection for database sessions.
# This ensures that EVERY connection is properly closed after the request,
# preventing 'Too many connections' errors.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI(title="Town Council Search API", description="Search and retrieve local government meeting minutes.")

# AI Configuration
api_key = os.getenv('GEMINI_API_KEY')
ai_client = genai.Client(api_key=api_key) if api_key else None

# SECURITY: Restrict CORS (Cross-Origin Resource Sharing)
# Why: Standard '*' is unsafe for production. We restrict to the expected frontend port.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], # Restrict to the Next.js app
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
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
    q: str = Query(..., min_length=1, description="The search query (e.g., 'zoning')"),
    city: Optional[str] = Query(None),
    meeting_type: Optional[str] = Query(None),
    org: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100), # Security: Enforce min/max limits
    offset: int = Query(0, ge=0)
):
    """
    Search for text within meeting minutes using Meilisearch.
    """
    try:
        index = client.index('documents')
        
        search_params = {
            'limit': limit,
            'offset': offset,
            'attributesToHighlight': ['content', 'title', 'description'],
            'highlightPreTag': '<em class="bg-yellow-200 not-italic font-semibold px-0.5 rounded">',
            'highlightPostTag': '</em>',
            'filter': []
        }
        
        # Normalize city to lowercase to match the indexed display_name (e.g., 'ca_berkeley')
        if city: search_params['filter'].append(f'city = "{city.lower()}"')
        if meeting_type: search_params['filter'].append(f'meeting_category = "{meeting_type}"')
        if org: search_params['filter'].append(f'organization = "{org}"')

        if date_from and date_to:
            search_params['filter'].append(f'date >= "{date_from}" AND date <= "{date_to}"')
        elif date_from:
            search_params['filter'].append(f'date >= "{date_from}"')
        elif date_to:
            search_params['filter'].append(f'date <= "{date_to}"')

        if not search_params['filter']:
            del search_params['filter']

        results = index.search(q, search_params)
        logger.info(f"Search query='{q}' city='{city}' returned {len(results['hits'])} hits")
        return results
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail="Internal search engine error")

@app.get("/metadata")
def get_metadata():
    """
    Returns unique cities and organizations present in the search index.
    """
    try:
        index = client.index('documents')
        res = index.search("*", {'facets': ['city', 'organization']})
        
        facet_dist = res.get('facetDistribution', {})
        cities = sorted(list(facet_dist.get('city', {}).keys()))
        orgs = sorted(list(facet_dist.get('organization', {}).keys()))
        
        return {
            "cities": [c.title() for c in cities],
            "organizations": orgs
        }
    except Exception as e:
        logger.error(f"Metadata retrieval failed: {e}")
        return {"cities": [], "organizations": []}

@app.get("/people")
def list_people(limit: int = 50, db: SQLAlchemySession = Depends(get_db)):
    """
    Returns a list of identified officials.
    """
    try:
        return db.query(Person).order_by(Person.name).limit(limit).all()
    except Exception as e:
        logger.error(f"Failed to list people: {e}")
        raise HTTPException(status_code=500, detail="Database error")

@app.get("/person/{person_id}")
def get_person_history(
    person_id: int = Path(..., ge=1), 
    db: SQLAlchemySession = Depends(get_db)
):
    """
    Returns a person's full profile and roles.
    """
    person = db.get(Person, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Official not found")
    
    history = []
    # Optimization: Use joined loading in production for memberships
    for membership in person.memberships:
        history.append({
            "body": membership.organization.name,
            "city": membership.organization.place.name.title(),
            "role": membership.label or "Member"
        })
        
    return {
        "name": person.name,
        "bio": person.biography,
        "current_role": person.current_role,
        "roles": history
    }

@app.post("/summarize/{catalog_id}")
def generate_summary(
    catalog_id: int = Path(..., ge=1),
    db: SQLAlchemySession = Depends(get_db)
):
    """
    Requests an AI-generated summary for a specific document.
    """
    if not ai_client:
        raise HTTPException(status_code=503, detail="Gemini AI is not configured")

    catalog = db.get(Catalog, catalog_id)
    if not catalog:
        raise HTTPException(status_code=404, detail="Document not found")

    if catalog.summary:
        return {"summary": catalog.summary, "cached": True}

    if not catalog.content:
        raise HTTPException(status_code=400, detail="Document has no text to summarize")

    try:
        prompt = (
            "Summarize the following civic meeting notes in 3 clear bullet points. "
            "ONLY use the provided text.\n\n"
            f"TEXT: {catalog.content[:100000]}"
        )

        response = ai_client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
            config={"temperature": 0.0, "max_output_tokens": 500}
        )

        if response and response.text:
            catalog.summary = response.text.strip()
            db.commit()
            
            # Async Index Update
            try:
                meili_index = client.index('documents')
                docs_to_update = db.query(Document).filter_by(catalog_id=catalog_id).all()
                for d in docs_to_update:
                    meili_index.update_documents([{"id": d.id, "summary": catalog.summary}])
            except Exception as e:
                logger.error(f"Search sync failed: {e}")

            return {"summary": catalog.summary, "cached": False}
        
        raise HTTPException(status_code=500, detail="AI generation failed")

    except Exception as e:
        db.rollback()
        logger.error(f"Summarization error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/stats")
def get_stats():
    """
    Returns basic statistics about the search index.
    """
    try:
        return client.index('documents').get_stats()
    except Exception as e:
        logger.error(f"Stats check failed: {e}")
        raise HTTPException(status_code=503, detail="Search engine unreachable")
