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

Current declared posture: `reachable` (operator-approved 2026-07-26).

## Trust boundaries

1. Internet -> Caddy -> Frontend (Next.js): untrusted browsers. Caddy is the
   only published frontend entry and replaces caller-supplied
   `X-Forwarded-For` before requests reach Next.js. It is deliberately not
   configured to trust an upstream proxy. CSP (nonce +
   strict-dynamic), security headers, and same-origin checks on mutation
   routes apply here. The mutation guard rejects `same-site` and `cross-site`
   Fetch Metadata plus mismatched `Origin` values; requests with neither
   browser signal remain compatible for non-browser callers
   `[remediation: T-SEC-5]`.
   Caddy preserves the public `Host` header and writes `X-Forwarded-Proto`;
   the guard deliberately ignores `X-Forwarded-Host`.
2. Frontend server -> API: the proxy injects `X-API-Key` server-side
   (`frontend/app/api/_lib/backend.js`). Consequence: the API key does NOT
   authenticate end users; it only authenticates the frontend deployment.
   Every proxied route is effectively public. Decision G2, approved 2026-07-24,
   keeps summarize, segment, extract, and topic-generation actions available to
   visitors through the public Next.js proxy. Direct calls to protected AI
   mutation endpoints, including vote extraction, still require `X-API-Key`;
   public read and task-status routes remain public. Town Council intentionally
   provides civic record analysis without end-user accounts. Adding operator
   authentication would change that access model. Per-client rate limits are
   therefore the approved abuse control. The frontend forwards one validated
   client IP, and the API uses it only when `API_AUTH_KEY` authenticates the
   deployment hop; otherwise the limiter uses the direct API peer
   `[remediation: T-SEC-4]`. Any future "operator only" action would require a
   new policy decision and proxy authentication, not just the deployment key.
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

- [x] Base compose publishes only `api:8000` and Caddy ingress `3000`
      (T-SEC-1, T-SEC-4)
- [ ] Non-default values for every key in the inventory above
- [x] API aborts on default key outside dev (T-SEC-2)
- [x] Meilisearch search key enforced for API and semantic readers (T-SEC-3)
- [x] Caddy replaces caller forwarding metadata; frontend validates one IP;
      API limiter trusts it only with the deployment key (T-SEC-4)
- [x] Origin/Sec-Fetch-Site check on proxy mutation routes (T-SEC-5)
- [ ] `NEXT_CSP_ENFORCE=true` after a report-only soak
- [x] `/stats` gated or minimized; CORS without `allow_credentials`
      (T-SEC-6)
- [ ] Backups configured per `docs/OPERATIONS.md` (T-PLAT-3)

## Known accepted risks

Record deliberate acceptances here with rationale and revisit date, per the
`AGENTS.md` status-reporting contract (old value, new value, rationale).

- **Deployment-key client identity trust.** G2 preserves account-free public
  access through the frontend while protected direct API actions require
  `API_AUTH_KEY`. The same deployment key authenticates forwarded client
  identity at the API. A direct caller holding that secret can therefore
  choose a forwarded limiter key, but already has authority to invoke the
  protected actions. Visitors never receive the key. Revisit if the key is
  delegated beyond trusted deployment operators or by 2026-10-31, whichever
  comes first.

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
