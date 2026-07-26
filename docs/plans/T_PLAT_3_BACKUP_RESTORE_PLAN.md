# T-PLAT-3: Add a Verified PostgreSQL Backup and Restore Workflow

`artifact_contract: ce-unified-plan/v1`  
`artifact_readiness: implementation-ready`  
`execution: code`

## 1. Context & Alignment

**a) Driver.** Town Council has migration-specific `pg_dump` snippets but no
reusable backup command, routine cadence, or end-to-end restore drill. T-PLAT-3
must give local operators one safe PostgreSQL archive workflow before further
destructive maintenance or architecture remediation. The workflow must protect
the complete database without changing local-first runtime defaults or treating
derived-data startup purge as a substitute for backups.

**b) Canonical documents consulted.**

- `AGENTS.md` `<security_sensitive_paths>`, `<workflow_contract>`,
  `<verification_matrix>`, and `<docs_sync_rules>` require a Full plan,
  trust-boundary reporting, exact verification, and current operator commands.
- `SECURITY.md` "Secrets and configuration" requires database credentials to
  remain in environment configuration and lists backups as unfinished
  hardening work.
- `docs/OPERATIONS.md` "Database migrations and backups" already owns
  migration preflight and restore commands; T-PLAT-3 must extend that section
  rather than introduce a competing runbook.
- `docs/TESTING.MD` permits filesystem-based tests but does not approve a fake
  Docker CLI boundary; the real dev-stack smoke remains authoritative.
- `docs/DATA_GOVERNANCE.md` requires retained private-individual content to
  stay access-controlled; database archives reproduce that governed content.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` assigns T-PLAT-3 a custom-format
  `pg_dump` script, restore procedure, cadence guidance, and explicit
  `STARTUP_PURGE_DERIVED` interaction.
- `ARCHITECTURE.md` identifies PostgreSQL as the system of record.

**c) Remediation alignment.** This is T-PLAT-3 in the PLAT lane. Expand its
exclusive `files_owned` set before implementation to:

- `docs/plans/T_PLAT_3_BACKUP_RESTORE_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `scripts/backup_db.sh`
- `tests/test_backup_db_contract.py`
- `docs/OPERATIONS.md`
- `pipeline/indexer.py`
- `pipeline/indexer_meilisearch.py`
- `pipeline/reindex_only.py`
- `tests/test_indexer_logic.py`

T-DD-1B also expects a later `docs/OPERATIONS.md` edit. The two tasks must run
serially; T-PLAT-3 lands first and T-DD-1B rebases before implementation.

**d) Decision-gate check.** No G1-G5 decision is required or foreclosed. G5
Alembic adoption is already approved and complete. The script does not restore
or delete data automatically, so no additional destructive-operation approval
is needed for implementation. The manual restore drill creates and drops only a
uniquely named temporary validation database.

## 2. Design

**e) Step-by-step approach.**

1. Create branch `codex/t-plat-3-backup-restore` from current `origin/master`.
2. Add this implementation-ready plan and update T-PLAT-3 ownership,
   dependencies, acceptance criteria, and verification in the remediation
   ledger.
3. Add failing tests before the script and runbook implementation.
4. Add executable `scripts/backup_db.sh` with one required positional
   argument: the destination archive path, plus standard `-h`/`--help`.
5. Resolve the repository root from the script location and use the existing
   development Compose pair:
   `docker compose -f docker-compose.yml -f docker-compose.dev.yml`.
6. Require the destination parent directory to exist and refuse to overwrite
   an existing destination.
7. Set `umask 077`, create a temporary archive beside the destination with
   `mktemp`, and register an exit trap that removes incomplete output.
8. Run `pg_dump` inside the existing `postgres` service with the container's
   `POSTGRES_USER` and `POSTGRES_DB`. Use custom format, omit ownership and ACL
   restoration metadata, and redirect binary stdout to the temporary host file.
9. Validate the completed archive through in-container `pg_restore --list`.
   Atomically hard-link the temporary file to the requested destination only
   after validation succeeds, then unlink the temporary name. Linking fails
   rather than overwriting a destination created after the preflight check.
10. Extend `docs/OPERATIONS.md` with routine backup, restore, cadence,
    retention, credential, and `STARTUP_PURGE_DERIVED` guidance.
