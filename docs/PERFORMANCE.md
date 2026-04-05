# Performance

Last updated: 2026-04-03

This page describes how to interpret and reproduce performance evidence for local Docker runs.
For operational troubleshooting and sorting diagnostics, use `docs/OPERATIONS.md`.

Important:
- Benchmarks here are environment-pinned examples, not universal guarantees.
- Promotion and regression decisions should compare like-for-like runs only.
- If the host, Docker version, runtime profile, model backend, or artifact state changes, treat the numbers as diagnostic rather than baseline-equivalent.
- The previous M1 Pro conservative results are historical reference only now that the active local baseline host is an M5 Pro MacBook Pro.

## Measurement Environment
Use this section as part of the evidence contract for any benchmark you want to compare against another run.

- Date: 2026-02-16
- Measured commit: `ba42bae`
- Mode: local Docker Compose stack
- Host platform: macOS 26.2 (arm64)
- API target for endpoint timing: `http://api:8000` (inside Docker network)
- Benchmark harness:
  - `pytest ../tests/test_benchmarks.py`
  - repeated endpoint timing loop (30 requests per endpoint)

Note:
- Docker daemon version was not captured in this measurement run.

Comparability checklist:
- Keep the same commit or record both commits explicitly.
- Keep the same runtime profile and inference backend settings.
- Keep the same dataset/index artifacts and semantic enablement state.
- Keep the same request mix, sample count, and warm/cold start conditions.
- Record any missing telemetry separately; missing metrics reduce confidence even when request success stays stable.

## Recent Performance Improvements

This section summarizes the recent Docker and runtime optimization work that changed the local performance profile. Use it as a compact history of the highest-signal improvements before diving into the detailed benchmark sections below.

### Docker Build and Image Optimization

| Phase | Main change | API image | Worker image | Other image(s) | Build timing impact | Result |
| :--- | :--- | ---: | ---: | ---: | :--- | :--- |
| Baseline | Monolithic shared Python image | N/A | N/A | old shared pipeline image: `~9.47GB` | cold `docker compose build --no-cache api worker frontend`: `181.15s` | large, slow shared build path |
| Model bootstrap split | Removed model downloads from image build | N/A | N/A | N/A | cold no-cache build: `181.15s -> 176.94s` | `4.21s` faster (`~2.3%`), but the main bottleneck remained |
| Role-based image split | Split into `crawler`, `api`, and `worker` images | `8.24GB` | `9.04GB` | `crawler`: `301MB` | `build crawler`: `17.19s`, `build api`: `61.93s`, `build worker`: `78.14s` | better targeted rebuild ownership, but API still carried semantic ML runtime |
| Venv-copy + CPU-only Torch | Removed duplicate wheel layers and GPU-class ML payloads | `8.24GB -> 1.42GB` | `9.04GB -> 2.1GB` | `crawler`: `301MB -> 297MB` | no-cache build: failed at `173.28s` before, passed in `105.25s` after | biggest storage/build improvement; fixed `no space left on device` |
| Worker runtime cleanup | Moved dev-only tooling out of the worker runtime image | `1.42GB -> 1.42GB` | `2.1GB -> 2.07GB` | N/A | `build worker`: `96.58s -> 53.76s` in the measured run | small size win, useful worker rebuild cleanup |
| Semantic service split | Moved semantic search out of API into internal `semantic` service | `1.42GB -> 345MB` | `2.07GB -> 2.07GB` | new `semantic`: `1.39GB` | API first rebuild: `40.62s -> 11.28s`; API warm rebuild: `0.72s`; worker warm rebuild: `0.73s` | API shed Torch/faiss/sentence-transformers entirely |
| Semantic worker split | Moved semantic build/index duties off the main worker and onto `semantic-worker` | `345MB -> 345MB` | `2.07GB -> 1.22GB` | `semantic`: `1.39GB -> 1.41GB` | `build worker`: `93.31s -> 35.95s`; `build semantic`: `44.80s -> 42.78s` | main worker no longer installs Torch/transformers/faiss; semantic build work now uses the semantic image |
| Worker-family split | Split the remaining worker family into `worker-core` and `worker-nlp` images | `345MB -> 345MB` | old shared worker: `1.22GB -> worker-core: 842MB` | `worker-nlp`: `1.89GB`; `semantic`: `1.41GB -> 1.41GB` | `build worker`: `73.57s -> 33.93s`; `build nlp`: `47.32s`; `build semantic`: `41.16s` | live Celery worker shed Camelot/OpenCV/Ghostscript; table-heavy tooling moved to the dedicated NLP image |
| Live/batch topology cleanup | Renamed the worker family to `worker-live` / `worker-batch`, moved `pipeline` onto the batch image, and turned `nlp` / `tables` / `topics` into on-demand profile services | `345MB -> 345MB` | `worker-core: 842MB -> worker-live: 842MB` | `worker-batch: 1.89GB`; `semantic`: `1.41GB -> 1.41GB` | `build worker`: `5.19s -> 31.67s`; `build pipeline`: `11.56s`; `build semantic`: `32.08s` | default startup no longer launches one-shot batch containers, `monitor` stays in the always-on stack, and batch tools now run explicitly with `docker compose run --rm ...` |
| Enrichment decoupling | Moved per-catalog topic generation onto `enrichment-worker`, moved `pipeline` back to `worker-live`, and split core pipeline vs batch enrichment entrypoints | `345MB -> 345MB` | `worker-live: 842MB -> 394MB` | `worker-batch: 1.89GB -> 1.22GB`; `semantic`: `1.41GB -> 1.41GB` | `build worker`: `5.19s -> 4.12s`; `build pipeline-batch`: `15.20s`; `build semantic`: `54.73s` | live worker no longer needs spaCy/TextRank/TF-IDF runtime, default startup keeps `pipeline-batch` off, and enrichment runs on its own queue/worker |

