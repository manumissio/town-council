# T-PLAT-1A: Make Migration Outcomes Visible

`artifact_contract: ce-unified-plan/v1`

`artifact_readiness: implementation-ready`

`execution: code`

## 1. Context & Alignment

**a) Driver.** PR #150 established the Alembic baseline, but a late review
finding identified an operator-visible defect. `pipeline/db_migrate.py` emits
the migration outcome at INFO while its direct CLI entrypoint never configures
logging. Python therefore discards the status, revision, and retired-vector
count that `docs/OPERATIONS.md` uses to determine whether embedding
rehydration is required.

**b) Canonical documents consulted.**

- `AGENTS.md` requires CLI behavior to match operational documentation,
  import-time side effects to remain absent, and review findings to be resolved
  with fresh evidence.
- `docs/TESTING.MD` permits subprocess verification and database factory
  substitution at the implementation-module lookup.
- `docs/ENGINEERING_GUARDRAILS.md` requires Ruff, Mypy, import-side-effect,
  and repository contract enforcement.
- `docs/OPERATIONS.md` treats `retired_catalog_vector_count` as the decision
  input for derived-vector rehydration.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` owns Alembic adoption in
  T-PLAT-1 and requires a separately registered follow-up.
- `docs/reviews/architecture-review-2026-07-19.html` requires one canonical
  migration entrypoint and observable operational outcomes.

**c) Remediation alignment.** T-PLAT-1A is the closure task for the late
PR #150 P2. It owns exactly:

- `docs/plans/T_PLAT_1A_MIGRATION_OUTCOME_VISIBILITY_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `pipeline/db_migrate.py`
- `tests/test_db_migrate.py`
- `tests/test_alembic_migrations.py`

The task registration and plan are committed before runtime implementation.

**d) Decision-gate check.** No G1-G5 decision is required or foreclosed. G5
already approved Alembic adoption. This task changes CLI visibility only, not
migration policy or database state.

## 2. Design

**e) Step-by-step approach.**

1. Register T-PLAT-1A and commit this implementation-ready plan.
2. Add a subprocess test that replaces only the database engine factory with
   a SQLite-dialect fake, invokes the CLI `main()`, and requires the structured
   zero-count migration outcome on stderr.
3. Add focused success and failure tests proving `migrate()` always disposes
   the engine and propagates migration failures.
4. Add a PostgreSQL acceptance test that creates an unversioned legacy
   catalog vector, invokes the real CLI subprocess, and requires
   `retired_catalog_vector_count=1` on stderr.
5. Run the new tests red because `main()` does not exist and INFO remains
   disabled.
6. Reuse `pipeline.cli_logging.configure_cli_logging` and the established
   CLI-only pattern from `db_init.py`.
7. Add `LOGGER_FORMAT`, a focused `_configure_cli_logging()`, and
   `main() -> int`.
8. Have `main()` configure INFO logging, call the unchanged `migrate()`, and
   return zero. Use `raise SystemExit(main())` under the existing
   `if __name__ == "__main__"` guard.
9. Preserve migration exception propagation and engine disposal.
10. Run targeted migration, import-side-effect, docs-link, and complete-suite
   verification.
11. Obtain fresh subagent review before commit, apply every eligible P1/P2,
   then rerun affected checks.
12. Commit, push, open one PR, reply to the late PR #150 review thread with
    the follow-up evidence, and watch CI to a decided state.

Each new function owns one concern. Imports continue from the CLI facade to
the shared logging helper and migration implementation; helpers do not import
the facade.

**f) Reuse audit.** Reuse `configure_cli_logging`, the established CLI
entrypoint pattern, `MigrationOutcome`, and the existing migration logger.
Do not add a logging wrapper, callback, return-value alias, compatibility path,
or second migration implementation.

Rejected alternatives:

- Raise the migration logger to WARNING: rejected because successful
  migrations are informational, and severity inflation would distort logs.
- Use `print()` inside `migrate_database()`: rejected because the
  implementation is also called programmatically and must not own CLI output.
- Configure logging at import time: rejected because Celery prefork and
  guardrail policy forbid import-time global side effects.
- Return a second result from `migrate()`: rejected because the existing
  operation already logs the typed result and no caller needs a new contract.

**g) Data contracts.** No application or database contract changes. The CLI
now guarantees one INFO record with `status`, `revision`, and
`retired_catalog_vector_count` after success. Exceptions still propagate and
produce a nonzero process exit. `migrate()` remains `-> None`.

**h) Schema and migrations.** None. The task does not execute new DDL or add
an Alembic revision.

## 3. Security & Data Governance

**i) Security boundary.** No `AGENTS.md` security-sensitive path is touched.
The additional output contains migration state and a count, not credentials
or document content. An attacker gains no new capability.

