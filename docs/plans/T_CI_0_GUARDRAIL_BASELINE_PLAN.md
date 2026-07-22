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
- **Stop conditions:** Stop if a correction needs a tracked file outside this task's eleven-file ownership set, broadens effective Ruff policy beyond the structural contract below, depends on G1-G5, or alters runtime behavior beyond preserving the existing batch-failure exit contract with `SystemExit`.
- **Tail ownership:** The implementation owner runs simplification, review, full verification, PR delivery, and bounded CI repair.

---

## Product Contract

### Summary

The repository currently fails four Python contract tests and the GitHub Actions Mypy gate when `pgvector` is installed. T-CI-0 realigns stale tests with already-landed dependency and Ruff policy changes and corrects the common SQLAlchemy datatype annotation so both installed and fallback vector implementations type-check.

### Problem Frame

A red default branch makes later remediation results unreliable. The four pytest failures are stale contract expectations, while the Mypy failure comes from annotating the selected vector constructor as a `TypeDecorator` class even though pgvector's `Vector` is a `UserDefinedType`. Both constructors return SQLAlchemy `TypeEngine` instances. Ruff also tolerates missing delimiters between valid rule codes, so directives such as `# noqa: BLE001F401` suppress BLE001 with a warning; the first token-aware predicate missed that form.

PR #108 review found a second guardrail defect: `_broad_exception_handler_is_approved` checks only the handler's final AST statement. A conditional or unconditional early `return`, generator suspension, or unreachable terminal `raise` can therefore pass while still swallowing the broad exception. Treating `sys.exit()` as terminal is also unsafe static policy because the name can be rebound. The correction is a conservative structural contract, not semantic control-flow proof. Later review found that an adjacent plain `# noqa` can evade the comment scanner and that Ruff-discovered crawler, semantic-service, and repository-root Python changes do not all trigger the guardrail workflow.

### Requirements

- R1. Register T-CI-0 before T-CI-5 and T-CI-1 with an exclusive eleven-file ownership set.
- R2. Require the current `pypdf==6.13.3` batch dependency without changing requirements files.
- R3. Preserve the current Ruff source roots, selected rule families, and effective exception boundary while centralizing the existing task-startup suppression in `ruff.toml`.
- R4. Keep the exact BLE001 boundary inventory aligned with current non-wildcard Ruff entries.
- R5. Preserve the formatter transition: documentation owns the config-driven `ruff format --check .` command while CI retains its explicit list until T-CI-4.
- R6. Type `VECTOR_COLUMN_TYPE` as the dimension constructor shared by pgvector `Vector` and `FallbackVector`, returning SQLAlchemy's common `TypeEngine` base.
- R7. Preserve ORM metadata, vector dimension construction, runtime fallback behavior, defaults, and public contracts.
- R8. Produce fresh targeted, guardrail-row, database, docs-link, full-suite, and CI evidence.
- R9. Keep broad-exception suppressions in Ruff's centralized boundary inventory and reject inline `BLE001` suppressions.
- R10. Reject every documented or Ruff-tolerated comment directive that can bypass centralized BLE001 policy: bare or rule-specific line-level `noqa`, bare or rule-specific file-level `ruff: noqa`, legacy file-level `flake8: noqa`, and delimiter-free joined rule codes.
- R11. Permit unlisted broad handlers only when they use a flat sequence of simple assignments or direct action calls followed by `raise`; approved Ruff boundary files remain exempt from this structural restriction.
- R12. Reject compound flow, suspension, early exits, nested definitions, nested exception handling, and `sys.exit()` in unlisted broad handlers.
- R13. Preserve the batch enrichment failure contract by replacing its direct `sys.exit(1)` terminal action with chained `SystemExit`, verifying the same contextual log and exit status, and leaving the existing metrics call before termination.
- R14. Require explicit exception translations to use chaining and apply the broad-handler scan to the Python files Ruff actually discovers for `ruff check .`.
- R15. Detect Ruff-accepted adjacent plain `# noqa` directives, honor only the first applicable line directive, and require file directives to start the comment token.
- R16. Require both Python Guardrails workflow `paths` blocks to cover every directory and repository-root Python file reported by Ruff discovery.

### Scope Boundaries

Only these tracked files may change:

- `docs/plans/T_CI_0_GUARDRAIL_BASELINE_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `pipeline/model_base.py`
- `pipeline/run_batch_enrichment.py`
- `pipeline/task_startup.py`
- `ruff.toml`
- `tests/test_repository_guardrails.py`
- `tests/test_docker_build_contracts.py`
- `tests/test_run_pipeline_orchestration.py`
- `docs/ENGINEERING_GUARDRAILS.md`
- `.github/workflows/python-guardrails.yml` (event path filters only)

No workflow job, command, permission, dependency, schema, migration, API, Celery, security boundary, runtime default, or soak policy changes are included. Workflow event coverage expands only to locations already included by Ruff discovery. Ruff's effective boundary is unchanged: the existing `pipeline/task_startup.py` suppression moves from inline source text to the centralized per-file inventory. T-CI-0 temporarily coordinates ownership of `docs/ENGINEERING_GUARDRAILS.md` with T-GOV-3 and T-GOV-5 only for this narrow exception-policy clarification; their broader redesign and rewrite responsibilities remain unchanged. T-CI-1 retains ownership of the future full-suite step, and T-CI-5 retains ownership of the Ruff invocation line.

### Acceptance Examples

- AE1. With a pgvector type stub whose `Vector` extends `UserDefinedType`, Mypy accepts `pipeline/model_base.py`.
- AE2. Without pgvector installed, existing database tests construct the fallback datatype and preserve ORM behavior.
- AE3. Guardrail tests compare their expectations to the current Ruff configuration and pass without weakening exact-set assertions.
- AE4. The complete Python suite passes from the branch before delivery.
- AE5. Guardrail tests reject spaced, compact, and delimiter-free joined BLE001 directives with BLE001 first or last, plus bare line-level and file-level suppression, without flagging non-BLE001 code fragments or directive-like text inside Python strings.
- AE6. Guardrail tests reject early returns, suspension, compound flow, nested scopes, nested `try`, unchained translation, and `sys.exit()` before a terminal `raise`, while accepting flat context capture or action calls followed by bare or explicitly chained `raise`.
- AE7. Guardrail tests detect adjacent plain `# noqa` suppressions while preserving Ruff parity for later duplicate directives, misplaced file directives, and directive-like strings.
- AE8. Pull-request and master-push filters cover every Ruff-discovered Python directory plus repository-root Python files.
- AE9. Batch enrichment failure still logs its context and exits with status 1 through chained `SystemExit`; the pre-existing metrics call remains unchanged and is outside this terminal-action correction.

---

## Planning Contract

### Key Technical Decisions

- KTD1. Add T-CI-0 as a distinct prerequisite task. (session-settled: user-approved — chosen over expanding unrelated remediation tasks: the red baseline and exclusive ownership deadlock require a bounded repair lane.)
- KTD2. Annotate the selector as `Callable[[int], TypeEngine[object | None]]`. (review-corrected — the initially approved `type[TypeEngine[object | None]]` accepts both concrete classes but rejects the existing `VECTOR_COLUMN_TYPE(384)` call under full Mypy. The callable contract preserves that constructor use without casts or ignores.)
- KTD3. Correct stale assertions without changing their strictness. (session-settled: user-directed — chosen over skipping, weakening, or widening tests: this task restores the baseline rather than lowering it.)
- KTD4. Keep the current formatter transition explicit. Documentation may advertise the config-owned command while the workflow list remains transitional until T-CI-4.
- KTD5. Centralize the existing `pipeline/task_startup.py` broad-exception suppression in `ruff.toml`. (session-settled: user-directed — chosen over accepting inline suppression outside the approved boundary inventory: centralization preserves behavior and makes policy enforceable.)
- KTD6. Parse Python comment tokens and split adjacent Ruff rule codes before classifying suppression directives. (review-corrected — chosen over extending a raw source-line regular expression: token-aware parsing covers line-level, file-level, blanket, rule-specific, and Ruff-tolerated joined forms without treating strings as policy directives.)
- KTD7. Enforce a flat structural contract for unlisted broad handlers and require a terminal `raise`. (review-corrected — chosen over final-statement inspection or a partial control-flow analyzer: the former permits early exits, while the latter adds unsound machinery.) Approved Ruff boundaries remain the reviewed home for legitimate complex handlers.
- KTD8. Replace the batch operator's `sys.exit(1)` with chained `SystemExit`. (review-corrected — chosen over recognizing `sys.exit` as terminal: direct raising preserves exit status and causal context without trusting a rebindable name.)

### Reuse Audit

The change extends existing guardrail tests, the existing vector datatype selector, and the existing batch failure path. The test-local predicate distinguishes configured BLE001 approvals from unlisted handlers satisfying the flat structural contract; no production helper, registry, compatibility alias, test seam, partial control-flow analyzer, or parallel implementation is introduced. `ruff.toml` remains the approved-boundary source.

### Security and Data Governance

No security-sensitive path, secret, person data, scraped content parser, or external trust boundary changes. No attacker capability changes.

### Implementation Constraints

- Preserve the existing optional-pgvector import boundary and fallback implementation.
- Add no Ruff exception or type suppression.
- Use existing exact-set comparisons for policy inventory.
- Do not edit tracked files outside the ownership set.
- Do not broaden the effective BLE001 boundary; only relocate the existing `pipeline/task_startup.py` suppression.
- Treat the unlisted-handler rule as conservative structural enforcement, not proof that an exception escapes every enclosing Python construct.
- Defer tuple catches and exception name-resolution parity to a separate Ruff-parity task; do not expand this P2 into name binding analysis.
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
- **Requirements:** R2, R3, R4, R5, R9, R10, R11, R12, R13, R14
- **Files:** `tests/test_repository_guardrails.py`, `tests/test_docker_build_contracts.py`, `tests/test_run_pipeline_orchestration.py`, `pipeline/run_batch_enrichment.py`, `pipeline/task_startup.py`, `ruff.toml`, `docs/ENGINEERING_GUARDRAILS.md`
- **Approach:** Update the pypdf pin, Ruff roots/rules, exact BLE001 set, and formatter-transition assertions in place. Move the existing task-startup suppression into Ruff, inspect Python comment tokens, split delimiter-free rule codes at digit-to-letter boundaries, and reject blanket or BLE001-specific line/file directives. Replace final-statement inspection with the flat unlisted-handler contract over Ruff's discovered Python files, require explicit translations to be chained, keep centrally approved Ruff boundaries unchanged, and replace the batch operator's direct `sys.exit(1)` with chained `SystemExit`.
- **Test scenarios:** Current dependency pin, Ruff policy drift, exact BLE001 drift, spaced and compact rule-specific suppression, `BLE001F401`, `F401BLE001`, non-BLE001 joined fragments, bare line suppression, bare and BLE001-specific Ruff file suppression, legacy Flake8 file suppression, string-literal non-directives, early and conditional return, suspension, compound flow, nested scopes and `try`, direct `sys.exit`, unchained translation, flat assignments/actions followed by bare or chained `raise`, Ruff-discovered file coverage, preserved batch log and exit status, and transitional formatter ownership.
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
| Suppression regression | `PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py::test_broad_exception_suppression_detection_covers_ruff_directives tests/test_repository_guardrails.py::test_broad_exception_suppression_scan_uses_comment_tokens tests/test_repository_guardrails.py::test_broad_exception_suppressions_stay_in_ruff_config` | Documented and Ruff-tolerated line/file forms are rejected and string literals are ignored |
| Broad-handler structure | `PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py -k broad_exception` | Early exits, suspension, compound flow, nested constructs, and `sys.exit` are rejected; flat action followed by `raise` is accepted |
| Batch failure exit | `PYTHONPATH=. .venv/bin/pytest -q tests/test_run_pipeline_orchestration.py` | Batch callable failure logs context and exits with status 1; the unchanged metrics path is outside this terminal-action correction |
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
- Runtime behavior, schemas, dependencies, workflow jobs and commands, effective Ruff policy, defaults, and decision gates remain unchanged.
- Simplification and plan-aware review find no unresolved eligible issue.
- Ruff's documented and tolerated line-level and file-level suppression forms cannot bypass the centralized BLE001 inventory.
- Unlisted broad handlers satisfy the documented flat structural contract; final-statement position and `sys.exit()` cannot bypass it.
- Batch enrichment failure preserves its observable status-1 exit contract through explicit `SystemExit`.
- Adjacent plain `# noqa` syntax cannot bypass the scanner, and every Ruff-discovered Python location triggers both workflow events.
- Every Verification Contract command and PR CI pass with fresh evidence.
- The diff contains no abandoned experiment, duplicate implementation, compatibility shim, type suppression, unrelated formatting, or personal path.
- The final report names exact commands, PASS or FAIL outcomes, changed paths, tree state, and review findings. The deviation report records the review-required constructor-callable correction, the operator-approved expansions for centralized task-startup suppression and the broad-handler structural contract, and the review-required joined-code parser correction. Tuple catches and exception name resolution remain an explicit follow-up deficit.

---

## Full Template Follow-up: Adjacent Noqa and Workflow Triggers

### 1. Context & Alignment

