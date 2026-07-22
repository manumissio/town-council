# Engineering Guardrails

Town Council uses a layered guardrail system to reduce low-signal code smells
before they land in `master`.

Status: this revision lands alongside remediation tasks T-CI-4 (formatter
scope moves to `ruff.toml`) and T-GOV-3 (structural rules replace per-file
line lists). Sections marked `[transition]` state which task activates them.

## Single-source rule for scopes

Every enforced file set lives in exactly one machine-readable location. This
document explains the policy and points at the scope; it never duplicates the
list (see `AGENTS.md` `<docs_sync_rules>`).

| Guardrail            | Scope lives in                                   |
|----------------------|--------------------------------------------------|
| Lint                 | `ruff.toml` (rule selection + paths)             |
| Formatter            | `ruff.toml` format include set `[transition: T-CI-4]` |
| Typed subtree        | `mypy.ini` `files`/per-module sections           |
| Smell tests          | constants at the top of `tests/test_repository_guardrails.py` |
| CI orchestration     | `.github/workflows/python-guardrails.yml`, `.github/workflows/frontend-tests.yml` |

Cleanup-wave history (the former Batch A–G family lists) is decision record
material, not living policy: see `docs/ADR.md`.

## Local commands

Run before opening a PR:

```bash
cd <REPO_ROOT>
./.venv/bin/ruff check .
./.venv/bin/ruff format --check .        # scope from ruff.toml [transition: T-CI-4]
./.venv/bin/mypy                          # scope from mypy.ini
PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py
```

CI runs the static checks, fast-fail test subset, and complete Python suite on
every relevant change. The fast-fail subset provides earlier diagnostics; the
complete suite remains the Python merge gate (see `docs/TESTING.md`).

## What the static checks block

- unused imports and unused locals
- mutable defaults and a small set of high-signal bug patterns
- bare `except:` blocks
- broad `except Exception` handlers that are neither in an approved boundary
  file nor compliant with the flat re-raise contract below

The pass is intentionally moderate: it blocks lazy hygiene regressions
without forcing a repo-wide style migration.

## Structural rules `[transition: T-GOV-3]`

These replace the per-file 300-line lists. Rationale: line caps measured a
proxy and drove mechanical facade+helper splits whose sync machinery was
worse than the length it removed. The replacement rules measure the thing we
actually care about — cohesion and dependency direction — and files may be as
long as their content is cohesive.

1. Complexity ceiling: no function above radon grade C (CC > 10) in `api/`
   or `pipeline/` without a documented exception. Enforcement mechanism and
   rule selection are recorded in `ruff.toml` / the guardrail test when
   adopted; per `AGENTS.md`, do not claim complexity enforcement before the
   config selects it.
2. Import direction: helper modules must not import their facade/route
   module. Generalized from the `semantic_service` rule to every
   facade+helpers family registered in the guardrail test constants.
3. Banned structures (mechanically checked): bidirectional
   `_sync_*_from_*` global-reconciliation functions; f-string interpolation
   inside SQLAlchemy `text(...)` DDL/DML; duplicated module-global state
   synchronized by convention. See `AGENTS.md` `<known_antipatterns>` for
   the full rationale.
4. Retired: per-file line-count assertions for families collapsed in
   remediation Phase 2. Remaining line assertions are deleted as their
   families are recombined, not extended to new files.

## Optional local dead-code and complexity audit

`pipeline/requirements-dev.txt` pins the local audit tools:

- `vulture==2.16`
- `radon==6.0.1`

Advisory local audits, not CI gates:

```bash
cd <REPO_ROOT>
./.venv/bin/python -m vulture api pipeline scripts tests --min-confidence 80
./.venv/bin/python -m radon cc api pipeline scripts -s -n C
```

## What the smell tests protect

- no personal absolute paths in tracked repo files
- no import-time logging configuration in reusable pipeline modules
- no raw `print(...)` in non-CLI pipeline modules
- no silent broad exception handlers or broad-exception allowlist drift
- fail-fast runtime behavior, freshness contracts, and profile comparability
  (existing Town Council policy tests)
- the structural rules above, as they are adopted

The broad-handler scan follows the Python files reported by
`ruff check --show-files .`; other smell-test scopes live as constants in
`tests/test_repository_guardrails.py`. Change the machine-readable source,
not this document.
The Python Guardrails workflow must trigger for every directory and
repository-root Python file included by that Ruff discovery command.

## How to request an exception

Keep exceptions narrow and path-specific.

- For stdout-driven operator tools, document why stdout is the contract.
- For broad handling that cannot satisfy the flat re-raise contract, keep it
  in an approved boundary file, log with context, and explain what invariant
  remains true.
- Remove path-specific suppressions only when both the current lint checks
  and the guardrail tests prove they are stale, instead of letting exception
  lists drift forward indefinitely.
- Do not add broad repo-wide ignores when a per-path exception is enough.

## Boundary exception handlers

Boundary handlers are limited to runtime, provider, exporter, maintenance,
and operator-entrypoint edges where the code is isolating an unstable
dependency.

- If the handler can preserve the caller contract, log with context and
  return a typed failure payload.
- If the handler cannot preserve the contract safely, log with context and
  re-raise.
- Log-only handlers are allowed only when a nearby comment states why the
  invariant remains true.
- Summary hydration embed dispatch is an approved best-effort boundary
  because summary writes are already durable before enqueue attempts.

## Flat re-raise contract

An unlisted broad handler is allowed only when it remains flat: zero or more
simple assignments or direct action calls followed by `raise`. The final raise
may re-raise the current exception or translate it explicitly with exception
chaining. This narrow path supports context capture, logging, rollback, and
metrics without treating every re-raising handler as a permanent boundary
exception.

Unlisted handlers must not contain conditional or loop flow, `return`,
`break`, `continue`, `yield`, `yield from`, `await`, nested `try`, `with`,
`match`, nested functions, nested classes, or `sys.exit()`. A legitimate
handler needing compound flow belongs in the centralized Ruff boundary
inventory and requires boundary review.

This is conservative structural enforcement, not semantic control-flow proof.
Python name binding and enclosing constructs can change runtime behavior, so
the guardrail intentionally recognizes only the narrow source structures it
can verify. Approved Ruff boundary files remain governed by the boundary
handler policy above.

## Typed subtree

The typed subtree is defined in `mypy.ini`. Run:

```bash
cd <REPO_ROOT>
./.venv/bin/mypy
```

Growing the subtree is a policy change: move modules into `mypy.ini` scope in
their own PR, report old/new scope per the `AGENTS.md` status-reporting
contract, and do not mix with behavioral edits.

## Formatting

Python formatting uses Ruff only. The formatter-ready path set is configured
in `ruff.toml` `[transition: T-CI-4]`; run:

```bash
cd <REPO_ROOT>
./.venv/bin/ruff format --check .
```

Keep formatter enforcement limited to the configured set, and do not mix
formatting with behavioral edits.

## How to add a new guardrail

When a smell recurs:

1. Add the smallest rule or smell test that catches it.
2. Prefer extending existing test helpers and config instead of adding a new
   framework.
3. Put any file scope in the single-source location for that guardrail type.
4. Add the verification command to the change summary.
5. Update `AGENTS.md` only if the contributor workflow needs to change.
