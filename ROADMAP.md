# Roadmap Plan: Feature Expansion for Town-Council (AI Extraction, Discovery, Engagement, and Scalable Inference)

This roadmap is the canonical A/B/C/D plan and dependency order for feature expansion.

## Current Status Snapshot

- Milestone A: **Complete**
- Milestone B: **Partially complete** (`B1 complete`, `B2 planned`)
- Milestone C: **Planned (re-baselined)**
- Milestone D: **Planned (re-baselined)**

## Summary

This roadmap turns feature ideas into an implementation sequence that fits the current codebase and avoids unnecessary rewrites.

1. **Milestone A (High ROI, low risk):** vote/outcome extraction hardening + scorecards foundation
2. **Milestone B (Search upgrade):** semantic retrieval (hybrid keyword + vector)
3. **Milestone C (Discovery UX):** longitudinal issue lineage + trends UI
4. **Milestone D (Engagement + Scaling):** civic subscriptions/alerts + dedicated inference server backend

It aligns with current architecture facts:
- `AgendaItem.result`, `AgendaItem.votes`, and `raw_history` already exist.
- Search is Meilisearch-first and meeting-only by default unless `include_agenda_items=true`.
- Celery worker is currently single-process (`--concurrency=1 --pool=solo`) with guardrails for LocalAI process duplication.

Re-baseline note after recent pushes:
- Summary trust/quality hardening is now complete (grounded decision-brief summaries + contextual AI disclaimers).
- This work is treated as a prerequisite layer and does **not** replace Milestones C or D scope.

## Important Public API / Interface / Type Changes

### Additive API changes
- `GET /trends/topics`
- `GET /trends/compare`
- `GET /trends/export`
- `POST /subscriptions`
- `GET /subscriptions`
- `DELETE /subscriptions/{id}`
- `GET /officials/{person_id}/scorecard` (or extend existing person endpoint)

### Additive DB/model changes
- `agenda_item.vote_tally_json` (optional if `votes` shape is insufficient)
- `agenda_item.outcome` (nullable string enum-like: passed/failed/deferred/continued/unknown)
- `catalog.embedding` and/or separate `embedding_chunk` table
- `agenda_item.embedding` (if item-level semantic retrieval is required)
- `subscription` table (+ delivery log table for idempotent notifications)
- `catalog.lineage_id`, `catalog.lineage_confidence`, `catalog.lineage_updated_at` (Milestone C v1)

### Internal interfaces
- `LocalAIProvider` abstraction:
  - `InProcessLlamaProvider` (current)
  - `HttpInferenceProvider` (Ollama/vLLM/llama.cpp server)
- `embedding_worker.py` for offline embedding generation
- `vote_worker.py` (or extend existing agenda task pipeline) for structured vote extraction

## Milestone A: Vote/Outcome Extraction + Official Scorecard Foundations

Status: **Complete**

### Scope
1. **Structured vote extraction pass** after agenda segmentation.
2. Normalize outcomes and tally votes from item-local context.
3. Expose reliable aggregated voting stats for official profiles.

### Implementation
1. Add extraction module (`pipeline/vote_extractor.py`) using deterministic-first parsing + LLM fallback.
2. Integrate into Celery flow after `segment_agenda_task` completion or as separate `extract_votes_task`.
3. Write fields:
   - `AgendaItem.outcome` (new)
   - `AgendaItem.votes` (reuse existing JSON)
   - `AgendaItem.result` normalized (backward-compatible)
4. Add scorecard aggregator service:
   - attendance proxy
   - majority-alignment %
   - top recurring topics voted on

### Edge handling
- If no explicit vote found: keep `outcome=unknown`, never fabricate tally.
- Keep raw snippet evidence for auditability (source span/page).

### Tests
- Unit: vote regex/parser (passed/failed/deferred/continued)
- Unit: LLM fallback schema conformance
- Integration: task writes correct fields and idempotent reruns
- API: scorecard metrics correctness
- Regression: existing agenda QA tests (especially `votes_missed` behavior)

## Milestone B: Semantic Search (Hybrid Retrieval)

Status: **In Rollout** (`B1 complete`, `B2 implementation in progress`)

### Scope
Enable conceptual search while preserving current keyword precision and performance.

### Implementation
1. Add pgvector extension and migration.
2. Add embedding worker:
   - model: `all-MiniLM-L6-v2`
   - embed `Catalog.summary` + optionally `AgendaItem.title/description`
3. Build hybrid retrieval pipeline:
   - Stage 1: Meilisearch lexical recall
   - Stage 2: pgvector similarity rerank/merge
4. Add optional query param to `/search`:
   - `semantic=true|false`
   - default `false` initially (safe rollout)

### Edge handling
- Missing embeddings: fallback to lexical-only.
- Low-quality/empty summaries: skip embedding, log reason.

### Transitional backend policy (explicit)
- FAISS remains a temporary fallback during B2 hydration/validation.
- pgvector is the target backend for hybrid rerank.

### FAISS retirement gates (mandatory)
FAISS is removed in a fast-follow PR after all gates pass:
1. Hydration complete: `semantic_embedding` populated for historical catalog summaries.
2. Performance validated: pgvector hybrid search meets p50/p95 SLO targets.
3. Cutover complete: production uses `SEMANTIC_BACKEND=pgvector` successfully.
4. Stability window: 72 hours with no semantic-search incidents.

