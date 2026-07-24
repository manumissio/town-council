from __future__ import annotations

import ast
import configparser
import json
import os
import re
import subprocess
import sys
import tomllib
import tokenize
from fnmatch import fnmatch
from io import StringIO
from pathlib import Path
from textwrap import indent

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
RUFF_CLEAN_EXIT = 0
RUFF_VIOLATION_EXIT = 1
GITHUB_EXPRESSION_OPEN = "${{"
COVERAGE_PROCESS_ENVIRONMENT_KEYS = (
    "COVERAGE_PROCESS_CONFIG",
    "COVERAGE_PROCESS_START",
)
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
LINE_NOQA_DIRECTIVE = re.compile(
    r"#\s*noqa(?=\s|:|$)(?:\s*:\s*(?P<rules>[^#]*))?",
    re.IGNORECASE,
)
FILE_NOQA_DIRECTIVE = re.compile(
    r"^#\s*(?:ruff|flake8)\s*:\s*noqa(?=\s|:|$)(?:\s*:\s*(?P<rules>[^#]*))?",
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
CONFIG_OWNED_FORMATTER_COMMAND = "./.venv/bin/ruff format --check . --config ruff-format.toml"
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
    directive_match = FILE_NOQA_DIRECTIVE.match(comment_text)
    if directive_match is None:
        directive_match = LINE_NOQA_DIRECTIVE.search(comment_text)
    if directive_match is None:
        return False

    directive_rules = directive_match.group("rules")
    return directive_rules is None or _noqa_rules_suppress_broad_exception(directive_rules)


def _broad_exception_suppression_lines(python_path: Path) -> list[int]:
    python_source = python_path.read_text(encoding="utf-8")
    python_tokens = tokenize.generate_tokens(StringIO(python_source).readline)
    return [
        python_token.start[0]
        for python_token in python_tokens
        if python_token.type == tokenize.COMMENT and _comment_suppresses_broad_exception(python_token.string)
    ]


def _broad_exception_scan_files() -> list[Path]:
    checked_files = subprocess.check_output(
        [sys.executable, "-m", "ruff", "check", "--show-files", "."],
        cwd=ROOT,
        text=True,
    )
    return sorted(Path(checked_path).resolve() for checked_path in checked_files.splitlines() if checked_path.endswith(".py"))


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


def _statement_contains_suspension(statement: ast.stmt) -> bool:
    return any(isinstance(node, ast.Await | ast.Yield | ast.YieldFrom) for node in ast.walk(statement))


def _statement_calls_sys_exit(statement: ast.stmt) -> bool:
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "sys"
        and node.func.attr == "exit"
        for node in ast.walk(statement)
    )


def _statement_is_flat_exception_context(statement: ast.stmt) -> bool:
    if _statement_contains_suspension(statement) or _statement_calls_sys_exit(statement):
        return False
    if isinstance(statement, ast.Assign):
        return all(isinstance(assignment_target, ast.Name) for assignment_target in statement.targets)
    return isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call)


def _broad_exception_handler_is_approved(
    relative_path: str,
    handler: ast.ExceptHandler,
) -> bool:
    if relative_path in APPROVED_BROAD_EXCEPTION_PATHS:
        return True
    if not handler.body:
        return False
    *context_statements, terminal_statement = handler.body
    explicit_cause = terminal_statement.cause if isinstance(terminal_statement, ast.Raise) else None
    explicit_cause_preserves_context = explicit_cause is not None and not (
        isinstance(explicit_cause, ast.Constant) and explicit_cause.value is None
    )
    terminal_raise_is_chained = (
        isinstance(terminal_statement, ast.Raise)
        and (terminal_statement.exc is None or explicit_cause_preserves_context)
    )
    return terminal_raise_is_chained and all(
        _statement_is_flat_exception_context(context_statement) for context_statement in context_statements
    )


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


def _ruff_selector_has_current_violation(
    ignore_pattern: str,
    ruff_selector: str,
    tracked_files: list[Path],
) -> bool:
    lint_targets = sorted(
        tracked_file for tracked_file in tracked_files if tracked_file.relative_to(ROOT).match(ignore_pattern)
    )
    if not lint_targets:
        raise AssertionError(f"Ruff ignore pattern has no tracked targets: {ignore_pattern}")

    relative_targets = [str(lint_target.relative_to(ROOT)) for lint_target in lint_targets]
    ruff_check = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--config",
            "lint.per-file-ignores = {}",
            "--select",
            ruff_selector,
            *relative_targets,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if ruff_check.returncode not in {RUFF_CLEAN_EXIT, RUFF_VIOLATION_EXIT}:
        raise AssertionError(
            f"Ruff failed while checking {ignore_pattern} for {ruff_selector}: "
            f"{ruff_check.stdout}{ruff_check.stderr}"
        )
    return ruff_check.returncode == RUFF_VIOLATION_EXIT


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
    for tracked_path in _tracked_files():
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


def test_ruff_entrypoints_use_config_owned_repository_scope():
    repository_command = "ruff check ."
    legacy_command = "ruff check api pipeline scripts tests"
    ruff_hook_contract = "\n".join(
        (
            "      - id: ruff",
            "        name: ruff-guardrails",
            '        args: ["."]',
            "        always_run: true",
            "        pass_filenames: false",
        )
    )
    workflow_text = (ROOT / ".github" / "workflows" / "python-guardrails.yml").read_text(encoding="utf-8")
    pre_commit_text = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    agents_text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    guardrail_docs_text = (ROOT / "docs" / "ENGINEERING_GUARDRAILS.md").read_text(encoding="utf-8")

    assert f"python -m {repository_command}" in workflow_text
    assert ruff_hook_contract in pre_commit_text
    assert f"./.venv/bin/{repository_command}" in agents_text
    assert f"./.venv/bin/{repository_command}" in guardrail_docs_text
    assert all(
        legacy_command not in policy_text
        for policy_text in (workflow_text, pre_commit_text, agents_text, guardrail_docs_text)
    )


