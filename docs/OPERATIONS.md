# Operations Runbook

Last verified: 2026-02-16

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
- `POST /votes/{catalog_id}`
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

## Semantic Search (Milestone B)

Semantic search is additive and disabled by default.

### Enable
Set:
- `SEMANTIC_ENABLED=true`
- `SEMANTIC_BACKEND=faiss`

### Build semantic artifacts
```bash
docker compose run --rm pipeline python reindex_semantic.py
```

### Verify FAISS runtime availability
```bash
docker compose run --rm pipeline python check_faiss_runtime.py
```

### Diagnose semantic search
```bash
docker compose run --rm pipeline python diagnose_semantic_search.py --query zoning --limit 10
```

### Common failures
- `503 Semantic search is disabled`:
  - enable `SEMANTIC_ENABLED=true`.
- `503 Semantic index artifacts are missing`:
  - run `python reindex_semantic.py`.
- semantic mode returns too few records with strict filters:
  - check `semantic_diagnostics` fields (`k_used`, `expansion_steps`) in response.
- semantic mode works but is slower than expected:
  - check `semantic_diagnostics.engine`; `numpy` means fallback mode (FAISS unavailable in runtime).
  - fix FAISS install/import, then rebuild artifacts with `python reindex_semantic.py`.

### Guardrail note
FAISS + sentence-transformers memory is process-local. Keep single-process runtime
unless you intentionally override:
- `SEMANTIC_REQUIRE_SINGLE_PROCESS=true` (default)
- `SEMANTIC_ALLOW_MULTIPROCESS=false` (default)

Optional strict mode:
- `SEMANTIC_REQUIRE_FAISS=true`
  - fail fast if `faiss-cpu` is missing instead of using NumPy fallback.

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

## Agenda Segmentation Precision Tuning

Segmentation precision is configurable and defaults to balanced behavior.

### Mode
- `AGENDA_SEGMENTATION_MODE=balanced|aggressive|recall` (default `balanced`)
  - `balanced`: default precision/recall tradeoff
  - `aggressive`: stronger filtering for procedural/contact/TOC-like noise
  - `recall`: looser filtering when documents are sparse/irregular

### Supporting thresholds
- `AGENDA_MIN_TITLE_CHARS` (default `10`)
- `AGENDA_MIN_SUBSTANTIVE_DESC_CHARS` (default `24`, LLM-parsed descriptions only)
- `AGENDA_TOC_DEDUP_FUZZ` (default `92`, per-document title dedupe threshold)
- `AGENDA_PROCEDURAL_REJECT_ENABLED` (default `true`)

### Re-segment after tuning
```bash
curl -X POST "http://localhost:8000/segment/<CATALOG_ID>?force=true" \
  -H "X-API-Key: dev_secret_key_change_me"
```

Notes:
- TOC/body dedupe runs only within the current document extraction set.
- Procedural filtering uses exact/anchored phrases to avoid dropping substantive titles such as contract approvals.
- Fallback parsing rejects numbered lowercase line fragments (for example `16. in the appropriate...`) by checking the first alphabetical character, not the first character.
- Agenda summary generation now builds a structured decision brief from segmented agenda items:
  - deterministic scaffold (`BLUF`, `Why this matters`, `Top actions`, `Potential impacts`, `Unknowns`)
  - constrained LLM synthesis
  - grounding/pruning of unsupported lines
  - deterministic fallback when synthesis is weak.
- Parent-item context now carries across page boundaries, so sub-markers (`A.`, `1a.`, `i.`) after a page break are still treated as nested content.
- Tabular-fragment rejection is weighted: low alpha density is the primary signal; whitespace artifacts are auxiliary only.
- End-of-agenda stop uses composite evidence (legal/attestation tail). `Adjournment` alone does not terminate parsing.

## Vote/Outcome Extraction (Milestone A)

Vote extraction is an optional async stage that runs on segmented agenda items.

### Enable the stage
Set:
- `ENABLE_VOTE_EXTRACTION=true`

Default is `false` for staged rollout.

### Trigger one catalog
```bash
curl -X POST "http://localhost:8000/votes/<CATALOG_ID>" \
  -H "X-API-Key: dev_secret_key_change_me"
```

