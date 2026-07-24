# Town Council Remediation Plan (Codex Multi-Agent)

version: 3.18
generated: 2026-07-24
source: Four-pass external code review (security, architecture, smells, process)
source_artifact: [Town Council architecture review](../reviews/architecture-review-2026-07-19.html)
orchestrator_contract: Codex instantiates one agent per lane. Agents run in
parallel ONLY within the same phase and ONLY on their owned paths. AGENTS.md
remains in force; where this plan is stricter, this plan wins for these tasks.

## Changelog

- **v3.18:** Accepts the G3 ADR, activates the testing policy, removes the stale
  live G3 deferral, completes T-GOV-1, and unblocks Phase 2. T-GOV-6 remains
  partial because its README Documentation Map links are still missing.
- **v3.17:** Records operator approval of G3 and activates T-GOV-1 with
  six-file ownership for the Accepted ADR, effective testing policy, policy
  guardrails, remediation state, and one stale source comment. Phase 2 remains
  blocked until the T-GOV-1 ADR merges.
- **v3.16:** Records the operator-approved G2 policy: account-free summarize,
  segment, extract, and topic-generation actions remain available through the
  public Next.js proxy, direct calls to protected AI mutation endpoints remain
  key-protected, and T-SEC-4 owns the pending per-client limiting control.
- **v3.15:** Activates T-SEC-4A to record the operator-approved G2
  visitor-access policy independently from T-SEC-5 closure and T-SEC-4
  runtime implementation.
- **v3.14:** Marks T-SEC-5 complete after PR #130 merged with all required
  checks green, its P2 review finding resolved, and final Codex review clean.
- **v3.13:** Activates T-SEC-5 with a Full implementation plan and expands
  ownership to its executable frontend test and canonical security checklist.
- **v3.12:** Marks T-PLAT-2A complete after PR #128 merged with required
  checks green, its final review found no unresolved P1/P2 issues, and
  Dependabot alert 106 closed as fixed.
- **v3.11:** Marks merged T-TIME-3 complete and activates urgent T-PLAT-2A
  to pin Next.js's transitive Sharp runtime to patched version 0.35.3 for
  Dependabot alert 106.
- **v3.10:** Marks merged T-CRAWL-2 complete and activates T-TIME-3 with
  tests-first ownership for PostgreSQL checkout pre-ping and its Full
  implementation plan.
- **v3.9:** Expands T-CRAWL-2 ownership to the repository guardrail contract
  after removing crawler BLE001 exceptions exposed its exact inventory as
  stale.
- **v3.8:** Activates T-CRAWL-2 with characterization-first ownership for the
  shared archive-table parser, all crawler Ruff debt, and parity verification.
- **v3.7:** Closes T-SEC-3 and T-SEC-3C after synchronizing the canonical
  Meilisearch reader-key checklist with the merged, green implementation.
- **v3.6:** Marks merged T-CRAWL-1 complete and registers T-SEC-3C to
  synchronize the canonical security checklist before closing T-SEC-3.
- **v3.5:** Records T-SEC-3 as implemented but not closed because its canonical
  `SECURITY.md` checklist item remains open. A separate owned documentation
  change must synchronize that checklist before T-SEC-3 returns to complete.
- **v3.4:** Marks T-SEC-3 complete after PR #123 merged with all required
  checks green and no unresolved P1/P2 findings, then activates T-CRAWL-1 with
  focused settings-contract, crawler-readme, and Full-plan ownership.
- **v3.3:** Preserves customized local Meilisearch credentials by deriving the
  development reader key from the local master only when no explicit search
  key is configured.
- **v3.2:** Closes T-SEC-3 review gaps by aligning base and development reader
  identities, preserving the development stack during bootstrap, soak
  recovery, and local experiments, and protecting the frontend's independent
  Docker build context.
- **v3.1:** Expands T-SEC-3 ownership to keep local model bootstrap and runtime
  profile commands on the explicit development Compose stack.
- **v3.0:** Expands T-SEC-3 to cover both Meilisearch reader services,
  non-development fail-fast behavior, writer credential wiring, tests,
  operations guidance, and its Full implementation plan.
- **v2.9:** Marks T-SEC-2 complete after transport-safe API-key validation,
  focused and full-suite verification, independent review, and green
  implementation-head pull-request checks. The closure commit must pass the
  same required checks before merge.
- **v2.8:** Expands T-SEC-2 ownership so its startup policy, focused tests,
  security checklist, registry, and Full plan land together.
- **v2.7:** Marks T-CI-2A complete after PR #120 merged under both required
  checks, the direct and effective ruleset readbacks passed against the
  advanced default branch, and the operator explicitly accepted the recorded
  digest-approval deviation. The closure record still must merge under both
  checks and receive the final no-drift readback required by its delivery
  procedure.
- **v2.6:** Records operator approval and live activation of the T-CI-2A
  frontend required check. Final completion remains pending until the policy
  record merges under both required checks and post-merge readback passes. It
  also retires T-CI-2's unsafe standalone rollback; any reversal must coordinate
  the ruleset, producer, guardrails, dependency contract, and policy text.
- **v2.5:** Records T-SEC-1 completion after local verification, independent
  review, and green pull-request checks.
- **v2.4:** Records T-CI-3 completion and expands T-SEC-1 ownership so
  backing-service port hardening, contract tests, and operator documentation
  land together. Includes Prometheus and limits development bindings to
  loopback.
- **v2.3:** Defines a production-only, subprocess-aware T-CI-3 coverage
  contract without adding coverage tools to runtime images.
- **v2.2:** Corrects T-CI-2A workflow identity checks for GitHub's YAML scalar
  semantics.
- **v2.1:** Adds the development-only PyYAML contract used to validate workflow
  check identities semantically.
- **v2.0:** Records T-CI-2 completion and adds the approval-gated T-CI-2A
  frontend required-check plan.
- **v1.9:** Aligns T-CI-2 with the existing Node 20 test runner, current CSP
  owner, testing policy, and completed Phase 0 work.
- **v1.8:** Expands T-CI-4 ownership and adds a dedicated formatter-scope
  config.
- **v1.7:** Adds T-CI-1A for the required Python Guardrails check and schedules
  T-CI-2A after the frontend check is proven.
- **v1.6:** Expands T-CI-1 ownership for the complete Python suite, crawler and
  Python 3.14 topic dependencies, subprocess environment, and universal CI
  triggers.
- **v1.5:** Expands T-CI-5 ownership for aligned Ruff entrypoints, policy tests,
  and pre-commit guidance.
- **v1.4:** Expands T-CI-0 ownership to keep workflow triggers aligned with Ruff
  discovery.
- **v1.3:** Adds T-CI-0 to restore the Python guardrail baseline before other
  Phase 0 work.
- **v1.2:** Adds T-CI-5, lint-ratchet ownership, the T-GOV-3 complexity
  correction, and pre-commit ownership.
- **v1.1:** Adds the T-GOV-4..6 documentation workstream and registers the
  initial policy-document drafts.

## Task Status

| State | Tasks |
|---|---|
| **Complete** | T-CI-0, T-CI-1, T-CI-1A, T-CI-2, T-CI-2A, T-CI-3, T-CI-4, T-CI-5, T-SEC-1, T-SEC-2, T-SEC-3, T-SEC-3C, T-SEC-5, T-TIME-3, T-CRAWL-1, T-CRAWL-2, T-PLAT-2A, T-GOV-1 |
| **In progress** | T-SEC-4A |
| **Partially landed; acceptance incomplete** | T-GOV-4, T-GOV-5, T-GOV-6 |
| **Pending** | T-SEC-4, T-SEC-6, T-TIME-1..2, T-DA-1, T-DB-1, T-DC-1, T-DD-1, T-DE-1, T-PLAT-1, T-PLAT-2, T-PLAT-3, T-PLAT-4, T-GOV-2..3 |

