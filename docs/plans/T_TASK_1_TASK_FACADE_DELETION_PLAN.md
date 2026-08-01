# T-TASK-1: Delete the Task Facade Helper Layer

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: implementation-ready`
`execution: code`

## 1. Context & Alignment

**a) Driver.** T-DC-2B is merged, so T-TASK-1 is the next ordered remediation
task. `pipeline/tasks.py` still passes `globals()` through nine compatibility
forwarders into `pipeline/task_facade_helpers.py`; the task-family modules then
receive twelve callable slots, five configuration slots, and one service bag.
This test-seam architecture obscures ownership and keeps production code tied
to historical monkeypatch targets. The task deletes that layer while preserving
all Celery identities, retry rules, sessions, payloads, persistence ordering,
and non-gating side effects.

**b) Canonical documents consulted.**

- `AGENTS.md` hierarchy, known-antipatterns, workflow contract, and verification
  matrix require direct owners, approved test boundaries, exact evidence, and
  the pipeline/task plus full-suite gates.
- `docs/TESTING.MD` limits substitution to the database session factory,
  inference provider contract, Celery boundary, Meilisearch client,
  outbound-HTTP transport, clock, and filesystem rather than facade exports.
- `docs/ENGINEERING_GUARDRAILS.md` keeps Ruff configuration and the BLE001
  boundary inventory authoritative.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` orders T-TASK-1 after T-DC-2B
  and requires exact ownership before implementation.
- `docs/reviews/architecture-review-2026-07-19.html` identifies task facades,
  `globals()` bags, and injected callables as deletion targets.
- `SECURITY.md` and `docs/DATA_GOVERNANCE.md` impose no additional runtime or
  person-data decision for this task.

**c) Remediation alignment.** Register T-TASK-1 in the pipeline/task lane with
these 23 owned paths:

- `docs/plans/T_TASK_1_TASK_FACADE_DELETION_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `pipeline/tasks.py`
- `pipeline/task_facade_helpers.py` (delete)
- `pipeline/task_agenda_segmentation.py`
- `pipeline/task_text_extraction.py`
- `pipeline/task_vote_extraction.py`
- `pipeline/task_startup.py`
- `tests/test_repository_guardrails.py`
- `tests/test_task_facade_cleanup.py`
- `tests/test_extract_task.py`
- `tests/test_tasks_vote_extraction_flow.py`
- `tests/test_async_flow.py`
- `tests/test_summary_generation_operation.py`
- `tests/test_summary_blocking.py`
- `tests/test_task_provider_retry_semantics.py`
- `tests/test_tasks_lineage_flow.py`
- `tests/test_worker_ready_concurrency_guardrail.py`
- `tests/test_agenda_title_extraction.py`
- `ARCHITECTURE.md`
- `docs/ADR.md`
- `docs/PIPELINE.md`
- `docs/TESTING.MD`

No other tracked file may change.

**d) Decision gates.** G3 authorizes direct implementation ownership and is
satisfied. G1, G2, G4, and G5 are unaffected. No open decision gate blocks or
is foreclosed by this deletion.

## 2. Design

**e) Step-by-step approach.**

1. Register the plan and ownership in the remediation ledger.
2. Add failing structural tests before implementation for the helper-file
   deletion, absence of `globals()`/compatibility wrappers, exact direct-family
   signatures, stable Celery task contracts, and forbidden test patch paths.
3. In `pipeline/tasks.py`, import domain modules rather than implementation
   symbols, call `pipeline.task_runtime.task_session()` directly, and keep the
   six Celery-decorated entrypoints in place. Remove the agenda-title test seam
   and repoint its test to `pipeline.task_agenda_titles`.
4. In `pipeline/task_text_extraction.py`, replace injected minimum length,
   extraction callable, and reindex callable with direct configuration,
   extraction-service, and indexer module ownership.
5. In `pipeline/task_vote_extraction.py`, replace injected feature policy,
   vote operation, and reindex callable with direct config, vote-extractor, and
   indexer module ownership.
6. In `pipeline/task_agenda_segmentation.py`, delete
   `AgendaSegmentationTaskServices`; call classifier, resolver, persistence,
   vote extraction, indexer, and feature policy through their direct modules.
7. In `pipeline/task_startup.py`, read current worker policy from the existing
   config module and call runtime guardrail and startup purge owners directly.
   Keep signal binding in `pipeline/tasks.py`.
8. Repoint tests from `pipeline.tasks` compatibility symbols to approved
   session-factory, provider-contract, Celery-task, filesystem, outbound-HTTP,
   and Meilisearch boundaries. Task-family behavior tests call the actual
   operation owners rather than replacing those operations. Celery `.retry`
   remains patched on the actual decorated task object because retry dispatch
   is the observable task boundary.
9. Delete `pipeline/task_facade_helpers.py`, all wrappers, imports, service bags,
   and obsolete test expectations in the same change.
10. Synchronize architecture, pipeline, testing policy, ADR supersession, and
    the remediation ledger; run simplification and independent pre-commit review.

Installed-code inspection confirms `LocalAI()` only allocates the singleton;
provider and configuration access happens during operation calls. The existing
vote-task construction order therefore remains unchanged rather than adding an
unreachable defensive branch. The worker-ready receiver continues to accept
and ignore additional Celery signal keyword arguments.

No new module or function is planned. Import direction stays
`tasks -> task-family module -> domain owner`; no lower module imports
`pipeline.tasks`.

**f) Reuse audit.** Reuse `pipeline.task_runtime`,
`pipeline.task_summary_generation`, `pipeline.extraction_service`,
`pipeline.vote_extractor`, `pipeline.agenda_resolver`,
`pipeline.agenda_service`, `pipeline.laserfiche_error_pages`,
`pipeline.indexer`, `pipeline.runtime_guardrails`, and
`pipeline.startup_purge`. The helper facade and service dataclass are deleted,
not renamed or replaced. `pipeline/task_runtime.py` remains the legitimate lazy
session-factory owner and is not modified.

**g) Data contracts.** Existing task result dictionaries remain unchanged.
No new raw-dictionary trust boundary or typed contract is added. The registered
Celery contracts remain:

| Task | Signature | Retry contract |
|---|---|---|
| `pipeline.tasks.generate_summary_task` | `(catalog_id, force=False)` | max 3, countdown 60 |
| `pipeline.tasks.segment_agenda_task` | `(catalog_id)` | max 3, countdown 60 |
| `pipeline.tasks.extract_votes_task` | `(catalog_id, force=False)` | max 3, countdown 60 |
| `pipeline.tasks.extract_text_task` | `(catalog_id, force=False, ocr_fallback=False)` | max 3, countdown 60 |
| `pipeline.tasks.compute_lineage_task` | `()` | max 3, countdown 30 |
| `pipeline.tasks.compute_lineage_for_catalog_task` | `(catalog_id)` | max 1 |

**h) Schema and migrations.** None. No database column, stored value, migration,
or timestamp contract changes.

## 3. Security & Data Governance

**i) Security boundary.** No `AGENTS.md` security-sensitive path is touched.
Task queue identity, provider policy, secrets, ports, authentication, and
network exposure remain unchanged. Direct imports reduce mutable patch surface
without changing attacker capability.

**j) Secrets.** No credential, key, environment variable, or default is added
or changed.

**k) Person data.** No person data is created, linked, aggregated, or exposed.
G4 is unaffected.

**l) Untrusted input.** Catalog content and provider responses continue through
their existing extraction, resolver, grounding, and provider boundaries. This
task only changes internal ownership and does not add a parsing or rendering
boundary.

## 4. Code Health

**m) GED conformance sweep.** Direct module owners replace generic facade,
service, and callable parameters. Existing retry handlers continue to rollback,
persist segmentation failure status where required, and retry or return typed
payloads. UTC segmentation timestamps remain unchanged. No new environment read,
magic timeout, broad exception, type suppression, import-time engine, or network
call is added. Existing task functions may retain their current nesting because
the task does not expand them; helper deletion reduces indirection instead.

**n) Antipattern scan, plan pass.**

- A1/H1: no dependency-facing API is added or changed. Installed Celery task
  names, decorators, `.retry`, and signal binding are preserved from current
  code and contract tests rather than inferred from memory.
- B1/B2/C1/F1: the helper, service bag, wrappers, and aliases are deleted; no
  executor, registry, adapter, compatibility path, or replacement bag is added.
- C2/D2: tests move to established runtime boundaries; no new seam is created.
- D1/D3: exact task identity and observable persistence/retry/payload behavior
  stay asserted; no test is skipped or weakened.
- E1/E2: edits stay within the 23 owned files; no broad formatting occurs.
- A2-A4, B3, E3, F2, H2-H4: no violation planned.

**o) Ratchet interaction.** `pipeline/tasks.py` and `pipeline/task_startup.py`
are existing BLE001 boundaries. This task adds no entry and does not widen any
selector. The broad startup catch remains because worker-ready must log policy
inspection failure and still run the established purge invariant. Removing a
BLE001 entry is not claimed because the approved catches remain.

**p) Dead code and duplication audit.** Delete `task_facade_helpers.py`,
`_TASK_FACADE_DEPENDENCIES`, `SessionLocal`, nine compatibility forwarders,
five `globals()` bags, `AgendaSegmentationTaskServices`, twelve callable slots,
five scalar injection slots, the agenda-title re-export, and unreachable
agenda/vote task-level provider catches. Reuse direct owners; expected
production delta is materially negative. The separate
`pipeline/enrichment_tasks.py` topic-generation service bag is explicitly
deferred because it is outside this task's registered ownership.

## 5. Testing

**q) Edge cases and failure scenarios.**

1. Each Celery task keeps its exact name, parameters, defaults, bind setting,
   retry limit, and countdown.
2. Database sessions are created once, rolled back on the same failures, and
   always closed.
3. Summary provider configuration errors retain their reachable error payload
   and do not retry; dead agenda/vote task catches are removed because those
   operation families already contain provider failures.
4. Segmentation errors persist failed status before returning or retrying;
   failure-status persistence errors remain non-authoritative after rollback.
5. Extraction and vote writes commit before best-effort reindex.
6. Post-segmentation vote extraction remains non-gating.
7. Disabled vote extraction and missing agenda items retain current payloads.
8. Missing catalog, content, or document links retain current errors.
9. Worker-ready pool/concurrency enforcement and purge ordering remain intact.
10. Tests cannot reintroduce `pipeline.tasks` patch aliases, helper bags, or a
    renamed service registry.
11. Lineage task payload, retry, and catalog-task forwarding remain unchanged.
12. Summary blocking, retry, and completion behavior remain unchanged.
13. Worker-ready remains compatible with additional Celery signal keywords.
14. Reverse-import guards cover the four task-family implementation modules,
    not legitimate task clients such as `pipeline/run_agenda_qa.py`.

**r) Tests mapped to scenarios.**

| Test group | Scenarios |
|---|---|
| New AST deletion and exact-signature guards in `test_repository_guardrails.py` and `test_task_facade_cleanup.py` | 1, 10, 14 |
| `test_extract_task.py` | 1, 2, 5, 8 |
| `test_tasks_vote_extraction_flow.py` | 1, 2, 5, 7, 8 |
| Segmentation cases in `test_async_flow.py` | 1-4, 6, 8 |
| `test_worker_ready_concurrency_guardrail.py` | 9, 13 |
| Summary operation, blocking, and provider retry tests | 1-3, 12 |
| `test_tasks_lineage_flow.py` | 1, 2, 11 |
| `test_agenda_title_extraction.py` | 10 |
| Complete suite and coverage gate | 1-14 and cross-family regressions |

Tests are added or tightened first and captured red before production edits.

**s) Fakes and mocks.** Approved boundaries are:

- `pipeline.task_runtime.task_session` for task-owned database sessions.
- A fake implementing `pipeline.inference_provider_contract.InferenceProvider`
  for inference.
- Filesystem, outbound HTTP transport, and Meilisearch client construction for
  their corresponding external effects.
- The actual Celery task object's `.retry` method for retry observation.

No facade, re-export, task-family operation, or injected callable is patched.

**t) Verification rows.** Apply the pipeline/task orchestration row, inference
row because the task-level provider boundary remains exercised, guardrail/tooling
row because the structural test changes, docs-only row, and the coverage-backed
complete suite because this is cross-cutting task infrastructure.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-task-1-task-facade-deletion

PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_repository_guardrails.py::test_task_facade_helper_layer_is_deleted \
  tests/test_task_facade_cleanup.py

./.venv/bin/ruff check .
./.venv/bin/ruff format --check . --config ruff-format.toml
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_extract_task.py \
  tests/test_tasks_vote_extraction_flow.py \
  tests/test_async_flow.py \
  tests/test_summary_generation_operation.py \
  tests/test_summary_blocking.py \
  tests/test_task_provider_retry_semantics.py \
  tests/test_tasks_lineage_flow.py \
  tests/test_worker_ready_concurrency_guardrail.py
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_run_pipeline_orchestration.py \
  tests/test_pipeline_batching.py \
  tests/test_task_metrics.py \
  tests/test_inference_provider_protocol_contract.py \
  tests/test_provider_error_mapping_retry_vs_fallback.py \
  tests/test_llm_backend_parity_*.py \
  tests/test_repository_guardrails.py \
  tests/test_docs_links.py
PYTHONPATH=. .venv/bin/python -m pytest -q --cov --cov-config=.coveragerc \
  --cov-report=term-missing:skip-covered tests/
git diff --check
git status --short
```

