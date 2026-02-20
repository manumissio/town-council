# Roadmap Plan: Feature Expansion for Town-Council (AI Extraction, Discovery, Engagement, and Scalable Inference)

This roadmap is the canonical feature expansion plan and dependency order.

## Current Status Snapshot

- Decision Integrity (`A`): **Complete**
- Hybrid Semantic Discovery (`B`): **Partially complete** (`B1 complete`, `B2 planned`)
- Issue Threads Foundation (`C v1`): **Complete**
- Inference Decoupling & Throughput Stabilization (`D2-lite`): **Planned (next)**

## Summary

This roadmap turns feature ideas into an implementation sequence that fits the current codebase and avoids unnecessary rewrites.

1. **Decision Integrity (`A`)**: vote/outcome extraction hardening + scorecards foundation
2. **Hybrid Semantic Discovery (`B`)**: semantic retrieval (hybrid keyword + vector)
3. **Issue Threads Foundation (`C v1`)**: meeting-level lineage + trends endpoints
4. **Inference Decoupling & Throughput Stabilization (`D2-lite`)**: HTTP inference backend + conservative runtime profile
5. **City Coverage Expansion I (`Wave 1`)**: existing spiders only
6. **City Coverage Expansion II (`Wave 2`)**: new spiders / provider-clustered
7. **Signal Intelligence (`C2`)**: agenda-level lineage + Civic Signals UX
8. **Civic Alerts & Subscriptions (`D1`)**: engagement layer after city breadth stabilizes

It aligns with current architecture facts:
- `AgendaItem.result`, `AgendaItem.votes`, and `raw_history` already exist.
- Search is Meilisearch-first and meeting-only by default unless `include_agenda_items=true`.
- Celery worker is currently single-process (`--concurrency=1 --pool=solo`) with guardrails for LocalAI process duplication.

Re-baseline note after recent pushes:
- Summary trust/quality hardening is now complete (grounded decision-brief summaries + contextual AI disclaimers).
- This work is treated as a prerequisite layer and does **not** replace Issue Threads Foundation (`C v1`) or Inference Decoupling & Throughput Stabilization (`D2-lite`) scope.

## Canonical Milestone Names

Use these names in roadmap, docs, and release communication:
1. **Decision Integrity** (`A`)
2. **Hybrid Semantic Discovery** (`B`)
3. **Issue Threads Foundation** (`C v1`)
4. **Inference Decoupling & Throughput Stabilization** (`D2-lite`)
5. **City Coverage Expansion I** (`Wave 1`)
6. **City Coverage Expansion II** (`Wave 2`)
7. **Signal Intelligence** (`C2`)
8. **Civic Alerts & Subscriptions** (`D1`)

Transition policy:
- Keep legacy aliases in parentheses for one transition cycle, then remove aliases.

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
- `catalog.lineage_id`, `catalog.lineage_confidence`, `catalog.lineage_updated_at` (Issue Threads Foundation / `C v1`)

### Internal interfaces
- `LocalAIProvider` abstraction:
  - `InProcessLlamaProvider` (current)
  - `HttpInferenceProvider` (Ollama/vLLM/llama.cpp server)
- `embedding_worker.py` for offline embedding generation
- `vote_worker.py` (or extend existing agenda task pipeline) for structured vote extraction

## Decision Integrity (`A`): Vote/Outcome Extraction + Scorecard Foundations

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

## Hybrid Semantic Discovery (`B`): Semantic Search (Hybrid Retrieval)

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

## Issue Threads Foundation (`C v1`): Meilisearch-Faceted Trends + Merge-Safe Lineage

Status: **Complete**

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

## Signal Intelligence (`C2`): Discovery UX Deepening (Agenda-Level Lineage + Civic Signals)

Status: **Planned**
Prerequisite lock: complete foundation-first refactor (central lexicon + shared QueryBuilder + provider protocol + shared UI search state) before re-enabling Signals UI.

### Scope
1. Add agenda-item-level lineage so users can follow a specific action/policy thread, not just meeting-level relatedness.
2. Reintroduce trends as a differentiated product surface (`Civic Signals`), focused on change-over-time instead of static top terms.
3. Connect trends directly to action paths (open lineage thread, compare cities, subscribe/watch).

Why this matters:
- meeting-level lineage answers "what else is related?";
- agenda-level lineage answers "what happened to this exact issue over time?"
- civic signals should answer "what changed and why should I care now?"

### Implementation
1. Add agenda-level lineage model and assignment logic with confidence and deterministic IDs.
2. Add change-aware signals:
   - rising/new/declining topics over configurable windows
   - city-to-city comparative deltas
3. Add topic normalization/curation to suppress low-value generic tokens.
4. Add UI affordances:
   - explicit "Open thread" from signal cards
   - "Watch this signal" hook for Civic Alerts & Subscriptions (`D1`).
5. Keep all C2 surfaces feature-flagged until validation completes.

### Edge handling
- avoid false merges by requiring stronger evidence at agenda-item granularity;
- sparse date windows produce low-confidence/insufficient-data states, not hard claims;
- preserve fallback to existing meeting-level lineage when agenda-level evidence is weak.

### Tests
- agenda-lineage determinism + merge rewrite tests;
- signal delta math tests (windowing and comparison correctness);
- regression tests proving C2 does not degrade C v1 search and lineage behavior.

### Acceptance criteria
1. Users can open an agenda-level issue thread and see chronological progression with stable IDs.
2. Civic Signals surfaces change-over-time (not static counts) with reproducible calculations.
3. Signal cards reliably deep-link to relevant lineage/search views.
4. False-positive rate remains bounded via confidence thresholds and deterministic fallbacks.

