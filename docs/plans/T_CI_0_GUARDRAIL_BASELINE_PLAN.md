---
title: "T-CI-0: Restore the Python Guardrail Baseline"
date: 2026-07-20
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: operator-approved-plan
execution: code
---

# T-CI-0: Restore the Python Guardrail Baseline

## Goal Capsule

- **Objective:** Restore a green Python guardrail baseline before T-CI-5, T-CI-1, or Phase 2 remediation work begins.
- **Authority:** Code and tests define current behavior; `AGENTS.md`, `docs/ENGINEERING_GUARDRAILS.md`, and `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` constrain implementation and verification.
- **Execution profile:** One documentation registration unit followed by independent contract-test and SQLAlchemy-typing units, then integrated verification and delivery.
- **Stop conditions:** Stop if a correction needs a tracked file outside this task's five-file ownership set, changes Ruff policy, depends on G1-G5, or alters runtime behavior.
- **Tail ownership:** The implementation owner runs simplification, review, full verification, PR delivery, and bounded CI repair.

---

## Product Contract

### Summary

The repository currently fails four Python contract tests and the GitHub Actions Mypy gate when `pgvector` is installed. T-CI-0 realigns stale tests with already-landed dependency and Ruff policy changes and corrects the common SQLAlchemy datatype annotation so both installed and fallback vector implementations type-check.

### Problem Frame

A red default branch makes later remediation results unreliable. The four pytest failures are stale contract expectations, while the Mypy failure comes from annotating the selected vector constructor as a `TypeDecorator` class even though pgvector's `Vector` is a `UserDefinedType`. Both constructors return SQLAlchemy `TypeEngine` instances.

### Requirements

- R1. Register T-CI-0 before T-CI-5 and T-CI-1 with an exclusive five-file ownership set.
- R2. Require the current `pypdf==6.13.3` batch dependency without changing requirements files.
- R3. Require the current Ruff source roots and selected rule families without changing `ruff.toml`.
- R4. Keep the exact BLE001 boundary inventory aligned with current non-wildcard Ruff entries.
- R5. Preserve the formatter transition: documentation owns the config-driven `ruff format --check .` command while CI retains its explicit list until T-CI-4.
- R6. Type `VECTOR_COLUMN_TYPE` as the dimension constructor shared by pgvector `Vector` and `FallbackVector`, returning SQLAlchemy's common `TypeEngine` base.
- R7. Preserve ORM metadata, vector dimension construction, runtime fallback behavior, defaults, and public contracts.
- R8. Produce fresh targeted, guardrail-row, database, docs-link, full-suite, and CI evidence.

### Scope Boundaries

Only these tracked files may change:

- `docs/plans/T_CI_0_GUARDRAIL_BASELINE_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `pipeline/model_base.py`
- `tests/test_repository_guardrails.py`
- `tests/test_docker_build_contracts.py`

No workflow, Ruff configuration, dependency, schema, migration, API, Celery, security boundary, runtime default, or soak policy changes are included.

### Acceptance Examples

- AE1. With a pgvector type stub whose `Vector` extends `UserDefinedType`, Mypy accepts `pipeline/model_base.py`.
- AE2. Without pgvector installed, existing database tests construct the fallback datatype and preserve ORM behavior.
- AE3. Guardrail tests compare their expectations to the current Ruff configuration and pass without weakening exact-set assertions.
- AE4. The complete Python suite passes from the branch before delivery.

---

## Planning Contract

### Key Technical Decisions

- KTD1. Add T-CI-0 as a distinct prerequisite task. (session-settled: user-approved — chosen over expanding unrelated remediation tasks: the red baseline and exclusive ownership deadlock require a bounded repair lane.)
- KTD2. Annotate the selector as `Callable[[int], TypeEngine[object | None]]`. (review-corrected — the initially approved `type[TypeEngine[object | None]]` accepts both concrete classes but rejects the existing `VECTOR_COLUMN_TYPE(384)` call under full Mypy. The callable contract preserves that constructor use without casts or ignores.)
- KTD3. Correct stale assertions without changing their strictness. (session-settled: user-directed — chosen over skipping, weakening, or widening tests: this task restores the baseline rather than lowering it.)
- KTD4. Keep the current formatter transition explicit. Documentation may advertise the config-owned command while the workflow list remains transitional until T-CI-4.

### Reuse Audit

The change extends existing guardrail tests and the existing vector datatype selector. One test-local predicate distinguishes configured or inline BLE001 approvals from handlers that propagate or terminate; no production helper, registry, compatibility alias, test seam, or parallel implementation is introduced. `ruff.toml` remains the policy source.

### Security and Data Governance

No security-sensitive path, secret, person data, scraped content parser, or external trust boundary changes. No attacker capability changes.

### Implementation Constraints

- Preserve the existing optional-pgvector import boundary and fallback implementation.
- Add no Ruff exception or type suppression.
- Use existing exact-set comparisons for policy inventory.
- Do not edit tracked files outside the ownership set.
- Run the antipattern checklist before and after implementation; any positive result must be corrected or reported.

### Sequencing

1. U1 registers the task and ownership boundary.
2. U2 and U3 may proceed independently after U1.
3. U4 integrates, reviews, verifies, commits, pushes, opens the PR, and observes CI.

---

## Implementation Units

### U1. Register T-CI-0

- **Goal:** Make T-CI-0 an implementation-ready prerequisite in the active remediation plan.
- **Requirements:** R1
- **Files:** `docs/plans/T_CI_0_GUARDRAIL_BASELINE_PLAN.md`, `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- **Approach:** Add ownership, acceptance, verification, dependencies, and execution order; replace T-CI-1's stale test-file count with all tests under `tests/`.
- **Test scenarios:** Documentation links resolve and no decision gate is silently resolved.
- **Verification:** `PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py`

