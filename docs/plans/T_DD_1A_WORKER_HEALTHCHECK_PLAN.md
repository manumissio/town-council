# T-DD-1A: Consolidate Worker Health Probes

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: implementation-ready`
`execution: code`

## 1. Context & Alignment

**a) Driver.** Town Council has three worker healthcheck CLIs, not the two
described by the older remediation task. All three aggregate failures and
probe Redis/PostgreSQL connectivity, while each owns different runtime checks.
The architecture review recommends a deeper shared health-probe module and
stable CLI entrypoints. T-DD-1A isolates that proven overlap from the disputed
city-state mutation overlap in T-DD-1B.

**b) Canonical documents consulted.**

- `AGENTS.md`: preserve CLI/runtime behavior, use approved test boundaries,
  avoid compatibility seams, and run applicable script and full-suite checks.
- `docs/TESTING.MD`: use approved outbound HTTP and filesystem boundaries;
  use real loopback sockets and real role containers instead of inventing
  socket, subprocess, environment, or dependency-import fakes.
- `docs/ENGINEERING_GUARDRAILS.md`: Ruff config owns BLE001 boundaries and
  repository scope.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`: DEDUP-D owns the three
  healthcheck scripts and their tests; task-level ownership must be exact.
- `docs/reviews/architecture-review-2026-07-19.html`, Candidate 05: separate
  health probing from city mutation; keep CLI names stable and test parity.
- `SECURITY.md` and `docs/DATA_GOVERNANCE.md`: no affected security or person
  data boundary.

**c) Remediation alignment.** T-DD-1 becomes two ordered tasks. T-DD-1A owns
exactly:

- `docs/plans/T_DD_1A_WORKER_HEALTHCHECK_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `scripts/worker_health_probes.py` (new)
- `scripts/worker_healthcheck.py`
- `scripts/enrichment_worker_healthcheck.py`
- `scripts/semantic_worker_healthcheck.py`
- `tests/test_worker_health_probes.py` (new)
- `tests/test_worker_healthcheck.py`
- `tests/test_docker_health_contracts.py`

T-DD-1B retains the two city-state scripts and their focused tests. The two
tasks must not run concurrently with each other because they share the ledger.

**d) Decision-gate check.** No G1-G5 decision is required or foreclosed.
Runtime defaults, service topology, model policy, task registration, and soak
comparability remain unchanged.

## 2. Design

**e) Step-by-step approach.**

1. Register T-DD-1A and T-DD-1B in the remediation ledger before production
   edits.
2. Add characterization tests first for shared TCP targeting, failure
   aggregation/reporting, primary-worker probes, import direction, and
   unchanged Compose entrypoints.
3. Record red evidence that enrichment and semantic CLIs import private
   helpers from `worker_healthcheck.py` and duplicate network/report blocks.
4. Add `scripts/worker_health_probes.py` as the single owner of:
   - URL-to-socket target parsing;
   - TCP connection probing;
   - Redis/PostgreSQL probe aggregation from targets resolved by each CLI;
   - printing all collected failures and returning the CLI exit code.
5. Have all three CLIs import the module, not copied symbols. This keeps tests
   on the implementation owner and avoids bound-name patch seams.
6. Keep all environment reads and role policy in each CLI, including the
   primary worker's `REDIS_HOST` fallback.
7. Keep primary-worker metrics and inference HTTP/model probes in
   `worker_healthcheck.py`.
8. Keep enrichment task registration and `sklearn`/`spacy`/`pytextrank`
   subprocess checks in `enrichment_worker_healthcheck.py`.
9. Keep semantic runtime imports, task registration, and artifact-directory
   write checks in `semantic_worker_healthcheck.py`.
10. Preserve broad exception handling only in the two existing role CLI
   boundaries. Do not move broad handlers into the shared module or widen
   Ruff.
11. Preserve malformed numeric configuration as fail-fast, and preserve probe
    order, timeout values, labels, and sequential execution. Compose's existing
    ten-second timeout tension is a separate operational issue.
12. Run targeted, static, docs-link, and complete-suite verification; perform
    simplification and independent pre-commit review; apply eligible findings.
13. Commit authorization and implementation separately, push one branch, open
    one PR, request review, and watch required checks to a decided state.

Existing primary-worker tests that monkeypatch `_probe_tcp` and
`_probe_http_model` are replaced with real loopback sockets and the approved
outbound HTTP boundary. The refactor must not preserve those private patch
targets.

Each shared function has one responsibility. `worker_health_probes.py` imports
only the standard library and never imports a CLI module.

**f) Reuse audit.** Move the existing URL parser and TCP probe from
`worker_healthcheck.py`; extend the existing aggregate-and-print behavior.
There is no current shared owner beyond private imports from the primary CLI,
so a focused module is justified. The old private imports and duplicated
blocks are deleted in the same PR.

Rejected alternatives:

- Keep importing primary-worker private helpers: preserves a CLI as a shallow
  facade and leaves reporting/network behavior split across three owners.
- Extract all role checks: creates a generic registry/manager and weakens
  domain ownership.
- Combine three CLIs: breaks Compose entrypoints and role-specific images.
- Include city-state scripts: mixes a disputed data-mutation invariant with
  proven health-probe duplication.

**g) Data contracts.** Shared functions use typed tuples and `list[str]`, the
family's existing convention. No external payload or new dataclass is needed.
The observable contract remains: print every failure to stderr, return `1` if
any probe fails, otherwise return `0`.

**h) Schema/migration impact.** None.

## 3. Security & Data Governance

**i) Security-sensitive paths.** None. Compose is verified but not edited.
Socket and local HTTP probes retain their current targets, timeouts, and
privileges. An attacker gains no new endpoint or capability.

**j) Secrets.** No credential, environment variable, key, or default is added.
Connection URLs remain read by the CLIs and are not printed.

**k) Person data.** No person-level data is created, linked, aggregated, or
exposed. G4 is unaffected.

**l) Untrusted input.** Environment URLs and provider JSON retain their current
parsing boundaries. The shared module parses only URL host/port values and
reports connection failures without echoing credentials.

## 4. Code Health

**m) GED conformance sweep.** New and modified functions have complete type
annotations, one responsibility, at most three parameters, and no nested
branching beyond two levels. Existing timeout/port values move with their
probe behavior or remain named constants. No timestamp or new environment read
is introduced. Shared handlers catch specific socket failures; broad role
boundary handlers still aggregate failures so all probes run before exit.

**n) Antipattern scan, plan pass.**

- A1/H1: `socket.create_connection`, `urlparse`, `subprocess.run`, and
  `NamedTemporaryFile` calls are unchanged and verified against installed
  Python 3.14 behavior.
- B1/F1: one focused probe module replaces duplicated code; no manager,
  registry, base class, or `utils` module.
- B2/C1: no compatibility re-export; private CLI imports are removed.
- C2/D2: tests patch implementation dependency boundaries, not facade aliases
  or the unit under test.
- D1/D3: characterization preserves outputs and role checks without skips,
  weaker assertions, or call-count contracts.
- E1/E2: only the nine owned files may change; no broad formatting.
- A2-A4, B3, F2, and H2-H4: no planned violations.

**o) Ratchet interaction.** Existing BLE001 entries for enrichment and semantic
healthcheck CLIs remain because their boundary aggregation is intentional.
The new shared module receives no exception. Ruff rule families and all other
selectors remain unchanged.

**p) Dead code and duplication audit.** Delete private helper imports from the
role CLIs and repeated broker/database/reporting blocks. Reuse existing probe
logic rather than copying it. Expected production line count decreases; tests
increase around the shared and primary-worker contracts. The task owns nine
files.

## 5. Testing

**q) Edge cases and failure scenarios.**

1. Missing URL host or port yields a configured-target failure.
2. Socket refusal/timeout becomes a compact failure and does not abort later
   probes.
3. Malformed ports and non-integer metrics ports retain their fail-fast
   exceptions rather than becoming compact failures.
4. IPv6 URLs continue to resolve host and port correctly.
5. Primary worker retains `REDIS_HOST:6379` fallback when broker URL is empty.
6. Enrichment and semantic workers do not gain that fallback.
7. Multiple failures are all written to stderr and return exit `1`.
8. No failures produce no stderr and return exit `0`.
9. Primary metrics and Ollama/OpenAI-compatible model probes remain intact.
10. Compose keeps all three exact script entrypoints.
11. A shared helper importing a CLI or a role CLI importing another CLI fails
    the structural contract.
12. Probe order and timeout values remain unchanged.
13. Local test environment lacks role-only packages; host availability must
    not be treated as image behavior.

**r) Tests mapped to scenarios.**

| Test | Scenarios |
|---|---|
| New shared-probe tests using real loopback sockets | 1-4, 7-8 |
| Updated primary-worker tests | 3, 5, 7-9, 12 |
| Import-direction structural contract | 6, 11, 13 |
| Docker health contract plus real role-container smoke | 6, 10, 12-13 |
| Ruff, Mypy, and complete suite | 1-13 regression check |

Characterization tests are added and run red before the shared module exists.

**s) Fakes and mocks.** Shared TCP behavior uses real loopback listeners, not a
socket fake. Primary-worker inference tests use the approved outbound HTTP
boundary and remove private `_probe_tcp`/`_probe_http_model` monkeypatches.
Role-only dependency and task-registration success paths are verified in their
real Compose images, not with unapproved import or subprocess fakes. No facade,
re-export, injectable callable, or production test seam is added.

**t) Verification rows.** No named matrix row covers script-only behavior, so
run focused healthcheck and Docker contract tests, the docs-only row for the
plan, Ruff for Python changes, Mypy for repository confidence, and the
complete Python suite before handoff.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-dd-1a-worker-healthchecks

PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_worker_health_probes.py \
  tests/test_worker_healthcheck.py \
  tests/test_docker_health_contracts.py \
  tests/test_docker_build_contracts.py

docker compose up -d \
  redis postgres inference worker enrichment-worker semantic-worker
docker compose exec -T worker python scripts/worker_healthcheck.py
docker compose exec -T enrichment-worker \
  python scripts/enrichment_worker_healthcheck.py
docker compose exec -T semantic-worker \
  python scripts/semantic_worker_healthcheck.py

set +e
enrichment_failure=$(
  docker compose run --rm --no-deps \
    -e CELERY_BROKER_URL= -e DATABASE_URL= \
    enrichment-worker python scripts/enrichment_worker_healthcheck.py 2>&1
)
enrichment_exit=$?
semantic_failure=$(
  docker compose run --rm --no-deps \
    -e CELERY_BROKER_URL= -e DATABASE_URL= \
    semantic-worker python scripts/semantic_worker_healthcheck.py 2>&1
)
semantic_exit=$?
set -e
test "$enrichment_exit" -eq 1
test "$semantic_exit" -eq 1
printf '%s\n' "$enrichment_failure" | grep -F "redis broker target is not configured"
printf '%s\n' "$semantic_failure" | grep -F "redis broker target is not configured"

./.venv/bin/ruff check .
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/pytest -q
git diff --check
git status --short
```

