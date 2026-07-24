# T-SEC-4: Trusted Client Identity and Per-Client Rate Limits

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: implementation-ready`
`execution: code`

## 1. Context & Alignment

**a) Driver.** G2 keeps account-free AI actions available through the public
frontend, so rate limits need a client identity that visitors cannot choose.
Next.js 16.2.11 preserves caller-supplied `X-Forwarded-For` and only inserts
the socket peer when that header is absent. Forwarding the header directly
would let non-browser callers select their own rate-limit bucket. The operator
approved a repository-owned ingress that becomes the sole public frontend
entry and overwrites forwarded identity before requests reach Next.js.

**b) Canonical documents consulted.**

- `AGENTS.md` security, workflow, verification, and runtime-default contracts
  require a trust-boundary report, tests first, full verification, and explicit
  approval for this topology change.
- `SECURITY.md` defines the Internet-to-Frontend and Frontend-to-API boundaries
  and records T-SEC-4 as the remaining G2 abuse control.
- `docs/TESTING.MD` permits HTTP, filesystem, subprocess, and dependency
  boundaries without production test seams.
- `docs/ENGINEERING_GUARDRAILS.md` keeps Ruff and Mypy policy unchanged.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` owns G2, T-SEC-4 sequencing,
  and exclusive paths.
- `docs/reviews/architecture-review-2026-07-19.html` identifies shared
  proxy-origin rate buckets as a P0 security defect.

**c) Remediation alignment.** T-SEC-4 remains in the SEC lane. Expand
`files_owned` to:

- `docs/plans/T_SEC_4_TRUSTED_CLIENT_IDENTITY_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `docker-compose.yml`
- `docker/Caddyfile`
- `frontend/app/api/_lib/backend.js`
- `frontend/components/__tests__/BackendProxy.origin.test.js`
- `api/app_setup.py`
- `tests/test_api_client_identity.py`
- `tests/test_docker_build_contracts.py`
- `tests/test_repository_guardrails.py`
- `scripts/verify_caddy_forwarded_for.sh`
- `SECURITY.md`
- `docs/OPERATIONS.md`

**d) Decision gates.** G2 is approved. On 2026-07-24 the operator also
approved the repository-owned ingress and its runtime-topology change. G1's
reachable posture is therefore handled, not assumed away. G3 is satisfied.
G4 and G5 are unaffected.

## 2. Design

**e) Step-by-step approach.**

1. Add failing tests for ingress isolation, Caddy configuration, Uvicorn raw
   peer preservation, frontend IP validation, API trust, spoof rejection,
   malformed input, and separate client keys.
2. Add `ingress` using exact image `caddy:2.11.4-alpine`. Publish host port
   `3000` only from ingress. Keep `frontend:3000` internal with `expose`.
3. Add `docker/Caddyfile`. Caddy directly accepts public traffic and uses its
   default reverse-proxy behavior, which ignores incoming spoofed forwarded
   headers and writes the direct client identity for Next.js.
4. Add `--no-proxy-headers` to Uvicorn so `request.client.host` remains the
   actual API peer instead of being rewritten before application validation.
5. In `backend.js`, accept exactly one valid IPv4 or IPv6 value from Caddy's
   `X-Forwarded-For`; forward it to the API. Omit missing, malformed, or
   multi-value input.
6. In `app_setup.py`, reuse API-key comparison to authenticate the frontend
   deployment. Trust one canonical forwarded IP only when the deployment key
   matches. Otherwise use SlowAPI's direct remote address.
7. Prove Caddy replaces a spoofed incoming header using a temporary echo
   upstream during runtime verification.
8. Update security and operations docs. Mark T-SEC-4 complete only after
   runtime verification, independent review, and green PR checks.

New functions:

- `getForwardedClientIp(request)`: validate one ingress-provided IP for the
  outgoing frontend-to-API request.
- `_api_key_matches(candidate)`: own constant-time deployment-key comparison.
- `_forwarded_client_ip(request)`: parse one canonical forwarded IP.
- `rate_limit_client_key(request)`: choose trusted forwarded identity or the
  direct API peer.

No helper imports a route or facade. `app_setup.py` remains the limiter owner.

**f) Reuse audit.** Reuse `proxyBackendJson`, `env_raw`,
`get_remote_address`, the deployment API key, SlowAPI's custom `key_func`,
existing frontend proxy tests, and Compose contract helpers. No middleware,
proxy framework, identity registry, CIDR parser, fixed subnet, compatibility
path, or duplicate limiter is added.

Rejected alternatives:

- Forward Next.js `X-Forwarded-For` directly: caller-spoofable.
- `@vercel/functions.ipAddress()`: reads forwarded metadata and does not fix
  the direct Docker deployment.
- Dynamic Compose-network CIDR trust: no stable subnet and trusts unrelated
  containers.
- Fixed container IPs: collision-prone host networking and unnecessary config.
- Visitor cookies: resettable and not a trustworthy abuse-control identity.

**g) Contracts.**

- Public port `3000` terminates at Caddy, not Next.js.
- Caddy is not configured to trust an upstream proxy.
- Frontend forwards only one syntactically valid IP.
- API trusts forwarded identity only with the valid deployment key.
- Invalid or untrusted identity falls back to the direct API peer.
- Possession of `API_AUTH_KEY` remains the trusted deployment-operator
  boundary. A direct caller with that secret can choose forwarded identity,
  but already holds authority to invoke protected actions; visitors do not.
- Runtime URLs, public access policy, API routes, task signatures, and rate
  thresholds remain unchanged.

**h) Schema/migrations.** None.

## 3. Security & Data Governance

**i) Trust-boundary impact.** Internet traffic loses direct access to Next.js.
Caddy strips caller-controlled forwarded identity and establishes the client
IP passed to Next.js. The deployment API key authenticates the frontend-to-API
hop. Direct API callers cannot select forwarded rate buckets without that key;
missing or malformed identity uses their socket peer. This implements
`SECURITY.md` T-SEC-4 and reduces anonymous inference-capacity abuse.

**j) Secrets.** No new secret or browser-visible variable. Existing
`API_AUTH_KEY` remains server-side.

**k) Person data.** Client IP is used transiently as a limiter key. It is not
persisted, linked to civic records, returned, or added to person metadata.

**l) Untrusted input.** Caddy owns the public header boundary. Frontend and API
still validate the resulting header. Scraped content is unaffected.

## 4. Code Health

**m) GED conformance.** Functions stay focused, typed in Python, and under two
nesting levels. IP literals live only in tests. Errors fall back to the direct
peer rather than being swallowed. No timestamp or new environment read exists.

**n) Antipattern scan, plan pass.**

- A1/H1 corrected: verified installed Next.js 16.2.11 source, SlowAPI 0.1.9,
  Node 20 `net.isIPv4`/`net.isIPv6`, Caddy reverse-proxy defaults, Compose
  service isolation, and Caddy release 2.11.4.
- A2/B1 corrected: no new env setting, middleware, registry, or fixed network.
- B3 corrected: validation covers attacker-controlled headers at two trust
  boundaries.
- C1 corrected: direct frontend publication is removed.
- D1-D3 corrected: tests assert externally visible forwarding, isolation, and
  limiter keys without skips or private patch seams.
- E1-E3/F1-F2/H2-H4: no planned violation.

**o) Ratchets.** No Ruff, Mypy, BLE001, coverage, formatter, or workflow
exception changes.

**p) Dead code and duplication.** Remove direct frontend port publication and
the limiter's direct-only key function. Reuse one API-key comparison. Expected
net growth is one small ingress config, focused tests, and policy/runbook text.

## 5. Testing

**q) Edge and failure scenarios.**

1. Caller supplies spoofed XFF to ingress.
2. Frontend receives missing, malformed, whitespace-padded, or multi-value IP.
3. Valid IPv4 and IPv6 identities reach API.
4. API receives forwarded IP with missing or wrong deployment key.
5. API receives malformed or multi-value forwarded identity with valid key.
6. Two trusted clients must produce different limiter keys.
7. Direct frontend publication or Uvicorn proxy rewriting returns.
8. Caddy is configured to trust an upstream proxy, weakening the sole-ingress
   invariant.
9. Ingress or frontend health/dependency wiring breaks.
10. Caddy validates but fails to replace spoofed forwarded identity at runtime.

**r) Tests.**

- Frontend Node tests cover 2-3 and outgoing headers.
- `tests/test_api_client_identity.py` covers 3-6 with Starlette request scopes.
- Docker contracts cover 1 and 7-9 by asserting sole publication, Caddy's
  minimal configuration, read-only mount, dependency, and Uvicorn command.
- Runtime verification covers 10 against a temporary echo upstream.
- Repository guardrails cover T-SEC-4 status and remaining-policy alignment.
- Existing API, frontend, security, and full suites cover regression.

**s) Fakes/mocks.** Frontend tests fake outbound `fetch`, an approved HTTP
boundary. API tests build Starlette requests and patch environment only.
Compose tests use the existing filesystem/subprocess boundary. No facade is
patched.

**t) Verification rows.** Apply security-sensitive, frontend behavior,
API/search, guardrail/tooling, and docs rows. Run frontend tests and the full
Python suite.

## 6. Execution, Rollback, Docs

**u) Commands.**

```bash
./.venv/bin/ruff check .
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_api_client_identity.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docker_build_contracts.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_api.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
cd frontend && npm test
docker compose config --quiet
docker run --rm -v "$PWD/docker/Caddyfile:/etc/caddy/Caddyfile:ro" \
  caddy:2.11.4-alpine caddy validate --config /etc/caddy/Caddyfile
