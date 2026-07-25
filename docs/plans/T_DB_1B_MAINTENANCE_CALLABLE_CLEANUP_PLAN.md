# T-DB-1B: Remove Maintenance Fallback Callable Injection

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: implementation-ready`
`execution: code`

## 1. Context & Alignment

**a) Driver.** T-DB-1 made summary hydration a direct operation, but its
maintenance path still passes generation, deterministic rendering, database
sessions, reindexing, embedding, clock, output, and staged-operation behavior
as callables. Two summary compatibility facades and the staged hydration
entrypoint keep these test seams alive. T-DB-1B removes those seams so each
maintenance operation owns its runtime dependencies while preserving summary
selection, fallback policy, counts, progress, persistence, and side effects.

**b) Canonical documents consulted.**

- `AGENTS.md` `<known_antipatterns>`, `<workflow_contract>`,
  `<verification_matrix>`, and `<status_reporting_contract>` prohibit
  patchability parameters, facade re-exports, duplicate implementations, and
  unverified completion claims.
- `docs/TESTING.MD` "Approved fake boundaries" and "Patch-target rules"
  require tests to substitute database, inference, Meilisearch, Celery, clock,
  and filesystem boundaries rather than maintenance operations.
- `docs/ENGINEERING_GUARDRAILS.md` keeps Ruff and structural guardrails
  authoritative.
- `docs/ADR.md` "Test patch points are not a public API" authorizes deleting
  compatibility seams when their callers and tests move in the same change.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` assigns this work to DEDUP-B
  after T-DB-1.
- `docs/reviews/architecture-review-2026-07-19.html` identifies facade
  indirection and callable dependency bags as architecture debt.

**c) Remediation alignment.** T-DB-1B remains in DEDUP-B. Expand its exclusive
`files_owned` set before implementation to:

- `docs/plans/T_DB_1B_MAINTENANCE_CALLABLE_CLEANUP_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `docs/ADR.md`
- `ARCHITECTURE.md` (agenda-summary maintenance owner map only)
- `docs/PIPELINE.md` (agenda-summary maintenance owner map only)
- `pipeline/agenda_summary_batch.py`
- `pipeline/agenda_summary_callbacks.py` (delete)
- `pipeline/agenda_summary_fallback.py`
- `pipeline/agenda_summary_maintenance.py` (delete)
- `pipeline/agenda_summary_side_effects.py` (new)
- `pipeline/backlog_maintenance.py`
- `pipeline/non_agenda_summary_fallback.py`
- `pipeline/summary_backfill_logging.py`
- `pipeline/summary_backfill_progress.py`
- `pipeline/summary_backfill_runner.py`
- `scripts/hydrate_repaired_city_catalogs.py`
- `scripts/hydration_repaired_runner.py`
- `scripts/hydration_repaired_summary.py`
- `scripts/staged_hydrate_cities.py`
- `scripts/staged_hydration_output.py`
- `scripts/staged_hydration_runner.py`
- `scripts/staged_hydration_segment.py`
- `tests/test_backlog_maintenance_laserfiche_guard.py`
- `tests/test_hydrate_repaired_city_catalogs.py`
- `tests/test_pipeline_batching.py`
- `tests/test_repository_guardrails.py`
- `tests/test_staged_hydrate_cities.py`
- `tests/test_tasks_agenda_summary_format.py`

No other tracked file may change.

**d) Decision-gate check.** G3 is satisfied and authorizes removal of
test-only patch seams. G5 is accepted but migration work is unaffected. G1,
G2, and G4 are unaffected. No open gate blocks T-DB-1B.

## 2. Design

**e) Step-by-step approach.**

1. Register this Full plan and exact ownership before implementation.
2. Add failing behavior and structural tests before production edits.
3. Make `pipeline/agenda_summary_fallback.py` the maintenance summary routing
   owner:
   - `summarize_catalog_with_maintenance_mode(catalog_id, *, force=False,
     summary_fallback_mode="none")` resolves document kind directly.
   - Agenda documents call deterministic agenda persistence directly.
   - Other documents call direct summary generation while capturing provider
     failure events, then invoke deterministic minutes fallback only under the
     existing policy.
   - The module owns generation session rollback and closure and retains the
     existing `LocalAIConfigError` payload and logging behavior.
4. Delete `pipeline/agenda_summary_maintenance.py`. Move callers to
   `agenda_summary_batch`, `agenda_summary_fallback`,
   `agenda_summary_inputs`, `agenda_summary_contracts`, and
   `document_kinds`.
5. Make `pipeline/agenda_summary_batch.py` own its database session and invoke
   post-commit side effects directly. Replace `agenda_summary_callbacks.py`
   with `agenda_summary_side_effects.py`; the replacement has one
   responsibility: time, normalize, and report direct
   `indexer.reindex_catalogs` and
   `summary_backfill_dispatch.enqueue_embed_catalogs` results. This keeps the
   batch module under its 300-line guardrail without retaining callback
   parameters.
6. Make `pipeline/non_agenda_summary_fallback.py` own its database session,
   targeted reindex, and embed dispatch. Preserve current best-effort
   exception classification and result counters.
7. Remove summary constants, builders, and fallback wrappers from
   `pipeline/backlog_maintenance.py`. Keep only its established agenda
   segmentation maintenance surface.
8. Update `summary_backfill_runner.py` to call the direct batch and fallback
   operations. Delete its duplicate generation and non-agenda fallback
   wrappers and their dependency imports.
9. Move summary timing imports in `summary_backfill_progress.py` and
   `summary_backfill_logging.py` directly to
   `agenda_summary_contracts`.
10. Make staged hydration direct:
    - `staged_hydration_runner.py` directly owns city iteration, snapshots,
      segment operation calls, summary backfill calls, count merging, output,
      and sleeping.
    - `staged_hydration_segment.py` calls the output boundary directly instead
      of accepting an output callable.
    - `staged_hydration_output.py` calls `hydration_output.emit_progress`
      directly.
    - `staged_hydrate_cities.py` becomes parser plus direct runner invocation;
      delete forwarding wrappers.
11. Make repaired summary hydration direct:
    - `hydration_repaired_summary.py` directly owns summary selection,
      maintenance routing, timeout context, and per-catalog exception
      conversion.
    - `hydration_repaired_runner.py` imports the repaired summary operation
      directly instead of accepting `run_summary_city`.
    - `hydrate_repaired_city_catalogs.py` stops importing summary behavior
      through `backlog_maintenance` and deletes summary-only forwarding
      wrappers.
    - General extract/segment runner injection outside the summary path is
      not changed by this task.
12. Repoint tests to direct operations and approved boundaries. Use the shared
    test database, fake inference provider, Meilisearch client construction,
    Celery task dispatch, and implementation clock lookup. Do not create a
    replacement operation patch seam.
13. Add an AST guardrail proving the deleted modules stay absent, summary
    behavior is not imported from `backlog_maintenance`, and the owned
    maintenance/staged files expose no dependency parameter ending in
    `_callable`, no `session_factory`, and no `time_module`.
14. Add a dated ADR entry superseding prior compatibility-facade decisions
    only for maintenance summary and staged hydration.
15. Update the canonical architecture and pipeline owner maps so they name the
    direct maintenance router, deterministic writers, and side-effect owner
    rather than the deleted facade and callback adapter.
16. Run required verification, simplify the diff, obtain fresh subagent
    pre-commit review, fix every eligible P1/P2, and deliver one PR.

Import direction:

```text
summary_backfill_runner and repaired/staged operators
  -> agenda_summary_fallback
       -> task_summary_generation
       -> agenda_summary_batch
       -> non_agenda_summary_fallback
       -> approved runtime boundaries

staged_hydrate_cities
  -> staged_hydration_runner
       -> staged_hydration_segment
       -> summary_backfill_runner
       -> hydration diagnostics/output
