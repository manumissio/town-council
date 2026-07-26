# T-GOV-3A: Retire File-Length Inventories and Consolidate Dependency Rules

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: complete`
`execution: code`

## 1. Context & Alignment

**a) Driver.** T-CI-5 enforces Ruff complexity limits across the repository,
but `tests/test_repository_guardrails.py` still carries 34 module inventories
and 34 tests enforcing a 300-line proxy. Those checks preserve the mechanical
facade-plus-helper splits the architecture review identifies as harmful.
T-GOV-3A removes that obsolete policy and consolidates existing
helper-to-facade dependency checks without prematurely enforcing the sync and
SQL smell rules reserved for T-GOV-3B.

**b) Canonical documents consulted.**

- `AGENTS.md` `<known_antipatterns>`, `<workflow_contract>`,
  `<verification_matrix>`, and `<docs_sync_rules>` require tests-first
  governance changes, config-owned inventories, exact evidence, and no new
  compatibility seams.
- `docs/ENGINEERING_GUARDRAILS.md` “Structural rules” makes Ruff C901 the
  complexity policy and identifies file-length checks as retired.
- `docs/TESTING.MD` permits filesystem and AST inspection without production
  patch seams.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` assigns T-GOV-3 to the GOV
  lane after at least two Phase 2 tasks merge.
- `docs/reviews/architecture-review-2026-07-19.html` rejects facade-plus-helper
  fragmentation driven by line limits.
- `SECURITY.md` and `docs/DATA_GOVERNANCE.md` impose no runtime or person-data
  control on this governance-only change.

**c) Remediation alignment.** Split T-GOV-3 into T-GOV-3A and T-GOV-3B.
T-GOV-3A owns exactly:

- `docs/plans/T_GOV_3A_GUARDRAIL_INVENTORY_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `docs/ENGINEERING_GUARDRAILS.md`
- `tests/test_repository_guardrails.py`

The prerequisite is satisfied: T-DA-1, T-DB-1A, T-DB-1, and T-DB-1B are
merged Phase 2 tasks. T-PLAT-1 is also merged, so its concurrency exclusion no
longer blocks T-GOV-3A. The ledger update also marks merged T-DD-1A complete.

**d) Decision gates.** No G1-G5 decision is required or foreclosed. G4 remains
open for T-GOV-2 and City Coverage Expansion. G2, G3, and G5 remain satisfied.

## 2. Design

**e) Step-by-step approach.**

1. Fast-forward `master` and create
   `codex/t-gov-3a-guardrail-inventory-cleanup`.
2. Add this Full plan and update the remediation ledger to version 3.57:
   mark T-DD-1A complete, split T-GOV-3A from T-GOV-3B, record exact
   ownership, and preserve task ordering.
3. Add a failing policy test before deleting old checks. It parses the
   guardrail test module and rejects module-level names ending
   `_CLEANUP_MODULES` plus test functions whose AST compares source
   `splitlines()` counts with numeric limits. This detects the retired
   behavior even if a test is renamed.
4. Capture the expected red result: 34 obsolete constants and 34 obsolete
   tests.
5. Replace the 11 separate helper-to-facade policy tests covering 24 helper
   paths with one
   `HELPER_FACADE_IMPORT_RULES` registry and one enforcement test. Each row
   names one of the 24 already-clean helper paths and its forbidden facade
   modules. Do not infer relationships from filenames or scan every
   facade-like module: active T-DC and T-DE reverse dependencies remain owned
   by those later tasks.
6. Preserve `_forbidden_imports()` and its relative-import behavior test.
   Keep these unrelated direct-operation boundary tests unchanged even though
   they call `_forbidden_imports()`:
   `test_summary_generation_uses_direct_operation_boundaries`,
   `test_summary_backfill_runner_is_the_direct_operation_boundary`, and
   `test_maintenance_summary_and_staged_hydration_own_runtime_dependencies`.
7. Delete all 34 file-length constants and 34 file-length tests. Do not
   replace them with another size threshold or inventory.
8. Update the guardrail policy to state that per-file line-count assertions
   are retired. Retain `[transition: T-GOV-3]` because T-GOV-3B still owns
   the sync-global and interpolated-SQL checks.
   T-GOV-3B depends on T-DC-1 and the revised T-DE-1; it owns registration of
   relationships made clean by those tasks, the remaining smell checks, and
   final transition-marker removal. T-DD-1B adds no current facade rule and
   remains outside this registry.
9. Run full verification, simplification, a fresh subagent pre-commit review,
   eligible fixes, atomic commits, PR delivery, and bounded CI repair.

Three small test helpers separate assignment-name detection, semantic
source-line comparison detection, and aggregation for one module. The new
policy test prevents those nodes from returning. The consolidated dependency
test verifies only registered helpers do not import their facades.

**f) Reuse audit.** Reuse the existing AST parser, `_forbidden_imports()`,
relative-import characterization, repository guardrail suite, and GOV lane.
No parser framework, runtime helper, policy manager, compatibility alias, or
second dependency implementation is added. The superseded tests are
`test_summary_hydration_sample_helpers_do_not_import_facade`,
`test_batch_f_operator_ab_helper_does_not_import_facade`,
`test_batch_e_reporting_helpers_do_not_import_facades`,
`test_batch_d_profile_helpers_do_not_import_facades`,
`test_batch_f_search_read_helpers_do_not_import_facade`,
`test_batch_f_city_coverage_helpers_do_not_import_facade`,
`test_batch_f_lineage_helpers_do_not_import_facade`,
`test_laserfiche_generated_pdf_helper_does_not_import_facades`,
`test_batch_g_semantic_service_helpers_do_not_import_facade`,
`test_summary_backfill_progress_helper_does_not_import_facades`, and
`test_vote_extraction_item_helper_does_not_import_facades`.

**g) Contracts.** No application payload changes. The guardrail contract
changes from 34 file-length inventories and 11 family-specific dependency
tests to:

- zero `*_CLEANUP_MODULES` inventories;
- zero `*_stay_under_size_target` tests;
- one 24-row helper/facade dependency registry;
- one general dependency-direction enforcement test;
- one durable test preventing file-length policy reintroduction.

**h) Schema and migrations.** None.

## 3. Security & Data Governance

**i) Security boundary.** No security-sensitive path is touched. The change
does not alter authentication, network exposure, workflow permissions, or
runtime execution.

**j) Secrets.** None added, read, or exposed.

**k) Person data.** None created, linked, aggregated, or exposed. G4 remains
unaffected.

**l) Untrusted input.** The tests parse tracked Python source with `ast` and
read registered helper modules. No scraped content, provider response, or user
input is parsed.

## 4. Code Health

**m) Conformance.** Test helpers remain typed and focused. No runtime
functions, exception handlers, timestamps, environment reads, or defaults
change. Registry identifiers use dependency-domain terms. No broad exception
or Ruff exception is added.

**n) Antipattern scan, plan pass.**

- A1/H1: no external API or dependency-facing call is introduced; the plan
  uses existing stdlib AST and path APIs already exercised in this test file.
- B1/F1: a table replaces 11 duplicate tests; no framework or wrapper is
  added.
- C1: all superseded size inventories and separate dependency tests are
  deleted.
- D1: this is an intentional policy change from 34 inventories enforcing a
  300-line limit to zero line caps, while retaining Ruff C901 and registered
  dependency direction. The remaining deficit is T-GOV-3B enforcement for
  sync globals and interpolated SQL.
- D3: the legacy constant-suffix check plus semantic AST detection are
  accepted because preventing the retired repository policy from returning
  is the observable governance contract.
- E1/E2: only four owned files change; no unrelated formatting.
- A2-A4, B2-B3, C2, D2, E3, F2, and H2-H4: no violations planned.

**o) Ratchets.** Ruff selectors, BLE001 boundaries, C901 maximum, formatter
scope, Mypy scope, coverage floor, and CI workflows remain unchanged.
T-GOV-3A removes 34 obsolete file-length inventories and adds no
new allowlist.

**p) Dead code and duplication.** Delete 34 constants, 34 size tests, and 11
duplicated dependency tests. The current gross removable inventory is 692
lines: 301 constant lines covering 233 paths, 272 size-test lines, and 119
dependency-test lines. Reuse one existing import analyzer. The guardrail test
file must shrink materially; report exact pre/post counts from the final diff
instead of predicting the whole-PR net delta.

## 5. Testing

**q) Edge and failure scenarios.**

1. A `*_CLEANUP_MODULES` inventory is reintroduced.
2. A `*_stay_under_size_target` test is reintroduced.
3. A registered helper imports its facade with an absolute import.
4. A registered helper imports its facade with a relative import.
5. A registered helper path is missing or renamed without updating policy;
   the enforcement test first asserts `helper_path.is_file()` and reports the
   missing registry path before import analysis.
6. The import analyzer falsely rejects an unrelated domain import.
7. Unrelated direct-operation boundary checks are accidentally removed.
8. The T-GOV-3 transition marker is removed before T-GOV-3B enforcement.
9. Ledger state continues to report merged T-DD-1A as active.

**r) Tests.**

| Test | Scenarios |
|---|---|
| New `test_structural_guardrails_do_not_restore_file_length_inventories` | 1, 2 |
| New detector characterization for named thresholds and non-policy reads | 1, 2 |
| Consolidated `test_registered_helpers_do_not_import_facades` | 3, 5 |
| Extended `test_facade_import_guardrail_detects_relative_imports` | 4, 6 |
| Existing direct-operation boundary tests | 7 |
| New `test_t_gov_3a_retires_line_limits_without_closing_t_gov_3` | 8, 9 |
| Repository guardrail suite | 1-9 |
| Complete Python suite | Regression check |

The new policy test is written and run red before deleting any existing
inventory or size test. It reports both the inventory names and semantic
line-limit tests in one assertion payload so neither deficit hides the other.

**s) Fakes and mocks.** None. Tests use approved filesystem and AST boundaries.
No facade, re-export, or implementation symbol is patched.

**t) Verification rows.** Apply the guardrail/tooling and docs-only rows. Run
the complete Python suite because the repository policy test is cross-cutting.

## 6. Execution, Rollback, Docs

**u) Commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-gov-3a-guardrail-inventory-cleanup
```

