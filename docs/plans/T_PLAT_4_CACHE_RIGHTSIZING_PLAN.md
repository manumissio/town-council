# T-PLAT-4: Delete the Generic API Cache

`artifact_contract: ce-unified-plan/v1`

`artifact_readiness: implementation-ready`

`execution: code`

## 1. Context & Alignment

**a) Driver.** The generic Redis cache serves one zero-argument metadata
endpoint but adds an import-time client, opaque key generation, JSON
serialization, broad exception handling, and a hardcoded password fallback.
Town Council can preserve the endpoint's one-hour refresh behavior with a
small process-local cache while deleting the unused abstraction and its
cache-only test seams.

**b) Canonical documents consulted.**

- `AGENTS.md` requires deletion of superseded code, approved fake boundaries,
  exact verification, and a trust-boundary statement for Compose edits.
- `docs/TESTING.MD` permits the Meilisearch and clock boundaries and forbids
  production seams added only for tests.
- `docs/ENGINEERING_GUARDRAILS.md` makes `ruff.toml` authoritative for the
  broad-exception inventory.
- `SECURITY.md` requires credentials to come from deployment configuration and
  forbids working secret defaults for reachable deployments.
- `docs/OPERATIONS.md` owns Redis recovery wording.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` selects deletion and
  call-site right-sizing as the default T-PLAT-4 approach.

**c) Remediation alignment.** This is T-PLAT-4 in the PLAT lane. Its
task-level ownership is authoritative for this PR:

- `docs/plans/T_PLAT_4_CACHE_RIGHTSIZING_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `api/cache.py`
- `api/search_read_routes.py`
- `ruff.toml`
- `tests/test_api.py`
- `tests/test_metrics_api.py`
- `tests/test_performance.py`
- `tests/test_repository_guardrails.py`
- `tests/locustfile.py`
- `docker-compose.yml`, Redis comments only
- `docs/OPERATIONS.md`, Redis recovery wording only

No other tracked file may change.

**d) Decision gates.** The operator approved the T-PLAT-4 deletion and
ownership expansion. It does not depend on or foreclose G1-G5. The reachable
deployment posture remains unchanged.

## 2. Design

**e) Step-by-step approach.**

1. Register this Full plan and the expanded ownership before implementation.
2. Add failing endpoint tests for cache hit, exact-expiry refresh, and
   failure-result caching.
3. Remove cache-only decorator and hash tests rather than preserving obsolete
   interfaces.
4. Add one route-owned cache entry containing the metadata payload and its
   monotonic expiry. Replace the tuple in one assignment so readers cannot
   observe a payload from one refresh with an expiry from another.
5. Add one focused function that returns unexpired metadata or refreshes it
   through the existing metadata loader. Cache successful and empty fallback
   payloads for one hour, matching the current decorator behavior. Compute the
   expiry after retrieval so a slow request does not shorten the residency.
6. Delete `api/cache.py` and all imports of it.
7. Remove the deleted file from Ruff and the exact broad-exception inventory.
8. Correct Compose, Locust, and operations wording that claims the API uses
   Redis caching. State that custom multi-process deployments keep one
   snapshot per process. Redis remains active for Celery and provider metrics.
9. Run targeted and complete verification, simplify the diff, and obtain an
   independent pre-commit review.
10. Commit, push, open one PR, resolve eligible review findings, and wait for
    required CI checks.

No new module, class, decorator, registry, environment variable, or production
test-reset function is added.

**f) Reuse audit.** Reuse `get_metadata`, the existing Meilisearch client
boundary, the route's one-hour constant, and FastAPI's route contract. No
existing general cache belongs in this path: `api/cache.py` is the general
cache and is the superseded layer this task deletes.

**g) Data contracts.** The endpoint continues to return
`dict[str, list[str]]` with `cities`, `organizations`, and `meeting_types`.
No API field, status code, authentication rule, or serialization contract
changes.

**h) Schema and migrations.** None.

## 3. Security & Data Governance

**i) Security boundary.** `docker-compose.yml` is security-sensitive, but this
task changes comments only. Deleting `api/cache.py` removes the API's Redis
credential path and its predictable password fallback. An attacker gains no
new access; one credential-consuming client disappears. Redis authentication,
network exposure, Celery use, and provider-metrics use remain unchanged under
the controls in `SECURITY.md`.

**j) Secrets.** No secret or default is added. The deleted API cache no longer
reads `REDIS_PASSWORD`.

**k) Person data.** No person-level data is created, linked, aggregated, or
exposed. G4 and T-GOV-2A are unaffected.

**l) Untrusted input.** Meilisearch facet responses remain untrusted and are
parsed by the existing metadata loader. This task adds no new external input
or rendering boundary.

## 4. Code Health

**m) Conformance.** New route logic uses domain names, complete annotations,
one-hour and empty-payload constants, `time.monotonic`, and focused functions.
There are no new environment reads, exception handlers, naive timestamps, or
more than two nesting levels.