After verification, run simplification and a fresh subagent pre-commit review,
apply every eligible P1/P2, commit, push, open the T-TASK-1 PR, and watch CI and
review threads to a decided state.

**v) Rollback.** Revert the T-TASK-1 merge commit, then run Ruff, formatter,
Mypy, task-family tests, repository guardrails, docs links, and the
coverage-backed complete suite. No migration, data remediation, configuration
restore, queue purge, or external-state cleanup is required. Rollback restores
the facade helper and old patch points.

**w) Docs synchronization.**

- `ARCHITECTURE.md`: task facade and domain-owner map.
- `docs/ADR.md`: supersede compatibility portions of the April task split and
  May cleanup-seam decisions.
- `docs/PIPELINE.md`: direct task-family ownership and ordering.
- `docs/TESTING.MD`: task session, provider-contract, and Celery retry patch
  boundaries.
- Remediation ledger: v3.93 activation and later completion status.
- README, operations, performance, roadmap, security, data governance, API
  contract, and frontend docs: no change.

## 7. Delivery Self-Audit

**x) Diff scan.** Re-run A-F/H against the final diff. Reject any new task
executor, registry, wrapper, re-export, injected callable, service bag,
`globals()` lookup, duplicate operation, changed task identity, widened Ruff
exception, type suppression, import-time runtime creation, or edit outside the
23 owned paths.

**y) Evidence.** Report the tests-first red result; exact Ruff, formatter,
Mypy, targeted, guardrail, docs, coverage, and full-suite outcomes; independent
planning and pre-commit review findings; commit hashes; PR URL; unresolved
thread count; and final CI state. Mark anything unrun `NOT VERIFIED`.

**z) Deviations.** Expected result is none. Any additional path, altered task
name/signature/retry, new dependency, policy/default change, skipped review,
unresolved P1/P2, or unrun required gate is a blocker and must be reported.
