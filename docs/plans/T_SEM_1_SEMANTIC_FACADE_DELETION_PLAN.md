# T-SEM-1: Delete the Semantic Index Facade

## 1. Context & Alignment

**a) Driver.** Semantic runtime behavior is split behind
`pipeline/semantic_index.py`, while five lower modules import back through that
facade and the runtime selector imports it directly. The resulting reverse
dependencies preserve mutable compatibility patch points, class-bound helper
aliases, and tests that patch backend internals. T-SEM-1 deletes that facade,
makes the existing runtime module own backend selection and optional adapters,
and preserves all semantic retrieval, artifact, reranking, and task behavior.

**b) Canonical documents consulted.**

- `AGENTS.md` requires removal of compatibility re-exports, owner-module test
  patching, local-first defaults, complete verification, and no new runtime
  policy.
- `docs/TESTING.MD` now approves the future semantic runtime fake boundary,
  public pgvector rerank capabilities, and optional-adapter substitution while
  prohibiting backend private-method patches.
- `docs/ENGINEERING_GUARDRAILS.md` keeps Ruff, Mypy, formatter, coverage, and
  boundary exception policy unchanged.
- `ARCHITECTURE.md` identifies FAISS as transitional, pgvector as the target,
  and the facade as part of the current semantic runtime map.
- `docs/ADR.md` records the earlier staged extraction that deliberately kept
  `pipeline.semantic_index` as a compatibility surface.
- `docs/OPERATIONS.md` documents semantic runtime selection, artifact health,
  multiprocess safety, and a stale facade-owner statement.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` requires T-SEM-1 after G3 and
  T-SEM-1A and before T-IDX-1.
- `SECURITY.md` and `docs/DATA_GOVERNANCE.md` impose no additional boundary for
  this internal ownership correction.

**c) Remediation alignment.** T-SEM-1 owns exactly 33 files.

Planning and canonical docs:

- `docs/plans/T_SEM_1_SEMANTIC_FACADE_DELETION_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `ARCHITECTURE.md`
- `docs/ADR.md`
- `docs/OPERATIONS.md`

Production:

- `pipeline/semantic_index.py` (delete)
- `pipeline/semantic_backend_runtime.py`
- `pipeline/semantic_faiss_backend.py`
- `pipeline/semantic_faiss_artifacts.py`
- `pipeline/semantic_faiss_rows.py`
- `pipeline/semantic_pgvector_backend.py`
- `pipeline/semantic_pgvector_rerank.py`
- `pipeline/semantic_pgvector_rows.py`
- `pipeline/semantic_tasks.py`
- `pipeline/reindex_semantic.py`
- `pipeline/diagnose_semantic_search.py`
- `semantic_service/main.py`

Tests:

- `tests/conftest.py`
- `tests/test_repository_guardrails.py`
- `tests/test_semantic_backend_selection.py`
- `tests/test_semantic_require_faiss.py`
- `tests/test_semantic_memory_guardrails.py`
- `tests/test_semantic_numpy_fallback.py`
- `tests/test_semantic_numpy_topk_selection.py`
- `tests/test_semantic_index_build.py`
- `tests/test_pgvector_rerank_diagnostics.py`
- `tests/test_embed_catalog_task_source_hash.py`
- `tests/test_search_pgvector_hybrid_rerank.py`
- `tests/test_semantic_recall_filters.py`
- `tests/test_semantic_service_api.py`
- `tests/test_semantic_service_contract_helpers.py`
- `tests/test_semantic_service_hydration.py`
- `tests/test_semantic_dedup_catalog.py`

All other files are verification-only. Any additional edit requires ownership
expansion before implementation.

**d) Decision-gate check.** G3 is satisfied by T-GOV-1 and the T-SEM-1A policy
prerequisite is merged. This deletion does not depend on or foreclose G1, G2,
G4, or G5. Runtime defaults, backend policy, and soak comparability remain
unchanged.

## 2. Design

**e) Step-by-step approach.**

1. Register this Full plan and exact ownership in the remediation ledger.
2. Add failing structural tests that require the facade to be absent, reject
   every tracked import of `pipeline.semantic_index`, reject all five
   `_semantic_index_facade` functions, and reject the six class-bound helper
   aliases.
