# Performance

Last updated: 2026-03-29

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

Current state:
- API image is now `345MB`, down from `1.42GB` before the semantic split.
- Core worker image is now `842MB`, down from the former single `1.22GB` worker image.
- NLP/table/topic image is now `1.89GB` and owns the Camelot/OpenCV/Ghostscript stack that no longer ships with the live Celery worker.
- Semantic runtime still lives in its own internal `1.41GB` image and also hosts the dedicated `semantic-worker`.

Interpretation:
- The API is now slim because semantic ML runtime moved into the internal `semantic` service.
- The main live Celery worker is now slimmer because table-heavy dependencies moved into the dedicated NLP image, while `spacy`, `pytextrank`, and `scikit-learn` intentionally stayed in the core image because current worker code paths still require them.
- Docker storage pressure is now driven more by persistent local data volumes and accumulated build cache than by API image bloat.

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

Preferred entrypoint:
```bash
python scripts/run_benchmarks.py
```

This writes benchmark artifacts under `experiments/results/benchmarks/<timestamp>/` with:
- `metadata.json`
- `pytest_benchmark.json`
- `endpoint_timings.json`

`metadata.json` captures the comparability contract:
- commit SHA and short SHA
- dirty worktree status
- host/platform metadata
- benchmark commands and exit codes

Recommended usage notes:
- run from a clean worktree when you want promotion-grade comparison
- keep the same runtime profile, dataset/index state, and endpoint sample count across runs
- use `--skip-endpoint-benchmarks` when the API stack is not available
- use `--skip-pytest-benchmarks` when you only want endpoint timings
