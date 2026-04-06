# Engineering Guardrails

Town Council uses a layered guardrail system to reduce low-signal code smells before they land in `master`.

## Local command

Run the Python-first guardrails before opening a PR:

```bash
cd <REPO_ROOT>
./.venv/bin/ruff check api pipeline scripts tests
./.venv/bin/mypy api/metrics.py pipeline/summary_freshness.py scripts/analyze_pipeline_profile.py
PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py
```

## What the static checks block

- unused imports and unused locals
- mutable defaults and a small set of high-signal bug patterns
- bare `except:` blocks
- broad `except Exception` handlers outside approved boundary files

The first pass is intentionally moderate. It is meant to block lazy hygiene regressions without forcing a repo-wide style migration.

## What the smell tests protect

- no personal absolute paths in tracked repo files
- no import-time logging configuration in reusable pipeline modules
- no raw `print(...)` in non-CLI pipeline modules
- no silent broad exception handlers or broad exception allowlist drift
- existing Town Council policy tests for fail-fast runtime behavior, freshness contracts, and profile comparability

## How to request an exception

Keep exceptions narrow and path-specific.

- For stdout-driven operator tools, document why stdout is the contract.
- For broader exception handling, keep it in an approved boundary file, log with context, and explain what invariant remains true.
- Do not add broad repo-wide ignores when a per-path exception is enough.

## Boundary exception handlers

Boundary handlers are limited to runtime, provider, exporter, maintenance, and operator-entrypoint edges where the code is isolating an unstable dependency.

- If the handler can preserve the caller contract, log with context and return a typed failure payload.
- If the handler cannot preserve the contract safely, log with context and re-raise.
- Log-only handlers are allowed only when a nearby comment states why the invariant remains true.

## Typed subtree

The first typed subtree is intentionally small and stable:

- `api/metrics.py`
- `pipeline/summary_freshness.py`
- `scripts/analyze_pipeline_profile.py`

Run:

```bash
cd <REPO_ROOT>
./.venv/bin/mypy api/metrics.py pipeline/summary_freshness.py scripts/analyze_pipeline_profile.py
```

## Formatting

Python formatting uses Ruff only:

```bash
cd <REPO_ROOT>
./.venv/bin/ruff format --check api pipeline scripts tests
```

## How to add a new guardrail

When a smell recurs:

1. Add the smallest rule or smell test that catches it.
2. Prefer extending existing test helpers and config instead of adding a new framework.
3. Add the verification command to the change summary.
4. Update `AGENTS.md` only if the contributor workflow needs to change.
