# Performance

Last verified: 2026-02-12

## User-facing benchmarks (local full stack)

| Operation | Previous | Optimized (E2E) | Engine Latency | Improvement |
| :--- | :--- | :--- | :--- | :--- |
| Search (Full Text) | 2000ms | 1.3s | 11ms | ~2x |
| City Metadata | 500ms | 5ms | <1ms | 100x |
| Official Profiles | 500ms | 10ms | 2ms | 50x |
| JSON Serialization | 125ms | 2ms | N/A | 60x |

Notes:
- These are local-machine measurements.
- E2E includes API/network/serialization overhead.
- Engine latency isolates backend compute/query time.
- GitHub Pages demo metrics are not equivalent: Pages runs static fixtures and bypasses backend services.

## Developer microbenchmarks

| Operation | Mean Latency | Throughput | Improvement |
| :--- | :--- | :--- | :--- |
| Fuzzy Name Matching (`find_best_person_match`) | 65.56 us | 15.25 K ops/s | Baseline |
| Regex Agenda Extraction | 778.98 us | 1.28 K ops/s | Baseline |
| Standard JSON Serialization (`json.dumps`) | 157.92 us | 6.33 K ops/s | Baseline |
| Rust JSON Serialization (`orjson.dumps`) | 8.56 us | 116.84 K ops/s | ~18.5x faster than stdlib JSON |

## How to reproduce

### Benchmark tests
```bash
docker compose run --rm pipeline pytest tests/test_benchmarks.py
```

### API load test (Locust)
```bash
docker compose run --rm pipeline locust -f tests/locustfile.py --headless -u 50 -r 5 --run-time 1m --host http://api:8000
```

## Optimization mechanisms currently in use
- Meilisearch payload controls (`attributesToRetrieve`, `attributesToCrop`)
- Redis caching for metadata/read-heavy paths
- SQLAlchemy eager loading (`joinedload`) for profile paths
- `orjson` for faster API serialization
