# AGENTS.md

This file is the AI collaboration contract for this repository.

<project_identity>
Town Council is a local-first civic data platform for crawling, extracting, indexing, and analyzing local meeting records. Treat `README.md`, `ARCHITECTURE.md`, `docs/OPERATIONS.md`, `docs/PERFORMANCE.md`, and `ROADMAP.md` as canonical references.
</project_identity>

<hierarchy_of_truth>
1. Code for Behavior: For implementation details, function signatures, schemas, and active defaults, the codebase and tests are the descriptive ground truth. If documentation contradicts the code regarding how a feature works, assume the code is correct and update the documentation.
2. AGENTS.md for Policy: For project constraints (e.g., local-first architecture, no silent remote fallbacks), this document is the prescriptive ground truth.
3. Asymmetric Conflict Resolution: If you observe the code violating a stated policy invariant in this file, DO NOT immediately rewrite the code. You must flag the violation to the user, ask if the policy is still current, and only enforce the constraint if the user confirms it.
4. Direct task instructions from the operator supersede this file. This file supersedes any nested subdirectory AGENTS.md.
</hierarchy_of_truth>

<hard_invariants>
Do:
- Keep local-first defaults for contributor workflows.
- Treat optional remote acceleration as personal opt-in only.
- Fail fast when remote inference is unreachable.

Don't:
- Do not silently fallback from remote to local inference.
- Do not run destructive git actions unless explicitly requested.
</hard_invariants>

<action_permissions>
Allowed without confirmation:
- Read, grep, or stat files
- Run a single-file lint or typecheck
- Run a single targeted test from the verification matrix

Require explicit user confirmation before running:
- Package installs (pip, apt, npm)
- git commit, git push, git stash drop
- Deleting or moving files
- Running the full pytest suite (PYTHONPATH=. .venv/bin/pytest -q)
- Any broad refactor not explicitly requested in the task
</action_permissions>

<path_policy>
Do:
- Use repo-relative paths in guidance (for example `pipeline/llm_provider.py`).
- Use `<REPO_ROOT>` placeholders in command templates.

Don't:
- Do not commit personal absolute paths.
- Do not hardcode user-specific paths in shared docs or scripts.

Note:
- If local OS tooling requires an absolute path (for example launchd), keep it in local untracked files or `.example` templates.
</path_policy>

<protected_paths>
- Do not edit generated/derived artifacts unless the task explicitly requires it.
- If generated artifacts are changed, include regeneration command used, reason for regeneration, and verification that source and generated outputs are consistent.
- Do not perform broad repository cleanup/refactors unrelated to the requested change.
</protected_paths>

<runtime_policy>
- Default runtime model is `gemma-3-270m-custom`.
- `gemma3:1b` is explicit opt-in only.
- Model-selection/cascading is not baseline policy unless explicitly updated in roadmap/runbooks.
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
- Keep changes small and scoped.
- Run targeted verification before completion.
- Report exact commands and outcomes.
- When task scope, affected files, or applicable verification row is ambiguous, stop and ask before proceeding. Do not resolve ambiguity with assumptions.
- Make one logical change, run its verification row, confirm pass, then proceed to the next change.
- All verification commands must be reported exactly as run, with pass/fail outcome.

Don't:
- Do not claim success without evidence.
- Do not let docs drift from code behavior.
</workflow_contract>

<verification_matrix>
All commands in applicable row(s) are mandatory, not advisory.
If no row applies, run `PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py` at minimum.
Do not skip checks because a change appears trivial.
If multiple change types apply, run the union of required command sets.

Docs-only changes (`README.md`, `docs/**`, `AGENTS.md`, `ARCHITECTURE.md`):
- Required: `PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py`
- Optional (if architecture/policy text changed materially): `PYTHONPATH=. .venv/bin/pytest -q tests/test_env_example_profile_alignment.py`

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

Broad cross-cutting changes:
- Required: run all applicable rows above.
- Optional full sweep (state why): `PYTHONPATH=. .venv/bin/pytest -q`
</verification_matrix>

<completion_checklist>
- [ ] Changed behavior has targeted tests added/updated where needed.
- [ ] Verification commands were run with exact command strings.
- [ ] Outcomes reported with explicit pass/fail.
- [ ] Docs updated when behavior/contracts changed.
- [ ] No drift from local-first/fail-fast invariants.
- [ ] No personal absolute paths were introduced.
</completion_checklist>

<change_reporting_contract>
Commit/PR summaries must include:
1. What changed
2. Why
3. Risk/compat impact
4. Verification run (exact commands + outcomes)
</change_reporting_contract>

<docs_sync_rules>
- English docs only unless explicitly requested otherwise.
- Preserve local-first defaults in docs and examples.
- Update operational metadata markers (`Last updated`) when materially changing runbooks.
- Do not duplicate Entry Points / Code Map content from `ARCHITECTURE.md` into `AGENTS.md`; `AGENTS.md` defines constraints/workflow, `ARCHITECTURE.md` defines system map.
</docs_sync_rules>

<maintenance>
Update this file when:
- runtime default policy changes,
- soak gate semantics change,
- roadmap sequencing or policy changes.

Keep this file concise and link to canonical docs for details.
Do not add session notes, implementation logs, or "what was done" summaries to this file. AGENTS.md defines constraints; it is not a changelog.
</maintenance>