---

## 0. GLOBAL ENGINEERING DIRECTIVES (apply to every task)

- GED-1 (No machinery): Produce the minimal diff satisfying acceptance criteria.
  Do NOT add typed validation infrastructure, wrapper classes, new facades,
  new config surfaces, or new abstraction layers unless a task explicitly
  names them as a deliverable.
- GED-2 (No new seams): Do not add re-export blocks, `X as X` import aliases,
  module-global sync functions, or injectable-callable parameters. If a test
  breaks because a patch target moved, fix the TEST to patch the real module.
- GED-3 (Scope lock): Touch only `files_owned` for your task. If a fix appears
  to require an unowned file, STOP and report; do not expand scope.
- GED-4 (Behavior freeze): No changes to runtime defaults, gate semantics,
  soak comparability, or inference policy unless the task says so
  (per AGENTS.md hard invariants).
- GED-5 (Guardrail edits): Editing `tests/test_repository_guardrails.py` or
  the CI workflow is permitted ONLY where a task grants it, and only the
  named entries.
- GED-6 (Verification): Run the task's `verify` block before reporting done.
  Report: diff summary, verify output, deviations, unresolved risks.
- GED-7 (Docs): Update only the doc sections named in the task. No sweeping
  doc rewrites.

---

## 1. HUMAN DECISION GATES (Users resolves; agents must not assume)

- G1 deployment_posture: Is any instance ever network-reachable beyond
  localhost? Default assumption for this plan: YES (harden accordingly).
  Affects severity of SEC lane; does not block it.
- G2 protected_action_policy: **Approved 2026-07-24.** AI task endpoints
  (summarize/segment/extract/topics) remain available to visitors through the
  public Next.js proxy with per-client rate limits. Direct calls to these
  protected AI mutation endpoints remain deployment-key protected; public read
  and task-status routes remain public. T-SEC-4 is authorized; operator-only
  proxy authentication is not approved. Rationale: preserve account-free
  public access to civic record analysis and use client-scoped limiting, rather
  than end-user identity, as the abuse control.
- G3 test_seam_adr: **Satisfied 2026-07-24.** The operator approved G3 and
  T-GOV-1 records the Accepted ADR. Tests patch implementation modules or fake
  at approved architectural boundaries; historical test patch targets are not
  public API. Phase 2 is unblocked, subject to each task's own sequencing and
  ownership.
- G4 pii_policy: Ratify ADR on person-entity minimization for non-officials
  (T-GOV-2). BLOCKS nothing in this plan, but blocks City Coverage Expansion.
- G5 migration_tooling: Alembic adoption approved? Default: yes (T-PLAT-1).
  If no, T-TIME-2 ships via the existing migrate_v10 chain unchanged.

---

## 2. LANES AND FILE OWNERSHIP (conflict-free parallelism)

