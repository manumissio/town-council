# T-CI-1A: Require Python Guardrails Before Default-Branch Updates

artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
execution: code
task: T-CI-1A
lane: CI
implementation_status: complete
external_state_status: active
external_ruleset_id: 19594795
activated: 2026-07-22

## 1. Context & Alignment

**a) Driver.** Before T-CI-1A, T-CI-1 ran the complete Python suite on every
pull request and master push, but GitHub had no branch protection or repository
ruleset. PR #111 remained mergeable while its first `python-guardrails` run was
red and was later merged by an owner. Ruleset 19594795 now closes that gap by
making the check mandatory.

**b) Canonical documents.** `AGENTS.md` defines the complete Python suite as
the authoritative merge gate and requires exact evidence for policy changes.
`docs/ENGINEERING_GUARDRAILS.md` names the complete suite as the Python gate.
`docs/TESTING.MD` preserves fast-fail diagnostics beneath the authoritative
suite. The remediation plan orders safety-net work before Phase 2.

**c) Remediation alignment.** Register T-CI-1A in the CI lane. It owns only
this plan, `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`, and the external
repository ruleset named `Require Python Guardrails`. No workflow or runtime
file changes.

**d) Decision gates.** No G1-G5 decision applies. The operator approved the
exact active ruleset payload in 2e on 2026-07-22, including strict status
checks, no bypass actors, and the branch-creation exemption. No policy field
may be added or altered without a new decision.

## 2. Design

**e) Approach.**

1. Record the historical precondition: default branch `master`, no branch
   protection, and no repository rulesets.
2. Resolve the successful `python-guardrails` check on T-CI-1 commit
   `07d0d99cc3184769a0b89a27a653758d10e3f220` and confirm it is produced by
   GitHub Actions integration ID 15368.
3. Confirm `.github/workflows/python-guardrails.yml` is the only workflow with
   a `python-guardrails` job ID.
4. Record the exact one-time creation request:

   ```json
   {
     "name": "Require Python Guardrails",
     "target": "branch",
     "enforcement": "active",
     "bypass_actors": [],
     "conditions": {
       "ref_name": {
         "include": ["~DEFAULT_BRANCH"],
         "exclude": []
       }
     },
     "rules": [
       {
         "type": "required_status_checks",
         "parameters": {
           "required_status_checks": [
             {
               "context": "python-guardrails",
               "integration_id": 15368
             }
           ],
           "strict_required_status_checks_policy": true,
           "do_not_enforce_on_create": true
         }
       }
     ]
   }
   ```

5. On 2026-07-22, post the request once to
   `POST /repos/manumissio/town-council/rulesets`, creating ruleset 19594795
   with:
   - target `branch`;
   - default-branch condition `~DEFAULT_BRANCH`;
   - no bypass actors;
   - one `required_status_checks` rule;
   - context `python-guardrails`, integration ID 15368;
   - strict latest-default-branch policy enabled;
   - branch-creation exemption enabled.
   This creation operation is complete and must not be rerun.
6. Read ruleset 19594795 back and compare every policy field with the
   request contract.
7. Read effective rules for `master` and prove this ruleset supplies the only
   required-status-check rule.
8. Confirm no second ruleset or legacy branch-protection policy was created.
9. Keep `python-guardrails` as the sole required check until T-CI-2 runs a
   stable `frontend-tests` context on every pull request. T-CI-2A then requires
   a separate operator-approved update to this ruleset; this task does not
   pre-authorize that future gate change.

No new function or module is added. The GitHub REST API remains the sole owner
of external repository policy.

**f) Reuse audit.** Reuse the existing GitHub Actions check identity and the
repository ruleset API. Do not add a workflow, script, policy registry, or
duplicate check.

**g) Data contracts.** The only contract is the recorded JSON request accepted
by GitHub's ruleset endpoint. It documents live repository policy, not an
application payload or a repeatable creation command.

**h) Schema and migrations.** None.

## 3. Security & Data Governance

**i) Security boundary.** This changes repository write policy, not an
application trust boundary. An update to the default branch loses the ability
to proceed without the named GitHub Actions check passing on current code.

**j) Secrets.** No new token or credential. `gh` uses the operator's existing
authenticated session; request and response output contain no secret.

**k) Person data.** None.

**l) Untrusted input.** GitHub API responses are external input. Verification
uses `jq` to select and compare named fields; no response text is executed.

## 4. Code Health

**m) Conformance.** No Python, error handler, timestamp, environment default,
or runtime logic changes. The temporary JSON uses named policy fields and an
exact check identity.

**n) Antipattern scan, plan pass.** A1/H1 are resolved through GitHub REST API
documentation and live check metadata. No new setting has a silent default.
No wrapper, compatibility path, duplicate workflow, weakened test, ignored
failure, broad edit, or import-time work is introduced. The ruleset is one
source of enforcement rather than a second implementation of CI.

**o) Ratchets.** Old value: zero default-branch protection rules and zero
required checks. New value: one active default-branch ruleset requiring only
`python-guardrails`. Remaining deficit: `frontend-tests` cannot become required
until T-CI-2 emits that context on every pull request and T-CI-2A receives
separate operator approval. Ruff, Mypy, coverage, formatter, and runtime policy
remain unchanged.

**p) Dead code and duplication.** None. No existing protection policy is
superseded because none exists. Expected tracked line delta is documentation
only.

## 5. Testing

**q) Failure scenarios.**

