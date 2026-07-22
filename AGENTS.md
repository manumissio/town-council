# AGENTS.md

This file is the AI collaboration contract for this repository.

<project_identity>
Town Council is a local-first civic data platform for crawling, extracting, indexing, and analyzing local government meeting records. Treat `README.md`, `ARCHITECTURE.md`, `SECURITY.md`, `docs/OPERATIONS.md`, `docs/PERFORMANCE.md`, `docs/ENGINEERING_GUARDRAILS.md`, `docs/TESTING.md`, `docs/DATA_GOVERNANCE.md`, and `ROADMAP.md` as canonical references.

Keep this file focused on repo-applicable operating policy: project constraints, commands, verification, quality rules, and reporting expectations. Do not use it for agent persona, chat-style output templates, session notes, or implementation logs.
</project_identity>

<hierarchy_of_truth>
1. Code for Behavior: For implementation details, function signatures, schemas, and active defaults, the codebase and tests are the descriptive ground truth. If documentation contradicts the code regarding how a feature works, assume the code is correct and update the documentation. Code is ground truth for *behavior only*; it is not a style guide for new structure. Structural idioms listed in `<known_antipatterns>` must not be replicated in new or modified code, even where they dominate the existing codebase.
2. AGENTS.md for Agent Policy: For agent workflow, repository constraints, action permissions, verification routing, and reporting requirements, this document is the prescriptive entrypoint.
3. ENGINEERING_GUARDRAILS.md for Guardrail Policy: For static-analysis scope, typed-subtree membership, boundary exception policy, formatter path scope, smell-test coverage, and guardrail exception handling, `docs/ENGINEERING_GUARDRAILS.md` is canonical. If this file and `docs/ENGINEERING_GUARDRAILS.md` conflict on guardrail specifics, treat `docs/ENGINEERING_GUARDRAILS.md` as correct and update this file.
4. Product and Architecture Docs: Treat `README.md`, `ARCHITECTURE.md`, `docs/OPERATIONS.md`, `docs/PERFORMANCE.md`, and `ROADMAP.md` as canonical for their stated domains.
5. Asymmetric Conflict Resolution: If code appears to violate a stated policy invariant, do not immediately rewrite the code. Flag the violation, ask whether the policy is still current, and enforce the constraint only if confirmed.
6. Direct task instructions from the operator supersede this file. This root file supersedes any nested subdirectory AGENTS.md when policy conflicts exist.
</hierarchy_of_truth>

<hard_invariants>
Do:
- Keep local-first defaults for contributor workflows.
- Treat optional remote acceleration as personal opt-in only.
- Fail fast when remote inference is unreachable.
- Preserve soak comparability unless the task explicitly changes baseline policy.

Don't:
- Do not silently fall back from remote to local inference.
- Do not change runtime defaults, gate semantics, or soak policy as an incidental side effect.
- Do not run destructive git actions unless explicitly requested.
- Do not bypass commit hooks or recommend `--no-verify`.
</hard_invariants>

<known_antipatterns>
These structures exist in the current codebase and are being removed (see
`docs/ADR.md`, "Test patch points are not a public API"). Do not replicate
them in new or materially modified code. Do not preserve them when a task
authorizes their removal.

- Bidirectional module-global synchronization: paired `_sync_X_from_Y` /
  `_sync_Y_from_X` functions reconciling duplicated globals between a facade
  and its implementation module. One module owns state; others import it.
- Test-seam re-exports: `from module import name as name` blocks or facade
  wrapper functions whose only purpose is to preserve historical monkeypatch
  targets. If a test breaks because a symbol moved, repoint the test at the
  implementation module instead (`docs/TESTING.md`).
- Patchability parameters: adding injectable-callable parameters to a
  function signature so tests can substitute internals. Fake at approved
  boundaries (DB session factory, Celery dispatch, inference provider,
  Meilisearch client) instead.
- Conditional splat forwarding: `**({...} if x is not None else {})` chains
  that duplicate a callee's signature and defaults in a wrapper. Call the
  callee directly or re-export it without a wrapper.
- Duplicated implementations held in sync by convention: copying a function
  into a second module and relying on manual synchronization. Extract to one
  location and import.
- Stdlib or dependency re-binding through project modules (for example
  `hmac = app_setup.hmac`). Import from the source.
</known_antipatterns>

