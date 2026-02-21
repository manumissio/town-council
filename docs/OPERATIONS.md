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

Backend-aware defaults:
- `LOCAL_AI_BACKEND=inprocess`:
  - use `--pool=solo --concurrency=1`
- `LOCAL_AI_BACKEND=http` (D2-lite conservative profile):
  - use `--pool=prefork --concurrency=3`
  - inference service caps: ~4GB RAM / 2 CPU
  - `LOCAL_AI_HTTP_PROFILE=conservative` (default)
    - longer timeout, lower retry budget
  - `LOCAL_AI_HTTP_PROFILE=balanced`
    - shorter timeout, higher retry budget after SLO gate pass
  - operation-specific timeout overrides (fallback to global timeout if unset):
    - `LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS`
    - `LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS`
    - `LOCAL_AI_HTTP_TIMEOUT_TOPICS_SECONDS`

Override (not recommended):
- `LOCAL_AI_ALLOW_MULTIPROCESS=true`
  - Use only if you understand the memory impact (each worker process loads its own model copy).

Security logging rule:
- Do not log API key values or key fragments. Log only path/client metadata on auth failures.

Provider error policy:
- Provider transport code raises typed errors (`ProviderTimeoutError`, `ProviderUnavailableError`, `ProviderResponseError`).
- Orchestrator mapping:
  - timeout/unavailable => retry path
  - response error => deterministic fallback path

Provider token/latency telemetry (HTTP backend):
- Additional best-effort fields are emitted when backend stats are available:
  - `ttft_ms`
  - `prompt_tokens`
  - `completion_tokens`
  - `tokens_per_sec`
  - `prompt_eval_duration_ms`
  - `eval_duration_ms`
- Metrics:
  - `tc_provider_ttft_ms`
  - `tc_provider_tokens_per_sec`
  - `tc_provider_prompt_tokens_total`
  - `tc_provider_completion_tokens_total`
- These are observational only; they do not change retry/timeout behavior.

A/B artifact integration (v1):
- `scripts/run_ab_eval.sh` captures best-effort provider telemetry from final task payloads.
- `scripts/collect_ab_results.py` carries telemetry into `ab_rows.csv` / `ab_rows.json`.
- `scripts/score_ab_results.py` reports TTFT/TPS/token rollups and deltas.
- These telemetry metrics are reporting-only in this phase and are not part of pass/fail gates.

## D2-lite 7-Day Soak Gate (Conservative -> Balanced)

Run profile:
- `env/profiles/m1_conservative.env` on M1 Pro.
- No new feature rollout during the soak window.

Promotion gate table:
- `provider_timeout_rate`:
  - source: `tc_provider_timeouts_total / tc_provider_requests_total`
  - threshold: `< 1.0%` for 7 consecutive days
  - fail action: remain conservative; investigate latency/queue
- `timeout_storms`:
  - source: retry/timeout log correlation
  - threshold: `0`
  - fail action: block promotion; tune infra limits
- `queue_wait_p95`:
  - source: worker queue latency trend
  - threshold: no sustained upward backlog trend
  - fail action: hold promotion; tune `OLLAMA_NUM_PARALLEL` or concurrency
- `segment_p95_s` and `summary_p95_s`:
  - source: task timing rollups
  - threshold: stable vs baseline (no persistent degradation)
  - fail action: hold promotion; investigate workload/profile
- `search_p95_regression_pct`:
  - source: API performance checks
  - threshold: `<= 15%` regression
  - fail action: hold promotion; prioritize API responsiveness
- `ttft_ms` and `tokens_per_sec` drift:
  - source: provider telemetry
  - threshold: no persistent adverse drift
  - fail action: hold promotion; investigate context/workload mix

Decision rule:
- Promote to `LOCAL_AI_HTTP_PROFILE=balanced` only if all gates pass continuously through day 7.
- If any gate fails, remain conservative and rerun soak after tuning.

### Automated daily soak harness (local M1 Pro)

Fixed manifest:
- `experiments/soak_catalogs_m1_v1.txt`
  - current cycle: `609`, `933`

Scripts:
- `scripts/run_soak_day.sh`
  - preflight `/health` poll for 60 seconds (default)
  - one fast self-heal attempt via `docker compose up -d inference worker api pipeline frontend`
  - falls back to `scripts/dev_up.sh` only if fast recovery fails
  - marks day `stack_offline` and exits cleanly if recovery fails
  - runs `extract -> segment -> summarize` for each CID
  - continues on per-task failures; extract failures are non-gating warnings while segment/summarize failures are gating
- `scripts/collect_soak_metrics.py`
  - stores raw snapshots:
    - `experiments/results/soak/<run_id>/api_metrics.prom`
    - `experiments/results/soak/<run_id>/worker_metrics.prom`
  - updates `experiments/results/soak/<run_id>/day_summary.json`
