# T-SEC-3C: Synchronize the Meilisearch Security Checklist

`artifact_contract: ce-unified-plan/v1`  
`artifact_readiness: implementation-ready`  
`execution: docs`

## 1. Implementation

**a) Root cause and fix.** PR #123 implemented T-SEC-3 and passed its runtime,
permission, and repository gates, but the canonical `SECURITY.md` checklist
item remained unchecked. PR #124 correctly stopped declaring the task complete
until that conflict was resolved. This closure task verifies the merged
implementation evidence, checks the canonical item, and returns T-SEC-3 to
complete. It also records merged T-CRAWL-1 as complete.

Steps:

1. Register this closure task and its three-file ownership before changing the
   checklist.
2. Confirm PR #123 is merged and its required checks passed.
3. Check only the T-SEC-3 item in `SECURITY.md`.
4. Mark T-SEC-3 and T-CRAWL-1 complete in the remediation status table.
5. Run docs-link and contradiction checks, obtain current-head review, and
   merge only with green CI and no unresolved P1/P2 findings.

**b) Edge cases and failures.**

1. If PR #123 is not merged or its required checks failed, leave T-SEC-3 open.
2. If `SECURITY.md` names a different control, stop rather than checking an
   adjacent item.
3. If remediation status still says closure pending after the checklist
   changes, fail the contradiction check.
4. If another security checklist item changes, reject the diff as scope drift.

**c) Code audit.** Docs only. No function, literal, nesting, parameter,
timestamp, environment read, or runtime error behavior changes.

**d) Dead code audit.** None. The closure-pending status is replaced by the
verified completed status; no historical implementation evidence is deleted.

**e) Boundary check.** `SECURITY.md` is canonical policy documentation but not
an `AGENTS.md` security-sensitive runtime path. No trust boundary, person data,
schema, facade family, Celery dispatch, crawler setting, runtime default, gate,
or soak policy changes.

**f) Antipattern quick-scan.** Pass. No invented API, abstraction,
compatibility path, surviving superseded status, weakened test, unrelated
formatting, or duplicated implementation.

## 2. Testing & Execution

**g) Tests.** No new test is justified for a one-time checklist-state
synchronization. `tests/test_docs_links.py` verifies document references.
Targeted text checks verify scenarios 2-4 directly against the canonical files.
No fake or mock is used.

**h) Verification and docs.**

```bash
gh pr view 123 --json state,mergedAt,statusCheckRollup
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
grep -n "Meilisearch search key enforced" SECURITY.md
grep -nE "T-SEC-3|T-CRAWL-1" docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md
git diff --check
git status --short
```

The docs-only verification row applies. No README, ADR, operations, testing,
architecture, API, or data-governance update is needed.

**i) Delivery evidence.** Report each command above as PASS or FAIL, the
current-head review outcome, commit hashes, PR URL, CI state, and any deviation.
The expected deviation report is `None`.
