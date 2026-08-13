# T-GOV-2A: Enforce Roster-Gated Person Linking

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: implementation-ready`
`execution: code`

## 1. Context & Alignment

**a) Driver.** Town Council still turns names extracted from municipal
documents into persistent people and memberships through title inference and
fuzzy matching. That behavior conflicts with the accepted G4 policy. T-GOV-2A
replaces that derived authority with Legistar OfficeRecords, deletes the old
linker path, removes legacy derived records, fails closed where no approved
roster exists, and retires the incompatible performance baseline.

**b) Canonical documents consulted.**

- `AGENTS.md`: roster authority, local-first operation, no compatibility
  facades, tests-first delivery, and verification routing.
- `docs/DATA_GOVERNANCE.md` Section 3: only independently authoritative
  membership evidence may create people-facing records.
- `docs/ADR.md`, "Roster-gated person linking": source-document mentions and
  linker memberships are not authority.
- `docs/TESTING.MD`: database, outbound HTTP, Meilisearch, clock, and
  filesystem boundaries are approved test boundaries.
- `docs/ENGINEERING_GUARDRAILS.md`: Ruff exceptions and the Mypy typed set
  must ratchet rather than widen.
- `docs/PERFORMANCE.md`: baseline-valid comparisons require a stable workload
  and compatible phase contract.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`: T-GOV-2A owns runtime
  enforcement and blocks City Coverage Expansion.

**c) Remediation alignment.** T-GOV-2A owns only the files named in the active
remediation plan. The work is split into five ordered commits: authorization,
tests, schema/roster runtime, legacy deletion/baseline transition, and docs.
Review expanded ownership to `semantic_service/hydration.py` so both meeting
search producers enforce the same omission policy. T-IDX-1 may later simplify
the remaining authoritative projection, but this task must make the current
projection fail closed.

**d) Decision gates.** G1-G5 are satisfied. The operator approved G4 Option A,
Legistar OfficeRecords as the authoritative source, and the baseline
transition: freeze `baseline_representative_v1` as historical and
non-comparable, allow a temporary non-comparable period, then capture
`baseline_representative_v2` without the document-derived people phase.

## 2. Design

**e) Step-by-step approach.**

1. Add failing tests for the migration, OfficeRecords parsing, exact body
   resolution, roster reconciliation, fail-closed behavior, API/index
   filtering, pipeline deletion, and profile-manifest v2 contract.
2. Add an explicit remediation command that defaults to dry-run, reports
   legacy person/membership/entity counts, and requires `--apply` to delete
   legacy memberships, people, and `Catalog.entities["persons"]`. It uses raw
   SQL so it can run before the new ORM schema is active.
3. Add Alembic revision `0002_roster_gated_people`:
   - fail with an actionable error while any legacy people, memberships, or
     stored person-entity arrays remain;
   - remove mention/title-inference columns and indexes;
   - add nullable roster identity to organizations;
   - add required roster identity and provenance to people and memberships;
   - add named uniqueness constraints and indexes.
4. Add `pipeline/roster_contracts.py`. Its only responsibility is typed roster
   payloads, counters, and domain errors.
5. Add `pipeline/legistar_roster.py`. Its only responsibility is validating
   Legistar Bodies and OfficeRecords responses. It reuses
   `pipeline.agenda_legistar.build_legistar_session`; helpers never import the
   sync operation.
6. Extend the existing rollout registry with explicit `roster_source`,
   `roster_body_name`, and `roster_source_verified_at` fields. An enabled city
   is not roster-authorized unless those fields name a verified source.
7. Add `pipeline/roster_sync.py`. Its only responsibility is exact
   organization-to-body resolution and atomic roster reconciliation:
   - person and membership identity is tenant-scoped by `legistar_client`;
   - body names match exactly after whitespace/case normalization;
   - the configured body name must resolve to exactly one active body;
   - missing or ambiguous bodies produce no people-facing records;
   - transport or malformed-payload failures preserve the last verified
     roster and report failure;
   - a structurally valid empty response is authoritative and clears the
     approved body's roster;
   - registry revocation commits before unrelated authorized-source fetches,
     so provider failure cannot preserve publication after authorization is
     removed; stale database provenance never overrides current authorization;
   - a successful governing-body change depublishes the superseded body's
     roster in the same transaction;
   - successful responses upsert source people/memberships, remove stale
     memberships, and delete orphan people.
