# T-PLAT-1: Establish the Alembic Baseline

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: implementation-ready`
`execution: code`

## 1. Context & Alignment

**a) Driver.** T-TIME-1 and T-TIME-2 are merged, so the final numbered
migration is authoritative on `master`. Town Council now needs one
transactionally guarded migration entrypoint for fresh databases, existing
unversioned databases, and future Alembic revisions. The current path is not
safe enough to stamp: v8 reads mutable application metadata, v8/v9 failures
are logged and swallowed, setup and operational commands can create tables
outside migrations, and legacy-only indexes are absent from model metadata.

**b) Canonical documents consulted.**

- `AGENTS.md`: G5 approval, tests-first work, PostgreSQL evidence, config and
  guardrail verification, no new compatibility seams, and exact reporting.
- `ARCHITECTURE.md`: `pipeline/db_migrate.py` remains the migration facade and
  `pipeline/run_pipeline.py` retains the `python db_migrate.py` subprocess.
- `docs/TESTING.MD`: PostgreSQL is the approved database boundary; tests patch
  implementation modules rather than migration facades.
- `docs/ENGINEERING_GUARDRAILS.md`: SQL identifiers must use SQLAlchemy
  constructs or dialect quoting; broad handlers require an existing boundary.
- `docs/OPERATIONS.md`: existing migration and backup procedures must remain
  fail-fast and locally reproducible.
- `docs/DATA_GOVERNANCE.md`: schema adoption must preserve stored civic data.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`: T-PLAT-1 scope, G5 decision,
  immutable numbered-migration history, and exclusion with T-GOV-3.
- `docs/plans/G5_ALEMBIC_ADOPTION_DECISION_PLAN.md`: Alembic owns every
  post-baseline migration; `migrate_v1` through `migrate_v10` become frozen
  adoption history.
- `docs/reviews/architecture-review-2026-07-19.html`: do not add another
  migration stratum; make one entrypoint authoritative.

**c) Remediation alignment.** This is Phase 3 task T-PLAT-1 in the PLAT lane.
The task-level ownership set is authoritative for this PR:

- `docs/plans/T_PLAT_1_ALEMBIC_BASELINE_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `docs/plans/G5_ALEMBIC_ADOPTION_DECISION_PLAN.md`
- `alembic.ini`
- `alembic/**`
- `pipeline/requirements.txt`
- `pipeline/db_init.py`
- `pipeline/db_migrate.py`
- `pipeline/db_migration_alembic.py` (new)
- `pipeline/db_migration_backfills.py`
- `pipeline/db_migration_runner.py`
- `pipeline/db_schema_contracts.py` (new)
- `pipeline/db_migration_columns.py`
- `pipeline/migrate_v8.py`
- `pipeline/migration_pgvector_semantic_embeddings.py`
- `pipeline/migrate_v9.py`
- `pipeline/migration_catalog_lineage_columns.py`
- `pipeline/migrate_v10.py`
- `pipeline/seed_places.py`
- `pipeline/promote_stage.py`
- `scripts/check_schema_parity.py` (new)
- `scripts/dev_up.sh`
- `README.md` setup section
- `ARCHITECTURE.md` migration map
- `docs/OPERATIONS.md` migration and backup sections
- `docs/PIPELINE.md` migration section
- `docs/CONTRIBUTING_CITIES.md` seed prerequisite
- `.github/workflows/python-guardrails.yml` migration step only
- `tests/test_alembic_migrations.py` (new)
- `tests/test_db_init.py`
- `tests/test_db_migrate.py`
- `tests/test_docker_build_contracts.py` fresh-database contract only
- `tests/test_migrate_v8_pgvector_order.py`
- `tests/test_migrate_v9.py`
- `tests/test_migrate_v10.py`
- `tests/test_seed_places.py`
- `tests/test_seed_places_includes_cupertino.py`
- `tests/test_database.py` promotion handoff only
- `tests/test_pipeline_idempotency.py` promotion handoff only
- `tests/test_pipeline_integration.py` promotion handoff only
- `tests/test_repository_guardrails.py` migration CI contract only
- `tests/test_run_pipeline_orchestration.py` migration prelude only

T-GOV-3 must not run concurrently. The pypdf and PostCSS security alerts are
separate dependency work and must not be hidden in this migration PR.

**d) Decision-gate check.** G5 was approved on 2026-07-24. G1-G4 are not
changed or foreclosed. No open decision gate blocks implementation.

## 2. Design

**e) Step-by-step approach.**

1. Add Alembic `1.18.5` to `pipeline/requirements.txt`, initialize the standard
   Alembic environment, and configure it from the repository-root
   `alembic.ini`. Do not add an environment variable or a second database URL
   parser.
2. Generate the candidate baseline against an isolated, empty PostgreSQL
   database after v10. Manually reconcile the revision with frozen legacy
   behavior. The checked-in revision must contain explicit Alembic operations;
   it must not import mutable application metadata.
3. Make the baseline revision create the `vector` extension before any vector
   column. Include every current table, column, constraint, sequence-backed
   identity, server default, ordinary index, partial index, HNSW operator
   class, and these four legacy-only indexes:
   - `ix_catalog_agenda_segmentation_attempted_at`
   - `ix_catalog_agenda_segmentation_status`
   - `ix_catalog_lineage_updated_at`
   - `ix_semantic_embedding_hnsw`
4. Make the baseline the downgrade floor. Its `downgrade()` raises before DDL.
   Later revisions may downgrade to the baseline but not below it.
5. Add `pipeline/db_schema_contracts.py`. Its sole responsibility is to
   inspect two PostgreSQL schemas into typed immutable contracts and return an
   ordered, operator-readable difference. Compare tables, columns, rendered
   types, nullability, normalized defaults, primary keys, foreign keys and
   actions, unique/check constraints, indexes including predicates and
   operator classes, sequences and ownership, and the required `vector`
   extension. Exclude `alembic_version` and extension-owned objects.
6. Add `pipeline/db_migration_alembic.py`. Its sole responsibility is to own
   Alembic configuration, migration-state detection, a PostgreSQL advisory
   lock, guarded adoption, stamping, and upgrade. It imports contracts but
   neither contracts nor `alembic/env.py` import the facade.
7. Preserve SQLite behavior as a migration no-op. For PostgreSQL, open one
   connection and one outer transaction for the complete state transition:
   - acquire `pg_try_advisory_xact_lock` once and fail immediately with a
     typed lock-conflict error when another migrator owns it;
   - if no application tables exist, run `upgrade head`;
   - if an Alembic version exists, run `upgrade head`;
   - if unversioned application tables exist, run the strict frozen legacy
     chain through v10, repair known indexes, build the baseline in a unique
     temporary schema, compare it with `public`, abort on any difference,
     stamp the baseline, then upgrade to head;
   - commit only after the complete state transition succeeds. Any migration,
     parity, stamp, or upgrade error rolls back legacy DDL, data backfills,
     temporary-schema work, and version state together.
8. Use a shared SQLAlchemy `Connection` through `Config.attributes` for each
   Alembic command. For reference construction, set
   `version_table_schema` to the generated temporary schema, set transaction
   local `search_path`, and restore it before the public comparison and stamp.
   Generate temporary schema names internally and use SQLAlchemy schema DDL
   plus bound values for `search_path`; never interpolate an identifier into
   `text()`. Drop the temporary schema and temporary version table before
   commit.
9. Make the legacy runner strict. Remove its broad warning-and-continue
   handler and injectable module arguments. Refactor v8, v9, v10, and core
   backfills to operate on the caller-owned `Connection`; their historical
   CLI wrappers may acquire a connection but contain no second implementation.
   A v8, v9, v10, repair, parity, or Alembic failure propagates and guarantees
   no committed schema or stamp.
10. Freeze v8 table metadata inside
    `migration_pgvector_semantic_embeddings.py`. It may create only the
    semantic-embedding table and required referenced-table stubs; it must not
    call current `Base.metadata.create_all()`. Preflight the legacy schema
    contract and count values in the retired catalog vector column before v8.
    The column drop and all other v8 work occur inside the adoption
    transaction, so a later failure restores them. Successful adoption records
    the derived-value count and documents rehydration.
11. Ensure known indexes independently of whether their columns were added in
    the current run. This repairs databases where a previous migration added a
    column but failed before its index.
12. Keep `pipeline/db_migrate.py` as the small public facade. It delegates once
    to the Alembic migration owner. Keep the exact pipeline subprocess
    `["python", "db_migrate.py"]`.
13. Make `pipeline/db_init.py` delegate to the migration owner rather than
    `create_tables()`. Update `scripts/dev_up.sh` to start migration
    prerequisites, run migration, then start schema consumers so API and
    workers cannot race table creation.
14. Remove implicit `create_tables()` from seed and promotion commands. Missing
    schema errors must cause a nonzero CLI exit after rollback and contextual
    logging.
15. Add `scripts/check_schema_parity.py` as a thin operator CLI over the typed
    comparison owner. It prints an empty difference on parity and exits nonzero
    with ordered differences on drift.
16. Add PostgreSQL acceptance tests using isolated databases, not schemas, for
    extension-free, fresh, existing-v10, delayed, drifted, partial,
    concurrent, post-baseline upgrade, and downgrade-floor scenarios.
17. Add a mandatory migration test step to Python Guardrails. Reuse its
    existing `pgvector/pgvector:pg15` service and
    `TEST_POSTGRES_DATABASE_URL`; do not add a second service.
18. Update only the named setup, migration, backup, architecture, and
    migrate-before-seed documentation.
19. Run simplification, a fresh subagent pre-commit review, all required
    verification, two atomic commits, push, PR creation, and bounded CI review
    repair.

New-module responsibilities and import direction:

- `pipeline/db_schema_contracts.py`: PostgreSQL inspection and typed
  comparison only; imports SQLAlchemy, never migration orchestration.
- `pipeline/db_migration_alembic.py`: state machine, transaction, lock, and
  Alembic commands; imports schema contracts and frozen legacy owners, never
  `db_migrate`.
- `scripts/check_schema_parity.py`: CLI translation only; imports the schema
  contract owner, never the facade.
- `alembic/env.py`: Alembic runtime adapter; imports model metadata only for
  future autogeneration and accepts an external connection through
  `Config.attributes`.

**f) Reuse audit.** Reuse `pipeline/db_migrate.py` as facade,
`pipeline/db_migration_columns.py` as legacy repair owner, v8-v10 as frozen
history, `pipeline.models.db_connect`, the current PostgreSQL CI service, and
the existing pipeline subprocess. New modules are required because migration
state/locking and normalized schema comparison are separate responsibilities
that do not fit the facade or Alembic runtime adapter. This supersedes
`create_all()` setup and best-effort legacy migration; both supported paths
are removed in the same PR.

Rejected alternatives:

- Stamp every existing database without comparison: rejected because it can
  bless missing constraints or indexes.
- Compare existing databases with current `Base.metadata`: rejected because
  later model changes would mutate the adoption contract.
- Keep both `db_init.py` table creation and Alembic setup: rejected because it
  creates competing schema owners.
- Put the entire adoption state machine in `alembic/env.py`: rejected because
  the runtime adapter would become an application facade.
- Use only `alembic check`: rejected because extensions, legacy-only objects,
  sequence ownership, and PostgreSQL index details need explicit comparison.
- Add a strict-mode boolean to the legacy runner: rejected because the
  supported migration path must always fail fast.

**g) Data contracts.** Use frozen dataclasses for schema, table, column,
constraint, index, sequence, and difference contracts. Database introspection
is a trust boundary; raw inspector dictionaries are normalized immediately
and do not cross the contract owner. Alembic revision identifiers remain
strings owned by Alembic.

**h) Schema and migrations.** Add one immutable Alembic baseline revision
representing the v10 schema. No application data transformation is added
beyond the existing frozen legacy chain. The baseline is idempotent through
Alembic versioning, uses timezone-aware timestamp declarations established by
v10, and cannot downgrade. No `migrate_v11.py` or later numbered migration is
allowed.

Dependency change: add exact runtime pin `alembic==1.18.5`. A dry-run against
the current environment resolves new transitive `Mako==1.3.12` and reuses
SQLAlchemy `2.0.38`, typing-extensions `4.15.0`, and MarkupSafe `3.0.3`.
No conflict was reported. Python 3.14 installation, import, and migration
execution remain mandatory evidence because upstream package classifiers do
not yet advertise Python 3.14.

## 3. Security & Data Governance

**i) Security-sensitive paths.** `.github/workflows/python-guardrails.yml` is
not listed as a security-sensitive runtime path. No Docker, credential, CORS,
or externally reachable boundary changes. The migration connection retains
the existing database privilege boundary. The operator must have table,
extension, temporary-schema, and advisory-lock privileges; missing privilege
fails before stamping.

**j) Secrets.** No credential, key, environment variable, or working default
is added. Alembic receives the existing SQLAlchemy connection; the database URL
is not printed.

**k) Person data.** Existing civic records, including official-person records,
are preserved. No person linking, aggregation, or exposure changes. Adoption
tests compare representative row counts and checksums before and after
stamping.

**l) Untrusted input.** Existing database schemas are untrusted adoption input.
They are inspected into typed contracts and must equal the immutable baseline
before stamping. Schema names used by the temporary reference database path
are internally generated. No scraped text is parsed or rendered.

## 4. Code Health

**m) GED conformance sweep.** New functions have complete annotations and one
responsibility. Complex comparison and orchestration branches are decomposed
before Ruff C901 reaches 10. Constants own the baseline revision, advisory
lock key, required extension, legacy-only indexes, and temporary-schema
prefix. New filesystem logic uses `Path`. Errors are raised as typed migration
or schema-drift failures after contextual logging; no broad handler is added.
All timestamps remain timezone-aware UTC.

**n) Antipattern scan, plan pass.**

- A1/H1: Alembic `1.18.5` APIs were verified with current official docs:
  `Config`, `Config.attributes`, `command.upgrade`, `command.current`,
  `command.stamp`, `command.downgrade`, and external-connection `env.py`.
  Autogenerate limits require manual PostgreSQL reconciliation.
- A2-A4: no env var, silent default, placeholder, or unverified success claim.
- B1: the two production modules and one CLI have named, necessary
  responsibilities; no generic manager, factory, registry, or utility module.
- B2/C1: `create_all()` setup and best-effort migration are deleted; no dual
  supported migration path or compatibility alias remains.
- B3: validation covers reachable adoption drift and concurrent migration, not
  speculative conditions.
- C2/D2: tests use PostgreSQL/filesystem/subprocess boundaries and do not add
  patchability arguments or facade patches.
- D1/D3: no skip, xfail, tolerance increase, weakened assertion, or private
  spelling contract.
- E1-E3: edits stay within the registered set; no repository-wide formatting
  or generated-file replacement.
- F1/F2: one comparison owner and one orchestration owner; no copied schema
  comparator.
- H2-H4: no type suppression, hand-rolled alternate contract, or import-time
  engine/network work.

**o) Ratchet interaction.** No Ruff selector, BLE001 boundary, coverage floor,
formatter scope, or Mypy scope is widened. `db_migration_runner.py` leaves the
BLE001 inventory if its only broad handler is removed. The guardrail test adds
only migration CI and no-v11 contracts.

**p) Dead code and duplication audit.** Delete mutable v8 metadata access,
best-effort migration swallowing, implicit schema creation in three
entrypoints, and stale tests/docs that preserve those behaviors. Reuse the
frozen v8-v10 operations and current database boundary. Production lines grow
for the explicit baseline and parity contract, while supported migration
entrypoints decrease from two to one.

## 5. Testing

**q) Edge cases, races, and failure scenarios.**

1. Empty PostgreSQL without `vector`.
2. SQLite invocation.
3. Existing unversioned v10 database.
4. Delayed adopter after a post-baseline revision exists.
5. Partial legacy migration with columns present and indexes absent.
6. Missing, extra, or changed table/column/type/nullability/default.
7. Changed PK, FK action, unique/check constraint, index predicate/opclass, or
   sequence ownership.
8. v8, v9, v10, repair, parity, stamp, or upgrade failure.
9. Two migrators start concurrently.
10. Downgrade below baseline.
11. Current model adds a table after the frozen v8 contract.
12. Seed or promotion runs before migration.
13. API/worker startup races migration.
14. Existing derived catalog vector data is removed by frozen v8.
15. Alembic on Python 3.14 with pinned SQLAlchemy and pgvector.
16. Unknown Alembic revision or multiple heads.
17. Temporary reference schema cleanup fails.

Handling:

- Scenarios 1 and 3-7 run inside isolated PostgreSQL databases and compare
  immutable contracts before stamp.
- Scenario 2 returns without schema work, preserving current local tests.
- Scenario 8 propagates a typed failure; no stamp occurs.
- Scenario 9 fails the second migrator immediately through a fixed
  transaction-scoped advisory lock; it never waits indefinitely.
- Scenario 10 raises before DDL and preserves schema plus data checksums.
- Scenario 11 proves v8 does not read current metadata.
- Scenario 12 exits nonzero and logs the missing-schema operation.
- Scenario 13 changes startup ordering: dependencies, migrate, consumers.
- Scenario 14 records derived-vector counts and documents mandatory
  rehydration after adoption; system-of-record rows remain unchanged.
- Scenarios 15-16 are mandatory CI failures, not optional skips.
- Scenario 17 logs cleanup context and re-raises; the migration transaction
  remains failed and unstamped.

**r) Tests added or updated.**

| Test | Scenarios |
|---|---|
| Fresh PostgreSQL baseline upgrade | 1, 7, 15 |
| SQLite no-op contract | 2 |
| Existing-v10 adoption and parity | 3, 5-8 |
| Delayed adopter with test-only later revision | 4, 16 |
| Parameterized drift rejection | 6, 7 |
| Failure-before-stamp tests | 8, 17 |
| Concurrent migrator integration test with elapsed-time ceiling | 9 |
| Downgrade-floor data-preservation test | 10 |
| Frozen-v8 sentinel metadata test | 11 |
| Seed/promotion missing-schema CLI tests | 12 |
| Dev startup and Docker contract tests | 13 |
| Derived-vector remediation evidence test | 14 |
| Guardrail workflow contract | 15 |
| No-v11 repository guardrail | 16 |
| Schema parity CLI contract | 3, 6, 7 |
| Existing pipeline orchestration contract | 13 |

Every PostgreSQL migration scenario is mandatory in CI. Local execution may
report `NOT VERIFIED` only when the configured PostgreSQL boundary is absent;
the PR cannot be considered decided until CI runs them without skips.

**s) Fakes and mocks.** PostgreSQL tests use the approved database boundary and
create unique temporary databases. CLI tests use approved filesystem and
subprocess boundaries. Unit tests may patch `pipeline.models.db_connect` or
the Alembic implementation module, never `pipeline.db_migrate` re-exports. No
new seam is added.

**t) Verification rows.** Apply guardrail/tooling, typed-subtree,
pipeline/task orchestration, and docs-only rows. Run PostgreSQL migration
acceptance, Docker configuration/build contracts, and the complete
coverage-enforced Python suite because this is cross-cutting.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

Baseline and branch:

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-plat-1-alembic-baseline
```

Dependency verification and installation:

```bash
.venv/bin/python -m pip index versions alembic
.venv/bin/python -m pip install "alembic==1.18.5"
.venv/bin/python -c \
  "import alembic, sqlalchemy; print(alembic.__version__, sqlalchemy.__version__)"
```

Tests-first red evidence:

```bash
PYTHONPATH=. TEST_POSTGRES_DATABASE_URL="$TEST_POSTGRES_DATABASE_URL" \
  .venv/bin/pytest -q \
  tests/test_alembic_migrations.py \
  tests/test_db_init.py \
  tests/test_db_migrate.py \
  tests/test_migrate_v8_pgvector_order.py \
  tests/test_seed_places.py \
  tests/test_database.py \
  tests/test_docker_build_contracts.py
```

Generate the candidate revision only against a disposable empty PostgreSQL
database. The preflight count must be zero before autogeneration. This example
uses the existing Compose service and deletes only the named disposable
database:

```bash
docker compose exec -T postgres \
  sh -c 'dropdb --if-exists --username "$POSTGRES_USER" tc_alembic_candidate'
docker compose exec -T postgres \
  sh -c 'createdb --username "$POSTGRES_USER" tc_alembic_candidate'
test "$(
  docker compose exec -T postgres \
    sh -c 'psql --username "$POSTGRES_USER" --dbname tc_alembic_candidate --tuples-only --no-align --command "select count(*) from pg_catalog.pg_tables where schemaname = current_schema()"'
)" = "0"
test -n "${TEST_POSTGRES_DATABASE_URL:-}"
DATABASE_URL="${TEST_POSTGRES_DATABASE_URL%/*}/tc_alembic_candidate" \
  .venv/bin/alembic revision \
  --autogenerate \
  -m "establish v10 baseline"
docker compose exec -T postgres \
  sh -c 'dropdb --username "$POSTGRES_USER" tc_alembic_candidate'
```

Focused verification:

```bash
./.venv/bin/ruff check .
./.venv/bin/pre-commit run ruff --all-files
./.venv/bin/mypy
PYTHONPATH=. TEST_POSTGRES_DATABASE_URL="$TEST_POSTGRES_DATABASE_URL" \
  .venv/bin/pytest -q tests/test_alembic_migrations.py
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_db_init.py \
  tests/test_db_migrate.py \
  tests/test_docker_build_contracts.py \
  tests/test_migrate_v8_pgvector_order.py \
  tests/test_seed_places.py \
  tests/test_seed_places_includes_cupertino.py \
  tests/test_database.py \
  tests/test_pipeline_idempotency.py \
  tests/test_pipeline_integration.py \
  tests/test_repository_guardrails.py \
  tests/test_run_pipeline_orchestration.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
```

Full and container verification:

```bash
PYTHONPATH=. .venv/bin/python -m pytest -q \
  --cov --cov-config=.coveragerc \
  --cov-report=term-missing:skip-covered tests/
docker compose config --quiet
docker compose build pipeline api worker
docker compose down --volumes
docker compose up -d postgres
docker compose run --rm pipeline python db_migrate.py
docker compose run --rm pipeline python seed_places.py
docker compose up -d api worker
docker compose exec -T api python -c \
  "from pipeline.models import db_connect; print(db_connect().dialect.name)"
git diff --check
git status --short
```

LFG delivery:

1. Simplify the branch diff without changing contracts.
2. Run a fresh subagent pre-commit review against this plan.
3. Apply every eligible P1/P2 and rerun affected checks.
4. Commit planning and implementation separately.
5. Push `codex/t-plat-1-alembic-baseline`.
6. Open `T-PLAT-1: Establish the Alembic baseline`.
7. Run browser routing in pipeline mode; expect `NOT APPLICABLE`.
8. Watch CI and review to a decided state without merging.

**v) Rollback.** The baseline has no supported downgrade. Before deployment,
take a `pg_dump --format=custom` backup and record row counts/checksums. If
adoption fails, the outer PostgreSQL transaction restores schema, data, and
version state; verify that rollback evidence, fix the reported error, and
rerun. Never stamp manually. If code rollback is required after a successful stamp
and before any later revision, stop writers, restore the pre-adoption backup,
deploy the prior application, and verify v10 plus representative row
checksums. Removing `alembic_version` without restoring or proving exact v10
parity is forbidden. Once a post-baseline revision has run, use its supported
downgrade only to the baseline or restore a backup; never cross the baseline
floor.

**w) Docs synchronization.**

- `README.md`: fresh setup calls `python db_migrate.py`.
- `ARCHITECTURE.md`: Alembic graph, frozen v1-v10 adoption history, and sole
  migration facade.
- `docs/OPERATIONS.md`: backup-before-adoption, fresh/existing/delayed
  workflows, parity command, lock behavior, baseline floor, and vector
  rehydration.
- `docs/PIPELINE.md`: migration prelude and no numbered migrations after v10.
- `docs/CONTRIBUTING_CITIES.md`: migrate before seed.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`: T-TIME completion,
  T-PLAT-1 activation, ownership, and final acceptance.
- `docs/plans/G5_ALEMBIC_ADOPTION_DECISION_PLAN.md`: prerequisite completion
  and active implementation status.
- ADR: None. The accepted G5 ADR already records this decision; update only if
  implementation must deviate.

## 7. Delivery Self-Audit

**x) Antipattern scan, diff pass.** Re-run A-F and H. Reject mutable model
imports from the baseline, a second schema owner, best-effort migration,
manual stamp guidance, interpolated SQL identifiers, generic helper modules,
patchability parameters, facade patches, optional CI migration skips, new
Ruff exceptions, unrelated dependency changes, or edits outside ownership.

**y) Evidence.** Report every command in 6u as `PASS`, `FAIL`, or
`NOT VERIFIED`; include dependency versions, red tests, PostgreSQL database
count, schema parity output, row checksums, downgrade result, Docker smoke,
full-suite counts/coverage, planning-review findings, pre-commit findings,
commit hashes, PR URL, unresolved thread count, and CI state.

**z) Deviations.** Expected deviations: none. Any additional file, new
environment variable, unsupported stamp path, optional PostgreSQL CI skip,
post-v10 numbered migration, dual schema owner, unresolved P1/P2, or unrun
required check blocks handoff.

## Independent Planning Review Incorporated

- Add explicit ownership for the plan, ledger, strict runner, Alembic owner,
  typed schema contracts, and parity CLI.
- Add ownership for v9, v10, and backfills so adoption can use one
  caller-owned transaction.
- Treat all four legacy-only indexes as baseline objects.
- Replace swallowed legacy failures rather than adding a strict-mode switch.
- Compare full PostgreSQL contracts, not only Alembic metadata differences.
- Use isolated databases where extension state matters.
- Use an immediate transaction-scoped advisory lock instead of an unbounded
  session lock.
- Isolate the reference version table and restore transaction-local
  `search_path` before public stamping.
- Roll back destructive v8 work with the rest of adoption on any failure.
- Migrate before starting API and workers.
- Preserve system-of-record rows and document derived-vector rehydration.
- Prove a test-only post-baseline revision reaches head.
