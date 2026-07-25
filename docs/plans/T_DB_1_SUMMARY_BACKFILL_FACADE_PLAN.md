# T-DB-1: Collapse the Summary Backfill Facade

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: implementation-ready`
`execution: code`

## 1. Context & Alignment

**a) Driver.** Summary hydration currently crosses four layers before reaching
its runner: callers import `pipeline.tasks`, which passes `globals()` through
`task_facade_helpers`, which calls a duplicate `summary_backfill` facade, which
finally reaches `summary_backfill_runner`. The chain exists to preserve patch
targets, duplicates a fifteen-parameter signature, and injects eight runtime
dependencies. T-DB-1 makes the runner the single backfill operation while
preserving eligibility, deterministic agenda handling, non-agenda fallback,
progress, counts, and operator interfaces.

**b) Canonical documents consulted.**

- `AGENTS.md` `<known_antipatterns>`, `<workflow_contract>`, and
  `<verification_matrix>` prohibit globals-based service lookup,
  test-seam wrappers, duplicated implementations, and injectable callables.
- `docs/TESTING.MD` "Approved fake boundaries" and "Patch-target rules"
  require tests to use database, inference, Meilisearch, and Celery boundaries
  rather than facade exports.
- `docs/ENGINEERING_GUARDRAILS.md` keeps Ruff and structural guardrails
  authoritative.
- `docs/ADR.md` "Test patch points are not a public API" authorizes deleting
  compatibility seams after callers and tests move.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` assigns this work to DEDUP-B
  after T-DB-1A.
- `docs/reviews/architecture-review-2026-07-19.html` identifies facade
  machinery and callable dependency bags as architecture debt.

**c) Remediation alignment.** T-DB-1 remains in DEDUP-B. Expand its exclusive
`files_owned` set before implementation to:

- `docs/plans/T_DB_1_SUMMARY_BACKFILL_FACADE_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `docs/ADR.md`
- `pipeline/summary_backfill.py` (delete)
- `pipeline/summary_backfill_dispatch.py`
- `pipeline/summary_backfill_logging.py`
- `pipeline/summary_backfill_progress.py`
- `pipeline/summary_backfill_queries.py`
- `pipeline/summary_backfill_runner.py`
- `pipeline/task_facade_helpers.py`
- `pipeline/tasks.py`
- `pipeline/run_pipeline.py`
- `scripts/backfill_summaries.py`
- `scripts/staged_hydrate_cities.py`
- `scripts/profile_pipeline_selection.py`
- `tests/test_backfill_summaries.py`
- `tests/test_pipeline_batching.py`
- `tests/test_run_pipeline_orchestration.py`
- `tests/test_staged_hydrate_cities.py`
- `tests/test_tasks_agenda_summary_format.py`
- `tests/test_profile_pipeline_cli.py`
- `tests/test_repository_guardrails.py`
- `tests/test_task_facade_cleanup.py`

No other tracked file may change.

**d) Decision-gate check.** G3 is satisfied and authorizes removal of test-only
patch seams. G1, G2, G4, and G5 are unaffected. No open gate blocks T-DB-1.
The separate callable-injection chains in maintenance fallback and staged
hydration are outside this operation and become T-DB-1B; T-DB-1 must not edit
around that debt by assumption.

## 2. Design

**e) Step-by-step approach.**

1. Register this Full plan, expanded ownership, and T-DB-1B follow-up before
   implementation.
2. Add failing behavior and structural tests before production edits.
3. Delete `pipeline/summary_backfill.py`. No compatibility re-export remains
   because all tracked callers move in the same change.
4. Make `pipeline/summary_backfill_runner.py` the canonical operation. Keep
   only seven public options: `force`, `limit`, `city`,
   `summary_timeout_seconds`, `summary_fallback_mode`, `progress_callback`,
   and `progress_every`.
5. Delete dependency-callable parameters from the public runner and its
   private helpers. Use direct module imports for selection, kind mapping,
   deterministic agenda batching, fallback orchestration, reindexing, and
   embed dispatch.
6. Add one data-only loop context in the runner so private functions receive
   coherent backfill state rather than another long parameter list. It has no
   behavior, registry, factory, or compatibility role.
7. Add one private maintenance generation function in the runner. It opens a
   `task_runtime.task_session`, calls
   `task_summary_generation.generate_catalog_summary`, and always closes the
   session. `LocalAIConfigError` logs at critical level with `catalog_id`,
   rolls back, and returns the existing error payload. SQLAlchemy, runtime, and
   value failures roll back and re-raise so existing fallback/error handling
   remains authoritative. SQL failures still abort the backfill rather than
   being swallowed.
8. Keep downstream maintenance-fallback callables unchanged. They are
   pre-existing APIs outside this task; T-DB-1 passes concrete internal
   operations to them but exposes no injectable dependency itself. T-DB-1B
   will remove those remaining chains.
9. Remove selector, kind-map, embed, and backfill wrappers from
   `task_facade_helpers.py` and `tasks.py`. Remove imports used only by those
   wrappers. Keep Celery task entrypoints unchanged.
10. Update runtime callers to import their owner directly:
    - `pipeline/run_pipeline.py`,
      `scripts/backfill_summaries.py`, and
      `scripts/staged_hydrate_cities.py` import the runner.
    - `scripts/profile_pipeline_selection.py` imports the selector from
      `summary_backfill_queries`.
11. Repoint tests to implementation modules and approved boundaries. Preserve
    CLI and staged-runner observable contracts without creating replacement
    wrappers.
12. Add an AST guardrail proving tracked callers do not import summary
    hydration through `pipeline.tasks`, lower backfill modules do not import
    facades, and no backfill runner parameter name ends in `_callable`.
13. Update the ADR with a dated superseding decision. Historical entries stay
    intact but are no longer current policy.
14. Run required verification, simplify the diff, obtain fresh subagent
    pre-commit review, fix every eligible P1/P2, and deliver one PR.

Import direction:

```text
pipeline/run_pipeline.py and operator scripts
  -> pipeline/summary_backfill_runner.py
       -> summary_backfill_queries/progress/logging/dispatch
       -> task_summary_generation.py
       -> existing maintenance fallback modules

pipeline/tasks.py
  -> Celery task operations only
