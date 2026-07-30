import json
import os
import re
import subprocess
from pathlib import Path

import pytest

TEST_MEILI_MASTER_KEY = "test-only-meilisearch-master-key"
RUNTIME_REQUIREMENT_PATHS = (
    Path("api/requirements.txt"),
    Path("council_crawler/requirements.txt"),
    Path("pipeline/requirements.txt"),
    Path("pipeline/requirements-batch.txt"),
    Path("semantic_service/requirements.txt"),
)
ACTIVE_REQUIREMENT_PATHS = (
    *RUNTIME_REQUIREMENT_PATHS,
    Path("pipeline/requirements-dev.txt"),
)
SHARED_EXACT_CONSTRAINTS = {
    "beautifulsoup4": "4.12.3",
    "celery": "5.3.4",
    "fastapi": "0.115.8",
    "httpx": "0.28.1",
    "meilisearch": "0.31.0",
    "prometheus-client": "0.26.0",
    "psycopg2-binary": "2.9.10",
    "rapidfuzz": "3.14.3",
    "redis": "5.0.1",
    "sqlalchemy": "2.0.38",
    "uvicorn": "0.34.0",
}


def _compose_services(
    *compose_paths: str,
    profiles: tuple[str, ...] = (),
) -> dict[str, dict[str, object]]:
    compose_command = ["docker", "compose"]
    for profile in profiles:
        compose_command.extend(("--profile", profile))
    for compose_path in compose_paths:
        compose_command.extend(("-f", compose_path))
    compose_command.extend(("config", "--format", "json"))
    compose_environment = os.environ.copy()
    compose_environment.setdefault("MEILI_MASTER_KEY", TEST_MEILI_MASTER_KEY)
    completed_process = subprocess.run(
        compose_command,
        check=True,
        capture_output=True,
        env=compose_environment,
        text=True,
    )
    compose_project = json.loads(completed_process.stdout)
    return compose_project["services"]


def _published_port_bindings(
    compose_services: dict[str, dict[str, object]],
) -> set[tuple[str, str | None, str, int]]:
    return {
        (
            service_name,
            port_mapping.get("host_ip"),
            port_mapping["published"],
            port_mapping["target"],
        )
        for service_name, service_config in compose_services.items()
        for port_mapping in service_config.get("ports", [])
    }


def _service_dependencies(
    compose_services: dict[str, dict[str, object]],
) -> dict[str, set[str]]:
    return {
        service_name: set(service_config.get("depends_on", {}))
        for service_name, service_config in compose_services.items()
    }


def _normalized_requirement_name(requirement_line: str) -> str | None:
    requirement_specifier = requirement_line.partition("#")[0].strip()
    if not requirement_specifier:
        return None
    requirement_name = re.split(
        r"[<>=!~;\[\s]",
        requirement_specifier,
        maxsplit=1,
    )[0]
    return re.sub(r"[-_.]+", "-", requirement_name).lower()


def _requirement_names(requirements_path: Path) -> set[str]:
    return {
        requirement_name
        for requirement_line in requirements_path.read_text(
            encoding="utf-8"
        ).splitlines()
        if (requirement_name := _normalized_requirement_name(requirement_line))
    }


def _requirement_directives(requirements_path: Path) -> list[str]:
    return [
        requirement_line.partition("#")[0].strip()
        for requirement_line in requirements_path.read_text(
            encoding="utf-8"
        ).splitlines()
        if requirement_line.partition("#")[0].strip()
    ]


def test_compose_uses_role_specific_python_images_and_model_volume():
    source = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "image: town-council-python-crawler" in source
    assert "image: town-council-python-api" in source
    assert "image: town-council-python-semantic" in source
    assert "image: town-council-python-worker-live" in source
    assert "image: town-council-python-worker-batch" in source
    assert "enrichment-worker:" in source
    assert "semantic-worker:" in source
    assert "models_data:/models" in source


def test_base_compose_publishes_only_application_interfaces():
    compose_services = _compose_services("docker-compose.yml")

    assert _published_port_bindings(compose_services) == {
        ("api", None, "8000", 8000),
        ("ingress", None, "3000", 3000),
    }
    assert all(service_config.get("network_mode") != "host" for service_config in compose_services.values())