<action_permissions>
Allowed without confirmation:
- Read, grep, stat, or inspect files.
- Run a single-file lint or typecheck.
- Run a single targeted test from the verification matrix.
- Run the full pytest suite (`PYTHONPATH=. .venv/bin/pytest -q`) when a task's
  verification requires it or before handoff on cross-cutting changes.
- Create local scratch files under an ignored temporary path when needed for analysis.

Require explicit user confirmation before running:
- Package installs (`pip`, `apt`, `npm`, etc.).
- `git commit`, `git push`, `git reset`, `git clean`, or `git stash drop`.
- Deleting, moving, or renaming tracked files.
- Broad refactors not explicitly requested in the task.
</action_permissions>

<path_policy>
Do:
- Use repo-relative paths in guidance, for example `pipeline/llm_provider.py`.
- Use `<REPO_ROOT>` placeholders in command templates.
- Keep machine-specific runtime paths in untracked local files or checked-in `.example` templates.

Don't:
- Do not commit personal absolute paths.
- Do not hardcode user-specific paths in shared docs, tests, or scripts.
</path_policy>

<protected_paths>
- Do not edit generated or derived artifacts unless the task explicitly requires it.
- If generated artifacts change, report the regeneration command, reason for regeneration, and verification that source and generated outputs are consistent.
- Do not perform broad repository cleanup, formatting sweeps, import sorting, or refactors unrelated to the requested change.
</protected_paths>

<runtime_policy>
- Default runtime model is `gemma-3-270m-custom`.
- `gemma3:1b` is explicit opt-in only.
- Model selection, cascading, or fallback policy is not baseline policy unless explicitly updated in roadmap/runbooks.
- Preserve soak comparability by avoiding default policy drift.
</runtime_policy>

<soak_baseline_rules>
- Baseline-valid runs use consistent baseline conditions across days.
- Non-baseline runs include probes/manual experiments and are diagnostic only.
- Extract failures are non-gating warnings.
- Segment and summarize failures are gating.
- Promotion decisions must use baseline-valid data.
</soak_baseline_rules>

<telemetry_rules>
- Under prefork, provider telemetry is exported through Redis-backed aggregates (`tc_provider_*` visibility).
- TTFT/TPS are observational unless promoted to gates in docs policy.
- Missing worker metrics must be reported as reduced confidence, not treated as equivalent data quality.
</telemetry_rules>

<workflow_contract>
Do:
- Keep changes small, scoped, and reversible.
- Make one logical change, run its verification row, confirm pass, then proceed to the next change.
- Run targeted verification before completion.
- Report exact commands and outcomes.
- Run `./.venv/bin/ruff check .` when changing Python code, guardrail config, or guardrail workflow files.
- Run `./.venv/bin/mypy` when changing the typed subtree or type-check config.
- When task scope, affected files, or applicable verification row is ambiguous, stop and ask before proceeding. Do not resolve ambiguity with assumptions.
- Treat partial verification as diagnostic only; final status must come from the applicable verification matrix row(s).

Don't:
- Do not claim success without fresh evidence from the current run.
- Do not let docs drift from code behavior.
- Do not mix feature work, infrastructure changes, guardrail changes, and policy changes in one logical change set.
</workflow_contract>

<objection_protocol>
- If a requested change is insecure, violates a project invariant, or adds unnecessary architectural complexity, state `CONCERN: <specific problem>`.
- Name the concrete failure mode.
- Propose the safer or simpler alternative.
- Ask before implementing the risky approach.
- Do not silently implement a bad approach and bury the concern in a note.
</objection_protocol>

<security_sensitive_paths>
Changes touching any of the following require a trust-boundary impact
statement in the change report (what boundary is affected, what an attacker
gains or loses, which `SECURITY.md` control applies):
- `api/app_setup.py` (auth, rate limiting, lifespan checks)
- `frontend/app/api/**` and `frontend/proxy.js` (proxy key injection, CSP, origin checks)
- `docker-compose*.yml` and `Dockerfile` (port exposure, credentials, image roles)
- Any code handling `API_AUTH_KEY`, `MEILI_MASTER_KEY`, `MEILI_SEARCH_KEY`,
  Redis/Postgres credentials, or CORS configuration.
If the impact is unclear, invoke the objection protocol rather than guessing.
`SECURITY.md` is canonical for the threat model and control set.
</security_sensitive_paths>

