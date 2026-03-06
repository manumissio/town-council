# Town Council Pipeline Guide

Last updated: 2026-03-06

## 1) Purpose and Boundaries

### What this document covers
This document explains how Town Council's pipeline works end-to-end, including:
- batch processing flow (`pipeline/run_pipeline.py`)
- async write/generation flow (`api/main.py` + `pipeline/tasks.py`)
- inference, data freshness, observability, and failure handling

### What this document does not replace
- `README.md`: setup and quickstart
- `ARCHITECTURE.md`: stable system boundaries/contracts
- `docs/OPERATIONS.md`: commands, troubleshooting procedures, and runbooks

### Why this exists
Pipeline behavior spans multiple modules and services; onboarding is slower if contributors only see isolated files or command snippets. This guide connects those pieces into one operational model.

## 2) Pipeline Mental Model

Town Council uses two complementary pipelines:

1. Batch pipeline (dataset-wide, offline):
- executes broad enrichment/indexing work across many records
- primary entrypoint: `pipeline/run_pipeline.py`

2. Async pipeline (record-scoped, on demand):
- executes user-triggered writes and generation through background tasks
- primary entrypoints: protected API write endpoints in `api/main.py` and tasks in `pipeline/tasks.py`

### Why both pipelines exist
- Batch pipeline provides broad consistency and index freshness.
- Async pipeline provides bounded-latency, user-driven regeneration without blocking request threads.

## 3) Batch Pipeline Walkthrough (`pipeline/run_pipeline.py`)

### Stage A: Setup and ingest prerequisites
- `db_migrate.py`
- `seed_places.py`
- `promote_stage.py`
- `downloader.py`

Why this exists:
- Later stages assume canonical rows, valid schema, and local files already present.

### Stage B: Parallel document processing
`run_parallel_processing()` finds records missing extracted text/entities and processes them in chunked parallel workers.

Per-record behavior in `process_document_chunk()`:
- extract text when needed
- compute/repair `content_hash`
- run entity extraction when needed
- commit per record

Why this exists:
- Chunked parallelism improves throughput.
- Per-record commits preserve partial progress if a later record fails.

### Stage C: Post-processing and indexing
- `table_worker.py`
- `backfill_orgs.py`
- `topic_worker.py`
- `person_linker.py`
- `indexer.py`

Why this exists:
- These depend on extracted/normalized content from earlier stages.
- Search and UI behavior depends on this final indexing step.

## 4) Async Task Pipeline Walkthrough (`api/main.py` -> `pipeline/tasks.py`)

### Request lifecycle
1. UI/client calls protected write endpoint (for example `POST /summarize/{catalog_id}`).
2. API enqueues a Celery task.
3. Worker executes task logic and persists outputs.
4. Client polls `GET /tasks/{task_id}` until terminal state.

### Task families and writes
- `extract`: refreshes canonical content (`catalog.content`) and `content_hash`.
- `segment`: computes structured agenda items and segmentation status fields.
- `summarize`: writes summary outputs and source-hash linkage.
- `topics`: writes topic outputs and source-hash linkage.
- `votes`: runs vote extraction/update logic over agenda items.

Why this exists:
- Heavy extraction/generation work is isolated from synchronous API reads.
- Task lifecycle makes long-running work observable and retryable.

### Gating vs non-gating (operational)
In soak/task orchestration contexts, not all failures are weighted equally (for example extract can be non-gating while segment/summarize is gating).

Why this exists:
- Keeps baseline reliability judgments tied to user-visible generation stages.

## 5) OCR Extraction Path

### OCR decision flow (`pipeline/extractor.py`)
1. First pass always uses Tika with `X-Tika-PDFOcrStrategy: no_ocr` (fast, digital text layer only).
2. If extracted text is present and has at least the minimum threshold, return it.
3. If text is empty/too short and OCR fallback is enabled, retry with `X-Tika-PDFOcrStrategy: ocr_only` (slower, CPU-heavy).
4. Apply text post-processing and persist cleaned text.
5. Ensure extracted text contains `[PAGE N]` markers for deep-linking and downstream page-aware logic.