def test_dev_overlay_publishes_operator_services_on_loopback_only():
    base_services = _compose_services("docker-compose.yml")
    development_services = _compose_services("docker-compose.yml", "docker-compose.dev.yml")

    assert _published_port_bindings(development_services) == {
        ("api", None, "8000", 8000),
        ("ingress", None, "3000", 3000),
        ("grafana", "127.0.0.1", "3001", 3000),
        ("meilisearch", "127.0.0.1", "7700", 7700),
        ("postgres", "127.0.0.1", "5432", 5432),
        ("prometheus", "127.0.0.1", "9090", 9090),
        ("redis", "127.0.0.1", "6379", 6379),
    }
    assert _service_dependencies(development_services) == _service_dependencies(base_services)
    assert all(service_config.get("network_mode") != "host" for service_config in development_services.values())


def test_ingress_is_the_only_public_frontend_boundary() -> None:
    compose_services = _compose_services("docker-compose.yml")
    development_services = _compose_services(
        "docker-compose.yml",
        "docker-compose.dev.yml",
    )
    ingress = compose_services["ingress"]
    frontend = compose_services["frontend"]
    api = compose_services["api"]

    assert ingress["image"] == "caddy:2.11.4-alpine"
    assert set(ingress["depends_on"]) == {"frontend"}
    assert frontend.get("ports", []) == []
    assert frontend["expose"] == ["3000"]
    assert "--no-proxy-headers" in api["command"]
    assert "--no-proxy-headers" in development_services["api"]["command"]

    ingress_mounts = {
        (volume["source"], volume["target"], volume["read_only"])
        for volume in ingress["volumes"]
    }
    assert (
        str((Path.cwd() / "docker" / "Caddyfile").resolve()),
        "/etc/caddy/Caddyfile",
        True,
    ) in ingress_mounts

    caddyfile = Path("docker/Caddyfile").read_text(encoding="utf-8")
    assert "reverse_proxy frontend:3000" in caddyfile
    assert "trusted_proxies" not in caddyfile
    assert "header_up X-Forwarded-For" not in caddyfile


def test_compose_separates_meilisearch_reader_and_writer_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scoped_search_key = "compose-scoped-search-key"
    master_key_sentinel = "compose-master-key-sentinel"
    monkeypatch.setenv("MEILI_SEARCH_KEY", scoped_search_key)
    monkeypatch.setenv("MEILI_MASTER_KEY", master_key_sentinel)
    compose_services = _compose_services("docker-compose.yml", profiles=("batch-tools",))

    for reader_service_name in ("api", "semantic"):
        reader_service = compose_services[reader_service_name]
        reader_environment = reader_service["environment"]
        assert reader_environment["MEILI_SEARCH_KEY"] == scoped_search_key
        assert "MEILI_MASTER_KEY" not in reader_environment
        assert all(volume.get("type") != "bind" for volume in reader_service["volumes"])

    for reader_service_name in ("api", "semantic"):
        assert compose_services[reader_service_name]["environment"]["APP_ENV"] == "production"
    assert compose_services["meilisearch"]["environment"]["MEILI_ENV"] == "production"
    for writer_service_name in ("pipeline", "pipeline-batch", "worker", "enrichment-worker"):
        writer_environment = compose_services[writer_service_name]["environment"]
        assert writer_environment["MEILI_HOST"] == "http://meilisearch:7700"
        assert writer_environment["MEILI_MASTER_KEY"] == master_key_sentinel


def test_base_compose_requires_meilisearch_master_key() -> None:
    compose_environment = os.environ.copy()
    compose_environment.pop("MEILI_MASTER_KEY", None)
    compose_environment.pop("COMPOSE_ENV_FILES", None)
    completed_process = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            "/dev/null",
            "-f",
            "docker-compose.yml",
            "config",
            "--quiet",
        ],
        check=False,
        capture_output=True,
        env=compose_environment,
        text=True,
    )

    assert completed_process.returncode != 0
    assert "MEILI_MASTER_KEY must be set" in completed_process.stderr


