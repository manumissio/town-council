# T-FE-1A: Test and Correct the ResultCard Polling Lifecycle

`artifact_contract: ce-unified-plan/v1`  
`artifact_readiness: implementation-ready`  
`execution: code`

## 1. Context & Alignment

**a) Driver.** T-FE-1's required audit found that `ResultCard` already has one
shared polling implementation, so the proposed cross-action consolidation has
no duplicate implementation to delete. The audit did find a cancellation race:
when unmount cleanup stops a poll while its fetch is pending, the resumed poll
can still dispatch completion or error state. T-FE-1A closes that correctness
gap and replaces source-token assertions with behavior tests before the
remediation program is declared complete.

**b) Canonical documents consulted.**

- `AGENTS.md`: frontend behavior changes require the frontend verification
  rows, observable tests, exact reporting, and no test-only seams.
- `docs/TESTING.MD`: tests may substitute the outbound HTTP and clock
  boundaries, but production code must not accept injected test callables.
- `docs/ENGINEERING_GUARDRAILS.md`: existing lint, formatter, typing, and
  complete-suite gates remain unchanged.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`: T-FE-1 requires behavior
  tests before implementation and permits consolidation only for proven shared
  behavior.
- `docs/reviews/architecture-review-2026-07-19.html`: the historical finding
  concerns mixed responsibilities in `ResultCard`, not multiple polling
  engines.

**c) Remediation alignment.** T-FE-1's audit is complete with no proven
duplicate poller. T-FE-1A is the frontend lane's narrow corrective task and
owns exactly:

- `docs/plans/T_FE_1A_TASK_POLLING_LIFECYCLE_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `frontend/components/ResultCard.js`
- `frontend/components/__tests__/ResultCard.polling-contract.test.js`
- `frontend/components/__tests__/ResultCard.people-projection.test.js`
- `frontend/lib/api.js`
- `frontend/lib/taskPolling.js` (new)
- `tests/test_resultcard_agenda_status_refresh.py`

**d) Decision gates.** No G1-G5 gate applies. The operator approved the
behavior-test design and narrowed task boundary. Runtime defaults, APIs, soak
comparability, and person-data policy remain unchanged.

## 2. Design

**e) Step-by-step approach.**

1. Register T-FE-1A and record the completed T-FE-1 audit before code edits.
2. Replace the source-regex polling test with failing `node:test` behavior
   tests for completion, failure, timeout, and cancellation during a pending
   fetch.
3. Move the existing JSON response reader from `ResultCard.js` to the existing
   API helper module so polling and mutation requests keep one response-error
   contract.
4. Move the existing polling lifecycle to `frontend/lib/taskPolling.js` as its
   sole production owner. It owns fetching task status, bounded backoff,
   timeout signaling, failure dispatch, and cancellation.
5. Recheck cancellation after every awaited provider boundary and before any
   callback. Pass the lifecycle's standard `AbortSignal` to completion work so
   asynchronous settlement also stops before later component state updates.
6. Keep summary, topic, agenda, and extraction settlement in `ResultCard`.
   Agenda alone converts `result.items` to its list; the other actions retain
   their existing result interpretation.
7. Delete the superseded poller, constants, and response-reader copies from
   `ResultCard.js`; do not retain wrappers or re-exports.
8. Run frontend and repository verification, simplify the diff, obtain an
   independent pre-commit review, apply eligible findings, then commit, push,
   open a PR, and watch CI.

New module responsibility: `frontend/lib/taskPolling.js` owns only the shared
background-task polling lifecycle. Import direction is component to library;
the library never imports the component.

**f) Reuse audit.** Reuse `buildApiUrl`, the existing response parser, the
current backoff constants, and `ResultCard`'s poll-stop registry. No generic
action executor, framework, test adapter, compatibility wrapper, or duplicate
poller is added. The implementation in `ResultCard.js` is deleted when the new
owner lands.

**g) Data contracts.** The polling owner accepts a task ID plus completion and
failure callbacks and passes through the raw task `result`. These callbacks are
the production component boundary, not injected test dependencies. Task payload
interpretation remains action-local. No public API or stored contract changes.

**h) Schema and migrations.** None.

## 3. Security & Data Governance

**i) Security boundary.** No `AGENTS.md` security-sensitive path changes.
Task status requests continue through `buildApiUrl`; no credential, origin, or
proxy behavior changes.

**j) Secrets.** None.

**k) Person data.** None. Roster-gated person policy remains unchanged.

**l) Untrusted input.** Task-status HTTP responses remain untrusted and pass
through the existing JSON/error parser before status interpretation. Malformed
successful JSON retains the current empty-object behavior; non-successful
responses raise the current contextual error.

## 4. Code Health

**m) Conformance.** New functions have one lifecycle responsibility, no more
than three parameters, bounded nesting, domain names, and named polling
constants. Errors either dispatch the existing failure outcome or are ignored
only after explicit cancellation, where the invariant is that an unmounted
component receives no state callback. No timestamp or environment changes.

**n) Antipattern scan, plan pass.**

- A1/H1: Node 26.5.1 is installed. Context7 verified `node:test` context mock
  methods and automatic timer restoration against Node 25.9 documentation;
  local execution is authoritative for Node 26.
- B1/F1: one small lifecycle owner replaces the component implementation; no
  generic executor or second helper family is introduced.
