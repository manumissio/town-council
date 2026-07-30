# T-PLAT-2C: Migrate Celery to 5.6.3

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: implementation-ready`
`execution: code`

## 1. Context & Alignment

**a) Driver.** Dependabot PR #194 proposes Celery 5.6.3, but it is based on an
older constraints file and fails the exact dependency contract. Celery spans
the API dispatch boundary, Redis broker and result backend, prefork workers,
queue routing, health probes, and graceful shutdown. The upgrade must therefore
be repaired on current master and proven in isolated Docker runtime checks
before merge.

**b) Canonical documents consulted.**

- `AGENTS.md` hard invariants, security-sensitive paths, verification matrix,
  and status reporting require unchanged runtime policy, exact evidence, and a
  trust-boundary report for Docker execution.
- `SECURITY.md` requires authenticated Redis use and prohibits credential
  exposure.
- `docs/TESTING.MD` permits Celery dispatch fakes in unit tests but requires
  observable runtime evidence for integration behavior.
- `docs/ENGINEERING_GUARDRAILS.md` keeps Ruff and Mypy policy unchanged.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` marks T-PLAT-2 complete and
  explicitly forbids package-version changes in that task, requiring this
  separately owned migration.
- `docs/reviews/architecture-review-2026-07-19.html` identifies worker
  boundaries and dependency drift as architecture risks.

**c) Remediation alignment.** T-PLAT-2C is a new platform-lane migration task.
Its exact `files_owned` set is:

- `docs/plans/T_PLAT_2C_CELERY_MIGRATION_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `constraints.txt`
- `tests/test_docker_build_contracts.py`

No production source, Dockerfile, Compose, requirement manifest, workflow, or
runtime policy file may change unless runtime verification exposes a concrete
incompatibility and the operator authorizes expanded ownership.

**d) Decision-gate check.** No G1-G5 decision applies. The operator approved
the migration ownership and Docker runtime gates. G3 remains satisfied; City
Coverage Expansion remains blocked on T-GOV-2A. Implementation starts only
after PR #196 merges and the branch is created from the resulting
`origin/master`, because both tasks own the remediation ledger.

## 2. Design

**e) Step-by-step approach.**

1. Confirm PR #196 is merged, fast-forward local `master`, and create the
   migration branch from that exact `origin/master`.
2. Register T-PLAT-2C, its ownership, acceptance criteria, and rollback in the
   remediation ledger.
3. Change the exact dependency contract to Celery 5.6.3 and run it red against
   the existing 5.3.4 constraint.
4. Change only the shared Celery constraint from 5.3.4 to 5.6.3.
5. Run Ruff, Mypy, Docker dependency contracts, task orchestration and routing
   tests, docs links, and the complete coverage-gated Python suite.
6. Build the four affected Docker targets: API, live worker, batch worker, and
   semantic service.
7. Run `pip check` and exact-version inspection in every image.
8. Start isolated Redis 7 and PostgreSQL, then run the actual live prefork
   worker, enrichment worker, and semantic worker with their production apps,
   pools, and queues.
9. Verify worker readiness, registered tasks, active queues, control ping,
   one deterministic Town Council task per queue, Redis result retrieval and
   cleanup, all role healthchecks, secret masking, and graceful shutdown.
10. Prove the final PR diff contains exactly the four owned files.
11. Obtain a fresh pre-commit review, commit, push, open the replacement PR,
   close #194 as superseded, and merge only after CI and runtime gates pass.

No new function or module is introduced.

**f) Reuse audit.** Reuse the shared constraints mechanism, existing Celery
app, production worker entrypoint, queue declarations, health probes, and
current tests. Do not add a compatibility wrapper, alternate Celery app,
version branch, test-only task, retry layer, or queue registry.

**g) Data contracts.** Preserve task names, arguments, result payloads, queue
names, retry behavior, broker/result URLs, worker pools, and concurrency
defaults. The only intended contract change is the installed Celery version
from 5.3.4 to 5.6.3.

**h) Schema/migration impact.** None. The smoke uses a disposable PostgreSQL
database because worker startup imports database-backed task code.

## 3. Security & Data Governance

**i) Security boundary.** Celery crosses API, Redis, and worker process
boundaries. The migration must preserve authenticated Redis connections,
private Docker networking, worker queue isolation, and credential masking.
No production port, permission, image role, or key policy changes.

**j) Secrets.** Use disposable runtime-only Redis and PostgreSQL credentials.
Assert the Redis password does not appear in worker logs. No credential or
default is committed.

**k) Person data.** None is created, linked, aggregated, or exposed.

**l) Untrusted input.** No new parser is introduced. Broker messages continue
through Celery's existing task deserialization boundary.

## 4. Code Health

**m) GED conformance sweep.** The implementation changes one version literal
and its exact contract. No function, exception handler, timestamp, environment
read, task signature, or runtime default changes.

**n) Antipattern scan, plan pass.**

- A1/H1: Celery 5.6 control ping, result retrieval, and result cleanup were
  verified against current Celery stable documentation and installed project
  usage.
- A2-A4: no new setting, silent default, placeholder, or unsupported claim.
- B1-B3/C1-C2/F1-F2: no wrapper, compatibility path, duplicate app, test seam,
  speculative validation, or copied implementation.
- D1-D3: no skip, xfail, tolerance change, mocked runtime, or weakened
  assertion.
- E1-E3: only the four owned files change; generated files are not committed.
- H2-H4: no type suppression, alternate contract, or import-time side effect.

**o) Ratchet interaction.** Ruff selectors, BLE001 boundaries, Mypy scope,
coverage floor, formatter scope, and CI gates remain unchanged.

**p) Dead code and duplication audit.** No code is superseded. The old Celery
pin and matching test expectation are replaced in place. Expected production
code delta is zero.

## 5. Testing

**q) Edge cases and failure scenarios.**

1. The exact constraint and contract disagree.
2. A transitive dependency produces a broken environment.
3. Python 3.14 static checks or the complete suite regress.
4. Production Python 3.12 worker roles or prefork startup regress.
5. Redis broker control ping fails.
6. Result-backend retrieval or cleanup fails.
7. Town Council tasks are not registered on their intended queues.
8. Queue routing or health probes regress.
9. Worker logs expose broker credentials.
10. Graceful shutdown exits nonzero or hangs.
11. Rebasing reverts unrelated current constraints.

**r) Tests.**

| Verification | Scenarios |
|---|---|
| Exact Docker dependency contract | 1, 11 |
| Task orchestration, routing, metrics, and health tests | 7-8 |
| Four Python 3.12 image builds plus `pip check` | 2, 4 |
| Isolated Redis/PostgreSQL worker smoke | 4-10 |
| Python 3.14 coverage-gated suite | 1-3, 7-8, 11 |
| PR CI dependency audits | 1-3, 11 |

The exact contract is changed and run red before the constraint is updated.

**s) Fakes and mocks.** Unit tests retain existing approved Celery dispatch
boundaries. Runtime acceptance uses real containers and the production Celery
app; no production symbol is patched.

**t) Verification rows.** Apply the guardrail minimum, Docker dependency
contract, task orchestration, docs-only, and broad cross-cutting rows. The
complete coverage-gated Python suite and all four affected image builds are
mandatory.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

Fresh base and ownership:

```bash
set -euo pipefail

git fetch origin --prune
test "$(gh pr view 196 --json state --jq .state)" = "MERGED"
git switch master
git merge --ff-only origin/master
git switch -c codex/t-plat-2c-celery-migration
```

Tests-first:

```bash
set -euo pipefail

PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_docker_build_contracts.py::test_active_python_manifests_use_shared_exact_constraints
```

Static and Python verification:

```bash
set -euo pipefail

./.venv/bin/ruff check .
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_docker_build_contracts.py \
  tests/test_async_flow.py \
  tests/test_enrichment_task_routing.py \
  tests/test_semantic_task_routing.py \
  tests/test_role_worker_healthchecks.py \
  tests/test_worker_healthcheck.py \
  tests/test_run_pipeline_orchestration.py \
  tests/test_pipeline_batching.py \
  tests/test_task_metrics.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/python -m pytest -q \
  --cov --cov-config=.coveragerc \
  --cov-report=term-missing:skip-covered tests/
git diff --check

expected_owned_files=$(
  printf '%s\n' \
    constraints.txt \
    docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md \
    docs/plans/T_PLAT_2C_CELERY_MIGRATION_PLAN.md \
    tests/test_docker_build_contracts.py |
    sort
)
actual_owned_files=$(
  {
    git diff --name-only origin/master
    git ls-files --others --exclude-standard
  } |
    sort
)
test "$actual_owned_files" = "$expected_owned_files"
```

Build and inspect:

```bash
set -euo pipefail