def test_redis_service_exposes_configured_password_to_container_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    redis_password_sentinel = "compose redis; password with spaces"
    monkeypatch.setenv("REDIS_PASSWORD", redis_password_sentinel)

    redis_service = _compose_services("docker-compose.yml")["redis"]
    redis_command = " ".join(redis_service["command"])
    redis_healthcheck = " ".join(redis_service["healthcheck"]["test"])

    assert redis_service["environment"]["REDIS_PASSWORD"] == redis_password_sentinel
    assert redis_password_sentinel not in redis_command
    assert redis_password_sentinel not in redis_healthcheck
    assert '"$$REDIS_PASSWORD"' in redis_command
    assert '"$$REDIS_PASSWORD"' in redis_healthcheck


def test_dev_overlay_mounts_reader_source_without_repository_secrets() -> None:
    development_services = _compose_services("docker-compose.yml", "docker-compose.dev.yml")
    expected_targets = {
        "api": {"/app/api", "/app/pipeline"},
        "semantic": {"/app/pipeline", "/app/semantic_service"},
    }

    for reader_service_name in ("api", "semantic"):
        reader_volumes = development_services[reader_service_name]["volumes"]
        bind_targets = {
            volume["target"]
            for volume in reader_volumes
            if volume.get("type") == "bind"
        }
        assert bind_targets == expected_targets[reader_service_name]
        assert "/app" not in bind_targets
        assert development_services[reader_service_name]["environment"]["APP_ENV"] == "dev"
    assert development_services["meilisearch"]["environment"]["MEILI_ENV"] == "development"


def test_dev_overlay_allows_soak_recovery_to_disable_startup_purge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STARTUP_PURGE_DERIVED", "false")
    development_services = _compose_services("docker-compose.yml", "docker-compose.dev.yml")

    for service_name in ("api", "worker", "pipeline"):
        assert development_services[service_name]["environment"]["STARTUP_PURGE_DERIVED"] == "false"


