# Testing Policy

This document operationalizes the ADR "Test patch points are not a public
API" (`docs/ADR.md`, decision gate G3). `AGENTS.md` `<code_quality>` states
the principle — tests assert observable behavior, not private implementation
details — and this document says how to do that in this repository.

Status: initial version, effective with the G3 ADR. During remediation
Phase 2, tests are actively migrated to these rules; new tests must follow
them immediately.

## The core rule

Production code is never shaped to preserve a test's patch target. If a
symbol moves or a facade is deleted, the test repoints; the code does not
grow re-exports, wrappers, injectable-callable parameters, or sync globals
to keep old patches alive (`AGENTS.md` `<known_antipatterns>`).

## Approved fake boundaries

Substitute behavior at these seams and only these seams. Each is a real
architectural boundary that exists for production reasons, not a seam
invented for tests.

| Boundary              | Substitute via                                          |
|-----------------------|---------------------------------------------------------|
| Database              | Session factory injection / test sessionmaker; SQLite or a test Postgres per existing conftest patterns |
| Celery dispatch       | Patch `celery_app.send_task` / task `.delay` at `api/task_dispatch.py` or use Celery eager mode |
| Inference / LLM       | Fake provider implementing `pipeline/inference_provider_contract.py` |
| Meilisearch           | Patch the client object where it is constructed (`api/search/support_core.py`, `pipeline/indexer.py`) |
| Outbound HTTP         | `httpx`/`requests` transport mocks at the call site      |
| Clock                 | Pass/patch time at the function under test, not globally |
| Filesystem            | `tmp_path` fixtures                                      |

Needing to fake something not on this list is a design signal: either the
list needs a deliberate addition (own PR, update this table) or the code
under test is reaching through a boundary it shouldn't.

## Patch-target rules

1. Patch the implementation module, not a facade or re-export
   (`pipeline.metrics_redis_backend._redis_client`, not a copy synced into
   `pipeline.metrics`).
2. Patch where the name is *looked up*, respecting Python's import-binding
   semantics — but if honoring that rule requires patching a facade
   re-export, fix the import style (import the module, call
   `module.function`) rather than entrenching the re-export.
3. Never assert call counts or private call sequences unless the
   interaction *is* the contract (e.g., "exactly one enqueue per catalog"
   is a contract; "helper A called helper B" is not).
4. One behavior per test; name the test after the behavior, matching the
   existing `test_<area>_<behavior>` convention.

## Test taxonomy and where things live

- `tests/` is flat and behavior-named; keep it that way.
- Shared fixtures belong in `tests/conftest.py`; single-file fixtures stay
  local. Do not build a fixture framework (`AGENTS.md` GED-style minimalism
  applies to test code too).
- Guardrail/policy tests (`test_repository_guardrails.py`,
  `test_config_cleanup.py`, etc.) are CI fast-fail steps and also run in the
  full suite.
- Frontend tests live in `frontend/components/__tests__/` and run via
  `cd frontend && npm test`.

## Verification layers

1. Local, while iterating: the applicable `AGENTS.md` verification-matrix
   row(s). Fast, targeted, mandatory.
2. Local, before handoff on cross-cutting work: full suite,
   `PYTHONPATH=. .venv/bin/pytest -q`.
3. CI, authoritative merge gate: full Python suite + guardrail fast-fail
   steps + frontend suite + coverage threshold (`.coveragerc`
   `fail_under`).

A change is "verified" only at layer 3. Layers 1–2 are diagnostic (matching
the existing `AGENTS.md` workflow contract).

## Flakes

Reproduce before declaring transient (`AGENTS.md` status-reporting
contract). A reproduced flake gets an issue and either a fix or a documented
quarantine with owner and revisit date — never a silent retry loop or a
skip without a linked issue.

## Coverage

`.coveragerc` owns the production file scope, subprocess measurement, and the
enforced `fail_under = 71` floor. Reproduce the CI gate locally with:

```bash
PYTHONPATH=. .venv/bin/python -m pytest -q --cov \
  --cov-config=.coveragerc \
  --cov-report=term-missing:skip-covered \
  tests/
```

Raising the floor is a ratchet decision: report old value, new value, and
rationale per the status-reporting contract. Do not chase coverage with
assertion-free tests; the floor exists to catch untested new production
modules, not to be gamed.