3. Add or update behavior tests before implementation so optional adapters are
   patched only in `pipeline.semantic_backend_runtime`, pgvector service tests
   patch the runtime selector owner, and FAISS singleton state is isolated by a
   non-autouse fixture.
4. Move the optional `faiss` and `SentenceTransformer` bindings into
   `pipeline.semantic_backend_runtime`. Keep backend implementation imports
   local inside `get_semantic_backend()` so the runtime module does not create
   an import cycle.
5. Make lower modules import configuration from `pipeline.config` and resolve
   optional adapters or worker detection through the runtime owner module.
   Consumers import `pipeline.semantic_backend_runtime as
   semantic_backend_runtime` and call through that module so approved runtime
   patches cannot be bypassed by stale direct-function bindings. Delete the
   five facade lookup functions and the runtime module's direct reverse import.
6. Remove FAISS class-bound aliases for `_artifact_paths`, `_load_artifacts`,
   `_write_artifacts`, and `_collect_rows`. Call their existing focused helper
   modules directly and remove the unused backend arguments from
   `_artifact_paths` and `_collect_rows`.
7. Remove pgvector class-bound aliases for `_collect_catalog_summary_rows` and
   `rerank_candidates_with_diagnostics`. Keep the public backend method as a
   narrow delegate to the existing rerank implementation and remove the unused
   backend argument from `_collect_catalog_summary_rows`.
8. Repoint semantic service and CLI consumers to import
   `pipeline.semantic_backend_runtime as semantic_backend_runtime` and call
   `semantic_backend_runtime.get_semantic_backend()`. Repoint contract imports
   to `pipeline.semantic_backend_types` and text helpers to
   `pipeline.semantic_text`.
9. Keep the semantic import inside `embed_catalog_task` local, but import its
   direct implementation owners so Celery worker startup does not eagerly load
   optional model dependencies.
10. Delete `pipeline/semantic_index.py`, update canonical architecture and
    operations text, then run all verification, simplification review,
    independent pre-commit review, delivery, and CI adjudication.

Each module keeps one responsibility: runtime selection and optional adapters
in `semantic_backend_runtime`; FAISS query behavior in
`semantic_faiss_backend`; artifact persistence in `semantic_faiss_artifacts`;
row construction in the row modules; and pgvector reranking in
`semantic_pgvector_rerank`. Helper modules never import a facade.

**f) Reuse audit.** Reuse the existing backend types, runtime selector,
configuration module, text helpers, backend implementations, artifact helpers,
row builders, and rerank implementation. No new registry, adapter framework,
base class, compatibility module, or test seam is added. The superseded
`pipeline.semantic_index` stratum and its reverse lookups are deleted in the
same PR.

**g) Data contracts.** Preserve `BuildResult`, `SemanticCandidate`,
`SemanticRerankResult`, `SemanticConfigError`, and `SemanticBackend` in
`pipeline.semantic_backend_types`. Pgvector's public rerank methods remain
backend-specific capabilities consumed by semantic retrieval. No raw payload
contract, API response, task payload, or persisted artifact format changes.

**h) Schema/migration impact.** None. No PostgreSQL extension, pgvector column,
index, stored embedding, artifact filename, metadata key, or timestamp behavior
changes.

## 3. Security & Data Governance

**i) Security-sensitive paths.** None under `AGENTS.md`. This change neither
opens a network boundary nor changes authentication, key handling, container
exposure, or service permissions. Existing semantic health sanitization must
continue to prevent local paths and backend details from reaching callers.

**j) Secrets.** No credential, key, environment variable, or default is added
or changed.

**k) Person data.** No person record is created, linked, aggregated, or
exposed. G4 remains unaffected.

**l) Untrusted input.** Search text, lexical hits, database summaries, and
artifact files remain untrusted at their existing boundaries. Existing text
sanitization, typed semantic candidates, artifact JSON parsing, and public
health sanitization remain unchanged.

## 4. Code Health

**m) GED conformance sweep.** Modified functions keep one responsibility,
existing domain names, timezone-aware UTC build timestamps, and current typed
contracts. No new environment read, error swallowing, broad handler, or
literal policy is introduced. Local imports are retained only where they
prevent cycles or eager optional-runtime loading.

