# Performance

Last verified: 2026-02-16

This page lists current empirical measurements for local Docker runs.
For operational troubleshooting and sorting diagnostics, use `docs/OPERATIONS.md`.

## Measurement Environment
- Date: 2026-02-16
- Mode: local Docker Compose stack
- API target for endpoint timing: `http://api:8000` (inside Docker network)
- Benchmark harness:
  - `pytest ../tests/test_benchmarks.py`
  - repeated endpoint timing loop (30 requests per endpoint)

## API Endpoint Timing (E2E, 30 samples each)

| Endpoint | p50 (ms) | p95 (ms) | Min (ms) | Max (ms) |
| :--- | ---: | ---: | ---: | ---: |
| `GET /search?q=zoning&sort=newest&limit=20` | 117.31 | 130.27 | 115.08 | 163.85 |
| `GET /metadata` | 1.40 | 1.89 | 1.06 | 10.57 |
| `GET /people?limit=50` | 4.08 | 4.58 | 2.76 | 20.46 |

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