1. Wrong ref target could protect an unrelated branch.
2. Wrong context or integration could leave the intended check optional.
3. A bypass actor could let owners merge red code.
4. Non-strict policy could test against stale default-branch code.
5. Extra rules could introduce unapproved review or commit requirements.
6. Duplicate rulesets could make rollback ambiguous.
7. API authorization failure must leave repository policy unchanged.

**r) Verification mapping.** Ruleset readback assertions cover scenarios 1-5.
Effective-rule readback covers scenarios 1, 2, 5, and 6. Capture the POST
status and list rulesets after any failure for scenario 7. Static workflow
search proves one check producer. Docs-link tests cover both tracked files.

**s) Fakes and mocks.** None. GitHub's authenticated REST API is the actual
operator boundary.

**t) Verification rows.** Apply the docs-only row. External acceptance requires
the live ruleset readback; local tests cannot prove repository enforcement.

## 6. Execution, Rollback, Docs

**u) Commands.**

```bash
gh api -H "X-GitHub-Api-Version: 2026-03-10" \
  repos/manumissio/town-council/commits/07d0d99cc3184769a0b89a27a653758d10e3f220/check-runs \
  --jq '.check_runs[] | select(.name=="python-guardrails") | {name, app_id:.app.id}'
test "$(rg -l '^  python-guardrails:' .github/workflows/*.yml | wc -l | tr -d ' ')" = "1"

gh api -H "X-GitHub-Api-Version: 2026-03-10" \
  repos/manumissio/town-council/rulesets/19594795 \
  > /tmp/t-ci-1-required-check-readback.json
jq -e '
  .id == 19594795 and
  .name == "Require Python Guardrails" and
  .target == "branch" and
  .enforcement == "active" and
  .bypass_actors == [] and
  .conditions.ref_name.include == ["~DEFAULT_BRANCH"] and
  .conditions.ref_name.exclude == [] and
  (.rules | length) == 1 and
  .rules[0].type == "required_status_checks" and
  .rules[0].parameters.required_status_checks ==
    [{"context":"python-guardrails","integration_id":15368}] and
  .rules[0].parameters.strict_required_status_checks_policy == true and
  .rules[0].parameters.do_not_enforce_on_create == true
' /tmp/t-ci-1-required-check-readback.json

gh api -H "X-GitHub-Api-Version: 2026-03-10" \
  repos/manumissio/town-council/rules/branches/master \
  > /tmp/t-ci-1-effective-master-rules.json
jq -e --argjson ruleset_id 19594795 '
  ([.[] | select(.type == "required_status_checks")] | length) == 1 and
  any(.[];
    .ruleset_id == $ruleset_id and
    .type == "required_status_checks" and
    .parameters.strict_required_status_checks_policy == true and
    .parameters.do_not_enforce_on_create == true and
    .parameters.required_status_checks ==
      [{"context":"python-guardrails","integration_id":15368}]
  )
' /tmp/t-ci-1-effective-master-rules.json
test "$(gh api -H 'X-GitHub-Api-Version: 2026-03-10' \
  repos/manumissio/town-council/rulesets --jq 'length')" = "1"
! gh api -H "X-GitHub-Api-Version: 2026-03-10" \
  repos/manumissio/town-council/branches/master/protection
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
git diff --check
```

The POST that created ruleset 19594795 is historical and non-repeatable.

**v) Rollback.**

This creation-time rollback applies only while ruleset 19594795 still has the
Python-only contract verified by this plan. After T-CI-2A adds
`frontend-tests`, its plan owns this section and must replace deletion with a
PATCH that restores the exact Python-only contract below. Deleting the ruleset
after T-CI-2A would also remove the established Python merge gate.

```bash
gh api -H "X-GitHub-Api-Version: 2026-03-10" --method DELETE \
  repos/manumissio/town-council/rulesets/19594795
! gh api -H "X-GitHub-Api-Version: 2026-03-10" \
  repos/manumissio/town-council/rulesets/19594795
gh api -H "X-GitHub-Api-Version: 2026-03-10" \
  repos/manumissio/town-council/rulesets \
  | jq -e --argjson ruleset_id 19594795 'all(.[]; .id != $ruleset_id)'
T_CI_1A_DOCS_COMMIT=$(git log --diff-filter=A -1 --format=%H -- \
  docs/plans/T_CI_1_REQUIRED_CHECK_POLICY_PLAN.md)
test -n "$T_CI_1A_DOCS_COMMIT"
git revert "$T_CI_1A_DOCS_COMMIT"
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
git diff --check
```

Rollback is complete only when the named ruleset is absent and the committed
documents no longer declare it active. No code, migration, data, package, or
runtime rollback exists.

**w) Docs synchronization.** Update this implementation plan and remediation
registry only. Existing guardrail policy text becomes accurate when the live
ruleset is active; do not duplicate the ruleset JSON into other docs.

## 7. Delivery Self-Audit

**x) Diff scan.** Reject any workflow edit, extra rule, bypass actor, extra
required check before T-CI-2A, external policy outside the default branch, or
tracked file outside the two-file ownership set.

**y) Evidence.** Ruleset 19594795 is active and exact REST readback confirms
the approved target, enforcement, conditions, bypass list, sole required
check, strict policy, and branch-creation exemption. Effective rules on
`master` contain that sole rule; legacy branch protection remains absent.
Report docs-link result, diff check, and rollback command. Mark GitHub UI
behavior not directly exercised as `NOT VERIFIED` rather than inferring it.

**z) Deviations.** Expected result is none. Any API field change, additional
ruleset, bypass, unverified readback, or tracked path outside ownership blocks
completion.
