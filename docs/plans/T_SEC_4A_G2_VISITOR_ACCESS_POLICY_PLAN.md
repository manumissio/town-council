# T-SEC-4A: Record the Approved G2 Visitor-Access Policy

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: implementation-ready`
`execution: docs-and-policy-tests`

## 1. Context & Alignment

**a) Driver.** The operator approved account-free visitor access through the
public Next.js proxy to summarize, segment, extract, and topic-generation
actions, with per-client rate limits as the abuse control. Direct API requests
to the protected AI mutation endpoints still require the deployment API key;
public read and task-status routes remain public. The repository must record
that decision consistently without implying that T-SEC-4 has already delivered
trustworthy client identity or separate rate buckets.

**b) Canonical documents consulted.**

- `AGENTS.md` `<hierarchy_of_truth>`, `<workflow_contract>`, and
  `<status_reporting_contract>` require canonical policy alignment, tests-first
  delivery, and explicit old/new values, rationale, and remaining deficits.
- `SECURITY.md` is canonical for the frontend-to-API trust boundary and
  deliberate accepted risks.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` owns G2 status, T-SEC-4
  sequencing, and task ownership.
- `docs/TESTING.MD` permits tracked-filesystem policy tests without a
  production test seam.
- `docs/reviews/architecture-review-2026-07-19.html` routes proxy identity and
  limiting through T-SEC-4 without requiring operator authentication.

**c) Remediation alignment.** Add T-SEC-4A to the SEC lane with exactly these
owned files:

- `docs/plans/T_SEC_4A_G2_VISITOR_ACCESS_POLICY_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `SECURITY.md`
- `tests/test_repository_guardrails.py`

T-SEC-4 retains exclusive ownership of its runtime implementation files.

**d) Decision-gate check.** G2 was approved by the operator on 2026-07-24:
AI task endpoints remain available to any visitor with per-client rate limits;
operator-only authentication is not approved. No further operator decision is
required. G1, G3, G4, and G5 are unaffected.

## 2. Design

**e) Step-by-step approach.**

1. Branch from `master` after the T-SEC-5 closure merges.
2. Add this plan and register T-SEC-4A ownership before policy or test edits.
3. Add two failing policy-alignment tests and record the red result.
4. Record G2 as approved in the remediation ledger, including its rationale.
5. Update the `SECURITY.md` frontend-to-API boundary:
   - AI task endpoints remain visitor-accessible through the public proxy.
   - Direct calls to protected AI mutation endpoints still require the
     deployment API key; public read and task-status routes remain public.
   - The frontend API key authenticates the deployment, not proxy visitors.
   - Per-client limiting is the approved abuse control.
   - Operator-only proxy authentication is not approved.
6. Add an accepted-risk entry for the period before T-SEC-4 merges, with a
   review checkpoint at T-SEC-4 merge or 2026-08-31, whichever comes first.
7. Replace stale "pending G2" text with the selected policy.
8. Keep T-SEC-4 pending and explicitly dependent on G2.
9. Run all required verification and obtain a fresh subagent pre-commit review.
10. Commit the policy/test change separately from this authorization commit,
    push, open one PR, resolve review findings, and wait for decided CI.

No production function, helper, parser, registry, authentication layer, or
runtime abstraction is added.

**f) Reuse audit.** Extend the existing G2 gate, T-SEC-4 task, `SECURITY.md`
trust-boundary and accepted-risk sections, and tracked-filesystem guardrail
tests. Add no ADR, policy registry, Markdown parser, compatibility path, or
duplicate security-policy source.

**g) Contracts.**

- Old policy: G2 is open and visitor access is only a default assumption.
- New policy: AI task endpoints remain visitor-accessible through the public
  Next.js proxy; direct calls to protected AI mutation endpoints still require
  the deployment API key; public read and task-status routes remain public;
  per-client limiting is the selected abuse control; operator-only proxy
  authentication is not approved.
- Remaining deficit: T-SEC-4 has not yet delivered trusted client identity or
  independent rate buckets.

No application API, schema, Celery signature, environment variable, runtime
default, or soak policy changes.

**h) Schema/migration impact.** None.

## 3. Security & Data Governance

**i) Trust-boundary impact.** This task records, but does not change, the
Internet-to-Frontend-to-API boundary. It grants an attacker no new runtime
capability. It documents the existing risk that unauthenticated proxy callers
can consume shared inference capacity until T-SEC-4 lands. Direct calls to
protected AI mutation endpoints remain API-key protected. `SECURITY.md` remains
the canonical control and risk record.

**j) Secrets.** No credential, key, environment variable, or default changes.

**k) Person data.** No person-level data is created, linked, aggregated, or
exposed. G4 is unaffected.

**l) Untrusted input.** No runtime input is parsed. Tests read tracked Markdown
through the approved filesystem boundary.

## 4. Code Health

**m) GED conformance sweep.** No production logic, timestamp, environment read,
error handler, dependency, or runtime literal changes. Test names use security
and remediation domain vocabulary. Each test checks one policy contract.

**n) Antipattern scan, plan pass.**

- A1/H1: no dependency API or configuration call is introduced.
- B1/F1: reuse tracked Markdown and existing guardrail tests; add no parser or
  policy framework.
- D1-D3: add positive and negative policy markers without weakening, skipping,
  or mocking tests. Exact markers are the observable governance contract.
- E1-E3: edit only the four owned files and remove only stale G2 claims.
- A2-A4, B2-B3, C1-C2, F2, H2-H4: no planned violations.

**o) Ratchet interaction.** Ruff selectors, BLE001 boundaries, Mypy scope,
formatter scope, coverage threshold, and workflow behavior remain unchanged.

**p) Dead code and duplication audit.** Remove stale "G2 open" and "pending
G2" claims. Keep detailed rationale and accepted risk in `SECURITY.md`; keep
only gate status, short rationale, dependency, and progress in the remediation
ledger. Expected runtime-code delta is zero.

## 5. Testing

**q) Edge cases and failure scenarios.**

1. `SECURITY.md` says G2 is approved while the ledger says open.
2. Either document describes operator-only authentication as approved or
   pending.
3. Visitor access is documented without per-client rate limits.
4. Documentation implies protected AI mutation endpoints no longer require the
   deployment API key, public read/status routes require it, or T-SEC-4 is
   already implemented.
5. The accepted risk lacks both the T-SEC-4 merge event and the 2026-08-31
   review deadline.
6. T-SEC-5 is incorrectly described as visitor authentication.
7. Future edits remove the policy rationale or T-SEC-4 dependency.

**r) Tests added.**

- `test_g2_visitor_access_policy_is_aligned_between_security_and_remediation_ledger`
  covers scenarios 1, 2, 3, and 7.
- `test_g2_accepted_risk_is_bounded_without_overclaiming_t_sec_4` covers
  scenarios 4, 5, and 6 and requires both review checkpoints.
- Existing repository guardrail and docs-link suites cover policy-file
  readability and reference integrity.

No edge case is deferred and no test is orphaned.

**s) Fakes and mocks.** None. Tests use only the tracked-filesystem boundary
approved by `docs/TESTING.MD`.

**t) Verification rows.** Apply the guardrail/tooling and docs-only rows. Run
the complete Python suite because the change adds cross-cutting policy
enforcement tests.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-sec-4a-g2-policy-record
```

