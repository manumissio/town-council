# Focused Plan: Post-Remediation Follow-Up

Scope: pipeline-doc integrity, baseline v2 evidence readiness, and
architecture-watchlist retirement.

plan_id: POST-REM-FOLLOWUP-2026-08
status_tracking: task state and evidence cells in the table below. Every task
PR may update only its own two cells in this file, even when the task's
implementation ownership is otherwise narrower. Do NOT add a
changelog section to this file and do NOT extend the frozen remediation plan
(docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md is historical evidence per the
2026-08-02 postmortem prevention table).
source: External review of docs/PIPELINE.md + verification of the
baseline_representative_v2 gap analysis. Both reviews dated 2026-08-02. The
file-map existence claim remains review evidence until T-DOC-2 supplies the
reproducible repository check.
amended: 2026-08-03 — reconciled against immutable master commit
a62ca0eff8eb7aae0e4d1b6776efefd7b401a1b1 after Codex review flagged
snapshot staleness: T-DOC-1,
T-DOC-3, T-DOC-4, and T-ARCH-9 were already completed on master and are
closed as pre-existing below. Earlier verification dates in this file refer
to the 2026-08-02 archive snapshot, which master has since advanced past.
postmortem_compliance: This plan follows the program postmortem's prevention
rules — it is small and focused; new checks are syntactic and bounded; task
ownership below was traced from entrypoints/consumers/docs/tests/CI, not from
expected diffs; policy meaning lands in canonical docs, task state lands in
the tracker table only.

---

## Directives (apply to every task)

- D1. AGENTS.md remains supreme; the planning templates
  (docs selection rules) apply. T-DOC-2 is Full-template work because it
  adds persistent enforcement machinery; T-BASE-2 is Full-template work
  because it touches soak-baseline comparability. T-ARCH-10 is an
  investigation only; any implementation it recommends gets a separate
  Full plan sized by assertion family.
- D2. Sourced vs derived: every step in an execution procedure (numbered
  steps in a task, a Full plan, or a PR body) must be marked either
  [sourced: <doc §>] or [derived: <policy it follows>]. Task charters in
  this file are scoping documents, not procedures; their Full plans carry
  the markings. Steps may not be presented as documented requirements
  unless a citation exists.
- D3. When restating the compatibility-seam prevention rule anywhere, quote
  its standard exactly:
  "proves duplication or reverse dependency and removes more seam machinery than it adds."
  Looser paraphrases (e.g. "proves it obsolete") drop the
  net-seam-reduction test and are incorrect.
- D4. Minimal diffs; no drive-by edits to PIPELINE.md sections not named in
  a task; the doc's honest documentation of retained facades is intentional
  and stays.
- D5. Deletion-test standard for every ARCH task: the change must remove
  complexity rather than move it, and per the compatibility-seam rule (D3)
  must remove more seam machinery than it adds. A task whose investigation
  concludes "no change warranted" is a VALID completion — record the
  evidence and close it.
- D6. No campaign: at most TWO ARCH *implementation* PRs in flight at once
  (P3 investigations and Full-plan authoring do not count toward the cap);
  one domain per PR; investigation and implementation are separate PRs.
  Template routing follows the planning templates' selection rules, which
  this plan cannot override (D1): T-ARCH-5 and T-ARCH-1 (facade families)
  are Full-mandatory regardless of
  tier; T-ARCH-2/3 Full per their gates. T-ARCH-10 does not authorize an
  implementation PR. An ARCH task edits
  tests/test_repository_guardrails.py only when its live HEAD census finds an
  entry affected by the task. PRs that actually edit that shared file
  SERIALIZE; independent ARCH PRs remain subject only to the two-PR cap.
- D7. Priority tiers below are a proposal; gate GA-1 applies.
- D8. Snapshot staleness: this plan was authored against an archive
  snapshot. Before opening any task's PR, re-verify the task's premise
  against HEAD. A premise that no longer holds closes the task as
  pre-completed (record the evidence in the tracker) — it does not license
  no-op or contradictory work.

## Gates

- GA-1 (operator): ratify or reorder the ARCH priority ranking. Blocks all
  ARCH implementation PRs; does not block investigations or Full-plan
  drafting.
