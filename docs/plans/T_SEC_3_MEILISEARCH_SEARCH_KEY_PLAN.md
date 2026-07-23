# T-SEC-3: Scope Meilisearch Reader Credentials

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: in-review`
`execution: code`
## 1. Context & Alignment

**a) Driver.** The API and semantic service currently construct read clients
with `MEILI_MASTER_KEY`. Compromise of either reader therefore exposes
Meilisearch administration and write capability. T-SEC-3 limits both reader
services to a scoped read key while preserving the master key for indexing and
administration.

**b) Canonical documents consulted.**

- `AGENTS.md` `<security_sensitive_paths>` requires a trust-boundary impact
  statement for Compose changes; `<hard_invariants>` requires local-first
  behavior and fail-fast non-development configuration.
- `SECURITY.md` "Trust boundaries" requires API-to-Meilisearch reads to use a
  scoped key; T-SEC-3 expands that control to the semantic lexical reader.
- `docs/TESTING.md` permits Meilisearch client substitution at its construction
  point and filesystem/subprocess verification without production test seams.
- `docs/ENGINEERING_GUARDRAILS.md` leaves Ruff, Mypy, formatter, and coverage
  policy unchanged.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` assigns T-SEC-3 to Phase 1 and
  keeps facade removal behind G3.
- `docs/reviews/architecture-review-2026-07-19.html` permits Phase 1 security
  work while Phase 2 remains blocked.

**c) Remediation alignment.** T-SEC-3 remains in the security lane. Expand its
owned files before implementation to
`docs/plans/T_SEC_3_MEILISEARCH_SEARCH_KEY_PLAN.md`,
`docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`,
`pipeline/meilisearch_credentials.py`, `api/app_setup.py`,
`api/search/support_core.py`, `semantic_service/main.py`, `docker-compose.yml`,
`docker-compose.dev.yml`, `.dockerignore`, `.env.example`, `README.md`,
`scripts/dev_up.sh`, `scripts/bootstrap_local_models.sh`,
`scripts/run_soak_day.sh`, `frontend/.dockerignore`,
`env/profiles/README.md`, `docs/OPERATIONS.md`, `SECURITY.md`,
`tests/test_api_startup_security.py`,
`tests/test_meilisearch_key_security.py`, and
`tests/test_docker_build_contracts.py`, and
`tests/test_run_soak_day_contract.py`, and
`tests/test_startup_purge_gating.py`.

No other tracked file may change.
**d) Decision-gate check.** T-SEC-3 does not depend on or foreclose G1-G5.
G1's reachable default requires this hardening. G3 still blocks removal of
`MEILI_MASTER_KEY` facade re-exports, so this task leaves them intact while
ensuring reader containers do not receive the deployed master credential.

## 2. Design

**e) Step-by-step approach.**

1. Register this Full plan, corrected ownership, and implementation-ready
   status before behavior changes.
2. Add failing tests for reader-key selection, production refusal, Compose role
   separation, and documentation contracts.
3. Add `pipeline/meilisearch_credentials.py` as the single policy owner. Its
   only function validates and selects a reader credential from `APP_ENV` and
   `MEILI_SEARCH_KEY`; a named constant owns the fake development key. It
   performs no environment reads, logging, client creation, or network work and
   never imports API or semantic modules.
4. Update API and semantic client construction to pass the selected reader key
   to the existing Meilisearch SDK client. Preserve raw valid keys. Until G3,
   the existing API `MEILI_MASTER_KEY` facade export remains but contains the
   resolved reader key and never reads the deployed master environment value.
5. Validate the reader credential when each reader module selects its
   import-time client configuration. Outside development, reject missing,
   blank, development-fallback, or transport-unsafe reader keys before serving
   requests. Use the API lifespan and a new semantic-service lifespan only to
   emit a value-free warning when development uses the fake-key fallback.
6. Update Compose:
   - API and semantic receive `MEILI_SEARCH_KEY` and no deployed master key.
   - Base Meilisearch runs in production mode with a required master key; only
     the development overlay selects development mode.
   - Base reader services use image code and cannot read a repository-mounted
     `.env`; the development overlay mounts only required source directories.
   - Semantic also receives `APP_ENV`.
   - Pipeline and pipeline-batch receive `MEILI_HOST` and `MEILI_MASTER_KEY`
     because both execute indexing paths.
   - Existing worker, enrichment-worker, and Meilisearch master-key wiring
     remains unchanged.
