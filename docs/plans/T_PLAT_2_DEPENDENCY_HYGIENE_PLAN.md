# T-PLAT-2: Centralize Dependency Policy and Add Audits

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: implementation-ready`
`execution: code`

## 1. Context & Alignment

**a) Driver.** Town Council repeats eleven exact Python package pins across
service manifests, does not configure Dependabot version updates, and claims
dependency audits exist although neither required workflow runs them. T-PLAT-2
must establish one reviewed version policy, preserve service-specific
environments, and make dependency findings visible without hiding audit-tool
failures or changing runtime package versions.

**b) Canonical documents consulted.**

- `AGENTS.md` `<security_sensitive_paths>`, `<workflow_contract>`,
  `<verification_matrix>`, and `<docs_sync_rules>` require a Full plan,
  trust-boundary reporting for Docker changes, exact verification, and
  synchronized workflow guidance.
- `SECURITY.md` "Dependency and supply chain" assigns Dependabot and dependency
  audits to T-PLAT-2 but currently describes them as already active.
- `docs/TESTING.MD` permits filesystem and subprocess boundaries without
  adding production test seams.
- `docs/ENGINEERING_GUARDRAILS.md` keeps audit tooling development-only.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` requires shared constraints,
  weekly pip/npm/action updates, report-only audits, image builds, and a green
  suite.
- `docs/reviews/architecture-review-2026-07-19.html` identifies dependency
  hygiene as platform work after the safety baseline.

**c) Remediation alignment.** This is T-PLAT-2 in the PLAT lane. The operator
approved this exact expansion on 2026-07-26:

- `docs/plans/T_PLAT_2_DEPENDENCY_HYGIENE_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `constraints.txt`
- `api/requirements.txt`
- `council_crawler/requirements.txt`
- `pipeline/requirements.txt`
- `pipeline/requirements-batch.txt`
- `pipeline/requirements-dev.txt`
- `pipeline/requirements-nlp.txt` for deletion
- `semantic_service/requirements.txt`
- `Dockerfile`
- `.github/dependabot.yml`
- `.github/workflows/python-guardrails.yml`
- `.github/workflows/frontend-tests.yml`
- `tests/test_docker_build_contracts.py`
- `tests/test_repository_guardrails.py`
- `SECURITY.md`

T-PLAT-2 starts after T-PLAT-2B and PR #159, both now merged. No active task
owns an overlapping file.

**d) Decision-gate check.** No G1-G5 decision is required or foreclosed.
Runtime package versions, merge thresholds, workflow permissions, and local
inference policy remain unchanged.

## 2. Design

**e) Step-by-step approach.**

1. Register this plan, exact ownership, active status, acceptance criteria,
   and verification in the remediation ledger.
2. Add failing dependency, Docker, Dependabot, workflow-audit, and policy
   contract tests before implementation.
3. Add root `constraints.txt` with the eleven repeated exact pins:
   `beautifulsoup4`, `celery`, `fastapi`, `httpx`, `meilisearch`,
   `prometheus-client`, `psycopg2-binary`, `rapidfuzz`, `redis`, `sqlalchemy`,
   and `uvicorn`. Add `pip-audit==2.10.1` as the audit tool's sole version
   policy.
4. Make each of the six active manifests begin with
   `-c ../constraints.txt`. Keep every direct dependency listed in its owning
   manifest, but remove versions now owned by constraints. Preserve
   `pgvector>=0.2.5`, batch `scikit-learn==1.5.0`, and every unique exact pin.
5. Add unversioned `pip-audit` to `pipeline/requirements-dev.txt`. Delete the
   obsolete, unreferenced `pipeline/requirements-nlp.txt`; the batch manifest
   already owns its three packages.
6. Preserve manifest directories in `Dockerfile`, copy root and semantic CPU
   constraints to their repository-relative paths, and install with absolute
   `/app/...` requirement paths. Remove redundant bare `rapidfuzz` arguments.
7. Add weekly Dependabot version updates for pip directories `/`, `/api`,
   `/council_crawler`, `/pipeline`, and `/semantic_service`; npm directory
   `/frontend`; and GitHub Actions directory `/`.
8. After the Python 3.14 test and coverage steps, select Python 3.12, install
   the constrained `pip-audit`, and audit API, crawler, live worker, batch
   worker, semantic, and development manifests separately. Batch uses both
   pipeline requirement files.
9. For each Python audit, write JSON to the runner temporary directory.
   Accept exit `0` only with valid zero-finding JSON. Treat exit `1` as
   report-only only when valid JSON contains at least one vulnerability.
   Missing, malformed, contradictory, or abnormal results fail the job.
10. After frontend tests, run
    `npm audit --omit=dev --audit-level=high --json`. Accept exit `0` only
    with a valid report and no high/critical findings. Treat exit `1` as
    report-only only when valid metadata reports high/critical findings.
    Top-level errors, malformed reports, contradictions, or abnormal exits
    fail the job.
11. Update `SECURITY.md` to distinguish weekly version updates, report-only
    vulnerability findings, and blocking audit execution failures.
12. Run all local gates, independent simplification, fresh subagent review,
    package-install/build verification after explicit execution approval,
    atomic commits, PR delivery, and bounded CI repair.

Each workflow keeps its audit classifier in the step that owns the external
tool protocol. No application helper, parser package, compatibility path, or
second dependency registry is added.

**f) Reuse audit.** Extend the six existing manifests, split-image Docker
build, two required workflows, PyYAML-based workflow contract tests, and
existing requirement parsers. `constraints.txt` is the single version-policy
home. `docker/semantic-cpu-constraints.txt` remains separate because it
selects a CPU-specific Torch build rather than shared application versions.

Rejected alternatives:
- Combined Python audit: creates cross-service conflicts absent from deployment.
- Non-blocking flags: suppress tool failures as if they were findings.
- Pinning `pgvector`: lacks evidence and authority to replace its lower bound.
- New audit wrapper: neither workflow nor runtime needs another shared module.

**g) Data contracts.** Dependency policy is the root constraints file plus six
service manifests. Python audit JSON must contain `dependencies` and `fixes`
lists, with vulnerability lists on resolved dependencies. npm JSON must contain
`auditReportVersion`, no top-level `error`, and numeric high/critical counts
under `metadata.vulnerabilities`.

**h) Schema/migration impact.** None. No database state, Alembic revision,
timestamp, API, Celery signature, environment variable, or runtime default
changes.

## 3. Security & Data Governance

**i) Security boundary.** `Dockerfile` is security-sensitive. This change
alters build-time dependency inputs and CI registry queries, reducing version
drift and exposing known vulnerabilities. It does not change base images,
ports, users, credentials, build context, runtime roles, or permissions.
`SECURITY.md` "Dependency and supply chain" applies.

**j) Secrets.** No credential, token, key, secret, permission, or working
default is added. Required workflows retain `contents: read`.

**k) Person data.** No person data is created, linked, aggregated, or exposed.
G4 and T-GOV-2 are unaffected.

**l) Untrusted input.** Package registries and audit JSON are untrusted.
Workflow classifiers validate required fields and status consistency before
allowing report-only findings. Invalid tool output fails closed.

## 4. Code Health

**m) GED conformance sweep.** Test helpers receive no more than three
parameters and perform one responsibility. Workflow functions use
dependency-domain names. No production Python, timestamp, environment read,
exception handler, or complexity boundary changes.

**n) Antipattern scan, plan pass.**

- A1/H1 corrected: pip requirements and constraints, pip-audit 2.10.1 flags,
  Dependabot directories, and npm 11 audit flags were verified against current
  docs or pinned source.
- B1/F1 corrected: no wrapper, manager, registry class, new parser dependency,
  or duplicate pin inventory is introduced.
- B3 corrected: validation distinguishes known real tool outcomes; no
  impossible-state scaffolding is planned.
- D1 corrected: findings are intentionally report-only per the ledger, while
  tool failures remain blocking. No existing gate is weakened.
- D3 accepted narrowly: exact manifest locations and workflow commands are
  observable supply-chain contracts.
- E1/E2 corrected: only the seventeen owned paths may change.
- A2-A4, B2, C1-C2, D2, E3, F2, H2-H4: no violations planned.

**o) Ratchet interaction.** Ruff rules, per-file ignores, BLE001 boundaries,
Mypy scope, coverage floor, required checks, and test thresholds are
unchanged.

**p) Dead code and duplication audit.** Delete
`pipeline/requirements-nlp.txt`, eleven repeated version declarations, and two
redundant Docker `rapidfuzz` arguments. Reuse existing manifests and workflow
jobs. Net growth comes from the Full plan, contract tests, audit steps, and
Dependabot configuration; production Python remains unchanged.

## 5. Testing

**q) Edge cases and failure scenarios.**

1. An active manifest omits the root constraint or duplicates a shared pin.
2. Docker flattens manifests so relative constraints resolve outside `/app`.
3. The batch image loses either its live or batch dependency set.
4. `pgvector` lower bounds or semantic CPU constraints drift.
5. The obsolete NLP manifest or a runtime reference survives.
6. A required Dependabot ecosystem, directory, or weekly schedule is absent.
7. Python audit findings produce valid JSON and exit `1`.
8. Python audit emits malformed, empty, contradictory, or error output.
9. Python audit exits outside `0`/`1`.
10. npm reports valid high/critical findings with exit `1`.
11. npm emits a top-level error, malformed report, contradiction, or abnormal
    exit.
12. Workflow findings are hidden by `continue-on-error`, `if`, or `|| true`.
13. Security prose claims findings block merge or tool failures are tolerated.
14. Native or Docker dependency resolution fails under Python 3.12.

**r) Tests.**

| Test | Scenarios |
|---|---|
| Shared constraint and active-manifest contract | 1, 4 |
| Docker requirement-path and split-image contract | 2-5 |
| Obsolete NLP manifest contract | 5 |
| Dependabot configuration contract | 6 |
| Executed Python audit-step contract with fake CLI | 7-9, 12 |
| Executed npm audit-step contract with fake CLI | 10-12 |
| Security policy/workflow agreement contract | 13 |
| Native dry-run and Docker target builds | 14 |
| Existing Docker and repository guardrail suites | 1-13 |
| Complete Python and frontend suites | Regression coverage |

Tests execute the actual workflow `run` blocks through temporary CLI
executables. They do not copy classifier logic into tests.

**s) Fakes and mocks.** Temporary `pip-audit` and `npm` executables use the
approved filesystem/subprocess boundary. No production symbol, facade, or
re-export is patched.

**t) Verification rows.** Apply guardrail/tooling, coverage-gate,
security-sensitive Docker, docs-only, and broad cross-cutting rows. Run the
complete Python and frontend suites plus all five Docker targets.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-plat-2-dependency-hygiene

PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_docker_build_contracts.py \
  tests/test_repository_guardrails.py

./.venv/bin/ruff check .
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_docker_build_contracts.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/pytest -q
git diff --check
```

After explicit approval for package-installing verification:

```bash
docker build --target python-crawler .
docker build --target python-api .
docker build --target python-worker-live .
docker build --target python-worker-batch .
docker build --target python-semantic .
cd frontend && npm ci && npm test
```

The native pip dry-run verifies all six manifest combinations under Python
3.12 without installing into the repository environment.

**v) Rollback.** Revert the T-PLAT-2 merge commit, rerun the same static,
contract, complete-suite, frontend, and image gates, then close only
Dependabot version-update PRs created by this configuration. Do not disable
existing security updates or automated fixes. No migration or data repair is
required.

**w) Docs sync.**

- `SECURITY.md`: dependency update cadence and report-only versus blocking
  audit behavior.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`: version, changelog, status,
  ownership, acceptance, and verification.
- New T-PLAT-2 Full plan.
- README, ADR, operations, architecture, testing, data-governance, and
  performance docs: no changes.

## 7. Delivery Self-Audit

**x) Antipattern scan, diff pass.** Re-run A-F/H. Reject version drift, a
combined audit environment, ignored tool failures, duplicated classifier
logic, new workflow jobs, changed permissions, added runtime packages,
unrelated formatting, or edits outside ownership.

**y) Evidence.** Report tests-first red evidence; Context7 and pinned-source
verification; Ruff, Mypy, focused contracts, docs links, complete Python and
frontend suites; native resolution; five image builds; planning and
pre-commit findings; commit hashes; PR URL; unresolved-thread count; and final
CI state. Mark unrun commands `NOT VERIFIED`.

**z) Deviations.** Authorized deviations are the operator-approved ownership
expansion, deletion of `pipeline/requirements-nlp.txt`, preservation of six
separate Python environments, and fail-closed report parsing. Any other file,
package version change, audit suppression, skipped review, unresolved P1/P2,
or unrun required check is a blocker.