| lane      | agent id   | owned paths (exclusive within phase)                      |
|-----------|-----------|------------------------------------------------------------|
| CI        | agent-ci   | .github/workflows/**, ruff.toml, ruff-format.toml (new), .pre-commit-config.yaml, .coveragerc, frontend/package.json, frontend/jest.config.* (new) |
| SEC       | agent-sec  | docker-compose.yml, docker-compose.dev.yml, .dockerignore, .env.example, api/app_setup.py, api/main.py (CORS+/stats sections only), api/search/support_core.py, pipeline/meilisearch_credentials.py, semantic_service/main.py, frontend/app/api/** |
| TIME      | agent-time | pipeline/model_base.py, model_civic.py, model_events.py, model_records.py, model_runtime.py, models.py, db_migrate.py, migrate_v10.py (new), pipeline/summary_freshness.py (verify-only) |
| CRAWL     | agent-crawl| council_crawler/**                                          |
| DEDUP-A   | agent-da   | pipeline/metrics.py, pipeline/metrics_redis_backend.py, tests/test_*metrics* |
| DEDUP-B   | agent-db   | pipeline/summary_backfill*.py, tests/test_*backfill*        |
| DEDUP-C   | agent-dc   | api/main.py, api/app_setup.py, tests/conftest.py, tests/test_*api* (Phase 2 only) |
| DEDUP-D   | agent-dd   | scripts/flush_city_pipeline_state.py, scripts/reset_city_verification_state.py, scripts/*_healthcheck.py, tests for same |
| DEDUP-E   | agent-de   | pipeline/http_inference_provider.py, pipeline/inprocess_inference_provider.py, pipeline/inference_provider_contract.py, tests for same |
| PLAT      | agent-plat | alembic/** (new), pipeline/requirements*.txt, api/requirements.txt, semantic_service/requirements.txt, constraints.txt (new), .github/dependabot.yml (new), docs/OPERATIONS.md (backup section only), api/cache.py |
| GOV       | agent-gov  | docs/ADR.md, docs/ENGINEERING_GUARDRAILS.md, AGENTS.md, SECURITY.md (new), docs/TESTING.md (new), docs/DATA_GOVERNANCE.md (new), tests/test_repository_guardrails.py (Phase 3 only) |

Sequencing rule: SEC and DEDUP-C both own api/app_setup.py + api/main.py —
they are in different phases and MUST NOT run concurrently. TIME owns
model files; PLAT's Alembic baseline runs AFTER TIME merges. T-CI-0 temporarily
coordinates `docs/ENGINEERING_GUARDRAILS.md` with T-GOV-3 and T-GOV-5 for the
narrow broad-handler policy correction described below; the GOV lane retains
ownership of the later redesign and rewrite. T-CI-5 temporarily coordinates
the lint-command sections of `AGENTS.md` and `docs/ENGINEERING_GUARDRAILS.md`
plus the corresponding repository guardrail tests; later GOV work retains all
other ownership of those files. T-CI-4 receives the same narrow temporary
coordination grant for formatter config-location prose and the formatter
contract test only; later GOV work retains all other ownership.
T-CI-3 receives a narrow temporary coordination grant for coverage scope
references, verification commands, merge-gate prose, and transition markers
in `AGENTS.md`, `docs/TESTING.MD`, and
`docs/ENGINEERING_GUARDRAILS.md`; later GOV work retains all other ownership.

---

## 3. PHASE 0 — SAFETY NET (run first; agent-ci; ~1 day)

### T-CI-0: Restore the Python guardrail baseline
- priority: P0 (run before every other Phase 0 task)
- status: complete and verified 2026-07-22 (PR #108)
- files_owned: docs/plans/T_CI_0_GUARDRAIL_BASELINE_PLAN.md,
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md,
  docs/ENGINEERING_GUARDRAILS.md, .github/workflows/python-guardrails.yml
  (event path filters only), pipeline/model_base.py,
  pipeline/run_batch_enrichment.py, pipeline/task_startup.py, ruff.toml,
  tests/test_repository_guardrails.py, tests/test_docker_build_contracts.py,
  tests/test_run_pipeline_orchestration.py
- do: Realign stale dependency and Ruff contract expectations with already-landed
  repository policy. Type the vector datatype selector against SQLAlchemy's
  common datatype base so installed pgvector and the local fallback both pass
  Mypy. Move the existing task-startup inline BLE001 suppression into Ruff's
  centralized boundary inventory. Enforce a conservative flat structural
  contract for unlisted broad handlers, reject compound flow and `sys.exit()`,
  preserve the batch operator's exit status with explicit `SystemExit`, and
  ensure all Ruff-discovered Python locations trigger the guardrail workflow.
  Follow the implementation-ready T-CI-0 plan.
- accept: The four baseline contract failures pass; pgvector-present Mypy passes;
  broad handlers cannot bypass policy through an early exit or unreachable terminal
  raise; both workflow events cover Ruff-discovered Python locations; complete
  Python suite passes; no runtime contract, effective Ruff boundary, workflow job,
  dependency, schema, default, or decision-gate change.
- forbidden: Editing outside `files_owned`; weakening or skipping tests; broadening
  Ruff boundary policy; claiming semantic control-flow proof; adding casts, ignores,
  compatibility paths, partial control-flow machinery, or new test seams.
- verify: Ruff checks, repo Mypy, deterministic pgvector-present Mypy stub,
  guardrail contracts, Docker contracts, database tests, docs links, complete
  Python suite, and `git diff --check` as specified in
  `docs/plans/T_CI_0_GUARDRAIL_BASELINE_PLAN.md`.

### T-CI-1: Run the full Python test suite in CI
- priority: P0
- depends_on: T-CI-0, T-CI-5
- status: complete and verified 2026-07-22 (PR #111)
- files_owned: docs/plans/T_CI_1_FULL_PYTHON_SUITE_PLAN.md,
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md,
  docs/ENGINEERING_GUARDRAILS.md, tests/test_repository_guardrails.py,
  .github/workflows/python-guardrails.yml
- do: Follow the implementation-ready T-CI-1 plan. Install the existing
  crawler requirements needed by spider tests, install scikit-learn 1.8.0 for
  Python 3.14 topic tests, create a system-site-packages `.venv` for existing
  subprocess tests, remove event path filters, and add a distinct
  `PYTHONPATH=. python -m pytest -q tests/` step after the seven-command
  fast-fail step.
- accept: Every pull request and master push triggers CI; the
  fast-fail tests remain separate and precede the complete suite; CI executes
  all collected tests under `tests/` with the pinned Python 3.14 environment;
  current master is green.
- forbidden: Skipping or x-failing tests; adding coverage before T-CI-3;
  using `continue-on-error`, `if: always()`, retries, caching, or another job;
  fixing unrelated assertions if dependency-aligned master is red.
- verify: Ruff, Mypy, repository guardrails, docs links, local
  `PYTHONPATH=. .venv/bin/python -m pytest -q tests/`, `git diff --check`, and
  the PR's Python Guardrails run with the pinned CI dependencies.

### T-CI-1A: Require Python Guardrails before default-branch updates
- priority: P0
- depends_on: T-CI-1
- status: complete and verified 2026-07-22
- external_state: active repository ruleset 19594795
- files_owned: docs/plans/T_CI_1_REQUIRED_CHECK_POLICY_PLAN.md,
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md
- external_state_owned: repository ruleset `Require Python Guardrails`
- decision: Approved by the operator on 2026-07-22 using the exact active
  ruleset payload in `docs/plans/T_CI_1_REQUIRED_CHECK_POLICY_PLAN.md`.
- do: Maintain `python-guardrails` from integration 15368 as the foundational
  required context. T-CI-2A now also requires `frontend-tests` under separate
  operator approval.
- accept: T-CI-1A's historical Python-only activation evidence remains
  recorded. Current acceptance is owned by T-CI-2A and must preserve the
  default-branch target, empty bypass list, strict policy, branch-creation
  exemption, and mandatory Python gate.
- forbidden: Requiring approvals, CodeQL, deployments, signed commits, linear
  history, or an unapproved third check; removing `python-guardrails`; adding
  bypass actors; changing workflow code or repository files outside
  `files_owned`.
- verify: Read the ruleset back through GitHub's REST API and compare target,
  enforcement, conditions, bypass actors, context, integration, strict policy,
  and effective rules on `master` with the expected contract.

### T-CI-2: Give the frontend a test runner and CI job
- priority: P0
- depends_on: T-CI-1A
- status: complete and verified 2026-07-23 (PR #115)
- files_owned: docs/plans/T_CI_2_FRONTEND_TESTS_PLAN.md,
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md, docs/TESTING.MD (frontend
  transition sentence only), frontend/package.json,
  frontend/components/__tests__/NextConfig.security-headers.test.js,
  .github/workflows/frontend-tests.yml (new),
  tests/test_repository_guardrails.py
- decision: Approved by the operator's completion objective on 2026-07-23:
  use the Node 20 test runner already imported by all four test files instead
  of adding Jest/Vitest, and repoint only the stale CSP source contract from
  next.config.js to its current owner in proxy.js.
- do: Add `"test": "node --test components/__tests__/*.test.js"` and a
  workflow running `npm ci` then `npm test` on every pull request and master
  push so the `frontend-tests` context always exists before T-CI-2A makes it
  required. Preserve all existing frontend assertions.
- accept: All 4 existing test files execute and pass in CI; frontend-only and
  non-frontend pull requests both receive a terminal `frontend-tests` check;
  a repository guardrail test enforces the exact job name and unconditional
  pull-request and master-push triggers.
- forbidden: Rewriting the existing frontend assertions; adding new frontend
  component tests; adding a third-party runner or package-lock change;
  path-filtering or masking workflow failures so an otherwise mergeable pull
  request lacks a terminal check.
- verify: `cd frontend && npm test` and
  `PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py` exit 0.

### T-CI-2A: Require the universal frontend test check
- priority: P0
- depends_on: T-CI-2
- status: complete and verified 2026-07-23
- files_owned: docs/plans/T_CI_2_REQUIRED_CHECK_POLICY_PLAN.md (new),
  docs/plans/T_CI_1_REQUIRED_CHECK_POLICY_PLAN.md,
  docs/plans/T_CI_2_FRONTEND_TESTS_PLAN.md (historical ruleset evidence and
  rollback section only),
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md, AGENTS.md (verification-matrix
  CI-status paragraph and transition markers only),
  pipeline/requirements-dev.txt,
  tests/test_docker_build_contracts.py
  (development-only workflow parser dependency contract only),
  tests/test_repository_guardrails.py
  (canonical frontend required-check job identity only)
- external_state_owned: repository ruleset `Require Python Guardrails`
- decision: Operator approved the exact semantic ruleset update on 2026-07-23.
  Live direct and effective readbacks require `frontend-tests` from integration
  15368 alongside `python-guardrails` while preserving every other T-CI-1A
  field. After PR #120 merged under both checks, those readbacks passed against
  the advanced default branch and the operator explicitly accepted the
  documented digest-approval deviation.
- implementation_plan: `docs/plans/T_CI_2_REQUIRED_CHECK_POLICY_PLAN.md`
- do: Preserve ruleset 19594795 with exactly `python-guardrails` and
  `frontend-tests` required. Keep the merged live-policy record and accepted
  procedural deviation as the audit trail. Merge the closure record under both
  checks and repeat the no-drift readback after `master` advances.
- accept: Every pull request receives both contexts; the default branch cannot
  update unless both pass; strict policy, branch-creation exemption, empty
  bypass list, target, and all other T-CI-1A fields remain unchanged. Workflow
  identity validation preserves GitHub string semantics for Boolean-like job
  IDs and display names.
- forbidden: Adding the check while the workflow is path-filtered or unproven;
  adding any third check or rule; changing the existing Python gate; assuming
  approval from T-CI-1A.
- verify: Demonstrate `frontend-tests` on one frontend and one non-frontend PR,
  preserve the one-time update evidence, require both checks on the policy
  record PR, and assert exact ruleset and effective-`master` readback after
  each default-branch advance.
- rollback: Restore ruleset 19594795 to the exact T-CI-1A Python-only contract;
  never delete the ruleset or remove `python-guardrails` while rolling back the
  frontend requirement. Replace T-CI-1A's original creation-time rollback in
  its owned plan with this restoration procedure.

### T-CI-3: Enforce coverage threshold
- priority: P2
- depends_on: T-CI-1
- status: complete and verified 2026-07-23 (PR #118)
- files_owned: docs/plans/T_CI_3_COVERAGE_GATE_PLAN.md,
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md, AGENTS.md,
  docs/TESTING.MD, docs/ENGINEERING_GUARDRAILS.md,
  .github/workflows/python-guardrails.yml, .coveragerc,
  pipeline/requirements-dev.txt, tests/test_repository_guardrails.py,
  tests/test_docker_build_contracts.py
- do: Follow the implementation-ready T-CI-3 plan. Pin pytest-cov and
  coverage.py as development-only dependencies. Measure repository production
  Python from `.coveragerc`, omit tests, archives, experiments, and local
  virtual environments, include namespace-package files, enable coverage.py
  subprocess patching, and replace only the authoritative full-suite workflow
  command with the coverage-aware command.
- accept: CI fails below the unchanged 71% floor; tests do not inflate the
  measured total; every tracked production Python file, including
  namespace-package, repository-root, and subprocess-executed files, remains
  eligible for measurement; coverage tooling remains absent from runtime
  requirements; fast-fail tests, workflow identity, permissions, triggers,
  static checks, and runtime behavior remain unchanged.
- forbidden: Raising or lowering the threshold; counting tests or archived
  code; using explicit `--cov=SOURCE` arguments that override `.coveragerc`;
  adding coverage to fast-fail tests; adding a job, retry, skip, xfail,
  tolerance, cache, external upload, or runtime dependency.
- verify: Ruff lint and configured formatter, pre-commit Ruff, Mypy,
  repository guardrails, Docker dependency contracts, docs links, the
  complete production-only coverage command, `git diff --check`, and PR CI as
  specified in `docs/plans/T_CI_3_COVERAGE_GATE_PLAN.md`.

### T-CI-4: Move formatter file list out of the workflow
- priority: P2
- depends_on: T-CI-1A
- status: complete and verified 2026-07-23 (PR #113)
- files_owned: docs/plans/T_CI_4_FORMATTER_SCOPE_PLAN.md,
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md, AGENTS.md,
  docs/ENGINEERING_GUARDRAILS.md, tests/test_repository_guardrails.py,
  .github/workflows/python-guardrails.yml (formatter step only), ruff.toml
  (verify only), ruff-format.toml (new)
- decision: Approved by the operator on 2026-07-22: replace the registered
  single-`ruff.toml` design with the dedicated `ruff-format.toml` and expanded
  ownership. Serialize this registry edit after T-CI-1A and use remediation
  plan version 1.8.
- do: Move the exact current formatter path set into `ruff-format.toml`, which
  extends `ruff.toml`, and run the one-line config-owned formatter command in
  CI. Keep lint discovery and every non-formatter workflow step unchanged.
- accept: The formatter config discovers exactly the current 68 paths;
  `ruff format --check` changes no bytes; the workflow contains no formatter
  file list; lint remains repository-wide; policy docs point to the correct
  config.
- forbidden: Narrowing lint discovery; expanding formatter enrollment;
  encoding the inverse set as hundreds of exclusions; editing workflow steps
  other than the formatter; formatting source files.
- verify: Ruff discovery parity, Ruff lint, configured formatter check,
  pre-commit, Mypy, repository guardrails, docs links, complete Python suite,
  and `git diff --check` as specified in the T-CI-4 plan.

### T-CI-5: Activate and ratchet the landed Ruff scope
- priority: P0 (run FIRST in Phase 0 — the allowlist is a snapshot of the
  tree at plan date and goes stale as other tasks merge)
- depends_on: T-CI-0
- status: complete and verified 2026-07-22 (PR #110)
- files_owned: docs/plans/T_CI_5_TIGHTENED_LINT_PLAN.md,
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md, AGENTS.md,
  docs/ENGINEERING_GUARDRAILS.md, tests/test_repository_guardrails.py,
  ruff.toml, .pre-commit-config.yaml,
  .github/workflows/python-guardrails.yml (ruff invocation line only)
- do: Activate the tightened Ruff configuration already on master by changing
  CI, pre-commit, and contributor commands to config-owned `ruff check .`.
  Reconcile every per-file ignore against current HEAD, remove stale selectors,
  and add persistent tests for entrypoint parity and allowlist freshness. Keep
  the existing hook ID and all rule families, exclusions, workflow behavior,
  and runtime contracts unchanged.
- accept: `ruff check .` exits 0 on HEAD; a planted DTZ003/C901 violation
  fails; pre-commit and CI use the same invocation; no per-file entry
  lists a code its file does not currently violate.
- forbidden: Widening any entry to silence a new violation; re-adding the
  pruned stale entries; enabling further rule families (I, UP, PTH, PL,
  TRY are explicitly deferred per review).
- verify: `ruff check .` (exit 0); plant-check; `pre-commit run ruff
  --all-files`; Mypy; repository guardrails; docs links; complete Python suite;
  `git diff --check`.
- ratchet_registry (entries other tasks must clear; enforced via their
  acceptance criteria): DTZ in api/pipeline/scripts -> T-TIME-1;
  crawler F401/B026/DTZ011/DTZ007/S324 -> T-CRAWL-2; S105 in
  pipeline/provider_telemetry.py + topic_generation_contracts.py ->
  T-SEC-6; S105 metrics_redis_backend.py -> T-DA-1; api/cache.py BLE001 ->
  T-PLAT-4; C901 entries -> Phase 2 refactors and T-GOV-3 exceptions
  process.

---

## 4. PHASE 1 — PARALLEL HARDENING (agents: sec, time, crawl)

### T-SEC-1: Stop publishing backing-store ports; remove default-cred blast radius
- priority: P0
- status: complete
- implementation_plan: `docs/plans/T_SEC_1_BACKEND_PORT_HARDENING_PLAN.md`
- files_owned: docs/plans/T_SEC_1_BACKEND_PORT_HARDENING_PLAN.md,
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md, docker-compose.yml,
  docker-compose.dev.yml, .env.example, tests/test_docker_build_contracts.py,
  README.md, docs/OPERATIONS.md, SECURITY.md
- do: Remove host `ports:` for postgres, redis, meilisearch, prometheus, and
  grafana from the base file. Add loopback-only development mappings to
  docker-compose.dev.yml. Label Grafana defaults as local-development values
  and synchronize operator access guidance. Add a comment that inter-container
  traffic uses the Compose network.
- accept: Base compose exposes only api:8000 and frontend:3000;
  `docker compose config` is valid; the explicit dev overlay restores local
  host access for all five moved services without publishing them beyond
  loopback.
- forbidden: Changing service images, env defaults, dependencies, credentials,
  startup-purge behavior, or the standard `scripts/dev_up.sh` path.
- verify: Follow the Full T-SEC-1 plan: base and merged Compose validation,
  Docker contract tests, startup-purge contract, Ruff, docs links, complete
  Python suite, and `git diff --check`.

### T-SEC-2: Fail fast on default API key outside dev
- priority: P0
- status: complete
- implementation_plan: `docs/plans/T_SEC_2_DEFAULT_API_KEY_PLAN.md`
- files_owned: docs/plans/T_SEC_2_DEFAULT_API_KEY_PLAN.md,
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md, api/app_setup.py,
  tests/test_api_startup_security.py, SECURITY.md
- do: In `lifespan`, require every nonempty `API_AUTH_KEY` to contain printable
  ASCII characters without leading or trailing whitespace. When normalized
  `APP_ENV != "dev"`, also reject the checked-in default after trimming or a
  blank key. Raise `RuntimeError` before database, purge, or semantic startup
  work. Read environment values through `pipeline/config_env.py`, preserve the
  default-key warning in dev, and preserve an accepted raw key for request
  authentication.
- accept: A key containing non-ASCII, control, or edge-whitespace characters
  always aborts with a clear message. Non-development boot with a default or
  blank key also aborts before downstream startup work; default-key development
  behavior is unchanged; a configured transport-safe key starts and remains
  case-sensitive; focused tests cover every branch without uncontrolled
  outbound HTTP or purge.
- verify: Targeted pytest for the new test; full suite green.

### T-SEC-3: API and semantic readers use a scoped Meilisearch search key
- priority: P1
- status: complete
- implementation_plan: `docs/plans/T_SEC_3_MEILISEARCH_SEARCH_KEY_PLAN.md`
- files_owned: docs/plans/T_SEC_3_MEILISEARCH_SEARCH_KEY_PLAN.md,
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md,
  pipeline/meilisearch_credentials.py, api/app_setup.py,
  api/search/support_core.py, semantic_service/main.py, docker-compose.yml,
  docker-compose.dev.yml, .dockerignore, .env.example, README.md,
  scripts/dev_up.sh, scripts/bootstrap_local_models.sh,
  scripts/run_soak_day.sh, frontend/.dockerignore,
  env/profiles/README.md, docs/OPERATIONS.md, SECURITY.md,
  tests/test_api_startup_security.py, tests/test_meilisearch_key_security.py,
  tests/test_docker_build_contracts.py, tests/test_run_soak_day_contract.py,
  tests/test_startup_purge_gating.py
- do: Introduce `MEILI_SEARCH_KEY` for API and semantic readers. Keep the fake
  master fallback only in development with a value-free warning; fail
  non-development startup when the scoped key is absent, equals the development
  fallback, or is unsafe. Scope the reader key to `search` and `stats.get` on
  `documents` so the existing API statistics read remains available. Remove
  the deployed master key from reader containers, require it in base Compose,
  run Meilisearch in production mode by default, and provide the key to
  pipeline writer containers. Document key creation, verification, rotation,
  and revocation.
- accept: API and semantic clients use only the scoped key when configured;
  reader containers do not receive the deployed master key or repository
  `.env`; development mounts expose only required source directories; build
  contexts exclude local environment files; base readers default to
  non-development while the overlay marks them as development; local
  bootstrap, soak recovery, and runtime profile commands preserve the
  development overlay; soak recovery explicitly disables startup purge; writer
  containers retain indexing access; isolated and deployed-key permission
  checks prove search and statistics reads succeed while write and
  administration fail.
- forbidden: Master retry, duplicate credential-policy implementations, facade
  removal before G3, public key exposure, or new client/config registries.
- verify: Follow the Full T-SEC-3 plan, including credential tests, resolved
  Compose contracts, live v1.6 permission smoke, API/semantic/indexer suites,
  Ruff, Mypy, docs links, and the complete Python suite.

### T-SEC-3C: Synchronize the Meilisearch security checklist
- priority: P1
- status: complete
- implementation_plan: `docs/plans/T_SEC_3_CHECKLIST_CLOSURE_PLAN.md`
- files_owned: docs/plans/T_SEC_3_CHECKLIST_CLOSURE_PLAN.md,
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md, SECURITY.md
- do: Verify the merged T-SEC-3 evidence, check its canonical `SECURITY.md`
  item, and return T-SEC-3 to complete without reopening runtime code.
- accept: The security checklist and remediation status agree; merged
  T-CRAWL-1 is recorded complete; no unrelated checklist item changes.
- forbidden: Runtime security changes, policy expansion, or edits outside the
  three owned files.
- verify: Docs links, targeted contradiction checks, clean diff, current-head
  review, and green PR checks.

### T-SEC-4A: Record the approved G2 visitor-access policy
- priority: P0
- status: in progress
- decision_gate: G2 operator approval received 2026-07-24; durable record
  pending this task
- implementation_plan: `docs/plans/T_SEC_4A_G2_VISITOR_ACCESS_POLICY_PLAN.md`
- files_owned: docs/plans/T_SEC_4A_G2_VISITOR_ACCESS_POLICY_PLAN.md,
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md, SECURITY.md,
  tests/test_repository_guardrails.py
- do: Record the approved visitor-access policy, its rationale, the interim
  accepted risk, and its dependency on T-SEC-4 without changing runtime code.
- accept: `SECURITY.md` and the remediation ledger agree; policy tests prevent
  status/risk drift; T-SEC-4 remains pending.
- forbidden: Runtime changes, operator-auth implementation, G3 content, or
  edits outside `files_owned`.
- verify: Follow the Full T-SEC-4A plan, including tests-first evidence,
  guardrail and docs verification, the complete Python suite, independent
  review, and decided CI.

### T-SEC-4: Real client identity through the proxy; per-client rate limits
- priority: P0
- decision_gate: G2 approved 2026-07-24
- files_owned: frontend/app/api/_lib/backend.js, api/app_setup.py
- do: (a) backend.js forwards `X-Forwarded-For` (append client IP from
  request) on proxied calls. (b) app_setup limiter key_func: trust XFF only
  when the direct peer is in a configured internal CIDR/hostname allowlist
  (env `TRUSTED_PROXY_CIDRS`, default the compose network); otherwise use
  remote address.
- accept: Two distinct simulated client IPs get independent rate buckets;
  spoofed XFF from a non-trusted peer is ignored (tests for both).
- forbidden: Global middleware rewrites; no new middleware class if a
  key_func suffices.
- verify: New targeted tests pass; suite green.

### T-SEC-5: CSRF/origin check on proxy mutation routes
- priority: P1
- status: complete and verified 2026-07-24 (PR #130)
- implementation_plan: `docs/plans/T_SEC_5_PROXY_ORIGIN_GUARD_PLAN.md`
- files_owned: docs/plans/T_SEC_5_PROXY_ORIGIN_GUARD_PLAN.md,
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md, SECURITY.md,
  frontend/app/api/**,
  frontend/components/__tests__/BackendProxy.origin.test.js
- do: In proxyBackendJson (or a small shared check), reject POSTs whose
  Origin/Sec-Fetch-Site indicate a non-same-origin browser request with 403.
  Same-origin and non-browser calls pass.
- accept: Cross-origin POST to /api/summarize/* returns 403; app UX
  unchanged; `node:test` coverage added.
- verify: Follow the Full T-SEC-5 plan, including tests-first evidence,
  frontend tests and build, Python frontend contracts, full-suite
  verification, independent review, and diff checks.

### T-SEC-6: Small closures
- priority: P2
- files_owned: .env.example, api/main.py (named sections only),
  pipeline/provider_telemetry.py, pipeline/topic_generation_contracts.py
- do: (a) Delete NEXT_PUBLIC_API_AUTH_KEY from .env.example. (b) Remove
  `allow_credentials=True` from CORS. (c) Gate `/stats` behind
  verify_api_key or reduce payload to counts only. (d) Resolve the S105
  hardcoded-secret findings in the two pipeline files above: replace with
  env-sourced values or, where the string is not actually a secret
  (telemetry field names, contract constants), add `# noqa: S105` with a
  one-line justification; then remove those ruff.toml per-file entries
  (ratchet from T-CI-5).
- accept: Each item verified by grep/test; no S105 per-file entries remain
  for the owned files; suite green.

### T-TIME-1: One clock — timezone-aware timestamps everywhere
- priority: P1
- files_owned: pipeline/model_civic.py, model_events.py, model_records.py
- do: All DateTime columns become `DateTime(timezone=True)` with
  `server_default=func.now()` (and `onupdate=func.now()` where present).
  Remove `datetime.now` / `utcnow` column defaults. Audit
  summary_freshness.py comparisons for naive/aware mixing (report only;
  fix in this task only if a comparison breaks).
- accept: No `datetime.datetime.now`/`utcnow` defaults remain in model
  files; the DTZ per-file-ignore entries in ruff.toml for the api/pipeline
  files this task fixes are REMOVED (ratchet from T-CI-5); note DTZ flags
  calls only — column defaults reference callables, so also add a
  guardrail-test assertion that model files contain no naive default
  callables; suite green.
- depends_on: T-TIME-2 for existing DBs.
- verify: grep + full suite.

### T-TIME-2: Migration for timestamp columns
- priority: P1
- files_owned: pipeline/migrate_v10.py (new), pipeline/db_migrate.py
- do: Additive migration converting existing columns to timestamptz
  (`ALTER ... TYPE timestamptz USING <col> AT TIME ZONE 'UTC'`). Wire into
  run_migrations after v9. If G5=yes and T-PLAT-1 has merged first, author
  as an Alembic revision instead.
- accept: Migration idempotent (safe re-run); documented in db_migrate
  docstring.
- verify: Run against a dev DB snapshot; suite green.

### T-TIME-3: pool_pre_ping
- priority: P2
- status: complete and verified 2026-07-23 (PR #127)
- implementation_plan: `docs/plans/T_TIME_3_POOL_PRE_PING_PLAN.md`
- files_owned: docs/plans/T_TIME_3_POOL_PRE_PING_PLAN.md,
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md,
  pipeline/model_runtime.py, tests/test_database.py
- do: Add `pool_pre_ping=True` only to the PostgreSQL `create_engine` kwargs.
  Preserve explicit SQLite and missing-URL behavior.
- accept: PostgreSQL checkout performs one liveness query and replaces stale
  pooled connections before use; existing pool settings remain unchanged;
  SQLite receives no PostgreSQL pool arguments. Pre-ping does not recover a
  disconnect during an active transaction.
- verify: Follow the Full T-TIME-3 plan: tests-first red evidence, Ruff,
  Mypy, database tests, docs links, the complete coverage-enabled Python
  suite, independent review, and `git diff --check`.

### T-CRAWL-1: Honest crawler identity
- priority: P1
- status: complete
- implementation_plan: `docs/plans/T_CRAWL_1_HONEST_CRAWLER_IDENTITY_PLAN.md`
- files_owned: docs/plans/T_CRAWL_1_HONEST_CRAWLER_IDENTITY_PLAN.md,
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md,
  council_crawler/council_crawler/settings.py,
  council_crawler/council_crawler_readme.md,
  tests/test_crawler_settings_contract.py
- do: Replace the spoofed Chrome UA with
  `TownCouncilBot/1.0 (+<repo-or-contact-url>)`. Keep ROBOTSTXT_OBEY,
  DOWNLOAD_DELAY. Update the now-accurate comment.
- accept: UA identifies the project; no other settings changed.
- verify: grep; run one spider dry parse against tests/mock_dublin.html
  fixtures if wired.

### T-CRAWL-2: Fold fork-style spiders onto the template layer
- priority: P1
- status: complete
- implementation_plan: `docs/plans/T_CRAWL_2_TEMPLATE_REFACTOR_PLAN.md`
- files_owned: docs/plans/T_CRAWL_2_TEMPLATE_REFACTOR_PLAN.md,
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md, ruff.toml,
  tests/test_crawler_refactor_contract.py,
  tests/test_repository_guardrails.py,
  council_crawler/council_crawler/pipelines.py,
  council_crawler/council_crawler/utils.py,
  council_crawler/council_crawler/spiders/base.py,
  council_crawler/council_crawler/spiders/ca_belmont.py,
  council_crawler/council_crawler/spiders/ca_berkeley.py,
  council_crawler/council_crawler/spiders/ca_cupertino.py,
  council_crawler/council_crawler/spiders/ca_dublin.py,
  council_crawler/council_crawler/spiders/ca_fremont.py,
  council_crawler/council_crawler/spiders/ca_hayward.py,
  council_crawler/council_crawler/spiders/ca_moraga.py,
  council_crawler/council_crawler/spiders/ca_mtn_view.py,
  council_crawler/council_crawler/spiders/ca_san_leandro.py,
  council_crawler/council_crawler/spiders/ca_san_mateo.py,
  council_crawler/council_crawler/spiders/ca_sunnyvale.py,
  council_crawler/templates/legistar_cms.py
- do: Refactor the three 60–80-line copy-paste spiders into thin subclasses
  of the existing template/base (target: parity with the 14-line spiders).
  Extract genuinely city-specific deltas into overrides. Byte-identical
  scraped-item output is the bar.
- accept: Each refactored spider <= ~25 lines of city-specific code;
  existing crawler tests green; duplicate-window count between these files
  drops to ~0; ALL council_crawler per-file entries in ruff.toml are
  cleared (ratchet from T-CI-5): F401 unused imports and B026 star-arg
  ordering are one-line fixes across the thin spiders too, DTZ007/DTZ011
  (fremont, san_mateo) get tz-aware parsing, and utils.py S324 becomes
  `hashlib.md5(..., usedforsecurity=False)` — it is URL fingerprinting,
  not crypto; content-hash values must remain byte-identical.
- forbidden: New template files; touching working thin spiders; changing
  item schemas.
- verify: Suite green; run each refactored spider against recorded/mock
  fixtures where available.

---

## 5. PHASE 2 — DEDUPLICATION & DE-FACADING

Shared directive for all Phase 2 tasks: when a test patches a facade symbol,
repoint the test at the implementation module. Delete the facade seam. Never
preserve both. Guardrail-file edits limited to removing entries for deleted
files (GED-5 grant).

### T-DA-1: Collapse the metrics twins
- priority: P1
- files_owned: pipeline/metrics.py, pipeline/metrics_redis_backend.py,
  tests/test_*metrics*
- do: Single source of truth for the redis client state machine and
  `_redis_incr/_redis_hincrby/_redis_hincrbyfloat` (keep them in
  metrics_redis_backend). metrics.py imports and calls; delete its
  duplicated implementations and BOTH `_sync_redis_*` functions and the
  duplicated module globals.
- accept: One implementation of each function repo-wide; zero
  `_sync_redis_*` symbols; the S105 ruff.toml entry for
  metrics_redis_backend.py is resolved and removed (env-source the default
  or noqa-with-justification; ratchet from T-CI-5); metrics tests green
  after repointing patches.
- verify: grep for sync fns returns nothing; full suite green.

### T-DB-1: Collapse the summary_backfill facade
- priority: P1
- files_owned: pipeline/summary_backfill*.py, tests/test_*backfill*
- do: Callers import run_summary_hydration_backfill from
  summary_backfill_runner directly (or keep summary_backfill.py as a pure
  one-line re-import, no signature duplication, no conditional **splats).
  Reduce injectable-callable params to the boundary fakes tests actually
  need (DB session factory, summary callable); repoint tests for the rest.
- accept: <= 8 params on the public signature; no conditional dict-splat
  forwarding; backfill tests green.
- verify: Full suite green.

### T-DC-1: Remove the api.main <-> app_setup sync machinery
- priority: P1
- must_not_run_concurrently_with: any SEC task
- files_owned: api/main.py, api/app_setup.py, tests/conftest.py,
  tests/test_*api*
- do: app_setup owns SessionLocal/_db_init_error/verify_api_key/lifespan as
  the single authority. Delete `_sync_app_setup_from_facade`,
  `_sync_facade_from_app_setup`, the wrapper defs in main.py, the
  `hmac = app_setup.hmac` rebind, and the `X as X` re-export blocks whose
  only consumers are tests. Repoint tests (conftest.py "api.main.db_connect"
  patch -> pipeline/app_setup target).
- accept: main.py contains no bidirectional sync functions; no stdlib
  re-exports; suite green.
- risk: Highest-touch task in the plan. Land as one PR; do not interleave.
- verify: Full suite + a manual `uvicorn api.main:app` boot smoke.

### T-DD-1: Consolidate twin scripts
- priority: P2
- files_owned: per lane table (flush/reset city state, worker healthchecks)
- do: Extract the 26-window shared core of flush_city_pipeline_state /
  reset_city_verification_state into one shared helper module in scripts/;
  same for the two healthchecks. CLIs keep identical names, flags, output.
- accept: Duplicate-window count between each pair ~0; CLI contract
  unchanged (capture before/after --help and a dry-run output).
- verify: Suite green; manual dry-run parity.

### T-DE-1: Shared provider retry/telemetry
- priority: P2
- files_owned: http_inference_provider.py, inprocess_inference_provider.py,
  inference_provider_contract.py, tests for same
- do: Move the 23 duplicated windows (retry/telemetry scaffolding) into the
  contract module or a small shared helper; providers call it. No behavior
  change: error mapping and fail-fast semantics are covered by
  tests/test_provider_error_mapping_retry_vs_fallback.py — it must pass
  unmodified.
- accept: Duplication between providers ~0; that guardrail test green
  UNCHANGED.
- verify: Full suite.

---

## 6. PHASE 3 — PLATFORM & GOVERNANCE (agents: plat, gov; after Phase 1)

### T-PLAT-1: Alembic baseline (gate G5)
- priority: P1
- files_owned: alembic/** (new), pipeline/db_migrate.py (deprecation note),
  docs/OPERATIONS.md (migration section)
- do: `alembic init`; autogenerate a baseline revision from current models
  (post T-TIME-1); stamp existing dev DBs; document the workflow. Keep
  migrate_v* chain readable but frozen (no v11+).
- accept: Fresh DB via alembic == create_all schema (diff empty);
  OPERATIONS documents upgrade/downgrade.
- verify: Schema diff script output empty; suite green.

### T-PLAT-2A: Patch Next.js's transitive Sharp runtime
- priority: P0 (urgent dependency security patch)
- status: complete and verified 2026-07-23 (PR #128; Dependabot alert 106 fixed)
- implementation_plan: `docs/plans/T_PLAT_2A_SHARP_SECURITY_PATCH_PLAN.md`
- files_owned: docs/plans/T_PLAT_2A_SHARP_SECURITY_PATCH_PLAN.md,
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md, frontend/package.json,
  frontend/package-lock.json,
  frontend/components/__tests__/SharpDependency.security.test.js
- do: Pin Sharp 0.35.3 only beneath Next.js through npm's nested override,
  regenerate the lockfile without lifecycle scripts, then verify a clean
  install, native module load, frontend tests, production build, and
  high-severity audit.
- accept: Next.js remains 16.2.11; the manifest and lockfile select Sharp
  0.35.3; `npm ci`, the native Sharp smoke, frontend tests, production build,
  and `npm audit --omit=dev --audit-level=high` pass; Dependabot alert 106
  closes after merge.
- forbidden: `npm audit fix --force`, a Next.js downgrade, a direct Sharp
  application dependency, audit suppression, or unrelated dependency churn.
- verify: Follow the Full T-PLAT-2A plan, including tests-first red evidence,
  lockfile-only generation, clean install, native and Docker build smokes,
  frontend tests, audit, docs links, independent review, and diff checks.

### T-PLAT-2: Dependency hygiene
- priority: P2
- files_owned: requirements files, constraints.txt (new),
  .github/dependabot.yml (new), python-guardrails.yml (audit step),
  frontend-tests.yml (audit step)
- do: (a) Shared constraints.txt for pins duplicated across the three
  Python requirements files; requirements reference it. (b) Dependabot for
  pip + npm + actions, weekly. (c) `pip-audit` and `npm audit --audit-level=high`
  CI steps, initially non-blocking (report-only), promote later.
- accept: One authoritative pin per shared package; audits visible in CI.
- verify: Images build; suite green.

### T-PLAT-3: Backup/restore runbook
- priority: P1
- files_owned: docs/OPERATIONS.md (new section), scripts/backup_db.sh (new)
- do: pg_dump-based backup script (custom format), restore procedure,
  cadence recommendation, and an explicit note on the STARTUP_PURGE
  interaction (purge is derived-only; backups still cover system of record).
- accept: Documented, script exits 0 against dev stack.
- verify: Manual run against dev compose.

### T-PLAT-4: cache.py right-sizing
- priority: P3
- files_owned: api/cache.py, api/search_read_routes.py
- do: Either (a) inline a purpose-built cache at the single call site and
  delete the generic decorator, or (b) keep the decorator but build keys
  from explicit primitives (not `str(args)`) and drop the hardcoded
  password default. Default: (a). Remove the api/cache.py BLE001 ruff.toml
  entry (ratchet from T-CI-5).
- verify: Suite green; endpoint behavior unchanged.

### T-GOV-1: ADR — "Test patch points are not a public API" (gate G3)
- priority: P0 (unblocks Phase 2)
- status: complete and verified 2026-07-24
- implementation_plan:
  `docs/plans/T_GOV_1_TEST_PATCH_POINTS_ADR_PLAN.md`
- files_owned: api/search/support_core.py (comment only), docs/ADR.md,
  docs/TESTING.MD, docs/plans/T_GOV_1_TEST_PATCH_POINTS_ADR_PLAN.md,
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md,
  tests/test_repository_guardrails.py
- do: Add an Accepted entry per the existing ADR format. Tests patch
  implementation modules or fake at the boundaries in docs/TESTING.MD.
  Explicitly supersede prior statements only to the extent that they preserve
  test-only patch targets; retain mixed runtime, import, CLI, API,
  task-identity, and operational contracts without rewriting historical ADR
  entries. Activate the testing policy, remove the stale live G3 deferral
  comment, and enforce the decision with repository guardrails.
- coordination: T-GOV-6 remains partially landed after this task because its
  README Documentation Map links remain missing and are outside T-GOV-1
  ownership.
- accept: Accepted ADR merged; testing policy effective; no live source treats
  G3 as a facade deferral; Phase 2 G3 blocker removed; runtime behavior and
  public contracts unchanged.
- forbidden: Facade removal, runtime/import/API changes, historical ADR
  rewrites, new fake boundaries, or edits outside `files_owned`.
- verify: Follow the Full T-GOV-1 implementation plan; Ruff, Mypy, repository
  guardrails, docs links, Meilisearch key-security tests, and the complete
  Python suite pass.

### T-GOV-2: ADR — Person-entity minimization & takedown (gate G4)
- priority: P1
- files_owned: docs/ADR.md
- do: Draft decision options for the user: (a) entity-link only persons
  matching official rosters (person_linker gate), (b) index commenter names
  but exclude from people profiles/metadata, (c) status quo + documented
  takedown SLA via the existing report-issue path. Include retention stance
  and correction workflow. Users selects; agent records.
- accept: ADR merged with a selected option; follow-up implementation task
  filed (out of scope here).

### T-GOV-3: Redesign the guardrail regime (after >= 2 Phase 2 tasks merge)
- priority: P2
- files_owned: tests/test_repository_guardrails.py,
  docs/ENGINEERING_GUARDRAILS.md
- coordination: T-CI-0 may edit only the broad-handler structural-policy prose
  needed to align PR #108 enforcement. T-GOV-3 retains the later structural-rule
  redesign and must preserve or deliberately supersede that contract.
- do: Replace enumerated 300-line file lists with general rules:
  (a) complexity ceiling — DELIVERED by T-CI-5 (ruff C901, max-complexity
  10, offenders allowlisted and ratcheting); this task only documents its
  exception process and removes the corresponding [transition] marker in
  ENGINEERING_GUARDRAILS.md;
  (b) import-direction rule generalized from the semantic_service pattern
  (helpers must not import their facade); (c) new smell checks banning
  `_sync_*_from_*` bidirectional-global patterns and f-string interpolation
  inside `text(...)` DDL; (d) delete line-count checks for recombined files.
- accept: Guardrail file shrinks materially; no enumerated per-file line
  lists for the collapsed families; CI green.
- verify: Full suite + guardrail tests green.

### T-GOV-4: Land the revised AGENTS.md
- priority: P1
- files_owned: AGENTS.md
- depends_on: none for the antipatterns/security/hierarchy edits; the
  verification-matrix and action-permission edits carry [transition]
  markers tied to T-CI-1/T-CI-2.
- do: Merge the provided draft (drafts/AGENTS.md). Verify every section not
  named in the draft changelog is byte-identical to master (the revision is
  surgical: canonical-doc list, hierarchy #1 clarification, new
  <known_antipatterns>, full-pytest permission move, matrix scope preamble +
  frontend npm row + mandatory cross-cutting sweep, new
  <security_sensitive_paths>, docs enumeration rule, checklist line,
  maintenance triggers). When T-CI-1 and T-CI-2 merge, remove the two
  [transition] markers in a follow-up commit.
- forbidden: Re-authoring policy text; reflowing unchanged sections.
- accept: Diff against master touches only the enumerated sections;
  docs-link test green.
- verify: `PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py`

### T-GOV-5: Land the rewritten ENGINEERING_GUARDRAILS.md
- priority: P1
- depends_on: T-CI-4 (formatter scope in ruff-format.toml); coordinates with
  T-GOV-3 (structural rules).
- files_owned: docs/ENGINEERING_GUARDRAILS.md
- coordination: T-CI-0's narrow broad-handler structural-policy correction lands
  first. T-GOV-5 must carry the corrected policy into the rewritten document and
  must not restore final-statement or `sys.exit()` authorization.
- do: Merge the provided draft (drafts/docs/ENGINEERING_GUARDRAILS.md) in
  the same PR as T-CI-4 or immediately after. Reconcile [transition]
  markers: T-CI-4 marker removed when the `ruff-format.toml` scope is live;
  T-GOV-3
  markers removed as each structural rule gains enforcement. The typed
  subtree list must be confirmed present in mypy.ini before deleting the
  doc enumeration (it already is — verify, don't assume).
- forbidden: Reintroducing any file enumeration; deleting the boundary-
  handler or exception-process prose.
- accept: No file-set enumerations remain in the doc; every scope statement
  points at a config location that actually contains the scope; docs-link
  test green.
- verify: docs-link test; grep the doc for `.py` path lists (should find
  none beyond illustrative single examples).

### T-GOV-6: Introduce SECURITY.md, docs/TESTING.md, docs/DATA_GOVERNANCE.md
- priority: P1 (SECURITY.md, TESTING.md), P2 (DATA_GOVERNANCE.md)
- files_owned: SECURITY.md (new), docs/TESTING.md (new),
  docs/DATA_GOVERNANCE.md (new), README.md (Documentation Map section only)
- sequencing: SECURITY.md merges at Phase 1 start (it is the reference for
  SEC-lane PR impact statements; its checklist items cite T-SEC tasks as
  pending — that is intentional, update checkboxes as tasks merge).
  TESTING.md is active with the G3 ADR (T-GOV-1) as its operational companion.
  T-GOV-6 remains partially landed until its three canonical documents are
  linked from the README Documentation Map. DATA_GOVERNANCE.md merges any time;
  its Section 3 stays in "options + working default" form until the user
  resolves G4, then the G4 ADR task replaces Section 3 with the adopted policy.
- do: Merge the provided drafts. Add the three documents to the README
  Documentation Map. The user fills the deployment-posture blank in
  SECURITY.md (G1) before or at merge.
- forbidden: Resolving G1/G2/G4 by editing defaults; adding further new
  documents (net-new doc budget for this remediation is exactly these
  three).
- accept: All three merged and linked from README; docs-link test green;
  no decision gate silently resolved.
- verify: `PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py`

---

## 7. EXECUTION ORDER SUMMARY

```
Phase 0: agent-ci  [T-CI-0, then T-CI-5 (allowlist snapshot freshness), then T-CI-1 .. T-CI-4]
Docs-0:  agent-gov [T-GOV-6: SECURITY.md] + [T-GOV-4: AGENTS.md]   (with/just after Phase 0)
Phase 1: agent-sec [T-SEC-1..6] || agent-time [T-TIME-1..3] || agent-crawl [T-CRAWL-1..2]
Gate:    G3 satisfied (T-GOV-1 Accepted ADR + active docs/TESTING.MD)
Phase 2: agent-da || agent-db || agent-dd || agent-de ; then agent-dc (exclusive on api/*)
Phase 3: agent-plat [T-PLAT-1..4] || agent-gov [T-GOV-2, T-GOV-3 + T-GOV-5]
Anytime: T-GOV-6 DATA_GOVERNANCE.md (Section 3 pending G4)
```

Merge policy: one task = one PR; PR title = task id; every PR body includes
the GED-6 report. Any agent that cannot satisfy acceptance criteria within
its owned files reports and halts rather than widening scope.

## 8. OUT OF SCOPE (explicitly deferred; do not attempt)

- Splitting frontend/components/ResultCard.js (needs a design pass, not a
  mechanical one; schedule after T-CI-2 provides a harness).
- "Operator-only" auth on the Next proxy (not approved by G2; requires a
  future policy change).
- Retiring generational strata (search_routes/search_read/api-search;
  migrate_v* files) beyond what Phase 2 tasks name.
- env-access consolidation into config_env (low value until Phase 2 lands).
- Any change to inference runtime policy, models, or soak baselines.