Delivery:

```bash
git push -u origin codex/t-dd-1a-worker-healthchecks
gh pr create --base master --head codex/t-dd-1a-worker-healthchecks \
  --title "T-DD-1A: Consolidate worker health probes"
```

**v) Rollback.** Revert the T-DD-1A merge commit and rerun focused healthcheck,
Docker contracts, Ruff, Mypy, docs links, and the complete suite. Compose
continues to call the same three filenames, so no operational command, data,
migration, or external-state rollback is needed.

**w) Docs sync.** Update only the remediation ledger and this implementation
plan. README, ADR, architecture review, operations, testing policy,
guardrails, API contracts, security, and data-governance docs remain accurate.

## 7. Delivery Self-Audit

**x) Antipattern scan, diff pass.** Re-run A-F/H. Reject callable injection,
CLI-to-CLI imports, compatibility exports, a generic probe registry, moved
broad handlers, new Ruff exceptions, altered probe labels/timeouts/defaults,
weakened tests, or files outside ownership.

**y) Evidence.** Report the tests-first red result, all commands in 6u,
independent planning/pre-commit findings, applied fixes, commit hashes, PR URL,
review threads, and CI state. Mark unrun checks `NOT VERIFIED`.

**z) Deviations.** Authorized changes are splitting T-DD-1 into T-DD-1A and
T-DD-1B and correcting the healthcheck count from two to three. Any other
owned-file expansion, CLI/Compose contract change, role-check relocation,
new exception, skipped review, unresolved P1/P2, or unrun required check is a
blocker.
