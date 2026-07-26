# T-PLAT-2B: Patch pypdf Batch Parsing

`artifact_contract: ce-unified-plan/v1`
`artifact_readiness: implementation-ready`
`execution: code`

## 1. Context & Alignment

**a) Driver.** The default branch pins `pypdf==6.13.3` in the batch worker.
Dependabot alerts 116 through 119 report two high- and two medium-severity
denial-of-service risks in malformed PDF parsing. Version 6.14.2 is the first
release that closes all four alerts. Civic documents are externally sourced,
so the parser must not retain known unbounded-loop or memory-risk defects.

**b) Canonical documents consulted.**

- `AGENTS.md`: current dependency evidence, tests first, narrow ownership,
  exact verification, and no runtime-policy drift.
- `SECURITY.md`: crawled documents are untrusted; patch dependencies without
  broadening exposure.
- `docs/TESTING.MD`: use observable filesystem, subprocess, and dependency
  contracts rather than test-only seams.
- `docs/ENGINEERING_GUARDRAILS.md`: Ruff and the complete suite are
  authoritative Python checks.
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md` assigns dependency hygiene to
  the PLAT lane. T-PLAT-2B isolates the urgent pypdf patch from the broader
  constraints, Dependabot, and audit work in T-PLAT-2.
- `docs/reviews/architecture-review-2026-07-19.html`: keep platform dependency
  work separate from facade and runtime architecture changes.

**c) Remediation alignment.** T-PLAT-2B is a focused child of T-PLAT-2 and
follows merged T-PLAT-1A. It owns exactly the two planning documents,
`pipeline/requirements-batch.txt`, `pipeline/table_worker.py`, `ruff.toml`,
`tests/test_docker_build_contracts.py`, `tests/test_repository_guardrails.py`,
and `tests/test_table_worker.py`.

The ledger closes T-PLAT-1 and T-PLAT-1A, activates T-PLAT-2B, and leaves
broader dependency hygiene pending.

**d) Decision-gate check.** No G1-G5 decision is required or foreclosed. This
patch changes no deployment posture, visitor policy, person-data policy, test
seam, migration behavior, model policy, runtime default, or soak baseline.

## 2. Design

**e) Step-by-step approach.**

1. Add a focused batch dependency contract requiring exactly one pypdf pin at
   6.14.2 while preserving its exclusion from the live-worker manifest.
2. Add a malformed-PDF test requiring `PyPdfError` from both Camelot strategies
   to persist `tables=[]` without aborting catalog processing.
3. Run both tests and record failures against 6.13.3 and `PdfStreamError`.
4. Pin 6.14.2; import and catch `PyPdfError`; narrow the optional import
   fallback to `ImportError`; remove the stale table-worker BLE001 allowance.
5. Download the exact wheel without installing it. Verify Python 3.14,
   `Requires-Python`, version 6.14.2, and the public exception import.
6. Build the real batch image and smoke pypdf, Camelot, and `PyPdfError`.
7. Run focused behavior, Docker and guardrail contracts, static gates, docs
   links, and the complete suite.
8. Inspect the diff and obtain a fresh subagent pre-commit review; apply P1/P2
   findings and rerun affected checks.
9. Commit implementation separately from authorization, push one branch,
   open one PR, request Codex review, and watch required checks.
10. After merge, query alerts 116-119 directly and require `state=fixed`.

**f) Reuse audit.** Extend the existing batch requirements split, parser error
boundary, Docker contract, table-worker tests, and Ruff ratchet. pypdf 6.14.2
uses `PdfReadError` and `LimitReachedError` for the patched failures; their
existing `PyPdfError` base is the single correct boundary. T-PLAT-2 retains
constraints and audit automation.

Rejected alternatives: 6.14.0/6.14.1 leave a high alert open; moving pypdf to
the core worker breaks the batch-only split; preserving `PdfStreamError` lets
sibling exceptions abort the batch; broad T-PLAT-2 delays urgent remediation.

**g) Contracts.**

- Old batch pin: `pypdf==6.13.3`.
- New batch pin: `pypdf==6.14.2`.
- Old parser boundary: `PdfStreamError`.
- New parser boundary: `PyPdfError`, covering documented pypdf parse failures.
- Unchanged: live-worker exclusion, batch image ownership, successful table
  extraction, runtime defaults, task signatures, and application interfaces.

**h) Schema and migrations.** None.
## 3. Security & Data Governance

**i) Security boundary.** The changed files are not listed under
`AGENTS.md` security-sensitive paths. The dependency parses externally sourced
PDF bytes in the batch worker. The patch removes known denial-of-service risks
and ensures the library's new bounded failures remain catalog-local rather
than aborting the batch. It changes no inputs, privileges, or exposure.

**j) Secrets.** No credential, key, token, environment variable, package index,
or default is added.

**k) Person data.** No person-level data is created, linked, aggregated,
retained, or exposed. G4 is unaffected.

**l) Untrusted input.** PDF bytes remain untrusted at the Camelot/pypdf
boundary. The failure catch expands to pypdf's documented base exception;
successful parsing and persistence are unchanged.

## 4. Code Health

**m) Conformance.** The implementation changes one pin and one existing
exception boundary. The error handler still takes meaningful action by
persisting an empty table result. Tests use existing approved boundaries.

**n) Antipattern scan, plan pass.**

- A1/H1: Context7 verifies current pypdf exception documentation and Python
  support. PyPI verifies 6.14.2 as a universal wheel with Python 3.14 support.
  Installed pip 26.1.1 help verifies `download`, `--no-deps`,
  `--only-binary`, and `--dest`.
- A3: package installation is not claimed. Wheel download/import and CI
  results are reported separately; the batch image build is explicit.
- B1/F1: reuse the manifest and existing contract test; add no dependency
  abstraction.
- D1: update the exact security expectation; do not skip, suppress, or dismiss
  an alert.
- D3: exact version matching is the public security outcome.
- E1/E2: edit only the eight owned files; no generated file exists.
- A2, A4, B2-B3, C1-C2, D2, E3, F2, and H2-H4: no planned violations.

**o) Ratchets.** Remove the table-worker BLE001 selector and matching exact
boundary inventory after replacing broad import fallback with `ImportError`.
No selector is added or widened.

**p) Dead code and duplication.** Remove the obsolete pin expectation,
`PdfStreamError` import/fallback, and stale BLE001 entries. Do not preserve an
alias. Expected production delta is neutral apart from exception naming.

## 5. Testing

**q) Edge and failure scenarios.**

1. The batch manifest remains on vulnerable 6.13.3.
2. More than one pypdf pin appears.
3. pypdf leaks into the live-worker manifest.
4. A patched `PdfReadError` or `LimitReachedError` escapes catalog processing.
5. Both Camelot strategies fail and the catalog is not marked `tables=[]`.
6. The wheel or batch image fails under its configured Python runtime.
7. Wheel metadata/version or `PyPdfError` import is wrong.
8. The table-worker BLE001 allowance remains after its violation is removed.
9. An unrelated dependency or application file changes.
10. Any alert 116-119 is not `fixed` after merge.

**r) Test mapping.**

| Test or evidence | Scenarios |
|---|---|
| Focused batch pypdf pin contract | 1-3 |
| New malformed-pypdf behavior test | 4-5 |
| Published wheel plus real batch-image smoke | 6-7 |
| Repository guardrail test | 8 |
| `git diff --check`, status, and file inventory | 9 |
| Direct per-alert Dependabot readback | 10 |

Both focused contracts are written and run red before implementation.

**s) Fakes and mocks.** The pin contract uses the filesystem boundary. The
behavior test uses the existing Camelot dependency fake and DB-session
boundary, patching `pipeline.table_worker`, not a facade. No seam is added.

**t) Verification rows.** Apply guardrail/tooling and docs-only rows, focused
table-worker and Docker contracts, real batch-image smoke, and the complete
suite. Required PR checks remain authoritative.
## 6. Execution, Rollback, Docs

**u) Exact commands.**

```bash
git fetch origin --prune
git switch master
git merge --ff-only origin/master
git switch -c codex/t-plat-2b-pypdf-security-patch
```

Tests-first red evidence:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_docker_build_contracts.py::test_batch_pdf_parser_uses_patched_pypdf \
  tests/test_table_worker.py::test_process_single_pdf_handles_pypdf_error_as_broken_pdf
```