- GB-1 (procedure, restating canonical policy — no new gate semantics):
  a `reduced-confidence` or non-baseline-valid capture is `non_comparable`;
  per docs/PERFORMANCE.md compare policy, inspect result.json and the
  listed confidence reason and fix that reason before using any run for
  the expected baseline [sourced: PERFORMANCE.md interpretation rules +
  compare policy]. Fixes land in separate PRs, then recapture
  [sourced: PERFORMANCE.md after T-BASE-1]. If the listed reason
  implicates runtime policy or profile configuration, escalate to the
  operator — agents may not alter those (AGENTS.md hard invariants).
  This gate introduces no retry counts or halt thresholds; any such
  addition would be a soak-gate semantic requiring ratification in
  canonical policy, not in this plan.

## Task tracker

| id        | state | immutable evidence and proving check |
|-----------|-------|-----------------|
| T-DOC-1   | closed (pre-completed) | `git show a62ca0e:docs/PIPELINE.md \| sed -n '52,68p'` |
| T-DOC-2   | open  |                 |
| T-DOC-3   | closed (pre-completed) | `git show a62ca0e:docs/PIPELINE.md \| sed -n '208,220p'` |
| T-DOC-4   | closed (pre-completed) | `git show a62ca0e:docs/PIPELINE.md \| rg '^## 11\\) Primary Implementation Map$'` |
| T-BASE-1  | open  |                 |
| T-BASE-2  | open  |                 |
| T-ARCH-1  | open  |                 |
| T-ARCH-2  | open  |                 |
| T-ARCH-3  | open  |                 |
| T-ARCH-4  | closed (pre-completed) | `a62ca0e`; [Python Guardrails run 30770109810](https://github.com/manumissio/town-council/actions/runs/30770109810) |
| T-ARCH-5  | open  |                 |
| T-ARCH-6  | open  |                 |
| T-ARCH-7  | open  |                 |
| T-ARCH-8  | open  |                 |
| T-ARCH-9  | closed (pre-completed) | [run 30770109810](https://github.com/manumissio/town-council/actions/runs/30770109810); `git show a62ca0e:tests/test_crawler_refactor_contract.py \| rg 'Fremont\|Moraga'` |
| T-ARCH-10 | open  |                 |
| T-ARCH-11 | blocked | ADR and supported-starting-state decision required |

---

## Lane DOC — PIPELINE.md integrity (one PR, agent-executable)

### T-DOC-1: Repair the Stage B duplicated rationale block  [CLOSED — pre-completed on master]
- evidence: master PIPELINE.md places the chunking rationale directly under run_parallel_processing(); no orphaned duplicate block remains.

### T-DOC-2: Guard the §11 file map with a syntactic existence check  [Full]
- files_owned: tests/test_pipeline_doc_file_map.py (new). The Full plan must
  name any additional file before implementation; this charter does not
  authorize edits elsewhere.
- do: Add a bounded check: extract every backtick-quoted syntactic path
  candidate from docs/PIPELINE.md that is either a literal `.py`/`.md` path
  or a terminal wildcard path. Terminal wildcards may be extensionless, such
  as `pipeline/task_*`, `api/task_route_*`, or `semantic_service/*`. Extract
  candidates without first consulting the filesystem. Derive the family
  set from those candidates' leading path segments, not from a hardcoded list
  or the set of directories that currently exists. Then assert that each
  candidate family exists, each literal path exists, and each glob family
  matches at least one file. This keeps a misspelled or entirely deleted
  family visible to the failure assertions. No prose
  interpretation, no content assertions — path existence only, per the
  postmortem rule for custom checks ("exact-set… syntactic and bounded").
- accept: Test passes on HEAD; deleting a literal referenced path or top-level
  family makes it fail; removing the final match for a glob family makes it
  fail, including for an extensionless terminal wildcard. The check names
  these supported cases in a docstring and does not
  claim that it protects every individual member represented only by a glob.
- forbidden: Extending the check to other docs in this PR; asserting doc
  content beyond path existence.
- verify: `./.venv/bin/ruff check .` + targeted pytest for the new test + full
  suite.

### T-DOC-3: Config-default provenance note on the OCR table  [CLOSED — pre-completed on master]
- evidence: master PIPELINE.md states pipeline/config_processing.py owns the loader fallbacks for the table.

### T-DOC-4: Retitle "Source-of-Truth File Map"  [CLOSED — pre-completed on master]
- evidence: master §11 is titled "Primary Implementation Map"; no "Source-of-Truth" occurrence remains.

---

## Lane BASE — baseline_representative_v2 evidence readiness

### T-BASE-1: Promote the capture-hygiene rule into PERFORMANCE.md
- files_owned: docs/PERFORMANCE.md (baseline interpretation-rules section,
  ~L121 block), docs/OPERATIONS.md (cross-reference line near the baseline
  capture commands, ~L1528, only if a pointer is missing)
- do: The rule "a baseline capture run makes no optimization, threshold, or
  runtime-policy changes; if capture exposes a defect, fix it in a separate
  PR and recapture" is currently only derived (from AGENTS.md hard
  invariants + the atomic-change policy) — it appears in no baseline doc.
  Add it to PERFORMANCE.md's baseline rules so it becomes [sourced].
  Runtime-policy immutability may cite AGENTS.md hard invariants inline.
- accept: The rule is stated once in PERFORMANCE.md; OPERATIONS capture
  section points to the rules rather than duplicating them; D2 marking in
  the PR body. If OPERATIONS changes, update its `Last updated` marker.
- verify: docs-link test; env/profile alignment test; grep confirms single
  statement; `git diff --check`.

### T-BASE-2: The evidence PR (Full template; human-gated execution)
- files_owned: profiling/baselines/baseline_representative_v2.json (new),
  docs/PERFORMANCE.md, docs/OPERATIONS.md,
  profiling/manifests/README.md, and docs/ADR.md. Preserve the accepted ADR
  decision and add implementation status; do not rewrite its history.
- depends_on: T-BASE-1 (so every step below is [sourced])
- human_gate: two independent captures run on the operator's machine with
  the same immutable commit, manifest and sidecar, preconditioned dataset,
  index artifacts, semantic settings, runtime profile, and warm/cold
  condition. The operator supplies complete artifacts for reference run A
  and validation run B. An agent prepares the plan and assembles the PR; it
  does not execute captures or fabricate artifacts. Absence of either
  artifact set = blocked, not improvisable.
- procedure (all steps must carry D2 markings in the plan):
  1. `--dry-run-prepare` inspection of controlled preconditioning
     [sourced: PERFORMANCE interpretation rules; OPERATIONS ~L1528].
  2. Stable local reference run A using the v2 manifest
     [sourced: OPERATIONS baseline capture section].
  3. Run A has `baseline_valid=true` and no `reduced-confidence` analyzer state
     [sourced: v1 baseline schema + PERFORMANCE rules].
  4. Run A artifacts present: provider telemetry, phase timings, stable
     workload counters [sourced: baseline schema fields
     elapsed_seconds/top_phases/stable_counters/reference_run_id].
  5. Derive the expected-baseline JSON from run A, same schema as v1, and set
     `reference_run_id` to run A
     [sourced: profiling/baselines/baseline_representative_v1.json].
  6. Capture independent validation run B under the same immutable commit,
     manifest and sidecar, preconditioned dataset, index artifacts, semantic
     settings, runtime profile, and warm/cold condition. Record those fields
     for both runs. Run B must also be baseline-valid and full-confidence,
     and may not reuse run A's output directory or run ID. Any mismatch makes
     the comparison `non_comparable` [sourced: PERFORMANCE interpretation
     rules; derived: independent validation].
  7. Compare run B via `--compare-to` against the expected baseline derived
     from run A. Include both commands, the shared runtime profile, both run
     IDs, and both artifact/report sets in the PR body
     [sourced: PERFORMANCE rules; derived: independent validation].
  8. Synchronize the four owned canonical documents from pending-candidate
     wording to merged-baseline status without changing the accepted ADR
     decision [derived: docs ownership and history preservation].
  9. No optimization/threshold/runtime-policy changes in the capture PR;
     defects found → separate fix PR, then recapture
     [sourced: PERFORMANCE after T-BASE-1].
- context_for_reviewer (include verbatim in the PR body): v2 uses the
  identical 30 catalog IDs as v1 with phase quotas redistributed — entity
  4→8 absorbs the retired people phase's slots (people 4→0; extract 8,
  segment 6, summary 6, org 2 unchanged). The shared IDs preserve record
  identity only. The phase change makes v1 and v2 non-comparable: do not use
  cross-version timings or stable counters for regression or promotion
  decisions. v1 and its checked-in expectation remain immutable historical
  evidence.
