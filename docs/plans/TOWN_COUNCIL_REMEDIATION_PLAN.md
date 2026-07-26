# Town Council Remediation Plan (Codex Multi-Agent)

version: 3.55
generated: 2026-07-26
source: Four-pass external code review (security, architecture, smells, process)
source_artifact: [Town Council architecture review](../reviews/architecture-review-2026-07-19.html)
orchestrator_contract: Codex instantiates one agent per lane. Agents run in
parallel ONLY within the same phase and ONLY on their owned paths. AGENTS.md
remains in force; where this plan is stricter, this plan wins for these tasks.

## Changelog

- **v3.55:** Marks T-PLAT-2B complete after PR #152 merged and Dependabot
  alerts 116 through 119 closed as fixed. Splits the inaccurate T-DD-1 task
  into T-DD-1A worker-healthcheck consolidation and T-DD-1B city-state
  mutation analysis. Activates T-DD-1A with exact ownership for all three
  worker healthcheck CLIs, a focused shared probe owner, parity tests, Docker
  contracts, and its Full implementation plan.
- **v3.54:** Marks T-PLAT-1 and T-PLAT-1A complete after PRs #150 and #151
  merged with required checks green and the late migration-outcome review
  thread resolved. Activates T-PLAT-2B before broader dependency hygiene to
  patch four open pypdf advisories, including two high-severity findings,
  without mixing audit or constraints work into the urgent pin update. The
  task also broadens malformed-PDF handling to pypdf's documented base
  exception and removes the obsolete table-worker BLE001 allowance.
- **v3.53:** Registers T-PLAT-1A after a late PR #150 review finding showed
  that direct migration commands discard the INFO outcome used to decide
  whether derived embeddings need rehydration. T-PLAT-1 remains implemented
  but acceptance-incomplete until the CLI makes that outcome visible. Broader
  dependency work remains pending.
- **v3.52:** Grants T-PLAT-1 narrow ownership of `ruff.toml` to remove the
  stale `pipeline/db_migration_runner.py` BLE001 selector after the strict
  legacy runner eliminated its broad handler. No Ruff rule, source scope, or
  other exception changes.
- **v3.51:** Marks coordinated T-TIME-1 and T-TIME-2 complete after PR #148
  merged with PostgreSQL migration evidence and activates T-PLAT-1. Expands
  T-PLAT-1 ownership for its Full plan, strict legacy runner, focused Alembic
  owner, typed schema contracts, parity CLI, and G5 status sync. Acceptance now
  requires all four legacy-only indexes, one caller-owned transaction,
  immediate transaction-lock conflict, complete object parity before stamp,
  fail-fast setup ordering, and no optional PostgreSQL migration skips in CI.
- **v3.50:** Activates T-TIME-1 and T-TIME-2 as one operator-approved
  coordinated PR because model-only or schema-only deployment is unsafe.
  Defines ten generated timestamps with server defaults, preserves three
  nullable lifecycle markers without defaults, makes v10 mandatory and
  fail-fast, and requires PostgreSQL CI evidence. Temporary coordination
  grants cover the exact CI, CRAWL, DEDUP-C, DEDUP-D, PLAT, and GOV paths in
  the shared Full plan.
- **v3.49:** Completes T-DB-1B. PR #146 removed maintenance fallback callable
  injection and the superseded summary facades, passed the complete local and
  CI suites, resolved its review finding, and merged as `9132864`. The
  temporary twenty-eight-file coordination grant is released.
- **v3.48:** Resolves the T-DB-1B remote review P1 by replacing newly added
  mock call-count assertions with observable fake-boundary state and persisted
  outcomes. Existing historical tests outside this migration remain deferred
  to their owning remediation tasks.
- **v3.47:** Expands T-DB-1B ownership to the agenda-summary maintenance owner
  maps in `ARCHITECTURE.md` and `docs/PIPELINE.md`. Independent review found
  both canonical maps still named the facade and callback adapter deleted by
  this task. A structural guardrail now prevents those stale active references
  from returning.
- **v3.46:** Activates T-DB-1B with exact ownership for maintenance summary,
  staged hydration, repaired summary hydration, affected tests, structural
  guardrails, and ADR synchronization. A temporary exclusive coordination
  grant makes this task-level list authoritative over the broader DEDUP-B and
  GOV lane rows. The task removes remaining dependency callable chains while
  preserving runtime and operator contracts.
- **v3.45:** Completes T-DB-1. The summary backfill runner now owns the
  operation directly, all tracked callers use the runner or query owner,
  task-facade exports are removed, and tests exercise approved runtime
  boundaries.
- **v3.44:** Activates T-DB-1 with expanded ownership for every tracked
  runtime caller, structural guardrails, and ADR sync. Registers T-DB-1B for
  the separate maintenance-fallback and staged-hydration callable chains found
  during independent planning review.
- **v3.43:** Completes T-DB-1A. Summary generation now has one direct
  operation owner, lower modules import domain implementations directly, and
  tests use approved runtime boundaries instead of facade service injection.
- **v3.42:** Adds T-DB-1A before the broader backfill cleanup. The focused
  task removes summary-generation callable service injection and globals-based
  facade forwarding while preserving the registered Celery task and approved
  runtime boundaries.
- **v3.41:** Prevents T-PLAT-1 and T-GOV-3 from running concurrently while
  both own focused changes in `tests/test_repository_guardrails.py`.
- **v3.40:** Requires T-PLAT-1 to inventory and encode schema objects created
  only by legacy raw SQL, preventing baseline autogeneration from omitting
  indexes that current model metadata does not declare.
- **v3.39:** Adds the canonical `ARCHITECTURE.md` migration map to T-PLAT-1
  ownership so Alembic adoption cannot leave the system map on the retired
  numbered-only design.
- **v3.38:** Closes three T-PLAT-1 implementation gaps: frozen v8 metadata for
  delayed adopters, mandatory PostgreSQL migration CI, and synchronized
  pipeline and city-contributor migration guidance.
- **v3.37:** Gives T-TIME-2 ownership of focused v10 migration and ordering
  tests so the final numbered migration cannot land unverified before the
  Alembic baseline.
- **v3.36:** Adds `seed_places.py` and `promote_stage.py` plus their affected
  tests to T-PLAT-1 ownership. Operational entrypoints may no longer call
  `create_tables()` outside the Alembic migration path.
