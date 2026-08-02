# T-PLAT-2E: Migrate the Meilisearch Python SDK

`artifact_contract: ce-unified-plan/v1`  
`artifact_readiness: implementation-ready`  
`execution: code`

## 1. Context & Alignment

**a) Driver.** The repository pins Meilisearch's Python SDK at 0.31.0 while
0.43.0 is the current published release. The old integration retains a
dictionary task-ID adapter and a two-method filtered-delete fallback even
though the supported SDK returns typed models and exposes one filtered-delete
API. This task upgrades the shared client, deletes those compatibility strata,
and proves it against the retained Meilisearch v1.6 server before the remaining
dependency migrations proceed.

**b) Canonical documents consulted.**

- `AGENTS.md`: dependency calls must be verified; the Meilisearch trust
  boundary, exact ownership, tests-first work, complete verification, and
  security impact reporting apply.
- `docs/TESTING.MD`: fake the Meilisearch client only where constructed and do
  not preserve production patch targets for tests.
- `docs/ENGINEERING_GUARDRAILS.md`: Ruff configuration owns BLE001 boundaries;
  remove stale entries rather than widening them.
- `SECURITY.md`: API and semantic readers retain scoped search keys while
  writers retain the master key; backing stores remain Compose-network only.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`: T-PLAT-2E follows T-IDX-1 and
  owns one deliberate SDK migration rather than the closed raw Dependabot PR.
- `docs/reviews/architecture-review-2026-07-19.html`: compatibility layers are
  retired only through narrow, evidence-backed tasks.

**c) Remediation alignment.** T-PLAT-2E owns exactly these 17 paths:

- `docs/plans/T_PLAT_2E_MEILISEARCH_SDK_MIGRATION_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `docs/ADR.md`
- `constraints.txt`
- `pipeline/indexer.py`
- `pipeline/indexer_meilisearch.py`
- `ruff.toml`
- `tests/test_api.py`
- `tests/test_async_flow.py`
- `tests/test_backlog_maintenance_laserfiche_guard.py`
- `tests/test_docker_build_contracts.py`
- `tests/test_extract_task.py`
- `tests/test_indexer_logic.py`
- `tests/test_pipeline_batching.py`
- `tests/test_repository_guardrails.py`
- `tests/test_tasks_agenda_summary_format.py`
- `tests/test_tasks_vote_extraction_flow.py`

No other tracked path may change. T-IDX-1 merged as PR #217 and T-PLAT-2D
merged as PR #218. T-FE-1 remains separate.

**d) Decision-gate check.** No G1-G5 decision is required or foreclosed. The
operator already approved replacing closed Dependabot PR #197 with an owned
Meilisearch migration. Runtime defaults, server version, gate semantics, and
soak comparability remain unchanged.

## 2. Design

**e) Step-by-step approach.**

1. Register T-PLAT-2E and its ownership in the remediation ledger.
2. Add failing tests before implementation for the exact dependency pin, typed
   task results, filtered deletion, error propagation, and BLE001 ratchet.
3. Change only the shared constraint from `meilisearch==0.31.0` to
   `meilisearch==0.43.0`.
4. Delete `_task_uid`; read `TaskInfo.task_uid` directly from every SDK
   mutation response.
5. Delete `_delete_documents_by_filter`; call
   `Index.delete_documents(filter=...)` directly.
6. Make the four index-setting updates and targeted filtered deletion use the
   existing `_wait_for_task_success` contract with their typed task IDs.
7. Propagate transport errors and completed failed-task states. Settings and
   targeted deletion must not be treated as successful merely because the
   server accepted them asynchronously.
8. Remove `pipeline/indexer_meilisearch.py` from Ruff's BLE001 allowance and
   from the exact broad-handler boundary inventory.
9. Add an ADR entry that supersedes only the task-ID and filtered-delete
   compatibility clauses of the 2026-05-08 indexing decision.
10. Update Meilisearch fakes to return typed-model-compatible objects and update
   the API statistics fixture for the current Pydantic model constructor.
11. Run static, targeted, complete, image-build, and isolated v1.6 runtime
    verification; simplify the diff; obtain independent pre-commit review;
    apply eligible P1/P2 findings; commit, push, open one PR, and watch review
    and CI to a decided state.

No new production function, wrapper, module, registry, or compatibility path is
introduced.

**f) Reuse audit.** Extend the current Meilisearch clients, indexer recovery
helpers, task-ordering tests, Docker dependency contracts, and guardrail
inventory. Reader calls in `api/search/**` and `semantic_service/**` continue to
use `Index.search()` dictionaries and `IndexStats.number_of_documents`. The two
deleted helpers have no valid post-migration role.

**g) Data contracts.** SDK task responses are existing `TaskInfo`, `Task`, and
`TaskResults` models. Production code consumes `task_uid`, `status`, `error`,
and `results` attributes directly. `IndexStats` remains the SDK's typed model;
search responses remain dictionaries at the existing boundary. No project
contract model is added around dependency-owned models.

Verified against the published 0.43.0 source:

- `Client.create_index(uid, options) -> TaskInfo`
- `Client.wait_for_task(uid, timeout_in_ms, interval_in_ms) -> Task`
- `Client.get_tasks(parameters) -> TaskResults`
- `Index.add_documents(documents) -> TaskInfo`
- `Index.delete_documents(ids=None, *, filter=None) -> TaskInfo`
- `Index.delete_all_documents() -> TaskInfo`
- index-setting update methods return `TaskInfo`
- `TaskInfo.task_uid: int`
- `Index.get_stats() -> IndexStats`
- `IndexStats.number_of_documents: int`

Context7's Meilisearch documentation was checked for server task, document,
settings, search, and statistics behavior. The official 0.43.0 SDK source is
authoritative for Python signatures because Context7's Python result describes
a different third-party package.

**h) Schema/migration impact.** None. Meilisearch remains derived state and the
server image remains v1.6. The SDK migration itself requires no database or
index migration. T-IDX-1's deployment replacement reindex remains required and
may run once with the upgraded client.

## 3. Security & Data Governance

**i) Security-sensitive paths.** No owned path is listed as security-sensitive
in `AGENTS.md`, but this task changes the API/pipeline/semantic-to-Meilisearch
dependency boundary. An attacker gains no endpoint, credential, permission, or
network path. `SECURITY.md` control 3 remains intact: readers use
`MEILI_SEARCH_KEY`, writers use `MEILI_MASTER_KEY`, and the service stays on the
Compose network. Runtime smoke output must not print either key.

**j) Secrets.** No credential, key, default, environment variable, port,
workflow permission, or image exposure changes.

**k) Person data.** No person data is created, linked, aggregated, or exposed.
T-IDX-1 has already removed meeting people projections; this migration must not
restore them.

**l) Untrusted input.** Meilisearch HTTP responses remain untrusted at the SDK
boundary. Version 0.43.0 validates task and statistics responses through its
Pydantic models. Search response dictionaries retain existing API validation
and frontend sanitization boundaries.

## 4. Code Health

**m) GED conformance sweep.** Production changes reduce helpers and narrow one
handler. No new nesting, callable parameter, timestamp, environment read,
magic policy literal, broad exception, type suppression, or import-time side
effect is added. Existing task-ordering constants and domain names are reused.

**n) Antipattern scan, plan pass.**

- A1/H1: PyPI and upstream releases confirm 0.43.0 is current; exact calls and
  return types were verified from the tagged official source. There is no
  published 0.43.1.
- A2-A4: no new setting, silent default, placeholder, or unverified completion
  claim.
- B1-B3: no wrapper, registry, dual client, retry, or impossible-condition
  validation is added.
- C1-C2: both superseded helpers and the legacy-method test are deleted; tests
  move to the supported client boundary.