**a) Driver.** PR #108 still allowed an adjacent plain `# noqa` to suppress BLE001 outside the centralized boundary inventory, while changes limited to Ruff-discovered crawler, semantic-service, or repository-root Python files did not trigger the guardrail workflow.

**b) Canonical documents.** `AGENTS.md` requires centralized boundary policy, observable tests, exact verification, and explicit workflow ownership. `docs/ENGINEERING_GUARDRAILS.md` keeps Ruff discovery as policy owner. `docs/TESTING.md` permits the existing filesystem and subprocess boundaries without a fake.

**c) Remediation alignment.** T-CI-0 owns the five follow-up files, with `.github/workflows/python-guardrails.yml` limited to event path filters. T-CI-1 retains the future full-suite step, and T-CI-5 retains the Ruff invocation line.

**d) Decision-gate check.** No G1-G5 decision is required or foreclosed.

### 2. Design

**e) Approach.** Add red tests first. Match the first plain line-level `# noqa` within a comment token and anchor file directives to the token start. Derive expected workflow trigger patterns from Ruff-discovered files, then add the missing directory and root-file patterns to both events.

**f) Reuse audit.** Extend `_comment_suppresses_broad_exception`, `_broad_exception_scan_files`, and existing workflow tests. No YAML parser, glob implementation, duplicate source-root list, or production seam is justified.

**g) Data contracts.** No production payload or structured-data contract changes.

**h) Schema/migration impact.** None.

### 3. Security & Data Governance

**i) Security-sensitive paths.** None. The change strengthens a static guardrail but does not alter a runtime trust boundary or attacker capability.

**j) Secrets.** None.

**k) Person data.** None; G4 is unaffected.

**l) Untrusted input.** No scraped content is parsed. Python source comments remain isolated through `tokenize.COMMENT`.

### 4. Code Health

**m) GED conformance sweep.** The correction keeps one focused regex and one focused workflow contract test. No runtime function, timestamp, environment read, or error handler changes.

**n) Antipattern scan, plan pass.** A1/H1 was resolved with Context7 and local Ruff 0.15.9 parity checks. B1/F1 reject a YAML parser and duplicate source-root registry. B3 rejects broadening invalid adjacent file directives. A2-A4, B2, C1-C2, D1-D3, E1-E3, F2, and H2-H4 are clear.

**o) Ratchet interaction.** No Ruff entry is added, removed, or widened. Workflow coverage expands only to Ruff-discovered locations.

**p) Dead code and duplication audit.** Reuse the token scanner and Ruff discovery output. No superseded parser or second root inventory survives.

### 5. Testing

**q) Edge and failure scenarios.** (1) Adjacent specific and blanket plain directives suppress BLE001. (2) Later duplicate line directives, misplaced file directives, similar non-directives, and strings remain unflagged. (3) both workflow `paths` blocks cover Ruff-discovered directories and root Python files. (4) unrelated event lists cannot satisfy path coverage. (5) jobs, permissions, commands, and branch filters remain unchanged.

**r) Tests.** Extend the existing directive and comment-token tests for scenarios 1-2. Add a workflow test that derives trigger patterns from Ruff discovery and checks each event's indentation-bounded `paths` list for scenarios 3-5.

**s) Fakes and mocks.** None.

**t) Verification rows.** Run the guardrail/tooling row, docs-link verification, and complete Python suite before handoff.

### 6. Execution, Rollback, Docs

**u) Commands.** Reproduce with `.venv/bin/ruff check --isolated --select BLE001 -`, prove all three red regressions with targeted pytest, then run Ruff, Mypy, guardrail tests, docs links, the complete suite, and `git diff --check`.

**v) Rollback.** Revert the follow-up commit, rerun the same checks, and reopen both review threads. No migration, configuration, or data remediation exists.

**w) Docs sync.** Update this plan, the remediation ownership record, and the canonical guardrail trigger invariant. README, API contracts, operations, architecture, security, and data-governance docs need no change.

### 7. Delivery Self-Audit

**x) Antipattern scan, diff pass.** Re-run A-F and H against the actual diff before commit.

**y) Evidence.** Report every command with PASS or FAIL; unrun checks are `NOT VERIFIED`.

**z) Deviations.** Record any file outside the eleven-file ownership set, workflow edit beyond event paths, parser behavior beyond Ruff parity, weakened test, skipped review, or unrun check. The authorized ownership and event-trigger expansions plus the pre-commit review's first-directive, anchored-file-directive, and exact-path-block corrections are expected.
