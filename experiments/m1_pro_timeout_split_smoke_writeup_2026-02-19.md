# M1 Pro D2-lite Timeout-Split Smoke Write-up (2026-02-19)

## 1) Problem statement
D2-lite moved inference to HTTP with worker concurrency >1. On Apple Silicon, concurrent requests can queue at the inference server and exceed a single global timeout, causing retry loops. The goal of this smoke was to validate the timeout-split configuration on **M1 Pro** using the conservative profile and confirm stable completion of extract/segment/summarize.

## 2) Methodology
1. Runtime profile: `env/profiles/m1_conservative.env`.
2. Services: `inference`, `worker`, `api`, `pipeline` via Docker Compose.
3. Test catalogs: `609`, `933`.
4. For each catalog, executed sequentially:
   - `POST /extract/{cid}?force=true&ocr_fallback=false`
   - `POST /segment/{cid}?force=true`
   - `POST /summarize/{cid}?force=true`
5. Polled `/tasks/{task_id}` to terminal state and measured wall-clock seconds per stage.

## 3) Models tested
- **Tested in this run:** `gemma-3-270m-custom` (HTTP backend).
- **Not run in this smoke:** `gemma3:1b`.

## 4) Model provenance
- Runtime selection:
  - `/Users/dennisshah/Documents/GitHub/town-council/env/profiles/m1_conservative.env:3`
  - `/Users/dennisshah/Documents/GitHub/town-council/pipeline/config.py:107`
- Compose defaults:
  - `/Users/dennisshah/Documents/GitHub/town-council/docker-compose.yml:49`
  - `/Users/dennisshah/Documents/GitHub/town-council/docker-compose.yml:284`
- Source model artifact in image build:
  - `/Users/dennisshah/Documents/GitHub/town-council/Dockerfile:97`
  - `unsloth/gemma-3-270m-it-GGUF` file `gemma-3-270m-it-Q4_K_M.gguf`

## 5) Metrics collected
### 5.1 Config under test
- `LOCAL_AI_BACKEND=http`
- `WORKER_CONCURRENCY=3`
- `WORKER_POOL=prefork`
- `OLLAMA_NUM_PARALLEL=1`
- `LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS=300`
- `LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS=180`
- `LOCAL_AI_HTTP_TIMEOUT_TOPICS_SECONDS=180`

### 5.2 Stage timing results (wall-clock)
| Catalog | Stage     | Status   | Wall sec |
|--------:|-----------|----------|---------:|
| 609     | extract   | complete | 2        |
| 609     | segment   | complete | 48       |
| 609     | summarize | complete | 12       |
| 933     | extract   | complete | 2        |
| 933     | segment   | complete | 104      |
| 933     | summarize | complete | 24       |

### 5.3 Derived checks
- Terminal failures: `0/6` stages.
- Segment p95 (n=2, nearest-rank): `104s`.
- Summarize p95 (n=2, nearest-rank): `24s`.
- Observed timeout/retry storm: **none** in this smoke.

## 6) Conclusions and insights
1. Timeout split is functioning as intended for `270m` on M1 Pro conservative profile.
2. Segment remains the dominant latency stage; summary is materially faster.
3. Current conservative budget provides comfortable headroom for tested heavy case (`CID 933 segment=104s` vs 300s budget).

## 7) Out of scope
1. 1B model performance/quality in this run.
2. Quality rubric scoring (this smoke focused on reliability/latency).
3. Throughput under sustained multi-catalog parallel load.
4. End-user UI latency characterization.

## 8) Remaining questions
1. Can M1 Pro safely tighten segment timeout from 300s to ~240s without regressions across a larger set?
2. Should segmentation and summarization use separate retry budgets in addition to separate timeouts?
3. What p95/p99 queue-wait and stage-latency targets should gate promotion from conservative to balanced?
4. Should we add explicit tokens/sec and TTFT instrumentation at provider layer for future comparisons?