8. Add `scripts/sync_rosters.py` as the explicit operator entrypoint. Roster
   synchronization is not inserted into the profiled batch pipeline because
   remote roster I/O would make baseline runs network-dependent.
9. Delete the document-derived linker, its title/fuzzy helpers, its profiling
   reset path, and PERSON extraction from stored NLP entity payloads. Remove
   the People Linking batch step while leaving source document text unchanged.
10. Make the people route require both roster-backed rows and current registry
    authorization. Omit meeting `people_metadata` entirely because the current
    event-to-organization link is heuristic, not independent body evidence.
    Delete the `include_mentions` diagnostic contract and undated fallback.
11. Delete synthetic demo people and demo `people_metadata`; demo source
    records remain available.
12. Raise the profile-manifest contract to schema version 2, remove the people
   phase, and move its four-document quota into entity coverage. Check in a v2
   manifest derived from the same 30 catalog IDs. Do not check in a v2
   expected baseline until a post-change baseline-valid run is captured.
13. Synchronize policy, architecture, operations, performance, and roadmap
    text; then run independent pre-commit review and all required gates.

**f) Reuse audit.**

- Reuse `Place.legistar_client`, `build_legistar_session`, `db_session`,
  existing model relationships, profile-manifest validation, and Alembic
  runtime.
- New typed modules are required because OfficeRecords is a new untrusted
  payload boundary and no current module owns roster records.
- Delete `person_linker`, `person_cache`, `person_mutations`, `person_names`,
  `person_selectors`, `profile_manifest_people`, and `utils_matching`.
- Do not retain aliases, wrappers, old patch targets, or a second inferred
  people path.

**g) Data contracts.**

- `RosterBody`: Legistar body ID/GUID and canonical name.
- `RosterOfficeRecord`: source record/person/body IDs, full name, title,
  membership type, term dates, and source-modified UTC timestamp.
- `RosterRunCounts`: selected, synchronized, and depublished cities plus
  created, updated, and deleted people and memberships. Provider failures
  raise typed roster errors instead of returning partial success counts.
- ORM rows store only roster identity, names, public role/term facts, source
  URL, and UTC synchronization metadata. Email, phone, address, biography,
  and image fields are not ingested.

**h) Schema and migration.**

- Revision: `0002_roster_gated_people`, down revision `0001_v10_baseline`.
- `organization`: nullable `legistar_body_id`, `legistar_body_guid`,
  `roster_source_url`, `roster_synced_at`; unique place/body pair.
- `person`: required `legistar_client`, `legistar_person_id`,
  `roster_source_url`, `roster_synced_at`; unique client/person pair.
- `membership`: required `legistar_client`, `legistar_office_record_id`,
  `legistar_office_record_guid`, `roster_source_url`,
  `roster_last_modified_at`, `roster_synced_at`; required `start_date`;
  unique client/office-record pair.
- Remove `person.image_url`, `person.biography`, `person.current_role`,
  `person.is_elected`, and `person.person_type`.
- Upgrade refuses to continue until the explicit remediation command reports
  and deletes policy-invalid derived rows.
  Downgrade fails before DDL because restoring the document-derived people
  schema could re-enable prohibited publication. Production recovery is
  roll-forward; backups are restored only in isolation.

## 3. Security & Data Governance

**i) Security boundary.** The new outbound boundary is the public Legistar Web
API. HTTPS, bounded connect/read timeouts, existing GET-only retries, strict
payload validation, and fail-closed publication preserve `SECURITY.md`
controls. No inbound endpoint or permission changes.

**j) Secrets.** None. No credentials, keys, environment variables, or remote
defaults are added.

**k) Person data.** This task deliberately changes person-level persistence.
It conforms to Data Governance Section 3 by retaining only public official
membership facts from OfficeRecords. Non-roster names remain only in source
documents and extracted source text. The migration removes legacy derived
people and memberships.

**l) Untrusted input.** Legistar JSON is validated before ORM use. Required
integer IDs, names, body identity, and dates reject malformed payloads.
HTML or contact/profile fields are ignored. Source-document person entities
are no longer parsed by a person-linking operation.

## 4. Code Health

**m) Conformance.** New and modified typed code has complete annotations.
Functions have one responsibility, at most four parameters, bounded nesting,
named constants, timezone-aware UTC timestamps, and specific domain errors.
No broad exception, inline environment read, import-time network call, or new
Ruff exception is added.