## Inference Decoupling & Throughput Stabilization (`D2-lite`)

Status: **Planned (next)**

Baseline dependency updates:
- Preserve parity with the new summary contract when inference backend changes.
- Preserve grounding/pruning behavior and UI disclaimer assumptions for any HTTP inference backend rollout.
- Runtime model policy is 270M-only by default; model-selection A/B is deferred until a new candidate model is explicitly reintroduced.

### Scope
1. Decouple inference from Celery worker processes before city expansion.
2. Lift worker concurrency conservatively (default profile) with explicit rollback.

### Implementation
1. Introduce provider abstraction in `pipeline/llm.py`.
2. Keep current in-process backend as default.
3. Add HTTP backend container (Ollama-compatible) in Compose.
4. Config switch:
   - `LOCAL_AI_BACKEND=inprocess|http`
5. Conservative runtime profile defaults:
   - inference service caps: ~4GB RAM, 2 CPU
   - inference queue throttling via `OLLAMA_NUM_PARALLEL=1` on constrained hosts
   - worker concurrency: 3
   - timeout budget must include inference queue wait on constrained hosts
   - use operation-specific HTTP timeout budgets (segment vs summary/topics) when needed
6. Promotion rule:
   - move from Conservative to Balanced only after 1 week of clean SLOs.

### Edge handling
- Inference server unavailable: fallback or explicit task failure with retry policy.
- Immediate rollback: `LOCAL_AI_BACKEND=inprocess`, worker concurrency back to `1`.

### Tests
- Integration: HTTP inference backend parity with in-process output contracts
  - sectioned summary format parity (`BLUF`, `Why this matters`, `Top actions`, `Potential impacts`, `Unknowns`)
  - grounding/pruning parity on unsupported claims
- Load test: compare throughput before/after backend switch
- Runtime profile A/B (`conservative` vs `balanced`) is the active tuning path while model-selection A/B remains disabled.

## City Coverage Expansion (after D2-lite gates)

### City Coverage Expansion I (`Wave 1`, existing spiders only)
- fremont
- hayward
- san_mateo
- sunnyvale
- san_leandro
- mtn_view
- moraga
- belmont

### City Coverage Expansion II (`Wave 2`, new spiders; provider-clustered)
- orinda (IQM2)
- brisbane
- danville
- los_gatos
- los_altos
- palo_alto
- san_bruno
- east_palo_alto
- santa_clara (SIRE/custom last)

Per-city quality gates:
- crawl success >=95% over 3 runs
- non-empty extraction >=90%
- segmentation complete/empty >=95% (failed <5%)
- searchable in API and Meilisearch facets

## Civic Alerts & Subscriptions (`D1`, deferred)

Status: **Planned (after city breadth stabilizes)**

Start criteria:
1. >=12 active cities stable for 14 days.
2. Queue/API/search SLOs remain within target on conservative profile.
3. No P1/P2 ingestion regressions for 2 consecutive weeks.

## Rollout Strategy (re-baselined, D2-lite first)

1. **Decision Integrity (`A`) first:** immediate user-visible value with minimal architectural change.
2. **Hybrid Semantic Discovery (`B`) next:** additive and feature-flagged.
3. **Issue Threads Foundation (`C v1`) then:** reproducible meeting-level lineage + trends endpoints.
4. **Inference Decoupling & Throughput Stabilization (`D2-lite`) next:** remove bottleneck safely before expansion.
5. **No new feature rollout during D2-lite soak:** hold feature scope while stability gates are evaluated.
6. **City Coverage Expansion I then II:** controlled onboarding with per-city reversible gates.
7. **Signal Intelligence (`C2`) next:** deepen discovery once expanded data baselines are stable.
8. **Civic Alerts & Subscriptions (`D1`) last:** launch engagement after breadth + stability criteria pass.

Use feature flags for:
- `FEATURE_SEMANTIC_SEARCH`
- `FEATURE_TRENDS_DASHBOARD`
- `FEATURE_SUBSCRIPTIONS`
- `LOCAL_AI_BACKEND`

## Documentation Updates Required per Milestone

- `README.md`: user-facing feature availability and flags
- `ARCHITECTURE.md`: data flow and component changes
- `docs/OPERATIONS.md`: runbook for backend mode switch, conservative profile, city wave gates
- `docs/PERFORMANCE.md`: before/after benchmark tables for hybrid search and HTTP inference

## Acceptance Criteria (Program-Level)

1. Vote/outcome extraction populates meaningful structured fields without hallucinated tallies.
2. Semantic search improves conceptual recall while preserving lexical fallback.
3. Trends and lineage views produce reproducible aggregates and coherent item threads.
4. Signal Intelligence (`C2`) delivers agenda-level issue threads and change-aware signals with bounded false positives.
5. Inference scaling path no longer depends on in-process singleton assumptions; Celery concurrency can be increased safely when using HTTP inference backend.
6. Civic Alerts & Subscriptions (`D1`) deliver notifications idempotently and are auditable after activation criteria pass.

## Explicit Assumptions and Defaults

1. Keep existing Meilisearch keyword search as baseline; semantic is additive.
2. Start with webhook subscriptions before email.
3. Preserve backward compatibility in `/search` and existing task endpoints.
4. Keep `AgendaItem.votes` JSON as canonical vote detail unless schema pressure requires split columns.
5. Use feature flags and phased rollout rather than big-bang migration.
