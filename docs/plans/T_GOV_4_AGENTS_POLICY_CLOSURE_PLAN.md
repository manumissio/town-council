# T-GOV-4: Close the Revised AGENTS Policy Task

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: implementation-ready`
`execution: code`

## 1. Context & Alignment

**a) Driver.** The revised `AGENTS.md` landed in commit `453c386`, and the
CI transitions it anticipated are complete. The active remediation ledger
still classifies T-GOV-4 as partially landed, and two links use
`docs/TESTING.md` instead of the tracked `docs/TESTING.MD` casing. This task
corrects those links and adds durable completion evidence without
re-authoring the policy.

**b) Canonical documents consulted.**

- `AGENTS.md` hierarchy, workflow contract, verification matrix, and
  maintenance rules define the policy being verified.
- `docs/ENGINEERING_GUARDRAILS.md` remains canonical for guardrail scope;
  this task must not duplicate its machine-readable inventories.
- `docs/TESTING.MD` permits tracked-filesystem policy tests and requires
  observable contracts.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` defines T-GOV-4 acceptance
  and currently records it as partially landed.
- `docs/reviews/architecture-review-2026-07-19.html` identifies T-GOV-4 as
  partial, but that implementation-state claim predates commit `453c386`.

**c) Remediation alignment.** T-GOV-4 remains in the GOV lane. Expand its
exclusive ownership to:

- `AGENTS.md`, the two `docs/TESTING.md` casing corrections only
- `docs/plans/T_GOV_4_AGENTS_POLICY_CLOSURE_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `tests/test_repository_guardrails.py`

No other tracked file may change.

**d) Decision-gate check.** T-GOV-4 depends on no G1-G5 decision. T-CI-1
and T-CI-2 are complete, so their former transition conditions are
satisfied. G4 and G5 remain open and unaffected.

## 2. Design

**e) Step-by-step approach.**

1. Register this plan and expanded ownership before changing the closure
   contract.
2. Audit `git diff --unified=0 453c386^ 453c386 -- AGENTS.md`. Record every
   changed hunk and verify each maps to the task's enumerated policy sections;
   this proves sections outside those hunks remained byte-identical.
3. Add a failing repository guardrail that expects T-GOV-4 to be uniquely
   complete, this artifact to be complete, and no completed CI transition
   marker or wrong-case testing-policy link to remain in `AGENTS.md`. The
   task entry must also describe the transitions as completed history.
4. Run the test red while the ledger and artifact still say in progress and
   implementation-ready.
5. Mark T-GOV-4 complete in the task table and task entry, record the landed
   commit evidence, and mark this artifact complete.
6. Correct only the two `docs/TESTING.md` references to the tracked
   `docs/TESTING.MD` casing.
7. Run the guardrail/tooling and docs verification rows plus the complete
   Python suite.
8. Obtain an independent pre-commit review, resolve every eligible P1/P2,
   and rerun affected verification.
9. Commit, push one PR, request Codex review, resolve feedback, and merge
   only after all required checks pass.

The only new function is the test
`test_t_gov_4_agents_policy_is_complete`. Its responsibility is to enforce
agreement among the live policy, task ledger, and closure artifact.

**f) Reuse audit.** Reuse `_required_markdown_section` and
`_remediation_task_states` in `tests/test_repository_guardrails.py`. No new
parser, policy registry, wrapper, compatibility alias, or duplicated
source inventory is introduced. No older implementation is retained or
superseded.

**g) Data contracts.** No application payload changes. The policy contract
is repository text: T-GOV-4 appears in exactly one task-table state, its
task entry has exactly one status, and `AGENTS.md` contains the required
policy sections without stale T-CI-1/T-CI-2 transition language or
wrong-case canonical paths.

**h) Schema/migration impact.** None.

## 3. Security & Data Governance

**i) Security-sensitive paths.** None under `AGENTS.md`. The test verifies
that `<security_sensitive_paths>` remains present but does not change any
runtime trust boundary or security control.

**j) Secrets.** No credential, key, environment variable, or default
changes.

**k) Person data.** No person-level data is created, linked, aggregated, or
exposed. G4 is unaffected.

**l) Untrusted input.** The test reads tracked Markdown policy files only.
No scraped content, provider response, HTML, or user input is parsed.

## 4. Code Health

**m) GED conformance sweep.** The new test uses repository-domain names,
existing helpers, no exception handler, no timestamp generation, no
environment read, and no nesting beyond the existing comprehensions in
the shared task-state parser. No production function changes.

**n) Antipattern scan, plan pass.**

- A1/H1: no external API or dependency-facing call is introduced.
- A3: commit, test, and CI claims must be backed by commands or GitHub
  evidence recorded in this artifact.
- B1/F1: existing Markdown and task-state helpers are reused.
- D1-D3: the test strengthens the state contract and checks public policy
  text; no assertion is weakened or skipped.
- E1-E3: edits are limited to the four owned paths; `AGENTS.md` changes only
  the two proven wrong-case paths.
- A2, A4, B2-B3, C1-C2, F2, H2-H4: no planned violations.

**o) Ratchet interaction.** Ruff selectors, BLE001 boundaries, formatter
scope, Mypy scope, coverage threshold, and verification commands remain
unchanged. This task removes only stale remediation status.

**p) Dead code and duplication audit.** No production code is deleted or
added. The guardrail reuses the shared task-state parser. Expected net
growth is one focused policy test and one implementation plan.

## 5. Testing

**q) Edge cases and failure scenarios.**

1. T-GOV-4 appears as Complete and another state.
2. The task entry remains partial, pending, or has multiple status lines.
3. The artifact remains implementation-ready after ledger closure.
4. A required `AGENTS.md` policy section is deleted or links the wrong path.
5. A stale T-CI-1/T-CI-2 transition marker is reintroduced.
6. Completion evidence names the wrong landed commit.
7. The T-GOV-4 ledger entry says transition markers still remain.
8. Historical commit `453c386` changed a section outside its enumerated
   acceptance list.
9. An unrelated current policy section is rewritten during closure.

**r) Tests.**

| Test | Scenarios |
|---|---|
| New `test_t_gov_4_agents_policy_is_complete` | 1-7 |
| `git diff --unified=0 453c386^ 453c386 -- AGENTS.md` | 8 |
| Current `git diff -- AGENTS.md` scope audit | 9 |
| Existing repository guardrails | 1-9 |
| Existing docs-link tests | policy-link integrity |
| Complete Python suite | cross-cutting regression check |

The closure test is written and run red before completion markers change.

**s) Fakes and mocks.** None. The test uses the approved tracked-filesystem
boundary and patches no production symbol.

**t) Verification rows.** Apply the guardrail/tooling row because
`tests/test_repository_guardrails.py` changes and the docs-only row because
`AGENTS.md` policy status is being closed. Run the complete Python suite
before handoff.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-gov-4-close-agents-policy

git show --name-only --format= 453c386
git diff --unified=0 453c386^ 453c386 -- AGENTS.md
rg -n "<known_antipatterns>|<security_sensitive_paths>|authoritative CI verification|\\[transition" AGENTS.md

PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_repository_guardrails.py::test_t_gov_4_agents_policy_is_complete

./.venv/bin/ruff check .
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/pytest -q
git diff --check
git status --short
```