7. Exclude local `.env` variants from the Docker build context while retaining
   `.env.example`. Add the environment example and concise README pointer. Put
   create, verify, rotate, revoke, and rollback commands in
   `docs/OPERATIONS.md`; reader deployment rebuilds images before recreation.
8. Keep local startup commands on the base-plus-development Compose stack,
   including model bootstrap and opt-in runtime profile examples, so starting
   support services cannot silently restore production-mode Meilisearch. Base
   reader services default to non-development; the overlay explicitly marks
   API and semantic as development. Soak self-recovery and active local
   inference/A-B runbook commands use the same overlay. Soak recovery overrides
   the existing purge setting to `false` so recovery cannot invalidate the
   measurement corpus.
9. Exclude every `.env.*` variant from the frontend's independent Docker build
   context; the root ignore file does not govern that context.
10. Run a disposable, volume-free smoke against pinned Meilisearch v1.6. Seed
   `documents`, create a short-lived scoped reader key, verify search and index
   statistics succeed while document writes, settings changes, and key
   creation return 403, then revoke the key and remove the container.
11. Run full local verification, simplification, independent pre-commit review,
   atomic commits, PR review, current-head CI, and merge.

The shared credential module is justified because two independently deployed
reader services enforce the same security policy. Duplicating the policy in
both services would create a convention-synchronized implementation.

**f) Reuse audit.** Reuse `pipeline/config_env.py` environment helpers, current
Meilisearch client constructors, existing FastAPI lifespan boundaries, Compose
configuration parsing, and subprocess test patterns. Do not add a config
registry, client factory, retry path, compatibility alias, or second fallback
implementation. Legacy API facade re-exports remain deferred to Phase 2.

**g) Data contracts.**

- `MEILI_SEARCH_KEY` is the reader credential for API and semantic services.
  Its deployed permissions are `search` and `stats.get` on `documents`.
- `MEILI_MASTER_KEY` remains the writer/admin credential.
- Development may use the fake master fallback when no search key is set.
- In the development overlay, a missing search key follows the configured
  local master so existing customized local environments remain usable.
- Non-development startup fails if the search key is missing, blank, equal to
  the development fallback, or transport-unsafe.
- A rejected search request never retries with the master key.
- A distinct master sentinel never reaches a reader client or legacy export.
- API and semantic clients require restart after key rotation because they are
  created during module import under the existing architecture.

No public API, Celery signature, database contract, or inference default
changes.
**h) Schema/migration impact.** None.

## 3. Security & Data Governance

**i) Security-sensitive path.** `docker-compose.yml` controls the API and
semantic-to-Meilisearch trust boundary. Before this change, compromise of a
reader container reveals an administrative credential. Afterward, reader
containers receive no master variable, and deployment requires permission
preflight of the candidate reader key. Writer services retain the master key.
This implements `SECURITY.md` trust-boundary control T-SEC-3.

**j) Secrets.** One new environment variable, `MEILI_SEARCH_KEY`, carries a
server-side secret. It has no working non-development default and is never
exposed through `NEXT_PUBLIC_*`, logs, test output, or committed files.

**k) Person data.** No person-level data is created, linked, aggregated, or
exposed. G4 is unaffected.

**l) Untrusted input.** No scraped or browser input parsing changes. The
Meilisearch key is untrusted environment input and is validated before reader
services accept requests.

## 4. Code Health

**m) GED conformance sweep.** The new policy function has two parameters, one
responsibility, complete type annotations, no nested branching beyond two
levels, and named constants for environment and error policy. No broad
exception, timestamp, retry, or silent fallback is added.

**n) Antipattern scan, plan pass.**

- A1/H1: Context7 verified `POST /keys`, `GET /keys/{uid}`, master
  authentication, action/index scoping, nullable `expiresAt`, and response
  `key`/`uid` fields. The repository
  pins server v1.6 and Python SDK 0.31.0; a live v1.6 smoke remains required
  because Context7 is not version-pinned.
- B1/F1: one side-effect-free policy module replaces two otherwise duplicated
  reader implementations; no factory or registry is added.
- B2/C1/C2: no compatibility alias or facade patch seam is added. Existing
  facades remain only because G3 forbids their removal in this phase.
- B3: validation covers concrete deployment failures and HTTP header transport.
- D1-D3: tests assert outbound authorization behavior, startup outcomes,
  Compose role separation, and live permissions.