- **v3.35:** Routes T-PLAT-1 through the canonical fresh-database contributor
  workflow by adding `pipeline/db_init.py`, `scripts/dev_up.sh`, README setup
  guidance, and their contract tests to task ownership.
- **v3.34:** Adds `tests/test_db_migrate.py` to T-PLAT-1 ownership so Alembic
  adoption can replace obsolete legacy-runner assertions without preserving
  compatibility seams solely for tests.
- **v3.33:** Records operator approval of G5 and fixes migration sequencing:
  T-TIME-1 updates model declarations, T-TIME-2 converts existing databases
  through the final numbered migration, and T-PLAT-1 then establishes the
  Alembic baseline. The baseline task must preserve the canonical pipeline
  entrypoint and prove legacy-schema parity before stamping. Implementation
  remains pending.
- **v3.32:** Marks T-DA-1 complete after removing duplicated Redis state,
  facade synchronization, dynamic metric lookups, and injected write
  callables. One collector now owns each provider series, preserves local
  fallback during Redis degradation, and emits canonical metadata.
- **v3.31:** Preserves provider telemetry during T-DA-1 Redis degradation.
  The sole registry-owning collector exports healthy Redis aggregates and
  falls back to existing process-local instruments for unavailable, read-error,
  and write-error states. Counter metadata must remain canonical.
- **v3.30:** Expands T-DA-1 ownership to provider metric registration after
  pre-commit review exposed duplicate local and Redis-backed Prometheus series.
  The Redis collector becomes the sole registry owner for mirrored provider
  metrics; request duration remains locally registered.
- **v3.29:** Activates T-DA-1 with tests-first ownership for a single Redis
  metrics state owner, direct backend test patches, and removal of the stale
  metrics S105 exception.
- **v3.28:** Marks T-GOV-5 complete after independently verifying the landed
  engineering guardrails rewrite, correcting three stale policy claims, and
  adding a durable completion contract. Exact identity with the unavailable
  original draft remains unverified.
- **v3.27:** Activates T-GOV-5 closure for the rewritten engineering
  guardrails policy. Expands ownership to its Full plan, durable completion
  guardrail, and ledger state while preserving the pending T-GOV-3 structural
  transition.
- **v3.26:** Marks T-GOV-4 complete after auditing policy commit `453c386`,
  correcting two testing-policy path references, and adding a durable
  completion guardrail.
- **v3.25:** Activates the T-GOV-4 closure audit for the revised `AGENTS.md`
  policy that landed in commit `453c386`; adds plan, ledger, guardrail, and
  two testing-policy path-casing corrections without re-authoring policy.
- **v3.24:** Marks T-SEC-6 complete after PR #138 merged as `1805acd`.
  Public stats now expose only document count, credentialed CORS is disabled,
  stale browser-key guidance is removed, and two broad S105 exceptions are
  replaced by ten explained line-level suppressions.
- **v3.23:** Activates T-SEC-6 with tests-first ownership for public stats
  minimization, credential-free CORS, stale public-key guidance removal, and
  exact line-level S105 explanations.
- **v3.22:** Marks T-SEC-4 complete after PR #136 merged as `2cbaf7e` with
  Frontend Tests, Python Guardrails, and CodeQL green. Codex found no major
  issues on implementation commit `0f1332a`. Caddy is now the sole public
  frontend entry, and authenticated frontend requests receive per-client
  limiter keys.
- **v3.21:** Starts T-SEC-4 implementation after tests-first evidence. Records
  Caddy as sole public frontend entry, validated client forwarding, raw API
  peer preservation, the deployment-key trust boundary, and the
  operator-approved startup-path ownership found during pre-commit review.
- **v3.20:** Authorizes T-SEC-4 after operator approval of a repository-owned
  Caddy ingress. Expands ownership for sole-entry topology, trusted
  frontend-to-API client identity, tests, security policy, and operations.
- **v3.19:** Marks T-SEC-4A complete after PR #133 merged the durable G2
  visitor-access policy record with required checks green. T-SEC-4 remains
  pending as the authorized runtime control.
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
| **Complete** | T-CI-0, T-CI-1, T-CI-1A, T-CI-2, T-CI-2A, T-CI-3, T-CI-4, T-CI-5, T-SEC-1, T-SEC-2, T-SEC-3, T-SEC-3C, T-SEC-4, T-SEC-4A, T-SEC-5, T-SEC-6, T-TIME-1, T-TIME-2, T-TIME-3, T-CRAWL-1, T-CRAWL-2, T-PLAT-1, T-PLAT-1A, T-PLAT-2A, T-PLAT-2B, T-GOV-1, T-GOV-4, T-GOV-5, T-DA-1, T-DB-1A, T-DB-1, T-DB-1B |
| **In progress** | T-DD-1A |
| **Partially landed; acceptance incomplete** | T-GOV-6 |
| **Pending** | T-DC-1, T-DD-1B, T-DE-1, T-PLAT-2, T-PLAT-3, T-PLAT-4, T-GOV-2..3 |

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
  and task-status routes remain public. T-SEC-4 is complete; operator-only
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
- G5 migration_tooling: **Approved 2026-07-24.** Adopt Alembic through
  T-PLAT-1 after T-TIME-1 and T-TIME-2. Freeze the readable `migrate_v*`
  chain after the baseline; author all later schema changes as Alembic
  revisions.

---

## 2. LANES AND FILE OWNERSHIP (conflict-free parallelism)

