# Town Council Remediation Plan (Codex Multi-Agent)

version: 4.04
generated: 2026-08-02
source: Four-pass external code review (security, architecture, smells, process)
source_artifact: [Town Council architecture review](../reviews/architecture-review-2026-07-19.html)
orchestrator_contract: Codex instantiates one agent per lane. Agents run in
parallel ONLY within the same phase and ONLY on their owned paths. AGENTS.md
remains in force; where this plan is stricter, this plan wins for these tasks.

## Changelog

- **v4.04:** Expands T-FE-1A ownership to the frontend package manifest and
  lockfile after PR review found that re-extraction cancellation and agenda
  settlement still relied on whole-file source inspection. Authorizes exact
  `jsdom@28.1.0` test support so the existing compiled `ResultCard` can be
  mounted, exercised, and unmounted through observable DOM behavior. Reconciles
  the stale T-PLAT-2E detailed status with its completed PR #219 record.
- **v4.03:** Completes T-FE-1A after replacing source-token polling checks
  with ten lifecycle behavior tests, moving polling to one non-JSX owner, and
  carrying cancellation through pending task requests and asynchronous
  completion refreshes. Final independent review found no remaining P1/P2;
  the remediation ledger now has no pending or in-progress T-tasks.
- **v4.02:** Marks T-PLAT-2E complete after PR #219 migrated the Meilisearch
  Python SDK to 0.43.0 and passed container and v1.6 runtime verification.
  Closes T-FE-1's duplication audit because one shared poller already owns all
  four actions, then activates T-FE-1A with exact eight-file ownership to replace
  source-token tests, fix the post-await cancellation race, and move the
  polling lifecycle to one behavior-tested non-JSX owner.
- **v4.01:** Expands T-PLAT-2E from 14 to 17 owned files after the complete
  suite exposed three agenda-maintenance test boundaries that still returned
  untyped Meilisearch deletion tasks. The operator approved aligning those
  fakes with SDK 0.43.0 while preserving their observable persistence and
  reindex contracts.
- **v4.00:** Marks T-PLAT-2D complete after PR #218 upgraded the semantic
  Torch runtime to 2.13.0 and Dependabot alert #121 reported fixed. Activates
  T-PLAT-2E with exact 14-file ownership to migrate the Meilisearch Python SDK
  from 0.31.0 to 0.43.0, delete obsolete task-ID and filtered-delete
  compatibility helpers, preserve failed-task propagation, and validate the
  existing Meilisearch v1.6 reader/writer boundary.
- **v3.99:** Marks T-IDX-1 complete after PR #217 and activates urgent
  T-PLAT-2D to patch Dependabot alert #121 by moving the semantic Torch base
  and CPU pins from 2.11.0 to 2.13.0. The separately prepared Meilisearch SDK
  migration remains unregistered until this security patch is complete.
- **v3.98:** Marks T-SEM-1 complete after PR #216 and activates P1 T-IDX-1
  with exact 22-file ownership to delete obsolete meeting people projections
  from indexing, lexical search, and the frontend. Roster-backed people
  endpoints remain unchanged; deployment requires a replacement reindex.
- **v3.97:** Completes the T-SEM-1A policy prerequisite and activates T-SEM-1
  with exact 33-file ownership to delete the semantic index facade, reverse
  lookups, and class-bound helper aliases while preserving backend behavior.
- **v3.96:** Extends T-SEM-1A's future-effective fake contract to include the
  public pgvector reranking capability consumed by semantic retrieval tests
  and records that T-SEM-1 must make consumers resolve the runtime owner.
- **v3.95:** Adds T-SEM-1A as a separate policy prerequisite that approves the
  typed semantic backend/runtime fake boundary required before T-SEM-1 can
  delete facade patch points. T-SEM-1 remains pending its corrected Full plan.
- **v3.94:** Completes T-TASK-1 after deleting the task facade helper layer,
  global dependency bags, callable injection, the agenda segmentation service
  bag, and obsolete task-level provider catches. Celery identities, retry
  rules, session cleanup, persistence ordering, and task payloads remain
  protected by direct contract tests.
- **v3.93:** Activates T-TASK-1 with exact 23-file ownership to delete the task
  facade helper, `globals()` dependency bags, callable injection, and the
  agenda segmentation service bag while preserving Celery identities, retry
  rules, session lifecycle, persistence ordering, and task payloads.
- **v3.92:** Completes T-DC-2B after deleting API router module-object and
  callable bags, removing task proxy and search compatibility exports,
  repointing tests to database and Celery runtime boundaries, and adding exact
  structural guards for the remaining router contracts.
- **v3.91:** Activates T-DC-2B with exact ownership to delete module-object
  router injection, route-level model/callable bags, and task/search/lineage
  compatibility exports. Routes keep their current database, auth, rate-limit,
  Celery, response, and startup contracts while tests move to approved runtime
  boundaries.
- **v3.90:** Completes T-DC-2A after deleting dynamic search lookup through
  `api.main`, removing seven search patch aliases, repointing routes and tests
  to direct Meilisearch, semantic transport, filter, and trends owners, and
  adding an AST deletion guard for imported, string, `patch.object`, and
  `setattr` patch forms. T-DC-2B remains pending for broader router facade bags.
- **v3.89:** Activates T-DC-2A with exact ownership to delete dynamic search
  lookups through `api.main`, repoint routes and tests to direct search,
  Meilisearch, and outbound-HTTP owners, and add a structural deletion guard.
  Broader router facade bags remain reserved for T-DC-2B.
- **v3.88:** Completes T-DE-2 after deleting the provider compatibility
  facade, repointing production and test imports to direct owners, removing
  provider-class re-exports from `pipeline.llm`, and passing the provider,
  guardrail, coverage, and complete-suite gates.
- **v3.87:** Activates T-DE-2 with exact ownership to delete the provider
  compatibility facade, repoint imports to the contract and adapter owners,
  retire obsolete structural registrations, and synchronize canonical
  provider-boundary documentation without changing runtime policy.
- **v3.86:** Completes governing-body normalization at the people-list query
  boundary by authorizing stable organization IDs after applying the shared
  case-and-whitespace contract to stored names.
- **v3.85:** Closes roster-sync review gaps by deleting people displaced by
  corrected OfficeRecord identities and reusing seeded organizations through
  the same normalized body-name contract used for source authorization.
- **v3.84:** Expands T-GOV-2A ownership to remove the obsolete empty
  `people_metadata` field from semantic meeting hydration after PR review.
  Also records normalized governing-body authorization and stable remediation
  inventory comparison fixes.
- **v3.83:** Marks T-GOV-2A complete after roster-gated persistence,
  fail-closed publication, legacy remediation, migration, and baseline-v2
  workload verification. City Coverage Expansion remains blocked until the
  separate expected-baseline PR merges.
- **v3.82:** Activates T-GOV-2A with exact ownership for authoritative
  OfficeRecords ingestion, Alembic remediation, fail-closed API/index
  behavior, deletion of document-derived person linking, and the approved
  performance-baseline transition. `baseline_representative_v1` remains
  immutable historical evidence; v2 removes the people-linking phase and
  receives a new expected baseline only after a post-change valid run.
- **v3.81:** Reconciles the active ledger with merged work and the architecture
  review. Marks T-PLAT-4 complete after PR #207, corrects the stale T-TIME-1
  and T-TIME-2 in-progress labels, and registers seven narrow deletion tasks:
  T-DE-2, T-DC-2A, T-DC-2B, T-TASK-1, T-SEM-1, T-IDX-1, and T-FE-1. Each
  pending task requires a separate Full plan and exact ownership before code
  changes. Records Legistar OfficeRecords as the approved T-GOV-2A roster
  authority and requires cities without an approved source to fail closed for
  people-derived data.
- **v3.80:** Activates operator-approved T-PLAT-4 with exact cross-lane
  ownership for deleting the generic API Redis cache, preserving the metadata
  endpoint's one-hour behavior in its route, removing obsolete cache-only
  tests and BLE001 debt, and correcting stale Redis role wording.
- **v3.79:** Deletes T-GOV-3B's remaining custom SQLAlchemy matcher after
  review found another qualifier gap. Ruff `S608` and `F403` now own dynamic
  SQL and wildcard-import enforcement without project-specific name resolution;
  an isolated Ruff ratchet scans Ruff's discovered production files without
  configured or inline rule suppressions.