cleanup_failed_celery_builds() {
  local build_status=$?

  trap - EXIT
  if [ "$build_status" -ne 0 ]; then
    docker image rm tc-celery563-api tc-celery563-worker-live \
      tc-celery563-worker-batch tc-celery563-semantic ||
      printf 'build cleanup failed; inspect tc-celery563-* images\n' >&2
  fi
  exit "$build_status"
}
trap cleanup_failed_celery_builds EXIT

docker build --target python-api -t tc-celery563-api .
docker build --target python-worker-live -t tc-celery563-worker-live .
docker build --target python-worker-batch -t tc-celery563-worker-batch .
docker build --target python-semantic -t tc-celery563-semantic .

for image in tc-celery563-api tc-celery563-worker-live \
  tc-celery563-worker-batch tc-celery563-semantic
do
  docker run --rm "$image" python -m pip check
  docker run --rm "$image" python -c \
    'from importlib.metadata import version
packages = ("celery", "kombu", "billiard", "vine", "redis")
versions = {package: version(package) for package in packages}
assert versions["celery"] == "5.6.3", versions
print(versions)'
done

trap - EXIT
```

Run the complete isolated runtime smoke as one shell block so exported state
and the cleanup trap cover dependencies, workers, probes, and shutdown:

```bash
set -euo pipefail

export TC_CELERY_NETWORK=tc-celery563-net
export TC_CELERY_REDIS=tc-celery563-redis
export TC_CELERY_POSTGRES=tc-celery563-postgres
export TC_CELERY_LIVE=tc-celery563-live
export TC_CELERY_ENRICHMENT=tc-celery563-enrichment
export TC_CELERY_SEMANTIC=tc-celery563-semantic
export TC_CELERY_PASSWORD=tc-celery563-test-only
export TC_CELERY_DATABASE_URL=postgresql://town_council:town_council_test@tc-celery563-postgres:5432/town_council_test
export TC_CELERY_BROKER_URL=redis://:tc-celery563-test-only@tc-celery563-redis:6379/0

cleanup_celery_smoke() {
  local cleanup_status=0
  local container
  local image

  if ! docker info >/dev/null; then
    printf 'cleanup failed: Docker daemon is unavailable\n' >&2
    return 1
  fi

  for container in "$TC_CELERY_LIVE" "$TC_CELERY_ENRICHMENT" \
    "$TC_CELERY_SEMANTIC" "$TC_CELERY_REDIS" "$TC_CELERY_POSTGRES"
  do
    if docker container inspect "$container" >/dev/null 2>&1; then
      docker rm -f "$container" || cleanup_status=1
    fi
    if docker container inspect "$container" >/dev/null 2>&1; then
      printf 'cleanup failed: container remains: %s\n' "$container" >&2
      cleanup_status=1
    fi
  done

  if docker network inspect "$TC_CELERY_NETWORK" >/dev/null 2>&1; then
    docker network rm "$TC_CELERY_NETWORK" || cleanup_status=1
  fi
  if docker network inspect "$TC_CELERY_NETWORK" >/dev/null 2>&1; then
    printf 'cleanup failed: network remains: %s\n' "$TC_CELERY_NETWORK" >&2
    cleanup_status=1
  fi

  for image in tc-celery563-api tc-celery563-worker-live \
    tc-celery563-worker-batch tc-celery563-semantic
  do
    if docker image inspect "$image" >/dev/null 2>&1; then
      docker image rm "$image" || cleanup_status=1
    fi
    if docker image inspect "$image" >/dev/null 2>&1; then
      printf 'cleanup failed: image remains: %s\n' "$image" >&2
      cleanup_status=1
    fi
  done

  if ! docker info >/dev/null; then
    printf 'cleanup failed: Docker daemon became unavailable\n' >&2
    cleanup_status=1
  fi

  return "$cleanup_status"
}

finish_celery_smoke() {
  local smoke_status=$?
  local cleanup_status=0

  trap - EXIT
  cleanup_celery_smoke || cleanup_status=$?
  if [ "$smoke_status" -ne 0 ]; then
    exit "$smoke_status"
  fi
  exit "$cleanup_status"
}
trap finish_celery_smoke EXIT

