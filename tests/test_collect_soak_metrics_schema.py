import importlib.util
from pathlib import Path


spec = importlib.util.spec_from_file_location("collect_soak_metrics", Path("scripts/collect_soak_metrics.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_parse_metrics_reads_labeled_rows():
    raw = '\n'.join([
        'tc_provider_requests_total{provider="http",operation="summarize_text",model="m",outcome="ok"} 10',
        'tc_provider_timeouts_total{provider="http",operation="summarize_text",model="m"} 1',
    ])
    rows = mod._parse_metrics(raw)
    assert len(rows) == 2
    assert rows[0]["name"] == "tc_provider_requests_total"
    assert rows[0]["labels"]["provider"] == "http"


def test_hist_quantile_handles_missing_data():
    assert mod._hist_quantile([], "tc_provider_ttft_ms", {}, 0.95) is None

