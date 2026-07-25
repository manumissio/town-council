# G5: Record Alembic Adoption

## 1. Context & Alignment

**a) Driver.** The operator approved G5 on 2026-07-24. The repository needs a
durable decision record before T-PLAT-1 or T-TIME-2 starts so agents do not
silently choose between Alembic and the existing `migrate_v*` chain.

**b) Canonical documents consulted.**

- `AGENTS.md`: decision gates require operator approval, exact scope, and docs
  synchronization.
- `docs/ADR.md`: accepted architecture decisions live in the indexed ADR log.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`: G5 controls T-PLAT-1 and the
  migration mechanism for T-TIME-2.
- `docs/reviews/architecture-review-2026-07-19.html`: migration compatibility
  strata should change only after the Alembic decision and PostgreSQL parity
  evidence.

**c) Remediation alignment.** This decision-only change owns:

- `docs/plans/G5_ALEMBIC_ADOPTION_DECISION_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `docs/ADR.md`

T-PLAT-1 remains pending and owns Alembic implementation. T-TIME-2 remains
pending and owns the timezone-column migration.

**d) Decision-gate check.** G5 is satisfied by explicit operator approval.
G1-G4 remain unchanged. This record authorizes T-PLAT-1 after the existing
TIME migration work; it does not rewrite T-TIME-2 into an Alembic revision.

## 2. Design

**e) Step-by-step approach.**

1. Record G5 as approved with date and rationale.
2. Preserve the migration sequence: T-TIME-1 updates model declarations,
   T-TIME-2 migrates existing databases through `migrate_v10.py`, then
   T-PLAT-1 establishes the Alembic baseline.
3. Mark T-PLAT-1 as approved and pending, not complete.
4. Add an Accepted ADR that preserves the current migration chain as frozen
   history after the baseline and assigns post-baseline migrations to Alembic.
5. Expand T-PLAT-1 ownership for root configuration, the pinned dependency,
   canonical existing- and fresh-database handoffs, legacy parity repair,
   affected setup and runner tests, and schema-parity tests.
6. Run docs-link and contradiction checks.
7. Obtain an independent pre-commit review and resolve all eligible P1/P2
   findings.

No function or module is added.

**f) Reuse audit.** Extend the existing remediation gate, task, sequencing,
and ADR sections. No second migration registry or implementation plan is
created.

**g) Data contracts.** None.

**h) Schema and migrations.** None in this change. T-TIME-2 remains the final
planned numbered migration. T-PLAT-1 will baseline the resulting schema.

## 3. Security & Data Governance

**i) Security boundary.** None. No runtime or credential path changes.

**j) Secrets.** None.

**k) Person data.** None.

**l) Untrusted input.** None.

## 4. Code Health

**m) GED conformance sweep.** Docs-only, three-file scope. No code, error
handling, timestamps, environment reads, or runtime defaults change.

**n) Antipattern scan, plan pass.** A1/H1 do not apply because no Alembic API
is called. A2-A4, B1-B3, C1-C2, D1-D3, E1-E3, F1-F2, and H2-H4 pass. The
decision does not add compatibility code; it explicitly freezes the old chain
after the future baseline.

**o) Ratchet interaction.** None.

**p) Dead code and duplication audit.** No code is deleted. Conflicting
conditional migration wording is replaced by one sequence. Expected net
change is one plan and short decision updates.

## 5. Testing

**q) Edge and failure scenarios.**

1. G5 remains worded as open or defaulted rather than approved.
2. T-TIME-2 is incorrectly rewritten as an Alembic revision or removed from
   the numbered chain.
3. Sequencing places T-PLAT-1 before the TIME migration work.
4. T-PLAT-1 is incorrectly marked complete.
5. ADR and remediation plan disagree.
6. Added links are broken.
7. Canonical `run_pipeline.py` migration flow bypasses Alembic after adoption.
8. An existing database is stamped despite drift from the frozen baseline
   schema.