- **v3.78:** Narrows T-GOV-3B after pre-commit review: activates Ruff `S608`
  for scripts by replacing their wildcard security exemption with eight
  current debt codes, and limits shadowing policy to interpolated calls.
- **v3.77:** Simplifies T-GOV-3B after independent review: deletes the partial
  lexical resolver, moves wildcard-import enforcement to Ruff `F403`, and
  preserves direct SQLAlchemy interpolation enforcement through a conservative
  file-level binding convention.
- **v3.76:** Expands T-GOV-3B ownership to `AGENTS.md` and synchronizes the
  binding contributor policy with active SQLAlchemy interpolation and
  wildcard-import enforcement.
- **v3.75:** Completes T-GOV-3B and umbrella T-GOV-3 after enforcing four
  dependency directions, top-level private synchronization-function rejection,
  and direct SQLAlchemy f-string rejection with no structural allowlist.
- **v3.74:** Marks T-PLAT-2C complete after PR #205 and activates T-GOV-3B
  with six-file ownership for final structural enforcement and removal of
  superseded domain-specific assertions.
- **v3.73:** Registers T-PLAT-2C to migrate Celery from 5.3.4 to 5.6.3 with
  exact dependency contracts, four image builds, and isolated Redis worker
  acceptance before superseding Dependabot PR #194.
- **v3.72:** Expands T-GOV-2 ownership to `AGENTS.md`, synchronizes the binding
  roster-authority and T-GOV-2A expansion invariant, and extends guardrails to
  reject contradictions in the ADR or agent policy.
- **v3.71:** Expands T-GOV-2 ownership to the roadmap after review, makes
  T-GOV-2A completion an explicit City Coverage Expansion start criterion,
  and strengthens the non-roster prohibition contract.
- **v3.70:** Completes T-GOV-2 by recording the approved roster-gated person
  policy in the ADR and Data Governance document. Runtime enforcement remains
  explicitly pending under T-GOV-2A, and City Coverage Expansion stays
  blocked.
- **v3.69:** Marks T-PLAT-2 complete after PR #160 merged with all required
  checks green, activates T-GOV-2, and records the exact policy-only ownership
  needed to adopt the operator-approved G4 roster-gated decision without
  overstating current runtime enforcement.
- **v3.68:** Closes T-PLAT-2 audit parity gaps found during review and CI.
  The CI-only scikit-learn pin now lives in the audited development manifest,
  while the semantic manifest exposes Torch's upstream version and Docker's
  existing CPU constraint continues to select the matching `+cpu` build.
- **v3.67:** Synchronizes T-DE-1 completion after PR #158 and activates
  T-PLAT-2 after operator approval of the exact dependency-policy, Docker,
  workflow, security, and test ownership needed for shared constraints, weekly
  version updates, and trustworthy report-only audits. Audit findings remain
  non-blocking, while malformed reports and audit-tool failures must fail CI.
- **v3.66:** Records the operator-approved reachable deployment posture in the
  G1 decision ledger and closes T-GOV-6 after all three governance documents
  were linked from the README. Expands T-GOV-6 ownership narrowly for the
  synchronized ledger update and its policy contract.
- **v3.65:** Marks T-DC-1 complete after PR #157 removed copied startup state,
  reverse startup imports, forwarding wrappers, stdlib rebinding, and test-only
  API re-exports. Activates a corrected T-DE-1 after independent review found
  that retry orchestration is already transport-local. T-DE-1 now removes
  reverse imports through the provider compatibility facade, repoints tests to
  implementation owners, and preserves HTTP retry and in-process reset policy.
- **v3.64:** Marks T-DD-1B complete after PR #156 merged the characterized
  event-graph mutation owner with shared-catalog, rollback, idempotency, and
  CLI parity coverage. Activates P1 T-DC-1 with exact ownership for removing
  copied startup state, forwarding wrappers, stdlib rebinding, and the
  `app_setup -> api.main` semantic startup dependency. Test-only model, search,
  task, and reporting re-exports are removed in the same task; only aliases
  resolved by assembled task, lineage, and search routes remain.
- **v3.63:** Marks T-PLAT-3 complete after PR #155 merged with verified backup,
  disposable restore, rollback, search rebuild, and Redis recovery contracts.
  Activates T-DD-1B with exact ownership for a tests-first extraction of only
  the identical selected-event reference and deletion policy. Stage behavior,
  temporal selection, validation, command defaults, transaction ownership, and
  reports remain command-local.
- **v3.62:** Expands active T-PLAT-3 ownership to the Redis service definition
  and its Compose contract test. Recovery must clear persistent Redis database
  0 after writers stop and before workers restart, using the service's existing
  credential inside the container rather than expanding it in the host shell.
- **v3.61:** Activates T-PLAT-3 with an implementation-ready backup and
  recovery plan. Expands ownership for tests-first shell contracts and the
  existing full-index maintenance path so a PostgreSQL restore cannot leave
  Meilisearch or FAISS newer than the restored system of record. T-PLAT-3 and
  T-DD-1B must serialize their shared operations-runbook edits.
- **v3.60:** Removes the partial source-line semantic analyzer added during
  T-GOV-3A review. Arbitrary Python data flow cannot be soundly enforced by a
  small repository test; Ruff C901 and registered dependency rules remain the
  durable controls after the final source-line cap is deleted.
- **v3.59:** Closes the T-GOV-3A review gap by removing the remaining
  search-support source-line cap. Expands ownership to the affected test file.
- **v3.58:** Completes T-GOV-3A. The repository no longer enforces 34
  per-family 300-line inventories; one explicit registry now protects the same
  24 already-clean helper-to-facade relationships. Umbrella T-GOV-3 remains
  partially landed, and its transition marker stays until T-DC-1 and revised
  T-DE-1 enable T-GOV-3B's final structural checks.
- **v3.57:** Marks T-DD-1A complete after PR #153 merged with all required
  checks green and no unresolved P1/P2 findings. Splits T-GOV-3 into
  T-GOV-3A inventory cleanup and T-GOV-3B final smell enforcement. Activates
  T-GOV-3A with exact ownership for removing 34 file-length inventories,
  consolidating 24 already-clean helper relationships, and retaining the
  structural transition until T-DC-1 and revised T-DE-1 clear the remaining
  reverse dependencies.
- **v3.56:** Expands T-DD-1A ownership with exact-path role CLI parity tests
  after pre-commit review found that direct script execution and role failure
  aggregation were not durably covered. All three CLIs must work without
  `PYTHONPATH`; real role containers remain the success-path evidence.
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
| **Complete** | T-CI-0, T-CI-1, T-CI-1A, T-CI-2, T-CI-2A, T-CI-3, T-CI-4, T-CI-5, T-SEC-1, T-SEC-2, T-SEC-3, T-SEC-3C, T-SEC-4, T-SEC-4A, T-SEC-5, T-SEC-6, T-TIME-1, T-TIME-2, T-TIME-3, T-CRAWL-1, T-CRAWL-2, T-PLAT-1, T-PLAT-1A, T-PLAT-2, T-PLAT-2A, T-PLAT-2B, T-PLAT-2C, T-PLAT-2D, T-PLAT-2E, T-PLAT-3, T-PLAT-4, T-GOV-1, T-GOV-2, T-GOV-2A, T-GOV-3, T-GOV-3A, T-GOV-3B, T-GOV-4, T-GOV-5, T-GOV-6, T-DA-1, T-DB-1A, T-DB-1, T-DB-1B, T-DC-1, T-DC-2A, T-DC-2B, T-DD-1A, T-DD-1B, T-DE-1, T-DE-2, T-TASK-1, T-SEM-1, T-IDX-1, T-FE-1, T-FE-1A |
| **In progress** | None |
| **Pending** | None |

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