docker network create "$TC_CELERY_NETWORK"
docker run -d --name "$TC_CELERY_REDIS" --network "$TC_CELERY_NETWORK" \
  -e REDIS_PASSWORD="$TC_CELERY_PASSWORD" redis:7-alpine \
  sh -eu -c 'exec redis-server --save "" --appendonly no --requirepass "$REDIS_PASSWORD"'
docker run -d --name "$TC_CELERY_POSTGRES" --network "$TC_CELERY_NETWORK" \
  -e POSTGRES_USER=town_council -e POSTGRES_PASSWORD=town_council_test \
  -e POSTGRES_DB=town_council_test pgvector/pgvector:pg15
for attempt in $(seq 1 60)
do
  if docker exec -e REDISCLI_AUTH="$TC_CELERY_PASSWORD" \
    "$TC_CELERY_REDIS" redis-cli ping | grep -qx PONG
  then
    break
  fi
  sleep 1
  if [ "$attempt" -eq 60 ]; then
    docker logs "$TC_CELERY_REDIS"
    exit 1
  fi
done
for attempt in $(seq 1 60)
do
  if docker exec "$TC_CELERY_POSTGRES" \
    pg_isready -U town_council -d town_council_test
  then
    break
  fi
  sleep 1
  if [ "$attempt" -eq 60 ]; then
    docker logs "$TC_CELERY_POSTGRES"
    exit 1
  fi
done
docker run --rm --network "$TC_CELERY_NETWORK" \
  -e DATABASE_URL="$TC_CELERY_DATABASE_URL" tc-celery563-worker-live \
  python -m pipeline.db_migrate

# Start the three production worker roles.
docker run -d --name "$TC_CELERY_LIVE" --network "$TC_CELERY_NETWORK" \
  -e PYTHONPATH=/app -e APP_ENV=dev -e STARTUP_PURGE_DERIVED=false \
  -e DATABASE_URL="$TC_CELERY_DATABASE_URL" -e REDIS_HOST="$TC_CELERY_REDIS" \
  -e REDIS_PASSWORD="$TC_CELERY_PASSWORD" \
  -e CELERY_BROKER_URL="$TC_CELERY_BROKER_URL" \
  -e CELERY_RESULT_BACKEND="$TC_CELERY_BROKER_URL" \
  -e LOCAL_AI_BACKEND=http -e TC_WORKER_METRICS_PORT=8001 \
  -e MEILI_MASTER_KEY=tc-celery563-test-only tc-celery563-worker-live \
  celery -A pipeline.tasks worker --loglevel=info --concurrency=3 \
  --pool=prefork -Q celery --hostname=live@%h

docker run -d --name "$TC_CELERY_ENRICHMENT" --network "$TC_CELERY_NETWORK" \
  -e PYTHONPATH=/app -e DATABASE_URL="$TC_CELERY_DATABASE_URL" \
  -e CELERY_BROKER_URL="$TC_CELERY_BROKER_URL" \
  -e CELERY_RESULT_BACKEND="$TC_CELERY_BROKER_URL" \
  -e MEILI_MASTER_KEY=tc-celery563-test-only tc-celery563-worker-batch \
  celery -A pipeline.enrichment_tasks worker --loglevel=info \
  --concurrency=1 --pool=solo -Q enrichment --hostname=enrichment@%h

docker run -d --name "$TC_CELERY_SEMANTIC" --network "$TC_CELERY_NETWORK" \
  -e PYTHONPATH=/app -e DATABASE_URL="$TC_CELERY_DATABASE_URL" \
  -e CELERY_BROKER_URL="$TC_CELERY_BROKER_URL" \
  -e CELERY_RESULT_BACKEND="$TC_CELERY_BROKER_URL" \
  -e SEMANTIC_ENABLED=false -e SEMANTIC_INDEX_DIR=/tmp/semantic \
  tc-celery563-semantic celery -A pipeline.semantic_tasks worker \
  --loglevel=info --concurrency=1 --pool=solo -Q semantic \
  --hostname=semantic@%h

# Inspect each worker and dispatch one deterministic task to each queue.
if ! docker run --rm -i --network "$TC_CELERY_NETWORK" \
  -e PYTHONPATH=/app -e CELERY_BROKER_URL="$TC_CELERY_BROKER_URL" \
  -e CELERY_RESULT_BACKEND="$TC_CELERY_BROKER_URL" tc-celery563-api \
  python - <<'PY'
import time

from pipeline.celery_app import app