- E1-E3: only owned files and named documentation sections change.
- A2-A4, F2, H2-H4: no violations planned. Existing import-time client
  creation remains but is not expanded with network work.

**o) Ratchet interaction.** No Ruff selector, BLE001 boundary, formatter scope,
Mypy scope, coverage threshold, or test tolerance changes.

**p) Dead code and duplication audit.** The API and semantic master-key client
selection is replaced by one shared reader policy. No facade symbol is removed
before G3. Expected production delta is one small policy module plus startup
validation; Compose gains role-correct credential entries.

## 5. Testing

**q) Edge and failure scenarios.**

1. Search key present: API and semantic clients use it, never the master key.
2. Search key missing or blank in development: fake master fallback works and
   emits a value-free warning.
3. Search key missing, blank, or equal to the development fallback outside
   development: startup fails.
4. Search key contains non-ASCII, control, or edge-whitespace characters:
   startup fails before serving requests.
5. Search key is invalid, expired, or unauthorized: one request fails without
   a second request or master-key retry.
6. API and semantic Compose services receive only the reader key, and semantic
   receives `APP_ENV`.
7. Base reader containers cannot read a repository-mounted `.env`, local
   environment files are absent from image build context, and development
   readers mount only required source directories rather than the repository
   root.
8. Pipeline writer services receive host and master key.
9. Existing worker and indexer writer paths retain master-key access.
10. Base Meilisearch uses production mode and refuses a missing or invalid
    master key; the development overlay alone selects development mode.
11. The disposable live key can search and read statistics for `documents` but
    cannot write documents, change settings, or manage keys.
12. Key rotation requires reader-service restart; revocation occurs only after
    the replacement key passes health and search checks.
13. Permission preflight rejects a candidate whose UID, key, actions, or index
    scope differs from the exact generated scoped-reader record.

**r) Tests.**

| Test | Scenarios |
|---|---|
| Reader policy unit tests | 2-4 |
| Isolated API and semantic client-selection/sentinel tests | 1 |
| API and semantic startup tests | 2-4 |
| One-request HTTP boundary test | 5 |
| Compose credential-role contract | 6-10 |
| Docker build-context contract | 7 |
| Environment/docs contract | 6, 12, 13 |
| Isolated Meilisearch v1.6 smoke | 1, 5, 10-13 |
| Existing API, semantic, and indexer suites | Regression coverage |

Tests are written and run red before runtime or Compose edits.

**s) Fakes and mocks.** Client tests use isolated subprocesses and the approved
Meilisearch construction boundary. A local fake HTTP server records the
authorization header and request count for scenario 5. Startup tests use
FastAPI `TestClient` and implementation modules. No facade is patched.

**t) Verification rows.** Apply security-sensitive trust-boundary reporting,
API/search, docs, Docker contract, semantic-service, and broad cross-cutting
verification. Run the complete Python suite and authoritative PR gates.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-sec-3-scoped-meilisearch-key

PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_meilisearch_key_security.py \
  tests/test_api_startup_security.py \
  tests/test_docker_build_contracts.py

docker compose --profile batch-tools config --quiet

./.venv/bin/ruff check .
./.venv/bin/pre-commit run ruff --all-files
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_meilisearch_key_security.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_api_startup_security.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_api.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_query_builder_filters.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_query_builder_parity_search_vs_trends.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_semantic_service_api.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_search_pgvector_hybrid_rerank.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_semantic_recall_filters.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_indexer_logic.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docker_build_contracts.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_env_example_profile_alignment.py
PYTHONPATH=. .venv/bin/python -m pytest -q tests/
git diff --check
```

Isolated server-v1.6 permission smoke:

```bash
(
set -euo pipefail
MASTER_KEY=$(openssl rand -hex 24)
bounded_curl() { command curl --connect-timeout 2 --max-time 10 "$@"; }
umask 077
MEILI_ENV_FILE=$(mktemp)
MASTER_HEADER_FILE=$(mktemp)
SEARCH_HEADER_FILE=$(mktemp)
printf 'MEILI_ENV=production\nMEILI_MASTER_KEY=%s\n' "$MASTER_KEY" >"$MEILI_ENV_FILE"
printf 'Authorization: Bearer %s\n' "$MASTER_KEY" >"$MASTER_HEADER_FILE"
CID=$(docker run --rm -d --env-file "$MEILI_ENV_FILE" \
  -p 127.0.0.1::7700 getmeili/meilisearch:v1.6)
KEY_UID=
cleanup() {
  test -z "$KEY_UID" || bounded_curl -fsS -X DELETE "$MEILI_URL/keys/$KEY_UID" \
    -H "@$MASTER_HEADER_FILE" >/dev/null || true
  docker rm -f "$CID" >/dev/null 2>&1 || true
  rm -f "$MEILI_ENV_FILE" "$MASTER_HEADER_FILE" "$SEARCH_HEADER_FILE"
}
# Container removal destroys the volume-free instance even if revocation fails.
trap cleanup EXIT
PORT=$(docker port "$CID" 7700/tcp | sed 's/.*://')
MEILI_URL="http://127.0.0.1:$PORT"
for _ in {1..60}; do bounded_curl -fsS "$MEILI_URL/health" >/dev/null && break; sleep 1; done
bounded_curl -fsS "$MEILI_URL/health" >/dev/null
VERSION=$(bounded_curl -fsS "$MEILI_URL/version" -H "@$MASTER_HEADER_FILE" |
  .venv/bin/python -c 'import json,sys; print(json.load(sys.stdin)["pkgVersion"])')
case "$VERSION" in 1.6.*) ;; *) exit 1 ;; esac

