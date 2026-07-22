---
title: "T-CI-5: Activate and Ratchet the Landed Ruff Scope"
date: 2026-07-21
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: operator-approved-plan
execution: code
---

# T-CI-5: Activate and Ratchet the Landed Ruff Scope

## Goal Capsule

- **Objective:** Make `ruff.toml` the enforced lint-scope source for local,
  pre-commit, and CI entrypoints while removing only empirically stale ignores.
- **Authority:** `AGENTS.md`, `docs/ENGINEERING_GUARDRAILS.md`, and the active
  remediation plan define policy, ownership, and verification.
- **Execution profile:** Register ownership, add red contract tests, implement
  the config and documentation alignment, verify, review, and deliver one PR.
- **Stop conditions:** Stop for any new rule family, allowlist widening,
  workflow change outside the Ruff invocation, runtime behavior change, G1-G5
  dependency, or required file outside the eight-file ownership set.

## 1. Context & Alignment

The tightened Ruff rules and repository discovery are already present and
`ruff check .` passes. CI and pre-commit still name four directories, while the
pre-commit arguments also send `check` as a nonexistent path. The current
allowlist contains 105 selectors; `F841` is stale in both wildcard entries.

T-CI-5 remains the next Phase 0 CI-lane task after T-CI-0. No decision gate
applies. T-CI-1 remains next and continues to own the full-suite CI step.

## 2. Design

1. Add red repository contracts for config-owned entrypoints and live ignore
   selectors before changing configuration.
2. Remove wildcard `F841` from `scripts/*.py` and `tests/*.py`, reducing the
   allowlist from 105 to 103 selectors. Change no other selector.
3. Correct the historical comment that still calls `pipeline/task_startup.py`
   pruned even though T-CI-0 restored its live centralized boundary.
4. Change CI to `python -m ruff check .` and pre-commit to `args: ["."]` with
   `pass_filenames: false`.
5. Keep pre-commit hook ID `ruff`, display name `ruff-guardrails`, workflow
   paths, permissions, formatter, Mypy, tests, dependencies, and branch filters.
6. Align the three contributor commands and state truthfully that T-CI-1 still
   owns the complete CI suite.

The only new helper, `_ruff_selector_has_current_violation`, runs isolated
pinned Ruff for one configured selector. It accepts only exit statuses zero
and one; abnormal termination fails with command output.

No application contract, schema, migration, task signature, dependency,
environment variable, runtime default, security boundary, or person data
changes.

## 3. Code Health

- Reuse the existing TOML parser, subprocess boundary, and guardrail tests.
- Add no YAML parser, policy registry, compatibility path, test seam, or second
  source-root inventory.
- Delete obsolete command strings, two stale selectors, the redundant
  pre-commit argument, and one inaccurate history reference.
- Keep all comments focused on policy intent.
- Add no broad exception, type suppression, environment read, or timestamp.

## 4. Testing

The entrypoint contract covers CI, pre-commit, contributor commands, root
Python files, crawler files, semantic-service files, and unchanged workflow
sections. The freshness contract checks every exact and wildcard selector and
fails with context if Ruff terminates abnormally.

Plant checks must report `DTZ003` and `C901`. Existing workflow-trigger tests,
the repository guardrail suite, Mypy, docs links, and the complete Python suite
must remain green. Tests use only approved filesystem and subprocess boundaries.

## 5. Delivery

Run simplification, plan-aware code review, and a fresh pre-commit subagent
review. Apply every eligible P1/P2, rerun affected gates, and run the complete
verification set before delivery.

Commit the ownership/plan registration separately from the lint enforcement.
Push `codex/t-ci-5-tightened-lint-scope`, open one T-CI-5 PR, invoke pipeline
browser routing, and babysit CI to a decided state.

Rollback reverts the T-CI-5 commits and reruns the same verification. No data
or external-state remediation is required.

## 6. Delivery Self-Audit

Reject any broadened ignore, new rule family, hook-ID migration, workflow edit
outside the Ruff command, duplicated scope list, unrelated formatting, weak
assertion, unresolved P1/P2, or claim without fresh command evidence. Report
all command outcomes and deviations explicitly.
