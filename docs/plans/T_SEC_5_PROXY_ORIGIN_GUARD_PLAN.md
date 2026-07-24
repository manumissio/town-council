# T-SEC-5: Reject Non-Same-Origin Proxy Mutations

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: implementation-ready`
`execution: code`

## 1. Context & Alignment
**a) Driver.** Town Council's frontend proxy injects the deployment API key
into every backend request, so that key authenticates the frontend service,
not the visitor. The current POST route handlers accept cross-site browser
requests without checking `Origin` or `Sec-Fetch-Site`. T-SEC-5 closes that
request-forgery gap without deciding who may use AI actions, changing the API
key contract, or altering local-first runtime defaults.

**b) Canonical documents consulted.**
- `AGENTS.md` `<security_sensitive_paths>` requires a trust-boundary impact
  statement for `frontend/app/api/**`.
- `SECURITY.md` "Trust boundaries" identifies Internet-to-Frontend mutations
  as untrusted and assigns origin checks to T-SEC-5.
- `docs/TESTING.md` "Test placement" requires frontend tests under
  `frontend/components/__tests__/` and observable behavior at approved
  boundaries.
- `docs/ENGINEERING_GUARDRAILS.md` keeps configuration and tests aligned with
  current automation; this task does not change its policy.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` assigns same-origin mutation
  enforcement to T-SEC-5.
- `docs/reviews/architecture-review-2026-07-19.html` identifies the shared
  frontend proxy as the correct enforcement boundary.

**c) Remediation alignment.** T-SEC-5 is the active SEC-lane task. Expand its
ownership before implementation to exactly:

- `docs/plans/T_SEC_5_PROXY_ORIGIN_GUARD_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `SECURITY.md`
- `frontend/app/api/**`
- `frontend/components/__tests__/BackendProxy.origin.test.js`

The test path and security checklist were missing from the original task
ownership. No other path may change.

**d) Decision-gate check.** T-SEC-5 does not depend on or foreclose G1-G5.
G2 remains open because origin validation establishes request provenance, not
visitor authorization. T-SEC-4 remains blocked on G2, and Phase 2 remains
blocked on G3.

## 2. Design
**e) Step-by-step approach.**
1. Register this Full Template plan and corrected ownership in the remediation
   ledger.
2. Add failing Node tests before implementation for cross-site, mismatched
   origin, same-origin, and headerless server-side POST requests.
3. Remove the `next/server` dependency from the shared backend helper by using
   the standard `Response.json` supported by Next.js route handlers. This
   makes the actual proxy boundary directly testable with Node's built-in Web
   APIs; it does not change response semantics.
4. Add private target-origin and mutation predicates to the existing backend
   helper. The target origin uses the standard `Host`, the first
   `X-Forwarded-Proto` value after the edge proxy overwrites it, and the
   request URL as fallback; it never trusts `X-Forwarded-Host`.
5. Require each existing POST route to pass its incoming request to
   `proxyBackendJson` and keep method metadata aligned. The guard rejects a
   method disagreement before applying POST origin policy.
6. Return a JSON 403 before reading the API key or calling the backend when
   `Sec-Fetch-Site` is `cross-site` or `same-site`, or when a present `Origin`
   differs from that external target origin. Town Council defines no trusted
   sibling subdomains, so same-site is not equivalent to same-origin.
7. Permit exact same-origin requests and requests with neither browser header;
   the latter preserves callers that do not originate in a browser. This is a
   compatibility exception, not complete CSRF protection for legacy browsers
   that omit both signals.
8. Mark the T-SEC-5 security checklist control implemented in the branch.
   Keep the remediation task in progress until the implementation PR merges
   and receives a post-merge evidence readback.
9. Run frontend tests, frontend production build, Python frontend-contract
   tests, docs links, full Python suite, independent pre-commit review, PR
   review, and CI.

No new module is added. `proxyBackendJson` remains the single proxy facade, and
the private predicate never imports route modules.

**f) Reuse audit.** Extend `frontend/app/api/_lib/backend.js` and the existing
Node test runner. Reuse standard `Request`, `Response`, `Headers`, and `fetch`
interfaces already supplied by the supported Node and Next runtimes. Do not
add middleware, a CSRF package, a test loader, a route wrapper, or a second
origin-policy implementation.

Rejected alternatives:
- Global Next proxy enforcement: rejected because it would cover safe reads
  and unrelated routes rather than the shared backend mutation boundary.
- Referer-only validation: rejected because `Origin` and Fetch Metadata are
  the explicit browser security signals in the remediation contract.
- A synchronizer token: rejected because no browser session or user identity
  exists, and adding either would decide G2 by implication.
- Static source assertions only: rejected because they would not prove the
  runtime 403 and pass-through behavior.

**g) Data contracts.** This adds one rejection contract: blocked mutations
return `{"detail": "Cross-site mutation requests are not allowed."}` with
HTTP 403 and JSON content type. Successful and backend-error responses retain
the existing proxy contract. No typed application contract is needed for this
JavaScript request-boundary change.

**h) Schema/migration impact.** None.

## 3. Security & Data Governance
**i) Security-sensitive path.** This task changes the
Internet-to-Frontend trust boundary defined by `SECURITY.md`. An attacker loses
the ability to cause a visitor's browser to submit a cross-site mutation
through Town Council's API-key-injecting proxy. It does not add visitor
authentication or change who may intentionally invoke a same-origin action.

**j) Secrets.** No credential, key, environment variable, or default changes.
The API key remains server-side and is not logged or returned.

**k) Person data.** No person-level data is created, linked, aggregated, or
exposed. G4 is unaffected.

**l) Untrusted input.** `Origin`, `Sec-Fetch-Site`, and forwarded protocol are
untrusted request headers. The guard normalizes the target through `URL`,
uses standard `Host` rather than spoofable `X-Forwarded-Host`, and rejects
invalid target metadata. No scraped content or HTML is parsed.

## 4. Code Health
**m) GED conformance sweep.** Each private function has one responsibility and
no deep nesting. Named constants own policy literals. URL parsing catches only
`TypeError` and maps invalid target metadata to rejection. No environment read,
timestamp, type suppression, or import-time side effect is added.

**n) Antipattern scan, plan pass.**
- A1/H1: Next.js route-handler `Request`/`Response` behavior was verified
  against official Next.js 16.2.9 documentation and installed Next.js
  16.2.11. Node 20 `node:test` cleanup and global Fetch APIs were verified
  against official Node 20 documentation.
- B1/F1: no middleware, package, wrapper, registry, or duplicate policy module
  is added.
- B3: validation covers only existing POST proxy calls and the explicit
  non-browser no-header compatibility case.
- D1-D3: behavior tests exercise response status and backend pass-through;
  one source contract verifies that every POST route supplies the request
  object because direct route imports are not supported by the dependency's
  Node ESM entrypoint.
- E1-E3: only owned proxy routes, one test, the ledger, plan, and checklist
  change.
- A2-A4, B2, C1-C2, F2, H2-H4: no violations planned.

**o) Ratchet interaction.** No Ruff, Mypy, formatter, coverage, or broad
exception selector changes. No exception boundary is added or widened.

**p) Dead code and duplication audit.** Delete the `next/server` import after
replacing its sole `NextResponse.json` use with standard `Response.json`.
Reuse the shared proxy instead of repeating checks in five route handlers.
Expected runtime delta is focused private parsing/classification helpers plus
five request-property additions.

## 5. Testing
**q) Edge cases and failure scenarios.**
1. `Sec-Fetch-Site: cross-site` must return 403 even without `Origin`.
2. `Sec-Fetch-Site: same-site` must return 403 because sibling subdomains are
   not trusted.
3. A present `Origin` that differs by scheme, host, or port must return 403.
4. `Origin: null` and malformed origins must return 403.
5. Exact same-origin POST must reach the backend proxy.
6. A POST request object with neither browser header must reach the backend
   proxy.
7. A same-origin `Origin` paired with blocked Fetch Metadata must return 403
   because either signal can identify a non-same-origin request.
8. Unknown future `Sec-Fetch-Site` values must fall back to Origin validation.
9. Rejection must occur before API-key lookup or backend fetch.
10. Every existing POST route must supply its request object and matching
    method metadata; missing or mismatched metadata must fail closed.
11. Existing JSON body, query, authentication header, and backend-response
   forwarding must remain unchanged for allowed requests.
12. Next standalone's internal URL must honor standard Host and the first
   forwarded protocol value for a matching external origin.
13. Malformed Host/protocol metadata must reject, and `X-Forwarded-Host` must
   not override the standard Host.
14. GET routes and frontend build behavior must remain unchanged.
15. Missing `API_AUTH_KEY` on an allowed request must retain the existing 500
   response.

**r) Tests added or updated.**
| Test | Scenarios |
|---|---|
| Cross-site and same-site Fetch Metadata return JSON 403 | 1, 2, 9 |
| Scheme, host, and port Origin mismatches return JSON 403 | 3, 9 |
| Null and malformed Origin values return JSON 403 | 4, 9 |
| Blocked Fetch Metadata overrides matching Origin | 7, 9 |
| Unknown Fetch Metadata falls back to Origin validation | 8 |
| Same-origin POST forwards the backend response | 5, 11 |
| Headerless POST forwards the backend response | 6, 11 |
| Missing/mismatched POST metadata fails before backend access | 10 |
| Every POST route forwards its request and POST method | 10 |
| Standalone internal URL honors external Host/first protocol | 12 |
| Malformed metadata and spoofed X-Forwarded-Host reject | 13 |
| Allowed request without API key retains configuration error | 15 |
| Existing frontend suite and production build | 11, 14 |
| Existing Python frontend-contract tests | 14 |

The test file is written and run red before proxy implementation.

**s) Fakes and mocks.** Tests replace only `globalThis.fetch`, the approved
outbound HTTP boundary, and restore it after every test with Node's
`afterEach`. They set and restore `API_AUTH_KEY` as process configuration.
No production symbol, facade, or private predicate is patched.

**t) Verification rows.** Apply the frontend contract and frontend
component/behavior rows from `AGENTS.md`, plus docs links because `SECURITY.md`
and `docs/plans/**` change. Run the complete Python suite before handoff
because this is a security-boundary change.

## 6. Execution, Rollback, Docs
**u) Exact commands.**
```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-sec-5-proxy-origin-guard
```

Tests-first red evidence:
```bash
cd frontend
node --test components/__tests__/BackendProxy.origin.test.js
```

Final local verification:
```bash
cd frontend
npm test
npm run build -- --webpack
STANDALONE_SERVER=$(find .next/standalone -path '*/frontend/server.js' -print -quit)
test -n "$STANDALONE_SERVER"
HOSTNAME=0.0.0.0 PORT=3124 APP_ENV=dev \
  API_AUTH_KEY=frontend-proxy-test-key \
  INTERNAL_API_BASE_URL=http://127.0.0.1:9999 \
  node "$STANDALONE_SERVER" >/tmp/t-sec-5-next.log 2>&1 &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT
until curl -fsS http://localhost:3124 >/dev/null; do sleep 1; done
STATUS=$(curl -sS -o /tmp/t-sec-5-response.json -w '%{http_code}' \
  -X POST -H 'Origin: http://localhost:3124' \
  -H 'Sec-Fetch-Site: same-origin' \
  http://localhost:3124/api/summarize/42)
test "$STATUS" != 403
kill "$SERVER_PID"
trap - EXIT
cd ..

PYTHONPATH=. .venv/bin/pytest -q tests/test_frontend_pages_config.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_resultcard_agenda_status_refresh.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_search_sort_ui_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_semantic_search_ui_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/pytest -q
git diff --check
git status --short
```

Delivery uses two atomic commits:
1. `docs(remediation): authorize the proxy origin guard`
2. `fix(frontend): reject non-same-origin proxy mutations`

Push `codex/t-sec-5-proxy-origin-guard`, open one PR, request Codex review, and
wait for all required checks. After merge, verify the default branch and
close T-SEC-5 in a separate evidence-only ledger change.

**v) Rollback.** If the evidence-only closure has merged, first run
`git revert -m 1 <t-sec-5-closure-merge-sha>`, then run
`git revert -m 1 <t-sec-5-implementation-merge-sha>`. Rerun frontend tests and
build, the four Python frontend-contract tests, docs links, and the complete
Python suite. The closure reversal reopens the ledger status; the
implementation reversal reopens the `SECURITY.md` checklist. No migration,
secret rotation, environment restore, or data repair is required. Rollback
restores the known non-same-origin mutation gap.

**w) Docs sync.**
- `SECURITY.md` "Trust boundaries" and hardening checklist: record active
  same-origin mutation enforcement.
- Remediation plan: version, active status, corrected ownership, acceptance,
  and verification details.
- New T-SEC-5 Full Template plan.
- README, ADR, operations, testing policy, architecture review, API contract,
  and data-governance docs: no change.

## 7. Delivery Self-Audit
**x) Antipattern scan, diff pass.** Re-run A-F and H. Reject a new middleware
layer, duplicate route checks, user-auth behavior, test-only production
exports, swallowed errors, source-only assertions, unrelated formatting, or
any changed path outside the ownership set.

**y) Evidence.** Report the tests-first failure, every command from 6u, exact
frontend and Python counts, independent planning and pre-commit review
findings, commit hashes, PR URL, unresolved-thread count, and final CI state.
Mark anything unrun as `NOT VERIFIED`.

**z) Deviations.** Authorized ledger corrections are the Full plan, test path,
and `SECURITY.md` ownership. Any other changed file, new package, middleware,
route contract, visitor-auth policy, unresolved P1/P2, skipped review, or
unrun required command is a blocker.
