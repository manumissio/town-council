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
    assert values["LOCAL_AI_HTTP_MAX_RETRIES"] == "1"


def test_desktop_balanced_profile_defaults():
    values = _read_profile("env/profiles/desktop_balanced.env")
    assert values["LOCAL_AI_BACKEND"] == "http"
    assert values["LOCAL_AI_HTTP_MODEL"] == "gemma-3-270m-custom"
    assert values["LOCAL_AI_HTTP_PROFILE"] == "balanced"
    assert values["WORKER_CONCURRENCY"] == "3"
    assert values["WORKER_POOL"] == "prefork"
    assert values["OLLAMA_NUM_PARALLEL"] == "4"
    assert values["LOCAL_AI_HTTP_TIMEOUT_SECONDS"] == "90"
    assert values["LOCAL_AI_HTTP_MAX_RETRIES"] == "1"