def test_ruff_per_file_ignore_selectors_cover_current_violations():
    ruff_config_text = (ROOT / "ruff.toml").read_text(encoding="utf-8")
    tracked_files = _tracked_files()
    stale_ignore_selectors = sorted(
        f"{ignore_pattern}: {ruff_selector}"
        for ignore_pattern, ruff_selectors in _parse_ruff_per_file_ignore_entries(ruff_config_text).items()
        for ruff_selector in ruff_selectors
        if not _ruff_selector_has_current_violation(
            ignore_pattern,
            ruff_selector,
            tracked_files,
        )
    )

    assert stale_ignore_selectors == []


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


def test_formatter_scope_is_config_owned_and_preserved():
    formatter_config_path = ROOT / "ruff-format.toml"
    formatter_config = tomllib.loads(formatter_config_path.read_text(encoding="utf-8"))
    ruff_config = tomllib.loads((ROOT / "ruff.toml").read_text(encoding="utf-8"))
    docs_text = (ROOT / "docs" / "ENGINEERING_GUARDRAILS.md").read_text(encoding="utf-8")
    agents_text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    workflow_text = (ROOT / ".github" / "workflows" / "python-guardrails.yml").read_text(encoding="utf-8")
    formatter_paths = formatter_config["include"]
    ruff_formatter_discovery = subprocess.check_output(
        [sys.executable, "-m", "ruff", "check", "--show-files", ".", "--config", "ruff-format.toml"],
        cwd=ROOT,
        text=True,
    )
    effective_formatter_paths = sorted(
        Path(discovered_path).resolve().relative_to(ROOT).as_posix()
        for discovered_path in ruff_formatter_discovery.splitlines()
    )
    workflow_formatter_commands = [
        workflow_line.strip()
        for workflow_line in workflow_text.splitlines()
        if "ruff format --check" in workflow_line
    ]

    assert formatter_config["extend"] == "ruff.toml"
    assert formatter_paths
    assert len(formatter_paths) == len(set(formatter_paths))
    assert all((ROOT / formatter_path).is_file() for formatter_path in formatter_paths)
    assert sorted(formatter_paths) == effective_formatter_paths
    assert "include" not in ruff_config
    assert "exclude" not in ruff_config.get("format", {})
    assert "exclude" not in formatter_config.get("format", {})
    assert CONFIG_OWNED_FORMATTER_COMMAND in docs_text
    assert (
        "Guardrail/tooling changes (`ruff.toml`, `ruff-format.toml`, `mypy.ini`,"
        in agents_text
    )
    assert "ruff format --check" not in agents_text
    assert workflow_formatter_commands == [
        "run: python -m ruff format --check . --config ruff-format.toml"
    ]


def test_python_guardrail_workflow_enforces_production_coverage():
    workflow_text = (ROOT / ".github" / "workflows" / "python-guardrails.yml").read_text(encoding="utf-8")
    expected_dependency_commands = (
        "python -m pip install -r pipeline/requirements.txt",
        "python -m pip install -r api/requirements.txt",
        "python -m pip install -r council_crawler/requirements.txt",
        "python -m pip install scikit-learn==1.8.0",
        "python -m pip install -r pipeline/requirements-dev.txt",
        "python -m venv --system-site-packages .venv",
    )
    expected_fast_fail_commands = (
        "PYTHONPATH=. python -m pytest -q tests/test_repository_guardrails.py",
        "PYTHONPATH=. python -m pytest -q tests/test_config_cleanup.py",
        "PYTHONPATH=. python -m pytest -q tests/test_pipeline_import_side_effects.py",
        "PYTHONPATH=. python -m pytest -q tests/test_provider_error_mapping_retry_vs_fallback.py",
        "PYTHONPATH=. python -m pytest -q tests/test_summary_staleness.py",
        "PYTHONPATH=. python -m pytest -q tests/test_pipeline_profile_report.py",
        "PYTHONPATH=. python -m pytest -q tests/test_docs_links.py",
    )
    full_suite_step = (
        "      - name: Run full Python test suite\n"
        "        run: PYTHONPATH=. python -m pytest -q --cov "
        "--cov-config=.coveragerc "
        "--cov-report=term-missing:skip-covered tests/"
    )

    dependency_step = workflow_text.partition("      - name: Install guardrail and runtime dependencies\n")[2]
    dependency_step = dependency_step.partition("\n      - name:")[0]
    dependency_commands = tuple(
        workflow_line.strip()
        for workflow_line in dependency_step.splitlines()
        if workflow_line.startswith("          python -m ")
    )
    assert dependency_commands == expected_dependency_commands
    assert workflow_text.count(full_suite_step) == 1

    fast_fail_prefix, full_suite_separator, full_suite_tail = workflow_text.partition(full_suite_step)
    assert full_suite_separator
    fast_fail_marker = "      - name: Run guardrail tests\n"
    assert fast_fail_marker in fast_fail_prefix
    fast_fail_step = fast_fail_prefix.rpartition(fast_fail_marker)[2]
    configured_fast_fail_commands = tuple(
        workflow_line.strip()
        for workflow_line in fast_fail_step.splitlines()
        if workflow_line.strip().startswith("PYTHONPATH=. python -m pytest -q ")
    )
    assert configured_fast_fail_commands == expected_fast_fail_commands
    assert "continue-on-error:" not in fast_fail_step
    assert "if:" not in fast_fail_step
    assert "--cov" not in fast_fail_step

    full_suite_step_body = full_suite_tail.partition("\n      - name:")[0]
    assert "continue-on-error:" not in full_suite_step_body
    assert "if:" not in full_suite_step_body


def test_coverage_configuration_measures_repository_production_python():
    coverage_config = configparser.ConfigParser()
    coverage_config.read(ROOT / ".coveragerc")

    assert coverage_config["run"].getboolean("branch") is False
    assert coverage_config["run"]["source"].split() == ["."]
    assert coverage_config["run"]["omit"].split() == [
        "tests/*",
        "archive/*",
        "experiments/*",
        ".venv*/*",
    ]
    assert coverage_config["run"]["patch"].split() == ["subprocess"]
    assert coverage_config["report"].getfloat("fail_under") == 71
    assert coverage_config["report"].getboolean("include_namespace_packages") is True


