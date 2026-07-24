# T-PLAT-2A: Patch Next.js's Transitive Sharp Runtime

`artifact_contract: ce-unified-plan/v1`

`artifact_readiness: implementation-ready`

`execution: code`

## 1. Context & Alignment

**a) Driver.** Dependabot alert 106 reports high-severity vulnerabilities in
Sharp versions before 0.35.0 through bundled libvips. Town Council locks
Next.js 16.2.11, whose optional dependency range currently resolves Sharp
0.34.5. The narrow remediation is to keep Next.js unchanged and pin only its
Sharp child to patched version 0.35.3.

**b) Canonical documents consulted.**

- `AGENTS.md` requires current dependency documentation, tests-first work,
  exact verification evidence, local-first behavior, and scoped delivery.
- `SECURITY.md` identifies browser input entering Next.js as an Internet to
  frontend trust boundary and assigns dependency auditing to T-PLAT-2.
- `docs/TESTING.md` requires observable contracts and permits filesystem and
  subprocess verification without a production test seam.
- `docs/ENGINEERING_GUARDRAILS.md` requires current frontend and docs checks.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` owns dependency hygiene in the
  PLAT lane but does not yet isolate this urgent alert.
- `docs/reviews/architecture-review-2026-07-19.html` keeps platform work
  separate from facade-removal tasks and open decision gates.

**c) Remediation alignment.** T-PLAT-2A is an urgent, narrow child of
T-PLAT-2. It owns exactly:

- `docs/plans/T_PLAT_2A_SHARP_SECURITY_PATCH_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/components/__tests__/SharpDependency.security.test.js`

The ledger marks merged T-TIME-3 complete and activates T-PLAT-2A before any
dependency implementation changes.

**d) Decision-gate check.** No G1-G5 decision is required or foreclosed. This
patch changes neither deployment posture nor product authorization, person
data, test-seam policy, or migration tooling.

## 2. Design

**e) Step-by-step approach.**

1. Add a Node test that requires Next.js to remain 16.2.11, forbids Sharp in
   every root dependency section, and requires both the nested override and
   lockfile to select Sharp 0.35.3.
2. Run the new test and capture its expected failure against Sharp 0.34.5.
3. Extend the existing `overrides` object in `frontend/package.json` with a
   nested `next.sharp` pin to 0.35.3. Preserve the existing PostCSS override.
4. Run `npm install --package-lock-only --ignore-scripts` so npm 11 updates
   only dependency resolution metadata.
5. Inspect the lockfile diff and reject unrelated package-version churn.
6. Run `npm ci` to prove the manifest and lockfile agree and to install the
   correct platform-specific Sharp binary.
7. Use `sharp.versions` to prove Sharp 0.35.3 loads with bundled libvips
   8.18.3, then perform a one-pixel in-memory PNG conversion.
8. Run frontend tests and the production frontend build.
9. Build the Linux-musl Docker builder stage, then run the same version and
   PNG smoke inside that image so the native runtime is exercised.
10. Run the high-severity npm audit, docs links, and diff checks.
11. Obtain independent pre-commit review, apply eligible findings, and rerun
   affected checks before delivery.

No application function, helper module, runtime route, or compatibility path
is added.

**f) Reuse audit.** Extend the existing npm `overrides` object and Node test
runner. npm's lockfile remains the only dependency graph. Do not add a direct
Sharp dependency, audit wrapper, package-manager script, alternate lockfile,
or separate security-test runner.

Rejected alternatives:

- `npm audit fix --force`: npm proposes Next.js 14.2.35, a breaking downgrade.
- Direct `sharp` dependency: application code does not import Sharp, so this
  would misrepresent ownership and create an unnecessary public dependency.
- Upgrade Next.js: 16.2.11 is already current in the repository and still
  declares `sharp@^0.34.5`; a framework change is wider than the alert.
- Accept the risk because no `next/image` component was found: the framework
  still ships an image route and vulnerable native code; the patch is small.

**g) Data contracts.**

- Old graph: Next.js 16.2.11 resolves optional Sharp 0.34.5.
- New graph: Next.js 16.2.11 resolves optional Sharp 0.35.3 through a nested
  npm override.
- Unchanged: frontend API, routes, browser bundle, runtime configuration,
  Next.js version, React versions, and PostCSS override.

The committed test reads `package.json` and lockfile version 3 as JSON. It
does not import Sharp as an application dependency.

**h) Schema and migration impact.** None.

## 3. Security & Data Governance

**i) Security boundary.** The changed files are not listed in
`AGENTS.md` `<security_sensitive_paths>`, but the dependency participates in
the Internet to frontend boundary because Next.js can decode image input.
The patch removes known vulnerable libvips code from the resolved frontend
runtime without broadening accepted image sources or network exposure. This
implements the immediate patch portion of `SECURITY.md`'s dependency and
supply-chain control; broader audit automation remains T-PLAT-2.

**j) Secrets.** No credential, key, environment variable, package token, or
default is added.

**k) Person data.** No person-level data is created, linked, aggregated, or
exposed.

**l) Untrusted input.** No parser or route changes. Existing Next.js image
handling remains the decoding boundary; only its native decoder version
changes.

## 4. Code Health

**m) GED conformance sweep.** The implementation is one nested override plus
its generated lockfile. The test has no custom version parser, mocks,
timestamps, environment reads, exception handler, or nested control flow.

**n) Antipattern scan, plan pass.**

- A1/H1: npm CLI 11 documentation confirms nested transitive overrides,
  lockfile-only generation, and `npm ci` lock validation. npm registry
  metadata confirms Next.js 16.2.11 and Sharp 0.35.3 both require Node
  20.9.0 or newer. Sharp documentation confirms `sharp.versions`.
- B1/F1: reuse npm and the existing Node runner; add no wrapper or registry.
- B3: runtime and Docker smokes are required because Sharp is a native
  optional dependency across macOS ARM and Linux musl.
- D1: do not suppress the alert, force a downgrade, skip a test, or weaken an
  audit level.
- D3: exact dependency versions are the observable security contract.
- E1/E2: accept generated lockfile changes only for Sharp and its native
  packages.
- A2-A4, B2, C1-C2, D2, E3, F2, and H2-H4: no planned violations.

**o) Ratchet interaction.** No Ruff, Mypy, coverage, formatter, exception, or
workflow allowlist changes.

**p) Dead code and duplication audit.** Nothing is deleted or duplicated.
Expected handwritten delta is one override object, one focused test file, and
planning text; npm generates the lockfile delta.

## 5. Testing

**q) Edge and failure scenarios.**

1. The manifest lacks the nested Sharp override.
2. Sharp is added to any root dependency section.
3. The lockfile still resolves vulnerable Sharp 0.34.5.
4. Updating Sharp changes Next.js away from 16.2.11.
5. Manifest and lockfile disagree, causing `npm ci` to fail.
6. The macOS ARM native module cannot load after clean installation.
7. Sharp loads but does not report 0.35.3 and libvips 8.18.3.
8. A minimal in-memory decode/encode operation fails.
9. The Linux-musl Docker builder cannot install or load the patched native
   dependency.
10. The frontend test or production build regresses.
11. A high-severity production dependency remains in `npm audit`.
12. Lockfile generation updates unrelated dependencies.
13. Dependabot alert 106 remains open after the patch reaches `master`.

**r) Tests and evidence.**

| Test or command | Scenarios |
|---|---|
| `SharpDependency.security.test.js` | 1-4 |
| `npm ci` | 5 |
| `sharp.versions` plus one-pixel PNG smoke | 6-8 |
| Docker builder-stage build and in-container smoke | 9 |
| `npm test` and `npm run build -- --webpack` | 10 |
| `npm audit --omit=dev --audit-level=high` | 11 |
| Lockfile diff inspection | 12 |
| Dependabot API readback after merge | 13 |

The new test is written and run red before modifying dependency files.

**s) Fakes and mocks.** None. Tests use the approved filesystem boundary.
Install, audit, build, and native-load evidence use real package-manager,
process, and container boundaries.

**t) Verification rows.** Apply frontend component/behavior and docs-only
verification. Run the complete frontend test command, production build, and
security-specific package checks. Python application code is unchanged, so
the complete Python suite is not required locally; PR Python Guardrails
remains an authoritative merge check.

## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-plat-2a-sharp-security-patch
```

Tests-first red evidence:

```bash
cd frontend
node --test components/__tests__/SharpDependency.security.test.js
```

Implementation and lockfile generation:

```bash
cd frontend
npm install --package-lock-only --ignore-scripts
git diff -- package.json package-lock.json
npm ci
```

Final verification:

```bash
cd frontend
node --test components/__tests__/SharpDependency.security.test.js
node - <<'NODE'
const assert = require("node:assert/strict");
const sharp = require("sharp");

(async () => {
  assert.equal(sharp.versions.sharp, "0.35.3");
  assert.equal(sharp.versions.vips, "8.18.3");
  const pngBuffer = await sharp({
    create: {
      width: 1,
      height: 1,
      channels: 4,
      background: { r: 0, g: 0, b: 0, alpha: 1 },
    },
  })
    .png()
    .toBuffer();
  assert.ok(pngBuffer.length > 0);
})().catch((sharpError) => {
  console.error(sharpError);
  process.exitCode = 1;
});
NODE
npm test
npm run build -- --webpack
npm audit --omit=dev --audit-level=high
cd ..
docker build --target builder \
  --tag town-council-frontend-sharp-smoke \
  frontend
docker run --rm \
  --entrypoint node \
  town-council-frontend-sharp-smoke \
  -e 'const assert=require("node:assert/strict");const sharp=require("sharp");assert.equal(sharp.versions.sharp,"0.35.3");assert.equal(sharp.versions.vips,"8.18.3");sharp({create:{width:1,height:1,channels:4,background:{r:0,g:0,b:0,alpha:1}}}).png().toBuffer().then((pngBuffer)=>assert.ok(pngBuffer.length>0)).catch((sharpError)=>{console.error(sharpError);process.exitCode=1;});'
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
git diff --check
git status --short
```

Post-merge alert verification:

```bash
gh api repos/manumissio/town-council/dependabot/alerts/106 \
  --jq '{state, fixed_at, dependency: .dependency.package.name}'
```

**v) Rollback.** There is no safe version rollback because reverting restores
vulnerable Sharp 0.34.5. If a pre-merge check fails, do not merge. If an
operational incompatibility appears after merge, stop the affected frontend
deployment and roll forward in a new branch to another verified Sharp version
at or above 0.35.0, regenerate the lockfile, and rerun every command in 6u
before deployment. No database, migration, configuration, or data repair is
required. Reverting to 0.34.5 requires explicit emergency risk acceptance and
must record the reopened high-severity alert.

**w) Docs synchronization.** Add this plan and update the remediation
ledger's version, changelog, T-TIME-3 completion, T-PLAT-2A status,
ownership, acceptance, and verification. README, ADR, architecture,
operations, testing policy, engineering guardrails, security policy, API
contracts, and data-governance docs remain unchanged because their current
contracts are still accurate.

## 7. Delivery Self-Audit

**x) Antipattern scan, diff pass.** Re-run A-F and H. Reject any Next.js
downgrade, direct Sharp dependency, audit suppression, alternate lockfile,
new package script, unrelated dependency churn, workflow change, or edit
outside the five owned files.

**y) Evidence.** Report the expected red test, npm and Node versions, exact
lockfile delta, clean install, native versions and PNG smoke, frontend tests,
production and Docker builds, audit result, docs links, independent planning
and pre-commit review findings, commit hashes, PR URL, unresolved threads,
CI state, and post-merge alert readback. Mark anything unrun as
`NOT VERIFIED`.

**z) Deviations.** Authorized remediation-plan changes are T-TIME-3 closure
and the five-file T-PLAT-2A registration. Any additional path, unresolved
high-severity audit finding, skipped review, failed required check, unrelated
lockfile update, or unresolved P1/P2 is a blocker.
