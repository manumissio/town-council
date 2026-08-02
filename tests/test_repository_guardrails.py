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
TEST_EXECUTABLE_MODE = 0o755
CPU_DEPENDENCY_AUDIT_ENV = (
    "PIP_CONSTRAINT=docker/semantic-cpu-constraints.txt "
    "PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu "
)
GENERATED_TIMESTAMP_COLUMNS = (
    ("person", "created_at"),
    ("data_issue", "created_at"),
    ("url_stage", "created_at"),
    ("event_stage", "scraped_datetime"),
    ("event", "scraped_datetime"),
    ("url_stage_hist", "created_at"),
    ("semantic_embedding", "updated_at"),
    ("catalog", "created_at"),
    ("catalog", "uploaded_at"),
    ("document", "created_at"),
)
LIFECYCLE_TIMESTAMP_COLUMNS = (
    ("catalog", "extraction_attempted_at"),
    ("catalog", "lineage_updated_at"),
    ("catalog", "agenda_segmentation_attempted_at"),
)
RETIRED_DTZ007_PATHS = (
    "pipeline/city_onboarding_metrics.py",
    "pipeline/run_pipeline_onboarding.py",
    "scripts/check_city_crawl_evidence.py",
    "scripts/reset_city_verification_state.py",
)
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
STRUCTURAL_SCAN_EXCLUDED_PREFIXES = {"tests"}
SYNC_GLOBAL_FUNCTION_NAME = re.compile(r"^_sync_.+_from_.+$")
LEXICAL_SCOPE_NODES = (
    ast.Module,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.Lambda,
)
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
    "api/main.py",
    "pipeline/agenda_legistar.py",
    "pipeline/agenda_worker.py",
    "pipeline/check_faiss_runtime.py",
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
    "pipeline/legistar_roster.py",
    "pipeline/roster_contracts.py",
    "pipeline/roster_sync.py",
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
HELPER_FACADE_IMPORT_RULES = (
    ("api/app_setup.py", ("api.main",)),
    (
        "pipeline/summary_hydration_diagnostic_samples.py",
        (
            "pipeline.summary_hydration_diagnostics",
            "pipeline.summary_hydration_diagnostic_queries",
        ),
    ),
    ("scripts/operator_profile_ab_aggregate.py", ("scripts.operator_profile_ab",)),
    (
        "scripts/collect_ab_results_rows.py",
        ("scripts.collect_ab_results", "scripts.evaluate_soak_week"),
    ),
    (
        "scripts/evaluate_soak_week_gates.py",
        ("scripts.collect_ab_results", "scripts.evaluate_soak_week"),
    ),
    (
        "scripts/operator_profile_worker_metrics.py",
        (
            "scripts.operator_profile_metrics",
            "scripts.profile_pipeline",
            "scripts.profile_pipeline_runner",
        ),
    ),
    (
        "scripts/profile_pipeline_commands.py",
        (
            "scripts.operator_profile_metrics",
            "scripts.profile_pipeline",
            "scripts.profile_pipeline_runner",
        ),
    ),
    (
        "scripts/profile_pipeline_results.py",
        (
            "scripts.operator_profile_metrics",
            "scripts.profile_pipeline",
            "scripts.profile_pipeline_runner",
        ),
    ),
    ("api/search_read_meilisearch.py", ("api.search_read_routes",)),
    ("api/search_read_params.py", ("api.search_read_routes",)),
    ("api/search_read_results.py", ("api.search_read_routes",)),
    ("pipeline/city_coverage_assembly.py", ("pipeline.city_coverage_audit",)),
    ("pipeline/city_coverage_buckets.py", ("pipeline.city_coverage_audit",)),
    ("pipeline/city_coverage_contracts.py", ("pipeline.city_coverage_audit",)),
    ("pipeline/city_coverage_queries.py", ("pipeline.city_coverage_audit",)),
    ("pipeline/city_coverage_windows.py", ("pipeline.city_coverage_audit",)),
    ("pipeline/lineage_assignment.py", ("pipeline.lineage_service",)),
    ("pipeline/lineage_graph.py", ("pipeline.lineage_service",)),
    (
        "scripts/laserfiche_repair_generated_pdf.py",
        (
            "scripts.repair_san_mateo_laserfiche_backlog",
            "scripts.laserfiche_repair_downloads",
        ),
    ),
    ("semantic_service/candidates.py", ("semantic_service.main",)),
    ("semantic_service/filters.py", ("semantic_service.main",)),
    ("semantic_service/retrieval.py", ("semantic_service.main",)),
    ("semantic_service/hydration.py", ("semantic_service.main",)),
    (
        "pipeline/summary_backfill_progress.py",
        ("pipeline.summary_backfill", "pipeline.summary_backfill_runner"),
    ),
    (
        "pipeline/vote_extraction_item.py",
        ("pipeline.vote_extractor", "pipeline.vote_extraction_runner"),
    ),
)
SEMANTIC_FACADE_LOOKUP_PATHS = (
    "pipeline/semantic_faiss_artifacts.py",
    "pipeline/semantic_faiss_backend.py",
    "pipeline/semantic_faiss_rows.py",
    "pipeline/semantic_pgvector_backend.py",
    "pipeline/semantic_pgvector_rerank.py",
)
SEMANTIC_BACKEND_CLASS_ALIASES = {
    "pipeline/semantic_faiss_backend.py": {
        "_artifact_paths",
        "_collect_rows",
        "_load_artifacts",
        "_write_artifacts",
    },
    "pipeline/semantic_pgvector_backend.py": {
        "_collect_catalog_summary_rows",
        "rerank_candidates_with_diagnostics",
    },
}


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


def test_summary_generation_uses_direct_operation_boundaries() -> None:
    summary_module_paths = (
        ROOT / "pipeline/task_summary_generation.py",
        ROOT / "pipeline/task_summary_generation_contracts.py",
        ROOT / "pipeline/task_summary_generation_flow.py",
        ROOT / "pipeline/task_summary_generation_persistence.py",
        ROOT / "pipeline/task_summary_empty_agenda.py",
        ROOT / "pipeline/task_summary_side_effects.py",
    )
    combined_source = "\n".join(
        summary_module_path.read_text(encoding="utf-8")
        for summary_module_path in summary_module_paths
    )
    tasks_source = (ROOT / "pipeline/tasks.py").read_text(encoding="utf-8")

    assert "SummaryGenerationTaskServices" not in combined_source
    assert "run_generate_summary_task_family" not in combined_source
    assert "backlog_maintenance" not in combined_source
    assert "agenda_summary_maintenance" not in combined_source
    assert "_summary_generation_task_services" not in tasks_source
    assert "_run_generate_summary_task_family" not in tasks_source

    lower_module_paths = summary_module_paths[1:]
    forbidden_imports = {
        str(summary_module_path.relative_to(ROOT)): _forbidden_imports(
            summary_module_path,
            {
                "pipeline.tasks",
                "pipeline.task_summary_generation",
            },
        )
        for summary_module_path in lower_module_paths
    }
    assert forbidden_imports == {
        str(summary_module_path.relative_to(ROOT)): []
        for summary_module_path in lower_module_paths
    }


def test_task_facade_helper_layer_is_deleted() -> None:
    helper_path = ROOT / "pipeline/task_facade_helpers.py"
    tasks_path = ROOT / "pipeline/tasks.py"
    tasks_tree = ast.parse(tasks_path.read_text(encoding="utf-8"))

    assert not helper_path.exists()
    assert not {
        "SessionLocal",
        "_TASK_FACADE_DEPENDENCIES",
        "_agenda_segmentation_task_services",
        "_extract_agenda_titles_from_text",
        "_persist_agenda_segmentation_failure_status",
        "_record_agenda_segmentation_status",
        "_run_extract_text_task_family",
        "_run_extract_votes_task_family",
        "_run_post_segmentation_vote_extraction",
        "_run_segment_agenda_task_family",
    } & _top_level_bound_names(tasks_tree)
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "globals"
        for node in ast.walk(tasks_tree)
    )

    expected_family_parameters = {
        "pipeline/task_text_extraction.py": {
            "run_extract_text_task_family": {"db", "catalog_id", "force", "ocr_fallback"},
        },
        "pipeline/task_vote_extraction.py": {
            "run_extract_votes_task_family": {"db", "catalog_id", "force", "local_ai"},
        },
        "pipeline/task_agenda_segmentation.py": {
            "persist_agenda_segmentation_failure_status": {"db", "catalog_id", "error_message"},
            "record_agenda_segmentation_status": {"catalog", "status", "item_count", "error_message"},
            "run_post_segmentation_vote_extraction": {"db", "local_ai", "catalog", "doc", "created_items"},
            "run_segment_agenda_task_family": {"db", "catalog_id", "local_ai"},
        },
        "pipeline/task_startup.py": {
            "run_startup_purge_on_worker_ready": {"sender"},
        },
    }
    for relative_path, function_contracts in expected_family_parameters.items():
        module_path = ROOT / relative_path
        module_tree = ast.parse(module_path.read_text(encoding="utf-8"))
        module_functions = {
            node.name: node
            for node in module_tree.body
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        }
        assert "AgendaSegmentationTaskServices" not in _top_level_bound_names(module_tree)
        assert _forbidden_imports(module_path, {"pipeline.tasks", "pipeline.task_facade_helpers"}) == []
        for function_name, expected_parameters in function_contracts.items():
            assert _function_parameter_names(module_functions[function_name]) == expected_parameters


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


def _tracked_forbidden_imports(forbidden_modules: set[str]) -> dict[str, list[str]]:
    remaining_imports: dict[str, list[str]] = {}
    for tracked_path in _tracked_files():
        if tracked_path.suffix != ".py" or not tracked_path.is_file():
            continue
        forbidden_imports = _forbidden_imports(tracked_path, forbidden_modules)
        if forbidden_imports:
            remaining_imports[str(tracked_path.relative_to(ROOT))] = forbidden_imports
    return remaining_imports


def _dotted_reference(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if not isinstance(node, ast.Attribute):
        return None
    parent_reference = _dotted_reference(node.value)
    if parent_reference is None:
        return None
    return f"{parent_reference}.{node.attr}"


def _search_main_import_context(
    test_tree: ast.AST,
    forbidden_names: set[str],
) -> tuple[set[str], set[str]]:
    main_module_bindings: set[str] = set()
    references: set[str] = set()
    for node in ast.walk(test_tree):
        if isinstance(node, ast.Import):
            main_module_bindings.update(
                alias.asname or "api.main"
                for alias in node.names
                if alias.name == "api.main"
            )
        elif isinstance(node, ast.ImportFrom) and node.module == "api":
            main_module_bindings.update(
                alias.asname or alias.name
                for alias in node.names
                if alias.name == "main"
            )
        elif isinstance(node, ast.ImportFrom) and node.module == "api.main":
            references.update(
                f"line {node.lineno}: import {alias.name}"
                for alias in node.names
                if alias.name in forbidden_names
            )
    return main_module_bindings, references


def _search_main_object_patch_reference(
    node: ast.AST,
    main_module_bindings: set[str],
    forbidden_names: set[str],
) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    patch_function = _dotted_reference(node.func) or ""
    is_object_patch = patch_function.endswith("patch.object")
    is_setattr_patch = patch_function == "setattr" or patch_function.endswith(
        ".setattr"
    )
    if not is_object_patch and not is_setattr_patch:
        return None
    if (
        len(node.args) < 2
        or _dotted_reference(node.args[0]) not in main_module_bindings
    ):
        return None
    patch_name = node.args[1]
    if not isinstance(patch_name, ast.Constant) or patch_name.value not in forbidden_names:
        return None
    patch_operation = "patch.object" if is_object_patch else "setattr"
    return f"line {node.lineno}: {patch_operation} {patch_name.value}"


def _search_main_alias_references(
    test_path: Path,
    forbidden_names: set[str],
) -> list[str]:
    test_tree = ast.parse(
        test_path.read_text(encoding="utf-8"),
        filename=str(test_path),
    )
    main_module_bindings, references = _search_main_import_context(
        test_tree,
        forbidden_names,
    )

    forbidden_references = {
        f"{module_binding}.{forbidden_name}"
        for module_binding in main_module_bindings
        for forbidden_name in forbidden_names
    }
    forbidden_references.update(
        f"api.main.{forbidden_name}" for forbidden_name in forbidden_names
    )

    for node in ast.walk(test_tree):
        dotted_reference = _dotted_reference(node)
        if dotted_reference and any(
            dotted_reference == forbidden_reference
            or dotted_reference.startswith(f"{forbidden_reference}.")
            for forbidden_reference in forbidden_references
        ):
            references.add(f"line {node.lineno}: {dotted_reference}")
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and any(
                node.value == forbidden_reference
                or node.value.startswith(f"{forbidden_reference}.")
                for forbidden_reference in forbidden_references
            )
        ):
            references.add(f"line {node.lineno}: {node.value}")
        patch_reference = _search_main_object_patch_reference(
            node,
            main_module_bindings,
            forbidden_names,
        )
        if patch_reference is not None:
            references.add(patch_reference)

    return sorted(references)


def _top_level_sync_function_lines(module_path: Path) -> list[int]:
    module_tree = ast.parse(
        module_path.read_text(encoding="utf-8"),
        filename=str(module_path),
    )
    return sorted(
        statement.lineno
        for statement in _nodes_in_lexical_scope(module_tree)
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
        and SYNC_GLOBAL_FUNCTION_NAME.fullmatch(statement.name)
    )


def _nodes_in_lexical_scope(scope_node: ast.AST) -> list[ast.AST]:
    scope_body = scope_node.body if hasattr(scope_node, "body") else []
    pending_nodes = list(scope_body) if isinstance(scope_body, list) else [scope_body]
    scope_nodes: list[ast.AST] = []

    while pending_nodes:
        current_node = pending_nodes.pop()
        scope_nodes.append(current_node)
        if isinstance(current_node, LEXICAL_SCOPE_NODES[1:]):
            continue
        pending_nodes.extend(ast.iter_child_nodes(current_node))

    return scope_nodes


def _is_production_structural_path(relative_source_path: Path) -> bool:
    return relative_source_path.parts[0] not in STRUCTURAL_SCAN_EXCLUDED_PREFIXES


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
    assert 'select = ["E722", "F401", "F403", "F841", "B", "BLE001", "C901", "DTZ", "S"]' in config_text
    assert (
        '"scripts/*.py" = ["F401", "S101", "S105", "S112", "S310", "S311", '
        '"S324", "S603", "S607"]'
    ) in config_text
    assert "pipeline/*.py" not in config_text
    assert "api/*.py" not in config_text


def test_timestamp_models_require_aware_server_owned_utc_values():
    from pipeline.models import Base

    for table_name, column_name in GENERATED_TIMESTAMP_COLUMNS:
        timestamp_column = Base.metadata.tables[table_name].c[column_name]

        assert timestamp_column.type.timezone is True
        assert timestamp_column.default is None
        assert timestamp_column.server_default is not None

    for table_name, column_name in LIFECYCLE_TIMESTAMP_COLUMNS:
        timestamp_column = Base.metadata.tables[table_name].c[column_name]

        assert timestamp_column.type.timezone is True
        assert timestamp_column.nullable is True
        assert timestamp_column.default is None
        assert timestamp_column.server_default is None


def test_timezone_migration_retires_only_the_owned_dtz007_exceptions():
    ignore_entries = _ruff_per_file_ignore_entries()

    assert all("DTZ007" not in ignore_entries.get(relative_path, set()) for relative_path in RETIRED_DTZ007_PATHS)


def test_timezone_migration_uses_only_literal_direct_sqlalchemy_text_calls():
    migration_source = (ROOT / "pipeline" / "migrate_v10.py").read_text(
        encoding="utf-8"
    )
    migration_tree = ast.parse(migration_source)
    sqlalchemy_imports = {
        (alias.name, None, alias.asname)
        for node in ast.walk(migration_tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name == "sqlalchemy" or alias.name.startswith("sqlalchemy.")
    } | {
        (node.module, alias.name, alias.asname)
        for node in ast.walk(migration_tree)
        if isinstance(node, ast.ImportFrom)
        and node.module
        and (node.module == "sqlalchemy" or node.module.startswith("sqlalchemy."))
        for alias in node.names
    }
    text_calls = [
        node
        for node in ast.walk(migration_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "text"
    ]
    text_name_references = [
        node
        for node in ast.walk(migration_tree)
        if isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Load)
        and node.id == "text"
    ]

    assert sqlalchemy_imports == {
        ("sqlalchemy", "DDL", None),
        ("sqlalchemy", "text", None),
        ("sqlalchemy.engine", "Connection", None),
    }
    assert text_calls
    assert {id(reference) for reference in text_name_references} == {
        id(text_call.func) for text_call in text_calls
    }
    assert all(
        len(text_call.args) == 1
        and not text_call.keywords
        and isinstance(text_call.args[0], ast.Constant)
        and isinstance(text_call.args[0].value, str)
        for text_call in text_calls
    )


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


def test_ruff_rejects_wildcard_imports_and_sql_interpolation() -> None:
    planted_violations = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--stdin-filename",
            "scripts/t_gov_3b_probe.py",
            "-",
        ],
        cwd=ROOT,
        input=(
            "from sqlalchemy import *\n"
            'table_name = "catalog"\n'
            'query = f"SELECT * FROM {table_name}"\n'
        ),
        capture_output=True,
        text=True,
        check=False,
    )

    assert planted_violations.returncode == RUFF_VIOLATION_EXIT
    assert "F403" in planted_violations.stdout
    assert "S608" in planted_violations.stdout


def test_ruff_structural_rule_suppressions_stay_explicit() -> None:
    structural_rule_targets = [
        str(source_path.relative_to(ROOT))
        for source_path in _broad_exception_scan_files()
        if _is_production_structural_path(source_path.relative_to(ROOT))
    ]
    structural_rule_check = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--isolated",
            "--ignore-noqa",
            "--select",
            "F403,S608",
            "--output-format",
            "json",
            *structural_rule_targets,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert structural_rule_check.returncode == RUFF_VIOLATION_EXIT
    structural_rule_violations = json.loads(structural_rule_check.stdout)
    assert [
        (
            str(Path(violation["filename"]).relative_to(ROOT)),
            violation["location"]["row"],
            violation["code"],
        )
        for violation in structural_rule_violations
    ] == [("pipeline/metrics.py", 12, "F403")]


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


def test_python_guardrails_provide_mandatory_pgvector_postgres():
    workflow_text = (ROOT / ".github" / "workflows" / "python-guardrails.yml").read_text(encoding="utf-8")
    workflow_contract = yaml.load(workflow_text, Loader=yaml.BaseLoader)
    guardrail_job = workflow_contract["jobs"]["python-guardrails"]
    postgres_service = guardrail_job["services"]["postgres"]

    assert guardrail_job["env"]["TEST_POSTGRES_DATABASE_URL"] == (
        "postgresql://town_council:town_council_test@localhost:5432/town_council_test"
    )
    assert postgres_service["image"] == "pgvector/pgvector:pg15"
    assert postgres_service["env"] == {
        "POSTGRES_DB": "town_council_test",
        "POSTGRES_PASSWORD": "town_council_test",
        "POSTGRES_USER": "town_council",
    }
    assert postgres_service["ports"] == ["5432:5432"]
    assert "pg_isready" in postgres_service["options"]


def test_python_guardrails_run_migration_acceptance_before_full_suite():
    workflow_text = (
        ROOT / ".github" / "workflows" / "python-guardrails.yml"
    ).read_text(encoding="utf-8")
    migration_step = (
        "      - name: Run PostgreSQL migration acceptance\n"
        "        run: PYTHONPATH=. python -m pytest -q "
        "tests/test_alembic_migrations.py"
    )
    full_suite_marker = "      - name: Run full Python test suite\n"

    assert workflow_text.count(migration_step) == 1
    assert workflow_text.index(migration_step) < workflow_text.index(full_suite_marker)
    migration_step_body = workflow_text.partition(migration_step)[2].partition(
        "\n      - name:"
    )[0]
    assert "continue-on-error:" not in migration_step_body
    assert "if:" not in migration_step_body


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