- D1-D3: tests strengthen typed-response and propagation contracts without
  skips, widened tolerances, private production patch targets, or call-order
  assertions unrelated to recovery correctness.
- E1-E3: edits stay within the 17 owned paths and avoid mechanical churn.
- F1-F2: no duplicate SDK adapter or shared location is created.
- H2-H4: no `Any`, ignore, cast, hand-rolled response model, or import-time
  work is introduced.

**o) Ratchet interaction.** Remove one existing `BLE001` selector for
`pipeline/indexer_meilisearch.py`; add or widen none. `pipeline/indexer.py`
retains its approved batch-boundary handler. Ruff rule families, exclusions,
formatter scope, Mypy scope, coverage floor, and CI gates remain unchanged.

**p) Dead code and duplication audit.** Delete `_task_uid`,
`_delete_documents_by_filter`, their facade imports, the fallback branch, the
legacy-method test, and stale SDK-version prose. Replace fake dictionaries with
typed-response-compatible objects. Expected production delta is negative.

## 5. Testing

**q) Edge cases and failure scenarios.**

1. Every settings mutation returns `TaskInfo`; all four task IDs must be waited.
2. Targeted reindex deletion must finish before replacement documents submit.
3. A settings wait transport error or completed failed task aborts indexing.
4. A targeted filtered-deletion wait error or completed failed task prevents
   replacement documents from being submitted.
5. A failed completed task still aborts recovery unless its explicitly accepted
   index-already-exists code matches.
6. Empty pending-task results end the idle wait; persistent work times out.
7. `IndexStats` construction and `number_of_documents` access match SDK 0.43.0.
8. All requirement consumers resolve exactly SDK 0.43.0.
9. Meilisearch v1.6 accepts settings updates, document add/search/stats/task
   listing, filtered deletion, and task waits from SDK 0.43.0.
10. A scoped reader key can search and read stats but cannot add documents or
    update settings. Writer credentials, server image, index settings, and
    people-field absence remain unchanged.

**r) Tests added or updated.**

| Test | Scenarios |
|---|---|
| Docker dependency contract | 8, 10 |
| `test_indexer_logic.py` typed task/settings/delete/recovery tests | 1-6, 10 |
| `test_api.py` current `IndexStats` fixture and search contracts | 7, 10 |
| Async/extract/vote task tests with typed fake tasks | 1, 2, 10 |
| Agenda maintenance, batching, and summary tests with typed delete-task fakes | 1, 2, 10 |
| Repository guardrail BLE001 inventory | 3, 8 |
| Four Docker image dependency inspections | 8, 10 |
| Isolated Meilisearch v1.6 runtime smoke | 1-6, 8-10 |

Tests are written and run red before implementation. No fixed total-test count
is asserted.

**s) Fakes and mocks.** Tests patch the approved Meilisearch client boundary
only where constructed in `pipeline.indexer` or `api.search.support_core`.
Task-result fakes expose the public `task_uid` attribute consumed from the SDK.
The agenda maintenance, batching, and summary tests also return a successful
typed wait result because their observable persistence paths reindex changed
catalogs. No facade, re-export, unit-under-test, or new production seam is
patched.

**t) Verification rows.** Apply API/search behavior, guardrail/tooling,
coverage-gate dependency contracts, and docs-only rows. Run the complete
coverage suite because one shared dependency crosses API, pipeline, and
semantic service images.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-plat-2e-meilisearch-sdk-migration
```

Tests-first red evidence:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_docker_build_contracts.py \
  tests/test_indexer_logic.py \
  tests/test_api.py \
  tests/test_repository_guardrails.py
```

Final local verification:

```bash
./.venv/bin/ruff check .
./.venv/bin/ruff format --check . --config ruff-format.toml
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_indexer_logic.py tests/test_api.py
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_async_flow.py tests/test_extract_task.py \
  tests/test_backlog_maintenance_laserfiche_guard.py \
  tests/test_pipeline_batching.py \
  tests/test_tasks_agenda_summary_format.py \
  tests/test_tasks_vote_extraction_flow.py
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_docker_build_contracts.py tests/test_repository_guardrails.py \
  tests/test_docs_links.py
PYTHONPATH=. .venv/bin/python -m pytest -q --cov --cov-config=.coveragerc \
  --cov-report=term-missing:skip-covered tests/
git diff --check
git status --short
```

Image and runtime acceptance:

```bash
docker build --target python-api -t tc-meili-api:0.43.0 .
docker build --target python-worker-live -t tc-meili-worker-live:0.43.0 .
docker build --target python-worker-batch -t tc-meili-worker-batch:0.43.0 .
docker build --target python-semantic -t tc-meili-semantic:0.43.0 .

for image in \
  tc-meili-api:0.43.0 \
  tc-meili-worker-live:0.43.0 \
  tc-meili-worker-batch:0.43.0 \
  tc-meili-semantic:0.43.0
do
  docker run --rm "$image" python -c \
    'import importlib.metadata as m; assert m.version("meilisearch") == "0.43.0"'
  docker run --rm "$image" python -m pip check
done
```

Run the cleanup-safe isolated server and client smoke below. It verifies the
v1.6 server, typed task/status/stat contracts, filtered deletion, and a scoped
reader's read-only permissions without printing either credential:

```bash
set -euo pipefail
MEILI_SMOKE_NETWORK="tc-meili-sdk-${RANDOM}"
MEILI_SMOKE_CONTAINER="tc-meili-v16-${RANDOM}"
MEILI_SMOKE_MASTER_KEY="$(openssl rand -hex 32)"
cleanup_meili_smoke() {
  docker rm -f "$MEILI_SMOKE_CONTAINER" >/dev/null 2>&1 || true
  docker network rm "$MEILI_SMOKE_NETWORK" >/dev/null 2>&1 || true
}
trap cleanup_meili_smoke EXIT

docker network create "$MEILI_SMOKE_NETWORK" >/dev/null
docker run -d --name "$MEILI_SMOKE_CONTAINER" \
  --network "$MEILI_SMOKE_NETWORK" \
  -e MEILI_ENV=production \
  -e MEILI_MASTER_KEY="$MEILI_SMOKE_MASTER_KEY" \
  getmeili/meilisearch:v1.6 >/dev/null

docker run --rm -i \
  --network "$MEILI_SMOKE_NETWORK" \
  -e MEILI_SMOKE_URL="http://${MEILI_SMOKE_CONTAINER}:7700" \
  -e MEILI_SMOKE_MASTER_KEY="$MEILI_SMOKE_MASTER_KEY" \
  tc-meili-worker-live:0.43.0 python - <<'PY'
import os
import time

from meilisearch import Client
from meilisearch.errors import MeilisearchApiError, MeilisearchCommunicationError

server_url = os.environ["MEILI_SMOKE_URL"]
admin = Client(server_url, os.environ["MEILI_SMOKE_MASTER_KEY"])
deadline = time.monotonic() + 60
while True:
    try:
        health = admin.health()
        break
    except MeilisearchCommunicationError:
        if time.monotonic() >= deadline:
            raise
        time.sleep(0.5)
assert health["status"] == "available"
assert admin.get_version()["pkgVersion"].startswith("1.6.")

index_uid = "tc_sdk_smoke"
creation = admin.create_index(index_uid, {"primaryKey": "id"})
assert admin.wait_for_task(creation.task_uid).status == "succeeded"
search_index = admin.index(index_uid)
settings_tasks = (
    search_index.update_filterable_attributes(["category"]),
    search_index.update_sortable_attributes(["date"]),
    search_index.update_searchable_attributes(["title"]),
    search_index.update_ranking_rules(["sort", "words", "typo", "proximity", "attribute", "exactness"]),
)
for settings_task in settings_tasks:
    assert admin.wait_for_task(settings_task.task_uid).status == "succeeded"

addition = search_index.add_documents([
    {"id": 1, "title": "Budget", "category": "minutes", "date": "2026-08-02"},
    {"id": 2, "title": "Transit", "category": "agenda", "date": "2026-08-03"},
])
assert admin.wait_for_task(addition.task_uid).status == "succeeded"
assert search_index.search("Budget")["estimatedTotalHits"] == 1
assert search_index.get_stats().number_of_documents == 2
assert admin.get_tasks({"indexUids": [index_uid]}).results

deletion = search_index.delete_documents(filter='category = "minutes"')
assert admin.wait_for_task(deletion.task_uid).status == "succeeded"
assert search_index.get_stats().number_of_documents == 1

reader_key = admin.create_key({
    "description": "ephemeral SDK smoke reader",
    "actions": ["search", "stats.get"],
    "indexes": [index_uid],
    "expiresAt": None,
})
reader_index = Client(server_url, reader_key.key).index(index_uid)
assert reader_index.search("Transit")["estimatedTotalHits"] == 1
assert reader_index.get_stats().number_of_documents == 1
for forbidden_call in (
    lambda: reader_index.add_documents([{"id": 3, "title": "Denied"}]),
    lambda: reader_index.update_sortable_attributes(["title"]),
):
    try:
        forbidden_call()
    except MeilisearchApiError:
        continue
    raise AssertionError("scoped reader unexpectedly changed the index")
print("Meilisearch v1.6 SDK and scoped-reader smoke passed")
PY
```

Delivery uses two commits:

1. `docs(remediation): authorize T-PLAT-2E SDK migration`
2. `build(search): migrate the Meilisearch Python SDK`

Push the branch, open one PR titled `T-PLAT-2E: Migrate the Meilisearch Python
SDK`, request Codex review, and watch required checks to a decided state.

**v) Rollback.** Revert the T-PLAT-2E merge commit and validate the restored
0.31.0 application contract rather than rerunning the 0.43-only typed-model
smoke:

```bash
git revert <t-plat-2e-merge-commit>
docker compose build api worker pipeline-batch semantic
docker compose up -d postgres redis meilisearch
docker compose run --rm --no-deps pipeline python reindex_only.py --replace-all
for image in \
  town-council-python-api \
  town-council-python-worker-live \
  town-council-python-worker-batch \
  town-council-python-semantic
do
  docker run --rm "$image" python -c \
    'import importlib.metadata as m; assert m.version("meilisearch") == "0.31.0"'
done
PYTHONPATH=. .venv/bin/pytest -q tests/test_indexer_logic.py tests/test_api.py
```

The reverted indexer contains the legacy task/detection adapter needed by SDK
0.31.0, so its own replacement-reindex path is the rollback acceptance test.
No database migration, server downgrade, or source-data repair is required. If
deployed together with T-IDX-1, do not restore the retired people projection
when rebuilding the index.

**w) Docs synchronization.** Update this Full plan, the remediation ledger, and
`docs/ADR.md`. The new ADR entry supersedes only the task-ID and filtered-delete
compatibility clauses of the 2026-05-08 indexing decision. Existing operations
commands, API contract, architecture map, README, security, testing,
performance, and data-governance text remain accurate.

## 7. Delivery Self-Audit

**x) Antipattern scan, diff pass.** Re-run A-F/H against the actual diff.
Reject surviving compatibility helpers, dictionary task parsing, a new wrapper,
server-image or credential changes, unrelated dependency updates, type
suppression, allowlist widening, or any path outside ownership.

**y) Evidence.** Report tests-first failures, every command from 6u with
PASS/FAIL, exact pass/skip/fail and coverage totals, all image dependency
checks, isolated v1.6 smoke results, planning-review and pre-commit-review
findings, commit hashes, PR URL, unresolved-thread count, and final CI state.

**z) Deviations.** Expected deviation report: none. Any additional path,
server-image change, key or port change, compatibility path, unverified SDK
call, package-resolution failure, skipped runtime gate, unresolved P1/P2, or
unrun required check is a blocker.