### U2. Realign guardrail contracts

- **Goal:** Make contract tests assert the already-landed dependency and Ruff policy accurately.
- **Requirements:** R2, R3, R4, R5
- **Files:** `tests/test_repository_guardrails.py`, `tests/test_docker_build_contracts.py`
- **Approach:** Update the pypdf pin, Ruff roots/rules, exact BLE001 set, and formatter-transition assertions in place. Keep the broad-handler contract strict by accepting only configured or inline approvals and handlers that explicitly propagate or terminate.
- **Test scenarios:** Current dependency pin, Ruff policy drift, exact BLE001 drift, and transitional formatter ownership.
- **Verification:** Targeted contract tests plus complete guardrail and Docker contract files.

### U3. Correct vector datatype typing

- **Goal:** Accept both pgvector and fallback SQLAlchemy datatype classes without changing runtime selection.
- **Requirements:** R6, R7
- **Files:** `pipeline/model_base.py`
- **Approach:** Import `Callable` and `TypeEngine`, then type the selector as the existing one-argument vector constructor returning the common datatype base.
- **Test scenarios:** Pgvector-present Mypy stub, local Mypy, fallback database tests, and vector construction.
- **Verification:** Deterministic pgvector stub Mypy check, repo Mypy, and `tests/test_database.py`.

### U4. Integrate and deliver

- **Goal:** Prove the restored baseline and deliver one reviewable PR.
- **Requirements:** R8
- **Files:** No additional tracked files.
- **Approach:** Run simplification and plan-aware review, apply eligible fixes within ownership, run all verification, audit the diff, commit atomically, push, open the PR, and watch CI to a decided state.
- **Test scenarios:** Cross-unit integration, full Python regression sweep, clean diff, and CI parity.
- **Verification:** Every command in the Verification Contract.

---

## Verification Contract

| Scope | Command | Done signal |
|---|---|---|
| Original pytest defect | `PYTHONPATH=. .venv/bin/pytest -q tests/test_docker_build_contracts.py::test_worker_live_and_batch_requirements_split_table_stack_only tests/test_repository_guardrails.py::test_ruff_guardrail_config_keeps_scope_and_exceptions_narrow tests/test_repository_guardrails.py::test_first_formatter_wave_stays_path_scoped_and_enforced tests/test_repository_guardrails.py::test_broad_exception_allowlist_stays_explicit` | Four targeted tests pass |
| Pgvector-present typing | Create the approved temporary `MYPYPATH` pgvector stub and run `.venv/bin/mypy` | The full typed subtree exits 0 |
| Ruff policy | `./.venv/bin/ruff check .` | Exit 0 |
| Python lint row | `./.venv/bin/ruff check api pipeline scripts tests` | Exit 0 |
| Typed subtree | `./.venv/bin/mypy` | Exit 0 |
| Guardrail contracts | `PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py` | File passes |
| Docker contracts | `PYTHONPATH=. .venv/bin/pytest -q tests/test_docker_build_contracts.py` | File passes |
| ORM behavior | `PYTHONPATH=. .venv/bin/pytest -q tests/test_database.py` | File passes |
| Documentation | `PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py` | File passes |
| Full regression | `PYTHONPATH=. .venv/bin/pytest -q` | Complete suite passes |
| Diff hygiene | `git diff --check` | Exit 0 |
| Remote gate | GitHub Actions Python Guardrails job | Passes on PR head |

No fake patches a production implementation. The temporary pgvector stub is isolated Mypy input and is removed after the command.

---

## Definition of Done

- T-CI-0 is registered before dependent remediation work with exactly the approved ownership set.
- All four original pytest failures pass without skips, weakened assertions, or changed policy.
- Pgvector-present and pgvector-absent paths both type-check or execute through their existing contracts.
- Runtime behavior, schemas, dependencies, workflows, Ruff policy, defaults, and decision gates remain unchanged.
- Simplification and plan-aware review find no unresolved eligible issue.
- Every Verification Contract command and PR CI pass with fresh evidence.
- The diff contains no abandoned experiment, duplicate implementation, compatibility shim, type suppression, unrelated formatting, or personal path.
- The final report names exact commands, PASS or FAIL outcomes, changed paths, tree state, and review findings. The expected deviation report records the review-required constructor-callable correction from the initially approved class annotation; no other deviation is expected.