Published-wheel verification without installation:

```bash
.venv/bin/python - <<'PY'
from importlib.metadata import metadata, version
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

assert sys.version_info[:2] == (3, 14)
with TemporaryDirectory(prefix="tc-pypdf-wheel-") as wheel_directory:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "download",
            "--no-deps",
            "--only-binary=:all:",
            "--dest",
            wheel_directory,
            "pypdf==6.14.2",
        ],
        check=True,
    )
    wheel_path = next(Path(wheel_directory).glob("pypdf-6.14.2-*.whl"))
    sys.path.insert(0, str(wheel_path))

    from pypdf.errors import PyPdfError

    assert version("pypdf") == "6.14.2"
    assert metadata("pypdf")["Requires-Python"] == ">=3.9"
    assert issubclass(PyPdfError, Exception)
    print(f"verified pypdf=={version('pypdf')}")
PY
```

Batch-image verification requires operator approval because it installs packages:

```bash
docker build --target python-worker-batch \
  -t town-council-pypdf-6.14.2-smoke .
docker run --rm --entrypoint python town-council-pypdf-6.14.2-smoke \
  -c "import camelot,pypdf; from pypdf.errors import PyPdfError; assert pypdf.__version__ == '6.14.2'; assert callable(camelot.read_pdf)"
```

Final verification:

```bash
./.venv/bin/ruff check .
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_docker_build_contracts.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_table_worker.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/pytest -q
git diff --check
git status --short
```

Delivery uses two commits:

1. `docs(remediation): authorize T-PLAT-2B pypdf patch`
2. `fix(deps): patch pypdf batch parsing`

Push the branch, open one PR titled
`T-PLAT-2B: Patch pypdf batch parsing`, request Codex review, and watch all
required checks. Do not merge without operator approval.

Post-merge readback:

```bash
set -e
for alert_number in 116 117 118 119; do
  test "$(gh api --method GET \
    "repos/manumissio/town-council/dependabot/alerts/$alert_number" \
    --jq .state)" = "fixed"
done
```

Dismissed or open alerts fail the loop.

**v) Rollback.** Revert the merge commit, rebuild the batch image, and rerun
the focused behavior, Docker, guardrail, static, docs, and complete-suite
checks. No data remediation is required. Rollback knowingly restores four
advisories and the narrower parser exception boundary.

**w) Docs synchronization.**

- Remediation plan: close T-PLAT-1/T-PLAT-1A, register T-PLAT-2B, and update
  execution order.
- New T-PLAT-2B Full plan.
- README, ADR, architecture, operations, testing policy, security policy, and
  data-governance docs: no change because behavior and operator commands do
  not change.

## 7. Delivery Self-Audit

**x) Diff scan.** Re-run A-F and H. Reject code outside the parser boundary,
constraints/audit machinery, another manifest, compatibility aliases,
dependency churn, unrelated formatting, or paths outside the eight-file set.

**y) Evidence.** Report both red tests, wheel metadata/import, batch-image
smoke, Ruff, Mypy, Docker/table-worker/guardrail/docs tests, complete-suite
counts, reviews, commits, PR, CI, and per-alert readback. Mark unrun package
installation or image build as `NOT VERIFIED`.

**z) Deviations.** Expected result is none. Any extra file, wrong version,
package installation without approval, swallowed non-pypdf error, audit
suppression, skipped review, unresolved P1/P2, or missing check is a blocker.
