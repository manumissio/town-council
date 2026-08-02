# T-IDX-1: Delete Obsolete People Index Projections

`artifact_contract: ce-unified-plan/v1`  
`artifact_readiness: implementation-ready`  
`execution: code`

## 1. Context & Alignment

**a) Driver.** T-GOV-2A stopped deriving meeting officials from documents, but
the old search projection still survives in Meilisearch settings, lexical
response handling, indexing query joins, and the frontend. New rows omit the
fields, yet a pre-transition index can still return `people_metadata` and the
UI can render it as verified officials. T-IDX-1 deletes that complete obsolete
path before the Meilisearch SDK and ResultCard migrations.

**b) Canonical documents consulted.**

- `AGENTS.md`: the roster gate is a hard invariant; person-data and facade
  deletions require a Full plan, tests first, exact ownership, and the complete
  verification rows.
- `docs/DATA_GOVERNANCE.md` sections 2-3: only a current approved OfficeRecords
  roster may authorize people-facing records; event-to-body linkage is not
  authoritative.
- `docs/TESTING.MD`: use database, Meilisearch, filesystem, and rendered
  frontend behavior as the approved boundaries; do not preserve patch seams.
- `docs/ENGINEERING_GUARDRAILS.md`: Ruff configuration remains authoritative;
  no allowlist expansion is permitted.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`: T-IDX-1 is the next P1 deletion
  after T-SEM-1 and must remove obsolete fields rather than alias them.
- `docs/reviews/architecture-review-2026-07-19.html`: remove generational
  compatibility strata instead of adapting them during dependency upgrades.

**c) Remediation alignment.** T-IDX-1 owns exactly these 22 paths:

- `docs/plans/T_IDX_1_OBSOLETE_PEOPLE_INDEX_PROJECTION_DELETION_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `README.md`
- `ARCHITECTURE.md`
- `ROADMAP.md`
- `docs/ADR.md`
- `docs/DATA_GOVERNANCE.md`
- `docs/OPERATIONS.md`
- `pipeline/indexer.py`
- `pipeline/indexer_documents.py`
- `pipeline/indexer_meilisearch.py`
- `api/search/support_core.py`
- `api/search_read_routes.py`
- `api/search_read_results.py` (delete)
- `frontend/app/page.js`
- `frontend/components/ResultCard.js`
- `frontend/components/PersonProfile.js` (delete)
- `frontend/components/__tests__/ResultCard.people-projection.test.js` (new)
- `tests/test_api.py`
- `tests/test_indexer_logic.py`
- `tests/test_indexer_official_roster.py`
- `tests/test_repository_guardrails.py`

No other tracked path may change. The Meilisearch SDK migration, FastAPI
migration, Torch security patch, Tailwind migration, and T-FE-1 remain separate
tasks.

**d) Decision-gate check.** G4 was approved as roster-gated person linking and
implemented by T-GOV-2A. This task deletes the current obsolete implementation;
it does not make meeting-person projection permanently unavailable. A future
projection would require independently authoritative event-to-body identity and
separate authorization. T-IDX-1 does not depend on or foreclose G1-G3 or G5.

## 2. Design

**e) Step-by-step approach.**

1. Register this plan and mark T-SEM-1 complete/T-IDX-1 active in the shared
   remediation ledger.
2. Add failing tests before implementation for index settings, lexical
   retrieval, indexing joins/call signatures, deleted modules/components, and
   frontend rendering.
3. Delete `_select_official_memberships_for_event`, the
   `membership_selector` parameter, membership imports, and membership eager
   loading used only by indexing.
4. Remove `people` from Meilisearch searchable and filterable settings.
5. Remove `people_metadata` from lexical attributes, delete truncation calls,
   and delete `api/search_read_results.py`.
6. Delete ResultCard official rendering, its state and callback, the page-level
   selected-person modal path, and the now-unreachable `PersonProfile.js`.
7. Preserve roster-backed `/people` and `/person/{id}` routes; source-document
   names remain searchable through municipal source text.
8. Update canonical docs to describe deletion of the current meeting projection
   while preserving the future authoritative-identity condition, and require a
   full replacement reindex during a maintenance window.
9. Run targeted and complete verification, simplify the diff, obtain an
   independent pre-commit review, apply eligible P1/P2 findings, commit, push,
   open one PR, and watch review/CI to a decided state.

No new production function or module is introduced. The new frontend test is
an explicit structural regression guard for the deleted search-driven official
profile path; API and build tests cover observable request and compilation
behavior.

