# Operations Runbook

Last verified: 2026-02-12

## Core workflow

### 1) Start stack
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

### 1.5) Verify containers are using the latest image
This catches “stale image” problems early (for example, missing Python deps).

```bash
docker compose run --rm api python -c "import bs4; print('bs4', bs4.__version__)"
# The API can take a few seconds to boot. Retry a few times before assuming it's broken.
for i in {1..20}; do curl -fsS http://localhost:8000/health && break; sleep 1; done
```

### 2) Scrape
```bash
docker compose run --rm crawler scrapy crawl berkeley
docker compose run --rm crawler scrapy crawl cupertino
```

### 3) Process
```bash
docker compose run --rm pipeline python run_pipeline.py
```

## GitHub Pages static demo

The Pages build is demo-only and uses fixtures from `frontend/public/demo`.

### Local demo preview
```bash
cd frontend
NEXT_PUBLIC_DEMO_MODE=true STATIC_EXPORT=true npm run build
npx serve out
```

### CI deploy workflow
- Workflow file: `.github/workflows/pages-demo.yml`
- Trigger: push to `master` or manual dispatch
- Output: static export deployed to GitHub Pages

## Protected write endpoints
These routes require `X-API-Key`:
- `POST /summarize/{catalog_id}`
- `POST /segment/{catalog_id}`
- `POST /topics/{catalog_id}`
- `POST /extract/{catalog_id}`
- `POST /report-issue`

Docker dev default key:
- `API_AUTH_KEY=dev_secret_key_change_me`

Frontend must set:
- `NEXT_PUBLIC_API_AUTH_KEY` (for browser-triggered protected actions)

Security logging rule:
- Do not log API key values or key fragments. Log only path/client metadata on auth failures.

## Agenda QA loop

Report only:
```bash
docker compose run --rm pipeline python run_agenda_qa.py
```

Report + targeted regeneration:
```bash
docker compose run --rm pipeline python run_agenda_qa.py --regenerate --max 50
```

Outputs:
- `data/reports/agenda_qa_<timestamp>.json`
- `data/reports/agenda_qa_<timestamp>.csv`

## Re-extraction + regeneration

### Re-extract one catalog
- UI: Full Text tab -> **Re-extract text**
- API: `POST /extract/{catalog_id}?force=true&ocr_fallback=true`

### Derived-state meaning
- `stale`: derived field hash does not match current extracted text hash
- `not generated yet`: derived field is absent
- `blocked_low_signal`: source text quality below reliability gate
- `blocked_ungrounded` (summary): generated claims not sufficiently supported by source text

Summary format:
- Stored and displayed as plain text with a `BLUF:` line and `- ` bullets (no Markdown rendering).

### Derived status endpoint
- `GET /catalog/{catalog_id}/derived_status`
- Includes stale flags, blocked reasons, and not-generated flags for summary/topics/agenda.

## Startup purge (dev)
When enabled, startup clears derived data for deterministic local testing.

Env controls:
- `STARTUP_PURGE_DERIVED=true|false`
- `APP_ENV=dev` (non-dev runs are blocked unless override is explicitly set)

Behavior:
- lock-protected purge (only one service executes during startup wave)
- preserves source ingest records

## Observability quick checks

Targets should be UP:
- `town_council_monitor`
- `town_council_api`
- `town_council_worker`
- `postgres_exporter`
- `redis_exporter`
- `cadvisor`

Check:
- Prometheus targets: [http://localhost:9090/targets](http://localhost:9090/targets)

## Code scanning hygiene
- Keep captured portal snapshots and fixtures out of runtime source roots when possible.
- If a fixture triggers a scanner result but is not executable code, move it under `tests/` or explicitly exclude that fixture path in scanner configuration.
