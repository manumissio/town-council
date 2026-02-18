from pathlib import Path


def test_env_example_contains_profile_alignment_keys():
    text = Path(".env.example").read_text(encoding="utf-8")
    assert "LOCAL_AI_HTTP_MODEL=gemma-3-270m-custom" in text
    assert "LOCAL_AI_HTTP_PROFILE=conservative" in text
    assert "OLLAMA_NUM_PARALLEL=1" in text
    assert "LOCAL_AI_HTTP_TIMEOUT_SECONDS=60" in text
    assert "LOCAL_AI_HTTP_MAX_RETRIES=1" in text


def test_operations_mentions_profile_env_files():
    text = Path("docs/OPERATIONS.md").read_text(encoding="utf-8")
    assert "env/profiles/m1_conservative.env" in text
    assert "env/profiles/desktop_balanced.env" in text