### Tests
- Unit: embedding generation and cosine thresholding
- Integration: lexical vs hybrid ranking behavior
- API: `semantic=true` returns expected structure without breaking existing clients
- Performance: p50/p95 impact under local load

## Milestone C: Meilisearch-Faceted Trends + Merge-Safe Lineage (Meeting-Level v1)

Status: **In implementation (re-baselined)**

### Scope
1. Meeting-level lineage threads users can follow across records.
2. City/topic trend comparison endpoints with no extra SQL cache layer in v1.
3. Lightweight UI panels behind feature flag.

Why this matters:
- users can follow one issue across meetings instead of scanning records one-by-one;
- users can compare topic momentum across cities without manual spreadsheets.

### Implementation (re-baselined)
1. Feature-gate with `FEATURE_TRENDS_DASHBOARD`.
2. Persist lineage only (`catalog.lineage_id`, `lineage_confidence`, `lineage_updated_at`).
3. Recompute lineage in Celery (`pipeline/tasks.py`) with a DB advisory lock and deterministic full-graph assignment.
4. Serve trends from Meilisearch facets (`topics`) via:
   - `GET /trends/topics`
   - `GET /trends/compare`
   - `GET /trends/export`
5. Expose lineage via:
   - `GET /lineage/{lineage_id}`
   - `GET /catalog/{catalog_id}/lineage`
6. Apply rate limits to all new read routes.

### Edge handling
- Cascading bridge merges rewrite lineage IDs across affected components in one authoritative recompute.
- Sparse cities/date windows return empty trend series, not errors.
- Low-confidence lineage remains visible with confidence metadata.

### Tests
- lineage connected-component determinism and merge rewrite behavior
- trends endpoints (topics/compare/export) and feature-flag gating
- UI contract checks for Trends panel and Lineage timeline wiring

## Milestone D: Civic Alerts + Inference Server Scaling

Status: **Planned (re-baselined)**

Baseline dependency updates:
- Preserve parity with the new summary contract when inference backend changes.
- Preserve grounding/pruning behavior and UI disclaimer assumptions for any HTTP inference backend rollout.

### Scope
1. User subscriptions and notifications.
2. Decouple inference from Celery worker processes.

### Implementation
#### Subscriptions
1. Add `subscription` and `notification_delivery` tables.
2. Matching worker compares new/updated indexed items against active subscriptions.
3. Delivery backend:
   - Phase 1: webhook only
   - Phase 2: email provider optional
4. UI/API subscription management.

#### Inference server
1. Introduce provider abstraction in `pipeline/llm.py`.
2. Keep current in-process backend as default.
3. Add HTTP backend container (Ollama or compatible).
4. Config switch:
   - `LOCAL_AI_BACKEND=inprocess|http`
5. After HTTP backend stable, permit higher Celery concurrency for non-LLM tasks and optionally LLM calls through HTTP.

### Edge handling
- Delivery retries + idempotency keys.
- Inference server unavailable: fallback or explicit task failure with retry policy.

### Tests
- Unit: subscription matching logic
- Integration: notification enqueue + retry idempotency
- Integration: HTTP inference backend parity with in-process output contracts
  - sectioned summary format parity (`BLUF`, `Why this matters`, `Top actions`, `Potential impacts`, `Unknowns`)
  - grounding/pruning parity on unsupported claims
- Load test: compare throughput before/after backend switch

## Rollout Strategy

1. **A first (votes/outcomes):** immediate user-visible value with minimal architectural change.
2. **B next (hybrid semantic):** additive and feature-flagged.
3. **C then (lineage/trends):** builds directly on B embeddings.
4. **D last (alerts + inference scaling):** larger ops surface area; do after metric baselines exist.

Use feature flags for:
- `FEATURE_SEMANTIC_SEARCH`
- `FEATURE_TRENDS_DASHBOARD`
- `FEATURE_SUBSCRIPTIONS`
- `LOCAL_AI_BACKEND`

## Documentation Updates Required per Milestone

- `README.md`: user-facing feature availability and flags
- `ARCHITECTURE.md`: data flow and component changes
- `docs/OPERATIONS.md`: runbook for new workers/jobs, alert retries, inference backend ops
- `docs/PERFORMANCE.md`: before/after benchmark tables for hybrid search and HTTP inference

## Acceptance Criteria (Program-Level)

1. Vote/outcome extraction populates meaningful structured fields without hallucinated tallies.
2. Semantic search improves conceptual recall while preserving lexical fallback.
3. Trends and lineage views produce reproducible aggregates and coherent item threads.
4. Subscriptions deliver notifications idempotently and are auditable.
5. Inference scaling path no longer depends on in-process singleton assumptions; Celery concurrency can be increased safely when using HTTP inference backend.

## Explicit Assumptions and Defaults

1. Keep existing Meilisearch keyword search as baseline; semantic is additive.
2. Start with webhook subscriptions before email.
3. Preserve backward compatibility in `/search` and existing task endpoints.
4. Keep `AgendaItem.votes` JSON as canonical vote detail unless schema pressure requires split columns.
5. Use feature flags and phased rollout rather than big-bang migration.