- accept: profiling/baselines/baseline_representative_v2.json merged;
  independent run B compares green against run A's expectation under
  documented tolerances; `reference_run_id` names run A; both artifact sets
  and all step evidence appear in the PR body with D2 markings; owned docs
  agree on implementation status.
- explicitly_not_claimed: merging this PR clears the baseline prerequisite
  only; City Expansion Readiness additionally requires the rollout-registry
  wave selection and crawl/derived-state/queue gates in ROADMAP.md — do not
  mark expansion ready on this PR.

---

## Lane ARCH — watchlist retirement (gated by D5–D7)

Source for every task: the 2026-07-19 architecture interrogation, re-verified
against the 2026-08-02 tree. Priority tiers: P1 = cheap true deletions with
evidence in hand; P2 = deep-module work needing a Full plan; P3 =
investigations that may close with no code change.

### T-ARCH-4: Verify the frozen migrate chain  [CLOSED — pre-completed]
- evidence: `.github/workflows/python-guardrails.yml` runs
  `tests/test_alembic_migrations.py` against Postgres before the full suite,
  which includes the frozen-runner and migrate_v8/v9/v10 contract tests;
  `pipeline/db_migration_runner.py` still invokes that chain for the supported
  unversioned-adoption path. Under the accepted ADR, the present result is
  "retain the frozen chain." No duplicate parity gate is needed.