**n) Antipattern scan, plan pass.**

- A1/H1: no dependency-facing API changes; optional adapter imports and NumPy
  operations are moved without changing their calls.
- B1/B2/C1/F1: the facade and aliases are deleted rather than replaced with a
  wrapper or compatibility path.
- B3: no speculative validation or retry is added.
- C2/D2: tests move to the approved runtime, database, filesystem, and public
  rerank boundaries; no new patchability parameter or private-method seam.
- D1: no skip, xfail, tolerance, or policy weakening. NumPy fallback remains
  intentionally unnormalized because changing it would alter scores.
- D3: exact structural assertions are accepted for the deletion contract;
  behavior tests assert results, artifacts, diagnostics, and errors.
- E1-E3: only the 33 owned files may change; no broad formatting or unrelated
  rewrite.
- F2/H3: existing focused modules remain the single owners.
- A2-A4 and H2/H4: no new setting, placeholder, suppression, type escape, or
  import-time engine/client/model creation.

**o) Ratchet interaction.** No Ruff ignore, BLE001 boundary, formatter scope,
Mypy scope, coverage floor, workflow rule, or runtime gate changes. T-SEM-1
adds structural deletion assertions without widening an allowlist.

**p) Dead code and duplication audit.** Delete one facade file, five reverse
lookup functions, six class-bound aliases, three unused helper parameters, all
facade imports, and compatibility-only tests. Reuse direct owners for every
remaining behavior. Expected production delta is materially negative.

## 5. Testing

**q) Edge cases and failure scenarios.**

1. Backend selection returns the same FAISS or pgvector implementation for the
   existing configuration values.
2. Optional FAISS absence still uses NumPy unless FAISS is required.
3. FAISS-present vectors remain L2-normalized.
4. NumPy fallback vectors remain unnormalized and rank by raw dot product.
5. Multiprocess guardrails still fail fast under unsafe FAISS configuration.
6. Missing or malformed artifacts still yield sanitized health errors.
7. Artifact names, metadata, row precedence, source counts, and corpus hashes
   remain stable.
8. FAISS singleton state cannot leak between requesting tests.
9. Pgvector model state starts fresh per backend instance and embeddings remain
   normalized.
10. Pgvector reranking preserves candidate limits, freshness diagnostics,
    stale/missing embedding behavior, ordering, and lexical degradation.
11. Semantic service health and search continue to sanitize backend details.
12. Direct-vector filtering, expansion, deduplication, hydration, and ordering
    remain unchanged.
13. `semantic.embed_catalog` keeps its task name, route, lazy import,
    source-hash caching, and stored vector dimensions.
14. No tracked Python file imports the deleted facade or recreates a class-bound
    helper alias.
15. Optional adapters unavailable during import do not break unrelated module
    imports.

**r) Tests added or updated.**

- Repository guardrails: facade deletion, reverse-import absence, five lookup
  deletion checks, and six class-alias deletion checks cover scenario 14.
- Backend selection and runtime guardrail tests cover scenarios 1, 2, 5, and
  15 through the runtime owner.
- FAISS/NumPy artifact, top-k, and build tests cover scenarios 2-8 with real
  temporary artifacts and optional-adapter fakes.
- Pgvector rerank and embed-task tests cover scenarios 9, 10, and 13 without
  private backend patches.
- Semantic service API, recall, hybrid rerank, contract-helper, hydration, and
  dedup tests cover scenarios 10-12 through the runtime selector boundary. A
  service test patches the runtime owner and proves `semantic_service/main.py`
  observes the replacement backend.
- Existing unchanged semantic task-routing, semantic text, NumPy benchmark,
  search API, feature-flag, model-constraint, and runtime-profile tests cover
  scenarios 3, 7, 12, 13, and 15.

**s) Fakes and mocks.** Database tests use the approved session boundary;
service tests patch `pipeline.semantic_backend_runtime.get_semantic_backend`;
optional model/FAISS tests patch adapters only in
`pipeline.semantic_backend_runtime`; filesystem behavior uses `tmp_path`.
Pgvector fakes implement the public rerank capability exercised by each test.
No facade, re-export, private backend method, or callable parameter is patched.