11. Replace the two migration-specific inline `pg_dump` and archive-list
    command pairs with calls to `scripts/backup_db.sh`, retaining the existing
    writer-stop and migration ordering.
12. Document active-database restore as a maintenance operation: validate the
    archive, stop Compose and external writers, start only PostgreSQL, drop the
    target database with forced connection termination, recreate it from
    `template0`, restore with error/owner/ACL controls, run migrations and
    schema parity, inspect core row counts, then restart with
    `STARTUP_PURGE_DERIVED=false`.
    Document migration rollback separately: select the previous application
    release before running its migration, parity, and reindex commands against
    the restored pre-migration backup.
13. Add one focused typed helper to existing `indexer_meilisearch.py`: delete
    every document and wait for the documented asynchronous task to succeed.
    Add a second focused helper that waits until no `documents` index task is
    enqueued or processing.
    Add one focused `replace_documents_index()` operation to `indexer.py` that
    calls that helper and then `index_documents()`. Its new return value is the
    PostgreSQL source-corpus count, including rows whose batch submission was
    rejected before Meilisearch accepted a task.
14. Extend the existing `reindex_only.py` CLI with explicit `--replace-all`.
    The default remains unchanged. Replacement mode routes to
    `replace_documents_index()`. The operation waits for the rebuild queue and
    verifies the live index settings before comparing the final Meilisearch
    document count with the PostgreSQL corpus count returned by
    `index_documents()`.
15. Require the recovery runbook to rebuild Meilisearch with `--replace-all`
    before accepting traffic. When `SEMANTIC_BACKEND=faiss`, rebuild FAISS
    artifacts from the restored database too. Pgvector embeddings are restored
    inside PostgreSQL and need no external artifact rebuild.
16. Run a real backup smoke against the local dev stack. Restore that archive
    into a uniquely named temporary database, inspect representative table
    counts, and drop only that temporary database.
17. Simplify the diff, run an independent pre-commit review, apply every
    eligible P1/P2, rerun affected verification, create atomic commits, push,
    open one PR, and watch CI to a decided state.

`scripts/backup_db.sh` has one responsibility: produce one validated,
private, custom-format archive from the configured Compose PostgreSQL service.
It does not stop writers, schedule itself, rotate files, upload archives, or
perform restores.

`pipeline.indexer.index_documents()` retains full-index synchronization
ownership and returns the source-corpus count needed for recovery verification.
The new `replace_documents_index()` operation owns the ordered
clear-then-rebuild workflow. The dependency-facing clear/wait helper stays in
`indexer_meilisearch.py`; helpers never import the indexer or CLI.

**f) Reuse audit.** Reuse the current Compose-array convention from
`scripts/dev_up.sh`, the existing PostgreSQL service environment, and the
current migration backup/restore section. No backup manager, scheduler,
configuration wrapper, restore script, Docker fake, or second credential
source is introduced. The new command supersedes and removes the two duplicate
inline backup command pairs in the runbook.

Rejected alternatives:

- Host-installed `pg_dump`: rejected because it adds a version and package
  prerequisite while the PostgreSQL 15-compatible client already exists in
  the database container.
- Automatic restore script: rejected because replacement restore is
  destructive, requires writers to be quiesced, and needs operator inspection.
- Default timestamped destination: rejected because an implicit write location
  would be a new silent CLI default. The operator must name the archive.
- Fake-Docker unit test: rejected because Docker CLI substitution is not an
  approved `docs/TESTING.MD` fake boundary.
- A runbook-only Meilisearch deletion snippet: rejected because it would
  duplicate SDK behavior without a tested implementation owner.
- Filesystem-copy backup of the Postgres volume: rejected because it is not a
  portable logical backup and can be inconsistent without storage-level
  coordination.

**g) Data contracts.**

- CLI input: exactly one non-empty destination path; `-h`/`--help` prints usage
  and exits without contacting Docker.
- Success: exit `0`, one non-empty custom-format archive at that path, archive
  list validation passed, mode restricted by `umask 077`, and no partial file.
- Usage/config/archive failure: nonzero exit, contextual stderr, no completed
  destination, and no partial file.
- Existing destination: nonzero exit without modifying it.
- No application API, database schema, migration revision, Celery signature,
  environment variable, credential default, or runtime default changes.
