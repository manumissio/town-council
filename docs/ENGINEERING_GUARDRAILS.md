# Engineering Guardrails

Town Council uses a layered guardrail system to reduce low-signal code smells before they land in `master`.

## Local command

Run the Python-first guardrails before opening a PR:

```bash
cd <REPO_ROOT>
./.venv/bin/ruff check api pipeline scripts tests
PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py
```

## What the static checks block

- unused imports and unused locals
- mutable defaults and a small set of high-signal bug patterns
- bare `except:` blocks

The first pass is intentionally moderate. It is meant to block lazy hygiene regressions without forcing a repo-wide style migration.

## What the smell tests protect

- no personal absolute paths in tracked repo files
- no import-time logging configuration in reusable pipeline modules
- no raw `print(...)` in non-CLI pipeline modules
- existing Town Council policy tests for fail-fast runtime behavior, freshness contracts, and profile comparability

## How to request an exception

Keep exceptions narrow and path-specific.

- For stdout-driven operator tools, document why stdout is the contract.
- For broader exception handling, document the runtime boundary, log with context, and explain what invariant remains true.
- Do not add broad repo-wide ignores when a per-path exception is enough.

## How to add a new guardrail

When a smell recurs:

1. Add the smallest rule or smell test that catches it.
2. Prefer extending existing test helpers and config instead of adding a new framework.
3. Add the verification command to the change summary.
4. Update `AGENTS.md` only if the contributor workflow needs to change.