**t) Verification rows.** Apply the guardrail/tooling row because repository
guardrails change, the pipeline/task row because `semantic_tasks.py` changes,
the frontend-contract row because semantic API behavior is cross-checked, and
the docs-only row. Run all focused semantic suites, the complete coverage suite,
and authoritative PR CI.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

Tests-first red evidence:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_repository_guardrails.py::test_semantic_index_facade_is_deleted \
  tests/test_repository_guardrails.py::test_semantic_backend_helpers_have_direct_owners
```

Focused semantic verification:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_semantic_backend_selection.py \
  tests/test_semantic_require_faiss.py \
  tests/test_semantic_memory_guardrails.py \
  tests/test_semantic_numpy_fallback.py \
  tests/test_semantic_numpy_topk_selection.py \
  tests/test_semantic_numpy_topk_benchmark.py \
  tests/test_semantic_index_build.py \
  tests/test_pgvector_rerank_diagnostics.py \
  tests/test_embed_catalog_task_source_hash.py \
  tests/test_search_pgvector_hybrid_rerank.py \
  tests/test_semantic_recall_filters.py \
  tests/test_semantic_service_api.py \
  tests/test_semantic_service_contract_helpers.py \
  tests/test_semantic_service_hydration.py \
  tests/test_semantic_dedup_catalog.py \
  tests/test_semantic_task_routing.py \
  tests/test_semantic_text.py \
  tests/test_semantic_search_api.py \
  tests/test_semantic_search_feature_flag.py \
  tests/test_semantic_embedding_model_constraints.py \
  tests/test_runtime_profiles_defaults.py
```

Final verification:

```bash
./.venv/bin/ruff check .
./.venv/bin/ruff format --check .
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_run_pipeline_orchestration.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_pipeline_batching.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_task_metrics.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_frontend_pages_config.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_resultcard_agenda_status_refresh.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_search_sort_ui_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_semantic_search_ui_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/python -m pytest -q --cov --cov-config=.coveragerc \
  --cov-report=term-missing:skip-covered tests/
git diff --check
git status --short
```

After tests pass, run simplification and a fresh independent P1/P2 pre-commit
review, apply eligible findings, rerun affected checks, create atomic commits,
push, open one PR, request Codex review, and watch all required checks.

**v) Rollback.** Revert the T-SEM-1 merge commit, rerun the same focused,
guardrail, docs, pipeline, frontend-contract, and coverage commands, and rebuild
semantic artifacts only if an operator wrote them while the reverted code was
active. No schema reversal or stored-data repair is required because artifact
and embedding formats do not change.

**w) Docs synchronization.**

- `ARCHITECTURE.md`: replace facade ownership references with direct runtime,
  contract, backend, and helper owners.
- `docs/ADR.md`: record completion of the staged facade retirement and direct
  owner boundaries.
- `docs/OPERATIONS.md`: replace the stale facade runtime guardrail statement
  and any active facade command references.
- Remediation plan: activate T-SEM-1 with exact ownership and execution order;
  mark T-SEM-1A complete.
- README, `AGENTS.md`, `docs/TESTING.MD`, security, data governance,
  performance, roadmap, OpenAPI, and environment docs remain unchanged.

## 7. Delivery Self-Audit

**x) Diff scan.** Re-run A-F/H. Reject a replacement facade, compatibility
re-export, reverse import, class-bound helper alias, private-method patch,
NumPy normalization change, eager model creation, config/default drift,
allowlist widening, unrelated formatting, or a 34th changed file.

**y) Evidence.** Report tests-first failures; all focused, guardrail, Ruff,
formatter, Mypy, docs, pipeline, frontend-contract, and coverage outcomes;
collected/pass/skip counts and coverage; planning and pre-commit review
findings; commit hashes; PR URL; unresolved-thread count; and final CI state.
Mark anything unrun `NOT VERIFIED`.

**z) Deviations.** Expected result is none. Any additional owned path, runtime
policy change, artifact format change, model behavior change, test skip,
private-method seam, unresolved P1/P2, skipped review, or unrun required check
is a blocker and must be reported.
