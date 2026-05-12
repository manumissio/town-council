# Engineering Guardrails

Town Council uses a layered guardrail system to reduce low-signal code smells before they land in `master`.

## Local command

Run the Python-first guardrails before opening a PR:

```bash
cd <REPO_ROOT>
./.venv/bin/ruff check api pipeline scripts tests
./.venv/bin/mypy
PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py
```

## What the static checks block

- unused imports and unused locals
- mutable defaults and a small set of high-signal bug patterns
- bare `except:` blocks
- broad `except Exception` handlers outside approved boundary files

The first pass is intentionally moderate. It is meant to block lazy hygiene regressions without forcing a repo-wide style migration.

## Optional local dead-code and complexity audit

`pipeline/requirements-dev.txt` pins the local audit tools used during Batch E:

- `vulture==2.16`
- `radon==6.0.1`

These commands are advisory local audits, not CI gates:

```bash
cd <REPO_ROOT>
./.venv/bin/python -m vulture api pipeline scripts tests --min-confidence 80
./.venv/bin/python -m radon cc api pipeline scripts -s -n C
```

## What the smell tests protect

- no personal absolute paths in tracked repo files
- no import-time logging configuration in reusable pipeline modules
- no raw `print(...)` in non-CLI pipeline modules
- no silent broad exception handlers or broad exception allowlist drift
- existing Town Council policy tests for fail-fast runtime behavior, freshness contracts, and profile comparability
- cleanup module families for downloader, NLP entities, segment-city CLI, hydration CLIs, models, DB migrations, LocalAI, indexing, semantic backends and service helpers, summary text and backfill, vote extraction, provider/person utilities, reporting/profile scripts, shared helper utilities, agenda QA, task/API/search helpers, onboarding/repair scripts, and prior facade splits stay under the 300-line target

Batch G cleanup coverage includes:
- semantic service facade and helpers: `semantic_service/main.py`, `semantic_service/candidates.py`, `semantic_service/filters.py`, `semantic_service/retrieval.py`, `semantic_service/hydration.py`
- semantic service helpers must not import `semantic_service.main`; dependencies flow from the route facade into helpers

Batch F cleanup coverage includes:
- search-read facade and helpers: `api/search_read_routes.py`, `api/search_read_meilisearch.py`, `api/search_read_params.py`, `api/search_read_results.py`
- city coverage facade and helpers: `pipeline/city_coverage_audit.py`, `pipeline/city_coverage_assembly.py`, `pipeline/city_coverage_buckets.py`, `pipeline/city_coverage_contracts.py`, `pipeline/city_coverage_queries.py`, `pipeline/city_coverage_windows.py`
- lineage facade and helpers: `pipeline/lineage_service.py`, `pipeline/lineage_assignment.py`, `pipeline/lineage_graph.py`
- operator A/B facade and aggregation helper: `scripts/operator_profile_ab.py`, `scripts/operator_profile_ab_aggregate.py`

Batch E cleanup coverage includes:
- reporting facades and helpers: `scripts/evaluate_soak_week.py`, `scripts/evaluate_soak_week_gates.py`, `scripts/collect_ab_results.py`, `scripts/collect_ab_results_rows.py`
- shared helper utilities: `pipeline/cli_logging.py`, `scripts/operator_numeric.py`
- agenda QA/scoring surfaces: `pipeline/agenda_qa.py`, `pipeline/agenda_resolver_quality.py`, `pipeline/utils_names.py`

## How to request an exception

Keep exceptions narrow and path-specific.

- For stdout-driven operator tools, document why stdout is the contract.
- For broader exception handling, keep it in an approved boundary file, log with context, and explain what invariant remains true.
- Remove path-specific suppressions only when both the current lint checks and the guardrail tests prove they are stale, instead of letting exception lists drift forward indefinitely.
- Do not add broad repo-wide ignores when a per-path exception is enough.

## Boundary exception handlers

Boundary handlers are limited to runtime, provider, exporter, maintenance, and operator-entrypoint edges where the code is isolating an unstable dependency.

- If the handler can preserve the caller contract, log with context and return a typed failure payload.
- If the handler cannot preserve the contract safely, log with context and re-raise.
- Log-only handlers are allowed only when a nearby comment states why the invariant remains true.
- Summary hydration embed dispatch is an approved best-effort boundary because summary writes are already durable before enqueue attempts.

## Typed subtree

The first typed subtree is intentionally small and stable:

- `api/metrics.py`
- `api/search/query_builder.py`
- `pipeline/config.py`
- `pipeline/config_env.py`
- `pipeline/config_startup.py`
- `pipeline/config_inference.py`
- `pipeline/config_semantic.py`
- `pipeline/config_processing.py`
- `pipeline/config_topic_similarity.py`
- `pipeline/config_table.py`
- `pipeline/agenda_crosscheck.py`
- `pipeline/agenda_legistar.py`
- `pipeline/agenda_resolver.py`
- `pipeline/agenda_resolver_contracts.py`
- `pipeline/agenda_resolver_quality.py`
- `pipeline/agenda_resolver_legistar_policy.py`
- `pipeline/agenda_resolver_html.py`
- `pipeline/agenda_resolver_enrichment.py`
- `pipeline/agenda_resolver_runner.py`
- `pipeline/city_scope.py`
- `pipeline/content_hash.py`
- `pipeline/document_kinds.py`
- `pipeline/agenda_service.py`
- `pipeline/agenda_verification_model_access.py`
- `pipeline/extraction_service.py`
- `pipeline/extraction_state.py`
- `pipeline/maintenance_run_status.py`
- `pipeline/models.py`
- `pipeline/model_base.py`
- `pipeline/model_runtime.py`
- `pipeline/model_civic.py`
- `pipeline/model_events.py`
- `pipeline/model_records.py`
- `pipeline/profiling.py`
- `pipeline/rollout_registry.py`
- `pipeline/runtime_guardrails.py`
- `pipeline/summary_hydration_diagnostics.py`
- `pipeline/summary_hydration_diagnostic_contracts.py`
- `pipeline/summary_hydration_diagnostic_policy.py`
- `pipeline/summary_hydration_diagnostic_queries.py`
- `pipeline/summary_hydration_diagnostic_samples.py`
- `pipeline/summary_hydration_diagnostic_builder.py`
- `pipeline/profile_manifest.py`
- `pipeline/profile_manifest_contracts.py`
- `pipeline/profile_manifest_io.py`
- `pipeline/profile_manifest_candidates.py`
- `pipeline/profile_manifest_people.py`
- `pipeline/profile_manifest_builder.py`
- `pipeline/profile_manifest_preconditioning.py`
- `pipeline/topic_generation.py`
- `pipeline/topic_generation_contracts.py`
- `pipeline/topic_generation_text.py`
- `pipeline/topic_generation_keywords.py`
- `pipeline/topic_generation_task.py`
- `pipeline/topic_generation_batch.py`
- `pipeline/summary_quality.py`
- `pipeline/summary_freshness.py`
- `pipeline/utils.py`
- `pipeline/verification_service.py`
- `pipeline/vote_extractor.py`
- `pipeline/vote_extraction_contracts.py`
- `pipeline/vote_extraction_prompting.py`
- `pipeline/vote_extraction_parser.py`
- `pipeline/vote_extraction_context.py`
- `pipeline/vote_extraction_policy.py`
- `pipeline/vote_extraction_runner.py`
- `pipeline/vote_extraction_item.py`
- `scripts/analyze_pipeline_profile.py`

Run:

```bash
cd <REPO_ROOT>
./.venv/bin/mypy
```

## Formatting

Python formatting uses Ruff only:

```bash
cd <REPO_ROOT>
./.venv/bin/ruff format --check api/metrics.py api/search/query_builder.py pipeline/config.py pipeline/config_env.py pipeline/config_startup.py pipeline/config_inference.py pipeline/config_semantic.py pipeline/config_processing.py pipeline/config_topic_similarity.py pipeline/config_table.py pipeline/agenda_crosscheck.py pipeline/agenda_legistar.py pipeline/agenda_resolver.py pipeline/agenda_resolver_contracts.py pipeline/agenda_resolver_quality.py pipeline/agenda_resolver_legistar_policy.py pipeline/agenda_resolver_html.py pipeline/agenda_resolver_enrichment.py pipeline/agenda_resolver_runner.py pipeline/city_scope.py pipeline/content_hash.py pipeline/document_kinds.py pipeline/agenda_service.py pipeline/agenda_verification_model_access.py pipeline/extraction_service.py pipeline/extraction_state.py pipeline/maintenance_run_status.py pipeline/models.py pipeline/model_base.py pipeline/model_runtime.py pipeline/model_civic.py pipeline/model_events.py pipeline/model_records.py pipeline/profiling.py pipeline/rollout_registry.py pipeline/runtime_guardrails.py pipeline/summary_hydration_diagnostics.py pipeline/summary_hydration_diagnostic_contracts.py pipeline/summary_hydration_diagnostic_policy.py pipeline/summary_hydration_diagnostic_queries.py pipeline/summary_hydration_diagnostic_samples.py pipeline/summary_hydration_diagnostic_builder.py pipeline/profile_manifest.py pipeline/profile_manifest_contracts.py pipeline/profile_manifest_io.py pipeline/profile_manifest_candidates.py pipeline/profile_manifest_people.py pipeline/profile_manifest_builder.py pipeline/profile_manifest_preconditioning.py pipeline/topic_generation.py pipeline/topic_generation_contracts.py pipeline/topic_generation_text.py pipeline/topic_generation_keywords.py pipeline/topic_generation_task.py pipeline/topic_generation_batch.py pipeline/summary_quality.py pipeline/summary_freshness.py pipeline/utils.py pipeline/verification_service.py pipeline/vote_extractor.py pipeline/vote_extraction_contracts.py pipeline/vote_extraction_prompting.py pipeline/vote_extraction_parser.py pipeline/vote_extraction_context.py pipeline/vote_extraction_policy.py pipeline/vote_extraction_runner.py pipeline/vote_extraction_item.py scripts/analyze_pipeline_profile.py
```

Use that exact path-scoped command as the scoped formatter guardrail for the current formatter-ready wave. Keep formatter enforcement limited to this explicit path set, and do not mix formatting with behavioral edits.

## How to add a new guardrail

When a smell recurs:

1. Add the smallest rule or smell test that catches it.
2. Prefer extending existing test helpers and config instead of adding a new framework.
3. Add the verification command to the change summary.
4. Update `AGENTS.md` only if the contributor workflow needs to change.
