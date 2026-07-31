# Architecture Remediation Reconciliation Plan

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: implementation-ready`
`execution: docs`

## 1. Context & Alignment

**a) Driver.** The original architecture review identified compatibility
facades and duplicated lifecycle code that were intentionally deferred until
the test runner, testing-policy ADR, and prerequisite remediation tasks landed.
The testing and facade-policy prerequisites are now complete; roster-gated
runtime enforcement remains pending. The active remediation ledger must
register the remaining deletion work, correct two stale completion markers,
record the merged T-PLAT-4 result, and record the operator-approved roster
authority before implementation continues.

**b) Canonical documents consulted.**

- `AGENTS.md`: code and tests are behavioral truth; known antipatterns must be
  deleted through narrow, owned tasks rather than preserved as compatibility
  seams.
- `docs/TESTING.MD`: tests patch implementation owners or fake approved
  boundaries; historical patch targets are not public API.
- `docs/ENGINEERING_GUARDRAILS.md`: Ruff and structural guardrails remain
  configuration-owned and may only be changed by an implementing task.
- `docs/ADR.md`: the accepted test-patch-point decision permits the planned
  facade deletions.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`: one task owns one concern,
  implementation requires exact `files_owned`, and shared files serialize.
- `docs/reviews/architecture-review-2026-07-19.html`: candidates 3, 4, and 8,
  plus the deferred compatibility watchlist, identify the remaining provider,
  search, task, semantic, indexing, and frontend seams.
- `SECURITY.md` and `docs/DATA_GOVERNANCE.md`: API trust boundaries and the
  approved roster-gated person policy must remain intact.

**c) Remediation alignment.** This operator-approved reconciliation changes
only:

- `docs/plans/ARCHITECTURE_REMEDIATION_RECONCILIATION_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`

It registers T-DE-2, T-DC-2A, T-DC-2B, T-TASK-1, T-SEM-1, T-IDX-1, and
T-FE-1 without authorizing implementation. Each registered task must create a
separate Full plan and exact `files_owned` list before editing code. Those
planning updates serialize through the shared ledger; implementation may run
in parallel only after approved ownership is proven disjoint.

**d) Decision gates.** G1-G5 are resolved. The operator approved Legistar
OfficeRecords as authoritative roster evidence for G4 implementation and
approved fail-closed behavior where no roster source is available. T-IDX-1
depends on T-GOV-2A because roster-gated data must become authoritative before
obsolete people projections can be deleted. T-IDX-1 remains blocked until
T-GOV-2A is complete and verified.

## 2. Design

**e) Step-by-step approach.**

1. Record T-PLAT-4 as complete after PR #207.
2. Correct T-TIME-1 and T-TIME-2 from “implementation in progress” to
   “complete and verified 2026-07-26 (PR #148).”
3. Record the T-GOV-2A roster-source decision: Legistar OfficeRecords is
   authoritative; cities without an approved source retain source documents
   while people-facing derived data remains disabled.
4. Register seven pending deletion tasks with one responsibility each:
   - T-DE-2 deletes the provider compatibility facade after repointing callers
     to the existing contract and adapters.
   - T-DC-2A deletes search-to-`api.main` patch lookup.
   - T-DC-2B deletes router facade bags after T-DC-2A.
   - T-TASK-1 deletes task helper globals bags and callable injection while
     preserving Celery task identities.
   - T-SEM-1 deletes reverse semantic-index facade lookups.
   - T-IDX-1 deletes obsolete people projection compatibility after
     T-GOV-2A.
   - T-FE-1 characterizes ResultCard task lifecycles and deletes only behavior
     proven identical by tests.
5. Update task status, execution order, and out-of-scope wording so the ledger
   names the remaining work without implying implementation has begun.
6. Run docs verification and an independent pre-commit review.

No new runtime function or module is created by this reconciliation.

**f) Reuse audit.** The plan extends the existing Phase 2 task ledger and uses
the architecture review’s deletion candidates. It does not create a second
roadmap, compatibility registry, or duplicate architecture inventory.

**g) Data contracts.** None. Future tasks must preserve their current public
contracts unless their own Full plans explicitly authorize a contract change.

