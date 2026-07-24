# T-GOV-5: Close the Engineering Guardrails Rewrite

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: complete`
`execution: code`

## 1. Context & Alignment

**a) Driver.** The rewritten `docs/ENGINEERING_GUARDRAILS.md` landed in
historical commit `c4a4a27`, and its T-CI-4 dependency is complete. The live
document still says that the revision lands alongside T-GOV-3, uses the wrong
case for the tracked testing-policy path, and describes C901 as not yet
adopted. T-GOV-5 therefore remains partially landed even though its current
acceptance criteria are independently verifiable. This closure corrects those
claims and adds durable evidence without changing guardrail policy or removing
the still-active T-GOV-3 transition.

**b) Canonical documents consulted.**

- `AGENTS.md` hierarchy, workflow contract, verification matrix, and docs-sync
  rules require config-owned scope, exact verification, and current commands.
- `docs/ENGINEERING_GUARDRAILS.md` is the guardrail-policy source being closed.
- `docs/TESTING.MD` permits tracked-filesystem policy tests and requires
  observable contracts.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` defines T-GOV-5 acceptance and
  currently records it as partially landed.
- `docs/reviews/architecture-review-2026-07-19.html` identifies the guardrail
  rewrite as landed but awaiting its CI dependencies and closure.
- `ruff.toml`, `ruff-format.toml`, `mypy.ini`, `.coveragerc`, and the Python and
  frontend workflows are the machine-readable sources for current guardrail
  scope and enforcement.

**c) Remediation alignment.** T-GOV-5 remains in the GOV lane. Expand its
exclusive ownership to:

- `docs/ENGINEERING_GUARDRAILS.md`
- `docs/plans/T_GOV_5_ENGINEERING_GUARDRAILS_CLOSURE_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `tests/test_repository_guardrails.py`

The machine-readable guardrail configs and workflows are read-only evidence
for this task.

**d) Decision-gate check.** T-GOV-5 depends on no G1-G5 decision. T-CI-4 is
complete. T-GOV-3 remains pending, so its structural-rules transition marker
must remain.

## 2. Design

**e) Step-by-step approach.**

1. Register this plan and expanded ownership before changing the closure
   contract.
2. Audit historical commit `c4a4a27` and current guardrail config. Record that
   the rewrite changed only `docs/ENGINEERING_GUARDRAILS.md`, while the
   original external draft is unavailable for exact identity verification.
3. Obtain an independent planning review and correct every eligible P1/P2.
4. Add a failing repository guardrail that expects T-GOV-5 to be uniquely
   complete, this artifact to be complete, and the live guardrail document to
   contain current testing-policy casing, current C901 enforcement, all
   required exception prose, and the pending T-GOV-3 marker.
5. Run the focused test red while the ledger and artifact remain incomplete
   and the live document contains stale claims.
6. Correct only three live-document claims: rewrite status, testing-policy
   path casing, and C901 adoption/scope wording.
7. Mark T-GOV-5 complete in the task table and task entry, record historical
   and current acceptance evidence, and mark this artifact complete.
8. Run guardrail/tooling, docs-link, and complete-suite verification.
9. Obtain a fresh pre-commit review, resolve every eligible P1/P2, and rerun
   affected verification.
10. Commit, push one PR, request Codex review, resolve feedback, and merge only
    after required checks pass.

The only new function is
`test_t_gov_5_engineering_guardrails_is_complete`. Its responsibility is to
enforce agreement among the live guardrail policy, current C901 config, task
ledger, and closure artifact.

**f) Reuse audit.** Reuse `_required_markdown_section` and
`_remediation_task_states` in `tests/test_repository_guardrails.py`, plus the
existing Ruff, formatter, Mypy, coverage, workflow, exception, and
suppression guardrails. No parser, policy registry, wrapper, compatibility
alias, or duplicate source inventory is introduced.

**g) Data contracts.** No application payload changes. The repository-policy
contract is text: T-GOV-5 appears in exactly one task-table state; its task
entry has exactly one status; scope remains config-owned; and the live
document retains its boundary-handler, exception-process, flat re-raise, and
`sys.exit()` prohibition contracts. The test parses `ruff.toml` with the
existing `tomllib` dependency and requires C901 selection plus
`max-complexity = 10`.

**h) Schema/migration impact.** None.

## 3. Security & Data Governance

**i) Security-sensitive paths.** None under `AGENTS.md`. The guardrail prose
describes exception policy but does not alter a runtime trust boundary or
security control.

**j) Secrets.** No credential, key, environment variable, or default changes.

**k) Person data.** No person-level data is created, linked, aggregated, or
exposed. G4 is unaffected.

**l) Untrusted input.** The new test reads tracked Markdown and existing
machine-readable configuration only. It does not parse scraped content,
provider responses, HTML, or user input.

## 4. Code Health

**m) GED conformance sweep.** The new test uses repository-domain names,
existing helpers, no exception handler, no timestamp generation, no
environment read, and no additional nesting. No production function changes.

**n) Antipattern scan, plan pass.**

- A1/H1: no external API or dependency-facing call is introduced; enforcement
  claims are checked against current repository config.
- A3: historical identity is explicitly `NOT VERIFIED` because the original
  draft is unavailable; current acceptance is verified independently.
- B1/F1: existing Markdown and guardrail helpers are reused.
- D1-D3: the test strengthens observable policy alignment without skips,
  widened tolerances, or private production assertions.
- E1-E3: edits are limited to the four owned paths and three named live-policy
  corrections.
- A2, A4, B2-B3, C1-C2, F2, H2-H4: no planned violations.

**o) Ratchet interaction.** Ruff selectors, BLE001 boundaries, formatter
scope, Mypy scope, coverage threshold, CI workflows, and runtime behavior
remain unchanged. T-GOV-3's transition marker remains because its structural
work is pending.

**p) Dead code and duplication audit.** No production code is added or
deleted. Stale status and adoption wording is replaced in place. The new test
reuses shared task-state and Markdown helpers. Expected net growth is one
focused policy test and this implementation plan.

## 5. Testing

**q) Edge cases and failure scenarios.**

1. T-GOV-5 appears as Complete and another state.
2. The task entry remains partial, pending, or has multiple status lines.
3. The artifact remains implementation-ready after ledger closure.
4. The live document restores stale “lands alongside T-GOV-3” wording.
5. The tracked testing-policy path regresses to `docs/TESTING.md`.
6. C901 is described as pending or limited to a duplicated path list.
7. The pending T-GOV-3 transition marker is removed prematurely.
8. Boundary-handler, exception-process, or flat re-raise prose is deleted.
9. `sys.exit()` becomes authorized inside unlisted broad handlers.
10. A scope inventory is duplicated into prose instead of remaining in config.
    The test extracts backticked and unbackticked Python path references,
    rejects all Python glob paths, and rejects any Markdown section containing
    more than one distinct Python path. Isolated config references and examples
    remain allowed.
11. Closure claims exact draft identity despite the original draft being
    unavailable.

**r) Tests.**

| Test | Scenarios |
|---|---|
| New `test_t_gov_5_engineering_guardrails_is_complete` | 1-11 |
| Existing Ruff, formatter, Mypy, coverage, and workflow guardrails | 6, 10 |
| Existing broad-handler and suppression guardrails | 8, 9 |
| Existing docs-link tests | 5 |
| Complete Python suite | cross-cutting regression check |

The closure test is written and run red before completion markers and live
policy claims change.

**s) Fakes and mocks.** None. The test uses the approved tracked-filesystem
boundary and patches no production symbol.

**t) Verification rows.** Apply the guardrail/tooling row because
`tests/test_repository_guardrails.py` changes and the docs-only row because
canonical guardrail policy changes. Run the complete Python suite before
handoff.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-gov-5-close-engineering-guardrails

git show --name-only --format= c4a4a27
rg -n "C901|max-complexity|src =" ruff.toml
rg -n "include =" ruff-format.toml
rg -n "^files =" mypy.ini
rg -n "^source =" .coveragerc
rg -n '`[^`]*\.py`' docs/ENGINEERING_GUARDRAILS.md

PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_repository_guardrails.py::test_t_gov_5_engineering_guardrails_is_complete

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
git push -u origin codex/t-gov-5-close-engineering-guardrails
gh pr create \
  --base master \
  --head codex/t-gov-5-close-engineering-guardrails \
  --title "T-GOV-5: Close the engineering guardrails rewrite"
```

**v) Rollback.** Revert the T-GOV-5 closure merge commit, rerun Ruff, Mypy,
repository guardrails, docs links, and the complete suite. No migration,
configuration restoration, data repair, or external-state cleanup exists.
Rollback restores stale partial status but does not revert active guardrail
enforcement.

**w) Docs sync.**

- `docs/ENGINEERING_GUARDRAILS.md`: current rewrite status, tracked testing
  path casing, and active C901 enforcement without a duplicated file list.
- Remediation ledger: ownership, implementation-plan link, unique completed
  state, historical caveat, and acceptance evidence.
- This plan: implementation, review, verification, and delivery evidence.
- `AGENTS.md`, README, ADR, architecture review, operations, security, testing,
  and data-governance docs: no changes.

## 7. Delivery Self-Audit

**x) Antipattern scan, diff pass.** Re-run A-F/H. Reject duplicated scope
inventories, removal of the live T-GOV-3 transition, weakened exception
policy, unrelated policy rewrites, new guardrail exceptions, type
suppressions, or claims of exact draft identity.

**y) Evidence.** Report each command from 6u with PASS or FAIL, including the
tests-first red result, historical audit, planning-review findings,
pre-commit-review findings, commit hashes, PR URL, unresolved-thread count,
and final CI state. Record original-draft identity as `NOT VERIFIED`.

**z) Deviations.** The authorized historical deviation is that commit
`c4a4a27` landed before T-CI-4 rather than in the same PR or immediately
after it. The dependency is now complete, so current acceptance can close.
Any additional changed path, guardrail-policy change, removed T-GOV-3 marker,
skipped review, unresolved P1/P2, or unrun required check is a blocker.
