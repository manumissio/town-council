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

## Access URLs
- UI: [http://localhost:3000](http://localhost:3000)
- API docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Meilisearch: [http://localhost:7700](http://localhost:7700)
- Grafana: [http://localhost:3001](http://localhost:3001)
- Prometheus: [http://localhost:9090](http://localhost:9090)
- Static demo (GitHub Pages): [https://manumissio.github.io/town-council/](https://manumissio.github.io/town-council/)

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

Summary format:
- Stored and displayed as plain text with a `BLUF:` line and `- ` bullets (no Markdown rendering).

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
