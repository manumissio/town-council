# T-CI-4: Move Formatter Scope Into Ruff Configuration

artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
execution: code
task: T-CI-4
lane: CI

## 1. Context & Alignment

**a) Driver.** Python Guardrails still carries the formatter-ready file set as
a long command-line enumeration. That duplicates machine policy in CI and
makes formatter enrollment hard to review or reuse locally. T-CI-4 moves the
same file set into Ruff configuration without formatting additional files,
narrowing lint discovery, or changing runtime behavior.

**b) Canonical documents.** `AGENTS.md` `<workflow_contract>`,
`<verification_matrix>`, and `<docs_sync_rules>` require config-owned scopes,
guardrail verification, and commands that match repository reality.
`docs/ENGINEERING_GUARDRAILS.md` makes Ruff the formatter owner and forbids
file enumerations in prose or CI. `docs/TESTING.MD` permits filesystem and
subprocess verification without production seams. The remediation plan places
T-CI-4 in Phase 0 and makes it a prerequisite for T-GOV-5. The architecture
review identifies workflow-owned formatter scope as transitional debt.

**c) Remediation alignment.** Expand T-CI-4 ownership before implementation
to:

- `docs/plans/T_CI_4_FORMATTER_SCOPE_PLAN.md`
- `docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md`
- `AGENTS.md` (`<docs_sync_rules>` config-location reference only)
- `docs/ENGINEERING_GUARDRAILS.md` (formatter scope and command sections only)
- `tests/test_repository_guardrails.py` (formatter contract only)
- `ruff.toml` (owned for verification; no edit expected)
- new `ruff-format.toml`
- `.github/workflows/python-guardrails.yml` (formatter step only)

No other tracked path may change.

**d) Decision gates.** T-CI-4 does not depend on or foreclose G1-G5. The
enforced formatter file set remains exactly the current 68-file typed subtree,
so this is not a gate-semantics change. On 2026-07-22, the operator approved
the dedicated `ruff-format.toml` design and expanded ownership together with
T-CI-1A's exact ruleset contract. T-CI-1A was delivered first on its review
branch; T-CI-4 rebases onto that branch and takes remediation-plan version 1.8
before implementation. This preserves the required serialization without
coupling formatter behavior to repository ruleset behavior.

## 2. Design

**e) Approach.**

1. Record the current workflow formatter arguments as the baseline set.
2. Add failing tests before configuration or workflow edits. The tests require
   a formatter-specific Ruff config, exact parity with the baseline set, and a
   one-line config-driven workflow command.
3. Add `ruff-format.toml` with one responsibility: select the formatter-ready
   files. It extends `ruff.toml` and defines `include` as the exact current
   formatter set.
4. Keep `ruff.toml` unchanged as the lint policy and repository-discovery
   owner. Ruff 0.15.9 has formatter-specific `exclude` but no
   formatter-specific `include`; changing its top-level `include` would narrow
   `ruff check .` and is forbidden.
5. Change only the formatter workflow step to:

   ```yaml
   run: python -m ruff format --check . --config ruff-format.toml
   ```

6. Replace the transitional formatter contract test with one that parses
   `ruff-format.toml`, confirms it extends `ruff.toml`, requires a non-empty
   unique include set whose paths exist, rejects formatter exclusions, and
   checks the exact workflow command. Formatter enrollment remains independent
   from Mypy enrollment after the migration.
7. Prove the effective formatter set by comparing the child config's `include`
   directly with the 68-path baseline, asserting that neither parent nor child
   defines formatter exclusions, and running the actual formatter command.
   Do not use `ruff check --show-files` as formatter evidence because that
   command does not apply `[format].exclude`.
8. Capture `ruff check --show-files .` before and after implementation and
   compare the normalized path lists. Add a durable test that `ruff.toml` has
   no top-level `include`, so the formatter child cannot narrow lint policy.
9. Update only the named policy prose so contributors use the formatter config
   and no document claims formatter scope lives in `ruff.toml`.
10. Run complete verification, LFG simplification, a plan-aware code review,
   and a fresh subagent pre-commit review. Apply every eligible P1/P2 before
   delivery.

No Python production function or module is added.

**f) Reuse audit.** Reuse the current formatter list, `ruff.toml`, Ruff's
native `extend` and `include` settings, the existing guardrail test, and the
existing CI step. A second Ruff config is justified because Ruff 0.15.9 cannot
express a formatter-only include set inside the shared lint config. It replaces
the workflow enumeration; the old list is deleted in the same change.

