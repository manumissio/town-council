# Operations Runbook

Last updated: 2026-03-28

## Core workflow

Pipeline internals note:
- For an onboarding-oriented deep dive on batch + async pipeline behavior (including design rationale), see [`docs/PIPELINE.md`](docs/PIPELINE.md).

Path note:
- Set `REPO_ROOT` once to avoid machine-specific absolute paths in commands:
```bash
REPO_ROOT="<REPO_ROOT>"
cd "$REPO_ROOT"
```

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

### 1.6) Verify stack health contracts
Use this after `docker compose up -d --build` and before running onboarding or soak flows.

```bash
docker ps --format '{{.Names}} {{.Status}}'
docker compose logs --tail=120 tika
docker compose logs --tail=120 worker
docker compose logs --tail=120 frontend
docker compose exec -T postgres psql -U town_council -d town_council_db -c "SELECT datname, datcollversion, pg_database_collation_actual_version(oid) AS actual_collversion FROM pg_database WHERE datname = current_database();"
```

Expected signals:
- `tika` should become `healthy` via an in-container `wget` probe to `127.0.0.1:9998/tika`.
- `worker` should become `healthy` only after its metrics listener is up and its Redis/Postgres dependencies are reachable.
- `frontend` should become `healthy` via an in-container `wget` probe to `127.0.0.1:3000/`.
- If the Postgres query reports mismatched collation versions, treat that as operator maintenance debt before long validation runs.

### 2) Scrape
```bash
docker compose run --rm crawler scrapy crawl berkeley
docker compose run --rm crawler scrapy crawl cupertino
```

For scoped historical recovery, crawlers accept `-a disable_delta=true` to bypass
the normal DB anchor for that one run:
```bash
docker compose run --rm crawler scrapy crawl sunnyvale -a disable_delta=true
docker compose run --rm crawler scrapy crawl hayward -a disable_delta=true
```
Use this only for validate-before-promote backfills; normal recurring crawls should
continue to rely on delta mode.

### 3) Process
```bash
docker compose run --rm pipeline python run_pipeline.py
```

### Maintenance hydrate helper for repaired agenda PDFs
- `scripts/hydrate_repaired_city_catalogs.py` is the maintenance helper for repaired city-scoped `agenda` catalogs that still need extract -> segment -> summarize work.
- By default it selects repaired agenda catalogs by city scope and repair state, not by one historical URL family.
- Use `--url-substring ...` only when you intentionally want to narrow a run to one recovered source shape such as `ElectronicFile.aspx`.
- `--segment-mode maintenance` keeps normal pipeline defaults untouched, but lets the helper skip LLM-first agenda extraction when the extracted text is already structured enough for the deterministic parser.
- `--summary-fallback-mode deterministic` keeps normal summary behavior untouched, but lets the helper persist a deterministic agenda-items summary when maintenance runs hit agenda-summary inference timeouts.
- Prefer this helper when a city recovery added agenda PDFs that never entered extraction; keep `scripts/staged_hydrate_cities.py` for city-wide unresolved backlog reduction.
- Watch these counters in helper output when tuning repaired batches:
  - segmentation: `llm_attempted`, `llm_skipped_heuristic_first`, `heuristic_complete`, `llm_timeout_then_fallback`
  - summary: `llm_complete`, `deterministic_fallback_complete`, `error`
- Example maintenance run:
```bash
docker compose run --rm pipeline python scripts/hydrate_repaired_city_catalogs.py \
  --city hayward \
  --limit 25 \
  --progress-every 5 \
  --extract-workers 4 \
  --segment-workers 1 \
  --segment-mode maintenance \
  --agenda-timeout-seconds 20 \
  --summary-timeout-seconds 90 \
  --summary-fallback-mode deterministic
```
- Example narrowed run for one recovered URL family:
```bash
docker compose run --rm pipeline python scripts/hydrate_repaired_city_catalogs.py \
  --city san_mateo \
  --url-substring ElectronicFile.aspx \
  --limit 25 \
  --progress-every 5 \
  --extract-workers 4 \
  --segment-workers 1 \
  --segment-mode maintenance \
  --agenda-timeout-seconds 20 \
  --summary-timeout-seconds 90 \
  --summary-fallback-mode deterministic
```

### Maintenance salvage helper for flaky Laserfiche agenda PDFs
- `scripts/repair_san_mateo_laserfiche_backlog.py` now distinguishes generated-PDF transport failures from permanent failures.
- The helper treats these generated-PDF failures as retryable and eligible for the slow retry lane:
  - `remote_disconnected`
  - `incomplete_read`
  - `connection_error`
  - `read_timeout`
  - `generated_pdf_html_retryable`
  - `invalid_partial_pdf`