**n) Antipattern scan, plan pass.**

- A1/H1: only Python's installed standard-library monotonic clock is added; no
  external API call or guessed dependency interface is introduced.
- B1/C1: the generic decorator is deleted rather than wrapped or retained.
- B2/C2: cache-only compatibility exports and tests are deleted; tests move to
  the endpoint contract.
- D1-D3: tests assert HTTP payloads and expiry behavior through approved
  Meilisearch and clock boundaries.
- E1-E3: edits remain within the owned files and named sections.
- F1/F2: one route owns the only cache; no second shared cache location exists.
- A2-A4, B3, H2-H4: no violations planned.

**o) Ratchet interaction.** Remove the `api/cache.py = ["BLE001"]` selector
from `ruff.toml` and the matching exact test inventory entry. Add or widen no
Ruff exception.

**p) Dead code and duplication.** Delete `api/cache.py`, its two cache-only
tests, the global Redis module mock in `tests/test_performance.py`, and stale
API-cache prose. The route adds only the behavior needed at its single call
site. Expected production and test net change is approximately minus 54 lines.

## 5. Testing

**q) Edge and failure scenarios.**

1. The first request fetches and normalizes Meilisearch facets.
2. A request before expiry returns the cached payload without another search.
3. A request exactly at expiry refreshes and returns changed facets.
4. A Meilisearch failure returns the existing empty payload and caches it until
   expiry.
5. Endpoint tests isolate cache lifetimes through non-overlapping clock epochs
   without patching private cache state.
6. The deleted module has no remaining import or Ruff exception.
7. Redis remains configured for non-API workloads.
8. Supported Compose runs one API process; a custom multi-process deployment
   refreshes once per process and may briefly serve different metadata
   snapshots across processes.

**r) Tests.**

| Test | Scenarios |
|---|---|
| Metadata snapshot test, before-expiry case | 1, 2, 5 |
| Metadata snapshot test, exact-expiry case | 1, 3, 5 |
| Metadata endpoint failure-cache test | 4, 5 |
| Repository broad-exception contract | 6 |
| Docker build contracts and full suite | 7, 8 |

Tests are written and run red before production changes. Existing search
endpoint, query-builder, metrics, and full-suite tests remain regression
coverage.

**s) Fakes and mocks.** Tests patch the Meilisearch client in
`api/search/support_core.py` and the monotonic clock where the route looks it
up. Non-overlapping test clock epochs expire prior snapshots without patching
private storage. These are approved Meilisearch and clock boundaries in
`docs/TESTING.MD`. No facade, re-export, private helper, cache state, or
production reset seam is patched.

**t) Verification rows.** Apply API/search behavior, guardrail/tooling,
security-sensitive Compose, and docs-only verification. Run the complete
Python suite because this deletes a shared import and removes a global test
module mock.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-plat-4-cache-rightsizing
```

Tests-first red:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_api.py -k "metadata and (cache or expiry)"
```

Final verification:

```bash
test ! -e api/cache.py
! rg -n "api\.cache|from api\.cache" api tests
./.venv/bin/ruff check .
./.venv/bin/ruff format --check . --config ruff-format.toml
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_api.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_query_builder_filters.py
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_query_builder_parity_search_vs_trends.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_metrics_api.py tests/test_performance.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docker_build_contracts.py
PYTHONPATH=. .venv/bin/pytest -q
git diff --check
git status --short
```

**v) Rollback.** Revert the T-PLAT-4 merge commit and rerun the same targeted
and complete verification. No migration, cache-data conversion, external
state cleanup, or data remediation is required. Existing Redis keys created by
the old endpoint are inert and expire naturally.

**w) Docs synchronization.**

- `docs/OPERATIONS.md`: remove API cache entries from Redis recovery effects.
- `docker-compose.yml`: describe Redis's remaining queue, task-result, and
  metrics roles without changing configuration.
- `tests/locustfile.py`: remove the Redis-specific metadata performance claim.
- Remediation plan: register exact ownership, acceptance, and verification.
- README, ADR, architecture, testing policy, security, data governance, and
  performance docs: no changes.

## 7. Delivery Self-Audit

**x) Diff scan.** Re-run A-F and H. Reject a surviving `api.cache` reference,
new cache abstraction, production reset seam, Redis fallback, extra
credential, broadened Ruff exception, unrelated formatting, or edit outside
the owned files.

**y) Evidence.** Report tests-first red, every command in 6u as `PASS` or
`FAIL`, collected/pass/skip/fail counts, independent planning and pre-commit
review findings, fixes applied, commits, PR URL, unresolved-thread count, and
final CI state. Mark anything unrun `NOT VERIFIED`.

**z) Deviations.** The authorized deviation is the T-PLAT-4 ownership
expansion above. Any additional file, behavior change, new dependency, new
environment variable, Ruff exception, skipped review, unresolved P1/P2, or
unrun required check is a blocker.