<api_library_confidence>
- Do not invent external API calls, library methods, configuration defaults, or signatures.
- Before adding or changing dependency-facing code, verify the call against installed code, lockfiles, project docs, tests, or current upstream documentation.
- If verification is not possible, mark the call as `UNVERIFIED` and do not ship speculative code.
- If a placeholder is unavoidable, use `TODO: verify METHOD_OR_CONFIG against LIBRARY docs`.
</api_library_confidence>

<code_quality>
- Reuse or extend existing project logic before adding a new implementation.
- Remove dead code, unused imports, orphaned branches, and speculative utilities introduced by the change.
- Error handlers must take meaningful action: re-raise, wrap in a typed/domain error, return a typed failure, or log with enough context and a stated invariant.
- Use project-domain names instead of generic identifiers when a domain term exists.
- Extract meaningful magic literals to named constants unless the value is self-evident.
- Keep new or materially modified functions focused on one logical responsibility.
- Decompose new or materially modified logic before it exceeds two nesting levels, grows beyond a readable unit, or accumulates unrelated branches.
- Comments must explain intent, policy, or business logic; do not narrate syntax.
- Tests must assert observable behavior and system effects, not private implementation details or call counts.
- Negative and boundary cases identified during planning must be covered by tests or explicitly deferred with rationale.
</code_quality>

<python_directives>
- Add complete type hints for new or modified functions in the typed subtree.
- Avoid `Any` in new or modified typed-subtree code; any necessary `Any` requires an inline justification.
- Prefer `pathlib.Path` for new or materially modified filesystem code.
- Use f-strings for new or materially modified string interpolation.
- Do not use bare `except:`.
- Avoid broad `except Exception` unless the handler re-raises, wraps, returns a typed failure, or is covered by an existing documented boundary/allowlist.
- Use typed models, dataclasses, or Pydantic models at new trust boundaries instead of raw dictionary access.
- Ruff is the current lint gate. Do not claim McCabe/C90 complexity enforcement unless `ruff.toml` is updated to select the matching rule in the same policy change.
- Mypy is the current typed-subtree gate. Do not claim repo-wide strict typing unless `mypy.ini` is expanded accordingly.
</python_directives>

<status_reporting_contract>
- Use `PASS` or `FAIL` for verification outcomes.
- Do not claim a change is fixed, complete, secure, stable, or production-ready without fresh evidence from the current run.
- If tracked files are modified at handoff, report the tree as dirty and list changed paths.
- Reproduce a suspected flake before calling it transient; report the original failure and rerun outcome.
- Keep one commit to one concern; do not mix policy/guardrail changes with feature or test changes.
- Any threshold, gate, allowlist, baseline, or policy change must report old value, new value, rationale, and remaining deficit list.
- Every major claim must be independently reproducible by another engineer using minimal steps.
</status_reporting_contract>

<verification_matrix>
Scope: the matrix is a fast local pre-check for iterating on a change. The
authoritative merge gate is the full test suite run by CI on every pull
request (`python-guardrails` for Python, `frontend-tests` for the frontend).
A passing matrix row is necessary for proceeding, not sufficient for merge.
[transition: the CI full-suite and frontend jobs are delivered by remediation
tasks T-CI-1 and T-CI-2; until both merge, run the full sweep locally before
handoff on any non-trivial change.]

All commands in applicable row(s) are mandatory, not advisory.
If no row applies, run `PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py` at minimum.
Do not skip checks because a change appears trivial.
If multiple change types apply, run the union of required command sets.

Docs-only changes (`README.md`, `docs/**`, `AGENTS.md`, `ARCHITECTURE.md`):
- Required: `PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py`
- Optional (if architecture/policy text changed materially): `PYTHONPATH=. .venv/bin/pytest -q tests/test_env_example_profile_alignment.py`

Guardrail/tooling changes (`ruff.toml`, `mypy.ini`, `.pre-commit-config.yaml`, `.github/workflows/python-guardrails.yml`, `tests/test_repository_guardrails.py`):
- `./.venv/bin/ruff check .`
- `./.venv/bin/mypy`
- `PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py`
- `PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py`

API/search behavior changes (`api/**`, query contracts):
- `PYTHONPATH=. .venv/bin/pytest -q tests/test_api.py`
- `PYTHONPATH=. .venv/bin/pytest -q tests/test_query_builder_filters.py`
- `PYTHONPATH=. .venv/bin/pytest -q tests/test_query_builder_parity_search_vs_trends.py`

