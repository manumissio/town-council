# Architecture Decision Record Index

This file is the indexed log of material architecture decisions for Town Council.

Use each entry to record:
- the decision
- the reason it was made
- the affected boundary or contract
- links to the canonical docs that carry the ongoing operational or architecture detail

## 2026-04-13: Start API main cleanup with lifecycle and search route boundaries

- Status: Accepted
- Decision:
  - `api/main.py` remains the FastAPI app entrypoint and compatibility facade.
  - API lifecycle, database dependency setup, API-key verification, and limiter setup move behind `api/app_setup.py`.
  - Search, semantic proxy, metadata, and trends routes move behind `api/search_routes.py`.
  - Existing `api.main` import and monkeypatch seams remain intentionally available during this wave.
- Why:
  - `api/main.py` had become the next large mixed-responsibility runtime module after the semantic backend extraction.
  - Search, semantic proxy, metadata, and trends form a coherent read-route family with shared Meilisearch/filter behavior.
  - Preserving `api.main` as a facade keeps existing tests and callers stable while narrowing implementation ownership.
- Affected boundaries:
  - `api/main.py` remains the ASGI app and route-wiring boundary.
  - `api/app_setup.py` owns lifecycle/session/auth/limiter setup.
  - `api/search_routes.py` owns search, semantic proxy, metadata, and trends routes.
  - Task enqueue/status, lineage, people, catalog, and issue-reporting endpoints remain deferred.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/OPERATIONS.md](OPERATIONS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-06: Use seam creation before the next model-coupled typing wave

- Status: Accepted
- Decision:
  - Strict typing has reached a boundary where direct subtree enrollment would immediately drag model-heavy and helper-heavy dependency debt.
  - The next strict-typing follow-up should create a typed seam around the extraction boundary before attempting the next model-coupled service-layer wave.
- Why:
  - Recent typed-subtree waves exhausted the low-churn utility and medium service-layer candidates that stayed isolated.
  - Probing the next likely candidates showed direct typing would spill into `pipeline.models`, extractor/text-cleaning helpers, and related runtime surfaces.
  - A seam at the extraction boundary reduces transitive drag while preserving current extraction behavior.
- Affected boundaries:
  - `pipeline/extraction_service.py` remains the orchestration layer for extraction reprocessing.
  - extractor, cleaning, and bad-content classification helpers remain dependencies behind narrow typed contracts.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/OPERATIONS.md](OPERATIONS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-06: Enroll extraction_service before larger service waves

- Status: Accepted
- Decision:
  - `pipeline/extraction_service.py` is the next strict-typing enrollment target after the seam-creation prep wave.
  - The service should isolate extractor, text-cleaning, and bad-content classification behind local typed wrappers so the typed subtree can expand without dragging those neighbors into the same wave.
  - `pipeline/agenda_service.py` remains deferred because its current import surface still spills into untyped `pipeline.models` and `pipeline.utils`.
- Why:
  - The extraction seam was already in place, which made it the narrowest meaningful post-seam enrollment candidate.
  - A direct agenda-service enrollment would still require broader model/helper typing work.
  - This keeps strict-typing progress incremental while preserving the larger model-coupled service wave for later.
- Affected boundaries:
  - `pipeline/extraction_service.py` remains the extraction orchestration layer.
  - extractor, cleaning, and bad-content classification stay behind locally typed service wrappers.
  - the typed subtree expands by one service file without widening into `pipeline.models`.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-07: Enroll summary_hydration_diagnostics after query-boundary cleanup

- Status: Accepted
- Decision:
  - `pipeline/summary_hydration_diagnostics.py` is enrolled in the typed subtree after a boundary-prep pass that split policy logic from query assembly and localized ORM symbol loading.
  - The module keeps `SummaryHydrationSnapshot` and existing script-visible output semantics stable while containing model/query typing inside the diagnostics boundary.
  - `pipeline/agenda_service.py` remains deferred because it still spills directly into untyped `pipeline.models` and `pipeline.utils`.
- Why:
  - The next honest strict-typing problem after `extraction_service` was the model/query-heavy summary hydration diagnostic boundary.
  - Refactoring that boundary made the module type-clean without widening the strict subtree into the ORM layer.
  - This reduces the cost of later service-layer typing work while preserving current operator workflows.
- Affected boundaries:
  - `pipeline/summary_hydration_diagnostics.py` remains the operator-facing hydration backlog diagnostic boundary.
  - `scripts/diagnose_summary_hydration.py` and `scripts/staged_hydrate_cities.py` keep consuming the same snapshot contract.
  - the typed subtree expands by one diagnostics module without typing `pipeline.models`.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-07: Establish a shared models seam before the next service enrollments

- Status: Accepted
- Decision:
  - Strict typing should stop relying on one-off service wrappers and instead introduce a shared `pipeline.models` access seam for agenda and verification workflows.
  - `pipeline/agenda_service.py` is enrolled through that seam as the first consumer.
  - `pipeline/verification_service.py` adopts the seam selectively for session and catalog/item loading, but remains outside the typed subtree until its remaining local annotation debt is addressed separately.
- Why:
  - Repeated direct-enrollment probes had reached the same structural blocker: broad imports from `pipeline.models` and `pipeline.utils`.
  - A shared seam keeps service modules dependent on the smallest record/query contracts they actually consume.
  - `agenda_service` was the narrowest path to prove the seam is reusable without dragging in a full verification cleanup wave.
- Affected boundaries:
  - `pipeline.models` remains the ORM layer.
  - `pipeline/agenda_verification_model_access.py` becomes the typed boundary for narrow agenda and verification model access.
  - `pipeline/agenda_service.py` remains an agenda-domain service and no longer imports broad ORM symbols directly.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-07: Finish strict typing for the reusable pipeline core

- Status: Accepted
- Decision:
  - Strict typing for the reusable pipeline core is complete once the remaining shared foundations and helper modules are enrolled together.
  - `pipeline/models.py`, `pipeline/utils.py`, and `pipeline/verification_service.py` are enrolled alongside the next reusable helper layer: `pipeline/agenda_resolver.py` and `pipeline/vote_extractor.py`.
  - `pipeline/agenda_crosscheck.py` and `pipeline/agenda_legistar.py` are enrolled with `agenda_resolver.py` because they are now part of the same typed helper boundary.
- Why:
  - The shared `pipeline.models` seam removed the structural blocker that had kept `verification_service` out of the typed subtree.
  - The remaining reusable-core debt was concentrated in typed foundations and helper modules, not in new architecture work.
  - Stopping here keeps strict typing scoped to reusable pipeline modules without widening into worker entrypoints or backend-heavy modules.
- Affected boundaries:
  - `pipeline.models` remains the ORM layer, but its helper surface is now part of the strict typed core.
  - `pipeline.utils` remains the shared utility boundary, now with explicit contracts.
  - `pipeline.verification_service`, `pipeline.agenda_resolver`, and `pipeline.vote_extractor` are part of the reusable typed pipeline core.
  - worker/orchestration modules and backend-heavy modules remain separate follow-ups.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-08: Enforce Ruff formatting for the scoped formatter-ready path set

- Status: Accepted
- Decision:
  - The current formatter-ready path set is mechanically normalized with Ruff and now enforced in CI with a path-scoped `ruff format --check` command.
  - Formatter enforcement remains limited to the existing formatter-ready path set rather than expanding to repo-wide Python coverage.
- Why:
  - The reusable pipeline core is now stable enough to support a dedicated mechanical formatting wave.
  - The repo already had an explicit formatter-ready path set, which made it possible to enforce formatting without widening into unrelated modules.
  - Keeping the formatter command path-scoped preserves low-risk rollout and avoids conflating formatting policy with broader cleanup.
- Affected boundaries:
  - `docs/ENGINEERING_GUARDRAILS.md` remains the human-readable formatter policy.
  - `tests/test_repository_guardrails.py` remains the alignment check for the scoped formatter command.
  - `.github/workflows/python-guardrails.yml` enforces the same explicit path set in CI.
- Canonical references:
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-08: Start legacy cleanup with stale suppression inventory only

- Status: Accepted
- Decision:
  - The first legacy-cleanup wave audits stale suppressions and matching allowlist entries before any structural cleanup.
  - A suppression or allowlist entry is removable only when both the Ruff layer and the repository guardrail layer prove it is stale.
  - Runtime refactors, broad exception-policy rewrites, and wildcard suppression cleanup remain out of scope for this first pass.
- Why:
  - The remaining cleanup debt now splits between low-risk hygiene/config drift and high-risk structural legacy refactors.
  - Some files can look stale in one enforcement layer while still being active in another, so a dual-proof rule avoids accidental policy drift.
  - This creates a narrower, safer baseline for later structural cleanup waves.
- Affected boundaries:
  - `ruff.toml` remains the suppression source of truth.
  - `tests/test_repository_guardrails.py` remains the alignment and enforcement source of truth.
  - `docs/ENGINEERING_GUARDRAILS.md` now states that stale path-specific suppressions should be removed only when both layers prove they are unnecessary.
- Canonical references:
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-08: Refactor the provider boundary before wider runtime cleanup

- Status: Accepted
- Decision:
  - The first structural legacy-cleanup wave targets the inference provider boundary in `pipeline/llm_provider.py` and the provider-facing `LocalAI` methods in `pipeline/llm.py`.
  - Transitional provider shims are removed in favor of explicit operation methods for agenda extraction, summary generation, topic generation, and JSON generation.
  - Provider code owns transport classification, timeout policy, retry-budget policy, payload validation, and provider metrics.
  - `LocalAI` remains the layer that interprets typed provider failures into product behavior such as deterministic fallback or `None`.
- Why:
  - This boundary is smaller, more testable, and more cross-cutting than a first-pass refactor of task orchestration or the full LLM heuristic module.
  - Cleaning the seam preserves Town Council's local-first and fail-fast defaults while reducing duplication and ambiguity around provider errors.
  - Keeping retry ownership above the provider layer avoids hidden orchestration drift.
- Affected boundaries:
  - `pipeline/llm_provider.py` now owns operation-specific provider methods and typed failure mapping.
  - `pipeline/llm.py` continues to own fallback and degradation policy.
  - Runtime profiles and backend defaults remain unchanged.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-08: Extract task families before introducing any generic task wrapper

- Status: Accepted
- Decision:
  - The first `pipeline/tasks.py` cleanup wave extracts family-local helpers for text extraction, vote extraction, and summary generation while keeping the Celery task entrypoints in place.
  - `pipeline/tasks.py` remains the retry boundary: each bound task still owns `SessionLocal()`, rollback, `self.retry(...)`, and final payload shape.
  - The extracted helpers own only family-specific orchestration such as loading records, enforcing preconditions, persisting writes, and running best-effort post-commit side effects.
  - The cleanup intentionally avoids a shared task executor, shared retry engine, or hidden transaction wrapper.
- Why:
  - `pipeline/tasks.py` had repeated inline orchestration, but the repeated parts were not uniform enough to justify a generic wrapper without risking retry and transaction drift.
  - Celery retries need to stay explicit at the task boundary, and DB commit/rollback ownership needs to remain obvious and short-lived.
  - Family-by-family extraction reduces duplication now while preserving current task signatures, retry semantics, and post-write best-effort behavior.
- Affected boundaries:
  - `pipeline/tasks.py` remains the Celery entrypoint layer.
  - Extracted family helpers stay file-local and do not bypass existing domain services such as `pipeline.extraction_service` or `pipeline.vote_extractor`.
  - Higher-risk task families such as agenda segmentation, worker startup handling, and lineage recompute remain separate follow-ups.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-08: Extract the segmentation task family without widening the worker boundary

- Status: Accepted
- Decision:
  - The next `pipeline/tasks.py` cleanup wave extracts the `segment_agenda_task` family into private file-local helpers.
  - The segmentation family now has one helper for the main segmentation flow and one helper for the non-gating post-segmentation vote extraction stage.
  - `segment_agenda_task` remains the retry boundary and continues to own `SessionLocal()`, rollback, `self.retry(...)`, and best-effort failure-status persistence in exception paths.
  - The cleanup does not refactor `pipeline.agenda_worker` or backlog-maintenance segmentation flows in the same wave.
- Why:
  - `segment_agenda_task` was the largest remaining mixed-responsibility task wrapper after the earlier family extractions.
  - Splitting the family locally reduces inline orchestration without hiding retry or transaction semantics behind a generic wrapper.
  - Keeping post-segmentation vote extraction inside the family preserves the rule that segmentation success must survive vote-extraction failure.
- Affected boundaries:
  - `pipeline/tasks.py` remains the Celery entrypoint and retry boundary.
  - `pipeline.agenda_resolver`, `pipeline.agenda_service`, and `pipeline.vote_extractor` keep owning their existing domain logic.
  - `pipeline.agenda_worker` and backlog-maintenance segmentation paths remain separate follow-ups.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-08: Finish `pipeline/tasks.py` by extracting the remaining orchestration clusters

- Status: Accepted
- Decision:
  - The final `pipeline/tasks.py` cleanup wave extracts the remaining orchestration-heavy clusters into dedicated support modules:
    - summary hydration/backfill orchestration
    - lineage recompute orchestration
    - worker startup guardrail and startup purge orchestration
  - `pipeline/tasks.py` remains the Celery and signal entrypoint layer and continues to own visible retry boundaries, task decorators, and task payload boundaries.
  - The cleanup keeps compatibility wrappers for the summary-hydration helper entrypoints so existing maintenance scripts can continue importing them from `pipeline.tasks`.
  - No generic task executor, retry abstraction, or shared transaction wrapper is introduced.
- Why:
  - After the earlier task-family waves, the remaining complexity in `pipeline/tasks.py` no longer represented one task family; it represented three separate orchestration domains.
  - Extracting those domains finishes the file without hiding retry/session ownership or widening into unrelated runtime cleanup.
  - Keeping the summary-hydration entrypoints importable from `pipeline.tasks` preserves maintenance tooling compatibility while moving the real orchestration out of the task module.
- Affected boundaries:
  - `pipeline/tasks.py` is now mostly an entrypoint module.
  - `pipeline/summary_backfill.py` owns backlog selection, summary hydration counting, progress reporting, and embed dispatch orchestration.
  - `pipeline/lineage_task_support.py` owns lineage recompute lock/recompute/metrics orchestration.
  - `pipeline/task_startup.py` owns worker-startup guardrail and startup-purge orchestration.
  - `pipeline/task_runtime.py` centralizes the task logger and shared session factory used by the extracted support modules.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-09: Extract the agenda-summary subsystem before broader `pipeline/llm.py` cleanup

- Status: Accepted
- Decision:
  - The next `pipeline/llm.py` legacy-cleanup wave extracts the agenda-summary subsystem centered on `LocalAI.summarize_agenda_items(...)` into a dedicated support module.
  - `LocalAI` remains the orchestration and provider-policy boundary: it still owns provider acquisition plus interpretation of typed provider failures into deterministic fallback or `None`.
  - The extracted module owns agenda-summary-specific flow only: item coercion/filtering, scaffold construction, prompt assembly, output normalization, grounding/pruning, and deterministic fallback selection.
  - Generic summary generation, JSON generation, agenda extraction heuristics, runtime defaults, and task retry ownership remain unchanged.
- Why:
  - After the provider and task-layer cleanup waves, the agenda-summary path is the narrowest high-value seam left inside `pipeline/llm.py`.
  - The path already has dense contract tests for structure, grounding, truncation disclosure, unknowns, and fallback semantics, which makes cleanup safer than a broad `LocalAI` rewrite.
  - Keeping provider policy in `LocalAI` avoids mixing transport outcomes with summary transformation logic.
- Affected boundaries:
  - `pipeline/llm.py` remains the product-policy boundary for local AI behavior.
  - `pipeline/agenda_summary.py` owns agenda-summary transformation and normalization flow.
  - `pipeline/llm_provider.py` continues to own provider transport, payload validation, timeout policy, retry-budget policy, and typed provider failures.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-09: Extract the agenda-extraction subsystem before finishing broader `pipeline/llm.py` cleanup

- Status: Accepted
- Decision:
  - The next `pipeline/llm.py` legacy-cleanup wave extracts the agenda-extraction subsystem centered on `LocalAI.extract_agenda(...)` into a dedicated support module.
  - `LocalAI` remains the orchestration and provider-policy boundary: it still owns provider acquisition plus interpretation of typed provider failures into heuristic fallback behavior.
  - The extracted module owns agenda-extraction-specific flow only: prompt assembly, provider-output parsing, fallback paragraph/numbered-line parsing, grounding-style acceptance checks, deduplication, and extraction counter logging.
  - Generic summary generation, JSON generation, agenda-summary behavior, runtime defaults, and task retry ownership remain unchanged.
- Why:
  - After the provider cleanup, task extraction waves, and agenda-summary extraction, the agenda-extraction path was the next coherent subsystem still embedded inside `pipeline/llm.py`.
  - That path already had focused regression coverage for prompt budgets, parser behavior, segmentation heuristics, backend parity, and task-facing retry semantics, which made it a safer cleanup target than a full `LocalAI` rewrite.
  - Keeping provider outcome interpretation in `LocalAI` avoids mixing provider-policy behavior with extraction heuristics and normalization code.
- Affected boundaries:
  - `pipeline/llm.py` remains the product-policy boundary for local AI behavior.
  - `pipeline/agenda_extraction.py` owns agenda-extraction transformation and fallback parsing flow.
  - `pipeline/llm_provider.py` continues to own provider transport, payload validation, timeout policy, retry-budget policy, and typed provider failures.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-09: Finish `pipeline/llm.py` by extracting heuristics, generic generation, and runtime bootstrap

- Status: Accepted
- Decision:
  - The final structural cleanup wave for `pipeline/llm.py` extracts three remaining mixed-responsibility clusters into dedicated support modules:
    - `pipeline/agenda_text_heuristics.py` for shared agenda lexical and filtering heuristics
    - `pipeline/text_generation.py` for generic summary, JSON-generation normalization, and title-spacing generation helpers
    - `pipeline/local_ai_runtime.py` for backend normalization, provider construction, and in-process runtime bootstrap
  - `pipeline/llm.py` remains the public `LocalAI` product-policy boundary and keeps the public methods `summarize(...)`, `generate_json(...)`, `summarize_agenda_items(...)`, `repair_title_spacing(...)`, and `extract_agenda(...)`.
  - `pipeline/llm.py` also keeps compatibility exports for currently used helper seams so in-repo callers and tests do not need a concurrent migration.
  - Provider-failure semantics, runtime defaults, local-first/fail-fast guardrails, and task retry ownership remain unchanged.
- Why:
  - After the provider cleanup plus the agenda-summary and agenda-extraction extractions, the remaining complexity in `pipeline/llm.py` was no longer one coherent subsystem; it was a mix of residual heuristics, generic text-generation code, and runtime/bootstrap code.
  - Extracting those clusters finishes the file structurally without widening into policy redesign or retry/session abstraction changes.
  - Keeping `LocalAI` as the product-policy boundary preserves the current `None` vs deterministic-fallback behavior while making the implementation easier to reason about and test.
- Affected boundaries:
  - `pipeline/llm.py` is now a thin public boundary centered on `LocalAI` plus compatibility exports.
  - `pipeline/agenda_text_heuristics.py` owns shared agenda text heuristics used by agenda extraction, agenda summary, and a small set of compatibility callers.
  - `pipeline/text_generation.py` owns generic summary formatting, JSON normalization, and title-spacing prompt/output helpers.
  - `pipeline/local_ai_runtime.py` owns runtime/bootstrap mechanics and provider construction while `LocalAI` retains the public seam.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-10: Extract the agenda-summary maintenance family before wider backlog-maintenance cleanup

- Status: Accepted
- Decision:
  - The next `pipeline/backlog_maintenance.py` cleanup wave extracts the agenda-summary maintenance family into `pipeline/agenda_summary_maintenance.py`.
  - The extracted module owns agenda-summary bundle construction, deterministic rendering, summary persistence/hash updates, batch reindex/embed timing helpers, and maintenance summary fallback orchestration.
  - `pipeline/backlog_maintenance.py` remains the maintenance-facing compatibility facade for the currently imported summary-maintenance names.
  - The segmentation maintenance family, timeout overrides, and fallback-event capture helpers remain in `pipeline/backlog_maintenance.py` for now.
  - Summary-backfill reporting fields, timing names, progress payloads, `completion_mode` values, retry ownership, and session ownership remain unchanged.
- Why:
  - The agenda-summary maintenance cluster was the clearest coherent seam left in `pipeline/backlog_maintenance.py` after the provider, task, and `pipeline/llm.py` cleanup waves.
  - That cluster was already consumed as a service-style API by `pipeline/summary_backfill.py`, task maintenance flows, and maintenance scripts, so extracting it sharpens an existing boundary instead of introducing a new abstraction.
  - Deferring segmentation maintenance avoids widening this wave into the more fragile timeout/log-capture cluster or into `pipeline/agenda_worker.py` behavior changes.
- Affected boundaries:
  - `pipeline/backlog_maintenance.py` remains the compatibility import surface for maintenance helpers.
  - `pipeline/agenda_summary_maintenance.py` owns agenda-summary maintenance orchestration only.
  - `pipeline/summary_backfill.py` continues to own backlog selection, reporting, and hydration-loop orchestration.
  - `pipeline/tasks.py` and `pipeline/agenda_worker.py` keep their current retry/session and non-maintenance boundaries.

- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-11: Finish backlog-maintenance cleanup by extracting agenda-segmentation maintenance

- Status: Accepted
- Decision:
  - The final structural cleanup wave for `pipeline/backlog_maintenance.py` extracts the agenda-segmentation maintenance family into `pipeline/agenda_segmentation_maintenance.py`.
  - The extracted module owns maintenance timeout overrides, fallback-event capture, heuristic-first segmentation gating, segmentation status persistence, and `segment_catalog_with_mode(...)`.
  - `pipeline/backlog_maintenance.py` remains the maintenance-facing compatibility facade for both agenda-summary and agenda-segmentation maintenance names.
  - Existing task, worker, script, and test import paths remain stable during this wave.
  - Task retry ownership, session ownership, fallback-counter names, segmentation status semantics, and summary-backfill reporting contracts remain unchanged.
- Why:
  - After agenda-summary maintenance was extracted, the remaining behavior in `pipeline/backlog_maintenance.py` formed one coherent segmentation maintenance family plus the timeout/log-capture helpers that support it.
  - Keeping a compatibility facade avoids a broad patch-path migration while still making the domain boundary explicit.
  - Deferring any redesign of log-derived fallback counters keeps this wave focused on structure rather than behavior.
- Affected boundaries:
  - `pipeline/backlog_maintenance.py` is now a compatibility import surface for maintenance helpers.
  - `pipeline/agenda_segmentation_maintenance.py` owns agenda-segmentation maintenance orchestration.
  - `pipeline/agenda_summary_maintenance.py` continues to own agenda-summary maintenance orchestration.
  - `pipeline/agenda_worker.py` and maintenance scripts keep their existing caller-facing contracts.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-11: Start semantic-index cleanup with shared semantic text utilities

- Status: Accepted
- Decision:
  - The first `pipeline/semantic_index.py` cleanup wave extracts shared semantic text normalization, source hashing, and fallback content chunking into `pipeline/semantic_text.py`.
  - `pipeline.semantic_index` remains the public compatibility facade for semantic backend classes, backend selection, and existing text-helper imports.
  - Backend extraction is deferred: `PgvectorSemanticBackend`, `FaissSemanticBackend` / NumPy artifact fallback, and runtime guardrails remain in `pipeline.semantic_index`.
  - Semantic ranking, source-hash semantics, diagnostics, config defaults, and runtime guardrails remain unchanged.
- Why:
  - `pipeline.semantic_index` is directly imported by semantic tasks, semantic service code, and tests, so splitting backend classes first would risk class-identity, singleton, and monkeypatch drift.
  - The shared text helpers are a low-risk boundary that already supports both semantic indexing and embedding freshness checks.
  - Keeping backend internals in place preserves FAISS/NumPy artifact behavior, pgvector rerank SQL, model loading, and guardrail policy while still reducing mixed responsibility in the module.
- Affected boundaries:
  - `pipeline/semantic_text.py` owns semantic text normalization, truncation, source hashing, and fallback chunking.
  - `pipeline/semantic_index.py` remains the semantic backend facade and compatibility import surface.
  - `pipeline/semantic_tasks.py` and `semantic_service/main.py` keep their existing public contracts.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)