- B2/C1/C2: the superseded component poller is deleted, with no wrapper,
  re-export, or test-only injectable.
- D1-D3: regex assertions are replaced by observable callback, request,
  timeout, and cancellation outcomes.
- E1-E3: only the eight owned paths change; the historical review is not edited.
- A2-A4, B3, F2, H2-H4: no violations planned.

**o) Ratchet interaction.** No Ruff selector, exception, coverage threshold,
or guardrail scope changes.

**p) Dead code and duplication audit.** Delete the polling constants,
`pollTaskStatus`, and local response helpers from `ResultCard.js`, plus the
source-regex test setup. Reuse the existing API helper module and poll-stop
registry. Expected production delta is roughly neutral because logic moves to
its single owner; component size decreases.

## 5. Testing

**q) Edge and failure scenarios.**

1. A pending task progresses to complete and returns the raw result once.
2. Agenda result interpretation remains action-specific in `ResultCard`.
3. A failed task dispatches its error once and stops.
4. An unsuccessful HTTP response dispatches a contextual error once, using its
   status text when the error body is unreadable.
5. Reaching the fixed attempt limit dispatches `task_poll_timeout` and stops.
6. Calling stop while fetch is pending suppresses completion after the await.
7. Calling stop while fetch is pending suppresses rejection after the await.
8. Stop clears a scheduled retry and prevents another request.
9. A successful response with unreadable JSON retains the current empty-object
   behavior and remains pending until stopped or timed out.
10. Asynchronous completion receives an abort signal and performs no later
   component state work after stop.
11. Existing summary, topic, agenda, extraction, loading, error, and rendered
   content contracts remain unchanged.

**r) Tests.**

| Test | Scenarios |
|---|---|
| queued task completes | 1 |
| failed task reports and stops | 3 |
| HTTP failures report and stop, including unreadable bodies | 4 |
| bounded polling times out | 5 |
| stop during pending success suppresses callback | 6 |
| stop during pending rejection suppresses callback | 7 |
| successful unreadable JSON stays pending | 9 |
| async completion observes stop | 10 |
| stop clears scheduled retry | 8 |
| existing ResultCard Python/frontend tests | 2, 11 |

Tests are written and run red before the production extraction. They use
`node:test` context mocks around global `fetch` and timers, not implementation
callbacks added for testing.

**s) Fakes and mocks.** Global `fetch` is replaced at the approved outbound
HTTP boundary. Node's test clock replaces `setTimeout` at the approved clock
boundary. No component, facade, or module under test is mocked.

**t) Verification rows.** Run frontend contract tests, frontend component
tests, docs links, and the complete Python suite because this closes the final
cross-cutting remediation task. Authoritative PR checks remain required.

## 6. Execution, Rollback, Docs

**u) Commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-fe-1-task-polling-lifecycle

cd frontend
node --test components/__tests__/ResultCard.polling-contract.test.js

cd ..
./.venv/bin/ruff check .
./.venv/bin/ruff format --check . --config ruff-format.toml
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_resultcard_agenda_status_refresh.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_frontend_pages_config.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_search_sort_ui_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_semantic_search_ui_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/pytest -q
cd frontend && npm test
git diff --check
git status --short
```

If dependencies are absent, `npm ci` requires separate operator approval;
targeted `node:test` remains available because the new lifecycle test imports
only standard-library modules and production libraries without package
dependencies.

**v) Rollback.** Revert the T-FE-1A merge commit and rerun the same frontend,
Python, and docs checks. No migration, data repair, configuration restoration,
or external-state cleanup is required. Rollback knowingly restores the
post-await cancellation race and source-regex tests.

**w) Docs synchronization.** Update only the remediation ledger and this Full
plan. Do not edit the historical architecture review, README, ADR, operations,
security, testing policy, or data-governance docs because the public runtime
contract does not change.

## 7. Delivery Self-Audit

**x) Diff scan.** Re-run A-F/H. Reject a generic action abstraction, duplicate
response parser, injectable fetch/timer parameter, compatibility export,
retained old poller, weakened timeout, visual change, dependency addition, or
edit outside the eight owned paths.

**y) Evidence.** Report the tests-first failure, every command from 6u with
PASS/FAIL, Node version, independent planning and pre-commit findings, applied
fixes, commits, PR URL, unresolved threads, and final CI state. Mark any
dependency-blocked command `NOT VERIFIED` rather than claiming success.

**z) Deviations.** Authorized correction: ownership includes the existing
agenda source-preservation contract because raw task-result interpretation now
moves explicitly into `ResultCard`, plus the compiled-render test's production
module list. T-FE-1 closes with no duplicate
poller found, and T-FE-1A extracts the sole lifecycle owner to make the real
cancellation defect behavior-testable. Any additional path, dependency,
action-level abstraction, skipped review, unresolved P1/P2, or unrun required
check is a blocker.

## Independent Planning Review

- One poller already serves all four actions; do not create a generic action
  executor.
- Keep action-specific cached, blocked, result-decoding, and refresh behavior
  in `ResultCard`.
- Source-regex tests do not satisfy the behavior-test gate.
- Recheck cancellation after awaited fetch/JSON work and before callbacks.
- A non-JSX lifecycle owner enables behavior tests with `node:test` and no new
  dependency or injected test callable.
