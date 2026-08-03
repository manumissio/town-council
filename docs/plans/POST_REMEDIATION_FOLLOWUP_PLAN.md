# Focused Plan: Post-Remediation Follow-Up

Scope: pipeline-doc integrity, baseline v2 evidence readiness, and
architecture-watchlist retirement.

plan_id: POST-REM-FOLLOWUP-2026-08
status_tracking: PR checkboxes against the task table below. Do NOT add a
changelog section to this file and do NOT extend the frozen remediation plan
(docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md is historical evidence per the
2026-08-02 postmortem prevention table).
source: External review of docs/PIPELINE.md (verified against tree, all 72
file refs currently valid) + verification of the baseline_representative_v2
gap analysis. Both reviews dated 2026-08-02.
amended: 2026-08-03 — reconciled against live master (parent of PR #224
commit 83b020a) after Codex review flagged snapshot staleness: T-DOC-1,
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
  (docs selection rules) apply — T-BASE-2 is a mandatory Full-template task
  because it touches soak-baseline comparability.
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
  this plan cannot override (D1): T-ARCH-4 (schema/migrations) and
  T-ARCH-5, T-ARCH-1 (facade families) are Full-mandatory regardless of
  tier; T-ARCH-2/3 Full per their gates; T-ARCH-9 may use Light;
  T-ARCH-10 may use Light with the guardrail-change justification the
  AGENTS.md maintenance triggers require.
  T-ARCH-10 lands first. After that, an ARCH task edits
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
- GA-2 (operator): one Postgres parity run for T-ARCH-4 (set
  TEST_POSTGRES_DATABASE_URL, run the currently-skipped migrate_v10
  tests); attach the run output to the T-ARCH-4 PR. Blocks T-ARCH-4 only.
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

