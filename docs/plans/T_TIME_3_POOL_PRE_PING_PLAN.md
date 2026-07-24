# T-TIME-3: Enable PostgreSQL Pool Pre-Ping

`artifact_contract: ce-unified-plan/v1`  
`artifact_readiness: implementation-ready`  
`execution: code`

## 1. Context & Alignment

**a) Driver.** Long-lived workers can receive a pooled PostgreSQL connection
that the server or network closed while idle. T-TIME-3 enables SQLAlchemy's
pessimistic pre-ping check so stale connections are replaced at checkout
before Town Council starts database work.

**b) Canonical documents consulted.**

- `AGENTS.md` requires fail-fast database configuration, tests-first changes,
  typed-subtree verification, exact delivery evidence, and scope locking.
- `docs/TESTING.md` permits substitution at the database connector boundary
  and requires patching the implementation lookup location.
- `docs/ENGINEERING_GUARDRAILS.md` makes Ruff and Mypy the applicable static
  gates.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` assigns PostgreSQL pre-ping to
  T-TIME-3 in the TIME lane.
- `docs/reviews/architecture-review-2026-07-19.html` identifies connection
  reliability as a Phase 1 closure before broader platform work.

**c) Remediation alignment.** T-TIME-3 owns exactly:

- `docs/plans/T_TIME_3_POOL_PRE_PING_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `pipeline/model_runtime.py`
- `tests/test_database.py`

The remediation ledger moves merged T-CRAWL-2 to complete, moves T-TIME-3 to
in progress, links this plan, and records the ownership expansion before code
changes.

**d) Decision-gate check.** No G1-G5 gate applies. G5 controls migration
tooling; T-TIME-3 changes only connection checkout behavior. T-TIME-1,
T-TIME-2, and T-PLAT-1 are not prerequisites.

## 2. Design

**e) Step-by-step approach.**

1. Update the existing PostgreSQL pooling test first to require
   `pool_pre_ping=True`.
2. Capture the expected red test before changing runtime code.
3. Add `pool_pre_ping=True` only to the PostgreSQL `create_engine` call in
   `pipeline/model_runtime.py`.
4. Preserve explicit SQLite engine creation and the missing-URL fail-fast
   error unchanged.
5. Run targeted database tests, static gates, docs links, and the complete
   coverage-enabled Python suite.
6. Obtain independent pre-commit review, apply eligible findings, and rerun
   affected checks before delivery.

No new function or module is introduced.

**f) Reuse audit.** Extend the existing PostgreSQL branch in
`db_connect_with()` and the existing pooling contract test. Do not add a retry
loop, wrapper, compatibility path, configuration variable, or duplicate
database connector.

**g) Data contracts.**

- Old behavior: PostgreSQL connections are checked out without a liveness
  query.
- New behavior: SQLAlchemy checks each pooled PostgreSQL connection at
  checkout and replaces a stale connection before yielding it.
- Unchanged: SQLite fixtures, missing-URL errors, engine return types, and the
  `pipeline.models.db_connect()` facade.

**h) Schema and migration impact.** None. No column, stored value, timestamp,
or migration ordering changes.

## 3. Security & Data Governance

**i) Security-sensitive paths.** None. Pre-ping uses the existing configured
database connection and does not expand access or network exposure.

**j) Secrets.** No credential, key, environment variable, or default is
added.

**k) Person data.** No person-level data is created, linked, aggregated, or
exposed.

**l) Untrusted input.** `DATABASE_URL` remains the existing environment trust
boundary. Its validation and fail-fast behavior do not change.

## 4. Code Health

**m) GED conformance sweep.** Runtime implementation is one explicit
SQLAlchemy keyword. No function, error handler, timestamp, environment read,
nesting level, import, or domain name changes.

**n) Antipattern scan, plan pass.**

- A1/H1: SQLAlchemy 2.0.38 is pinned locally; current SQLAlchemy 2.0
  documentation confirms `create_engine(..., pool_pre_ping=True)` performs
  pessimistic disconnect handling at checkout.
- D3: the exact keyword assertion is accepted because connection policy is
  the observable contract of `db_connect()`.
- A2-A4, B1-B3, C1-C2, D1-D2, E1-E3, F1-F2, and H2-H4: no planned
  violations.

**o) Ratchet interaction.** `pipeline/model_runtime.py` is in the Mypy typed
subtree and has no Ruff per-file ignore. No exception, threshold, or
allowlist changes.

**p) Dead code and duplication audit.** Nothing is deleted or duplicated.
Expected runtime/test delta is one keyword and one expected argument.

## 5. Testing

**q) Edge and failure scenarios.**

1. PostgreSQL engine creation includes `pool_pre_ping=True`.
2. Existing PostgreSQL pool size, overflow, timeout, and recycle values remain
   unchanged.
3. Explicit SQLite URLs do not receive PostgreSQL pool arguments.
4. Missing `DATABASE_URL` retains the existing `RuntimeError`.
5. Engine-creation failures continue to propagate because no handler is
   introduced.
6. Pre-ping adds one checkout-time liveness query and replaces stale pooled
   connections, but it does not recover a disconnect during an active
   transaction.

**r) Tests.**

- Update `test_db_connect_uses_postgresql_pooling` for scenarios 1 and 2.
- Retain `test_db_connect_allows_explicit_sqlite_url_without_fallback_pooling`
  for scenario 3.
- Retain `test_db_connect_requires_explicit_database_url` for scenario 4.
- Scenario 5 is preserved structurally because the call has no new handler.
- Scenario 6 is documented behavior and requires no integration fixture for
  this keyword-only task.

**s) Fakes and mocks.** The existing `create_engine` mock uses the approved
database boundary and patches the implementation lookup location. No new seam
is added.

**t) Verification rows.** Apply typed-subtree and docs verification, then run
the complete coverage-enabled Python suite because this changes a shared
database connector.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-time-3-pool-pre-ping
```

Tests-first red evidence:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_database.py::test_db_connect_uses_postgresql_pooling
```

Final verification:

```bash
./.venv/bin/ruff check .
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_database.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
COVERAGE_FILE=/private/tmp/tc-t-time-3-coverage \
  PYTHONPATH=. .venv/bin/python -m pytest -q \
  --cov \
  --cov-config=.coveragerc \
  --cov-report=term-missing:skip-covered \
  tests/
git diff --check
git status --short
```

**v) Rollback.** Revert the T-TIME-3 merge commit and rerun the same checks.
No migration reversal, database repair, configuration restoration, or
external cleanup is required. Rollback restores the risk of stale pooled
connections.

**w) Docs synchronization.** Add this plan and update the remediation
ledger's version, changelog, task status, ownership, implementation-plan link,
and checkout-overhead statement. README, ADR, architecture, operations,
security, API contracts, and data-governance docs require no changes.

## 7. Delivery Self-Audit

**x) Antipattern scan, diff pass.** Re-run A-F and H. Reject edits outside the
four owned files, new retry machinery, SQLite policy changes, exception
swallowing, configuration additions, or unrelated formatting.

**y) Evidence.** Report the expected red test, every final command with
PASS/FAIL, complete-suite count and coverage, planning and pre-commit review
findings, commit hashes, PR URL, unresolved review threads, and final CI
state. Mark anything unrun as `NOT VERIFIED`.

**z) Deviations.** Expected deviation from remediation plan v3.9 is the
four-file ownership expansion and task activation. Any additional file,
runtime behavior, unrun required check, or unresolved P1/P2 is a blocker.
