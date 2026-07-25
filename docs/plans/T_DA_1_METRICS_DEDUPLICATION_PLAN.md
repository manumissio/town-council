# T-DA-1: Collapse the Metrics Redis Twins

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: complete`
`execution: code`

## 1. Context & Alignment

**a) Driver.** `pipeline.metrics` and `pipeline.metrics_redis_backend` both
own Redis client state, backend-health state, write operations, and collector
adapters. Two synchronization functions copy four process-local globals in
both directions solely to preserve historical facade patch points. G3 is
accepted, so those patch points are no longer contracts. T-DA-1 removes that
split authority while preserving the public metrics interface, prefork Redis
aggregation, nonfatal telemetry degradation, and current metric names and
labels.

**b) Canonical documents consulted.**

- `AGENTS.md` hierarchy, known-antipatterns, telemetry rules, security paths,
  verification matrix, and workflow contract require one state owner, direct
  implementation patching, and full metrics verification.
- `docs/TESTING.MD` requires tests to patch the Redis client at the
  implementation boundary rather than through `pipeline.metrics`.
- `docs/ENGINEERING_GUARDRAILS.md` requires narrow, explained exceptions and
  removal of stale Ruff entries.
- `SECURITY.md` requires Redis credentials to remain environment-sourced and
  undisclosed.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` defines T-DA-1 acceptance and
  authorizes Phase 2 after G3.
- `docs/reviews/architecture-review-2026-07-19.html` identifies the metrics
  state as exact duplication and ready after CI/G3.

**c) Remediation alignment.** T-DA-1 remains in the DEDUP-A lane. Expand its
exclusive ownership to:

- `docs/plans/T_DA_1_METRICS_DEDUPLICATION_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `pipeline/metrics.py`
- `pipeline/metrics_definitions.py`, provider metric registration only
- `pipeline/metrics_provider_collector.py`
- `pipeline/metrics_redis_backend.py`
- `pipeline/metrics_provider_recorders.py`
- `pipeline/metrics_task_recorders.py`
- `ruff.toml`, only the `pipeline/metrics_redis_backend.py` S105 entry
- `tests/test_metrics_api.py`
- `tests/test_provider_metrics_prefork_redis_aggregation.py`
- `tests/test_task_metrics.py`
- `tests/test_worker_metrics_exporter_provider_series.py`

No other tracked file may change.

**d) Decision-gate check.** G3 is satisfied and explicitly permits removal of
test-only facade patch points. T-DA-1 depends on no open G1, G2, G4, or G5
decision.

## 2. Design

**e) Step-by-step approach.**

1. Register this Full plan, exact ownership, and in-progress state before
   editing implementation files.
2. Obtain independent planning review and correct every eligible P1/P2.
3. Add tests first that require the backend to be the sole owner of Redis
   state and operations, preserve the public collector binding, and patch the
   Redis implementation boundary.
4. Run those tests red against the duplicated facade.
5. In `pipeline.metrics`, delete the four copied Redis globals, both
   synchronization functions, facade client and health wrappers, three
   duplicate write functions, and duplicate collector subclass.
6. Import `RedisProviderMetricsCollector` directly from
   `metrics_redis_backend`. This preserves the operational
   `pipeline.metrics.RedisProviderMetricsCollector` interface used by worker
   metrics collection while binding it to the single implementation.
7. Make the seven Redis-mirrored provider metric instruments in
   `metrics_definitions` unregistered local instruments. Keep provider request
   duration registered because it is not mirrored into Redis. This gives each
   exported provider series one registry owner while preserving recorder calls.
   When Redis is unavailable or degraded, the collector yields those local
   instruments so process-local telemetry remains available.
8. Give the provider collector a side-effect-free `describe()` path backed by
   one metric-construction helper. Describe all Redis-backed names now owned by
   the collector using canonical counter family names, so registration never
   calls Redis, metadata stays valid, and scrape output contains one copy of
   each provider series. Decompose `collect()` into focused aggregate and local
   fallback helpers.
9. Make both recorder modules use `metrics_definitions` directly. Provider
   recorders call `metrics_redis_backend` directly and drop injected Redis
   callable parameters; both modules delete their dynamic facade lookups.
10. Repoint Redis tests to `pipeline.metrics_redis_backend` and replace facade
   metric patches with before/after assertions on exported Prometheus samples.
11. Add a line-level S105 suppression to `REDIS_PASSWORD_ENV` explaining that
   it is an environment-variable identifier, not a credential. Remove the
   now-stale Ruff per-file S105 entry.
12. Run focused metrics, lint-ratchet, security, docs, and complete-suite
    verification.
13. Obtain a fresh pre-commit review, resolve every eligible P1/P2, and rerun
    affected verification.
14. Mark T-DA-1 complete, commit atomically, push one PR, request Codex
    review, resolve feedback, and merge only after required checks pass.

The only new production methods/helpers are `describe()`, one metric factory,
one focused aggregate population helper, and one local fallback helper in the
collector. No new class, wrapper, registry, reset hook, state container, or
compatibility shim is introduced.

**f) Reuse audit.** Reuse the canonical backend and `metrics_definitions`;
one collector metric factory serves both `describe()` and `collect()`.
`pipeline.metrics` remains the public recorder, Celery-signal, and collector
registration module. Duplicate implementations and test seams are deleted.

**g) Data contracts.** Public metric recorder names, Prometheus metric names,
Redis key formats, label escaping, `tc_provider_*` exports, Celery signal
registration, and `pipeline.metrics.RedisProviderMetricsCollector` remain
unchanged. Redis-mirrored local instruments stop self-registering so the Redis
collector is the sole registry owner; it exports Redis aggregates when healthy
and process-local instruments when degraded. Provider request duration remains
a local registered histogram. Redis state remains process-local; Redis atomic
increments remain the cross-process aggregation mechanism.

**h) Schema/migration impact.** None.

## 3. Security & Data Governance

**i) Security-sensitive paths.** `pipeline.metrics_redis_backend` handles the
Redis password environment variable, so this task touches the Redis credential
boundary named by `AGENTS.md`. Attacker capability does not change: the
password remains environment-sourced, is passed only to the Redis client, is
never logged, and gains no default or new exposure. The S105 change narrows a
file-wide exception to one explained false-positive line, strengthening the
`SECURITY.md` secret-policy control.

**j) Secrets.** No credential, key, environment variable, value, or default is
added or changed. `REDIS_PASSWORD_ENV` remains a name, not a credential.

**k) Person data.** No person-level data is created, linked, aggregated, or
exposed. G4 is unaffected.

**l) Untrusted input.** Redis metric values and keys remain external backend
input to the existing collector parser. This task does not change parsing,
validation, malformed-value handling, or scraped-content boundaries.

## 4. Code Health

**m) GED conformance sweep.** The change deletes two-way synchronization,
duplicate functions, dynamic facade lookup, and injected callables. No new
environment reads, handlers, timestamps, literals, nested flow, or parameters
are introduced. Redis write failures still mark backend health down while
preserving local Prometheus metrics.

**n) Antipattern scan, plan pass.**

- A1/H1: installed redis-py 5.0.1 signatures for `ping`, `incrby`, `hincrby`,
  and `hincrbyfloat` were inspected locally. Upstream tag v0.19.0, matching
  the repository pin, confirms `CollectorRegistry` prefers `describe()` and
  otherwise calls `collect()` when auto-description is enabled. Context7 and
  the pinned constructor source confirm `registry=None` skips default
  registration while preserving metric instrumentation methods.
- B1/F1: the existing backend is reused; no adapter or state abstraction is
  introduced.
- B2/C1: copied state, sync functions, duplicate writes, and duplicate
  collector subclass are deleted in the same PR.
- C2: tests patch `metrics_redis_backend`, not the facade; both dynamic facade
  lookups are deleted.
- D1-D3: tests preserve observable Redis, Prometheus, and HTTP outcomes; one
  structural test enforces the task's explicit single-owner acceptance.
- E1-E3: only the thirteen owned files change; no formatting sweep is permitted.
- A2-A4, B3, F2, H2-H4: no planned violations.

**o) Ratchet interaction.** Remove one Ruff selector:
`pipeline/metrics_redis_backend.py: S105`. Replace it with one explained
line-level suppression on `REDIS_PASSWORD_ENV`. No rule family, scope,
threshold, BLE001 boundary, formatter scope, Mypy scope, or coverage floor
changes.

**p) Dead code and duplication audit.** Delete four facade globals, two sync
functions, three Redis writes, three accessors, one collector subclass, two
dynamic facade lookups, three callable aliases, injected callable parameters,
and unused imports. The collector gains only the registration-safe descriptor
path and focused population helpers. Expected production delta remains negative.

## 5. Testing

**q) Edge cases and failure scenarios.**

1. Importing `pipeline.metrics` must not connect to Redis; registration uses
   `describe()` rather than `collect()` and claims all collector-owned metric
   families.
2. The backend remains the only owner of Redis client, init, warning, and
   health state.
3. Provider recorders update local Prometheus metrics and canonical Redis
   keys.
4. Redis unavailable at first access preserves local metrics, warns once per
   process, and leaves the backend gauge down.
5. Redis write failure is swallowed only after marking backend health down.
6. Collector read failure emits the backend gauge and does not break
   `/metrics`.
7. Malformed Redis keys and values remain nonfatal and mark confidence down.
8. Collector counters, histograms, labels, and special-character escaping
   remain unchanged.
9. Prefork workers retain atomic Redis aggregation without cross-process
   Python state synchronization.
10. The operational collector import through `pipeline.metrics` remains valid.
11. Removing the Ruff exception must expose no S105 violation except the
    explained environment-variable-name line.
12. Task and provider Prometheus recorders use canonical metric definitions
    without facade lookup or injected callables.
13. A generated registry scrape contains one copy of each provider series;
    Redis-backed provider names belong to the collector, while request duration
    remains locally registered.
14. Redis unavailable, read failure, or write failure yields the backend-down
    gauge plus process-local provider series rather than dropping telemetry.
15. Provider counter `HELP`, `TYPE`, and sample names agree without
    `_total_total` metadata.

**r) Tests.**

| Test | Scenarios |
|---|---|
| Fresh-interpreter import test and single-owner test | 1, 2, 10 |
| Backend initialization and parameterized write-failure tests | 3-5 |
| Updated provider Redis aggregation tests | 3, 8, 9, 12 |
| Collector descriptor-ownership, registry-collision, scrape-uniqueness, metadata, fallback, and worker collector tests | 1, 2, 4-8, 10, 13-15 |
| Updated metrics API degradation test | 6 |
| Updated task and provider Prometheus output tests | 3, 12 |
| Existing `tests/*metrics*.py` suite | 3-12 |
| Isolated S105 Ruff command and repository guardrails | 11 |
| Complete Python suite | runtime regression check |

Tests are edited and run red before production or Ruff config changes.

**s) Fakes and mocks.** Existing fake Redis clients remain at the approved
Redis boundary. A fresh-interpreter subprocess proves import safety before
metrics modules enter `sys.modules`. Monkeypatch targets move to
`pipeline.metrics_redis_backend`; no facade, re-export, or metric object is
patched.

**t) Verification rows.** Apply the telemetry/metrics row, guardrail/tooling
row because `ruff.toml` changes, and docs-only row because the remediation
ledger and Full plan change. Run all metrics tests and the complete Python
suite before handoff.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-da-1-collapse-metrics-twins

gh api \
  'repos/prometheus/client_python/contents/prometheus_client/registry.py?ref=v0.19.0' \
  --jq .content | base64 --decode | sed -n '20,75p'
.venv/bin/python - <<'PY'
import inspect
import redis
print(redis.__version__)
for method_name in ("ping", "incrby", "hincrby", "hincrbyfloat"):
    print(method_name, inspect.signature(getattr(redis.Redis, method_name)))
PY
./.venv/bin/ruff check --isolated --select S105 \
  pipeline/metrics_redis_backend.py

PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_provider_metrics_prefork_redis_aggregation.py \
  tests/test_worker_metrics_exporter_provider_series.py \
  tests/test_metrics_api.py tests/test_task_metrics.py

# Tests-first red evidence after test edits.
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_provider_metrics_prefork_redis_aggregation.py \
  tests/test_worker_metrics_exporter_provider_series.py \
  tests/test_metrics_api.py tests/test_task_metrics.py

./.venv/bin/ruff check .
./.venv/bin/ruff check --isolated --select S105 \
  pipeline/metrics_redis_backend.py
./.venv/bin/ruff format --check . --config ruff-format.toml
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_provider_metrics_prefork_redis_aggregation.py \
  tests/test_worker_metrics_exporter_provider_series.py \
  tests/test_metrics_api.py tests/test_task_metrics.py
PYTHONPATH=. .venv/bin/pytest -q tests/*metrics*.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/pytest -q
test -z "$(rg -n 'def _sync_redis_' pipeline)"
test "$(rg -n '^def _redis_incr\(' pipeline | wc -l | tr -d ' ')" -eq 1
test "$(rg -n '^def _redis_hincrby\(' pipeline | wc -l | tr -d ' ')" -eq 1
test "$(rg -n '^def _redis_hincrbyfloat\(' pipeline | wc -l | tr -d ' ')" -eq 1
git diff --check
git status --short
```

Delivery:

```bash
git push -u origin codex/t-da-1-collapse-metrics-twins
gh pr create \
  --base master \
  --head codex/t-da-1-collapse-metrics-twins \
  --title "T-DA-1: Collapse the metrics Redis twins"
```

**v) Rollback.** Revert the T-DA-1 merge commit, rerun Ruff, formatter, Mypy,
focused metrics tests, repository guardrails, docs links, and the complete
suite. No migration, data repair, environment restoration, or external-state
cleanup exists. Rollback restores duplicated process-local state and the
file-wide S105 exception.

**w) Docs sync.**

- Remediation ledger: exact ownership, implementation-plan link, state,
  acceptance evidence, and changelog.
- This Full plan: implementation, review, verification, and delivery evidence.
- Runtime, operations, performance, security, testing, engineering guardrails,
  ADR, architecture review, README, and data-governance docs: no changes
  because runtime behavior and policy remain unchanged.

## 7. Delivery Self-Audit

**x) Antipattern scan, diff pass.** Re-run A-F/H. Reject copied Redis state,
sync functions, facade-private patches, dynamic facade lookup, new adapters,
reset hooks, callable parameters, registration drift, widened Ruff exceptions,
or edits outside the thirteen owned files.

**y) Evidence.** Report every command from 6u with PASS or FAIL, including
baseline evidence, tests-first red result, exact deletion grep, planning and
pre-commit review findings, commit hashes, PR URL, unresolved-thread count,
and final CI state.

Implementation-head evidence: the original focused suite failed 4 tests,
confirming import-time Redis initialization and duplicated facade state.
Successive pre-commit reviews found one registration-collision P1, one
duplicate-series P1, two degraded-export/metadata findings, and two malformed
key/plan-drift P2s. Each received a focused red regression before correction;
final rereview found no remaining P1/P2. Ruff, isolated S105, formatter, Mypy,
76 metrics tests, 388 repository guardrail tests, 2 docs-link tests, and the
complete 1,489-test Python suite pass locally.

**z) Deviations.** Expected result is none. Any additional changed path,
metric contract change, new retry, changed warning policy, new test seam,
unresolved P1/P2, or unrun required check is a blocker.
