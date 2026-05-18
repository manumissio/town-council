import csv
from pathlib import Path


ACTIVE_PROFILE_DIR = Path("env/profiles")
ARCHIVED_PROFILE_DIR = Path("archive/env/profiles")
PROFILE_MANIFEST = ACTIVE_PROFILE_DIR / "profile_manifest.csv"
REQUIRED_PROFILE_KEYS = {
    "LOCAL_AI_BACKEND",
    "LOCAL_AI_HTTP_API",
    "LOCAL_AI_HTTP_MODEL",
    "LOCAL_AI_HTTP_PROFILE",
    "WORKER_CONCURRENCY",
    "WORKER_POOL",
}
VALID_PROFILE_STATUSES = {"preferred", "baseline", "diagnostic", "historical"}
EXPECTED_ACTIVE_PROFILES = {
    "env/profiles/m5_mlx_conservative.env",
    "env/profiles/m5_mlx_balanced.env",
    "env/profiles/m5_conservative.env",
    "env/profiles/desktop_balanced.env",
    "env/profiles/gemma4_e2b_second_tier.env",
}
ARCHIVED_PROFILE_NAMES = {
    "m1_conservative.env",
    "gemma3_270m_host_metal_conservative.env",
    "gemma4_e2b_host_metal_strict.env",
}


def _read_profile(path: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def _read_manifest() -> list[dict[str, str]]:
    with PROFILE_MANIFEST.open(encoding="utf-8", newline="") as manifest_file:
        return list(csv.DictReader(manifest_file))


def _manifest_by_path() -> dict[str, dict[str, str]]:
    return {row["profile_path"]: row for row in _read_manifest()}


def test_profile_manifest_lists_active_profiles_only():
    manifest_paths = set(_manifest_by_path())
    active_profile_paths = {
        str(path)
        for path in ACTIVE_PROFILE_DIR.glob("*.env")
    }

    assert manifest_paths == EXPECTED_ACTIVE_PROFILES
    assert active_profile_paths == EXPECTED_ACTIVE_PROFILES


def test_profile_manifest_uses_known_statuses_and_models():
    manifest = _manifest_by_path()

    assert {row["status"] for row in manifest.values()} <= VALID_PROFILE_STATUSES
    assert manifest["env/profiles/m5_mlx_conservative.env"]["status"] == "preferred"
    assert manifest["env/profiles/m5_mlx_conservative.env"]["model"] == "mlx-community/gemma-3-text-4b-it-4bit"
    assert manifest["env/profiles/m5_conservative.env"]["status"] == "baseline"
    assert manifest["env/profiles/m5_conservative.env"]["model"] == "gemma-3-270m-custom"
    assert manifest["env/profiles/gemma4_e2b_second_tier.env"]["status"] == "diagnostic"
    assert manifest["env/profiles/gemma4_e2b_second_tier.env"]["model"] == "gemma4:e2b"


def test_active_profiles_have_required_runtime_keys():
    for profile_path in EXPECTED_ACTIVE_PROFILES:
        values = _read_profile(profile_path)
        assert REQUIRED_PROFILE_KEYS <= set(values)


def test_retired_profiles_live_only_in_archive():
    active_profile_names = {path.name for path in ACTIVE_PROFILE_DIR.glob("*.env")}
    archived_profile_names = {path.name for path in ARCHIVED_PROFILE_DIR.glob("*.env")}

    assert active_profile_names.isdisjoint(ARCHIVED_PROFILE_NAMES)
    assert ARCHIVED_PROFILE_NAMES <= archived_profile_names


def test_active_profiles_do_not_use_retired_models():
    retired_models = {"gemma3:1b", "mlx-community/gemma-3-270m-it-4bit"}

    for profile_path in EXPECTED_ACTIVE_PROFILES:
        values = _read_profile(profile_path)
        assert values["LOCAL_AI_HTTP_MODEL"] not in retired_models


def test_m5_conservative_profile_defaults():
    values = _read_profile("env/profiles/m5_conservative.env")
    assert values["LOCAL_AI_BACKEND"] == "http"
    assert values["LOCAL_AI_HTTP_API"] == "ollama"
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


def test_m5_mlx_conservative_profile_defaults():
    values = _read_profile("env/profiles/m5_mlx_conservative.env")
    assert values["LOCAL_AI_BACKEND"] == "http"
    assert values["LOCAL_AI_HTTP_API"] == "openai_compat"
    assert values["LOCAL_AI_HTTP_BASE_URL"] == "http://host.docker.internal:8080"
    assert values["HOST_MLX_BASE_URL"] == "http://localhost:8080"
    assert values["LOCAL_AI_HTTP_MODEL"] == "mlx-community/gemma-3-text-4b-it-4bit"
    assert values["LOCAL_AI_HTTP_PROFILE"] == "conservative"
    assert values["WORKER_CONCURRENCY"] == "2"
    assert values["WORKER_POOL"] == "prefork"
    assert values["LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS"] == "180"
    assert values["LOCAL_AI_HTTP_MAX_RETRIES"] == "0"
    assert values["LLM_CONTEXT_WINDOW"] == "8192"
    assert values["LLM_SUMMARY_MAX_TEXT"] == "12000"


def test_m5_mlx_balanced_profile_defaults():
    values = _read_profile("env/profiles/m5_mlx_balanced.env")
    assert values["LOCAL_AI_BACKEND"] == "http"
    assert values["LOCAL_AI_HTTP_API"] == "openai_compat"
    assert values["LOCAL_AI_HTTP_BASE_URL"] == "http://host.docker.internal:8080"
    assert values["HOST_MLX_BASE_URL"] == "http://localhost:8080"
    assert values["LOCAL_AI_HTTP_MODEL"] == "mlx-community/gemma-3-text-4b-it-4bit"
    assert values["LOCAL_AI_HTTP_PROFILE"] == "balanced"
    assert values["WORKER_CONCURRENCY"] == "4"
    assert values["WORKER_POOL"] == "prefork"
    assert values["LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS"] == "120"
    assert values["LOCAL_AI_HTTP_MAX_RETRIES"] == "1"
    assert values["LLM_CONTEXT_WINDOW"] == "8192"
    assert values["LLM_SUMMARY_MAX_TEXT"] == "12000"


def test_desktop_balanced_profile_defaults():
    values = _read_profile("env/profiles/desktop_balanced.env")
    assert values["LOCAL_AI_BACKEND"] == "http"
    assert values["LOCAL_AI_HTTP_API"] == "ollama"
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
    assert values["LOCAL_AI_HTTP_API"] == "ollama"
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


def test_docker_compose_forwards_operation_specific_http_timeouts():
    text = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "LOCAL_AI_HTTP_API=${LOCAL_AI_HTTP_API:-ollama}" in text
    assert "LOCAL_AI_HTTP_PROFILE=${LOCAL_AI_HTTP_PROFILE:-conservative}" in text
    assert "LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS=${LOCAL_AI_HTTP_TIMEOUT_SEGMENT_SECONDS:-60}" in text
    assert "LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS=${LOCAL_AI_HTTP_TIMEOUT_SUMMARY_SECONDS:-60}" in text
    assert "LOCAL_AI_HTTP_TIMEOUT_TOPICS_SECONDS=${LOCAL_AI_HTTP_TIMEOUT_TOPICS_SECONDS:-60}" in text