- Watch `retry_stats` in `repair_finish` output when evaluating bad-tail salvage batches:
  - `generated_pdf_fetch_retries`
  - `generated_pdf_html_retryable`
  - `generated_pdf_transport_retryable`
  - `generated_pdf_invalid_partial_pdf`

### Laserfiche bad-page cleanup
- The pipeline now rejects known Laserfiche portal bad HTML instead of treating it as valid agenda content.
- The guard applies in three places:
  - extraction rejects polluted `.html` Laserfiche portal pages with an explicit poison reason
  - agenda segmentation marks those rows `failed` instead of `complete` or `empty`
  - summary generation refuses to summarize those rows
- The current bad-page detector covers:
  - explicit Laserfiche error pages
  - Laserfiche loading-shell/viewer pages that only contain placeholder text like `Loading...` and `Your browser does not support the video tag.`
- Use `scripts/reset_laserfiche_error_agenda_rows.py` to measure or reset already polluted derived rows.
- Dry run first:
```bash
docker compose run --rm pipeline python scripts/reset_laserfiche_error_agenda_rows.py --city san_mateo
docker compose run --rm pipeline python scripts/reset_laserfiche_error_agenda_rows.py --city san_mateo --json
```
- Apply reset only when no large backlog mutation job is running:
```bash
docker compose run --rm pipeline python scripts/reset_laserfiche_error_agenda_rows.py --city san_mateo --apply
```
- The reset clears poisoned derived state so those catalogs can be re-extracted later:
  - `Catalog.content`
  - `Catalog.summary`
  - agenda segmentation status/error fields
  - derived `AgendaItem` rows
  - catalog-level semantic embeddings
- Historical note:
  backlog metrics captured before this guard may overstate real progress for San Mateo because some `complete` and `empty` agenda segmentations were built from Laserfiche bad pages, not real agendas.

### Agenda report / staff memo cleanup
- The shared bad-content classifier also recognizes a separate non-Laserfiche document-shape category:
  - `single_item_staff_report_detected`
- This category is for `agenda` PDFs that are really single-item `Agenda Report` / `Administrative Report` staff memos rather than meeting-wide agendas.
- Segmentation marks these rows `failed` with the explicit reason instead of letting them churn as `empty`.
- Summary behavior is unchanged:
  agenda summaries still require segmented agenda items, so this category is a backlog-classification fix, not a new summary path.
- Cleanup for this category is opt-in so default Laserfiche bad-page cleanup stays narrow.
- The opt-in cleanup only targets unresolved document-shape backlog rows; it does not reset already summarized historical staff-report rows.
- Dry-run with document-shape rows included:
```bash
docker compose run --rm pipeline python scripts/reset_laserfiche_error_agenda_rows.py --city san_mateo --json --include-document-shape
```
- Apply reset for document-shape rows only when no large backlog mutation job is running:
```bash
docker compose run --rm pipeline python scripts/reset_laserfiche_error_agenda_rows.py --city san_mateo --apply --include-document-shape
```

### Summary hydration diagnostics
- `scripts/diagnose_summary_hydration.py` mixes two kinds of metrics on purpose:
  - cumulative totals, such as `catalogs_with_summary`
  - unresolved backlog metrics, which only count rows where `summary` is still null
- When a hydrate batch succeeds, `catalogs_with_summary` can rise while unresolved backlog buckets stay flat or even rise slightly if the same batch also adds new content or produces `empty` segmentation outcomes.
- Read the CLI headings literally:
  - `Cumulative totals`
  - `Unresolved backlog totals`
  - `Backlog buckets (rows where summary is still null)`
- The backlog diagnostic answers "how much known work is unresolved?" It does not answer "did we scrape enough meetings across the full period?"

### City coverage audit
- `scripts/audit_city_coverage.py` answers the source-completeness question that backlog diagnostics cannot:
  - month-by-month `Event.record_date` coverage for a city
  - agenda document/catalog coverage for those events
  - downstream content/summary coverage on those agenda catalogs
- Example:
```bash
docker compose run --rm pipeline python /app/scripts/audit_city_coverage.py --city san_mateo --months 12
docker compose run --rm pipeline python /app/scripts/audit_city_coverage.py --city san_mateo --months 12 --json
```
- Month flags are advisory diagnostics:
  - `no_events`
  - `events_but_no_agendas`
  - `agendas_but_no_content`
  - `content_but_no_summaries`
  - `below_expected_cadence`
- The audit reports both raw `event_count` and a deduped meeting-style count based on `record_date + normalized event name`.
- `below_expected_cadence` uses the deduped meeting-style count, not raw event rows.
- The current in-progress month is still shown in the window, but it does not receive `below_expected_cadence` because partial months are not comparable to completed months.
- `below_expected_cadence` is meant to surface suspicious troughs, not to encode each city's true meeting schedule.
- Use the coverage audit alongside `scripts/diagnose_summary_hydration.py`:
  - coverage audit asks "did we capture enough of the city's meetings?"
  - hydration diagnostics ask "how much known catalog work is still unresolved?"