def test_coverage_configuration_reports_every_tracked_production_python_file(
    tmp_path: Path,
):
    coverage_data_path = tmp_path / "coverage-data"
    coverage_report_path = tmp_path / "coverage.json"
    coverage_environment = os.environ.copy()
    for environment_key in COVERAGE_PROCESS_ENVIRONMENT_KEYS:
        coverage_environment.pop(environment_key, None)
    coverage_environment["COVERAGE_FILE"] = str(coverage_data_path)

    subprocess.run(
        [
            sys.executable,
            "-m",
            "coverage",
            "run",
            "--rcfile=.coveragerc",
            "pipeline/content_hash.py",
        ],
        cwd=ROOT,
        env=coverage_environment,
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "coverage",
            "combine",
            "--rcfile=.coveragerc",
            str(tmp_path),
        ],
        cwd=ROOT,
        env=coverage_environment,
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "coverage",
            "json",
            "--rcfile=.coveragerc",
            "--fail-under=0",
            "-o",
            str(coverage_report_path),
            "-q",
        ],
        cwd=ROOT,
        env=coverage_environment,
        check=True,
    )

    coverage_config = configparser.ConfigParser()
    coverage_config.read(ROOT / ".coveragerc")
    omit_patterns = coverage_config["run"]["omit"].split()
    tracked_production_paths = {
        tracked_path.relative_to(ROOT).as_posix()
        for tracked_path in _tracked_files()
        if tracked_path.suffix == ".py"
        and not any(fnmatch(tracked_path.relative_to(ROOT).as_posix(), omit_pattern) for omit_pattern in omit_patterns)
    }
    coverage_report = json.loads(coverage_report_path.read_text(encoding="utf-8"))
    reported_paths = {Path(reported_path).as_posix() for reported_path in coverage_report["files"]}

    assert reported_paths == tracked_production_paths


def test_python_guardrail_workflow_runs_for_every_pull_request_and_master_push():
    workflow_text = (ROOT / ".github" / "workflows" / "python-guardrails.yml").read_text(encoding="utf-8")
    event_configuration = workflow_text.partition("on:\n")[2].partition("\npermissions:\n")[0]

    assert event_configuration == '  pull_request:\n  push:\n    branches: ["master"]\n'


def test_frontend_test_script_uses_existing_node_runner():
    frontend_package = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))

    assert frontend_package["scripts"]["test"] == "node --test components/__tests__/*.test.js"
    assert "jest" not in frontend_package.get("devDependencies", {})
    assert "vitest" not in frontend_package.get("devDependencies", {})


def test_frontend_workflow_runs_for_every_pull_request_and_master_push():
    workflow_text = (ROOT / ".github" / "workflows" / "frontend-tests.yml").read_text(encoding="utf-8")
    event_configuration = workflow_text.partition("on:\n")[2].partition("\npermissions:\n")[0]

    assert event_configuration == '  pull_request:\n  push:\n    branches: ["master"]\n'
    assert workflow_text.count("\n  frontend-tests:\n") == 1
    assert "paths:" not in event_configuration
    assert "paths-ignore:" not in event_configuration


def _workflow_job_check_producers(
    workflow_text: str,
    required_check_name: str,
) -> tuple[tuple[str, str | None], ...]:
    workflow_contract = yaml.load(workflow_text, Loader=yaml.BaseLoader)
    assert isinstance(workflow_contract, dict)
    workflow_jobs = workflow_contract.get("jobs")
    assert isinstance(workflow_jobs, dict)

    check_producers: list[tuple[str, str | None]] = []
    for workflow_job_id, workflow_job_contract in workflow_jobs.items():
        assert isinstance(workflow_job_id, str)
        assert isinstance(workflow_job_contract, dict)
        configured_job_name = workflow_job_contract.get("name")
        assert configured_job_name is None or isinstance(configured_job_name, str)
        assert configured_job_name is None or GITHUB_EXPRESSION_OPEN not in configured_job_name, (
            f"Dynamic workflow job name cannot prove required-check identity: {workflow_job_id}"
        )
        if (configured_job_name or workflow_job_id) == required_check_name:
            check_producers.append((workflow_job_id, configured_job_name))
    return tuple(check_producers)


def test_frontend_required_check_uses_one_canonical_workflow_job():
    workflow_directory = ROOT / ".github" / "workflows"
    candidate_workflow_paths = sorted(
        (*workflow_directory.glob("*.yml"), *workflow_directory.glob("*.yaml"))
    )
    frontend_check_producers = tuple(
        (
            workflow_path.relative_to(ROOT).as_posix(),
            workflow_job_id,
            configured_job_name,
        )
        for workflow_path in candidate_workflow_paths
        for workflow_job_id, configured_job_name in _workflow_job_check_producers(
            workflow_path.read_text(encoding="utf-8"),
            "frontend-tests",
        )
    )

    assert frontend_check_producers == (
        (".github/workflows/frontend-tests.yml", "frontend-tests", None),
    )


@pytest.mark.parametrize(
    "configured_job_name",
    (
        "frontend-tests",
        '"frontend-tests"',
        ">-\n      frontend-tests",
    ),
)
def test_frontend_required_check_detects_semantic_job_name_overrides(
    configured_job_name: str,
):
    workflow_text = f"""\
jobs:
  alternate:
    name: {configured_job_name}
    runs-on: ubuntu-latest
    steps: []
"""

    assert _workflow_job_check_producers(workflow_text, "frontend-tests") == (
        ("alternate", "frontend-tests"),
    )


def test_frontend_required_check_ignores_comments_steps_and_command_text():
    workflow_text = """\
jobs:
  alternate:
    runs-on: ubuntu-latest
    steps:
      # frontend-tests: required check
      - name: frontend-tests
        run: |
          echo "frontend-tests:"
"""

    assert _workflow_job_check_producers(workflow_text, "frontend-tests") == ()


def test_frontend_required_check_rejects_dynamic_job_names():
    workflow_text = """\
jobs:
  alternate:
    name: ${{ vars.REQUIRED_CHECK }}
    runs-on: ubuntu-latest
    steps: []
"""

    with pytest.raises(AssertionError, match="Dynamic workflow job name"):
        _workflow_job_check_producers(workflow_text, "frontend-tests")


