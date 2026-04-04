from pathlib import Path


def _read_profile(path: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def test_m1_conservative_profile_defaults():
    values = _read_profile("env/profiles/m1_conservative.env")
    assert values["LOCAL_AI_BACKEND"] == "http"
    assert values["LOCAL_AI_HTTP_MODEL"] == "gemma-3-270m-custom"
    assert values["LOCAL_AI_HTTP_PROFILE"] == "conservative"
    assert values["WORKER_CONCURRENCY"] == "3"
    assert values["WORKER_POOL"] == "prefork"
    assert values["OLLAMA_NUM_PARALLEL"] == "1"
    assert values["LOCAL_AI_HTTP_TIMEOUT_SECONDS"] == "300"
    assert values["LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS"] == "300"
    assert values["LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS"] == "180"
    assert values["LOCAL_AI_HTTP_TIMEOUT_TOPICS_SECONDS"] == "180"
    assert values["LOCAL_AI_HTTP_MAX_RETRIES"] == "0"


def test_m5_conservative_profile_defaults():
    values = _read_profile("env/profiles/m5_conservative.env")
    assert values["LOCAL_AI_BACKEND"] == "http"
    assert values["LOCAL_AI_HTTP_MODEL"] == "gemma-3-270m-custom"
    assert values["LOCAL_AI_HTTP_PROFILE"] == "conservative"
    assert values["WORKER_CONCURRENCY"] == "3"
    assert values["WORKER_POOL"] == "prefork"
    assert values["OLLAMA_NUM_PARALLEL"] == "1"
    assert values["LOCAL_AI_HTTP_TIMEOUT_SECONDS"] == "300"
    assert values["LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS"] == "300"
    assert values["LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS"] == "180"
    assert values["LOCAL_AI_HTTP_TIMEOUT_TOPICS_SECONDS"] == "180"
    assert values["LOCAL_AI_HTTP_MAX_RETRIES"] == "0"


def test_desktop_balanced_profile_defaults():
    values = _read_profile("env/profiles/desktop_balanced.env")
    assert values["LOCAL_AI_BACKEND"] == "http"
    assert values["LOCAL_AI_HTTP_MODEL"] == "gemma-3-270m-custom"
    assert values["LOCAL_AI_HTTP_PROFILE"] == "balanced"
    assert values["WORKER_CONCURRENCY"] == "3"
    assert values["WORKER_POOL"] == "prefork"
    assert values["OLLAMA_NUM_PARALLEL"] == "4"
    assert values["LOCAL_AI_HTTP_TIMEOUT_SECONDS"] == "90"
    assert values["LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS"] == "90"
    assert values["LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS"] == "90"
    assert values["LOCAL_AI_HTTP_TIMEOUT_TOPICS_SECONDS"] == "90"
    assert values["LOCAL_AI_HTTP_MAX_RETRIES"] == "1"


def test_gemma4_e2b_second_tier_profile_defaults():
    values = _read_profile("env/profiles/gemma4_e2b_second_tier.env")
    assert values["LOCAL_AI_BACKEND"] == "http"
    assert values["LOCAL_AI_HTTP_MODEL"] == "gemma4:e2b"
    assert values["LOCAL_AI_HTTP_PROFILE"] == "conservative"
    assert values["WORKER_CONCURRENCY"] == "3"
    assert values["WORKER_POOL"] == "prefork"
    assert values["OLLAMA_NUM_PARALLEL"] == "1"
    assert values["LOCAL_AI_HTTP_TIMEOUT_SECONDS"] == "300"
    assert values["LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS"] == "300"
    assert values["LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS"] == "180"
    assert values["LOCAL_AI_HTTP_TIMEOUT_TOPICS_SECONDS"] == "180"
    assert values["LOCAL_AI_HTTP_MAX_RETRIES"] == "0"
    assert values["INFERENCE_MEM_LIMIT"] == "10G"


def test_gemma4_e2b_host_metal_strict_profile_defaults():
    values = _read_profile("env/profiles/gemma4_e2b_host_metal_strict.env")
    assert values["LOCAL_AI_BACKEND"] == "http"
    assert values["LOCAL_AI_HTTP_BASE_URL"] == "http://host.docker.internal:11434"
    assert values["HOST_OLLAMA_BASE_URL"] == "http://localhost:11434"
    assert values["LOCAL_AI_HTTP_MODEL"] == "gemma4:e2b"
    assert values["LOCAL_AI_HTTP_PROFILE"] == "conservative"
    assert values["WORKER_CONCURRENCY"] == "3"
    assert values["WORKER_POOL"] == "prefork"
    assert values["OLLAMA_NUM_PARALLEL"] == "1"
    assert values["LOCAL_AI_HTTP_TIMEOUT_SECONDS"] == "300"
    assert values["LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS"] == "300"
    assert values["LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS"] == "180"
    assert values["LOCAL_AI_HTTP_TIMEOUT_TOPICS_SECONDS"] == "180"
    assert values["LOCAL_AI_HTTP_MAX_RETRIES"] == "0"


def test_gemma3_270m_host_metal_conservative_profile_defaults():
    values = _read_profile("env/profiles/gemma3_270m_host_metal_conservative.env")
    assert values["LOCAL_AI_BACKEND"] == "http"
    assert values["LOCAL_AI_HTTP_BASE_URL"] == "http://host.docker.internal:11434"
    assert values["HOST_OLLAMA_BASE_URL"] == "http://localhost:11434"
    assert values["LOCAL_AI_HTTP_MODEL"] == "gemma-3-270m-custom"
    assert values["LOCAL_AI_HTTP_PROFILE"] == "conservative"
    assert values["WORKER_CONCURRENCY"] == "3"
    assert values["WORKER_POOL"] == "prefork"
    assert values["OLLAMA_NUM_PARALLEL"] == "1"
    assert values["LOCAL_AI_HTTP_TIMEOUT_SECONDS"] == "300"
    assert values["LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS"] == "300"
    assert values["LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS"] == "180"
    assert values["LOCAL_AI_HTTP_TIMEOUT_TOPICS_SECONDS"] == "180"
    assert values["LOCAL_AI_HTTP_MAX_RETRIES"] == "0"


def test_docker_compose_forwards_operation_specific_http_timeouts():
    text = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "LOCAL_AI_HTTP_PROFILE=${LOCAL_AI_HTTP_PROFILE:-conservative}" in text
    assert "LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS=${LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS:-60}" in text
    assert "LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS=${LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS:-60}" in text
    assert "LOCAL_AI_HTTP_TIMEOUT_TOPICS_SECONDS=${LOCAL_AI_HTTP_TIMEOUT_TOPICS_SECONDS:-60}" in text
