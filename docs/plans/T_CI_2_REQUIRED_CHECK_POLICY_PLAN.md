# T-CI-2A: Require the Universal Frontend Test Check

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: implementation-ready`
`execution: code`
`task: T-CI-2A`
`lane: CI`
`implementation_status: live policy active; merge verification pending`
`external_state_status: active`
`external_ruleset_id: 19594795`
`approved: 2026-07-23`
`activated: 2026-07-23`

## 1. Context & Alignment

**a) Driver.** T-CI-2 emits `frontend-tests` on every pull request and every
push to `master`. Before T-CI-2A activation, the default-branch ruleset required
only `python-guardrails`, so a frontend regression could remain mergeable even
when the frontend test job failed. The approved live update now requires both
checks. Final completion remains pending until this policy record merges under
both checks and the post-merge ruleset readback passes.

**b) Canonical documents consulted.**

- `AGENTS.md` `<hard_invariants>`, `<workflow_contract>`,
  `<verification_matrix>`, and `<status_reporting_contract>` require an
  operator decision for gate changes, exact evidence, and current merge-gate
  guidance.
- `docs/TESTING.MD` defines the frontend test command and complete Python suite
  as independent authoritative gates.
- `docs/ENGINEERING_GUARDRAILS.md` assigns frontend CI orchestration to
  `.github/workflows/frontend-tests.yml`.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` requires T-CI-2A after T-CI-2
  and grants ownership of the live ruleset.
- `docs/plans/T_CI_1_REQUIRED_CHECK_POLICY_PLAN.md` records every field in the
  historical Python-only contract and requires T-CI-2A to preserve its
  non-destructive rollback.
- `docs/plans/T_CI_2_FRONTEND_TESTS_PLAN.md` records the universal workflow,
  its exact job context, and the required frontend/non-frontend proof.
- `docs/reviews/architecture-review-2026-07-19.html` historically identified
  missing merge gates; current completion status comes from the remediation
  registry and live repository policy.

**c) Remediation alignment.** T-CI-2A remains in the CI lane and owns exactly:

- `docs/plans/T_CI_2_REQUIRED_CHECK_POLICY_PLAN.md`
- `docs/plans/T_CI_1_REQUIRED_CHECK_POLICY_PLAN.md`
- `docs/plans/T_CI_2_FRONTEND_TESTS_PLAN.md`, historical ruleset evidence and
  rollback section only
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `AGENTS.md`, verification-matrix CI-status paragraph and transition markers
  only
- `pipeline/requirements-dev.txt`, direct development-only YAML parser pin
- `tests/test_docker_build_contracts.py`, development-only dependency boundary
  assertion
- `tests/test_repository_guardrails.py`, canonical frontend required-check job
  identity only
- repository ruleset `Require Python Guardrails`, ID `19594795`

No workflow, runtime package, runtime behavior, or application file may change.

**d) Decision-gate check.** No G1-G5 gate applies. The operator explicitly
approved the T-CI-2A ruleset update on 2026-07-23, and the live direct and
effective readbacks match the contracts below. G3 remains open and continues
to block Phase 2.

## 2. Design

**e) Step-by-step approach.**

1. Record the current ruleset and effective `master` rules. Fail unless they
   exactly match the T-CI-1A Python-only contract.
2. Confirm PR #114 supplies the post-T-CI-2 frontend-change proof:
   `frontend-tests` completed successfully from GitHub Actions integration
   `15368`.
3. Pin PyYAML in development requirements and use
   `yaml.load(..., Loader=yaml.BaseLoader)` to prove
   `.github/workflows/frontend-tests.yml` contains the only workflow job whose
   effective check name is `frontend-tests`, as canonical job ID
   `frontend-tests` with no display-name override. The string-only loader is
   deliberately narrow: it preserves GitHub's treatment of `on`, `off`, `yes`,
   and `no` as strings while parsing only the job mappings needed by this
   contract. Regression cases must cover comments, quoted keys, folded scalars,
   command blocks, and Boolean-like job IDs and names.
4. Add this Full plan, update the remediation registry, replace T-CI-1A's
   obsolete deletion rollback with a non-destructive restoration policy, and
   replace the stale AGENTS transition annotations with accurate T-CI-2A
   pending text.
5. Run repository verification and obtain a fresh subagent pre-commit review.
   Apply every eligible P1/P2 finding and repeat affected checks.
6. Commit, push, and open a non-frontend policy PR without changing live
   policy. Wait for that PR's `frontend-tests` and `python-guardrails` contexts to
   complete successfully. Confirm `frontend-tests` also comes from integration
   `15368`. This supplies the non-frontend proof.
7. Merge the planning PR and verify that the live ruleset remains Python-only.
8. Generate the exact request and canonical observed pre-state in untracked
   temporary files. Present both complete JSON documents and SHA-256 digests
   for operator approval. The pre-state includes the ruleset `updated_at`
   value:
   - old required checks:
     `python-guardrails` from integration `15368`;
   - new required checks, in order:
     `python-guardrails` and `frontend-tests`, both from integration `15368`;
   - all other ruleset fields unchanged.
9. Stop unless the operator explicitly approves both exact JSON documents and
   digests and establishes an exclusive ruleset change window through the
   post-update readback. Any byte change or concurrent policy operation
   invalidates approval.
10. In one fail-closed shell block, verify both approved digests, repeat the
    full direct and effective Python-only preflight, prove the canonical direct
    pre-state still matches approval, prepare the exact rollback request,
    send one `PUT`, and perform complete direct and effective readback. GitHub
    does not expose a documented atomic compare-and-swap for this full ruleset
    `PUT`; the exclusive change window, immediate pre-state check, and exact
    readback reduce but do not eliminate that non-atomic interval.
11. Only after successful live readback, create a completion documentation
    branch and:
    - mark T-CI-2A `live policy active; merge verification pending`;
    - update T-CI-1A's current-state wording without erasing its historical
      decision;
    - retire T-CI-2's now-unsafe standalone rollback and require a separately
      authorized coordinated reversal of the ruleset, producer, guardrails,
      dependency contract, and policy text;
    - remove the two T-CI-2A-pending transition annotations from
      `AGENTS.md`.
