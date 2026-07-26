# T-TIME-1 + T-TIME-2: Make Stored Timestamps UTC-Aware

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: implementation-ready`
`execution: code`

## 1. Context & Alignment

**a) Driver.** Town Council stores thirteen ORM timestamps as timezone-naive
values. Five onboarding and verification paths then remove UTC information to
keep comparisons working. This weakens ordering, freshness, and recovery
contracts. T-TIME-1 and T-TIME-2 must land together: timezone-aware model
declarations without the database conversion can make existing deployments
fail, while converting the database before the models can reintroduce naive
values.

**b) Canonical documents consulted.**

- `AGENTS.md`: requires timezone-aware UTC timestamps, tests-first work,
  exact ownership, PostgreSQL evidence for schema changes, and complete
  verification.
- `docs/TESTING.MD`: permits the database, filesystem, and subprocess
  boundaries used by the migration and guardrail tests.
- `docs/ENGINEERING_GUARDRAILS.md`: `ruff.toml` owns DTZ exceptions; this task
  may remove only the four stale entries named below.
- `SECURITY.md`: CI database credentials must be test-only and may not alter
  runtime defaults.
- `docs/DATA_GOVERNANCE.md`: timestamp conversion does not create, link,
  aggregate, or expose person data.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`: T-TIME-1 and T-TIME-2 precede
  the approved T-PLAT-1 Alembic baseline.
- `docs/reviews/architecture-review-2026-07-19.html`: schema parity must be
  proven against PostgreSQL before retiring the numbered migration chain.

**c) Remediation alignment.** This is one operator-approved coordinated TIME
lane change. Its exact `files_owned` set is:

- `.github/workflows/python-guardrails.yml`
- `ruff.toml`
- `docs/ADR.md`
- `docs/OPERATIONS.md`
- `docs/plans/G5_ALEMBIC_ADOPTION_DECISION_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `docs/plans/T_TIME_1_2_TIMEZONE_MIGRATION_PLAN.md`
- `pipeline/model_civic.py`
- `pipeline/model_events.py`
- `pipeline/model_records.py`
- `council_crawler/council_crawler/models.py`
- `pipeline/run_pipeline_onboarding.py`
- `pipeline/downloader_selection.py`
- `pipeline/city_onboarding_metrics.py`
- `pipeline/migrate_v10.py`
- `pipeline/db_migrate.py`
- `scripts/check_city_crawl_evidence.py`
- `scripts/reset_city_verification_state.py`
- `tests/test_model_timestamp_contract.py`
- `tests/test_migrate_v10.py`
- `tests/test_db_migrate.py`
- `tests/test_repository_guardrails.py`
- `tests/test_downloader.py`
- `tests/test_city_onboarding_gate_evaluator.py`
- `tests/test_check_city_crawl_evidence.py`
- `tests/test_reset_city_verification_state.py`
- `tests/test_api.py`
- `tests/test_run_pipeline_onboarding.py`

The task receives narrow coordination grants from CI for the PostgreSQL
service and DTZ ratchet, CRAWL for its duplicate stage-table declarations,
DEDUP-C for timestamp response contracts, DEDUP-D for the two verification
scripts, PLAT for migration operations documentation, and GOV for the accepted
ADR wording. Those lanes retain all unrelated ownership.

**d) Decision gates.** G5 was approved on 2026-07-24. The operator approved
combining T-TIME-1 and T-TIME-2 on 2026-07-25. G1-G4 are unaffected.
T-PLAT-1 remains blocked until this coordinated task merges.

## 2. Design

**e) Step-by-step approach.**

1. Record the combined task, ownership, lifecycle semantics, and sequence in
   the remediation ledger, G5 decision plan, and ADR.
2. Add failing tests before model, migration, consumer, workflow, or Ruff
   changes.
3. Change all thirteen columns to `DateTime(timezone=True)`.
4. Give ten generated timestamps `server_default=func.now()`. Preserve
   `SemanticEmbedding.updated_at`'s existing `onupdate=func.now()`.
5. Keep `Catalog.extraction_attempted_at`, `Catalog.lineage_updated_at`, and
   `Catalog.agenda_segmentation_attempted_at` nullable with no default because
   null means the lifecycle action has not occurred.
6. Make the crawler's duplicate `UrlStage` and `EventStage` declarations match
   the canonical timezone and server-default contracts.
7. Make the five UTC parsers/comparison paths retain timezone information.
   Non-null API timestamp strings retain their existing keys but now include
   an explicit RFC 3339 offset. The offset reflects the database session while
   preserving the same UTC instant.
8. Add `pipeline/migrate_v10.py`. Its sole responsibility is converting the
   static timestamp inventory and enforcing defaults in one PostgreSQL
   transaction.
9. For each inventory entry, inspect `information_schema.columns` in
   `current_schema()`. Fail on missing or unsupported types. Convert
   `timestamp without time zone` with
   `USING <column> AT TIME ZONE 'UTC'`; accept an already converted
   `timestamp with time zone`.
10. Drop each old physical default before type conversion. Restore `now()` for
   generated timestamps and no default for lifecycle timestamps. Run
   `ANALYZE` on tables whose column types changed.
11. Call v10 directly from `pipeline.db_migrate.migrate()` after the existing
    v8/v9 runner. Do not route v10 through the best-effort submigration
    handler; any v10 error aborts startup.
12. Add a `pgvector/pgvector:pg15` service to Python Guardrails and expose only
    `TEST_POSTGRES_DATABASE_URL` to tests. Do not replace `DATABASE_URL` or
    make the main suite use PostgreSQL.
13. Remove only the four now-stale DTZ007 ignores for
    `pipeline/city_onboarding_metrics.py`,
    `pipeline/run_pipeline_onboarding.py`,
    `scripts/check_city_crawl_evidence.py`, and
    `scripts/reset_city_verification_state.py`.
14. Document preflight sampling, maintenance locking, backup, migration,
    validation, and restore-based rollback.
15. Run full verification, simplification, independent pre-commit review,
    eligible fixes, atomic commits, PR delivery, and bounded CI repair.

New `TimestampColumnSpec` is a frozen, slotted dataclass containing one table,
column, and default policy. New migration functions remain below the
`db_migrate` facade and never import it.

**f) Reuse audit.** Reuse `pipeline.models.db_connect`, SQLAlchemy
`Engine.begin()`, current `db_migrate` ordering, existing model modules,
existing UTC formats, Ruff configuration, and workflow. No migration registry,
compatibility wrapper, callable injection, alternate runner, or duplicate
timestamp implementation is added. `summary_freshness.py` was audited and has
no timestamp comparison to modify.

**g) Data contracts.** `TimestampColumnSpec` is the typed internal migration
contract. CLI arguments, response keys, and null behavior remain unchanged.
Non-null lineage and agenda-attempt response timestamps become RFC 3339 values
with an explicit numeric offset instead of ambiguous naive ISO strings. The
offset need not be `+00:00`; PostgreSQL may render the same instant in the
session timezone. Strict clients comparing exact timestamp text must accept
the offset-bearing form.
The workflow variable is test-only and is not an application config surface.

**h) Schema and migration impact.** Thirteen columns change from PostgreSQL
`timestamp without time zone` to `timestamp with time zone`. Existing wall
clock values are interpreted as UTC. Ten columns receive `DEFAULT now()`;
three lifecycle columns have no default. V10 is idempotent, supports mixed
converted/unconverted schemas, and is the mandatory final numbered migration
before T-PLAT-1. PostgreSQL `ALTER TABLE` takes locks; operators must use a
maintenance window. No data row is deleted.

## 3. Security & Data Governance

**i) Security boundary.** The workflow service uses fixed ephemeral CI
credentials and maps PostgreSQL only inside the hosted runner. It does not
change application secrets, production ports, or permissions. `SECURITY.md`'s
development-default and secret-isolation controls remain intact.

**j) Secrets.** No production credential or default is added.
`TEST_POSTGRES_DATABASE_URL` contains CI-only credentials.

**k) Person data.** Existing person timestamps are converted in place. No new
person attribute, relationship, aggregation, or exposure is introduced.

**l) Untrusted input.** Migration identifiers come only from a checked-in
typed constant. Database metadata and stored timestamps are the trust
boundary. Bound parameters read metadata; fixed identifiers form DDL. Missing
or unexpected types raise a typed migration error and roll back.

## 4. Code Health

**m) GED conformance sweep.** Migration functions each perform one operation,
use domain names, stay within two nesting levels, and have complete type
annotations. UTC, SQL type names, default policies, and the thirteen-column
inventory are named constants. No broad exception, environment read in
production code, naive datetime call, or import-time I/O is added.

**n) Antipattern scan, plan pass.**

- A1/H1: SQLAlchemy 2.0 and PostgreSQL documentation confirm
  `DateTime(timezone=True)`, server defaults, `Engine.begin()`, `ALTER COLUMN
  TYPE ... USING`, `AT TIME ZONE`, and post-conversion `ANALYZE`. GitHub
  Actions documentation confirms Linux service containers, health checks, and
  localhost port mapping.
- A2: corrected by making the new URL CI-test-only and mandatory in CI.
- B1/F1: one focused v10 module is required by the remediation plan; no generic
  migration framework is introduced before T-PLAT-1.
- B2/C1: no dual timezone path survives. Canonical and crawler model
  declarations agree, and all owned consumers retain awareness.
- D1-D3: tests assert metadata, stored types/defaults, transaction rollback,
  UTC instant preservation, and observable query behavior.
- E1-E3: only owned paths change; no broad formatting or generated artifacts.
- A3-A4, B3, C2, F2, H2-H4: pass.

**o) Ratchet interaction.** Remove four DTZ007 per-file entries. Add no Ruff,
BLE001, Mypy, formatter, coverage, or test exceptions.

**p) Dead code and duplication.** Remove three `datetime` imports used only by
model defaults and five timezone-stripping calls. Reuse one inventory for all
v10 operations and tests inspect it rather than duplicating column names.
Expected net production change is one focused migration module plus smaller
canonical model, crawler model, and consumer edits.

## 5. Testing

**q) Edge and failure scenarios.**

1. Fresh metadata declares all thirteen timestamps timezone-aware.
2. Ten generated timestamps have server defaults; three lifecycle markers do
   not.
3. `SemanticEmbedding.updated_at` keeps update behavior.
4. Crawler `UrlStage.created_at` and `EventStage.scraped_datetime` match their
   canonical timezone and server-default declarations.
5. Legacy UTC wall-clock rows preserve their instant after conversion.
6. A non-UTC PostgreSQL session returns the same instant.
7. Re-running v10 is a no-op for already converted types.
8. A mixed schema converges.
9. Missing or unsupported columns fail and roll back earlier DDL.
10. SQLite remains a no-op.
11. V10 runs after v9 and its failures escape.
12. UTC parsers return aware values; invalid onboarding input keeps existing
    fallback behavior.
13. Onboarding windows and verification queries no longer strip timezone.
14. Python Guardrails always provides PostgreSQL for the integration test.
15. Local runs without the test URL skip only PostgreSQL integration; CI
    without it fails.
16. Existing populated deployments may contain non-UTC wall clocks despite
    current UTC server settings; operator sampling must stop migration if that
    assumption is false.
17. Non-null API timestamps include an RFC 3339 numeric offset; response keys
    and null behavior remain unchanged.

**r) Tests.**

- `tests/test_model_timestamp_contract.py`: scenarios 1-4 and the fresh
  PostgreSQL physical schema, including explicit crawler/canonical parity.
- `tests/test_migrate_v10.py`: scenarios 5-10 and 15.
- `tests/test_db_migrate.py`: scenario 11 using observable ordering and raised
  errors, not new call-count assertions.
- Existing downloader, onboarding evaluator, crawl evidence, and reset-state
  tests: scenarios 12-13.
- Existing API tests: scenario 17.
- `tests/test_repository_guardrails.py`: scenarios 1-3, 14-15, and exact DTZ
  ratchet.
- Operations contract and docs-link checks: scenario 16.

**s) Fakes and mocks.** PostgreSQL integration uses the approved database
boundary. Existing SQLite tests retain their database factory boundary. Tests
patch `pipeline.migrate_v10.db_connect` only when selecting an isolated test
schema. No facade, re-export, clock global, or unit-under-test is mocked.

**t) Verification rows.** Apply guardrail/tooling, typed-subtree, docs-only,
and broad cross-cutting rows. Run targeted timestamp, migration, database,
onboarding, downloader, verification-script, orchestration, repository
guardrail, and docs-link tests, then the complete coverage-enabled suite.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-time-1-2-timezone-migration

docker compose exec -T postgres psql -U town_council -d town_council_db \
  -c "show timezone"
docker compose exec -T postgres psql -U town_council -d town_council_db \
  -c "select table_name, column_name, data_type, column_default
      from information_schema.columns
      where table_schema = 'public' and data_type like 'timestamp%'
      order by table_name, ordinal_position"

docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres
export TEST_POSTGRES_DATABASE_URL=\
postgresql://town_council:secure_dev_password@127.0.0.1:5432/town_council_db

PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_model_timestamp_contract.py \
  tests/test_migrate_v10.py \
  tests/test_db_migrate.py \
  tests/test_repository_guardrails.py

./.venv/bin/ruff check .
./.venv/bin/pre-commit run ruff --all-files
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_model_timestamp_contract.py \
  tests/test_migrate_v10.py \
  tests/test_db_migrate.py \
  tests/test_database.py \
  tests/test_downloader.py \
  tests/test_city_onboarding_gate_evaluator.py \
  tests/test_check_city_crawl_evidence.py \
  tests/test_reset_city_verification_state.py \
  tests/test_api.py \
  tests/test_run_pipeline_orchestration.py \
  tests/test_repository_guardrails.py \
  tests/test_docs_links.py
PYTHONPATH=. .venv/bin/python -m pytest -q --cov --cov-config=.coveragerc \
  --cov-report=term-missing:skip-covered tests/
git diff --check
git status --short
```

