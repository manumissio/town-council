from __future__ import annotations

import ast
import re
import subprocess
import tomllib
import tokenize
from io import StringIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_FILE_SUFFIXES = {
    ".md",
    ".plist",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
GUARDRAIL_SCAN_PREFIXES = {"api", "pipeline", "scripts", "tests", "docs", "ops", "experiments"}
FACADE_IMPORT_PACKAGE_ROOTS = ("api", "pipeline", "scripts", "semantic_service", "tests")
PERSONAL_PATH_PATTERNS = (
    re.compile(r"/Users/[^/\s]+/"),
    re.compile(r"/home/[^/\s]+/"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\[^\\\s]+\\\\"),
    re.compile(r"/var/folders/[A-Za-z0-9_/.-]+"),
)
APPROVED_PIPELINE_PRINT_PATHS = {
    "pipeline/backfill_orgs.py",
    "pipeline/check_faiss_runtime.py",
    "pipeline/diagnose_search_sort.py",
    "pipeline/diagnose_semantic_search.py",
    "pipeline/indexer.py",
    "pipeline/indexer_meilisearch.py",
    "pipeline/monitor.py",
    "pipeline/person_linker.py",
    "pipeline/reindex_semantic.py",
    "pipeline/run_agenda_qa.py",
    "pipeline/run_pipeline_extraction.py",
}
REUSABLE_PIPELINE_MODULES = (
    "pipeline.downloader",
    "pipeline.backfill_catalog_hashes",
    "pipeline.extractor",
    "pipeline.verification_service",
)
APPROVED_BROAD_EXCEPTION_PATHS = {
    "api/cache.py",
    "api/main.py",
    "council_crawler/council_crawler/pipelines.py",
    "council_crawler/council_crawler/spiders/base.py",
    "pipeline/agenda_legistar.py",
    "pipeline/agenda_worker.py",
    "pipeline/check_faiss_runtime.py",
    "pipeline/db_migration_runner.py",
    "pipeline/diagnose_search_sort.py",
    "pipeline/diagnose_semantic_search.py",
    "pipeline/indexer.py",
    "pipeline/indexer_meilisearch.py",
    "pipeline/llm.py",
    "pipeline/local_ai_provider_calls.py",
    "pipeline/model_base.py",
    "pipeline/run_agenda_qa.py",
    "pipeline/run_pipeline_steps.py",
    "pipeline/runtime_guardrails.py",
    "pipeline/summary_backfill_dispatch.py",
    "pipeline/semantic_tasks.py",
    "pipeline/startup_purge.py",
    "pipeline/task_startup.py",
    "pipeline/table_worker.py",
    "pipeline/tasks.py",
    "pipeline/text_cleaning.py",
    "pipeline/topic_worker.py",
    "pipeline/vote_extraction_runner.py",
    "scripts/collect_soak_metrics.py",
    "scripts/enrichment_worker_healthcheck.py",
    "scripts/hydration_repaired_summary.py",
    "scripts/parse_task_launch.py",
    "scripts/probe_local_model_candidate.py",
    "scripts/repair_san_mateo_laserfiche_backlog.py",
    "scripts/reset_laserfiche_error_agenda_rows.py",
    "scripts/score_ab_results.py",
    "scripts/semantic_worker_healthcheck.py",
}
BLE001_WILDCARD_PATHS = {"scripts/*.py", "tests/*.py"}
BROAD_EXCEPTION_RULE = "BLE001"
NOQA_DIRECTIVE = re.compile(
    r"(?<!\S)#\s*(?:(?:ruff|flake8)\s*:\s*)?noqa(?=\s|:|$)(?:\s*:\s*(?P<rules>[^#]*))?",
    re.IGNORECASE,
)
NOQA_RULE_SEPARATOR = re.compile(r"[\s,]+")
NOQA_JOINED_RULE_BOUNDARY = re.compile(r"(?<=\d)(?=[A-Z])")
NOQA_RULE_CODE = re.compile(r"[A-Z]+\d{3,4}")
TYPED_SUBTREE_PATHS = (
    "api/metrics.py",
    "api/search/query_builder.py",
    "pipeline/config.py",
    "pipeline/config_env.py",
    "pipeline/config_startup.py",
    "pipeline/config_inference.py",
    "pipeline/config_semantic.py",
    "pipeline/config_processing.py",
    "pipeline/config_topic_similarity.py",
    "pipeline/config_table.py",
    "pipeline/agenda_crosscheck.py",
    "pipeline/agenda_legistar.py",
    "pipeline/agenda_resolver.py",
    "pipeline/agenda_resolver_contracts.py",
    "pipeline/agenda_resolver_quality.py",
    "pipeline/agenda_resolver_legistar_policy.py",
    "pipeline/agenda_resolver_html.py",
    "pipeline/agenda_resolver_enrichment.py",
    "pipeline/agenda_resolver_runner.py",
    "pipeline/city_scope.py",
    "pipeline/content_hash.py",
    "pipeline/document_kinds.py",
    "pipeline/agenda_service.py",
    "pipeline/agenda_verification_model_access.py",
    "pipeline/extraction_service.py",
    "pipeline/extraction_state.py",
    "pipeline/maintenance_run_status.py",
    "pipeline/models.py",
    "pipeline/model_base.py",
    "pipeline/model_runtime.py",
    "pipeline/model_civic.py",
    "pipeline/model_events.py",
    "pipeline/model_records.py",
    "pipeline/profiling.py",
    "pipeline/rollout_registry.py",
    "pipeline/runtime_guardrails.py",
    "pipeline/summary_hydration_diagnostics.py",
    "pipeline/summary_hydration_diagnostic_contracts.py",
    "pipeline/summary_hydration_diagnostic_policy.py",
    "pipeline/summary_hydration_diagnostic_queries.py",
    "pipeline/summary_hydration_diagnostic_samples.py",
    "pipeline/summary_hydration_diagnostic_builder.py",
    "pipeline/profile_manifest.py",
    "pipeline/profile_manifest_contracts.py",
    "pipeline/profile_manifest_io.py",
    "pipeline/profile_manifest_candidates.py",
    "pipeline/profile_manifest_people.py",
    "pipeline/profile_manifest_builder.py",
    "pipeline/profile_manifest_preconditioning.py",
    "pipeline/topic_generation.py",
    "pipeline/topic_generation_contracts.py",
    "pipeline/topic_generation_text.py",
    "pipeline/topic_generation_keywords.py",
    "pipeline/topic_generation_task.py",
    "pipeline/topic_generation_batch.py",
    "pipeline/summary_quality.py",
    "pipeline/summary_freshness.py",
    "pipeline/utils.py",
    "pipeline/verification_service.py",
    "pipeline/vote_extractor.py",
    "pipeline/vote_extraction_contracts.py",
    "pipeline/vote_extraction_prompting.py",
    "pipeline/vote_extraction_parser.py",
    "pipeline/vote_extraction_context.py",
    "pipeline/vote_extraction_policy.py",
    "pipeline/vote_extraction_runner.py",
    "pipeline/vote_extraction_item.py",
    "scripts/analyze_pipeline_profile.py",
)
CANDIDATE_FORMATTER_WAVE_PATHS = TYPED_SUBTREE_PATHS
CONFIG_OWNED_FORMATTER_COMMAND = "./.venv/bin/ruff format --check ."
CONFIG_CLEANUP_MODULES = (
    "pipeline/config.py",
    "pipeline/config_env.py",
    "pipeline/config_startup.py",
    "pipeline/config_inference.py",
    "pipeline/config_semantic.py",
    "pipeline/config_processing.py",
    "pipeline/config_topic_similarity.py",
    "pipeline/config_table.py",
)
METRICS_CLEANUP_MODULES = (
    "pipeline/metrics.py",
    "pipeline/metrics_celery_signals.py",
    "pipeline/metrics_definitions.py",
    "pipeline/metrics_profile_events.py",
    "pipeline/metrics_provider_collector.py",
    "pipeline/metrics_provider_keys.py",
    "pipeline/metrics_provider_recorders.py",
    "pipeline/metrics_redis_backend.py",
    "pipeline/metrics_task_recorders.py",
)
DOWNLOADER_CLEANUP_MODULES = (
    "pipeline/downloader.py",
    "pipeline/downloader_archive.py",
    "pipeline/downloader_media.py",
    "pipeline/downloader_processing.py",
    "pipeline/downloader_selection.py",
)
AGENDA_EXTRACTION_CLEANUP_MODULES = (
    "pipeline/agenda_extraction.py",
    "pipeline/agenda_extraction_acceptance.py",
    "pipeline/agenda_extraction_diagnostics.py",
    "pipeline/agenda_extraction_fallback.py",
    "pipeline/agenda_extraction_noise.py",
    "pipeline/agenda_extraction_numbered.py",
    "pipeline/agenda_extraction_pages.py",
    "pipeline/agenda_extraction_paragraphs.py",
    "pipeline/agenda_extraction_parser.py",
)
AGENDA_TEXT_HEURISTICS_CLEANUP_MODULES = (
    "pipeline/agenda_text_heuristics.py",
    "pipeline/agenda_text_normalization.py",
    "pipeline/agenda_text_noise.py",
    "pipeline/agenda_text_noise_patterns.py",
    "pipeline/agenda_item_acceptance.py",
    "pipeline/agenda_item_dedupe.py",
    "pipeline/agenda_end_markers.py",
)
AGENDA_RESOLVER_CLEANUP_MODULES = (
    "pipeline/agenda_resolver.py",
    "pipeline/agenda_resolver_contracts.py",
    "pipeline/agenda_resolver_quality.py",
    "pipeline/agenda_resolver_legistar_policy.py",
    "pipeline/agenda_resolver_html.py",
    "pipeline/agenda_resolver_enrichment.py",
    "pipeline/agenda_resolver_runner.py",
)
AGENDA_QA_CLEANUP_MODULES = (
    "pipeline/agenda_qa.py",
)
AGENDA_SUMMARY_MAINTENANCE_CLEANUP_MODULES = (
    "pipeline/agenda_summary_maintenance.py",
    "pipeline/agenda_summary_contracts.py",
    "pipeline/agenda_summary_inputs.py",
    "pipeline/agenda_summary_callbacks.py",
    "pipeline/agenda_summary_batch.py",
    "pipeline/agenda_summary_fallback.py",
)
AGENDA_SUMMARY_RUNTIME_CLEANUP_MODULES = (
    "pipeline/agenda_summary.py",
    "pipeline/agenda_summary_items.py",
    "pipeline/agenda_summary_scaffold.py",
    "pipeline/agenda_summary_prompting.py",
    "pipeline/agenda_summary_rendering.py",
    "pipeline/agenda_summary_counters.py",
    "pipeline/agenda_summary_pipeline.py",
)
RUN_PIPELINE_CLEANUP_MODULES = (
    "pipeline/run_pipeline.py",
    "pipeline/run_pipeline_steps.py",
    "pipeline/run_pipeline_onboarding.py",
    "pipeline/run_pipeline_selectors.py",
    "pipeline/run_pipeline_extraction.py",
    "pipeline/run_pipeline_parallel.py",
)
SUMMARY_HYDRATION_DIAGNOSTIC_CLEANUP_MODULES = (
    "pipeline/summary_hydration_diagnostics.py",
    "pipeline/summary_hydration_diagnostic_contracts.py",
    "pipeline/summary_hydration_diagnostic_policy.py",
    "pipeline/summary_hydration_diagnostic_queries.py",
    "pipeline/summary_hydration_diagnostic_samples.py",
    "pipeline/summary_hydration_diagnostic_builder.py",
)
PROFILE_MANIFEST_CLEANUP_MODULES = (
    "pipeline/profile_manifest.py",
    "pipeline/profile_manifest_contracts.py",
    "pipeline/profile_manifest_io.py",
    "pipeline/profile_manifest_candidates.py",
    "pipeline/profile_manifest_people.py",
    "pipeline/profile_manifest_builder.py",
    "pipeline/profile_manifest_preconditioning.py",
)
TOPIC_GENERATION_CLEANUP_MODULES = (
    "pipeline/topic_generation.py",
    "pipeline/topic_generation_contracts.py",
    "pipeline/topic_generation_text.py",
    "pipeline/topic_generation_keywords.py",
    "pipeline/topic_generation_task.py",
    "pipeline/topic_generation_batch.py",
)
LOCAL_AI_CLEANUP_MODULES = (
    "pipeline/llm.py",
    "pipeline/local_ai_agenda_compat.py",
    "pipeline/local_ai_provider_calls.py",
)
HTTP_PROVIDER_CLEANUP_MODULES = (
    "pipeline/http_inference_provider.py",
    "pipeline/http_inference_attempts.py",
    "pipeline/http_inference_errors.py",
    "pipeline/http_inference_payloads.py",
    "pipeline/http_inference_policy.py",
    "pipeline/http_inference_telemetry.py",
)
PERSON_UTILS_CLEANUP_MODULES = (
    "pipeline/person_linker.py",
    "pipeline/person_cache.py",
    "pipeline/person_mutations.py",
    "pipeline/person_names.py",
    "pipeline/person_selectors.py",
    "pipeline/utils.py",
    "pipeline/utils_matching.py",
    "pipeline/utils_names.py",
    "pipeline/utils_ocd.py",
    "pipeline/utils_pdf.py",
)
REPORTING_SCRIPTS_CLEANUP_MODULES = (
    "scripts/analyze_pipeline_profile.py",
    "scripts/collect_ab_results.py",
    "scripts/collect_ab_results_rows.py",
    "scripts/collect_soak_metrics.py",
    "scripts/evaluate_soak_week.py",
    "scripts/evaluate_soak_week_gates.py",
    "scripts/operator_profile_ab.py",
    "scripts/operator_profile_ab_aggregate.py",
    "scripts/operator_profile_artifacts.py",
    "scripts/operator_profile_metric_deltas.py",
    "scripts/operator_profile_metrics.py",
    "scripts/operator_profile_worker_metrics.py",
    "scripts/operator_profile_reports.py",
    "scripts/operator_profile_soak_eval.py",
    "scripts/pipeline_profile_analysis.py",
    "scripts/pipeline_profile_compare.py",
    "scripts/profile_pipeline.py",
    "scripts/profile_pipeline_commands.py",
    "scripts/profile_pipeline_runner.py",
    "scripts/profile_pipeline_results.py",
    "scripts/profile_pipeline_selection.py",
    "scripts/score_ab_results.py",
)
SHARED_HELPER_CLEANUP_MODULES = (
    "pipeline/cli_logging.py",
    "scripts/operator_numeric.py",
)
TASK_API_FACADE_CLEANUP_MODULES = (
    "pipeline/tasks.py",
    "pipeline/task_facade_helpers.py",
    "pipeline/task_summary_generation.py",
    "pipeline/task_summary_side_effects.py",
    "api/task_routes.py",
    "api/task_dispatch.py",
    "api/task_route_generation.py",
    "api/task_route_segmentation.py",
    "api/task_route_summary.py",
    "api/task_route_support.py",
)
SEARCH_SUPPORT_CLEANUP_MODULES = (
    "api/search_support.py",
    "api/search_read_routes.py",
    "api/search_read_meilisearch.py",
    "api/search_read_params.py",
    "api/search_read_results.py",
    "api/search/support_core.py",
    "api/search/filter_support.py",
    "api/search/trends_support.py",
    "api/search/semantic_support.py",
)
CITY_COVERAGE_CLEANUP_MODULES = (
    "pipeline/city_coverage_audit.py",
    "pipeline/city_coverage_assembly.py",
    "pipeline/city_coverage_buckets.py",
    "pipeline/city_coverage_contracts.py",
    "pipeline/city_coverage_queries.py",
    "pipeline/city_coverage_windows.py",
)
LINEAGE_CLEANUP_MODULES = (
    "pipeline/lineage_service.py",
    "pipeline/lineage_assignment.py",
    "pipeline/lineage_graph.py",
)
CITY_ONBOARDING_EVALUATOR_CLEANUP_MODULES = (
    "scripts/evaluate_city_onboarding.py",
    "pipeline/city_onboarding_metrics.py",
    "pipeline/city_onboarding_gate.py",
)
LASERFICHE_REPAIR_CLEANUP_MODULES = (
    "scripts/repair_san_mateo_laserfiche_backlog.py",
    "scripts/laserfiche_repair_contracts.py",
    "scripts/laserfiche_repair_pdf_io.py",
    "scripts/laserfiche_repair_downloads.py",
    "scripts/laserfiche_repair_generated_pdf.py",
    "scripts/laserfiche_repair_backlog.py",
    "scripts/laserfiche_repair_reporting.py",
)
SEGMENT_CITY_CORPUS_CLEANUP_MODULES = (
    "scripts/segment_city_corpus.py",
    "scripts/segment_city_contracts.py",
    "scripts/segment_city_selection.py",
    "scripts/segment_city_worker.py",
    "scripts/segment_city_runner.py",
)
HYDRATION_CLI_CLEANUP_MODULES = (
    "scripts/staged_hydrate_cities.py",
    "scripts/staged_hydration_segment.py",
    "scripts/staged_hydration_runner.py",
    "scripts/staged_hydration_output.py",
    "scripts/hydrate_repaired_city_catalogs.py",
    "scripts/hydration_counts.py",
    "scripts/hydration_output.py",
    "scripts/hydration_repaired_selectors.py",
    "scripts/hydration_repaired_extract.py",
    "scripts/hydration_repaired_segment.py",
    "scripts/hydration_repaired_summary.py",
    "scripts/hydration_repaired_runner.py",
)
MODEL_CLEANUP_MODULES = (
    "pipeline/models.py",
    "pipeline/model_base.py",
    "pipeline/model_runtime.py",
    "pipeline/model_civic.py",
    "pipeline/model_events.py",
    "pipeline/model_records.py",
)
DB_MIGRATION_CLEANUP_MODULES = (
    "pipeline/db_migrate.py",
    "pipeline/db_migration_columns.py",
    "pipeline/db_migration_backfills.py",
    "pipeline/db_migration_runner.py",
    "pipeline/migrate_v8.py",
    "pipeline/migrate_v9.py",
    "pipeline/migration_pgvector_semantic_embeddings.py",
    "pipeline/migration_catalog_lineage_columns.py",
)
INDEXER_CLEANUP_MODULES = (
    "pipeline/indexer.py",
    "pipeline/indexer_documents.py",
    "pipeline/indexer_meilisearch.py",
)
SEMANTIC_BACKEND_CLEANUP_MODULES = (
    "pipeline/semantic_faiss_backend.py",
    "pipeline/semantic_faiss_artifacts.py",
    "pipeline/semantic_faiss_rows.py",
    "pipeline/semantic_pgvector_backend.py",
    "pipeline/semantic_pgvector_rows.py",
    "pipeline/semantic_pgvector_rerank.py",
)
SEMANTIC_SERVICE_CLEANUP_MODULES = (
    "semantic_service/main.py",
    "semantic_service/candidates.py",
    "semantic_service/filters.py",
    "semantic_service/retrieval.py",
    "semantic_service/hydration.py",
)
SUMMARY_TEXT_CLEANUP_MODULES = (
    "pipeline/text_generation.py",
    "pipeline/summary_text_formatting.py",
    "pipeline/summary_text_prompting.py",
    "pipeline/summary_quality.py",
    "pipeline/summary_source_quality.py",
    "pipeline/summary_grounding.py",
    "pipeline/summary_backfill.py",
    "pipeline/summary_backfill_queries.py",
    "pipeline/summary_backfill_dispatch.py",
    "pipeline/summary_backfill_runner.py",
    "pipeline/summary_backfill_progress.py",
    "pipeline/summary_backfill_logging.py",
)
VOTE_EXTRACTION_CLEANUP_MODULES = (
    "pipeline/vote_extractor.py",
    "pipeline/vote_extraction_contracts.py",
    "pipeline/vote_extraction_prompting.py",
    "pipeline/vote_extraction_parser.py",
    "pipeline/vote_extraction_context.py",
    "pipeline/vote_extraction_policy.py",
    "pipeline/vote_extraction_runner.py",
    "pipeline/vote_extraction_item.py",
)
NLP_ENTITY_CLEANUP_MODULES = (
    "pipeline/nlp_worker.py",
    "pipeline/nlp_entity_candidates.py",
    "pipeline/nlp_entity_extraction.py",
    "pipeline/nlp_entity_model.py",
)


def _tracked_files() -> list[Path]:
    output = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True)
    return [ROOT / line for line in output.splitlines() if line]


def _noqa_rules_suppress_broad_exception(directive_rules: str) -> bool:
    for rule_fragment in NOQA_RULE_SEPARATOR.split(directive_rules):
        if not rule_fragment:
            continue
        joined_rule_codes = NOQA_JOINED_RULE_BOUNDARY.split(rule_fragment)
        if not all(NOQA_RULE_CODE.fullmatch(rule_code) for rule_code in joined_rule_codes):
            return False
        if BROAD_EXCEPTION_RULE in joined_rule_codes:
            return True
    return False


def _comment_suppresses_broad_exception(comment_text: str) -> bool:
    for directive_match in NOQA_DIRECTIVE.finditer(comment_text):
        directive_rules = directive_match.group("rules")
        if directive_rules is None:
            return True
        if _noqa_rules_suppress_broad_exception(directive_rules):
            return True
    return False


def _broad_exception_suppression_lines(python_path: Path) -> list[int]:
    python_source = python_path.read_text(encoding="utf-8")
    python_tokens = tokenize.generate_tokens(StringIO(python_source).readline)
    return [
        python_token.start[0]
        for python_token in python_tokens
        if python_token.type == tokenize.COMMENT and _comment_suppresses_broad_exception(python_token.string)
    ]


def _broad_exception_scan_files() -> list[Path]:
    tracked_files = {path.resolve() for path in _tracked_files()}
    for module_path in (
        *CONFIG_CLEANUP_MODULES,
        *METRICS_CLEANUP_MODULES,
        *DOWNLOADER_CLEANUP_MODULES,
        *AGENDA_EXTRACTION_CLEANUP_MODULES,
        *AGENDA_TEXT_HEURISTICS_CLEANUP_MODULES,
        *AGENDA_RESOLVER_CLEANUP_MODULES,
        *AGENDA_QA_CLEANUP_MODULES,
        *AGENDA_SUMMARY_MAINTENANCE_CLEANUP_MODULES,
        *AGENDA_SUMMARY_RUNTIME_CLEANUP_MODULES,
        *PROFILE_MANIFEST_CLEANUP_MODULES,
        *TOPIC_GENERATION_CLEANUP_MODULES,
        *LOCAL_AI_CLEANUP_MODULES,
        *INDEXER_CLEANUP_MODULES,
        *SEMANTIC_BACKEND_CLEANUP_MODULES,
        *SUMMARY_TEXT_CLEANUP_MODULES,
        *VOTE_EXTRACTION_CLEANUP_MODULES,
        *NLP_ENTITY_CLEANUP_MODULES,
        *HTTP_PROVIDER_CLEANUP_MODULES,
        *PERSON_UTILS_CLEANUP_MODULES,
        *REPORTING_SCRIPTS_CLEANUP_MODULES,
        *SHARED_HELPER_CLEANUP_MODULES,
        *TASK_API_FACADE_CLEANUP_MODULES,
        *SEARCH_SUPPORT_CLEANUP_MODULES,
        *CITY_COVERAGE_CLEANUP_MODULES,
        *LINEAGE_CLEANUP_MODULES,
        *CITY_ONBOARDING_EVALUATOR_CLEANUP_MODULES,
        *LASERFICHE_REPAIR_CLEANUP_MODULES,
        *SEGMENT_CITY_CORPUS_CLEANUP_MODULES,
        *HYDRATION_CLI_CLEANUP_MODULES,
        *MODEL_CLEANUP_MODULES,
        *DB_MIGRATION_CLEANUP_MODULES,
    ):
        tracked_files.add((ROOT / module_path).resolve())
    return sorted(tracked_files)


def _python_module_paths(prefix: str) -> list[Path]:
    return sorted(
        path
        for path in _tracked_files()
        if path.suffix == ".py" and len(path.parts) > 1 and path.relative_to(ROOT).parts[0] == prefix
    )


def _exception_handler_name(handler_type: ast.expr | None) -> str | None:
    if isinstance(handler_type, ast.Name):
        return handler_type.id
    if isinstance(handler_type, ast.Attribute):
        return handler_type.attr
    return None


def _statement_is_direct_sys_exit(statement: ast.stmt) -> bool:
    return (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Call)
        and isinstance(statement.value.func, ast.Attribute)
        and isinstance(statement.value.func.value, ast.Name)
        and statement.value.func.value.id == "sys"
        and statement.value.func.attr == "exit"
    )