@pytest.mark.parametrize(
    "github_string_scalar",
    ("on", "off", "yes", "no", "On", "OFF", "Yes", "NO"),
)
def test_frontend_required_check_preserves_github_string_job_ids(
    github_string_scalar: str,
):
    workflow_text = f"""\
jobs:
  {github_string_scalar}:
    runs-on: ubuntu-latest
    steps: []
"""

    assert _workflow_job_check_producers(workflow_text, "frontend-tests") == ()


@pytest.mark.parametrize(
    "github_string_scalar",
    ("on", "off", "yes", "no", "On", "OFF", "Yes", "NO"),
)
def test_frontend_required_check_preserves_github_string_job_names(
    github_string_scalar: str,
):
    workflow_text = f"""\
jobs:
  alternate:
    name: {github_string_scalar}
    runs-on: ubuntu-latest
    steps: []
"""

    assert _workflow_job_check_producers(workflow_text, "frontend-tests") == ()


def test_frontend_workflow_installs_locked_dependencies_before_tests():
    workflow_text = (ROOT / ".github" / "workflows" / "frontend-tests.yml").read_text(encoding="utf-8")
    install_step = "      - name: Install dependencies\n        run: npm ci"
    test_step = "      - name: Run frontend tests\n        run: npm test"

    assert "uses: actions/checkout@v5" in workflow_text
    assert "uses: actions/setup-node@v6" in workflow_text
    assert 'node-version: "20"' in workflow_text
    assert 'cache: "npm"' in workflow_text
    assert "cache-dependency-path: frontend/package-lock.json" in workflow_text
    assert "working-directory: frontend" in workflow_text
    assert workflow_text.index(install_step) < workflow_text.index(test_step)
    assert "continue-on-error:" not in workflow_text
    assert "if:" not in workflow_text
    assert "strategy:" not in workflow_text


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
    adjacent_specific_directive = f"# type: ignore# noqa: {BROAD_EXCEPTION_RULE}"
    adjacent_blanket_directive = "# reason# noqa"

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
    assert _comment_suppresses_broad_exception(adjacent_specific_directive)
    assert _comment_suppresses_broad_exception(adjacent_blanket_directive)
    assert not _comment_suppresses_broad_exception("# noqa: F401")
    assert not _comment_suppresses_broad_exception("# noqa: F401E722")
    assert not _comment_suppresses_broad_exception("# noqa: XBLE001")
    assert not _comment_suppresses_broad_exception("# noqa: BLE001EXTRA")
    assert not _comment_suppresses_broad_exception("# noqa: BLE001f401")
    assert not _comment_suppresses_broad_exception("# noqa: f401BLE001")
    assert not _comment_suppresses_broad_exception("# noqa: EXTRA,BLE001F401")
    assert not _comment_suppresses_broad_exception("# noqa: F401 because BLE001 is centralized")
    assert not _comment_suppresses_broad_exception("# ruff: noqa: F401")
    assert not _comment_suppresses_broad_exception("# type: ignore# ruff: noqa: BLE001")
    assert not _comment_suppresses_broad_exception("# type: ignore# flake8: noqa")
    assert not _comment_suppresses_broad_exception("# reason# noqaish: BLE001")
    assert not _comment_suppresses_broad_exception("# reason# noqa-not: BLE001")
    assert not _comment_suppresses_broad_exception("# noqa: F401# noqa: BLE001")
    assert not _comment_suppresses_broad_exception("# reason  # ruff: noqa: BLE001")
    assert not _comment_suppresses_broad_exception("# reason  # flake8: noqa")


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
        "except Exception:  # type: ignore# noqa: BLE001\n"
        "    pass\n"
        "try:\n"
        "    pass\n"
        "except Exception:  # reason# noqa\n"
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
        "    pass\n"
        "try:\n"
        "    pass\n"
        "except Exception:  # noqa: F401# noqa: BLE001\n"
        "    pass\n"
        "try:\n"
        "    pass\n"
        "except Exception:  # reason  # ruff: noqa: BLE001\n"
        "    pass\n"
        "try:\n"
        "    pass\n"
        "except Exception:  # reason  # flake8: noqa\n"
        "    pass\n",
        encoding="utf-8",
    )

    assert _broad_exception_suppression_lines(python_path) == [5, 7, 10, 14, 18, 22, 26, 34]


def _first_broad_exception_handler(python_source: str) -> ast.ExceptHandler:
    syntax_tree = ast.parse(python_source)
    try_node = next(
        syntax_node
        for syntax_node in ast.walk(syntax_tree)
        if isinstance(syntax_node, ast.Try | ast.TryStar)
    )
    return try_node.handlers[0]


def _source_handler_is_approved(python_source: str) -> bool:
    exception_handler = _first_broad_exception_handler(python_source)
    return _broad_exception_handler_is_approved("pipeline/unapproved.py", exception_handler)


def _broad_exception_source(
    handler_body: str,
    *,
    async_function: bool = False,
    exception_operator: str = "except",
) -> str:
    function_prefix = "async " if async_function else ""
    return (
        f"{function_prefix}def run():\n"
        "    try:\n"
        "        operation()\n"
        f"    {exception_operator} Exception as exc:\n"
        f"{indent(handler_body, '        ')}\n"
    )


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


@pytest.mark.parametrize(
    "handler_body",
    [
        "failure_message = str(exc)\nraise",
        "record_failure(exc)\nraise RuntimeError('operation failed') from exc",
    ],
    ids=["assignment-and-reraise", "action-and-chained-translation"],
)
def test_flat_broad_exception_handlers_must_finish_with_raise(handler_body: str) -> None:
    assert _source_handler_is_approved(_broad_exception_source(handler_body))


@pytest.mark.parametrize(
    "terminal_raise",
    ["raise RuntimeError('operation failed')", "raise RuntimeError('operation failed') from None"],
    ids=["unchained", "suppressed-context"],
)
def test_explicit_broad_exception_translation_requires_chaining(terminal_raise: str) -> None:
    unchained_translation = _broad_exception_source(f"record_failure(exc)\n{terminal_raise}")

    assert not _source_handler_is_approved(unchained_translation)


