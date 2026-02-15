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

### Optional: Reindex Meilisearch only (no extraction/AI)
If you changed indexing logic (or you want to refresh search after cleaning up bad HTML in stored titles):
```bash
docker compose run --rm pipeline python reindex_only.py
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

## Local AI tuning (Gemma 3)
Default local model: Gemma 3 270M (trained for up to 32K context).

We default to a smaller context window for Docker stability/performance. Tune via env vars (worker reads them):
- `LLM_CONTEXT_WINDOW` (default `16384`, max for this model: `32768`)
- `LLM_SUMMARY_MAX_TEXT` (default `30000`)
- `LLM_SUMMARY_MAX_TOKENS` (default `512`)
- `LLM_AGENDA_MAX_TEXT` (default `60000`)

### LocalAI process model guardrail
LocalAI (llama.cpp) loads the GGUF model into the current *process*.

Celery's default prefork worker model uses multiple processes, which would duplicate the model in RAM and can OOM the host.
This repo fails fast by default if the worker is started with an unsafe pool/concurrency configuration.

Safe default (Compose):
- `--pool=solo --concurrency=1`

Override (not recommended):
- `LOCAL_AI_ALLOW_MULTIPROCESS=true`
  - Use only if you understand the memory impact (each worker process loads its own model copy).

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
- Agenda segmentation status:
  - `agenda_segmentation_status=null`: segmentation has not been attempted yet
  - `agenda_segmentation_status=empty`: attempted, but no substantive agenda items were detected
  - `agenda_segmentation_status=failed`: attempted, but task errored and is eligible for retry

Summary format:
- Stored and displayed as plain text with a `BLUF:` line and `- ` bullets (no Markdown rendering).

Agenda summary contract:
- For `Document.category == "agenda"`, summaries are derived from segmented agenda items (Structured Agenda) to avoid drift.
- If an agenda has not been segmented yet, summary generation returns `not_generated_yet` and prompts you to segment first.
- If the model output is too short or missing bullets, the system falls back to a deterministic summary built from agenda item titles.

Search behavior:
- `/search` returns meeting records only by default.
- To include agenda items as independent search hits, enable the UI toggle (**Agenda Items: On**) or set `include_agenda_items=true`.
- The UI defaults to sorting by date (newest first). Sorting requires `date` to be configured as a sortable attribute in Meilisearch.
  If you changed indexing logic or rebuilt the index from scratch, run `python reindex_only.py` to reapply settings.

Segmentation noise suppression:
- Agenda segmentation suppresses common participation template blocks (teleconference/COVID/ADA/how-to-join instructions).
- If you have old segmented items that include boilerplate, re-segment the catalog after upgrading.

Extracted text normalization:
- After extraction, we postprocess text to reduce common artifacts like spaced-letter ALLCAPS
  (`P R O C L A M A T I O N` -> `PROCLAMATION`). This improves both summaries and topics.
- Some PDFs also extract ALLCAPS headers as small chunks (for example `ANN OT AT ED` or `B ER K EL EY`).
  This is also fixed during extraction-time postprocessing, but you must **re-extract** a catalog to apply it
  to already-stored content.

Topic tagging notes:
- Per-catalog topics use TF-IDF over a bounded, same-city corpus.
- If only 1 document has extracted text (common right after startup purge), topics may be low-signal,
  but regeneration should still complete (no crashes).

### Derived status endpoint
- `GET /catalog/{catalog_id}/derived_status`
- Includes stale flags, blocked reasons, not-generated flags, and agenda segmentation status/count.

## Startup purge (dev)
When enabled, startup clears derived data for deterministic local testing.

Env controls:
- `STARTUP_PURGE_DERIVED=true|false`
- `APP_ENV=dev` (non-dev runs are blocked unless override is explicitly set)

Behavior:
- lock-protected purge (only one service executes during startup wave)
- preserves source ingest records
- extracted text (`Catalog.content`) is cleared, so Full Text will show **Not extracted yet** until re-extraction runs

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