**n) Antipattern scan, plan pass.**

- A1/H1: SQLAlchemy 2.0 constraints and Alembic 1.18 operations were verified
  with Context7. Legistar has no Context7 library; its official Web API help
  verified Bodies and OfficeRecords endpoints and response fields.
- B1/F1: three focused modules are the minimum needed to separate untrusted
  payload parsing from persistence; no generic client, registry, or utility
  layer is added.
- B2/C1/C2: the inferred linker and obsolete test seams are deleted rather
  than preserved.
- D1-D3: tests assert stored provenance, API/index output, transaction
  behavior, and deleted contracts; no skip or tolerance changes.
- E1-E3: v1 artifacts remain immutable; only a new v2 manifest is added.
- A2-A4, B3, F2, H2-H4: no violations planned.

**o) Ratchets.** Remove the `pipeline/person_linker.py` C901 exception and
remove `pipeline/profile_manifest_people.py` from Mypy. Add the three new
roster modules and script to the typed set where applicable. No rule,
allowlist, exclusion, or coverage threshold is widened.

**p) Dead code and duplication.** Delete seven production modules, three
obsolete test files, the fuzzy benchmark, the mention diagnostic, the people
profile-manifest stratum, and the batch linker step. Expected production-code
delta is negative after the new roster boundary is added.

## 5. Testing

**q) Edge and failure scenarios.**

1. A city has no `legistar_client`: no people-facing data is created.
2. No exact body or multiple exact bodies: that organization remains empty.
3. Provider timeout/HTTP error: last verified roster remains and sync fails.
4. Malformed JSON, IDs, names, or dates: no partial city mutation.
5. Missing optional title/end date: membership remains authoritative.
6. Repeated sync: no duplicate people or memberships.
7. Changed record: public name/title/dates and source metadata update.
8. Removed record: membership disappears and orphan person is deleted.
   A validated empty roster removes every record for the approved body.
9. Same numeric IDs in different clients: composite source identity prevents
   collision.
10. Legacy database upgrade fails before explicit remediation, then succeeds
    after apply; old people/memberships/person entity arrays disappear and
    provenance constraints are active.
11. Ordinary and semantic meeting metadata omit people because events lack
    independently verified Legistar body identity.
12. Existing stale search documents and revoked registry approvals: roster
    sync depublishes stored roster rows, while the transition's replacement
    reindex removes every obsolete people projection.
13. Underscores in city slugs remain literal during database matching, and a
    governing-body change leaves only the newly authorized body published.
14. Registry body names use the same case and whitespace normalization as
    source resolution; equal person names use a stable person-ID tie-breaker.
15. Dry-run and apply remediation inventories compare stable counts rather
    than their intentionally different operation modes.
16. Historical manifest v1: rejected for active preparation as
    non-comparable.
17. Manifest v2: preserves 30 documents, removes people resets, and uses eight
    entity candidates.
18. An OfficeRecord reassigned to a corrected person identity deletes the
    displaced person only when no other roster membership still references it.
19. A seeded organization whose name differs only by case or whitespace is
    reused rather than duplicated during roster synchronization.
20. People-list and person-detail authorization both accept canonical stored
    body names containing repeated internal whitespace.

**r) Test mapping.**

| Tests | Scenarios |
|---|---|
| `tests/test_legistar_roster.py` | 2-5, 9 |
| `tests/test_roster_sync.py`, `tests/test_roster_sync_cli.py` | 1-9, 12-13, 18-19 |
| `tests/test_person_remediation.py` | 10, 15 |
| `tests/test_alembic_migrations.py` | 10 |
| `tests/test_people_endpoint_filters.py` | 1, 10, 12-14, 20 |
| `tests/test_indexer_official_roster.py` | 1, 2, 11 |
| `tests/test_run_pipeline_orchestration.py` | inferred linker deletion |
| `tests/test_profile_manifest_builder.py`, `tests/test_profile_pipeline_cli.py` | 16-17 |
| Existing API, search, migration, database, docs, and guardrail suites | regression |

**s) Fakes and mocks.** HTTP tests fake `requests.Session` at
`pipeline.legistar_roster`; roster persistence tests use the approved database
boundary. No facade, re-export, or unit-under-test is mocked.

