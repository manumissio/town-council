# Roadmap Plan: Feature Expansion for Town-Council (AI Extraction, Discovery, Engagement, and Scalable Inference)

This roadmap is the canonical feature expansion plan and dependency order.

## Current Status Snapshot

- Decision Integrity: **Complete**
- Hybrid Semantic Discovery: **Partially complete** (Phase 1 complete, Phase 2 meeting-search rollout in progress)
- Issue Threads Foundation: **Complete**
- Inference Decoupling & Throughput Stabilization: **Implemented; stabilization rollout in progress** (not complete until promotion gates pass)

## Summary

This roadmap turns feature ideas into an implementation sequence that fits the current codebase and avoids unnecessary rewrites.

1. **Decision Integrity**: vote/outcome extraction hardening + scorecards foundation
2. **Hybrid Semantic Discovery**: semantic retrieval (hybrid keyword + vector)
3. **Issue Threads Foundation**: meeting-level lineage + trends endpoints
4. **Inference Decoupling & Throughput Stabilization**: implemented HTTP inference backend + runtime-profile stabilization before city expansion
5. **City Coverage Expansion I**: existing spiders only
6. **City Coverage Expansion II**: new spiders / provider-clustered
7. **Signal Intelligence**: agenda-level lineage + Civic Signals UX
8. **Civic Alerts & Subscriptions**: engagement layer after city breadth stabilizes

It aligns with current architecture facts:
- `AgendaItem.result`, `AgendaItem.votes`, and `raw_history` already exist.
- Search is Meilisearch-first and meeting-only by default unless `include_agenda_items=true`.
- The checked-in Compose default for the HTTP inference path is a prefork Celery worker (`--concurrency=3 --pool=prefork`).
- In-process inference remains available as an explicit alternative mode with stricter single-process guardrails.

Re-baseline note after recent pushes:
- Summary trust/quality hardening is now complete (grounded decision-brief summaries + contextual AI disclaimers).
- This work is treated as a prerequisite layer and does **not** replace Issue Threads Foundation or Inference Decoupling & Throughput Stabilization scope.

## Canonical Initiative Names

Use these names in roadmap, docs, and release communication:
1. **Decision Integrity**
2. **Hybrid Semantic Discovery**
3. **Issue Threads Foundation**
4. **Inference Decoupling & Throughput Stabilization**
5. **City Coverage Expansion I**
6. **City Coverage Expansion II**
7. **Signal Intelligence**
8. **Civic Alerts & Subscriptions**

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

## Decision Integrity: Vote/Outcome Extraction + Scorecard Foundations

Status: **Complete**

### Scope
1. **Structured vote extraction pass** after agenda segmentation.
2. Normalize outcomes and tally votes from item-local context.
3. Expose reliable aggregated voting stats for official profiles.

Why this matters:
- agenda-level vote/outcome structure turns narrative meeting text into auditable decision data;
- scorecard-ready outputs enable consistent official-level comparisons from the same source fields;
- this stage improves downstream trust before adding broader discovery surfaces.

Tradeoff note:
- Chosen path: deterministic-first extraction with LLM fallback and confidence gating.
- No documented alternative path found in current repo artifacts.
- Why chosen now: the implementation and tests already enforce non-fabrication and source-backed outcomes (`ROADMAP.md` -> Decision Integrity -> Edge handling/Tests).

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

## Hybrid Semantic Discovery: Semantic Search (Hybrid Retrieval)

Status: **In Rollout** (Phase 1 complete, Phase 2 implementation in progress)

### Scope
Enable conceptual search while preserving current keyword precision and performance.

Why this matters:
- lexical-only search misses semantically related records when exact term overlap is low;
- hybrid retrieval raises conceptual recall while preserving predictable keyword behavior;
- phased enablement (`semantic=false` default) reduces rollout risk for existing clients.

Tradeoff note:
- Chosen path: pgvector-targeted hybrid rerank with temporary FAISS fallback during hydration/validation.
- Alternative considered: keeping FAISS as the long-term primary backend (source: `ROADMAP.md` -> Hybrid Semantic Discovery -> Transitional backend policy + FAISS retirement gates).
- Why chosen now: the roadmap explicitly targets pgvector and defines concrete retirement gates for FAISS, indicating FAISS is transitional rather than strategic.

### Implementation
1. Add pgvector extension and migration.
2. Add embedding worker:
   - model: `all-MiniLM-L6-v2`
   - Phase 2 scope: embed meeting summaries for pgvector rerank
   - defer agenda-item semantic retrieval to a follow-on slice
3. Build hybrid retrieval pipeline:
   - Stage 1: Meilisearch lexical recall
   - Stage 2: pgvector similarity rerank/merge