Tests-first red evidence:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_repository_guardrails.py::test_g2_visitor_access_policy_is_aligned_between_security_and_remediation_ledger \
  tests/test_repository_guardrails.py::test_g2_accepted_risk_is_bounded_without_overclaiming_t_sec_4
```

Expected: both fail against the G2-open policy.

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

1. `docs(remediation): authorize the G2 policy record`
2. `docs(security): record visitor access for AI actions`

**v) Rollback.** Revert the T-SEC-4A merge commit and rerun the same checks.
The operator approval remains valid, but T-SEC-4 pauses until a corrected
durable policy record lands. No migration, data repair, configuration restore,
or external-state cleanup is required.

**w) Docs synchronization.**

- `SECURITY.md`: trust-boundary rationale and accepted risk.
- Remediation ledger: G2 approval, rationale, T-SEC-4A task, T-SEC-4
  dependency, status table, changelog, and out-of-scope wording.
- This Full Template plan.
- `AGENTS.md`, ADR, architecture review, README, operations, testing policy,
  and data-governance docs: no changes.

## 7. Delivery Self-Audit

**x) Antipattern scan, diff pass.** Re-run A-F and H. Reject runtime changes,
operator-auth implementation, T-SEC-4 implementation, G3 content, an ADR,
duplicated policy paragraphs, weakened tests, or files outside the four-file
ownership set.

**y) Evidence.** Report the tests-first failures and every command from 6u with
`PASS` or `FAIL`, exact test counts, subagent planning and pre-commit review
findings, commit hashes, PR URL, unresolved-thread count, and final CI state.
Mark anything unrun as `NOT VERIFIED`.

**z) Deviations.** Expected: none. The superseded
`codex/t-sec-5-closure` branch is wording reference only and must not enter this
branch's history.