expected_nodes = {"live", "enrichment", "semantic"}
deadline = time.monotonic() + 60
while True:
    ping_responses = app.control.ping(timeout=2) or []
    pinged_nodes = {
        node.split("@", maxsplit=1)[0]
        for response in ping_responses
        for node, payload in response.items()
        if payload == {"ok": "pong"}
    }
    if pinged_nodes == expected_nodes:
        break
    if time.monotonic() >= deadline:
        raise RuntimeError(
            f"Workers did not become ready: expected={expected_nodes}, "
            f"pinged={pinged_nodes}"
        )
    time.sleep(1)

inspect = app.control.inspect(timeout=10)
registered = inspect.registered() or {}
active_queues = inspect.active_queues() or {}
expected = {
    "live": ("pipeline.tasks.generate_summary_task", "celery"),
    "enrichment": ("enrichment.generate_topics", "enrichment"),
    "semantic": ("semantic.embed_catalog", "semantic"),
}
for role, (task_name, queue_name) in expected.items():
    matching_nodes = [node for node in registered if node.startswith(f"{role}@")]
    assert len(matching_nodes) == 1, (role, registered)
    node = matching_nodes[0]
    assert task_name in registered[node], (node, registered[node])
    assert {queue["name"] for queue in active_queues[node]} == {queue_name}

tasks = (
    ("pipeline.tasks.generate_summary_task", "celery", {"error": "Catalog not found"}),
    ("enrichment.generate_topics", "enrichment", {"error": "No content to tag"}),
    (
        "semantic.embed_catalog",
        "semantic",
        {"status": "skipped", "reason": "semantic_disabled"},
    ),
)
for task_name, queue_name, expected_payload in tasks:
    task_result = app.send_task(task_name, args=(2_147_483_647,), queue=queue_name)
    try:
        assert task_result.get(timeout=30) == expected_payload
    finally:
        task_id = task_result.id
        task_result.forget()
    assert app.AsyncResult(task_id).state == "PENDING", task_id
PY
then
  for worker in "$TC_CELERY_LIVE" "$TC_CELERY_ENRICHMENT" "$TC_CELERY_SEMANTIC"
  do
    docker logs "$worker"
  done
  exit 1
fi

# The healthcheck-only override disables the unrelated external model probe.
docker exec -e LOCAL_AI_BACKEND=inprocess "$TC_CELERY_LIVE" \
  python scripts/worker_healthcheck.py
docker exec "$TC_CELERY_ENRICHMENT" \
  python scripts/enrichment_worker_healthcheck.py
docker exec "$TC_CELERY_SEMANTIC" \
  python scripts/semantic_worker_healthcheck.py

# Require secret masking and graceful exit.
for worker in "$TC_CELERY_LIVE" "$TC_CELERY_ENRICHMENT" "$TC_CELERY_SEMANTIC"
do
  if docker logs "$worker" 2>&1 | grep -F "$TC_CELERY_PASSWORD"; then
    exit 1
  fi
  docker stop --timeout 30 "$worker"
  test "$(docker inspect -f '{{.State.ExitCode}}' "$worker")" = 0
done
```

Cleanup runs after success or failure and removes only test-labeled workers,
dependencies, network, images, and temporary logs.

All temporary containers, networks, images, logs, and credentials are removed
after success or failure.

**v) Rollback.** Before merge, close the migration PR and leave Celery 5.3.4.
After merge, keep Redis and PostgreSQL running, stop task producers, confirm
no manually launched backfill, pipeline, or Celery producer remains active,
drain the three worker roles, and rebuild all affected application images:

```bash
set -euo pipefail

docker compose stop api pipeline pipeline-batch extractor monitor semantic

# Stop any one-off producer started outside Compose before continuing.
# Do not drain workers while an operator-run backfill or pipeline can enqueue work.

for attempt in $(seq 1 60)
do
  if docker compose exec -T worker python - <<'PY'
from pipeline.celery_app import app

inspect = app.control.inspect(timeout=5)
registered = inspect.registered() or {}
active_queues = inspect.active_queues() or {}
active_tasks = inspect.active() or {}
reserved_tasks = inspect.reserved() or {}
scheduled_tasks = inspect.scheduled() or {}
expected = {
    "live": ("pipeline.tasks.generate_summary_task", "celery"),
    "enrichment": ("enrichment.generate_topics", "enrichment"),
    "semantic": ("semantic.embed_catalog", "semantic"),
}
matched_nodes = {}
for role, (task_name, queue_name) in expected.items():
    candidates = [
        node
        for node, tasks in registered.items()
        if task_name in tasks
        and {queue["name"] for queue in active_queues.get(node, [])} == {queue_name}
    ]
    if len(candidates) != 1:
        raise RuntimeError(f"Cannot identify {role} worker: {candidates}")
    matched_nodes[role] = candidates[0]