4. Add optional query param to `/search`:
   - `semantic=true|false`
   - default `false` initially (safe rollout)

### Edge handling
- Missing or stale embeddings: degrade to lexical results with explicit `semantic_diagnostics`.
- Low-quality/empty summaries: skip embedding, log reason.

### Transitional backend policy (explicit)
- FAISS remains a temporary fallback during Phase 2 hydration/validation.
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

## Issue Threads Foundation: Meilisearch-Faceted Trends + Merge-Safe Lineage

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

## Signal Intelligence: Discovery UX Deepening (Agenda-Level Lineage + Civic Signals)

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
   - "Watch this signal" hook for Civic Alerts & Subscriptions.
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

## Inference Decoupling & Throughput Stabilization

Status: **Implemented; rollout/stabilization in progress**

Completion rule:
- This milestone uses tiered soak evidence:
  - short-run validation: a clean baseline-valid 2-day conservative window is sufficient for targeted stabilization acceptance
  - promotion-grade confirmation: a 7-day conservative window remains the stronger evidence tier when the team explicitly wants a higher-confidence rollout gate

Baseline dependency updates:
- Preserve parity with the new summary contract when inference backend changes.
- Preserve grounding/pruning behavior and UI disclaimer assumptions for any HTTP inference backend rollout.
- Runtime model policy is 270M-only by default; model-selection A/B is deferred until a new candidate model is explicitly reintroduced.

### Scope
1. Decouple inference from Celery worker processes before city expansion.
2. Lift worker concurrency conservatively (default profile) with explicit rollback.

Why this matters:
- in-process inference can constrain concurrency and increase resource coupling risk in worker scaling;
- decoupling inference transport creates a safer path to throughput gains before city expansion;
- conservative-to-balanced gating protects baseline comparability and rollback safety.

Tradeoff note:
- Chosen path: runtime-profile A/B (`conservative` vs `balanced`) with model-selection A/B deferred.
- Alternative considered: model-selection/cascading experimentation as baseline tuning path (source: `ROADMAP.md` -> Inference Decoupling & Throughput Stabilization -> Baseline dependency updates/Tests; `AGENTS.md` -> runtime_policy).
- Why chosen now: repo policy and roadmap both prioritize runtime-profile stabilization first to avoid policy drift during soak.

Evidence note:
- Implementation is already landed in `pipeline/llm.py`, `pipeline/llm_provider.py`, `pipeline/config.py`, and `docker-compose.yml`.
- Verification coverage already exists for provider protocol, retry/error mapping, backend parity, and runtime-profile defaults.
- Earlier short-window timeout failures were invalidated by the soak provider delta-accounting bug: stale cumulative Redis counters were being treated as fresh run-local failures.
- The corrected conservative validation window `soak_20260323_deltafix_day1` + `soak_20260323_deltafix_day2` is the first trustworthy post-fix evidence and passes with zero run-local provider timeouts.
- The historical `experiments/results/soak/soak_eval_7d.*` artifacts remain useful for diagnosis, but they no longer define the current targeted-stabilization readout by themselves.
- As a result, the next execution priority can move from timeout debugging to policy-aligned confirmation and rollout sequencing, not rebuilding the provider abstraction from scratch.

### Implementation
1. Provider abstraction is implemented in `pipeline/llm.py` and `pipeline/llm_provider.py`.
2. In-process backend remains available as an explicit alternative mode with stricter worker guardrails.
3. HTTP backend container (Ollama-compatible) is implemented in Compose and is the checked-in default path.
4. Config switch is implemented:
   - `LOCAL_AI_BACKEND=inprocess|http`
5. Conservative and balanced runtime profiles are implemented:
   - inference service caps: ~4GB RAM, 2 CPU
   - inference queue throttling via `OLLAMA_NUM_PARALLEL=1` on constrained hosts
   - worker concurrency: 3
   - timeout budget must include inference queue wait on constrained hosts
   - use operation-specific HTTP timeout budgets (segment vs summary/topics) when needed
6. Completion / promotion rule:
   - use a baseline-valid 2-day conservative window for short-cycle stabilization acceptance
   - use a 7-day conservative window when stronger promotion-grade confirmation is explicitly required before balanced evaluation

### Edge handling
- Inference server unavailable: explicit task failure with retry policy or deterministic local non-provider fallback where already implemented; do not silently switch backend modes.
- Immediate rollback: `LOCAL_AI_BACKEND=inprocess`, worker concurrency back to `1`.

### Tests
- Integration: HTTP inference backend parity with in-process output contracts
  - sectioned summary format parity (`BLUF`, `Why this matters`, `Top actions`, `Potential impacts`, `Unknowns`)
  - grounding/pruning parity on unsupported claims
- Load test: compare throughput before/after backend switch
- Runtime profile A/B (`conservative` vs `balanced`) is the active tuning path while model-selection A/B remains disabled.
- Milestone exit still depends on passing stabilization evidence, not just passing implementation tests.

## City Coverage Expansion (after inference stabilization gates)

Why this matters:
- expansion after stabilization limits compounding failure modes during onboarding of new municipalities;
- phased coverage improves reversibility (wave-level rollback/isolation) and quality control;
- quality gates keep ingestion/search integrity comparable across cities.

Tradeoff note:
- Chosen path: two-wave expansion (existing spiders first, new spiders/provider-clustered second).
- No documented alternative path found in current repo artifacts.
- Why chosen now: wave sequencing is explicitly encoded in the roadmap and supports controlled expansion with per-wave quality gates, but execution remains blocked until inference stabilization exit criteria pass.

### City Coverage Expansion I (existing spiders only)
- fremont
- hayward
- san_mateo
- sunnyvale
- san_leandro
- mtn_view
- moraga
- belmont

### City Coverage Expansion II (new spiders; provider-clustered)
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

## Civic Alerts & Subscriptions (deferred)

Status: **Planned (after city breadth stabilizes)**

Why this matters:
- alerts are high-trust user-facing features and should depend on stable upstream data breadth/quality;
- delaying activation until stability criteria are met reduces noisy or misleading notifications;
- start criteria tie launch readiness to measurable reliability signals.

Tradeoff note:
- Chosen path: defer subscriptions until city breadth and stability thresholds are met.
- No documented alternative path found in current repo artifacts.
- Why chosen now: the roadmap defines explicit start criteria and positions this milestone last in rollout order.

Start criteria:
1. >=12 active cities stable for 14 days.
2. Queue/API/search SLOs remain within target on conservative profile.
3. No P1/P2 ingestion regressions for 2 consecutive weeks.

## Rollout Strategy (re-baselined, inference stabilization first)

Why this matters:
- sequencing high-confidence data quality features before breadth/engagement reduces downstream correction cost;
- staged rollout keeps each milestone reversible and measurable;
- infrastructure stabilization before expansion lowers operational risk during city onboarding.

Tradeoff note:
- Chosen path: phased, feature-flag-first rollout.
- Alternative considered: big-bang migration across multiple milestones (source: `ROADMAP.md` -> Explicit Assumptions and Defaults #5).
- Why chosen now: current constraints favor controlled blast radius, explicit gates, and incremental verification.

1. **Decision Integrity first:** immediate user-visible value with minimal architectural change.
2. **Hybrid Semantic Discovery next:** additive and feature-flagged.
3. **Issue Threads Foundation then:** reproducible meeting-level lineage + trends endpoints.
4. **Inference Decoupling & Throughput Stabilization next:** implementation is landed; current priority is stabilization soak closure and promotion-grade evidence before expansion.
5. **City Coverage Expansion I then II:** controlled onboarding with per-city reversible gates.
6. **Signal Intelligence next:** deepen discovery once expanded data baselines are stable.
7. **Civic Alerts & Subscriptions last:** launch engagement after breadth + stability criteria pass.

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

## Rationale Evidence Sources

Tradeoff and rationale notes in this roadmap are grounded in current repository artifacts:
- `ROADMAP.md` section-local evidence:
  - Hybrid Semantic Discovery -> Transitional backend policy + FAISS retirement gates
  - Inference Decoupling & Throughput Stabilization -> Baseline dependency updates + Tests
  - City Coverage Expansion I/II split
  - Civic Alerts start criteria and rollout ordering
  - Explicit Assumptions and Defaults #5
- `AGENTS.md` policy evidence:
  - `runtime_policy` (model-selection/cascading is not baseline policy)
  - soak baseline and telemetry rules used by inference-stabilization rationale

## Acceptance Criteria (Program-Level)

1. Vote/outcome extraction populates meaningful structured fields without hallucinated tallies.
2. Semantic search improves conceptual recall while preserving lexical fallback.
3. Trends and lineage views produce reproducible aggregates and coherent item threads.
4. Signal Intelligence delivers agenda-level issue threads and change-aware signals with bounded false positives.
5. Inference scaling path no longer depends on in-process singleton assumptions; Celery concurrency can be increased safely when using HTTP inference backend.
6. Civic Alerts & Subscriptions deliver notifications idempotently and are auditable after activation criteria pass.

## Explicit Assumptions and Defaults

1. Keep existing Meilisearch keyword search as baseline; semantic is additive.
2. Start with webhook subscriptions before email.
3. Preserve backward compatibility in `/search` and existing task endpoints.
4. Keep `AgendaItem.votes` JSON as canonical vote detail unless schema pressure requires split columns.
5. Use feature flags and phased rollout rather than big-bang migration.