def _broad_exception_handler_is_approved(
    relative_path: str,
    handler: ast.ExceptHandler,
) -> bool:
    if relative_path in APPROVED_BROAD_EXCEPTION_PATHS:
        return True
    if not handler.body:
        return False
    terminal_statement = handler.body[-1]
    return isinstance(terminal_statement, ast.Raise) or _statement_is_direct_sys_exit(terminal_statement)


def _parse_ruff_per_file_ignore_entries(config_text: str) -> dict[str, set[str]]:
    ruff_config = tomllib.loads(config_text)
    lint_config = ruff_config.get("lint")
    if not isinstance(lint_config, dict):
        raise ValueError("ruff.toml must define a lint table")
    per_file_ignores = lint_config.get("per-file-ignores")
    if not isinstance(per_file_ignores, dict):
        raise ValueError("ruff.toml must define lint.per-file-ignores")

    ignore_entries: dict[str, set[str]] = {}
    for ignore_path, rule_codes in per_file_ignores.items():
        if not isinstance(ignore_path, str) or not isinstance(rule_codes, list):
            raise ValueError("lint.per-file-ignores entries must map paths to rule lists")
        if not all(isinstance(rule_code, str) for rule_code in rule_codes):
            raise ValueError(f"lint.per-file-ignores entry {ignore_path} must contain only rule strings")
        ignore_entries[ignore_path] = set(rule_codes)
    return ignore_entries


