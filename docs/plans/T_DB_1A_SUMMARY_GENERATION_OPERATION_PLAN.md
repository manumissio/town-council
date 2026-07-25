# T-DB-1A: Make Summary Generation a Direct Operation

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: implementation-ready`
`execution: code`

## 1. Context & Alignment

**a) Driver.** Summary generation currently routes fifteen callables through
`SummaryGenerationTaskServices`, constructs that service bag from
`tasks.py.globals()`, and crosses two facade wrappers before reaching the
actual operation. This preserves test patch targets instead of an
architectural boundary. T-DB-1A removes that summary-only service locator
before T-DB-1 collapses the separate backfill facade, while preserving summary
results, persistence, best-effort side effects, and the registered Celery task.

**b) Canonical documents consulted.**

- `AGENTS.md` `<known_antipatterns>`, `<workflow_contract>`, and
  `<verification_matrix>` prohibit service-locator globals, test-seam
  re-exports, and injectable callables while requiring targeted and complete
  verification.
- `docs/TESTING.MD` "Approved fake boundaries" and "Patch-target rules"
  require tests to use the database, Celery, inference-provider, and
  Meilisearch boundaries rather than facade globals.
- `docs/ENGINEERING_GUARDRAILS.md` keeps Ruff and the repository smell tests
  authoritative.
- `docs/ADR.md` "Test patch points are not a public API" authorizes deletion
  of test-only facade seams while preserving runtime and task contracts.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` places this work in DEDUP-B,
  after G3 and before the broader T-DB-1 backfill cleanup.
- `docs/reviews/architecture-review-2026-07-19.html` identifies facade
  machinery and callable dependency bags as architectural debt.

**c) Remediation alignment.** Add T-DB-1A to the DEDUP-B lane before T-DB-1.
Its exclusive `files_owned` set is:

- `docs/plans/T_DB_1A_SUMMARY_GENERATION_OPERATION_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `docs/ADR.md`
- `pipeline/task_summary_generation.py`
- `pipeline/task_summary_generation_contracts.py`
- `pipeline/task_summary_generation_flow.py`
- `pipeline/task_summary_generation_persistence.py`
- `pipeline/task_summary_empty_agenda.py`
- `pipeline/task_summary_side_effects.py`
- `pipeline/task_facade_helpers.py`
- `pipeline/tasks.py`
- `tests/test_summary_generation_operation.py`
- `tests/test_agenda_summary_payload_budget.py`
- `tests/test_summary_blocking.py`
- `tests/test_task_provider_retry_semantics.py`
- `tests/test_tasks_agenda_summary_format.py`
- `tests/test_async_flow.py`
- `tests/test_task_facade_cleanup.py`
- `tests/test_repository_guardrails.py`

T-DB-1A must merge before T-DB-1. No other tracked file may change.

**d) Decision-gate check.** G3 is satisfied and directly authorizes removal of
test-only patch seams. G1, G2, G4, and G5 are unaffected. No open gate blocks
this task.

## 2. Design

**e) Step-by-step approach.**

1. Record this Full plan and T-DB-1A ownership before implementation.
2. Add failing behavior and structure tests before changing production code.
3. Make `pipeline/task_summary_generation.py` the canonical operation owner.
   Its single public `generate_catalog_summary` operation accepts an existing
   SQLAlchemy session, `catalog_id`, and `force`, then coordinates load,
   preparation, freshness, generation, persistence, commit, and side effects.
4. Retain `pipeline/task_summary_generation_flow.py` as a focused preparation
   helper. It loads catalog/document/agenda records, validates source quality,
   builds agenda input, and determines cached or stale outcomes. It imports
   concrete domain helpers and never imports the operation owner or task
   facade. Delete its old `run_generate_summary_task_family` end-to-end runner.
5. Reduce `pipeline/task_summary_generation_contracts.py` to data-only
   constants and typed dataclasses. Delete `SummaryGenerationTaskServices`
   and every callable field.
6. Update `pipeline/task_summary_generation_flow.py` to import
   `agenda_summary_inputs.build_agenda_summary_input_bundle` directly. Update
   `pipeline/task_summary_generation_persistence.py` to import
   `agenda_summary_batch.persist_agenda_summary` and the real inference,
   grounding, and freshness-hash modules directly. Neither module may import
   `backlog_maintenance` or `agenda_summary_maintenance`. Persistence receives
   only data contexts, not injectable callables.
7. Update `pipeline/task_summary_empty_agenda.py` to use direct freshness and
   persistence imports. Its context contains only session and summary record
   data.
8. Update `pipeline/task_summary_side_effects.py` to call the real indexer and
   Celery embed task. Existing best-effort exception handling and result
   counters remain unchanged.
9. Delete summary-generation service construction and forwarding from
   `pipeline/task_facade_helpers.py`.
10. Import the operation module in `pipeline/tasks.py` and call it directly
    from the existing bound Celery task. Preserve task name, arguments,
    retries, countdown, logging, transaction rollback, and session closure.
11. Repoint affected tests to the operation and approved boundaries. Inference
    tests patch `pipeline.llm.get_runtime_provider`; indexing tests fake
    `pipeline.indexer.meilisearch.Client` plus its database boundary; embed
    dispatch tests patch `embed_catalog_task.delay`. Do not retain aliases,
    wrappers, synchronized globals, or callable injection for obsolete patch
    targets.
12. Run the applicable verification rows, simplify the diff, obtain a fresh
    subagent pre-commit review, fix eligible P1/P2 findings, and deliver one PR.

Import direction:

```text
pipeline/tasks.py
  -> pipeline/task_summary_generation.py
       -> task_summary_generation_flow.py
       -> task_summary_generation_persistence.py
            -> task_summary_side_effects.py
       -> task_summary_generation_contracts.py