Why this exists:
- Most civic PDFs already contain selectable text; always-on OCR wastes time and CPU.
- OCR fallback recovers scanned/image-heavy packets when digital text is missing or weak.

### Where OCR is triggered

| Path | Trigger | OCR behavior | Cache/force behavior |
|---|---|---|---|
| Batch pipeline (`pipeline/run_pipeline.py` -> extraction paths) | Batch processing records that need extraction | Uses config defaults through extractor (`TIKA_OCR_FALLBACK_ENABLED`) | No API force flag; behavior follows pipeline extraction conditions |
| Async API (`POST /extract/{catalog_id}` in `api/main.py`) | User-triggered re-extraction, optional `ocr_fallback=true` | Passes `ocr_fallback` query flag into task | API short-circuits to `cached` when `force=false` and content length is already substantial |
| Async task (`extract_text_task` in `pipeline/tasks.py`) | Celery worker execution for one catalog | Calls `reextract_catalog_content(..., ocr_fallback=...)`, which passes per-call OCR setting into extractor | Returns `cached` unless `force=true` when existing text meets minimum chars; updates content/hash only on successful extraction |

### OCR/Tika config defaults (`pipeline/config.py`)

| Variable | Default | Meaning |
|---|---|---|
| `TIKA_OCR_FALLBACK_ENABLED` | `false` | Enables second-pass OCR when first-pass text is empty/too short |
| `TIKA_MIN_EXTRACTED_CHARS_FOR_NO_OCR` | `800` | Minimum chars for first-pass text to be considered good enough |
| `TIKA_TIMEOUT_SECONDS` | `60` | Request timeout for a single Tika extraction call |
| `TIKA_RETRY_BACKOFF_MULTIPLIER` | `2` | Backoff multiplier across up to 3 extractor attempts |
| `TIKA_PDF_SPACING_TOLERANCE` | unset | Optional PDFBox spacing tuning header (off by default) |
| `TIKA_PDF_AVG_CHAR_TOLERANCE` | unset | Optional PDFBox average-char tuning header (off by default) |

### OCR failure and triage notes
- Fail-fast cases (no retry path): catalog missing, missing/placeholder location, unsafe path, or missing file on disk.
- Retryable extraction failure in async task flow: `"Extraction returned empty text"` is treated as transient and retried by Celery (`max_retries=3`).
- Extractor-level retry behavior: each Tika strategy call retries up to 3 attempts with backoff.
- Operational re-extraction entrypoint: see `docs/OPERATIONS.md` (`POST /extract/{catalog_id}?force=true&ocr_fallback=true`).

Why this exists:
- Makes OCR behavior explicit for debugging slow extraction, empty-text errors, and scan-heavy document recovery.

## 6) Inference Layer and Policy

### Core modules
- `pipeline/llm.py`: orchestration policy (prompting, grounding/fallback orchestration)
- `pipeline/llm_provider.py`: backend transport abstraction (`inprocess` / `http`)

### Typed provider errors
- `ProviderTimeoutError`
- `ProviderUnavailableError`
- `ProviderResponseError`

Why this exists:
- Task orchestration must distinguish retryable transport failures from deterministic response failures.

### Local-first and fail-fast constraints
- Local-first defaults for contributor workflows.
- Optional remote acceleration is opt-in.
- No silent remote/local fallback policy.

Why this exists:
- Preserves reproducibility and avoids hidden mode shifts during baseline operations.

## 7) Data Contracts and Freshness

### Freshness keys and state contracts
- `catalog.content_hash`: hash of extracted text version.
- `catalog.summary_source_hash`: source hash tied to current summary.
- `catalog.topics_source_hash`: source hash tied to current topics.
- Agenda segmentation status fields on `catalog`.