| lane      | agent id   | owned paths (exclusive within phase)                      |
|-----------|-----------|------------------------------------------------------------|
| CI        | agent-ci   | .github/workflows/**, ruff.toml, ruff-format.toml (new), .pre-commit-config.yaml, .coveragerc, frontend/package.json, frontend/jest.config.* (new) |
| SEC       | agent-sec  | docker-compose.yml, docker-compose.dev.yml, .dockerignore, .env.example, api/app_setup.py, api/main.py (CORS+/stats sections only), api/search/support_core.py, pipeline/meilisearch_credentials.py, semantic_service/main.py, frontend/app/api/** |
| TIME      | agent-time | pipeline/model_base.py, model_civic.py, model_events.py, model_records.py, model_runtime.py, models.py, db_migrate.py, db_migration_runner.py, migrate_v10.py (new), tests/test_migrate_v10.py (new), tests/test_db_migrate.py (T-TIME-2 v10 ordering only), pipeline/summary_freshness.py (verify-only) |
| CRAWL     | agent-crawl| council_crawler/**                                          |
| DEDUP-A   | agent-da   | pipeline/metrics.py, pipeline/metrics_redis_backend.py, tests/test_*metrics* |
| DEDUP-B   | agent-db   | pipeline/summary_backfill*.py, pipeline/task_summary_generation*.py, pipeline/task_summary_empty_agenda.py, pipeline/task_summary_side_effects.py, pipeline/task_facade_helpers.py, pipeline/tasks.py, pipeline/run_pipeline.py (T-DB-1 only), pipeline/backlog_maintenance.py (T-DB-1B only), pipeline/agenda_summary_maintenance.py (T-DB-1B only), pipeline/agenda_summary_fallback.py (T-DB-1B only), pipeline/non_agenda_summary_fallback.py (T-DB-1B only), pipeline/agenda_summary_batch.py (T-DB-1B only), scripts/backfill_summaries.py, scripts/staged_hydrate_cities.py, scripts/profile_pipeline_selection.py, scripts/staged_hydration_runner.py (T-DB-1B only), ARCHITECTURE.md and docs/PIPELINE.md (T-DB-1B agenda-summary maintenance map only), tests/test_*backfill*, tests/test_summary_generation_operation.py (new), tests/test_agenda_summary_payload_budget.py, tests/test_summary_blocking.py, tests/test_task_provider_retry_semantics.py, tests/test_async_flow.py, tests/test_task_facade_cleanup.py, tests/test_repository_guardrails.py (T-DB tasks only), tests/test_pipeline_batching.py, tests/test_run_pipeline_orchestration.py, tests/test_staged_hydrate_cities.py, tests/test_tasks_agenda_summary_format.py, tests/test_profile_pipeline_cli.py |
| DEDUP-C   | agent-dc   | api/main.py, api/app_setup.py, tests/conftest.py, tests/test_*api* (Phase 2 only) |
| DEDUP-D   | agent-dd   | scripts/flush_city_pipeline_state.py, scripts/reset_city_verification_state.py, scripts/worker_health_probes.py, scripts/*_healthcheck.py, tests for same |
| DEDUP-E   | agent-de   | pipeline/http_inference_provider.py, pipeline/inprocess_inference_provider.py, pipeline/inference_provider_contract.py, tests for same |
| PLAT      | agent-plat | alembic/** (new), alembic.ini (new), pipeline/requirements*.txt, pipeline/db_init.py (T-PLAT-1 only), pipeline/db_migrate.py (T-PLAT-1 only, after TIME), pipeline/db_migration_alembic.py (new, T-PLAT-1 only), pipeline/db_migration_backfills.py (T-PLAT-1 shared transaction only), pipeline/db_migration_runner.py (T-PLAT-1 strict legacy path only), pipeline/db_schema_contracts.py (new, T-PLAT-1 only), pipeline/db_migration_columns.py (T-PLAT-1 legacy parity only), pipeline/migrate_v8.py (T-PLAT-1 frozen transaction adapter only), pipeline/migration_pgvector_semantic_embeddings.py (T-PLAT-1 frozen metadata only), pipeline/migrate_v9.py and pipeline/migration_catalog_lineage_columns.py (T-PLAT-1 shared transaction only), pipeline/migrate_v10.py (T-PLAT-1 shared transaction only), pipeline/seed_places.py (T-PLAT-1 schema handoff only), pipeline/promote_stage.py (T-PLAT-1 schema handoff only), scripts/check_schema_parity.py (new, T-PLAT-1 only), scripts/dev_up.sh (T-PLAT-1 only), README.md (T-PLAT-1 setup section only), ARCHITECTURE.md (T-PLAT-1 migration map only), api/requirements.txt, semantic_service/requirements.txt, constraints.txt (new), .github/dependabot.yml (new), .github/workflows/python-guardrails.yml (T-PLAT-1 PostgreSQL migration service/step only), ruff.toml (T-PLAT-1 stale db_migration_runner.py BLE001 selector removal only), docs/OPERATIONS.md (migration and backup sections only), docs/PIPELINE.md (T-PLAT-1 migration section only), docs/CONTRIBUTING_CITIES.md (T-PLAT-1 seed prerequisite only), docs/plans/T_PLAT_1_ALEMBIC_BASELINE_PLAN.md (new), docs/plans/G5_ALEMBIC_ADOPTION_DECISION_PLAN.md (T-PLAT-1 status only), docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md (T-PLAT-1 only), tests/test_alembic_migrations.py (new), tests/test_db_init.py (T-PLAT-1 only), tests/test_db_migrate.py (T-PLAT-1 only), tests/test_docker_build_contracts.py (T-PLAT-1 fresh-DB contract only), tests/test_migrate_v8_pgvector_order.py (T-PLAT-1 only), tests/test_migrate_v9.py (T-PLAT-1 only), tests/test_migrate_v10.py (T-PLAT-1 only), tests/test_seed_places.py (T-PLAT-1 schema handoff only), tests/test_seed_places_includes_cupertino.py (T-PLAT-1 schema handoff only), tests/test_database.py (T-PLAT-1 promotion schema handoff only), tests/test_pipeline_idempotency.py (T-PLAT-1 promotion schema handoff only), tests/test_pipeline_integration.py (T-PLAT-1 promotion schema handoff only), tests/test_repository_guardrails.py (T-PLAT-1 migration CI and BLE001 ratchet only), tests/test_run_pipeline_orchestration.py (T-PLAT-1 migration-prelude contract only), api/cache.py |
| GOV       | agent-gov  | docs/ADR.md, docs/ENGINEERING_GUARDRAILS.md, AGENTS.md, SECURITY.md (new), docs/TESTING.md (new), docs/DATA_GOVERNANCE.md (new), tests/test_repository_guardrails.py (Phase 3 only) |

Sequencing rule: SEC and DEDUP-C both own api/app_setup.py + api/main.py —
they are in different phases and MUST NOT run concurrently. TIME owns model
files. T-TIME-1 and T-TIME-2 execute in one coordinated PR, then T-PLAT-1 may
establish the Alembic baseline. Their task-level ownership in
`docs/plans/T_TIME_1_2_TIMEZONE_MIGRATION_PLAN.md` is authoritative for this
PR and grants narrow coordination over CI's PostgreSQL service and DTZ
ratchet, CRAWL's duplicate stage models, DEDUP-C's API timestamp contracts,
DEDUP-D's two verification scripts, PLAT's migration runbook, and GOV's
accepted ADR wording. No task sharing those files may run concurrently.
Other TIME and PLAT work may run independently when ownership permits.
T-CI-0 temporarily
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
T-PLAT-1 and T-GOV-3 MUST NOT run concurrently because both own focused
changes in `tests/test_repository_guardrails.py`; whichever starts second
must wait for the first PR to merge and rebase on `master`.
T-PLAT-1 also receives a narrow operator-approved coordination grant over
CI-owned `ruff.toml` for removal of the stale
`pipeline/db_migration_runner.py` BLE001 selector only.

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
- status: complete and verified 2026-07-24 (PR #133)
- decision_gate: G2 operator approval received 2026-07-24; durable record satisfied by PR #133
- implementation_plan: `docs/plans/T_SEC_4A_G2_VISITOR_ACCESS_POLICY_PLAN.md`
- files_owned: docs/plans/T_SEC_4A_G2_VISITOR_ACCESS_POLICY_PLAN.md,
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md, SECURITY.md,
  tests/test_repository_guardrails.py
- do: Record the approved visitor-access policy, its rationale, the interim
  accepted risk, and its dependency on T-SEC-4 without changing runtime code.
- accept: `SECURITY.md` and the remediation ledger agree; policy tests prevent
  status/risk drift. T-SEC-4 was pending when this policy record merged;
  current delivery status is owned by the T-SEC-4 task entry.
- forbidden: Runtime changes, operator-auth implementation, G3 content, or
  edits outside `files_owned`.
- verify: Follow the Full T-SEC-4A plan, including tests-first evidence,
  guardrail and docs verification, the complete Python suite, independent
  review, and decided CI.

### T-SEC-4: Real client identity through the proxy; per-client rate limits
- priority: P0
- status: complete and verified 2026-07-24 (PR #136)
- decision_gate: G2 approved 2026-07-24; repository-owned ingress approved 2026-07-24
- implementation_plan: `docs/plans/T_SEC_4_TRUSTED_CLIENT_IDENTITY_PLAN.md`
- files_owned: docs/plans/T_SEC_4_TRUSTED_CLIENT_IDENTITY_PLAN.md,
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md, docker-compose.yml,
  docker-compose.dev.yml, docker/Caddyfile, frontend/app/api/_lib/backend.js,
  frontend/components/__tests__/BackendProxy.origin.test.js, api/app_setup.py,
  tests/test_api_client_identity.py, tests/test_docker_build_contracts.py,
  tests/test_repository_guardrails.py, scripts/verify_caddy_forwarded_for.sh,
  scripts/dev_up.sh, tests/test_startup_purge_gating.py, README.md,
  env/profiles/README.md, SECURITY.md, docs/OPERATIONS.md
- do: Make Caddy the sole public frontend entry so caller-supplied forwarded
  headers are replaced. Validate and forward one client IP from Next.js. Trust
  it at the API only when the deployment key authenticates the frontend;
  otherwise use the direct peer. Disable Uvicorn proxy-header rewriting.
- trust_assumption: Possession of `API_AUTH_KEY` is already the deployment
  operator boundary. A direct API caller with that secret can choose forwarded
  identity; this does not grant capability beyond the protected actions that
  key already authorizes. Public visitors never receive the key.
- accept: Direct frontend bypass is unavailable; spoofed ingress headers are
  replaced; two trusted client IPs receive separate limiter keys; untrusted,
  missing, malformed, and multi-value identity falls back to the direct peer.
- forbidden: Trusted upstream-proxy configuration, fixed container IPs,
  dynamic Compose CIDR trust, global middleware, new secrets, or direct
  frontend publication.
- verify: Follow the Full T-SEC-4 plan, including tests-first evidence,
  security/frontend/API/Compose verification, runtime smoke, independent
  review, complete suites, and decided CI.

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
- status: complete and verified 2026-07-24 (PR #138)
- implementation_plan: `docs/plans/T_SEC_6_SMALL_SECURITY_CLOSURES_PLAN.md`
- files_owned: .env.example, api/main.py (CORS and `/stats` only),
  pipeline/provider_telemetry.py (metric-key constants only),
  pipeline/topic_generation_contracts.py (token-pattern constants only),
  ruff.toml (two owned S105 selectors only), tests/test_api.py,
  tests/test_meilisearch_key_security.py, tests/test_repository_guardrails.py,
  SECURITY.md (T-SEC-6 checklist only),
  docs/plans/T_SEC_6_SMALL_SECURITY_CLOSURES_PLAN.md,
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md
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
- status: coordinated implementation in progress with T-TIME-2
- implementation_plan: `docs/plans/T_TIME_1_2_TIMEZONE_MIGRATION_PLAN.md`
- files_owned: exact shared twenty-eight-file set in the implementation plan
- do: Make all thirteen model timestamps timezone-aware. Give the ten
  generated timestamps `server_default=func.now()` and preserve
  `SemanticEmbedding.updated_at` update behavior. Keep extraction,
  lineage, and agenda-segmentation attempted timestamps nullable without
  defaults because null means not attempted. Remove owned UTC-stripping
  consumer paths and exactly four stale DTZ007 ignores.
- accept: Metadata, fresh PostgreSQL DDL, UTC consumers, guardrail ratchets,
  and the complete suite pass. No naive model default or owned timezone
  stripping remains.
- sequencing: Must merge and deploy in the same PR/release as T-TIME-2.
- verify: Follow the shared Full plan.

### T-TIME-2: Migration for timestamp columns
- priority: P1
- status: coordinated implementation in progress with T-TIME-1
- implementation_plan: `docs/plans/T_TIME_1_2_TIMEZONE_MIGRATION_PLAN.md`
- files_owned: exact shared twenty-eight-file set in the implementation plan
- do: Add mandatory v10 conversion using
  `ALTER ... TYPE timestamptz USING <column> AT TIME ZONE 'UTC'`. Enforce
  the ten generated defaults and three lifecycle no-default contracts in one
  transaction. Call v10 after the best-effort v8/v9 runner but do not route it
  through that error-swallowing boundary.
- accept: PostgreSQL tests prove UTC instant preservation, non-UTC reads,
  mixed-schema convergence, idempotency, rollback on drift, physical
  defaults, and fail-fast ordering. CI provides mandatory pgvector PostgreSQL
  evidence; operator docs require sampling, backup, and a maintenance window.
- sequencing: Must merge and deploy in the same PR/release as T-TIME-1.
  T-PLAT-1 follows this final numbered migration.
- verify: Follow the shared Full plan.

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
- status: complete and verified 2026-07-24
- implementation_plan: `docs/plans/T_DA_1_METRICS_DEDUPLICATION_PLAN.md`
- files_owned: docs/plans/T_DA_1_METRICS_DEDUPLICATION_PLAN.md,
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md, pipeline/metrics.py,
  pipeline/metrics_definitions.py,
  pipeline/metrics_provider_collector.py, pipeline/metrics_redis_backend.py,
  pipeline/metrics_provider_recorders.py, pipeline/metrics_task_recorders.py,
  ruff.toml, tests/test_metrics_api.py,
  tests/test_provider_metrics_prefork_redis_aggregation.py,
  tests/test_task_metrics.py, tests/test_worker_metrics_exporter_provider_series.py
- do: Single source of truth for the redis client state machine and
  `_redis_incr/_redis_hincrby/_redis_hincrbyfloat` (keep them in
  metrics_redis_backend). Provider recorders import and call that backend;
  metrics.py keeps the public collector binding, and collector registration
  describes names without reading Redis. Redis-mirrored provider instruments
  do not self-register; the collector is their sole registry owner, while
  provider request duration remains locally registered. The collector exports
  Redis aggregates while healthy and process-local instruments while degraded,
  with canonical counter metadata. Delete the facade's duplicate
  implementations, BOTH `_sync_redis_*` functions, duplicated module globals,
  dynamic metric lookups, and injected Redis callables.
- accept: One implementation of each function repo-wide; zero
  `_sync_redis_*` symbols; the S105 ruff.toml entry for
  metrics_redis_backend.py is resolved and removed (env-source the default
  or noqa-with-justification; ratchet from T-CI-5); each provider series has
  one registry owner; degraded scrapes retain process-local provider series;
  metrics tests green after repointing patches.
- verify: grep for sync fns returns nothing; full suite green.

### T-DB-1A: Make summary generation a direct operation
- priority: P1
- status: complete and verified 2026-07-25
- implementation_plan:
  `docs/plans/T_DB_1A_SUMMARY_GENERATION_OPERATION_PLAN.md`
- must_merge_before: T-DB-1
- files_owned: docs/plans/T_DB_1A_SUMMARY_GENERATION_OPERATION_PLAN.md,
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md, docs/ADR.md,
  pipeline/task_summary_generation.py,
  pipeline/task_summary_generation_contracts.py,
  pipeline/task_summary_generation_flow.py,
  pipeline/task_summary_generation_persistence.py,
  pipeline/task_summary_empty_agenda.py,
  pipeline/task_summary_side_effects.py, pipeline/task_facade_helpers.py,
  pipeline/tasks.py, tests/test_summary_generation_operation.py (new),
  tests/test_agenda_summary_payload_budget.py, tests/test_summary_blocking.py,
  tests/test_task_provider_retry_semantics.py,
  tests/test_tasks_agenda_summary_format.py, tests/test_async_flow.py,
  tests/test_task_facade_cleanup.py, tests/test_repository_guardrails.py
- do: Make `pipeline/task_summary_generation.py` own the direct summary
  operation as `generate_catalog_summary`. Delete
  `SummaryGenerationTaskServices`, `run_generate_summary_task_family`,
  summary-only `globals()` wiring, and summary forwarding in
  `task_facade_helpers.py`. Lower modules import real domain implementations,
  including `agenda_summary_inputs.build_agenda_summary_input_bundle` and
  `agenda_summary_batch.persist_agenda_summary`, and never import the task
  facade, operation owner, `backlog_maintenance`, or
  `agenda_summary_maintenance`.
- preserve: Celery task name, bind/max-retry/countdown settings, arguments,
  task-session lifecycle, rollback/retry behavior, summary result payloads,
  hash persistence, grounding, and best-effort reindex/embed outcomes.
- accept: No summary callable service bag, summary globals lookup, injectable
  callable, old end-to-end runner, facade re-export, or lower-to-facade import
  remains. Tests use only the approved DB, Celery, inference, and Meilisearch
  boundaries and explicitly preserve task identity, retry countdown, rollback,
  and session closure.
- forbidden: Backfill facade cleanup, API task dispatch changes, new fake
  boundaries, compatibility aliases, or edits outside `files_owned`.
- verify: Follow the Full T-DB-1A plan; Ruff, Mypy, summary/task/provider
  suites, repository guardrails, docs links, and complete Python suite pass.

### T-DB-1: Collapse the summary_backfill facade
- priority: P1
- status: complete and verified 2026-07-25
- implementation_plan:
  `docs/plans/T_DB_1_SUMMARY_BACKFILL_FACADE_PLAN.md`
- files_owned: docs/plans/T_DB_1_SUMMARY_BACKFILL_FACADE_PLAN.md,
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md, docs/ADR.md,
  pipeline/summary_backfill.py (delete),
  pipeline/summary_backfill_dispatch.py,
  pipeline/summary_backfill_logging.py,
  pipeline/summary_backfill_progress.py,
  pipeline/summary_backfill_queries.py,
  pipeline/summary_backfill_runner.py, pipeline/task_facade_helpers.py,
  pipeline/tasks.py, pipeline/run_pipeline.py, scripts/backfill_summaries.py,
  scripts/staged_hydrate_cities.py, scripts/profile_pipeline_selection.py,
  tests/test_backfill_summaries.py, tests/test_pipeline_batching.py,
  tests/test_run_pipeline_orchestration.py,
  tests/test_staged_hydrate_cities.py,
  tests/test_tasks_agenda_summary_format.py,
  tests/test_profile_pipeline_cli.py, tests/test_repository_guardrails.py,
  tests/test_task_facade_cleanup.py
- do: Delete `summary_backfill.py`. Make `summary_backfill_runner.py` the
  direct operation owner with seven public options and no injected dependency
  parameters. Move every tracked runtime caller to the runner or query owner.
  Delete task-facade selectors, mapping, dispatch, globals wiring, and
  forwarding. Repoint tests to implementation modules and approved database,
  provider, Meilisearch, and Celery boundaries.
- preserve: Eligibility/order, city and manifest filtering, deterministic
  agenda-first handling, non-agenda provider fallback, low-signal blocking,
  session rollback/closure, counts, timings, progress cadence, canonical
  pipeline settings, staged hydration, profiling selection, and CLI output.
- accept: `summary_backfill.py` is absent; no tracked caller imports summary
  hydration from `pipeline.tasks`; public runner has at most eight parameters
  and no dependency-callable parameter; no conditional splat forwarding or
  lower-to-facade import remains; focused and complete suites pass.
- forbidden: Rewriting downstream maintenance-fallback or staged-hydration
  callable chains, preserving compatibility aliases, new fake boundaries, or
  edits outside `files_owned`.
- verify: Follow the Full T-DB-1 plan; Ruff, Mypy, backfill, orchestration,
  provider, guardrail, docs-link, and complete Python suites pass.

### T-DB-1B: Remove maintenance fallback callable injection
- priority: P1
- status: complete and verified 2026-07-25 (PR #146)
- must_merge_after: T-DB-1
- must_not_run_concurrently_with: agent-gov or any task touching the owned
  repaired/staged hydration scripts
- coordination_grant: Released after PR #146 merged. The exact task-level
  `files_owned` list was authoritative over the broader DEDUP-B and GOV lane
  rows during implementation.
- implementation_plan:
  `docs/plans/T_DB_1B_MAINTENANCE_CALLABLE_CLEANUP_PLAN.md`
- files_owned:
  docs/plans/T_DB_1B_MAINTENANCE_CALLABLE_CLEANUP_PLAN.md,
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md, docs/ADR.md,
  ARCHITECTURE.md (agenda-summary maintenance owner map only),
  docs/PIPELINE.md (agenda-summary maintenance owner map only),
  pipeline/agenda_summary_batch.py,
  pipeline/agenda_summary_callbacks.py (delete),
  pipeline/agenda_summary_fallback.py,
  pipeline/agenda_summary_maintenance.py (delete),
  pipeline/agenda_summary_side_effects.py (new),
  pipeline/backlog_maintenance.py,
  pipeline/non_agenda_summary_fallback.py,
  pipeline/summary_backfill_logging.py,
  pipeline/summary_backfill_progress.py,
  pipeline/summary_backfill_runner.py,
  scripts/hydrate_repaired_city_catalogs.py,
  scripts/hydration_repaired_runner.py,
  scripts/hydration_repaired_summary.py,
  scripts/staged_hydrate_cities.py,
  scripts/staged_hydration_output.py,
  scripts/staged_hydration_runner.py,
  scripts/staged_hydration_segment.py,
  tests/test_backlog_maintenance_laserfiche_guard.py,
  tests/test_hydrate_repaired_city_catalogs.py,
  tests/test_pipeline_batching.py, tests/test_repository_guardrails.py,
  tests/test_staged_hydrate_cities.py,
  tests/test_tasks_agenda_summary_format.py
- do: Replace remaining generation, deterministic-summary, session, reindex,
  embed, output, clock, staged-summary, and repaired-summary callable
  threading with direct operation ownership and approved runtime boundaries.
  Delete the summary compatibility facade, callback helper, and superseded
  wrappers in the same PR.
- accept: No maintenance fallback or staged hydration production signature
  accepts dependency callables; summary behavior is absent from
  `backlog_maintenance`; deleted facades cannot return; tests fake only
  approved boundaries; behavior, progress, fallback, session, persistence,
  and side-effect contracts remain unchanged; canonical owner maps name only
  live maintenance modules.
- forbidden: Runtime default, fallback policy, timeout policy, or soak
  comparability changes; general repaired extract/segment rewrites.
- verify: Follow the Full T-DB-1B plan; Ruff, Mypy, maintenance, batching,
  staged/repaired hydration, orchestration, provider, guardrail, docs-link,
  and complete Python suites pass.

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

### T-DD-1A: Consolidate worker health probes
- priority: P2
- status: in progress
- implementation_plan: `docs/plans/T_DD_1A_WORKER_HEALTHCHECK_PLAN.md`
- files_owned: the plan and ledger; `scripts/worker_health_probes.py`;
  `scripts/worker_healthcheck.py`;
  `scripts/enrichment_worker_healthcheck.py`;
  `scripts/semantic_worker_healthcheck.py`;
  `tests/test_worker_health_probes.py`;
  `tests/test_worker_healthcheck.py`;
  `tests/test_docker_health_contracts.py`
- do: Move shared URL/TCP, Redis/PostgreSQL, failure aggregation, and reporting
  behavior into one implementation owner. Preserve all three CLI filenames,
  role-specific probes, labels, defaults, timeouts, and exit behavior.
- accept: No healthcheck CLI imports private helpers from another CLI; the
  shared module never imports a CLI; all three role contracts and Compose
  entrypoints remain unchanged; no BLE001 selector is added or widened.
- verify: Follow the Full T-DD-1A plan; targeted healthcheck and Docker
  contracts, Ruff, Mypy, docs links, and the complete Python suite pass.

### T-DD-1B: Evaluate city-state mutation consolidation
- priority: P2
- status: pending after T-DD-1A
- files_owned: `scripts/flush_city_pipeline_state.py`,
  `scripts/reset_city_verification_state.py`, and focused tests to be named in
  a separate Full plan
- do: Characterize the exact shared event-graph deletion invariant before
  extracting code. Preserve each command's distinct stage-row behavior,
  defaults, temporal selection, output, and dry-run contract.
- accept: Consolidate only proven identical mutation policy; do not force
  shallow reuse when semantics differ.
- verify: Separate tests-first Full plan, CLI parity, targeted tests, and the
  complete suite.

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
- status: complete and verified 2026-07-26 (PRs #150 and #151)
- must_not_run_concurrently_with: T-GOV-3
- decision_record: `docs/plans/G5_ALEMBIC_ADOPTION_DECISION_PLAN.md`
- implementation_plan: `docs/plans/T_PLAT_1_ALEMBIC_BASELINE_PLAN.md`
- files_owned: alembic/** (new), alembic.ini (new),
  docs/plans/T_PLAT_1_ALEMBIC_BASELINE_PLAN.md,
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md,
  docs/plans/G5_ALEMBIC_ADOPTION_DECISION_PLAN.md (status only),
  ruff.toml (`pipeline/db_migration_runner.py` BLE001 selector removal only),
  pipeline/requirements.txt, pipeline/db_init.py (fresh-DB handoff),
  pipeline/db_migrate.py (Alembic handoff),
  pipeline/db_migration_alembic.py (new),
  pipeline/db_migration_backfills.py (shared transaction only),
  pipeline/db_migration_runner.py (strict legacy path only),
  pipeline/db_schema_contracts.py (new),
  pipeline/db_migration_columns.py (legacy parity repair only),
  pipeline/migrate_v8.py and
  pipeline/migration_pgvector_semantic_embeddings.py (frozen metadata only),
  pipeline/migrate_v9.py and
  pipeline/migration_catalog_lineage_columns.py (shared transaction only),
  pipeline/migrate_v10.py (shared transaction only),
  pipeline/seed_places.py (schema handoff only),
  pipeline/promote_stage.py (schema handoff only),
  scripts/check_schema_parity.py (new),
  scripts/dev_up.sh, README.md (setup section), ARCHITECTURE.md (migration
  map), docs/OPERATIONS.md and docs/PIPELINE.md (migration sections),
  docs/CONTRIBUTING_CITIES.md (seed prerequisite),
  .github/workflows/python-guardrails.yml
  (PostgreSQL migration service/step only),
  tests/test_alembic_migrations.py (new),
  tests/test_db_init.py, tests/test_db_migrate.py,
  tests/test_docker_build_contracts.py (fresh-DB contract only),
  tests/test_migrate_v8_pgvector_order.py,
  tests/test_migrate_v9.py, tests/test_migrate_v10.py,
  tests/test_seed_places.py and tests/test_seed_places_includes_cupertino.py
  (schema handoff only), tests/test_database.py,
  tests/test_pipeline_idempotency.py, and tests/test_pipeline_integration.py
  (promotion schema handoff only),
  tests/test_repository_guardrails.py (migration CI and BLE001 ratchet only),
  tests/test_run_pipeline_orchestration.py (migration-prelude contract only)
- do: `alembic init`; autogenerate a baseline revision from current models
  after T-TIME-2, then reconcile it against an explicit inventory of every
  schema object created by the frozen legacy migrations. This inventory must
  include legacy-only objects absent from model metadata:
  `ix_catalog_agenda_segmentation_attempted_at`,
  `ix_catalog_agenda_segmentation_status`,
  `ix_catalog_lineage_updated_at`, and `ix_semantic_embedding_hnsw`.
  Preserve the existing `python db_migrate.py` subprocess in
  `pipeline.run_pipeline`; make `db_migrate.migrate()` delegate through the
  frozen legacy runner when needed and then run `alembic upgrade head`.
  Make `pipeline/db_init.py`, `scripts/dev_up.sh`, and README setup use the
  same migration entrypoint so fresh contributor databases are Alembic-owned
  immediately instead of being created through `Base.metadata.create_all()`.
  Remove implicit schema creation from `seed_places.py` and
  `promote_stage.py`; operators must migrate before seeding or promotion.
  `pipeline/db_migrate.py` owns the only supported existing-database adoption
  path: run the legacy chain through v10, repair the known missing-index drift
  in the existing column-migration owner, compare tables, columns, rendered
  types, nullability, defaults, keys, constraints, indexes, predicates,
  operator classes, sequences, ownership, and required extensions against
  the frozen baseline, abort on drift, stamp the baseline, then upgrade to
  head. Delayed
  adopters use that same frozen comparison even when newer revisions exist.
  Replace v8's mutable `Base.metadata.create_all()` dependency with frozen
  baseline metadata so later models cannot mutate delayed adopters before the
  parity check.
  Baseline upgrade creates the pgvector extension before baseline table DDL.
  Execute legacy repair, baseline parity, stamp, and upgrade in one
  caller-owned PostgreSQL transaction. Serialize migration entrypoints with
  an immediate `pg_try_advisory_xact_lock`; conflict must fail fast rather
  than wait. Legacy migration failures must propagate and must never permit
  committed partial DDL or stamping.
  Keep migrate_v* readable but frozen (no v11+). Document fresh, existing,
  delayed-adoption, upgrade, and downgrade workflows; do not instruct operators
  to run an unguarded `alembic stamp`. The baseline is the downgrade floor:
  its downgrade must fail before any DDL, while later revisions may downgrade
  only as far as the baseline.
- accept: Fresh extension-free PostgreSQL via Alembic creates pgvector before
  vector columns, contains every inventoried legacy-only object, and equals
  the frozen baseline schema; an existing database migrated through v10 has
  an empty object-level diff against that baseline before stamping; a delayed
  adopter stamps only after baseline parity and then
  reaches head; stamping aborts on nonempty baseline drift; the canonical
  `python db_migrate.py` subprocess remains unchanged and applies
  post-baseline revisions; attempting to downgrade below the baseline exits
  nonzero without changing schema or representative data; OPERATIONS documents
  the baseline floor, migration lock, derived-vector rehydration, and
  supported workflows. Python Guardrails runs fresh,
  existing, delayed-adoption, upgrade, and downgrade tests against an isolated
  pgvector PostgreSQL service without optional skips. ARCHITECTURE maps
  Alembic as the authoritative post-baseline migration graph.
- verify: Schema diff script output empty; suite green.

### T-PLAT-1A: Make migration outcomes visible
- priority: P1 (PR #150 closure)
- status: complete and verified 2026-07-26 (PR #151)
- depends_on: T-PLAT-1 implementation
- implementation_plan:
  `docs/plans/T_PLAT_1A_MIGRATION_OUTCOME_VISIBILITY_PLAN.md`
- files_owned: docs/plans/T_PLAT_1A_MIGRATION_OUTCOME_VISIBILITY_PLAN.md,
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md, pipeline/db_migrate.py,
  tests/test_db_migrate.py, tests/test_alembic_migrations.py
- do: Configure INFO logging only at the `db_migrate.py` CLI boundary and
  preserve the import-safe `migrate()` operation. Make direct commands display
  migration status, revision, and `retired_catalog_vector_count` so operators
  can follow the existing embedding-rehydration procedure.
- accept: Direct CLI execution exits successfully and writes the structured
  migration outcome to stderr, including a zero or nonzero retired-vector
  count; importing the module has no logging side effect; migration and
  disposal behavior remain unchanged.
- forbidden: Printing from the migration implementation, configuring logging
  at import time, changing the migration result contract, swallowing failures,
  or editing outside the five owned files.
- verify: Follow the Full T-PLAT-1A plan, including tests-first subprocess
  evidence, migration and docs contracts, full suite, independent review, and
  CI.

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

### T-PLAT-2B: Patch pypdf batch parsing
- priority: P0 (urgent dependency security patch)
- status: in progress
- depends_on: T-PLAT-1A closure
- implementation_plan:
  `docs/plans/T_PLAT_2B_PYPDF_SECURITY_PATCH_PLAN.md`
- files_owned: docs/plans/T_PLAT_2B_PYPDF_SECURITY_PATCH_PLAN.md,
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md,
  pipeline/requirements-batch.txt, pipeline/table_worker.py, ruff.toml,
  tests/test_docker_build_contracts.py, tests/test_repository_guardrails.py,
  tests/test_table_worker.py
- do: Replace the vulnerable `pypdf==6.13.3` batch-only pin with
  `pypdf==6.14.2`, the first release that closes all four open repository
  advisories. Catch pypdf's documented `PyPdfError` base at both table-parser
  boundaries because patched malformed inputs now raise `PdfReadError` and
  `LimitReachedError`. Limit the optional import fallback to an absent
  top-level `pypdf` package and remove the resulting stale table-worker
  BLE001 allowance.
- accept: The batch manifest has exactly one pypdf pin at 6.14.2; the core
  worker manifest still excludes pypdf; the batch image imports
  `pypdf.errors.PyPdfError`; malformed pypdf failures persist `tables=[]`
  instead of aborting the batch; the stale BLE001 allowance is removed; the
  complete Python suite remains green; alerts 116-119 report `fixed` after
  merge.
- forbidden: Broad constraints, audit workflow, parser logic, Camelot,
  unrelated dependency changes, or a compatibility alias for
  `PdfStreamError`.
- verify: Follow the Full T-PLAT-2B plan, including tests-first pin evidence,
  published-wheel import verification, dependency and table-worker contracts,
  complete suite, independent review, and post-merge Dependabot readback.

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
- status: complete and verified 2026-07-24
- implementation_plan: `docs/plans/T_GOV_4_AGENTS_POLICY_CLOSURE_PLAN.md`
- files_owned: AGENTS.md (two `docs/TESTING.md` casing corrections only),
  docs/plans/T_GOV_4_AGENTS_POLICY_CLOSURE_PLAN.md,
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md,
  tests/test_repository_guardrails.py
- depends_on: none. The former T-CI-1/T-CI-2 transition conditions are
  satisfied, and their markers have been removed from `AGENTS.md`.
- landed_evidence: commit `453c386` changed only `AGENTS.md`.
- do: Verify every section not named in the landed revision is byte-identical
  to its parent and correct two testing-policy links to tracked-path casing.
  The revision is surgical: canonical-doc list, hierarchy #1 clarification, new
  <known_antipatterns>, full-pytest permission move, matrix scope preamble +
  frontend npm row + mandatory cross-cutting sweep, new
  <security_sensitive_paths>, docs enumeration rule, checklist line,
  maintenance triggers.
- forbidden: Re-authoring policy text; reflowing unchanged sections.
- accept: Diff against master touches only the enumerated sections;
  docs-link test green.
- verify: `PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py`

### T-GOV-5: Land the rewritten ENGINEERING_GUARDRAILS.md
- priority: P1
- status: complete and verified 2026-07-24
- implementation_plan:
  `docs/plans/T_GOV_5_ENGINEERING_GUARDRAILS_CLOSURE_PLAN.md`
- depends_on: T-CI-4 (formatter scope in ruff-format.toml); coordinates with
  T-GOV-3 (structural rules).
- files_owned: docs/ENGINEERING_GUARDRAILS.md,
  docs/plans/T_GOV_5_ENGINEERING_GUARDRAILS_CLOSURE_PLAN.md,
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md,
  tests/test_repository_guardrails.py
- coordination: T-CI-0's narrow broad-handler structural-policy correction lands
  first. T-GOV-5 must carry the corrected policy into the rewritten document and
  must not restore final-statement or `sys.exit()` authorization.
- landed_evidence: commit `c4a4a27` changed only
  `docs/ENGINEERING_GUARDRAILS.md`. The original draft is unavailable for
  exact identity comparison; current acceptance was independently verified
  after T-CI-4 completed.
- do: Close the rewrite that landed in historical commit `c4a4a27` after
  independently verifying current acceptance. Record that the original draft
  is unavailable for exact identity comparison and that the rewrite landed
  before T-CI-4 rather than alongside it. Reconcile [transition] markers:
  retain T-GOV-3 markers until each structural rule gains enforcement; do not
  restore a T-CI-4 marker now that `ruff-format.toml` scope is live. Confirm
  the typed subtree remains in `mypy.ini` and C901 remains selected with
  `max-complexity = 10`; do not duplicate either scope in prose.
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
Phase 1: agent-sec [T-SEC-1..6] || agent-time [T-TIME-1 + T-TIME-2 coordinated, T-TIME-3] || agent-crawl [T-CRAWL-1..2]
Gate:    G3 satisfied (T-GOV-1 Accepted ADR + active docs/TESTING.MD)
Phase 2: agent-da || agent-db [T-DB-1A, then T-DB-1, then T-DB-1B] || agent-dd || agent-de ;
         then agent-dc (exclusive on api/*)
Phase 3: agent-plat [T-PLAT-1 after T-TIME-1 and T-TIME-2, T-PLAT-1A
         closure, T-PLAT-2B security patch, then T-PLAT-2..4]
         || agent-gov [T-GOV-2, T-GOV-3 + T-GOV-5]
Anytime: T-GOV-6 DATA_GOVERNANCE.md (Section 3 pending G4)
```

Merge policy: one task = one PR, except operator-approved T-TIME-1 +
T-TIME-2, whose model and schema halves must ship together. PR title = task
id(s); every PR body includes
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