Current state:
- API image is now `345MB`, down from `1.42GB` before the semantic split.
- Live worker image is now `842MB`, down from the former single `1.22GB` worker image.
- Batch worker image is `1.89GB` and owns the Camelot/OpenCV/Ghostscript stack plus the broad `pipeline` orchestration path that no longer ships with the always-on live worker.
- Semantic runtime still lives in its own internal `1.41GB` image and also hosts the dedicated `semantic-worker`.
- Default local startup no longer launches `nlp`, `tables`, or `topics`; those run on demand or behind the `batch-tools` profile.

Interpretation:
- The API is now slim because semantic ML runtime moved into the internal `semantic` service.
- The main live Celery worker is now slimmer because table-heavy dependencies moved into the dedicated NLP image, while `spacy`, `pytextrank`, and `scikit-learn` intentionally stayed in the core image because current worker code paths still require them.
- Docker storage pressure is now driven more by persistent local data volumes and accumulated build cache than by API image bloat.

## End-to-end pipeline profiling

Use the profiling harness when the question is "what is actually slow on the critical path?" rather than "which image is large?"

Commands:
```bash
python scripts/profile_pipeline.py --mode triage
python scripts/build_profile_manifest.py --name <name>
python scripts/build_profile_manifest.py --name <name> --write
python scripts/profile_pipeline.py --mode baseline --manifest profiling/manifests/<name>.txt --dry-run-prepare
python scripts/profile_pipeline.py --mode baseline --manifest profiling/manifests/<name>.txt
python scripts/profile_pipeline.py --mode baseline --manifest profiling/manifests/<name>.txt --compare-to profiling/baselines/<name>.json
python scripts/analyze_pipeline_profile.py --run-id <run_id>
python scripts/analyze_pipeline_profile.py --run-id <run_id> --compare-to profiling/baselines/<name>.json
```

Artifacts:
- `experiments/results/profiling/<run_id>/run_manifest.json`
- `experiments/results/profiling/<run_id>/spans.jsonl`
- `experiments/results/profiling/<run_id>/summary.json`
- `experiments/results/profiling/<run_id>/top_bottlenecks.md`

What the profiler attributes:
- core orchestrator wall-clock time
- batch enrichment wall-clock time
- subprocess timings
- extraction chunk timings
- Celery queue wait (`tc_task_queue_wait_seconds`)
- task execution time (`tc_celery_task_duration_seconds`)
- phase timing (`tc_pipeline_phase_duration_seconds`)
- provider evidence correlation via existing `tc_provider_*` metrics

