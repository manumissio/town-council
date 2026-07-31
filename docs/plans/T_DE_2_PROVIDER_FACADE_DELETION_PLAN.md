# T-DE-2: Delete the Provider Compatibility Facade

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: implementation-ready`
`execution: code`

## 1. Context & Alignment

**a) Driver.** T-DE-1 removed reverse dependencies from the provider
implementations but intentionally retained `pipeline/llm_provider.py` as a
compatibility facade. The facade now contains only re-exports. Deleting it
completes the provider-boundary cleanup, makes the contract and adapter owners
directly visible, and removes a test patch surface that the accepted G3 policy
no longer protects.

**b) Canonical documents consulted.**

- `AGENTS.md` hierarchy, known-antipattern, workflow, verification, and
  reporting sections require direct implementation imports, tests at approved
  provider boundaries, complete verification, and no compatibility alias.
- `docs/TESTING.MD` requires provider fakes to implement
  `pipeline/inference_provider_contract.py` and forbids preserving facade patch
  targets.
- `docs/ENGINEERING_GUARDRAILS.md` makes helper-to-facade import direction a
  structural rule and requires removal of obsolete registrations.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` registers T-DE-2 after T-DE-1
  and freezes runtime policy, retries, timeouts, telemetry, model selection,
  and fallback behavior.
- `ARCHITECTURE.md` and `docs/PIPELINE.md` currently describe the transitional
  compatibility facade and must describe the direct contract/adapter boundary
  after deletion.
- `docs/ADR.md` records the historical facade-preservation decision and the
  later accepted G3 rule that test patch points are not public API. A new dated
  entry records the deliberate completion of that transition without rewriting
  historical decisions.

**c) Remediation alignment.** This is T-DE-2 in the DEDUP-E lane. Its exact
`files_owned` set is:

- `docs/plans/T_DE_2_PROVIDER_FACADE_DELETION_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `pipeline/llm_provider.py` (delete)
- `pipeline/llm.py`
- `pipeline/local_ai_runtime.py`
- `pipeline/local_ai_provider_calls.py`
- `tests/test_http_provider_operation_timeout_selection.py`
- `tests/test_inference_provider_protocol_contract.py`
- `tests/test_task_provider_retry_semantics.py`
- `tests/test_provider_error_mapping_retry_vs_fallback.py`
- `tests/test_pipeline_batching.py`
- `tests/test_agenda_segmentation_llm_proclamation_noise_rejection.py`
- `tests/test_agenda_segmentation_mode_switch.py`
- `tests/test_ai_logic.py`
- `tests/test_extract_agenda_prompt_budget.py`
- `tests/test_final_polish.py`
- `tests/test_llm_backend_parity_agenda_segmentation.py`
- `tests/test_llm_backend_parity_grounding.py`
- `tests/test_llm_backend_parity_summary.py`
- `tests/test_repository_guardrails.py`
- `AGENTS.md`
- `ARCHITECTURE.md`
- `docs/PIPELINE.md`
- `docs/ADR.md`

This plan grants DEDUP-E narrow coordination over GOV-owned canonical docs and
the structural guardrail test only for removing the provider-facade contract.
No other task may modify these paths concurrently.

**d) Decision gates.** G3 is satisfied by T-GOV-1 and explicitly authorizes
repointing tests away from compatibility facades. G1, G2, G4, and G5 are
unaffected. No open decision gate blocks T-DE-2.

## 2. Design

**e) Step-by-step approach.**

1. Add characterization assertions before deletion: direct adapters satisfy
   `InferenceProvider`; LocalAI selects the same adapter classes; typed errors
   retain their fallback/retry behavior; and the compatibility module still
   exists before the change.
2. Add a failing structural guardrail that requires
   `pipeline/llm_provider.py` to be absent and rejects imports of
   `pipeline.llm_provider` from tracked Python files.
3. Repoint production imports by owner:
   - `pipeline/llm.py` imports HTTP and in-process adapters from their modules
     and typed failures from `pipeline/inference_provider_contract.py`.
   - `pipeline/local_ai_runtime.py` imports each adapter from its owner.
   - `pipeline/local_ai_provider_calls.py` imports typed failures from the
     contract owner.
4. Remove the provider-class aliases from `pipeline.llm`; they are historical
   test seams rather than product-policy API. Repoint tests to the adapter
   owners and replace facade-preservation assertions with direct contract and
   adapter identity assertions. Do not add a new compatibility module or alias.
5. Delete `pipeline/llm_provider.py`.
6. Remove obsolete helper-to-facade registrations from
   `HELPER_FACADE_IMPORT_RULES`; the repository-wide deletion guardrail becomes
   the enduring contract.
7. Update the inference verification row and architecture maps to name the
   contract and adapter owners directly.
8. Append an ADR entry recording that T-DE-2 supersedes the compatibility
   portion of the 2026-07-20 provider-boundary decision while preserving its
   transport and policy allocations.
9. Mark T-DE-2 complete only after targeted, guardrail, coverage, and complete
   suite verification succeeds.

No new production function or module is created. The only new test logic uses
the existing `_tracked_files()` and `_forbidden_imports()` helpers.

**f) Reuse audit.** Reuse `pipeline/inference_provider_contract.py` as the
single protocol/error owner, `pipeline/http_inference_provider.py` and
`pipeline/inprocess_inference_provider.py` as adapter owners, and
`pipeline/llm.py` as the product-policy boundary. The deleted facade is the
older stratum; nothing replaces it.

**g) Data contracts.** `InferenceProvider`, provider operation constants,
response-field constants, and typed provider errors remain unchanged in
`pipeline/inference_provider_contract.py`. Adapter classes retain their
existing constructors and methods. No raw-dict or new typed contract is added.
Imports of `pipeline.llm_provider` and provider classes re-exported from
`pipeline.llm` intentionally stop working. This is the authorized compatibility
break that deletes the obsolete facade; tracked callers are migrated atomically.

**h) Schema and migrations.** None.

## 3. Security & Data Governance

**i) Security boundary.** No `AGENTS.md` security-sensitive path changes.
Provider endpoint selection, request transport, credentials, retry behavior,
and fail-fast policy are unchanged. An attacker gains no new capability.

**j) Secrets.** No credential, key, environment variable, or default changes.

**k) Person data.** No person entity, roster, people metadata, or publication
behavior changes. G4 remains satisfied.

**l) Untrusted input.** Provider responses remain validated by the existing
HTTP and in-process adapters. This task changes import ownership only and adds
no new parsing or rendering boundary.

## 4. Code Health

**m) GED conformance sweep.** Production edits are import-only plus one file
deletion. No function, nesting, parameter, timestamp, error handler,
environment read, or runtime literal changes. Names continue to use provider
domain vocabulary.

**n) Antipattern scan, plan pass.**

- A1/H1: no external API call changes; installed provider APIs are untouched.
- B1/B2/C1: the facade is deleted without a replacement wrapper, alias, or
  compatibility path.
- C2/D2: tests repoint to implementation owners and the approved provider
  boundary; no test seam is added.
- D1/D3: behavior assertions remain; only obsolete facade-identity assertions
  are replaced by direct owner and deletion contracts.
- E1/E2: only owned import lines, canonical map entries, and task records
  change.
- F1/F2: no implementation is copied; each symbol keeps one owner.
- A2-A4, B3, D2, E3, H2-H4: no planned violation.

**o) Ratchet interaction.** Three helper-to-facade entries become obsolete and
are removed from `HELPER_FACADE_IMPORT_RULES`. No Ruff selector, BLE001
boundary, formatter scope, Mypy scope, or coverage threshold changes.

**p) Dead code and duplication audit.** Delete the 46-line facade and its
facade-only tests. Replace imports in place. Expected production net is about
minus 46 lines; test/docs additions make the review contract explicit without
adding runtime machinery.

## 5. Testing

**q) Edge and failure scenarios.**

1. HTTP backend selection still constructs `HttpInferenceProvider`.
2. In-process backend selection still constructs `InProcessLlamaProvider`.
3. Unknown backend still normalizes to HTTP.
4. Provider response errors still trigger deterministic agenda fallback or
   return `None` for operations whose established contract does so.
5. Provider timeout/unavailable errors retain retry/fail-soft behavior.
6. Operation-specific timeout selection remains unchanged.
7. Direct adapters still satisfy the runtime-checkable protocol.
8. No tracked Python file imports the deleted facade.
9. The deleted path cannot be restored unnoticed.
10. Local-first defaults, runtime profiles, and model policy remain unchanged.

**r) Test mapping.**

| Tests | Scenarios |
|---|---|
| `tests/test_inference_provider_protocol_contract.py` | 1-3, 7, 10 |
| `tests/test_provider_error_mapping_retry_vs_fallback.py` | 4, 5 |
| `tests/test_task_provider_retry_semantics.py` | 4, 5 |
| `tests/test_http_provider_operation_timeout_selection.py` | 6 |
| `tests/test_repository_guardrails.py` | 8, 9 |
| `tests/test_pipeline_batching.py` | 4, 10 |
| Backend parity and direct LocalAI behavior suites | 1-5, 10 |
| Existing runtime-profile suite | 1-3, 10 |

Write and run the deletion guardrail red before deleting the facade. Existing
behavior tests characterize the runtime contract before imports move.

**s) Fakes and mocks.** Existing tests use provider fakes implementing the
approved inference boundary and patch `pipeline.llm.get_runtime_provider`,
where the name is looked up. No facade/re-export patch or new fake boundary is
introduced.

**t) Verification rows.** Apply the inference backend/provider/policy,
guardrail/tooling, and docs-only rows. Run the coverage gate because production
files change, then the complete Python suite because the provider boundary is
cross-cutting.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git switch -c codex/t-de-2-provider-facade-deletion origin/master

PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_inference_provider_protocol_contract.py \
  tests/test_provider_error_mapping_retry_vs_fallback.py \
  tests/test_task_provider_retry_semantics.py \
  tests/test_http_provider_operation_timeout_selection.py \
  tests/test_pipeline_batching.py

# Expected red after adding the deletion contract and before implementation.
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_repository_guardrails.py::test_provider_compatibility_facade_is_deleted

./.venv/bin/ruff check .
./.venv/bin/ruff format --check . --config ruff-format.toml
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_inference_provider_protocol_contract.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_provider_error_mapping_retry_vs_fallback.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_llm_backend_parity_*.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_runtime_profiles_defaults.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_task_provider_retry_semantics.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_http_provider_operation_timeout_selection.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_pipeline_batching.py
PYTHONPATH=. .venv/bin/python -m pytest -q --cov \
  --cov-config=.coveragerc \
  --cov-report=term-missing:skip-covered \
  tests/
PYTHONPATH=. .venv/bin/pytest -q
git diff --check
git status --short
```