### Onboarding-safe extraction mode
- `scripts/onboard_city_wave.sh` runs the pipeline in an onboarding-scoped extraction mode.
- That mode limits extraction to catalogs touched by the current city's staged URL set for the run window instead of waking up the full missing-content backlog.
- It also reduces parallel extraction pressure (`PIPELINE_ONBOARDING_MAX_WORKERS=1`, smaller chunks) and disables OCR fallback for the onboarding pipeline run (`TIKA_OCR_FALLBACK_ENABLED=false`).
- `PIPELINE_RUNTIME_PROFILE=onboarding_fast` now keeps onboarding on the gating path only:
  - runs crawl, download/extract for touched catalogs, segmentation, and search indexing
  - skips table extraction, organization backfill, topic modeling, and people linking during onboarding validation runs
- `scripts/onboard_city_wave.sh` now performs an explicit crawler image preflight before running a city crawl.
  - it resolves the crawler image name from `docker compose config --images`
  - it fails fast with a rebuild instruction if that image is missing
  - it does not rely on implicit rebuilds inside the onboarding run
- The goal is decision-grade city verification without destabilizing Tika on unrelated historical backlog.

### PostgreSQL collation drift
- Detect the current state with:

```bash
docker compose run --rm -w /app pipeline python scripts/check_postgres_collation.py
docker compose run --rm -w /app pipeline python scripts/check_postgres_collation.py --json
```

- A non-zero exit means the stored database collation version does not match the container OS collation version.
- Do not auto-repair this on startup.
- Guarded local repair flow:

```bash
docker compose stop api worker pipeline crawler frontend monitor
docker compose exec -T postgres psql -U town_council -d town_council_db -c "REINDEX DATABASE town_council_db;"
docker compose exec -T postgres psql -U town_council -d town_council_db -c "ALTER DATABASE town_council_db REFRESH COLLATION VERSION;"
docker compose start api worker frontend monitor
```

- Why this is guarded:
  The server warning explicitly requires rebuilding collation-sensitive objects before refreshing the database metadata version. For this local stack, `REINDEX DATABASE` is the supported first step; if you have additional custom collation-sensitive objects outside normal indexes, repair them before refreshing the database version marker.

### Stable delta no-op confirmation
- `scripts/onboard_city_wave.sh` now distinguishes first-time onboarding failures from previously passing delta-crawl no-ops.
- If a city already has a verified fresh-evidence pass recorded in `city_metadata/city_rollout_registry.csv`, and the crawler exits successfully but stages no newer city-attributable rows, the run is recorded as `crawler_stable_noop`.
- `crawler_stable_noop` skips pipeline, segmentation, and search smoke for that city in that run because there is no fresh touched corpus to process.
- `scripts/evaluate_city_onboarding.py` treats that case as `pass` only for cities explicitly marked stable-no-op eligible in the rollout registry, and the output artifacts record the reason as `stable_delta_noop:<last_fresh_pass_run_id>`.
- First-time onboarding cities still require fresh staged evidence; zero evidence remains `crawler_empty` for them.

### First-time onboarding verification mode
- `scripts/onboard_city_wave.sh` now writes `verification_mode` into `runs.jsonl` for every onboarding attempt.
- Cities with `quality_gate=pass` in the rollout registry run in `confirmation` mode.
- Cities still in `pending` or `fail` state run in `first_time_onboarding` mode.
- First-time onboarding still keeps the 3-run evidence policy, but the runner now captures a pre-run baseline artifact and restores the city's effective delta anchor between runs 2 and 3 so delta crawlers are measured against the same pre-run anchor instead of self-advancing after run 1.
- The baseline artifact lives under `experiments/results/city_onboarding/<run_id>/baselines/<city>.json` and records:
  - `baseline_event_count`
  - `baseline_max_record_date`
  - `baseline_max_scraped_datetime`
- The reset is city-scoped and removes rows that advance the city's crawl anchor beyond that captured baseline; it does not broaden into a full database rollback.
- If run 1 for a first-time city stages no evidence, the runner stops that city immediately instead of spending runs 2 and 3 on guaranteed `crawler_empty` repeats.

### Pending-city rewind recovery
- Use this only when a pending city was contaminated by pre-fix first-time onboarding runs that advanced its delta anchor before the current runner semantics existed.
- The supported recovery entrypoint is `scripts/rewind_pending_city_onboarding.py`.
- Safety rules:
  - dry-run first
  - city must still be `enabled=no`
  - city must still have `quality_gate` of `pending` or `fail`
  - stop write-capable services before `--apply`
