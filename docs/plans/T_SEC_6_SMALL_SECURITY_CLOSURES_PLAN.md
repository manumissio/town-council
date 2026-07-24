# T-SEC-6: Small Security Closures

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: complete`
`execution: code`

## 1. Context & Alignment

**a) Driver.** Four small security debts remain after T-SEC-4: a browser-public
API key example, credentialed CORS without a credential use case, an overly
detailed public search-statistics response, and two broad S105 suppressions
covering non-secret protocol constants. Closing them removes misleading secret
guidance, reduces reconnaissance data, and narrows the Ruff exception surface.

**b) Canonical documents consulted.**

- `AGENTS.md` requires a trust-boundary statement, tests first, exact
  verification, and a ratchet report for security and guardrail changes.
- `SECURITY.md` forbids secrets in `NEXT_PUBLIC_*` and lists CORS and `/stats`
  as open reachable-posture controls.
- `docs/TESTING.MD` permits TestClient, Meilisearch, filesystem, and subprocess
  boundaries; tests patch the implementation owner.
- `docs/ENGINEERING_GUARDRAILS.md` makes `ruff.toml` authoritative for S105
  scope and requires narrower exceptions when debt is removed.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` defines T-SEC-6 and its
  behavior freeze.
- `docs/reviews/architecture-review-2026-07-19.html` prioritizes small
  security closures before overlapping `api/main.py` architecture work.

**c) Remediation alignment.** T-SEC-6 remains in the SEC lane. Expand
`files_owned` to:

- `.env.example`
- `api/main.py`, CORS and `/stats` sections only
- `pipeline/provider_telemetry.py`, metric-key constants only
- `pipeline/topic_generation_contracts.py`, token-pattern constants only
- `ruff.toml`, the two owned S105 selectors only
- `tests/test_api.py`
- `tests/test_meilisearch_key_security.py`
- `tests/test_repository_guardrails.py`
- `SECURITY.md`, T-SEC-6 checklist only
- `docs/plans/T_SEC_6_SMALL_SECURITY_CLOSURES_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`

**d) Decision gates.** G2 keeps public read routes public, so `/stats` remains
public but returns only the document count. G1's reachable-posture default
supports hardening. G3 is satisfied. G4 and G5 are unrelated. No open gate
blocks or is foreclosed by this work.

## 2. Design

**e) Step-by-step approach.**

1. Commit this plan and T-SEC-6 ownership before implementation.
2. Add failing tests for CORS headers, minimized `/stats`, reader-key use,
   environment-example cleanup, exact S105 ratchet, and policy status.
3. Remove `NEXT_PUBLIC_API_AUTH_KEY` and its obsolete guidance from
   `.env.example`.
4. Set `allow_credentials=False` in the existing CORS middleware.
5. Read the existing client through `api.search.support_core`, preserve the
   error boundary, and return only
   `{"number_of_documents": stats.number_of_documents}`. Leave the unrelated
   `api.main.client` compatibility export for its later facade-removal owner.
6. Add line-level `# noqa: S105` explanations to the seven telemetry labels
   and three regex patterns. They are stable protocol/parsing constants, not
   secrets, so environment configuration is incorrect.
7. Remove the two broad S105 entries from `ruff.toml`.
8. After the implementation PR merges, open one narrow closure PR that marks
   the security checklist and ledger complete, updates this plan's delivery
   evidence, and ratchets the status test.

No new production helper or module is added. Each edit stays within its current
owner and import direction.

**f) Reuse audit.** Reuse `CORSMiddleware`, the existing Meilisearch client,
`get_stats()` error handling, `api.search.support_core.client`, current
API/TestClient fixtures, the reader-key subprocess test, and the repository's
exact Ruff selector checks. No wrapper, response model, config layer,
compatibility alias, or duplicate implementation is introduced.

Rejected alternatives:

- Protect `/stats` with the deployment key: conflicts with G2's public-read
  policy and adds no value once the payload is minimized.
- Move telemetry labels or regex patterns to environment variables: makes
  stable contracts mutable and disguises false positives as secrets.
- Use file-level `# ruff: noqa: S105`: preserves broad suppression and hides
  future real findings.

**g) Data contracts.** `/stats` changes from Meilisearch's complete
`IndexStats` payload to one JSON field, `number_of_documents: int`. This is a
deliberate public-response reduction. No request, Celery, schema, CLI, or
environment contract is added.

**h) Schema/migration impact.** None.

## 3. Security & Data Governance

**i) Security boundary.** This changes Internet-to-API CORS behavior and public
search metadata. Browsers lose credentialed cross-origin permission, and
unauthenticated callers lose indexing-state and field-distribution details.
`SECURITY.md` secret and reachable-posture controls apply.

**j) Secrets.** No secret is added. A misleading `NEXT_PUBLIC_*` key example is
removed. `API_AUTH_KEY` remains server-side.

**k) Person data.** None is created, linked, aggregated, or exposed. G4 is
unaffected.

**l) Untrusted input.** CORS origins remain checked by Starlette against
`ALLOWED_ORIGINS`. `/stats` returns a selected integer from the existing
Meilisearch response; no scraped content is rendered.

## 4. Code Health

**m) GED conformance.** No new nesting, time handling, environment reads, or
exception classes. The existing broad `/stats` boundary logs context and
returns HTTP 503; its invariant remains fail-closed. `api/main.py`'s unrelated
legacy structures are not replicated or expanded.

**n) Antipattern scan, plan pass.**

- A1/H1: installed Starlette 0.45.3 confirms `allow_credentials=False` and
  Context7 confirms restrictive CORS behavior; Ruff docs confirm line-level
  `# noqa: S105` versus file-level suppression.
