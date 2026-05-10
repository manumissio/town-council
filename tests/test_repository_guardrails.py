from __future__ import annotations

import ast
import subprocess
from pathlib import Path
import re


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
    "api/metrics.py",
    "pipeline/agenda_legistar.py",
    "pipeline/agenda_worker.py",
    "pipeline/backlog_maintenance.py",
    "pipeline/check_faiss_runtime.py",
    "pipeline/db_migration_runner.py",
    "pipeline/db_session.py",
    "pipeline/diagnose_search_sort.py",
    "pipeline/diagnose_semantic_search.py",
    "pipeline/indexer.py",
    "pipeline/indexer_meilisearch.py",
    "pipeline/lineage_service.py",
    "pipeline/llm.py",
    "pipeline/local_ai_provider_calls.py",
    "pipeline/model_base.py",
    "pipeline/nlp_entity_model.py",
    "pipeline/profiling.py",
    "pipeline/run_agenda_qa.py",
    "pipeline/run_batch_enrichment.py",
    "pipeline/run_pipeline_steps.py",
    "pipeline/runtime_guardrails.py",
    "pipeline/summary_backfill.py",
    "pipeline/summary_backfill_dispatch.py",
    "pipeline/semantic_index.py",
    "pipeline/semantic_tasks.py",
    "pipeline/startup_purge.py",
    "pipeline/task_startup.py",
    "pipeline/table_worker.py",
    "pipeline/tasks.py",
    "pipeline/text_cleaning.py",
    "pipeline/topic_worker.py",
    "pipeline/vote_extraction_runner.py",
    "scripts/backfill_summaries.py",
    "scripts/collect_soak_metrics.py",
    "scripts/enrichment_worker_healthcheck.py",
    "scripts/evaluate_soak_week.py",
    "scripts/hydration_repaired_runner.py",
    "scripts/hydration_repaired_summary.py",
    "scripts/parse_task_launch.py",
    "scripts/probe_local_model_candidate.py",
    "scripts/repair_san_mateo_laserfiche_backlog.py",
    "scripts/reset_laserfiche_error_agenda_rows.py",
    "scripts/score_ab_results.py",
    "scripts/semantic_worker_healthcheck.py",
    "scripts/worker_healthcheck.py",
}
BLE001_WILDCARD_PATHS = {"scripts/*.py", "tests/*.py"}
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
    "scripts/analyze_pipeline_profile.py",
)
CANDIDATE_FORMATTER_WAVE_PATHS = TYPED_SUBTREE_PATHS
FORMATTER_WAVE_COMMAND = "./.venv/bin/ruff format --check " + " ".join(CANDIDATE_FORMATTER_WAVE_PATHS)
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
    "scripts/collect_soak_metrics.py",
    "scripts/evaluate_soak_week.py",
    "scripts/operator_profile_ab.py",
    "scripts/operator_profile_artifacts.py",
    "scripts/operator_profile_metric_deltas.py",
    "scripts/operator_profile_metrics.py",
    "scripts/operator_profile_reports.py",
    "scripts/operator_profile_soak_eval.py",
    "scripts/pipeline_profile_analysis.py",
    "scripts/pipeline_profile_compare.py",
    "scripts/profile_pipeline.py",
    "scripts/profile_pipeline_runner.py",
    "scripts/profile_pipeline_selection.py",
    "scripts/score_ab_results.py",
)
TASK_API_FACADE_CLEANUP_MODULES = (
    "pipeline/tasks.py",
    "pipeline/task_facade_helpers.py",
    "pipeline/task_summary_generation.py",
    "pipeline/task_summary_side_effects.py",
    "api/task_routes.py",
    "api/task_dispatch.py",
    "api/task_route_support.py",
)
SEARCH_SUPPORT_CLEANUP_MODULES = (
    "api/search_support.py",
    "api/search/support_core.py",
    "api/search/filter_support.py",
    "api/search/trends_support.py",
    "api/search/semantic_support.py",
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


def _broad_exception_scan_files() -> list[Path]:
    tracked_files = {path.resolve() for path in _tracked_files()}
    for module_path in (
        *CONFIG_CLEANUP_MODULES,
        *METRICS_CLEANUP_MODULES,
        *DOWNLOADER_CLEANUP_MODULES,
        *AGENDA_EXTRACTION_CLEANUP_MODULES,
        *AGENDA_TEXT_HEURISTICS_CLEANUP_MODULES,
        *AGENDA_RESOLVER_CLEANUP_MODULES,
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
        *TASK_API_FACADE_CLEANUP_MODULES,
        *SEARCH_SUPPORT_CLEANUP_MODULES,
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


def _ruff_per_file_ignore_entries() -> dict[str, set[str]]:
    config_text = (ROOT / "ruff.toml").read_text(encoding="utf-8")
    entries: dict[str, set[str]] = {}
    for raw_line in config_text.splitlines():
        line = raw_line.strip()
        match = re.match(r'^"(?P<path>[^"]+)"\s*=\s*\[(?P<rules>[^\]]*)\]', line)
        if not match:
            continue
        entries[match.group("path")] = {
            token.strip().strip('"') for token in match.group("rules").split(",") if token.strip()
        }
    return entries


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

    assert 'src = ["api", "pipeline", "scripts", "tests"]' in config_text
    assert 'select = ["E722", "F401", "F841", "B006", "B007", "B023", "BLE001"]' in config_text
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

    assert FORMATTER_WAVE_COMMAND in docs_text
    assert "scoped formatter guardrail" in docs_text
    assert "./.venv/bin/ruff format --check api pipeline scripts tests" not in docs_text
    assert "ruff format --check" not in agents_text
    assert "python -m ruff format --check " + " ".join(CANDIDATE_FORMATTER_WAVE_PATHS) in workflow_text
    assert "python -m ruff format --check api pipeline scripts tests" not in workflow_text


def test_broad_exception_allowlist_stays_explicit():
    ignore_entries = _ruff_per_file_ignore_entries()
    broad_exception_paths = {path for path, rules in ignore_entries.items() if "BLE001" in rules}

    assert broad_exception_paths == APPROVED_BROAD_EXCEPTION_PATHS
    assert broad_exception_paths.isdisjoint(BLE001_WILDCARD_PATHS)


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
                if relative_path not in APPROVED_BROAD_EXCEPTION_PATHS:
                    unauthorized_handlers.append(handler_ref)
                    continue

                body_nodes = handler.body
                is_silent = all(
                    isinstance(body_node, ast.Pass)
                    or (isinstance(body_node, ast.Expr) and isinstance(body_node.value, ast.Constant))
                    for body_node in body_nodes
                )
                if is_silent:
                    silent_handlers.append(handler_ref)

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


def test_summary_text_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in SUMMARY_TEXT_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_vote_extraction_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in VOTE_EXTRACTION_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []


def test_nlp_entity_cleanup_modules_stay_under_size_target():
    oversized_modules = [
        module_path
        for module_path in NLP_ENTITY_CLEANUP_MODULES
        if len((ROOT / module_path).read_text(encoding="utf-8").splitlines()) > 300
    ]

    assert oversized_modules == []
