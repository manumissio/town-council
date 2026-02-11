# Town Council
Tools to scrape and centralize the text of meeting agendas & minutes from local city governments.

## Project Description
Engagement in local government is limited by physical access and electronic barriers, including difficult-to-navigate portals and non-searchable scanned PDF documents. This project provides a **publicly available database that automatically scrapes, extracts text (OCR), and indexes city council agendas and minutes** for transparency and cross-city trend analysis.

## Project Status (Modernized 2026)
This project has been modernized from its 2017 pilot into a high-performance accountability platform.

Key updates:
- Official profile views: search results can open person profiles with current role and organization membership history.
- Name deduplication: fuzzy matching merges near-duplicate person names during linking.
- Agenda segmentation with deep links: segmented agenda items are generated on demand and can include page links when page numbers are available.
- Shared agenda resolver: extraction follows a maintainable order of Legistar (when configured), HTML eAgenda parsing, then local LLM fallback.
- OCD-style identifiers: core civic entities use standardized IDs (for example event, person, organization, agenda item).
- Two summary paths: extractive summaries (TextRank) and local generative summaries (Gemma 3 270M) are both supported. Local summaries are doc-type aware (agenda vs minutes) so agenda PDFs do not produce misleading "minutes" summaries.
- Topic tagging and semantic similarity: TF-IDF topic tags are generated (with URL stripping to avoid junk topics like "HTTP ..."), and the UI lets you click topic chips to quickly re-run a search.
- Unified search UI: keyword, city, organization, and meeting-type filters are available in one search hub.
- Ingestion architecture: BaseCitySpider supports reusable crawl plumbing and delta-crawl behavior to reduce duplicate ingestion.
- Data issue reporting: users can submit broken-link/OCR/city issues through the UI and API.
- Ground-truth pipeline foundations: Legistar vote/action sync and PDF spatial alignment fields are implemented for verification workflows.
- Transaction and rollback safety: database writes use guarded patterns with rollback on failure paths.
- Local AI inference: summarization and segmentation run locally via llama-cpp and Gemma after model setup.
- Search and API performance tooling: Redis caching, orjson responses, Meilisearch indexing, and benchmark tests are in place.
- Resilience guardrails: health checks, task polling failure handling, and fail-soft behavior are implemented in API and worker paths.
- Security controls: CORS controls, API-key protected write endpoints, non-root first-party containers, and request validation are implemented.

## Performance Metrics (2026 Benchmarks)

### User-facing performance (end-to-end)

These numbers are from local full-stack runs on MacBook ARM using ApacheBench-style endpoint timing.

| Operation | Previous | Optimized (E2E) | Engine Latency | Improvement |
| :--- | :--- | :--- | :--- | :--- |
| Search (Full Text) | 2000ms | 1.3s | 11ms | ~2x |
| City Metadata | 500ms | 5ms | <1ms | 100x |
| Official Profiles | 500ms | 10ms | 2ms | 50x |
| JSON Serialization | 125ms | 2ms | N/A | 60x |

### Developer microbenchmarks

These numbers are from the latest local `pytest-benchmark` run on MacBook ARM (`CPython 3.14.3`), saved at `.benchmarks/Darwin-CPython-3.14-64bit/0012_264fd8cd921e79e81ee1dceae2d2e9fa43b52204_20260208_181835_uncommited-changes.json`.

| Operation | Mean Latency | Throughput | Improvement |
| :--- | :--- | :--- | :--- |
| Fuzzy Name Matching (`find_best_person_match`) | 65.56 us | 15.25 K ops/s | Baseline |
| Regex Agenda Extraction | 778.98 us | 1.28 K ops/s | Baseline |
| Standard JSON Serialization (`json.dumps`) | 157.92 us | 6.33 K ops/s | Baseline |
| Rust JSON Serialization (`orjson.dumps`) | 8.56 us | 116.84 K ops/s | ~18.5x faster than stdlib JSON |

Optimizations applied:
*   Search engine payload controls (`attributesToRetrieve` / `attributesToCrop`) reduce response size.
*   Redis caching accelerates metadata and repeated reads.
*   SQLAlchemy eager loading (`joinedload`) reduces N+1 query overhead for profiles.
*   orjson improves serialization throughput in API response paths.

## System Requirements
*   **CPU:** Any modern processor (AVX2 support recommended for speed).
*   **RAM:** 8GB minimum (16GB recommended) for the full Docker stack. Apache Tika and local AI/model workloads can exceed lightweight laptop defaults.
*   **Storage:** At least 8GB free for Docker images, model artifacts, and local database/volume data.

## Getting Started

### 1. Install Docker
This project uses **Docker** to ensure the database, AI models, and search engine run identically on every computer.

