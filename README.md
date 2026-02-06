# Town Council
Tools to scrape and centralize the text of meeting agendas & minutes from local city governments.

## Project Description
Engagement in local government is limited by physical access and electronic barriers, including difficult-to-navigate portals and non-searchable scanned PDF documents. This project provides a **publicly available database that automatically scrapes, extracts text (OCR), and indexes city council agendas and minutes** for transparency and cross-city trend analysis.

## Project Status (Modernized 2026)
This project has been modernized from its 2017 pilot into a high-performance accountability platform.

**Key Updates:**
- **Accountability Hub:** Clickable **Official Profiles** showing full legislative history and committee assignments.
- **Fuzzy Matching:** Traditional AI (string math) to automatically merge similar names (e.g., "J. Smith" and "John Smith") into a single official profile.
- **Deep-Linking:** AI-segmented **Agenda Items** that take you directly to specific discussions within large documents.
- **Interoperability:** Standardized **OCD-IDs** for all entities, allowing data federation with other civic platforms.
- **Multi-Tier Summaries:** Instant, **zero-cost extractive summaries** for every document (Local AI), with optional on-demand generative upgrades (Cloud AI).
- **Topic Discovery:** Statistical **TF-IDF tagging** that identifies unique discussion topics (e.g., "Rent Control", "ADUs") for every meeting automatically.
- **Unified Search:** A segmented "Airbnb-style" Search Hub integrating Municipality, Body, and Meeting Type filters.
- **On-Demand AI:** Instant 3-bullet summaries using **Gemini 2.0 Flash** with automatic database caching.
- **Scalable Search:** Instant, typo-tolerant search powered by **Meilisearch** using yield-based indexing.
- **Security:** Hardened CORS, Dependency Injection for DB safety, and non-root Docker execution.

## Getting Started

### 1. Build and Start
Ensure you have Docker installed, then build the optimized multi-stage images:
```bash
docker-compose build
docker-compose up -d
```

### 2. Scrape a City
Gather meeting metadata and PDF links from supported municipalities:
```bash
# Scrape Berkeley, CA (Native Table)
docker-compose run crawler scrapy crawl berkeley

# Scrape Cupertino, CA (Legistar API)
docker-compose run crawler scrapy crawl cupertino
```

### 3. Process Data
Run the processing pipeline (Downloads, OCR, Entity Linking, Indexing). 
```bash
docker-compose run pipeline python run_pipeline.py
```

## Access Links
| Service | URL | Credentials |
| :--- | :--- | :--- |
| **Search UI** | [http://localhost:3000](http://localhost:3000) | N/A |
| **Backend API** | [http://localhost:8000/docs](http://localhost:8000/docs) | N/A |
| **Meilisearch** | [http://localhost:7700](http://localhost:7700) | `masterKey` |
| **Grafana** | [http://localhost:3001](http://localhost:3001) | `admin` / `admin` |

## Development
The platform is built using a modular component architecture:
- **API:** FastAPI with SQLAlchemy 2.0 and dependency injection.
- **Frontend:** Next.js with specialized components in `frontend/components/` (SearchHub, ResultCard, PersonProfile).
- **Indexing:** Python stream-based batch processing for scalability.

## Testing
Run the comprehensive suite of 25+ unit tests:
```bash
docker-compose run pipeline pytest /app/tests/
```

## Project History
Originally led by @chooliu and @bstarling in 2017. Modernized in 2026 to improve civic transparency through structured data and AI.