- `reindex_only.py --replace-all` is a new explicit maintenance option.
  Running the CLI without it preserves current additive reindex behavior.

**h) Schema/migration impact.** None. The validation restore uses a temporary
database created from `template0`, does not alter the active database, and is
dropped after verification. Existing Alembic migrations remain the only schema
upgrade path after restoring an older archive.

## 3. Security & Data Governance

**i) Security-sensitive path.** The script handles PostgreSQL access and
therefore crosses the backing-store credential boundary in `SECURITY.md`.
Credentials remain inside the Compose service environment and are never passed
as host command arguments, printed, copied into the archive name, or written to
logs. An attacker gains no new network access. The backup contains the database
snapshot and must be treated as sensitive local data; `umask 077` limits new
archive access to the invoking user.

`pipeline/indexer.py` handles `MEILI_MASTER_KEY`, so its focused edit also
touches the privileged search-writer boundary. The change neither logs nor
changes the key; it uses the existing writer client to delete and rebuild only
the `documents` index.

**j) Secrets.** No new secret, key, environment variable, or default is added.
The script references `POSTGRES_USER` and `POSTGRES_DB` only inside the
container. PostgreSQL authentication continues to use the existing container
environment.

**k) Person data.** The task does not create, link, aggregate, or expose new
person data. A backup reproduces existing database contents, including any
governed private-individual records, so operators must apply the same retention
and access controls as the live database. G4 is unaffected.

**l) Untrusted input.** The destination path is operator input. It is quoted,
must have an existing parent, and cannot already exist. It is never evaluated
as shell code. Atomic hard-link publication also refuses a destination created
after preflight. The archive is validated by PostgreSQL's own
`pg_restore --list` before publication. Restore commands accept only an
operator-selected local archive and run with writers stopped.

## 4. Code Health

**m) GED conformance sweep.** The script uses `set -euo pipefail`, named
constants/variables, quoted expansions, one cleanup function, and a single exit
trap. Errors either stop execution with context or remove incomplete output.
The indexer receives one short ordered operation, while its existing batch
function adds only the source-corpus counter returned to recovery verification.
The Meilisearch helper has typed concrete SDK parameters and one fail-fast
responsibility. No environment config surface, timestamp behavior, broad
exception handler, or Ruff boundary changes.

**n) Antipattern scan, plan pass.**

- A1/H1 corrected: current PostgreSQL and Docker Compose docs were checked for
  custom archives, consistent snapshots, `pg_restore` validation/options,
  repeated `-f`, and `exec -T`. Meilisearch docs and installed
  `meilisearch==0.31.0` were checked for `delete_all_documents()`,
  `TaskInfo.task_uid`, and `Client.wait_for_task()`.
- A2 corrected: destination is required; no new environment variable or silent
  path default.
- B1/F1 corrected: one focused script extends the existing runbook; no manager,
  registry, wrapper, or duplicate backup implementation.
- B3 corrected: overwrite refusal, partial cleanup, and archive validation
  protect real operator failure modes.
- C1 corrected: migration snippets call the new command; the duplicate inline
  dump commands are removed.
- D1-D3 corrected: tests preserve strict behavior and avoid fake Docker or
  private helper assertions.
- E1-E3 corrected: only the nine owned files change and the runbook receives
  minimal edits.
- A3-A4, B2, C2, H2-H4: no violations planned.

**o) Ratchet interaction.** `pipeline/indexer.py` and
`pipeline/indexer_meilisearch.py` already have BLE001 allowances. This task
leaves both unchanged because it adds no broad handler and does not modify the
existing allowed boundaries. No selector, formatter scope, Mypy scope,
coverage floor, or test skip changes.

**p) Dead code and duplication audit.** Remove two duplicated migration
`pg_dump`/`pg_restore --list` pairs and two duplicate in-place restore command
blocks. Reuse the new script for backup and the new routine replacement-restore
procedure by reference. The only production Python delta is the explicit
Meilisearch replacement mode in the existing index owner and CLI. Expected net
delta is one small shell command, focused contract coverage, one Full plan, and
concise runbook/ledger text.

## 5. Testing

**q) Edge cases and failure scenarios.**

