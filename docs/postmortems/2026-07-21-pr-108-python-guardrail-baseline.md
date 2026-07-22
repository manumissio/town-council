---
commit: 0a2c9f3c269fac454088e43e9b723e5bde7fabe0
date: 2026-07-21
severity: medium
tags: [python-guardrails, ruff, ble001, ci, static-analysis]
files_changed: 11
related_commits:
  - 46e25db5c247707d68fa9e80542a8e8d47868fe5
  - 3c591c2ffa4a54c5b9a820660d57f8e7cd41d2b4
  - 142c55c916d599a7e8f09c29a4df5aae52a7b28d
  - ea1fc84991cf1b70ca3845a2a16179c014754ea8
  - bfab7bc071c8a84d026f4d2cb4278977dac8ed82
  - 4fedd5be384777a0206b460e7d80fc764efc6b89
  - 7dab949d2655d92b6af32ea6f5d83d4bfb2609af
---

# Postmortem: Restore confidence in Python guardrails

## Problem Summary

The default branch had four failing contract tests, and Mypy failed when
`pgvector` was installed. The first repair also introduced policy checks that
did not yet match Ruff's accepted suppression syntax, Python control-flow
escape paths, or every CI trigger path. Review found these gaps before merge.

## Impact

| Area | Impact |
|---|---|
| Merge confidence | Reduced until the baseline and policy checks were corrected. |
| Broad-exception policy | Some `noqa` forms and handler escape paths could bypass the first scanner versions. |
| CI routing | Changes in some Ruff-discovered locations did not initially trigger Python Guardrails. |
| Product behavior | No API, schema, runtime default, inference policy, or soak behavior changed. |
| Data and security | No production outage, data loss, person-data incident, or security breach was identified. |

This was a guardrail reliability incident, not a production incident.

## Timeline