### T-ARCH-11: Sunset the frozen migration chain  [future, Full, blocked]
- gate: a separately ratified ADR must define the minimum supported database
  state and retire support for unversioned/pre-Alembic starting states.
- files_owned: must be derived by the Full plan after that decision; this
  charter authorizes no migration-file edit or deletion.
- do: prove that every supported database starts from an Alembic-owned state,
  then remove the frozen runner and migrate_v8/v9/v10 end to end. Update
  migration and operator documentation and verify each supported starting
  state. This task records the operator's intended direction; it cannot begin
  while the current ADR and support floor remain active.

### T-ARCH-5: Retire LocalAI private re-exports  [P1, Full-mandatory]
- files_owned: pipeline/llm.py, pipeline/local_ai_agenda_compat.py,
  consumers identified by the census below, their tests,
  docs/PIPELINE.md (the LocalAI provider section and §11 entries touched)
- do: Step 1 (in the Full plan): consumer census — enumerate every import
  of llm.py's aliased symbols and of local_ai_agenda_compat, from code and
  from tests, distinguishing (a) external consumers of re-exports from
  (b) llm.py's own internal delegation to implementation modules, which is
  legitimate implementation and STAYS. The census covers every current
  implementation owner, including agenda_extraction, agenda_summary,
  agenda_text_heuristics, local_ai_runtime, and text_generation. Step 2:
  repoint (a) to those implementation owners, delete obsolete compatibility
  tests whose only contract is the retired seam, delete
  local_ai_agenda_compat.py, and remove the now-unconsumed re-export surface.
  Keep LocalAI product policy and public entrypoints intact.
- accept (behavioral, not lexical): no module outside llm.py imports a
  symbol from llm.py that llm.py merely re-exports from another module;
  local_ai_agenda_compat.py deleted; census table in the PR body with each
  consumer's disposition; D5 evidence (net symbols/seams removed); suite
  green. Renaming aliases without removing the re-export relationship does
  NOT satisfy this task.

### T-ARCH-9: Fremont/Moraga recorded-parse parity  [CLOSED — pre-completed on master]
- evidence: master test_crawler_refactor_contract.py has equivalent Belmont/Fremont/Moraga archive event contracts with document-level assertions and no network I/O.

### T-ARCH-10: Guardrail-file census  [P1, investigation only]
- read_scope: tests/test_repository_guardrails.py, ruff.toml, mypy.ini,
  .coveragerc, docs/ENGINEERING_GUARDRAILS.md, docs/TESTING.MD, and the
  canonical document targeted by each document-content assertion.
- files_owned: docs/plans/POST_REMEDIATION_FOLLOWUP_PLAN.md, tracker evidence
  cell only. The investigation may not edit guardrails or tests.
