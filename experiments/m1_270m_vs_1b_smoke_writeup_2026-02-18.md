# M1 Smoke Evaluation Write-up: `gemma-3-270m-custom` vs `gemma3:1b`

Date: 2026-02-18  
Environment: MacBook Pro (M1), D2-lite M1 conservative profile

## 1) Problem Statement
The pipeline experienced timeout/retry loops during local HTTP inference. We needed to determine whether this was primarily a model/runtime latency issue under concurrent worker load, and quantify behavior for `gemma-3-270m-custom` versus `gemma3:1b` using the same end-to-end flow.

## 2) Methodology
Step-by-step:
1. Use the same stack topology and task flow for both models.
2. Execute forced pipeline endpoints in sequence per catalog:
   - `POST /extract/{cid}?force=true&ocr_fallback=false`
   - `POST /segment/{cid}?force=true`
   - `POST /summarize/{cid}?force=true`
3. Run the same representative catalogs for both models:
   - `CID=609` (single-item agenda)
   - `CID=933` (multi-item agenda)
4. Collect metrics from Celery worker logs (`Task ... succeeded in ...`, `provider_request ... duration_ms=...`, timeout outcomes), task status endpoint, and DB summary lengths.

Profile used:
- `LOCAL_AI_BACKEND=http`
- `WORKER_CONCURRENCY=3`
- `WORKER_POOL=prefork`
- `OLLAMA_NUM_PARALLEL=1`
- `LOCAL_AI_HTTP_TIMEOUT_SECONDS=300` (for the 1B run)

## 3) Models Tested
1. `gemma-3-270m-custom`
2. `gemma3:1b`

## 4) Model Provenance
### `gemma-3-270m-custom`
- Source artifact in repo build path: Hugging Face `unsloth/gemma-3-270m-it-GGUF`, file `gemma-3-270m-it-Q4_K_M.gguf` (downloaded in Docker image build).
- Served through local inference HTTP backend using local model alias `gemma-3-270m-custom`.

### `gemma3:1b`
- Pulled directly from Ollama registry via:
  - `docker compose exec -T inference ollama pull gemma3:1b`
- Pull output indicated ~815 MB model payload.

## 5) Metrics Collected
### 5.1 Per-step wall-clock durations (Celery task runtime)

| Model | CID | Extract (s) | Segment (s) | Summarize (s) | Total (s) |
|---|---:|---:|---:|---:|---:|
| 270M | 609 | 0.638 | 47.180 | 11.365 | 59.183 |
| 270M | 933 | 0.118 | 104.947 | 31.919 | 136.984 |
| 1B | 609 | 0.886 | 202.998 | 74.174 | 278.058 |
| 1B | 933 | 0.149 | 601.283 | 195.841 | 797.273 |

### 5.2 Inference call durations (`provider_request ... duration_ms`)

| Model | CID | Operation | Attempt | Outcome | Duration (ms) |
|---|---:|---|---:|---|---:|
| 270M | 609 | segment generate | 1 | ok | 47,117 |
| 270M | 609 | summary generate | 1 | ok | 10,922 |
| 270M | 933 | segment generate | 1 | ok | 103,793 |
| 270M | 933 | summary generate | 1 | ok | 31,859 |
| 1B | 609 | segment generate | 1 | ok | 202,936 |
| 1B | 609 | summary generate | 1 | ok | 73,673 |
| 1B | 933 | segment generate | 1 | timeout | 300,112 |
| 1B | 933 | segment generate | 2 | timeout | 300,106 |
| 1B | 933 | summary generate | 1 | ok | 195,685 |

### 5.3 Task stability outcomes
- 270M run: all tasks completed, no timeouts observed in this smoke.
- 1B run: 933 segmentation hit two 300s timeouts; task still completed after fallback path and long runtime.

### 5.4 Output indicators
- 270M summary lengths in DB:
  - CID 609: 1340 chars
  - CID 933: 1230 chars
- Both runs produced completed summaries for tested CIDs.

## 6) Conclusions and Insights
1. Under this M1 profile, `gemma3:1b` is materially slower than 270M.
   - ~4.7x slower total on CID 609.
   - ~5.8x slower total on CID 933.
2. Timeout risk remains significant for 1B even with a 300s timeout budget when large segmentation calls are involved.
3. The dominant pain point is long segmentation generation latency under constrained parallel execution, not extraction overhead.
4. The 270M model remains the operationally stable default for this environment.

## 7) Out of Scope
1. Full decision-grade randomized A/B experiment with repeated runs and manual blinded scoring.
2. Desktop/GPU profile execution and comparison.
3. Token-accurate throughput instrumentation (true prompt/completion token counts and TTFT).
4. Quality scoring rubric beyond pipeline completion/structure stability in this smoke pass.

## 8) Remaining Questions
1. Can batched/overlapping segmentation windows reduce 1B timeout probability without unacceptable quality loss at chunk boundaries?
2. What are exact TTFT, prompt token, and completion token distributions per operation for 270M vs 1B?
3. On desktop profile (`OLLAMA_NUM_PARALLEL>=4`), does 1B clear latency and timeout gates while improving quality enough to justify use?
4. Should segmentation and summarization have separate timeout budgets by model and workload class?

## 9) Recommendation
For M1-class local runs, keep `gemma-3-270m-custom` as default. Treat 1B as optional and environment-specific until additional batching/token-telemetry experiments prove acceptable latency and timeout behavior.
