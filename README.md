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

### 2) Start stack and initialize DB
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

If sorting appears to have no effect, see the runbook section in [`docs/OPERATIONS.md`](docs/OPERATIONS.md) ("Diagnosing date sorting").

## Semantic Search (Milestone B)
Semantic search is opt-in and feature-flagged.

- Endpoint: `GET /search/semantic`
- Feature flag: `SEMANTIC_ENABLED` (default `false`)
- Backend: `SEMANTIC_BACKEND=faiss` for MVP
- Runtime engine can be `faiss` (preferred) or `numpy` (fallback when FAISS is unavailable)

Keyword search (`/search`) remains the default and is unchanged.
For setup, rebuild, diagnostics, and guardrails, use [`docs/OPERATIONS.md`](docs/OPERATIONS.md).

## Vote/Outcome Extraction (Milestone A)
Vote and outcome extraction is available as an async post-processing stage for segmented agenda items.

- Feature flag: `ENABLE_VOTE_EXTRACTION` (default `false`)
- Async endpoint: `POST /votes/{catalog_id}` (supports `force=true`)
- Storage: normalized outcome in `AgendaItem.result`, structured details in `AgendaItem.votes`

This README keeps the feature overview concise. For rollout, troubleshooting, and counter interpretation, use [`docs/OPERATIONS.md`](docs/OPERATIONS.md).

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

## Common Troubleshooting (Quick)

- Protected write actions (`/summarize`, `/segment`, `/topics`, `/extract`) require `X-API-Key`.
- If Full Text looks missing after restart, check whether `STARTUP_PURGE_DERIVED=true` and re-extract.
- If sort order looks wrong, run the “Diagnosing date sorting” flow in `docs/OPERATIONS.md`.
- If Structured Agenda is empty, run segmentation first (`POST /segment/{catalog_id}`).
- If extracted text still shows chunked ALLCAPS heading artifacts, re-extract and review extraction tuning flags in `docs/OPERATIONS.md`.
- If Structured Agenda is too noisy (TOC/procedural/contact items), review `AGENDA_SEGMENTATION_MODE` and segmentation tuning in `docs/OPERATIONS.md`.
- If Cupertino-style notice fragments leak into summaries, re-run segmentation and summary for that catalog; summary generation now applies a residual title+description safety filter.
- If table rows or subparts are showing as separate agenda items, re-run segmentation; hierarchy-aware parsing now keeps only top-level items and treats nested rows as child content.

For complete troubleshooting (auth, stale/blocked/not-generated states, startup purge, LocalAI tuning, and observability), use:
- [`docs/OPERATIONS.md`](docs/OPERATIONS.md)

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
Originally led by @chooliu and @bstarling in 2017, with early work in the Data4Democracy ecosystem.
Historical provenance for Open Civic Data division-ID discussion is captured in [Data4Democracy issue #4](https://github.com/Data4Democracy/town-council/issues/4).
The project was modernized in 2026 to improve civic transparency through structured data and local-first AI workflows.

## License
MIT. See [`LICENSE`](LICENSE).