@pytest.mark.parametrize(
    ("handler_body", "async_function"),
    [
        ("if cached:\n    return None\nraise", False),
        ("return None\nraise", False),
        ("yield failure_record()\nraise", False),
        ("yield from failure_records()\nraise", False),
        ("await record_failure()\nraise", True),
    ],
    ids=["conditional-return", "unreachable-raise", "yield", "yield-from", "await"],
)
def test_early_exit_or_suspension_rejects_broad_exception_handler(
    handler_body: str,
    async_function: bool,
) -> None:
    python_source = _broad_exception_source(handler_body, async_function=async_function)
    assert not _source_handler_is_approved(python_source)


@pytest.mark.parametrize(
    "handler_body",
    [
        "if should_record:\n    record_failure()\nraise",
        "for failure in failures:\n    record_failure(failure)\nraise",
        "with failure_context():\n    record_failure()\nraise",
        "match failure_code:\n    case 1:\n        record_failure()\nraise",
        "try:\n    record_failure()\nfinally:\n    release_failure_lock()\nraise",
        "def record_later():\n    record_failure()\nraise",
        "class FailureRecord:\n    code = 1\nraise",
    ],
    ids=["branch", "loop", "with", "match", "nested-try", "nested-function", "nested-class"],
)
def test_compound_broad_exception_handlers_require_central_approval(handler_body: str) -> None:
    assert not _source_handler_is_approved(_broad_exception_source(handler_body))


def test_central_boundary_approves_compound_broad_exception_handler() -> None:
    branch_source = _broad_exception_source("if should_record:\n    record_failure()\nraise")
    approved_handler = _first_broad_exception_handler(branch_source)
    approved_path = min(APPROVED_BROAD_EXCEPTION_PATHS)
    assert _broad_exception_handler_is_approved(approved_path, approved_handler)


@pytest.mark.parametrize(
    "handler_body",
    [
        "record_failure()\nsys.exit(1)",
        "sys = failure_controller\nsys.exit(1)",
        "sys.exit(1)\nraise",
        "sys = failure_controller\nsys.exit(1)\nraise",
    ],
    ids=["direct", "rebound", "before-raise", "rebound-before-raise"],
)
def test_sys_exit_does_not_authorize_unlisted_broad_exception_handler(handler_body: str) -> None:
    assert not _source_handler_is_approved(_broad_exception_source(handler_body))


def test_try_star_broad_exception_handlers_follow_the_same_policy() -> None:
    unsafe_try_star = _broad_exception_source("return None\nraise", exception_operator="except*")
    assert not _source_handler_is_approved(unsafe_try_star)


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
        relative_path = str(tracked_path.relative_to(ROOT))
        source = tracked_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relative_path)

        for node in ast.walk(tree):
            if not isinstance(node, ast.Try | ast.TryStar):
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


def _required_markdown_section(markdown: str, heading: str, next_heading: str) -> str:
    _, heading_separator, section_remainder = markdown.partition(heading)
    assert heading_separator, f"Missing required Markdown heading: {heading}"
    section, next_separator, _ = section_remainder.partition(next_heading)
    assert next_separator, f"Missing Markdown boundary after: {heading}"
    return " ".join(section.split())


def _python_comment_blocks(source_path: Path) -> list[tuple[int, str]]:
    source_text = source_path.read_text(encoding="utf-8")
    source_lines = source_text.splitlines()
    comment_tokens = [
        (
            python_token.start[0],
            python_token.start[1],
            not source_lines[python_token.start[0] - 1][: python_token.start[1]].strip(),
            python_token.string,
        )
        for python_token in tokenize.generate_tokens(StringIO(source_text).readline)
        if python_token.type == tokenize.COMMENT
    ]
    grouped_comments: list[tuple[int, int, int, bool, str]] = []

    for line_number, column, is_full_line, comment_text in comment_tokens:
        previous_comment = grouped_comments[-1] if grouped_comments else None
        if (
            previous_comment
            and is_full_line
            and previous_comment[3]
            and line_number == previous_comment[1] + 1
            and column == previous_comment[2]
        ):
            start_line, _, _, _, previous_text = previous_comment
            grouped_comments[-1] = (
                start_line,
                line_number,
                column,
                is_full_line,
                f"{previous_text} {comment_text}",
            )
        else:
            grouped_comments.append(
                (line_number, line_number, column, is_full_line, comment_text)
            )

    return [
        (start_line, comment_text)
        for start_line, _, _, _, comment_text in grouped_comments
    ]


G3_REFERENCE = re.compile(r"\bG3\b", re.IGNORECASE)
G3_DEFERRAL_ACTION_PATTERN = (
    r"(?:defer(?:s|red|ring)?|block(?:s|ed|ing)?|preserv(?:e|es|ed|ing)|"
    r"prevent(?:s|ed|ing)?|retain(?:s|ed)?|retaining)"
)
G3_DEFERRAL_ACTION = re.compile(
    rf"\b{G3_DEFERRAL_ACTION_PATTERN}\b",
    re.IGNORECASE,
)
G3_DEFERRED_WORK = re.compile(
    r"(?:facade\s+(?:removal|cleanup)|test\s+(?:facade|seam)|patch\s+target|"
    r"deduplicat\w*|de-fac\w*)",
    re.IGNORECASE,
)
G3_NEGATION_GAP = (
    r"(?:\s+(?!(?:so|therefore|thus|hence|then)\b)[a-z][\w'-]*){0,4}"
)
G3_NEGATED_DEFERRED_WORK = re.compile(
    rf"\b(?:neither|nor|no|not(?!\s+(?:only|just|merely)\b)){G3_NEGATION_GAP}\s+"
    rf"{G3_DEFERRED_WORK.pattern}",
    re.IGNORECASE,
)
G3_NEGATED_DEFERRAL_ACTION = re.compile(
    r"\b(?:no\s+longer|never|cannot|can't|does\s+not|doesn't|is\s+not|isn't|"
    r"not|without)(?!\s+(?:only|just|merely)\b)"
    rf"{G3_NEGATION_GAP}\s+{G3_DEFERRAL_ACTION_PATTERN}\b",
    re.IGNORECASE,
)
G3_POLICY_SENTENCE_BOUNDARY = re.compile(r"\.(?=\s|$)")
G3_POLICY_CLAUSE_BOUNDARY = re.compile(
    r"(;|,|\b(?:and|but|however|while|yet|so|therefore|thus|hence|then)\b)",
    re.IGNORECASE,
)
G3_NOUN_ACTION_CONTINUATION = re.compile(
    r"^\s+(?:are|is|was|were|exist|exists|listed|documented)\b",
    re.IGNORECASE,
)
G3_BLOCKER_POLICY = re.compile(r"\bG3\b\s+remains\s+a\s+blocker\b", re.IGNORECASE)
G3_PREREQUISITE_POLICY = re.compile(
    r"\bG3\b.{0,40}\b(?:is|remains)\s+(?:a\s+)?prerequisite\b",
    re.IGNORECASE,
)
G3_NEGATED_PREREQUISITE_POLICY = re.compile(
    r"\bG3\b.{0,40}\b(?:no\s+longer|not|never)\b.{0,30}\bprerequisite\b",
    re.IGNORECASE,
)


