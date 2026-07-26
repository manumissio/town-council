# T-DC-1: Give API Startup One State Owner

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: implementation-ready`
`execution: code`

## 1. Context & Alignment

**a) Driver.** `api.main` and `api.app_setup` currently copy database startup
state in both directions. Tests mutate the facade copies, so every database
operation must synchronize `SessionLocal`, `_db_init_error`, `db_connect`, and
`sessionmaker` before and after delegating. `app_setup` also imports back
through `api.main` for semantic startup policy. T-DC-1 removes this cycle
without changing authentication, startup validation, database failure
responses, semantic fail-fast behavior, or route contracts.

**b) Canonical documents consulted.**

- `AGENTS.md` hierarchy, known-antipatterns, security-sensitive paths,
  verification matrix, and testing policy require one state owner, direct
  implementation patch targets, a trust-boundary report, and full verification.
- `docs/TESTING.MD` requires tests to patch implementation modules or use
  FastAPI dependency overrides rather than preserving facade globals.
- `SECURITY.md` requires non-development API-key rejection, secret redaction,
  scoped client identity, and semantic startup fail-fast behavior.
- `docs/ENGINEERING_GUARDRAILS.md` treats helper-to-facade imports and
  bidirectional synchronization as structural debt.
- `docs/ADR.md`, “Start API main cleanup with lifecycle and search route
  boundaries,” assigns lifecycle, session, auth, and limiter ownership to
  `api/app_setup.py`. Its temporary test-seam preservation was superseded by
  the accepted G3 ADR.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` names T-DC-1 as the remaining
  P1 architecture task and prohibits concurrent security work.
- `docs/reviews/architecture-review-2026-07-19.html`, “Give application startup
  one state owner,” confirms `app_setup` as the implementation boundary.

**c) Remediation alignment.** T-DC-1 owns exactly:

- `docs/plans/T_DC_1_APP_STARTUP_OWNERSHIP_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `api/main.py`
- `api/app_setup.py`
- `api/search/semantic_support.py` (`SEMANTIC_SERVICE_URL` ownership only)
- `tests/conftest.py`
- `tests/test_api.py` (database startup, direct model imports, and dead AI
  override only)
- `tests/test_api_key_compare_digest.py`
- `tests/test_api_startup_security.py`
- `tests/test_city_slug_normalization.py`
- `tests/test_semantic_search_api.py` (dead semantic health patches only)

The task marks T-DD-1B complete after PR #156 and activates T-DC-1 before
implementation. No security task runs concurrently. Only task, lineage, and
search aliases resolved by assembled routers remain; test-only re-exports are
deleted in this task.

**d) Decision gates.** G3 is satisfied and authorizes removal of test-only
patch seams. G1, G2, G4, and G5 are unaffected. No open gate blocks this task.

## 2. Design

**e) Step-by-step approach.**

1. Update the remediation ledger to version 3.64, mark T-DD-1B complete, and
   activate T-DC-1 with exact ownership and acceptance criteria.
2. Add failing tests before production edits:
   - assembled application behavior continues through the `app_setup`
     lifespan, DB dependency, and API-key dependency;
   - copied startup globals and synchronization functions are absent from
     `api.main`;
   - semantic startup reads `app_setup.SEMANTIC_ENABLED` and calls the
     implementation health boundary without importing `api.main`;
   - database failure and recovery tests patch only `api.app_setup`;
   - test-only model, reporting, task, and search exports are absent.
3. Remove from `api.main`:
   - `_sync_app_setup_from_facade` and `_sync_facade_from_app_setup`;
   - wrapper definitions for `initialize_database`, `is_db_ready`, `get_db`,
     `verify_api_key`, and `lifespan`;
   - copied `SessionLocal`, `_db_init_error`, `db_connect`, `sessionmaker`, and
     `hmac` globals;
   - the unused `SEMANTIC_SERVICE_URL` facade export;
   - imports made dead by those removals.
4. Import `get_db`, `verify_api_key`, `lifespan`, and `limiter` directly from
   `api.app_setup` because application assembly consumes those callables at
   runtime. Their names remain part of application assembly and FastAPI
   dependency override identity; mutable facade state and forwarding wrappers
   do not.
5. Move `SEMANTIC_SERVICE_URL` from `app_setup` to
   `api.search.semantic_support`, its only runtime consumer. Remove
   `app_setup` helpers that import `api.main`; `lifespan` reads its own
   `SEMANTIC_ENABLED` setting and calls the semantic implementation. Import
   direction becomes `main -> app_setup -> semantic_support`, with no reverse
   semantic import into startup.
6. Repoint tests:
   - shared DB fixture patches only `api.app_setup.db_connect`;
   - database startup tests exercise `api.app_setup` and assert HTTP/session
     outcomes rather than synchronized private copies or call counts;
   - constant-time comparison test patches `api.app_setup.hmac.compare_digest`;
   - catalog and agenda-item models import from `pipeline.models`;
   - city normalization imports from `api.search.query_builder`;
   - dead semantic health patches and the inert local-AI dependency override
     are removed.
7. Delete test-only `api.main` exports. Preserve this explicit runtime
   allowlist:
   - task routes: `AsyncResult`, `_enqueue_task`, `extract_text_task`,
     `extract_votes_task`, `generate_summary_task`, `generate_topics_task`,
     `segment_agenda_task`, `agenda_items_look_low_quality`, and
     `_summary_doc_kind_and_hashes`;
   - lineage routes: `_lineage_rows`;
   - search routes: `client`, `_build_meilisearch_filter_clauses`,
     `_collect_meeting_docs`, `_semantic_service_get_json`,
     `search_documents_semantic`, `SEMANTIC_ENABLED`, and
     `FEATURE_TRENDS_DASHBOARD`;
   - application assembly imports and router builders.
8. Run targeted tests, API/search verification rows, security startup tests,
   direct import/boot smoke, Ruff, Mypy, coverage, and the complete suite.
9. Run simplification and independent pre-commit review. Apply every eligible
   P1/P2, commit in two logical changes, push, open a PR, request Codex review,
   and watch CI to a decided state.

No new production module or helper is introduced.

**f) Reuse audit.** Extend `api.app_setup` as the already-established owner.
Reuse FastAPI’s direct lifespan callable and dependency-overrides mechanism,
SQLAlchemy’s existing `sessionmaker`, and current semantic health helper.
Nothing new duplicates route or startup logic. The synchronized facade
implementation is deleted, not renamed or retained.

Rejected alternatives:

- Keep one-way synchronization: rejected because it preserves duplicated
  mutable state and stale test patch points.
- Add setters or a startup-state registry: rejected as unrequested machinery.
- Pass semantic callables into `lifespan`: rejected because injectable
  callables are a banned test seam.
- Remove every `api.main` alias now: rejected because the explicit task,
  lineage, and search allowlist is still resolved at runtime by assembled
  routers.
- Leave `SEMANTIC_SERVICE_URL` in `app_setup` and import semantic support only
  during lifespan: rejected because it delays but does not remove the two-way
  module dependency.

**g) Data contracts.** No new application payload. Existing contracts remain:

- `get_db` yields one SQLAlchemy session and closes it.
- unavailable database initialization returns sanitized HTTP 503.
- `verify_api_key` returns no value on success and raises HTTP 401 on failure.
- `lifespan` rejects unsafe production keys before database work, warns without
  logging secrets, runs startup purge, and fails fast on semantic
  misconfiguration.
- `api.main.app` retains all current routes, middleware, dependencies, and
  response formats.
- `api.main.get_db`, `verify_api_key`, and `lifespan` remain runtime assembly
  names bound directly to implementation callables, not wrappers or mutable
  test seams.

**h) Schema/migrations.** None. No database definition, migration, timestamp,
or stored value changes.

## 3. Security & Data Governance

**i) Security boundary.** `api/app_setup.py` is security-sensitive. This task
changes ownership, not policy. An attacker gains no route, credential,
permission, or bypass. `SECURITY.md` controls for API-key fail-fast validation,
constant-time comparison, secret-free logging, client identity, database
failure sanitization, and semantic startup checks remain enforced by targeted
tests. `api.main` remains the public ASGI assembly boundary.

**j) Secrets.** No credential, environment variable, key, or default changes.
No secret moves into a browser-visible or logged surface.

**k) Person data.** No person record is created, linked, aggregated, or
exposed. G4 is unaffected.

**l) Untrusted input.** API headers and client address metadata remain
validated in `app_setup`. No scraped content, HTML, provider response, or new
input parser is introduced.

## 4. Code Health

**m) GED conformance.** Deletion reduces functions, globals, imports, and
module coupling. No new nesting, environment read, exception handler,
timestamp, mutable default, or broad exception is added. Existing startup
errors continue to take meaningful action: typed HTTP failure, contextual log,
or re-raise.

**n) Antipattern scan, plan pass.**

- A1/H1: FastAPI current docs verify async-context-manager lifespan,
  `Depends`, dependency overrides, and `TestClient` lifespan execution.
  SQLAlchemy 2.0 docs verify module-owned `sessionmaker`, factory invocation,
  and `Session.close`.
- B1/B2/C1: no registry, compatibility shim, wrapper, or old synchronized path.
- B3: no new validation or retry.
- C2: tests move to the implementation owner rather than preserving facade
  patch targets.
- D1-D3: no assertion weakening, skips, call-count contracts, or mocked unit
  under test.
- E1-E3: only eleven owned files change; no broad formatting.
- F1/F2: existing startup logic remains in one module.
- H2-H4: no type suppression, alternative contract, or new import-time
  engine/client/network work.

**o) Ratchet interaction.** `api/main.py` remains in the BLE001 allowlist for
its middleware and endpoint boundaries; this task neither adds nor widens an
entry. T-GOV-3B will later enforce the generic synchronization ban after
T-DC-1 and T-DE-1 merge.

**p) Dead code and duplication.** Delete two synchronization functions, five
facade wrappers, six copied globals/stdlib bindings, two reverse semantic
helpers, 27 test-only exports/hooks, and their dead imports. Expected production
delta is materially negative. No superseded code survives.

## 5. Testing

**q) Edge cases and failure scenarios.**

1. First database connection attempt fails; request receives sanitized 503.
2. Later database attempt succeeds; session is yielded and closed.
3. Unsafe non-development API key stops startup before database work.
4. Invalid key uses constant-time comparison and returns 401 without logging
   the key.
5. Default development key warning omits the key value.
6. Semantic startup disabled skips semantic health.
7. Semantic startup enabled checks health and re-raises misconfiguration.
8. Meilisearch fallback warning omits search and master key values.
9. FastAPI application behavior uses implementation-owned lifespan/auth/DB
   logic.
10. No copied startup state, sync function, stdlib rebind, or reverse
    `app_setup -> api.main` dependency remains.
11. API routes, dependency overrides, task dispatch, search, lineage, and
    response contracts remain unchanged.
12. Test-only model, reporting, task, and search exports are absent from
    `api.main`; explicit runtime-resolved aliases remain.

**r) Tests mapped to scenarios.**

| Test | Scenarios |
|---|---|
| Updated database startup tests in `tests/test_api.py` | 1, 2 |
| Updated `tests/test_api_key_compare_digest.py` | 4 |
| Existing and extended `tests/test_api_startup_security.py` | 3, 5-10, 12 |
| Updated direct imports and semantic patch targets | 11, 12 |
| Shared fixture collection/full-suite execution | 2, 11 |
| Existing API/search/query verification rows | 11 |
| Manual Uvicorn boot and `/health` smoke | 2, 9, 11 |

Tests are written and run red before production edits. Existing 65 focused
tests establish the pre-change behavior baseline.

**s) Fakes/mocks.** Tests fake only approved boundaries:

- database engine creation at `api.app_setup.db_connect`;
- SQLAlchemy session factory at `api.app_setup.sessionmaker`;
- semantic HTTP boundary at `api.search.semantic_support`;
- FastAPI dependency overrides for route-level DB behavior.

Changed startup tests patch no facade or re-export. Existing tests still patch
the task, lineage, and search aliases in the explicit runtime allowlist; that
debt remains until those route families stop resolving through `api.main`.
Structural assertions are limited to explicitly prohibited synchronization
functions, copied mutable globals, stdlib rebinding, reverse imports, and
test-only exports; runtime behavior is asserted through FastAPI and session
outcomes.

**t) Verification rows.** Apply security-sensitive trust-boundary reporting,
API/search behavior, and broad cross-cutting rows. Run the complete Python
suite and coverage gate because application assembly and shared fixtures
change.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
test "$(git branch --show-current)" = "codex/t-dc-1-app-startup-ownership"
git merge-base --is-ancestor origin/master HEAD
```

Tests-first:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_api.py::test_get_db_returns_sanitized_503_when_database_init_fails \
  tests/test_api.py::test_initialize_database_recovers_after_transient_failure \
  tests/test_api_key_compare_digest.py \
  tests/test_api_startup_security.py
```

Final:

```bash
./.venv/bin/ruff check .
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_api_startup_security.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_api.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_api_key_compare_digest.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_api_auth_logging.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_semantic_search_api.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_query_builder_filters.py
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_query_builder_parity_search_vs_trends.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/python -m pytest -q \
  --cov --cov-config=.coveragerc --cov-report=term-missing:skip-covered tests/
PYTHONPATH=. .venv/bin/pytest -q
git diff --check
```

Boot smoke uses the existing API image because Uvicorn is a runtime dependency,
not a local development dependency. It binds only to loopback:

```bash
cleanup() {
  docker stop "$smoke_container" >/dev/null 2>&1 || true
}
trap cleanup EXIT

smoke_container=$(
  docker compose -f docker-compose.yml -f docker-compose.dev.yml run \
    -d --rm --no-deps \
    -p 127.0.0.1:8019:8000 \
    -e DATABASE_URL=sqlite:////tmp/tc-t-dc-1-smoke.sqlite \
    -e APP_ENV=dev \
    -e STARTUP_PURGE_DERIVED=false \
    -e SEMANTIC_ENABLED=false \
    api uvicorn main:app --host 0.0.0.0 --port 8000 --no-proxy-headers
)

for attempt in 1 2 3 4 5; do
  curl -fsS http://127.0.0.1:8019/health && break
  sleep 1
done
curl -fsS http://127.0.0.1:8019/health
```

**v) Rollback.** Revert the T-DC-1 merge commit, rerun Ruff, Mypy, focused API
and security tests, coverage, and the complete suite, then boot-smoke the
restored application. No migration, data repair, credential rotation, or
external-state cleanup is required. Rollback knowingly restores duplicated
startup state and facade test seams.

**w) Docs sync.**

- Remediation ledger: version 3.64, T-DD-1B completion, T-DC-1 activation,
  exact ownership, behavior boundary, and verification.
- This implementation plan.
- `SECURITY.md`, `ARCHITECTURE.md`, `docs/ADR.md`, `docs/OPERATIONS.md`,
  `docs/TESTING.MD`, README, API contracts, and data-governance docs: no
  update. Their current ownership and security statements remain accurate;
  historical ADR text is not rewritten.

## 7. Delivery Self-Audit

**x) Diff scan.** Re-run A-F/H. Reject facade wrappers, synchronized globals,
reverse `app_setup -> api.main` imports, test-only aliases, callable injection,
new config, auth changes, route changes, type suppression, unrelated alias
cleanup, or files outside ownership.

**y) Evidence.** Report tests-first red output; FastAPI/SQLAlchemy documentation
verification; Ruff, Mypy, focused API/security/search tests, coverage, complete
suite, and boot smoke results; planning and pre-commit review findings; commit
hashes; PR URL; current-head review; CI state; and unresolved-thread count.
Mark every unrun check `NOT VERIFIED`.

**z) Deviations.** Expected deviation is the remediation ownership expansion
to include this plan, ledger, semantic URL owner, and six exact test files.
Any other changed
path, removed runtime facade used by task/search/lineage routers, security
policy change, new compatibility seam, skipped review, unresolved P1/P2, or
unrun required check blocks delivery.