Confidence model:
- `baseline-valid`
  - pinned manifest
  - comparable workload identity
  - suitable for direct before/after comparisons
- `diagnostic-only`
  - ad hoc or triage workload
  - useful for local investigation, not promotion-style comparison
- `reduced-confidence`
  - missing queue timestamps, missing provider series, or incomplete artifacts

Ranking model:
- the analyzer ranks bottlenecks by critical-path phase contribution
- it separates queue wait from active execution time
- when both core pipeline and batch enrichment run, contribution percentages are computed against the combined elapsed total rather than only `pipeline_total`
- each top bottleneck is classified as one of:
  - `queueing`
  - `inference/provider`
  - `CPU/parsing`
  - `database/indexing`
  - `orchestration/serialization`

Interpretation rule:
- do not compare `triage` runs to baseline runs as if they were equivalent evidence
- use `baseline` runs for longitudinal comparison and `triage` runs for local diagnosis
- if the analyzer reports `reduced-confidence`, inspect `result.json` and run-quality notes before using the ranking to prioritize work
- selected-manifest profiling runs are workload-only by default, so unrelated global prelude work such as staged promotion and downloader retries should not appear in the ranked bottlenecks
- if a baseline manifest has a `.json` sidecar, the harness applies controlled preconditioning to only the selected workload before the run so the baseline still contains real pending work
- use `--dry-run-prepare` to inspect that preconditioning plan before mutating the selected workload
- use `--compare-to` to guard steady-state baselines against regressions in elapsed time, top bottleneck phases, and stable workload-shape counters
- the checked-in baseline expectation for the representative workload lives at `profiling/baselines/baseline_representative_v1.json`
- compare policy:
  - timings use percentage tolerances to absorb normal host variance
  - stable counters from `commands.log` are compared exactly
  - reduced-confidence or non-baseline-valid runs are reported as non-comparable, not clean passes

### Latest runtime optimization note

- The default core pipeline and batch enrichment paths no longer shell into full `python indexer.py` rebuilds.
- Search freshness now comes from targeted `reindex_catalog(...)` hooks in the writers that mutate indexed fields.
- Keep `python reindex_only.py` as the manual repair path for schema/settings changes or explicit full rebuilds.
- The default core and batch snapshot backfills now invoke summary/agenda/entity/org/people runners in-process instead of paying Python subprocess startup on every run.
- That change is mainly a profiling-fidelity and orchestration win: zero-work backlog phases should now be nearly free, which makes the next triage report more representative of actual useful work.
- The default batch topic path now hydrates only missing/stale catalogs through the single-catalog topic task instead of sweeping every content-bearing catalog.
- The default batch table path now preflights eligibility and skips the heavy Camelot subprocess on zero-work runs.
- The earlier `download` ranking in triage profiling was a workload-fidelity artifact; workload-only profiling now excludes unrelated staged URL work from selected-manifest runs.
- The near-no-op triage run that followed those fixes was still useful as a fidelity check, but not as a promotion-grade benchmark; representative baseline evidence now comes from a pinned manifest package plus controlled preconditioning.
- The next baseline optimization pass moved agenda and summary maintenance onto backlog-specific routing instead of the full interactive defaults:
  - agenda segmentation now runs heuristic-first in maintenance mode with a shorter maintenance timeout
  - summary hydration now uses a shorter maintenance timeout and deterministic fallback on provider timeout/unavailable failures
- On the same `baseline_representative_v1` manifest, that reduced combined elapsed time from `355.655s` in `pipeline_profile_baseline_20260402_020239` to `85.202s` in `pipeline_profile_baseline_20260402_023734`.
- After that change, `segment_agenda` dropped from `270.549s` to `0.178s`; `summarize` is now the primary remaining provider bottleneck.
- The next summary-focused pass made maintenance agenda summaries deterministic-first instead of paying for an LLM call that grounding checks often replaced anyway.
- On the same `baseline_representative_v1` manifest, that reduced combined elapsed time again from `85.202s` in `pipeline_profile_baseline_20260402_023734` to `17.165s` in `pipeline_profile_baseline_20260402_025623`.
- In that run, `summary_hydration_backfill` reported `agenda_deterministic_complete=12`, `llm_complete=0`, and `deterministic_fallback_complete=0`, and maintenance `summarize_agenda_items` provider calls disappeared from `commands.log`.
- After that change, the remaining top bottlenecks are `entity_backfill` (`6.849s`), `people_linking` (`5.277s`), and `summarize` (`2.764s`).
- The next batch-focused pass collapsed entity extraction and people linking into one delta-oriented path:
  - `entity_backfill` now keeps small snapshots in-process and commits once per chunk
  - `people_linking` now scopes itself to the catalogs whose entity payloads changed in that same run