## 2026-04-12: Finish semantic-index cleanup with backend extraction

- Status: Accepted
- Decision:
  - The final structural cleanup wave for `pipeline/semantic_index.py` extracts backend contracts into `pipeline/semantic_backend_types.py`.
  - Pgvector embedding build and hybrid rerank implementation move into `pipeline/semantic_pgvector_backend.py`.
  - FAISS direct vector search, NumPy fallback behavior, and artifact read/write implementation move into `pipeline/semantic_faiss_backend.py`.
  - Runtime guardrail detection and backend selection helpers move into `pipeline/semantic_backend_runtime.py`.
  - `pipeline.semantic_index` remains the public compatibility facade and monkeypatch surface for existing callers and tests.
  - Semantic ranking, source-hash semantics, diagnostics, config defaults, FAISS retirement policy, and runtime guardrails remain unchanged.
- Why:
  - The prior semantic cleanup wave deliberately deferred backend extraction to avoid class-identity, singleton, and monkeypatch drift.
  - Keeping `pipeline.semantic_index` as a facade preserves imports from semantic tasks, semantic service code, scripts, and tests while letting each backend own its implementation details.
  - Pgvector, FAISS/NumPy, and runtime selection are separate orchestration domains, so extracting them sharpens boundaries without introducing a generic vector-backend framework.
- Affected boundaries:
  - `pipeline/semantic_index.py` remains the semantic backend facade and compatibility import surface.
  - `pipeline/semantic_backend_types.py` owns shared backend contracts and result types.
  - `pipeline/semantic_pgvector_backend.py` owns pgvector build and hybrid rerank behavior.
  - `pipeline/semantic_faiss_backend.py` owns FAISS/NumPy artifact and direct vector query behavior.
  - `pipeline/semantic_backend_runtime.py` owns runtime guardrail detection and backend selection helpers.
  - `pipeline/semantic_tasks.py` and `semantic_service/main.py` keep their existing public contracts.
- Canonical references:
  - [ARCHITECTURE.md](../ARCHITECTURE.md)
  - [docs/ENGINEERING_GUARDRAILS.md](ENGINEERING_GUARDRAILS.md)
  - [ROADMAP.md](../ROADMAP.md)