9. T-TIME-2 cannot wire v10 into the focused migration runner within ownership.
10. Downgrading below a stamped baseline runs destructive baseline DDL against
    pre-existing tables.
11. A delayed adopter is compared with newer models instead of the immutable
    baseline schema and cannot reach post-baseline upgrades.
12. A fresh PostgreSQL database lacks the pgvector extension when baseline
    table DDL creates vector columns.
13. Planning preserves an internal helper instead of the actual
    `python db_migrate.py` pipeline subprocess contract.

**r) Tests.**

- Docs-link test covers scenario 6.
- Separate positive and negative `rg` checks cover scenarios 1-5 and 7.
- Manual diff review confirms T-PLAT-1 remains pending.
- T-PLAT-1 contract tests must cover scenario 8 with both fresh and
  legacy-migrated database paths.
- Ownership checks cover scenario 9.
- A cross-baseline downgrade test covers scenario 10 and asserts schema and
  representative data remain unchanged.
- Fresh, immediate-adoption, and delayed-adoption PostgreSQL tests cover
  scenarios 11 and 12.
- Pipeline orchestration contract tests cover scenario 13.

**s) Fakes and mocks.** None.

**t) Verification rows.** Docs-only row.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
rg -n "G5 migration_tooling: \\*\\*Approved 2026-07-24" \
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md
rg -n "status: approved; implementation pending" \
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md
rg -n "Migration order is T-TIME-1, T-TIME-2, then T-PLAT-1" \
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md
rg -n "files_owned: alembic/\\*\\* \\(new\\), alembic.ini \\(new\\)" \
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md
rg -n "\\| PLAT.*alembic.ini.*pipeline/db_migrate.py.*docs/OPERATIONS.md.*tests/test_alembic_migrations.py.*tests/test_db_migrate.py" \
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md
rg -n "pipeline/db_init.py.*scripts/dev_up.sh.*README.md.*tests/test_db_init.py.*tests/test_docker_build_contracts.py" \
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md
rg -n "alembic upgrade head" docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md
rg -n "existing database" docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md
rg -n "pipeline/db_migration_runner.py" \
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md
rg -n "only supported existing-database adoption" \
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md
rg -n "unguarded" \
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md
rg -n "downgrade floor" \
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md
rg -n "frozen baseline schema" \
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md
rg -n "adopters use that same frozen comparison" \
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md
rg -n "stamping aborts on nonempty baseline drift" \
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md
rg -n "pgvector extension before baseline table DDL" \
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md
rg -n "python db_migrate.py" \
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md docs/ADR.md
rg -n "Adopt Alembic for schema migrations" docs/ADR.md
rg -n "T-TIME-1 updates timezone-aware model" docs/ADR.md
rg -n "T-TIME-2 converts existing databases" docs/ADR.md
rg -n "T-PLAT-1 establishes the Alembic baseline" docs/ADR.md
! rg -n "depends_on: T-TIME-2|T-TIME-1, T-PLAT-1, then T-TIME-2|T-TIME-2.*Alembic revision" \
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md docs/ADR.md
git diff --check
git status --short
```

After these checks, an independent subagent reviews the complete diff before
commit.

**v) Rollback.** Revert the decision-record commit. No schema, data, runtime,
or external-state remediation is required.

**w) Docs synchronization.**

- Remediation plan: gate, sequence, task status, and changelog.
- ADR: accepted migration-tooling decision.
- Architecture review: unchanged historical artifact.
- Operations: deferred to T-PLAT-1 implementation.

## 7. Delivery Self-Audit

**x) Antipattern scan, diff pass.** Re-run A-F and H. Reject migration code,
new dependencies, out-of-scope docs edits, or claims that Alembic is already
implemented.

**y) Evidence.** Report every command in 6u and the pre-commit review with
`PASS` or `FAIL`. Mark anything unrun as `NOT VERIFIED`.

**z) Deviations.** Expected result: none. Any fourth changed file or migration
implementation is a blocker.