12. Run documentation verification and obtain a fresh subagent pre-commit
    review. Apply every eligible P1/P2 finding and repeat affected checks.
13. Commit and push the completion policy record, open a second PR, wait for
    all checks, request review, merge, and verify the ruleset again after the
    default branch advances.
14. Obtain explicit operator acceptance of the digest-approval deviation
    recorded in 7z. Then open a final closure PR that records T-CI-2A complete
    only after that acceptance and the post-merge ruleset and
    effective-`master` readbacks pass. Merge it after both required checks
    pass, then repeat the policy readback.

No production function, module, workflow, helper script, compatibility path,
or new configuration surface is added. The guardrail test uses the direct
development-only PyYAML dependency and its string-only `BaseLoader` rather
than maintaining a partial YAML parser or mutating a shared loader resolver.

**f) Reuse audit.** Reuse the existing universal frontend workflow, its
GitHub Actions check identity, ruleset `19594795`, T-CI-1A readback
assertions, GitHub CLI authentication, `jq`, and PyYAML's `BaseLoader` for the
two string-valued workflow fields under inspection. A second ruleset, legacy
branch protection, custom loader subclass, custom resolver, policy script, or
workflow duplication is rejected because each would create another
enforcement owner.

**Dependencies.** Add `PyYAML==6.0.3` to
`pipeline/requirements-dev.txt`. It is already present locally as a transitive
dependency of pre-commit, but the workflow contract test must not depend on
that accidental relationship. It remains absent from runtime requirements.

**g) Data contracts.**

Historical pre-activation contract:

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
          {"context": "python-guardrails", "integration_id": 15368}
        ],
        "strict_required_status_checks_policy": true,
        "do_not_enforce_on_create": true
      }
    }
  ]
}
```

Activated live contract:

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
          {"context": "python-guardrails", "integration_id": 15368},
          {"context": "frontend-tests", "integration_id": 15368}
        ],
        "strict_required_status_checks_policy": true,
        "do_not_enforce_on_create": true
      }
    }
  ]
}
```

GitHub REST API documentation verifies `PUT` as the update method and requires
the ruleset name, target, and enforcement fields. The OpenAPI contract
verifies each status-check context, optional integration identity, required
strict policy, and creation-exemption parameter.

**h) Schema and migration impact.** None.

## 3. Security & Data Governance

**i) Security boundary.** This changes repository write policy, not an
application trust boundary. Default-branch updates lose the ability to proceed
unless both authoritative test contexts pass against current default-branch
code. No actor gains bypass capability; the bypass list stays empty.

**j) Secrets.** No credential or secret is added. `gh` uses the operator's
existing authenticated session. Request and readback artifacts contain policy
metadata only.

**k) Person data.** No person-level data is created, linked, aggregated, or
exposed. G4 is unaffected.

**l) Untrusted input.** GitHub API responses are external input. Verification
selects and compares named JSON fields with `jq`; no response text is executed.
Tracked workflow YAML is parsed with PyYAML's `BaseLoader`, which performs
minimal construction and preserves scalar values as strings. This avoids both
arbitrary Python object construction and YAML 1.1 Boolean coercion. It is not
treated as a complete GitHub Actions parser.

## 4. Code Health

**m) GED conformance sweep.** No Python, JavaScript, error handler, timestamp,
environment read, runtime default, soak gate, or inference policy changes.
The external mutation is fail-fast and preceded by exact drift detection.

**n) Antipattern scan, plan pass.**

- A1/H1 corrected: current GitHub REST and OpenAPI documentation verify the
  ruleset update method and required-status-check fields. PyYAML 6.0.3
  documentation verifies the explicit `yaml.load(stream, Loader)` call and
  string-only `BaseLoader` behavior.
- A2 corrected: no new setting or hidden default is introduced; every changed
  field appears in the approved contract.
- A3 corrected: repository, PR, and effective-rule claims require fresh API
  readback.
- B1/F1 corrected: no wrapper, registry, hand-written parser, duplicate
  workflow, or second ruleset. The established PyYAML parser is pinned
  directly for the contract test.
- B2/C1 corrected: T-CI-1A's obsolete deletion rollback is replaced in the
  planning PR before any live policy change; no destructive fallback survives.
- D1-D3 corrected: no test is weakened or mocked; live policy equality is the
  observable contract.
- E1-E3 corrected: only the eight tracked owned files and one owned external
  ruleset may change.
- A4, B3, C2, F2, H2-H4: no planned violations.

**o) Ratchet interaction.**

- Required checks: 1 to 2.
- Added check: `frontend-tests`, integration `15368`.
- Strict latest-default-branch policy: unchanged at `true`.
- Branch-creation exemption: unchanged at `true`.
- Bypass actors: unchanged at none.
- Other rules and rulesets: unchanged.
- Ruff, formatter, Mypy, coverage, runtime, and soak policy: unchanged.

**p) Dead code and duplication audit.** Replace two obsolete transition
annotations with accurate pending text, then remove that text after activation.
Remove the obsolete ruleset-deletion rollback and retire the unsafe T-CI-2
standalone procedure, which cannot also reconcile later T-CI-2A guardrails and
policy. Reuse all existing CI producers and readback commands. Runtime-code
delta is zero.

## 5. Testing

**q) Edge and failure scenarios.**

1. The current ruleset drifts before mutation.
2. The frontend context is absent or non-terminal on a non-frontend PR.
3. A check context comes from the wrong GitHub integration.
4. The request omits an existing policy field.
5. The request adds an extra check, rule, bypass actor, or ref target.
6. GitHub rejects or partially applies the update.
7. Effective `master` rules differ from the direct ruleset readback.
8. The policy update succeeds but documentation still describes the
   transition.
9. The PR fails after live policy changes.
10. A default-branch update after merge changes or removes the policy.
11. Another workflow occurrence or job-name override can alter or duplicate the
    `frontend-tests` check identity.
12. The request or observed pre-state bytes change after operator approval.
13. Another operator changes the ruleset between the final pre-state read and
    the full `PUT`; the API has no documented atomic write precondition.