- do: Apply the postmortem's prevention rule to the 5,555-line file by
  classifying every assertion targeting document
  content, record one of: (a) pure prose-content assertion (headings,
  phrasing, casing of narrative text) → candidate for deletion; (b) invariant-bearing
  assertion (e.g., frozen-document immutability, link integrity) →
  candidate for syntactic replacement (content-hash pin for frozen files,
  path-existence for links) that names its supported cases; (c) syntactic
  code-policy check → retain. The PR body includes assertion family, current
  invariant owner, disposition, estimated line delta, and proposed task ID.
- accept: every document-content assertion belongs to exactly one family;
  every proposed implementation is split by concrete assertion family,
  declares exact ownership and size, uses a Full plan, and includes the full
  guardrail verification row. The tracker records the investigation PR. No
  implementation is authorized and unrelated ARCH work is not blocked.
- verify: `PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py` and
  `git diff --check` for the tracker-only investigation PR.

### T-ARCH-1: Search facade stack retirement  [P2, largest, Full-mandatory]
- gate: GA-1 + its own Full-template plan (one stratum per PR)
- files_owned: derived per contract-graph tracing in the Full plan —
  candidate set: api/search_routes.py, api/search_read_*.py, api/search/,
  api/search_semantic_routes.py, api/trends_routes.py, api/main.py wiring,
  consuming tests, docs/PIPELINE.md §11 entries
- do: MANDATORY investigation first: a route/consumer inventory
  establishing which endpoints are wired, which modules are live routes vs
  helpers vs genuinely superseded strata. The retirement direction is an
  OUTPUT of that inventory, not an input — do not assume oldest-first or
  that newer strata are complete replacements. Then retire one proven-
  redundant stratum per PR under the D5 deletion test.
- accept (per stratum PR): the inventory evidence names the stratum
  redundant; it is deleted end-to-end including its tests' patch targets;
  no re-export bridge left behind; §11 updated.

### T-ARCH-2: ResultCard decomposition  [P2, Full-mandatory]
- gate: GA-1 + Full plan (design pass, not mechanical)
- investigation_scope: frontend/components/ResultCard.js,
  frontend/lib/taskPolling.js,
  frontend/components/__tests__/ResultCard.ai-disclaimer.test.js,
  frontend/components/__tests__/ResultCard.people-projection.test.js, and
  frontend/components/__tests__/ResultCard.polling-contract.test.js. The Full
  plan must name each implementation file, new module, and test file exactly;
  broad directory ownership is not permitted.
- do: Both review prerequisites are met (runner + 42-test harness) and the
  polling seam is already extracted (taskPolling.js). Continue along the
  review's seam list — mutation dispatch, formatting, rendering — one
  extraction per PR, each behind the existing tests. The Full plan sets an
  explicit numeric line budget and a one-responsibility statement for what
  remains in ResultCard.js; "near composition-only" without numbers is not
  an acceptance criterion.
- accept (per extraction PR): user-visible behavior parity. Source-text
  assertions in ResultCard.ai-disclaimer.test.js may be replaced with
  rendered-behavior assertions; do not preserve the old source arrangement
  merely to keep a patch point. Other observable contracts remain covered,
  the extracted module has its own behavior test, and ResultCard.js shrinks
  toward the Full plan's stated budget.

### T-ARCH-3: Deepen semantic retrieval interface  [P2, Full-mandatory]
- gate: GA-1 + Full plan
- files_owned: semantic_service/retrieval.py, its callers and tests
- do: Replace the 13-parameter retrieve signatures with a typed request
  contract containing only query, filters, pagination, and retrieval
  settings (match the *_contracts.py convention). Backend, database session,
  and Meilisearch client remain explicit boundary parameters. Injectable
  implementation callables are removed in favor of private imports from
  their implementation owners.
- accept: Public retrieve interface takes the request contract plus explicit
  backend, database-session, and Meilisearch-client boundaries; every
  contract field is individually typed and
  documented — no dict payload field, no **kwargs, no Any escape hatch
  (a god-object with an opaque bag does not satisfy this task); suite
  green.

### T-ARCH-6: Frontend search coordinator  [P3, investigation first]
- read_scope: frontend/state/search-state.js, frontend/lib/api.js, their
  direct importers, and their tests.