def _positive_g3_deferral_action(policy_clause: str) -> str | None:
    negated_action_spans = [
        negated_action.span()
        for negated_action in G3_NEGATED_DEFERRAL_ACTION.finditer(policy_clause)
    ]
    for deferral_action in G3_DEFERRAL_ACTION.finditer(policy_clause):
        if any(
            start <= deferral_action.start() < end
            for start, end in negated_action_spans
        ):
            continue
        if G3_NOUN_ACTION_CONTINUATION.search(
            policy_clause[deferral_action.end() :]
        ):
            continue
        return deferral_action.group(0)
    return None


def _has_positive_g3_deferred_work(policy_clause: str) -> bool:
    negated_work_spans = [
        negated_work.span()
        for negated_work in G3_NEGATED_DEFERRED_WORK.finditer(policy_clause)
    ]
    return any(
        not any(start <= deferred_work.start() < end for start, end in negated_work_spans)
        for deferred_work in G3_DEFERRED_WORK.finditer(policy_clause)
    )


def _g3_clause_defers_work(policy_clause: str) -> bool:
    return bool(
        G3_REFERENCE.search(policy_clause)
        and _has_positive_g3_deferred_work(policy_clause)
        and (
            _positive_g3_deferral_action(policy_clause)
            or G3_BLOCKER_POLICY.search(policy_clause)
            or (
                G3_PREREQUISITE_POLICY.search(policy_clause)
                and not G3_NEGATED_PREREQUISITE_POLICY.search(policy_clause)
            )
        )
    )


def _g3_sentence_defers_work(policy_sentence: str) -> bool:
    has_g3_context = False
    inherited_deferral_action: str | None = None
    preceding_boundary = ""
    policy_parts = G3_POLICY_CLAUSE_BOUNDARY.split(policy_sentence)
    for part_index in range(0, len(policy_parts), 2):
        policy_clause = policy_parts[part_index]
        if preceding_boundary and preceding_boundary != "and":
            inherited_deferral_action = None
        clause_has_g3 = bool(G3_REFERENCE.search(policy_clause))
        if clause_has_g3:
            has_g3_context = True
        positive_deferral_action = _positive_g3_deferral_action(policy_clause)
        if positive_deferral_action:
            inherited_deferral_action = positive_deferral_action
        elif G3_DEFERRAL_ACTION.search(policy_clause):
            inherited_deferral_action = None
        inherited_policy = ""
        if has_g3_context and not clause_has_g3:
            inherited_policy = "G3 "
        if (
            inherited_deferral_action
            and not G3_DEFERRAL_ACTION.search(policy_clause)
        ):
            inherited_policy = f"{inherited_policy}{inherited_deferral_action} "
        scoped_clause = f"{inherited_policy}{policy_clause}"
        if _g3_clause_defers_work(scoped_clause):
            return True
        if part_index + 1 < len(policy_parts):
            preceding_boundary = policy_parts[part_index + 1].lower()
    return False


def _comment_block_defers_g3(comment_block: str) -> bool:
    normalized_comment = " ".join(comment_block.replace("#", " ").split())
    return any(
        _g3_sentence_defers_work(policy_sentence)
        for policy_sentence in G3_POLICY_SENTENCE_BOUNDARY.split(normalized_comment)
    )


G2_OPEN_POLICY = re.compile(
    r"(?:\bg2\b\s+(?:is|remains)\s+(?:open|pending|unresolved)\b"
    r"|\bg2\b\s*(?:status\s*)?:\s*(?:open|pending|unresolved)\b"
    r"|\bdecision\s+g2,\s+currently\s+(?:open|pending|unresolved)\b"
    r"|\b(?:open|pending|unresolved)\s+g2\b)",
    re.IGNORECASE,
)
OPERATOR_AUTH_APPROVAL_POLICY = re.compile(
    r"\boperator(?:-only)?(?: proxy)? authentication\s+(?:is\s+)?(?:approved|pending)\b",
    re.IGNORECASE,
)
G3_UNRESOLVED_POLICY = re.compile(
    r"(?:\bg3\b\s+(?:is|remains)\s+(?:open|pending|unresolved)\b"
    r"|\bg3\b\s*(?:status\s*)?:\s*(?:open|pending|unresolved)\b"
    r"|\b(?:open|pending|unresolved)\s+g3\b)",
    re.IGNORECASE,
)
PHASE_2_G3_BLOCKER_POLICY = re.compile(
    r"(?:\bphase 2\b.{0,40}\bblock\w*\b.{0,20}\bg3\b"
    r"|\bg3\b.{0,40}\bblock\w*\b.{0,20}\bphase 2\b)",
    re.IGNORECASE,
)


def _g2_policy_has_contradiction(g2_policy: str) -> bool:
    return bool(
        G2_OPEN_POLICY.search(g2_policy) or OPERATOR_AUTH_APPROVAL_POLICY.search(g2_policy)
    )


@pytest.mark.parametrize(
    "contradictory_policy",
    (
        "G2 is open.",
        "G2 status: pending.",
        "Pending G2.",
        "Operator-only authentication is approved.",
        "Operator authentication pending.",
    ),
)
def test_g2_policy_contradiction_detection_covers_equivalent_wording(
    contradictory_policy: str,
) -> None:
    assert _g2_policy_has_contradiction(contradictory_policy)