- G1 deployment_posture: **Approved 2026-07-26.** Town Council is operated
  with a `reachable` deployment posture. Reachable controls in `SECURITY.md`
  are mandatory for any instance exposed beyond localhost. This decision
  affects SEC-lane severity and does not block remediation execution.
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
- G4 pii_policy: **Approved 2026-07-26.** Use roster-gated person linking.
  Only current approved Legistar OfficeRecords roster entries may become
  person entities or people-facing derived records. Title inference, fuzzy
  matching, and source-document mentions are not roster authority. T-GOV-2
  records the decision; T-GOV-2A implements and remediates it. City Coverage
  Expansion remains blocked until a valid `baseline_representative_v2`
  expected-baseline PR merges.
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
| DEDUP-E   | agent-de   | pipeline/http_inference_provider.py, pipeline/http_inference_attempts.py (verify-only), pipeline/inprocess_inference_provider.py (verify-only), pipeline/inference_provider_contract.py (verify-only), pipeline/llm_provider.py, pipeline/provider_telemetry.py, pipeline/agenda_segmentation_maintenance.py, ARCHITECTURE.md, docs/PIPELINE.md, docs/plans/T_DE_1_PROVIDER_BOUNDARY_PLAN.md, docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md (T-DE-1 only), tests/test_inference_provider_protocol_contract.py, tests/test_http_provider_telemetry_metrics.py, tests/test_http_provider_operation_retry_budgets.py, tests/test_http_provider_ttft_tps_computation.py, tests/test_http_provider_token_metrics_parsing.py, tests/test_hydrate_repaired_city_catalogs.py |
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
- status: complete and verified 2026-07-26 (PR #148)
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
- status: complete and verified 2026-07-26 (PR #148)
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
- status: complete and verified 2026-07-26 (PR #157)
- must_not_run_concurrently_with: any SEC task
- implementation_plan: `docs/plans/T_DC_1_APP_STARTUP_OWNERSHIP_PLAN.md`
- files_owned: the implementation plan and ledger; `api/main.py`;
  `api/app_setup.py`; `api/search/semantic_support.py`
  (`SEMANTIC_SERVICE_URL` ownership only); `tests/conftest.py`;
  `tests/test_api.py` (database startup, direct model imports, and dead AI
  override only);
  `tests/test_api_key_compare_digest.py`;
  `tests/test_api_startup_security.py`;
  `tests/test_city_slug_normalization.py`;
  `tests/test_semantic_search_api.py` (dead semantic health patches only)
- do: `api.app_setup` owns
  `SessionLocal`/`_db_init_error`/`verify_api_key`/`lifespan` as the single
  authority. Delete `_sync_app_setup_from_facade`,
  `_sync_facade_from_app_setup`, the wrapper defs in main.py, the
  `hmac = app_setup.hmac` rebind, and the `X as X` re-export blocks whose
  only consumers are tests. Delete the inert `get_local_ai` test hook and
  override. Repoint tests from `api.main.db_connect` to `api.app_setup.db_connect`,
  model and normalization imports to their implementation modules, and remove
  dead semantic health facade patches. Move the semantic service URL to its
  semantic implementation owner so startup no longer imports back through
  `api.main`.
- preserve: Direct runtime assembly names for FastAPI lifespan, authentication,
  and database dependency; task, lineage, and search facade aliases used by
  routers; all auth, startup, fail-fast, route, and response behavior.
- accept: `main.py` contains no bidirectional sync functions, copied mutable
  startup state, forwarding startup wrappers, or stdlib re-exports;
  `app_setup.py` does not import `api.main`; focused security/API behavior,
  coverage, complete suite, and boot smoke pass.
- risk: Highest-touch task in the plan. Land as one PR; do not interleave.
- verify: Follow the Full T-DC-1 plan; Ruff, Mypy, focused security/API/search
  tests, docs links, coverage, complete suite, and manual
  `uvicorn api.main:app` boot smoke pass.

### T-DD-1A: Consolidate worker health probes
- priority: P2
- status: complete and verified 2026-07-26 (PR #153)
- implementation_plan: `docs/plans/T_DD_1A_WORKER_HEALTHCHECK_PLAN.md`
- files_owned: the plan and ledger; `scripts/worker_health_probes.py`;
  `scripts/worker_healthcheck.py`;
  `scripts/enrichment_worker_healthcheck.py`;
  `scripts/semantic_worker_healthcheck.py`;
  `tests/test_worker_health_probes.py`;
  `tests/test_worker_healthcheck.py`;
  `tests/test_role_worker_healthchecks.py`;
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
- status: complete and verified 2026-07-26 (PR #156)
- depends_on: T-DD-1A (satisfied by PR #153)
- implementation_plan: `docs/plans/T_DD_1B_CITY_STATE_MUTATION_PLAN.md`
- files_owned: the implementation plan and ledger;
  `docs/OPERATIONS.md` (pending-city rewind deletion list only);
  `scripts/city_state_mutation.py` (new);
  `scripts/flush_city_pipeline_state.py`;
  `scripts/reset_city_verification_state.py`;
  `tests/test_city_state_mutation_cli.py` (new);
  `tests/test_flush_city_pipeline_state.py`;
  `tests/test_reset_city_verification_baseline.py` (new);
  `tests/test_reset_city_verification_state.py`
- do: Characterize the exact shared event-graph deletion invariant before
  extracting code. Move only selected-event ID accounting, shared-catalog
  protection, and live event-graph deletion into one implementation owner.
  Preserve each command's distinct stage-row behavior, defaults, temporal
  selection, validation, output, commit ownership, and dry-run contract.
- accept: Consolidate only proven identical mutation policy; do not force
  shallow reuse when semantics differ. Both commands retain their CLI and
  persisted-state behavior, and the shared module never imports either CLI or
  commits the caller-owned transaction.
- verify: Follow the Full T-DD-1B plan; CLI characterization, focused
  persisted-state and onboarding contracts, Ruff, Mypy, docs links, coverage,
  and the complete suite pass.

### T-DE-1: Remove reverse provider-facade dependencies
- priority: P2
- status: complete and verified 2026-07-26 (PR #158)
- implementation_plan: `docs/plans/T_DE_1_PROVIDER_BOUNDARY_PLAN.md`
- files_owned: the implementation plan and ledger; `ARCHITECTURE.md`;
  `docs/PIPELINE.md`; `pipeline/http_inference_provider.py`;
  `pipeline/llm_provider.py`;
  `pipeline/provider_telemetry.py`;
  `pipeline/agenda_segmentation_maintenance.py`;
  `tests/test_inference_provider_protocol_contract.py`;
  `tests/test_http_provider_telemetry_metrics.py`;
  `tests/test_http_provider_operation_retry_budgets.py`;
  `tests/test_http_provider_ttft_tps_computation.py`;
  `tests/test_http_provider_token_metrics_parsing.py`;
  `tests/test_hydrate_repaired_city_catalogs.py`
- do: Remove implementation imports through `pipeline.llm_provider`. HTTP
  transport reads config and calls `requests` at its implementation owner;
  provider telemetry calls metric recorders at its implementation owner;
  maintenance timeout overrides patch the HTTP owner. Repoint affected tests
  from facade monkeypatches. Keep HTTP retry orchestration in
  `pipeline/http_inference_attempts.py`; in-process locking/reset behavior
  remains distinct.
- preserve: `pipeline.llm_provider` runtime import compatibility; provider
  classes, protocol, operation labels, response fields, and typed errors;
  retry budgets, timeout values, metric labels, local-first defaults,
  fail-fast behavior, and model/fallback policy. Remove test-only config,
  `requests`, and metric-recorder re-exports rather than leaving inert names.
- accept: Provider implementations do not import their compatibility facade;
  tests patch implementation or approved fake boundaries; temporary timeout
  overrides still restore prior values and provider state; the unchanged
  provider error-mapping test remains green.
- verify: Follow the Full T-DE-1 plan; focused inference, telemetry, and
  maintenance tests, Ruff, Mypy, docs links, coverage, and the complete Python
  suite pass.

### T-DE-2: Delete the provider compatibility facade
- priority: P2
- status: complete and verified 2026-07-31
- depends_on: T-DE-1 (satisfied by PR #158)
- implementation_plan: `docs/plans/T_DE_2_PROVIDER_FACADE_DELETION_PLAN.md`
- files_owned: the implementation plan and ledger; `pipeline/llm_provider.py`
  (delete); `pipeline/llm.py`; `pipeline/local_ai_runtime.py`;
  `pipeline/local_ai_provider_calls.py`;
  `tests/test_http_provider_operation_timeout_selection.py`;
  `tests/test_inference_provider_protocol_contract.py`;
  `tests/test_task_provider_retry_semantics.py`;
  `tests/test_provider_error_mapping_retry_vs_fallback.py`;
  `tests/test_pipeline_batching.py`; `tests/test_repository_guardrails.py`;
  `tests/test_agenda_segmentation_llm_proclamation_noise_rejection.py`;
  `tests/test_agenda_segmentation_mode_switch.py`; `tests/test_ai_logic.py`;
  `tests/test_extract_agenda_prompt_budget.py`; `tests/test_final_polish.py`;
  `tests/test_llm_backend_parity_agenda_segmentation.py`;
  `tests/test_llm_backend_parity_grounding.py`;
  `tests/test_llm_backend_parity_summary.py`;
  `AGENTS.md`; `ARCHITECTURE.md`; `docs/PIPELINE.md`; `docs/ADR.md`
- delivered: Deleted the facade and provider-class re-exports, repointed all
  maintained callers to direct contract/adapter owners, retired three obsolete
  helper-to-facade registrations, and added a repository-wide deletion/import
  guardrail. Provider, static, coverage, and complete Python gates pass.
- do: Delete `pipeline/llm_provider.py`. Repoint production callers and tests
  to `pipeline/inference_provider_contract.py`,
  `pipeline/http_inference_provider.py`, and
  `pipeline/inprocess_inference_provider.py`, according to ownership. Preserve
  the `LocalAI` product-policy boundary in `pipeline/llm.py`.
- preserve: Provider protocol, typed errors, adapters, retries, timeouts,
  telemetry, local-first defaults, fail-fast behavior, model selection, and
  fallback policy.
- accept: No tracked import of `pipeline.llm_provider` remains; the file is
  deleted rather than retained as a re-export; tests patch implementation
  owners or approved provider boundaries.
- forbidden: Compatibility aliases, provider-policy changes, retry changes,
  or implementation before the task-specific Full plan locks ownership.

### T-DC-2A: Delete search-to-api.main patch lookup
- priority: P2
- status: complete and verified 2026-07-31
- depends_on: T-DC-1 (satisfied by PR #157)
- implementation_plan: `docs/plans/T_DC_2A_SEARCH_MAIN_LOOKUP_DELETION_PLAN.md`
- files_owned: the implementation plan and ledger;
  `api/main.py` (seven search patch aliases only);
  `api/search/support_core.py`; `api/search/trends_support.py`;
  `api/search_support.py`; `api/search_read_params.py`;
  `api/search_read_meilisearch.py`; `api/search_read_routes.py`;
  `api/search_semantic_routes.py`; `api/trends_routes.py`;
  `tests/test_api.py`; `tests/test_catalog_lineage_endpoint.py`;
  `tests/test_query_builder_parity_search_vs_trends.py`;
  `tests/test_search_support_facade.py`; `tests/test_semantic_search_api.py`;
  `tests/test_semantic_search_feature_flag.py`;
  `tests/test_trends_compare_endpoint.py`; `tests/test_trends_export_csv.py`;
  `tests/test_trends_topics_endpoint.py`; `tests/test_repository_guardrails.py`;
  `docs/ADR.md`
- delivered: Deleted four dynamic lookup functions, three facade exports, and
  seven `api.main` search aliases; migrated route behavior and tests to direct
  search-domain and approved service boundaries; and added repository guards
  against reverse imports and stale patch forms. Search, security, static,
  coverage, and complete Python gates pass.
- do: Delete `_api_main`, `facade_value`, `facade_callable`, and
  `search_client` lookup behavior from the search support family. Repoint
  callers and tests to direct search implementation owners and the approved
  Meilisearch boundary.
- preserve: Search, trends, semantic-search, feature-flag, pagination, filter,
  response, authentication, and Meilisearch-key behavior.
- accept: Search helpers never import or inspect `api.main`; no patch-safe
  lookup wrapper or facade re-export survives; behavior-focused search tests
  remain green.
- forbidden: Search redesign, query-policy changes, compatibility aliases, or
  implementation before exact ownership is approved.

### T-DC-2B: Delete API router facade bags
- priority: P2
- status: complete; facade bags deleted and direct runtime boundaries verified
- depends_on: T-DC-2A (satisfied by PR #211)
- implementation_plan: `docs/plans/T_DC_2B_API_ROUTER_FACADE_DELETION_PLAN.md`
- files_owned: the implementation plan and ledger; `api/main.py`;
  `api/search_routes.py`; `api/search_support.py` (delete);
  `api/lineage_routes.py`; `api/catalog_routes.py`;
  new `api/catalog_summary_state.py`; `api/task_routes.py`;
  `api/task_dispatch.py`; `api/task_route_generation.py`;
  `api/task_route_segmentation.py`; `api/task_route_summary.py`;
  `api/task_route_support.py`; `tests/test_api.py`; `tests/test_async_flow.py`;
  `tests/test_catalog_lineage_endpoint.py`; `tests/test_extract_endpoint.py`;
  `tests/test_summary_staleness.py`; `tests/test_topics_staleness.py`;
  `tests/test_task_facade_cleanup.py`; `tests/test_search_support_facade.py`
  (delete); `tests/test_repository_guardrails.py`; `ARCHITECTURE.md`;
  `docs/ADR.md`; `docs/PIPELINE.md`; `docs/TESTING.MD`
- do: Replace `sys.modules[__name__]`, `lineage_facade`, `task_facade`, and
  route-level model/callable bags with direct imports and approved runtime
  boundaries.
- preserve: FastAPI routes, request and response contracts, Celery dispatch,
  task status, lineage filtering, authentication, and startup behavior.
- accept: Router builders receive only real runtime dependencies; no route
  function accepts a module facade or generic callable bag; tests patch
  implementation modules rather than `api.main`.
- forbidden: Route-contract changes, Celery signature changes, new dependency
  injection machinery, or concurrent implementation with T-DC-2A.

### T-TASK-1: Delete the task facade helper layer
- priority: P1
- status: complete under
  [T-TASK-1 implementation plan](T_TASK_1_TASK_FACADE_DELETION_PLAN.md)
- depends_on: T-DB-1B (satisfied by PR #146)
- files_owned: `docs/plans/T_TASK_1_TASK_FACADE_DELETION_PLAN.md`;
  `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`; `pipeline/tasks.py`;
  `pipeline/task_facade_helpers.py` (delete);
  `pipeline/task_agenda_segmentation.py`; `pipeline/task_text_extraction.py`;
  `pipeline/task_vote_extraction.py`; `pipeline/task_startup.py`;
  `tests/test_repository_guardrails.py`; `tests/test_task_facade_cleanup.py`;
  `tests/test_extract_task.py`; `tests/test_tasks_vote_extraction_flow.py`;
  `tests/test_async_flow.py`; `tests/test_summary_generation_operation.py`;
  `tests/test_summary_blocking.py`;
  `tests/test_task_provider_retry_semantics.py`;
  `tests/test_tasks_lineage_flow.py`;
  `tests/test_worker_ready_concurrency_guardrail.py`; `ARCHITECTURE.md`;
  `tests/test_agenda_title_extraction.py`;
  `docs/ADR.md`; `docs/PIPELINE.md`; `docs/TESTING.MD`
- do: Delete `pipeline/task_facade_helpers.py` and the remaining `globals()`
  service bags, callable injection, and forwarding wrappers in
  `pipeline/tasks.py`. Move each operation to its existing domain owner and
  keep the Celery-decorated entrypoints thin.
- preserve: Celery task names, signatures, routes, retry and rollback
  behavior, task result payloads, session ownership, and pipeline ordering.
- accept: The helper file and global lookup paths are absent; task entrypoints
  call domain operations directly; tests use approved DB, Celery, provider,
  and Meilisearch boundaries.
- forbidden: Task identity drift, new wrappers or compatibility exports,
  orchestration redesign, or implementation without exact ownership.

### T-SEM-1A: Approve the semantic test boundary
- priority: P1 prerequisite
- status: complete under
  [T-SEM-1A implementation plan](T_SEM_1A_SEMANTIC_TEST_BOUNDARY_PLAN.md)
- depends_on: G3 (satisfied by T-GOV-1)
- files_owned: `docs/plans/T_SEM_1A_SEMANTIC_TEST_BOUNDARY_PLAN.md`;
  `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`; `docs/TESTING.MD`
- do: After T-SEM-1 repoints consumers to resolve backend selection through
  the owner module, approve patching
  `semantic_backend_runtime.get_semantic_backend` to return a
  `SemanticBackend` fake. Pgvector retrieval fakes also implement the public
  `rerank_candidates_with_diagnostics` or `rerank_candidates` capability
  exercised by the test. Permit optional FAISS and SentenceTransformer
  substitution there only after T-SEM-1 establishes that ownership.
- preserve: Every existing approved fake boundary and the prohibition on
  facade/private-method patch targets.
- accept: T-SEM-1 can migrate semantic tests without preserving facade seams.
- forbidden: Production changes, a fixture framework, private-method fakes, or
  implementation mixed into this policy PR.

### T-SEM-1: Delete reverse semantic-index facade lookups
- priority: P2
- status: complete and verified 2026-08-02 (PR #216) under
  [T-SEM-1 implementation plan](T_SEM_1_SEMANTIC_FACADE_DELETION_PLAN.md)
- depends_on: G3 (satisfied by T-GOV-1), T-SEM-1A
- files_owned: `docs/plans/T_SEM_1_SEMANTIC_FACADE_DELETION_PLAN.md`;
  `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`; `ARCHITECTURE.md`;
  `docs/ADR.md`; `docs/OPERATIONS.md`; `pipeline/semantic_index.py` (delete);
  `pipeline/semantic_backend_runtime.py`; `pipeline/semantic_faiss_backend.py`;
  `pipeline/semantic_faiss_artifacts.py`; `pipeline/semantic_faiss_rows.py`;
  `pipeline/semantic_pgvector_backend.py`;
  `pipeline/semantic_pgvector_rerank.py`; `pipeline/semantic_pgvector_rows.py`;
  `pipeline/semantic_tasks.py`; `pipeline/reindex_semantic.py`;
  `pipeline/diagnose_semantic_search.py`; `semantic_service/main.py`;
  `tests/conftest.py`; `tests/test_repository_guardrails.py`;
  `tests/test_semantic_backend_selection.py`;
  `tests/test_semantic_require_faiss.py`;
  `tests/test_semantic_memory_guardrails.py`;
  `tests/test_semantic_numpy_fallback.py`;
  `tests/test_semantic_numpy_topk_selection.py`;
  `tests/test_semantic_index_build.py`;
  `tests/test_pgvector_rerank_diagnostics.py`;
  `tests/test_embed_catalog_task_source_hash.py`;
  `tests/test_search_pgvector_hybrid_rerank.py`;
  `tests/test_semantic_recall_filters.py`;
  `tests/test_semantic_service_api.py`;
  `tests/test_semantic_service_contract_helpers.py`;
  `tests/test_semantic_service_hydration.py`;
  `tests/test_semantic_dedup_catalog.py`
- do: Delete `_semantic_index_facade` lookups and implementation-callable
  exposure across semantic backends, row builders, artifact handling,
  reranking, and backend selection. Move configuration and optional dependency
  ownership to one existing semantic implementation boundary.
- preserve: FAISS and pgvector behavior, model configuration, worker-safety
  checks, artifact contracts, reranking, telemetry, and semantic API results.
- accept: Lower semantic modules do not import back through
  `pipeline.semantic_index`; tests fake the approved semantic/provider or
  persistence boundary rather than a facade.
- forbidden: New semantic registry, backend-policy changes, model changes,
  compatibility aliases, or implementation before exact ownership.

### T-IDX-1: Delete obsolete people index projections
- priority: P1
- status: complete and verified 2026-08-02 under
  [T-IDX-1 implementation plan](T_IDX_1_OBSOLETE_PEOPLE_INDEX_PROJECTION_DELETION_PLAN.md)
- depends_on: T-GOV-2A
- files_owned:
  `docs/plans/T_IDX_1_OBSOLETE_PEOPLE_INDEX_PROJECTION_DELETION_PLAN.md`;
  `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`; `README.md`;
  `ARCHITECTURE.md`; `ROADMAP.md`; `docs/ADR.md`;
  `docs/DATA_GOVERNANCE.md`; `docs/OPERATIONS.md`; `pipeline/indexer.py`;
  `pipeline/indexer_documents.py`; `pipeline/indexer_meilisearch.py`;
  `api/search/support_core.py`; `api/search_read_routes.py`;
  `api/search_read_results.py` (delete); `frontend/app/page.js`;
  `frontend/components/ResultCard.js`;
  `frontend/components/PersonProfile.js` (delete);
  `frontend/components/__tests__/ResultCard.people-projection.test.js` (new);
  `tests/test_api.py`; `tests/test_indexer_logic.py`;
  `tests/test_indexer_official_roster.py`; `tests/test_repository_guardrails.py`
- do: Remove all current meeting-search people projection paths and
  compatibility fields made obsolete by roster-gated person linking. Retain
  only the separate roster-backed `/people` and `/person/{id}` APIs; a future
  meeting projection requires independently authoritative event-to-body
  identity and separate authorization. Delete superseded title-inference
  assumptions rather than translating them.
- preserve: Source-document availability, non-person search behavior,
  grounding, lineage, and independently authoritative roster evidence.
- accept: Search indexes and API responses cannot expose document-inferred
  people as officials; obsolete projection code and fields are deleted in the
  same task.
- forbidden: New person inference, hardcoded city roster status, or preserving
  obsolete fields as aliases.

### T-FE-1: Delete proven ResultCard task lifecycle duplication
- priority: P2
- status: complete audit 2026-08-02; no duplicate poller found
- depends_on: T-CI-2 (satisfied)
- files_owned: read-only audit; no tracked files changed
- do: Characterize summary, topic, extraction, and segmentation task
  lifecycles. Consolidate only polling, cancellation, timeout, error, or state
  transitions that behavior tests prove identical, then delete each
  superseded copy from `frontend/components/ResultCard.js`.
- preserve: User-visible actions, loading and error states, bounded polling,
  unmount cleanup, task-status interpretation, rendered result content, and
  accessibility behavior.
- accept: One tested implementation owns each proven shared behavior;
  ResultCard retains action-specific differences and rendering; superseded
  lifecycle code is deleted rather than wrapped.
- forbidden: Visual redesign, API changes, weakened polling tests, speculative
  frontend framework, or implementation before behavior tests are approved.

### T-FE-1A: Test and correct the ResultCard polling lifecycle
- priority: P2
- status: complete in PR #220 under
  `docs/plans/T_FE_1A_TASK_POLLING_LIFECYCLE_PLAN.md`
- depends_on: T-FE-1 audit (satisfied)
- files_owned: `docs/plans/T_FE_1A_TASK_POLLING_LIFECYCLE_PLAN.md`,
  `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`,
  `frontend/components/ResultCard.js`,
  `frontend/components/__tests__/ResultCard.polling-contract.test.js`,
  `frontend/components/__tests__/ResultCard.people-projection.test.js`,
  `frontend/package.json`, `frontend/package-lock.json`,
  `frontend/lib/api.js`, `frontend/lib/taskPolling.js` (new),
  `tests/test_resultcard_agenda_status_refresh.py`
- do: Replace source-token polling assertions with behavior tests, move the
  shared lifecycle to one non-JSX owner, and suppress completion or failure
  callbacks after cancellation during awaited HTTP work.
- preserve: Action-specific summary, topic, agenda, and extraction settlement;
  visible loading and error states; bounded backoff; task response contracts;
  unmount cleanup; rendering; accessibility; and API behavior.
- accept: Completion, failure, HTTP error, timeout, scheduled-retry stop, and
  pending-request cancellation are behavior-tested; `ResultCard` contains no
  polling implementation or response-parser copy; stopped polls cannot update
  component state.
- forbidden: Generic task-action executor, visual redesign, dependencies beyond
  exact test-only `jsdom@28.1.0`, injected test callable, compatibility export,
  API change, or retained old polling implementation.

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
- status: complete and verified 2026-07-26 (PR #152)
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
- status: complete and verified 2026-07-27 (PR #160)
- implementation_plan:
  `docs/plans/T_PLAT_2_DEPENDENCY_HYGIENE_PLAN.md`
- scope_authorization: Operator-approved 2026-07-26.
- files_owned: `docs/plans/T_PLAT_2_DEPENDENCY_HYGIENE_PLAN.md`,
  `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`, `constraints.txt` (new),
  `api/requirements.txt`, `council_crawler/requirements.txt`,
  `pipeline/requirements.txt`, `pipeline/requirements-batch.txt`,
  `pipeline/requirements-dev.txt`, `pipeline/requirements-nlp.txt` (delete),
  `semantic_service/requirements.txt`, `Dockerfile`,
  `.github/dependabot.yml` (new),
  `.github/workflows/python-guardrails.yml` (audit steps only),
  `.github/workflows/frontend-tests.yml` (audit step only),
  `tests/test_docker_build_contracts.py`,
  `tests/test_repository_guardrails.py`, `SECURITY.md`.
- do: Centralize eleven repeated exact pins without changing versions; preserve
  six separate Python environments and the `pgvector>=0.2.5` policy; delete
  the obsolete NLP manifest; preserve manifest directories in Docker; add
  weekly pip, npm, and Actions version updates; and add report-only Python and
  npm vulnerability findings whose malformed reports or tool failures still
  fail CI.
- accept: Each shared package has one authoritative exact pin; every active
  manifest uses the root constraints; all five Python images resolve their
  intended dependencies; Dependabot covers every manifest location weekly;
  valid vulnerability findings are visible but non-blocking; invalid reports,
  network failures, and abnormal tool exits are blocking; security policy and
  workflows agree.
- forbidden: Package-version changes; pinning `pgvector`; combined
  cross-service audit environments; `continue-on-error`, `if: always()`, or
  `|| true` audit suppression; workflow permission or required-check changes;
  runtime API, schema, environment, inference, or soak-policy changes.
- verify: Follow the Full T-PLAT-2 plan, including tests-first evidence, Ruff,
  Mypy, Docker and repository contracts, docs links, complete Python and
  frontend suites, native Python 3.12 resolution, all five image builds,
  independent review, and PR CI.

### T-PLAT-2C: Migrate Celery to 5.6.3
- priority: P1
- status: complete and verified 2026-07-30 (PR #205)
- depends_on: T-PLAT-2 and PR #196 merge (ledger serialization only)
- implementation_plan: `docs/plans/T_PLAT_2C_CELERY_MIGRATION_PLAN.md`
- scope_authorization: Operator-approved 2026-07-30.
- files_owned: `docs/plans/T_PLAT_2C_CELERY_MIGRATION_PLAN.md`,
  `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`, `constraints.txt`,
  `tests/test_docker_build_contracts.py`
- do: Replace only the shared Celery 5.3.4 constraint and matching exact
  contract with 5.6.3. Prove API, live-worker, batch-worker, and semantic
  images resolve cleanly, then verify the production Celery app against
  isolated authenticated Redis and PostgreSQL.
- preserve: Task names and arguments, result payloads, queues, retries, worker
  pools and concurrency, broker/result configuration, runtime defaults, and
  soak comparability.
- forbidden: Production source, Dockerfile, Compose, requirement-manifest,
  workflow, API, schema, task-signature, queue, retry, fallback, or unrelated
  dependency changes; compatibility layers; edits outside `files_owned`.
- accept: Exact contracts and all Python gates pass; all four affected images
  build and pass dependency inspection; prefork readiness, task registration,
  control ping, broker/result round-trip, healthcheck, credential masking, and
  graceful shutdown pass; PR #194 is superseded.
- verify: Follow the Full T-PLAT-2C plan, including tests-first evidence,
  Ruff, Mypy, task and Docker contracts, docs links, coverage-gated suite,
  four image builds, isolated runtime smoke, independent review, and PR CI.

### T-PLAT-2D: Patch the Torch semantic runtime
- priority: P1 (urgent dependency security patch)
- status: complete and verified 2026-08-02 (PR #218; alert #121 fixed)
- depends_on: T-IDX-1 merge; serialized ahead of prepared Meilisearch work
- implementation_plan:
  `docs/plans/T_PLAT_2D_TORCH_SECURITY_PATCH_PLAN.md`
- scope_authorization: Operator requested remediation of Dependabot alert #121
  on 2026-08-01.
- files_owned: `docs/plans/T_PLAT_2D_TORCH_SECURITY_PATCH_PLAN.md`,
  `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`,
  `semantic_service/requirements.txt`,
  `docker/semantic-cpu-constraints.txt`,
  `tests/test_docker_build_contracts.py`
- do: Replace the vulnerable audit-visible `torch==2.11.0` pin and matching
  Docker `torch==2.11.0+cpu` constraint with patched 2.13.0 declarations.
  Prove both pins stay aligned and validate the real CPU semantic image through
  dependency, model-encoding, and FAISS search smokes.
- preserve: Semantic APIs, model selection, embedding dimensions, index data,
  worker behavior, Dockerfile, ports, credentials, runtime defaults, gate
  semantics, and soak comparability.
- forbidden: One-sided pin changes; application or Dockerfile edits; alert
  suppression; unrelated dependency upgrades; compatibility code; API,
  schema, workflow, environment, model-policy, or soak-policy changes; edits
  outside `files_owned`.
- accept: Exact pin contracts and all required Python gates pass;
  `python-semantic` resolves `torch==2.13.0+cpu`; `pip check`, CPU-only runtime,
  384-dimensional finite model embeddings, and FAISS nearest-neighbor search
  pass; PR CI is green; alert #121 reports fixed after merge.
- verify: Follow the Full T-PLAT-2D plan, including tests-first red evidence,
  Ruff, Mypy, Docker and semantic tests, docs links, coverage-gated suite, real
  semantic image build and runtime smoke, independent review, and PR CI.

### T-PLAT-2E: Migrate the Meilisearch Python SDK
- priority: P1
- status: complete in PR #219
- depends_on: T-PLAT-2D merge; T-IDX-1 merge
- implementation_plan:
  `docs/plans/T_PLAT_2E_MEILISEARCH_SDK_MIGRATION_PLAN.md`
- scope_authorization: Operator approved replacing closed Dependabot PR #197
  with an owned Meilisearch migration on 2026-07-27.
- files_owned: `docs/plans/T_PLAT_2E_MEILISEARCH_SDK_MIGRATION_PLAN.md`,
  `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`, `docs/ADR.md`,
  `constraints.txt`, `pipeline/indexer.py`,
  `pipeline/indexer_meilisearch.py`, `ruff.toml`, `tests/test_api.py`,
  `tests/test_async_flow.py`,
  `tests/test_backlog_maintenance_laserfiche_guard.py`,
  `tests/test_docker_build_contracts.py`, `tests/test_extract_task.py`,
  `tests/test_indexer_logic.py`, `tests/test_pipeline_batching.py`,
  `tests/test_repository_guardrails.py`,
  `tests/test_tasks_agenda_summary_format.py`,
  `tests/test_tasks_vote_extraction_flow.py`
- do: Upgrade only the shared Meilisearch Python SDK constraint from 0.31.0
  to 0.43.0; consume typed task IDs directly; delete the obsolete task-ID and
  filtered-delete compatibility helpers; and use the existing successful-task
  waiter for settings and targeted deletion.
- preserve: Meilisearch server v1.6, index UID and settings, reader/writer key
  separation, task ordering, replacement-index recovery, document payloads,
  API/search behavior, people-field absence, runtime defaults, and soak
  comparability.
- forbidden: Server-image, key, port, API, schema, environment, index-contract,
  workflow, inference, or soak-policy changes; compatibility shims; failed-task
  swallowing; unrelated dependency updates; edits outside `files_owned`.
- accept: Exact pin and typed-task contracts pass; all Python gates pass; four
  affected images resolve SDK 0.43.0 with clean dependency checks; an isolated
  v1.6 server accepts settings, add/search/stats/task-list/filter-delete flows;
  and a scoped reader can search/read stats but cannot add or change settings.
- verify: Follow the Full T-PLAT-2E plan, including tests-first red evidence,
  Ruff, formatter, Mypy, targeted and coverage-gated suites, four image builds,
  isolated reader/writer runtime smoke, independent review, and PR CI.

### T-PLAT-3: Backup/restore runbook
- priority: P1
- status: complete and verified 2026-07-26 (PR #155)
- implementation_plan: `docs/plans/T_PLAT_3_BACKUP_RESTORE_PLAN.md`
- must_not_run_concurrently_with: T-DD-1B
- files_owned: `docs/plans/T_PLAT_3_BACKUP_RESTORE_PLAN.md`,
  `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`,
  `scripts/backup_db.sh`, `tests/test_backup_db_contract.py`,
  `docs/OPERATIONS.md`, `pipeline/indexer.py`,
  `pipeline/indexer_meilisearch.py`, `pipeline/reindex_only.py`,
  `tests/test_indexer_logic.py`, `docker-compose.yml`,
  `tests/test_docker_build_contracts.py`
- do: Add one private, atomic, custom-format `pg_dump` command; document
  cadence and fresh-database replacement restore; make the
  `STARTUP_PURGE_DERIVED` interaction explicit; and add a tested full-index
  replacement mode so restored PostgreSQL, Meilisearch, and FAISS converge
  before traffic resumes.
- accept: The script exits 0 against the dev stack, validates before
  publication, never overwrites a destination, and leaves no partial archive.
  A disposable database restore proves archive usability. Recovery guidance
  keeps writers stopped, recreates the database from `template0`, migrates and
  verifies it, clears persistent Redis database 0, rebuilds external search
  state, and restarts with startup purge disabled.
- forbidden: Automatic scheduling or restore; embedded credentials; a default
  archive destination; Docker fake seams; runtime-default, schema, migration,
  or search-query behavior changes; edits outside `files_owned`.
- verify: Follow the Full T-PLAT-3 plan, including tests-first evidence, shell
  syntax, Ruff, Mypy, focused backup/indexer contracts, docs links, complete
  suite, real dev-stack backup, disposable restore drill, independent review,
  and PR CI.

### T-PLAT-4: cache.py right-sizing
- priority: P3
- status: complete and verified 2026-07-31 (PR #207)
- implementation_plan: `docs/plans/T_PLAT_4_CACHE_RIGHTSIZING_PLAN.md`
- files_owned: `docs/plans/T_PLAT_4_CACHE_RIGHTSIZING_PLAN.md`,
  `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`, `api/cache.py`,
  `api/search_read_routes.py`, `ruff.toml`, `tests/test_api.py`,
  `tests/test_metrics_api.py`, `tests/test_performance.py`,
  `tests/test_repository_guardrails.py`, `tests/locustfile.py`,
  `docker-compose.yml` (Redis comments only), `docs/OPERATIONS.md`
  (Redis recovery wording only)
- do: Delete the generic Redis decorator and its cache-only interfaces. Keep
  the metadata endpoint's one-hour refresh behavior in the route with a
  process-local monotonic TTL cache. Cache the existing empty failure payload
  too, matching current behavior. Remove obsolete cache tests, the global
  Redis module mock, stale API-cache prose, and the deleted file's BLE001
  selector.
- preserve: Metadata response fields and normalization, failure payload,
  endpoint authentication, one-hour TTL, Redis's Celery and metrics roles,
  Compose service configuration, runtime defaults, and soak comparability.
- forbidden: New cache abstraction, Redis compatibility path, test-only
  production reset seam, new dependency or environment variable, API contract
  change, Ruff widening, Compose configuration change, or edits outside
  `files_owned`.
- accept: `api/cache.py` and all imports are gone; repeated metadata requests
  use one search before expiry and refresh at expiry; failure payloads are
  cached for the same TTL; broad-exception debt decreases by one; all
  targeted and complete gates pass.
- verify: Follow the Full T-PLAT-4 plan, including tests-first evidence, Ruff,
  formatter, Mypy, API/search, metrics/performance, repository guardrails,
  docs links, Docker contracts, complete suite, independent review, and PR CI.

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
- historical_coordination: T-GOV-6 remained partial after this task because its
  README Documentation Map links were outside T-GOV-1 ownership. T-GOV-6 is
  now complete.
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
- status: complete and verified 2026-07-29
- implementation_plan:
  `docs/plans/T_GOV_2_PERSON_MINIMIZATION_PLAN.md`
- scope_authorization: The operator approved G4 Option A and directed continued
  remediation execution through completion.
- files_owned: `docs/plans/T_GOV_2_PERSON_MINIMIZATION_PLAN.md`,
  `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`, `docs/ADR.md`,
  `docs/DATA_GOVERNANCE.md`, `AGENTS.md`, `ROADMAP.md`,
  `tests/test_repository_guardrails.py`
  (G4 and T-GOV-2 policy contracts only)
- do: Record roster-gated person linking as an Accepted ADR. Replace the live
  option list in Data Governance with the adopted policy. Define roster
  authority as independently authoritative official membership data, not title
  inference or linker-created memberships. Preserve source-document text and
  correction of derived records. Register T-GOV-2A for runtime enforcement,
  existing derived-data remediation, reindexing, and prevention of
  re-derivation.
- forbidden: Runtime, schema, API, crawler, search, inference, or migration
  changes; claiming current behavior is compliant; treating inferred titles or
  current derived memberships as roster authority; edits outside
  `files_owned`.
- accept: ADR and Data Governance agree on the approved policy; live G4 option
  and working-default language is gone; AGENTS names the binding roster
  authority and T-GOV-2A expansion gate; T-GOV-2A is complete; City Coverage
  Expansion names the valid v2 expected-baseline PR as a start criterion;
  repository guardrails, docs links, and the complete suite pass.
- verify: Follow the Full T-GOV-2 plan; Ruff, Mypy, repository guardrails, docs
  links, complete Python suite, independent review, and PR CI.

### T-GOV-2A: Enforce roster-gated person linking
- priority: P1
- status: complete and verified 2026-07-31
- depends_on: T-GOV-2
- implementation_plan: `docs/plans/T_GOV_2A_ROSTER_GATED_LINKING_PLAN.md`
- authoritative_source: Legistar OfficeRecords membership records, resolved
  through the owning city's approved Legistar body rather than a hardcoded
  body identifier
- files_owned: `docs/plans/T_GOV_2A_ROSTER_GATED_LINKING_PLAN.md`,
  `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`, `AGENTS.md`,
  `README.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `docs/ADR.md`,
  `docs/DATA_GOVERNANCE.md`, `docs/OPERATIONS.md`, `docs/PIPELINE.md`,
  `docs/PERFORMANCE.md`, `mypy.ini`, `ruff.toml`, `ruff-format.toml`,
  `city_metadata/city_rollout_registry.csv`,
  `alembic/versions/0002_roster_gated_people.py`, `api/people_routes.py`,
  `pipeline/model_civic.py`, `pipeline/roster_contracts.py`,
  `pipeline/legistar_roster.py`, `pipeline/roster_sync.py`,
  `scripts/build_profile_manifest.py`, `scripts/remediate_legacy_people.py`,
  `scripts/sync_rosters.py`,
  `pipeline/rollout_registry.py`, `pipeline/run_batch_enrichment.py`,
  `pipeline/run_pipeline_steps.py`, `pipeline/indexer_documents.py`,
  `semantic_service/hydration.py`,
  `pipeline/nlp_entity_candidates.py`, `pipeline/nlp_entity_extraction.py`,
  `pipeline/nlp_entity_model.py`, `pipeline/nlp_worker.py`,
  `pipeline/profile_manifest.py`, `pipeline/profile_manifest_builder.py`,
  `pipeline/profile_manifest_contracts.py`,
  `pipeline/profile_manifest_preconditioning.py`, `pipeline/utils.py`,
  `pipeline/person_cache.py`, `pipeline/person_linker.py`,
  `pipeline/person_mutations.py`, `pipeline/person_names.py`,
  `pipeline/person_selectors.py`, `pipeline/profile_manifest_people.py`,
  `pipeline/utils_matching.py`,
  `profiling/manifests/baseline_representative_v2.json`,
  `profiling/manifests/baseline_representative_v2.txt`,
  `profiling/manifests/README.md`,
  `frontend/components/PersonProfile.js`, `frontend/lib/api.js`,
  `frontend/public/demo/search.json`,
  `frontend/public/demo/person_1.json`, `frontend/public/demo/person_2.json`,
  `frontend/public/demo/person_3.json`, `frontend/public/demo/person_4.json`,
  `tests/test_alembic_migrations.py`, `tests/test_benchmarks.py`,
  `tests/test_demo_mode_contract.py`,
  `tests/test_database.py`, `tests/test_fuzzy_matcher.py`,
  `tests/test_entity_staleness.py`,
  `tests/test_indexer_official_roster.py`,
  `tests/test_legistar_roster.py`, `tests/test_people_endpoint_filters.py`,
  `tests/test_person_classification.py`,
  `tests/test_person_promotion_rules.py`,
  `tests/test_pipeline_idempotency.py`,
  `tests/test_pipeline_integration.py`,
  `tests/test_pipeline_batching.py`, `tests/test_noise_reduction.py`,
  `tests/test_person_remediation.py`,
  `tests/test_profile_manifest_builder.py`,
  `tests/test_profile_pipeline_cli.py`,
  `tests/test_rollout_registry.py`, `tests/test_rule_ruler.py`,
  `tests/test_run_pipeline_orchestration.py`,
  `tests/test_roster_sync.py`, `tests/test_roster_sync_cli.py`,
  `tests/test_utils.py`, `tests/test_validation.py`,
  `tests/test_repository_guardrails.py`
- do: Ingest independently authoritative OfficeRecords membership evidence;
  gate person creation and people-facing derived records; remediate existing
  non-roster entities and memberships; reindex affected catalogs; and prevent
  re-derivation. Cities without an approved roster source fail closed: source
  documents remain available, while people-facing derived data is disabled.
- forbidden: Inferring roster authority from titles, source-document mentions,
  or linker-generated memberships; deleting or rewriting municipal source
  records; hardcoding a Legistar body identifier; enabling people-derived data
  for cities without an approved roster source; implementing without an
  approved Full person-data plan.
- accept: Runtime behavior and existing derived data conform to the accepted G4
  policy; correction and reindexing are repeatable; City Coverage Expansion
  remains blocked until a baseline-valid v2 capture is reproduced and its
  expected-baseline PR merges.

### T-GOV-3: Redesign the guardrail regime
- priority: P2
- status: complete and verified 2026-07-30
- prerequisite: at least two Phase 2 tasks merged (satisfied by T-DA-1,
  T-DB-1A, T-DB-1, and T-DB-1B)
- delivered: Ruff C901 with max-complexity 10 and ratcheting path-specific
  exceptions; T-GOV-3A retirement of the file-length proxy and consolidation
  of existing dependency rules; T-GOV-3B enforcement of the remaining
  dependency directions, sync-global convention, and interpolated-SQL rule.
- accept: T-GOV-3A and T-GOV-3B complete; the structural transition marker is
  removed only after every replacement rule is enforced.

### T-GOV-3A: Retire file-length inventories
- priority: P2
- status: complete and verified 2026-07-26
- implementation_plan:
  `docs/plans/T_GOV_3A_GUARDRAIL_INVENTORY_PLAN.md`
- files_owned: `docs/plans/T_GOV_3A_GUARDRAIL_INVENTORY_PLAN.md`,
  `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`,
  `docs/ENGINEERING_GUARDRAILS.md`,
  `tests/test_repository_guardrails.py`,
  `tests/test_search_support_facade.py`
- do: Delete all 34 `*_CLEANUP_MODULES` inventories and all 35 300-line
  tests. Consolidate the 11 standalone dependency-direction tests into one
  registry and one enforcement test covering the same 24 already-clean helper
  paths. Do not add a partial source-line semantic analyzer, infer new facade
  relationships, or capture pending T-DC/T-DE debt.
- forbidden: A replacement file-size threshold, Ruff policy changes,
  sync-global or interpolated-SQL enforcement, T-GOV-3 completion, or
  transition-marker removal.
- accept: No file-length policy remains; registered helper dependencies remain
  protected; the guardrail test file shrinks materially; T-GOV-3 remains
  partially landed.
- verify: Follow the Full T-GOV-3A plan; Ruff, Mypy, repository guardrails,
  docs links, and the complete Python suite pass.

### T-GOV-3B: Enforce remaining structural smells
- priority: P2
- status: complete and verified 2026-07-30
- depends_on: T-DC-1 and revised T-DE-1
- implementation_plan: `docs/plans/T_GOV_3B_STRUCTURAL_GUARDRAILS_PLAN.md`
- scope_authorization: Operator-approved 2026-07-30.
- files_owned: `docs/plans/T_GOV_3B_STRUCTURAL_GUARDRAILS_PLAN.md`,
  `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`,
  `AGENTS.md`, `docs/ENGINEERING_GUARDRAILS.md`,
  `ruff.toml`,
  `tests/test_repository_guardrails.py`,
  `tests/test_api_startup_security.py`,
  `tests/test_inference_provider_protocol_contract.py`
- do: Register four helper relationships made clean by T-DC-1 and revised
  T-DE-1; add checks banning top-level private `_sync_*_from_*` functions and
  select Ruff `F403` for wildcard imports; activate Ruff `S608` for scripts by
  narrowing their security debt list; remove the partial SQLAlchemy matcher,
  superseded domain-specific assertions, and the `[transition: T-GOV-3]`
  marker only after all checks pass.
- note: T-DD-1B introduces no current facade rule and remains outside the
  dependency registry.
- accept: Remaining structural rules are mechanically enforced, no pending
  reverse dependencies are hidden by an allowlist, and T-GOV-3 is complete.
- verify: Follow the Full T-GOV-3B plan, including tests-first AST examples,
  repository guardrails, docs links, coverage-gated complete Python suite,
  independent review, and PR CI.

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
- status: complete and verified 2026-07-26
- files_owned: SECURITY.md (new), docs/TESTING.md (new),
  docs/DATA_GOVERNANCE.md (new), README.md (Documentation Map section only),
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md (G1 and T-GOV-6 only),
  tests/test_repository_guardrails.py (T-GOV-6 policy contract only)
- scope_authorization: Operator-approved 2026-07-26.
- sequencing: SECURITY.md merges at Phase 1 start (it is the reference for
  SEC-lane PR impact statements; its checklist items cite T-SEC tasks as
  pending — that is intentional, update checkboxes as tasks merge).
  TESTING.md is active with the G3 ADR (T-GOV-1) as its operational companion.
  All three canonical documents are linked from the README Documentation Map.
  DATA_GOVERNANCE.md Section 3 remains in its historical
  "options + working default" form only until T-GOV-2 records the approved G4
  policy; T-GOV-2A owns runtime implementation.
- do: Keep the three governance documents linked from the README and keep the
  G1 deployment posture synchronized between SECURITY.md and this ledger.
- forbidden: Resolving G2/G4 by editing defaults; adding further new documents
  (net-new doc budget for this remediation is exactly these three).
- accept: All three documents are linked from README; G1 records the
  operator-approved `reachable` posture in both canonical locations; docs-link
  and T-GOV-6 policy-contract tests are green.
- verify: `./.venv/bin/ruff check .`;
  `./.venv/bin/mypy`;
  `PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py`;
  `PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py`;
  `PYTHONPATH=. .venv/bin/pytest -q`.

---

## 7. EXECUTION ORDER SUMMARY

```
Phase 0: agent-ci  [T-CI-0, then T-CI-5 (allowlist snapshot freshness), then T-CI-1 .. T-CI-4]
Docs-0:  agent-gov [T-GOV-6: SECURITY.md] + [T-GOV-4: AGENTS.md]   (with/just after Phase 0)
Phase 1: agent-sec [T-SEC-1..6] || agent-time [T-TIME-1 + T-TIME-2 coordinated, T-TIME-3] || agent-crawl [T-CRAWL-1..2]
Gate:    G3 satisfied (T-GOV-1 Accepted ADR + active docs/TESTING.MD)
Phase 2: completed foundations [T-DA-1, T-DB-1A, T-DB-1, T-DB-1B,
         T-DC-1, T-DD-1A, T-DD-1B, T-DE-1]
Next:    Serialize each task's Full-plan registration through this ledger.
         T-PLAT-2D, T-PLAT-2E, and T-FE-1A are complete.
Phase 3: agent-plat [T-PLAT-1 after T-TIME-1 and T-TIME-2, T-PLAT-1A
         closure, T-PLAT-2B security patch, then T-PLAT-2..4; complete;
         T-PLAT-2D alert #121 and T-PLAT-2E Meilisearch migration complete]
         || agent-gov [T-GOV-2 policy and T-GOV-2A runtime enforcement
         complete; T-GOV-3A/B and T-GOV-5 complete]
After:   Remediation implementation is complete. City Coverage Expansion awaits
         the valid v2 expected-baseline PR.
```

Merge policy: one task = one PR, except operator-approved T-TIME-1 +
T-TIME-2, whose model and schema halves must ship together. PR title = task
id(s); every PR body includes
the GED-6 report. Any agent that cannot satisfy acceptance criteria within
its owned files reports and halts rather than widening scope.

## 8. OUT OF SCOPE (explicitly deferred; do not attempt)

- "Operator-only" auth on the Next proxy (not approved by G2; requires a
  future policy change).
- Retiring compatibility strata beyond the seven registered deletion tasks.
- Retiring frozen `migrate_v*` history after the Alembic baseline.
- env-access consolidation into config_env (low value until Phase 2 lands).
- Any change to inference runtime policy, models, or soak baselines.