| Stage | What happened |
|---|---|
| Baseline repair | Stale dependency, Ruff, formatter, and exception-boundary contracts were aligned with current policy. SQLAlchemy vector typing was corrected for both pgvector and the fallback. |
| Suppression parity | Review exposed compact, blanket, file-level, joined-code, chained, and adjacent `noqa` forms that the custom scanner did not initially classify like Ruff. |
| Control-flow parity | Review showed that checking only a handler's final statement could approve an earlier `return`, suspension, nested flow, or unreachable `raise`. |
| Scope parity | Ruff discovery expanded the scan, but CI path filters did not initially cover crawler, semantic-service, and repository-root Python changes. |
| Merge | The final branch passed Python Guardrails, CodeQL, Ruff, Mypy, 84 guardrail tests, and the 1,095-test local Python suite. PR [#108](https://github.com/manumissio/town-council/pull/108) merged after all review threads were resolved. |

## Root Cause Analysis

**Root cause category**: Incomplete behavioral model

**Direct causes**:

- Contract tests had not kept pace with landed dependency and guardrail policy changes.
- `VECTOR_COLUMN_TYPE` was typed against `TypeDecorator`, but pgvector's
  `Vector` uses `UserDefinedType`; their common SQLAlchemy contract is
  `TypeEngine`.
- The first suppression detector modeled one spelling instead of Ruff's
  broader directive behavior.
- The first broad-handler check modeled terminal syntax instead of all paths
  that could avoid propagation.
- Tool discovery scope and workflow trigger scope were treated as separate
  concerns.

**Systemic cause**:

The scanner was treated like a test helper, but it was policy code with parser,
control-flow, and CI-orchestration responsibilities. The implementation began
with known examples rather than a complete behavior matrix and a differential
contract against the pinned tool. Each narrow correction therefore exposed a
neighboring case during the next review.

## What Worked

- Every review finding received a focused regression test and a code correction.
- No assertion was weakened, skipped, or given a wider tolerance to reach green.
- Ruff, Python tokenization, the AST, `tomllib`, and Ruff file discovery remained
  the authoritative boundaries; no production wrapper or compatibility path was added.
- The final broad-handler rule became deliberately conservative: complex cases
  require centralized approval instead of relying on partial control-flow proof.
- Independent review, targeted tests, the full local suite, and remote CI kept
  the known bypasses from merging.
- Runtime contracts stayed stable. The batch command still exits with status 1,
  now using chained `SystemExit` to preserve failure context.

## What Slowed Us Down

- The repair loop was serial. Several fixes covered the latest example before
  the complete syntax or control-flow boundary had been enumerated.
- A passing full suite showed that existing behavior remained intact, but it
  could not discover cases that had never been modeled.
- The task began as baseline repair and expanded into policy and workflow work.
  Ownership was updated correctly, but earlier recognition of that wider scope
  would have improved the initial plan.

Repeated same-class review findings are a design signal. After the second one,
the next step should be to restate the behavioral model, not add another local
pattern.

## Code Changes

**Modified areas**:

- `pipeline/model_base.py`: typed the vector constructor against SQLAlchemy's
  shared `TypeEngine` contract.
- `pipeline/task_startup.py`, `pipeline/run_batch_enrichment.py`, and
  `ruff.toml`: centralized the broad-exception boundary and preserved the batch
  exit contract with explicit exception chaining.
- `tests/test_repository_guardrails.py`: added token-aware suppression checks,
  conservative broad-handler checks, Ruff-discovered file coverage, and
  adversarial regressions.
- `.github/workflows/python-guardrails.yml`: aligned pull-request and push path
  filters with Ruff-discovered Python locations.
- Guardrail and remediation documents: recorded policy, ownership, verification,
  and known limitations.

**API and interface changes**: None. No public API, task signature, schema,
dependency, environment variable, or runtime default changed.

## Risk Pattern

**High-risk area**: Code that decides whether another check runs, whether a
violation is suppressed, or which files CI inspects.

**Patterns to watch**:

- Reimplementing a third-party tool's grammar from a few examples.
- Approving control flow by inspecting only the last statement.
- Maintaining separate lists for discovery, enforcement, and CI routing.
- Adding one regression for the reported input without nearby negative cases.
- Describing a structural check as semantic proof.

**Common mistake**: Treating policy code as low-risk because it lives under
`tests/`. A false negative in a guardrail can bless defects across the entire
repository.

## Prevention Strategy

### Automated Testing

- [ ] Add a table-driven differential corpus that compares the repository's
  suppression classification with the pinned Ruff version.
- [x] Keep positive and negative cases for compact, blanket, file-level,
  joined, chained, adjacent, duplicate, malformed, and misplaced directives.
- [x] Keep rejection cases for early returns, unreachable raises, suspension,
  compound flow, nested scopes, unchained translations, and `sys.exit()`.
- [x] Derive workflow trigger expectations from Ruff-discovered files for both
  pull requests and pushes.
- [ ] Decide tuple-catch, alias, qualified-name, and `BaseException` behavior in
  a separate task before extending the scanner.

### AI Coding Context

**When to load**: Before changing Ruff policy, suppression scanning,
broad-exception handling, repository discovery, or Python Guardrails routing.

**What to load**:

- [ ] This postmortem.
- [ ] [`docs/ENGINEERING_GUARDRAILS.md`](../ENGINEERING_GUARDRAILS.md).
- [ ] [`docs/TESTING.md`](../TESTING.md).
- [ ] [`docs/plans/T_CI_0_GUARDRAIL_BASELINE_PLAN.md`](../plans/T_CI_0_GUARDRAIL_BASELINE_PLAN.md).

**Context strategy**: Identify the pinned tool, the authoritative behavior, the
differential test, malformed-input rules, control-flow escapes, and CI trigger
scope before implementation. Distinguish documented upstream behavior, locally
observed pinned-version behavior, and repository policy.

### Automation Hooks

- **Pre-commit**: Keep Ruff and exact exception-inventory checks active. Do not
  permit inline suppression as a substitute for centralized policy.
- **CI**: Complete T-CI-1 so every relevant Python change runs the full suite,
  not only the current fast-fail checks.
- **CI**: Complete T-CI-5 so Ruff invocation and allowlist freshness use the
  intended repository-wide policy.
- **Parity probe**: Run isolated Ruff fixtures whenever suppression parsing
  changes; fail when repository classification and Ruff disagree.

### Code Review Checklist

- [ ] Is an external tool's behavior being reimplemented instead of queried?
- [ ] Do tests include both the bypass and the nearest overmatching cases?
- [ ] Can return, suspension, nested flow, rebinding, aliasing, or unreachable
  code bypass the rule?
- [ ] Do discovery, enforcement, workflow trigger, and documented scopes agree?
- [ ] Is every exception centralized and exact-set tested?
- [ ] Are unsupported cases named instead of hidden behind complete wording?
- [ ] After a second related finding, was the behavior matrix rebuilt before
  another patch?

## Lessons Learned

1. Guardrails are production code for the development system.
2. Prefer direct tool output over reproducing tool behavior from examples.
3. When custom parsing is unavoidable, prove parity with differential tests.
4. Conservative structural rules are safer than partial semantic claims.
5. Discovery scope, enforcement scope, and CI trigger scope form one contract.
6. A second same-class defect means the model needs review, not another patch.
7. Regression tests should define the boundary around a bug, not only preserve
   the reported input.
8. Centralized exceptions are easier to audit, ratchet, and remove.

## Action Items

### Immediate

| Status | Action | Done when |
|---|---|---|
| Complete | Preserve adversarial suppression and broad-handler regressions. | The merged positive and negative cases remain active without skips or weaker assertions. |
| Complete | Align CI event filters with Ruff discovery. | Both workflow events cover Ruff-discovered directories and root Python files. |
| Open | Plan exception-target parity. | A focused plan decides tuple catches, aliases, qualified names, and `BaseException`, with acceptance tests and documented limits. |

### Short-term

| Status | Action | Done when |
|---|---|---|
| Open | Add the Ruff differential corpus. | Every supported and intentionally unsupported directive family has Ruff and repository outcomes asserted together. |
| Planned: T-CI-1 | Run the full Python suite in CI. | Every relevant Python pull request runs all tests under `tests/`, and a non-guardrail failure blocks merge. |
| Planned: T-CI-5 | Align Ruff invocation and allowlist freshness. | CI checks the intended Ruff scope and stale BLE001 inventory entries fail exact-set verification. |
| Open | Add a same-class review stop rule to planning guidance. | A second related P2 requires a consolidated behavior matrix and red-team review before another commit. |

### Long-term

| Status | Action | Done when |
|---|---|---|
| Evaluate | Minimize handwritten Ruff parsing. | A bounded technical decision compares the current classifier with direct Ruff diagnostics and selects the smaller verified contract. |
| Evaluate | Generate parser boundary cases. | A bounded property-based experiment finds unique boundary defects or records why its cost exceeds its value. |
| Evaluate | Reuse scope-parity checks for future guardrails. | New guardrails validate discovery, enforcement, and CI routing from machine-readable sources without duplicate inventories. |

## Related Issues

**Known follow-up areas**:

- T-CI-1: full Python suite in CI.
- T-CI-4: config-owned formatter scope.
- T-CI-5: tightened Ruff invocation and allowlist freshness.
- Tuple catches and exception-name resolution remain intentionally deferred.

The current broad-handler check is conservative structural enforcement. It is
not a complete Python control-flow or name-resolution engine.

## Technical Context

Ruff rule `BLE001` flags broad exception catches. Town Council permits them only
at explicit boundaries recorded in `ruff.toml`; unlisted handlers must meet the
repository's flat re-raise contract. The repository test uses Python comment
tokens and AST nodes, while Ruff remains authoritative for lint discovery and
suppression behavior.

The final local verification reported 1,095 passing tests with 376 existing
warnings. Remote Python Guardrails and CodeQL checks passed before merge.

## Evidence

- [PR #108](https://github.com/manumissio/town-council/pull/108)
- [Merge commit `0a2c9f3`](https://github.com/manumissio/town-council/commit/0a2c9f3c269fac454088e43e9b723e5bde7fabe0)
- [Engineering Guardrails](../ENGINEERING_GUARDRAILS.md)
- [T-CI-0 implementation plan](../plans/T_CI_0_GUARDRAIL_BASELINE_PLAN.md)
- [Town Council remediation plan](../plans/TOWN_COUNCIL_REMEDIATION_PLAN.md)
- [Testing policy](../TESTING.md)
- [ADR](../ADR.md)