@pytest.mark.parametrize(
    "approved_policy",
    (
        "G2 is approved; T-SEC-4 remains pending.",
        "G2 is not open.",
        "Operator-only proxy authentication is not approved.",
    ),
)
def test_g2_policy_contradiction_detection_allows_approved_wording(
    approved_policy: str,
) -> None:
    assert not _g2_policy_has_contradiction(approved_policy)


def test_g2_visitor_access_policy_is_aligned_between_security_and_remediation_ledger():
    security_policy = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    remediation_ledger = (
        ROOT / "docs" / "plans" / "TOWN_COUNCIL_REMEDIATION_PLAN.md"
    ).read_text(encoding="utf-8")
    frontend_api_boundary = _required_markdown_section(
        security_policy,
        "2. Frontend server -> API:",
        "\n3. API and semantic service",
    )
    g2_entry = _required_markdown_section(
        remediation_ledger,
        "- G2 protected_action_policy:",
        "\n- G3 test_seam_adr:",
    )
    t_sec_4_entry = _required_markdown_section(
        remediation_ledger,
        "### T-SEC-4: Real client identity through the proxy; per-client rate limits",
        "\n### T-SEC-5:",
    )
    pending_row = next(
        line for line in remediation_ledger.splitlines() if line.startswith("| **Pending** |")
    )
    pending_tasks = {task.strip() for task in pending_row.split("|")[2].split(",")}

    assert "Decision G2, approved 2026-07-24" in frontend_api_boundary
    assert (
        "summarize, segment, extract, and topic-generation actions"
        in frontend_api_boundary
    )
    assert "public Next.js proxy" in frontend_api_boundary
    assert (
        "Direct calls to protected AI mutation endpoints, including vote extraction, still require "
        "`X-API-Key`"
        in frontend_api_boundary
    )
    assert "public read and task-status routes remain public" in frontend_api_boundary
    assert "**Approved 2026-07-24.**" in g2_entry
    assert "(summarize/segment/extract/topics)" in g2_entry
    assert "public Next.js proxy" in g2_entry
    assert "T-SEC-4 is authorized" in g2_entry
    assert "operator-only proxy authentication is not approved" in g2_entry
    assert "per-client rate limits" in frontend_api_boundary.lower()
    assert "per-client rate limits" in g2_entry.lower()
    assert "decision_gate: G2 approved 2026-07-24" in t_sec_4_entry
    assert "T-SEC-4" in pending_tasks
    canonical_g2_policy = f"{frontend_api_boundary} {g2_entry}".lower()
    assert not _g2_policy_has_contradiction(canonical_g2_policy)


def test_g2_accepted_risk_is_bounded_without_overclaiming_t_sec_4():
    security_policy = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    accepted_risk = _required_markdown_section(
        security_policy,
        "**Visitor-accessible AI actions before T-SEC-4.**",
        "\n## Dependency and supply chain",
    )

    assert "unauthenticated proxy callers" in accepted_risk
    assert "Direct calls to protected AI mutation endpoints remain API-key protected." in (
        accepted_risk
    )
    assert "T-SEC-5 reduces cross-site browser abuse but does not authenticate" in accepted_risk
    assert (
        "Revisit when T-SEC-4 merges or by 2026-08-31, whichever comes first."
        in accepted_risk
    )
    assert "- [ ] Client IP forwarded from proxy" in security_policy


def test_test_patch_points_policy_has_accepted_adr_and_effective_runbook():
    architecture_decisions = (ROOT / "docs" / "ADR.md").read_text(encoding="utf-8")
    testing_policy = (ROOT / "docs" / "TESTING.MD").read_text(encoding="utf-8")
    remediation_ledger = (
        ROOT / "docs" / "plans" / "TOWN_COUNCIL_REMEDIATION_PLAN.md"
    ).read_text(encoding="utf-8")
    test_patch_point_decision = _required_markdown_section(
        architecture_decisions,
        "## 2026-07-24: Test patch points are not a public API",
        "\n## 2026-05-17:",
    )
    g3_entry = _required_markdown_section(
        remediation_ledger,
        "- G3 test_seam_adr:",
        "\n- G4 pii_policy:",
    )
    t_gov_1_entry = _required_markdown_section(
        remediation_ledger,
        '### T-GOV-1: ADR — "Test patch points are not a public API" (gate G3)',
        "\n### T-GOV-2:",
    )
    t_gov_6_entry = _required_markdown_section(
        remediation_ledger,
        "### T-GOV-6: Introduce SECURITY.md, docs/TESTING.md, docs/DATA_GOVERNANCE.md",
        "\n---\n\n## 7. EXECUTION ORDER SUMMARY",
    )
    phase_2_policy = _required_markdown_section(
        remediation_ledger,
        "## 5. PHASE 2 — DEDUPLICATION & DE-FACADING",
        "\n### T-DA-1:",
    )
    complete_row = next(
        line for line in remediation_ledger.splitlines() if line.startswith("| **Complete** |")
    )
    in_progress_row = next(
        line
        for line in remediation_ledger.splitlines()
        if line.startswith("| **In progress** |")
    )
    partial_row = next(
        line
        for line in remediation_ledger.splitlines()
        if line.startswith("| **Partially landed; acceptance incomplete** |")
    )
    pending_row = next(
        line for line in remediation_ledger.splitlines() if line.startswith("| **Pending** |")
    )

    assert "- Status: Accepted" in test_patch_point_decision
    assert test_patch_point_decision.count("- Status:") == 1
    assert "only to the extent that" in test_patch_point_decision
    assert "test-only patch target" in test_patch_point_decision
    assert "Runtime, import, CLI, API, task-identity, and operational contracts remain active" in (
        test_patch_point_decision
    )
    assert "docs/TESTING.MD" in test_patch_point_decision
    assert "Status: effective." in testing_policy
    assert testing_policy.count("Status:") == 1
    assert "effective with the G3 ADR" not in testing_policy
    assert "**Satisfied 2026-07-24.**" in g3_entry
    assert "status: complete and verified 2026-07-24" in t_gov_1_entry
    assert t_gov_1_entry.count("- status:") == 1
    assert not re.search(
        r"\bstatus:\s*(?:draft|proposed|pending|in progress|incomplete)\b",
        f"{test_patch_point_decision} {testing_policy} {t_gov_1_entry}",
        re.IGNORECASE,
    )
    assert "T-GOV-1" in complete_row
    assert "T-GOV-1" not in pending_row
    assert "T-SEC-4A" not in complete_row
    assert "T-SEC-4A" in in_progress_row
    assert "T-GOV-6" in partial_row
    assert (
        "remains partially landed until its three canonical documents are linked from the README "
        "Documentation Map"
        in t_gov_6_entry
    )
    assert "## 5. PHASE 2 — DEDUPLICATION & DE-FACADING\n" in remediation_ledger
    assert "PHASE 2 — DEDUPLICATION & DE-FACADING (blocked by G3)" not in remediation_ledger
    active_g3_policy = (
        f"{test_patch_point_decision} {testing_policy} {g3_entry} "
        f"{t_gov_1_entry} {phase_2_policy}"
    )
    assert not G3_UNRESOLVED_POLICY.search(active_g3_policy)
    assert not PHASE_2_G3_BLOCKER_POLICY.search(active_g3_policy)