Tests-first red evidence:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_repository_guardrails.py::test_structural_guardrails_do_not_restore_file_length_inventories
```

Expected: one failure listing exactly 34 `*_CLEANUP_MODULES` constants and 34
tests containing semantic source-line limits.

Final verification:

```bash
./.venv/bin/ruff check .
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/pytest -q
git diff --check
git status --short
```

Delivery uses two commits:

1. `docs(remediation): authorize T-GOV-3A guardrail cleanup`
2. `refactor(guardrails): replace file-length inventories`

Push the branch and open one PR titled
`T-GOV-3A: Replace file-length inventories with dependency rules`. Browser
testing is not applicable. Watch required CI and resolve all P1/P2 findings
before merge.

**v) Rollback.** Revert the T-GOV-3A merge commit, rerun Ruff, Mypy,
repository guardrails, docs links, and the complete suite. No migration,
runtime configuration, external state, or data repair is involved. Rollback
knowingly restores the obsolete 300-line proxy policy.

**w) Docs synchronization.**

- Remediation plan: v3.57 changelog, T-DD-1A completion, T-GOV-3A/T-GOV-3B
  split, ownership, acceptance, and execution order. The task table must show
  T-GOV-3A complete after delivery, T-GOV-3B pending, and umbrella T-GOV-3
  partially landed; umbrella T-GOV-3 never enters the completed row.
  T-GOV-3B depends on T-DC-1 and revised T-DE-1 and owns later registrations,
  remaining smell checks, and final transition-marker removal.
- `docs/ENGINEERING_GUARDRAILS.md`: state that all per-file line-count
  assertions are retired while retaining the T-GOV-3 transition marker.
- New T-GOV-3A Full plan.
- `AGENTS.md`, README, ADR, testing policy, architecture review, operations,
  security, and data-governance docs: no changes.

## 7. Delivery Self-Audit

**x) Diff scan.** Re-run A-F/H. Reject a replacement file-size threshold,
duplicate dependency scanner, new structural allowlist, premature sync/SQL
checks, transition-marker removal, Ruff-policy edit, unrelated formatting, or
any path outside the four-file ownership set.

**y) Evidence required.** Report the tests-first red result, Ruff, Mypy,
repository guardrail, docs-link, and complete-suite outcomes; exact test
counts; planning-review and pre-commit-review findings; fixes; commit hashes;
PR URL; unresolved-thread count; and final CI state. Mark any unrun item
`NOT VERIFIED`.

**z) Deviations.** Authorized changes are the T-GOV-3A/T-GOV-3B split,
T-DD-1A completion update, removal of 34 constants and 34 tests, and
consolidation of 11 dependency tests covering 24 helper paths. Any inferred
facade scan that captures pending T-DC/T-DE debt, added runtime file, new lint
rule, allowlist widening, removed direct-operation contract, premature
T-GOV-3 completion, skipped subagent review, unresolved P1/P2, or unrun
required check is a blocker.