**f) Reuse audit.** Extend the existing meeting index builder, Meilisearch
settings constants, lexical request builder, route tests, repository deletion
guards, and Node source-contract tests. No sanitizer, response wrapper, people
alias, migration adapter, or second profile component is added. The deleted
`api/search_read_results.py` and `PersonProfile.js` have no remaining caller.

**g) Data contracts.** Existing search responses remain dictionaries, but
`people_metadata` and `people` cease to be recognized meeting/agenda search
fields. Roster-backed people endpoint payloads remain unchanged. No new typed
contract is needed because this task deletes fields and adapters.

**h) Schema/migration impact.** None. Existing Meilisearch documents are
derived state, not the system of record. Deployment must stop writers and
readers, run the existing in-place replacement reindex, verify it, and restart
only after success. The serving index is cleared and repopulated; publication
is not atomic.

## 3. Security & Data Governance

**i) Security-sensitive paths.** None of the owned paths are in the
`AGENTS.md` security-sensitive list. The privacy boundary becomes stricter:
Meilisearch and the search UI lose the ability to publish historical
document-derived officials. `SECURITY.md` credential, proxy, and key controls
do not change.

**j) Secrets.** No credential, key, environment variable, port, permission, or
working default changes.

**k) Person data.** Yes. This task deletes meeting-level person projection and
exposure. It conforms to Data Governance section 3 and approved G4: only
independently roster-backed `/people` records remain publishable. It creates no
person, membership, alias, inference, or cross-city aggregation.

**l) Untrusted input.** Scraped municipal text remains searchable and continues
through existing extraction and frontend HTML sanitization boundaries. It no
longer becomes an officials list. Meilisearch responses remain untrusted, but
the request no longer asks for retired person fields.

## 4. Code Health

**m) GED conformance sweep.** The implementation primarily deletes code. The
meeting builder loses one callable parameter and one branchless selector. No
new nesting, broad handler, timestamp, environment read, runtime literal, or
import-time side effect is added. Existing domain names and error behavior are
preserved.

**n) Antipattern scan, plan pass.**

- A1/H1: no new external API call is introduced. Existing Meilisearch settings
  and replacement-index APIs are reused unchanged.
- B1-B3: no wrapper, registry, compatibility field, sanitizer, retry, or
  defensive response scrubber is added.
- C1-C2: the selector, truncation module, modal component, callback path, and
  stale fields are deleted rather than retained under new names.
- D1-D3: tests strengthen absence and observable request/UI contracts; no skip,
  tolerance, call-count assertion, or fake of the unit under test is added.
- E1-E3: edits stay inside the 22 owned paths; no broad formatting or generated
  artifact update is planned.
- F1-F2: no sibling implementation or second shared location is created.
- H2-H4: no type suppression, hand-rolled trust-boundary model, or import-time
  execution is introduced.

**o) Ratchet interaction.** `pipeline/indexer.py` and
`pipeline/indexer_meilisearch.py` retain their existing BLE001 boundaries; this
task neither touches those handlers nor widens the allowlist. No Ruff selector,
formatter scope, typed-subtree scope, coverage floor, or CI gate changes.

**p) Dead code and duplication audit.** Delete two obsolete modules/components,
one empty selector, one injected callable, two eager-load clauses, two
Meilisearch settings entries, one lexical attribute, one route postprocessor,
one ResultCard state path, one page modal path, and their stale tests/imports.
Expected net production delta is substantially negative.

## 5. Testing

**q) Edge cases and failure scenarios.**

1. A roster-backed organization on a meeting must not recreate person fields.
2. Full and targeted indexing must not eager-load memberships or accept a
   membership selector.
3. Meilisearch settings must contain neither `people` nor `people_metadata`.
4. Lexical search must not request retired person fields.
5. Historical fake hits containing the fields must not keep a dedicated
   truncation or rendering contract alive.
6. Agenda-item and non-person meeting fields must remain unchanged.
7. Semantic hits must remain person-free.
8. The home page must not retain selected-person state, callback plumbing, or a
   search-driven profile modal.
9. Roster-backed people endpoints must remain available.
10. A deployment without replacement reindex can retain stale derived fields;
    the operations contract must require replacement before restart.

**r) Tests added or updated.**

| Test | Scenarios |
|---|---|
| `test_indexer_official_roster.py` meeting and semantic absence contracts | 1, 6, 7 |
| `test_indexer_logic.py` builder/query contracts | 2, 6 |
| `test_api.py` lexical attributes and people endpoint coverage | 4, 5, 9 |
| New `ResultCard.people-projection.test.js` structural deletion guard | 5, 8 |
| `test_repository_guardrails.py` deleted-file and forbidden-token guard | 2-5, 8 |
| Existing index recovery/settings tests | 3, 6, 10 |
| Existing query parity and frontend tests | 4, 6, 8, 9 |

