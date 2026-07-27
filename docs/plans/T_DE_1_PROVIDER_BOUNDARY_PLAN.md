# T-DE-1: Remove Reverse Provider-Facade Dependencies

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: implementation-ready`
`execution: code`

## 1. Context & Alignment

**a) Driver.** The current remediation entry incorrectly treats HTTP retry and
telemetry policy as duplicated across both inference adapters. Current code
shows that HTTP retry orchestration is already isolated in
`pipeline/http_inference_attempts.py`, while the in-process adapter has no retry
loop and instead owns model locking and reset behavior. The actual defect is
that HTTP transport and telemetry implementations import backward through
`pipeline/llm_provider.py`, preserving a test-driven facade cycle. T-DE-1 must
remove those reverse imports without changing inference behavior.

**b) Canonical documents consulted.**

- `AGENTS.md` `<known_antipatterns>`, `<workflow_contract>`, and
  `<verification_matrix>` prohibit test-seam re-exports, require implementation
  patch targets, and define the inference verification row.
- `docs/TESTING.MD` "The core rule" and "Patch-target rules" require tests to
  fake the inference and outbound-HTTP boundaries at implementation modules.
- `docs/ADR.md` "Test patch points are not a public API" authorizes the
  domain-scoped removal of test-only facade seams while preserving runtime
  import contracts not explicitly retired.
- `docs/ADR.md` "Split inference provider implementation behind the existing
  facade" remains historical context. G3 supersedes its test-patch preservation
  clauses, but not its runtime import compatibility decision.
- `docs/reviews/architecture-review-2026-07-19.html` Candidate 04 requires
  reverse-facade removal and explicitly rejects moving HTTP retry policy into
  the shared contract.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` assigns T-DE-1 to the DEDUP-E
  lane and requires provider failure mapping to remain unchanged.

**c) Remediation alignment.** Revise T-DE-1 and own exactly:

- `docs/plans/T_DE_1_PROVIDER_BOUNDARY_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `ARCHITECTURE.md`
- `docs/PIPELINE.md`
- `pipeline/http_inference_provider.py`
- `pipeline/llm_provider.py`
- `pipeline/provider_telemetry.py`
- `pipeline/agenda_segmentation_maintenance.py`
- `tests/test_inference_provider_protocol_contract.py`
- `tests/test_http_provider_telemetry_metrics.py`
- `tests/test_http_provider_operation_retry_budgets.py`
- `tests/test_http_provider_ttft_tps_computation.py`
- `tests/test_http_provider_token_metrics_parsing.py`
- `tests/test_hydrate_repaired_city_catalogs.py`

`pipeline/http_inference_attempts.py`, `pipeline/inprocess_inference_provider.py`, and
`pipeline/inference_provider_contract.py` are read-only in this task. The facade
retains provider class, protocol, operation-label, response-field, and typed
error imports. Its config, `requests`, and metric-recorder exports are
test-only rebinding seams and are removed. Deleting the tracked facade file
remains outside this task and requires separate operator authorization.

**d) Decision gates.** G3 is accepted and authorizes domain-scoped test seam
removal. No open G1-G5 gate is required or foreclosed. Runtime defaults, retry
budgets, timeout values, fail-fast policy, error mapping, and soak comparability
remain unchanged.

## 2. Design

**e) Step-by-step approach.**

1. Record T-DC-1 as complete and replace the stale T-DE-1 ledger entry with
   this corrected scope.
2. Add failing tests before implementation:
   - provider construction reads configuration from
     `pipeline.http_inference_provider`;
   - outbound HTTP patches target `pipeline.http_inference_provider.requests`;
   - metric patches target `pipeline.provider_telemetry`;
   - in-process success and failure still emit request metrics through the
     telemetry implementation owner;
   - maintenance timeout overrides change the HTTP implementation owner;
   - provider implementation modules do not import `pipeline.llm_provider`.
3. In `pipeline/http_inference_provider.py`, import HTTP configuration directly
   from `pipeline.config`, use its direct `requests` import, and remove
   `_provider_facade()`.
4. In `pipeline/provider_telemetry.py`, import provider metric recorders
   directly from `pipeline.metrics` and remove `_provider_facade()`.
5. In `pipeline/agenda_segmentation_maintenance.py`, apply temporary timeout
   overrides to `pipeline.http_inference_provider`, where provider instances now
   read the values. Preserve provider reset and restoration behavior.
6. In `pipeline/llm_provider.py`, remove config, `requests`, and metric-recorder
   re-exports that existed only for facade patching. Preserve provider classes,
   protocol symbols, operation labels, response fields, and typed errors.
7. Repoint affected tests from `pipeline.llm_provider` patches to the modules
   where names are looked up. Preserve the provider-class facade identity test
   because that runtime import compatibility is not retired here.
8. Update architecture and pipeline docs to state that HTTP retries remain
   transport-local and implementation modules do not import through the
   compatibility facade.
9. Run simplification, independent pre-commit review, all verification gates,
   atomic commits, PR review, and CI watch.

No new production function or module is introduced.

**f) Reuse audit.** Reuse `pipeline.http_inference_attempts` for HTTP retry
orchestration, `pipeline.inference_provider_contract` for typed errors and the
provider protocol, `pipeline.provider_telemetry` for telemetry formatting, and
`pipeline.metrics` for metric recording. No retry helper, adapter base class,
registry, wrapper, or alternate contract is added.

Rejected alternatives:

- Move retry policy into `inference_provider_contract.py`: rejected because
  retry is HTTP transport policy and the in-process adapter intentionally has
  different locking/reset behavior.
- Delete `pipeline/llm_provider.py`: rejected because provider class, protocol,
  operation-label, response-field, and typed-error imports remain runtime
  compatibility contracts, and tracked-file deletion requires separate
  operator authorization. Test-only config, HTTP client, and metric re-exports
  are removed instead.
- Leave maintenance overrides on the facade: rejected because direct
  implementation configuration would make those overrides inert.
- Preserve facade patch targets with synchronization: rejected by G3 and the
  repository's known-antipattern rules.

**g) Data contracts.** The existing `InferenceProvider` protocol and typed
provider errors remain unchanged. Telemetry dataclasses and metric labels remain
unchanged. No raw-dictionary contract, API payload, Celery signature, CLI, or
environment variable changes. Import compatibility narrows only by removing
test-only config, `requests`, and metric-recorder facade names.

**h) Schema/migration impact.** None.

## 3. Security & Data Governance

**i) Security boundary.** No `AGENTS.md` security-sensitive path changes.
Outbound inference remains local-first and uses the same configured base URL,
timeouts, typed failures, and fail-fast behavior.

**j) Secrets.** No credential, key, environment default, or log field changes.

**k) Person data.** No person-level data is created, linked, aggregated, or
exposed.

**l) Untrusted input.** Provider HTTP responses remain parsed at the existing
HTTP payload boundary. This task changes import ownership only, not response
validation or rendering.

## 4. Code Health

**m) Conformance.** Removing `_provider_facade()` eliminates dependency
rebinding and backward imports. No new nesting, broad exception, timestamp,
environment read, or magic policy value is added. Existing configuration
constants continue to come from `pipeline.config`.

**n) Antipattern scan, plan pass.**

- A1/H1: no external API changes; current `requests` and pytest monkeypatch
  behavior are already exercised by installed tests.
- B1/F1: no new abstraction or duplicate retry implementation.
- B2/C1/C2: the old facade patch path is removed from implementation tests; no
  synchronization or compatibility shim replaces it.
- D1-D3: assertions remain behavioral; the unchanged error-mapping suite guards
  retry and fallback semantics.
- E1-E3: edits remain within the owned provider family, tests, and canonical
  docs.
- A2-A4, B3, F2, H2-H4: no planned violations.

**o) Ratchet interaction.** No Ruff selector, BLE001 boundary, type-check scope,
coverage threshold, runtime gate, or soak policy changes. T-GOV-3B may later
register the now-clean dependency direction.

**p) Dead code and duplication audit.** Delete two `_provider_facade()`
functions, their `ModuleType` imports, test patches that rely on the facade as a
rebinding seam, and the facade's config, HTTP-client, and metric-recorder
re-exports. Keep one provider-class facade identity assertion for active runtime
import compatibility. Expected production delta is negative.

## 5. Testing

**q) Edge and failure scenarios.**

1. HTTP provider configuration changes at its implementation owner are applied
   to newly constructed providers.
2. HTTP request fakes at the outbound HTTP call site affect generation and
   health checks.
3. Metric recorder fakes at the telemetry owner receive request, retry,
   timeout, TTFT, TPS, and token events.
4. Conservative profiles remain one-shot and balanced profiles retain their
   retry budget.
5. Provider response, timeout, unavailable, and fallback mappings remain
   unchanged.
6. Temporary segment and summary timeout overrides affect only the context and
   restore prior values and provider state afterward.
7. In-process locking/reset behavior remains unchanged.
8. In-process success and failure continue to emit provider request telemetry.
9. The implementation modules do not import the compatibility facade.
10. Existing callers importing provider classes and errors through
   `pipeline.llm_provider` remain compatible.
11. Removed config, HTTP-client, and metric-recorder facade names are absent
    rather than inert.

**r) Test mapping.**

| Tests | Scenarios |
|---|---|
| `test_inference_provider_protocol_contract.py` | 1, 2, 7-11 |
| `test_http_provider_telemetry_metrics.py` | 2-5 |
| `test_http_provider_operation_retry_budgets.py` | 2, 4, 5 |
| `test_http_provider_ttft_tps_computation.py` | 2, 3 |
| `test_http_provider_token_metrics_parsing.py` | 2, 3 |
| `test_hydrate_repaired_city_catalogs.py` | 6 |
| Unchanged `test_provider_error_mapping_retry_vs_fallback.py` | 4, 5 |
| Unchanged in-process protocol tests | 7 |
| Complete Python suite and coverage gate | 1-11 |

**s) Fakes and mocks.** Outbound HTTP is patched at
`pipeline.http_inference_provider.requests`, the approved outbound-HTTP
boundary. Provider metrics are patched where looked up in
`pipeline.provider_telemetry`. No facade, re-export, private sequence, or
unapproved boundary is patched.

**t) Verification rows.** Apply the inference backend/provider/policy row and
docs-only row. Run focused telemetry and maintenance tests, Ruff, Mypy,
coverage, and the complete Python suite because the change crosses provider,
telemetry, and maintenance boundaries.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-de-1-provider-boundary
```

