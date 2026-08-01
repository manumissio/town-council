# T-SEM-1A: Approve the Semantic Test Boundary

## 1. Context & Alignment

**a) Driver.** T-SEM-1 must delete the semantic facade and repoint service
tests without preserving facade patch points. Those tests need to substitute a
semantic backend or optional model runtime, but `docs/TESTING.MD` does not yet
list that architectural boundary. Its policy requires boundary additions to
land in a separate PR, so T-SEM-1A records the narrow boundary first.

**b) Canonical documents consulted.**

- `AGENTS.md` requires implementation-module patching, separate policy and
  implementation changes, docs verification, and exact evidence.
- `docs/TESTING.MD` requires an independent policy update before adding a fake
  boundary.
- `docs/ENGINEERING_GUARDRAILS.md` keeps test policy and static enforcement
  separate.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` makes G3 effective and defines
  T-SEM-1 as the next facade deletion.
- `SECURITY.md` and `docs/DATA_GOVERNANCE.md` impose no additional constraint
  because this is test policy only.

**c) Remediation alignment.** T-SEM-1A owns exactly:

- `docs/plans/T_SEM_1A_SEMANTIC_TEST_BOUNDARY_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `docs/TESTING.MD`

T-SEM-1 remains pending and owns no implementation file until its corrected
Full plan lands after this prerequisite.

**d) Decision-gate check.** G3 is satisfied by T-GOV-1. This policy update is
the separate approval mechanism required by `docs/TESTING.MD`; it does not
depend on or foreclose G1, G2, G4, or G5.

## 2. Design

**e) Step-by-step approach.**

1. Register T-SEM-1A before T-SEM-1 in the remediation ledger.
2. Add one approved fake-boundary row for semantic backend/runtime behavior.
3. Permit patching `pipeline.semantic_backend_runtime.get_semantic_backend` to
   return a fake implementing the existing `SemanticBackend` contract.
4. Permit optional FAISS and SentenceTransformer substitution only after
   T-SEM-1 moves their ownership to `pipeline.semantic_backend_runtime`.
5. Explicitly prohibit patching backend private methods.
6. Keep database, filesystem, Meilisearch, HTTP, clock, and inference rows
   unchanged.
7. Verify docs links, review independently, commit, push, merge, then return to
   a corrected T-SEM-1 Full plan.

No runtime code, test seam, helper, environment variable, or dependency is
added.

**f) Reuse audit.** Reuse the existing `SemanticBackend` typed contract and
the current approved-boundary table. No second testing policy, adapter class,
fixture framework, or compatibility layer is introduced.

**g) Data contracts.** The existing `SemanticBackend` contract remains
unchanged. The policy authorizes substitution; it does not alter the contract.

**h) Schema/migration impact.** None.

## 3. Security & Data Governance

**i) Security-sensitive paths.** None. Production credentials, endpoints,
dependencies, and execution permissions are unchanged.

**j) Secrets.** None.

**k) Person data.** None.

**l) Untrusted input.** None is newly parsed or rendered.

## 4. Code Health

**m) GED conformance sweep.** This is a three-file policy-only change. It adds
no code, errors, timestamps, literals, environment reads, or runtime imports.

**n) Antipattern scan, plan pass.**

- A1/H1: `SemanticBackend` and `semantic_backend_runtime` exist in the checked
  in code; no external API assumption is introduced.
- B1-B3/F1-F2: no wrapper, registry, fixture framework, or duplicate policy.
- C1-C2: the boundary exists to let T-SEM-1 delete, not preserve, facade patch
  points.
- D1-D3: no test is skipped, weakened, or rewritten in this PR.
- E1-E3: only the three owned docs change.
- A2-A4 and H2-H4: no violation.

**o) Ratchet interaction.** No Ruff, Mypy, coverage, formatter, BLE001, or
workflow setting changes.

**p) Dead code and duplication audit.** None in this policy prerequisite.
T-SEM-1 remains responsible for deleting the facade and old patch targets.

## 5. Testing

**q) Edge cases and failure scenarios.**

1. The boundary must name the typed backend contract and runtime selection
   function, not a facade.
2. Optional runtime substitutions must remain future-effective until T-SEM-1
   establishes the named direct owner.
3. The row must not authorize patching backend private methods.
4. Existing approved boundaries must remain unchanged.
5. Links between the ledger, plan, and testing policy must resolve.

**r) Tests added or updated.** No test code changes. `tests/test_docs_links.py`
verifies scenario 5. Independent review verifies scenarios 1-4 against the
policy text and checked-in owners.

**s) Fakes and mocks.** None are used in this docs-only PR. The policy row
authorizes only the future semantic boundary described above.

**t) Verification rows.** The docs-only row applies. The optional environment
alignment test is unnecessary because no runtime profile or environment
contract changes.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
git diff --check
git status --short
```

After review, commit, push, open the T-SEM-1A PR, watch CI, merge, synchronize
`master`, and resume T-SEM-1.

**v) Rollback.** Revert the T-SEM-1A merge commit and rerun docs links. No
migration, data repair, configuration restore, or external-state cleanup is
required. T-SEM-1 would become blocked again on an unapproved fake boundary.

**w) Docs synchronization.** Update only `docs/TESTING.MD`, this plan, and the
remediation ledger. Architecture, ADR, operations, README, security, data
governance, performance, roadmap, and API contracts remain unchanged.

## 7. Delivery Self-Audit

**x) Diff scan.** Re-run A-F/H. Reject code changes, a facade patch target, a
private-method fake, a second policy list, or a path outside the three-file set.

**y) Evidence.** Report docs-link and diff-check outcomes, independent review,
commit, PR, unresolved threads, and CI state. Mark anything unrun `NOT
VERIFIED`.

**z) Deviations.** Expected result is none. Any implementation edit, expanded
boundary, skipped review, unresolved P1/P2, or unrun docs gate is a blocker.
