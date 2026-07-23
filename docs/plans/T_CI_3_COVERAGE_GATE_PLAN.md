# T-CI-3: Enforce the Production Python Coverage Floor

artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
execution: code
task: T-CI-3
lane: CI

## 1. Context & Alignment

**a) Driver.** T-CI-1 made the complete Python suite authoritative, but the
existing `fail_under = 71` setting is not part of the CI command. A bare
coverage run on current `master` reports 90.37% because it counts test code,
which would make the gate easier to satisfy as tests grow. T-CI-3 must enforce
the existing floor against production Python, include subprocess-executed
operator scripts, and keep coverage tooling out of runtime images.

**b) Canonical documents.** `AGENTS.md` `<workflow_contract>`,
`<verification_matrix>`, `<status_reporting_contract>`, and
`<docs_sync_rules>` require exact evidence, config-owned scopes, old/new gate
reporting, and aligned contributor commands. `docs/TESTING.MD` defines the
three verification layers and the 71% floor. `docs/ENGINEERING_GUARDRAILS.md`
requires one machine-readable owner per enforced file set. The remediation
plan places T-CI-3 after T-CI-1 and before Phase 2. The architecture review
requires the Phase 0 safety net before de-facading work begins. The PR #108
postmortem requires durable contract tests for enforcement changes.

**c) Remediation alignment.** T-CI-3 owns exactly:

- `docs/plans/T_CI_3_COVERAGE_GATE_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `AGENTS.md`
- `docs/TESTING.MD`
- `docs/ENGINEERING_GUARDRAILS.md`
- `.github/workflows/python-guardrails.yml`
- `.coveragerc`
- `pipeline/requirements-dev.txt`
- `tests/test_repository_guardrails.py`
- `tests/test_docker_build_contracts.py`

The remediation plan is updated to version 2.3 before implementation. No
other tracked file may change.

**d) Decision gates.** T-CI-3 is the already-authorized Phase 0 coverage gate
and does not depend on or foreclose G1-G5. The threshold remains 71%, so no
new threshold decision is introduced. G3 remains open and continues to block
Phase 2 after this task.

## 2. Design

**e) Approach.**

1. Record current evidence using the checked-in configuration:
   `PYTHONPATH=. .venv/bin/python -m pytest --cov -q tests/` passes but
   reports 90.37% because tests are measured.
2. Validate a production-only configuration before editing. The selected
   contract reports 81.03% on current `master` and includes all 360 currently
   tracked production Python files.
3. Add failing contract tests before changing configuration, dependencies,
   workflow, or policy docs.
4. Make `.coveragerc` the sole coverage-scope owner:
   - `source = .` automatically enrolls new repository Python.
   - omit `tests/*`, `archive/*`, `experiments/*`, and `.venv*/*`.
   - retain `branch = False` and `fail_under = 71`.
   - add `patch = subprocess` for pytest-cov 7 and coverage.py 7.
   - add `include_namespace_packages = True` so unexecuted Python below
     namespace-style directories remains reportable.
5. Pin `pytest-cov==7.0.0` and `coverage==7.13.3` in
   `pipeline/requirements-dev.txt`. Keep both absent from all runtime
   requirement files.
6. Replace only the `Run full Python test suite` command with:

   ```bash
   PYTHONPATH=. python -m pytest -q --cov \
     --cov-config=.coveragerc \
     --cov-report=term-missing:skip-covered \
     tests/
   ```

   Bare `--cov` is deliberate: pytest-cov documents that `--cov=SOURCE`
   overrides coverage.py's configured source list.
7. Keep the seven-command fast-fail step outside coverage so early diagnostics
   remain fast and the authoritative run measures the suite once.
8. Replace the temporary "coverage absent" workflow assertion with exact
   coverage-command, source, omission, namespace-package, subprocess,
   threshold, and dependency contracts.
9. Add an executable inventory regression. It runs pinned coverage against one
   tracked production module, generates a JSON report, and compares its file
   keys with dynamically discovered tracked production Python after the
   configured omission classes. This catches configuration that parses
   correctly but silently drops unexecuted namespace-package files. The test
   stores its data, config, and report under `tmp_path` and removes
   `COVERAGE_PROCESS_CONFIG` and `COVERAGE_PROCESS_START` from the child
   environment so an outer coverage-enabled suite cannot create nested
   collectors.
10. Remove completed T-CI-3 transition markers and add the coverage command to
   testing and guardrail policy without duplicating its file inventory.
11. Run complete verification, simplify the diff, and obtain an independent
    pre-commit review. Apply every eligible P1/P2 before delivery.

No production function, helper module, facade, environment variable, runtime
dependency, or external coverage service is added.

**f) Reuse audit.** Extend the existing Python Guardrails job, `.coveragerc`,
development requirement file, workflow contract test, runtime dependency
contract test, and canonical policy docs. No YAML parser, coverage wrapper,
source registry, compatibility path, or custom reporting utility is created.

Rejected alternatives:

- Bare `--cov` with the current config: rejected because it counts tests and
  inflates current coverage from 81.03% to 90.37%.
- Repeated `--cov=SOURCE`: rejected because it moves scope into CI and
  overrides `.coveragerc`.
- An explicit production-directory list: rejected because it would require
  maintenance whenever a new production directory or root module lands.
- Coverage in the fast-fail step: rejected because the same tests would be
  measured twice and early feedback would slow down.
- Coverage upload service: rejected because the task needs a local merge gate,
  not a new network dependency or credential boundary.

**g) Contracts.**

- Scope contract: all repository Python under `source = .`, excluding only
  configured non-production and local-environment paths. Namespace-package
  discovery keeps unexecuted tracked files in the report.
- Gate contract: coverage.py exits nonzero when total production coverage is
  below 71%.
- Subprocess contract: coverage.py patches Python subprocess startup;
  pytest-cov combines measured process data.
- Dependency contract: coverage tooling is development-only.
- CI contract: the fast-fail tests precede one authoritative coverage-enabled
  complete-suite step.

No application API, schema, Celery signature, CLI, runtime default, inference
policy, or soak baseline changes.

**h) Schema and migrations.** None.

## 3. Security & Data Governance

**i) Security boundary.** No `AGENTS.md` security-sensitive path is touched.
Workflow permissions remain `contents: read`; no secrets or external upload
step is introduced. Measuring more production code reduces untested-change
risk without altering execution privileges.

**j) Secrets.** None added, read, logged, or exposed.

**k) Person data.** None created, linked, aggregated, or exposed. G4 is
unaffected.

**l) Untrusted input.** Pull-request code and tests remain untrusted CI input.
The workflow installs checked-in pinned development dependencies and runs them
in GitHub's ephemeral runner. No scraped content, provider response, user
payload, or external coverage artifact is parsed by new application code.

## 4. Code Health

**m) Conformance.** No production Python logic, timestamp, environment read,
exception handler, or runtime literal changes. Test additions use
`configparser` and `pathlib.Path`, have complete annotations where helpers are
needed, and assert checked-in policy rather than private production state.

**n) Antipattern scan, plan pass.**

- A1/H1 corrected: installed pytest-cov 7.0.0 and coverage.py 7.13.3 match the
  proposed pins. Context7 verified bare `--cov`, `--cov-config`,
  `--cov-report`, configured source behavior, `patch = subprocess`, and
  `fail_under` exit status.
- A3 corrected: 90.37% and 81.03% are fresh local measurements; the final PR
  report must distinguish local pytest 8.3.4 from authoritative CI pytest
  9.0.3.
- B1/F1 corrected: `.coveragerc` remains the single policy owner; no wrapper,
  manager, parser framework, or duplicate source inventory is added.
- D1 corrected: the threshold remains 71%; no skip, xfail, retry, or tolerance
  changes.
- D3 accepted narrowly: exact workflow and config assertions are the
  observable merge-gate contract.
- E1/E2 corrected: only the ten owned files may change.
- A2, A4, B2-B3, C1-C2, D2, E3, F2, and H2-H4 do not apply.

**o) Ratchets.**

- Coverage threshold: 71% configured but unenforced -> 71% enforced in CI.
- Measured scope: implicit pytest-cov discovery that counts tests ->
  repository production Python with four omission classes.
- Branch coverage: unchanged at false.
- Ruff selectors, BLE001 boundaries, formatter scope, Mypy scope, test
  selection, workflow triggers, required-check policy, and permissions:
  unchanged.

**p) Dead code and duplication.** Delete the temporary assertion that coverage
is absent and the completed transition markers. Reuse the existing full-suite
step rather than adding another job or test run. Expected net growth is one
implementation plan plus focused policy tests and configuration.

## 5. Testing

**q) Edge and failure scenarios.**

1. Tests or archived Python inflate the total.
2. A new production directory is omitted from measurement.
3. The repository-root diagnostic wrapper is omitted.
4. Unexecuted files under namespace-style directories are omitted.
5. Python subprocesses execute production scripts without measurement.
6. CI uses `--cov=SOURCE` and overrides `.coveragerc`.
7. CI stops using the checked-in coverage config or actionable terminal
   report.
8. Coverage falls below 71% but the job passes.
9. Coverage packages enter a runtime requirement file.
10. Fast-fail tests gain coverage overhead or move after the complete suite.
11. Workflow triggers, permissions, static checks, formatter, Mypy, or
    required-check identity drift.
12. Dependency installation omits the pinned coverage packages.
13. Local installed versions differ from CI; local results must be reported
    as reduced confidence rather than treated as authoritative.

**r) Tests.**

| Test or command | Scenarios |
|---|---|
| Updated complete-suite workflow contract | 6-8, 10-12 |
| New `.coveragerc` contract test | 1-8 |
| `test_coverage_configuration_reports_every_tracked_production_python_file` | 1-4 |
| Runtime/development dependency contract | 9, 12 |
| Existing workflow trigger and check-identity tests | 10-11 |
| Actual production-only coverage command | 1-8, 13 |
| Repository guardrail and Docker contract suites | 1-12 |
| PR Python Guardrails check | 1-13 |

Tests are written and run red before implementation. No fixed collected-test
count is asserted.

The dependency contract parses `api/requirements.txt`,
`council_crawler/requirements.txt`, `pipeline/requirements.txt`,
`pipeline/requirements-batch.txt`, and
`semantic_service/requirements.txt`; normalizes distribution names; requires
`coverage` and `pytest-cov` to be absent from each runtime surface; and
requires the exact two development pins.

**s) Fakes and mocks.** None. Tests use approved filesystem and subprocess
boundaries and patch no facade, re-export, or implementation symbol.

**t) Verification rows.** Apply the guardrail/tooling and docs-only rows.
Run the Docker dependency contract test and the complete Python suite under
the coverage gate. The PR's Python Guardrails run is authoritative for Python
3.14, pytest 9.0.3, pytest-cov 7.0.0, and coverage.py 7.13.3.

## 6. Execution, Rollback, Docs

**u) Commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-ci-3-coverage-gate
```

