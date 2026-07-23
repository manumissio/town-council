# T-SEC-1: Restrict Backing-Service Host Ports

artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
execution: code
task: T-SEC-1
lane: SEC

## 1. Context & Alignment

**a) Driver.** The base Compose file publishes PostgreSQL, Redis,
Meilisearch, Prometheus, and Grafana on every host interface while those
services use development credentials or expose operational data. This lets a
network peer bypass the API boundary and reach internal services directly.
T-SEC-1 must make the base stack expose only the API and frontend while
preserving explicit, loopback-only operator access through the existing
development overlay.

**b) Canonical documents.** `AGENTS.md` `<hard_invariants>`,
`<security_sensitive_paths>`, `<workflow_contract>`,
`<verification_matrix>`, and `<docs_sync_rules>` require a trust-boundary
statement, local-first behavior, exact verification, and synchronized
commands. `SECURITY.md` "Deployment posture", "Trust boundaries", and
"Hardening checklist" require backing stores to remain on the Compose network
in the base stack. `docs/TESTING.MD` requires observable contract tests.
`docs/OPERATIONS.md` and `README.md` currently advertise host URLs that will
require the development overlay after this change. The remediation plan places
T-SEC-1 at the start of the Phase 1 security lane. The architecture review
confirms Phase 1 security work may proceed while G3 blocks Phase 2.

**c) Remediation alignment.** Expand T-SEC-1 ownership before implementation
to exactly:

- `docs/plans/T_SEC_1_BACKEND_PORT_HARDENING_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `docker-compose.yml`
- `docker-compose.dev.yml`
- `.env.example`
- `tests/test_docker_build_contracts.py`
- `README.md`
- `docs/OPERATIONS.md`
- `SECURITY.md`

The remediation plan also records T-CI-3 as complete in PR #118. No other
tracked file may change. In particular, `scripts/dev_up.sh` remains unchanged
because loading the development overlay there would also enable
`STARTUP_PURGE_DERIVED=true`.

**d) Decision gates.** No G1-G5 decision blocks this task. G1 remains formally
open, but `SECURITY.md` and the remediation plan explicitly use the reachable
posture as the hardening assumption. G2 is unrelated to backing-service
publication. G3 continues to block Phase 2 only.

## 2. Design

**e) Approach.**

1. Register the expanded ownership and this Full plan before implementation.
2. Reproduce the current exposure with
   `docker compose -f docker-compose.yml config --format json`: seven services
   publish ports, including five internal or administrative services.
3. Add failing tests before changing Compose or documentation. The tests
   render Docker Compose JSON and require:
   - the base project to publish only `api:8000` and `frontend:3000`;
   - the merged development project to publish exact loopback mappings for
     PostgreSQL, Redis, Meilisearch, Prometheus, and Grafana;
   - the base and merged dependency graphs to remain identical;
   - neither project to use host network mode;
   - the checked-in Grafana credentials must be labeled local-development
     defaults that are unsafe for reachable deployments.
4. Remove the five internal or administrative `ports` blocks from
   `docker-compose.yml`. Add a top-level intent comment explaining that
   inter-container traffic uses the Compose network and host bindings belong
   in the explicit development overlay.
5. Add the five mappings to `docker-compose.dev.yml` with
   `127.0.0.1:HOST:CONTAINER`. This deliberately restores local operator
   access rather than the old all-interface exposure.
6. Keep the existing API `8000` and frontend `3000` mappings unchanged. Do
   not add `expose`, networks, profiles, or service changes because Compose
   service-name routing already provides internal access.
7. Clarify the `.env.example` Grafana comment without changing any value.
8. Update README access guidance and the operations observability check with
   an exact service-scoped command:

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d \
     postgres redis meilisearch prometheus grafana
   ```

   The service list prevents this access-only command from starting the
   purge-enabled API, worker, or pipeline definitions in the same overlay.
   State that using the overlay for the full stack also enables development
   startup purge behavior.
9. Mark the T-SEC-1 checklist item complete in `SECURITY.md`; leave all other
   security tasks and the G1 blank unchanged.
10. Validate both rendered configurations, run all applicable tests, simplify
    the diff, obtain a fresh independent pre-commit review, and deliver one
    planning commit plus one implementation commit.

No new production function or module is introduced. The only new test helper
renders one effective Compose project as JSON. It does not start containers or
require a Docker daemon connection.

**f) Reuse audit.** Reuse the existing Compose base/overlay model,
`tests/test_docker_build_contracts.py`, Docker Compose CLI, and canonical
security/runbook sections. No new overlay, parser framework, network
abstraction, helper script, compatibility path, or duplicate port inventory is
added. The old all-interface backing-service publication is removed in the
same change.

Rejected alternatives:

- Leave Prometheus in the base file: rejected because the acceptance contract
  and security checklist require only API and frontend host publication.
- Restore development mappings without a host address: rejected because it
  recreates the network blast radius that T-SEC-1 removes.
- Make `scripts/dev_up.sh` load the overlay: rejected because the same overlay
  also enables derived-data startup purge and would change the standard helper
  beyond this security task.
- Add `expose` for internal ports: rejected because Compose networking already
  permits service-to-service traffic and `expose` would add redundant config.

**g) Contracts.**

- Base host-publication contract:
  `{"api": ["8000:8000"], "frontend": ["3000:3000"]}`.
- Development overlay contract:
  - PostgreSQL `127.0.0.1:5432:5432`
  - Redis `127.0.0.1:6379:6379`
  - Meilisearch `127.0.0.1:7700:7700`
  - Prometheus `127.0.0.1:9090:9090`
  - Grafana `127.0.0.1:3001:3000`
- Service names, container ports, credentials, images, volumes, dependencies,
  health checks, API contracts, and runtime defaults remain unchanged.

The tests invoke `docker compose config --format json`, which is the semantic
authority for interpolation and multi-file merging. The test environment must
provide the Docker Compose CLI, but no daemon or running container is needed.

**h) Schema and migrations.** None. Named volumes and stored data are
unchanged.

## 3. Security & Data Governance

**i) Security boundary.** This task touches `docker-compose.yml` and
`docker-compose.dev.yml`, which are security-sensitive. Before the change,
network peers can directly reach services protected only by development
credentials or no authentication. After the change, base-stack peers can reach
only the API and frontend host interfaces; backing and monitoring services
remain reachable by containers on the Compose network. The explicit
development overlay grants only loopback access. This implements
`SECURITY.md` trust boundary 3 and hardening checklist item T-SEC-1.

**j) Secrets.** No credential, key, value, environment variable, or fallback
changes. The `.env.example` edit only labels existing Grafana values as
local-development defaults. T-SEC-2 and T-SEC-3 retain ownership of API-key
and Meilisearch-key policy.

**k) Person data.** No person-level data is created, linked, aggregated, or
exposed. G4 is unaffected.

**l) Untrusted input.** No scraped content or user input is parsed. Tests parse
tracked repository YAML. Docker Compose environment interpolation remains
unchanged.

## 4. Code Health

**m) GED conformance sweep.** No Python production logic, error handler,
timestamp, environment read, function signature, or nested control flow
changes. Port literals are policy values and remain centralized in the two
Compose files. Test names use service and publication vocabulary. No exception
is required.

**n) Antipattern scan, plan pass.**

- A1/H1: Docker Compose multi-file merge, `config --quiet`, and
  `config --format json` behavior were verified against `/docker/compose` and
  local Compose 5.2.0.
- B1/F1: no new config framework, parser package, helper script, or duplicate
  overlay.
- B2/C1: no compatibility path; superseded base port mappings are deleted.
- B3: no redundant `expose` declarations or new validation in production.
- D1-D3: tests assert the checked-in security contract and rendered behavior;
  no skip, xfail, tolerance, or implementation mock.
- E1-E3: only the nine owned files may change; the historical architecture
  review remains untouched.
- A2-A4, C2, F2, H2-H4: no violations planned.

**o) Ratchet interaction.** No Ruff selector, BLE001 boundary, formatter
scope, Mypy scope, coverage threshold, or soak gate changes.

**p) Dead code and duplication audit.** Delete five base `ports` blocks.
Re-home those five mappings once in the development overlay. Reuse current
service definitions and docs sections. Expected net config delta is small;
documentation and tests account for most added lines.

## 5. Testing

**q) Edge and failure scenarios.**

1. A backing or monitoring service regains a base host mapping.
2. API or frontend publication is accidentally removed or changed.
3. Development overlay omits one required operator mapping.
4. Development overlay binds an internal service to all interfaces.
5. Prometheus is missed because the old work list named only four services.
6. Compose merge or interpolation becomes invalid.
7. Container-to-container dependencies change.
8. Operator docs advertise unavailable URLs without the overlay command.
9. Existing dev credentials are mistaken for reachable-deployment values.
10. Existing running containers retain old published bindings until recreated.
11. Loading the overlay unexpectedly remains undocumented as also enabling
    startup purge.
12. A service bypasses port policy through `network_mode: host`.
13. Compose merging changes a service dependency.

**r) Test mapping.**

| Test or verification | Scenarios |
|---|---|
| `test_base_compose_publishes_only_application_interfaces` | 1, 2, 5, 12 |
| `test_dev_overlay_publishes_operator_services_on_loopback_only` | 3, 4, 5, 12, 13 |
| `test_example_grafana_credentials_are_labeled_local_only` | 9 |
| `test_operator_docs_scope_dev_overlay_to_port_services` | 8, 11 |
| Existing startup-purge contract | 11 |
| Base and merged `docker compose config --quiet` | 6 |
| Docs-link test plus semantic doc review | 8, 10, 11 |
| Complete Python suite | Regression check |