def _ruff_per_file_ignore_entries() -> dict[str, set[str]]:
    config_text = (ROOT / "ruff.toml").read_text(encoding="utf-8")
    return _parse_ruff_per_file_ignore_entries(config_text)


def _mypy_enrolled_paths() -> tuple[str, ...]:
    config_text = (ROOT / "mypy.ini").read_text(encoding="utf-8")
    enrolled_paths: list[str] = []
    in_files_block = False
    for raw_line in config_text.splitlines():
        if raw_line == "files =":
            in_files_block = True
            continue
        if not in_files_block:
            continue
        if not raw_line.startswith("    "):
            break
        path = raw_line.strip().rstrip(",")
        if path:
            enrolled_paths.append(path)
    return tuple(enrolled_paths)


def _module_name_for_path(module_path: Path) -> str:
    module_parts = module_path.with_suffix("").parts
    for package_name in FACADE_IMPORT_PACKAGE_ROOTS:
        if package_name in module_parts:
            package_index = module_parts.index(package_name)
            return ".".join(module_parts[package_index:])
    return module_path.stem


def _absolute_import_from_name(*, importing_module: str, module_name: str | None, level: int, alias_name: str) -> str:
    if level == 0:
        return module_name or alias_name

    package_parts = importing_module.split(".")[:-1]
    base_parts = package_parts[: max(0, len(package_parts) - level + 1)]
    import_parts = [part for part in (module_name or "").split(".") if part]
    if import_parts:
        return ".".join([*base_parts, *import_parts])
    return ".".join([*base_parts, alias_name])