- The rewind deletes only city-scoped verification-era state:
  - `event`
  - linked `document`
  - unreferenced `catalog`
  - linked derived agenda/embedding rows via existing cascades
- Example shape:

```bash
docker compose stop api worker pipeline crawler frontend monitor
docker compose run --rm -w /app pipeline python scripts/rewind_pending_city_onboarding.py --city sunnyvale --since 2026-03-15T02:08:17Z
docker compose run --rm -w /app pipeline python scripts/rewind_pending_city_onboarding.py --city sunnyvale --since 2026-03-15T02:08:17Z --apply
docker compose start api worker frontend monitor
```

### City segmentation timeout behavior
- `scripts/segment_city_corpus.py` now bounds per-catalog agenda segmentation instead of letting one stuck catalog hang the whole city run indefinitely.
- The timeout is controlled by `CITY_SEGMENTATION_TIMEOUT_SECONDS` and defaults to `120`.
- `--segment-mode maintenance` reuses the same heuristic-first agenda parsing path as `scripts/hydrate_repaired_city_catalogs.py`, so city-wide backlog runs can skip LLM-first extraction when the extracted agenda text is already structured enough for the deterministic parser.
- Maintenance mode keeps existing terminal states unchanged:
  - `complete`
  - `empty`
  - `failed`
- Watch these counters when the goal is shrinking `agenda_missing_summary_without_items` instead of only processing repaired rows:
  - `llm_attempted`
  - `llm_skipped_heuristic_first`
  - `heuristic_complete`
  - `timeout_fallbacks`
- `pipeline/agenda_resolver.py` now evaluates agenda sources lazily in the documented priority order `Legistar -> HTML -> LLM`, so deterministic sources can satisfy segmentation without paying the full LLM cost first.
- Legistar exports are filtered before acceptance so portal wrapper rows like `Call to Order`, `Roll Call`, and meeting-header scaffolding do not force otherwise-structured agendas into the LLM fallback path.
- `pipeline/agenda_legistar.py` now treats the known tenant-specific Legistar `400` (`Agenda Draft Status` / public visibility setting not configured) as an unsupported cross-check capability, not as a content-quality failure.
  - the capability miss is memoized per client with a TTL (`LEGISTAR_EVENT_ITEMS_CAPABILITY_TTL_SECONDS`)
  - cache scope is per worker process, not cross-worker shared state
  - once detected, later agenda resolution skips the same doomed Legistar cross-check until the per-process TTL expires
- Base `docker-compose.yml` runtime defaults are now shared/prod safe:
  - `STARTUP_PURGE_DERIVED=false` by default for `api`, `worker`, and `pipeline`
  - the base API service no longer runs `uvicorn --reload`
  - dev-only convenience now lives in `docker-compose.dev.yml`
- Frontend privileged actions now flow through same-origin Next route handlers instead of embedding `NEXT_PUBLIC_API_AUTH_KEY` in the browser bundle.
  - required frontend server-side env:
    - `INTERNAL_API_BASE_URL` for backend-to-backend calls, default `http://api:8000`
    - `API_AUTH_KEY` for forwarding privileged requests
- Frontend CSP is now generated per request in `frontend/proxy.js` using a nonce-based `script-src`.
  - `NEXT_PUBLIC_API_URL` remains public configuration and is used in `connect-src`
  - when `APP_ENV` is not `dev`, `NEXT_PUBLIC_API_URL` must be set to a non-localhost origin at build time
- On timeout, the script records a terminal catalog failure:
  - `agenda_segmentation_status=failed`
  - `agenda_segmentation_item_count=0`
  - `agenda_segmentation_attempted_at=<now>`
  - `agenda_segmentation_error=agenda_segmentation_timeout:<seconds>s`
- The city runner continues to the next catalog and prints a summary line with `complete`, `empty`, `failed`, and `timed_out` counts.
- This does not relax onboarding gates; it only converts an infinite wait into an explicit catalog outcome that the evaluator can grade.

### Staged hydration progress output
- `scripts/staged_hydrate_cities.py` now emits live stage and per-catalog segmentation progress in normal mode so long-running maintenance runs no longer appear idle.
- `scripts/staged_hydrate_cities.py` is now the preferred operator entrypoint for shrinking a city-wide unresolved agenda backlog.
- Maintenance runs can pass through the same backlog-oriented controls used by the repaired-row helper:
  - `--segment-mode maintenance`
  - `--agenda-timeout-seconds <seconds>`
  - `--summary-timeout-seconds <seconds>`
  - `--summary-fallback-mode deterministic`