14. Comments, step names, command bodies, quoted YAML, or folded scalars cause
    a text scanner to misclassify the effective workflow job name.
15. The workflow parser is present only transitively or leaks into runtime
    requirements.
16. A dynamic top-level job name resolves to `frontend-tests` only at runtime,
    preventing static proof that the required-check producer is unique.
17. PyYAML's YAML 1.1 Boolean resolver coerces valid GitHub job IDs or names
    such as `yes` and `On`, causing false guardrail failures.

**r) Verification mapping.**

| Evidence | Scenarios |
|---|---|
| Pre-mutation exact ruleset assertion | 1, 4, 5 |
| PR #114 check-run readback | 2, 3 |
| T-CI-2A PR check-run readback | 2, 3 |
| Approved request-file equality assertion | 4, 5 |
| Direct post-update ruleset assertion | 4-6 |
| Effective `master` rules assertion | 6, 7 |
| Documentation search and docs-link test | 8 |
| Python-only rollback `PUT` | 9 |
| Post-merge ruleset and effective-rule readback | 10 |
| Canonical frontend job-identity guardrail | 11 |
| Approved request and pre-state SHA-256 assertions | 12 |
| Exclusive change window, immediate pre-state check, and exact readback | 13 |
| Semantic workflow-parser regression cases | 14 |
| Development/runtime dependency boundary contract | 15 |
| Fail-closed dynamic job-name regression case | 16 |
| GitHub Boolean-like scalar parity regression cases | 17 |

No fixed test count or inferred UI behavior is used as acceptance evidence.

**s) Fakes and mocks.** None. GitHub's authenticated REST API is the real
operator boundary. Tracked documentation is verified through the filesystem.

**t) Verification rows.** Apply the guardrail/tooling and docs-only rows, then
run the complete Python suite because a repository-wide CI identity contract
changes. External acceptance also requires the frontend and non-frontend PR
check evidence, direct ruleset readback, effective-`master` readback, and
post-merge recheck.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

The activation sequence below is historical audit evidence. It completed on
2026-07-23 and **none of its repository setup, Python-only precondition,
approval-artifact, or mutation commands may be rerun**. Current remaining work
is limited to merging the completion record under both required checks,
performing its post-merge direct and effective two-check readbacks, obtaining
explicit operator acceptance of the deviation in 7z, merging the final closure
record under both required checks, and repeating the policy readbacks after
that second default-branch advance.

Historical repository setup:

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-ci-2a-required-frontend-check
```

Precondition and tests-first policy evidence:

```bash
set -euo pipefail
API_VERSION=2026-03-10
RULESET_ENDPOINT=repos/manumissio/town-council/rulesets/19594795
EFFECTIVE_ENDPOINT=repos/manumissio/town-council/rules/branches/master
WORK_DIR=$(mktemp -d)

gh api -H "X-GitHub-Api-Version: 2026-03-10" \
  "$RULESET_ENDPOINT" > "$WORK_DIR/ruleset-before.json"
gh api -H "X-GitHub-Api-Version: 2026-03-10" \
  "$EFFECTIVE_ENDPOINT" > "$WORK_DIR/effective-before.json"

jq -e '
  .id == 19594795 and
  .source == "manumissio/town-council" and
  .source_type == "Repository" and
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
' "$WORK_DIR/ruleset-before.json"

jq -e '
  length == 1 and
  .[0].ruleset_id == 19594795 and
  .[0].ruleset_source == "manumissio/town-council" and
  .[0].ruleset_source_type == "Repository" and
  .[0].type == "required_status_checks" and
  .[0].parameters.required_status_checks ==
    [{"context":"python-guardrails","integration_id":15368}] and
  .[0].parameters.strict_required_status_checks_policy == true and
  .[0].parameters.do_not_enforce_on_create == true
' "$WORK_DIR/effective-before.json"

if ! RULESET_COUNT=$(gh api -H "X-GitHub-Api-Version: $API_VERSION" \
  "repos/manumissio/town-council/rulesets?includes_parents=false" \
  --jq 'length'); then
  echo "Ruleset-count readback failed; external state is unknown" >&2
  exit 1
fi
if [ "$RULESET_COUNT" != "1" ]; then
  echo "Expected exactly one repository ruleset" >&2
  exit 1
fi

if gh api --include -H "X-GitHub-Api-Version: $API_VERSION" \
  repos/manumissio/town-council/branches/master/protection \
  > "$WORK_DIR/legacy-protection.txt" 2>&1; then
  echo "Expected legacy branch protection to be absent" >&2
  exit 1
fi
LEGACY_STATUS=$(awk '
  index($0, "HTTP/") == 1 { status=$2 }
  END { print status }
' "$WORK_DIR/legacy-protection.txt")
test "$LEGACY_STATUS" = "404"

if jq -e '
  (.rules[0].parameters.required_status_checks | sort_by(.context)) ==
    [
      {"context":"frontend-tests","integration_id":15368},
      {"context":"python-guardrails","integration_id":15368}
    ]
' "$WORK_DIR/ruleset-before.json"; then
  echo "Expected frontend-tests to be optional before T-CI-2A" >&2
  exit 1
fi
```

Frontend and non-frontend proof:

```bash
set -euo pipefail
API_VERSION=2026-03-10
WORK_DIR=$(mktemp -d)
T_CI_2A_PR=$(gh pr view --json number --jq .number)

assert_ci_contexts() {
  PR_NUMBER=$1
  PR_HEAD=$(gh pr view "$PR_NUMBER" --json headRefOid --jq .headRefOid)
  gh api -H "X-GitHub-Api-Version: $API_VERSION" \
    "repos/manumissio/town-council/commits/$PR_HEAD/check-runs" \
    > "$WORK_DIR/pr-$PR_NUMBER-checks.json"
  jq -e --arg head "$PR_HEAD" '
    [
      .check_runs[]
      | select(.name == "frontend-tests" or .name == "python-guardrails")
    ]
    | group_by(.name)
    | map(max_by(.id))
    | map({
        name,
        status,
        conclusion,
        integration_id: .app.id,
        head_sha
      })
    | sort_by(.name)
    ==
      [
        {
          name: "frontend-tests",
          status: "completed",
          conclusion: "success",
          integration_id: 15368,
          head_sha: $head
        },
        {
          name: "python-guardrails",
          status: "completed",
          conclusion: "success",
          integration_id: 15368,
          head_sha: $head
        }
      ]
  ' "$WORK_DIR/pr-$PR_NUMBER-checks.json"
}

gh pr view 114 --json files |
jq -e '
  (.files | length) > 0 and
  all(.files[]; .path | startswith("frontend/"))
'

gh pr view "$T_CI_2A_PR" --json files |
jq -e '
  (.files | length) > 0 and
  all(.files[]; (.path | startswith("frontend/") | not))
'

assert_ci_contexts 114
assert_ci_contexts "$T_CI_2A_PR"

test "$(rg -l '^  frontend-tests:' .github/workflows \
  -g '*.yml' -g '*.yaml' | wc -l | tr -d ' ')" = "1"
test "$(rg -l '^  python-guardrails:' .github/workflows \
  -g '*.yml' -g '*.yaml' | wc -l | tr -d ' ')" = "1"
```

Generate the immutable approval artifact before requesting approval:

```bash
set -euo pipefail
API_VERSION=2026-03-10
RULESET_ENDPOINT=repos/manumissio/town-council/rulesets/19594795
RULESET_REQUEST=/tmp/t-ci-2a-ruleset-request.json
RULESET_PRESTATE=/tmp/t-ci-2a-ruleset-prestate.json
RULESET_PRESTATE_RAW=$(mktemp)

gh api -H "X-GitHub-Api-Version: $API_VERSION" \
  "$RULESET_ENDPOINT" > "$RULESET_PRESTATE_RAW"
jq -S '{
  id,
  source,
  source_type,
  updated_at,
  name,
  target,
  enforcement,
  bypass_actors,
  conditions,
  rules
}' "$RULESET_PRESTATE_RAW" > "$RULESET_PRESTATE"

jq -n -S '
  {
    name: "Require Python Guardrails",
    target: "branch",
    enforcement: "active",
    bypass_actors: [],
    conditions: {
      ref_name: {
        include: ["~DEFAULT_BRANCH"],
        exclude: []
      }
    },
    rules: [
      {
        type: "required_status_checks",
        parameters: {
          required_status_checks: [
            {context: "python-guardrails", integration_id: 15368},
            {context: "frontend-tests", integration_id: 15368}
          ],
          strict_required_status_checks_policy: true,
          do_not_enforce_on_create: true
        }
      }
    ]
  }
' > "$RULESET_REQUEST"

jq -e '
  .name == "Require Python Guardrails" and
  .target == "branch" and
  .enforcement == "active" and
  .bypass_actors == [] and
  .conditions.ref_name.include == ["~DEFAULT_BRANCH"] and
  .conditions.ref_name.exclude == [] and
  (.rules | length) == 1 and
  .rules[0].type == "required_status_checks" and
  (.rules[0].parameters.required_status_checks | sort_by(.context)) ==
    [
      {"context":"frontend-tests","integration_id":15368},
      {"context":"python-guardrails","integration_id":15368}
    ] and
  .rules[0].parameters.strict_required_status_checks_policy == true and
  .rules[0].parameters.do_not_enforce_on_create == true
' "$RULESET_REQUEST"

jq -e '
  .id == 19594795 and
  .source == "manumissio/town-council" and
  .source_type == "Repository" and
  (.updated_at | type) == "string" and
  (.updated_at | length) > 0 and
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
' "$RULESET_PRESTATE"

jq . "$RULESET_PRESTATE"
shasum -a 256 "$RULESET_PRESTATE"
jq . "$RULESET_REQUEST"
shasum -a 256 "$RULESET_REQUEST"
```

The historical mutation procedure required approval of both displayed JSON
documents and digests, an exclusive ruleset change window, and one fail-closed
mutation block:

```bash
set -euo pipefail
API_VERSION=2026-03-10
RULESET_ENDPOINT=repos/manumissio/town-council/rulesets/19594795
EFFECTIVE_ENDPOINT=repos/manumissio/town-council/rules/branches/master
RULESET_REQUEST=/tmp/t-ci-2a-ruleset-request.json
: "${APPROVED_PRESTATE_SHA256:?Set the exact operator-approved pre-state SHA-256 digest}"
: "${APPROVED_REQUEST_SHA256:?Set the exact operator-approved SHA-256 digest}"
EXPECTED_PRESTATE_SHA256=$APPROVED_PRESTATE_SHA256
EXPECTED_REQUEST_SHA256=$APPROVED_REQUEST_SHA256
WORK_DIR=$(mktemp -d)
SUBMITTED_REQUEST="$WORK_DIR/approved-request.json"

cp "$RULESET_REQUEST" "$SUBMITTED_REQUEST"
ACTUAL_REQUEST_SHA256=$(shasum -a 256 "$SUBMITTED_REQUEST" | awk '{print $1}')
test "$ACTUAL_REQUEST_SHA256" = "$EXPECTED_REQUEST_SHA256"

gh api -H "X-GitHub-Api-Version: $API_VERSION" \
  "$RULESET_ENDPOINT" > "$WORK_DIR/ruleset-before.json"
gh api -H "X-GitHub-Api-Version: $API_VERSION" \
  "$EFFECTIVE_ENDPOINT" > "$WORK_DIR/effective-before.json"
jq -S '{
  id,
  source,
  source_type,
  updated_at,
  name,
  target,
  enforcement,
  bypass_actors,
  conditions,
  rules
}' "$WORK_DIR/ruleset-before.json" > "$WORK_DIR/prestate-before.json"
ACTUAL_PRESTATE_SHA256=$(shasum -a 256 "$WORK_DIR/prestate-before.json" | awk '{print $1}')
test "$ACTUAL_PRESTATE_SHA256" = "$EXPECTED_PRESTATE_SHA256"

jq -e '
  .id == 19594795 and
  .source == "manumissio/town-council" and
  .source_type == "Repository" and
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
' "$WORK_DIR/ruleset-before.json"

jq -e '
  length == 1 and
  .[0].ruleset_id == 19594795 and
  .[0].ruleset_source == "manumissio/town-council" and
  .[0].ruleset_source_type == "Repository" and
  .[0].type == "required_status_checks" and
  .[0].parameters.required_status_checks ==
    [{"context":"python-guardrails","integration_id":15368}] and
  .[0].parameters.strict_required_status_checks_policy == true and
  .[0].parameters.do_not_enforce_on_create == true
' "$WORK_DIR/effective-before.json"

if ! RULESET_COUNT=$(gh api -H "X-GitHub-Api-Version: $API_VERSION" \
  "repos/manumissio/town-council/rulesets?includes_parents=false" \
  --jq 'length'); then
  echo "Ruleset-count readback failed; external state is unknown" >&2
  exit 1
fi
if [ "$RULESET_COUNT" != "1" ]; then
  echo "Expected exactly one repository ruleset" >&2
  exit 1
fi

if gh api --include -H "X-GitHub-Api-Version: $API_VERSION" \
  repos/manumissio/town-council/branches/master/protection \
  > "$WORK_DIR/legacy-protection.txt" 2>&1; then
  echo "Expected legacy branch protection to be absent" >&2
  exit 1
fi
LEGACY_STATUS=$(awk '
  index($0, "HTTP/") == 1 { status=$2 }
  END { print status }
' "$WORK_DIR/legacy-protection.txt")
test "$LEGACY_STATUS" = "404"

jq '{
  name,
  target,
  enforcement,
  bypass_actors,
  conditions,
  rules
}' "$WORK_DIR/ruleset-before.json" > "$WORK_DIR/rollback.json"
jq -e '
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
' "$WORK_DIR/rollback.json" >/dev/null
ROLLBACK_REQUEST_SHA256=$(shasum -a 256 "$WORK_DIR/rollback.json" | awk '{print $1}')

is_python_ruleset() {
  jq -e '
    .id == 19594795 and
    .source == "manumissio/town-council" and
    .source_type == "Repository" and
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
  ' "$1" >/dev/null
}

is_two_check_ruleset() {
  jq -e '
    .id == 19594795 and
    .source == "manumissio/town-council" and
    .source_type == "Repository" and
    .name == "Require Python Guardrails" and
    .target == "branch" and
    .enforcement == "active" and
    .bypass_actors == [] and
    .conditions.ref_name.include == ["~DEFAULT_BRANCH"] and
    .conditions.ref_name.exclude == [] and
    (.rules | length) == 1 and
    .rules[0].type == "required_status_checks" and
    (.rules[0].parameters.required_status_checks | sort_by(.context)) ==
      [
        {"context":"frontend-tests","integration_id":15368},
        {"context":"python-guardrails","integration_id":15368}
      ] and
    .rules[0].parameters.strict_required_status_checks_policy == true and
    .rules[0].parameters.do_not_enforce_on_create == true
  ' "$1" >/dev/null
}

is_python_effective() {
  jq -e '
    length == 1 and
    .[0].ruleset_id == 19594795 and
    .[0].ruleset_source == "manumissio/town-council" and
    .[0].ruleset_source_type == "Repository" and
    .[0].type == "required_status_checks" and
    .[0].parameters.required_status_checks ==
      [{"context":"python-guardrails","integration_id":15368}] and
    .[0].parameters.strict_required_status_checks_policy == true and
    .[0].parameters.do_not_enforce_on_create == true
  ' "$1" >/dev/null
}

is_two_check_effective() {
  jq -e '
    length == 1 and
    .[0].ruleset_id == 19594795 and
    .[0].ruleset_source == "manumissio/town-council" and
    .[0].ruleset_source_type == "Repository" and
    .[0].type == "required_status_checks" and
    (.[0].parameters.required_status_checks | sort_by(.context)) ==
      [
        {"context":"frontend-tests","integration_id":15368},
        {"context":"python-guardrails","integration_id":15368}
      ] and
    .[0].parameters.strict_required_status_checks_policy == true and
    .[0].parameters.do_not_enforce_on_create == true
  ' "$1" >/dev/null
}

has_one_repository_ruleset() {
  test "$(gh api -H "X-GitHub-Api-Version: $API_VERSION" \
    "repos/manumissio/town-council/rulesets?includes_parents=false" \
    --jq 'length')" = "1"
}

has_no_legacy_protection() {
  local readback_path=$1
  if gh api --include -H "X-GitHub-Api-Version: $API_VERSION" \
    repos/manumissio/town-council/branches/master/protection \
    > "$readback_path" 2>&1; then
    return 1
  fi
  local legacy_status
  legacy_status=$(awk '
    index($0, "HTTP/") == 1 { status=$2 }
    END { print status }
  ' "$readback_path")
  test "$legacy_status" = "404"
}

PUT_OK=1
test "$(shasum -a 256 "$SUBMITTED_REQUEST" | awk '{print $1}')" = \
  "$EXPECTED_REQUEST_SHA256"
if ! gh api -H "X-GitHub-Api-Version: $API_VERSION" \
  --method PUT \
  "$RULESET_ENDPOINT" \
  --input "$SUBMITTED_REQUEST" \
  > "$WORK_DIR/update-response.json"; then
  PUT_OK=0
fi

POST_READBACK_OK=1
if ! gh api -H "X-GitHub-Api-Version: $API_VERSION" \
  "$RULESET_ENDPOINT" > "$WORK_DIR/ruleset-after.json"; then
  POST_READBACK_OK=0
fi
if ! gh api -H "X-GitHub-Api-Version: $API_VERSION" \
  "$EFFECTIVE_ENDPOINT" > "$WORK_DIR/effective-after.json"; then
  POST_READBACK_OK=0
fi

if [ "$PUT_OK" -eq 1 ] &&
  [ "$POST_READBACK_OK" -eq 1 ] &&
  is_two_check_ruleset "$WORK_DIR/ruleset-after.json" &&
  is_two_check_effective "$WORK_DIR/effective-after.json" &&
  has_one_repository_ruleset &&
  has_no_legacy_protection "$WORK_DIR/legacy-protection-after.txt"; then
  printf '%s\n' "$WORK_DIR"
else
  RECOVERY_READBACK_OK=1
  if ! gh api -H "X-GitHub-Api-Version: $API_VERSION" \
    "$RULESET_ENDPOINT" > "$WORK_DIR/ruleset-recovery.json"; then
    RECOVERY_READBACK_OK=0
  fi
  if ! gh api -H "X-GitHub-Api-Version: $API_VERSION" \
    "$EFFECTIVE_ENDPOINT" > "$WORK_DIR/effective-recovery.json"; then
    RECOVERY_READBACK_OK=0
  fi
  if [ "$RECOVERY_READBACK_OK" -ne 1 ]; then
    echo "Ruleset update failed and live state could not be read; external state is unknown" >&2
    echo "Recovery artifacts: $WORK_DIR" >&2
    exit 1
  fi
  if is_python_ruleset "$WORK_DIR/ruleset-recovery.json" &&
    is_python_effective "$WORK_DIR/effective-recovery.json" &&
    has_one_repository_ruleset &&
    has_no_legacy_protection "$WORK_DIR/legacy-protection-recovery.txt"; then
    echo "Ruleset update failed; the Python-only contract remains active" >&2
    exit 1
  fi
  if ! is_two_check_ruleset "$WORK_DIR/ruleset-recovery.json" ||
    ! is_two_check_effective "$WORK_DIR/effective-recovery.json"; then
    echo "Ruleset update failed with unrecognized concurrent policy drift; rollback not attempted" >&2
    exit 1
  fi

  if ! gh api -H "X-GitHub-Api-Version: $API_VERSION" \
    "$RULESET_ENDPOINT" > "$WORK_DIR/ruleset-rollback-preflight.json" ||
    ! gh api -H "X-GitHub-Api-Version: $API_VERSION" \
      "$EFFECTIVE_ENDPOINT" > "$WORK_DIR/effective-rollback-preflight.json" ||
    ! is_two_check_ruleset "$WORK_DIR/ruleset-rollback-preflight.json" ||
    ! is_two_check_effective "$WORK_DIR/effective-rollback-preflight.json" ||
    ! has_one_repository_ruleset ||
    ! has_no_legacy_protection "$WORK_DIR/legacy-protection-rollback-preflight.txt"; then
    echo "Rollback preflight could not prove the approved two-check state; external state is unknown" >&2
    echo "Recovery artifacts: $WORK_DIR" >&2
    exit 1
  fi

  test "$(shasum -a 256 "$WORK_DIR/rollback.json" | awk '{print $1}')" = \
    "$ROLLBACK_REQUEST_SHA256"
  if ! gh api -H "X-GitHub-Api-Version: $API_VERSION" \
    --method PUT \
    "$RULESET_ENDPOINT" \
    --input "$WORK_DIR/rollback.json" \
    > "$WORK_DIR/rollback-response.json"; then
    echo "Rollback request failed; external state is unknown" >&2
    echo "Recovery artifacts: $WORK_DIR" >&2
    exit 1
  fi

  if ! gh api -H "X-GitHub-Api-Version: $API_VERSION" \
    "$RULESET_ENDPOINT" > "$WORK_DIR/ruleset-rollback.json" ||
    ! gh api -H "X-GitHub-Api-Version: $API_VERSION" \
      "$EFFECTIVE_ENDPOINT" > "$WORK_DIR/effective-rollback.json" ||
    ! is_python_ruleset "$WORK_DIR/ruleset-rollback.json" ||
    ! is_python_effective "$WORK_DIR/effective-rollback.json" ||
    ! has_one_repository_ruleset ||
    ! has_no_legacy_protection "$WORK_DIR/legacy-protection-rollback.txt"; then
    echo "Rollback completed without a complete Python-only readback; external state is unknown" >&2
    echo "Recovery artifacts: $WORK_DIR" >&2
    exit 1
  fi
  echo "Two-check readback failed; restored the Python-only ruleset" >&2
  exit 1
fi
```

Repository verification:

```bash
./.venv/bin/ruff check .
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docker_build_contracts.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/pytest -q
git diff --check
git status --short

FENCE_DIR=$(mktemp -d)
awk -v fence_dir="$FENCE_DIR" '
  /^```bash$/ {
    in_bash=1
    file=sprintf("%s/fence-%02d.sh", fence_dir, ++count)
    next
  }
  /^```$/ && in_bash {
    close(file)
    in_bash=0
    next
  }
  in_bash { print > file }
' docs/plans/T_CI_2_REQUIRED_CHECK_POLICY_PLAN.md
for fence in "$FENCE_DIR"/*.sh; do
  bash -n "$fence"
done
```

**v) Rollback.** If the live update succeeds but completion cannot proceed,
establish the same exclusive ruleset change window, then restore and verify the
Python-only policy with this fail-closed block:

```bash
set -euo pipefail
API_VERSION=2026-03-10
RULESET_ENDPOINT=repos/manumissio/town-council/rulesets/19594795
EFFECTIVE_ENDPOINT=repos/manumissio/town-council/rules/branches/master
ROLLBACK_REQUEST=/tmp/t-ci-2a-python-only-rollback.json
WORK_DIR=$(mktemp -d)

gh api -H "X-GitHub-Api-Version: $API_VERSION" \
  "$RULESET_ENDPOINT" > "$WORK_DIR/ruleset-before-rollback.json"
gh api -H "X-GitHub-Api-Version: $API_VERSION" \
  "$EFFECTIVE_ENDPOINT" > "$WORK_DIR/effective-before-rollback.json"

jq -e '
  .id == 19594795 and
  .source == "manumissio/town-council" and
  .source_type == "Repository" and
  .name == "Require Python Guardrails" and
  .target == "branch" and
  .enforcement == "active" and
  .bypass_actors == [] and
  .conditions.ref_name.include == ["~DEFAULT_BRANCH"] and
  .conditions.ref_name.exclude == [] and
  (.rules | length) == 1 and
  .rules[0].type == "required_status_checks" and
  (.rules[0].parameters.required_status_checks | sort_by(.context)) ==
    [
      {"context":"frontend-tests","integration_id":15368},
      {"context":"python-guardrails","integration_id":15368}
    ] and
  .rules[0].parameters.strict_required_status_checks_policy == true and
  .rules[0].parameters.do_not_enforce_on_create == true
' "$WORK_DIR/ruleset-before-rollback.json"

jq -e '
  length == 1 and
  .[0].ruleset_id == 19594795 and
  .[0].ruleset_source == "manumissio/town-council" and
  .[0].ruleset_source_type == "Repository" and
  .[0].type == "required_status_checks" and
  (.[0].parameters.required_status_checks | sort_by(.context)) ==
    [
      {"context":"frontend-tests","integration_id":15368},
      {"context":"python-guardrails","integration_id":15368}
    ] and
  .[0].parameters.strict_required_status_checks_policy == true and
  .[0].parameters.do_not_enforce_on_create == true
' "$WORK_DIR/effective-before-rollback.json"

test "$(gh api -H "X-GitHub-Api-Version: $API_VERSION" \
  "repos/manumissio/town-council/rulesets?includes_parents=false" \
  --jq 'length')" = "1"

if gh api --include -H "X-GitHub-Api-Version: $API_VERSION" \
  repos/manumissio/town-council/branches/master/protection \
  > "$WORK_DIR/legacy-protection-before-rollback.txt" 2>&1; then
  echo "Expected legacy branch protection to be absent" >&2
  exit 1
fi
LEGACY_STATUS=$(awk '
  index($0, "HTTP/") == 1 { status=$2 }
  END { print status }
' "$WORK_DIR/legacy-protection-before-rollback.txt")
test "$LEGACY_STATUS" = "404"

jq -n -S '
  {
    name: "Require Python Guardrails",
    target: "branch",
    enforcement: "active",
    bypass_actors: [],
    conditions: {
      ref_name: {
        include: ["~DEFAULT_BRANCH"],
        exclude: []
      }
    },
    rules: [
      {
        type: "required_status_checks",
        parameters: {
          required_status_checks: [
            {context: "python-guardrails", integration_id: 15368}
          ],
          strict_required_status_checks_policy: true,
          do_not_enforce_on_create: true
        }
      }
    ]
  }
' > "$ROLLBACK_REQUEST"

jq -e '
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
' "$ROLLBACK_REQUEST" >/dev/null
ROLLBACK_REQUEST_SHA256=$(shasum -a 256 "$ROLLBACK_REQUEST" | awk '{print $1}')

if ! gh api -H "X-GitHub-Api-Version: $API_VERSION" \
  "$RULESET_ENDPOINT" > "$WORK_DIR/ruleset-rollback-preflight.json" ||
  ! gh api -H "X-GitHub-Api-Version: $API_VERSION" \
    "$EFFECTIVE_ENDPOINT" > "$WORK_DIR/effective-rollback-preflight.json"; then
  echo "Rollback preflight readback failed; external state is unknown" >&2
  echo "Recovery artifacts: $WORK_DIR" >&2
  exit 1
fi

if ! jq -e '
  .id == 19594795 and
  .source == "manumissio/town-council" and
  .source_type == "Repository" and
  .name == "Require Python Guardrails" and
  .target == "branch" and
  .enforcement == "active" and
  .bypass_actors == [] and
  .conditions.ref_name.include == ["~DEFAULT_BRANCH"] and
  .conditions.ref_name.exclude == [] and
  (.rules | length) == 1 and
  .rules[0].type == "required_status_checks" and
  (.rules[0].parameters.required_status_checks | sort_by(.context)) ==
    [
      {"context":"frontend-tests","integration_id":15368},
      {"context":"python-guardrails","integration_id":15368}
    ] and
  .rules[0].parameters.strict_required_status_checks_policy == true and
  .rules[0].parameters.do_not_enforce_on_create == true
' "$WORK_DIR/ruleset-rollback-preflight.json" >/dev/null ||
  ! jq -e '
  length == 1 and
  .[0].ruleset_id == 19594795 and
  .[0].ruleset_source == "manumissio/town-council" and
  .[0].ruleset_source_type == "Repository" and
  .[0].type == "required_status_checks" and
  (.[0].parameters.required_status_checks | sort_by(.context)) ==
    [
      {"context":"frontend-tests","integration_id":15368},
      {"context":"python-guardrails","integration_id":15368}
    ] and
  .[0].parameters.strict_required_status_checks_policy == true and
  .[0].parameters.do_not_enforce_on_create == true
' "$WORK_DIR/effective-rollback-preflight.json" >/dev/null; then
  echo "Rollback preflight found unrecognized policy drift; rollback not attempted" >&2
  exit 1
fi

test "$(gh api -H "X-GitHub-Api-Version: $API_VERSION" \
  "repos/manumissio/town-council/rulesets?includes_parents=false" \
  --jq 'length')" = "1"

if gh api --include -H "X-GitHub-Api-Version: $API_VERSION" \
  repos/manumissio/town-council/branches/master/protection \
  > "$WORK_DIR/legacy-protection-rollback-preflight.txt" 2>&1; then
  echo "Expected legacy branch protection to remain absent" >&2
  exit 1
fi
ROLLBACK_PREFLIGHT_LEGACY_STATUS=$(awk '
  index($0, "HTTP/") == 1 { status=$2 }
  END { print status }
' "$WORK_DIR/legacy-protection-rollback-preflight.txt")
if [ "$ROLLBACK_PREFLIGHT_LEGACY_STATUS" != "404" ]; then
  echo "Rollback preflight could not prove legacy branch protection is absent" >&2
  exit 1
fi

test "$(shasum -a 256 "$ROLLBACK_REQUEST" | awk '{print $1}')" = \
  "$ROLLBACK_REQUEST_SHA256"
if ! gh api -H "X-GitHub-Api-Version: $API_VERSION" \
  --method PUT \
  "$RULESET_ENDPOINT" \
  --input "$ROLLBACK_REQUEST" \
  > "$WORK_DIR/rollback-response.json"; then
  echo "Rollback request failed; external state is unknown" >&2
  echo "Recovery artifacts: $WORK_DIR" >&2
  exit 1
fi
if ! gh api -H "X-GitHub-Api-Version: $API_VERSION" \
  "$RULESET_ENDPOINT" > "$WORK_DIR/ruleset-rollback.json" ||
  ! gh api -H "X-GitHub-Api-Version: $API_VERSION" \
    "$EFFECTIVE_ENDPOINT" > "$WORK_DIR/effective-rollback.json"; then
  echo "Rollback completed without a complete readback; external state is unknown" >&2
  echo "Recovery artifacts: $WORK_DIR" >&2
  exit 1
fi

if ! jq -e '
  .id == 19594795 and
  .source == "manumissio/town-council" and
  .source_type == "Repository" and
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
' "$WORK_DIR/ruleset-rollback.json" >/dev/null ||
  ! jq -e '
  length == 1 and
  .[0].ruleset_id == 19594795 and
  .[0].ruleset_source == "manumissio/town-council" and
  .[0].ruleset_source_type == "Repository" and
  .[0].type == "required_status_checks" and
  .[0].parameters.required_status_checks ==
    [{"context":"python-guardrails","integration_id":15368}] and
  .[0].parameters.strict_required_status_checks_policy == true and
  .[0].parameters.do_not_enforce_on_create == true
' "$WORK_DIR/effective-rollback.json" >/dev/null; then
  echo "Rollback readback does not match the Python-only contract; external state is unknown" >&2
  echo "Recovery artifacts: $WORK_DIR" >&2
  exit 1
fi

if ! ROLLBACK_RULESET_COUNT=$(gh api -H "X-GitHub-Api-Version: $API_VERSION" \
  "repos/manumissio/town-council/rulesets?includes_parents=false" \
  --jq 'length'); then
  echo "Rollback ruleset-count readback failed; external state is unknown" >&2
  echo "Recovery artifacts: $WORK_DIR" >&2
  exit 1
fi
if [ "$ROLLBACK_RULESET_COUNT" != "1" ]; then
  echo "Rollback readback found an unexpected repository ruleset count" >&2
  exit 1
fi

if gh api --include -H "X-GitHub-Api-Version: $API_VERSION" \
  repos/manumissio/town-council/branches/master/protection \
  > "$WORK_DIR/legacy-protection-after-rollback.txt" 2>&1; then
  echo "Expected legacy branch protection to remain absent" >&2
  exit 1
fi
ROLLBACK_LEGACY_STATUS=$(awk '
  index($0, "HTTP/") == 1 { status=$2 }
  END { print status }
' "$WORK_DIR/legacy-protection-after-rollback.txt")
if [ "$ROLLBACK_LEGACY_STATUS" != "404" ]; then
  echo "Rollback readback could not prove legacy branch protection is absent" >&2
  echo "Recovery artifacts: $WORK_DIR" >&2
  exit 1
fi
```

Never delete ruleset `19594795`, remove `python-guardrails`, add a bypass
actor, or infer rollback success from a command exit alone. Revert tracked
completion records only after both Python-only readbacks pass. Keep the safer
rollback guidance in T-CI-1A.

**w) Docs synchronization.**

- This plan records the activated request and defines how approval, evidence,
  rollback, and final state are recorded.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` records T-CI-2 completion,
  T-CI-2A progress, approval, and final completion.
- `docs/plans/T_CI_1_REQUIRED_CHECK_POLICY_PLAN.md` replaces the obsolete
  ruleset-deletion rollback in the planning PR before the live update.
- `docs/plans/T_CI_2_FRONTEND_TESTS_PLAN.md` preserves its historical
  pre-activation evidence and retires standalone rollback after T-CI-2A
  activation.
- `AGENTS.md` first replaces stale landed-task annotations with accurate
  T-CI-2A-pending text, then removes that temporary text after live readback.
- `tests/test_repository_guardrails.py` enforces one canonical repository-wide
  `frontend-tests` workflow job ID and no alternate effective job-name
  producer, using string-preserving structural YAML parsing.
- `pipeline/requirements-dev.txt` and `tests/test_docker_build_contracts.py`
  make the parser a direct development-only dependency.
- README, architecture review, ADR, operations, security, data governance,
  application contracts, and workflows: no changes.

## 7. Delivery Self-Audit

**x) Antipattern scan, diff pass.** Re-run A-F and H. Reject a second ruleset,
extra check, bypass actor, copied API response as request, missing drift check,
workflow edit, new script, weakened evidence, unrelated documentation edit,
or transition removal before live proof.

**y) Evidence.** On 2026-07-23, the operator approved the exact semantic
transition from one required check to two. The fail-closed update produced a
live direct and effective readback with:

- ruleset ID `19594795`, target `branch`, enforcement `active`;
- exactly one repository ruleset and no legacy branch protection (`404`);
- default-branch-only condition and no bypass actors;
- strict required-check policy and branch-creation exemption unchanged;
- required contexts `python-guardrails` and `frontend-tests`, both from
  integration `15368`;
- observed update timestamp `2026-07-23T11:23:01.116-04:00`.

The canonical pre-state SHA-256 was
`335bce222d1664b91fd89e0eb16cc687654e1b24913f60ef78842bf69f04f98d`;
the request SHA-256 was
`9d0fd138be8c765b451098898c714c5cc50001333f07c0937835537d8e464065`.
This completion-record pull request and its post-merge policy readback remain
pending and must be reported separately before T-CI-2A is marked complete.
Final closure also requires explicit operator acceptance of the procedural
deviation below.

**z) Deviations.** The operator approved the exact semantic old and new
contracts after they were displayed, but did not separately approve the
generated SHA-256 values before the update. The live request changed no field
outside that approved semantic contract, and complete direct and effective
readbacks matched it. The first shell attempt was rejected before execution
because it contained a prohibited cleanup command, so it changed no external
state; the corrected fail-closed attempt performed the one approved update.
This process deviation is recorded rather than hidden. The remaining
acceptance path requires explicit operator acceptance of this deviation, both
mandatory checks on this record PR, and a fresh post-merge readback. No tracked
path outside ownership may change.
