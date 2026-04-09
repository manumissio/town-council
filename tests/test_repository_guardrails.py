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
    "pipeline/monitor.py",
    "pipeline/person_linker.py",
    "pipeline/reindex_semantic.py",
    "pipeline/run_agenda_qa.py",
    "pipeline/run_pipeline.py",
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
    "pipeline/db_migrate.py",
    "pipeline/db_session.py",
    "pipeline/diagnose_search_sort.py",
    "pipeline/diagnose_semantic_search.py",
    "pipeline/enrichment_tasks.py",
    "pipeline/indexer.py",
    "pipeline/lineage_service.py",
    "pipeline/llm.py",
    "pipeline/llm_provider.py",
    "pipeline/metrics.py",
    "pipeline/models.py",
    "pipeline/nlp_worker.py",
    "pipeline/profiling.py",
    "pipeline/run_agenda_qa.py",
    "pipeline/run_batch_enrichment.py",
    "pipeline/run_pipeline.py",
    "pipeline/runtime_guardrails.py",
    "pipeline/summary_backfill.py",
    "pipeline/semantic_index.py",
    "pipeline/semantic_tasks.py",
    "pipeline/startup_purge.py",
    "pipeline/task_startup.py",
    "pipeline/table_worker.py",
    "pipeline/tasks.py",
    "pipeline/text_cleaning.py",
    "pipeline/topic_worker.py",
    "pipeline/vote_extractor.py",
    "scripts/backfill_summaries.py",
    "scripts/collect_soak_metrics.py",
    "scripts/enrichment_worker_healthcheck.py",
    "scripts/evaluate_soak_week.py",
    "scripts/hydrate_repaired_city_catalogs.py",
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
    "pipeline/agenda_crosscheck.py",
    "pipeline/agenda_legistar.py",
    "pipeline/agenda_resolver.py",
    "pipeline/city_scope.py",
    "pipeline/content_hash.py",
    "pipeline/document_kinds.py",
    "pipeline/agenda_service.py",
    "pipeline/agenda_verification_model_access.py",
    "pipeline/extraction_service.py",
    "pipeline/extraction_state.py",
    "pipeline/maintenance_run_status.py",
    "pipeline/models.py",
    "pipeline/profiling.py",
    "pipeline/rollout_registry.py",
    "pipeline/runtime_guardrails.py",
    "pipeline/summary_hydration_diagnostics.py",
    "pipeline/summary_quality.py",
    "pipeline/summary_freshness.py",
    "pipeline/utils.py",
    "pipeline/verification_service.py",
    "pipeline/vote_extractor.py",
    "scripts/analyze_pipeline_profile.py",
)
CANDIDATE_FORMATTER_WAVE_PATHS = TYPED_SUBTREE_PATHS
FORMATTER_WAVE_COMMAND = (
    "./.venv/bin/ruff format --check "
    + " ".join(CANDIDATE_FORMATTER_WAVE_PATHS)
)


def _tracked_files() -> list[Path]:
    output = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True)
    return [ROOT / line for line in output.splitlines() if line]


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
            token.strip().strip('"')
            for token in match.group("rules").split(",")
            if token.strip()
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

    assert 'src = ["api", "pipeline", "scripts", "tests"]' in config_text
    assert "select = [\"E722\", \"F401\", \"F841\", \"B006\", \"B007\", \"B023\", \"BLE001\"]" in config_text
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
    broad_exception_paths = {
        path
        for path, rules in ignore_entries.items()
        if "BLE001" in rules
    }

    assert broad_exception_paths == APPROVED_BROAD_EXCEPTION_PATHS
    assert broad_exception_paths.isdisjoint(BLE001_WILDCARD_PATHS)


def test_broad_exception_handlers_stay_on_approved_boundaries_and_take_action():
    unauthorized_handlers: list[str] = []
    silent_handlers: list[str] = []

    for tracked_path in _tracked_files():
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
                    or (
                        isinstance(body_node, ast.Expr)
                        and isinstance(body_node.value, ast.Constant)
                    )
                    for body_node in body_nodes
                )
                if is_silent:
                    silent_handlers.append(handler_ref)

    assert unauthorized_handlers == []
    assert silent_handlers == []
