# Focused Plan: Post-Remediation Follow-Up

Scope: baseline-v2 evidence readiness and bounded architecture investigations.

Plan ID: `POST-REM-FOLLOWUP-2026-08`

Status owner: repository maintainer

Source: operator-provided pipeline review, PR #224 review record, and the
2026-08-02 remediation postmortem.

Last reconciled: 2026-08-03 against commit
`a62ca0eff8eb7aae0e4d1b6776efefd7b401a1b1` and current PR #224 HEAD.

This file is the only task tracker for this follow-up. The frozen remediation
plan remains historical evidence and must not be extended. Do not add a
changelog here.

---

## 1. Operating Rules

1. `AGENTS.md` and the canonical documents it names remain authoritative.
2. Every task re-verifies its premise against HEAD before planning or edits.
3. Investigation and implementation are separate PRs. An investigation may
   close with "no change warranted."
4. An investigation cannot authorize code changes. It may propose a child
   implementation task with exact ownership, verification, and rollback;
   adding that child to this tracker requires operator approval.
5. Evidence used by later work must be checked in. PR prose may summarize it
   but is not its only home.
6. Each task PR updates only its own tracker row. Concurrent task branches
   rebase before merge so tracker updates land sequentially.
7. Compatibility work must prove duplication or reverse dependency and remove
   more seam machinery than it adds.
8. Citations are required for normative or non-obvious claims. No universal
   sentence-tagging protocol is required.
9. At most two future architecture implementation PRs may be active at once.
   Investigation PRs do not count toward this limit.

## 2. Task Tracker