- `scripts/evaluate_soak_week.py`
  - reads 7-day window and emits:
    - `experiments/results/soak/soak_eval_7d.json`
    - `experiments/results/soak/soak_eval_7d.md`
  - uses day-over-day counter deltas (not absolute counter values)
  - handles counter reset after restarts by re-baselining deltas

Manual run:
```bash
cd /Users/dennisshah/GitHub/town-council && RUN_ID="soak_$(date +%Y%m%d)" && ./scripts/run_soak_day.sh --run-id "$RUN_ID" --catalog-file experiments/soak_catalogs_m1_v1.txt --output-dir experiments/results/soak || true; PYTHONPATH=. .venv/bin/python scripts/collect_soak_metrics.py --run-id "$RUN_ID" --output-dir experiments/results/soak
```

Weekly evaluation:
```bash
cd /Users/dennisshah/GitHub/town-council && PYTHONPATH=. .venv/bin/python scripts/evaluate_soak_week.py --input-dir experiments/results/soak --window-days 7
```

### Wake policy for local schedule (required)

To reduce missed runs on macOS laptops:
```bash
sudo pmset repeat wake MTWRFSU 19:50:00
```

Install the daily launchd job:
```bash
launchctl bootstrap gui/$(id -u) /Users/dennisshah/GitHub/town-council/ops/launchd/com.towncouncil.soak.daily.plist && launchctl enable gui/$(id -u)/com.towncouncil.soak.daily
```

Notes:
- Schedule is system local timezone.
- launchd target time is 19:55 daily (system local timezone).
- Logs:
  - `/Users/dennisshah/GitHub/town-council/experiments/results/soak/launchd.out.log`
  - `/Users/dennisshah/GitHub/town-council/experiments/results/soak/launchd.err.log`

Shared filter semantics:
- `/search` and `/trends/*` now use one QueryBuilder path.
- Procedural/contact/trend-noise rules come from a centralized lexicon module to avoid cross-surface drift.

## Hybrid Semantic Discovery (`B`): Semantic Search

Semantic search is additive and disabled by default.

### Enable
Set:
- `SEMANTIC_ENABLED=true`
- `SEMANTIC_BACKEND=faiss|pgvector`

Recommended rollout sequence:
1. Keep `SEMANTIC_BACKEND=faiss` while pgvector schema/backfill is deployed.
2. Validate pgvector quality/perf with `SEMANTIC_BACKEND=pgvector` in staging/dev.
3. Cut over production to pgvector.
4. Remove FAISS code path after 72h stable runtime and no incidents.

### Build semantic artifacts
```bash
docker compose run --rm pipeline python reindex_semantic.py
```

### Verify FAISS runtime availability (transitional only)
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
  - NumPy fallback now uses partial top-k selection (`argpartition`) to reduce ranking overhead.
  - fix FAISS install/import, then rebuild artifacts with `python reindex_semantic.py`.
  - when using pgvector, verify Postgres has `vector` extension and `semantic_embedding` HNSW index.

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

## Decision Integrity (`A`): Vote/Outcome Extraction

Vote extraction is an optional async stage that runs on segmented agenda items.

### Enable the stage
Set:
- `ENABLE_VOTE_EXTRACTION=true`

## Issue Threads Foundation (`C v1`): Trends + Lineage

Feature flag:
- `FEATURE_TRENDS_DASHBOARD=true`

API smoke checks:
```bash
curl -fsS "http://localhost:8000/trends/topics?limit=5"
curl -fsS "http://localhost:8000/trends/compare?cities=berkeley&cities=cupertino&date_from=2025-01-01&date_to=2025-12-31"
curl -fsS "http://localhost:8000/catalog/<CATALOG_ID>/lineage"
```

Manual lineage recompute task:
```bash
docker compose exec -T worker celery -A pipeline.tasks call pipeline.tasks.compute_lineage_task
```

Notes:
- Trends are served from Meilisearch facets (`topics`) in v1.
- Lineage recompute is full-graph and lock-protected to handle cascading component merges safely.

## D2-lite Rollout (before city expansion)

1. Enable HTTP backend:
```bash
LOCAL_AI_BACKEND=http docker compose up -d --build worker api pipeline inference
```
2. Pull the inference model once:
```bash
docker compose exec -T inference ollama pull "${LOCAL_AI_HTTP_MODEL:-gemma-3-270m-custom}"
```
3. Run backend parity tests:
```bash
.venv/bin/pytest -q tests/test_llm_backend_parity_*.py
```
4. If parity or SLOs regress, rollback immediately:
```bash
LOCAL_AI_BACKEND=inprocess WORKER_CONCURRENCY=1 WORKER_POOL=solo docker compose up -d --build worker api pipeline
```

