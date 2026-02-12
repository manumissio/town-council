from pathlib import Path


def test_api_main_does_not_log_api_key_material():
    api_main = Path("api/main.py").read_text(encoding="utf-8")

    forbidden_patterns = [
        "logger.warning(f\"Unauthorized API access attempt with key:",
        "masked_key",
        "x_api_key[:",
    ]

    for pattern in forbidden_patterns:
        assert pattern not in api_main