PostgreSQL tests create and remove isolated schemas under the configured
database. The PR's Python Guardrails result is mandatory PostgreSQL evidence.

**v) Rollback.** Before migration, write a custom-format backup:

```bash
BACKUP_PATH="<BACKUP_PATH>/town_council_pre_v10.dump"
docker compose -f docker-compose.yml -f docker-compose.dev.yml stop
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres
docker compose exec -T postgres pg_dump \
  -U town_council -d town_council_db -Fc > "$BACKUP_PATH"
docker compose exec -T postgres pg_restore --list < "$BACKUP_PATH" >/dev/null
```

If rollback is required, stop every application writer, restore the backup,
revert the merge commit, and validate the restored types:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml stop
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres
docker compose exec -T postgres pg_restore \
  -U town_council -d town_council_db --clean --if-exists --exit-on-error \
  < "$BACKUP_PATH"
docker compose exec -T postgres psql -U town_council -d town_council_db \
  -c "select table_name, column_name, data_type, column_default
      from information_schema.columns
      where table_schema = 'public' and data_type like 'timestamp%'
      order by table_name, ordinal_position"
git revert <merge_commit_sha>
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

Do not reverse-convert a partially written live database. Backup restoration
is the supported path. No irreversible data deletion is planned.

**w) Docs synchronization.**

