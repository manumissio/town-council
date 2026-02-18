from pipeline.llm import LocalAI
from pipeline.llm_provider import ProviderResponseError, ProviderTimeoutError


class _ResponseErrorProvider:
    def summarize_agenda_items(self, prompt, *, temperature, max_tokens):
        _ = (prompt, temperature, max_tokens)
        raise ProviderResponseError("bad payload")


class _TimeoutProvider:
    def summarize_agenda_items(self, prompt, *, temperature, max_tokens):
        _ = (prompt, temperature, max_tokens)
        raise ProviderTimeoutError("timeout")


def _sample_items():
    return [
        {
            "title": "Approve Contract Amendment",
            "description": "Authorize contract extension for public works project.",
            "classification": "Agenda Item",
            "result": "",
            "page_number": 3,
        }
    ]


def test_response_error_uses_deterministic_fallback(monkeypatch):
    ai = LocalAI()
    monkeypatch.setattr(ai, "_get_provider", lambda: _ResponseErrorProvider())
    out = ai.summarize_agenda_items("Meeting", "2026-01-01", _sample_items(), truncation_meta={})
    assert isinstance(out, str)
    assert out.startswith("BLUF:")


def test_timeout_error_returns_none_for_retry(monkeypatch):
    ai = LocalAI()
    monkeypatch.setattr(ai, "_get_provider", lambda: _TimeoutProvider())
    out = ai.summarize_agenda_items("Meeting", "2026-01-01", _sample_items(), truncation_meta={})
    assert out is None