```

Helpers never import `pipeline/tasks.py` or
`pipeline/task_summary_generation.py`.

**f) Reuse audit.** Reuse the current summary preparation, persistence,
grounding, agenda payload, side-effect, and task-session behavior. The
equivalent implementation already exists but is obscured by
`SummaryGenerationTaskServices` and two forwarding layers; this task removes
those layers rather than adding a parallel implementation. The retained flow,
persistence, empty-agenda, and side-effect modules each keep one real
responsibility. No new utility, manager, registry, factory, or compatibility
module is created.

**g) Data contracts.** Keep typed data contexts in
`task_summary_generation_contracts.py`, using SQLAlchemy `Session`, `Catalog`,
`Document`, and the existing agenda payload mapping convention.
`SummaryTaskContext` loses its services field. No raw external-input boundary
is added. Celery's returned dictionary remains the observable task contract.

**h) Schema/migration impact.** None. No database declaration, migration,
stored value, timestamp, or transaction ordering changes.

## 3. Security & Data Governance

**i) Security-sensitive paths.** None of the owned files is listed under
`AGENTS.md` `<security_sensitive_paths>`. The task does not alter
authentication, proxying, credentials, CORS, or port exposure.

**j) Secrets.** No secret, credential, environment variable, or default is
added or changed.

**k) Person data.** No person-level data is created, linked, aggregated, or
exposed. G4 is unaffected.

**l) Untrusted input.** Extracted catalog text and model responses remain the
untrusted inputs. Existing source-quality checks, grounding checks, typed
provider failures, and persistence rules remain the validation boundaries.
No new rendering or network surface is introduced.

## 4. Code Health

**m) GED conformance sweep.** Modified functions remain focused, use domain
names, and stay below Ruff's complexity ceiling. Data contexts prevent
parameter growth. Existing meaningful exception behavior remains: summary
persistence is authoritative, while index and embed failures are logged with
catalog context and returned as explicit counters. No timestamp or environment
read changes.

**n) Antipattern scan, plan pass.**

- A1/H1: SQLAlchemy session use, Celery task options, and direct project helper
  signatures are verified against installed code and existing tests; no new
  external API call is introduced.
- B1/B2/C1/F1: the service bag and forwarding wrappers are deleted; no
  replacement abstraction or compatibility alias is added.
- C2/D2: tests move to approved boundaries and observable outcomes rather than
  gaining a new seam or asserting helper call sequences.
- D1: no test is skipped, weakened, or given wider tolerances.
- E1/E2: only owned files receive focused edits; no wholesale formatting.
- A2-A4, B3, D3, E3, F2, H2-H4: no planned violation.

**o) Ratchet interaction.** `pipeline/tasks.py` retains its existing Ruff
boundary entries because other task families still own those debts.
T-DB-1A adds no Ruff ignore, BLE001 path, type suppression, or test exception.
The repository guardrail gains negative assertions against reintroducing the
summary service bag and facade forwarding.

**p) Dead code and duplication audit.** Delete
`SummaryGenerationTaskServices`, `summary_generation_task_services`,
`run_generate_summary_task_family`, summary-only forwarding functions, their
imports, and summary-only entries in `_TASK_FACADE_DEPENDENCIES`. Reuse all
real domain implementations. Expected production delta is negative.

## 5. Testing

**q) Edge cases, race conditions, and failure scenarios.**

1. Missing catalog returns the existing error without inference or commit.
2. Bad-content classification returns the existing error.
3. Low-signal non-agenda content remains blocked before inference.
4. Empty agenda without items keeps deterministic cached, stale, and forced
   completion behavior.
5. Agenda input not ready returns its existing status without inference.
6. Fresh summary remains cached; stale summary remains visible unless forced.
7. Empty provider response raises the existing retryable runtime error.
8. Ungrounded non-agenda output remains blocked without persistence.
9. Successful agenda and non-agenda summaries persist hashes and commit once.
10. Reindex or embed dispatch failure does not roll back an already committed
    summary and remains visible in result counters.
11. `LocalAIConfigError` returns an error after rollback.
12. SQLAlchemy, runtime, and value failures preserve Celery retry with
    countdown 60.
13. Session closes on success, typed configuration error, and retry.
14. The Celery task remains bound, named
    `pipeline.tasks.generate_summary_task`, and has `max_retries=3`.
15. Lower summary modules never import `pipeline.tasks` or the operation owner.
16. No callable service bag, summary globals lookup, injectable callable, or
    summary facade forwarding survives.
17. Empty catalog content returns `{"error": "No content to summarize"}`
    without inference or persistence.
18. A missing `Document` keeps the current normalized `unknown` document kind
    behavior.

**r) Tests added or updated.**

| Test | Scenarios |
|---|---|
| New `tests/test_summary_generation_operation.py` behavior tests | 1-10, 17-18 |
| Updated provider retry tests | 7, 11-13 |
| Existing agenda payload and format tests | 4-6, 9 |
| Existing summary blocking tests | 3, 8, 10 |
| Updated async/task facade tests | 12-14 |
| Repository structural guardrails | 15-16 |
| Complete Python suite | All observable regression risks |

Tests are written and run red before production edits. Assertions target
returned statuses, stored catalog values, commits, dispatch outcomes, retry
behavior, and import structure, not private helper call order.
The task-contract tests explicitly cover `LocalAIConfigError`, rollback and
close on every exit, retry `countdown=60`, task name, `max_retries=3`, and the
`(catalog_id, force=False)` signature.

**s) Fakes and mocks.** Database tests use the existing session factory or
real test session. Inference tests fake the provider through the established
`pipeline.llm.get_runtime_provider` lookup. Side-effect tests patch
`pipeline.indexer.meilisearch.Client` and its database boundary, then patch
`embed_catalog_task.delay` at the Celery dispatch boundary. Task retry tests
patch the Celery task's `retry` method and session factory. No facade,
re-export, private provider method, or lower-level helper is patched.

**t) Verification rows.** Apply pipeline/task orchestration, inference
provider/policy, and guardrail/tooling rows. Run the complete Python suite
because this is a cross-cutting task-family refactor.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-db-1a-summary-generation-operation
```