# Seed documents and wait for the asynchronous task before testing search.
TASK_UID=$(bounded_curl -fsS -X POST "$MEILI_URL/indexes/documents/documents?primaryKey=id" \
  -H "@$MASTER_HEADER_FILE" -H "Content-Type: application/json" \
  --data-binary '[{"id":"t-sec-3","title":"permission probe"}]' |
  .venv/bin/python -c 'import json,sys; print(json.load(sys.stdin)["taskUid"])')
for _ in {1..60}; do
  TASK_STATUS=$(bounded_curl -fsS "$MEILI_URL/tasks/$TASK_UID" \
    -H "@$MASTER_HEADER_FILE" | .venv/bin/python -c \
    'import json,sys; print(json.load(sys.stdin)["status"])')
  case "$TASK_STATUS" in succeeded) break ;; failed|canceled) exit 1 ;; esac
  sleep 1
done
test "$TASK_STATUS" = succeeded

EXPIRES_AT=$(.venv/bin/python -c \
  'from datetime import UTC,datetime,timedelta; print((datetime.now(UTC)+timedelta(minutes=15)).isoformat())')
KEY_JSON=$(bounded_curl -fsS -X POST "$MEILI_URL/keys" \
  -H "@$MASTER_HEADER_FILE" -H "Content-Type: application/json" \
  --data-binary "{\"name\":\"T-SEC-3 probe\",\"actions\":[\"search\",\"stats.get\"],\"indexes\":[\"documents\"],\"expiresAt\":\"$EXPIRES_AT\"}")
MEILI_SEARCH_KEY=$(printf '%s' "$KEY_JSON" | .venv/bin/python -c \
  'import json,sys; print(json.load(sys.stdin)["key"])')
KEY_UID=$(printf '%s' "$KEY_JSON" | .venv/bin/python -c \
  'import json,sys; print(json.load(sys.stdin)["uid"])')
printf 'Authorization: Bearer %s\n' "$MEILI_SEARCH_KEY" >"$SEARCH_HEADER_FILE"
bounded_curl -fsS -X POST "$MEILI_URL/indexes/documents/search" \
  -H "@$SEARCH_HEADER_FILE" -H "Content-Type: application/json" \
  --data-binary '{"q":"permission"}' >/dev/null
bounded_curl -fsS "$MEILI_URL/indexes/documents/stats" \
  -H "@$SEARCH_HEADER_FILE" >/dev/null
test "$(bounded_curl -sS -o /dev/null -w '%{http_code}' -X POST \
  "$MEILI_URL/indexes/documents/documents" -H "@$SEARCH_HEADER_FILE" \
  -H "Content-Type: application/json" --data-binary '[{"id":"denied"}]')" = 403
test "$(bounded_curl -sS -o /dev/null -w '%{http_code}' -X PATCH \
  "$MEILI_URL/indexes/documents/settings" -H "@$SEARCH_HEADER_FILE" \
  -H "Content-Type: application/json" --data-binary '{"displayedAttributes":["id"]}')" = 403