| id        | state | evidence (PR #) |
|-----------|-------|-----------------|
| T-DOC-1   | closed (pre-completed) | master@parent-of-83b020a |
| T-DOC-2   | open  |                 |
| T-DOC-3   | closed (pre-completed) | master@parent-of-83b020a |
| T-DOC-4   | closed (pre-completed) | master@parent-of-83b020a |
| T-BASE-1  | open  |                 |
| T-BASE-2  | open  |                 |
| T-ARCH-1  | open  |                 |
| T-ARCH-2  | open  |                 |
| T-ARCH-3  | open  |                 |
| T-ARCH-4  | open  |                 |
| T-ARCH-5  | open  |                 |
| T-ARCH-6  | open  |                 |
| T-ARCH-7  | open  |                 |
| T-ARCH-8  | open  |                 |
| T-ARCH-9  | closed (pre-completed) | master@parent-of-83b020a |
| T-ARCH-10 | open  |                 |

---

## Lane DOC — PIPELINE.md integrity (one PR, agent-executable)

### T-DOC-1: Repair the Stage B duplicated rationale block  [CLOSED — pre-completed on master]
- evidence: master PIPELINE.md places the chunking rationale directly under run_parallel_processing(); no orphaned duplicate block remains.

### T-DOC-2: Guard the §11 file map with a syntactic existence check
- files_owned: tests/test_docs_links.py (or a sibling
  tests/test_pipeline_doc_file_map.py if link-test scope is link-only by
  design — decide in-PR and say why)
- do: Add a bounded check: extract every backtick-quoted syntactic path
  candidate from docs/PIPELINE.md matching `<family>/<...>.py|.md`, including
  glob families, without first consulting the filesystem. Derive the family
  set from those candidates' leading path segments, not from a hardcoded list
  or the set of directories that currently exists. Then assert that each
  candidate family exists, each literal path exists, and each glob family
  matches at least one file. This keeps a misspelled or entirely deleted
  family visible to the failure assertions. No prose
  interpretation, no content assertions — path existence only, per the
  postmortem rule for custom checks ("exact-set… syntactic and bounded").
- accept: Test passes on HEAD; deleting any referenced module or top-level
  family makes it fail; the check names its supported cases in a docstring
  (paths and globs) and nothing else.
- forbidden: Extending the check to other docs in this PR; asserting doc
  content beyond path existence.
- verify: targeted pytest for the new test + full suite.

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
  the PR body.
- verify: docs-link test; grep confirms single statement.

### T-BASE-2: The evidence PR (Full template; human-gated execution)
- files_owned: profiling/baselines/baseline_representative_v2.json (new),
  PR body artifacts; ROADMAP.md City Expansion Readiness status line only
  if the operator chooses to tick it in the same PR.
- depends_on: T-BASE-1 (so every step below is [sourced])
- human_gate: the capture itself runs on the operator's machine with the
  local runtime profile — an agent prepares the plan and assembles the PR;
  it does not execute the capture or fabricate its artifacts. Absence of
  artifacts = the task is blocked, not improvisable.
- procedure (all steps must carry D2 markings in the plan):
  1. `--dry-run-prepare` inspection of controlled preconditioning
     [sourced: PERFORMANCE interpretation rules; OPERATIONS ~L1528].
  2. Stable local baseline run using the v2 manifest
     [sourced: OPERATIONS baseline capture section].
  3. `baseline_valid=true` and no `reduced-confidence` analyzer state
     [sourced: v1 baseline schema + PERFORMANCE rules].
  4. Required artifacts present: provider telemetry, phase timings, stable
     workload counters [sourced: baseline schema fields
     elapsed_seconds/top_phases/stable_counters/reference_run_id].
  5. Derive the expected-baseline JSON from that run, same schema as v1
     [sourced: profiling/baselines/baseline_representative_v1.json].
  6. Re-run comparison via `--compare-to` against the proposed baseline;
     include commands, runtime profile, run ID, and reports in the PR body
     [sourced: PERFORMANCE rules].
  7. No optimization/threshold/runtime-policy changes in the capture PR;
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
  comparison run green under documented tolerances; PR body carries all
  step evidence with D2 markings.
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

### T-ARCH-4: Rationalize the migrate chain vs Alembic ownership  [P1, Full-mandatory]
- gate: GA-2 (operator parity run)
- correction (Codex P1, PR #224): migrate_v10.py is NOT a shallow wrapper —
  it owns ~200 lines of timestamp-contract validation and UTC conversion,
  and pipeline/db_migration_runner.py imports migrate_v8 and migrate_v10
  for unversioned-database adoption. The July watchlist's "shallow
  wrapper" characterization applied to the v8/v9 era and does not transfer
  wholesale. Blanket deletion would drop or merely relocate that
  conversion, failing D5 and the legacy-upgrade criterion.
- files_owned (contract-graph traced): pipeline/migrate_v8.py,
  migrate_v9.py, migrate_v10.py, pipeline/db_migrate.py,
  pipeline/db_migration_runner.py and every caller of the migrate chain
  (enumerate in the Full plan), docs/OPERATIONS.md (migration section),
  docs/PIPELINE.md (§11 entries for any deleted module), alembic/ (only
  if delegation wiring changes), their tests.
- do: Census first (in the Full plan): map every migrate_v* module's role —
  implementation owner vs pass-through — and its consumers, including
  db_migration_runner's unversioned-adoption path. Retire ONLY modules
  the census proves are pass-throughs whose behavior Alembic revisions or
  a retained owner already provide. migrate_v10's conversion logic is
  RETAINED as the unversioned-adoption owner unless the census proves the
  Alembic baseline subsumes it for every supported starting state; the
  Full plan MUST state the upgrade story for pre-Alembic databases —
  silent loss of the legacy upgrade path is a rejection criterion.
- accept: Census table in the PR body with each module's disposition and
  evidence; only census-proven pass-throughs deleted; fresh-DB and
  upgraded-DB schema diff empty; a v9/v10-era database's documented
  upgrade path verified in the parity run; OPERATIONS and §11 updated;
  suite green; GA-2 output attached. "No change warranted" is a valid
  census outcome (D5).

### T-ARCH-5: Retire LocalAI private re-exports  [P1, Full-mandatory]
- files_owned: pipeline/llm.py, pipeline/local_ai_agenda_compat.py,
  consumers identified by the census below, their tests,
  docs/PIPELINE.md (§11 entries touched)
- do: Step 1 (in the Full plan): consumer census — enumerate every import
  of llm.py's aliased symbols and of local_ai_agenda_compat, from code and
  from tests, distinguishing (a) external consumers of re-exports from
  (b) llm.py's own internal delegation to implementation modules, which is
  legitimate implementation and STAYS. The census covers every current
  implementation owner, including agenda_extraction, agenda_summary,
  agenda_text_heuristics, local_ai_runtime, and text_generation. Step 2:
  repoint (a) to those implementation owners, delete
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

### T-ARCH-10: Guardrail-file diet  [P1, Light OK, lands FIRST in lane]
- files_owned: tests/test_repository_guardrails.py
- do: Apply the postmortem's prevention rule to the 5,555-line file — but
  classify before deleting. For every assertion targeting document
  content, record one of: (a) pure prose-content assertion (headings,
  phrasing, casing of narrative text) → DELETE; (b) invariant-bearing
  assertion (e.g., frozen-document immutability, link integrity) →
  REPLACE with a syntactic equivalent (content-hash pin for frozen files,
  path-existence for links) that names its supported cases; (c) syntactic
  code-policy check → KEEP. The classification table ships in the PR body.
  An invariant-bearing assertion may be dropped only after a separate,
  ratified change removes or replaces the invariant in its canonical policy;
  recording a drop decision in the PR body is not sufficient.
  Differential change, not a rewrite: this is the candidate-07 end-state
  the program did not reach, taken in one bounded step.
- accept: No test asserts prose content of docs/plans/* or
  docs/postmortems/*; every invariant previously enforced by a deleted
  assertion has a named syntactic replacement, or its canonical policy change
  was separately ratified and merged before the assertion is removed; file
  materially smaller; every retained custom check names its supported cases
  in a docstring; suite green.
- sequencing: lands before any other ARCH implementation PR. Later PRs follow
  D6's conditional shared-file rule.

### T-ARCH-1: Search facade stack retirement  [P2, largest, Full-mandatory]
- gate: GA-1 + its own Full-template plan (one stratum per PR)
- files_owned: derived per contract-graph tracing in the Full plan —
  candidate set: api/search_routes.py, api/search_read_*.py, api/search/,
  api/main.py wiring, consuming tests, docs/PIPELINE.md §11 entries
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
- files_owned: frontend/components/ResultCard.js, frontend/lib/,
  frontend/components/__tests__/
- do: Both review prerequisites are met (runner + 42-test harness) and the
  polling seam is already extracted (taskPolling.js). Continue along the
  review's seam list — mutation dispatch, formatting, rendering — one
  extraction per PR, each behind the existing tests. The Full plan sets an
  explicit numeric line budget and a one-responsibility statement for what
  remains in ResultCard.js; "near composition-only" without numbers is not
  an acceptance criterion.
- accept (per extraction PR): behavior parity — the existing test files
  pass with their ASSERTIONS unchanged (imports/patch targets may move per
  TESTING.MD); the extracted module has its own test; ResultCard.js
  shrinks toward the Full plan's stated budget.

### T-ARCH-3: Deepen semantic retrieval interface  [P2, Full-mandatory]
- gate: GA-1 + Full plan
- files_owned: semantic_service/retrieval.py, its callers and tests
- do: Replace the 13-parameter retrieve signatures with a typed request
  contract (match the *_contracts.py convention); implementation callables
  become private.
- accept: Public retrieve interface takes the request contract (plus at
  most session/config); every contract field is individually typed and
  documented — no dict payload field, no **kwargs, no Any escape hatch
  (a god-object with an opaque bag does not satisfy this task); suite
  green.

### T-ARCH-6: Frontend search coordinator  [P3, investigation first]
- do: Investigate consolidating live/demo search adapters behind one
  coordinator (frontend/state/search-state.js + lib/api.js). Output: a
  one-page finding — proceed with a Full plan, or close per D5.

### T-ARCH-7: Index projection consolidation  [P3, investigation first]
- do: Post-G4/T-IDX-1, investigate whether projection policy (what enters
  the search index per data class) has a single owner; propose one if not.
  DATA_GOVERNANCE §3 is the policy source; code should mirror it in one
  place.

### T-ARCH-8: Crawler staging persistence  [P3, investigation first]
- do: The review flagged duplicated session/transaction policy; current
  tree shows it concentrated in council_crawler pipelines.py. Verify
  against pipeline/ persistence policy and either file a narrow follow-up
  or close with evidence. Expected outcome: closes cheaply.

---

## Execution order

```
PR 1: T-DOC-2 (only remaining DOC task; new guardrail, reviewed against
      postmortem rules — T-DOC-1/3/4 closed as pre-completed on master)
PR 2: T-BASE-1 (doc promotion; unblocks sourced markings)
PR 3: T-BASE-2 (operator capture + agent-assembled evidence PR)
ARCH: T-ARCH-10 lands FIRST; then P1 tasks (T-ARCH-4/5) in any order, max
      two implementation PRs in flight (T-ARCH-9 closed as pre-completed).
      Only tasks whose live census requires an edit to the shared guardrail
      file serialize under D6. P2 tasks follow GA-1, each behind its own Full
      plan; P3 investigations may run anytime, with implementation only via
      new gated tasks. Per D8, every task re-verifies its premise against HEAD
      before its PR opens.
```

DOC, BASE, and ARCH lanes are independent; T-BASE-2 alone is sequenced
after T-BASE-1; T-ARCH-4 alone is gated on the operator parity run.

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
