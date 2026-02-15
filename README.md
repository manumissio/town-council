# Town Council

Search, inspect, and analyze local government meeting records from multiple cities.

This project ingests agendas/minutes, extracts text, indexes search content, and provides UI workflows for:
- Full-text search
- Structured agenda segmentation
- Local-AI summaries
- Topic tagging
- Official profile browsing

## Quickstart

### 1) Prerequisites
- Docker Desktop (Mac/Windows) or Docker Engine (Linux)
- `docker compose`

### 2) Start core services and initialize DB
```bash
docker compose up -d --build
docker compose run --rm pipeline python db_init.py
```

Optional helper (same steps, fewer flags to remember):
```bash
bash ./scripts/dev_up.sh
```

What `scripts/dev_up.sh` does:
- starts the Docker Compose stack (with `--build`)
- initializes the DB schema
- runs a small smoke check (`/health`)

What it does *not* do:
- scrape any city data (no crawler runs)
- process/index documents (no `run_pipeline.py`)

Note on Full Text after restart:
If `STARTUP_PURGE_DERIVED=true` (default in this repo’s `docker-compose.yml`), extracted text is cleared from the DB on startup.
The UI Full Text tab pulls canonical text from Postgres (`/catalog/{id}/content`), so it may show **Not extracted yet** until you click **Re-extract text** for that record.

### 2.5) Verify containers are using the latest image
This catches “stale image” problems early (for example, missing Python deps).

```bash
docker compose run --rm api python -c "import bs4; print('bs4', bs4.__version__)"
# The API can take a few seconds to boot. Retry a few times before assuming it's broken.
for i in {1..20}; do curl -fsS http://localhost:8000/health && break; sleep 1; done
```

### 3) Scrape a city
```bash
# Berkeley (native table crawler)
docker compose run --rm crawler scrapy crawl berkeley

# Cupertino (Legistar API crawler)
docker compose run --rm crawler scrapy crawl cupertino
```

### 4) Process + index
```bash
docker compose run --rm pipeline python run_pipeline.py
```

### Optional: Reindex Meilisearch only (no extraction/AI)
If you changed indexing logic (or want to refresh search results without re-running the full pipeline):
```bash
docker compose run --rm pipeline python reindex_only.py
```

## Access URLs
- UI: [http://localhost:3000](http://localhost:3000)
- API docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Meilisearch: [http://localhost:7700](http://localhost:7700)
- Grafana: [http://localhost:3001](http://localhost:3001)
- Prometheus: [http://localhost:9090](http://localhost:9090)
- Static demo (GitHub Pages): [https://manumissio.github.io/town-council/](https://manumissio.github.io/town-council/)

## Search Behavior (Meetings vs Agenda Items)
Search results default to **meeting records only**. This avoids confusing “agenda item” hits that look like separate meetings.

If you want agenda items to appear as separate search hits, toggle **Agenda Items: On** in the UI (it sets `include_agenda_items=true` on `/search`).

## Sorting Search Results
The UI defaults to **Newest** first (date descending). Use the **Sort** pill to cycle:
- Newest
- Oldest
- Relevance

## GitHub Pages Demo

The Pages site is a static product demo powered by local JSON fixtures.

- No backend/API/DB required
- No write actions (summarize/segment/topics/extract/report)
- Intended for walkthroughs, not live production data

Local demo build:
```bash
cd frontend
NEXT_PUBLIC_DEMO_MODE=true STATIC_EXPORT=true npm run build
npx serve out
```

## Common Troubleshooting

### 401 on summary/segment/topics/extract
Protected write endpoints require `X-API-Key`.

- Backend key (Docker default): `dev_secret_key_change_me`
- Frontend must set `NEXT_PUBLIC_API_AUTH_KEY` to call protected actions from browser.
- Unauthorized requests are logged without storing API key values or key fragments.

### Structured Agenda is empty
This is expected until segmentation runs.

- UI: click **Segment Agenda Items**
- API: `POST /segment/{catalog_id}` with API key

### Text looks bad or too short
Use **Re-extract text** in Full Text tab.

- Uses existing downloaded file only (no re-download)
- OCR fallback is slower and optional
- Re-extraction updates `catalog.content` and reindexes that catalog

Note: the `pipeline` Docker image does not include `curl`. Run health checks from your host shell, or use Python inside a container:
```bash
docker compose run --rm pipeline python - <<'PY'
import urllib.request
print(urllib.request.urlopen("http://api:8000/health", timeout=5).read().decode())
PY
```

### Stale / Not generated yet / Blocked states
- **Stale**: extracted text changed after summary/topics were generated
- **Not generated yet**: derived fields not created yet (common after startup purge)
- **Blocked**: extracted text too low-signal for reliable summary/topics
- **Agenda empty**: agenda segmentation ran but detected 0 substantive agenda items (no infinite reprocessing)

### Segmentation includes teleconference/ADA/COVID boilerplate
If structured agenda items look like participation instructions (teleconference/COVID/ADA text), re-run segmentation after upgrading.
The agenda extractor now suppresses common template boilerplate blocks so they do not become agenda items.

Summary format:
- Stored and displayed as plain text with a `BLUF:` line and `- ` bullets (no Markdown rendering).

Agenda summary contract:
- For `Document.category == "agenda"`, summaries are derived from segmented agenda items (Structured Agenda).
- If an agenda has not been segmented yet, summary generation returns `not_generated_yet` and prompts you to segment first.

### Startup purge behavior (dev)
If `STARTUP_PURGE_DERIVED=true`, startup clears derived data (summary/topics/agenda items/content hashes) for deterministic local runs while preserving source ingest records.

### Local AI context + input limits
The default local model is Gemma 3 270M (trained for up to 32K context). We default to a smaller context window for Docker stability/performance.

You can tune these via env vars (worker reads them):
- `LLM_CONTEXT_WINDOW` (default `16384`, max for this model: `32768`)
- `LLM_SUMMARY_MAX_TEXT` (default `30000`)
- `LLM_SUMMARY_MAX_TOKENS` (default `512`)
- `LLM_AGENDA_MAX_TEXT` (default `60000`)

Local dev memory guardrail:
- Keep the Celery worker single-process (Compose uses `--concurrency=1 --pool=solo`). Higher concurrency can load multiple model copies into RAM.

## Documentation Map
- Operations runbook: [`docs/OPERATIONS.md`](docs/OPERATIONS.md)
- Performance metrics + reproducibility: [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md)
- Adding a new city crawler: [`docs/CONTRIBUTING_CITIES.md`](docs/CONTRIBUTING_CITIES.md)
- System architecture: [`ARCHITECTURE.md`](ARCHITECTURE.md)

## Documentation Maintenance Checklist
Update docs when you change:
1. API routes or auth requirements (`api/main.py`)
2. Docker service/env wiring (`docker-compose.yml`)
3. Startup purge, stale/not-generated, or blocked-state behavior
4. Quickstart commands or required dependencies

## Project History
Originally led by @chooliu and @bstarling in 2017. Modernized in 2026 to improve civic transparency through structured data and local-first AI workflows.

## License
MIT. See [`LICENSE`](LICENSE).
