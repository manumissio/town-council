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
docker compose up -d --build postgres redis
sleep 10
docker compose run --rm pipeline python db_init.py
docker compose up -d
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

## Access URLs
- UI: [http://localhost:3000](http://localhost:3000)
- API docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Meilisearch: [http://localhost:7700](http://localhost:7700)
- Grafana: [http://localhost:3001](http://localhost:3001)
- Prometheus: [http://localhost:9090](http://localhost:9090)

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

### Stale / Not generated yet / Blocked states
- **Stale**: extracted text changed after summary/topics were generated
- **Not generated yet**: derived fields not created yet (common after startup purge)
- **Blocked**: extracted text too low-signal for reliable summary/topics

### Startup purge behavior (dev)
If `STARTUP_PURGE_DERIVED=true`, startup clears derived data (summary/topics/agenda items/content hashes) for deterministic local runs while preserving source ingest records.

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