- Each chunk now includes unresolved-backlog deltas so operators can tell whether the broad backlog is actually shrinking:
  - `agenda_missing_summary_without_items`
  - `agenda_missing_summary_with_items`
  - `catalogs_with_summary`
  - `agenda_unresolved_segmentation_status_counts`
- Expected progress shape:
  - city start
  - before snapshot
  - segmentation start
  - per-catalog segmentation start/finish lines with running counts
  - summary start/finish
  - city finish with after-state delta
- `--json` remains machine-readable only and does not mix human progress lines into stdout.

### Optional: Reindex Meilisearch only (no extraction/AI)
If you changed indexing logic (or you want to refresh search after cleaning up bad HTML in stored titles):
```bash
docker compose run --rm pipeline python reindex_only.py
```

### Extraction failure recovery
- Batch extraction now stops retrying deterministic failures forever.
- Catalogs with `catalog.extraction_status=failed_terminal` are excluded from the default extraction backlog until an operator forces re-extraction.
- Targeted recovery path:

```bash
curl -X POST "http://localhost:8000/extract/<CATALOG_ID>?force=true" \
  -H "X-API-Key: $API_AUTH_KEY"
```

- Add `ocr_fallback=true` when you need the slower OCR retry path for scan-heavy PDFs.
- Rows with `content` already present but missing `entities` still remain eligible for NLP-only batch work; they do not need extraction recovery.

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

Frontend server-side proxy must set:
- `INTERNAL_API_BASE_URL` for backend-to-backend calls, default `http://api:8000`
- `API_AUTH_KEY` for forwarding privileged requests

Task polling note:
- `GET /tasks/{task_id}` expects a valid UUID task ID; malformed IDs return `400`

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
- `LOCAL_AI_BACKEND=http` (conservative profile for inference decoupling and throughput stabilization):
  - use `--pool=prefork --concurrency=3`
  - inference service caps: ~4GB RAM / 2 CPU
  - `LOCAL_AI_HTTP_PROFILE=conservative` (default)
    - longer timeout, zero provider retries for summary/topic workloads
  - `LOCAL_AI_HTTP_PROFILE=balanced`
    - shorter timeout, small provider retry budget after SLO gate pass
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
  - response error => deterministic fallback path (no transport retry loop)
- `extract_agenda` on the HTTP provider skips transport retries and falls back to the local heuristic parser after the first timeout/unavailable response. This avoids paying the same long queue wait twice before segmentation degrades to its deterministic path.
- Under the conservative HTTP profile, summary/topic operations also skip provider-level retries so Celery owns the retry and the worker does not immediately re-enter the same saturated inference queue.
- HTTP provider classification:
  - timeout => `ProviderTimeoutError` (retryable)
  - transport/unreachable/5xx => `ProviderUnavailableError` (retryable)
  - malformed JSON/payload shape errors/empty response/HTTP 4xx => `ProviderResponseError` (deterministic, non-retryable)

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

## Inference Decoupling & Throughput Stabilization Soak Evidence Tiers

Policy guardrails:
- Shared workflows are local-first by default.
- Optional remote acceleration is personal/opt-in and should fail fast if unreachable.
- Baseline soak integrity depends on consistent baseline target conditions across days.

Run profile:
- `env/profiles/m5_conservative.env` for the current M5 Pro baseline host.
- `env/profiles/m1_conservative.env` remains available for historical M1 Pro comparisons only.

Shared gate table:
- `provider_timeout_rate`:
  - source: `tc_provider_timeouts_total / tc_provider_requests_total`
  - threshold: `< 1.0%`
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
- `2-day validation`:
  - use for targeted stabilization acceptance after a focused fix
  - requires a baseline-valid 2-day conservative window with run-local provider deltas present for both days
  - a passing 2-day window is sufficient to conclude that a targeted stabilization change behaved correctly under the current baseline
- `7-day promotion-grade confirmation`:
  - use when the team explicitly wants stronger rollout confidence before balanced-profile evaluation or milestone promotion
  - requires all gates to pass continuously through day 7
- For either tier:
  - if any gate fails, remain conservative and rerun soak after tuning
  - if any gate is `INCONCLUSIVE`, treat the evidence as unusable until telemetry is restored
- A clean 7-day conservative week makes balanced eligible for opt-in evaluation only; conservative remains the default recommendation.

Current interpretation:
- the earlier failing short-window timeout readouts were invalidated by the soak provider delta-accounting bug
- stale cumulative Redis counters were previously being treated as fresh run-local timeout deltas
- the corrected conservative validation window `soak_20260323_deltafix_day1` + `soak_20260323_deltafix_day2` is the first trustworthy post-fix short-run evidence
- that corrected 2-day window passed with zero run-local provider timeouts, so `extract_agenda` is no longer the active blocker on the basis of the current evidence