PYTHONPATH=. .venv/bin/pytest -q
git diff --check
```

Runtime smoke:

```bash
docker compose up -d --build ingress frontend api
curl -fsS http://localhost:3000/
docker compose ps ingress frontend api
```

Spoof replacement proof uses the same pinned Caddy image with a temporary echo
upstream. The response must contain the direct Docker client address and must
not contain `198.51.100.77`:

```bash
./scripts/verify_caddy_forwarded_for.sh
```

**v) Rollback.** Revert the T-SEC-4 merge commit, remove the obsolete ingress
container, recreate `api` and `frontend`, then verify the prior direct frontend
port and direct-peer limiter behavior. This knowingly restores the accepted
shared-bucket risk.
No migration or data repair is required.

**w) Docs sync.** Update `SECURITY.md` trust boundaries, checklist, and accepted
risk; `docs/OPERATIONS.md` startup, ingress, verification, and rollback;
remediation status and changelog; this plan. README, ADR, testing policy,
architecture map, API contract, and data-governance docs remain unchanged.

## 7. Delivery Self-Audit

**x) Diff scan.** Re-run A-F/H. Reject trusted upstream proxies, direct
frontend publication, XFF forwarding without validation and deployment-key
trust, middleware, new secrets, fixed container IPs, broadened guardrails,
unrelated formatting, and edits outside owned paths.

**y) Evidence.** Report tests-first failures, every command outcome, exact
counts, image/config validation, runtime smoke, planning and pre-commit review
findings, commits, PR, unresolved threads, and final CI state. Mark unrun work
`NOT VERIFIED`.

**z) Deviations.** Expected: Caddy ingress, expanded ownership, explicit
deployment-key trust instead of unstable CIDR trust, Uvicorn raw-peer
preservation, and one owned verification script for the functional Caddy
proof. Any other topology, dependency, config, policy, or file change is a
blocker.
