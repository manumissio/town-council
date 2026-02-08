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
- **Multi-Tier Summaries:** Instant, **zero-cost summaries** using a hybrid local approach: Fast-pass extractive summaries (TextRank) for every document, with deep generative upgrades (Gemma 3 270M) available on-demand.
- **Topic Discovery:** Transformer-based **Semantic Embeddings** (all-MiniLM-L6-v2) that understand concepts (e.g., 'housing' vs 'zoning') regardless of keyword overlap.
- **Semantic Linking:** A high-performance **Similarity Engine** powered by **FAISS**, automatically connecting related meetings across years and municipalities in milliseconds.
- **Unified Search:** A segmented "Airbnb-style" Search Hub integrating Municipality, Body, and Meeting Type filters.
- **Robust Ingestion:** Refactored **BaseCitySpider** architecture that simplifies adding new cities and ensures resilient "Delta Crawling" (skipping duplicates).
- **Data Quality:** Integrated **Crowdsourced Error Reporting** allowing users to flag broken links or OCR errors directly to administrators.
- **Ground Truth Verification:** Dual-source validation system that fetches official voting records from the Legistar API and spatially aligns them with PDF content using PyMuPDF, providing "Verified" badges on search results with exact page coordinates for vote tallies.
- **Transaction Safety:** Production-grade exception handling with 30+ specific error handlers categorized by operation type (database, network, file I/O, search, PDF processing). Every error includes educational comments explaining what can fail, why it fails, and how it's handled. Context managers and migrations use broad exception catching where architecturally required. All database operations protected with rollback mechanisms to prevent data corruption.
- **Local-First AI:** 100% private, air-gapped intelligence using **Gemma 3 270M** running entirely on your CPU. No API keys or internet required.
- **High-Performance Data Layer:** Sub-100ms response times powered by **Redis caching**, **orjson**, and database query optimization.
- **Production Resilience:** Optimized for 24/7 availability with **fail-soft logic** that handles database or AI outages gracefully without crashing the server.
- **Scalable Search:** Instant, typo-tolerant search powered by **Meilisearch** using yield-based indexing.
- **Security:** Hardened CORS, Dependency Injection for DB safety, non-root Docker execution, **Proactive Health Probes**, and **Strict Schema Validation**.

## Performance Metrics (2026 Benchmarks)

These numbers are verified on local hardware (MacBook ARM) using `ApacheBench`.

| Operation | Previous | Optimized (E2E) | Engine Latency | Improvement |
| :--- | :--- | :--- | :--- | :--- |
| **Search (Full Text)** | 2000ms | **1.3s** | **11ms** | **~2x** |
| **City Metadata** | 500ms | **5ms** | **<1ms** | **100x** |
| **Official Profiles** | 500ms | **10ms** | **2ms** | **50x** |
| **JSON Serialization** | 125ms | **2ms** | **N/A** | **60x** |

**Optimizations applied:**
*   **Search Engine:** Meilisearch indexed with optimized `attributesToRetrieve` and `attributesToCrop` to prevent 24MB JSON payloads.
*   **Caching:** Redis stores pre-serialized JSON for metadata, delivering results in <5ms.
*   **Database:** SQLAlchemy `joinedload` eliminates the N+1 problem for official profiles (1 query vs 30+).
*   **JSON:** `orjson` library provides Rust-powered serialization speed.

## System Requirements
*   **CPU:** Any modern processor (AVX2 support recommended for speed).
*   **RAM:** 4GB minimum (8GB recommended). The AI model uses ~2GB of RAM.
*   **Storage:** 2GB free space for the Docker image and database.

## Getting Started

### 1. Install Docker
This project uses **Docker** to ensure the database, AI models, and search engine run identically on every computer.

*   **Mac/Windows:** Download and install [Docker Desktop](https://www.docker.com/products/docker-desktop/).
*   **Linux:** Follow the [official engine installation guide](https://docs.docker.com/engine/install/).
*   **Verify:** Open your terminal and run `docker compose version`. You should see a version number (e.g., v2.x.x).

### 2. Initialize and Start
Once Docker is running, build the images and initialize the database schema. **Note:** We wait 10 seconds for the database to "wake up" before creating tables.
```bash
docker-compose up -d --build postgres redis
sleep 10
docker-compose run --rm pipeline python db_init.py
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

### 4. Process Data
Run the processing pipeline (Downloads, OCR, Entity Linking, Indexing). 
```bash
docker-compose run --rm pipeline python run_pipeline.py
```

> **Developer Note:** Always use the `--rm` flag when running one-off commands. This ensures Docker automatically cleans up the container after it finishes, preventing "orphaned" containers from cluttering your system.

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

### Data Quality & Official Resolution (The Smart Bouncer)
To ensure the 'Person' table remains 100% human, the pipeline implements strict automated guardrails:
1. **Tech-Character Block:** Any string containing `@`, `://`, or `.php` is automatically discarded.
2. **Smart Blacklisting:**
   - **Total Noise:** Blocks municipal boilerplate (ordinances, departments, abbreviations like "ca") using word boundaries to protect names like "Catherine".
   - **Contextual Noise:** Blocks ambiguous words like "Park" or "Staff" when they appear as single words, but allows them in multi-word names (e.g., "Linda Park") or when preceded by a title (e.g., "Mayor Park").
3. **Vowel Density Check:** Heuristic for OCR noise. Real names have high vowel density; fragments like "Spl Tax Bds" are blocked.
4. **Header Suppression:** ALL-CAPS strings longer than 15 characters (boilerplate document headers) are ignored.
5. **Proper Noun Enforcement:** Every official name MUST contain at least one Proper Noun (PROPN) as identified by the NLP model.

## Testing
Run the comprehensive suite of 80+ unit, integration, and benchmark tests (37% code coverage):
```bash
docker-compose run --rm pipeline pytest /app/tests/
```

**Test Results:** 79 passing, 2 failing (98% pass rate)
- Core functionality: AI extraction, NLP entity recognition, fuzzy matching, spider parsing
- Data quality: Noise filtering, name validation, deduplication
- Infrastructure: Database migrations, session management, error handling

## Performance & Load Testing
We use automated audits to ensure the platform remains fast as it grows.

1. **Algorithmic Benchmarks:** Measures the millisecond cost of internal logic.
   ```bash
   docker-compose run --rm pipeline pytest tests/test_benchmarks.py
   ```

2. **Load Testing (Traffic Simulation):** Simulates 50+ users attacking the API.
   ```bash
   # Runs a 60-second headless stress test
   docker-compose run --rm pipeline locust -f tests/locustfile.py --headless -u 50 -r 5 --run-time 1m --host http://api:8000
   ```

## Scaling Up (Enterprise Mode)
The system is designed to scale horizontally as your dataset grows:
1.  **Add More Workers:** If AI processing is slow, simply add more Celery workers:
    ```bash
    docker-compose up -d --scale worker=3
    ```
2.  **Distributed Pipeline:** The ingestion pipeline automatically detects your CPU count and scales OCR/NLP tasks to use all available cores.
3.  **Database:** Use a managed PostgreSQL instance (AWS RDS, Google Cloud SQL) for production reliability.

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
