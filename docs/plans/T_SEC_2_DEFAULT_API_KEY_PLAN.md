# T-SEC-2: Reject the Default API Key Outside Development

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: complete`
`execution: code`

## 1. Context & Alignment

**a) Driver.** `SECURITY.md` states that a reachable deployment must refuse
startup when `API_AUTH_KEY` still uses the checked-in development value, but
`api/app_setup.py` currently logs a warning and continues in every environment.
T-SEC-2 closes that policy/behavior gap before later proxy and scoped-key work.

**b) Canonical documents consulted.**

- `AGENTS.md` `<security_sensitive_paths>` requires a trust-boundary impact
  statement for `api/app_setup.py`; `<workflow_contract>` requires the API and
  full-suite verification rows.
- `SECURITY.md` "Secret policy" requires non-development startup refusal for
  working default credentials while preserving local development ergonomics.
- `docs/TESTING.MD` requires observable startup behavior through real framework
  boundaries and implementation-module patch targets.
- `docs/ENGINEERING_GUARDRAILS.md` keeps Ruff and Mypy policy unchanged.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` assigns T-SEC-2 P0 priority
  after completed T-SEC-1.
- `docs/reviews/architecture-review-2026-07-19.html` keeps Phase 2 blocked but
  permits Phase 1 security work.

**c) Remediation alignment.** T-SEC-2 remains in the security lane. Expand its
owned files before implementation to:

- `docs/plans/T_SEC_2_DEFAULT_API_KEY_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `api/app_setup.py`
- `tests/test_api_startup_security.py`
- `SECURITY.md`

No other tracked file may change.

**d) Decision-gate check.** T-SEC-2 does not depend on or foreclose G1-G5.
The plan's reachable-posture assumption requires the control regardless of
whether the owner later declares G1 local or reachable. G2 remains open and is
not an authentication claim: the API key authenticates the frontend deployment,
not individual users.

## 2. Design

**e) Step-by-step approach.**

1. Register the plan, expanded ownership, and implementation-ready status.
2. Add failing FastAPI lifespan tests before production changes.
3. In `api/app_setup.py`, replace both inline `API_AUTH_KEY` reads with
   `env_raw` and read `APP_ENV` through `env_lower`, reusing
   `pipeline/config_env.py`. Preserve the raw configured key for constant-time
   request comparison.
4. When normalized `APP_ENV` is not `dev` and the stripped key is the
   checked-in default or blank, raise `RuntimeError` with a named,
   operator-facing message before database initialization, startup purge, or
   semantic health checks. Use stripping only to classify unsafe credentials;
   do not rewrite an accepted key.
5. When the key equals the default and normalized `APP_ENV` is `dev`, preserve
   the current critical warning and continue startup.
6. Reject every nonempty key containing non-ASCII, control, or leading or
   trailing whitespace characters because HTTP header parsing or string
   comparison cannot authenticate it reliably. When a printable-ASCII,
   nonblank, non-default key is supplied, continue startup without rewriting
   it.
7. Mark the T-SEC-2 security checklist item complete only after local and pull
   request verification are green.
8. Run simplification and an independent pre-commit review, then commit, push,
   open one PR, resolve all P1/P2 feedback, and merge only after current-head CI
   and review are clean.

No new module or production helper is required. The existing lifespan function
owns startup policy and remains within the enforced complexity ceiling.

**f) Reuse audit.** Reuse `DEFAULT_API_AUTH_KEY`, the existing lifespan
boundary, `pipeline.config_env.env_lower`, `pipeline.config_env.env_raw`, and
FastAPI's existing `TestClient` pattern. Do not introduce a secret manager,
configuration object, compatibility path, middleware, or duplicate key
validator.

**g) Data contracts.** No application payload changes. The startup contract is:

- missing `APP_ENV` defaults to `dev`;
- whitespace and case in `APP_ENV` normalize through `env_lower`;
- blank or any normalized value other than `dev` is non-development;
- the known development key with or without surrounding whitespace, an empty
  key, and a whitespace-only key are rejected outside development;
- keys containing non-ASCII, control, or edge-whitespace characters are
  rejected with an operator-facing error instead of failing later during HTTP
  authentication;
- a printable-ASCII, nonblank, non-default key starts normally and remains
  byte-for-byte unchanged and case-sensitive for request authentication.

**h) Schema/migration impact.** None.

## 3. Security & Data Governance

**i) Security-sensitive path.** `api/app_setup.py` is the API startup,
authentication, and rate-limit trust boundary. The change removes an attacker's
ability to authenticate to a non-development API with the public checked-in
key, a padded form of that key, or no request header when the configured key is
empty. It also rejects keys whose non-ASCII, control, or edge-whitespace
characters cannot survive the HTTP header boundary unchanged. It implements
`SECURITY.md` "Secret policy" and does not alter endpoint authorization, rate
limiting, CORS, or proxy behavior.

**j) Secrets.** No credential or default changes. The checked-in key remains a
local-development fallback. No value is logged; only the policy violation is
reported.

**k) Person data.** No person-level data is created, linked, aggregated, or
exposed. G4 is unaffected.

**l) Untrusted input.** Environment values are the only inputs. `APP_ENV` is
stripped and lowercased by the established helper. No scraped content,
provider response, HTTP body, or browser input is parsed.

## 4. Code Health

**m) GED conformance sweep.** The modified lifespan retains one responsibility:
ordered startup policy and initialization. The error text becomes a named
constant. No new nesting beyond two levels, broad exception, timestamp,
generic identifier, inline environment default, or import-time execution is
added.

**n) Antipattern scan, plan pass.**

- A1/H1: FastAPI lifespan and `TestClient` context-manager behavior were
  verified against `/websites/fastapi_tiangolo`; installed tests already use
  the same API.
- A2/B1: no environment variable or configuration layer is added.
- B2/C1: no compatibility or warning-only non-development path survives.
- D1-D3: tests assert startup success/failure and warning behavior, not helper
  calls or private state.
- E1-E3: only the five owned files may change.
- A3-A4, B3, C2, F1-F2, H2-H4: no violations planned.

**o) Ratchet interaction.** `api/app_setup.py` is not in a Ruff per-file-ignore
entry. No selector, BLE001 boundary, type scope, formatter scope, coverage
threshold, or workflow gate changes.

**p) Dead code and duplication audit.** The unconditional warning branch is
replaced by environment-aware fail-fast behavior in the same location. No
production code is copied. Expected production delta is two named messages,
two config-helper imports, and two conditional branches.

## 5. Testing

**q) Edge and failure scenarios.**

1. `APP_ENV=prod` with the default key aborts startup.
2. Another non-development value such as `staging` with the default key aborts.
3. Blank `APP_ENV` with the default key fails closed.
4. An empty or whitespace-only key outside development aborts startup, so a
   missing request header cannot authenticate against an empty expected key.
5. Surrounding whitespace cannot disguise the checked-in default key outside
   development.
6. A key containing non-ASCII, control, or edge-whitespace characters aborts
   with a clear startup error before downstream startup work.
7. Missing `APP_ENV` defaults to development and starts with the current
   critical warning.
8. Mixed-case or padded `dev` normalizes to development and starts.
9. A non-default printable-ASCII key starts in production and remains
   case-sensitive.
10. Rejection occurs before database, purge, or semantic startup work.
11. No key value appears in the exception or log message.
12. Accepted startup never performs an uncontrolled semantic-service request,
    regardless of the process's imported feature-flag state.

**r) Tests added.**

| Test | Scenarios |
|---|---|
| `test_non_dev_startup_rejects_unsafe_api_key` | 1-6, 10, 11 |
| `test_dev_startup_allows_default_api_key_with_warning` | 7, 8, 11, 12 |
| `test_non_dev_startup_accepts_configured_api_key` | 9, 12 |

Each test constructs a small `FastAPI(lifespan=app_setup.lifespan)` instance
and enters it through `TestClient` so startup behavior is observable at the
framework boundary. No fixed test-count assertion is added.

**s) Fakes and mocks.** Tests use FastAPI's real lifespan boundary and the
approved environment, database, and outbound-HTTP boundaries:

- the existing autouse fixture replaces `api.app_setup.db_connect` with the
  shared SQLite engine for accepted startup;
- rejection tests replace that same implementation-module database boundary
  with a fail-if-reached sentinel after resetting `SessionLocal`, proving the
  first downstream startup stage was not entered. Because database
  initialization precedes purge and semantic checks, that observable boundary
  also proves later stages were not reached;
- accepted tests patch `api.search.semantic_support.httpx.get` with a healthy
  response at the approved outbound-HTTP boundary, preventing a real request
  even if `SEMANTIC_ENABLED` was true before test collection;
- accepted tests explicitly disable startup purge through its documented
  environment contract.

No private semantic helper, facade re-export, or purge function is patched. No
new production test seam is added.

**t) Verification rows.** Apply the API/search behavior row because
`api/app_setup.py` changes, the docs-only row because security and planning
docs change, Ruff for Python changes, and the full suite because this modifies
the shared API lifespan. Run current-head PR CI as the authoritative merge gate.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-sec-2-default-key-fail-fast
```

