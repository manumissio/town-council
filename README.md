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
docker compose up -d --build postgres redis meilisearch tika inference semantic semantic-worker api worker enrichment-worker monitor frontend
bash ./scripts/bootstrap_local_models.sh
docker compose run --rm pipeline python db_init.py
```

Optional helper (same steps, fewer flags to remember):
```bash
bash ./scripts/dev_up.sh
```

What `scripts/dev_up.sh` does:
- starts the core Docker Compose stack (with `--build`)
- bootstraps the shared local model volume
- initializes the DB schema
- runs a small smoke check (`/health`)

What it does *not* do:
- scrape any city data (no crawler runs)
- process/index documents (no `run_pipeline.py`)

Why the explicit model bootstrap exists:
- local model downloads no longer happen during Docker image builds
- rebuilds stay much faster, while model artifacts persist in a shared Docker volume
- if you skip the bootstrap step, the worker healthcheck will report the missing local Ollama model explicitly
- Python images are now split by role (`crawler`, `api`, `semantic`, `worker-live`, `worker-batch`), and semantic build work runs on its own `semantic-worker`, so targeted rebuilds only pay for the dependency family they actually use.
- `worker-live` serves the always-on Celery worker, extractor, monitor, and default `pipeline` path. `worker-batch` serves `enrichment-worker` plus the heavier batch enrichment and table/topic tooling.
- `pipeline` is now the core orchestration path. Heavy post-processing moved to `pipeline-batch`.
- `pipeline-batch`, `nlp`, `tables`, and `topics` are explicit batch tools, not part of the default stack. Run them with `docker compose run --rm pipeline-batch python run_batch_enrichment.py`, `docker compose run --rm nlp`, `docker compose run --rm tables`, `docker compose run --rm topics`, or opt into `--profile batch-tools`.
- If Docker builds fail with `no space left on device`, inspect Docker-managed storage first with `docker system df -v` or `bash ./scripts/docker_storage_report.sh`; large local data, search, and Ollama volumes can exhaust Docker Desktop storage before host disk space looks low.
- To verify the profile split itself, run `bash ./scripts/check_compose_profiles.sh`.
- Use `docker image prune -a` or `docker system prune` only as an explicit local cleanup step when you need to reclaim Docker storage.

Note on Full Text after restart:
If `STARTUP_PURGE_DERIVED=true`, extracted text is cleared from the DB on startup.
The checked-in base `docker-compose.yml` defaults this to `false`; `docker-compose.dev.yml` turns it on for dev convenience.
(`pipeline/config.py` also defaults to `false` unless env is explicitly set.)
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

Optional batch tools:
```bash
docker compose run --rm pipeline-batch python run_batch_enrichment.py
docker compose run --rm nlp
docker compose run --rm tables
docker compose run --rm topics
```

### 5) Profile the pipeline
Use this when you want end-to-end evidence before tuning runtime behavior.

Fast diagnostic run:
```bash
python scripts/profile_pipeline.py --mode triage
```

Repeatable baseline run:
```bash
python scripts/profile_pipeline.py --mode baseline --manifest profiling/manifests/<name>.txt
```

Analyze an existing profiling run:
```bash
python scripts/analyze_pipeline_profile.py --run-id <run_id>
```

Artifacts land under `experiments/results/profiling/<run_id>/` and include:
- `run_manifest.json`
- `spans.jsonl`
- `summary.json`
- `top_bottlenecks.md`

Interpretation:
- `triage` runs are diagnostic and optimized for speed.
- `baseline` runs use a pinned manifest and are the only profiling runs that should be compared directly over time.
- queue wait is tracked separately from task execution so the report can distinguish worker backlog from slow execution.

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
  - enables trends endpoints and trends UI surfaces
  - lineage read endpoints remain available independently
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
docker compose --env-file env/profiles/m5_conservative.env up -d --build inference worker api pipeline frontend
docker compose --env-file env/profiles/desktop_balanced.env up -d --build inference worker api pipeline frontend
```

Historical reference:
- `env/profiles/m1_conservative.env` remains available for reproducing older M1 Pro baseline runs.

## Runtime Modes
- Local default:
  - required path for all contributors
  - all tracked defaults target local compose services
  - the default Docker Compose stack uses `LOCAL_AI_BACKEND=http` with a prefork worker (`WORKER_POOL=prefork`, `WORKER_CONCURRENCY=3`)
- Soak baseline mode:
  - use local baseline profile and keep run conditions consistent day-to-day
  - do not mix optional remote acceleration into baseline soak windows
- Optional personal remote acceleration:
  - explicit opt-in only
  - fail-fast when the remote inference target is unreachable
  - not required for contributors and not used by shared default commands

### Optional Personal Offload
- Use this only for personal development acceleration.
- Keep contributor setup local-first.
- Do not rely on silent fallback between remote and local inference modes.

Current compose default:
- The checked-in `docker-compose.yml` defaults to the HTTP inference backend (`LOCAL_AI_BACKEND=http`) and starts the worker as `prefork` with concurrency `3`.
- `LOCAL_AI_BACKEND=inprocess` remains supported, but it is an explicit alternative mode that should run with stricter worker settings (`WORKER_POOL=solo`, `WORKER_CONCURRENCY=1`).
- That is a local-first default because the HTTP inference service is part of the local Compose stack, not a required remote dependency.

For detailed rollout status, milestones, and policy:
- [`ROADMAP.md`](ROADMAP.md)
- [`docs/OPERATIONS.md`](docs/OPERATIONS.md)
- [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md)
- [`docs/city-onboarding-status.md`](docs/city-onboarding-status.md)

City onboarding truth:
- use [`docs/OPERATIONS.md`](docs/OPERATIONS.md) for the runnable onboarding flow and artifact commands
- use [`docs/city-onboarding-status.md`](docs/city-onboarding-status.md) for current city-by-city rollout status and latest verified run IDs
- use [`city_metadata/city_rollout_registry.csv`](city_metadata/city_rollout_registry.csv) as the machine-readable source of rollout wave membership and enabled-city state

Canonical initiative names:
- Decision Integrity
- Hybrid Semantic Discovery
- Issue Threads Foundation
- Inference Decoupling & Throughput Stabilization
- City Coverage Expansion I/II
- Signal Intelligence
- Civic Alerts & Subscriptions

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
- Start here for architecture intent and system boundaries: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Use the runnable operator procedures and troubleshooting guide: [`docs/OPERATIONS.md`](docs/OPERATIONS.md)
- Use the pipeline deep-dive for batch + async behavior details: [`docs/PIPELINE.md`](docs/PIPELINE.md)
- Use rollout and milestone status: [`ROADMAP.md`](ROADMAP.md)
- Use city rollout truth and latest onboarding evidence: [`docs/city-onboarding-status.md`](docs/city-onboarding-status.md)
- Use reproducibility and performance notes: [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md)
- Use contributor guidance for new crawlers: [`docs/CONTRIBUTING_CITIES.md`](docs/CONTRIBUTING_CITIES.md)
- Use repo policy and collaboration constraints: [`AGENTS.md`](AGENTS.md)

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