- On the same `baseline_representative_v1` manifest, that reduced combined elapsed time from `17.165s` in `pipeline_profile_baseline_20260402_025623` to `12.391s` in `pipeline_profile_baseline_20260402_110906`.
- In that run, `entity_backfill` reported `selected=8 complete=8 changed_catalogs=8 execution_mode=in_process chunks=1`, and `people_linking_preflight` selected `8` catalogs instead of the previous full rescan of `30`.
- After that change, the top 3 shifted to `entity_backfill` (`6.060s`), `summarize` (`2.611s`), and `people_linking` (`1.433s`).
- The next entity-focused pass makes NER staleness-aware and cheap-first:
  - `catalog.entities_source_hash` now mirrors the freshness contract already used for summaries/topics
  - entity backfill now selects missing or stale rows instead of relying on `entities is null` only
  - agenda-heavy documents now build a smaller candidate slice from roll-call / attendance / motion / speaker cues before running spaCy
  - clearly low-signal docs can be marked fresh with an empty entity payload instead of repeatedly paying for the full NER pass
- On the same `baseline_representative_v1` manifest, that reduced combined elapsed time from `12.391s` in `pipeline_profile_baseline_20260402_110906` to `9.199s` in `pipeline_profile_baseline_20260402_220500`.
- In that run, `entity_backfill` reported `selected=8 complete=8 changed_catalogs=8 execution_mode=in_process chunks=1 ner_processed=8 ner_skipped_low_signal=0 freshness_advanced=8 candidate_slice_fallback_prefix=0`.
- After that change, the top 3 shifted to `summarize` (`3.647s`), `entity_backfill` (`1.486s`), and `people_linking` (`0.967s`).
- The next summary-focused pass batched deterministic agenda summary hydration and fixed the profile analyzer so deterministic summary runs are not mislabeled as provider-bound work:
  - maintenance agenda summaries now preload agenda items for the selected snapshot and persist changed rows before one targeted reindex/embed pass
  - the profiler now uses `summary_hydration_backfill` evidence from `commands.log` before classifying `summarize` as `inference/provider`
- On the same `baseline_representative_v1` manifest, that reduced combined elapsed time from `9.199s` in `pipeline_profile_baseline_20260402_220500` to `8.792s` in `pipeline_profile_baseline_20260402_231035`.
- In that run, `summary_hydration_backfill` reported `selected=12 complete=12 changed_catalogs=12 agenda_deterministic_complete=12 llm_complete=0 deterministic_fallback_complete=0 reindexed=0 reindex_failed=12 embed_enqueued=12 embed_dispatch_failed=0`.
- After that change, `summarize` remained the top bottleneck, but the report now classifies it as `CPU/parsing` with stage-local `provider_requests_total=0.0`, which matches the deterministic-only workload:
  - `summarize` `3.385s`
  - `entity_backfill` `1.532s`
  - `people_linking` `0.969s`
- The next summary-freshness pass made agenda summary hydration stale-aware via structured-input hashing:
  - `Catalog.agenda_items_hash` now fingerprints the normalized `AgendaItem` payload that deterministic agenda summaries actually depend on
  - deterministic agenda summaries now store `summary_source_hash = agenda_items_hash` instead of `content_hash`
  - the profiling harness now runs `pipeline/backfill_catalog_hashes.py` before baseline preconditioning so legacy agenda summaries are measured in steady state instead of one-time migration churn