**h) Schema and migrations.** None. T-GOV-2A may require an Alembic revision,
but this reconciliation neither specifies nor implements it.

## 3. Security & Data Governance

**i) Security boundary.** No security-sensitive path changes. Future API
facade tasks must preserve authentication, rate limiting, proxy, and search-key
boundaries.

**j) Secrets.** None.

**k) Person data.** No person data changes here. T-IDX-1 is sequenced after
T-GOV-2A so it cannot bypass the approved roster-gated policy.

**l) Untrusted input.** No scraped content, provider response, HTTP request, or
user input is parsed or rendered.

## 4. Code Health

**m) Conformance.** This is a docs-only change. It adds no functions,
exceptions, timestamps, environment reads, or runtime literals.

**n) Antipattern scan, plan pass.**

- A1-A4: no external API or unverified command is introduced.
- B1-B3: no wrapper, manager, registry, compatibility path, retry, or
  speculative validation is added.
- C1-C2: future tasks explicitly delete superseded seams and repoint tests.
- D1-D3: no assertion, skip, tolerance, or test seam changes here.
- E1-E3: only the two owned planning files change.
- F1-F2: the existing ledger remains the single remediation source.
- H1-H4: no dependency API, type suppression, alternate contract, or
  import-time behavior changes.

**o) Ratchet interaction.** None. Future implementation tasks may remove stale
Ruff or structural-guardrail entries but may not widen them.

**p) Dead code and duplication audit.** No code is deleted in this
reconciliation. Each new task names a deletion target and forbids preserving
the old implementation through an alias or re-export.

## 5. Testing

**q) Edge and failure scenarios.**

1. A registered task overstates implementation as complete.
2. A task begins without exact ownership.
3. Search route cleanup runs before search-to-main lookup is removed.
4. People index cleanup runs before roster-gated enforcement.
5. Celery task names or signatures drift during helper deletion.
6. Frontend task behavior changes during duplication removal.
7. Stale T-TIME or T-PLAT status contradicts merged repository history.
8. The ledger still lists registered work as globally out of scope.
9. A city without an approved roster source exposes people-derived data.

**r) Tests.**

| Verification | Scenarios |
|---|---|
| Docs-link suite | 1, 2, 7, 8 |
| Direct ledger inspection and independent review | 1-9 |
| Future task-specific tests | 3-6, 9 |

No future runtime test is added prematurely in this docs-only PR.

**s) Fakes and mocks.** None.

**t) Verification rows.** The docs-only row applies. Because the remediation
ledger controls cross-cutting execution, run the complete Python suite before
delivery.

## 6. Execution, Rollback, Docs

**u) Commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/architecture-remediation-reconciliation

PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/pytest -q
git diff --check
git status --short
```

After a fresh subagent review:

```bash
git add \
  docs/plans/ARCHITECTURE_REMEDIATION_RECONCILIATION_PLAN.md \
  docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md
git commit -m "docs(remediation): register remaining architecture deletions"
git push -u origin codex/architecture-remediation-reconciliation
gh pr create \
  --base master \
  --head codex/architecture-remediation-reconciliation \
  --title "Register the remaining architecture deletion tasks"
```

**v) Rollback.** Revert the docs commit and rerun docs links and the complete
suite. No migration, runtime configuration, external state, or data repair is
involved.

**w) Docs synchronization.** Update only the remediation ledger and this plan.
The historical architecture review remains unchanged. No README, ADR,
operations, security, data-governance, API, or runtime documentation changes
are required.

## 7. Delivery Self-Audit

**x) Diff scan.** Re-run A-F and H. Reject implementation edits, invented
ownership, compatibility preservation, duplicated inventories, unrelated
formatting, or claims that pending tasks are complete.

**y) Evidence.** Report docs-link and complete-suite outcomes, review findings,
commit hash, PR URL, and CI state. Mark any unrun check `NOT VERIFIED`.

**z) Deviations.** Expected result is none. Any changed path beyond the two
owned planning files, implementation begun without a task-specific Full plan,
or changed G1-G5 decision is a blocker.
