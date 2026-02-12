# Operations Runbook

Last verified: 2026-02-12

## Core workflow

### 1) Start stack
```bash
docker compose up -d --build postgres redis
docker compose run --rm pipeline python db_init.py
docker compose up -d
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