*   **Mac/Windows:** Download and install [Docker Desktop](https://www.docker.com/products/docker-desktop/).
*   **Linux:** Follow the [official engine installation guide](https://docs.docker.com/engine/install/).
*   **Verify:** Open your terminal and run `docker compose version`. You should see a version number (e.g., v2.x.x).

### 2. Initialize and Start
Once Docker is running, build the images and initialize the database schema. **Note:** We wait 10 seconds for the database to "wake up" before creating tables.

Build-time note: the image downloads local models (Hugging Face) during build, so internet access is required for the initial build. After models are present, inference is fully local.

```bash
docker compose up -d --build postgres redis
sleep 10
docker compose run --rm pipeline python db_init.py
docker compose up -d
```

### 3. Scrape a City
Gather meeting metadata and PDF links from supported municipalities:
```bash
# Scrape Berkeley, CA (Native Table)
docker compose run crawler scrapy crawl berkeley

# Scrape Cupertino, CA (Legistar API)
docker compose run crawler scrapy crawl cupertino
```

What you should see after scraping + processing:
* `http://localhost:8000/metadata` includes "Cupertino" in the `cities` list (this comes from the search index facets).
* The UI can filter/search for Cupertino and open at least one meeting.

Troubleshooting (Cupertino):
* Cupertino missing from `/metadata`:
  - Run `docker compose run --rm pipeline python seed_places.py` (ensures the `Place` row exists).
  - Run `docker compose run --rm pipeline python run_pipeline.py` again (ensures indexing happened).
* No Cupertino meetings:
  - Re-run `docker compose run --rm crawler scrapy crawl cupertino` and check crawler logs for Legistar API errors.
* Meetings exist but no text:
  - Re-run `docker compose run --rm pipeline python run_pipeline.py` (extractor/NLP/indexing runs only when fields are missing).
* Meetings exist, but "Structured Agenda" is empty (0 agenda items):
  - This is expected until segmentation is triggered (agenda items are generated on-demand).
  - Ensure the API + worker are running: `docker compose up -d api worker redis`
  - If you're calling the API directly, `/segment/{catalog_id}` requires an `X-API-Key` header:
    - Default dev key in Docker is `dev_secret_key_change_me` (set by `API_AUTH_KEY` in `docker-compose.yml`).
  - If you're using the UI, set `NEXT_PUBLIC_API_AUTH_KEY` so the browser can call protected endpoints:
    - Example: set `NEXT_PUBLIC_API_AUTH_KEY=dev_secret_key_change_me` in your `.env` before running `docker compose up -d`.
* Cupertino agenda items look low-quality:
  - Run `docker compose run --rm pipeline python seed_places.py` to ensure `Place.legistar_client` is set from the `*.legistar.com` seed URL.
  - When `Place.legistar_client` is present, the resolver can use Legistar Web API agenda items (more reliable than PDF-only parsing).

### 4. Process Data
Run the processing pipeline (Downloads, OCR, Entity Linking, Indexing). 
```bash
docker compose run --rm pipeline python run_pipeline.py
```

> **Developer Note:** Always use the `--rm` flag when running one-off commands. This ensures Docker automatically cleans up the container after it finishes, preventing "orphaned" containers from cluttering your system.

## Access Links
| Service | URL | Credentials |
| :--- | :--- | :--- |
| **Search UI** | [http://localhost:3000](http://localhost:3000) | N/A |
| **Backend API** | [http://localhost:8000/docs](http://localhost:8000/docs) | N/A |
| **Meilisearch** | [http://localhost:7700](http://localhost:7700) | `masterKey` |
| **Grafana** | [http://localhost:3001](http://localhost:3001) | set via `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` |
| **Prometheus** | [http://localhost:9090](http://localhost:9090) | N/A |

## Observability (Grafana + Prometheus)
The stack exports performance metrics so you can debug latency, errors, and worker throughput.

Checklist (targets must be UP):
1. Open Prometheus targets: `http://localhost:9090/targets`
2. Confirm scrapes are healthy:
   - `town_council_monitor` (pipeline/monitor.py gauges)
   - `town_council_api` (FastAPI `/metrics`)
   - `town_council_worker` (Celery worker task metrics)
   - `postgres_exporter`, `redis_exporter`, `cadvisor`

Reloading Prometheus config (no restart needed):
* `docker compose exec prometheus wget -qO- --post-data='' http://127.0.0.1:9090/-/reload`

Dashboards:
* Grafana is pre-provisioned from `monitoring/grafana/`.
* Dashboards live in `monitoring/grafana/dashboards/`.

## Development
The platform is built using a modular component architecture:
- **API:** FastAPI with SQLAlchemy 2.0 and dependency injection.
- **Frontend:** Next.js with specialized components in `frontend/components/` (SearchHub, ResultCard, PersonProfile).
- **Indexing:** Python stream-based batch processing for scalability.

### Officials vs Mentioned People
The pipeline now separates person records into two categories:
1. `official`: people with official evidence (for example title context like Mayor/Councilmember and membership linkage).
2. `mentioned`: names detected in text without enough evidence to treat as governing officials.

API behavior:
* `/people` returns `official` records by default.
* `/people?include_mentions=true` includes both categories for diagnostics.

This prevents noisy NLP detections from inflating the public officials list.

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
Run the full suite with coverage:
```bash
docker compose run --rm pipeline pytest --cov=. --cov-report=term /app/tests/
```

For local development, you can run targeted tests in a project virtualenv:
```bash
python3 -m venv .venv
.venv/bin/pip install -r pipeline/requirements.txt -r api/requirements.txt
.venv/bin/pip install pytest-benchmark
.venv/bin/pytest -q tests/test_downloader.py tests/test_indexer_logic.py tests/test_async_flow.py tests/test_vote_parser.py tests/test_spatial_alignment.py
```

Notes:
* Test tiers:
  * `tests/test_*pipeline*`, `tests/test_db_utils.py`, `tests/test_backfill_orgs.py`, `tests/test_verification_service.py`: pipeline reliability/unit+integration.
  * `tests/test_api.py`, `tests/test_reporting.py`: API contract and security-negative paths.
  * `tests/test_benchmarks.py`: performance regression checks.
* `tests/test_spatial_alignment.py` is integration-style and will skip if no suitable PDF is present in `data/` or if `pymupdf` is unavailable.
* `pymupdf` is required for spatial vote verification and coordinate extraction paths.
* NLP tests are deterministic in the current suite and should run in CI instead of being treated as expected skips.

## Performance & Load Testing
We use automated audits to ensure the platform remains fast as it grows.

1. **Algorithmic Benchmarks:** Measures the millisecond cost of internal logic.
   ```bash
   docker compose run --rm pipeline pytest tests/test_benchmarks.py
   ```

2. **Load Testing (Traffic Simulation):** Simulates 50+ users attacking the API.
   ```bash
   # Runs a 60-second headless stress test
   docker compose run --rm pipeline locust -f tests/locustfile.py --headless -u 50 -r 5 --run-time 1m --host http://api:8000
   ```

## Frontend Auth Header Configuration
Protected write endpoints (for example summary generation and issue reporting) only send `X-API-Key` from the frontend when `NEXT_PUBLIC_API_AUTH_KEY` is explicitly configured.

* No default API key is embedded in browser code.
* Configure this key only for trusted deployments where client-triggered protected actions are intended.

## Agenda Segmentation Reliability
To improve quality and maintainability, segmentation now uses one shared resolver in the pipeline:
1. Use Legistar agenda items first when `Place.legistar_client` is available.
2. Fallback to generic HTML agenda parsing when an `.html` agenda exists.
3. Fallback to local LLM extraction only when structured sources are unavailable.

Additional behavior:
* Cached low-quality agenda items are automatically re-generated.
* Async segmentation preserves `page_number` for deep-linking when available.
* Fallback extraction now detects page context from both `[PAGE N]` markers and inline `... Page N` headers.
* Fallback extraction suppresses speaker-roll name lists and legal boilerplate so those lines are not promoted as agenda items.
* When fallback text includes `Vote:` lines, the extracted vote outcome is stored in item `result` and shown in the Structured Agenda UI.
* Resolver code is shared by both async tasks and batch workers to avoid duplicate logic.

### Agenda QA (Quality Scoring + Targeted Regeneration)
You should not have to manually inspect every meeting to find segmentation errors.
Instead, run Agenda QA to score stored agenda items using generic signals (boilerplate,
speaker-name rolls, page-number issues, and missed `Vote:` lines).

Report only (safe):
```bash
docker compose run --rm pipeline python run_agenda_qa.py
```

Report + targeted regeneration (opt-in):
```bash
docker compose run --rm pipeline python run_agenda_qa.py --regenerate --max 50
```

Outputs:
* Reports are written to `data/reports/agenda_qa_<timestamp>.json` and `.csv`.
* Regeneration is capped and rate-limited; it only enqueues catalogs that look suspect.

### Docker Compose Note
`docker-compose.yml` was reviewed for this change set.
No service or environment changes were required because Legistar cross-check uses existing DB metadata (`place.legistar_client`) and existing API/network paths.

## Troubleshooting: Missing or Bad Extracted Text
Some PDFs have little/no selectable text (scanned documents). In those cases, extraction may return very little text unless OCR fallback is used.

The UI includes a dev/admin-only action (requires `NEXT_PUBLIC_API_AUTH_KEY`) to re-extract text for a single meeting:
* Open the meeting result.
* In the **Extracted Text** tab, click **Re-extract text**.

Notes:
* This uses the already-downloaded file on disk only (no re-download).
* OCR fallback is slower; use it only when needed.
* Re-extraction updates `catalog.content` and reindexes that single catalog so search/UI can reflect the updated text.

## Scaling Up (Enterprise Mode)
The system is designed to scale horizontally as your dataset grows:
1.  **Add More Workers:** If AI processing is slow, simply add more Celery workers:
    ```bash
    docker compose up -d --scale worker=3
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

## License
MIT. See `LICENSE`.

## Project History
Originally led by @chooliu and @bstarling in 2017. Modernized in 2026 to improve civic transparency through structured data and AI.