| ID | State | Accountable role | Durable evidence |
| --- | --- | --- | --- |
| T-DOC-1 | Closed before this plan | Repository maintainer | PR #222 and current `docs/PIPELINE.md` Stage B |
| T-DOC-2 | Closed, not pursued | Repository maintainer | PR #224 review record; permanent Markdown parser rejected |
| T-DOC-3 | Closed before this plan | Repository maintainer | PR #222 and current OCR provenance note |
| T-DOC-4 | Closed before this plan | Repository maintainer | PR #222 and current `Primary Implementation Map` heading |
| T-BASE-1 | Open | Repository maintainer | Pending PR |
| T-BASE-2A | Open | Repository maintainer | Pending Full plan and PR |
| T-BASE-2B | Blocked on T-BASE-2A and operator captures | Repository operator | Pending evidence PR |
| T-ARCH-1I | Open investigation | Repository maintainer | Pending checked-in census |
| T-ARCH-2I | Open investigation | Frontend maintainer | Pending checked-in census |
| T-ARCH-3I | Open investigation | Semantic-service maintainer | Pending checked-in census |
| T-ARCH-4 | Closed before this plan | Repository maintainer | [Python Guardrails run 30770109810](https://github.com/manumissio/town-council/actions/runs/30770109810) |
| T-ARCH-5I | Open investigation | Inference maintainer | Pending checked-in census |
| T-ARCH-6I | Open investigation | Frontend maintainer | Pending checked-in census |
| T-ARCH-7I | Open investigation | Search/index maintainer | Pending checked-in census |
| T-ARCH-8I | Open investigation | Crawler maintainer | Pending checked-in census |
| T-ARCH-9 | Closed before this plan | Crawler maintainer | Python Guardrails run 30770109810 and `tests/test_crawler_refactor_contract.py` |
| T-ARCH-10I | Open investigation | Guardrail maintainer | Pending checked-in census |

Closed-state provenance remains tied to the cited commit/PR. Before relying on
a closed state, rerun its current enforcing test or inspect the current
canonical section; stale evidence reopens the task instead of licensing a
contradictory change.

---

## 3. Documentation Lane

### T-DOC-1, T-DOC-3, and T-DOC-4: Closed

PR #222 already repaired the Stage B rationale placement, added OCR-default
provenance, and renamed the implementation map. Current verification:

```bash
sed -n '52,68p' docs/PIPELINE.md
sed -n '208,220p' docs/PIPELINE.md
rg -n '^## 11\) Primary Implementation Map$' docs/PIPELINE.md
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
```

### T-DOC-2: Do not build a PIPELINE.md path parser

The proposed syntactic guard grew from a small existence test into a custom
Markdown grammar with section-boundary, wildcard, tracked-file, and fixture
requirements. Even then it could detect only stale literals and empty glob
families, not a missing member from a still-populated wildcard family.

Decision: do not add persistent enforcement machinery. Every architecture PR
must update the exact `docs/PIPELINE.md` entries it invalidates and run the
normal documentation checks. Architecture review remains responsible for
semantic omissions.

---

## 4. Baseline Lane

### T-BASE-1: Make capture hygiene canonical

**Ownership**

- `docs/PERFORMANCE.md`, baseline interpretation rules
- `docs/OPERATIONS.md`, one pointer only if the capture section lacks it
- this task's tracker row

**Change**

Add this rule once to `docs/PERFORMANCE.md`:

> A baseline capture is measurement-only: do not change optimization,
> thresholds, or runtime policy during capture. Fix defects in a separate PR,
> then recapture.

If `docs/OPERATIONS.md` changes, point to the performance rule rather than
duplicating it. Update every materially changed document's `Last updated`
marker.

**Acceptance and verification**

```bash
test "$(rg -F -c 'A baseline capture is measurement-only:' docs/PERFORMANCE.md)" -eq 1
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_env_example_profile_alignment.py
git diff --check
```

### T-BASE-2A: Add machine-verifiable baseline provenance

This is a separate Full-template implementation task. It must land before any
v2 capture is accepted.

**Problem to solve**

Current `baseline_valid` means only that baseline mode was selected. The
comparator does not prove commit, manifest package, preconditioned workload,
dataset/index state, semantic settings, or warm/cold condition. Run output
directories are ignored, so PR prose alone is not durable evidence.

**Required first production result**

Given independent run directories A and B, one command produces a bounded,
checked-in evidence document and exits nonzero unless the runs are comparable.
The document must contain:

- schema version and complete run IDs
- immutable commit SHA for each run
- host platform, Docker version, and explicit inference backend/model identity
- manifest and sidecar identity, including SHA-256 and catalog IDs
- recorded direct reset counts and the execution matrix derived from the
  restored pre-run state
- pre-run database snapshot, index, and semantic-state identifiers defined by
  the Full plan
- recorded service and queue quiescence evidence before each measured run
- controlled runtime-profile fields, request/sample count, and warm/cold
  condition
- required artifact presence and SHA-256 values
- nonempty elapsed, phase, and stable-counter evidence
- mismatch reasons and final `comparable` status

The checked-in evidence package must contain every normalized input and value
used for comparability and expected-baseline generation. External raw-artifact
URLs may be included only as supplemental evidence; expiry cannot prevent a
reviewer from reproducing the package's hashes, validation, or derivation.

**Design constraints**

- Extend existing profiler result/comparison modules; do not create a second
  profiling framework.
- Separate expected-baseline fields from analyzer-confidence evidence.
- Generate the expected baseline deterministically from run A.
- Require these v2 phase families from the manifest and command plan:
  `extract_parallel`, `segment_agenda`, `summarize`, `entity_backfill`, and
  `org_backfill`.
- Treat `phase_quotas`, `strata`, and `expected_phase_coverage` as direct
  selection metadata, not observed execution coverage. For the approved
  restored v2 state, validate direct quotas and runtime outcomes separately:
  - extraction: `8` direct catalogs; `8` selected and processed. Preconditioning
    does not reset extraction, so another count is non-comparable unless the
    Full plan explicitly changes the restoration mechanism.
  - segmentation: `6` direct catalogs; `6` selected.
  - summary: `6` direct catalogs; `12` selected after the six segmentation
    catalogs also lose summary state.
  - entity enrichment: `8` direct catalogs; `8` selected.
  - organization enrichment: `2` direct event resets; the runner selects every
    unique event attached to the 30 scoped catalogs. The current evidence shows
    `24` selected and `2` linked, but T-BASE-2A must derive and record the event
    count from each restored snapshot instead of treating `24` as universal.
- Require the existing stable-counter families `agenda_segmentation_backfill`,
  `summary_hydration_backfill`, and `entity_backfill`. Add normalized extract
  evidence with selected, processed, and failure totals. Add normalized
  organization evidence with selected events, linked events, failures, and the
  manifest-to-event mapping. Add normalized segmentation reindex-failure
  evidence until that path exposes it in the stable counter. Those paths
  currently lack equivalent structured counters.
- Define successful execution through observable outcomes rather than attempt
  counts:
  - extraction selects and processes `8`; every direct extraction catalog ends
    with complete extraction state, nonempty content, and a content hash, with
    zero failed catalogs.
  - segmentation reports `selected=6`, `complete=6`, and zero empty, failed, or
    other outcomes, with zero reindex failures.
  - summary reports `selected=12`, `complete=12`, `cached=0`, `stale=0`,
    `blocked_low_signal=0`, `blocked_ungrounded=0`, `not_generated_yet=0`,
    `error=0`, `other=0`, `reindex_failed=0`, and
    `embed_dispatch_failed=0`.
  - entity enrichment reports `selected=8`, `complete=8`, and freshness
    advanced for all eight reset catalogs; an exception fails the run.
  - organization enrichment reports the derived selected-event count,
    `linked=2`, zero failed reindexes, and successful reindexing of every
    changed catalog.
- Fail generation and comparison unless direct selections match the v2
  sidecar, all accepted outcomes above hold, and observed execution matches the
  restored-state matrix. Empty or partial phase/counter contracts are invalid.
- Treat partial, failed, reduced-confidence, provenance-mismatched, or reused
  run IDs as non-comparable.
- Document that `--dry-run-prepare` currently runs migration and hash-backfill
  setup before its dry-run preconditioning report. The Full plan must either
  make inspection genuinely non-mutating or name those setup effects and the
  restoration procedure.

**Owned files and exact verification**

The Full plan derives exact ownership from the existing profiler modules and
tests before implementation. It must include targeted profiler tests, Ruff,
Mypy when typed files change, the complete Python suite, and `git diff --check`.
No runtime default, tolerance, or soak-gate semantic may change.

### T-BASE-2B: Capture and promote baseline_representative_v2

This Full-template evidence task begins only after T-BASE-2A merges and the
operator supplies two independent captures.

**Ownership**

- `profiling/baselines/baseline_representative_v2.json` (new)
- the checked-in evidence document produced by T-BASE-2A
- `docs/PERFORMANCE.md`
- `docs/OPERATIONS.md`
- `profiling/manifests/README.md`
- `docs/ADR.md`, implementation status only; preserve accepted history
- `ROADMAP.md`, baseline-prerequisite status only; preserve every other gate
- this task's tracker row

**Capture contract**

Run A and run B use the same immutable commit, host platform, Docker version,
inference backend/model, manifest/sidecar, runtime profile, request/sample
count, and warm/cold condition. Before run A and again before run B, restore
the same captured database snapshot and recreate the same index and semantic
state through the mechanism approved in T-BASE-2A's Full plan. Record the
pre-run state identifiers for both captures. The runs use distinct run IDs and
output directories. Each must be complete, baseline-valid under the
T-BASE-2A contract, and full-confidence. Any mismatch, partial run, or failed
restoration is non-comparable and requires restoration followed by recapture.

Each capture must also exclude unrelated asynchronous work. T-BASE-2A's Full
plan must choose either a dedicated isolated Compose project or a documented
stop-and-drain sequence followed by transient profiling command containers.
Immediately before each measured run, record the chosen isolation mechanism
and zero broker depth for every queue configured for the profile stack. If any
worker daemons remain running, also record zero Celery active, reserved, and
scheduled tasks. Keep unrelated task producers and asynchronous consumers
stopped during measurement, and record any work emitted by the profile after
the measured commands. An empty queue check while unrelated producers or
consumers remain live is not sufficient.

Run A deterministically produces the expected baseline. Run B is compared
against it. `reference_run_id` names run A. The v1 and v2 workloads remain
non-comparable because v2 removes the retired people phase and reallocates its
catalogs to entity enrichment.

**Acceptance**

- T-BASE-2A's validator accepts the checked-in A/B evidence.
- Run B compares successfully against the expectation generated from run A.
- Required phase and stable-counter families are nonempty.
- Direct selections match the manifest sidecar, every workload satisfies the
  explicit accepted outcomes in T-BASE-2A, and observed execution matches its
  complete restored-state matrix.
- Both captures include passing quiescence evidence and show no unrelated task
  execution during the measured commands.
- Canonical documents agree that v2 evidence has landed while retaining all
  other City Coverage Expansion gates.
- No optimization, threshold, runtime-profile, or gate-policy change appears
  in the evidence PR.

**Verification**

The Full plan must provide the exact T-BASE-2A validation/export command and
expected output, plus:

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/test_pipeline_profile_report.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_profile_pipeline_cli.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_operator_profile_helpers.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_env_example_profile_alignment.py
PYTHONPATH=. .venv/bin/pytest -q
git diff --check
```

---

## 5. Architecture Investigation Lane

Every open architecture item below is investigation-only. Its PR may add one
evidence file under `docs/reviews/post-remediation/` and update its tracker
row. Each evidence file must record the full HEAD SHA, exact census commands,
the resulting population and count, zero unclassified entries, ownership and
dependency direction, observable behavior at risk, deletion-test result, and
either `close` or `propose child task`.

A child task is not authorized until the operator approves its exact ID,
ownership, Full plan, verification-matrix union, observable regression tests,
and rollback. Parent investigations close when their evidence merges; they do
not remain open across an undefined implementation campaign.

### T-ARCH-1I: Search ownership census

**Seeds:** `api/search_routes.py`, `api/search_read_*.py`, `api/search/`,
`api/search_semantic_routes.py`, `api/trends_routes.py`, `api/main.py`, direct
tests, and `docs/PIPELINE.md` §11.

**Census:** trace router registration, imports, callers, and endpoint contracts.
Classify every module as live route, implementation owner, compatibility seam,
or unreferenced. Do not preselect a stratum for deletion.

### T-ARCH-2I: ResultCard responsibility census

**Seeds:** `frontend/components/ResultCard.js`, `frontend/lib/taskPolling.js`,
and the three `ResultCard.*.test.js` files.

**Census:** identify responsibilities, dependency direction, duplicated logic,
and rendered behavior contracts. Do not use line count as a gate. Propose an
extraction only when it improves cohesion or dependency direction and removes
more complexity than it introduces. Source-text tests may be replaced only by
rendered-behavior tests in an approved child task.

### T-ARCH-3I: Semantic retrieval dependency census

**Seeds:** `semantic_service/retrieval.py`, its direct callers, and retrieval
tests.

**Census:** evaluate the existing `SemanticRetrievalSettings` and
`SemanticSearchFilters`, the duplicate raw filter representation, boundary
parameters, and injected callables. Prefer composing or narrowing existing
types. A new request contract is acceptable only if evidence proves net
machinery reduction.

### T-ARCH-5I: LocalAI compatibility census

**Seeds:** `pipeline/llm.py`, `pipeline/local_ai_agenda_compat.py`,
`pipeline/agenda_summary_batch.py`, agenda rendering/scaffold modules, all
imports, and direct tests.

**Census:** record every symbol, caller, signature, threshold, output contract,
and production path. Prove behavioral equivalence per symbol before proposing
migration or deletion. Current production use means deletion is not presumed.
Any child task must own both affected LocalAI sections of `docs/PIPELINE.md`.

### T-ARCH-6I: Frontend search coordination census

**Seeds:** `frontend/state/search-state.js`, `frontend/lib/api.js`, their direct
importers, and tests.

**Census:** record adapter, caller, state owner, duplicated policy, and deletion
impact. Close if one owner already exists or consolidation only moves
complexity.

### T-ARCH-7I: Search projection ownership census

**Seeds:** `pipeline/indexer.py`, `pipeline/indexer_documents.py`,
`pipeline/indexer_meilisearch.py`, `pipeline/reindex_only.py`,
`pipeline/reindex_semantic.py`, `pipeline/task_side_effects.py`,
`api/search_read_meilisearch.py`, `semantic_service/main.py`,
`semantic_service/retrieval.py`, direct tests, and DATA_GOVERNANCE §3.

**Census:** record each indexed data class, policy owner, implementation owner,
consumer, and conflicting decision. Close if each projection rule already has
one implementation owner.

### T-ARCH-8I: Crawler staging transaction census

**Seeds:** `council_crawler/council_crawler/pipelines.py`, crawler models and
settings, `pipeline/promote_stage.py`, `pipeline/db_session.py`, and direct
tests.

**Census:** record each transaction block, owner, invariant, error behavior,
and actual duplication. Do not introduce a shared seam unless repeated policy
is proven. The expected cheap outcome is closure when the local transactions
are cohesive.

### T-ARCH-10I: Bounded guardrail assertion census

**Seeds:** complete matching test functions emitted by this reproducible,
single-file command only:

```bash
awk '
function flush_test() {
  if (in_test && relevant) printf "%s", test_block
}
/^(async )?def / {
  flush_test()
  in_test = ($0 ~ /^(async )?def test_/)
  relevant = 0
  test_block = ""
}
in_test {
  test_block = test_block sprintf("%d:%s\n", NR, $0)
  if ($0 ~ /docs\/(plans|postmortems)\// ||
      $0 ~ /ROOT \/ "docs" \/ "(plans|postmortems)"/) relevant = 1
}
END { flush_test() }
' tests/test_repository_guardrails.py
```

The two match branches cover slash-delimited literals and `pathlib`-constructed
directory references. At the reconciled commit, the command emits nine tests
containing 13 references: 12 constructed paths and one slash-delimited literal.
Classify every assertion consuming plan or postmortem content in each emitted
test by canonical invariant and enforcement type. Do not build an AST analyzer
or classify unrelated test functions in the 5,555-line file. A child task must
cover one assertion family only and use the complete guardrail verification
row.

### Investigation verification

Every investigation PR runs:

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
git diff --check
```

Its evidence file also names the exact AGENTS verification-matrix union and
observable regression scenarios required by any proposed child task.

---

## 6. Closed and Deferred Architecture Work

### T-ARCH-4: Frozen migration chain retained

Python Guardrails run 30770109810 separately ran PostgreSQL Alembic acceptance
and then the complete suite containing the migrate_v8/v9/v10 contracts. The
accepted ADR still supports unversioned-database adoption through
`pipeline/db_migration_runner.py`; the chain remains active.

### Deferred migration-chain sunset

Operator direction is to sunset the frozen chain in a future PR. This is not
an executable task yet. A new ADR must first define the minimum supported
database state and retire unversioned/pre-Alembic adoption. Only then may a
Full plan derive ownership and verification for deleting the chain.

### T-ARCH-9: Crawler recorded-parse parity closed

The complete suite in Python Guardrails run 30770109810 includes the
Belmont/Fremont/Moraga recorded-parse contracts in
`tests/test_crawler_refactor_contract.py`.

---

## 7. Execution

The documentation, baseline, and architecture lanes may proceed independently.

- Baseline order is strict: T-BASE-1, then T-BASE-2A, then operator captures
  and T-BASE-2B.
- Architecture investigations may run in parallel because they write separate
  evidence files. Tracker updates merge sequentially after rebasing.
- No architecture implementation begins until its investigation evidence and
  separately numbered child task are approved.
- The deferred migration sunset remains blocked on its ADR/support-floor
  decision.

## 8. Plan Verification

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_env_example_profile_alignment.py
git diff --check
```

## 9. Out of Scope

- Runtime defaults, model policy, thresholds, tolerances, and soak-gate changes
- City Coverage Expansion before valid v2 evidence and all ROADMAP gates
- Repository-wide facade removal or guardrail rewrites
- A permanent Markdown or AST policy analyzer
- Migration-chain deletion before the new ADR and support-floor decision