1. No destination argument: usage error before Docker is invoked.
2. Extra argument: usage error before Docker is invoked.
3. Missing destination parent: fail without creating directories.
4. Existing destination: fail without modifying it.
5. `pg_dump` failure: exit nonzero and remove the temporary file.
6. Empty or malformed archive: validation fails and no destination is
   published.
7. Successful dump: archive validates, is atomically published, and is
   private to the invoking user.
8. Credentials containing shell metacharacters: remain container environment
   values and are not host-evaluated.
9. Live writes during routine backup: PostgreSQL supplies one consistent
   snapshot; migration backups still stop writers before the dump.
10. Active restore with connected writers: runbook requires all Compose and
    external writers to stop before dropping and recreating the target
    database.
11. Older archive: run migrations and schema parity before writer restart.
12. Startup purge: derived rows may be cleared, source ingest remains, and
    backups still cover the complete snapshot.
13. Temporary restore drill: use a unique database and drop only that database.
14. Temporary database name collision or failed creation: cleanup must never
    drop a database the drill did not create.
15. Restored PostgreSQL is older than Meilisearch/FAISS: delete all
    Meilisearch documents and wait before reindex; rebuild FAISS before traffic.
16. Meilisearch deletion task fails: stop recovery before indexing or restart.
17. Meilisearch rebuild task fails or stalls: queue timeout, settings mismatch,
    or final count mismatch blocks restart.
18. A batch submission fails before Meilisearch accepts the asynchronous task:
    the PostgreSQL corpus count still includes those rows, so final count
    verification blocks restart.
19. Failed schema release: selecting the rollback release before migration and
    parity prevents the failed current migration from being reapplied.

**r) Tests added or updated.**

| Test | Scenarios |
|---|---|
| `test_backup_script_has_valid_shell_syntax` | 1-8 |
| `test_backup_script_requires_one_destination` | 1, 2 |
| `test_backup_script_prints_help_without_docker` | 1, 2 |
| `test_backup_script_refuses_existing_destination` | 4 |
| `test_backup_script_uses_private_atomic_validated_archive` | 5-8 |
| `test_backup_runbook_covers_restore_cadence_and_startup_purge` | 9-13 |
| `test_migration_rollback_selects_previous_release_before_schema_tools` | 19 |
| `test_full_reindex_replaces_existing_meilisearch_documents` | 15 |
| `test_full_reindex_stops_when_meilisearch_clear_fails` | 16 |
| `test_full_reindex_uses_maintenance_timeout_for_document_clear` | 17 |
| `test_full_reindex_rejects_missing_index_settings` | 17 |
| `test_full_reindex_rejects_document_count_mismatch` | 17 |
| `test_indexer_reports_agenda_source_count_after_batch_attempt` | 18 |
| `test_backup_runbook_rebuilds_external_search_state` | 15-18 |
| Real dev-stack backup and temporary restore drill | 5-13 |
| Existing docs-link suite | Runbook and plan links |
| Complete Python suite | Cross-cutting regression check |

The source-contract test may assert CLI and command tokens because those are
the operator-facing shell contract. It also runs `bash -n`. Failure-path tests
execute only pre-Docker validation branches.

**s) Fakes and mocks.** Backup tests use the approved `tmp_path` filesystem
boundary and real subprocess execution of pre-Docker script branches.
Meilisearch replacement tests use the approved Meilisearch-client and database
session boundaries in `pipeline.indexer`; they assert externally visible fake
index state and raised recovery errors, not call counts. The backup success
path uses the real Docker Compose/PostgreSQL boundary manually.

**t) Verification rows.** Apply the docs-only row for `docs/**`. No existing
matrix row names shell operator scripts, so run Ruff, Mypy, the focused backup
contract, docs links, and the complete Python suite. The real dev-stack backup
and temporary restore drill are required before handoff.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-plat-3-backup-restore
```

Tests-first red evidence:

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/test_backup_db_contract.py
```

Expected: collection or assertion failure because the script and runbook
contract do not exist yet.

Final local verification:

```bash
bash -n scripts/backup_db.sh
./.venv/bin/ruff check .
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_backup_db_contract.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_indexer_logic.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/pytest -q
git diff --check
git status --short
```

Real backup smoke:

```bash
BACKUP_SMOKE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/town-council-backup.XXXXXX")"
BACKUP_PATH="$BACKUP_SMOKE_DIR/t_plat_3_smoke.dump"
bash ./scripts/backup_db.sh "$BACKUP_PATH"
docker compose exec -T postgres pg_restore --list < "$BACKUP_PATH" >/dev/null
stat -f '%Lp %z %N' "$BACKUP_PATH"
```

Temporary restore drill:

```bash
RESTORE_DB="town_council_restore_check_$(.venv/bin/python -c \
  'import secrets; print(secrets.token_hex(8))')"
POSTGRES_USER="$(docker compose exec -T postgres printenv POSTGRES_USER)"
RESTORE_DB_CREATED=false
cleanup_restore_drill() {
  if [[ "$RESTORE_DB_CREATED" == "true" ]]; then
    docker compose exec -T postgres dropdb \
      -U "$POSTGRES_USER" --if-exists "$RESTORE_DB" >/dev/null
  fi
  rm -rf "$BACKUP_SMOKE_DIR"
}
trap cleanup_restore_drill EXIT
docker compose exec -T postgres createdb \
  -U "$POSTGRES_USER" -T template0 "$RESTORE_DB"
RESTORE_DB_CREATED=true
docker compose exec -T postgres pg_restore \
  -U "$POSTGRES_USER" -d "$RESTORE_DB" \
  --exit-on-error --no-owner --no-privileges < "$BACKUP_PATH"
docker compose exec -T postgres psql \
  -U "$POSTGRES_USER" -d "$RESTORE_DB" \
  -c "select version_num from alembic_version;
      select 'catalog' as relation, count(*) from catalog
      union all
      select 'event' as relation, count(*) from event
      order by relation"
cleanup_restore_drill
trap - EXIT
```

Delivery uses two commits:

1. `docs(remediation): authorize T-PLAT-3 backup workflow`
2. `feat(operations): add verified database backups`

Push `codex/t-plat-3-backup-restore`, open one PR titled
`T-PLAT-3: Add verified PostgreSQL backups`, request independent review, and
watch CI to a decided state.

**v) Rollback.** Revert the T-PLAT-3 merge commit, rerun the focused contract,
docs links, and complete suite, and remove only the temporary smoke directory
created under `${TMPDIR:-/tmp}`. No schema, migration, active database,
credential, or external service state changes. If the temporary restore drill
is interrupted, verify the generated database name and drop only that
`town_council_restore_check_*` database.

**w) Docs synchronization.**

- `docs/OPERATIONS.md`: add routine backup/restore, cadence, retention,
  archive security, fresh-database replacement restore, restore verification,
  startup-purge interaction, and external search-state rebuild; route migration
  backups through the script and migration rollback to the routine restore
  procedure; update `Last updated`.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`: version, ownership,
  dependencies, implementation plan, acceptance, and verification.
- `SECURITY.md`: no edit. Its checklist says backups must be configured by an
  operator; adding a script and recommendation does not prove a schedule or
  off-host copy exists.
- README, ADR, architecture, testing policy, API contracts, and data-governance
  docs: no update.

## 7. Delivery Self-Audit

**x) Antipattern scan, diff pass.** Re-run A-F/H. Reject a second backup path,
automatic restore, embedded credentials, implicit destination, overwrite,
world-readable archive, fake Docker seam, duplicated migration dump commands,
unrelated runbook edits, new environment settings, or files outside ownership.

**y) Evidence required at delivery.**

- Tests-first red result.
- `bash -n`, Ruff, Mypy, focused backup tests, docs links, complete suite, and
  `git diff --check` outcomes.
- Real backup path, archive size/mode, and `pg_restore --list` result.
- Temporary restore database name, representative row counts, and confirmed
  drop result.
- Planning-review and pre-commit-review findings with applied fixes.
- Commit hashes, PR URL, unresolved P1/P2 count, and final CI state.
- Browser stage: `NOT APPLICABLE` because no UI route changes.

**z) Deviations.** Expected authorized deviations are the nine-file ownership
expansion and serial ordering before T-DD-1B's runbook edit. Any additional
path, automatic schedule, environment variable, credential default, active
database restore during verification, unresolved P1/P2, unrun required check,
or remaining temporary restore database is a blocker.