Tests are written and run red before implementation. No fixed total-test count
is asserted.

**s) Fakes and mocks.** Existing API tests fake the approved Meilisearch client
boundary at `api.search.support_core.client`. Indexer tests use database/model
fixtures and direct pure builders. The Node test uses the approved filesystem
boundary. No facade, re-export, private helper, or injectable production
callable is patched.

**t) Verification rows.** Apply API/search behavior, frontend contract,
frontend component behavior, guardrail/tooling, and docs-only rows. Run the
complete coverage suite because the change crosses indexing, API, frontend,
governance, and derived-data boundaries.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-idx-1-delete-people-index-projection
```

Tests-first evidence:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_indexer_official_roster.py \
  tests/test_indexer_logic.py \
  tests/test_api.py \
  tests/test_repository_guardrails.py
cd frontend && node --test --test-name-pattern='people projection' \
  components/__tests__/*.test.js
```

Final verification:

```bash
./.venv/bin/ruff check .
./.venv/bin/ruff format --check . --config ruff-format.toml
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_indexer_logic.py tests/test_indexer_official_roster.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_api.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_query_builder_filters.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_query_builder_parity_search_vs_trends.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_frontend_pages_config.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_resultcard_agenda_status_refresh.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_search_sort_ui_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_semantic_search_ui_guardrails.py
cd frontend && npm test
cd frontend && npm run build
PYTHONPATH=. .venv/bin/pytest -q
PYTHONPATH=. .venv/bin/python -m pytest -q --cov --cov-config=.coveragerc \
  --cov-report=term-missing:skip-covered tests/
git diff --check
git status --short
```

Operational acceptance during the deployment maintenance window:

```bash
REINDEX_COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.dev.yml)
"${REINDEX_COMPOSE[@]}" stop \
  api crawler pipeline pipeline-batch extractor worker enrichment-worker \
  semantic semantic-worker nlp tables topics
"${REINDEX_COMPOSE[@]}" up -d postgres redis meilisearch
"${REINDEX_COMPOSE[@]}" run --rm --no-deps pipeline \
  python reindex_only.py --replace-all
"${REINDEX_COMPOSE[@]}" exec -T meilisearch sh -c \
  'wget -qO- http://localhost:7700/health'
STARTUP_PURGE_DERIVED=false "${REINDEX_COMPOSE[@]}" up -d --build
```

Delivery uses two commits:

1. `docs(remediation): authorize T-IDX-1 projection deletion`
2. `refactor(index): delete obsolete people projections`

Push the branch, open one PR titled `T-IDX-1: Delete obsolete people index
projections`, request Codex review, and watch required checks to a decided
state.

**v) Rollback.** Revert the T-IDX-1 merge commit and run the same static,
targeted, frontend, and complete-suite checks. If a replacement index was
already published, rebuild it again with the reverted code. No database
migration or data repair is required. Rollback knowingly restores the obsolete
search projection and should be used only for a verified non-person search
regression.

**w) Docs synchronization.**

- `README.md`: state that the current meeting people projection is removed,
  while roster-backed people endpoints remain.
- `ARCHITECTURE.md`: remove `people_metadata` as a current meeting index
  contract and record roster/search boundary ownership.
- `ROADMAP.md`: record completed deletion of the obsolete implementation
  without foreclosing a future independently authorized projection.
- `docs/ADR.md`: record implementation completion of the approved G4 decision.
- `docs/DATA_GOVERNANCE.md`: distinguish removed meeting projection from
  retained roster-backed people publication.
- `docs/OPERATIONS.md`: require replacement reindex and remove stale projection
  language.
- Remediation plan: version/status/ownership/execution-order updates.

No OpenAPI, security, testing-policy, performance, or inference documentation
changes.

## 7. Delivery Self-Audit

**x) Antipattern scan, diff pass.** Re-run A-F/H against the actual diff.
Reject any people alias, response scrubber, compatibility wrapper, retained
selector, test seam, unrelated ResultCard lifecycle refactor, UI redesign,
Meilisearch SDK migration, allowlist widening, or path outside ownership.

**y) Evidence.** Report the tests-first failures, every command from 6u with
PASS/FAIL, exact pass/skip/fail and coverage totals, frontend test/build output,
planning-review and pre-commit-review findings, commit hashes, PR URL, review
thread count, and final CI state. Mark operational replacement reindex as
deployment-required if it is not run locally.

**z) Deviations.** Expected deviation report: none. Any extra file, retained
person projection, altered roster endpoint, new compatibility code, skipped
review, unresolved P1/P2, unrun required gate, or absent replacement-reindex
instruction is a blocker.