Tests-first evidence:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_inference_provider_protocol_contract.py \
  tests/test_http_provider_telemetry_metrics.py \
  tests/test_http_provider_operation_retry_budgets.py \
  tests/test_http_provider_ttft_tps_computation.py \
  tests/test_http_provider_token_metrics_parsing.py \
  tests/test_hydrate_repaired_city_catalogs.py
```

Final verification:

```bash
./.venv/bin/ruff check .
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_inference_provider_protocol_contract.py \
  tests/test_provider_error_mapping_retry_vs_fallback.py \
  tests/test_llm_backend_parity_*.py \
  tests/test_runtime_profiles_defaults.py
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_http_provider_telemetry_metrics.py \
  tests/test_http_provider_operation_retry_budgets.py \
  tests/test_http_provider_operation_timeout_selection.py \
  tests/test_http_provider_ttft_tps_computation.py \
  tests/test_http_provider_token_metrics_parsing.py \
  tests/test_hydrate_repaired_city_catalogs.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/python -m pytest -q --cov \
  --cov-config=.coveragerc \
  --cov-report=term-missing:skip-covered \
  tests/
PYTHONPATH=. .venv/bin/pytest -q
git diff --check
git status --short
```

Delivery uses two commits:

1. `docs(remediation): correct T-DE-1 provider ownership`
2. `refactor(inference): remove reverse provider facade imports`

Push `codex/t-de-1-provider-boundary`, open one PR, request Codex review, and
watch required CI and review threads to a decided state.

**v) Rollback.** Revert the T-DE-1 merge commit and rerun the inference,
telemetry, maintenance, docs-link, coverage, and complete-suite commands. No
migration, data repair, environment rollback, or external-state cleanup exists.
Rollback knowingly restores test-driven reverse facade imports.

**w) Docs synchronization.**

- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`: close T-DC-1, activate corrected
  T-DE-1, and replace the false shared-retry premise.
- `ARCHITECTURE.md`: document provider dependency direction and transport-local
  retry ownership.
- `docs/PIPELINE.md`: distinguish the runtime compatibility facade from
  implementation patch and configuration owners.
- `AGENTS.md`, README, ADR, operations, performance, security, and data
  governance: no change.

## 7. Delivery Self-Audit

**x) Diff scan.** Re-run A-F/H. Reject retry-policy movement, new provider
abstractions, facade synchronization, runtime default changes, error-map drift,
metrics-label drift, unowned files, weakened tests, type suppression, or
unrelated formatting.

**y) Evidence required.** Report the tests-first failure, every command from
6u with PASS/FAIL, exact suite counts, coverage result, independent planning
and pre-commit findings, commit hashes, PR URL, unresolved-thread count, and CI
state. Browser testing is not applicable because no UI path changes.

**z) Deviations.** Expected deviations from remediation plan v3.64 are the
corrected T-DE-1 premise and expanded ownership. Any tracked-file deletion,
runtime import break, retry/timeout/model-policy change, added dependency,
skipped review, unresolved P1/P2, or unrun required check is a blocker.