def test_live_python_does_not_treat_g3_as_a_facade_deferral():
    live_g3_references = []

    for source_path in _broad_exception_scan_files():
        relative_source_path = source_path.relative_to(ROOT)
        if relative_source_path.parts[0] in {"archive", "tests"}:
            continue
        for line_number, comment_block in _python_comment_blocks(source_path):
            if _comment_block_defers_g3(comment_block):
                live_g3_references.append(
                    f"{relative_source_path}:{line_number}: {comment_block}"
                )

    assert live_g3_references == []


def test_g3_deferral_scan_groups_wrapped_comment_blocks(tmp_path: Path):
    wrapped_policy = tmp_path / "wrapped_policy.py"
    wrapped_policy.write_text(
        "# G3 still\n# blocks facade removal.\n\n# An unrelated comment.\n",
        encoding="utf-8",
    )
    comment_blocks = _python_comment_blocks(wrapped_policy)

    assert comment_blocks == [
        (1, "# G3 still # blocks facade removal."),
        (4, "# An unrelated comment."),
    ]
    assert _comment_block_defers_g3(comment_blocks[0][1])
    assert not _comment_block_defers_g3(comment_blocks[1][1])


@pytest.mark.parametrize(
    "accepted_policy",
    (
        "# G3 no longer blocks facade removal while preserving the runtime API.",
        "# G3 blocks are listed in the report.",
        "# G3 preserves runtime API compatibility.",
        "# Facade removal is not blocked by G3.",
        "# Facade removal is not being blocked by G3.",
        "# G3 is pending for historical reference; facade removal is no longer blocked.",
        "# G3 remains open for discussion. The facade documentation is current.",
        "# G3 blocks migration and does not block facade removal and the test seam.",
        "# G3 blocks are documented and facade removal status is current.",
        "# G3 blocks are documented; facade removal status is current.",
        "# G3 block is documented and facade removal status is current.",
        "# G3 blocker is documented and facade removal status is current.",
        "# G3 preservation is documented and facade removal status is current.",
        "# G3 blocks migration, not facade removal.",
        "# G3 no longer blocks facade removal, preserving the runtime API.",
        "# G3 blocks neither facade removal nor test seams.",
        "# G3 preserves no test facade.",
        "# G3 is not expected to block facade removal.",
        "# G3 proceeds without blocking facade removal.",
        "# G3 preserves the public facade.",
        "# G3 preserves facade runtime compatibility.",
        "# G3 blocks cache removal.",
        "# G3 blocks temporary-file removal.",
        "# G3 no longer remains a prerequisite for facade removal.",
        "# G3 no longer is a prerequisite for facade removal.",
        "# G3 is no longer a prerequisite for facade removal.",
    ),
)
def test_g3_deferral_scan_allows_non_deferral_policy(accepted_policy: str):
    assert not _comment_block_defers_g3(accepted_policy)


@pytest.mark.parametrize(
    "deferred_policy",
    (
        "# G3 no longer blocks one cleanup, but G3 still preserves the test facade.",
        "# G3 no longer blocks one cleanup. # G3 still preserves the test facade.",
        "# G3 no longer blocks one cleanup, and G3 still preserves the test facade.",
        "# G3 no longer blocks one cleanup, yet G3 still preserves the test facade.",
        "# G3 no longer blocks facade removal and still preserves the test seam.",
        "# G3 blocks migration and facade removal.",
        "# G3 preserves runtime compatibility and the test facade.",
        "# G3 remains pending; therefore preserve the test facade.",
        "# G3 blockers are blocking facade removal.",
        "# G3 blocks are blocking facade removal.",
        "# G3 blocks are preserving the test facade.",
        "# G3 blocks api.main facade removal.",
        "# G3 blocks not only facade removal but also the test seam.",
        "# G3 not only blocks facade removal but also preserves the test seam.",
        "# G3 is not resolved, so preserve the test facade.",
        "# G3 is not resolved so preserve the test facade.",
        "# G3 is pending, so preserve the test facade.",
        "# G3 is still pending, so preserve the test facade.",
        "# G3 is unresolved, therefore block facade removal.",
        "# G3 remains a blocker for facade removal.",
        "# G3 prevents facade removal.",
        "# Until G3 is resolved, retain the test seam.",
        "# G3 remains a prerequisite for facade removal.",
        "# G3 is not resolved so remains a prerequisite for facade removal.",
    ),
)
def test_g3_deferral_scan_detects_positive_policy_after_other_negation(
    deferred_policy: str,
):
    assert _comment_block_defers_g3(deferred_policy)


def test_g3_deferral_scan_keeps_adjacent_inline_comments_separate(tmp_path: Path):
    unrelated_comments = tmp_path / "unrelated_comments.py"
    unrelated_comments.write_text(
        "first = 1  # G3 marker\n"
        "second = 2  # preserves runtime behavior\n"
        "# G3 standalone\n"
        "third = 3  # blocks invalid input\n",
        encoding="utf-8",
    )
    comment_blocks = _python_comment_blocks(unrelated_comments)

    assert comment_blocks == [
        (1, "# G3 marker"),
        (2, "# preserves runtime behavior"),
        (3, "# G3 standalone"),
        (4, "# blocks invalid input"),
    ]
    assert not any(
        _comment_block_defers_g3(comment_text)
        for _, comment_text in comment_blocks
    )