def _forbidden_imports(module_path: Path, forbidden_modules: set[str]) -> list[str]:
    importing_module = _module_name_for_path(module_path)
    try:
        filename = str(module_path.relative_to(ROOT))
    except ValueError:
        filename = str(module_path)
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=filename)
    found_imports: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found_imports.extend(alias.name for alias in node.names if alias.name in forbidden_modules)
        elif isinstance(node, ast.ImportFrom):
            resolved_imports = [
                _absolute_import_from_name(
                    importing_module=importing_module,
                    module_name=node.module,
                    level=node.level,
                    alias_name=alias.name,
                )
                for alias in node.names
            ]
            found_imports.extend(
                resolved_import for resolved_import in resolved_imports if resolved_import in forbidden_modules
            )
            if node.level == 0 and node.module in forbidden_modules:
                found_imports.append(node.module)
            if node.level == 0 and node.module:
                found_imports.extend(
                    f"{node.module}.{alias.name}"
                    for alias in node.names
                    if f"{node.module}.{alias.name}" in forbidden_modules
                )
            if node.level == 0 and node.module:
                for forbidden_module in forbidden_modules:
                    if node.module.startswith(f"{forbidden_module}."):
                        found_imports.append(node.module)

    return found_imports


def test_tracked_text_files_do_not_contain_personal_absolute_paths():
    offending_files: list[str] = []
    for tracked_path in _broad_exception_scan_files():
        relative_path = tracked_path.relative_to(ROOT)
        if relative_path.parts[0] not in GUARDRAIL_SCAN_PREFIXES:
            continue
        if tracked_path.suffix not in TEXT_FILE_SUFFIXES:
            continue
        text = tracked_path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in PERSONAL_PATH_PATTERNS):
            if str(relative_path) == "tests/test_repository_guardrails.py":
                continue
            offending_files.append(str(relative_path))

    assert offending_files == []