The four new contracts are written and run red before Compose, env, or docs
implementation changes.

**s) Fakes and mocks.** None. Tests use the approved filesystem and subprocess
boundaries. Docker Compose renders configuration directly; no facade,
environment, Docker daemon, or production implementation is mocked.

**t) Verification rows.** Apply the security-sensitive Compose trust-boundary
report, Docker contract tests, docs-only row, Ruff because Python tests change,
and the complete Python suite for this cross-cutting infrastructure change.
Docker Compose rendering is an additional mandatory acceptance check.

## 6. Execution, Rollback, Docs

**u) Commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-sec-1-backend-port-hardening
```

Current exposure:

```bash
docker compose -f docker-compose.yml config --format json |
  .venv/bin/python -c \
  'import json,sys; services=json.load(sys.stdin)["services"]; print({name: service["ports"] for name, service in services.items() if service.get("ports")})'
```

Tests-first red evidence:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_docker_build_contracts.py::test_base_compose_publishes_only_application_interfaces \
  tests/test_docker_build_contracts.py::test_dev_overlay_publishes_operator_services_on_loopback_only \
  tests/test_docker_build_contracts.py::test_example_grafana_credentials_are_labeled_local_only \
  tests/test_docker_build_contracts.py::test_operator_docs_scope_dev_overlay_to_port_services
```

Final verification:

```bash
docker compose -f docker-compose.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.dev.yml config --quiet
docker compose -f docker-compose.yml config --format json |
  .venv/bin/python -c \
  'import json,sys; services=json.load(sys.stdin)["services"]; print({name: service["ports"] for name, service in services.items() if service.get("ports")})'
docker compose -f docker-compose.yml -f docker-compose.dev.yml config --format json |
  .venv/bin/python -c \
  'import json,sys; services=json.load(sys.stdin)["services"]; print({name: service["ports"] for name, service in services.items() if service.get("ports")})'
./.venv/bin/ruff check .
PYTHONPATH=. .venv/bin/pytest -q tests/test_docker_build_contracts.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_startup_purge_gating.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/python -m pytest -q tests/
git diff --check
git status --short
```

After merge, recreate affected services so old bindings do not survive in
running containers:

```bash
docker compose -f docker-compose.yml up -d --force-recreate \
  postgres redis meilisearch prometheus grafana
```

**v) Rollback.** Revert the T-SEC-1 merge commit, validate both Compose
configurations, and recreate the five affected services with the restored base
file:

```bash
docker compose -f docker-compose.yml up -d --force-recreate \
  postgres redis meilisearch prometheus grafana
```

Named volumes preserve PostgreSQL, Redis, Meilisearch, Prometheus, and Grafana
data. No migration or data remediation is required.

**w) Docs synchronization.**

- `README.md` "Access URLs": distinguish base URLs from explicit
  development-overlay URLs and show the exact service-scoped command.
- `docs/OPERATIONS.md` "Start stack" and "Observability quick checks": explain
  opt-in loopback bindings, startup-purge interaction, and service recreation;
  update `Last updated`.
- `SECURITY.md` "Hardening checklist": mark T-SEC-1 complete.
- `.env.example`: label Grafana defaults as local-development only.
- Remediation registry: version 2.4, T-CI-3 completion, T-SEC-1 ownership and
  clarified acceptance.
- `AGENTS.md`, testing/guardrail policy, ADR, architecture review, API docs,
  and data-governance docs: no change.

## 7. Delivery Self-Audit

**x) Diff scan.** Re-run A-F/H. Reject any all-interface backing-service
mapping, new port, changed credential, `expose` declaration, service/dependency
change, automatic `dev_up.sh` overlay loading, unrelated formatting, weakened
test, historical-review edit, or changed gate/default policy.

**y) Evidence required.** Report the tests-first red result, both Compose
validation results, exact rendered base and merged port inventories, Ruff,
targeted contract tests, startup-purge tests, docs links, complete-suite
counts, independent planning and pre-commit review findings, commit hashes, PR
URL, unresolved-thread count, and final CI state. Mark anything unrun as
`NOT VERIFIED`.

**z) Deviations.** Authorized corrections are adding Prometheus to the move,
using loopback-only development bindings rather than all-interface mappings,
expanding ownership to nine files, and synchronizing the stale T-CI-3 status.
The operator additionally directed the remediation changelog to become a
versioned list and requested a scannable task-status summary.
Any additional path, changed service behavior, credential/default change,
unresolved P1/P2, skipped review, or unrun required check is a blocker.