Delivery:

```bash
git push -u origin codex/t-gov-4-close-agents-policy
gh pr create \
  --base master \
  --head codex/t-gov-4-close-agents-policy \
  --title "T-GOV-4: Close the revised AGENTS policy task"
```

**v) Rollback.** Revert the T-GOV-4 closure merge commit, rerun Ruff, Mypy,
repository guardrails, docs links, and the complete suite. No migration,
configuration restoration, data repair, or external-state cleanup exists.
Rollback restores the stale partial status but does not revert the already
active `AGENTS.md` policy.

**w) Docs sync.**

- Remediation ledger: ownership, implementation-plan link, unique completed
  state, landed commit, and changelog evidence.
- This plan: implementation and delivery evidence.
- `AGENTS.md`: correct the two canonical testing-policy path references;
  leave all policy language unchanged.
- README, ADR, architecture review, operations, security, testing,
  engineering guardrails, and data-governance docs: no changes.

## 7. Delivery Self-Audit

**x) Antipattern scan, diff pass.** Re-run A-F/H. Reject any `AGENTS.md`
policy rewrite, duplicated task-state parser, weakened guardrail, unrelated
formatting, invented evidence, or change outside the four owned paths.

**y) Evidence.** Record the tests-first red result, commit `453c386`
verification, Ruff, Mypy, guardrail, docs-link, and complete-suite outcomes,
independent review findings, commits, PR URL, unresolved-thread count, and
final CI state. Anything unrun is `NOT VERIFIED`.

**z) Deviations.** Expected authorized changes: ownership expands from one
file to four closure paths, two testing-policy links receive case-only
corrections, and the ledger moves T-GOV-4 from partial to complete. Any
other `AGENTS.md` content edit, new dependency, runtime change, skipped
review, unresolved P1/P2, or unrun required check is a blocker.