def _action_reference_targets(
    action_reference: str,
    action_name: str,
) -> bool:
    action_target, version_separator, _ = action_reference.partition("@")
    return bool(version_separator) and action_target.casefold() == action_name.casefold()


def _active_workflow_action_references(action_name: str) -> tuple[str, ...]:
    workflow_directory = ROOT / ".github" / "workflows"
    workflow_paths = sorted(
        (*workflow_directory.glob("*.yml"), *workflow_directory.glob("*.yaml"))
    )
    action_references: list[str] = []

    for workflow_path in workflow_paths:
        workflow_contract = yaml.load(
            workflow_path.read_text(encoding="utf-8"),
            Loader=yaml.BaseLoader,
        )
        assert isinstance(workflow_contract, dict)
        workflow_jobs = workflow_contract.get("jobs")
        assert isinstance(workflow_jobs, dict)
        for workflow_job in workflow_jobs.values():
            assert isinstance(workflow_job, dict)
            workflow_steps = workflow_job.get("steps", ())
            assert isinstance(workflow_steps, (list, tuple))
            action_references.extend(
                action_reference
                for workflow_step in workflow_steps
                if isinstance(workflow_step, dict)
                and isinstance(
                    action_reference := workflow_step.get("uses"),
                    str,
                )
                and _action_reference_targets(action_reference, action_name)
            )
    return tuple(action_references)


@pytest.mark.parametrize(
    ("action_reference", "action_name", "targets_action"),
    (
        ("Actions/Checkout@v4", "actions/checkout", True),
        ("actions/checkout@v7", "actions/checkout", True),
        ("actions/checkout-helper@v7", "actions/checkout", False),
        ("actions/checkout", "actions/checkout", False),
    ),
)
def test_workflow_action_matching_follows_github_repository_identity(
    action_reference: str,
    action_name: str,
    targets_action: bool,
) -> None:
    assert _action_reference_targets(action_reference, action_name) is targets_action


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

    assert "uses: actions/checkout@v7" in workflow_text
    assert "uses: actions/setup-node@v7" in workflow_text
    assert 'node-version: "20"' in workflow_text
    assert 'cache: "npm"' in workflow_text
    assert "cache-dependency-path: frontend/package-lock.json" in workflow_text
    assert "working-directory: frontend" in workflow_text
    assert workflow_text.index(install_step) < workflow_text.index(test_step)
    assert "continue-on-error:" not in workflow_text
    assert "if:" not in workflow_text
    assert "strategy:" not in workflow_text


def test_active_workflows_use_setup_node_v7() -> None:
    assert set(_active_workflow_action_references("actions/setup-node")) == {
        "actions/setup-node@v7"
    }


def test_active_workflows_use_checkout_v7() -> None:
    assert set(_active_workflow_action_references("actions/checkout")) == {
        "actions/checkout@v7"
    }