def test_dev_overlay_reader_key_tracks_customized_local_master(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    customized_local_master_key = "customized-local-meilisearch-master-key"
    monkeypatch.delenv("MEILI_SEARCH_KEY", raising=False)
    monkeypatch.setenv("MEILI_MASTER_KEY", customized_local_master_key)
    development_services = _compose_services("docker-compose.yml", "docker-compose.dev.yml")

    for reader_service_name in ("api", "semantic"):
        reader_environment = development_services[reader_service_name]["environment"]
        assert reader_environment["MEILI_SEARCH_KEY"] == customized_local_master_key
        assert "MEILI_MASTER_KEY" not in reader_environment

    explicit_search_key = "explicit-local-reader-key"
    monkeypatch.setenv("MEILI_SEARCH_KEY", explicit_search_key)
    explicit_search_services = _compose_services("docker-compose.yml", "docker-compose.dev.yml")
    for reader_service_name in ("api", "semantic"):
        assert (
            explicit_search_services[reader_service_name]["environment"]["MEILI_SEARCH_KEY"]
            == explicit_search_key
        )


def test_docker_build_context_excludes_local_environment_files() -> None:
    dockerignore = Path(".dockerignore").read_text(encoding="utf-8").splitlines()
    frontend_dockerignore = Path("frontend/.dockerignore").read_text(encoding="utf-8").splitlines()

    assert "**/.env" in dockerignore
    assert "**/.env.*" in dockerignore
    assert "!**/.env.example" in dockerignore
    assert "!.env" not in dockerignore
    assert "!.env.*" not in dockerignore
    assert ".env" in frontend_dockerignore
    assert ".env.*" in frontend_dockerignore


def test_dev_helper_requires_local_environment_file() -> None:
    dev_helper = Path("scripts/dev_up.sh").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")
    operations = Path("docs/OPERATIONS.md").read_text(encoding="utf-8")
    profile_readme = Path("env/profiles/README.md").read_text(encoding="utf-8")

    assert 'if [[ ! -f .env ]]' in dev_helper
    assert "Create it from .env.example" in dev_helper
    assert "COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.dev.yml)" in dev_helper
    assert "monitor frontend ingress)" in dev_helper
    assert dev_helper.count('"${COMPOSE[@]}"') == 5
    assert "bash ./scripts/dev_up.sh" in readme
    assert "bash ./scripts/dev_up.sh" in operations
    assert "worker api pipeline frontend ingress" in profile_readme


def test_example_grafana_credentials_are_labeled_local_only():
    example_environment = Path(".env.example").read_text(encoding="utf-8")

    assert "Grafana admin credentials (local development only)" in example_environment
    assert "unsafe for reachable deployments" in example_environment


def test_operator_docs_scope_dev_overlay_to_port_services():
    readme = Path("README.md").read_text(encoding="utf-8")
    operations = Path("docs/OPERATIONS.md").read_text(encoding="utf-8")
    access_command = (
        "docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d \\\n"
        "  postgres redis meilisearch prometheus grafana"
    )
    purge_warning = "Using the development overlay for the full stack also enables `STARTUP_PURGE_DERIVED=true`."
    upgrade_command = (
        "docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --force-recreate \\\n"
        "  postgres redis meilisearch prometheus grafana"
    )

    assert access_command in readme
    assert access_command in operations
    assert purge_warning in readme
    assert purge_warning in operations
    assert upgrade_command in operations


def test_dockerfile_defines_split_python_targets():
    source = Path("Dockerfile").read_text(encoding="utf-8")

    assert "FROM python-runtime-base AS python-crawler" in source
    assert "FROM python-runtime-base AS python-api" in source
    assert "FROM python-runtime-base AS python-semantic" in source
    assert "FROM python-runtime-base AS python-worker-live" in source
    assert "FROM python-runtime-base AS python-worker-batch" in source
    assert "COPY --from=venv-crawler /opt/venv /opt/venv" in source
    assert "COPY --from=venv-api /opt/venv /opt/venv" in source
    assert "COPY --from=venv-worker-live /opt/venv /opt/venv" in source
    assert "COPY --from=venv-worker-batch /opt/venv /opt/venv" in source
    assert "COPY --from=wheels-api /app/wheels /wheels" not in source
    assert "COPY --from=wheels-worker /app/wheels /wheels" not in source
    assert "PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu" in source
    assert "/app/docker/semantic-cpu-constraints.txt" in source


def test_active_python_manifests_use_shared_exact_constraints() -> None:
    constraint_directives = _requirement_directives(Path("constraints.txt"))
    expected_constraint_directives = {
        f"{package_name}=={package_version}"
        for package_name, package_version in SHARED_EXACT_CONSTRAINTS.items()
    }
    expected_constraint_directives.add("pip-audit==2.10.1")

    assert len(constraint_directives) == len(set(constraint_directives))
    assert set(constraint_directives) == expected_constraint_directives

    for requirements_path in ACTIVE_REQUIREMENT_PATHS:
        requirement_directives = _requirement_directives(requirements_path)
        assert requirement_directives[0] == "-c ../constraints.txt"
        for requirement_directive in requirement_directives:
            requirement_name = _normalized_requirement_name(requirement_directive)
            if requirement_name in SHARED_EXACT_CONSTRAINTS:
                assert requirement_directive == requirement_name


def test_dependency_audit_and_pgvector_constraints_remain_explicit() -> None:
    development_directives = _requirement_directives(
        Path("pipeline/requirements-dev.txt")
    )
    constraint_directives = _requirement_directives(Path("constraints.txt"))

    assert "pip-audit" in development_directives
    assert "scikit-learn==1.8.0" in development_directives
    assert "pip-audit==2.10.1" in constraint_directives
    for requirements_path in (
        Path("api/requirements.txt"),
        Path("pipeline/requirements.txt"),
        Path("semantic_service/requirements.txt"),
    ):
        assert "pgvector>=0.5.0" in _requirement_directives(requirements_path)


def test_semantic_cpu_constraint_preserves_auditable_upstream_version() -> None:
    semantic_directives = _requirement_directives(
        Path("semantic_service/requirements.txt")
    )
    cpu_constraint_directives = _requirement_directives(
        Path("docker/semantic-cpu-constraints.txt")
    )

    assert "torch==2.11.0" in semantic_directives
    assert "torch==2.11.0+cpu" in cpu_constraint_directives


def test_docker_preserves_requirement_paths_and_applies_constraints() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert "COPY constraints.txt ./constraints.txt" in dockerfile
    for requirements_path in ACTIVE_REQUIREMENT_PATHS:
        if requirements_path == Path("pipeline/requirements-dev.txt"):
            continue
        copy_contract = f"COPY {requirements_path} ./{requirements_path}"
        install_contract = f"-r /app/{requirements_path}"
        assert copy_contract in dockerfile
        assert install_contract in dockerfile
    assert (
        "COPY docker/semantic-cpu-constraints.txt "
        "./docker/semantic-cpu-constraints.txt"
    ) in dockerfile
    assert "-c /app/docker/semantic-cpu-constraints.txt" in dockerfile
    assert "rapidfuzz" not in dockerfile


def test_dev_up_migrates_before_starting_schema_consumers():
    source = Path("scripts/dev_up.sh").read_text(encoding="utf-8")
    prerequisite_command = (
        '"${COMPOSE[@]}" up -d --build "${MIGRATION_PREREQUISITES[@]}"'
    )
    migration_command = (
        '"${COMPOSE[@]}" run --rm --build --no-deps pipeline python db_migrate.py'
    )
    readiness_command = '"${COMPOSE[@]}" exec -T postgres pg_isready'
    consumer_command = '"${COMPOSE[@]}" up -d --build "${CORE_SERVICES[@]}"'

    assert "MIGRATION_PREREQUISITES=(postgres)" in source
    assert "POSTGRES_READY_ATTEMPTS=30" in source
    assert "POSTGRES_READY_DELAY_SECONDS=1" in source
    assert prerequisite_command in source
    assert readiness_command in source
    assert migration_command in source
    assert consumer_command in source
    assert "semantic" in source
    assert "semantic-worker" in source
    assert "enrichment-worker" in source
    assert "monitor" in source
    assert " nlp" not in source
    assert "bash ./scripts/bootstrap_local_models.sh" in source
    assert "python db_init.py" not in source
    assert source.index(prerequisite_command) < source.index(readiness_command)
    assert source.index(readiness_command) < source.index(migration_command)
    assert source.index(migration_command) < source.index(
        "bash ./scripts/bootstrap_local_models.sh"
    )
    assert source.index("bash ./scripts/bootstrap_local_models.sh") < source.index(
        consumer_command
    )


def test_migration_runbook_uses_container_absolute_parity_script():
    operations = Path("docs/OPERATIONS.md").read_text(encoding="utf-8")

    assert "pipeline python /app/scripts/check_schema_parity.py" in operations
    assert "pipeline python scripts/check_schema_parity.py" not in operations


def test_compose_maps_worker_family_to_live_and_batch_images():
    source = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "worker:\n    build:\n      context: .\n      target: python-worker-live" in source
    assert "pipeline:\n    build:\n      context: .\n      target: python-worker-live" in source
    assert "pipeline-batch:\n    build:\n      context: .\n      target: python-worker-batch" in source
    assert "pipeline-batch:\n    build:\n      context: .\n      target: python-worker-batch\n    image: town-council-python-worker-batch" in source
    assert "extractor:\n    image: town-council-python-worker-live" in source
    assert "enrichment-worker:\n    image: town-council-python-worker-batch" in source
    assert "nlp:\n    image: town-council-python-worker-batch" in source
    assert "tables:\n    image: town-council-python-worker-batch" in source
    assert "topics:\n    image: town-council-python-worker-batch" in source
    assert "monitor:\n    image: town-council-python-worker-live" in source
    assert 'profiles: ["batch-tools"]' in source


def test_worker_runtime_requirements_exclude_development_tooling():
    runtime = Path("pipeline/requirements.txt").read_text(encoding="utf-8")
    dev = Path("pipeline/requirements-dev.txt").read_text(encoding="utf-8")
    pytest_configuration = Path("pytest.ini").read_text(encoding="utf-8")
    runtime_requirement_names = _requirement_names(
        Path("pipeline/requirements.txt")
    )

    for package in (
        "pytest==9.1.1",
        "pytest-mock==3.12.0",
        "pytest-benchmark==5.1.0",
        "locust==2.33.0",
    ):
        assert package not in runtime
        assert package in dev
    assert "pyyaml" not in runtime_requirement_names
    assert "PyYAML==6.0.3" in dev
    assert "PytestRemovedIn9Warning" not in pytest_configuration


def test_coverage_tooling_is_development_only():
    development_requirements = Path("pipeline/requirements-dev.txt").read_text(encoding="utf-8")

    for runtime_requirement_path in RUNTIME_REQUIREMENT_PATHS:
        runtime_requirements = runtime_requirement_path.read_text(encoding="utf-8")
        runtime_requirement_names = _requirement_names(runtime_requirement_path)
        runtime_requirement_directives = [
            requirement_line.partition("#")[0].strip()
            for requirement_line in runtime_requirements.splitlines()
        ]
        assert "coverage" not in runtime_requirement_names
        assert "pytest-cov" not in runtime_requirement_names
        assert not any(
            requirement_directive.startswith(("-r", "--requirement"))
            and "requirements-dev.txt" in requirement_directive
            for requirement_directive in runtime_requirement_directives
        )

    assert "coverage==7.13.3" in development_requirements
    assert "pytest-cov==7.1.0" in development_requirements


def test_semantic_dependencies_live_outside_worker_runtime():
    runtime = Path("pipeline/requirements.txt").read_text(encoding="utf-8")
    semantic = Path("semantic_service/requirements.txt").read_text(encoding="utf-8")

    for package in ("sentence-transformers==3.3.0", "faiss-cpu==1.10.0"):
        assert package not in runtime
        assert package in semantic


def test_worker_live_and_batch_requirements_split_table_stack_only():
    core = Path("pipeline/requirements.txt").read_text(encoding="utf-8")
    batch = Path("pipeline/requirements-batch.txt").read_text(encoding="utf-8")

    for package in ("camelot-py==0.11.0", "opencv-python-headless==4.9.0.80", "ghostscript==0.8.1"):
        assert package not in core
        assert package in batch

    for package in ("spacy==3.7.4", "pytextrank==3.3.0", "scikit-learn==1.5.0"):
        assert package not in core
        assert package in batch


def test_batch_pdf_parser_uses_patched_pypdf():
    batch_requirements_path = Path("pipeline/requirements-batch.txt")
    pypdf_requirement_paths = [
        requirements_path
        for requirements_path in RUNTIME_REQUIREMENT_PATHS
        if "pypdf" in _requirement_names(requirements_path)
    ]
    batch_pypdf_requirements = [
        requirement_line.partition("#")[0].strip()
        for requirement_line in batch_requirements_path.read_text(
            encoding="utf-8"
        ).splitlines()
        if _normalized_requirement_name(requirement_line) == "pypdf"
    ]

    assert pypdf_requirement_paths == [batch_requirements_path]
    assert batch_pypdf_requirements == ["pypdf==6.14.2"]


def test_bootstrap_and_runbook_use_semantic_image_for_semantic_artifacts():
    bootstrap = Path("scripts/bootstrap_local_models.sh").read_text(encoding="utf-8")
    ops = Path("docs/OPERATIONS.md").read_text(encoding="utf-8")

    assert "COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.dev.yml)" in bootstrap
    assert bootstrap.count('"${COMPOSE[@]}"') == 4
    assert (
        '"${COMPOSE[@]}" run --rm semantic python -c '
        '"from sentence_transformers import SentenceTransformer; '
        "SentenceTransformer('all-MiniLM-L6-v2')\""
    ) in bootstrap
    assert "\ndocker compose " not in bootstrap
    assert "docker compose run --rm semantic python ../pipeline/reindex_semantic.py" in ops


def test_semantic_worker_healthcheck_and_storage_report_are_wired_in():
    source = Path("docker-compose.yml").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")
    ops = Path("docs/OPERATIONS.md").read_text(encoding="utf-8")

    assert "python scripts/semantic_worker_healthcheck.py || exit 1" in source
    assert "python scripts/enrichment_worker_healthcheck.py || exit 1" in source
    assert "bash ./scripts/check_compose_profiles.sh" in readme
    assert "bash ./scripts/check_compose_profiles.sh" in ops
    assert "bash ./scripts/docker_storage_report.sh" in readme
    assert "bash ./scripts/docker_storage_report.sh" in ops
    assert "docker compose run --rm nlp" in readme
    assert "docker compose run --rm tables" in readme
    assert "docker compose run --rm topics" in ops


def test_old_batch_requirements_file_is_not_referenced():
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert not Path("pipeline/requirements-nlp.txt").exists()
    assert "requirements-nlp.txt" not in dockerfile
    assert "requirements-nlp.txt" not in compose