Tests-first red evidence:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_summary_generation_operation.py \
  tests/test_repository_guardrails.py::test_summary_generation_uses_direct_operation_boundaries
```

Targeted verification:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_summary_generation_operation.py \
  tests/test_agenda_summary_payload_budget.py \
  tests/test_summary_blocking.py \
  tests/test_task_provider_retry_semantics.py \
  tests/test_tasks_agenda_summary_format.py \
  tests/test_async_flow.py \
  tests/test_task_facade_cleanup.py
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_run_pipeline_orchestration.py \
  tests/test_pipeline_batching.py \
  tests/test_task_metrics.py
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_inference_provider_protocol_contract.py \
  tests/test_provider_error_mapping_retry_vs_fallback.py \
  tests/test_llm_backend_parity_*.py \
  tests/test_runtime_profiles_defaults.py
```

Final verification:

```bash
./.venv/bin/ruff check .
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/pytest -q
git diff --check
git status --short
```

Delivery uses two commits:

1. `docs(remediation): authorize direct summary generation`
2. `refactor(summary): remove facade service injection`

Push `codex/t-db-1a-summary-generation-operation`, open one PR, request Codex
review, and watch required checks until decided.

**v) Rollback.** Revert the T-DB-1A merge commit, then run Ruff, Mypy, the
targeted summary/task suites, repository guardrails, docs links, and the
complete Python suite. No migration reversal, data repair, configuration
restore, or external-state cleanup is required.

**w) Docs synchronization.**

- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`: add T-DB-1A ownership,
  sequencing, state, and acceptance criteria.
- `docs/ADR.md`: record the new direct summary-operation owner and supersede
  earlier summary-specific test-patch facade expectations.
- `ARCHITECTURE.md`, README, API contracts, operations, security, and
  data-governance docs: no update because public task, persistence, and
  operator behavior remain unchanged and no existing map names this internal
  split.

## 7. Delivery Self-Audit

**x) Antipattern scan, diff pass.** Re-run A-F and H. Reject surviving service
bags, `run_generate_summary_task_family`, globals-based summary wiring, imports
from `backlog_maintenance` or `agenda_summary_maintenance`, facade aliases,
injectable callables, conditional forwarding, tests patching obsolete facades,
new ignores, import-time work, or edits outside `files_owned`.

**y) Evidence.** Report the tests-first red result, every command in 6u with
PASS or FAIL, planning-review and pre-commit-review findings, applied fixes,
commit hashes, PR URL, unresolved-thread count, and final CI state. Browser
testing is not applicable because no UI route changes.

**z) Deviations.** Expected deviation report is "None." Any additional file,
Celery task identity/signature change, persistence-order change, new fake
boundary, skipped review, unresolved P1/P2, or unrun required check is a
blocker.