### Automated daily soak harness (current local baseline host: M5 Pro)

Fixed manifest:
- `experiments/soak_catalogs_m1_v1.txt`
  - current cycle: `609`, `933`

Scripts:
- `scripts/run_soak_day.sh`
  - writes `experiments/results/soak/<run_id>/run_manifest.json` with:
    - profile identity (`LOCAL_AI_BACKEND`, `LOCAL_AI_HTTP_PROFILE`, `LOCAL_AI_HTTP_MODEL`, `WORKER_CONCURRENCY`, `WORKER_POOL`, `OLLAMA_NUM_PARALLEL`)
    - soak corpus identity (`catalog_ids`, `catalog_count`, source catalog file)
    - pre-run worker-provider counters (`provider_counters_before_run`)
    - baseline capture status (`provider_counters_before_run_available`, `provider_counters_before_run_source`, optional `provider_counters_before_run_error`)
  - uses the same worker scrape strategy ordering as post-run collection:
    - strategy A: HTTP probe to `http://localhost:8001/metrics`
    - strategy B: collector-based registry exposition (`RedisProviderMetricsCollector`)
  - preflight `/health` poll for 60 seconds (default)
  - one fast self-heal attempt via `docker compose up -d inference worker api pipeline frontend`
  - falls back to `scripts/dev_up.sh` only if fast recovery fails
  - treats a successful pre-run worker scrape with no provider series yet as a valid zero baseline (`provider_counters_before_run_source=zero_baseline_no_provider_series`)
  - marks day `stack_offline` and exits cleanly if recovery fails
  - records preflight recovery diagnostics on `stack_offline` days:
    - `preflight_recovery_attempted`
    - `preflight_recovery_result`
    - `preflight_recovery_output`
    - `preflight_compose_ps`
  - runs `extract -> segment -> summarize` for each CID
  - continues on per-task failures; extract failures are non-gating warnings while segment/summarize failures are gating
  - records additional failure diagnostics in `day_summary.json`:
    - `task_submission_failures`
    - `task_poll_timeouts`
    - refined `failure_reason` (`task_submission_failures`, `task_poll_timeout`, `gating_phase_failures`)
  - records `phase_duration_p95_s_capped` for queue-proxy drift analysis while retaining raw p95 fields
- `scripts/collect_soak_metrics.py`
  - stores raw snapshots:
    - `experiments/results/soak/<run_id>/api_metrics.prom`
    - `experiments/results/soak/<run_id>/worker_metrics.prom`
  - scrapes worker metrics by executing Python inside the worker container
    (does not depend on `curl`/`wget` being installed in the image)
  - uses two scrape strategies with bounded retries:
    - strategy A: HTTP probe to `http://localhost:8001/metrics` in the worker container
    - strategy B: fallback to collector-based registry exposition in the worker container (`RedisProviderMetricsCollector`)
  - marks `worker_scrape_failed` only when both strategies fail across retry attempts
  - annotates provider telemetry availability:
    - `provider_metrics_present`
    - `provider_metrics_reason` (`ok`, `worker_scrape_failed`, `no_provider_series`)
  - computes run-local provider deltas using the manifest baseline plus the post-run worker scrape:
    - `provider_requests_delta_run`
    - `provider_timeouts_delta_run`
    - `provider_retries_delta_run`
    - `provider_timeout_rate_run`
  - rejects legacy/malformed `tc_provider_*` baseline payloads rather than silently treating them as zero baselines
  - adds hotspot diagnostics from `tasks.jsonl`:
    - `slowest_phase`
    - `slowest_catalog_id`
    - `slowest_duration_s`
    - `segment_max_s`
    - `summary_max_s`
  - updates `experiments/results/soak/<run_id>/day_summary.json`
- `scripts/evaluate_soak_week.py`
  - reads an arbitrary window via `--window-days` and emits:
    - `experiments/results/soak/soak_eval_<N>d.json`
    - `experiments/results/soak/soak_eval_<N>d.md`
  - treats run-local provider deltas as the only trustworthy timeout evidence for either tier
  - treats legacy cumulative-only summaries as diagnostic and marks timeout-rate gate `INCONCLUSIVE`
  - emits `overall_status` (`PASS|FAIL|INCONCLUSIVE`) while keeping `overall_pass` for compatibility
  - emits per-gate `gate_statuses` and `gate_reasons`
  - emits `baseline_valid`, `baseline_artifact_days`, and `evidence_quality_reasons`
  - annotates `telemetry_confidence` (`high|degraded`) based on worker metrics availability
    and whether provider requests were observed during successful phases