- files_owned: docs/plans/POST_REMEDIATION_FOLLOWUP_PLAN.md, tracker evidence
  cell only.
- do: Census live/demo adapter ownership and call direction. The PR body
  table records adapter, caller, state owner, duplicated policy, and deletion
  impact.
- accept: close when one owner already exists or consolidation would only
  move complexity; otherwise register a separately approved Full task with
  exact files and deletion evidence. Verify docs links and `git diff --check`.

### T-ARCH-7: Index projection consolidation  [P3, investigation first]
- read_scope seeds: pipeline/indexer.py, pipeline/indexer_documents.py,
  pipeline/indexer_meilisearch.py, pipeline/reindex_only.py,
  pipeline/reindex_semantic.py, pipeline/task_side_effects.py,
  api/search_read_meilisearch.py, semantic_service/main.py,
  semantic_service/retrieval.py, tests/test_indexer_logic.py,
  tests/test_indexer_official_roster.py, and DATA_GOVERNANCE §3. Expand the
  census only through direct imports/callers found with
  `rg -n 'index_documents|_build_.*search_doc|reindex|people_metadata'`.
- files_owned: docs/plans/POST_REMEDIATION_FOLLOWUP_PLAN.md, tracker evidence
  cell only.
- do: Record data class, policy owner, implementation owner, consumers, and
  conflicting/duplicated decisions in the PR body evidence table.
- accept: close if every projection rule has one implementation owner;
  otherwise register a separately approved Full task that names the exact
  duplicated policy and files. Verify docs links and `git diff --check`.

### T-ARCH-8: Crawler staging persistence  [P3, investigation first]
- read_scope seeds: council_crawler/council_crawler/pipelines.py,
  council_crawler/council_crawler/models.py,
  council_crawler/council_crawler/settings.py, pipeline/promote_stage.py,
  pipeline/db_session.py, tests/test_crawler_refactor_contract.py,
  tests/test_database.py, and tests/test_pipeline_idempotency.py. Expand only
  through direct imports/callers found with
  `rg -n 'CreateEventPipeline|StageDocumentLinkPipeline|promote_stage|EventStage|UrlStage'`.
- files_owned: docs/plans/POST_REMEDIATION_FOLLOWUP_PLAN.md, tracker evidence
  cell only.
- do: Record each local transaction block, owner, invariant, and any actual
  duplicated policy in the PR body evidence table.
- accept: default to closure when the two local transaction blocks are
  cohesive and do not justify another seam. Only proven duplicated policy
  may create a separately approved narrow task. Verify docs links and
  `git diff --check`.

---

## Execution order

```
DOC lane: T-DOC-2 may proceed independently (T-DOC-1/3/4 are closed).
BASE lane: T-BASE-1 -> independent operator runs A/B -> T-BASE-2.
ARCH lane: T-ARCH-10 is an investigation and does not block T-ARCH-5 or other
           unrelated work. T-ARCH-4 and T-ARCH-9 are closed; T-ARCH-11 is
           blocked on a future ADR/support-floor decision. At most two
           implementation PRs are in flight. Only tasks whose live census
           requires an edit to the shared guardrail file serialize under D6.
           P2 tasks follow GA-1 behind their own Full plans. P3 investigations
           may run anytime; implementation requires a new gated task. Per D8,
           every task re-verifies its premise against HEAD before its PR opens.
```

DOC, BASE, and ARCH lanes are independent; T-BASE-2 alone is sequenced
after T-BASE-1. Investigation tasks may run in parallel when their read
scopes do not overlap; each resulting implementation requires its own
approved task and plan.

## Out of scope

- Any other PIPELINE.md edits, including facade-inventory pruning — the
  retained-facade honesty is a feature (though ARCH deletions must update
  the §11 map entries they invalidate; the T-DOC-2 check will catch misses).
- Extending the file-map existence check to other documents (revisit only
  if a second doc exhibits the same staleness risk — the second-finding
  rule, not preemption).
- Baseline threshold or tolerance changes; runtime-profile changes; any
  soak-gate semantics (hard invariants, human decision required).
- Reopening or amending the frozen remediation plan.
- Any facade retirement outside the domains named in Lane ARCH — the
  candidate-08 rule stands: no repository-wide purge; watchlist domains
  only, one at a time, under D5/D6.
