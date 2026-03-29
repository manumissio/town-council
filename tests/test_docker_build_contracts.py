from pathlib import Path


def test_compose_uses_role_specific_python_images_and_model_volume():
    source = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "image: town-council-python-crawler" in source
    assert "image: town-council-python-api" in source
    assert "image: town-council-python-semantic" in source
    assert "image: town-council-python-worker" in source
    assert "models_data:/models" in source


def test_dockerfile_defines_split_python_targets():
    source = Path("Dockerfile").read_text(encoding="utf-8")

    assert "FROM python-runtime-base AS python-crawler" in source
    assert "FROM python-runtime-base AS python-api" in source
    assert "FROM python-runtime-base AS python-semantic" in source
    assert "FROM python-runtime-base AS python-worker" in source
    assert "COPY --from=venv-crawler /opt/venv /opt/venv" in source
    assert "COPY --from=venv-api /opt/venv /opt/venv" in source
    assert "COPY --from=venv-worker /opt/venv /opt/venv" in source
    assert "COPY --from=wheels-api /app/wheels /wheels" not in source
    assert "COPY --from=wheels-worker /app/wheels /wheels" not in source
    assert "PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu" in source
    assert "semantic_cpu_constraints.txt" in source


def test_dev_up_bootstraps_models_before_db_init():
    source = Path("scripts/dev_up.sh").read_text(encoding="utf-8")

    assert 'docker compose up -d --build "${CORE_SERVICES[@]}"' in source
    assert "semantic" in source
    assert "bash ./scripts/bootstrap_local_models.sh" in source
    assert source.index("bash ./scripts/bootstrap_local_models.sh") < source.index(
        "docker compose run --rm pipeline python db_init.py"
    )


def test_worker_runtime_requirements_exclude_dev_benchmark_tooling():
    runtime = Path("pipeline/requirements.txt").read_text(encoding="utf-8")
    dev = Path("pipeline/requirements-dev.txt").read_text(encoding="utf-8")

    for package in ("pytest==8.3.4", "pytest-mock==3.12.0", "pytest-benchmark==5.1.0", "locust==2.33.0"):
        assert package not in runtime
        assert package in dev