Baseline-valid soak requirements:
- same profile settings and soak corpus across the whole evaluated window
- `run_manifest.json` present for each day
- `provider_requests_delta_run`, `provider_timeouts_delta_run`, and `provider_retries_delta_run` present for each day
- zero-valued provider baselines count as valid evidence when the pre-run worker scrape succeeded
- evaluate a fresh hardened window only; do not mix pre-hardening and post-hardening artifacts for either validation or promotion

Manual run:
```bash
cd "$REPO_ROOT" && RUN_ID="soak_$(date +%Y%m%d)" && ./scripts/run_soak_day.sh --run-id "$RUN_ID" --catalog-file experiments/soak_catalogs_m1_v1.txt --output-dir experiments/results/soak || true; PYTHONPATH=. .venv/bin/python scripts/collect_soak_metrics.py --run-id "$RUN_ID" --output-dir experiments/results/soak
```

2-day validation:
```bash
cd "$REPO_ROOT" && PYTHONPATH=. .venv/bin/python scripts/evaluate_soak_week.py --input-dir experiments/results/soak --window-days 2
```

7-day promotion-grade evaluation:
```bash
cd "$REPO_ROOT" && PYTHONPATH=. .venv/bin/python scripts/evaluate_soak_week.py --input-dir experiments/results/soak --window-days 7
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
   - Phase 2 scope is meeting-level hybrid rerank, not agenda-item semantic retrieval.
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
- semantic mode returns lexical-looking records instead of semantic reranks:
  - check `semantic_diagnostics.retrieval_mode`; pgvector Phase 2 should report `hybrid_pgvector`.
  - check `semantic_diagnostics.degraded_to_lexical` and `semantic_diagnostics.skipped_reason`.
  - check `semantic_diagnostics.fresh_embeddings`, `missing_embeddings`, and `stale_embeddings`.
  - `missing_embeddings` or `stale_embeddings` means the API intentionally fell back to lexical ordering for those meetings.
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
- Lineage read endpoints are available even when `FEATURE_TRENDS_DASHBOARD=false`.
- Lineage recompute is full-graph and lock-protected to handle cascading component merges safely.
- `pipeline/semantic_index.py` still carries its own env-based multiprocess guardrail path; Batch 2 only unified the LocalAI task and runtime checks.

## Inference Decoupling & Throughput Stabilization Rollout (before city expansion)

1. Enable HTTP backend:
```bash
LOCAL_AI_BACKEND=http docker compose up -d --build worker api pipeline inference
```
2. Create the local inference model alias once:
```bash
./scripts/setup_ollama_270m.sh /models/gemma-3-270m-it-Q4_K_M.gguf
```
3. Run backend parity tests:
```bash
.venv/bin/pytest -q tests/test_llm_backend_parity_*.py
```
4. If parity or SLOs regress, rollback immediately:
```bash
LOCAL_AI_BACKEND=inprocess WORKER_CONCURRENCY=1 WORKER_POOL=solo docker compose up -d --build worker api pipeline
```
5. If the recent inference hardening commits cause regressions, rollback code explicitly:
```bash
git revert 85e2c66 d463e18 5ae10e2
```
6. If only telemetry collector hardening regresses scrape behavior:
```bash
git revert 85e2c66
```

City onboarding helper:
```bash
DRY_RUN=1 ./scripts/onboard_city_wave.sh wave1
```

Wave 1 targeted slice (Hayward + San Mateo):
```bash
RUN_ID="city_wave1_hayward_sanmateo_$(date +%Y%m%d_%H%M%S)"
DRY_RUN=1 ./scripts/onboard_city_wave.sh wave1 --cities hayward,san_mateo --runs 3 --run-id "$RUN_ID" --output-dir experiments/results/city_onboarding
DRY_RUN=0 ./scripts/onboard_city_wave.sh wave1 --cities hayward,san_mateo --runs 3 --run-id "$RUN_ID" --output-dir experiments/results/city_onboarding
docker compose run --rm -w /app -e STARTUP_PURGE_DERIVED=false pipeline python scripts/evaluate_city_onboarding.py --run-id "$RUN_ID" --cities hayward,san_mateo --output-dir experiments/results/city_onboarding
```

Artifacts:
- `experiments/results/city_onboarding/<run_id>/runs.jsonl`
- `experiments/results/city_onboarding/<run_id>/city_gate_eval.json`
- `experiments/results/city_onboarding/<run_id>/city_gate_eval.md`

Notes:
- `city_metadata/city_rollout_registry.csv` is the source of truth for wave membership, enabled-city state, and latest verified rollout evidence. `city_metadata/list_of_cities.csv` remains static place/source metadata only.
- `scripts/onboard_city_wave.sh` runs pipeline with `STARTUP_PURGE_DERIVED=false` to avoid wiping derived state between onboarding attempts.
- `scripts/onboard_city_wave.sh` now loads `wave1` / `wave2` membership from the rollout registry instead of hardcoded shell arrays.
- `scripts/onboard_city_wave.sh` now attempts city-scoped agenda segmentation after `run_pipeline.py` so segmentation gates reflect attempted outcomes instead of lingering `null` statuses.
- `scripts/onboard_city_wave.sh` now verifies that each crawl wrote city-attributable staging rows during the run window. A zero-exit crawl with no staged `event_stage`/`url_stage` evidence is recorded as `crawler_empty` and does not proceed to pipeline, segmentation, or search smoke.
- `scripts/evaluate_city_onboarding.py` now grades extraction and segmentation quality against the onboarding run's touched catalog set for that city, not the city's full historical backlog. Historical totals remain in the artifacts as diagnostic context.
- San Mateo now uses the official city Laserfiche legislative-records portal as its primary onboarding source instead of COSM/PrimeGov. PrimeGov remains out of scope because `sanmateo.primegov.com` is robots-blocked.
- San Mateo's Laserfiche spider emits canonical `san_mateo` source identity, uses a bounded bootstrap window when no trustworthy delta anchor exists, and builds the known-good Laserfiche listing query directly instead of depending on `CustomSearchService.aspx/GetSearchQuery`.
- Latest verified San Mateo evidence run is `city_wave1_san_mateo_20260314_004358`, which completed with `quality_gate=pass` under the run-window denominator.
- Legistar CMS crawlers now write normalized slug `Event.source` values (for example `san_mateo`) while onboarding evaluation still tolerates legacy spaced-name rows during transition.
- Flip `enabled` in `city_metadata/city_rollout_registry.csv` only after a city's latest verification artifacts show `quality_gate=pass`.

### Host profiles (recommended)

M5 conservative baseline:
```bash
docker compose --env-file env/profiles/m5_conservative.env up -d --build inference worker api pipeline frontend
```

Desktop balanced:
```bash
docker compose --env-file env/profiles/desktop_balanced.env up -d --build inference worker api pipeline frontend
```

Historical M1 conservative reference:
```bash
docker compose --env-file env/profiles/m1_conservative.env up -d --build inference worker api pipeline frontend
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

