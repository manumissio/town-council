# T-CI-1: Make the Complete Python Suite a CI Merge Gate

artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
execution: code
task: T-CI-1
lane: CI

## 1. Context & Alignment

T-CI-5 is merged. Python Guardrails runs static checks and seven fast-fail
test files, but not the complete Python suite. T-CI-1 adds that gate before
Phase 2 architecture work; G3 remains a separate prerequisite.

Canonical constraints come from `AGENTS.md`, `docs/TESTING.MD`,
`docs/ENGINEERING_GUARDRAILS.md`, the remediation plan, and the architecture
review. This task owns exactly the five files registered in remediation plan
v1.6. No G1-G5 decision is required.

## 2. Design

1. Add contract tests before workflow or runbook edits.
2. Confirm the tests fail because the complete suite, crawler dependency
   installation, pytest configuration triggers, and updated runbook claim are
   absent.
3. Add `pytest.ini` to both workflow event path lists.
4. Install `council_crawler/requirements.txt` in the existing dependency step.
5. Add a distinct `Run full Python test suite` step after `Run guardrail tests`:

   ```yaml
   - name: Run full Python test suite
     run: PYTHONPATH=. python -m pytest -q tests/
   ```

6. Update the guardrail runbook to describe the complete Python CI gate while
   preserving T-CI-2, T-CI-3, and T-CI-4 transition boundaries.
7. Run local gates, independent simplification, pre-commit review, PR delivery,
   and CI babysitting.

Reuse the existing job, path parser, tests, and pinned requirements. Do not add
a YAML parser, actionlint, a second job, caching, retries, coverage, or runtime
code. No application contract, schema, migration, or default changes.

## 3. Security & Data Governance

The workflow retains `contents: read`, uses no secrets, and gains no elevated
permission. Pull-request code remains untrusted CI input in an ephemeral
runner. Existing pinned crawler dependencies are added to the test environment.
No person data or scraped-content boundary changes.

## 4. Code Health

No production functions change. Exact workflow command assertions are the
observable CI contract. Ruff selectors, BLE001 boundaries, formatter scope,
Mypy scope, and coverage policy remain unchanged. Re-running the seven
fast-fail tests in the complete suite is deliberate staging, not duplicate
implementation.

Plan antipattern scan: no invented API, new setting, compatibility path,
wrapper, parser framework, weakened assertion, test seam, duplicated
implementation, type suppression, or import-time behavior. Context7 verified
GitHub Actions default step sequencing and pytest 9 `python -m pytest` behavior.

## 5. Testing

Add tests proving:

- the seven fast-fail commands remain together and precede the complete suite;
- the complete command appears exactly once in a distinct blocking step;
- neither test step uses `if` or `continue-on-error`;
- the existing workflow installs crawler requirements;
- both workflow events include `pytest.ini`;
- no coverage flags appear before T-CI-3.

Run repository guardrails, docs links, and the complete suite. Optional-package
skips are valid; do not assert a fixed test count. Local pytest 8.3.4 and Scrapy
2.14.1 results are reduced-confidence. The PR workflow using pytest 9.0.3 and
Scrapy 2.16.0 is authoritative.

## 6. Execution, Rollback, Docs

Tests-first command:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_repository_guardrails.py::test_python_guardrail_workflow_runs_complete_suite_after_fast_fail_checks \
  tests/test_repository_guardrails.py::test_python_guardrail_workflow_triggers_for_test_configuration
```

Final verification:

```bash
./.venv/bin/ruff check .
./.venv/bin/pre-commit run ruff --all-files
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/python -m pytest -q tests/
git diff --check
```

Rollback by reverting the T-CI-1 merge commit and rerunning the same checks.
No migration, data repair, or external-state cleanup exists. Update only the
remediation registry, this plan, and the guardrail runbook; leave combined
T-CI-1..3 transition markers and the historical architecture review unchanged.

## 7. Delivery Self-Audit

Reject any extra workflow job, unpinned dependency, failure override, coverage
flag, permission change, formatter or Mypy edit, unrelated test change, or path
outside the five-file ownership set. Report all verification outcomes, local
version limitations, pre-commit review findings, commit hashes, PR URL, CI
state, and deviations. If dependency-aligned master has assertion failures,
stop and report rather than expanding scope.