**j) Secrets.** No credential, key, environment variable, or default is added
or logged.

**k) Person data.** No person-level data is created, linked, aggregated, or
exposed. G4 is unaffected.

**l) Untrusted input.** No scraped content, provider response, HTML, or user
input is parsed. The subprocess test supplies a test-only database factory.

## 4. Code Health

**m) GED conformance sweep.** New functions have no parameters, complete
annotations, no nested branches, and one responsibility. The log format is a
named constant. No error handler, timestamp, environment read, broad exception,
or database behavior changes.

**n) Antipattern scan, plan pass.**

- A1/H1: the repository's installed `logging.basicConfig` wrapper and existing
  `db_init.py` pattern define the verified API.
- B1/F1: reuse the existing helper instead of adding logging machinery.
- B2/C1: `migrate()` remains the single programmatic operation; `main()` is
  only the standard CLI boundary, not a compatibility path.
- D2: the test asserts process exit and stderr, not helper calls.
- D3: the structured log fields are the operator-visible contract.
- H4: logging is configured only inside `main()`.
- A2-A4, B3, C2, D1, E1-E3, F2, and H2-H3: no planned violations.

**o) Ratchet interaction.** `pipeline/db_migrate.py` and
`tests/test_db_migrate.py` have no Ruff per-file selectors or BLE001
boundaries. No exception is added or widened.

**p) Dead code and duplication audit.** No code becomes dead. The CLI logging
pattern is reused through the existing shared helper. Expected production
delta is one constant and two small CLI functions.

## 5. Testing

**q) Edge and failure scenarios.**

1. Direct CLI execution keeps INFO logging disabled.
2. A successful no-op migration omits status or revision.
3. A zero retired-vector count is omitted because it is falsey.
4. A real unversioned adoption retires a vector but does not display count one.
5. Importing `pipeline.db_migrate` configures global logging.
6. Migration exceptions are swallowed or converted to success.
7. The engine is not disposed after success or failure.
8. Programmatic callers unexpectedly configure logging.

**r) Tests and evidence.**

| Test or command | Scenarios |
|---|---|
| New isolated SQLite CLI subprocess test | 1-3 |
| New PostgreSQL CLI adoption test | 4 |
| Existing import-side-effect guardrails | 5, 8 |
| New migration failure/disposal tests | 6, 7 |
| Complete Python suite | 1-8 regression sweep |

The subprocess test is added and run red before the implementation edit.

**s) Fakes and mocks.** Unit tests replace `db_connect` where
`pipeline.db_migrate` looks it up. This is the approved database factory
boundary from `docs/TESTING.MD`. The fake engines select the existing
`not_applicable` and failure paths; no migration implementation is patched.
The nonzero test uses an isolated real PostgreSQL database and the real CLI.

**t) Verification rows.** Apply docs-only verification and the typed-subtree
row because `pipeline/db_migrate.py` changes. Run migration-focused tests,
the import-side-effect guardrail, and the complete Python suite before
handoff.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-plat-1a-migration-outcome-visibility
```

Tests-first red evidence:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_db_migrate.py::test_db_migrate_cli_reports_migration_outcome \
  tests/test_alembic_migrations.py::test_cli_reports_retired_legacy_vectors
```

Final verification:

```bash
./.venv/bin/ruff check .
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_db_migrate.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_alembic_migrations.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_pipeline_import_side_effects.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/pytest -q
git diff --check
git status --short
```

Delivery uses two commits:

1. `docs(remediation): authorize migration outcome visibility`
2. `fix(db): show migration outcomes in CLI runs`

**v) Rollback.** Revert the T-PLAT-1A merge commit and rerun the same targeted
and full verification. No migration reversal or data remediation is required.
Rollback knowingly restores invisible successful migration outcomes; operators
must inspect the database manually before deciding on rehydration.

**w) Docs synchronization.** Add this plan and update only the remediation
ledger's version, changelog, task status, T-PLAT-1 acceptance state,
T-PLAT-1A entry, and execution order. Existing operations instructions remain
correct once the CLI output is fixed. README, ADR, architecture, testing,
guardrails, security, and data-governance docs remain unchanged.

## 7. Delivery Self-Audit

**x) Antipattern scan, diff pass.** Re-run A-F and H. Reject import-time
logging, print calls in migration implementation, new result wrappers,
exception swallowing, test call-count assertions, unrelated formatting, or
edits outside the four owned files.

**y) Evidence.** Report the expected red test, stderr outcome, targeted and
full verification, planning and pre-commit review findings, commit hashes,
PR URL, thread response, unresolved-thread count, and CI state. Mark anything
unrun as `NOT VERIFIED`.

**z) Deviations.** Expected result is none. Any additional file, changed
migration behavior, skipped review, unresolved P1/P2, or unrun required check
is a blocker.