```

Lower summary modules never import deleted facades. Existing staged
segmentation delegation through `segment_city_corpus` is unchanged; replacing
that separate operator family is outside T-DB-1B.

**f) Reuse audit.** Reuse the existing agenda batch, summary generation,
provider-event capture, non-agenda fallback, backfill runner, staged runner,
diagnostic snapshot, count, and output implementations. The direct operations
already exist; this task removes dependency threading and forwarding layers
rather than adding parallel implementations.

Replacing `agenda_summary_callbacks.py` is viable because only
`agenda_summary_batch.py` imports it. The focused replacement is required
because the batch is already near its 300-line guardrail. No manager,
registry, factory, base class, or general utility module is needed.

Rejected alternatives:

- Keep compatibility re-exports: rejected because all tracked callers can
  move atomically and dead patch targets would remain architectural debt.
- Add a dependency container: rejected because it replaces explicit callable
  injection with more machinery and preserves the same ownership ambiguity.
- Call the registered Celery summary task from maintenance code: rejected
  because synchronous maintenance must not depend on task retry semantics.
- Remove repaired extract/segment injection too: rejected because it is a
  separate operation family outside this summary/staged task.

**g) Data contracts.** Existing dictionary payloads remain the maintenance
contract. Summary statuses, completion modes, count keys, timing keys,
provider-failure payloads, staged chunk payloads, progress text, JSON output,
and CLI flags remain unchanged. No new data contract is introduced.

**h) Schema/migration impact.** None. No table, column, migration, stored
value, timestamp, transaction ordering, or Alembic state changes.

## 3. Security & Data Governance

**i) Security-sensitive paths.** None under `AGENTS.md`. No authentication,
proxy, container, credential, CORS, or network exposure changes.

**j) Secrets.** None.

**k) Person data.** No person-level data is created, linked, aggregated, or
exposed. G4 is unaffected.

**l) Untrusted input.** Existing catalog content and provider responses remain
validated by summary generation, content-quality, and fallback modules. No new
parser or rendering boundary is added.

## 4. Code Health

**m) GED conformance sweep.** Public maintenance summary routing has three
scalar inputs. Direct batch and fallback operations accept domain inputs, not
runtime dependencies. Staged helpers receive data and CLI options only.
Existing progress callbacks remain only where progress observation is the
public contract, not as service injection. No environment read, naive
timestamp, broad exception boundary, or runtime default is added.

`hydration_repaired_summary.py` already converts per-catalog failures to an
error payload so a city run continues. The catch remains at that operator
boundary and preserves the invariant that one bad catalog does not abort the
bounded repair batch.

**n) Antipattern scan, plan pass.**

- A1/H1: no new external API or dependency call is planned; installed
  SQLAlchemy, Celery, Meilisearch, and pytest behavior remains unchanged.
- B1/B2/C1: delete facades and callback helpers; add no compatibility layer or
  dependency container.
- C2: tests move to approved runtime boundaries instead of preserving patch
  targets.
- D1-D3: no skip, tolerance change, weakened assertion, private call-order
  assertion, or mock of the unit under test is planned.
- E1-E3: only owned files change; historical ADR text is superseded rather
  than rewritten.
- F1/F2: one maintenance router, one batch writer, and one staged runner
  remain; duplicate wrappers are deleted.
- A2-A4, B3, H2-H4: no violations planned.

**o) Ratchet interaction.** No Ruff selector, BLE001 boundary, exclusion,
coverage threshold, formatter scope, or Mypy scope changes. Structural
guardrails become stricter by rejecting the deleted facades and dependency
parameters in the owned operation family.

**p) Dead code and duplication audit.** Delete two compatibility modules,
summary exports from `backlog_maintenance`, batch callback adapters, runner
wrappers, entrypoint wrappers, callback parameters, and obsolete imports.
Reuse all domain logic and runtime boundaries. Expected production delta is
negative.

## 5. Testing

**q) Edge cases and failure scenarios.**

1. Agenda documents bypass the provider and complete deterministically.
2. Non-agenda provider success records `completion_mode=llm`.
3. Empty response, timeout, and unavailable failures use deterministic
   fallback only when enabled.
4. Disabled fallback leaves provider failure as an error.
5. Low-signal content remains blocked and never falls back.
6. Missing catalog/document and unsupported document kind retain current
   errors.
7. `LocalAIConfigError` logs catalog context, rolls back, closes the session,
   and does not trigger deterministic fallback.
8. SQLAlchemy/runtime/value failures retain current rollback and propagation
   behavior.
9. Agenda batch persists once, reindexes changed catalogs, and enqueues one
   embed per changed catalog.
10. Agenda empty and failed segmentation classifications remain unchanged.
11. Non-agenda fallback persists freshness hashes and preserves best-effort
    reindex/embed counters on success and failure.
12. Empty staged city selection returns the current payload.
13. Segment-first, summary-only, max-chunk, resume, repeat, sleep, and
    idle-stop behavior remains unchanged.
14. Human progress and JSON output remain unchanged.
15. Repaired city summary continues after one catalog error and retains
    completion-mode counts.
16. Deleted facades and callback modules cannot return through imports.
17. Owned maintenance/staged production signatures contain no dependency
    callable, session factory, or clock module parameters.
18. Lower summary modules do not import deleted facades.

**r) Tests added or updated.**

- `tests/test_pipeline_batching.py`: scenarios 1-11 using the database,
  inference, Meilisearch, and Celery boundaries.
- `tests/test_tasks_agenda_summary_format.py`: scenarios 1-8 through direct
  maintenance routing.
- `tests/test_backlog_maintenance_laserfiche_guard.py`: scenarios 1, 6,
  9-11, and facade deletion.
- `tests/test_staged_hydrate_cities.py`: scenarios 12-14 with real runner
  operations and approved database, inference, dispatch, filesystem, and
  clock boundaries. Positive segment/multi-chunk tests use a temporary
  file-backed SQLite database and the real child process so parent and worker
  observe the same committed state. They do not patch the staged segment
  operation or subprocess launcher.
- `tests/test_hydrate_repaired_city_catalogs.py`: scenario 15 without
  summary-operation injection.
- `tests/test_repository_guardrails.py`: scenarios 16-18.

No orphan test is planned. General repaired extract/segment injectable
dependencies remain visible debt outside this task rather than being hidden by
new seams.

**s) Fakes and mocks.** Database tests use the existing shared SQLite
sessionmaker through `pipeline.db_session` or `pipeline.task_runtime`.
Inference tests fake `pipeline.llm.get_runtime_provider`. Meilisearch tests
patch client construction in `pipeline.indexer`. Celery tests patch
`embed_catalog_task.delay`. Staged segmentation integration tests use a real
child process and a temporary file-backed SQLite database created under
`tmp_path`; no new fake boundary is added. Clock tests patch `time.sleep`
where the staged runner looks it up. No facade, re-export, or operation under
test is patched.

**t) Verification rows.** Apply pipeline/task orchestration, inference
provider, guardrail/tooling, and docs rows. Run the complete Python suite
before handoff. Python Guardrails and coverage remain the authoritative merge
gate.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-db-1b-remove-maintenance-callables
```

Tests-first red:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_backlog_maintenance_laserfiche_guard.py \
  tests/test_pipeline_batching.py \
  tests/test_staged_hydrate_cities.py \
  tests/test_hydrate_repaired_city_catalogs.py \
  tests/test_repository_guardrails.py
```

Targeted verification:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_backlog_maintenance_laserfiche_guard.py \
  tests/test_pipeline_batching.py \
  tests/test_staged_hydrate_cities.py \
  tests/test_hydrate_repaired_city_catalogs.py \
  tests/test_tasks_agenda_summary_format.py \
  tests/test_run_pipeline_orchestration.py \
  tests/test_provider_error_mapping_retry_vs_fallback.py
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
  tests/test_llm_backend_parity_*.py \
  tests/test_runtime_profiles_defaults.py
PYTHONPATH=. .venv/bin/pytest -q
git diff --check
git status --short
```

Delivery uses focused commits:

1. `docs(remediation): authorize T-DB-1B callable cleanup`
2. `refactor(maintenance): make repaired summary hydration direct`
3. `refactor(maintenance): make staged hydration operations direct`
4. `refactor(maintenance): make summary fallback operations direct`
5. `fix(maintenance): close direct hydration contract gaps`
6. `test(maintenance): assert observable boundary effects`

Push `codex/t-db-1b-remove-maintenance-callables`, open one PR titled
`T-DB-1B: Remove maintenance fallback callable injection`, request Codex
review, and watch CI to a decided state.

**v) Rollback.** Revert the T-DB-1B merge commit and rerun Ruff, Mypy,
targeted tests, docs links, and the complete suite. No migration, data repair,
environment rollback, or external-state cleanup is required. Rollback
knowingly restores compatibility facades and callable injection.

**w) Docs synchronization.**

- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`: exact ownership, active
  status, acceptance, verification, and changelog.
- New T-DB-1B implementation plan.
- `docs/ADR.md`: accepted direct maintenance/staged operation ownership and
  superseded facade decisions.
- `ARCHITECTURE.md` and `docs/PIPELINE.md`: replace deleted maintenance module
  names in their active owner maps.
- README, historical architecture review, operations, performance, testing
  policy, security, data governance, and API contracts: no changes.

## 7. Delivery Self-Audit

**x) Antipattern scan, diff pass.** Re-run A-F and H. Reject compatibility
aliases, dependency containers, retained injectable callables, operation
patches in tests, lower-to-facade imports, unrelated formatting, weakened
assertions, added broad exceptions, type suppression, or edits outside the
owned files.

**y) Evidence.** Report PASS/FAIL for every command in section 6u, including
tests-first red evidence, planning-review findings, simplification findings,
pre-commit subagent findings, applied fixes, commit hashes, PR URL, unresolved
thread count, and final CI state. Mark anything unrun `NOT VERIFIED`.

**z) Deviations.** The authorized ledger deviation is expansion from the
original nine named files plus unspecified tests to the exact twenty-eight-file
set above. The operator approved the final two-file expansion after independent
review found the canonical owner maps still named the deleted modules. T-DB-1B
also receives a temporary exclusive coordination grant for these files over
the DEDUP-B, GOV, and affected PLAT documentation subsections. Implementation
landed as six focused commits rather than the initially proposed two because
parallel work separated repaired hydration, staged hydration, fallback
ownership, final contract closure, and the remote-review test correction. No
history was rewritten. Any other changed file, runtime default change, fallback-policy
change, timeout-policy change, soak-comparability change, skipped review,
unresolved P1/P2, or unrun required check is a blocker.