def test_non_cli_pipeline_modules_do_not_use_raw_print():
    offending_paths: list[str] = []
    for tracked_path in _python_module_paths("pipeline"):
        relative_path = str(tracked_path.relative_to(ROOT))
        if relative_path in APPROVED_PIPELINE_PRINT_PATHS:
            continue
        source = tracked_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relative_path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
                offending_paths.append(relative_path)
                break

    assert offending_paths == []


def test_reusable_pipeline_modules_do_not_call_logging_basicconfig_on_import(monkeypatch):
    import importlib
    import logging
    import sys

    recorded_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def tracking_basicconfig(*args, **kwargs):
        recorded_calls.append((args, kwargs))

    monkeypatch.setattr(logging, "basicConfig", tracking_basicconfig)
    for module_name in REUSABLE_PIPELINE_MODULES:
        sys.modules.pop(module_name, None)
        importlib.import_module(module_name)

    assert recorded_calls == []


def test_ruff_guardrail_config_keeps_scope_and_exceptions_narrow():
    config_text = (ROOT / "ruff.toml").read_text(encoding="utf-8")

    assert 'src = ["api", "council_crawler", "pipeline", "scripts", "semantic_service", "tests"]' in config_text
    assert 'select = ["E722", "F401", "F841", "B", "BLE001", "C901", "DTZ", "S"]' in config_text
    assert "pipeline/*.py" not in config_text
    assert "api/*.py" not in config_text


