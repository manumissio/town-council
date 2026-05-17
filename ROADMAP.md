# Town Council Living Roadmap

This roadmap is the strategic planning surface for Town Council. It records
initiative order, current priorities, and exit criteria. It is not the source of
truth for implemented behavior.

## Purpose

Town Council is moving from single-city exploration toward reliable local-first
civic data coverage. The roadmap keeps that work sequenced so product features
do not outrun extraction quality, runtime stability, or city onboarding evidence.

Current ordering:
1. **Decision Integrity**
2. **Hybrid Semantic Discovery**
3. **Issue Threads Foundation**
4. **Inference Decoupling & Throughput Stabilization**
5. **City Coverage Expansion I/II**
6. **Signal Intelligence**
7. **Civic Alerts & Subscriptions**

## Sources of Truth

- Architecture and data ownership: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Operator runbooks and runtime policy: [`docs/OPERATIONS.md`](docs/OPERATIONS.md)
- Benchmarks, soak gates, and performance evidence: [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md)
- Guardrail scope and cleanup families: [`docs/ENGINEERING_GUARDRAILS.md`](docs/ENGINEERING_GUARDRAILS.md)
- City rollout notes: [`docs/city-onboarding-status.md`](docs/city-onboarding-status.md)
- City wave/status registry: [`city_metadata/city_rollout_registry.csv`](city_metadata/city_rollout_registry.csv)

If this file conflicts with code or those canonical docs, treat the code and
canonical docs as correct and update this roadmap.

## Completed

### Decision Integrity

The platform has landed source-backed agenda outcome and vote extraction around
the existing `AgendaItem.result` and `AgendaItem.votes` fields. The completed
scope is deterministic-first extraction with guarded LLM fallback, no fabricated
tallies, and tests around vote/result parsing and persistence.

Not included in the completed scope: a separate `AgendaItem.outcome` column or
official scorecard endpoint.

### Issue Threads Foundation

Meeting-level lineage and trends are implemented as the first issue-thread
foundation. Lineage persists on `catalog.lineage_*`, recomputes through the
pipeline task path, and exposes read endpoints for catalog and lineage views.
Trends use Meilisearch-backed topic facets.

Current behavior and endpoint ownership are documented in `ARCHITECTURE.md` and
`docs/OPERATIONS.md`; timing and measurement notes live in `docs/PERFORMANCE.md`.

### Hybrid Semantic Discovery Platform Work

The semantic search surface is now split behind stable facades. `/search`,
`/search?semantic=true`, and `/search/semantic` remain additive search surfaces,
while semantic execution is isolated behind the semantic service and focused
helper modules.

The current target remains pgvector-backed hybrid rerank with FAISS/NumPy as
transitional support. Diagnostics expose stale or missing embedding behavior
without breaking lexical fallback.

### Runtime And Guardrail Cleanup

The API, worker, semantic, enrichment, crawler, and batch responsibilities have
been separated enough to support targeted rebuilds and smaller runtime surfaces.
Recent guardrail batches also enrolled the extracted helper families so facade
modules stay small and source ownership remains clear.

### Protected Derived Actions

Protected catalog reads and derived actions now flow through server-side routes
rather than browser-visible API keys. The local UI can load protected content,
status, agenda rows, and derived action results through the same-origin proxy
pattern.

### Sunnyvale Recovery Path

Sunnyvale crawling now uses the Legistar Web API template and recovers missing
agenda/minutes links from meeting detail pages when API rows are partial. Summary
backfill and empty-agenda fallback behavior are implemented; final completion
evidence belongs in the active Sunnyvale finalization item below.

## Active

### Sunnyvale Finalization

Goal: finish and record Sunnyvale coverage evidence after the Legistar API
recovery and summary backfill work.

Exit criteria:
- remaining Sunnyvale agenda/minutes summary gaps are resolved or explicitly
  documented with reason codes;
- crawl, extraction, segmentation, summary, and search evidence is recorded in
  the city rollout notes or registry;
- any residual failures are classified as data/source limitations, not silent
  pipeline gaps.

### Inference Decoupling & Throughput Stabilization

Goal: keep the local-first HTTP inference path stable while preserving baseline
comparability.

Exit criteria:
- baseline-valid evidence satisfies the documented stabilization gate in
  `docs/PERFORMANCE.md`;
- runtime defaults remain Gemma 3/local-first unless policy is explicitly
  changed in the runbook;
- Gemma 4 remains diagnostic or opt-in only until a separate model-policy
  decision is accepted.

### Semantic Pgvector / FAISS Decision

Goal: decide whether to retire, keep, or defer FAISS after pgvector evidence is
strong enough.

Exit criteria:
- historical semantic hydration coverage is known;
- pgvector hybrid rerank latency and result quality meet the current benchmark
  expectations;
- production/local default backend choice is recorded with evidence;
- the decision is reflected in architecture, operations, and guardrail docs.

### City Expansion Readiness

Goal: confirm the system is ready to resume city expansion without compounding
runtime or data-quality failures.

Exit criteria:
- rollout registry and onboarding status identify the next city wave;
- crawl and derived-state quality gates are measurable for the wave;
- queue/API/search behavior remains within the documented conservative-profile
  expectations.

## Next

### City Coverage Expansion I/II

Expand coverage in controlled waves after active readiness criteria pass.
Existing spider coverage should be promoted before new provider families. City
membership and enabled status should come from the rollout registry, not from
hardcoded roadmap lists.

Quality gates stay outcome-based:
- crawl success is high enough for repeatable ingestion;
- extraction is non-empty for the expected document set;
- agenda segmentation reaches `complete` or `empty` for nearly all eligible
  agendas;
- records are searchable through API and Meilisearch facets.

### Signal Intelligence

Add discovery surfaces that show change over time, not just static topic counts.
The intended product direction is agenda-level issue progression, comparative
signals, and direct paths into lineage/search views.

Start criteria:
- meeting-level lineage and trends remain stable under expanded city coverage;
- topic normalization is good enough to avoid generic or low-value signals;
- false-positive controls are defined before user-facing signal cards ship.

## Later

### Civic Alerts & Subscriptions

Subscriptions remain deferred until city breadth and upstream quality are stable
enough to avoid noisy or misleading notifications.

Start criteria:
- enough active cities are stable for a meaningful alert product;
- queue, API, and search behavior meet the conservative-profile SLOs;
- no unresolved P1/P2 ingestion regressions are active.

Initial delivery shape is still open. Webhook-style subscriptions remain the
preferred starting point unless a later accepted design chooses email or another
channel.

## Candidate Future Interfaces

These are candidate surfaces, not commitments. They require a separate accepted
design before implementation.

Candidate APIs:
- subscription create/list/delete endpoints;
- official scorecard or official-profile aggregate endpoint;
- agenda-level lineage reads;
- Civic Signals comparison/export endpoints beyond the current trends surface.

Candidate data model changes:
- dedicated subscription and delivery-log tables for idempotent notification
  delivery;
- agenda-level lineage identifiers and confidence fields;
- additional vote/outcome columns only if `AgendaItem.result` and
  `AgendaItem.votes` become insufficient;
- agenda-item embeddings only if item-level semantic retrieval is accepted.

## Defaults And Assumptions

- Meilisearch keyword search remains the baseline; semantic search is additive.
- Runtime defaults remain local-first and Gemma 3 based unless policy changes.
- Do not silently fall back between inference backends or model tiers.
- Use feature flags and staged rollout instead of big-bang launches.
- Keep completed sections descriptive; do not list unimplemented APIs or schema
  as landed work.
