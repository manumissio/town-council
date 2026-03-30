from pathlib import Path


def test_compose_uses_role_specific_python_images_and_model_volume():
    source = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "image: town-council-python-crawler" in source
    assert "image: town-council-python-api" in source
    assert "image: town-council-python-semantic" in source
    assert "image: town-council-python-worker-core" in source
    assert "image: town-council-python-worker-nlp" in source
    assert "semantic-worker:" in source
    assert "models_data:/models" in source


def test_dockerfile_defines_split_python_targets():
    source = Path("Dockerfile").read_text(encoding="utf-8")

    assert "FROM python-runtime-base AS python-crawler" in source
    assert "FROM python-runtime-base AS python-api" in source
    assert "FROM python-runtime-base AS python-semantic" in source
    assert "FROM python-runtime-base AS python-worker-core" in source
    assert "FROM python-worker-core AS python-worker-nlp" in source
    assert "COPY --from=venv-crawler /opt/venv /opt/venv" in source
    assert "COPY --from=venv-api /opt/venv /opt/venv" in source
    assert "COPY --from=venv-worker-core /opt/venv /opt/venv" in source
    assert "COPY --from=venv-worker-nlp /opt/venv /opt/venv" in source
    assert "COPY --from=wheels-api /app/wheels /wheels" not in source
    assert "COPY --from=wheels-worker /app/wheels /wheels" not in source
    assert "PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu" in source
    assert "semantic_cpu_constraints.txt" in source


def test_dev_up_bootstraps_models_before_db_init():
    source = Path("scripts/dev_up.sh").read_text(encoding="utf-8")

    assert 'docker compose up -d --build "${CORE_SERVICES[@]}"' in source
    assert "semantic" in source
    assert "semantic-worker" in source
    assert "bash ./scripts/bootstrap_local_models.sh" in source
    assert source.index("bash ./scripts/bootstrap_local_models.sh") < source.index(
        "docker compose run --rm pipeline python db_init.py"
    )


def test_compose_maps_worker_family_to_core_and_nlp_images():
    source = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "worker:\n    build:\n      context: .\n      target: python-worker-core" in source
    assert "nlp:\n    build:\n      context: .\n      target: python-worker-nlp" in source
    assert "pipeline:\n    image: town-council-python-worker-nlp" in source
    assert "extractor:\n    image: town-council-python-worker-core" in source
    assert "tables:\n    image: town-council-python-worker-nlp" in source
    assert "topics:\n    image: town-council-python-worker-nlp" in source
    assert "monitor:\n    image: town-council-python-worker-core" in source


def test_worker_runtime_requirements_exclude_dev_benchmark_tooling():
    runtime = Path("pipeline/requirements.txt").read_text(encoding="utf-8")
    dev = Path("pipeline/requirements-dev.txt").read_text(encoding="utf-8")

    for package in ("pytest==8.3.4", "pytest-mock==3.12.0", "pytest-benchmark==5.1.0", "locust==2.33.0"):
        assert package not in runtime
        assert package in dev


def test_semantic_dependencies_live_outside_worker_runtime():
    runtime = Path("pipeline/requirements.txt").read_text(encoding="utf-8")
    semantic = Path("semantic_service/requirements.txt").read_text(encoding="utf-8")

    for package in ("sentence-transformers==3.3.0", "faiss-cpu==1.10.0"):
        assert package not in runtime
        assert package in semantic


def test_worker_core_and_nlp_requirements_split_table_stack_only():
    core = Path("pipeline/requirements.txt").read_text(encoding="utf-8")
    nlp = Path("pipeline/requirements-nlp.txt").read_text(encoding="utf-8")

    for package in ("camelot-py==0.11.0", "opencv-python-headless==4.9.0.80", "ghostscript==0.8.1"):
        assert package not in core
        assert package in nlp

    for package in ("spacy==3.7.4", "pytextrank==3.3.0", "scikit-learn==1.5.0"):
        assert package in core


def test_bootstrap_and_runbook_use_semantic_image_for_semantic_artifacts():
    bootstrap = Path("scripts/bootstrap_local_models.sh").read_text(encoding="utf-8")
    ops = Path("docs/OPERATIONS.md").read_text(encoding="utf-8")

    assert 'docker compose run --rm semantic python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer(\'all-MiniLM-L6-v2\')"' in bootstrap
    assert "docker compose run --rm semantic python ../pipeline/reindex_semantic.py" in ops


def test_semantic_worker_healthcheck_and_storage_report_are_wired_in():
    source = Path("docker-compose.yml").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")
    ops = Path("docs/OPERATIONS.md").read_text(encoding="utf-8")

    assert "python scripts/semantic_worker_healthcheck.py || exit 1" in source
    assert "bash ./scripts/docker_storage_report.sh" in readme
    assert "bash ./scripts/docker_storage_report.sh" in ops