Canonical batch hydration:
- `docker compose run --rm pipeline python run_pipeline.py` now performs:
  - extraction / NLP backfill
  - agenda segmentation backfill
  - summary hydration backfill
- This is the preferred way to repair broad local missing-summary backlogs after crawl/extraction succeeds.

Staged city hydration:
- For large legacy backlogs, prefer the staged hydrator instead of waiting on one full-corpus run:
```bash
docker compose run --rm pipeline python /app/scripts/staged_hydrate_cities.py --city hayward --city sunnyvale --city berkeley --segment-limit 25 --summary-limit 25 --segment-workers 2
docker compose run --rm pipeline python /app/scripts/staged_hydrate_cities.py --city cupertino --segment-limit 25 --summary-limit 25 --segment-workers 2
docker compose run --rm pipeline python /app/scripts/staged_hydrate_cities.py --city san_mateo --segment-limit 25 --summary-limit 25 --segment-workers 2
```
- The staged hydrator runs:
  - before snapshot
  - one bounded segmentation chunk
  - one bounded city summary pass
  - after snapshot / chunk delta
- Useful controls:
  - `--segment-limit`: max catalogs selected for one segmentation chunk
  - `--summary-limit`: max catalogs selected for one summary pass
  - `--segment-workers`: parent-side subprocess orchestration width
  - `--resume-after-id`: resume from the next catalog ID
  - `--max-chunks`: stop after a fixed number of chunks
- Use this when backlog size is skewed heavily toward one city and you need checkpointable progress with earlier summaries.
- Important operational note:
  - summary fanout can be much larger than the segmentation slice because one chunk can unlock many previously blocked city summaries
  - a single chunk can therefore spend more time in summary hydration than in segmentation
- Safe worker defaults:
  - HTTP inference (`LOCAL_AI_BACKEND=http`) defaults to `2` parent-side segmentation workers
  - guarded in-process LocalAI clamps staged segmentation back to `1`
- Resume example:
```bash
docker compose run --rm pipeline python /app/scripts/staged_hydrate_cities.py --city san_mateo --segment-limit 25 --summary-limit 25 --segment-workers 2 --resume-after-id 2500 --max-chunks 1
```
- Summary-stage troubleshooting:
  - per-catalog summary failures are partial, not all-or-nothing; the chunk continues and increments `error`
  - `LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS` is the primary timeout knob when summary hydration stalls on the HTTP inference path
  - `embed_catalog_task.dispatch_failed ... Authentication required` is downstream semantic hydration noise; it does not roll back summaries that were already written

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
