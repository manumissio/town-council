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
- **Topic Discovery:** Transformer-based **Semantic Embeddings** (all-MiniLM-L6-v2) that understand concepts (e.g., 'housing' vs 'zoning') regardless of keyword overlap.
- **Semantic Linking:** A high-performance **Similarity Engine** powered by **FAISS**, automatically connecting related meetings across years and municipalities in milliseconds.
- **Unified Search:** A segmented "Airbnb-style" Search Hub integrating Municipality, Body, and Meeting Type filters.
- **Robust Ingestion:** Refactored **BaseCitySpider** architecture that simplifies adding new cities and ensures resilient "Delta Crawling" (skipping duplicates).
- **Data Quality:** Integrated **Crowdsourced Error Reporting** allowing users to flag broken links or OCR errors directly to administrators.
- **Local-First AI:** Zero-cost, private AI summaries using **Gemma 3 270M** running entirely on your CPU. No API keys required.
- **Scalable Search:** Instant, typo-tolerant search powered by **Meilisearch** using yield-based indexing.
- **Security:** Hardened CORS, Dependency Injection for DB safety, and non-root Docker execution.

## System Requirements
*   **CPU:** Any modern processor (AVX2 support recommended for speed).
*   **RAM:** 4GB minimum (8GB recommended). The AI model uses ~200MB of RAM.
*   **Storage:** 2GB free space for the Docker image and database.

## Getting Started

### 1. Install Docker
This project uses **Docker** to ensure the database, AI models, and search engine run identically on every computer.

*   **Mac/Windows:** Download and install [Docker Desktop](https://www.docker.com/products/docker-desktop/).
*   **Linux:** Follow the [official engine installation guide](https://docs.docker.com/engine/install/).
*   **Verify:** Open your terminal and run `docker compose version`. You should see a version number (e.g., v2.x.x).

### 2. Build and Start
Once Docker is running, build the optimized multi-stage images:
```bash
docker-compose build
docker-compose up -d
```

### 3. Scrape a City
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

## How to Add a New City
Adding a new municipality is now easy thanks to the **BaseCitySpider** architecture. You only need to define the "where" and "how to find" logic.

1. **Create a new file** in `council_crawler/council_crawler/spiders/ca_cityname.py`.
2. **Inherit from `BaseCitySpider`**:
```python
from .base import BaseCitySpider

class MyCitySpider(BaseCitySpider):
    name = 'mycity'
    # Follow the OCD-ID standard format
    ocd_division_id = 'ocd-division/country:us/state:ca/place:mycity'

    def start_requests(self):
        # Tell the spider where to start looking
        yield scrapy.Request(url='http://mycity.gov/meetings', callback=self.parse)

    def parse(self, response):
        # The Base class handles database checks and skipping old meetings.
        # You only need to write the logic to find the <tr> rows.
        for row in response.xpath('//tr'):
            # ... extraction logic ...
            yield self.create_event_item(
                meeting_date=date,
                meeting_name="City Council",
                source_url=response.url,
                documents=docs
            )
```

## Project History
Originally led by @chooliu and @bstarling in 2017. Modernized in 2026 to improve civic transparency through structured data and AI.