Baseline evidence:

```bash
PYTHONPATH=. .venv/bin/python -m pytest --cov -q tests/
```

Expected on pre-change `master`: the suite passes and reports an inflated
90.37% because test files are included.

Tests-first red evidence:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_repository_guardrails.py::test_python_guardrail_workflow_enforces_production_coverage \
  tests/test_repository_guardrails.py::test_coverage_configuration_measures_repository_production_python \
  tests/test_repository_guardrails.py::test_coverage_configuration_reports_every_tracked_production_python_file \
  tests/test_docker_build_contracts.py::test_coverage_tooling_is_development_only
```

Final verification:

```bash
./.venv/bin/ruff check .
./.venv/bin/ruff format --check . --config ruff-format.toml
./.venv/bin/pre-commit run ruff --all-files
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docker_build_contracts.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/python -m pytest -q --cov \
  --cov-config=.coveragerc \
  --cov-report=term-missing:skip-covered \
  tests/
git diff --check
git status --short
```

Delivery uses two commits:

1. `docs(remediation): authorize T-CI-3 coverage enforcement`
2. `fix(ci): enforce the production Python coverage floor`

Push `codex/t-ci-3-coverage-gate`, open one PR titled
`T-CI-3: Enforce the production Python coverage floor`, request Codex review,
and watch CI until every check is decided. Browser testing is not applicable.

**v) Rollback.** Revert the T-CI-3 merge commit, then rerun Ruff, formatter,
Mypy, repository guardrails, Docker contracts, docs links, and the complete
suite. No migration, data repair, environment restoration, external artifact,
or ruleset mutation exists. Rollback knowingly restores the configured but
unenforced 71% floor.

**w) Docs synchronization.**

- `AGENTS.md`: authoritative Python merge-gate wording and coverage command.
- `docs/TESTING.MD`: remove completed T-CI-3 markers and document the
  production-only command.
- `docs/ENGINEERING_GUARDRAILS.md`: point coverage scope to `.coveragerc` and
  state that CI enforces the floor.
- Remediation plan: version 2.3, expanded ownership, corrected measurement
  semantics, and acceptance criteria.
- README, ADR, architecture review, operations, API contracts, security, and
  data-governance docs: no changes.

## 7. Delivery Self-Audit

**x) Diff scan.** Re-run A-F and H. Reject any threshold change, branch
coverage change, explicit `--cov=SOURCE`, duplicated source list, runtime
coverage dependency, external upload, workflow job or permission change,
fast-fail modification, skip/xfail/retry, unrelated formatting, type
suppression, or edit outside the ten-file ownership set.

**y) Evidence required.** Report the tests-first failures; Ruff, formatter,
pre-commit, Mypy, repository guardrail, Docker contract, docs-link, and
coverage-suite outcomes; exact pass/skip/fail counts; measured percentage;
local and CI package versions; independent planning and pre-commit review
findings; commit hashes; PR URL; unresolved-thread count; and final CI state.
Anything unrun is `NOT VERIFIED`.

**z) Deviations.** Expected authorized changes are the ten-file ownership
expansion, production-only scope, namespace-package discovery, executable
inventory check, subprocess patch, two direct development pins, workflow
command replacement, and completed transition-marker removal.
Any other changed path, threshold adjustment, workflow-step change, skipped
review, unresolved P1/P2, or unrun required check is a blocker and must be
reported.
