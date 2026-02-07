import sys
import os
import logging
import meilisearch
from fastapi import FastAPI, HTTPException, Query, Path, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as SQLAlchemySession, sessionmaker

# Set up structured logging for production observability
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("town-council-api")

# Add the project root to the python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from pipeline.models import db_connect, Document, Event, Place, Catalog, Person, AgendaItem, DataIssue, IssueType
    from pipeline.utils import generate_ocd_id
    from pipeline.llm import LocalAI
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

# Initialize Local AI (Singleton)
# This loads the model into RAM once when the API starts.
local_ai = LocalAI()

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
        res = index.search("", {
            "facets": ["city", "organization", "meeting_category"],
            "limit": 0
        })
        
        facets = res.get('facetDistribution', {})
        cities = sorted([c.replace("ca_", "").replace("_", " ").title() for c in facets.get('city', {}).keys()])
        orgs = sorted(list(facets.get('organization', {}).keys()))
        types = sorted(list(facets.get('meeting_category', {}).keys()))
        
        return {
            "cities": cities,
            "organizations": orgs,
            "meeting_types": types
        }
    except Exception as e:
        logger.error(f"Metadata retrieval failed: {e}")
        return {"cities": [], "organizations": [], "meeting_types": []}

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

@app.get("/catalog/batch")
def get_catalogs_batch(
    ids: List[int] = Query(...),
    db: SQLAlchemySession = Depends(get_db)
):
    """
    Returns a list of meeting summaries for multiple IDs.
    Used to display 'Related Meetings' links.
    """
    records = db.query(Catalog, Document, Event, Place).join(
        Document, Document.catalog_id == Catalog.id
    ).join(
        Event, Document.event_id == Event.id
    ).join(
        Place, Document.place_id == Place.id
    ).filter(Catalog.id.in_(ids)).all()
    
    results = []
    for cat, doc, event, place in records:
        results.append({
            "id": cat.id,
            "filename": cat.filename,
            "title": event.name,
            "date": event.record_date.isoformat() if event.record_date else None,
            "city": place.display_name or place.name
        })
    return results

@app.post("/summarize/{catalog_id}")
def generate_summary(
    catalog_id: int = Path(..., ge=1),
    db: SQLAlchemySession = Depends(get_db)
):
    """
    Requests an AI-generated summary for a specific document.
    
    Updated: Now uses LocalAI (Gemma 3 270M) running on the CPU.
    """
    catalog = db.get(Catalog, catalog_id)
    if not catalog:
        raise HTTPException(status_code=404, detail="Document not found")

    if catalog.summary:
        return {"summary": catalog.summary, "cached": True}

    if not catalog.content:
        raise HTTPException(status_code=400, detail="Document has no text to summarize")

    try:
        # Use the local model to generate the summary
        summary_text = local_ai.summarize(catalog.content)

        if summary_text:
            catalog.summary = summary_text.strip()
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
        
        raise HTTPException(status_code=500, detail="AI generation returned empty text")

    except Exception as e:
        db.rollback()
        logger.error(f"Summarization error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/segment/{catalog_id}")
def segment_agenda(
    catalog_id: int = Path(..., ge=1),
    db: SQLAlchemySession = Depends(get_db)
):
    """
    On-Demand AI Worker: Splits a large document into structured agenda items.
    
    Updated: Now uses LocalAI (Gemma 3 270M) to extract JSON from text.
    """
    catalog = db.get(Catalog, catalog_id)
    if not catalog:
        raise HTTPException(status_code=404, detail="Document not found")

    # 1. Check if we already have these items saved (Caching)
    existing_items = db.query(AgendaItem).filter_by(catalog_id=catalog_id).order_by(AgendaItem.order).all()
    if existing_items:
        return {"items": [
            {
                "title": i.title, 
                "description": i.description, 
                "classification": i.classification, 
                "result": i.result,
                "order": i.order
            } for i in existing_items
        ], "cached": True}

    if not catalog.content:
        raise HTTPException(status_code=400, detail="Document has no text to segment")

    # 2. Get the associated meeting so we can link the items correctly
    doc_link = db.query(Document).filter_by(catalog_id=catalog_id).first()
    if not doc_link:
        raise HTTPException(status_code=400, detail="Document is not linked to a meeting")

    try:
        # 3. Call Local AI to extract JSON items
        items_data = local_ai.extract_agenda(catalog.content)

        if items_data:
            for data in items_data:
                # Validate the item has a title before saving
                if not data.get('title'):
                    continue
                    
                item = AgendaItem(
                    ocd_id=generate_ocd_id('agendaitem'),
                    event_id=doc_link.event_id,
                    catalog_id=catalog_id,
                    order=data.get('order'),
                    title=data.get('title', 'Untitled Item'),
                    description=data.get('description'),
                    classification=data.get('classification'),
                    result=data.get('result')
                )
                db.add(item)
            
            db.commit()
            return {"items": items_data, "cached": False}
        
        raise HTTPException(status_code=500, detail="AI segmentation failed to return valid JSON")

    except Exception as e:
        db.rollback()
        logger.error(f"Segmentation error: {e}")
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

# --------------------------------------------------------------------------
# DATA QUALITY REPORTING (FEEDBACK LOOP)
# --------------------------------------------------------------------------

class IssueReport(BaseModel):
    """
    Schema for the data quality report submitted by the user.
    """
    event_id: int = Field(..., description="The ID of the meeting being reported")
    issue_type: str = Field(..., description="The type of problem (e.g., 'broken_link')")
    description: Optional[str] = Field(None, max_length=500, description="Optional details about the issue")

@app.post("/report-issue")
def report_data_issue(report: IssueReport, db: SQLAlchemySession = Depends(get_db)):
    """
    Allows users to report errors in the data (e.g., broken links, OCR errors).
    
    Novice Developer Note:
    This function validates the report, checks if the meeting actually exists,
    and then saves the report to the 'data_issue' table for an admin to review.
    """
    # 1. Validation: Does the meeting actually exist in our database?
    event = db.query(Event).filter(Event.id == report.event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # 2. Validation: Is the issue type one we recognize?
    valid_types = [t.value for t in IssueType]
    if report.issue_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid issue_type. Must be one of: {valid_types}")

    # 3. Save the report
    try:
        new_issue = DataIssue(
            event_id=report.event_id,
            issue_type=report.issue_type,
            description=report.description
        )
        db.add(new_issue)
        db.commit()
        
        logger.info(f"User reported an issue for event {report.event_id}: {report.issue_type}")
        return {"status": "success", "message": "Thank you for your report. Our team will review it."}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save data issue: {e}")
        raise HTTPException(status_code=500, detail="Internal server error while saving report")