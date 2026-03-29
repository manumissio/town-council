from pathlib import Path


def test_compose_uses_role_specific_python_images_and_model_volume():
    source = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "image: town-council-python-crawler" in source
    assert "image: town-council-python-api" in source
    assert "image: town-council-python-worker" in source
    assert "models_data:/models" in source


def test_dockerfile_defines_split_python_targets():
    source = Path("Dockerfile").read_text(encoding="utf-8")

    assert "FROM python-runtime-base AS python-crawler" in source
    assert "FROM python-runtime-base AS python-api" in source
    assert "FROM python-runtime-base AS python-worker" in source


def test_dev_up_bootstraps_models_before_db_init():
    source = Path("scripts/dev_up.sh").read_text(encoding="utf-8")

    assert 'docker compose up -d --build "${CORE_SERVICES[@]}"' in source
    assert "bash ./scripts/bootstrap_local_models.sh" in source
    assert source.index("bash ./scripts/bootstrap_local_models.sh") < source.index(
        "docker compose run --rm pipeline python db_init.py"
    )
