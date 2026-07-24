# Security

This document is canonical for Town Council's threat model, trust boundaries,
secret policy, and hardening controls. `AGENTS.md`
`<security_sensitive_paths>` requires a trust-boundary impact statement for
changes touching the paths listed there; this document defines the boundaries
those statements reference.

Status: initial version. Controls marked `[remediation: T-SEC-*]` are
delivered by the corresponding remediation-plan tasks; until a task merges,
treat its control as a known gap, not an implemented guarantee.

## Deployment posture (decision G1)

Two supported postures. The posture in effect determines which controls are
mandatory.

- `local`: single-machine dev/contributor stack. Default credentials are
  tolerated; backing-store ports may be published via
  `docker-compose.dev.yml` only.
- `reachable`: any instance where the frontend or API is network-accessible
  beyond localhost (VPS, LAN demo, tunnel). All controls below are mandatory.

Current declared posture: ___ (owner fills in; default assumption for
engineering decisions is `reachable`).

## Trust boundaries

1. Internet -> Frontend (Next.js): untrusted browsers. CSP (nonce +
   strict-dynamic), security headers, and same-origin checks on mutation
   routes apply here. The mutation guard rejects `same-site` and `cross-site`
   Fetch Metadata plus mismatched `Origin` values; requests with neither
   browser signal remain compatible for non-browser callers
   `[remediation: T-SEC-5]`.
   Reverse proxies must preserve the public `Host` header and overwrite any
   incoming `X-Forwarded-Proto`; the guard deliberately ignores
   `X-Forwarded-Host`.
2. Frontend server -> API: the proxy injects `X-API-Key` server-side
   (`frontend/app/api/_lib/backend.js`). Consequence: the API key does NOT
   authenticate end users; it only authenticates the frontend deployment.
   Every proxied route is effectively public. Per-client rate limiting
   therefore depends on forwarding real client identity
   `[remediation: T-SEC-4]`, and any "operator only" action requires auth at
   the proxy, not just the key (decision G2, currently open).
3. API and semantic service -> backing stores (Postgres, Redis, Meilisearch,
   inference): compose
   network only. No host port publication in the base compose file
   `[remediation: T-SEC-1]`. API and semantic Meilisearch readers use
   `MEILI_SEARCH_KEY`, scoped to `search` and `stats.get` on `documents`; only
   writer and administration services receive `MEILI_MASTER_KEY`
   `[remediation: T-SEC-3]`.
4. Crawler -> municipal portals: outbound only. Honest identifying
   user agent, `ROBOTSTXT_OBEY=True`, per-domain delay
   `[remediation: T-CRAWL-1]`.
5. Untrusted document content -> pipeline/UI: scraped PDFs/HTML are
   attacker-influencable input. Extracted text and Meilisearch highlight
   HTML must be sanitized before `dangerouslySetInnerHTML` (DOMPurify —
   already enforced in `ResultCard.js`; keep it that way).

## Secret policy

- No working default or blank credential may permit non-development
  operation. The API refuses to start outside development with a default
  (including surrounding whitespace), empty, or whitespace-only
  `API_AUTH_KEY`. Every nonempty API key must contain printable ASCII
  characters without leading or trailing whitespace so HTTP header parsing
  cannot change the authenticated value `[remediation: T-SEC-2]`. Extend the
  same pattern to any future secret.
- API and semantic startup rejects a missing, development-fallback, or
  transport-unsafe `MEILI_SEARCH_KEY` outside development. The fake reader
  fallback is development-only. Operators must verify the candidate key's
  exact action and index scope before restarting either reader.
- Base Compose runs Meilisearch in production mode and requires a master key;
  the development overlay is the only checked-in path that selects
  Meilisearch development mode.
- No secret in a `NEXT_PUBLIC_*` variable, ever. These ship to browser
  bundles.
- Secrets enter via environment/.env only; `.env` is gitignored. No secrets
  in compose files beyond dev-only fallbacks, and dev fallbacks must be
  obviously fake (`dev_secret_key_change_me` style).
- Base reader services do not bind-mount the repository, and Docker build
  context excludes local `.env` variants. The development overlay may restore
  targeted source-directory mounts for local iteration, never the repository
  root.
- Key inventory: `API_AUTH_KEY` (frontend->API), `MEILI_MASTER_KEY`
  (pipeline/worker writes + admin), `MEILI_SEARCH_KEY` (API and semantic reads,
  `[remediation: T-SEC-3]`), `POSTGRES_PASSWORD`, `REDIS_PASSWORD`,
  Grafana admin credentials.

## Hardening checklist (reachable posture)

- [x] Base compose publishes only `api:8000` and `frontend:3000` (T-SEC-1)
- [ ] Non-default values for every key in the inventory above
- [x] API aborts on default key outside dev (T-SEC-2)
- [x] Meilisearch search key enforced for API and semantic readers (T-SEC-3)
- [ ] Client IP forwarded from proxy; limiter keys on it with trusted-proxy
      allowlist (T-SEC-4)
- [x] Origin/Sec-Fetch-Site check on proxy mutation routes (T-SEC-5)
- [ ] `NEXT_CSP_ENFORCE=true` after a report-only soak
- [ ] `/stats` gated or minimized; CORS without `allow_credentials`
      (T-SEC-6)
- [ ] Backups configured per `docs/OPERATIONS.md` (T-PLAT-3)

## Known accepted risks

Record deliberate acceptances here with rationale and revisit date, per the
`AGENTS.md` status-reporting contract (old value, new value, rationale).

- (none recorded yet)

## Dependency and supply chain

Dependabot plus `pip-audit` / `npm audit` run in CI `[remediation: T-PLAT-2]`.
High-severity findings on the API, frontend, or crawler dependency families
block merge once the audit steps are promoted from report-only.

## Reporting a vulnerability

Open a GitHub security advisory on the repository (preferred) or contact the
maintainer through the repository profile. Do not open public issues for
exploitable findings. Municipal data is public record, but responsible
disclosure still applies to anything enabling service abuse or data
tampering.