```

No backfill module imports `pipeline.tasks`, `task_facade_helpers`, or the
deleted facade.

**f) Reuse audit.** Reuse the existing runner, query, progress, logging,
dispatch, summary-generation, and fallback implementations. The equivalent
operation already exists in `summary_backfill_runner`; T-DB-1 removes three
forwarding layers rather than adding a parallel implementation. A small
data-only loop context stays in the runner because no existing contract
matches its internal state.

Rejected alternatives:

- Keep a one-line compatibility facade: rejected because all tracked callers
  can move atomically and an unused re-export would retain dead architecture.
- Import the Celery task and call `.run`: rejected because maintenance work is
  synchronous and must not depend on a task facade or Celery retry sentinel.
- Remove every fallback and staged-hydration callable in this PR: rejected
  because that crosses additional owned families and hides a second
  architecture change inside facade collapse.

**g) Data contracts.** Public input and output remain dictionaries and scalar
options because that is the established maintenance API. Internal loop state
uses one typed frozen dataclass. Progress payload keys, count keys, completion
modes, and CLI JSON remain unchanged.

**h) Schema/migration impact.** None. No database declaration, migration,
stored value, timestamp, or commit ordering changes.

## 3. Security & Data Governance

**i) Security-sensitive paths.** None under `AGENTS.md`. No auth, proxy,
container, credential, CORS, or network boundary changes.

**j) Secrets.** None.

**k) Person data.** No person-level data is created, linked, aggregated, or
exposed. G4 is unaffected.

**l) Untrusted input.** Existing catalog content and provider responses remain
validated by summary generation and fallback modules. This task adds no parser
or rendering boundary.

## 4. Code Health

**m) GED conformance sweep.** The public function has seven parameters. The
loop context prevents long private signatures. The maintenance generation
helper has one responsibility. It converts only `LocalAIConfigError` to the
existing typed payload; every other caught failure rolls back and re-raises.
No environment read, timestamp, broad exception, or runtime default is added.

**n) Antipattern scan, plan pass.**

- A1/H1: no new external API or library call is planned; installed SQLAlchemy,
  Celery, and pytest usage remains unchanged.
- B1: one data-only context is required to replace a ten-parameter helper; no
  manager, registry, factory, or utility module is added.
- B2/C1: the facade and wrappers are deleted, not retained as aliases.
- C2: tests move to implementation modules and approved runtime boundaries.
- D1-D3: no skip, tolerance change, call-sequence assertion, or weakened
  behavior check is planned.
- E1-E3: only owned files change; historical ADR text is superseded, not
  rewritten.
- F1/F2: one runner remains; no copied operation or second shared home.
- A2-A4, B3, H2-H4: no violations planned.

**o) Ratchet interaction.** No Ruff selector, BLE001 boundary, exclusion,
coverage threshold, or Mypy scope changes. Structural guardrails become
stricter by rejecting facade imports and callable parameters in the backfill
runner.

**p) Dead code and duplication audit.** Delete `summary_backfill.py`, four
task-facade wrappers, the globals mapping, duplicate signature, conditional
splat forwarding, and obsolete imports. Reuse all lower implementations.
Expected production delta is negative.

## 5. Testing

**q) Edge cases and failure scenarios.**

1. Empty selection returns the full zero-count payload and emits the existing
   empty start/finish progress events.
2. Limit, city, stale-summary, manifest, and agenda eligibility selection stay
   unchanged.
3. Agenda documents run in the deterministic batch before the per-catalog
   loop.
4. `agenda_html` and empty agenda outcomes retain current classifications.
5. Non-agenda LLM success records `completion_mode=llm`.
6. Empty response, timeout, and unavailable provider failures trigger
   deterministic fallback only when enabled.
7. Disabled fallback leaves provider failures as errors.
8. Low-signal content remains blocked and never falls back.
9. Unknown or missing document behavior remains unchanged.
10. Selection, kind-map, and generation sessions always close.
11. Generation failure rolls back before propagating to fallback/error
    handling.
12. SQLAlchemy failure aborts the run and is not swallowed.
13. `LocalAIConfigError` logs at critical level with the catalog id, rolls
    back, closes the session, and returns the current error payload without
    deterministic fallback.
14. Reindex/embed failures retain current best-effort counts.
15. Progress cadence and final event payload stay unchanged.
16. Canonical pipeline still runs segmentation before summary hydration with
    maintenance timeout and deterministic fallback.
17. Backfill CLI retains heartbeat, artifacts, JSON, error, and exit behavior.
18. Staged hydration retains city/chunk/repeat/idle behavior.
19. Profiling triage selection still includes summary candidates.
20. No tracked caller imports the backfill operation from `pipeline.tasks`.
21. No runner dependency parameter ends in `_callable`; no conditional splat
    forwarding or deleted facade import remains.

**r) Tests added or updated.**

- `tests/test_pipeline_batching.py`: scenarios 1-15 using the database,
  inference-provider, Meilisearch, and Celery boundaries.
- `tests/test_tasks_agenda_summary_format.py`: scenarios 5-9 without task
  facade patches.
- `tests/test_run_pipeline_orchestration.py`: scenario 16 and direct runner
  import.
- `tests/test_backfill_summaries.py`: scenario 17.
- `tests/test_staged_hydrate_cities.py`: scenario 18.
- `tests/test_profile_pipeline_cli.py`: scenario 19 if the direct selector
  import changes its contract coverage.
- `tests/test_repository_guardrails.py`: scenarios 20-21.
- `tests/test_task_facade_cleanup.py`: assert removed task/helper exports do
  not return.

No orphan test is planned. T-DB-1B will own tests for downstream fallback and
staged-hydration callable removal; T-DB-1 does not weaken them.

**s) Fakes and mocks.** Database sessions use existing SQLite fixtures or
patch the session factory at the implementation lookup. Inference uses a fake
provider through `pipeline.llm.get_runtime_provider`. Meilisearch patches the
client where `pipeline.indexer` constructs it. Celery patches
`embed_catalog_task.delay`. CLI and staged-hydration tests invoke the real
backfill runner and control it only through those approved boundaries; they
must not patch `run_summary_hydration_backfill` in a caller module or the
runner module. Existing staged-runner callable injection is covered separately
by T-DB-1B and is not used as a new T-DB-1 test seam.

**t) Verification rows.** Apply pipeline/task orchestration, inference
provider, guardrail/tooling, and docs rows. Run the complete Python suite
before handoff and rely on Python Guardrails as the authoritative merge gate.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-db-1-collapse-summary-backfill-facade
```

