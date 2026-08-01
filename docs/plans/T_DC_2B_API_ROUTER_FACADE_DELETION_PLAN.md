# T-DC-2B: Delete API Router Facade Bags

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: implementation-ready`
`execution: code`

## 1. Context & Alignment

**a) Driver.** T-DC-2A removed reverse search lookups through `api.main`, but
the API assembly layer still passes its module object into lineage and task
routers. Task request helpers also receive models and domain callables only to
preserve historical patch targets, while `api/search_routes.py` republishes a
large compatibility surface unrelated to router assembly. T-DC-2B deletes
these bags so each route reads from its real implementation owner and tests
substitute only approved database and Celery boundaries.

**b) Canonical documents consulted.**

- `AGENTS.md` `<known_antipatterns>`, `<security_sensitive_paths>`,
  `<workflow_contract>`, and `<verification_matrix>` prohibit test-seam
  re-exports and patchability parameters, require a trust-boundary report for
  `api/main.py`, and require API, orchestration, guardrail, docs, and complete
  suite verification.
- `docs/TESTING.MD` requires tests to patch implementation owners and limits
  substitution here to the database and Celery dispatch boundaries.
- `ARCHITECTURE.md` identifies `api.main`, `api.task_routes`, and
  `api.search_routes` as transitional compatibility surfaces.
- `docs/ADR.md` records G3 and the T-DC-2A decision that reserves remaining
  router compatibility bags for T-DC-2B.
- `SECURITY.md` requires authentication, CORS, rate limiting, startup checks,
  and error minimization to remain unchanged.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` orders T-DC-2B after completed
  T-DC-2A and before the remaining deletion tasks.

**c) Remediation alignment.** This is Phase 2 task T-DC-2B in the API
deduplication lane. Its exact `files_owned` set is:

- `docs/plans/T_DC_2B_API_ROUTER_FACADE_DELETION_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `api/main.py`
- `api/search_routes.py`
- `api/search_support.py` (delete)
- `api/lineage_routes.py`
- `api/catalog_routes.py`
- New `api/catalog_summary_state.py`
- `api/task_routes.py`
- `api/task_dispatch.py`
- `api/task_route_generation.py`
- `api/task_route_segmentation.py`
- `api/task_route_summary.py`
- `api/task_route_support.py`
- `tests/test_api.py`
- `tests/test_async_flow.py`
- `tests/test_catalog_lineage_endpoint.py`
- `tests/test_extract_endpoint.py`
- `tests/test_summary_staleness.py`
- `tests/test_topics_staleness.py`
- `tests/test_task_facade_cleanup.py`
- `tests/test_search_support_facade.py` (delete)
- `tests/test_repository_guardrails.py`
- `ARCHITECTURE.md`
- `docs/ADR.md`
- `docs/PIPELINE.md`
- `docs/TESTING.MD`

No other tracked file may change.

**d) Decision-gate check.** G3 is satisfied by T-GOV-1. T-DC-2B neither
depends on nor forecloses G1, G2, G4, or G5. It preserves runtime defaults,
route contracts, Celery task identity, and soak comparability.

## 2. Design

**e) Step-by-step approach.**

1. Add failing repository guards that reject `sys.modules[__name__]`, module
   facade parameters, route-level model/callable injection, compatibility
   exports from `api.main`, `api.task_routes`, and `api.search_routes`, and
   restoration of deleted `api/search_support.py`.
2. Repoint API tests from `api.main` aliases to observable database behavior
   or `api.task_dispatch`'s existing Celery dispatch boundary. Preserve the
   Docker-style `main:app` import test without mutating module aliases.
3. Remove `lineage_facade` from `build_lineage_router`; call `_lineage_rows`
   directly and exercise it through the injected database session.
4. Move shared summary-input resolution from `api.catalog_routes` to the
   focused `api.catalog_summary_state` owner. Both catalog and task routes call
   that owner directly; the new module never imports a route or app facade.
5. Remove `task_facade` from `build_task_router` and all five task request
   helpers. Import `Catalog`, `AgendaItem`, quality policy, freshness logic,
   summary-input resolution, and `api.task_dispatch` from their real owners.
6. Change task-status lookup to construct Celery `AsyncResult` in
   `api.task_route_support`, where the name is used. Keep UUID validation and
   task result payloads unchanged.
7. Reduce `api.task_routes` to route assembly and rate-limit constants. Delete
   `_CeleryTaskProxy`, task proxy globals, and the callable-taking enqueue
   wrapper. The focused `api.task_dispatch.enqueue_task` sends the existing
   named Celery task through `celery_app.send_task`, preserving arguments,
   failure mapping, and the existing short operation key in structured error
   logs.
8. Reduce `api.search_routes` to an `APIRouter` aggregator. Delete all search
   compatibility aliases and its `__all__` export bag, then delete the now
   unreferenced pure re-export module `api/search_support.py` and its obsolete
   facade-preservation test.
9. Remove `sys`, lineage/task aliases, and module-object injection from
   `api.main`. Keep app construction, middleware, auth dependencies, route
   registration order, startup, health, and stats behavior unchanged.
10. Update canonical architecture, pipeline, testing, ADR, and remediation records to
   describe direct ownership and mark T-DC-2B complete only after verification.
11. Run simplification and a fresh subagent pre-commit review. Resolve every
    eligible P1/P2 finding before delivery.

The new `api.catalog_summary_state` module has one responsibility: resolve the
document kind and current summary source hashes shared by catalog and task
routes. Import direction remains `api.main` to router builders, router helpers
to domain implementations, and domain implementations never back to `api.main`
or a route aggregator.

**f) Reuse audit.** Reuse `api.task_dispatch` as the existing Celery boundary,
and move the existing `_summary_doc_kind_and_hashes` implementation unchanged
to `api.catalog_summary_state` because no current focused shared owner fits.
Reuse `pipeline.agenda_resolver`, `pipeline.summary_quality`,
`pipeline.summary_freshness`, and `pipeline.content_hash` as domain owners.
`api.search_routes` remains only because combining three routers is a real app
assembly responsibility. `api/search_support.py` and its obsolete test are
deleted in the same change. No registry, wrapper, compatibility alias, or
second implementation is introduced.

**g) Data contracts.** Existing route response dictionaries remain unchanged.
No new trust-boundary payload is introduced. The internal builder contracts
lose only fake dependencies: `lineage_facade`, `task_facade`, model classes,
logger objects, and domain callables. Real runtime dependencies remain the
FastAPI limiter, database dependency, and API-key dependency.

**h) Schema/migration impact.** None. No database columns, migrations,
timestamps, stored values, or transaction behavior change.

## 3. Security & Data Governance

**i) Security-sensitive paths.** `api/main.py` is security-sensitive because
it owns auth wiring, CORS, rate limiting, lifespan checks, and the global error
interceptor. T-DC-2B changes only router imports and builder arguments. An
attacker gains no endpoint, credential, error detail, or origin capability.
The `SECURITY.md` controls for API-key verification, restricted CORS,
rate-limited mutation routes, startup checks, and minimized 500 responses are
preserved and covered by existing tests.

**j) Secrets.** No credential, key, environment variable, or default changes.

**k) Person data.** No person-level data is created, linked, aggregated, or
exposed. The roster-gated G4 policy is unaffected.

**l) Untrusted input.** Path/query values, task IDs, and database content
continue through existing FastAPI validation, UUID parsing, quality policy,
and ORM query boundaries. No new scraped-content or rendering path is added.

## 4. Code Health

**m) GED conformance sweep.** Modified functions have one responsibility and
complete annotations where already typed. Removing injected bags reduces
parameter counts and `Any` usage. Named route limits and task names remain
constants. Existing typed HTTP errors and broker failure handling remain.
No timestamp or environment read changes occur.

**n) Antipattern scan, plan pass.**

- A1/H1: no external API signature changes are planned; FastAPI and Celery
  calls remain byte-for-byte at their established owners.
- B1/B2/C1/F1: the change deletes wrappers and compatibility exports rather
  than adding an abstraction or retaining two paths.
- B3: no new validation or retry branch is added.
- C2/D1/D2: tests move to approved boundaries without a new seam, skip,
  tolerance change, or weakened assertion.
- D3: exact absence assertions are accepted only in repository guardrails;
  route tests assert HTTP payloads and persistence/dispatch effects.
- E1/E2/E3: edits stay inside the owned set and update stale architecture
  prose; no broad formatting occurs.
- A2-A4, F2, H2-H4: no violations planned.

**o) Ratchet interaction.** No Ruff or BLE001 entry is added or widened.
Deleting facade exports removes the inline `F401` suppression in
`api/task_routes.py`. Any newly stale per-file ignore discovered by the
repository guard must be removed only if it belongs to an owned file;
otherwise delivery stops for ownership review.

**p) Dead code and duplication audit.** Delete two module-object injections,
two facade parameters, five `api.main` task/lineage import groups, the task
dispatch re-export block, five task proxy objects, `api/search_support.py`, its
obsolete facade test, the search compatibility export bag, and all helper
model/callable bags. Move one shared summary resolver without duplicating it.
Expected production delta is materially negative, with test changes dominated
by patch-target migration and one structural guard.

## 5. Testing

**q) Edge cases, race conditions, and failure scenarios.**

1. API imports as both `api.main:app` and Docker-style `main:app` without
   relying on module identity.
2. Lineage reads preserve both route contracts, minimum-confidence filtering,
   ordering, 404/empty behavior, and timezone-bearing timestamps.
3. Summary routes preserve cached, stale, forced, low-signal, and empty-agenda
   behavior.
4. Segmentation preserves good-cache reuse, low-quality regeneration, force,
   and rate limits.
5. Topic, vote, and extraction routes preserve cached/stale/blocked/forced
   behavior and exact dispatch arguments.
6. Broker failures and missing task IDs remain HTTP 503; unexpected errors
   remain handled by the global minimized-error boundary.
7. Task polling preserves invalid UUID, processing, exception-result failure,
   error-dictionary failure, and complete payloads.
8. Authentication remains required on all five mutation routes and route paths
   remain unchanged.
9. Search, semantic, metadata, and trends routes remain registered after their
   compatibility exports are deleted.
10. Future module facade parameters, `sys.modules[__name__]`, or patchability
    bags fail the repository guard.

No shared mutable state is added, so no new race exists.

**r) Tests added or updated.**

| Test area | Scenarios |
|---|---|
| New API facade deletion guard in `tests/test_repository_guardrails.py` | 1, 9, 10 |
| Updated `tests/test_task_facade_cleanup.py` | 3-7, 10 |
| Updated `tests/test_async_flow.py` | 1, 3, 4, 6, 7 |
| Updated `tests/test_api.py` | 2-9 |
| Updated lineage endpoint tests | 2 |
| Updated extraction, summary-staleness, and topic-staleness tests | 3, 5, 6 |
| Deleted obsolete search-support facade test | 9, 10 |
| Existing auth and API suites | 8, 9 |
| Complete Python and coverage suites | 1-10 regression check |

Tests are written and run red before production changes. No orphaned test or
identified edge case is intentionally deferred. API-specific assertions in
`tests/test_task_facade_cleanup.py` are replaced, while its pipeline assertions
remain unchanged for separate T-TASK-1 ownership.

**s) Fakes and mocks.** Database behavior uses FastAPI's existing `get_db`
dependency override and SQLAlchemy session doubles, the approved database
boundary. Task enqueue tests patch `api.task_dispatch.celery_app.send_task`,
the approved Celery dispatch boundary. Task polling patches `AsyncResult` where
it is used in `api.task_route_support`; `docs/TESTING.MD` is updated in this task
to explicitly recognize the Celery result-backend boundary. No facade,
re-export, or production unit under test is mocked.

**t) Verification rows.** Apply API/search behavior, pipeline/task
orchestration, guardrail/tooling, and docs-only rows. Run the complete Python
suite and coverage gate because the change crosses app assembly, every async
API route, and compatibility policy. Frontend tests are not required because
no frontend file or contract changes.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-dc-2b-router-facade-deletion
```

Tests-first red evidence:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_repository_guardrails.py -k 'api_router_facade_bags' \
  tests/test_task_facade_cleanup.py
```

Targeted verification:

```bash
./.venv/bin/ruff check .
./.venv/bin/ruff format --check . --config ruff-format.toml
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py tests/test_docs_links.py
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_api.py \
  tests/test_async_flow.py \
  tests/test_catalog_lineage_endpoint.py \
  tests/test_extract_endpoint.py \
  tests/test_summary_staleness.py \
  tests/test_topics_staleness.py \
  tests/test_query_builder_filters.py \
  tests/test_query_builder_parity_search_vs_trends.py \
  tests/test_run_pipeline_orchestration.py \
  tests/test_pipeline_batching.py \
  tests/test_task_metrics.py
```

Final verification:

```bash
PYTHONPATH=. .venv/bin/pytest -q
PYTHONPATH=. .venv/bin/python -m pytest -q --cov \
  --cov-config=.coveragerc \
  --cov-report=term-missing:skip-covered \
  tests/
git diff --check
git status --short
```

Delivery uses one implementation commit after the planning registration is
reviewed: `refactor(api): delete router facade bags`. Push the branch, open a
T-DC-2B PR, request review, and monitor all required checks to a decided state.

**v) Rollback.** Revert the T-DC-2B merge commit and rerun Ruff, formatter,
Mypy, guardrails, docs links, targeted API/task tests, the complete suite, and
coverage. No migration reversal, data repair, cache invalidation, or external
state cleanup is required. Rollback knowingly restores forbidden test-seam
facades.

**w) Docs sync.**

- `ARCHITECTURE.md`: describe `api.main` as app assembly, `api.search_routes`
  as router aggregation, and `api.task_routes` as task-route assembly.
- `docs/PIPELINE.md`: describe `api.task_dispatch` as broker ownership and
  task route helpers as direct domain callers.
- `docs/TESTING.MD`: remove the deleted task-proxy `.delay` option and retain
  `api.task_dispatch.celery_app.send_task` as the approved Celery dispatch
  boundary; add `api.task_route_support.AsyncResult` as the Celery
  result-backend boundary.
- `docs/ADR.md`: add the accepted T-DC-2B deletion decision and supersede
  compatibility portions of earlier task/search/lineage split decisions.
- Remediation plan: register exact ownership, then record verified completion.
- README, operations, performance, security, data governance, and API contract:
  no update because behavior and operator commands remain unchanged.

## 7. Delivery Self-Audit

**x) Antipattern scan, diff pass.** Re-run A-F and H against the actual diff.
Reject a new injection parameter, compatibility alias, test-only wrapper,
duplicate dispatch implementation, direct helper-to-`api.main` import,
weakened test, type suppression, import-time network call, or unrelated edit.

**y) Evidence.** Report the tests-first failures; every command in 6u with
PASS or FAIL; exact test, skip, and coverage totals; planning-review and
pre-commit-review findings; commit hash; PR URL; unresolved-thread count; and
final CI state. Mark any unrun command `NOT VERIFIED`.

**z) Deviations.** Any changed path outside the 27-file ownership set,
route/Celery contract change, new dependency, altered security control,
allowlist widening, skipped subagent review, unresolved P1/P2, or unrun gate is
a blocker. The expected deviation report is `None`.
