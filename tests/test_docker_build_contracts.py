from pathlib import Path


def test_compose_uses_shared_python_image_and_model_volume():
    source = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "image: town-council-python-base" in source
    assert "models_data:/models" in source


def test_dev_up_bootstraps_models_before_db_init():
    source = Path("scripts/dev_up.sh").read_text(encoding="utf-8")

    assert 'docker compose up -d --build "${CORE_SERVICES[@]}"' in source
    assert "bash ./scripts/bootstrap_local_models.sh" in source
    assert source.index("bash ./scripts/bootstrap_local_models.sh") < source.index(
        "docker compose run --rm pipeline python db_init.py"
    )
