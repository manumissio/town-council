# T-GOV-3B: Enforce Remaining Structural Guardrails

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: implementation-ready`
`execution: code`

## 1. Context & Alignment

**a) Driver.** T-GOV-3A replaced file-length limits with dependency-direction
rules, but the structural policy remains transitional. T-DC-1 and T-DE-1 have
now removed the active reverse dependencies. T-GOV-3B must register those clean
boundaries, mechanically reject top-level private `_sync_*_from_*` functions,
and reject direct f-string interpolation passed to SQLAlchemy `text(...)`.

**b) Canonical documents consulted.**

- `AGENTS.md` `<known_antipatterns>`, `<workflow_contract>`, and
  `<verification_matrix>` require durable structural enforcement, tests-first
  delivery, and complete guardrail verification.
- `docs/TESTING.MD` permits filesystem and subprocess checks without production
  test seams.
- `docs/ENGINEERING_GUARDRAILS.md` defines the transitional structural rules
  and requires config-owned scan scopes.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` makes T-GOV-3B the final
  acceptance task for T-GOV-3.
- T-DC-1 establishes `api.main -> api.app_setup ->
  api.search.semantic_support`.
- T-DE-1 establishes direct implementation ownership beneath
  `pipeline.llm_provider`.
- `docs/reviews/architecture-review-2026-07-19.html` recommends replacing
  facade-preserving proxies with enforceable dependency rules.

**c) Remediation alignment.** T-GOV-3B owns exactly:

- `docs/plans/T_GOV_3B_STRUCTURAL_GUARDRAILS_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `docs/ENGINEERING_GUARDRAILS.md`
- `tests/test_repository_guardrails.py`
- `tests/test_api_startup_security.py`
- `tests/test_inference_provider_protocol_contract.py`

No production source, Ruff configuration, workflow, API, schema, or runtime
file may change.

**d) Decision gates.** G3 is satisfied. T-DC-1 and revised T-DE-1 are complete.
The operator approved T-GOV-3B planning, ownership, and implementation on
2026-07-30. No G1-G5 decision remains.

## 2. Design

**e) Step-by-step approach.**

1. Mark merged T-PLAT-2C complete, then register T-GOV-3B as active with exact
   ownership.
2. Add failing tests for the two structural rules, the four new dependency
   registrations, and final T-GOV-3 policy status.
3. Extend `HELPER_FACADE_IMPORT_RULES` with:
   - `api/app_setup.py` must not import `api.main`;
   - `pipeline/http_inference_provider.py` must not import
     `pipeline.llm_provider`;
   - `pipeline/provider_telemetry.py` must not import
     `pipeline.llm_provider`;
   - `pipeline/agenda_segmentation_maintenance.py` must not import
     `pipeline.llm_provider`.
4. Remove superseded source-string assertions for these synchronization and
   reverse-import rules from their domain tests. Keep their runtime and facade
   compatibility assertions.
5. Add a test-local AST helper that reports every top-level function or async
   function following `_sync_<owner>_from_<peer>`. A one-way function is also
   prohibited so synchronization debt cannot land in stages. Nested functions,
   methods, and names outside that private convention remain allowed.
6. Add test-local AST helpers that resolve direct and module-qualified
   SQLAlchemy `text` imports in each call's ancestor lexical scopes and report
   positional or `text=` f-string arguments. Scan
   Ruff-discovered production Python files, including repository-root modules
   and `alembic/**`, while excluding tests, archive, and experiments. Treat all
   direct SQLAlchemy `text(f"...")` calls as prohibited because static segments
   cannot reliably classify dynamically assembled SQL as read or mutation.
   Do not treat imports from sibling scopes as aliases, trace values through
   variables, or model rebinding and statement order.
7. Add focused positive and negative tests:
   - single, reciprocal, and async top-level sync names fail;
   - nested functions, methods, and nonmatching names remain allowed;
   - `from sqlalchemy import text`, aliased direct imports,
     `from sqlalchemy.sql import text`, aliased `sqlalchemy.sql` imports,
     `import sqlalchemy`, `import sqlalchemy as sa`,
     `import sqlalchemy.sql as sql`, and deeper qualified module aliases all
     reject direct positional or keyword `text(f"...")` calls;
   - later assignments, function defaults, and comprehension targets cannot
     hide an earlier direct SQLAlchemy call;
   - literal SQL, non-SQLAlchemy helpers, and directive text inside strings do
     not fail.
8. Enforce both rules against the current repository. No exceptions or
   allowlists are permitted.
9. Remove the T-GOV-3 transition marker from the guardrail policy, narrow the
   policy to the enforceable named structures, and assert that policy:
   - has no `[transition: T-GOV-3]` marker;
   - no longer claims generic duplicated-global detection;
   - covers all direct SQLAlchemy `text(f"...")` calls, not only DDL/DML;
   - prohibits one-way top-level `_sync_*_from_*` functions.
   Mark T-GOV-3/T-GOV-3B complete only after enforcement passes.
10. Run static checks, repository guardrails, docs links, and the coverage-gated
   complete Python suite.
11. Run simplification and independent pre-commit review, apply eligible
    findings, commit atomically, push, open a PR, and watch CI and review to a
    decided state.

New test-local responsibilities:

- `_top_level_sync_function_lines`: report top-level functions matching the
  prohibited private synchronization convention.
- `_sqlalchemy_import_bindings`: resolve direct and module-qualified names
  that reference SQLAlchemy's `text` callable.
- `_scope_sqlalchemy_text_bindings`: keep alias identity within the call's
  ancestor lexical scopes without attempting value-flow analysis.
- `_interpolated_sqlalchemy_text_lines`: report direct f-string arguments to
  those resolved callables.
- `_is_production_structural_path`: preserve the explicit non-production
  exclusions while keeping repository-root and Alembic Python in scope.

**f) Reuse audit.** Reuse `_broad_exception_scan_files()` for Ruff-owned Python
discovery, `_forbidden_imports()` for dependency direction, existing AST
parsing patterns, and `HELPER_FACADE_IMPORT_RULES` as the single registry. A new
module or second scope registry is not justified.

Rejected alternatives:

- Add a Ruff plugin or standalone scanner: unnecessary machinery for two
  repository contracts.
- Search source text with regular expressions: cannot distinguish comments,
  strings, aliases, or unrelated `text` helpers.
- Build variable/data-flow tracking for SQL statements: unsound at repository
  test scale and repeats the partial-analyzer mistake retired in T-GOV-3A.
- Add exceptions for current files: rejected because current production code
  has no violations.

**g) Contracts.** No application data contract changes. The developer contract
gains two enforced structural prohibitions and four registered import
directions. Scan scope remains derived from Ruff.

**h) Schema and migrations.** None.

## 3. Security & Data Governance

**i) Security boundary.** No security-sensitive production path changes.
Rejecting interpolated SQLAlchemy text reduces future SQL-injection risk, but
does not alter current query execution or trust boundaries.

**j) Secrets.** None.

**k) Person data.** None. G4 and T-GOV-2A are unaffected.

**l) Untrusted input.** Guardrail tests parse tracked Python source with
`ast.parse`. Scraped content and runtime requests are not involved.

## 4. Code Health

**m) Conformance.** New helpers are test-local, typed, single-purpose, and use
`pathlib.Path`. Each function remains below the enforced complexity ceiling.
No environment read, timestamp, broad exception, type suppression, or runtime
literal is added.

**n) Antipattern scan, plan pass.**

- A1/H1: only Python standard-library AST APIs and existing repository helpers
  are used.
- B1/F1: no plugin, parser framework, registry duplicate, or utility module.
- B3: checks target only structures explicitly named by T-GOV-3B.
- C1: the transition marker is deleted when its replacement rules land.
- D1-D3: tests plant observable source examples and do not weaken policy.
- E1-E3: only six owned files change.
- A2-A4, B2, C2, F2, H2-H4: no planned violations.

**o) Ratchets.** Ruff selectors, BLE001 boundaries, C901 exceptions, typing
scope, formatter scope, and coverage threshold remain unchanged. Structural
rules move from documented transition to enforced acceptance with zero
exceptions.

**p) Dead code and duplication.** Remove transition-only assertions and prose,
two exact sync-name assertions, one exact reverse-import assertion, and one
three-file source-string test superseded by the central registry. Reuse the
existing import registry and Ruff discovery. Expected change is test-heavy with
zero production-code delta.

## 5. Testing

**q) Edge and failure scenarios.**

1. A top-level `_sync_a_from_b` function appears alone or with its reciprocal.
2. Async top-level sync functions are prohibited, while nested functions,
   methods, `_sync_worker_config`, `_sync_helper_test_hooks`, and public
   `sync_rows_from_db` remain allowed.
3. SQLAlchemy `text` is imported directly under its original name.
4. SQLAlchemy `text` is imported under an alias.
5. SQLAlchemy is imported as a module alias and `.text(...)` is called.
6. Literal SQL is passed to SQLAlchemy `text`.
7. An unrelated helper named `text` receives an f-string.
8. Directive-like source appears only inside a string or comment.
9. Any of the four T-DC-1 or T-DE-1 implementations imports backward through
   its facade.
10. Ruff discovers a new production Python file containing either banned
    structure.
11. Tests, archived history, and experiments do not become production
    violations; repository-root and Alembic modules do.
12. T-GOV-3 is marked complete before both checks and dependency registrations
    are present.

**r) Test mapping.**

| Test | Scenarios |
|---|---|
| Top-level sync detector examples | 1, 2, 8 |
| SQLAlchemy text detector examples | 3-8 |
| Repository-wide structural enforcement | 1, 3-5, 10, 11 |
| Registered helper dependency test | 9 |
| T-GOV-3 completion contract | 12 |
| Complete Python suite | Runtime regression check |

**s) Fakes and mocks.** None. Temporary source files use pytest's approved
filesystem boundary. Ruff discovery uses the existing subprocess boundary.

**t) Verification rows.** Apply guardrail/tooling and docs-only rows. Run the
coverage-gated complete Python suite because the guardrail applies across
production Python.

## 6. Execution, Rollback, Docs

**u) Commands.**

```bash
git fetch origin --prune
test "$(git branch --show-current)" = "codex/t-gov-3b-structural-guardrails"
git merge-base --is-ancestor origin/master HEAD
VENV_DIR="$(dirname "$(git rev-parse --git-common-dir)")/.venv"
test -x "$VENV_DIR/bin/python"
ln -s "$VENV_DIR" .venv
```

Tests-first:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_repository_guardrails.py::test_sync_global_guardrail_detects_top_level_functions \
  tests/test_repository_guardrails.py::test_sqlalchemy_text_guardrail_detects_direct_interpolation \
  tests/test_repository_guardrails.py::test_production_python_has_no_banned_structural_smells \
  tests/test_repository_guardrails.py::test_t_gov_3_closes_after_structural_rules_land
```

Final verification:

```bash
./.venv/bin/ruff check .
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/python -m pytest -q \
  --cov --cov-config=.coveragerc \
  --cov-report=term-missing:skip-covered tests/
git diff --check

expected_owned_files=$(
  printf '%s\n' \
    docs/ENGINEERING_GUARDRAILS.md \
    docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md \
    docs/plans/T_GOV_3B_STRUCTURAL_GUARDRAILS_PLAN.md \
    tests/test_api_startup_security.py \
    tests/test_inference_provider_protocol_contract.py \
    tests/test_repository_guardrails.py |
    sort
)
actual_owned_files=$(
  {
    git diff --name-only origin/master
    git ls-files --others --exclude-standard
  } |
    sort
)
test "$actual_owned_files" = "$expected_owned_files"
git status --short --untracked-files=all
```

Remove the ignored `.venv` symlink after verification.

**v) Rollback.** Revert the T-GOV-3B merge commit and rerun Ruff, Mypy,
repository guardrails, docs links, and the complete coverage gate. No
migration, data repair, environment rollback, or external-state cleanup is
required. Rollback knowingly restores the structural transition.

**w) Docs synchronization.**

- Remediation ledger: close merged T-PLAT-2C, register and complete T-GOV-3B,
  and complete umbrella T-GOV-3.
- Engineering Guardrails: remove the transition marker and state that both
  structural checks are active.
- No README, ADR, architecture, operations, testing, security, data-governance,
  API-contract, or runtime documentation changes.

## 7. Delivery Self-Audit

**x) Diff scan.** Re-run A-F/H. Reject production edits, a second scan scope,
partial data-flow machinery, source-text regex enforcement, any allowlist,
Ruff-policy drift, test weakening, or files outside ownership.

**y) Evidence.** Report tests-first red output, all commands from 6u, suite and
coverage totals, planning and pre-commit review findings, commits, PR URL,
unresolved thread count, and final CI state. Mark unrun checks `NOT VERIFIED`.

**z) Deviations.** Expected deviation is the approved activation and completion
of T-GOV-3B and six-file ownership needed to retire superseded domain-specific
assertions. Any extra file, production behavior change, policy exception,
skipped review, unresolved P1/P2, or unrun required gate blocks delivery.