expected_node_names = set(matched_nodes.values())
pending_states = {
    "active": active_tasks,
    "reserved": reserved_tasks,
    "scheduled": scheduled_tasks,
}
for state_name, task_state in pending_states.items():
    if set(task_state) != expected_node_names:
        raise RuntimeError(
            f"Not every worker reported {state_name} tasks: "
            f"{task_state}, {matched_nodes}"
        )
    if any(task_state[node] for node in expected_node_names):
        raise RuntimeError(f"Workers still have {state_name} tasks: {task_state}")
PY
  then
    break
  fi
  sleep 2
  if [ "$attempt" -eq 60 ]; then
    docker compose logs --tail=200 worker enrichment-worker semantic-worker
    exit 1
  fi
done

docker compose stop worker enrichment-worker semantic-worker
git revert <celery_migration_commit_sha>
docker compose build api worker pipeline-batch semantic
docker compose up -d --no-deps worker enrichment-worker semantic-worker

for attempt in $(seq 1 60)
do
  if docker compose exec -T worker python - <<'PY'
from pipeline.celery_app import app

ping_responses = app.control.ping(timeout=5) or []
pinged_nodes = {
    node for response in ping_responses for node, payload in response.items()
    if payload == {"ok": "pong"}
}
registered = app.control.inspect(timeout=5).registered() or {}
active_queues = app.control.inspect(timeout=5).active_queues() or {}
expected = {
    "live": ("pipeline.tasks.generate_summary_task", "celery"),
    "enrichment": ("enrichment.generate_topics", "enrichment"),
    "semantic": ("semantic.embed_catalog", "semantic"),
}
matched_nodes = set()
for role, (task_name, queue_name) in expected.items():
    candidates = [
        node
        for node, tasks in registered.items()
        if node in pinged_nodes
        and task_name in tasks
        and {queue["name"] for queue in active_queues.get(node, [])} == {queue_name}
    ]
    if len(candidates) != 1:
        raise RuntimeError(f"Cannot verify restarted {role} worker: {candidates}")
    matched_nodes.add(candidates[0])
if matched_nodes != pinged_nodes:
    raise RuntimeError(
        f"Unexpected ping responders: matched={matched_nodes}, pinged={pinged_nodes}"
    )
PY
  then
    break
  fi
  sleep 2
  if [ "$attempt" -eq 60 ]; then
    docker compose logs --tail=200 worker enrichment-worker semantic-worker
    exit 1
  fi
done

docker compose exec -T worker python scripts/worker_healthcheck.py
docker compose exec -T enrichment-worker \
  python scripts/enrichment_worker_healthcheck.py
docker compose exec -T semantic-worker \
  python scripts/semantic_worker_healthcheck.py

docker compose up -d --no-deps api pipeline extractor monitor semantic
```

Do not restart or flush Redis or PostgreSQL. Do not resume external task
dispatch until all three pings succeed. No data remediation or schema reversal
is required.

**w) Docs synchronization.** Add this implementation plan and register
T-PLAT-2C in the remediation ledger. README, architecture, ADR, operations,
performance, testing policy, security policy, and API contracts do not change
because runtime behavior and defaults remain unchanged.

## 7. Delivery Self-Audit

**x) Antipattern scan, diff pass.** Re-run A-F/H. Reject production source
changes, a compatibility layer, alternate app, task-signature drift, queue
changes, runtime fallback, dependency churn beyond Celery and its resolver
output, test weakening, or files outside ownership.

**y) Evidence.** Report the tests-first failure, every command from 6u,
resolved dependency versions, Docker target results, runtime probes, secret
scan, cleanup, planning and pre-commit review findings, commit hashes,
replacement PR URL, #194 closure, unresolved-thread count, and final CI state.
Mark anything unrun `NOT VERIFIED`.

**z) Deviations.** Expected deviations are the operator-approved new T-PLAT-2C
task and replacement of Dependabot PR #194 with an owned migration PR. Any
production source edit, extra file, skipped image, unrun runtime probe,
unresolved P1/P2, widened policy, or altered task contract is a blocker.