test "$(bounded_curl -sS -o /dev/null -w '%{http_code}' -X POST \
  "$MEILI_URL/keys" -H "@$SEARCH_HEADER_FILE" -H "Content-Type: application/json" \
  --data-binary '{"actions":["search"],"indexes":["*"],"expiresAt":null}')" = 403
)
```

Preflight the actual reader key before restarting API or semantic:

```bash
(
set -euo pipefail
bounded_curl() { command curl --connect-timeout 2 --max-time 10 "$@"; }
: "${MEILI_URL:?set the deployed Meilisearch URL}"
: "${MEILI_MASTER_KEY:?set the deployed master key for operator preflight}"
: "${MEILI_SEARCH_KEY:?set the candidate reader key}"
: "${MEILI_SEARCH_KEY_UID:?set the candidate reader key UID}"
umask 077
MASTER_HEADER_FILE=$(mktemp)
SEARCH_HEADER_FILE=$(mktemp)
trap 'rm -f "$MASTER_HEADER_FILE" "$SEARCH_HEADER_FILE"' EXIT
printf 'Authorization: Bearer %s\n' "$MEILI_MASTER_KEY" >"$MASTER_HEADER_FILE"
printf 'Authorization: Bearer %s\n' "$MEILI_SEARCH_KEY" >"$SEARCH_HEADER_FILE"
KEY_RECORD=$(bounded_curl -fsS "$MEILI_URL/keys/$MEILI_SEARCH_KEY_UID" \
  -H "@$MASTER_HEADER_FILE")
printf '%s' "$KEY_RECORD" | .venv/bin/python -c \
  'import json,sys; from pathlib import Path; r=json.load(sys.stdin); expected=Path(sys.argv[1]).read_text().removeprefix("Authorization: Bearer ").strip(); assert r["uid"] == sys.argv[2] and r["key"] == expected and r["actions"] == ["search","stats.get"] and r["indexes"] == ["documents"]' \
  "$SEARCH_HEADER_FILE" "$MEILI_SEARCH_KEY_UID"
bounded_curl -fsS -X POST "$MEILI_URL/indexes/documents/search" \
  -H "@$SEARCH_HEADER_FILE" -H "Content-Type: application/json" \
  --data-binary '{"q":"","limit":1}' >/dev/null
bounded_curl -fsS "$MEILI_URL/indexes/documents/stats" \
  -H "@$SEARCH_HEADER_FILE" >/dev/null
test "$(bounded_curl -sS -o /dev/null -w '%{http_code}' \
  "$MEILI_URL/indexes/documents/settings" -H "@$SEARCH_HEADER_FILE")" = 403
test "$(bounded_curl -sS -o /dev/null -w '%{http_code}' \
  "$MEILI_URL/keys" -H "@$SEARCH_HEADER_FILE")" = 403
)
```

**v) Rollback.** Revert the T-SEC-3 merge commit. Restore reader containers to
their previous environment, recreate API and semantic services, and verify
health/search before revoking any deployed scoped key. If a disposable key
remains, delete it by captured UID through `DELETE /keys/{uid}` using the
master key. Rerun Compose validation, targeted tests, Ruff, Mypy, docs links,
and the complete suite. No database or index data remediation is required.

**w) Docs synchronization.**

- `README.md`: concise reader-key requirement and operations link.
- `env/profiles/README.md`: development-overlay and layered environment
  commands for opt-in profiles.
- `docs/OPERATIONS.md`: create, deploy, verify, rotate, revoke, and rollback.
- `SECURITY.md`: reader boundary and T-SEC-3 checklist.
- Remediation registry and this Full plan.
- ADR, architecture, roadmap, testing policy, data governance, and OpenAPI:
  no changes.

## 7. Delivery Self-Audit

**x) Diff scan.** Re-run A-F/H. Reject master-key exposure to reader
containers, non-development fallback, master retry, duplicate policy, facade
cleanup, secret-bearing logs, unrelated Compose edits, invented Meilisearch
fields, weakened tests, or files outside ownership.

**y) Evidence required.** Report tests-first red output, every command in 6u,
live v1.6 permission results, local environment versions, independent planning
and pre-commit reviews, commit hashes, PR URL, unresolved-thread count,
current-head review, and final CI. Anything unrun is `NOT VERIFIED`.

**z) Deviations.** Authorized corrections to the original registry task are
semantic-reader coverage, non-development fail-fast behavior, a shared policy
module, writer-service credential injection, tests, operations documentation,
and expanded ownership. Any other file, facade removal before G3, permission
expansion, skipped review, unresolved P1/P2, or unrun required check is a
blocker.
