# Performance

Last verified: 2026-02-16

This page lists current empirical measurements for local Docker runs.
For operational troubleshooting and sorting diagnostics, use `docs/OPERATIONS.md`.

## Measurement Environment
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

## API Endpoint Timing (E2E, 30 samples each)

| Endpoint | p50 (ms) | p95 (ms) | Min (ms) | Max (ms) |
| :--- | ---: | ---: | ---: | ---: |
| `GET /search?q=zoning&sort=newest&limit=20` | 117.31 | 130.27 | 115.08 | 163.85 |
| `GET /metadata` | 1.40 | 1.89 | 1.06 | 10.57 |
| `GET /people?limit=50` | 4.08 | 4.58 | 2.76 | 20.46 |

## Semantic Endpoint Timing (Milestone B)

Semantic endpoint timing should be measured after:
1. `SEMANTIC_ENABLED=true`
2. semantic artifacts are built (`python reindex_semantic.py`)

Suggested benchmark endpoint:
- `GET /search/semantic?q=zoning&limit=20`

Track:
- p50/p95 latency
- `semantic_diagnostics.k_used`
- `semantic_diagnostics.expansion_steps`
- `semantic_diagnostics.engine` (`faiss` preferred; `numpy` fallback is expected to be slower)

## D2-lite Runtime Profile (Milestone D)

Default conservative profile for rollout:
- `LOCAL_AI_BACKEND=http`
- worker concurrency: `3`
- inference service caps: ~4GB RAM / 2 CPU
- inference parallelism: `OLLAMA_NUM_PARALLEL=1`
- timeout budget includes internal inference queue wait (`LOCAL_AI_HTTP_TIMEOUT_SECONDS=300` on M1 profile)

Promotion rule:
- move to a balanced profile only after one week of clean SLOs.

Provider telemetry for promotion gate:
- `tc_provider_requests_total` by `{provider,operation,model,outcome}`
- `tc_provider_request_duration_ms` histogram
- `tc_provider_timeouts_total`
- `tc_provider_retries_total`

Interpretation:
- sustained timeout/retry growth under `LOCAL_AI_HTTP_PROFILE=conservative` blocks promotion.
- balanced profile is only eligible when provider timeout/retry counters remain low and task failure rates stay stable.
- concurrency throttling belongs in inference infrastructure (`OLLAMA_NUM_PARALLEL`), not in model-identity app logic.

## A/B Experiment Artifacts

For `270M` runtime-profile runs (`conservative` vs `balanced`), evaluate:
- section compliance delta
- fallback and grounding deltas
- summary/segment p95 deltas
- failure-rate delta

Primary outputs:
- `experiments/results/ab_report_v1.md`
- `experiments/results/ab_score_<runs>.json`

## Trends + Lineage Endpoint Timing (Milestone C v1)

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
