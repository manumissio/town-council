# T-GOV-2: Record Roster-Gated Person Minimization

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: implementation-ready`
`execution: docs-and-tests`

## 1. Context & Alignment

**a) Driver.** The operator approved G4 Option A, but the canonical governance
documents still describe G4 as open. Town Council currently persists and
exposes mention-only people, so this task must record the selected
roster-gated policy without falsely claiming runtime compliance. A separate
T-GOV-2A implementation task will own roster authority, runtime enforcement,
derived-data remediation, and reindexing before City Coverage Expansion may
resume.

**b) Canonical documents consulted.**

- `AGENTS.md` `<hierarchy_of_truth>`, `<workflow_contract>`,
  `<verification_matrix>`, and `<docs_sync_rules>` require current policy,
  exact evidence, docs-link verification, and no duplicated configuration
  inventories.
- `docs/DATA_GOVERNANCE.md` Sections 1-5 define data classes, minimization,
  source-record preservation, correction, and retention. Section 3 is the open
  G4 decision this task replaces.
- `docs/ADR.md` supplies the established Accepted-decision format.
- `docs/TESTING.MD` permits direct filesystem contracts without a production
  test seam.
- `SECURITY.md` confirms this task changes no authentication, credential, or
  network boundary.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` makes T-GOV-2 the G4 decision
  task and requires a separate implementation follow-up.
- `docs/reviews/architecture-review-2026-07-19.html` identifies person-level
  aggregation as a governance concern rather than ordinary search behavior.

**c) Remediation alignment.** T-GOV-2 is the governance-lane decision task.
Its exact `files_owned` set is:

- `docs/plans/T_GOV_2_PERSON_MINIMIZATION_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `docs/ADR.md`
- `docs/DATA_GOVERNANCE.md`
- `tests/test_repository_guardrails.py`

The remediation ledger update is limited to the changelog, task table,
T-PLAT-2 completion, G4, T-GOV-2, new T-GOV-2A registration, T-GOV-6's
superseded sequencing note, and execution order. No runtime or schema file may
change.

**d) Decision-gate check.** G4 is already approved as Option A:
roster-gated person linking. This task records that decision and does not
reopen it. G1, G2, G3, and G5 are unaffected. City Coverage Expansion remains
blocked until T-GOV-2A is complete.

## 2. Design

**e) Step-by-step approach.**

1. Register this Full plan, exact ownership, acceptance criteria, and
   sequencing in the remediation ledger.
2. Add failing repository contract tests before changing the ADR or governance
   policy.
3. Add an Accepted ADR entry dated 2026-07-26 that:
   - selects roster-gated person linking;
   - defines a roster as independently authoritative official membership data;
   - rejects inferred titles and linker-created memberships as roster proof;
   - preserves source-document text and source records;
   - records that current runtime behavior is not yet compliant; and
   - delegates runtime enforcement and remediation to T-GOV-2A.
4. Replace `docs/DATA_GOVERNANCE.md` Section 3's option list and working
   default with the adopted policy:
   - covered officials may receive person entities, profiles, memberships, and
     vote attribution only after authoritative roster matching;
   - non-roster names remain searchable source text but do not become person
     entities, people metadata, profiles, or cross-document aggregation;
   - outside enrichment of private individuals remains forbidden; and
   - correction changes derived records and indexes, never source documents.
5. Update the ledger so G4 and T-GOV-2 are complete and T-GOV-2A is pending.
   T-GOV-2A must own authoritative roster input, selection rules, runtime
   gating, existing derived-data remediation, reindexing, and prevention of
   re-derivation.
6. Run the docs and guardrail gates, simplify the diff, and obtain a fresh
   subagent pre-commit review.
7. Commit the planning authorization separately from the policy and contract
   implementation, push one branch, open one PR, request remote review, and
   wait for required CI.

No production function or module is added.

**f) Reuse audit.** Reuse the existing ADR format, Data Governance sections,
remediation task-state table, Markdown section helper, and cross-document
policy-contract pattern in `tests/test_repository_guardrails.py`. Do not add a
Markdown parser, policy registry, runtime compatibility path, or duplicate
governance document.

**g) Data contracts.** This task changes policy contracts only. The policy
distinguishes independently authoritative roster records from title inference,
linker output, source-document mentions, and derived person records. No API
payload, database model, Celery signature, CLI, environment variable, or
runtime default changes.

**h) Schema/migration impact.** None. T-GOV-2A must separately plan any
schema or data-remediation work after inspecting authoritative roster inputs
and existing derived records.

## 3. Security & Data Governance

**i) Security-sensitive paths.** None. No authentication, proxy, container,
credential, CORS, or backing-store path changes.

**j) Secrets.** None.

**k) Person data.** This task directly governs person-level data and therefore
uses the Full template. The accepted policy minimizes aggregation: non-roster
people remain only in municipal source text and cannot be promoted into
persistent person entities or people-facing derived products. The policy does
not delete or rewrite public source records.

**l) Untrusted input.** No scraped or user input is parsed by new code.
Repository tests read checked-in Markdown through the existing filesystem
boundary.

## 4. Code Health

**m) GED conformance sweep.** The implementation is docs and one focused
contract test. No runtime functions, nesting, timestamps, environment reads,
exception handlers, or dependency calls change. Policy terms use Town Council
domain vocabulary: source document, official roster, person entity,
membership, derived record, and reindexing.

**n) Antipattern scan, plan pass.**

- A1/H1: no external API or library call is introduced.
- A2-A4: no setting, silent default, placeholder, or unsupported completion
  claim.
- B1-B3/F1-F2: no parser framework, registry, wrapper, compatibility path, or
  duplicate policy implementation.
- C1: active open/options wording is replaced, not retained as a second live
  policy.
- C2/D2: no test seam, facade patch, call-count assertion, or mocked unit under
  test.
- D1: no skip, xfail, weakened assertion, or widened tolerance.
- D3: exact decision and task states are observable governance contracts;
  tests avoid full-document snapshots.
- E1-E3: edits remain within the five owned files and do not rewrite
  historical ADR entries.
- H2-H4: no type suppression, alternate trust-boundary model, or import-time
  behavior.

Independent planning review found two required corrections incorporated here:
the roster must be independently authoritative rather than created by the
linker, and the policy task must state that runtime enforcement remains
pending.

**o) Ratchet interaction.** Ruff selectors, BLE001 boundaries, formatter
scope, typed scope, coverage, and CI gates remain unchanged.

**p) Dead code and duplication audit.** Delete the active G4 option list,
working-default prose, and stale ledger wording. Add one ADR entry, one adopted
policy section, one implementation follow-up registration, and focused
contracts. Expected production-code delta is zero.

## 5. Testing

**q) Edge cases and failure scenarios.**

1. A canonical document still calls G4 open, pending, unresolved, or a working
   default.
2. Option B, Option C, or status quo remains presented as a live choice.
3. Historical descriptions are incorrectly treated as active policy.
4. A title inferred from source text or a linker-created membership is treated
   as authoritative roster evidence.
5. Policy claims current runtime already enforces roster gating.
6. Non-roster names are allowed into person entities, metadata, profiles, or
   cross-document aggregation.
7. Correction language permits editing municipal source records.
8. T-GOV-2 is complete without a pending runtime follow-up.
9. City Coverage Expansion is unblocked before T-GOV-2A completes.
10. ADR, governance policy, and remediation ledger disagree.

**r) Tests.**

| Test | Scenarios |
|---|---|
| G4 contradiction detector positive and negative fixtures | 1-3 |
| Cross-document roster-gated policy contract | 4-7, 10 |
| T-GOV-2/T-GOV-2A ledger contract | 5, 8, 9, 10 |
| Existing repository guardrail suite | 1-10 |
| Docs-link test | Canonical references |
| Complete Python suite | Regression coverage |

Tests are written and run red before policy edits. Historical ADR text is
outside the live-policy scan so accepted decisions remain append-only.

**s) Fakes and mocks.** None. Tests use the approved filesystem boundary and
existing Markdown section helper. No production symbol is patched.

**t) Verification rows.** Apply the docs-only and guardrail/tooling rows, then
run the complete Python suite because the policy contract is cross-document.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git worktree add -b codex/t-gov-2-person-minimization \
  <TEMP_WORKTREE> origin/master
```