- On the same `baseline_representative_v1` manifest, the rollout-skewed first run (`pipeline_profile_baseline_20260403_003945`) selected `21` agenda summaries because old rows were missing the new agenda hash metadata, but the steady-state baseline after backfill (`pipeline_profile_baseline_20260403_004122`) returned to `selected=12`.
- In the steady-state run, `summary_hydration_backfill` reported `selected=12 complete=12 changed_catalogs=12 agenda_deterministic_complete=12 llm_complete=0 deterministic_fallback_complete=0 reindexed=12 reindex_failed=0 embed_enqueued=12 embed_dispatch_failed=0`.
- After that change, the top 3 remained:
  - `summarize` `3.601s`
  - `entity_backfill` `1.576s`
  - `people_linking` `0.987s`
- This pass did not make deterministic agenda summaries dramatically cheaper per rebuild; it made the freshness contract correct so already-fresh agenda summaries can now be skipped once their structured input is unchanged.

### Other Performance-Related Changes

The detailed endpoint timing and soak sections below still apply, but recent runtime work changes how they should be interpreted:

- API endpoint timing examples now reflect a lighter API container path that no longer bundles the semantic ML stack by default.
- `/search/semantic` remains a public API route, but semantic execution now runs in the internal `semantic` service, so semantic timing should be treated as a separate runtime boundary from the main API image.
- Recent Docker/runtime work reduced API container overhead, while worker and inference tuning remain the main remaining levers for end-to-end throughput and soak stability.

## API Endpoint Timing (E2E, 30 samples each)

| Endpoint | p50 (ms) | p95 (ms) | Min (ms) | Max (ms) |
| :--- | ---: | ---: | ---: | ---: |
| `GET /search?q=zoning&sort=newest&limit=20` | 117.31 | 130.27 | 115.08 | 163.85 |
| `GET /metadata` | 1.40 | 1.89 | 1.06 | 10.57 |
| `GET /people?limit=50` | 4.08 | 4.58 | 2.76 | 20.46 |

## Hybrid Semantic Discovery: Semantic Endpoint Timing

Semantic endpoint timing should be measured after:
1. `SEMANTIC_ENABLED=true`
2. semantic artifacts are built (`docker compose run --rm semantic python ../pipeline/reindex_semantic.py`)

Suggested benchmark endpoint:
- `GET /search/semantic?q=zoning&limit=20`

Track:
- p50/p95 latency
- `semantic_diagnostics.k_used`
- `semantic_diagnostics.expansion_steps`
- `semantic_diagnostics.engine` (`faiss` preferred; `numpy` fallback is expected to be slower)
- `semantic_diagnostics.retrieval_mode` (`hybrid_pgvector` indicates meeting-level lexical recall + pgvector rerank)
- `semantic_diagnostics.degraded_to_lexical` and `semantic_diagnostics.skipped_reason`
- `semantic_diagnostics.fresh_embeddings`, `missing_embeddings`, and `stale_embeddings`

## Inference Decoupling & Throughput Stabilization: Runtime Profile

Default conservative profile for rollout:
- `LOCAL_AI_BACKEND=http`
- worker concurrency: `3`
- inference service caps: ~4GB RAM / 2 CPU
- inference parallelism: `OLLAMA_NUM_PARALLEL=1`
- timeout budget includes internal inference queue wait (`LOCAL_AI_HTTP_TIMEOUT_SECONDS=300` in the conservative baseline profile)
- operation budgets can be split:
  - `LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS` (usually highest)
  - `LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS`
  - `LOCAL_AI_HTTP_TIMEOUT_TOPICS_SECONDS`

Promotion rule:
- move to a balanced profile only after one week of clean SLOs.
- a passing conservative week makes balanced eligible for opt-in evaluation only; conservative remains the default recommendation.

Provider telemetry for promotion gate:
- `tc_provider_requests_total` by `{provider,operation,model,outcome}`
- `tc_provider_request_duration_ms` histogram
- `tc_provider_timeouts_total`
- `tc_provider_retries_total`
- `tc_provider_ttft_ms` histogram
- `tc_provider_tokens_per_sec` histogram
- `tc_provider_prompt_tokens_total`
- `tc_provider_completion_tokens_total`

Prefork note:
- Provider telemetry is mirrored to a Redis-backed aggregate so `tc_provider_*` series are visible
  from the worker metrics endpoint under `WORKER_POOL=prefork`.
