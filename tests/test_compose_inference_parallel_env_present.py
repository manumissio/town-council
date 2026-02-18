from pathlib import Path


def test_inference_service_wires_ollama_parallelism_env():
    text = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "inference:" in text
    assert "OLLAMA_NUM_PARALLEL=${OLLAMA_NUM_PARALLEL:-1}" in text