Tests-first red evidence:

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/test_api_startup_security.py
```

Final local verification:

```bash
./.venv/bin/ruff check .
./.venv/bin/pre-commit run ruff --all-files
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_api_startup_security.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_api.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_query_builder_filters.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_query_builder_parity_search_vs_trends.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/pytest -q
git diff --check
git status --short
```

Delivery uses two commits:

1. `docs(remediation): authorize T-SEC-2 startup hardening`
2. `fix(security): reject the default API key outside development`

Push the branch, open one PR titled
`T-SEC-2: Reject the default API key outside development`, request Codex
review, and watch current-head CI to a decided state before merge.

**v) Rollback.** Revert the T-SEC-2 merge commit and rerun the same targeted,
API, docs, Ruff, Mypy, and complete-suite commands. No migration, data repair,
credential rotation, or external-state cleanup is required. Rollback knowingly
restores warning-only behavior for non-development use of the public default
key.

**w) Docs synchronization.**

- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`: version, ownership, status,
  plan link, acceptance, and completion ledger.
- `SECURITY.md`: mark T-SEC-2 complete only after verified implementation.
- New T-SEC-2 Full plan.
- README, ADR, operations, architecture review, testing policy, data governance,
  OpenAPI, and environment examples: no changes.

## 7. Delivery Self-Audit

**x) Diff scan.** Re-run A-F/H. Reject a second validator, inline `os.getenv`
default, secret-bearing logs, dev behavior drift, uncontrolled outbound HTTP,
endpoint changes, new configuration, private-state assertions, facade
patching, unrelated formatting, or edits outside the five-file ownership set.

**y) Evidence.**

- Tests-first: `4 failed, 9 passed`; the edge-whitespace and internal-whitespace
  cases reached the database sentinel before the production correction.
- Focused startup security: `14 passed`.
- API and docs verification: `63 passed`.
- Complete Python suite: `1,143 passed`.
- Ruff, pre-commit Ruff, Mypy, and `git diff --check`: PASS.
- Independent pre-commit review: two P2 findings corrected; final re-review
  reported no P1/P2 findings.
- Pull request: [#122](https://github.com/manumissio/town-council/pull/122).
- Commits: `eb41624`, `109cb46`, and P1 correction `97ff76f`.
- Implementation-head review: Codex reported no major issues on `97ff76f`.
- Implementation-head CI: frontend, Python Guardrails, and CodeQL checks
  passed. The closure commit must pass the same pull-request gates before
  merge.
- Review threads: `0` unresolved.

**z) Deviations.** The authorized remediation-plan correction expanded
T-SEC-2 ownership. Delivery uses a fourth, docs-only closure commit because the
security checklist and registry could not truthfully close until implementation
CI and review passed. A narrow `sed -i` removed only merge-conflict markers
during rebase after `apply_patch` could not match them. Context7 had no h11
entry, so the installed h11 0.16.0 parser provided executable API and boundary
evidence. No additional path, credential/default, endpoint policy, or unrelated
task status changed.
