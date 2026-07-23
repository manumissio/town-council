# T-CI-2: Give the Frontend a Test Runner and CI Job

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: implementation-ready`
`execution: code`

## 1. Context & Alignment

**a) Driver.** T-CI-1A and T-CI-4 are complete, so T-CI-2 is the next
ordered P0 remediation task. The repository has four frontend test files,
but `frontend/package.json` has no test script and no CI workflow runs them.
Direct execution with Node 20 discovers all four files and 11 assertions.
Ten pass; the remaining CSP assertion reads a superseded config file even
though the CSP behavior moved to `frontend/proxy.js`.

**b) Canonical documents consulted.**

- `AGENTS.md` `<hierarchy_of_truth>`, `<known_antipatterns>`,
  `<verification_matrix>`, and `<status_reporting_contract>` require
  current code as behavioral truth, no compatibility machinery, exact
  verification, and a frontend test command once T-CI-2 lands.
- `docs/TESTING.MD` defines behavior-focused tests and currently marks the
  frontend runner as transitional.
- `docs/ENGINEERING_GUARDRAILS.md` already identifies
  `.github/workflows/frontend-tests.yml` as the frontend CI owner.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` requires an unconditional
  `frontend-tests` check before T-CI-2A may make it mandatory.
- `docs/reviews/architecture-review-2026-07-19.html` defers frontend
  decomposition until a test runner exists.
- `SECURITY.md` and `docs/OPERATIONS.md` identify
  `frontend/proxy.js` as the current nonce-based CSP owner.

**c) Remediation alignment.** T-CI-2 remains in the CI lane. Before
implementation, expand its `files_owned` set to exactly:

- `docs/plans/T_CI_2_FRONTEND_TESTS_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `docs/TESTING.MD`, frontend transition sentence only
- `frontend/package.json`
- `frontend/components/__tests__/NextConfig.security-headers.test.js`
- `.github/workflows/frontend-tests.yml`
- `tests/test_repository_guardrails.py`

The remediation-plan correction replaces the stale Jest/Vitest assumption
with the already-used Node test runner and permits only the CSP test's source
target to move from `next.config.js` to `proxy.js`. No assertion is removed
or weakened.

**d) Decision-gate check.** No G1-G5 decision is required or foreclosed.
T-CI-2A remains a separate operator decision because it changes the live
required-check ruleset. G3 remains open and continues to block Phase 2.

## 2. Design

**e) Step-by-step approach.**

1. Branch from current `origin/master`.
2. Register this Full plan, corrected ownership, completed Phase 0 statuses,
   and the current G3-only Phase 2 blocker in the remediation plan.
3. Add failing repository guardrail tests before implementation. They require
   the exact package script and a universal frontend workflow.
4. Record red evidence:
   - `npm test` fails because the script is absent.
   - `node --test components/__tests__/*.test.js` runs all four files but
     fails the stale CSP source assertion.
   - the new workflow contracts fail because the workflow is absent.
5. Run three disjoint implementation lines:
   - Frontend contract line: add `"test": "node --test
     components/__tests__/*.test.js"` and repoint only the CSP source
     variable to `frontend/proxy.js`.
   - Workflow line: add the unconditional `frontend-tests` workflow.
   - Documentation line: remove only the landed-runner transition from
     `docs/TESTING.MD`.
6. Integrate the lines and run the applicable verification rows and complete
   Python suite.
7. Obtain a fresh independent pre-commit review. Apply every eligible P1/P2
   finding and rerun affected checks.
8. Commit the implementation, push, open one PR, request review, and watch CI
   to a decided state.

No production helper, facade, wrapper, runner config, or compatibility path
is added.

**f) Reuse audit.** Reuse the four existing `node:test` files, Node 20's
built-in stable test runner, the existing npm lockfile, the repository's
workflow conventions, and current guardrail test patterns. A Jest or Vitest
dependency is rejected because the tests do not use either API and adding one
would create unnecessary dependency and configuration work. Adding
`"type": "module"` is rejected because `frontend/next.config.js` remains
CommonJS.

The CSP test keeps both existing behavioral assertions. Only the CSP source
changes to the module that now owns CSP. The static security-header assertion
continues reading `next.config.js`.

**g) Data contracts.**

- Frontend command: `npm test` runs exactly the four checked-in
  `components/__tests__/*.test.js` files with Node's built-in runner.
- CI context: job ID `frontend-tests`.
- CI events: every `pull_request` and every push to `master`, without path
  filters.
- CI sequence: `actions/checkout@v5`, `actions/setup-node@v6` with Node 20
  and npm cache, `npm ci`, then `npm test`.
- CSP test contract: CSP rollout assertions read `proxy.js`; static header
  assertions read `next.config.js`.

No application API, schema, Celery signature, runtime default, soak gate, or
model policy changes.

**h) Schema and migration impact.** None.

## 3. Security & Data Governance

**i) Security boundary.** No security-sensitive runtime file is modified.
The stale test is corrected to inspect the current CSP owner without changing
CSP generation, headers, proxy behavior, or attacker capability. The workflow
runs pull-request code in an ephemeral GitHub-hosted runner with
`contents: read` and no secrets.

**j) Secrets.** No credentials, tokens, environment defaults, or
`NEXT_PUBLIC_*` values are added.

**k) Person data.** No person-level data is created, linked, aggregated, or
exposed. G4 is unaffected.

**l) Untrusted input.** Pull-request JavaScript and npm lockfile content are
untrusted CI inputs. `npm ci` installs only the checked-in lockfile, and tests
read checked-in source files. No scraped content, browser input, or provider
response is newly parsed.

## 4. Code Health

**m) GED conformance sweep.** No production function, timestamp, environment
read, error handler, or broad exception changes. The package command is a
single explicit command. Workflow permissions and event rules are explicit.
The stale test continues to assert observable security contracts.

**n) Antipattern scan, plan pass.**

- A1/H1 corrected: Context7 verified Node 20's stable `node --test`,
  recursive discovery, and nonzero failure behavior. Context7 also verified
  `actions/setup-node@v6` inputs for Node 20, npm caching, and a nested
  `cache-dependency-path`.
- B1/F1 corrected: no Jest, Vitest, config file, wrapper, or duplicate runner.
- B2/C1 corrected: the test points directly at the current CSP owner; no old
  source alias survives.
- D1 corrected: no assertion, tolerance, or test file is removed. The stale
  source target is repaired instead.
- D3 accepted narrowly: exact workflow and package commands are observable CI
  contracts.
- E1/E2 corrected: only the seven owned files may change.
- A2-A4, B3, C2, D2, E3, F2, H2-H4: no planned violations.

Independent planning review identified the stale CSP target, unnecessary
third-party runner, missing planning ownership, stale Phase 2 blocker text,
and package conflict with Dependabot PR #114. All are incorporated.

**o) Ratchet interaction.** Ruff selectors, BLE001 boundaries, formatter
scope, Mypy scope, coverage threshold, and existing required-check ruleset
remain unchanged. T-CI-2 creates the `frontend-tests` context but does not
make it required.

**p) Dead code and duplication audit.** No dependency or runner config is
added. The superseded assumption that CSP lives in `next.config.js` is removed
from the test. Expected runtime-code delta is zero.

## 5. Testing

**q) Edge and failure scenarios.**

1. Missing package script prevents local frontend verification.
2. A runner that does not discover all four files gives false confidence.
3. The stale CSP source target fails despite current proxy behavior.
4. A frontend test failure must fail `npm test`.
5. A pull request that changes no frontend files must still receive the
   `frontend-tests` context.
6. A master push must run the same frontend job.
7. Path filters can leave a future required check pending indefinitely.
8. `continue-on-error`, conditional execution, or retries can mask failure.
9. CI must install from the lockfile before testing.
10. T-CI-2 must not change the live ruleset or add coverage.
11. Dependabot PR #114 must remain a separate Next.js update.

**r) Tests added or updated.**

| Test | Scenarios |
|---|---|
| Existing four frontend test files via `npm test` | 1-4 |
| Corrected CSP source contract | 3 |
| `test_frontend_test_script_uses_existing_node_runner` | 1, 2, 4 |
| `test_frontend_workflow_runs_for_every_pull_request_and_master_push` | 5-7 |
| `test_frontend_workflow_installs_locked_dependencies_before_tests` | 8, 9 |
| Read-only ruleset 19594795 API comparison | 10 |
| Diff ownership audit | 10, 11 |

Tests are written and run red before package or workflow implementation. No
fixed total-test count is asserted; the package command explicitly targets
the four current files.

**s) Fakes and mocks.** None. Frontend tests use the filesystem boundary.
Repository guardrail tests read tracked files. No facade, re-export, or
runtime symbol is patched.

**t) Verification rows.** Apply the guardrail/tooling, frontend
component/behavior, frontend contract, and docs-only rows. Run the complete
Python suite because the new workflow is cross-cutting. The PR's
`frontend-tests` run after a clean `npm ci` is authoritative for the lockfile
environment.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-ci-2-frontend-tests
```

Tests-first evidence:

```bash
cd frontend
npm test
node --test components/__tests__/*.test.js
cd ..

PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_repository_guardrails.py::test_frontend_test_script_uses_existing_node_runner \
  tests/test_repository_guardrails.py::test_frontend_workflow_runs_for_every_pull_request_and_master_push \
  tests/test_repository_guardrails.py::test_frontend_workflow_installs_locked_dependencies_before_tests
```

Expected before implementation: missing npm script, one stale CSP failure,
and missing workflow/package contracts.

Final local verification:

```bash
(cd frontend && npm test)
./.venv/bin/ruff check .
./.venv/bin/ruff format --check . --config ruff-format.toml
./.venv/bin/pre-commit run ruff --all-files
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_frontend_pages_config.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_resultcard_agenda_status_refresh.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_search_sort_ui_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_semantic_search_ui_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q
git diff --check
git status --short
```

No local package installation is required because no dependency changes.
The workflow's clean `npm ci` validates the existing lockfile.

Delivery uses two commits:

1. `docs(remediation): authorize T-CI-2 frontend test gate`
2. `fix(ci): run frontend tests on every pull request`

Push `codex/t-ci-2-frontend-tests`, open one PR titled
`T-CI-2: Run frontend tests in CI`, request review, and wait for both
`python-guardrails` and `frontend-tests`.

Dependabot PR #114 remains separate. After T-CI-2 merges, update its branch so
the new frontend check validates Next.js 16.2.11 and supplies the live
frontend-change demonstration. The subsequent T-CI-2A planning PR changes
only non-frontend policy documents and supplies the non-frontend
demonstration. Do not update the ruleset until both checks are terminal and
green.

Read back the unchanged Python-only ruleset before delivery:

```bash
gh api repos/manumissio/town-council/rulesets/19594795 |
  jq -e '
    [.rules[] | select(.type == "required_status_checks") | .parameters] ==
    [{
      "do_not_enforce_on_create": true,
      "required_status_checks": [{
        "context": "python-guardrails",
        "integration_id": 15368
      }],
      "strict_required_status_checks_policy": true
    }]
  '
```

Expected required checks remain exactly:

The comparison exits zero only when `python-guardrails` is the sole required
context, integration ID `15368` is preserved, strict checking remains enabled,
and branch creation remains exempt.

**v) Rollback.**

```bash
git switch master
git merge --ff-only origin/master
git revert -m 1 <t_ci_2_merge_commit_sha>
./.venv/bin/ruff check .
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/pytest -q
test ! -e .github/workflows/frontend-tests.yml
gh api repos/manumissio/town-council/rulesets/19594795 |
  jq -e '
    [.rules[] | select(.type == "required_status_checks") | .parameters] ==
    [{
      "do_not_enforce_on_create": true,
      "required_status_checks": [{
        "context": "python-guardrails",
        "integration_id": 15368
      }],
      "strict_required_status_checks_policy": true
    }]
  '
```

No migration, data remediation, dependency rollback, or external-state
cleanup is required. Rollback knowingly removes the frontend merge signal;
ruleset 19594795 must still require only `python-guardrails`.

**w) Docs synchronization.**

- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`: version 1.9, corrected T-CI-2
  runner and ownership, completed task statuses, and G3-only Phase 2 blocker.
- `docs/plans/T_CI_2_FRONTEND_TESTS_PLAN.md`: this implementation plan.
- `docs/TESTING.MD`: remove only the T-CI-2 transition from the frontend test
  location sentence.
- `AGENTS.md`: unchanged; T-CI-2A owns its combined frontend-required-check
  transition marker.
- Architecture review, README, ADR, operations, security, and data-governance
  docs: unchanged.

## 7. Delivery Self-Audit

**x) Antipattern scan, diff pass.** Re-run A-F and H. Reject any third-party
runner, new dependency, runner config, package-lock edit, weakened frontend
assertion, path-filtered workflow, failure masking, ruleset update, coverage
flag, runtime CSP edit, unrelated formatting, or file outside ownership.

**y) Evidence required at delivery.**

- Missing-script and stale-CSP red evidence.
- Tests-first repository guardrail red evidence.
- Node and npm versions.
- `npm test` file and assertion totals.
- Ruff, formatter, pre-commit, Mypy, targeted Python, docs-link, and complete
  Python-suite outcomes.
- Independent planning and pre-commit review findings with applied fixes.
- CI outcomes for `python-guardrails`, `frontend-tests`, and CodeQL.
- A green frontend-change check on PR #114 and a green non-frontend check on
  the later T-CI-2A planning PR before any ruleset update.
- Commit hashes, PR URL, unresolved-thread count, and final CI state.
- Browser stage: not applicable because runtime UI behavior does not change.

**z) Deviations.** Authorized corrections are the switch from stale
Jest/Vitest planning to the existing Node runner, narrow CSP test repointing,
planning-document ownership, and current task-status text. Any package-lock
edit, dependency addition, runtime proxy/config change, new frontend
assertion, ruleset update, coverage addition, skipped review, unresolved
P1/P2, or unrun required check is a blocker.