def test_typed_subtree_config_stays_explicit_and_aligned():
    enrolled_paths = _mypy_enrolled_paths()
    docs_text = (ROOT / "docs" / "ENGINEERING_GUARDRAILS.md").read_text(encoding="utf-8")
    agents_text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    workflow_text = (ROOT / ".github" / "workflows" / "python-guardrails.yml").read_text(encoding="utf-8")

    assert enrolled_paths == TYPED_SUBTREE_PATHS
    assert "./.venv/bin/mypy\n" in docs_text
    assert "./.venv/bin/mypy" in agents_text
    assert "python -m mypy" in workflow_text
    assert "python -m mypy api/metrics.py" not in workflow_text


def test_first_formatter_wave_stays_path_scoped_and_enforced():
    docs_text = (ROOT / "docs" / "ENGINEERING_GUARDRAILS.md").read_text(encoding="utf-8")
    agents_text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    workflow_text = (ROOT / ".github" / "workflows" / "python-guardrails.yml").read_text(encoding="utf-8")

    assert CONFIG_OWNED_FORMATTER_COMMAND in docs_text
    assert "./.venv/bin/ruff format --check api pipeline scripts tests" not in docs_text
    assert "ruff format --check" not in agents_text
    assert "python -m ruff format --check " + " ".join(CANDIDATE_FORMATTER_WAVE_PATHS) in workflow_text
    assert "python -m ruff format --check api pipeline scripts tests" not in workflow_text


def test_facade_import_guardrail_detects_relative_imports(tmp_path: Path):
    pipeline_helper = tmp_path / "pipeline" / "helper.py"
    pipeline_helper.parent.mkdir(parents=True)
    pipeline_helper.write_text(
        "from . import vote_extractor\nfrom .vote_extraction_runner import run_vote_extraction_for_catalog\n",
        encoding="utf-8",
    )
    script_helper = tmp_path / "scripts" / "helper.py"
    script_helper.parent.mkdir(parents=True)
    script_helper.write_text("from .profile_pipeline import main\n", encoding="utf-8")
    semantic_helper = tmp_path / "semantic_service" / "helper.py"
    semantic_helper.parent.mkdir(parents=True)
    semantic_helper.write_text(
        "from . import main\nfrom .main import app\nfrom semantic_service import main as semantic_main\n",
        encoding="utf-8",
    )

    assert _forbidden_imports(
        pipeline_helper,
        {"pipeline.vote_extractor", "pipeline.vote_extraction_runner"},
    ) == ["pipeline.vote_extractor", "pipeline.vote_extraction_runner"]
    assert _forbidden_imports(script_helper, {"scripts.profile_pipeline"}) == ["scripts.profile_pipeline"]
    assert _forbidden_imports(semantic_helper, {"semantic_service.main"}) == [
        "semantic_service.main",
        "semantic_service.main",
        "semantic_service.main",
    ]


def test_broad_exception_allowlist_stays_explicit():
    ignore_entries = _ruff_per_file_ignore_entries()
    broad_exception_paths = {path for path, rules in ignore_entries.items() if "BLE001" in rules}

    assert broad_exception_paths == APPROVED_BROAD_EXCEPTION_PATHS
    assert broad_exception_paths.isdisjoint(BLE001_WILDCARD_PATHS)


def test_broad_exception_suppression_detection_covers_ruff_directives():
    directive_prefix = "# noqa:"
    spaced_directive = f"{directive_prefix} {BROAD_EXCEPTION_RULE}"
    compact_directive = f"{directive_prefix}{BROAD_EXCEPTION_RULE}"
    blanket_line_directive = "# noqa"
    blanket_ruff_file_directive = "# ruff: noqa"
    specific_ruff_file_directive = f"# ruff: noqa: {BROAD_EXCEPTION_RULE}"
    mixed_rule_directive = f"# noqa: F401, {BROAD_EXCEPTION_RULE}"
    joined_rule_suffix_directive = f"# noqa: F401{BROAD_EXCEPTION_RULE}"
    joined_rule_prefix_directive = f"# noqa: {BROAD_EXCEPTION_RULE}F401"
    blanket_flake8_file_directive = "# flake8: noqa"
    chained_specific_directive = f"# type: ignore  # noqa: {BROAD_EXCEPTION_RULE}"
    chained_blanket_directive = "# reason  # noqa"

    assert _comment_suppresses_broad_exception(spaced_directive)
    assert _comment_suppresses_broad_exception(compact_directive)
    assert _comment_suppresses_broad_exception(blanket_line_directive)
    assert _comment_suppresses_broad_exception(blanket_ruff_file_directive)
    assert _comment_suppresses_broad_exception(specific_ruff_file_directive)
    assert _comment_suppresses_broad_exception(mixed_rule_directive)
    assert _comment_suppresses_broad_exception(f"# noqa:,{BROAD_EXCEPTION_RULE}")
    assert _comment_suppresses_broad_exception(joined_rule_suffix_directive)
    assert _comment_suppresses_broad_exception(joined_rule_prefix_directive)
    assert _comment_suppresses_broad_exception(blanket_flake8_file_directive)
    assert _comment_suppresses_broad_exception(chained_specific_directive)
    assert _comment_suppresses_broad_exception(chained_blanket_directive)
    assert not _comment_suppresses_broad_exception("# noqa: F401")
    assert not _comment_suppresses_broad_exception("# noqa: F401E722")
    assert not _comment_suppresses_broad_exception("# noqa: XBLE001")
    assert not _comment_suppresses_broad_exception("# noqa: BLE001EXTRA")
    assert not _comment_suppresses_broad_exception("# noqa: BLE001f401")
    assert not _comment_suppresses_broad_exception("# noqa: f401BLE001")
    assert not _comment_suppresses_broad_exception("# noqa: EXTRA,BLE001F401")
    assert not _comment_suppresses_broad_exception("# noqa: F401 because BLE001 is centralized")
    assert not _comment_suppresses_broad_exception("# ruff: noqa: F401")


