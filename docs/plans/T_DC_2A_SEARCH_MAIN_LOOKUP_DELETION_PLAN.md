# T-DC-2A: Delete Search-to-api.main Patch Lookup

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: implementation-ready`
`execution: code`

## 1. Context & Alignment

**a) Driver.** Search route implementations still resolve feature flags,
Meilisearch clients, filter builders, semantic transport, and trends helpers by
looking back through `api.main`. That behavior exists only to preserve historical
monkeypatch targets. It hides the real implementation owners, creates reverse
imports, and allows tests to pass through a compatibility surface rather than
the approved Meilisearch and outbound-HTTP boundaries. T-DC-2A deletes that
lookup layer without changing search behavior or beginning T-DC-2B's broader
router-facade deletion.

**b) Canonical documents consulted.**

- `AGENTS.md` hierarchy, known-antipattern, workflow, API/search verification,
  and reporting sections require direct implementation ownership, observable
  tests, complete verification, and no compatibility aliases.
- `docs/TESTING.MD` requires Meilisearch tests to patch the client where it is
  constructed in `api/search/support_core.py` and outbound semantic requests at
  the `httpx` call site.
- `docs/ENGINEERING_GUARDRAILS.md` requires helper modules to avoid reverse
  imports through facades and rejects preserving historical patch targets.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` sequences T-DC-2A after T-DC-1
  and before T-DC-2B while freezing search, authentication, key, and response
  behavior.
- `docs/reviews/architecture-review-2026-07-19.html` identifies the search
  facade stack as a deferred compatibility stratum that should be removed one
  domain at a time after G3.
- `docs/ADR.md` records the historical `api.main` patch-surface decision. A new
  dated entry records that G3 and T-DC-2A supersede only its search lookup
  compatibility, leaving T-DC-2B to address router facade bags.

**c) Remediation alignment.** This is T-DC-2A in the DEDUP-C lane. Its exact
`files_owned` set is:

- `docs/plans/T_DC_2A_SEARCH_MAIN_LOOKUP_DELETION_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `api/main.py`
- `api/search/support_core.py`
- `api/search/trends_support.py`
- `api/search_support.py`
- `api/search_read_params.py`
- `api/search_read_meilisearch.py`
- `api/search_read_routes.py`
- `api/search_semantic_routes.py`
- `api/trends_routes.py`
- `tests/test_api.py`
- `tests/test_catalog_lineage_endpoint.py`
- `tests/test_query_builder_parity_search_vs_trends.py`
- `tests/test_search_support_facade.py`
- `tests/test_semantic_search_api.py`
- `tests/test_semantic_search_feature_flag.py`
- `tests/test_trends_compare_endpoint.py`
- `tests/test_trends_export_csv.py`
- `tests/test_trends_topics_endpoint.py`
- `tests/test_repository_guardrails.py`
- `docs/ADR.md`

This plan grants DEDUP-C narrow coordination over the GOV-owned ADR and
structural guardrail only for this lookup deletion. The `api/main.py` edit is
limited to removing seven search patch aliases; its ASGI assembly and all other
compatibility exports remain unchanged. `api/search_routes.py` remains outside
this task; T-DC-2B owns its broader router dependency bag and the remaining
`api.main` compatibility exports.

**d) Decision gates.** G3 is satisfied by T-GOV-1 and explicitly removes the
requirement to preserve monkeypatch facades. G1, G2, G4, and G5 are unaffected.
No open decision gate blocks T-DC-2A.

## 2. Design

**e) Step-by-step approach.**

1. Run the current route behavior suite to characterize lexical search,
   metadata, semantic search, and trends outcomes before changing imports.
2. Add failing structural tests that reject `_api_main`, `facade_value`,
   `facade_callable`, and `search_client`, reject their re-export from
   `api.search_support`, and reject imports of `api.main` from search helper
   modules.
3. Delete the four lookup functions and their `Any` import from
   `api/search/support_core.py`. Keep the configured reader-key Meilisearch
   client in that module as the approved construction boundary.
4. Repoint route and helper modules directly:
   - lexical and metadata routes use `api.search.support_core.client`;
   - search parameter construction uses `api.search.filter_support` and
     constants from `support_core`;
   - semantic routes read `support_core.SEMANTIC_ENABLED` and call
     `api.search.semantic_support._semantic_service_get_json`;
   - trends routes use `api.search.trends_support` and
     `api.search.filter_support` directly;
   - trends support reads feature flags and the client from the
     `support_core` module and calls the filter builder directly;
   - Meilisearch error mapping reads logging and detail constants from
     `support_core`.
5. Remove the three exported lookup names from the `api.search_support`
   compatibility surface. `_api_main` was private to `support_core`. Do not add
   replacement wrappers or aliases.
6. Remove the seven search patch aliases from `api.main`: `client`,
   `_build_meilisearch_filter_clauses`, `_collect_meeting_docs`,
   `_semantic_service_get_json`, `search_documents_semantic`,
   `SEMANTIC_ENABLED`, and `FEATURE_TRENDS_DASHBOARD`. Keep only the search
   router import needed for application assembly. Broader facade cleanup stays
   with T-DC-2B.
7. Repoint tests from `api.main` to the approved Meilisearch client or outbound
   HTTP boundary and assert HTTP responses and persisted route effects. Keep
   `api.main.app` imports because ASGI application assembly is not deleted here.
   Delete the unrelated trends-flag patch from the lineage route test.
8. Append a dated ADR entry that supersedes the old search patch-lookup
   decision while preserving route contracts and the later T-DC-2B boundary.
9. Mark T-DC-2A complete only after targeted, guardrail, coverage, and complete
   suite verification succeeds.

No production module or abstraction is added. Existing implementation modules
remain the only owners.

**f) Reuse audit.** Reuse `api/search/support_core.py` as configuration,
constant, logging, and Meilisearch-client owner; `filter_support.py` as filter
validation owner; `semantic_support.py` as outbound semantic transport owner;
and `trends_support.py` as trends data owner. The deleted dynamic lookup layer
is the older stratum; nothing replaces it.

**g) Data contracts.** Route paths, query parameters, response dictionaries,
HTTP status codes, Meilisearch request dictionaries, semantic diagnostics, and
trends CSV columns remain unchanged. No new typed contract or raw external
input boundary is introduced. Tests and untracked callers that patch search
internals through `api.main` intentionally lose that compatibility path and
must use the documented implementation boundary.

**h) Schema and migrations.** None.

## 3. Security & Data Governance

**i) Security boundary.** `api/search/support_core.py` handles
`MEILI_SEARCH_KEY` and is therefore security-sensitive under `AGENTS.md`.
This task does not change key resolution, host selection, client construction,
timeout behavior, or permissions. The `SECURITY.md` reader-key control remains:
API and semantic readers receive only `search` and `stats.get` on `documents`,
while writer/admin services retain the master key. An attacker gains no new
capability because only Python lookup ownership changes.

**j) Secrets.** No credential, key, environment variable, or default changes.
The existing reader-only Meilisearch key remains owned by `support_core`.

**k) Person data.** No person entity, roster, people metadata, or publication
behavior changes. Roster-gated people results continue to follow G4.

**l) Untrusted input.** FastAPI continues to validate route/query input.
`filter_support` continues to normalize filters before Meilisearch receives
them, and `semantic_support` continues to validate outbound response status and
JSON. This task changes import ownership only.

## 4. Code Health

**m) GED conformance sweep.** The implementation deletes four functions and
replaces dynamic lookup with qualified module calls. No new nesting, long
parameter list, timestamp, environment read, broad handler, or runtime literal
is introduced. Existing route and search-domain names remain unchanged.

**n) Antipattern scan, plan pass.**

- A1/H1: no external API or dependency call changes.
- B1/B2/C1: no wrapper, registry, injection layer, alias, or dual path replaces
  the deleted lookup behavior.
- C2/D2: tests move to approved Meilisearch and outbound-HTTP boundaries rather
  than preserving `api.main` patch targets or mocking the route under test.
- D1/D3: response, error, query, and filter assertions remain; only obsolete
  patch-path assertions are replaced by deletion and direct-owner contracts.
- E1/E2: edits stay within the exact owned paths and do not reformat unrelated
  code.
- F1/F2: no logic is copied; callers invoke existing owners.
- A2-A4, B3, E3, H2-H4: no planned violation.

**o) Ratchet interaction.** `api/search/trends_support.py` and
`api/trends_routes.py` retain their existing `DTZ007` debt because date parsing
behavior is frozen here. No Ruff selector, BLE001 boundary, formatter scope,
Mypy scope, or coverage threshold changes.

**p) Dead code and duplication audit.** Delete four lookup functions, one
unused type import, three compatibility exports, and test patch paths.
Reuse all route/query implementations. Expected production delta is negative;
test/docs growth records the deletion contract without runtime machinery.

## 5. Testing

**q) Edge and failure scenarios.**

1. Lexical search still sends the same query, filters, sorting, limit, and
   offset to Meilisearch.
2. Metadata retains its one-hour process-local cache and empty failure payload.
3. Meilisearch timeout, unavailable, invalid-sort, and generic errors retain
   their HTTP mappings.
4. Semantic-disabled requests return 503.
5. Semantic requests preserve filters, diagnostics, upstream status, and
   non-dictionary error details.
6. Trends feature disablement returns 503.
7. Trends topic, comparison, date filtering, and CSV output remain unchanged.
8. Feature flags patched at their direct owner affect route behavior without
   `api.main` lookup.
9. Every search route/helper uses the configured reader client directly.
10. No helper imports or inspects `api.main`, none of the four lookup names can
    return through `api.search_support`, and none of the seven search patch
    aliases survives in `api.main`.
11. Authentication and Meilisearch key behavior remain unchanged.
12. Date-filtered trends execute normal Meilisearch pagination and filtering
    rather than a patched `_collect_meeting_docs` helper.

**r) Test mapping.**

| Tests | Scenarios |
|---|---|
| `tests/test_api.py` | 1-3, 5, 9, 11 |
| `tests/test_catalog_lineage_endpoint.py` | 10 |
| `tests/test_semantic_search_feature_flag.py` | 4, 8 |
| `tests/test_semantic_search_api.py` | 5, 8 |
| `tests/test_trends_compare_endpoint.py` | 7-9, 12 |
| `tests/test_trends_export_csv.py` | 7-9 |
| `tests/test_trends_topics_endpoint.py` | 6-9 |
| `tests/test_query_builder_parity_search_vs_trends.py` | 1, 7 |
| `tests/test_search_support_facade.py` | 10 |
| `tests/test_repository_guardrails.py` | 10 |
| Existing auth and API suites | 1-11 |

Write and run the structural deletion tests red before implementation.

**s) Fakes and mocks.** Meilisearch tests patch
`api.search.support_core.client`, the approved construction boundary.
Semantic tests patch `api.search.semantic_support.httpx.get`, the approved
outbound-HTTP boundary. Feature tests patch implementation-owned configuration
at `api.search.support_core.SEMANTIC_ENABLED` and
`api.search.support_core.FEATURE_TRENDS_DASHBOARD`; these are configuration
state changes, not substitute service boundaries. No accessor, copied
`api.main` value, facade/re-export patch, or new fake seam is added.

**t) Verification rows.** Apply the API/search behavior, guardrail/tooling,
and docs-only rows. Run coverage because production API files change, then the
complete Python suite because the search compatibility boundary is
cross-cutting.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-dc-2a-search-main-lookup-deletion

PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_api.py \
  tests/test_catalog_lineage_endpoint.py \
  tests/test_semantic_search_feature_flag.py \
  tests/test_semantic_search_api.py \
  tests/test_trends_compare_endpoint.py \
  tests/test_trends_export_csv.py \
  tests/test_trends_topics_endpoint.py \
  tests/test_query_builder_parity_search_vs_trends.py \
  tests/test_search_support_facade.py

# Expected red after adding deletion contracts and before implementation.
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_search_support_facade.py \
  tests/test_repository_guardrails.py::test_search_helpers_do_not_lookup_api_main

./.venv/bin/ruff check .
./.venv/bin/ruff format --check . --config ruff-format.toml
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_api.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_query_builder_filters.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_query_builder_parity_search_vs_trends.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_meilisearch_key_security.py
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_semantic_search_feature_flag.py \
  tests/test_semantic_search_api.py \
  tests/test_trends_compare_endpoint.py \
  tests/test_trends_export_csv.py \
  tests/test_trends_topics_endpoint.py
PYTHONPATH=. .venv/bin/python -m pytest -q --cov \
  --cov-config=.coveragerc \
  --cov-report=term-missing:skip-covered \
  tests/
PYTHONPATH=. .venv/bin/pytest -q
git diff --check
git status --short
```

Run an independent planning review before implementation and a fresh
pre-commit code review after verification. Resolve every eligible P1/P2 and
rerun affected commands.

**v) Rollback.** Revert the T-DC-2A merge commit. This restores dynamic lookup
and test patch paths atomically. Rerun the API/search, guardrail, docs-link,
coverage, and complete-suite commands above. No migration, data repair, cache
purge, or external-state restoration is required.

**w) Docs synchronization.** Update `docs/ADR.md` with the direct search-owner
decision and the boundary left for T-DC-2B. Update the remediation ledger and
this implementation plan. `ARCHITECTURE.md` remains unchanged because its
broader `api.main`, `api.search_routes`, and `api.search_support` facade map is
not retired until T-DC-2B. README, operations, pipeline, security, testing, and
data-governance docs require no change.

## 7. Delivery Self-Audit

**x) Antipattern scan, diff pass.** Re-run A-F and H. Reject any compatibility
alias, new dependency injection, duplicated filter/client policy, route or
query drift, widened ignore, test assertion weakening, unrelated formatting,
type suppression, or import-time side effect.

**y) Evidence.** Report the baseline characterization, tests-first red result,
all commands from 6u, exact pass/skip/fail and coverage counts, planning-review
and pre-commit-review findings, fixes applied, commit hashes, PR URL, review
thread count, and final CI state. Mark anything unrun as `NOT VERIFIED`.

**z) Deviations.** Expected result is none. Any path outside the exact ownership
set, route-contract change, feature-flag default change, Meilisearch key or
client-policy change, compatibility alias, skipped review, unresolved P1/P2,
or unrun required check is a blocker and must be reported.