Rejected alternatives:

- Put the allowlist in top-level `ruff.toml` `include`: rejected because it
  narrows repository-wide lint discovery.
- Use `[format].exclude` to encode the inverse set: rejected because it would
  require hundreds of exclusions and preserve policy through an opaque
  complement list.
- Enroll every file Ruff currently considers formatted: rejected because it
  expands the gate beyond the approved set.
- Keep the workflow list: rejected because CI would remain a second policy
  owner.

**g) Data contracts.** `ruff-format.toml` is the sole machine-readable
formatter scope contract. Its `include` entries are unique repository-relative
paths. The existing test tuple remains only the typed-subtree contract. The
current equality is verified once during migration and is not made a permanent
cross-tool invariant.

**h) Schema and migrations.** None.

## 3. Security & Data Governance

**i) Security boundary.** No `AGENTS.md` security-sensitive path is touched.
Workflow permissions, dependencies, event triggers, and executed source code
remain unchanged.

**j) Secrets.** None.

**k) Person data.** None. G4 is unaffected.

**l) Untrusted input.** Tests parse tracked TOML with `tomllib` and invoke the
pinned Ruff binary through the approved subprocess boundary. No scraped,
provider, or user content is parsed.

## 4. Code Health

**m) Conformance.** The only new test helper, if needed, reads one TOML list
and returns normalized repository paths. It has complete annotations, no
branching beyond validation, and no error swallowing, timestamp, environment
read, or runtime side effect. Config paths use repository-relative names.

**n) Antipattern scan, plan pass.** A1/H1 were resolved against installed Ruff
0.15.9, `ruff config format`, `ruff config format.exclude`, `ruff config
include`, local discovery probes, and current Context7 Ruff documentation. B1
is a documented exception: one formatter-only config is the smallest mechanism
that preserves both exact formatter and lint scopes; the inverse-exclusion and
gate-expansion alternatives are materially worse. C1 is satisfied by deleting
the workflow enumeration. D1-D3 are avoided by preserving the exact set and
asserting observable config/workflow behavior. F1 is resolved by making
`ruff-format.toml` the sole durable formatter list rather than coupling it to
the Mypy test oracle. E1-E3 and F2 are controlled by the ownership list and
removal of the old policy copy. A2-A4, B2-B3, C2, and H2-H4 do not apply.

**o) Ratchets.** Ruff lint selectors, per-file ignores, BLE001 boundaries,
source discovery, and McCabe limits remain unchanged. Formatter enrollment is
68 files before and after. No selector or exclusion is added to silence code.

**p) Dead code and duplication.** Delete the long workflow argument list and
the transitional test assertion that requires it. Reuse the same path set in
the formatter config. Expected net growth is documentation and one config
file; workflow size decreases substantially.

## 5. Testing

**q) Edge and failure scenarios.**

1. A formatter config path is added, removed, misspelled, or missing.
2. The formatter config stops extending the canonical Ruff policy.
3. The workflow points at the wrong config or reintroduces file arguments.
4. Top-level `ruff.toml` lint discovery is accidentally narrowed.
5. A newly enrolled file is not yet Ruff-formatted.
6. A previously enrolled file silently drops out of formatter enforcement.
7. Formatter execution modifies tracked bytes.
8. Workflow triggers, dependencies, permissions, lint, Mypy, or pytest steps
   drift as collateral edits.

**r) Tests.**

| Test or command | Scenarios |
|---|---|
| Updated formatter contract test | 1-5, 8 |
| Existing Ruff entrypoint and workflow contracts | 3, 4, 8 |
| Before/after `ruff check --show-files .` comparison | 4, 8 |
| One-time old-workflow/config path diff | 1, 6 |
| Actual formatter check and write-mode source diff | 5, 7 |
| Repository guardrail suite | 1-8 |
| Complete Python suite | Runtime regression check |

The formatter contract test is changed and run red before adding
`ruff-format.toml` or editing the workflow.

**s) Fakes and mocks.** None. Tests use approved filesystem and subprocess
boundaries and patch no facade or implementation symbol.

**t) Verification rows.** Apply the guardrail/tooling and docs-only rows. Run
the complete Python suite because CI policy is cross-cutting.

## 6. Execution, Rollback, Docs

**u) Commands.**

```bash
git fetch origin --prune
git worktree add -b codex/t-ci-4-formatter-scope \
  <SIBLING_WORKTREE> origin/master
cd <SIBLING_WORKTREE>
test -e .venv || ln -s <PRIMARY_REPO_ROOT>/.venv .venv
test -x .venv/bin/ruff && test -x .venv/bin/pytest
./.venv/bin/ruff --version
./.venv/bin/ruff check --show-files . \
  | sed "s#$(pwd)/##" | sort > /tmp/t-ci-4-lint-files.before
git show origin/master:.github/workflows/python-guardrails.yml \
  | sed -n 's/^        run: python -m ruff format --check //p' \
  | tr ' ' '\n' | sort > /tmp/t-ci-4-formatter-paths.before
```

The `.venv` symlink is ignored, local-only worktree setup; no personal path is
written to tracked files.

Tests-first red evidence:

```bash
PYTHONPATH=. .venv/bin/pytest -q \
  tests/test_repository_guardrails.py::test_formatter_scope_is_config_owned_and_preserved
```

Final verification:

```bash
./.venv/bin/python - <<'PY' > /tmp/t-ci-4-formatter-paths.after
from pathlib import Path
import tomllib

formatter_config = tomllib.loads(Path("ruff-format.toml").read_text(encoding="utf-8"))
for formatter_path in sorted(formatter_config["include"]):
    print(formatter_path)
PY
diff -u /tmp/t-ci-4-formatter-paths.before /tmp/t-ci-4-formatter-paths.after
./.venv/bin/ruff check --show-files . \
  | sed "s#$(pwd)/##" | sort > /tmp/t-ci-4-lint-files.after
diff -u /tmp/t-ci-4-lint-files.before /tmp/t-ci-4-lint-files.after
./.venv/bin/ruff check .
./.venv/bin/ruff format --check . --config ruff-format.toml
git diff --exit-code -- api pipeline scripts
./.venv/bin/ruff format . --config ruff-format.toml
git diff --exit-code -- api pipeline scripts
./.venv/bin/pre-commit run ruff --all-files
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py
PYTHONPATH=. .venv/bin/python -m pytest -q tests/
git diff --check
git status --short
```

Delivery uses two atomic commits:

1. `docs(remediation): authorize T-CI-4 formatter scope cleanup`
2. `fix(guardrails): move formatter scope into Ruff config`

Push `codex/t-ci-4-formatter-scope`, open one PR, request review, and use the
bounded PR watcher until CI is decided.

**v) Rollback.** Revert the T-CI-4 commits, restoring the explicit workflow
list and transitional policy text. Rerun Ruff lint, the old scoped formatter
command from the reverted workflow, Mypy, repository guardrails, docs links,
and the complete Python suite. No migration, data repair, dependency rollback,
or external-state cleanup exists.

**w) Docs synchronization.** Update `AGENTS.md` `<docs_sync_rules>` to name
`ruff-format.toml` as the formatter scope config. Update
`docs/ENGINEERING_GUARDRAILS.md` Single-source rule, local command, and
Formatting sections and remove T-CI-4 transition markers. Update the
remediation registry's T-CI-4 and T-GOV-5 references. README, ADR, operations,
testing policy, architecture review, security, and data-governance docs do not
change.

## 7. Delivery Self-Audit

**x) Diff scan.** Re-run A-F and H. Reject any formatter-set expansion,
`ruff.toml` lint-scope change, inverse exclusion list, workflow edit outside
the formatter step, duplicate workflow list, unrelated formatting, weakened
assertion, new dependency, or tracked path outside ownership.

**y) Evidence.** Report the tests-first red result, exact 68-path parity,
unchanged 608-file lint discovery, Ruff lint and formatter outcomes, the
write-mode source diff, pre-commit, Mypy, repository guardrails, docs links,
complete-suite counts, planning-review and pre-commit-review findings, commit
hashes, PR URL, unresolved P1/P2 count, and final CI state. Anything unrun is
`NOT VERIFIED`.

**z) Deviations.** The approved design correction is a dedicated
`ruff-format.toml` because Ruff 0.15.9 lacks formatter-specific include. The
operator approved the new config and ownership set on 2026-07-22. Any other
added config, expanded formatter enrollment, lint policy change, additional
owned path, skipped review, unresolved P1/P2, or unrun required check blocks
delivery.