def test_broad_exception_suppression_scan_uses_comment_tokens(tmp_path: Path):
    python_path = tmp_path / "directive_examples.py"
    python_path.write_text(
        'LINE_DIRECTIVE = "# noqa"\n'
        'FILE_DIRECTIVE = "# ruff: noqa: BLE001"\n'
        "try:\n"
        "    pass\n"
        "except Exception:  # noqa\n"
        "    pass\n"
        "# ruff: noqa: BLE001\n"
        "try:\n"
        "    pass\n"
        "except Exception:  # type: ignore  # noqa: BLE001\n"
        "    pass\n"
        "try:\n"
        "    pass\n"
        "except Exception:  # noqa: BLE001F401\n"
        "    pass\n"
        "try:\n"
        "    pass\n"
        "except Exception:  # noqa: F401BLE001\n"
        "    pass\n"
        "try:\n"
        "    pass\n"
        "except Exception:  # noqa: F401E722\n"
        "    pass\n"
        "try:\n"
        "    pass\n"
        "except Exception:  # noqa:,BLE001\n"
        "    pass\n",
        encoding="utf-8",
    )

    assert _broad_exception_suppression_lines(python_path) == [5, 7, 10, 14, 18, 26]


def _first_broad_exception_handler(python_source: str) -> ast.ExceptHandler:
    syntax_tree = ast.parse(python_source)
    try_node = next(syntax_node for syntax_node in ast.walk(syntax_tree) if isinstance(syntax_node, ast.Try))
    return try_node.handlers[0]


def test_nested_raise_does_not_approve_a_swallowed_broad_exception():
    exception_handler = _first_broad_exception_handler(
        "try:\n"
        "    operation()\n"
        "except Exception:\n"
        "    def deferred_failure():\n"
        "        raise RuntimeError\n"
        "    record_failure()\n"
    )

    assert not _broad_exception_handler_is_approved("pipeline/unapproved.py", exception_handler)


def test_conditional_and_deferred_termination_do_not_approve_broad_exceptions():
    conditional_raise = _first_broad_exception_handler(
        "try:\n"
        "    operation()\n"
        "except Exception:\n"
        "    if should_raise:\n"
        "        raise\n"
        "    record_failure()\n"
    )
    deferred_exit = _first_broad_exception_handler(
        "try:\n"
        "    operation()\n"
        "except Exception:\n"
        "    pending_exits = (sys.exit(1) for _ in range(1))\n"
        "    record_failure()\n"
    )

    assert not _broad_exception_handler_is_approved("pipeline/unapproved.py", conditional_raise)
    assert not _broad_exception_handler_is_approved("pipeline/unapproved.py", deferred_exit)


def test_unconditional_terminal_actions_approve_broad_exceptions():
    direct_raise = _first_broad_exception_handler(
        "try:\n    operation()\nexcept Exception:\n    record_failure()\n    raise\n"
    )
    direct_exit = _first_broad_exception_handler(
        "try:\n    operation()\nexcept Exception:\n    record_failure()\n    sys.exit(1)\n"
    )

    assert _broad_exception_handler_is_approved("pipeline/unapproved.py", direct_raise)
    assert _broad_exception_handler_is_approved("pipeline/unapproved.py", direct_exit)


def test_ruff_per_file_ignore_parser_accepts_valid_toml_forms():
    ruff_config = """
[lint.per-file-ignores]
'pipeline/single_quote.py' = ['BLE001']
"pipeline/multiline.py" = [
    "BLE001",
    "F401",
]
"""

    assert _parse_ruff_per_file_ignore_entries(ruff_config) == {
        "pipeline/multiline.py": {"BLE001", "F401"},
        "pipeline/single_quote.py": {"BLE001"},
    }


def test_broad_exception_suppressions_stay_in_ruff_config():
    inline_suppressions = [
        f"{tracked_path.relative_to(ROOT)}:{line_number}"
        for tracked_path in _tracked_files()
        if tracked_path.suffix == ".py"
        for line_number in _broad_exception_suppression_lines(tracked_path)
    ]

    assert inline_suppressions == []


def test_broad_exception_handlers_stay_on_approved_boundaries_and_take_action():
    unauthorized_handlers: list[str] = []
    silent_handlers: list[str] = []

    for tracked_path in _broad_exception_scan_files():
        if tracked_path.suffix != ".py":
            continue
        relative_path = str(tracked_path.relative_to(ROOT))
        if relative_path.split("/", 1)[0] not in {"api", "pipeline", "scripts", "tests"}:
            continue
        source = tracked_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relative_path)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            for handler in node.handlers:
                if _exception_handler_name(handler.type) != "Exception":
                    continue

                handler_ref = f"{relative_path}:{handler.lineno}"
                body_nodes = handler.body
                is_silent = all(
                    isinstance(body_node, ast.Pass)
                    or (isinstance(body_node, ast.Expr) and isinstance(body_node.value, ast.Constant))
                    for body_node in body_nodes
                )
                if is_silent:
                    silent_handlers.append(handler_ref)
                    continue
                if not _broad_exception_handler_is_approved(relative_path, handler):
                    unauthorized_handlers.append(handler_ref)

    assert unauthorized_handlers == []
    assert silent_handlers == []


def test_metrics_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in METRICS_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_downloader_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in DOWNLOADER_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_config_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in CONFIG_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_agenda_extraction_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in AGENDA_EXTRACTION_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_agenda_text_heuristics_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in AGENDA_TEXT_HEURISTICS_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_agenda_resolver_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in AGENDA_RESOLVER_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_agenda_qa_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in AGENDA_QA_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_agenda_summary_maintenance_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in AGENDA_SUMMARY_MAINTENANCE_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_agenda_summary_runtime_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in AGENDA_SUMMARY_RUNTIME_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_run_pipeline_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in RUN_PIPELINE_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_summary_hydration_diagnostic_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in SUMMARY_HYDRATION_DIAGNOSTIC_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_summary_hydration_sample_helpers_do_not_import_facade():
    module_path = ROOT / "pipeline" / "summary_hydration_diagnostic_samples.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path.relative_to(ROOT)))
    forbidden_modules = {
        "pipeline.summary_hydration_diagnostics",
        "pipeline.summary_hydration_diagnostic_queries",
    }
    forbidden_imports: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            forbidden_imports.extend(alias.name for alias in node.names if alias.name in forbidden_modules)
        elif isinstance(node, ast.ImportFrom) and node.module in forbidden_modules:
            forbidden_imports.append(node.module)
        elif isinstance(node, ast.ImportFrom) and node.module == "pipeline":
            forbidden_imports.extend(
                f"pipeline.{alias.name}" for alias in node.names if f"pipeline.{alias.name}" in forbidden_modules
            )

    assert forbidden_imports == []