Force run (bypasses feature-flag gate and high-confidence LLM idempotency):
```bash
curl -X POST "http://localhost:8000/votes/<CATALOG_ID>?force=true" \
  -H "X-API-Key: dev_secret_key_change_me"
```

Poll:
```bash
curl "http://localhost:8000/tasks/<TASK_ID>" \
  -H "X-API-Key: dev_secret_key_change_me"
```

### Expected task result counters
- `processed_items`: items sent to the extractor
- `updated_items`: items persisted with new vote/outcome data
- `skipped_items`: items intentionally not processed or not persisted
- `failed_items`: extraction/parse failures
- `skip_reasons`: reason histogram, commonly:
  - `trusted_source` (`manual`/`legistar` source preserved)
  - `existing_result` (non-unknown result already present)
  - `already_high_confidence` (idempotency for prior LLM extraction)
  - `insufficient_text` (below minimum context threshold)
  - `low_confidence`
  - `unknown_no_tally`

### Source hierarchy (non-negotiable)
- `manual > legistar > llm_extracted`
- LLM extraction never overwrites trusted vote sources.

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
- Stored and displayed as plain text in sectioned decision-brief format (no Markdown rendering):
  - `BLUF:`
  - `Why this matters:`
  - `Top actions:`
  - `Potential impacts:`
  - `Unknowns:`

Agenda summary contract:
- For `Document.category == "agenda"`, summaries are derived from segmented agenda items (Structured Agenda) to avoid drift.
- Agenda summary input uses structured fields (`title`, `description`, `classification`, `result`, `page_number`) and is hard-capped for context safety.
- If input is truncated for context budget, summary output discloses partial coverage (`first N of M agenda items`) in `Unknowns`.
- If an agenda has not been segmented yet, summary generation returns `not_generated_yet` and prompts you to segment first.
- If model output is too short/noncompliant/ungrounded, the system falls back to deterministic decision-brief output.
- Existing catalogs do not update retroactively. Re-run both steps after tuning:
  - `POST /segment/{catalog_id}?force=true`
  - `POST /summarize/{catalog_id}?force=true`

Search behavior:
- `/search` returns meeting records only by default.
- To include agenda items as independent search hits, enable the UI toggle (**Agenda Items: On**) or set `include_agenda_items=true`.
- The UI defaults to sorting by date (newest first). Sorting requires `date` to be configured as a sortable attribute in Meilisearch.
  If you changed indexing logic or rebuilt the index from scratch, run `python reindex_only.py` to reapply settings.

### Diagnosing date sorting
If Newest/Oldest/Relevance look identical, treat it as a diagnostics problem first (don’t guess).

1. Reapply Meilisearch settings + reindex:
```bash
docker compose run --rm pipeline python reindex_only.py
```

2. Print evidence for all sort modes:
```bash
docker compose run --rm pipeline python diagnose_search_sort.py --query zoning --limit 10
```

Notes:
- In Docker, the script uses `http://api:8000` by default.
- On host, use `--base-url http://localhost:8000`.
- If sort order is still wrong after `reindex_only.py`, inspect `/search` sort handling and current Meilisearch index settings.

Segmentation noise suppression:
- Agenda segmentation suppresses common participation template blocks (teleconference/COVID/ADA/how-to-join instructions).
- If you have old segmented items that include boilerplate, re-segment the catalog after upgrading.

Extracted text normalization:
- After extraction, we postprocess text to reduce common artifacts like spaced-letter ALLCAPS
  (`P R O C L A M A T I O N` -> `PROCLAMATION`). This improves both summaries and topics.
- Some PDFs also extract ALLCAPS headers as small chunks (for example `ANN OT AT ED` or `B ER K EL EY`).
  This is also fixed during extraction-time postprocessing, but you must **re-extract** a catalog to apply it
  to already-stored content.
- Optional extraction tuning (off by default) for kerning-heavy PDFs:
  - `TIKA_PDF_SPACING_TOLERANCE`
  - `TIKA_PDF_AVG_CHAR_TOLERANCE`
- Optional LLM escalation (off by default) if deterministic repair still leaves implausible lines:
  - `TEXT_REPAIR_ENABLE_LLM_ESCALATION=true`
  - `TEXT_REPAIR_LLM_MAX_LINES_PER_DOC=10`
  - `TEXT_REPAIR_MIN_IMPLAUSIBILITY_SCORE=0.65`

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