**t) Verification rows.** Apply schema/migration, API/search, guardrail/tooling,
docs, and broad cross-cutting rows. Run the complete coverage-gated Python
suite and frontend tests because people API output is rendered by the
frontend.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_legistar_roster.py \
  tests/test_roster_sync.py \
  tests/test_alembic_migrations.py \
  tests/test_people_endpoint_filters.py \
  tests/test_indexer_official_roster.py \
  tests/test_run_pipeline_orchestration.py \
  tests/test_profile_manifest_builder.py

./.venv/bin/ruff check .
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_api.py
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_query_builder_filters.py \
  tests/test_query_builder_parity_search_vs_trends.py
TEST_POSTGRES_DATABASE_URL=postgresql://town_council:town_council@localhost:5432/town_council_db \
  PYTHONPATH=. .venv/bin/pytest -q tests/test_alembic_migrations.py
PYTHONPATH=. .venv/bin/python -m pytest -q --cov \
  --cov-config=.coveragerc --cov-report=term-missing:skip-covered tests/
(cd frontend && npm test)
git diff --check
```

Production transition. Writers remain stopped until schema parity, roster
sync, and full replacement reindex all succeed:

```bash
docker compose stop \
  api crawler pipeline pipeline-batch extractor worker enrichment-worker \
  semantic-worker nlp tables topics
bash ./scripts/backup_db.sh backups/pre_roster_gate.sql.gz
gzip -t backups/pre_roster_gate.sql.gz
PYTHONPATH=. .venv/bin/python scripts/remediate_legacy_people.py
PYTHONPATH=. .venv/bin/python scripts/remediate_legacy_people.py --apply
PYTHONPATH=. .venv/bin/python pipeline/db_migrate.py
PYTHONPATH=. .venv/bin/python scripts/check_schema_parity.py
PYTHONPATH=. .venv/bin/python scripts/sync_rosters.py --dry-run
PYTHONPATH=. .venv/bin/python scripts/sync_rosters.py --apply
PYTHONPATH=. .venv/bin/python pipeline/reindex_only.py --replace-all
docker compose start \
  api crawler pipeline pipeline-batch extractor worker enrichment-worker \
  semantic-worker nlp tables topics
```

Evidence-integrity validation is active. Use diagnostic mode for investigation;
it keeps the resulting evidence non-comparable:

```bash
PYTHONPATH=. .venv/bin/python scripts/profile_pipeline.py \
  --mode baseline \
  --manifest profiling/manifests/baseline_representative_v2.txt \
  --diagnostic
```

No v1-to-v2 comparison is allowed. City Coverage Expansion requires the
checked-in v2 expectation to remain tied to baseline-valid, reproduced
evidence.

**v) Rollback.** This governance transition is roll-forward in production.
Keep a roster-gated build running with people publication disabled until
roster synchronization and reindex recovery succeed. The pre-migration backup
or an old release may be restored only in an isolated forensic environment;
never restart it as the serving runtime because it can re-derive prohibited
people records. No source documents are changed.

**w) Docs synchronization.**

- `AGENTS.md`: mark the roster gate enforced while retaining its invariant.
- `ARCHITECTURE.md`: replace document-derived people enrichment with explicit
  roster synchronization.
- `README.md`: remove people-linker hot-path claims.
- `docs/DATA_GOVERNANCE.md` and `docs/ADR.md`: mark runtime enforcement and
  remediation complete.
- `docs/OPERATIONS.md`: migration, dry-run/apply, fail-closed, reindex, and
  rollback procedure.
- `docs/PERFORMANCE.md`: classify v1 as historical/non-comparable and document
  the v2 capture gap.
- `ROADMAP.md`: retain T-GOV-2A as the City Coverage Expansion prerequisite
  and mark it satisfied only after verification.

## 7. Delivery Self-Audit

**x) Diff scan.** Re-run A-F/H. Reject old linker aliases, dual authority
paths, inferred roster matching, hardcoded body IDs, contact/profile
ingestion, swallowed provider failures, undated index fallback, v1 mutation,
new lint debt, or edits outside ownership.

**y) Evidence.** Report the tests-first failures, migration upgrade and
downgrade refusal,
live endpoint inventory without person names, Ruff, Mypy, targeted tests,
coverage suite, frontend tests, independent reviews, commit hashes, PR URL,
and final CI. Mark unrun commands `NOT VERIFIED`.

**z) Deviations.** Expected deviations are none. A new dependency,
environment variable, body-ID configuration, changed source document,
cross-version baseline comparison, unresolved P1/P2, or unrun required gate
blocks delivery.