def test_profile_manifest_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in PROFILE_MANIFEST_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_topic_generation_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in TOPIC_GENERATION_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_local_ai_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in LOCAL_AI_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_http_provider_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in HTTP_PROVIDER_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_person_utils_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in PERSON_UTILS_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_reporting_scripts_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in REPORTING_SCRIPTS_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_batch_f_operator_ab_helper_does_not_import_facade():
    forbidden_imports = _forbidden_imports(
        ROOT / "scripts" / "operator_profile_ab_aggregate.py",
        {"scripts.operator_profile_ab"},
    )

    assert forbidden_imports == []


def test_batch_e_reporting_helpers_do_not_import_facades():
    forbidden_imports: list[str] = []
    for module_path in (
        ROOT / "scripts" / "collect_ab_results_rows.py",
        ROOT / "scripts" / "evaluate_soak_week_gates.py",
    ):
        forbidden_imports.extend(
            _forbidden_imports(
                module_path,
                {"scripts.collect_ab_results", "scripts.evaluate_soak_week"},
            )
        )

    assert forbidden_imports == []


def test_shared_helper_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in SHARED_HELPER_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_batch_d_profile_helpers_do_not_import_facades():
    forbidden_imports: list[str] = []
    for module_path in (
        ROOT / "scripts" / "operator_profile_worker_metrics.py",
        ROOT / "scripts" / "profile_pipeline_commands.py",
        ROOT / "scripts" / "profile_pipeline_results.py",
    ):
        forbidden_imports.extend(
            _forbidden_imports(
                module_path,
                {"scripts.operator_profile_metrics", "scripts.profile_pipeline", "scripts.profile_pipeline_runner"},
            )
        )

    assert forbidden_imports == []


def test_task_api_facade_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in TASK_API_FACADE_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_search_support_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in SEARCH_SUPPORT_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_batch_f_search_read_helpers_do_not_import_facade():
    forbidden_imports: list[str] = []
    for module_path in (
        ROOT / "api" / "search_read_meilisearch.py",
        ROOT / "api" / "search_read_params.py",
        ROOT / "api" / "search_read_results.py",
    ):
        forbidden_imports.extend(_forbidden_imports(module_path, {"api.search_read_routes"}))

    assert forbidden_imports == []


def test_city_coverage_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in CITY_COVERAGE_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_batch_f_city_coverage_helpers_do_not_import_facade():
    forbidden_imports: list[str] = []
    for module_path in (
        ROOT / "pipeline" / "city_coverage_assembly.py",
        ROOT / "pipeline" / "city_coverage_buckets.py",
        ROOT / "pipeline" / "city_coverage_contracts.py",
        ROOT / "pipeline" / "city_coverage_queries.py",
        ROOT / "pipeline" / "city_coverage_windows.py",
    ):
        forbidden_imports.extend(_forbidden_imports(module_path, {"pipeline.city_coverage_audit"}))

    assert forbidden_imports == []


def test_lineage_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in LINEAGE_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_batch_f_lineage_helpers_do_not_import_facade():
    forbidden_imports: list[str] = []
    for module_path in (
        ROOT / "pipeline" / "lineage_assignment.py",
        ROOT / "pipeline" / "lineage_graph.py",
    ):
        forbidden_imports.extend(_forbidden_imports(module_path, {"pipeline.lineage_service"}))

    assert forbidden_imports == []


def test_city_onboarding_evaluator_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in CITY_ONBOARDING_EVALUATOR_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_laserfiche_repair_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in LASERFICHE_REPAIR_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_laserfiche_generated_pdf_helper_does_not_import_facades():
    forbidden_imports = _forbidden_imports(
        ROOT / "scripts" / "laserfiche_repair_generated_pdf.py",
        {"scripts.repair_san_mateo_laserfiche_backlog", "scripts.laserfiche_repair_downloads"},
    )

    assert forbidden_imports == []


def test_segment_city_corpus_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in SEGMENT_CITY_CORPUS_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_hydration_cli_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in HYDRATION_CLI_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_model_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in MODEL_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_db_migration_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in DB_MIGRATION_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_indexer_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in INDEXER_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_semantic_backend_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in SEMANTIC_BACKEND_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_semantic_service_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in SEMANTIC_SERVICE_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_batch_g_semantic_service_helpers_do_not_import_facade():
    forbidden_imports: list[str] = []
    for module_path in (
        ROOT / "semantic_service" / "candidates.py",
        ROOT / "semantic_service" / "filters.py",
        ROOT / "semantic_service" / "retrieval.py",
        ROOT / "semantic_service" / "hydration.py",
    ):
        forbidden_imports.extend(_forbidden_imports(module_path, {"semantic_service.main"}))

    assert forbidden_imports == []


def test_summary_text_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in SUMMARY_TEXT_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_summary_backfill_progress_helper_does_not_import_facades():
    forbidden_imports = _forbidden_imports(
        ROOT / "pipeline" / "summary_backfill_progress.py",
        {"pipeline.summary_backfill", "pipeline.summary_backfill_runner"},
    )

    assert forbidden_imports == []


def test_vote_extraction_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in VOTE_EXTRACTION_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_vote_extraction_item_helper_does_not_import_facades():
    forbidden_imports = _forbidden_imports(
        ROOT / "pipeline" / "vote_extraction_item.py",
        {"pipeline.vote_extractor", "pipeline.vote_extraction_runner"},
    )

    assert forbidden_imports == []


def test_nlp_entity_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in NLP_ENTITY_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []
