# T-GOV-1: Ratify Test Patch Points as Non-Public API

`artifact_contract: ce-unified-plan/v1`  
`artifact_readiness: implementation-ready`  
`execution: code`

## 1. Context & Alignment

**a) Driver.** The operator approved G3 on 2026-07-24. Town Council has
accumulated facade exports, synchronized globals, wrappers, and dependency
rebindings whose only durable consumers are tests. Phase 2 cannot safely remove
that debt until the architecture record makes the governing distinction
explicit: runtime and public import contracts remain protected, but a test's
historical monkeypatch target is not a public API.

**b) Canonical documents consulted.**

- `AGENTS.md` `<hierarchy_of_truth>`, `<known_antipatterns>`,
  `<workflow_contract>`, and `<verification_matrix>` require an explicit
  architecture decision, implementation-module patching, scoped ownership, and
  complete verification.
- `docs/ADR.md` is the accepted-decision log. Earlier entries preserve
  test-only compatibility seams, so the new entry must explicitly supersede
  those clauses without rewriting history or revoking runtime contracts.
- `docs/TESTING.MD` already contains the approved fake boundaries and
  implementation-module patching rules, but still says it becomes effective
  with G3.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` makes T-GOV-1 the P0
  governance task blocking every Phase 2 de-facading task.
- `docs/reviews/architecture-review-2026-07-19.html` identifies facade
  compatibility and test seams as material architecture debt.
- `SECURITY.md` requires preserving the least-privilege Meilisearch reader-key
  boundary touched by the comment-only source edit.
- `docs/DATA_GOVERNANCE.md` adds no person-data constraint to this policy-only
  task.

**c) Remediation alignment.** This is T-GOV-1 in the GOV lane. Its exclusive
`files_owned` set is:

- `api/search/support_core.py`, comment only
- `docs/ADR.md`
- `docs/TESTING.MD`
- `docs/plans/T_GOV_1_TEST_PATCH_POINTS_ADR_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `tests/test_repository_guardrails.py`

The search module is coordinated with the SEC lane only to remove its stale
statement that G3 defers facade removal. No runtime symbol, import, constant, or
behavior may change.

**d) Decision-gate check.** G3 was approved by the operator on 2026-07-24. The
approval authorizes the Accepted ADR but does not unblock Phase 2 until this
task merges. G1, G2, G4, and G5 are unchanged.

## 2. Design

**e) Step-by-step approach.**

1. Register this Full Template plan, six-file ownership, operator approval, and
   in-progress status in the remediation ledger.
2. Commit the authorization record before changing policy, tests, or source
   comments.
3. Add failing repository guardrail tests before implementation:
   - require a scoped Accepted ADR, effective testing policy, approved ledger
     state, and removal of the Phase 2 G3 blocker after merge;
   - reject live production Python comments that still treat G3 as a reason to
     preserve a facade.
4. Add a dated Accepted entry to `docs/ADR.md` with one responsibility:
   distinguish protected runtime/public contracts from non-public test patch
   targets.
5. State that the new ADR supersedes prior accepted statements only to the
   extent that they preserve monkeypatch paths, test-only re-exports,
   synchronized globals, injectable callables, or dependency rebinding for test
   compatibility. Runtime, import, CLI, API, task-identity, and operational
   portions of mixed historical statements remain active. Leave all historical
   entries unchanged.
6. Preserve runtime behavior, supported import paths, CLI contracts, API
   contracts, Celery signatures, provider boundaries, and operational
   compatibility unless a separately owned remediation task explicitly
   changes them.
7. Activate `docs/TESTING.MD` by removing its G3 transition wording. Keep its
   approved fake boundaries and implementation-module patching rules intact.
8. Replace the stale G3 deferral comment in `api/search/support_core.py` with a
   factual comment about current reader-key compatibility. Do not remove the
   export in this task.
9. Preserve the already-recorded operator approval of G3. In the implementation
   commit, mark the T-GOV-1 ADR gate satisfied and the task complete, then
   remove the Phase 2 G3 blocker while preserving each Phase 2 task's own
   sequencing and ownership.
10. Keep T-GOV-6 partially landed after T-GOV-1. This task activates its
    testing-policy component, but the README Documentation Map still lacks the
    three T-GOV-6 canonical links and is outside this task's ownership.
11. Run the required gates, inspect the diff for generated antipatterns, obtain
    a fresh subagent pre-commit review, and deliver one implementation commit
    after the authorization commit.

No new production function, helper module, facade, registry, wrapper, or
configuration surface is introduced.

**f) Reuse audit.** Extend the existing ADR format, testing policy,
remediation ledger, and repository guardrail suite. The policy does not create
a second fake-boundary list; `docs/TESTING.MD` remains the operational source.
The new ADR supersedes older statements only to the extent that they preserve
test-only patch targets; mixed runtime and operational contracts remain active.
It does not duplicate or delete those historical records.

Rejected alternatives:

- Rewrite every historical ADR: rejected because architecture records must
  preserve decision history and because broad edits would obscure the new
  precedence rule.
- Remove facade code in the ADR PR: rejected because Phase 2 tasks own those
  runtime changes, tests, and rollback boundaries.
- Treat all facades as immediately private: rejected because supported runtime
  and public import contracts remain protected until an owned task changes
  them.
- Add a repository-wide monkeypatch scanner now: rejected because T-GOV-3 owns
  the later guardrail redesign and this task needs only durable decision-state
  checks.

**g) Data contracts.** No application payload changes. The policy contract is:

- Tests patch implementation modules or use approved architectural fakes.
- Test-only patch locations do not block owned refactors.
- Runtime behavior and public contracts remain protected.
- A facade is removed only by its named remediation task with behavior tests.

**h) Schema/migration impact.** None.

## 3. Security & Data Governance

**i) Security-sensitive paths.** `api/search/support_core.py` handles
`MEILI_SEARCH_KEY` and `MEILI_MASTER_KEY`, so the required trust-boundary
review applies even though the edit is comment-only. The API-to-Meilisearch
reader boundary remains unchanged, an attacker gains no capability, and the
`SECURITY.md` least-privilege reader-key control remains intact. No credential,
authentication, rate-limit, CORS, proxy, client-construction, or key-resolution
behavior changes.

**j) Secrets.** No credential, key, environment variable, or default changes.

**k) Person data.** No person-level data is created, linked, aggregated, or
exposed. G4 remains open.

**l) Untrusted input.** No scraped content, provider response, request body,
HTML, JSON, or external artifact parsing changes.

## 4. Code Health

**m) GED conformance sweep.** The only production-file edit is a policy
comment. New test helpers, if needed, remain test-local, typed, focused, and
limited to exact Markdown sections or active Python roots. No exception
handler, timestamp, environment read, runtime literal, or import-time side
effect changes.

**n) Antipattern scan, plan pass.**

- A1/H1: no external library API or configuration call changes.
- B1/F1: no parser framework, policy registry, wrapper, compatibility layer,
  or duplicate fake-boundary inventory.
- B2/C1: historical ADR text remains for audit history, but its test-only
  compatibility clauses are explicitly superseded rather than kept active.
- C2: tests are directed away from facade patch targets; no new seam preserves
  an old target.
- D1-D3: guardrails assert the observable policy state and active-code comment,
  without skips, relaxed tolerances, or production mocks.
- E1-E3: only six owned files may change; the source edit is comment-only.
- A2-A4, B3, F2, and H2-H4: no planned violations.

**o) Ratchet interaction.** No Ruff selector, BLE001 boundary, formatter
scope, Mypy scope, coverage threshold, or CI gate changes. The task removes a
policy blocker but does not remove any runtime allowlist entry.

**p) Dead code and duplication audit.** Replace one stale G3-deferral comment
and two transition statements. Reuse the existing approved-boundary table.
Delete no runtime implementation. Expected production-code delta is zero.

## 5. Testing

**q) Edge and failure scenarios.**

1. The ADR is present but not `Accepted`.
2. The ADR fails to supersede prior test-only compatibility clauses.
3. The ADR overreaches and treats runtime/API/import contracts as disposable.
4. `docs/TESTING.MD` still says it becomes effective in the future.
5. The ledger still describes G3 as open or Phase 2 as blocked by G3 after the
   ADR implementation commit.
6. The T-GOV-1 task is marked complete before the Accepted ADR exists.
7. Live production Python still says G3 defers facade removal.
8. Historical ADR text mentioning monkeypatch seams is incorrectly treated as
   active production policy.
9. The source comment edit changes executable behavior or imports.
10. T-GOV-6 is incorrectly marked complete even though its README
    Documentation Map acceptance deficit remains.

**r) Tests.**

| Test | Scenarios |
|---|---|
| `test_test_patch_points_policy_has_accepted_adr_and_effective_runbook` | 1-6, 8, 10 |
| `test_live_python_does_not_treat_g3_as_a_facade_deferral` | 7, 9 |
| Existing repository guardrail suite | 1-9 |
| `tests/test_meilisearch_key_security.py` | 9 |
| Complete Python suite | Runtime regression check |

Both new tests are written and run red before the ADR, testing-policy, ledger,
or source-comment implementation changes.

**s) Fakes and mocks.** None. Tests use the approved filesystem boundary and
read tracked policy/source files directly. No production facade, re-export, or
implementation symbol is patched.

**t) Verification rows.** Apply the guardrail/tooling row because
`tests/test_repository_guardrails.py` changes, the docs-only row because
canonical policy changes, and a focused search credential regression because
`api/search/support_core.py` is touched. Run the complete Python suite before
handoff.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-gov-1-test-patch-points-adr
```

Tests-first red evidence:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_repository_guardrails.py::test_test_patch_points_policy_has_accepted_adr_and_effective_runbook \
  tests/test_repository_guardrails.py::test_live_python_does_not_treat_g3_as_a_facade_deferral
```

Final local verification:

```bash
./.venv/bin/ruff check .
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_meilisearch_key_security.py
PYTHONPATH=. .venv/bin/pytest -q
git diff --check
git status --short
```

Delivery uses two commits:

1. `docs(remediation): authorize the G3 policy record`
2. `docs(governance): accept test patch point policy`

Push `codex/t-gov-1-test-patch-points-adr`, open one PR titled
`T-GOV-1: Accept test patch points as non-public API`, request Codex review,
and watch all checks to a decided state. Merge with a merge commit so the
authorization and implementation commits remain independently reversible.
Browser testing is not applicable.

**v) Rollback.** Do not revert the PR merge commit because that would also
erase the authorization record. Revert only the implementation commit retained
by the required merge-commit strategy:

```bash
git switch master
git pull --ff-only
git revert <t_gov_1_implementation_commit_sha>
./.venv/bin/ruff check .
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_meilisearch_key_security.py
PYTHONPATH=. .venv/bin/pytest -q
git diff --check
```

No migration, data repair, configuration restore, or external-state cleanup is
required. Reverting only the implementation restores the approval-only ledger
state, makes the Accepted ADR gate unmet again, and re-blocks Phase 2.

**w) Docs synchronization.**

- `docs/ADR.md`: add the Accepted decision and scoped supersession rule.
- `docs/TESTING.MD`: make the already-landed policy immediately effective.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`: record approval, task
  ownership/status, the satisfied ADR gate, and the Phase 2 gate transition.
  T-GOV-6 remains partially landed because its README Documentation Map links
  are still missing and outside this task.
- `api/search/support_core.py`: update the stale policy comment only.
- `AGENTS.md`, `SECURITY.md`, README, architecture review, operations,
  performance, engineering guardrails, and data governance: no changes.

## 7. Delivery Self-Audit

**x) Antipattern scan, diff pass.** Re-run A-F and H. Reject facade removal,
runtime/import changes, historical ADR rewrites, a second fake-boundary list,
new test seams, policy registries, weakened tests, unrelated formatting, type
suppression, or edits outside the six-file ownership set.

**y) Evidence required at delivery.**

- Tests-first red result.
- Ruff, Mypy, repository guardrail, docs-link, Meilisearch key-security, and
  complete-suite outcomes.
- Planning-review and pre-commit-review findings with applied fixes.
- Commit hashes, PR URL, unresolved-thread count, and final CI state.
- Browser stage: `NOT APPLICABLE`.

Anything unrun is reported as `NOT VERIFIED`.

**z) Deviations.** Expected result is none. Any additional file, executable
source change, facade removal, runtime/API/import contract change, new fake
boundary, skipped review, unresolved P1/P2, or unrun required check is a
blocker.