### Stale vs fresh behavior
If source hashes diverge, derived values can be marked stale and regeneration paths are exposed via API/task flows.

Why this exists:
- Prevents presenting outdated derived outputs as current truth.
- Makes regeneration explicit and auditable.

### Agenda-summary coupling
Agenda summaries are derived from segmented agenda items, not arbitrary raw text.

Why this exists:
- Prevents drift between Structured Agenda and AI Summary.

## 8) Observability and Soak Linkage

### Pipeline observability surfaces
- API metrics endpoint (`/metrics`)
- Worker metrics exporter
- Provider telemetry series (`tc_provider_*`)
- Task-level duration/failure/retry signals

### Soak integration points
- daily task run artifact (`tasks.jsonl`, `day_summary.json`)
- metrics snapshot artifacts (`api_metrics.prom`, `worker_metrics.prom`)
- 7-day evaluation output (`soak_eval_7d.json`, `soak_eval_7d.md`)

### Why confidence and inconclusive semantics exist
Telemetry can be missing/degraded even when some tasks complete; promotion decisions need explicit confidence semantics (`PASS`/`FAIL`/`INCONCLUSIVE`) rather than collapsing missing evidence into ambiguous outcomes.

## 9) Failure Mode Matrix

| Signature | Likely Root Cause | First Places to Check | Why Check Order Works |
|---|---|---|---|
| `missing_task_id` | API enqueue/write endpoint response issue | `api/main.py`, endpoint response payload, task queue health | Fastest way to confirm enqueue contract break |
| `task_poll_timeout` | worker backlog/inference stall/timeout budget mismatch | `pipeline/tasks.py`, worker logs, runtime profile timeouts, queue metrics | Distinguishes queue pressure from task logic bugs |
| low-signal summary block | source text quality below summary gate | `pipeline/summary_quality.py`, extracted text quality, segmentation state | Avoids chasing LLM prompts when source is insufficient |
| segmentation noisy/empty/failed | extraction artifacts or segmentation heuristics mismatch | `pipeline/agenda_resolver.py`, `pipeline/llm.py` segmentation paths, extraction output | Segmentation quality is upstream of summary quality |
| provider telemetry absent | worker scrape failure or missing provider series | `pipeline/metrics.py`, soak metrics collector, worker exporter | Prevents false performance conclusions |

Why this exists:
- Ordered triage reduces mean-time-to-isolation by checking contract boundaries first.

## 10) How to Extend the Pipeline Safely

### Checklist for a new async generation stage
1. Add protected API route in `api/main.py`.
2. Add task implementation in `pipeline/tasks.py`.
3. Define deterministic write contract (which fields are written and when).
4. Ensure task lifecycle is observable via `GET /tasks/{task_id}`.
5. Add metrics and error mapping semantics.
6. Add tests for contract, retries/fallbacks, and stale/fresh behavior.
7. Update docs (`README.md`, this file, `docs/OPERATIONS.md`, and `ARCHITECTURE.md` when architectural contract changes).

### Why this exists
Most regressions come from partial stage additions (route without durable write semantics, or task without observability/tests).

## 11) Source-of-Truth File Map

Use these files as primary references:
- Batch orchestration: `pipeline/run_pipeline.py`
- Async orchestration: `pipeline/tasks.py`
- API task entrypoints: `api/main.py`
- Inference policy: `pipeline/llm.py`
- Provider transport + typed errors: `pipeline/llm_provider.py`
- Extraction freshness/hash: `pipeline/extraction_service.py`, `pipeline/content_hash.py`
- Metrics: `pipeline/metrics.py`
- Runbook and troubleshooting: `docs/OPERATIONS.md`

## 12) Related Docs

- Architecture contracts: `ARCHITECTURE.md`
- Operations runbook: `docs/OPERATIONS.md`
- Performance and soak policy: `docs/PERFORMANCE.md`
- Feature sequencing/status: `ROADMAP.md`