- `docs/ADR.md`: record coordinated model/schema delivery and lifecycle-null
  semantics.
- `docs/OPERATIONS.md`: add migration preflight, maintenance, validation, and
  rollback.
- G5 and remediation plans: update sequence, ownership, acceptance, and
  status.
- README, architecture map, API contracts, testing policy, security policy,
  and data-governance policy: no change.

## 7. Delivery Self-Audit

**x) Antipattern scan, diff pass.** Re-run A-F and H. Reject callable
injection, best-effort v10 handling, duplicated inventories, blanket defaults,
timezone stripping, new ignores, optional CI PostgreSQL evidence, unrelated
formatting, or deployment-default changes.

**y) Evidence.** Report every command from 6u with `PASS` or `FAIL`, exact test
counts, PostgreSQL server/version evidence, tests-first red evidence, planning
and pre-commit review findings, applied fixes, commit hashes, PR URL, review
thread count, and final CI state. Current preflight evidence: PostgreSQL 15
container is running with `Etc/UTC`, but the local database has no application
tables, so historical UTC-wall-clock validity is `NOT VERIFIED`.

Local delivery evidence on 2026-07-25:

- PASS, tests-first red: the initial contract run produced 39 expected failures,
  466 passes, and 6 PostgreSQL skips; v10 ordering separately produced 2
  expected failures before implementation.
- PASS: `./.venv/bin/ruff check .`,
  `./.venv/bin/pre-commit run ruff --all-files`, and `./.venv/bin/mypy`.
- PASS: focused timestamp, migration, guardrail, and docs tests produced 436
  passes and 6 local PostgreSQL skips.
- PASS: the coverage-enabled suite produced 1,531 passes, 6 local PostgreSQL
  skips, and 82.83% coverage against the 71% floor.
- PASS: isolated PostgreSQL 15 smokes proved UTC-instant preservation, physical
  defaults, no-DDL reruns, and validation of all metadata before DDL.
- PASS: independent pre-commit review initially found two P1 and two P2
  findings. The backup now follows writer shutdown, migration uses `--no-deps`,
  metadata validation precedes DDL, and diff whitespace is clean. Re-review
  found no remaining P1/P2.
- PASS: PR review found one offset-serialization P2 and one brittle-test P1.
  Verification artifacts now normalize to UTC before adding `Z`, and the
  duplicate crawler source-text guardrail was removed in favor of the existing
  mapped-column contract test.
- NOT VERIFIED: historical UTC wall-clock validity on a populated deployment
  and the mandatory CI PostgreSQL run.

**z) Deviations.** Authorized deviations are combining T-TIME-1/T-TIME-2 and
the narrow CI, CRAWL, DEDUP-C, DEDUP-D, PLAT, and GOV coordination grants.
Independent planning review added crawler model parity, mandatory local
PostgreSQL commands, current G5 checks, RFC 3339 API coverage, and executable
backup/restore steps. Any other changed path, schema object, dependency,
environment default, skipped review, unresolved P1/P2, or unrun required gate
is a blocker.

One procedural deviation occurred during review repair: the validation-before-
DDL regression assertion and implementation correction were applied in the
same focused patch rather than running the new assertion red first. The defect
had already been reproduced by the independent reviewer; focused tests,
isolated PostgreSQL evidence, the complete suite, and independent re-review
then passed.