City onboarding helper:
```bash
DRY_RUN=1 ./scripts/onboard_city_wave.sh wave1
```

### Host profiles (recommended)

M1 conservative:
```bash
docker compose --env-file env/profiles/m1_conservative.env up -d --build inference worker api pipeline frontend
```

Desktop balanced:
```bash
docker compose --env-file env/profiles/desktop_balanced.env up -d --build inference worker api pipeline frontend
```

### Queue-aware timeout math (why conservative timeout is high)

When `WORKER_CONCURRENCY=3` and `OLLAMA_NUM_PARALLEL=1`, three workers can enqueue
requests at once but only one is processed immediately. Timeout must cover:
- waiting behind earlier requests in Ollama's internal queue, plus
- generation time of the current request.

Recommended split on constrained hosts:
- segmentation timeout higher (read-heavy, long TTFT),
- summary/topics timeout lower (write-heavy, fail faster if stalled).

Because this is an infrastructure queueing effect, concurrency control is handled
at the inference service layer (`OLLAMA_NUM_PARALLEL`) rather than with model locks
in application code.

## A/B Runtime Profile Evaluation (270M-only, staging-local)

This runbook evaluates `conservative` vs `balanced` runtime profiles under the
same 270M model.

1) One-time setup for 270M custom model in Ollama:
```bash
./scripts/setup_ollama_270m.sh /models/gemma-3-270m-it-Q4_K_M.gguf
```

2) Run Arm A (control, conservative):
```bash
LOCAL_AI_BACKEND=http LOCAL_AI_HTTP_MODEL=gemma-3-270m-custom LOCAL_AI_HTTP_PROFILE=conservative WORKER_CONCURRENCY=3 WORKER_POOL=prefork docker compose up -d --build inference worker api pipeline
./scripts/run_ab_eval.sh --arm A --catalog-file experiments/ab_catalogs_v1.txt --run-id A_run1
python scripts/collect_ab_results.py --run-id A_run1
```

3) Run Arm B (treatment, balanced):
```bash
LOCAL_AI_BACKEND=http LOCAL_AI_HTTP_MODEL=gemma-3-270m-custom LOCAL_AI_HTTP_PROFILE=balanced WORKER_CONCURRENCY=3 WORKER_POOL=prefork docker compose up -d --build inference worker api pipeline
./scripts/run_ab_eval.sh --arm B --catalog-file experiments/ab_catalogs_v1.txt --run-id B_run1
python scripts/collect_ab_results.py --run-id B_run1
```

4) Score gates and generate report:
```bash
python scripts/score_ab_results.py \
  --runs A_run1,B_run1 \
  --queue-wait-p95-minutes <PROM_QUEUE_WAIT_P95_MINUTES> \
  --search-p95-regression-pct <SEARCH_P95_REGRESSION_PCT>
```

5) Optional blinded manual review pack:
```bash
python scripts/sample_ab_manual_review.py --runs A_run1,B_run1 --sample-size 20
```

After reviewers fill `manual_review_blind_v1.csv`, re-run scorer with manual inputs:
```bash
python scripts/score_ab_results.py \
  --runs A_run1,B_run1 \
  --queue-wait-p95-minutes <PROM_QUEUE_WAIT_P95_MINUTES> \
  --search-p95-regression-pct <SEARCH_P95_REGRESSION_PCT> \
  --manual-review-csv experiments/results/manual_review_blind_v1.csv \
  --manual-review-key-csv experiments/results/manual_review_key_v1.csv
```

Artifacts:
- `experiments/results/<run_id>/tasks.jsonl`
- `experiments/results/<run_id>/ab_rows.csv`
- `experiments/results/<run_id>/ab_rows.json`
- `experiments/results/ab_report_v1.md`

## Deferred Model-Selection A/B (disabled by policy)

Model-selection A/B (for example `270M vs <candidate>`) is intentionally disabled
until a new candidate model is explicitly approved and reintroduced.

Current policy:
- runtime defaults remain 270M-only (`LOCAL_AI_HTTP_MODEL=gemma-3-270m-custom`);
- executable A/B in this repo is profile-level (`conservative` vs `balanced`);
- model-selection A/B resumes only with an explicit roadmap decision and candidate
  reintroduction PR.

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
- Meeting hits now include truncation observability fields:
  - `content_truncated` (boolean)
  - `original_content_chars` (int)
  - `indexed_content_chars` (int)
  Use these to identify search misses caused by indexed-content limits.

Frontend security headers:
- Next.js now emits security headers for all routes, including a CSP rollout mode.
- Default is report-only CSP; enforce mode requires:
  - `NEXT_CSP_ENFORCE=true`

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