Run an independent planning review before implementation and a fresh
pre-commit code review after verification. Resolve every eligible P1/P2 and
rerun affected commands.

**v) Rollback.** Revert the T-DE-2 merge commit. This restores the facade and
its imports atomically. Rerun the inference, guardrail, docs-link, coverage,
and complete-suite commands above. No migration, data repair, cache purge, or
external-state restoration is required.

**w) Docs synchronization.**

- `AGENTS.md`: replace the deleted facade in the inference verification scope.
- `ARCHITECTURE.md`: remove provider import-compatibility ownership and name
  direct contract/adapter owners.
- `docs/PIPELINE.md`: remove the compatibility module from core modules and
  source-of-truth map.
- `docs/ADR.md`: append the T-DE-2 supersession decision; preserve history.
- Remediation ledger and this task plan: exact ownership, completion evidence,
  and remaining task list.
- README, operations, performance, security, data governance, roadmap, and API
  contracts: no update because runtime behavior and operator commands do not
  change.

## 7. Delivery Self-Audit

**x) Diff scan.** Re-run A-F/H. Reject a new provider re-export, compatibility
alias, policy/retry/default change, facade patch target, copied provider
implementation, unrelated formatting, widened ignore, or file outside the
owned set.

**y) Evidence.** Report the characterization baseline, tests-first red result,
all commands in 6u, exact pass/fail counts, planning-review findings,
pre-commit-review findings, applied fixes, commit hashes, PR URL, unresolved
threads, and final CI state. Mark anything unrun `NOT VERIFIED`.

**z) Deviations.** Expected deviation report is `None`. Any extra path,
behavior change, policy change, skipped review, unresolved P1/P2, or unrun
required check blocks delivery.
