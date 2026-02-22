# AGENTS.md

This file is the AI collaboration contract for this repository.

<project_identity>
Town Council is a local-first civic data platform for crawling, extracting, indexing, and analyzing local meeting records. Treat `README.md`, `ARCHITECTURE.md`, `docs/OPERATIONS.md`, `docs/PERFORMANCE.md`, and `ROADMAP.md` as canonical references.
</project_identity>

<hierarchy_of_truth>
1. Code for Behavior: For implementation details, function signatures, schemas, and active defaults, the codebase and tests are the descriptive ground truth. If documentation contradicts the code regarding how a feature works, assume the code is correct and update the documentation.
2. AGENTS.md for Policy: For project constraints (e.g., local-first architecture, no silent remote fallbacks), this document is the prescriptive ground truth.
3. Asymmetric Conflict Resolution: If you observe the code violating a stated policy invariant in this file, DO NOT immediately rewrite the code. You must flag the violation to the user, ask if the policy is still current, and only enforce the constraint if the user confirms it.
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

Don't:
- Do not claim success without evidence.
- Do not let docs drift from code behavior.
</workflow_contract>

<docs_sync_rules>
- English docs only unless explicitly requested otherwise.
- Preserve local-first defaults in docs and examples.
- Update operational metadata markers (`Last updated`) when materially changing runbooks.
</docs_sync_rules>

<maintenance>
Update this file when:
- runtime default policy changes,
- soak gate semantics change,
- roadmap sequencing or policy changes.

Keep this file concise and link to canonical docs for details.
</maintenance>