Tests-first red evidence:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_repository_guardrails.py::test_g4_contradiction_detection_covers_equivalent_wording \
  tests/test_repository_guardrails.py::test_g4_roster_gated_policy_is_aligned
```

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

1. `docs(remediation): authorize T-GOV-2 person minimization`
2. `docs(governance): adopt roster-gated person linking`

Push `codex/t-gov-2-person-minimization`, open one PR titled
`T-GOV-2: Adopt roster-gated person linking`, request Codex review, and wait
for all required checks.

**v) Rollback.** Revert the T-GOV-2 merge commit, rerun repository guardrails,
docs links, and the complete Python suite. No migration, data restoration, or
external-state cleanup applies. Rollback knowingly returns G4 to an unresolved
policy and keeps City Coverage Expansion blocked.

**w) Docs synchronization.**

- `docs/ADR.md`: add the Accepted G4 decision.
- `docs/DATA_GOVERNANCE.md`: activate the document and replace Section 3's
  open options with the adopted policy.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`: version, changelog, task
  states, T-PLAT-2 completion, G4, T-GOV-2, T-GOV-2A, T-GOV-6 sequencing,
  and execution order.
- New T-GOV-2 Full plan.
- README, architecture, operations, performance, engineering guardrails,
  testing policy, security policy, API contracts, and roadmap: no changes.

## 7. Delivery Self-Audit

**x) Antipattern scan, diff pass.** Re-run A-F/H. Reject a runtime-compliance
claim, circular roster authority, a second live option list, policy parser
machinery, implementation edits, historical ADR rewrites, unrelated
formatting, or files outside ownership.

**y) Evidence.** Report the tests-first red result, Ruff, Mypy, repository
guardrails, docs links, complete-suite counts, planning-review findings,
pre-commit-review findings, commit hashes, PR URL, unresolved-thread count,
and final CI state. Mark unrun evidence `NOT VERIFIED`.

**z) Deviations.** The authorized scope expansion from the ledger's original
single ADR file to the five-file set above is required to keep the canonical
policy, task states, implementation follow-up, and durable contract aligned.
Any runtime file, schema change, new dependency, new governance document,
skipped review, unresolved P1/P2, or unrun required check is a blocker.
