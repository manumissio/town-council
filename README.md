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
(`pipeline/config.py` defaults to `false` outside Compose unless env is explicitly set.)
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

## Feature Flags (Quick Reference)
- `SEMANTIC_ENABLED` + `SEMANTIC_BACKEND=faiss|pgvector`:
  - enables semantic retrieval paths (`/search/semantic`, optional `/search?semantic=true`)
- `ENABLE_VOTE_EXTRACTION`:
  - enables async vote extraction (`POST /votes/{catalog_id}`)
- `FEATURE_TRENDS_DASHBOARD`:
  - enables trends/lineage read endpoints and UI surfaces
- `LOCAL_AI_BACKEND=inprocess|http`:
  - switches LocalAI transport mode
- `LOCAL_AI_HTTP_PROFILE=conservative|balanced`:
  - selects HTTP inference runtime profile
- timeout overrides (optional):
  - `LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS`
  - `LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS`
  - `LOCAL_AI_HTTP_TIMEOUT_TOPICS_SECONDS`

Runtime profile commands:
```bash
docker compose --env-file env/profiles/m1_conservative.env up -d --build inference worker api pipeline frontend
docker compose --env-file env/profiles/desktop_balanced.env up -d --build inference worker api pipeline frontend
```

For detailed rollout status, milestones, and policy:
- [`ROADMAP.md`](ROADMAP.md)
- [`docs/OPERATIONS.md`](docs/OPERATIONS.md)
- [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md)
- [`docs/city-onboarding-status.md`](docs/city-onboarding-status.md)

Canonical milestone names (legacy aliases in `ROADMAP.md`):
- Decision Integrity (`A`)
- Hybrid Semantic Discovery (`B`)
- Issue Threads Foundation (`C v1`)
- Inference Decoupling & Throughput Stabilization (`D2-lite`)
- City Coverage Expansion I/II (`Wave 1` / `Wave 2`)
- Signal Intelligence (`C2`)
- Civic Alerts & Subscriptions (`D1`)

Model A/B tooling:
- `scripts/setup_ollama_270m.sh`
- `scripts/run_ab_eval.sh`
- `scripts/collect_ab_results.py`
- `scripts/score_ab_results.py`
- `scripts/sample_ab_manual_review.py`

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
- If AI Summary looks like title regurgitation, re-run segmentation and summary for that catalog; agenda summaries now use a structured decision-brief scaffold with grounding/pruning and deterministic fallback.
- Large agendas may be partially summarized to stay within local model context limits; AI Summary discloses partial coverage in the `Unknowns` section.
- If table rows or subparts are showing as separate agenda items, re-run segmentation; hierarchy-aware parsing now keeps only top-level items and treats nested rows as child content.

For complete troubleshooting (auth, stale/blocked/not-generated states, startup purge, LocalAI tuning, and observability), use:
- [`docs/OPERATIONS.md`](docs/OPERATIONS.md)

## Documentation Map
- Roadmap / milestone status: [`ROADMAP.md`](ROADMAP.md)
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