- B1/F1: no response wrapper, parser, registry, or helper.
- D1: broad ignores are removed; no test, threshold, or policy is weakened.
- D3: exact JSON keys and CORS headers are public contracts.
- E1/E2: only named sections and owned selectors change.
- A2-A4, B2-B3, C1-C2, D2, E3, F2, H2-H4: no planned violations.

**o) Ratchet interaction.** Remove two `ruff.toml` S105 selectors:
`pipeline/provider_telemetry.py` and
`pipeline/topic_generation_contracts.py`. Add ten line-level S105
explanations for current false positives. Add or widen no rule, exclusion, or
file-level suppression.

**p) Dead code and duplication.** Delete two obsolete environment lines and
two broad Ruff selectors. Reuse all runtime owners. Expected production delta
is approximately ten explanatory comment suffixes and a smaller `/stats`
response.

## 5. Testing

**q) Edge and failure scenarios.**

1. Allowed-origin preflight succeeds without credential permission.
2. Disallowed-origin preflight receives no allowed-origin or credential header.
3. `/stats` returns exactly the document count.
4. Meilisearch failure still returns HTTP 503.
5. `/stats` still authenticates to Meilisearch with `MEILI_SEARCH_KEY`.
6. `.env.example` contains no browser-public API key.
7. Both broad S105 entries are absent.
8. Every current S105 false positive has a line-level explanation.
9. Telemetry keys and topic regex behavior remain unchanged.
10. Ledger, plan, and security checklist agree on T-SEC-6 state.

**r) Tests.**

| Test | Scenarios |
|---|---|
| New CORS tests in `tests/test_api.py` | 1-2 |
| New `/stats` success/failure tests in `tests/test_api.py` | 3-4 |
| Updated reader-key subprocess test | 3, 5 |
| New repository guardrail contract | 6-8, 10 |
| Existing telemetry/topic tests | 9 |
| Complete Python suite | Regression check |

Tests are written and run red before implementation.

**s) Fakes and mocks.** CORS uses FastAPI TestClient. `/stats` patches
`api.search.support_core.client`, the approved implementation boundary.
Reader-key coverage uses the existing local HTTP subprocess boundary. No
facade-only seam or new injectable parameter is added.

**t) Verification rows.** Apply security-sensitive trust reporting,
guardrail/tooling, API/search, inference-provider telemetry, and docs rows.
Run the complete Python suite because the task spans API, pipeline contracts,
guardrails, and policy.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

Tests-first red:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_api.py::test_cors_preflight_omits_credentials_for_allowed_origin \
  tests/test_api.py::test_cors_preflight_rejects_disallowed_origin \
  tests/test_api.py::test_stats_response_is_minimized \
  tests/test_api.py::test_stats_failure_returns_503 \
  tests/test_meilisearch_key_security.py::test_api_stats_uses_scoped_reader_key \
  tests/test_repository_guardrails.py::test_t_sec_6_closures_are_scoped
```

Expected before implementation: the CORS, minimized-stats, environment-example,
and S105-ratchet assertions fail; the existing 503 behavior remains green.

Final verification:

```bash
./.venv/bin/ruff check .
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_api.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_meilisearch_key_security.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_query_builder_filters.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_query_builder_parity_search_vs_trends.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_inference_provider_protocol_contract.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_http_provider_telemetry_metrics.py
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_topic_generation_cleanup.py tests/test_topics_tfidf_small_corpus.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/pytest -q
git diff --check
```

**v) Rollback.** Revert the T-SEC-6 merge commit and rerun the same commands.
No migration or data repair exists. Rollback restores credentialed CORS,
detailed public stats, the obsolete browser-key example, and two broad S105
exceptions.

**w) Docs sync.** The implementation PR records in-progress remediation
status and this plan. The closure PR updates the T-SEC-6 checklist in
`SECURITY.md`, completion status/changelog, this plan's evidence, and the
status guardrail. README, ADR, architecture, operations, testing policy, API
contract, and data-governance docs remain unchanged.

## 7. Delivery Self-Audit

**x) Diff scan.** Re-run A-F/H. Reject new authentication policy, full
Meilisearch payloads, configurable telemetry schemas, file-level S105
suppression, new seams, unrelated formatting, or edits outside ownership.

**y) Evidence.** Record tests-first failures, exact command outcomes and
counts, ratchet old/new values, independent reviews, commits, PR, review
threads, and final CI. Mark anything unrun `NOT VERIFIED`.

Implementation-head evidence: the tests-first command produced 5 expected
failures and 1 passing 503 test. After implementation, the same six tests
passed. Ruff passed; Mypy passed 68 files; API/reader-key tests passed 69;
guardrail/docs tests passed 388; telemetry/topic/query tests passed 46; the
complete Python suite passed 1,476 tests. Pre-commit review found one P2 in
the S105 explanation ratchet; the test now requires each exact explanation,
and rereview found no remaining P1/P2. PR #138 passed Frontend Tests, Python
Guardrails, and CodeQL; Codex found no major issues on `d6ddc00`; the PR
merged as `1805acd`. The post-merge closure test passed before delivery.
Closure review found one P2 because the task-table assertion did not reject
duplicate states; one shared parser now requires T-SEC-4, T-SEC-4A, and
T-SEC-6 to each have exactly one completed state.

**z) Deviations.** Expected: ownership expands from four to eleven files;
`/stats` remains public under G2 but is minimized; ten current S105 false
positives become line-level explanations. Any other response, secret, CORS,
rule, dependency, or file change is a blocker.