def _workflow_run_step(
    workflow_path: Path,
    workflow_job_id: str,
    workflow_step_name: str,
) -> str:
    workflow_contract = yaml.load(
        workflow_path.read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    workflow_steps = workflow_contract["jobs"][workflow_job_id]["steps"]
    matching_steps = [
        workflow_step
        for workflow_step in workflow_steps
        if workflow_step.get("name") == workflow_step_name
    ]
    assert len(matching_steps) == 1
    workflow_script = matching_steps[0].get("run")
    assert isinstance(workflow_script, str)
    return workflow_script


def _write_test_executable(executable_path: Path, executable_source: str) -> None:
    executable_path.write_text(executable_source, encoding="utf-8")
    executable_path.chmod(TEST_EXECUTABLE_MODE)


def _run_workflow_script(
    workflow_script: str,
    working_directory: Path,
    environment_overrides: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    workflow_environment = os.environ.copy()
    workflow_environment.update(environment_overrides)
    return subprocess.run(
        ["bash", "-c", workflow_script],
        cwd=working_directory,
        env=workflow_environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_dependabot_checks_every_dependency_manifest_weekly_and_groups_python_updates() -> None:
    dependabot_contract = yaml.load(
        (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )

    assert dependabot_contract["version"] == "2"
    assert dependabot_contract["updates"] == [
        {
            "package-ecosystem": "pip",
            "directories": [
                "/",
                "/api",
                "/council_crawler",
                "/pipeline",
                "/semantic_service",
            ],
            "schedule": {"interval": "weekly"},
            "groups": {
                "python-dependencies": {
                    "group-by": "dependency-name",
                },
            },
        },
        {
            "package-ecosystem": "npm",
            "directory": "/frontend",
            "schedule": {"interval": "weekly"},
        },
        {
            "package-ecosystem": "github-actions",
            "directory": "/",
            "schedule": {"interval": "weekly"},
        },
    ]


def test_python_dependency_audit_covers_six_separate_environments() -> None:
    workflow_path = ROOT / ".github" / "workflows" / "python-guardrails.yml"
    workflow_text = workflow_path.read_text(encoding="utf-8")
    audit_script = _workflow_run_step(
        workflow_path,
        "python-guardrails",
        "Audit Python dependency environments",
    )
    expected_audit_commands = (
        "audit_requirements api -r api/requirements.txt",
        "audit_requirements crawler -r council_crawler/requirements.txt",
        (
            f"{CPU_DEPENDENCY_AUDIT_ENV}"
            "audit_requirements worker-live -r pipeline/requirements.txt"
        ),
        (
            f"{CPU_DEPENDENCY_AUDIT_ENV}"
            "audit_requirements worker-batch -r pipeline/requirements.txt "
            "-r pipeline/requirements-batch.txt"
        ),
        (
            "audit_requirements semantic -r semantic_service/requirements.txt"
        ),
        "audit_requirements development -r pipeline/requirements-dev.txt",
    )
    configured_audit_commands = tuple(
        workflow_line.strip()
        for workflow_line in audit_script.splitlines()
        if "audit_requirements " in workflow_line
    )

    assert configured_audit_commands == expected_audit_commands
    assert "python-version: \"3.12\"" in workflow_text
    assert "python -m pip install -c constraints.txt pip-audit" in workflow_text
    assert "python -m pip install scikit-learn==1.8.0" not in workflow_text
    assert workflow_text.index("Run full Python test suite") < workflow_text.index(
        "Audit Python dependency environments"
    )
    assert "pip-audit --strict --format json --output" in audit_script
    assert "continue-on-error:" not in workflow_text
    assert "if: always()" not in workflow_text
    assert "|| true" not in audit_script


@pytest.mark.parametrize(
    ("audit_status", "audit_payload", "should_pass"),
    (
        (
            "0",
            {"dependencies": [{"name": "safe", "version": "1", "vulns": []}], "fixes": []},
            True,
        ),
        (
            "1",
            {
                "dependencies": [
                    {
                        "name": "affected",
                        "version": "1",
                        "vulns": [{"id": "PYSEC-1", "fix_versions": ["2"]}],
                    }
                ],
                "fixes": [],
            },
            True,
        ),
        ("1", {"dependencies": [], "fixes": []}, False),
        ("1", {"error": "registry unavailable"}, False),
        ("2", {"dependencies": [], "fixes": []}, False),
    ),
)
def test_python_dependency_audit_distinguishes_findings_from_tool_failures(
    tmp_path: Path,
    audit_status: str,
    audit_payload: dict[str, object],
    should_pass: bool,
) -> None:
    workflow_script = _workflow_run_step(
        ROOT / ".github" / "workflows" / "python-guardrails.yml",
        "python-guardrails",
        "Audit Python dependency environments",
    )
    executable_directory = tmp_path / "bin"
    executable_directory.mkdir()
    _write_test_executable(
        executable_directory / "pip-audit",
        """#!/usr/bin/env bash
set -eu
report_path=""
case " $* " in
  *" pipeline/requirements.txt "*)
    test "$PIP_CONSTRAINT" = "docker/semantic-cpu-constraints.txt"
    test "$PIP_EXTRA_INDEX_URL" = "https://download.pytorch.org/whl/cpu"
    ;;
  *" semantic_service/requirements.txt "*)
    test -z "${PIP_CONSTRAINT:-}"
    test -z "${PIP_EXTRA_INDEX_URL:-}"
    ;;
esac
while [ "$#" -gt 0 ]; do
  if [ "$1" = "--output" ]; then
    report_path="$2"
    shift 2
  else
    shift
  fi
done
printf '%s' "$FAKE_AUDIT_JSON" > "$report_path"
exit "$FAKE_AUDIT_STATUS"
""",
    )
    workflow_result = _run_workflow_script(
        workflow_script,
        ROOT,
        {
            "FAKE_AUDIT_JSON": json.dumps(audit_payload),
            "FAKE_AUDIT_STATUS": audit_status,
            "PATH": (
                f"{executable_directory}:{Path(sys.executable).parent}:"
                f"{os.environ['PATH']}"
            ),
            "RUNNER_TEMP": str(tmp_path),
        },
    )

    assert (workflow_result.returncode == 0) is should_pass, workflow_result.stderr


def test_frontend_dependency_audit_runs_after_tests() -> None:
    workflow_path = ROOT / ".github" / "workflows" / "frontend-tests.yml"
    workflow_text = workflow_path.read_text(encoding="utf-8")
    audit_script = _workflow_run_step(
        workflow_path,
        "frontend-tests",
        "Audit frontend production dependencies",
    )

    assert workflow_text.index("Run frontend tests") < workflow_text.index(
        "Audit frontend production dependencies"
    )
    assert "npm audit --omit=dev --audit-level=high --json" in audit_script
    assert "continue-on-error:" not in workflow_text
    assert "if: always()" not in workflow_text
    assert "|| true" not in audit_script


@pytest.mark.parametrize(
    ("audit_status", "audit_payload", "should_pass"),
    (
        (
            "0",
            {
                "auditReportVersion": 2,
                "metadata": {"vulnerabilities": {"high": 0, "critical": 0}},
            },
            True,
        ),
        (
            "1",
            {
                "auditReportVersion": 2,
                "metadata": {"vulnerabilities": {"high": 1, "critical": 0}},
            },
            True,
        ),
        (
            "1",
            {
                "auditReportVersion": 2,
                "metadata": {"vulnerabilities": {"high": 0, "critical": 0}},
            },
            False,
        ),
        ("1", {"error": {"code": "ENETUNREACH"}}, False),
        (
            "2",
            {
                "auditReportVersion": 2,
                "metadata": {"vulnerabilities": {"high": 1, "critical": 0}},
            },
            False,
        ),
    ),
)
def test_frontend_dependency_audit_distinguishes_findings_from_tool_failures(
    tmp_path: Path,
    audit_status: str,
    audit_payload: dict[str, object],
    should_pass: bool,
) -> None:
    workflow_script = _workflow_run_step(
        ROOT / ".github" / "workflows" / "frontend-tests.yml",
        "frontend-tests",
        "Audit frontend production dependencies",
    )
    executable_directory = tmp_path / "bin"
    executable_directory.mkdir()
    _write_test_executable(
        executable_directory / "npm",
        """#!/usr/bin/env bash
set -eu
printf '%s' "$FAKE_AUDIT_JSON"
exit "$FAKE_AUDIT_STATUS"
""",
    )
    workflow_result = _run_workflow_script(
        workflow_script,
        ROOT / "frontend",
        {
            "FAKE_AUDIT_JSON": json.dumps(audit_payload),
            "FAKE_AUDIT_STATUS": audit_status,
            "PATH": f"{executable_directory}:{os.environ['PATH']}",
            "RUNNER_TEMP": str(tmp_path),
        },
    )

    assert (workflow_result.returncode == 0) is should_pass, workflow_result.stderr


def test_dependency_security_policy_matches_report_only_workflows() -> None:
    security_policy = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    dependency_policy = _required_markdown_section(
        security_policy,
        "## Dependency and supply chain",
        "\n## Reporting a vulnerability",
    )

    normalized_dependency_policy = dependency_policy.lower()
    assert "weekly version updates" in normalized_dependency_policy
    assert "report-only" in normalized_dependency_policy
    assert (
        "audit-tool, registry, network, and report-validation failures block"
        in normalized_dependency_policy
    )
    assert "vulnerability findings block merge" not in normalized_dependency_policy


def test_facade_import_guardrail_detects_relative_imports(tmp_path: Path):
    pipeline_helper = tmp_path / "pipeline" / "helper.py"
    pipeline_helper.parent.mkdir(parents=True)
    pipeline_helper.write_text(
        "from . import vote_extractor\n"
        "from .vote_extraction_runner import run_vote_extraction_for_catalog\n"
        "from pipeline.city_scope import city_scope\n",
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


def test_registered_helpers_do_not_import_facades():
    dependency_violations: dict[str, list[str]] = {}

    for helper_relative_path, forbidden_facades in HELPER_FACADE_IMPORT_RULES:
        helper_path = ROOT / helper_relative_path
        assert helper_path.is_file(), (
            f"Registered helper path does not exist: {helper_relative_path}"
        )
        forbidden_imports = _forbidden_imports(
            helper_path,
            set(forbidden_facades),
        )
        if forbidden_imports:
            dependency_violations[helper_relative_path] = forbidden_imports

    assert dependency_violations == {}


def test_provider_compatibility_facade_is_deleted() -> None:
    deleted_facade = ROOT / "pipeline/llm_provider.py"

    assert not deleted_facade.exists()
    assert _tracked_forbidden_imports({"pipeline.llm_provider"}) == {}


def test_semantic_index_facade_is_deleted() -> None:
    deleted_facade = ROOT / "pipeline/semantic_index.py"

    assert not deleted_facade.exists()
    assert _tracked_forbidden_imports({"pipeline.semantic_index"}) == {}


def test_semantic_backend_helpers_have_direct_owners() -> None:
    remaining_lookups: list[str] = []
    remaining_class_aliases: list[str] = []

    for semantic_lookup_path in SEMANTIC_FACADE_LOOKUP_PATHS:
        semantic_lookup_tree = ast.parse(
            (ROOT / semantic_lookup_path).read_text(encoding="utf-8")
        )
        if any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "_semantic_index_facade"
            for node in ast.walk(semantic_lookup_tree)
        ):
            remaining_lookups.append(semantic_lookup_path)

    for semantic_backend_path, forbidden_aliases in SEMANTIC_BACKEND_CLASS_ALIASES.items():
        semantic_backend_tree = ast.parse(
            (ROOT / semantic_backend_path).read_text(encoding="utf-8")
        )
        for class_node in (
            node for node in ast.walk(semantic_backend_tree) if isinstance(node, ast.ClassDef)
        ):
            class_aliases = {
                assignment_target.id
                for class_statement in class_node.body
                if isinstance(class_statement, (ast.Assign, ast.AnnAssign))
                for assignment_target in (
                    class_statement.targets
                    if isinstance(class_statement, ast.Assign)
                    else [class_statement.target]
                )
                if isinstance(assignment_target, ast.Name)
            }
            remaining_class_aliases.extend(
                f"{semantic_backend_path}:{alias_name}"
                for alias_name in sorted(class_aliases & forbidden_aliases)
            )

    assert remaining_lookups == []
    assert remaining_class_aliases == []


def test_search_helpers_do_not_lookup_api_main() -> None:
    lookup_names = {"_api_main", "facade_value", "facade_callable", "search_client"}
    main_search_aliases = {
        "client",
        "_build_meilisearch_filter_clauses",
        "_collect_meeting_docs",
        "_semantic_service_get_json",
        "search_documents_semantic",
        "SEMANTIC_ENABLED",
        "FEATURE_TRENDS_DASHBOARD",
    }
    support_core_path = ROOT / "api/search/support_core.py"
    support_core_tree = ast.parse(support_core_path.read_text(encoding="utf-8"))
    support_core_functions = {
        node.name
        for node in support_core_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    api_main_path = ROOT / "api/main.py"
    api_main_tree = ast.parse(api_main_path.read_text(encoding="utf-8"))
    api_main_imports = {
        alias.name
        for node in api_main_tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }

    search_helper_paths = sorted((ROOT / "api/search").rglob("*.py"))
    search_helper_paths.extend(sorted((ROOT / "api").glob("search_*.py")))
    search_helper_paths.append(ROOT / "api/trends_routes.py")
    reverse_imports = {
        str(search_helper_path.relative_to(ROOT)): forbidden_imports
        for search_helper_path in search_helper_paths
        if (
            forbidden_imports := _forbidden_imports(
                search_helper_path,
                {"api.main"},
            )
        )
    }

    stale_test_patches = {
        str(test_path.relative_to(ROOT)): alias_references
        for test_path in _tracked_files()
        if test_path.suffix == ".py"
        and test_path.relative_to(ROOT).parts[0] == "tests"
        and (
            alias_references := _search_main_alias_references(
                test_path,
                main_search_aliases,
            )
        )
    }

    assert lookup_names.isdisjoint(support_core_functions)
    assert main_search_aliases.isdisjoint(api_main_imports)
    assert reverse_imports == {}
    assert _forbidden_imports(
        ROOT / "api/search_read_meilisearch.py",
        {"api.search_support"},
    ) == []
    assert stale_test_patches == {}


def test_search_main_alias_guard_covers_import_and_object_patch_forms(
    tmp_path: Path,
) -> None:
    test_path = tmp_path / "test_stale_search_patches.py"
    test_path.write_text(
        "\n".join(
            (
                "import api.main",
                "import api.main as api_main",
                "from api import main as assembled_api",
                "from api.main import client as reader_client",
                "api.main" + ".SEMANTIC_ENABLED",
                "api_main._collect_meeting_docs",
                'mocker.patch("api.main.search_documents_semantic")',
                'mocker.patch.object(assembled_api, "FEATURE_TRENDS_DASHBOARD")',
                'monkeypatch.setattr(api_main, "client", replacement)',
                "from api.main import app",
            )
        ),
        encoding="utf-8",
    )

    alias_references = _search_main_alias_references(
        test_path,
        {
            "client",
            "_collect_meeting_docs",
            "search_documents_semantic",
            "SEMANTIC_ENABLED",
            "FEATURE_TRENDS_DASHBOARD",
        },
    )

    assert alias_references == [
        "line 4: import client",
        "line 5: api.main.SEMANTIC_ENABLED",
        "line 6: api_main._collect_meeting_docs",
        "line 7: api.main.search_documents_semantic",
        "line 8: patch.object FEATURE_TRENDS_DASHBOARD",
        "line 9: setattr client",
    ]


API_MAIN_ROUTER_FACADE_ALIASES = {
    "AsyncResult",
    "_enqueue_task",
    "_lineage_rows",
    "_summary_doc_kind_and_hashes",
    "agenda_items_look_low_quality",
    "extract_text_task",
    "extract_votes_task",
    "generate_summary_task",
    "generate_topics_task",
    "segment_agenda_task",
}
TASK_DISPATCH_COMPATIBILITY_EXPORTS = {
    "AsyncResult",
    "EXTRACT_TEXT_TASK_NAME",
    "EXTRACT_VOTES_TASK_NAME",
    "GENERATE_SUMMARY_TASK_NAME",
    "GENERATE_TOPICS_TASK_NAME",
    "INVALID_TASK_ID_DETAIL",
    "SEGMENT_AGENDA_TASK_NAME",
    "TASK_DISPATCH_ERRORS",
    "TASK_QUEUE_UNAVAILABLE_DETAIL",
    "_CeleryTaskProxy",
    "_enqueue_task",
    "extract_text_task",
    "extract_votes_task",
    "generate_summary_task",
    "generate_topics_task",
    "segment_agenda_task",
}
TASK_PROXY_GLOBALS = {
    "extract_text_task",
    "extract_votes_task",
    "generate_summary_task",
    "generate_topics_task",
    "segment_agenda_task",
}
SEARCH_ROUTE_COMPATIBILITY_EXPORTS = {
    "MEILI_HOST",
    "MEILI_MASTER_KEY",
    "_build_filter_values",
    "_build_meilisearch_filter_clauses",
    "_collect_meeting_docs",
    "_count_topics_from_docs",
    "_facet_topics",
    "_iter_time_buckets",
    "_normalize_city_or_400",
    "_normalize_filters_or_400",
    "_parse_iso_date",
    "_require_trends_feature",
    "_semantic_service_get_json",
    "_semantic_service_healthcheck",
    "client",
    "export_trends",
    "get_metadata",
    "get_trends_compare",
    "get_trends_topics",
    "httpx",
    "normalize_city_filter",
    "search_documents",
    "search_documents_semantic",
    "validate_date_format",
}


def _top_level_bound_names(module_tree: ast.Module) -> set[str]:
    bound_names: set[str] = set()
    for statement in module_tree.body:
        if isinstance(statement, ast.Import):
            bound_names.update(
                alias.asname or alias.name.split(".")[0]
                for alias in statement.names
            )
        elif isinstance(statement, ast.ImportFrom):
            bound_names.update(alias.asname or alias.name for alias in statement.names)
        elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound_names.add(statement.name)
        elif isinstance(statement, (ast.Assign, ast.AnnAssign)):
            assignment_targets = (
                statement.targets
                if isinstance(statement, ast.Assign)
                else [statement.target]
            )
            bound_names.update(
                target.id for target in assignment_targets if isinstance(target, ast.Name)
            )
    return bound_names


def _function_parameter_names(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> set[str]:
    function_arguments = function_node.args
    return {
        argument.arg
        for argument in (
            *function_arguments.posonlyargs,
            *function_arguments.args,
            *function_arguments.kwonlyargs,
        )
    }


def _is_current_module_registry_lookup(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "sys"
        and node.value.attr == "modules"
        and isinstance(node.slice, ast.Name)
        and node.slice.id == "__name__"
    )


def test_api_router_modules_do_not_expose_facade_dependency_bags() -> None:
    main_tree = ast.parse((ROOT / "api/main.py").read_text(encoding="utf-8"))
    lineage_tree = ast.parse(
        (ROOT / "api/lineage_routes.py").read_text(encoding="utf-8")
    )
    task_route_paths = (
        ROOT / "api/task_routes.py",
        ROOT / "api/task_route_generation.py",
        ROOT / "api/task_route_segmentation.py",
        ROOT / "api/task_route_summary.py",
        ROOT / "api/task_route_support.py",
    )
    task_route_trees = {
        str(task_route_path.relative_to(ROOT)): ast.parse(
            task_route_path.read_text(encoding="utf-8")
        )
        for task_route_path in task_route_paths
    }

    assert not any(
        _is_current_module_registry_lookup(node) for node in ast.walk(main_tree)
    )
    assert API_MAIN_ROUTER_FACADE_ALIASES.isdisjoint(
        _top_level_bound_names(main_tree)
    )
    lineage_parameters = {
        node.name: _function_parameter_names(node)
        for node in ast.walk(lineage_tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert lineage_parameters["build_lineage_router"] == {
        "limiter",
        "get_db_dependency",
    }

    task_route_parameters = {
        f"{module_path}:{node.name}": _function_parameter_names(node)
        for module_path, module_tree in task_route_trees.items()
        for node in ast.walk(module_tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert task_route_parameters["api/task_routes.py:build_task_router"] == {
        "limiter",
        "get_db_dependency",
        "verify_api_key_dependency",
    }
    assert task_route_parameters["api/task_route_generation.py:extract_votes_request"] == {
        "db",
        "catalog_id",
        "force",
    }
    assert task_route_parameters["api/task_route_generation.py:generate_topics_request"] == {
        "db",
        "catalog_id",
        "force",
    }
    assert task_route_parameters["api/task_route_generation.py:extract_catalog_text_request"] == {
        "db",
        "catalog_id",
        "force",
        "ocr_fallback",
    }
    assert task_route_parameters["api/task_route_segmentation.py:segment_agenda_request"] == {
        "db",
        "catalog_id",
        "force",
    }
    assert task_route_parameters["api/task_route_summary.py:summarize_document_request"] == {
        "db",
        "catalog_id",
        "force",
    }
    assert task_route_parameters["api/task_route_support.py:get_task_status_payload"] == {
        "task_id",
    }
    assert TASK_DISPATCH_COMPATIBILITY_EXPORTS.isdisjoint(
        _top_level_bound_names(task_route_trees["api/task_routes.py"])
    )


def test_api_router_compatibility_facades_are_deleted() -> None:
    search_routes_tree = ast.parse(
        (ROOT / "api/search_routes.py").read_text(encoding="utf-8")
    )
    task_dispatch_tree = ast.parse(
        (ROOT / "api/task_dispatch.py").read_text(encoding="utf-8")
    )

    assert not (ROOT / "api/search_support.py").exists()
    assert SEARCH_ROUTE_COMPATIBILITY_EXPORTS.isdisjoint(
        _top_level_bound_names(search_routes_tree)
    )
    assert "_CeleryTaskProxy" not in _top_level_bound_names(task_dispatch_tree)
    assert TASK_PROXY_GLOBALS.isdisjoint(_top_level_bound_names(task_dispatch_tree))


def test_api_main_patch_guard_allows_only_assembly_and_database_exports(
    tmp_path: Path,
) -> None:
    test_path = tmp_path / "test_router_facade_patches.py"
    test_path.write_text(
        "\n".join(
            (
                "from api.main import app, get_db",
                "import api.main as api_main",
                "from api import main as assembled_api",
                "from api.main import generate_summary_task",
                "api_main._lineage_rows",
                'mocker.patch("api.main.extract_text_task.delay")',
                'mocker.patch.object(assembled_api, "AsyncResult")',
                'monkeypatch.setattr(api_main, "_summary_doc_kind_and_hashes", replacement)',
            )
        ),
        encoding="utf-8",
    )

    alias_references = _search_main_alias_references(
        test_path,
        API_MAIN_ROUTER_FACADE_ALIASES,
    )

    assert alias_references == [
        "line 4: import generate_summary_task",
        "line 5: api_main._lineage_rows",
        "line 6: api.main.extract_text_task.delay",
        "line 7: patch.object AsyncResult",
        "line 8: setattr _summary_doc_kind_and_hashes",
    ]


def test_tests_do_not_patch_api_main_router_facade_aliases() -> None:
    stale_test_patches = {
        str(test_path.relative_to(ROOT)): alias_references
        for test_path in _tracked_files()
        if test_path.suffix == ".py"
        and test_path.relative_to(ROOT).parts[0] == "tests"
        and (
            alias_references := _search_main_alias_references(
                test_path,
                API_MAIN_ROUTER_FACADE_ALIASES,
            )
        )
    }

    assert stale_test_patches == {}


def test_sync_global_guardrail_detects_top_level_functions(
    tmp_path: Path,
) -> None:
    sync_source = tmp_path / "sync_source.py"
    sync_source.write_text(
        "def _sync_owner_from_facade():\n"
        "    pass\n"
        "\n"
        "def _sync_facade_from_owner():\n"
        "    pass\n"
        "\n"
        "async def _sync_async_from_owner():\n"
        "    pass\n"
        "\n"
        "def _sync_worker_config():\n"
        "    pass\n"
        "\n"
        "def _sync_helper_test_hooks():\n"
        "    pass\n"
        "\n"
        "def sync_rows_from_db():\n"
        "    pass\n"
        "\n"
        "def outer():\n"
        "    def _sync_nested_from_owner():\n"
        "        pass\n"
        "\n"
        "class Owner:\n"
        "    def _sync_method_from_owner(self):\n"
        "        pass\n"
        "\n"
        "if enabled:\n"
        "    def _sync_conditional_from_owner():\n"
        "        pass\n"
        "\n"
        "try:\n"
        "    async def _sync_guarded_from_owner():\n"
        "        pass\n"
        "except ImportError:\n"
        "    pass\n",
        encoding="utf-8",
    )

    assert _top_level_sync_function_lines(sync_source) == [1, 4, 7, 28, 32]


def test_structural_scan_scope_covers_production_python_only() -> None:
    assert _is_production_structural_path(Path("root_module.py"))
    assert _is_production_structural_path(Path("alembic/versions/0001.py"))
    assert _is_production_structural_path(Path("pipeline/tasks.py"))
    assert not _is_production_structural_path(Path("tests/test_tasks.py"))


def test_production_python_has_no_banned_structural_smells() -> None:
    sync_violations: dict[str, list[int]] = {}

    for source_path in _broad_exception_scan_files():
        relative_source_path = source_path.relative_to(ROOT)
        if not _is_production_structural_path(relative_source_path):
            continue
        sync_lines = _top_level_sync_function_lines(source_path)
        if sync_lines:
            sync_violations[str(relative_source_path)] = sync_lines

    assert sync_violations == {}


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


def test_summary_backfill_runner_is_the_direct_operation_boundary() -> None:
    deleted_facade = ROOT / "pipeline" / "summary_backfill.py"
    runner_path = ROOT / "pipeline" / "summary_backfill_runner.py"
    runner_tree = ast.parse(
        runner_path.read_text(encoding="utf-8"),
        filename=str(runner_path.relative_to(ROOT)),
    )
    public_runner = next(
        node
        for node in runner_tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "run_summary_hydration_backfill"
    )
    public_parameters = [
        *public_runner.args.posonlyargs,
        *public_runner.args.args,
        *public_runner.args.kwonlyargs,
    ]

    assert not deleted_facade.exists()
    assert len(public_parameters) <= 8
    assert [
        parameter.arg
        for parameter in public_parameters
        if parameter.arg.endswith("_callable")
    ] == []

    caller_paths = (
        ROOT / "pipeline/run_pipeline.py",
        ROOT / "scripts/backfill_summaries.py",
        ROOT / "scripts/staged_hydrate_cities.py",
        ROOT / "scripts/profile_pipeline_selection.py",
    )
    forbidden_caller_imports = {
        str(caller_path.relative_to(ROOT)): _forbidden_imports(
            caller_path,
            {
                "pipeline.tasks",
                "pipeline.summary_backfill",
            },
        )
        for caller_path in caller_paths
    }
    assert forbidden_caller_imports == {
        str(caller_path.relative_to(ROOT)): []
        for caller_path in caller_paths
    }

    backfill_module_paths = tuple(
        ROOT / "pipeline" / module_name
        for module_name in (
            "summary_backfill_dispatch.py",
            "summary_backfill_logging.py",
            "summary_backfill_progress.py",
            "summary_backfill_queries.py",
            "summary_backfill_runner.py",
        )
    )
    forbidden_backfill_imports = {
        str(module_path.relative_to(ROOT)): _forbidden_imports(
            module_path,
            {
                "pipeline.summary_backfill",
                "pipeline.task_facade_helpers",
                "pipeline.tasks",
            },
        )
        for module_path in backfill_module_paths
    }
    assert forbidden_backfill_imports == {
        str(module_path.relative_to(ROOT)): []
        for module_path in backfill_module_paths
    }

    tasks_source = (ROOT / "pipeline/tasks.py").read_text(encoding="utf-8")
    for obsolete_name in (
        "_summary_doc_kind_subquery",
        "select_catalog_ids_for_summary_hydration",
        "_summary_doc_kind_map",
        "_enqueue_embed_catalogs",
        "run_summary_hydration_backfill",
    ):
        assert obsolete_name not in tasks_source


def test_maintenance_summary_and_staged_hydration_own_runtime_dependencies() -> None:
    deleted_modules = (
        ROOT / "pipeline/agenda_summary_callbacks.py",
        ROOT / "pipeline/agenda_summary_maintenance.py",
    )
    assert [str(module_path.relative_to(ROOT)) for module_path in deleted_modules if module_path.exists()] == []

    operation_paths = tuple(
        ROOT / module_path
        for module_path in (
            "pipeline/agenda_summary_batch.py",
            "pipeline/agenda_summary_fallback.py",
            "pipeline/agenda_summary_side_effects.py",
            "pipeline/non_agenda_summary_fallback.py",
            "pipeline/summary_backfill_runner.py",
            "scripts/hydration_repaired_runner.py",
            "scripts/hydration_repaired_summary.py",
            "scripts/staged_hydrate_cities.py",
            "scripts/staged_hydration_output.py",
            "scripts/staged_hydration_runner.py",
            "scripts/staged_hydration_segment.py",
        )
    )
    forbidden_parameter_names = {"session_factory", "time_module"}
    dependency_parameters: dict[str, list[str]] = {}
    for operation_path in operation_paths:
        operation_tree = ast.parse(
            operation_path.read_text(encoding="utf-8"),
            filename=str(operation_path.relative_to(ROOT)),
        )
        dependency_parameters[str(operation_path.relative_to(ROOT))] = [
            parameter.arg
            for function_node in ast.walk(operation_tree)
            if isinstance(function_node, ast.FunctionDef)
            for parameter in (
                *function_node.args.posonlyargs,
                *function_node.args.args,
                *function_node.args.kwonlyargs,
            )
            if parameter.arg.endswith("_callable")
            or parameter.arg in forbidden_parameter_names
        ]
    assert dependency_parameters == {
        str(operation_path.relative_to(ROOT)): []
        for operation_path in operation_paths
    }

    summary_operation_paths = (
        ROOT / "pipeline/agenda_summary_batch.py",
        ROOT / "pipeline/agenda_summary_fallback.py",
        ROOT / "pipeline/non_agenda_summary_fallback.py",
        ROOT / "pipeline/summary_backfill_runner.py",
        ROOT / "scripts/hydration_repaired_summary.py",
    )
    forbidden_summary_imports = {
        str(operation_path.relative_to(ROOT)): _forbidden_imports(
            operation_path,
            {
                "pipeline.agenda_summary_maintenance",
                "pipeline.backlog_maintenance",
                "pipeline.tasks",
            },
        )
        for operation_path in summary_operation_paths
    }
    assert forbidden_summary_imports == {
        str(operation_path.relative_to(ROOT)): []
        for operation_path in summary_operation_paths
    }

    backlog_source = (ROOT / "pipeline/backlog_maintenance.py").read_text(
        encoding="utf-8"
    )
    for removed_summary_name in (
        "build_agenda_summary_input_bundle",
        "build_deterministic_agenda_summary_payload",
        "build_deterministic_non_agenda_summary_payload",
        "persist_agenda_summary",
        "summarize_catalog_with_maintenance_mode",
        "summarize_catalog_with_optional_fallback",
    ):
        assert removed_summary_name not in backlog_source

    for canonical_map_path in (
        ROOT / "ARCHITECTURE.md",
        ROOT / "docs/PIPELINE.md",
    ):
        canonical_map_source = canonical_map_path.read_text(encoding="utf-8")
        assert "pipeline/agenda_summary_maintenance.py" not in canonical_map_source
        assert "pipeline/agenda_summary_callbacks.py" not in canonical_map_source


def _required_markdown_section(markdown: str, heading: str, next_heading: str) -> str:
    _, heading_separator, section_remainder = markdown.partition(heading)
    assert heading_separator, f"Missing required Markdown heading: {heading}"
    section, next_separator, _ = section_remainder.partition(next_heading)
    assert next_separator, f"Missing Markdown boundary after: {heading}"
    return " ".join(section.split())


def _required_markdown_entry(markdown: str, heading: str) -> str:
    _, heading_separator, section_remainder = markdown.partition(heading)
    assert heading_separator, f"Missing required Markdown heading: {heading}"
    next_heading = re.search(r"\n## ", section_remainder)
    assert next_heading, f"Missing Markdown boundary after: {heading}"
    return " ".join(section_remainder[: next_heading.start()].split())


def _remediation_task_states(remediation_ledger: str, task_id: str) -> list[str]:
    status_rows = [
        line
        for line in remediation_ledger.splitlines()
        if line.startswith("| **") and " |" in line
    ]
    return [
        row.split("|")[1].strip().strip("*")
        for row in status_rows
        for listed_task_id in row.split("|")[2].split(",")
        if listed_task_id.strip() == task_id
    ]


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
                f"{previous_text}\n{comment_text}",
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
REMEDIATION_TASK_REFERENCE = re.compile(r"\bT-[A-Z]+-\d+[A-Z]?\b", re.IGNORECASE)
REMEDIATION_TASK_LINE_REFERENCE = re.compile(
    r"^\s*(?:(?:[-*+]|\d+\.)\s+)?T-[A-Z]+-\d+[A-Z]?\b",
    re.IGNORECASE,
)
G3_COORDINATED_SUBJECT = re.compile(r"^\s*(?:both\s+)?G3\s*$", re.IGNORECASE)
G3_DEFERRAL_ACTION_PATTERN = (
    r"(?:defer(?:s|red|ring)?|block(?:s|ed|ing)?|preserv(?:e|es|ed|ing)|"
    r"prevent(?:s|ed|ing)?|retain(?:s|ed)?|retaining|delay(?:s|ed|ing)?|"
    r"postpon(?:e|es|ed|ing)|stop(?:s|ped|ping)?|gat(?:es|ed|ing))"
)
G3_DEFERRAL_ACTION = re.compile(
    rf"\b{G3_DEFERRAL_ACTION_PATTERN}\b",
    re.IGNORECASE,
)
G3_LEGACY_SEAM_OBJECT_PATTERN = (
    r"(?:(?:compatibility|monkeypatch)\s+(?:re-exports?|wrappers?)|"
    r"test(?:-only|\s+only)?\s+(?:re-exports?|wrappers?)|"
    r"test\s+facade\s+wrappers?|"
    r"(?:monkeypatch\s+)?compatibility\s+shims?|"
    r"(?:bidirectional(?:ly)?\s+)?synchronized\s+globals?|"
    r"injectable(?:-|\s+)callables?(?:\s+(?:parameters?|seams?))?)"
)
G3_TEST_ONLY_OBJECT_PATTERN = (
    r"(?:test\s+(?:facades?|seams?)|"
    r"(?:test(?:-only|\s+only)?\s+)?patch\s+(?:points?|targets?)|"
    rf"{G3_LEGACY_SEAM_OBJECT_PATTERN})"
)
G3_REMOVAL_OBJECT_PATTERN = (
    rf"(?:facades?|{G3_TEST_ONLY_OBJECT_PATTERN})"
)
G3_REMOVAL_OBJECT_MODIFIER_PATTERN = r"(?:a|an|existing|legacy|temporary|that|the|this)"
G3_MUST_PRECEDE_ACTION_PATTERN = (
    r"must\s+(?:land|be\s+(?:accepted|completed?|resolved))\s+before"
)
G3_PREREQUISITE_SUBJECT_PATTERN = (
    r"(?:(?:contributors?|maintainers?|they|we|you)\s+)?"
)
G3_ORDERED_PREREQUISITE_ACTION_PATTERN = (
    rf"(?:{G3_MUST_PRECEDE_ACTION_PATTERN}|must\s+wait\s+(?:for|until))"
)
G3_PROHIBITION_ACTION_PATTERN = (
    r"(?:prohibit(?:s|ed|ing)?|forbid(?:s|ding)?|forbade|forbidden)"
)
G3_PASSIVE_PROHIBITION_ACTION_PATTERN = r"(?:prohibited|forbidden)"
G3_PROHIBITION_EMPHASIS_PATTERN = r"(?:(?:[a-z]+ly|still)\s+){0,2}"
G3_PROHIBITION_REJECTION_PATTERN = (
    rf"(?:(?:are|is|was|were)\s+{G3_PROHIBITION_EMPHASIS_PATTERN}"
    rf"{G3_PASSIVE_PROHIBITION_ACTION_PATTERN}\s+from|"
    rf"{G3_PROHIBITION_EMPHASIS_PATTERN}{G3_PROHIBITION_ACTION_PATTERN}"
    rf"(?:(?:\s+[a-z0-9-]+){{0,4}}\s+from)?)"
)
G3_CONTROLLED_WORK_CONTINUATION_PATTERN = (
    r"can\s+(?:proceed|be\s+(?:cleaned\s+up|deleted|removed))"
)
G3_COPULAR_TEMPORAL_ACTION_PATTERN = (
    r"(?:(?:(?:must|shall|should|will)\s+(?:(?:continue\s+to|still)\s+)?|"
    r"(?:has|have|needs?)\s+to\s+|"
    r"(?:are|is)\s+(?:still\s+)?required\s+to\s+)?"
    r"(?:remain(?:s)?|stay(?:s)?)\s+(?:in\s+place\s+)?until\s+\bG3\b|"
    r"(?:cannot|can't)\s+begin\s+until\s+\bG3\b)"
)
G3_CONTROLLED_WORK_TAIL_PATTERN = (
    rf"(?:$|\b{G3_CONTROLLED_WORK_CONTINUATION_PATTERN}\b|"
    rf"\b{G3_COPULAR_TEMPORAL_ACTION_PATTERN}|"
    r"\b(?:because|pending|unless|until|while)\b|"
    rf"\b{G3_ORDERED_PREREQUISITE_ACTION_PATTERN}\b|"
    rf"\b(?:are|is|remain(?:s)?|was|were)\s+"
    rf"{G3_PROHIBITION_EMPHASIS_PATTERN}"
    rf"{G3_PASSIVE_PROHIBITION_ACTION_PATTERN}\s+by\s+\bG3\b|"
    rf"\b(?:are|is|remain(?:s)?|was|were)\s+{G3_DEFERRAL_ACTION_PATTERN}\b)"
)
G3_REMOVAL_FIRST_WORK_PATTERN = (
    rf"(?:(?:cleanup|deletion|removal)\s+of\s+"
    rf"(?:{G3_REMOVAL_OBJECT_MODIFIER_PATTERN}\s+){{0,3}}"
    rf"{G3_REMOVAL_OBJECT_PATTERN}|"
    rf"(?:remov|delet)(?:e|es|ed|ing)\s+"
    rf"(?:{G3_REMOVAL_OBJECT_MODIFIER_PATTERN}\s+){{0,3}}"
    rf"{G3_REMOVAL_OBJECT_PATTERN})"
    rf"(?=\s*{G3_CONTROLLED_WORK_TAIL_PATTERN})"
)
G3_DIRECT_DEFERRED_WORK_PATTERN = (
    r"(?:facade\s+(?:removals?|cleanups?)|"
    r"test\s+(?:facades?|seams?)(?:\s+(?:removals?|cleanups?))?|"
    r"test(?:-only|\s+only)?\s+patch\s+(?:points?|targets?)|patch\s+targets?|"
    rf"{G3_LEGACY_SEAM_OBJECT_PATTERN})"
    rf"(?=\s*{G3_CONTROLLED_WORK_TAIL_PATTERN})"
)
G3_DEFERRED_WORK = re.compile(
    rf"(?:{G3_DIRECT_DEFERRED_WORK_PATTERN}|deduplicat\w*|de-fac\w*|"
    rf"phase\s+2|{G3_REMOVAL_FIRST_WORK_PATTERN})",
    re.IGNORECASE,
)
G3_PERMISSIVE_ACTION_PATTERN = (
    r"(?:permit(?:s|ted|ting)?|allow(?:s|ed|ing)?|enabl(?:e|es|ed|ing))"
)
G3_KEEP_HOLD_ACTION_PATTERN = r"(?:keep(?:s|ing)?|kept|hold(?:s|ing)?|held)"
G3_REQUIREMENT_ACTION_PATTERN = r"requir(?:e|es|ed|ing)"
G3_REQUIREMENT_MODIFIER_PATTERN = r"(?:a|an|continued|existing|temporary|the)"
G3_RUNTIME_FACADE_PREFIX_PATTERN = r"(?:(?:public|runtime)\s+facades?\s+and\s+)?"
G3_CONTRASTIVE_DEFERRED_WORK = re.compile(
    rf"\b(?:instead\s+of|rather\s+than)\s+"
    rf"(?:(?:{G3_DEFERRAL_ACTION_PATTERN}|{G3_PERMISSIVE_ACTION_PATTERN}|"
    rf"{G3_KEEP_HOLD_ACTION_PATTERN}|{G3_REQUIREMENT_ACTION_PATTERN}"
    rf"(?:\s+(?:{G3_REQUIREMENT_MODIFIER_PATTERN}\s+){{0,3}}"
    rf"preserv(?:ation|ing)\s+of)?)\s+)?"
    rf"(?:{G3_REMOVAL_OBJECT_MODIFIER_PATTERN}\s+){{0,2}}"
    rf"{G3_DEFERRED_WORK.pattern}",
    re.IGNORECASE,
)
G3_COPULAR_TEMPORAL_POLICY = re.compile(
    rf"{G3_DEFERRED_WORK.pattern}\s+{G3_COPULAR_TEMPORAL_ACTION_PATTERN}",
    re.IGNORECASE,
)
G3_QUALIFIED_FACADE_TEMPORAL_POLICY = re.compile(
    rf"\b(?:the\s+)?[a-z_]\w*(?:\.[a-z_]\w*)+\s+facades?\s+"
    rf"{G3_COPULAR_TEMPORAL_ACTION_PATTERN}",
    re.IGNORECASE,
)
G3_INTERROGATIVE_OPENING_PATTERN = (
    r"(?:am|are|can|could|did|do|does|had|has|have|how|is|may|might|must|"
    r"shall|should|was|were|what|when|where|which|who|why|will|would)"
)
G3_NONASSERTIVE_POLICY_CONTEXT = re.compile(
    r"(?:\b(?:ask(?:s|ed|ing)?|check(?:s|ed|ing)?|document(?:s|ed|ing)?|"
    r"record(?:s|ed|ing)?|report(?:s|ed|ing)?|track(?:s|ed|ing)?)\s*"
    rf"(?:(?:if|whether)\b|:\s*{G3_INTERROGATIVE_OPENING_PATTERN}\b)|"
    rf"^\s*{G3_INTERROGATIVE_OPENING_PATTERN}\b|\?\s*$)",
    re.IGNORECASE,
)
G3_HISTORICAL_POLICY_CONTEXT = re.compile(
    r"(?:^\s*(?:(?:historically|previously|formerly|in\s+the\s+past)\b|"
    r"(?:the\s+)?(?:old|superseded)\b)"
    r"|\bG3\b(?:\s+[a-z][\w'-]*){0,3}\s+once(?!\s+again\b)"
    r"|\bG3\b(?:\s+[a-z][\w'-]*){0,3}\s+used\s+to\b)",
    re.IGNORECASE,
)
G3_ACTIVE_POLICY_CONTEXT = re.compile(
    r"\b(?:are|is|has|have|must|shall|should|will|cannot|can't|currently|now|still|"
    r"defers|blocks|preserves|prevents|retains|delays|postpones|keeps|holds|"
    r"requires|prohibits|forbids)\b",
    re.IGNORECASE,
)
G3_ORDERED_PREREQUISITE_POLICY = re.compile(
    rf"(?:\bG3\b\s+(?:{REMEDIATION_TASK_REFERENCE.pattern}\s+)?"
    rf"{G3_MUST_PRECEDE_ACTION_PATTERN}\s+"
    rf"{G3_PREREQUISITE_SUBJECT_PATTERN}"
    rf"(?:{G3_REMOVAL_OBJECT_MODIFIER_PATTERN}\s+){{0,2}}"
    rf"{G3_DEFERRED_WORK.pattern}|"
    rf"{G3_DEFERRED_WORK.pattern}\s+must\s+wait\s+(?:for|until)\s+\bG3\b)",
    re.IGNORECASE,
)
G3_PROHIBITION_POLICY = re.compile(
    rf"(?:\bG3\b\s+{G3_PROHIBITION_EMPHASIS_PATTERN}"
    rf"{G3_PROHIBITION_ACTION_PATTERN}\s+(?:(?:a|an|the)\s+)?"
    rf"{G3_DEFERRED_WORK.pattern}|"
    rf"{G3_DEFERRED_WORK.pattern}\s+"
    rf"(?:are|is|remain(?:s)?|was|were)\s+"
    rf"{G3_PROHIBITION_EMPHASIS_PATTERN}"
    rf"{G3_PASSIVE_PROHIBITION_ACTION_PATTERN}\s+by\s+\bG3\b)",
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
    r"\b(?:(?:nothing|nobody|none)(?!\s+(?:but|other\s+than)\b)|"
    r"(?:no\s+longer|never|cannot|can't|does\s+not|doesn't|is\s+not|isn't|"
    r"not|without)(?!\s+(?:only|just|merely)\b))"
    rf"{G3_NEGATION_GAP}\s+{G3_DEFERRAL_ACTION_PATTERN}\b",
    re.IGNORECASE,
)
G3_NEGATED_SUBJECT_DEFERRAL_ACTION = re.compile(
    rf"\bnone\s+of\s+(?:the\s+)?{G3_DEFERRED_WORK.pattern}\s+"
    rf"(?:are|is|remain(?:s)?|was|were)\s+{G3_DEFERRAL_ACTION_PATTERN}\b",
    re.IGNORECASE,
)
G3_PROHIBITED_DEFERRAL_ACTION = re.compile(
    rf"\b(?:{G3_PROHIBITION_REJECTION_PATTERN}|prevent(?:s|ed|ing)?|"
    rf"stop(?:s|ped|ping)?)\s+"
    rf"{G3_DEFERRAL_ACTION_PATTERN}\b",
    re.IGNORECASE,
)
G3_KEEP_HOLD_NON_OBJECT_PATTERN = (
    r"(?:about|comment|discussion|documentation|for|note|of|on|policy|progress|"
    r"record|regarding|report|status|tracking)"
)
G3_KEEP_HOLD_OBJECT_MODIFIER_PATTERN = (
    rf"(?!(?:{G3_KEEP_HOLD_NON_OBJECT_PATTERN})\b)[a-z][\w'-]*"
)
G3_KEEP_HOLD_POLICY = re.compile(
    rf"\b{G3_KEEP_HOLD_ACTION_PATTERN}\b"
    rf"(?:\s+{G3_KEEP_HOLD_OBJECT_MODIFIER_PATTERN}){{0,4}}\s+"
    rf"{G3_DEFERRED_WORK.pattern}(?=\s*{G3_CONTROLLED_WORK_TAIL_PATTERN})",
    re.IGNORECASE,
)
G3_NEGATED_KEEP_HOLD_ACTION = re.compile(
    r"\b(?:no\s+longer|never|cannot|can't|does\s+not|doesn't|is\s+not|isn't|"
    r"not|without)(?!\s+(?:only|just|merely)\b)"
    rf"{G3_NEGATION_GAP}\s+{G3_KEEP_HOLD_ACTION_PATTERN}\b",
    re.IGNORECASE,
)
G3_REJECTED_KEEP_HOLD_ACTION = re.compile(
    rf"\b(?:avoid(?:s|ed|ing)?|stop(?:s|ped|ping)?|"
    rf"{G3_PROHIBITION_REJECTION_PATTERN})"
    rf"{G3_NEGATION_GAP}\s+{G3_KEEP_HOLD_ACTION_PATTERN}\b",
    re.IGNORECASE,
)
G3_REQUIREMENT_POLICY = re.compile(
    rf"\b{G3_REQUIREMENT_ACTION_PATTERN}\s+"
    rf"(?:{G3_REQUIREMENT_MODIFIER_PATTERN}\s+){{0,3}}"
    rf"(?:preserv(?:ation|ing)\s+of\s+"
    rf"(?:{G3_REQUIREMENT_MODIFIER_PATTERN}\s+){{0,3}})?"
    rf"{G3_DEFERRED_WORK.pattern}(?=\s*{G3_CONTROLLED_WORK_TAIL_PATTERN})",
    re.IGNORECASE,
)
G3_SUBJECT_FIRST_REQUIREMENT_POLICY = re.compile(
    rf"(?:\b{G3_REQUIREMENT_ACTION_PATTERN}\s+"
    rf"(?:{G3_REQUIREMENT_MODIFIER_PATTERN}\s+){{0,3}}"
    rf"{G3_RUNTIME_FACADE_PREFIX_PATTERN}"
    rf"{G3_TEST_ONLY_OBJECT_PATTERN}\s+to\s+remain(?:\s+in\s+place)?"
    rf"(?=\s*{G3_CONTROLLED_WORK_TAIL_PATTERN})|"
    rf"\b{G3_RUNTIME_FACADE_PREFIX_PATTERN}{G3_TEST_ONLY_OBJECT_PATTERN}\s+"
    r"must\s+remain(?:\s+in\s+place)?(?=\s*(?:$|[.,;])))",
    re.IGNORECASE,
)
G3_NEGATED_REQUIREMENT_POLICY = re.compile(
    r"\b(?:no\s+longer|never|cannot|can't|does\s+not|doesn't|is\s+not|isn't|"
    r"not|without)(?!\s+(?:only|just|merely)\b)"
    rf"{G3_NEGATION_GAP}\s+requir(?:e|es|ed|ing)\b",
    re.IGNORECASE,
)
G3_SUBJECT_NEGATED_REQUIREMENT_POLICY = re.compile(
    rf"(?:\bno\s+G3\b(?:\s+[a-z-]+){{0,3}}|"
    rf"\bneither\s+G3\s+nor\s+{REMEDIATION_TASK_REFERENCE.pattern})\s+"
    rf"{G3_REQUIREMENT_ACTION_PATTERN}\b",
    re.IGNORECASE,
)
G3_NEGATED_SUBJECT_MUST_REMAIN_POLICY = re.compile(
    rf"\b(?:no\s+(?:the\s+)?{G3_TEST_ONLY_OBJECT_PATTERN}|"
    rf"neither\s+(?:the\s+)?{G3_TEST_ONLY_OBJECT_PATTERN}\s+nor\s+"
    rf"(?:the\s+)?{G3_TEST_ONLY_OBJECT_PATTERN})\s+must\s+remain\b",
    re.IGNORECASE,
)
G3_TEMPORAL_REFERENCE_POLICY = re.compile(
    r"(?:\b(?:pending|unless|until|while)\b.*\bG3\b|"
    r"\bG3\b.*\b(?:pending|unless|until|while)\b)",
    re.IGNORECASE,
)
G3_NEGATED_REMOVAL_DIRECTIVE_PATTERN = (
    r"(?:\b(?:cannot|can't|do\s+not|don't|never)\s+"
    rf"(?:remov|delet)(?:e|es|ed|ing)\s+"
    rf"(?:{G3_REMOVAL_OBJECT_MODIFIER_PATTERN}\s+){{0,3}}"
    rf"{G3_REMOVAL_OBJECT_PATTERN}|"
    rf"\b(?:{G3_REMOVAL_OBJECT_MODIFIER_PATTERN}\s+){{0,3}}"
    rf"{G3_REMOVAL_OBJECT_PATTERN}\s+(?:cannot|can't)\s+be\s+"
    r"(?:removed|deleted))"
)
G3_NEGATED_REMOVAL_DIRECTIVE = re.compile(
    rf"{G3_NEGATED_REMOVAL_DIRECTIVE_PATTERN}"
    rf"(?=\s*{G3_CONTROLLED_WORK_TAIL_PATTERN})",
    re.IGNORECASE,
)
G3_DECLARATIVE_REMOVAL_POLICY = re.compile(
    rf"\bG3\b\s+means\s+(?:that\s+)?{G3_NEGATED_REMOVAL_DIRECTIVE_PATTERN}",
    re.IGNORECASE,
)
G3_BEFORE_REMOVAL_DIRECTIVE_POLICY = re.compile(
    rf"(?:{G3_NEGATED_REMOVAL_DIRECTIVE_PATTERN}\s+before\s+\bG3\b|"
    rf"\bbefore\s+\bG3\b.{{0,80}}{G3_NEGATED_REMOVAL_DIRECTIVE_PATTERN})",
    re.IGNORECASE,
)
G3_BEFORE_REFERENCE_POLICY = re.compile(
    r"(?:\bbefore\b.*\bG3\b|\bG3\b.*\bbefore\b)",
    re.IGNORECASE,
)
G3_POLICY_SENTENCE_BOUNDARY = re.compile(r"([.?])(?=\s|$)")
G3_POLICY_CLAUSE_BOUNDARY = re.compile(
    r"(;|,|\b(?:and|but|however|while|yet|so|therefore|thus|hence|then)\b)",
    re.IGNORECASE,
)
G3_NOUN_ACTION_CONTINUATION = re.compile(
    r"^\s+(?:are|is|was|were|exist|exists|listed|documented)\b",
    re.IGNORECASE,
)
G3_PERMISSIVE_ACTION = re.compile(
    rf"\b{G3_PERMISSIVE_ACTION_PATTERN}\b",
    re.IGNORECASE,
)
G3_NEGATED_PERMISSIVE_ACTION = re.compile(
    r"\b(?:no\s+longer|never|cannot|can't|does\s+not|doesn't|is\s+not|isn't|"
    r"not|without)(?!\s+(?:only|just|merely)\b)"
    rf"{G3_NEGATION_GAP}\s+{G3_PERMISSIVE_ACTION_PATTERN}\b",
    re.IGNORECASE,
)
G3_BLOCKER_POLICY = re.compile(
    r"\bG3\b\s+(?:is|remains)\s+a\s+blocker\b",
    re.IGNORECASE,
)
G3_PREREQUISITE_POLICY = re.compile(
    r"\bG3\b.{0,40}\b(?:is|remains)\s+(?:a\s+)?prerequisite\b",
    re.IGNORECASE,
)
G3_NEGATED_PREREQUISITE_POLICY = re.compile(
    r"\bG3\b.{0,40}\b(?:no\s+longer|not|never)\b.{0,30}\bprerequisite\b",
    re.IGNORECASE,
)
G3_POLICY_RECORD_BRIDGE = re.compile(
    r"\b(?:adr|decision|documentation|history|note|record|report|status)\b",
    re.IGNORECASE,
)
G3_PASSIVE_ACTION_BRIDGE = re.compile(
    r"^\s+(?:are|is|remain(?:s)?|was|were)\s+$",
    re.IGNORECASE,
)


def _positive_g3_deferral_action(policy_clause: str) -> re.Match[str] | None:
    negated_action_spans = [
        negated_action.span()
        for negated_action in G3_NEGATED_DEFERRAL_ACTION.finditer(policy_clause)
    ] + [
        negated_action.span()
        for negated_action in G3_NEGATED_SUBJECT_DEFERRAL_ACTION.finditer(
            policy_clause
        )
    ] + [
        negated_action.span()
        for negated_action in G3_PROHIBITED_DEFERRAL_ACTION.finditer(policy_clause)
    ] + [
        rejected_action.span()
        for rejected_action in G3_REJECTED_KEEP_HOLD_ACTION.finditer(policy_clause)
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
        return deferral_action
    return None


def _positive_g3_deferred_work_matches(
    policy_clause: str,
) -> list[re.Match[str]]:
    negated_work_spans = [
        negated_work.span()
        for negated_work in G3_NEGATED_DEFERRED_WORK.finditer(policy_clause)
    ] + [
        contrastive_work.span()
        for contrastive_work in G3_CONTRASTIVE_DEFERRED_WORK.finditer(policy_clause)
    ]
    return [
        deferred_work
        for deferred_work in G3_DEFERRED_WORK.finditer(policy_clause)
        if not any(
            start <= deferred_work.start() < end
            for start, end in negated_work_spans
        )
    ]


def _g3_deferral_action_governs_work(
    policy_clause: str,
    deferral_action: re.Match[str],
) -> bool:
    for deferred_work in _positive_g3_deferred_work_matches(policy_clause):
        if deferred_work.start() >= deferral_action.end():
            action_bridge = policy_clause[
                deferral_action.end() : deferred_work.start()
            ]
            if not G3_POLICY_RECORD_BRIDGE.search(action_bridge):
                return True
        if deferral_action.start() >= deferred_work.end() and (
            G3_PASSIVE_ACTION_BRIDGE.fullmatch(
                policy_clause[deferred_work.end() : deferral_action.start()]
            )
        ):
            return True
    return False


def _g3_keep_hold_defers_work(policy_text: str) -> bool:
    negated_permission = G3_NEGATED_PERMISSIVE_ACTION.search(policy_text)
    positive_permission = G3_PERMISSIVE_ACTION.search(policy_text)
    contrastive_spans = [
        contrastive_work.span()
        for contrastive_work in G3_CONTRASTIVE_DEFERRED_WORK.finditer(policy_text)
    ]
    positive_keep_hold = any(
        not any(start <= keep_hold.start() < end for start, end in contrastive_spans)
        for keep_hold in G3_KEEP_HOLD_POLICY.finditer(policy_text)
    )
    return bool(
        positive_keep_hold
        and not G3_NEGATED_KEEP_HOLD_ACTION.search(policy_text)
        and not G3_REJECTED_KEEP_HOLD_ACTION.search(policy_text)
        and not G3_NONASSERTIVE_POLICY_CONTEXT.search(policy_text)
        and not (positive_permission and not negated_permission)
    )


def _g3_clause_defers_work(policy_clause: str) -> bool:
    if G3_NONASSERTIVE_POLICY_CONTEXT.search(
        policy_clause
    ) or G3_HISTORICAL_POLICY_CONTEXT.search(policy_clause):
        return False
    if G3_DECLARATIVE_REMOVAL_POLICY.search(policy_clause):
        return True
    negated_permission = G3_NEGATED_PERMISSIVE_ACTION.search(policy_clause)
    subject_first_requirement = G3_SUBJECT_FIRST_REQUIREMENT_POLICY.search(
        policy_clause
    )
    positive_deferral_action = _positive_g3_deferral_action(policy_clause)
    action_defers_work = bool(
        positive_deferral_action
        and _g3_deferral_action_governs_work(
            policy_clause,
            positive_deferral_action,
        )
    )
    qualified_facade_temporal = G3_QUALIFIED_FACADE_TEMPORAL_POLICY.search(
        policy_clause
    )
    if negated_permission:
        has_deferred_work = (
            subject_first_requirement
            or qualified_facade_temporal
            or G3_DEFERRED_WORK.search(policy_clause)
        )
    else:
        has_deferred_work = (
            subject_first_requirement
            or qualified_facade_temporal
            or bool(_positive_g3_deferred_work_matches(policy_clause))
        )
    return bool(
        G3_REFERENCE.search(policy_clause)
        and has_deferred_work
        and (
            action_defers_work
            or G3_BLOCKER_POLICY.search(policy_clause)
            or negated_permission
            or _g3_keep_hold_defers_work(policy_clause)
            or (
                (
                    G3_REQUIREMENT_POLICY.search(policy_clause)
                    or subject_first_requirement
                )
                and not (
                    G3_NEGATED_REQUIREMENT_POLICY.search(policy_clause)
                    or G3_SUBJECT_NEGATED_REQUIREMENT_POLICY.search(policy_clause)
                    or G3_NEGATED_SUBJECT_MUST_REMAIN_POLICY.search(policy_clause)
                )
            )
            or (
                G3_PREREQUISITE_POLICY.search(policy_clause)
                and not G3_NEGATED_PREREQUISITE_POLICY.search(policy_clause)
            )
            or (
                G3_COPULAR_TEMPORAL_POLICY.search(policy_clause)
                and not G3_NONASSERTIVE_POLICY_CONTEXT.search(policy_clause)
            )
            or qualified_facade_temporal
            or G3_ORDERED_PREREQUISITE_POLICY.search(policy_clause)
            or G3_PROHIBITION_POLICY.search(policy_clause)
        )
    )


def _g3_sentence_defers_work(policy_sentence: str) -> bool:
    sentence_has_other_task = bool(
        REMEDIATION_TASK_REFERENCE.search(policy_sentence)
    )
    sentence_is_historical = bool(
        G3_HISTORICAL_POLICY_CONTEXT.search(policy_sentence)
    )
    if (
        not sentence_has_other_task
        and not sentence_is_historical
        and G3_REFERENCE.search(policy_sentence)
    ):
        if _g3_keep_hold_defers_work(policy_sentence):
            return True
        if (
            G3_SUBJECT_FIRST_REQUIREMENT_POLICY.search(policy_sentence)
            and not G3_NEGATED_REQUIREMENT_POLICY.search(policy_sentence)
            and not G3_SUBJECT_NEGATED_REQUIREMENT_POLICY.search(policy_sentence)
            and not G3_NEGATED_SUBJECT_MUST_REMAIN_POLICY.search(policy_sentence)
        ):
            return True
    has_g3_context = False
    has_historical_context = False
    inherited_deferral_action: str | None = None
    inherited_removal_guard = False
    preceding_boundary = ""
    policy_parts = G3_POLICY_CLAUSE_BOUNDARY.split(policy_sentence)
    for part_index in range(0, len(policy_parts), 2):
        policy_clause = policy_parts[part_index]
        clause_has_g3 = bool(G3_REFERENCE.search(policy_clause))
        clause_is_historical = bool(
            G3_HISTORICAL_POLICY_CONTEXT.search(policy_clause)
        )
        if clause_is_historical:
            has_historical_context = True
        elif (
            has_historical_context
            and clause_has_g3
            and G3_ACTIVE_POLICY_CONTEXT.search(policy_clause)
            and not G3_DECLARATIVE_REMOVAL_POLICY.search(policy_clause)
        ):
            has_historical_context = False
        if preceding_boundary and preceding_boundary != "and":
            inherited_deferral_action = None
        if (
            G3_PERMISSIVE_ACTION.search(policy_clause)
            and not G3_NEGATED_PERMISSIVE_ACTION.search(policy_clause)
        ):
            inherited_deferral_action = None
        clause_has_other_task = bool(
            REMEDIATION_TASK_REFERENCE.search(policy_clause)
        )
        coordinates_g3_subject = bool(
            part_index >= 2
            and preceding_boundary == "and"
            and G3_COORDINATED_SUBJECT.fullmatch(
                policy_parts[part_index - 2].strip()
            )
        )
        coordinates_g3_prerequisite = bool(
            preceding_boundary == "and"
            and inherited_removal_guard
            and not G3_DEFERRAL_ACTION.search(policy_clause)
            and not G3_DEFERRED_WORK.search(policy_clause)
        )
        if (
            clause_has_other_task
            and not clause_has_g3
            and not coordinates_g3_subject
            and not coordinates_g3_prerequisite
        ):
            has_g3_context = False
            inherited_deferral_action = None
            inherited_removal_guard = False
        if clause_has_g3:
            has_g3_context = True
            inherited_removal_guard = bool(
                G3_TEMPORAL_REFERENCE_POLICY.search(policy_clause)
                or G3_BEFORE_REFERENCE_POLICY.search(policy_clause)
            )
        positive_deferral_action = _positive_g3_deferral_action(policy_clause)
        if positive_deferral_action:
            inherited_deferral_action = positive_deferral_action.group(0)
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
        if has_historical_context:
            if part_index + 1 < len(policy_parts):
                preceding_boundary = policy_parts[part_index + 1].lower()
            continue
        if G3_BEFORE_REMOVAL_DIRECTIVE_POLICY.search(scoped_clause):
            return True
        if G3_TEMPORAL_REFERENCE_POLICY.search(
            scoped_clause
        ) and G3_NEGATED_REMOVAL_DIRECTIVE.search(scoped_clause):
            return True
        if inherited_removal_guard and G3_NEGATED_REMOVAL_DIRECTIVE.search(
            policy_clause
        ):
            return True
        if _g3_clause_defers_work(scoped_clause):
            return True
        if part_index + 1 < len(policy_parts):
            preceding_boundary = policy_parts[part_index + 1].lower()
    return False


def _comment_block_defers_g3(comment_block: str) -> bool:
    normalized_comment = ""
    previous_comment_line = ""
    for raw_comment_line in comment_block.splitlines():
        comment_line = " ".join(raw_comment_line.replace("#", " ").split())
        separator = " "
        if (
            normalized_comment
            and REMEDIATION_TASK_LINE_REFERENCE.match(comment_line)
            and not re.search(r"\b(?:and|or)\s*$", previous_comment_line, re.IGNORECASE)
        ):
            separator = ". "
        normalized_comment = f"{normalized_comment}{separator}{comment_line}".strip()
        previous_comment_line = comment_line
    has_g3_context = False
    policy_parts = G3_POLICY_SENTENCE_BOUNDARY.split(normalized_comment)
    for part_index in range(0, len(policy_parts), 2):
        policy_sentence = policy_parts[part_index]
        if part_index + 1 < len(policy_parts) and policy_parts[part_index + 1] == "?":
            policy_sentence = f"{policy_sentence}?"
        sentence_has_g3 = bool(G3_REFERENCE.search(policy_sentence))
        sentence_has_other_task = bool(
            REMEDIATION_TASK_REFERENCE.search(policy_sentence)
        )
        if sentence_has_g3:
            has_g3_context = bool(
                not G3_NONASSERTIVE_POLICY_CONTEXT.search(policy_sentence)
                and not G3_HISTORICAL_POLICY_CONTEXT.search(policy_sentence)
                and (
                    G3_UNRESOLVED_POLICY.search(policy_sentence)
                    or G3_PENDING_PREREQUISITE_POLICY.search(policy_sentence)
                    or G3_TEMPORAL_REFERENCE_POLICY.search(policy_sentence)
                    or G3_BEFORE_REFERENCE_POLICY.search(policy_sentence)
                )
            )
        elif sentence_has_other_task:
            has_g3_context = False
        scoped_sentence = policy_sentence
        if (
            has_g3_context
            and not sentence_has_g3
            and not sentence_has_other_task
        ):
            scoped_sentence = f"G3 {policy_sentence}"
        if _g3_sentence_defers_work(scoped_sentence):
            return True
    return False


G2_OPEN_POLICY = re.compile(
    r"(?:\bg2\b\s+(?:is|remains)\s+(?:open|pending|unresolved)\b"
    r"|\bg2\b\s*(?:status\s*)?:\s*(?:open|pending|unresolved)\b"
    r"|\bdecision\s+g2,\s+currently\s+(?:open|pending|unresolved)\b"
    r"|\b(?:open|pending|unresolved)\s+g2\b)",
    re.IGNORECASE,
)
G4_UNRESOLVED_POLICY = re.compile(
    r"(?:\bg4\b\s+(?:is|remains)\s+(?:open|pending|unresolved)\b"
    r"|\bg4\b\s*(?:status\s*)?:\s*(?:open|pending|unresolved)\b"
    r"|\bdecision\s+g4\b.{0,20}\b(?:open|pending|unresolved)\b"
    r"|\b(?:open|pending|unresolved)\s+g4\b)",
    re.IGNORECASE,
)
G4_LIVE_OPTIONS_POLICY = re.compile(
    r"(?:\boptions?\s+under\s+consideration\b"
    r"|\bexactly\s+one\s+will\s+be\s+adopted\s+by\s+adr\b"
    r"|\bworking\s+default\s+until\s+(?:the\s+)?adr\s+lands\b"
    r"|\b(?:option [abc]|status quo)\b[^.!?;]{0,40}\b(?:remains?|is)\s+"
    r"(?:a\s+)?(?:live|viable|current)\s+(?:alternative|choice|option)\b)",
    re.IGNORECASE,
)
G4_DERIVED_EVIDENCE_SOURCE = re.compile(
    r"\b(?:title inference|source-document mentions?|linker-created memberships?"
    r"|memberships created by the entity linker)\b",
    re.IGNORECASE,
)
G4_DERIVED_PERSON_ACTION = re.compile(
    r"(?<!-)\b(?:authoriz(?:e|es|ed|ing)|becom(?:e|es|ing)|"
    r"creat(?:e|es|ed|ing)|generat(?:e|es|ed|ing)|produc(?:e|es|ed|ing))\b",
    re.IGNORECASE,
)
G4_DERIVED_PERSON_TARGET = re.compile(
    r"\b(?:person creation|person entities|people-facing records|profiles?|"
    r"memberships?|people metadata|vote attribution|cross-document aggregation)\b",
    re.IGNORECASE,
)
G4_DERIVED_PASSIVE_PERSON_PROMOTION = re.compile(
    r"\b(?:person entities|people-facing records|profiles?|memberships?|"
    r"people metadata|vote attribution|cross-document aggregation)\b"
    r"[^.!?;]{0,60}"
    r"\b(?:(?:may|can|will|must|should)\s+be|is|are)\s+"
    r"(?:authorized|created|generated|produced)\s+from\s+"
    r"(?:title inference|source-document mentions?|linker-created memberships?"
    r"|memberships created by the entity linker)\b",
    re.IGNORECASE,
)
G4_DERIVED_PERSON_RELATION_BARRIER = re.compile(
    r"\b(?:links?|linked|references?|referenced|associations?|associated|related)"
    r"\s+(?:to|with|by)\s+roster-authorized\s*$",
    re.IGNORECASE,
)
G4_DERIVED_AUTHORITY_ACTION = re.compile(
    r"\b(?:is|are|be|becom(?:e|es|ing)|constitut(?:e|es|ed|ing)|"
    r"establish(?:es|ed|ing)?|serv(?:e|es|ed|ing)\s+as|"
    r"qualif(?:y|ies|ied|ying)\s+as|count(?:s|ed|ing)?\s+as|"
    r"provid(?:e|es|ed|ing))\b",
    re.IGNORECASE,
)
G4_DERIVED_AUTHORITY_TARGET = re.compile(r"\broster authority\b", re.IGNORECASE)
G4_DERIVED_AUTHORITY_RELATION_BARRIER = re.compile(
    r"\b(?:rather than|instead of|rejected as)\b",
    re.IGNORECASE,
)
G4_AUTHORITATIVE_ROSTER_SUBJECT = re.compile(
    r"(?<!not )(?<!rather than )(?<!instead of )"
    r"\b(?:independently authoritative(?: official)?"
    r"(?: membership data| rosters?)|official membership data|official rosters?)"
    r"\s*,?\s*$",
    re.IGNORECASE,
)
G4_NON_ROSTER_PERSON_CREATION_POLICY = re.compile(
    r"\bnon-roster (?:names?|people)\b"
    r"(?![^.!?;]{0,80}\bwhile\b)"
    r"[^.!?;]{0,80}\b(?:(?:may|can)\s+"
    r"(?:become|create|generate|produce|appear in|be retained as|receive|"
    r"(?:be\s+)?link(?:ed|ing)?\s+to)"
    r"|are\s+allowed\s+to\s+"
    r"(?:become|create|generate|produce|appear in|be retained as|receive|"
    r"(?:be\s+)?link(?:ed|ing)?\s+to)"
    r"|(?<!not )(?<!never )(?<!cannot )"
    r"(?:become|create|generate|produce|appear in|are retained as|receive|"
    r"(?:are\s+)?link(?:ed|ing|s)?\s+to))"
    r"(?![^.!?;]{0,40}\bnot\s+(?:person entities|people metadata|profiles|"
    r"memberships|vote attribution|cross-document aggregation)\b)"
    r"[^.!?;]{0,40}"
    r"\b(?:person entities|people metadata|profiles|memberships|"
    r"vote attribution|cross-document aggregation)\b",
    re.IGNORECASE,
)
G4_NON_ROSTER_WHILE_CONTINUATION_POLICY = re.compile(
    r"\bnon-roster (?:names?|people)\b[^.!?;]{0,80}"
    r"\bwhile\s+they\s+(?:(?:may|can)\s+)?"
    r"(?:become|create|generate|produce|appear in|are retained as|receive|"
    r"(?:be\s+|are\s+)?link(?:ed|ing|s)?\s+to)\b"
    r"(?![^.!?;]{0,40}\bnot\s+(?:person entities|people metadata|profiles|"
    r"memberships|vote attribution|cross-document aggregation)\b)"
    r"[^.!?;]{0,40}"
    r"\b(?:person entities|people metadata|profiles|memberships|"
    r"vote attribution|cross-document aggregation)\b",
    re.IGNORECASE,
)
G4_POLICY_SENTENCE_BOUNDARY = re.compile(r"[.!?]+")
G4_POLICY_CLAUSE_BOUNDARY = re.compile(r";+")
G4_POLICY_LIST_NEGATION = re.compile(r"\b(?:forbidden|prohibited)\s*:", re.IGNORECASE)
G4_POLICY_CONTRAST_BOUNDARY = re.compile(r"\b(?:but|while)\b", re.IGNORECASE)
G4_SOURCE_ACTIVE_ACTION = re.compile(
    r"\b(?:edit(?:ed|ing|s)?|modif(?:ied|ies|y|ying)|rewrite(?:s|ten)?|"
    r"rewriting|delet(?:e|ed|es|ing)|alter(?:ed|ing|s)?|remove(?:d|s)?|removing|"
    r"redact(?:ed|ing|s)?)\b",
    re.IGNORECASE,
)
G4_SOURCE_PASSIVE_ACTION = re.compile(
    r"\b(?:edited|modified|rewritten|deleted|altered|removed|redacted)\b",
    re.IGNORECASE,
)
G4_SOURCE_RECORD_TARGET = re.compile(
    r"\b(?:municipal\s+)?source (?:documents?|records?|text)\b",
    re.IGNORECASE,
)
G4_EXTERNAL_SOURCE_CUSTODIAN_ACTIVE_ACTOR = re.compile(
    r"(?:^|[,;]\s*|\bwhile\s+)(?:only\s+)?(?:the\s+)?"
    r"(?:originating municipality|source municipality|records? custodian)\b"
    r"(?:\s+(?:may|can|will|must|should|does|is|are))?\s*$",
    re.IGNORECASE,
)
G4_EXTERNAL_SOURCE_CUSTODIAN_ACTOR = re.compile(
    r"\bby\s+(?:the\s+)?"
    r"(?:originating municipality|source municipality|records? custodian)\b",
    re.IGNORECASE,
)
G4_EXTERNAL_SOURCE_CUSTODIAN_PASSIVE_AGENT = re.compile(
    r"^\s+by\s+(?:the\s+)?"
    r"(?:originating municipality|source municipality|records? custodian)\b"
    r"(?!\s*,?\s*(?:and|or)\b)",
    re.IGNORECASE,
)
G4_SOURCE_ACTION_BARRIER = re.compile(
    r"\b(?:not|rather than|instead of|links? to|linked to|associated with|related to|"
    r"derived from|extracted from|built from|"
    r"keep(?:s|ing)?|leav(?:e|es|ing)|"
    r"preserv(?:e|es|ed|ing)|retain(?:s|ed|ing)?)\b",
    re.IGNORECASE,
)
G4_SOURCE_PASSIVE_SUBJECT_BARRIER = re.compile(
    r"\b(?:derived (?:records?|indexes?|metadata|summaries|profiles?|memberships?)"
    r"|entity links?|annotations?)\b",
    re.IGNORECASE,
)
G4_SOURCE_TARGET_PRESERVATION = re.compile(
    r"^\s*(?:(?:is|are|will be|must be|should be)\s+(?:kept\s+)?unchanged|"
    r"remain(?:s|ed)?\s+unchanged|"
    r"(?:is|are|will be|must be|should be)\s+(?:preserved|retained))\b",
    re.IGNORECASE,
)
G4_SOURCE_NOMINAL_AUTHORIZATION = re.compile(
    r"\b(?:deletion|modification|removal|alteration|rewriting|editing|redaction)"
    r"\s+of\s+"
    r"(?:municipal\s+)?source (?:documents?|records?|text)\b"
    r"[^.!?;]{0,40}\b(?:is|are|may be|can be|will be|must be|should be)\s+"
    r"(?P<negated>not\s+)?"
    r"(?:allowed|authorized|permitted)\b",
    re.IGNORECASE,
)
G4_SOURCE_NEGATION_CUE = re.compile(
    r"\b(?:not(?:\s+(?:allowed|permitted|authorized)(?:\s+to)?)?|never|cannot|"
    r"prevent(?:s|ed|ing)?|refus(?:e|es|ed|ing)|"
    r"prohibit(?:s|ed)?|forbid(?:s|den)?|prohibited|forbidden)\b",
    re.IGNORECASE,
)
G4_SOURCE_AFFIRMATIVE_CUE = re.compile(
    r"\b(?:may|can|will|must|should)\b",
    re.IGNORECASE,
)
G4_NEGATION_SCOPE_BOUNDARY = re.compile(r"\b(?:and|but|while)\b", re.IGNORECASE)
G4_NO_DETERMINER_NEGATION = re.compile(r"^\s*no\b", re.IGNORECASE)
G4_SHARED_NEGATION = re.compile(
    r"(?:\b(?:forbidden|prohibited|not (?:allowed|permitted|authorized))\s+to\b"
    r"|\b(?:do|does|must|may|can|will|should)\s+not\b|\bcannot\b)"
    r"[^.!?;]{0,80}\band\s*$",
    re.IGNORECASE,
)
G4_PAIRED_NEGATION = re.compile(
    r"\bneither\b[^.!?;]{0,120}\bnor\b",
    re.IGNORECASE,
)
G4_SOURCE_INHERITED_PASSIVE_SUBJECT = re.compile(
    r"^\s*(?:(?:they|it)\s+)?(?:may|can|will|must|should|is|are)\b",
    re.IGNORECASE,
)
G4_SOURCE_NEW_SUBJECT_CUE = re.compile(
    r"\b(?:and|or)\s+(?:[a-z][a-z-]*\s+){1,4}"
    r"(?:(?:is|are|will|may|can|must|should)\s+(?:be\s+)?|"
    r"(?:has|have)\s+been\s+)$",
    re.IGNORECASE,
)
G4_SOURCE_WHILE_CONTINUATION_POLICY = re.compile(
    r"\b(?:corrections?|takedowns?)\b[^.!?;]{0,80}"
    r"\bwhile\s+they\s+(?:(?:may|can)\s+)?"
    r"(?:edit|modify|rewrite|delete|alter|remove)\b"
    r"[^.!?;]{0,40}\b(?:municipal\s+)?source "
    r"(?:documents?|records?|text)\b",
    re.IGNORECASE,
)
G4_PREMATURE_CITY_EXPANSION_POLICY = re.compile(
    r"(?:\bcity coverage expansion\b"
    r"(?=[^.!?;]{0,120}\b(?:(?:may|can)\s+(?:start|begin|proceed|resume)"
    r"|(?:starts|begins|proceeds|resumes)|(?:is|remains)\s+(?:allowed|unblocked))\b)"
    r"[^.!?;]{0,160}\b(?:(?<!not )(?<!never )before\b[^.!?;]{0,80}"
    r"\b(?:t-gov-2a|roster enforcement|roster-gated person linking)\b"
    r"|prior\s+to\s+(?:the\s+)?completion\s+of\s+t-gov-2a\b"
    r"|without\b[^.!?;]{0,40}\b(?:completion\s+of|completing)\s+t-gov-2a\b)"
    r"|\bt-gov-2a\b[^.!?;]{0,80}\b(?:is|becomes|remains)\s+"
    r"(?:optional|unnecessary|not\s+(?:required|mandatory)|"
    r"no\s+longer\s+(?:required|mandatory))\b"
    r"[^.!?;]{0,80}\bbefore\b[^.!?;]{0,80}\bcity coverage expansion\b"
    r"|\bt-gov-2a\b[^.!?;]{0,40}\b"
    r"(?:need(?:s)?\s+not|do(?:es)?\s+not\s+need\s+to)\s+"
    r"(?:be\s+)?complete\b[^.!?;]{0,80}\bbefore\b[^.!?;]{0,80}"
    r"\bcity coverage expansion\b"
    r"|\bbefore\b[^.!?;]{0,80}\bt-gov-2a\b[^.!?;]{0,80}"
    r"\bcity coverage expansion\b[^.!?;]{0,80}"
    r"(?:(?:may|can)\s+(?:start|begin|proceed|resume)"
    r"|(?:starts|begins|proceeds|resumes)|(?:is|remains)\s+(?:allowed|unblocked))\b)",
    re.IGNORECASE,
)
G4_PREMATURE_ENFORCEMENT_POLICY = re.compile(
    r"(?:\btown council\b[^.!?;]{0,80}\b(?:currently|already|now)\s+"
    r"enforces?\s+(?:this|the)\s+(?:g4\s+)?policy\b"
    r"|\bruntime enforcement\b[^.!?;]{0,80}\b"
    r"(?:is|has been)\s+(?:complete|implemented|verified)\b"
    r"|\broster gating\b[^.!?;]{0,40}\b(?:is|has been)\s+"
    r"(?:(?:already|currently|now)\s+)?(?:enforced|implemented|complete|verified)\b)",
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
G3_PENDING_PREREQUISITE_POLICY = re.compile(
    r"\bG3\b\s+(?:still\s+)?must\s+"
    r"(?:land|be\s+(?:accepted|completed?|resolved))\s*$",
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


def _g4_policy_has_contradiction(g4_policy: str) -> bool:
    normalized_g4_policy = " ".join(g4_policy.split())
    return bool(
        G4_UNRESOLVED_POLICY.search(normalized_g4_policy)
        or G4_LIVE_OPTIONS_POLICY.search(normalized_g4_policy)
        or _g4_policy_promotes_derived_evidence(normalized_g4_policy)
        or G4_NON_ROSTER_PERSON_CREATION_POLICY.search(normalized_g4_policy)
        or G4_NON_ROSTER_WHILE_CONTINUATION_POLICY.search(normalized_g4_policy)
        or _g4_policy_allows_source_record_modification(normalized_g4_policy)
        or G4_SOURCE_WHILE_CONTINUATION_POLICY.search(normalized_g4_policy)
        or G4_PREMATURE_CITY_EXPANSION_POLICY.search(normalized_g4_policy)
        or G4_PREMATURE_ENFORCEMENT_POLICY.search(normalized_g4_policy)
    )


def _g4_policy_promotes_derived_evidence(g4_policy: str) -> bool:
    return any(
        _g4_clause_passively_promotes_derived_evidence(policy_clause)
        or _g4_clause_grants_roster_authority(policy_clause)
        or _g4_clause_creates_person_record(policy_clause)
        for policy_clause in _g4_policy_clauses(g4_policy)
    )


def _g4_clause_passively_promotes_derived_evidence(policy_clause: str) -> bool:
    passive_promotion = G4_DERIVED_PASSIVE_PERSON_PROMOTION.search(policy_clause)
    return passive_promotion is not None and not _source_action_is_negated(
        policy_clause[: passive_promotion.end()]
    )


def _g4_authority_subject(authority_prefix: str) -> str:
    relative_marker = re.search(r"\b(?:that|which)\s*$", authority_prefix, re.IGNORECASE)
    if relative_marker is not None:
        relative_subject = G4_AUTHORITATIVE_ROSTER_SUBJECT.search(
            authority_prefix[: relative_marker.start()]
        )
        if relative_subject is not None:
            return relative_subject.group()
    return re.split(
        r",|\bwhile\b",
        authority_prefix,
        flags=re.IGNORECASE,
    )[-1]


def _g4_clause_grants_roster_authority(policy_clause: str) -> bool:
    for authority_target in G4_DERIVED_AUTHORITY_TARGET.finditer(policy_clause):
        authority_actions = tuple(
            G4_DERIVED_AUTHORITY_ACTION.finditer(
                policy_clause,
                0,
                authority_target.start(),
            )
        )
        if not authority_actions:
            continue
        authority_action = authority_actions[-1]
        evidence_sources = tuple(
            G4_DERIVED_EVIDENCE_SOURCE.finditer(
                policy_clause,
                0,
                authority_action.start(),
            )
        )
        if not evidence_sources:
            continue
        authority_prefix = policy_clause[: authority_action.start()]
        authority_subject = _g4_authority_subject(authority_prefix)
        action_target_text = policy_clause[
            authority_action.end() : authority_target.start()
        ]
        if (
            (
                G4_AUTHORITATIVE_ROSTER_SUBJECT.search(authority_subject) is None
                or G4_DERIVED_EVIDENCE_SOURCE.search(authority_subject) is not None
            )
            and not _source_action_is_negated(
                policy_clause[: authority_action.start()].rsplit(",", maxsplit=1)[-1]
            )
            and G4_SOURCE_NEGATION_CUE.search(action_target_text) is None
            and G4_DERIVED_AUTHORITY_RELATION_BARRIER.search(action_target_text)
            is None
        ):
            return True
    return False


def _g4_clause_creates_person_record(policy_clause: str) -> bool:
    for person_target in G4_DERIVED_PERSON_TARGET.finditer(policy_clause):
        person_actions = tuple(
            G4_DERIVED_PERSON_ACTION.finditer(
                policy_clause,
                0,
                person_target.start(),
            )
        )
        if not person_actions:
            continue
        person_action = person_actions[-1]
        evidence_sources = tuple(
            G4_DERIVED_EVIDENCE_SOURCE.finditer(
                policy_clause,
                0,
                person_action.start(),
            )
        )
        if not evidence_sources:
            continue
        source_action_text = policy_clause[
            evidence_sources[-1].end() : person_action.start()
        ]
        action_target_text = policy_clause[person_action.end() : person_target.start()]
        if (
            G4_AUTHORITATIVE_ROSTER_SUBJECT.search(source_action_text) is None
            and G4_DERIVED_PERSON_RELATION_BARRIER.search(action_target_text) is None
            and G4_SOURCE_NEGATION_CUE.search(action_target_text) is None
            and not _source_action_is_negated(policy_clause[: person_action.start()])
        ):
            return True
    return False


def _g4_policy_clauses(g4_policy: str) -> tuple[str, ...]:
    policy_clauses: list[str] = []
    for policy_sentence in G4_POLICY_SENTENCE_BOUNDARY.split(g4_policy):
        sentence_clauses = G4_POLICY_CLAUSE_BOUNDARY.split(policy_sentence)
        list_match = G4_POLICY_LIST_NEGATION.search(sentence_clauses[0])
        list_negation = list_match.group() if list_match else ""
        policy_clauses.extend(
            f"{list_negation} {policy_clause}" if list_negation else policy_clause
            for policy_clause in sentence_clauses
        )
    return tuple(policy_clauses)


def _g4_policy_allows_source_record_modification(g4_policy: str) -> bool:
    for policy_sentence in _g4_policy_clauses(g4_policy):
        if any(
            nominal_action.group("negated") is None
            and G4_EXTERNAL_SOURCE_CUSTODIAN_ACTOR.search(
                nominal_action.group()
            )
            is None
            for nominal_action in G4_SOURCE_NOMINAL_AUTHORIZATION.finditer(
                policy_sentence
            )
        ):
            return True
        source_context = False
        for policy_segment in G4_POLICY_CONTRAST_BOUNDARY.split(policy_sentence):
            source_targets = tuple(G4_SOURCE_RECORD_TARGET.finditer(policy_segment))
            if _segment_allows_active_source_edit(
                policy_segment,
                source_targets,
            ):
                return True
            if _segment_allows_passive_source_edit(
                policy_segment,
                source_targets,
                source_context,
            ):
                return True
            source_context = bool(source_targets) or (
                source_context
                and G4_SOURCE_INHERITED_PASSIVE_SUBJECT.match(policy_segment) is not None
            )
    return False


def _segment_allows_active_source_edit(
    policy_segment: str,
    source_targets: tuple[re.Match[str], ...],
) -> bool:
    for source_target in source_targets:
        source_actions = tuple(
            G4_SOURCE_ACTIVE_ACTION.finditer(
                policy_segment,
                0,
                source_target.start(),
            )
        )
        if not source_actions:
            continue
        source_action = source_actions[-1]
        action_target_text = policy_segment[
            source_action.end() : source_target.start()
        ]
        if (
            G4_SOURCE_ACTION_BARRIER.search(action_target_text) is None
            and G4_EXTERNAL_SOURCE_CUSTODIAN_ACTIVE_ACTOR.search(
                policy_segment[: source_action.start()]
            )
            is None
            and G4_SOURCE_TARGET_PRESERVATION.match(
                policy_segment[source_target.end() :]
            )
            is None
            and not _source_action_is_negated(
                policy_segment[: source_action.start()]
            )
        ):
            return True
    return False


def _segment_allows_passive_source_edit(
    policy_segment: str,
    source_targets: tuple[re.Match[str], ...],
    source_context: bool,
) -> bool:
    for source_action in G4_SOURCE_PASSIVE_ACTION.finditer(policy_segment):
        explicit_source = any(
            source_target.end() <= source_action.start()
            and G4_SOURCE_PASSIVE_SUBJECT_BARRIER.search(
                policy_segment[source_target.end() : source_action.start()]
            )
            is None
            for source_target in source_targets
        )
        inherited_source = (
            not source_targets
            and source_context
            and G4_SOURCE_INHERITED_PASSIVE_SUBJECT.match(policy_segment) is not None
            and G4_SOURCE_NEW_SUBJECT_CUE.search(
                policy_segment[: source_action.start()]
            )
            is None
        )
        if (
            (explicit_source or inherited_source)
            and G4_EXTERNAL_SOURCE_CUSTODIAN_PASSIVE_AGENT.match(
                policy_segment[source_action.end() :]
            )
            is None
            and not _source_action_is_negated(policy_segment[: source_action.start()])
        ):
            return True
    return False


def _source_action_is_negated(action_prefix: str) -> bool:
    if (
        G4_NO_DETERMINER_NEGATION.search(action_prefix)
        or G4_SHARED_NEGATION.search(action_prefix)
        or G4_PAIRED_NEGATION.search(action_prefix)
    ):
        return True
    action_scope = G4_NEGATION_SCOPE_BOUNDARY.split(action_prefix)[-1]
    latest_negative = max(
        (negative_cue.end() for negative_cue in G4_SOURCE_NEGATION_CUE.finditer(action_scope)),
        default=-1,
    )
    latest_affirmative = max(
        (
            affirmative_cue.end()
            for affirmative_cue in G4_SOURCE_AFFIRMATIVE_CUE.finditer(action_scope)
        ),
        default=-1,
    )
    return latest_negative > latest_affirmative


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
        "G2 is approved; T-SEC-4 is complete.",
        "G2 is not open.",
        "Operator-only proxy authentication is not approved.",
    ),
)
def test_g2_policy_contradiction_detection_allows_approved_wording(
    approved_policy: str,
) -> None:
    assert not _g2_policy_has_contradiction(approved_policy)


@pytest.mark.parametrize(
    ("g4_policy", "has_contradiction"),
    (
        ("G4 remains open.", True),
        ("G4 status: pending.", True),
        ("DECISION G4 - unresolved", True),
        ("Options under consideration; exactly one will be adopted by ADR.", True),
        ("Working default until the ADR lands.", True),
        ("Option B remains a live alternative.", True),
        ("Title inference may establish roster authority.", True),
        ("Title inference and official rosters provide roster authority.", True),
        ("Title inference constitutes roster authority.", True),
        ("Title inference qualifies as roster authority.", True),
        ("Source-document mentions provide roster authority.", True),
        ("Title inference can authorize person creation.", True),
        ("Title inference is not rejected and constitutes roster authority.", True),
        ("Title inference is reviewed while it provides roster authority.", True),
        ("Title inference\nmay establish roster authority.", True),
        ("Linker-created memberships are roster authority.", True),
        ("Memberships created by the entity linker are roster authority.", True),
        ("Non-roster names may become person entities.", True),
        (
            "Non-roster names may become person entities, but they are not public.",
            True,
        ),
        ("Non-roster names may be linked to person entities.", True),
        ("Non-roster names link to person entities.", True),
        ("Non-roster names are linked to person entities.", True),
        ("Non-roster names become person entities.", True),
        ("Non-roster names can appear in people metadata.", True),
        ("Non-roster names may appear in source text, not profiles.", False),
        ("Non-roster names may receive profiles.", True),
        ("Non-roster people may become person entities.", True),
        ("Non-roster names remain searchable while they become person entities.", True),
        ("Non-roster names are allowed to become person entities.", True),
        ("Non-roster names\nmay become person entities.", True),
        ("Corrections may edit municipal source records.", True),
        ("Corrections edit municipal source records.", True),
        ("Corrections alter municipal source records.", True),
        ("Source documents will be modified during correction.", True),
        ("Source documents may be modified during correction.", True),
        ("No source documents may be edited.", False),
        ("City Coverage Expansion may proceed before T-GOV-2A completes.", True),
        ("City Coverage Expansion starts before T-GOV-2A completes.", True),
        ("City Coverage Expansion is unblocked before roster enforcement.", True),
        ("City Coverage Expansion is allowed before T-GOV-2A completes.", True),
        ("T-GOV-2A is optional before City Coverage Expansion.", True),
        ("Takedowns remove source text.", True),
        ("Corrections apply to derived records while they remove source documents.", True),
        ("Before T-GOV-2A completes, City Coverage Expansion may proceed.", True),
        ("Town Council currently enforces this policy.", True),
        ("Roster gating is already enforced.", True),
        ("Runtime enforcement is complete.", True),
        ("G4 is approved; T-GOV-2A remains pending.", False),
        ("Runtime enforcement is pending T-GOV-2A.", False),
        ("The historical alternatives were superseded by approved G4.", False),
        ("Title inference and linker-created memberships are not roster authority.", False),
        ("Non-roster names do not become person entities.", False),
        ("Corrections apply to derived records; source documents are not modified.", False),
        ("Corrections do not edit municipal source records.", False),
        ("Corrections are not allowed to edit municipal source records.", False),
        (
            "Corrections do not edit derived indexes but may remove municipal "
            "source records.",
            True,
        ),
        (
            "Corrections may edit municipal source records but do not modify "
            "derived indexes.",
            True,
        ),
        (
            "Corrections do not edit source records but may delete source documents.",
            True,
        ),
        (
            "Source documents are not modified but may be deleted during correction.",
            True,
        ),
        ("Corrections do not edit or remove source records.", False),
        (
            "Corrections are not allowed to modify or delete source documents.",
            False,
        ),
        ("Corrections do not edit, modify, or remove source records.", False),
        (
            "Source documents are not modified, but derived indexes are deleted.",
            False,
        ),
        ("Corrections apply while staff may edit source documents.", True),
        ("Corrections edit derived indexes and preserve source documents.", False),
        (
            "Source documents are not modified but may be retained and derived "
            "indexes are deleted.",
            False,
        ),
        ("Corrections permit editing source documents.", True),
        ("Deletion of source records is authorized for takedowns.", True),
        ("Deletion of source records is not authorized for takedowns.", False),
        ("Corrections prohibit editing source documents.", False),
        ("Correction controls prevent editing municipal source records.", False),
        (
            "Corrections remove derived records and source documents remain unchanged.",
            False,
        ),
        (
            "Source documents are not modified but may be retained, and derived "
            "indexes will be deleted.",
            False,
        ),
        ("Deletion of source records may be authorized for takedowns.", True),
        (
            "Deletion of source records is authorized for private-individual "
            "removal requests.",
            True,
        ),
        (
            "Corrections remove derived records and do not edit source documents.",
            False,
        ),
        ("Deletion of source records is authorized.", True),
        ("Removal of municipal source documents is permitted.", True),
        ("Corrections remove derived records, not source documents.", False),
        (
            "Corrections alter derived indexes rather than source records.",
            False,
        ),
        (
            "Corrections modify only derived records, leaving source documents "
            "unchanged.",
            False,
        ),
        ("Source documents are not modified but they may be deleted.", True),
        ("Staff may edit municipal source records.", True),
        ("Town Council deletes source documents.", True),
        ("Source-document mentions may become person entities.", True),
        ("Source-document mentions may create profiles.", True),
        ("Source-document mentions may create a profile.", True),
        ("Source-document mentions may create a membership.", True),
        ("Source-document mentions may generate profiles.", True),
        ("Source-document mentions may create links to profiles.", True),
        ("Title inference may produce memberships.", True),
        ("Person entities may be created from source-document mentions.", True),
        ("Profiles are created from source-document mentions.", True),
        ("Profiles are generated from source-document mentions.", True),
        ("No profiles may be created from source-document mentions.", False),
        (
            "Neither profiles nor memberships are created from "
            "source-document mentions.",
            False,
        ),
        (
            "Profiles for non-roster names may be created from "
            "source-document mentions.",
            True,
        ),
        (
            "Memberships may be created from linker-created memberships.",
            True,
        ),
        ("Title inference may produce people-facing records.", True),
        ("Source-document mentions may not become person entities.", False),
        (
            "Source-document mentions are not allowed to become person entities.",
            False,
        ),
        (
            "Title inference is not allowed to create people-facing records.",
            False,
        ),
        (
            "Corrections remove derived indexes associated with source documents.",
            False,
        ),
        (
            "Source-document mentions may create links to roster-authorized "
            "person entities.",
            False,
        ),
        (
            "Source-document mentions may become linked to roster-authorized "
            "person entities.",
            False,
        ),
        (
            "Source-document mentions may become associated with roster-authorized "
            "person entities.",
            False,
        ),
        (
            "Source-document mentions remain searchable while they may create "
            "links to roster-authorized person entities.",
            False,
        ),
        (
            "Title inference is prohibited; independently authoritative rosters "
            "may create person entities.",
            False,
        ),
        (
            "Corrections remove derived data; source documents are the public "
            "record and are not edited.",
            False,
        ),
        ("Title inference, not official rosters, provides roster authority.", True),
        (
            "Title inference rather than official membership data establishes "
            "roster authority.",
            True,
        ),
        ("Staff are forbidden to edit and delete source records.", False),
        ("Staff cannot edit and delete source records.", False),
        ("Staff are deleting source documents.", True),
        ("Staff may redact municipal source documents.", True),
        (
            "The originating municipality may edit its source records before "
            "publication.",
            False,
        ),
        ("Only the originating municipality may edit source records.", False),
        (
            "At the originating municipality's request, Town Council may edit "
            "source records.",
            True,
        ),
        (
            "Town Council and the originating municipality may edit source records.",
            True,
        ),
        (
            "Deletion of source records by the originating municipality is "
            "permitted under local retention law.",
            False,
        ),
        (
            "Deletion of source records by Town Council is permitted when the "
            "originating municipality requests it.",
            True,
        ),
        (
            "Source records may be edited by the originating municipality "
            "before publication.",
            False,
        ),
        (
            "Source records may be edited by the originating municipality or "
            "Town Council.",
            True,
        ),
        (
            "Source records may be edited by the originating municipality, or "
            "Town Council.",
            True,
        ),
        ("Corrections remove entity links to source documents.", False),
        (
            "Corrections modify annotations linked to municipal source records.",
            False,
        ),
        (
            "Source documents link to derived records that are deleted during "
            "correction.",
            False,
        ),
        (
            "Source documents link to derived metadata that is deleted during "
            "correction.",
            False,
        ),
        (
            "Source-document mentions remain searchable while official rosters "
            "create person entities.",
            False,
        ),
        ("Title inference is derived evidence rather than roster authority.", False),
        (
            "Title inference helps locate official rosters that provide roster "
            "authority.",
            False,
        ),
        (
            "Title inference, instead of official rosters, provides roster authority.",
            True,
        ),
        ("Title inference may count as roster authority.", True),
        ("Title inference is rejected as roster authority.", False),
        (
            "Neither title inference nor source-document mentions provide "
            "roster authority.",
            False,
        ),
        ("Corrections remove links derived from source documents.", False),
        ("Corrections remove metadata extracted from source records.", False),
        ("Corrections remove profiles built from source documents.", False),
        ("Title inference does not constitute roster authority.", False),
        ("City Coverage Expansion remains blocked until T-GOV-2A completes.", False),
        (
            "City Coverage Expansion may proceed after T-GOV-2A is complete "
            "and verified.",
            False,
        ),
        (
            "City Coverage Expansion starts only after T-GOV-2A is complete "
            "and verified.",
            False,
        ),
        ("City Coverage Expansion resumes when T-GOV-2A passes verification.", False),
        ("Non-roster names remain searchable; official rosters create person entities.", False),
        (
            "Corrections alter derived indexes; municipal source records remain "
            "unchanged.",
            False,
        ),
        (
            "City Coverage Expansion may proceed after T-GOV-2A completes, "
            "never before verification.",
            False,
        ),
        (
            "City Coverage Expansion can start prior to completion of T-GOV-2A.",
            True,
        ),
        (
            "City Coverage Expansion may proceed before roster-gated person "
            "linking is complete and verified.",
            True,
        ),
        (
            "City Coverage Expansion may proceed without delay once T-GOV-2A "
            "is complete and verified.",
            False,
        ),
        (
            "Non-roster names remain searchable, while official rosters create "
            "person entities.",
            False,
        ),
        (
            "Corrections alter derived indexes, while municipal source records "
            "remain unchanged.",
            False,
        ),
        (
            "Title inference is reviewed, while independently authoritative "
            "official membership data provides roster authority.",
            False,
        ),
        ("Town Council does not yet enforce this policy.", False),
        ("Runtime enforcement remains pending under T-GOV-2A.", False),
        ("T-GOV-2A must complete before City Coverage Expansion starts.", False),
        (
            "T-GOV-2A need not complete before City Coverage Expansion proceeds.",
            True,
        ),
        (
            "T-GOV-2A does not need to be complete before City Coverage "
            "Expansion proceeds.",
            True,
        ),
        (
            "T-GOV-2A is not required before City Coverage Expansion proceeds.",
            True,
        ),
    ),
)
def test_g4_contradiction_detection_covers_equivalent_wording(
    g4_policy: str,
    has_contradiction: bool,
) -> None:
    assert _g4_policy_has_contradiction(g4_policy) is has_contradiction


@pytest.mark.parametrize(
    "section_heading",
    (
        "## 2. Principles",
        "## 4. Correction and takedown",
        "## 5. Retention",
    ),
)
def test_g4_policy_scan_covers_live_data_governance_sections(
    section_heading: str,
) -> None:
    data_governance = (ROOT / "docs" / "DATA_GOVERNANCE.md").read_text(
        encoding="utf-8"
    )
    contradictory_governance = data_governance.replace(
        section_heading,
        f"{section_heading}\n\nCorrections edit municipal source records.",
        1,
    )

    assert _g4_policy_has_contradiction(contradictory_governance)


def test_g4_policy_scan_excludes_later_historical_adr_entries() -> None:
    architecture_decisions = (ROOT / "docs" / "ADR.md").read_text(encoding="utf-8")
    architecture_decisions_with_history = (
        f"{architecture_decisions}\n"
        "## 2026-07-30: Historical G4 wording\n\n"
        "The prior policy said G4 remains open.\n"
    )
    live_g4_decision = _required_markdown_entry(
        architecture_decisions_with_history,
        "## 2026-07-26: Roster-gated person linking",
    )

    assert not _g4_policy_has_contradiction(live_g4_decision)


def test_g4_policy_scan_covers_city_expansion_readiness() -> None:
    roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
    city_readiness = _required_markdown_section(
        roadmap,
        "### City Expansion Readiness",
        "\n## Next",
    )

    assert _g4_policy_has_contradiction(
        f"{city_readiness}\nCity Coverage Expansion may proceed before "
        "T-GOV-2A completes."
    )


def test_g4_roster_gated_policy_is_aligned() -> None:
    agent_policy = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    architecture_decisions = (ROOT / "docs" / "ADR.md").read_text(encoding="utf-8")
    data_governance = (ROOT / "docs" / "DATA_GOVERNANCE.md").read_text(
        encoding="utf-8"
    )
    roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
    remediation_ledger = (
        ROOT / "docs" / "plans" / "TOWN_COUNCIL_REMEDIATION_PLAN.md"
    ).read_text(encoding="utf-8")

    g4_decision = _required_markdown_entry(
        architecture_decisions,
        "## 2026-07-26: Roster-gated person linking",
    )
    person_policy = _required_markdown_section(
        data_governance,
        "## 3. Roster-gated person entities",
        "\n## 4. Correction and takedown",
    )
    g4_entry = _required_markdown_section(
        remediation_ledger,
        "- G4 pii_policy:",
        "\n- G5 migration_tooling:",
    )
    t_gov_2_entry = _required_markdown_section(
        remediation_ledger,
        "### T-GOV-2: ADR — Person-entity minimization & takedown (gate G4)",
        "\n### T-GOV-2A:",
    )
    t_gov_2a_entry = _required_markdown_section(
        remediation_ledger,
        "### T-GOV-2A: Enforce roster-gated person linking",
        "\n### T-GOV-3:",
    )
    city_coverage_plan = _required_markdown_section(
        roadmap,
        "### City Coverage Expansion I/II",
        "\n### Signal Intelligence",
    )
    city_readiness = _required_markdown_section(
        roadmap,
        "### City Expansion Readiness",
        "\n## Next",
    )

    assert "- Status: Accepted" in g4_decision
    assert "- Implemented: 2026-07-31" in g4_decision
    assert "currently approved Legistar OfficeRecords roster" in g4_decision
    assert "municipality and governing body" in g4_decision
    normalized_g4_decision = " ".join(g4_decision.split())
    assert (
        "Title inference, fuzzy matching, and source-document mentions are not "
        "roster authority. Their person-linking implementation is removed."
        in normalized_g4_decision
    )
    assert "Meeting `people_metadata` is omitted" in g4_decision
    assert "baseline_representative_v2" in g4_decision

    assert "Status: effective." in data_governance
    assert "currently approved Legistar OfficeRecords roster" in person_policy
    assert "municipality and governing body" in person_policy
    normalized_person_policy = " ".join(person_policy.split())
    assert (
        "Title inference, fuzzy matching, and source-document mentions are not "
        "roster authority. The document-derived person-linking path is removed."
        in normalized_person_policy
    )
    assert (
        "Non-roster names remain searchable source text. They do not become "
        "person entities, people metadata, profiles, memberships, vote attribution, "
        "or cross-document aggregation."
        in normalized_person_policy
    )
    assert "Source documents are not modified" in person_policy

    normalized_agent_policy = " ".join(agent_policy.split())
    assert (
        "Create person entities and people-facing records only from a currently "
        "approved Legistar OfficeRecords roster scoped to municipality and governing "
        "body. Cities without a current approved roster source fail closed. Title "
        "inference, fuzzy matching, and source-document mentions are not roster "
        "authority."
        in normalized_agent_policy
    )
    active_g4_policy = " ".join(
        (
            agent_policy,
            g4_decision,
            data_governance,
            g4_entry,
            t_gov_2_entry,
            t_gov_2a_entry,
            city_readiness,
            city_coverage_plan,
        )
    )
    assert not _g4_policy_has_contradiction(active_g4_policy)
    assert "status: complete and verified" in t_gov_2_entry
    assert "status: complete and verified" in t_gov_2a_entry
    assert "baseline_representative_v2" in g4_entry
    assert (
        "a valid `baseline_representative_v2` expected-baseline PR has merged"
        in city_coverage_plan
    )
    assert _remediation_task_states(remediation_ledger, "T-GOV-2") == ["Complete"]
    assert _remediation_task_states(remediation_ledger, "T-GOV-2A") == ["Complete"]


def test_g2_visitor_access_policy_is_aligned_after_t_sec_4_delivery():
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
    t_sec_4_states = _remediation_task_states(remediation_ledger, "T-SEC-4")

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
    assert "T-SEC-4 is complete" in g2_entry
    assert "operator-only proxy authentication is not approved" in g2_entry
    assert "per-client rate limits" in frontend_api_boundary.lower()
    assert "per-client rate limits" in g2_entry.lower()
    assert "decision_gate: G2 approved 2026-07-24" in t_sec_4_entry
    assert "status: complete and verified 2026-07-24 (PR #136)" in t_sec_4_entry
    assert t_sec_4_entry.count("- status:") == 1
    assert t_sec_4_states == ["Complete"]
    canonical_g2_policy = f"{frontend_api_boundary} {g2_entry}".lower()
    assert not _g2_policy_has_contradiction(canonical_g2_policy)


def test_g2_deployment_key_trust_is_bounded_after_t_sec_4_delivery():
    security_policy = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    accepted_risk = _required_markdown_section(
        security_policy,
        "**Deployment-key client identity trust.**",
        "\n## Dependency and supply chain",
    )

    assert "direct caller holding that secret" in accepted_risk
    assert "already has authority to invoke the protected actions" in accepted_risk
    assert "Visitors never receive the key." in accepted_risk
    assert "Revisit if the key is delegated" in accepted_risk
    assert "- [x] Caddy replaces caller forwarding metadata" in security_policy
    assert "Visitor-accessible AI actions before T-SEC-4" not in security_policy


def test_t_sec_6_closures_are_scoped():
    environment_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    remediation_ledger = (
        ROOT / "docs" / "plans" / "TOWN_COUNCIL_REMEDIATION_PLAN.md"
    ).read_text(encoding="utf-8")
    security_policy = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    implementation_plan = (
        ROOT / "docs" / "plans" / "T_SEC_6_SMALL_SECURITY_CLOSURES_PLAN.md"
    ).read_text(encoding="utf-8")
    ignore_entries = _ruff_per_file_ignore_entries()
    s105_explanations = {
        "pipeline/provider_telemetry.py": (
            7,
            "# noqa: S105 - Telemetry field label, not a secret.",
        ),
        "pipeline/topic_generation_contracts.py": (
            3,
            "# noqa: S105 - Parsing rule, not a secret.",
        ),
    }

    assert "NEXT_PUBLIC_API_AUTH_KEY" not in environment_example
    for relative_path, (
        expected_explanations,
        expected_explanation,
    ) in s105_explanations.items():
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "S105" not in ignore_entries.get(relative_path, set())
        assert "# ruff: noqa" not in source
        assert source.count("# noqa: S105") == expected_explanations
        assert source.count(expected_explanation) == expected_explanations

    assert _remediation_task_states(remediation_ledger, "T-SEC-6") == ["Complete"]
    assert "- status: complete and verified 2026-07-24 (PR #138)" in _required_markdown_section(
        remediation_ledger,
        "### T-SEC-6: Small closures",
        "\n### T-TIME-1:",
    )
    assert "`artifact_readiness: complete`" in implementation_plan
    assert "- [x] `/stats` gated or minimized; CORS without `allow_credentials`" in security_policy


def test_t_sec_4a_is_complete_after_g2_policy_record_merged():
    remediation_ledger = (
        ROOT / "docs" / "plans" / "TOWN_COUNCIL_REMEDIATION_PLAN.md"
    ).read_text(encoding="utf-8")
    t_sec_4a_entry = _required_markdown_section(
        remediation_ledger,
        "### T-SEC-4A: Record the approved G2 visitor-access policy",
        "\n### T-SEC-4:",
    )
    t_sec_4a_states = _remediation_task_states(remediation_ledger, "T-SEC-4A")
    normalized_t_sec_4a_entry = " ".join(t_sec_4a_entry.lower().split())

    assert "status: complete and verified 2026-07-24 (PR #133)" in t_sec_4a_entry
    assert t_sec_4a_entry.count("- status:") == 1
    assert "durable record satisfied by PR #133" in t_sec_4a_entry
    assert "durable record pending" not in normalized_t_sec_4a_entry
    assert t_sec_4a_states == ["Complete"]


def test_test_patch_points_policy_has_accepted_adr_and_effective_runbook():
    architecture_decisions = (ROOT / "docs" / "ADR.md").read_text(encoding="utf-8")
    testing_policy = (ROOT / "docs" / "TESTING.MD").read_text(encoding="utf-8")
    remediation_ledger = (
        ROOT / "docs" / "plans" / "TOWN_COUNCIL_REMEDIATION_PLAN.md"
    ).read_text(encoding="utf-8")
    test_patch_point_decision = _required_markdown_entry(
        architecture_decisions,
        "## 2026-07-24: Test patch points are not a public API",
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
    t_db_1_entry = _required_markdown_section(
        remediation_ledger,
        "### T-DB-1: Collapse the summary_backfill facade",
        "\n### T-DB-1B:",
    )
    dedup_b_row = next(
        line for line in remediation_ledger.splitlines() if line.startswith("| DEDUP-B")
    )
    complete_row = next(
        line for line in remediation_ledger.splitlines() if line.startswith("| **Complete** |")
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
    assert "T-GOV-6" in complete_row
    assert (
        "All three canonical documents are linked from the README Documentation Map"
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
    assert "Reduce injectable-callable" not in t_db_1_entry
    assert "summary callable" not in t_db_1_entry
    assert "no dependency-callable parameter" in t_db_1_entry
    assert "provider, Meilisearch, and Celery boundaries" in t_db_1_entry
    for owned_path in (
        "pipeline/task_facade_helpers.py",
        "pipeline/tasks.py",
        "tests/test_pipeline_batching.py",
        "tests/test_run_pipeline_orchestration.py",
        "tests/test_staged_hydrate_cities.py",
        "tests/test_tasks_agenda_summary_format.py",
    ):
        assert owned_path in t_db_1_entry
        assert owned_path in dedup_b_row


def test_t_gov_6_closes_reachable_deployment_posture_decision():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    security_policy = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    remediation_ledger = (
        ROOT / "docs" / "plans" / "TOWN_COUNCIL_REMEDIATION_PLAN.md"
    ).read_text(encoding="utf-8")
    g1_entry = _required_markdown_section(
        remediation_ledger,
        "- G1 deployment_posture:",
        "\n- G2 protected_action_policy:",
    )
    t_gov_6_entry = _required_markdown_section(
        remediation_ledger,
        "### T-GOV-6: Introduce SECURITY.md, docs/TESTING.md, docs/DATA_GOVERNANCE.md",
        "\n---\n\n## 7. EXECUTION ORDER SUMMARY",
    )

    deployment_posture = _required_markdown_section(
        security_policy,
        "## Deployment posture (decision G1)",
        "\n## Trust boundaries",
    )
    assert "Current declared posture: `reachable`" in deployment_posture
    assert "operator-approved 2026-07-26" in deployment_posture
    assert "**Approved 2026-07-26.**" in g1_entry
    assert "`reachable` deployment posture" in g1_entry
    assert not re.search(
        r"\b(?:default assumption|is any instance ever|open|pending|unresolved)\b",
        g1_entry,
        re.IGNORECASE,
    )
    assert "status: complete and verified 2026-07-26" in t_gov_6_entry
    assert _remediation_task_states(remediation_ledger, "T-GOV-6") == ["Complete"]
    assert "docs/plans/TOWN_COUNCIL_REMEDIATION_PLAN.md" in t_gov_6_entry
    assert "tests/test_repository_guardrails.py" in t_gov_6_entry
    assert "scope_authorization: Operator-approved 2026-07-26" in t_gov_6_entry
    assert "T-GOV-6 remains partially landed" not in remediation_ledger
    assert "T-GOV-6 DATA_GOVERNANCE.md (Section 3 pending G4)" not in remediation_ledger
    _, verify_marker, verification_block = t_gov_6_entry.partition("- verify:")
    assert verify_marker
    assert tuple(re.findall(r"`([^`]+)`", verification_block)) == (
        "./.venv/bin/ruff check .",
        "./.venv/bin/mypy",
        "PYTHONPATH=. .venv/bin/pytest -q tests/test_repository_guardrails.py",
        "PYTHONPATH=. .venv/bin/pytest -q tests/test_docs_links.py",
        "PYTHONPATH=. .venv/bin/pytest -q",
    )
    for policy_path in ("SECURITY.md", "docs/TESTING.MD", "docs/DATA_GOVERNANCE.md"):
        assert f"]({policy_path})" in readme


def test_t_gov_4_agents_policy_is_complete():
    agent_policy = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    remediation_ledger = (
        ROOT / "docs" / "plans" / "TOWN_COUNCIL_REMEDIATION_PLAN.md"
    ).read_text(encoding="utf-8")
    implementation_plan = (
        ROOT / "docs" / "plans" / "T_GOV_4_AGENTS_POLICY_CLOSURE_PLAN.md"
    ).read_text(encoding="utf-8")
    t_gov_4_entry = _required_markdown_section(
        remediation_ledger,
        "### T-GOV-4: Land the revised AGENTS.md",
        "\n### T-GOV-5:",
    )
    project_identity = _required_markdown_section(
        agent_policy,
        "<project_identity>",
        "\n</project_identity>",
    )
    known_antipatterns = _required_markdown_section(
        agent_policy,
        "<known_antipatterns>",
        "\n</known_antipatterns>",
    )

    assert _remediation_task_states(remediation_ledger, "T-GOV-4") == ["Complete"]
    assert "status: complete and verified 2026-07-24" in t_gov_4_entry
    assert t_gov_4_entry.count("- status:") == 1
    assert "commit `453c386` changed only `AGENTS.md`" in t_gov_4_entry
    assert "carry [transition] markers" not in t_gov_4_entry
    assert "`artifact_readiness: complete`" in implementation_plan

    assert "<known_antipatterns>" in agent_policy
    assert "<security_sensitive_paths>" in agent_policy
    assert "authoritative CI verification is the full test suite" in agent_policy
    assert "Both jobs are mandatory under the active" in agent_policy
    assert "File-set enumerations" in agent_policy
    assert "the CI full-suite and frontend jobs are delivered by remediation" not in agent_policy
    assert "effective when the frontend test runner lands" not in agent_policy
    assert "docs/TESTING.md" not in agent_policy
    assert "docs/TESTING.MD" in project_identity
    assert "docs/TESTING.MD" in known_antipatterns


def test_t_gov_3_closes_after_structural_rules_land():
    guardrail_policy = (
        ROOT / "docs" / "ENGINEERING_GUARDRAILS.md"
    ).read_text(encoding="utf-8")
    remediation_ledger = (
        ROOT / "docs" / "plans" / "TOWN_COUNCIL_REMEDIATION_PLAN.md"
    ).read_text(encoding="utf-8")
    t_gov_3_entry = _required_markdown_section(
        remediation_ledger,
        "### T-GOV-3: Redesign the guardrail regime",
        "\n### T-GOV-3A:",
    )
    t_gov_3a_entry = _required_markdown_section(
        remediation_ledger,
        "### T-GOV-3A: Retire file-length inventories",
        "\n### T-GOV-3B:",
    )
    t_gov_3b_entry = _required_markdown_section(
        remediation_ledger,
        "### T-GOV-3B: Enforce remaining structural smells",
        "\n### T-GOV-4:",
    )

    assert _remediation_task_states(remediation_ledger, "T-GOV-3") == ["Complete"]
    assert _remediation_task_states(remediation_ledger, "T-GOV-3A") == [
        "Complete"
    ]
    assert _remediation_task_states(remediation_ledger, "T-GOV-3B") == ["Complete"]
    assert "status: complete and verified 2026-07-30" in t_gov_3_entry
    assert "delivered:" in t_gov_3_entry
    assert "T-GOV-3A retirement" in t_gov_3_entry
    assert "remaining:" not in t_gov_3_entry
    assert "status: complete and verified 2026-07-26" in t_gov_3a_entry
    assert "depends_on: T-DC-1 and revised T-DE-1" in t_gov_3b_entry
    assert "status: complete and verified 2026-07-30" in t_gov_3b_entry
    assert "## Structural rules\n" in guardrail_policy
    assert "[transition: T-GOV-3]" not in guardrail_policy
    assert "duplicated module-global state synchronized by convention" not in guardrail_policy
    assert "Ruff `S608` rejects SQL-looking string interpolation" in guardrail_policy
    assert "Ruff `F403` rejects new wildcard imports" in guardrail_policy
    assert "top-level private `_sync_*_from_*` functions" in guardrail_policy
    assert "Retired: all per-file line-count assertions." in guardrail_policy
    assert "Remaining line assertions are deleted" not in guardrail_policy
    assert ("api/app_setup.py", ("api.main",)) in HELPER_FACADE_IMPORT_RULES


def test_t_gov_5_engineering_guardrails_is_complete():
    guardrail_policy = (
        ROOT / "docs" / "ENGINEERING_GUARDRAILS.md"
    ).read_text(encoding="utf-8")
    remediation_ledger = (
        ROOT / "docs" / "plans" / "TOWN_COUNCIL_REMEDIATION_PLAN.md"
    ).read_text(encoding="utf-8")
    implementation_plan = (
        ROOT / "docs" / "plans" / "T_GOV_5_ENGINEERING_GUARDRAILS_CLOSURE_PLAN.md"
    ).read_text(encoding="utf-8")
    ruff_config = tomllib.loads((ROOT / "ruff.toml").read_text(encoding="utf-8"))
    t_gov_5_entry = _required_markdown_section(
        remediation_ledger,
        "### T-GOV-5: Land the rewritten ENGINEERING_GUARDRAILS.md",
        "\n### T-GOV-6:",
    )
    structural_rules = _required_markdown_section(
        guardrail_policy,
        "## Structural rules",
        "\n## Optional local dead-code and complexity audit",
    )
    exception_process = _required_markdown_section(
        guardrail_policy,
        "## How to request an exception",
        "\n## Boundary exception handlers",
    )
    boundary_handlers = _required_markdown_section(
        guardrail_policy,
        "## Boundary exception handlers",
        "\n## Flat re-raise contract",
    )
    flat_reraise_contract = _required_markdown_section(
        guardrail_policy,
        "## Flat re-raise contract",
        "\n## Typed subtree",
    )
    python_path_pattern = re.compile(
        r"(?<![\w./*?\[\]-])(?:[\w.*?\[\]-]+/)*[\w.*?\[\]-]+\.py\b"
    )
    python_path_references = python_path_pattern.findall(guardrail_policy)
    python_path_globs = {
        python_path
        for python_path in python_path_references
        if any(glob_marker in python_path for glob_marker in ("*", "?", "["))
    }
    python_path_enumerations = [
        sorted(set(python_path_pattern.findall(markdown_section)))
        for markdown_section in re.split(r"(?m)^## ", guardrail_policy)
        if len(set(python_path_pattern.findall(markdown_section))) > 1
    ]

    assert _remediation_task_states(remediation_ledger, "T-GOV-5") == ["Complete"]
    assert "status: complete and verified 2026-07-24" in t_gov_5_entry
    assert t_gov_5_entry.count("- status:") == 1
    assert "commit `c4a4a27` changed only `docs/ENGINEERING_GUARDRAILS.md`" in (
        t_gov_5_entry
    )
    assert "original draft is unavailable for exact identity comparison" in (
        t_gov_5_entry
    )
    assert "`artifact_readiness: complete`" in implementation_plan

    assert "lands alongside remediation task T-GOV-3" not in guardrail_policy
    assert "docs/TESTING.md" not in guardrail_policy
    assert "docs/TESTING.MD" in guardrail_policy
    assert "when adopted" not in structural_rules
    assert "C901" in structural_rules
    assert "configured repository scope" in structural_rules
    assert "max-complexity = 10" in structural_rules
    assert "C901" in ruff_config["lint"]["select"]
    assert ruff_config["lint"]["mccabe"]["max-complexity"] == 10
    assert "[transition: T-CI-4]" not in guardrail_policy
    assert "Keep exceptions narrow and path-specific." in exception_process
    assert "log with context and return a typed failure payload" in boundary_handlers
    assert "must not contain conditional or loop flow" in flat_reraise_contract
    assert re.search(
        r"must not contain .*?`sys\.exit\(\)`\.",
        flat_reraise_contract,
    )
    assert python_path_globs == set()
    assert python_path_enumerations == []


def test_test_patch_point_adr_boundary_uses_the_next_decision_heading():
    architecture_decisions = """
## 2026-07-24: Test patch points are not a public API

- Status: Accepted

## 2026-07-23: Unrelated later decision

- Status: Proposed

## 2026-05-17: Older decision

- Status: Accepted
"""

    test_patch_point_decision = _required_markdown_entry(
        architecture_decisions,
        "## 2026-07-24: Test patch points are not a public API",
    )

    assert test_patch_point_decision == "- Status: Accepted"


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
        (1, "# G3 still\n# blocks facade removal."),
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
        "# G3 preserves the historical ADR about facade removal.",
        "# The old ADR says G3 blocks facade removal.",
        "# The superseded decision says G3 preserves the test seam.",
        "# G3 used to block facade removal.",
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
        "# G3 blocks migration rather than facade removal.",
        "# G3 blocks migration instead of test seam cleanup.",
        "# G3 blocks migration rather than blocking facade removal.",
        "# G3 blocks migration instead of allowing facade removal.",
        "# G3 delays migration rather than preserving the test seam.",
        "# G3 blocks migration instead of keeping the test facade.",
        "# G3 blocks migration rather than holding the test seam.",
        "# G3 blocks migration instead of requiring preservation of the test facade.",
        "# G3 blocks migration instead of requiring the preservation of the test facade.",
        "# G3 blocks migration instead of requiring continued preservation of the test facade.",
        "# G3 no longer blocks facade removal, preserving the runtime API.",
        "# G3 blocks neither facade removal nor test seams.",
        "# G3 preserves no test facade.",
        "# G3 is not expected to block facade removal.",
        "# G3 proceeds without blocking facade removal.",
        "# G3 preserves the public facade.",
        "# G3 requires the public facade to remain.",
        "# The api.main facade does not remain until G3 lands.",
        "# G3 preserves facade runtime compatibility.",
        "# G3 blocks cache removal.",
        "# G3 blocks temporary-file removal.",
        "# G3 no longer remains a prerequisite for facade removal.",
        "# G3 no longer is a prerequisite for facade removal.",
        "# G3 is no longer a prerequisite for facade removal.",
        "# G3 preserves runtime compatibility and permits test facade removal.",
        "# G3 is on hold and facade removal continues.",
        "# G3 permits keeping the test facade.",
        "# G3 does not keep the test facade.",
        "# Do not hold the test seam until G3 is resolved.",
        "# G3 keeps documentation for the test facade current.",
        "# G3 keeps the test facade documentation current.",
        "# The G3 hold note documents facade removal progress.",
        "# Avoid keeping the test facade until G3 is resolved.",
        "# Stop keeping the test seam until G3 is resolved.",
        "# G3 is satisfied, so nothing blocks facade removal.",
        "# None of the facade removals are blocked by G3.",
        "# None of the test seams remain blocked by G3.",
        "# G3 no longer requires preservation of the test facade.",
        "# G3 does not require the test facade to remain.",
        "# No G3 policy requires the test facade to remain.",
        "# Neither G3 nor T-SEC-4 requires the test facade to remain.",
        "# G3 requires the test facade documentation.",
        "# G3 requires the test seam status.",
        "# G3 allows removing the public facade.",
        "# G3 does not remove the public facade.",
        "# G3 blocks removal of the facade documentation.",
        "# Until G3 lands, do not remove this facade documentation.",
        "# G3 defers deleting the test seam status.",
        "# G3 is not a blocker for facade removal.",
        "# G3 blocks cleanup of the facade documentation.",
        "# G3 is satisfied. T-SEC-4 blocks facade removal until its work lands.",
        "# G3 is accepted, but T-SEC-4 blocks facade removal.",
        "# G3 is accepted and T-SEC-4 blocks facade removal.",
        "# G3 blocks migration and T-SEC-4 blocks facade removal.",
        "# G3 is accepted, but T-SEC-4 keeps the test facade until its work lands.",
        "# G3 is accepted, but T-SEC-4 is pending, so do not remove the test facade until T-SEC-4 lands.",
        "# G3 is satisfied\n# T-SEC-4 blocks facade removal until its work lands.",
        "# G3 is satisfied\n# - T-SEC-4 blocks facade removal until its work lands.",
        "# G3 need not land before facade removal.",
        "# Facade removal must not wait for G3.",
        "# Facade removal must land before G3.",
        "# G3 must wait for facade removal.",
        "# G3 must be accepted before facade removal documentation can proceed.",
        "# G3 must land before we update facade documentation.",
        "# G3 must be accepted before the test facade status can be removed.",
        "# G3 is satisfied; T-SEC-4 must land before facade removal.",
        "# G3 does not prohibit facade removal.",
        "# G3 no longer forbids facade removal.",
        "# G3 is prohibited from blocking facade removal.",
        "# G3 is forbidden from blocking facade removal.",
        "# G3 prohibits blocking facade removal.",
        "# G3 forbids keeping the test facade.",
        "# G3 prohibits T-SEC-4 from blocking facade removal.",
        "# G3 means facade removal can proceed.",
        "# Historically, G3 means the facade cannot be removed.",
        "# Does G3 mean the facade cannot be removed?",
        "# G3 means the facade cannot be removed?",
        "# Until G3 lands? Keep the test facade.",
        "# Historically, before G3 landed. Keep the test facade.",
        "# G3 preserves the HTTP response wrapper.",
        "# G3 blocks removal of the crawler request wrapper.",
        "# G3 preserves the public API re-export.",
        "# G3 must land for audit documentation. T-SEC-4 blocks facade removal until its work lands.",
        "# G3 must land. T-SEC-4 blocks facade removal until its work lands.",
        "# G3 must land. T-SEC-4 blocks migration until its work lands. Facade removal remains blocked until then.",
        "# Do not remove the test facade before T-SEC-4 lands; G3 is accepted.",
        "# G3 is accepted; do not remove the test facade before T-SEC-4 lands.",
        "# G3 records whether the test seam remains until G3 is accepted.",
        "# G3 asks whether the test facade stays until G3 lands.",
        "# G3 asks whether the test seam remains until G3 is accepted.",
        "# G3 checks whether the test seam remains until G3 is accepted.",
        "# Does the test seam remain until G3 is accepted?",
        "# Why must the test seam remain until G3 is accepted?",
        "# The G3 audit asks: does the test seam remain until G3 is accepted?",
        "# G3 asks whether to keep the test facade until Phase 2.",
        "# Does G3 block facade removal until G3 is accepted?",
        "# Why does G3 preserve the test seam until Phase 2?",
        "# Does G3 require preservation of the test facade until Phase 2?",
        "# Does G3 prohibit facade removal until Phase 2?",
        "# May G3 preserve the test seam until Phase 2?",
        "# Might G3 block facade removal until Phase 2?",
        "# Shall G3 keep the test facade until Phase 2?",
        "# Did G3 block facade removal until Phase 2?",
        "# Was G3 preserving the test seam until Phase 2?",
        "# Did G3 require preservation of the test facade until Phase 2?",
        "# Historically, G3 required the test facade to remain.",
        "# G3 once blocked facade removal.",
        "# Historically, G3 required the test facade to remain, and G3 preserved the test seam.",
        "# G3 prevents retaining the test facade.",
        "# G3 stops retaining the test facade.",
        "# Phase 2 can begin after G3 lands.",
        "# G3: no test facade must remain.",
        "# G3: neither the test facade nor the test seam must remain.",
        "# G3 records the Phase 2 gate.",
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
        "# G3 and T-SEC-4 block facade removal.",
        "# G3 and T-SEC-4 preserve the test seam.",
        "# G3 and T-SEC-4 keep the test facade until Phase 2.",
        "# G3 and\n# T-SEC-4 block facade removal.",
        "# Both G3 and T-SEC-4 block facade removal.",
        "# Both G3 and\n# T-SEC-4 block facade removal.",
        "# G3 and T-SEC-4 must land before facade removal.",
        "# G3 and\n# T-SEC-4 must land before facade removal.",
        "# Both G3 and T-SEC-4 must land before facade removal.",
        "# Historically, G3 required the test facade to remain, but G3 still blocks facade removal.",
        "# The old ADR says G3 blocks facade removal, but G3 still preserves the test facade.",
        "# Historically, G3 means the facade cannot be removed, but G3 still blocks facade removal.",
        "# Historically, G3 required the test facade to remain, and G3 still blocks facade removal.",
        "# Previously G3 blocked facade removal; G3 still preserves the test seam.",
        "# Historically, the test facade remained in place; G3 still blocks facade removal.",
        "# Historically, the test facade remained in place, and G3 now preserves the test seam.",
        "# Historically, the test facade remained in place, and G3 blocks facade removal.",
        "# G3 once again blocks facade removal.",
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
        "# G3 stops facade removal.",
        "# Until G3 is resolved, retain the test seam.",
        "# Until G3 lands, do not remove the test facade, but T-SEC-4 status is current.",
        "# T-SEC-4 status is current, but before G3 lands, do not remove the test facade.",
        "# Until G3 lands and T-SEC-4 is complete, do not remove the test facade.",
        "# Before G3 lands and T-SEC-4 is complete, do not remove the test facade.",
        "# G3 remains a prerequisite for facade removal.",
        "# G3 is not resolved so remains a prerequisite for facade removal.",
        "# G3 is unresolved. # Facade removal remains blocked.",
        "# G3 does not permit facade removal.",
        "# G3 does not allow the test seam.",
        "# Keep the test facade until G3 is resolved.",
        "# Hold the test seam until G3 is resolved.",
        "# Keep the test patch point until G3 is resolved.",
        "# Keep this test-only patch point until G3 is resolved.",
        "# Keep our test facade until G3 is resolved.",
        "# Keep the compatibility-only test facade until G3 is resolved.",
        "# Keep these test patch points until G3 is resolved.",
        "# Keep the test facades until G3 is resolved.",
        "# Keep the test facade while G3 remains unresolved.",
        "# The test seam remains until G3 is accepted.",
        "# The test facade remains in place until G3 is resolved.",
        "# The test patch point remains until G3 lands.",
        "# The test seam will remain until G3 is accepted.",
        "# The test facades must remain in place until G3 lands.",
        "# G3: the test facade must remain.",
        "# The test patch point should remain until G3 is resolved.",
        "# The test seam has to remain until G3 is accepted.",
        "# The test seam is required to remain until G3 is accepted.",
        "# The test seam needs to remain until G3 is accepted.",
        "# The test seam is still required to remain until G3 is accepted.",
        "# The test seam must continue to remain until G3 is accepted.",
        "# G3 blocks migration rather than facade removal, but G3 preserves the test seam.",
        "# G3 records whether migration is blocked, but the test seam remains until G3 is accepted.",
        "# G3 asks whether migration is blocked, but the test seam remains until G3 is accepted.",
        "# G3 asks whether to keep one test facade, but G3 preserves the test seam.",
        "# Does G3 block migration? G3 preserves the test seam.",
        "# G3 delays facade removal.",
        "# Facade removal is gated on G3.",
        "# Phase 2 cannot begin until G3 lands.",
        "# G3 gates Phase 2.",
        "# G3 postpones test seam cleanup.",
        "# Nothing but G3 blocks facade removal.",
        "# G3 remains unresolved, requiring preservation of the test facade.",
        "# G3 requires continued preservation of the test facade.",
        "# G3 requires temporary preservation of the test seam.",
        "# G3 requires the test facade to remain.",
        "# G3 requires the public facade and test facade to remain.",
        "# The api.main facade remains until G3 lands.",
        "# G3 still blocks removal of the facade.",
        "# G3 defers removing the facade.",
        "# Until G3 lands, do not remove this facade.",
        "# G3 is a blocker for facade removal.",
        "# G3 blocks cleanup of the facade.",
        "# G3 must land before facade removal.",
        "# G3 must land before we remove the facade.",
        "# G3 must be accepted before facade removal.",
        "# G3 must be complete before facade removal.",
        "# G3 must be completed before test seam cleanup.",
        "# G3 must be resolved before removing the test facade.",
        "# G3 must be accepted before facade removal can proceed.",
        "# G3 must be accepted before the test facade can be removed.",
        "# Facade removal must wait for G3.",
        "# G3 prohibits facade removal.",
        "# G3 forbids facade removal.",
        "# Facade removal is prohibited by G3.",
        "# Facade removal is forbidden by G3.",
        "# G3 still prohibits facade removal.",
        "# G3 prohibits the removal of the facade.",
        "# Facade removal is still prohibited by G3.",
        "# G3 currently prohibits facade removal.",
        "# Facade removal is explicitly prohibited by G3.",
        "# G3 remains pending, so preserve the monkeypatch compatibility shim.",
        "# G3 preserves the test re-export until Phase 2.",
        "# G3 still blocks removal of test-only re-exports.",
        "# G3 blocks removal of test facade wrappers.",
        "# G3 blocks removal of the test wrapper.",
        "# G3 preserves synchronized globals.",
        "# G3 delays removal of injectable callables.",
        "# G3 must land. Facade removal remains blocked until then.",
        "# Until G3 lands. Keep the test facade.",
        "# Do not remove the test facade before G3 is accepted.",
        "# The test facade cannot be removed until G3 lands.",
        "# The test facade stays until G3 lands.",
        "# G3 means the facade cannot be removed.",
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