Pipeline/task orchestration changes (`pipeline/tasks.py`, worker flow):
- `PYTHONPATH=. .venv/bin/pytest -q tests/test_run_pipeline_orchestration.py`
- `PYTHONPATH=. .venv/bin/pytest -q tests/test_pipeline_batching.py`
- `PYTHONPATH=. .venv/bin/pytest -q tests/test_task_metrics.py`

Inference backend/provider/policy changes (`pipeline/llm.py`, `pipeline/llm_provider.py`, `pipeline/config.py`):
- `PYTHONPATH=. .venv/bin/pytest -q tests/test_inference_provider_protocol_contract.py`
- `PYTHONPATH=. .venv/bin/pytest -q tests/test_provider_error_mapping_retry_vs_fallback.py`
- `PYTHONPATH=. .venv/bin/pytest -q tests/test_llm_backend_parity_*.py`
- `PYTHONPATH=. .venv/bin/pytest -q tests/test_runtime_profiles_defaults.py`

Telemetry/metrics changes (`pipeline/metrics.py`, exporter behavior):
- `PYTHONPATH=. .venv/bin/pytest -q tests/test_provider_metrics_prefork_redis_aggregation.py`
- `PYTHONPATH=. .venv/bin/pytest -q tests/test_worker_metrics_exporter_provider_series.py`
- `PYTHONPATH=. .venv/bin/pytest -q tests/test_metrics_api.py`

Frontend contract changes (`frontend/**` affecting API/task/search behavior):
- `PYTHONPATH=. .venv/bin/pytest -q tests/test_frontend_pages_config.py`
- `PYTHONPATH=. .venv/bin/pytest -q tests/test_resultcard_agenda_status_refresh.py`
- `PYTHONPATH=. .venv/bin/pytest -q tests/test_search_sort_ui_guardrails.py`
- `PYTHONPATH=. .venv/bin/pytest -q tests/test_semantic_search_ui_guardrails.py`

Frontend component/behavior changes (`frontend/**` JS/JSX):
- `cd frontend && npm test`
  [transition: effective when the frontend test runner lands (T-CI-2)]

Broad cross-cutting changes:
- Required: run all applicable rows above.
- Required before handoff: `PYTHONPATH=. .venv/bin/pytest -q`
</verification_matrix>

<completion_checklist>
- [ ] Changed behavior has targeted tests added or updated where needed.
- [ ] Applicable verification matrix row(s) were run.
- [ ] Verification commands are reported exactly as run.
- [ ] Outcomes are reported with explicit PASS/FAIL.
- [ ] Docs were updated when behavior, contracts, commands, or policy changed.
- [ ] No drift from local-first/fail-fast invariants was introduced.
- [ ] No structures from `<known_antipatterns>` were introduced or preserved past an authorized removal.
- [ ] No personal absolute paths were introduced.
- [ ] Dirty tree status and changed paths are reported at handoff.
</completion_checklist>

<change_reporting_contract>
Commit/PR summaries must include:
1. What changed
2. Why
3. Risk/compat impact
4. Verification run, with exact commands and PASS/FAIL outcomes
5. Remaining deficits or deferred checks, if any
</change_reporting_contract>

<docs_sync_rules>
- English docs only unless explicitly requested otherwise.
- Preserve local-first defaults in docs and examples.
- Update operational metadata markers (`Last updated`) when materially changing runbooks.
- Commands, gates, and workflow guidance in docs must reflect current repository reality.
- Do not duplicate Entry Points / Code Map content from `ARCHITECTURE.md` into `AGENTS.md`; `AGENTS.md` defines constraints/workflow, `ARCHITECTURE.md` defines system map.
- File-set enumerations (typed subtree, formatter scope, smell-test scope) live in machine-readable config only (`mypy.ini`, `ruff.toml`, guardrail test constants). Docs reference the config location; they never duplicate the list.
</docs_sync_rules>

<maintenance>
Update this file when:
- runtime default policy changes,
- soak gate semantics change,
- verification matrix rows change,
- guardrail or policy enforcement changes,
- security boundary, testing policy, or data governance policy changes,
- roadmap sequencing or policy changes.

Keep this file concise and link to canonical docs for details.
Do not add session notes, implementation logs, or "what was done" summaries to this file. AGENTS.md defines constraints; it is not a changelog.
</maintenance>
