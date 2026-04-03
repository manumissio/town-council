import importlib.util
import json
from pathlib import Path


spec = importlib.util.spec_from_file_location("probe_local_model_candidate", Path("scripts/probe_local_model_candidate.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_probe_candidate_passes_for_ready_response(monkeypatch):
    monkeypatch.setattr(mod, "_list_models", lambda base_url, timeout_seconds: ["gemma4:e2b"])
    monkeypatch.setattr(
        mod.requests,
        "post",
        lambda *args, **kwargs: _FakeResponse({"response": "READY"}),
    )

    out = mod.probe_candidate(
        base_url="http://localhost:11434",
        model="gemma4:e2b",
        prompt="Reply with exactly READY.",
        timeout_seconds=5,
        max_tokens=8,
    )

    assert out["status"] == "pass"
    assert out["reason"] == "probe_passed"


def test_probe_candidate_rejects_reasoning_tags(monkeypatch):
    monkeypatch.setattr(mod, "_list_models", lambda base_url, timeout_seconds: ["gemma4:e2b"])
    monkeypatch.setattr(
        mod.requests,
        "post",
        lambda *args, **kwargs: _FakeResponse({"response": "<think>hidden</think>\nREADY"}),
    )

    out = mod.probe_candidate(
        base_url="http://localhost:11434",
        model="gemma4:e2b",
        prompt="Reply with exactly READY.",
        timeout_seconds=5,
        max_tokens=8,
    )

    assert out["status"] == "fail"
    assert out["reason"] == "reasoning_tag_detected"


def test_main_uses_candidate_order_and_writes_artifact(monkeypatch, tmp_path: Path):
    attempts = []

    def _fake_probe(**kwargs):
        attempts.append(kwargs["model"])
        return {
            "candidate": kwargs["model"],
            "status": "pass" if kwargs["model"] == "gemma4:e2b" else "fail",
            "reason": "probe_passed" if kwargs["model"] == "gemma4:e2b" else "model_missing",
            "available": kwargs["model"] == "gemma4:e2b",
            "response_preview": "READY" if kwargs["model"] == "gemma4:e2b" else None,
        }

    monkeypatch.setattr(mod, "probe_candidate", _fake_probe)
    monkeypatch.setattr(mod, "_docker_memory_limit_bytes", lambda: 8321716224)

    exit_code = mod.main(
        [
            "--output-dir",
            str(tmp_path),
            "--run-id",
            "probe_run",
            "--candidate",
            "gemma4:e2b",
            "--candidate",
            "gemma4:e4b",
        ]
    )

    payload = json.loads((tmp_path / "probe_run" / "probe_result.json").read_text(encoding="utf-8"))
    assert exit_code == 0
    assert attempts == ["gemma4:e2b", "gemma4:e4b"]
    assert payload["selected_candidate"] == "gemma4:e2b"