- This keeps runtime behavior unchanged while preserving TTFT/TPS observability.

Token/throughput formulas (HTTP provider, best-effort):
- `ttft_ms = prompt_eval_duration_ns / 1_000_000`
- `tokens_per_sec = eval_count / (eval_duration_ns / 1_000_000_000)` when `eval_duration_ns > 0`
- `prompt_tokens = prompt_eval_count`
- `completion_tokens = eval_count`

Notes:
- These fields are emitted only when the inference backend returns the corresponding stats.
- Missing stats do not affect task success; baseline request metrics still emit.
- Search indexing now exposes truncation observability metadata:
  - `content_truncated`
  - `original_content_chars`
  - `indexed_content_chars`
  Monitor truncated-document ratio from indexer logs to assess recall impact of `MAX_CONTENT_LENGTH`.

Interpretation:
- sustained timeout/retry growth under `LOCAL_AI_HTTP_PROFILE=conservative` blocks promotion.
- balanced profile is only eligible when provider timeout/retry counters remain low and task failure rates stay stable.
- concurrency throttling belongs in inference infrastructure (`OLLAMA_NUM_PARALLEL`), not in model-identity app logic.

## Inference Decoupling & Throughput Stabilization Promotion Gate Thresholds

Apply these thresholds over a 7-day conservative soak:
- Note: extract-phase failures are non-gating warnings in this soak iteration; segment/summarize remain gating.
- `provider_timeout_rate < 1.0%`
- `timeout_storms = 0`
- `queue_wait_p95`: no sustained upward backlog trend
- `search_p95_regression_pct <= 15%`
- segment/summary p95: stable vs baseline (no persistent degradation)
- `ttft_ms` and `tokens_per_sec`: no persistent adverse drift

Fail policy:
- if any gate fails, remain conservative and tune infra before re-running soak.
- if any gate is `INCONCLUSIVE` (insufficient telemetry evidence), remain conservative and restore telemetry quality before re-running soak.

## Soak automation metric semantics

The soak harness writes one `day_summary.json` per run under:
- `experiments/results/soak/<run_id>/day_summary.json`

Weekly evaluation (`scripts/evaluate_soak_week.py`) uses:
- run-local provider deltas captured from `run_manifest.json` baseline counters plus the post-run worker scrape
- cumulative provider totals remain observational only
- a successful pre-run worker scrape with no provider series yet counts as a zero baseline, not missing evidence

Why:
- Prometheus counters are cumulative across runs; promotion gates need per-run evidence so the first day of a window is not contaminated by pre-window history.

Current queue signal:
- `queue_wait_p95` is approximated by `phase_duration_p95_s_capped` when available, otherwise `phase_duration_p95_s`.
- This is an operational proxy until explicit queue wait metrics are exported.

Soak confidence signals:
- `worker_metrics_error` is recorded when worker metrics cannot be scraped.
- `provider_metrics_present` and `provider_metrics_reason` classify whether provider series were observed (`ok`, `worker_scrape_failed`, `no_provider_series`).
- `worker_scrape_failed` means both worker scrape strategies failed (HTTP endpoint probe and process-registry fallback) after bounded retries.
- `no_provider_series` means the scrape succeeded but no `tc_provider_*` series were observed; this is still valid pre-run zero-baseline evidence, but it reduces post-run interpretability if successful phases never emit provider requests.
- Missing worker metrics do not crash collection, but reduce confidence for TTFT/TPS trend interpretation.
- Weekly evaluator emits `telemetry_confidence` and `degraded_telemetry_days` to make this explicit.
- Weekly evaluator now reports per-gate status as `PASS|FAIL|INCONCLUSIVE` with machine-readable `gate_reasons`.
- Weekly evaluator also reports `baseline_valid`, `baseline_artifact_days`, and `evidence_quality_reasons`.

## Baseline interpretation

- `baseline-valid` runs:
  - consistent local baseline conditions across the soak window
  - `run_manifest.json` present for each day
  - run-local provider delta fields present for each day
  - suitable for promotion-gate interpretation
- `non-baseline` runs:
  - manual probes, experiments, mixed runtime conditions, or legacy cumulative-only artifacts
  - useful for diagnostics, not for baseline promotion decisions
  - after the M5 Pro host change, use a fresh 7-day conservative M5 window for promotion-grade comparisons

Metric interpretation policy:
- Gate-driving metrics: timeout rate, timeout storms, queue proxy trend, search regression, segment/summary stability.
- Observational metrics: TTFT/TPS/token telemetry and related confidence annotations.
- Existing gate thresholds in this document are unchanged by this docs sync.

Current evidence note:
- The March 6-12, 2026 conservative window remains diagnostically useful.
- It is not promotion-grade after the artifact-contract hardening because it predates the run-local delta fields required for `baseline-valid` evaluation.
- Treat pre-M5 host windows as historical diagnostics rather than the active local baseline.

## A/B Experiment Artifacts

For `270M` runtime-profile runs (`conservative` vs `balanced`), evaluate:
- section compliance delta
- fallback and grounding deltas
- summary/segment p95 deltas
- failure-rate delta
- observational telemetry rollups (non-gating):
  - TTFT median/p95 (`ttft_ms`)
  - throughput median (`tokens_per_sec`)
  - prompt/completion/total token totals

Primary outputs:
- `experiments/results/ab_report_v1.md`
- `experiments/results/ab_score_<runs>.json`

## Issue Threads Foundation (`C v1`): Trends + Lineage Endpoint Timing

Suggested benchmark endpoints:
- `GET /trends/topics?limit=10`
- `GET /trends/compare?cities=berkeley&cities=cupertino&date_from=2025-01-01&date_to=2025-12-31`
- `GET /catalog/<CATALOG_ID>/lineage`

Track:
- p50/p95 latency
- trends request volume and error rate
- lineage recompute counters (`tc_lineage_recompute_runs_total`, `tc_lineage_catalog_updates_total`)

## Developer Microbenchmarks

Measured via:
```bash
docker compose run --rm pipeline pytest ../tests/test_benchmarks.py -q
```

| Benchmark | Mean | Throughput |
| :--- | ---: | ---: |
| `test_benchmark_orjson_serialization` | 17.53 us | 57.04 K ops/s |
| `test_benchmark_fuzzy_matching` | 48.48 us | 20.63 K ops/s |
| `test_benchmark_standard_json_serialization` | 168.55 us | 5.93 K ops/s |
| `test_benchmark_regex_extraction` | 766.74 us | 1.30 K ops/s |

## Reproduce

### Microbenchmarks
```bash
docker compose run --rm pipeline pytest ../tests/test_benchmarks.py -q
```

### Endpoint timing
```bash
docker compose run --rm pipeline python - <<'PY'
import time, statistics, urllib.request
base='http://api:8000'
endpoints=[
    ('search_newest','/search?q=zoning&sort=newest&limit=20'),
    ('search_semantic','/search/semantic?q=zoning&limit=20'),
    ('metadata','/metadata'),
    ('people','/people?limit=50')
]
N=30
for name,path in endpoints:
    samples=[]
    for _ in range(N):
        t0=time.perf_counter()
        with urllib.request.urlopen(base+path, timeout=10) as r:
            r.read()
        samples.append((time.perf_counter()-t0)*1000)
    p50=statistics.median(samples)
    p95=sorted(samples)[int(0.95*len(samples))-1]
    print(f"{name} p50_ms={p50:.2f} p95_ms={p95:.2f} min_ms={min(samples):.2f} max_ms={max(samples):.2f}")
PY
```

Recommended rerun notes:
- Record the measured commit, host platform, Docker version, and whether the stack was already warm.
- For endpoint timing, keep the same sample count and endpoint list when comparing against prior runs.
- For semantic timing, note whether artifacts were freshly built or reused.
- Treat one-off manual probes as diagnostic only unless they match the baseline conditions above.

## Reproducible benchmark capture

Historical note:
- The former benchmark capture helper has been retired from the active `scripts/` surface.
- Its implementation remains under `archive/scripts/` as historical experiment reference only, not as a supported fallback command.
- If benchmark capture becomes an active workflow again, restore a supported entrypoint with fresh docs and tests instead of pointing operators at archived code.