Tests-first red:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_pipeline_batching.py \
  tests/test_run_pipeline_orchestration.py \
  tests/test_repository_guardrails.py \
  tests/test_task_facade_cleanup.py
```

Targeted verification:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_pipeline_batching.py \
  tests/test_run_pipeline_orchestration.py \
  tests/test_staged_hydrate_cities.py \
  tests/test_tasks_agenda_summary_format.py \
  tests/test_backfill_summaries.py \
  tests/test_profile_pipeline_cli.py \
  tests/test_task_facade_cleanup.py
```

Final verification:

```bash
./.venv/bin/ruff check .
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_run_pipeline_orchestration.py \
  tests/test_pipeline_batching.py \
  tests/test_task_metrics.py
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_inference_provider_protocol_contract.py \
  tests/test_provider_error_mapping_retry_vs_fallback.py \
  tests/test_llm_backend_parity_*.py
PYTHONPATH=. .venv/bin/pytest -q
git diff --check
git status --short
```

Delivery uses two commits:

1. `docs(remediation): authorize T-DB-1 facade collapse`
2. `refactor(backfill): remove summary facade injection`

Push `codex/t-db-1-collapse-summary-backfill-facade`, open one PR, request a
fresh Codex review, and watch CI until decided.

**v) Rollback.** Revert the T-DB-1 merge commit, rerun the same Ruff, Mypy,
targeted, docs-link, and full-suite commands. No migration, data repair,
configuration restoration, or external-state cleanup is required.

**w) Docs synchronization.**

- `docs/ADR.md`: add a dated decision that supersedes current compatibility
  facade claims and identifies the runner as owner.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`: expanded ownership,
  implementation-ready plan, in-progress status, and T-DB-1B follow-up.
- New T-DB-1 Full plan.
- README, architecture map, operations, pipeline, testing, security, and data
  governance docs: no update because their current commands and behavior do
  not name the removed facade.

## 7. Delivery Self-Audit

**x) Antipattern scan, diff pass.** Re-run A-F and H. Reject compatibility
re-exports, facade imports, callable dependency parameters, conditional splat
forwarding, new patch seams, duplicated selection or fallback logic,
unapproved mocks, unrelated formatting, and type suppression.

**y) Evidence.** Report tests-first red evidence, every command from 6u,
planning-review and pre-commit-review findings, applied fixes, exact pass/fail
counts, commits, PR URL, unresolved-thread count, and CI state. Mark anything
unrun as `NOT VERIFIED`.

**z) Deviations.** Authorized ledger changes are expanded ownership, direct
caller migration, facade deletion, and T-DB-1B registration. Any other changed
path, downstream fallback rewrite, staged-runner callable rewrite, runtime
default, policy change, skipped review, unresolved P1/P2, or unrun required
check is a blocker.
