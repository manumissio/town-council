from __future__ import annotations

import subprocess
import time
from typing import Callable


WORKER_METRICS_SCRAPE_ATTEMPTS = 2
WORKER_METRICS_BACKOFF_SECONDS = 0.5

WORKER_HTTP_METRICS_PROBE = (
    "import urllib.request; "
    "print(urllib.request.urlopen('http://localhost:8001/metrics', timeout=10)"
    ".read().decode('utf-8', errors='replace'))"
)
WORKER_REGISTRY_METRICS_PROBE = (
    "from prometheus_client import CollectorRegistry, generate_latest; "
    "from pipeline.metrics import RedisProviderMetricsCollector; "
    "registry = CollectorRegistry(); "
    "registry.register(RedisProviderMetricsCollector()); "
    "print(generate_latest(registry).decode('utf-8', errors='replace'))"
)


def docker_exec_python(script: str) -> str:
    cmd = [
        "docker",
        "compose",
        "exec",
        "-T",
        "worker",
        "python",
        "-c",
        script,
    ]
    return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT, timeout=30)


def fetch_worker_metrics_via_docker(
    exec_python: Callable[[str], str] | None = None,
) -> tuple[str, str | None]:
    run_probe = exec_python or docker_exec_python
    strategies = [
        ("worker_http", WORKER_HTTP_METRICS_PROBE),
        ("worker_registry", WORKER_REGISTRY_METRICS_PROBE),
    ]
    errors: list[str] = []
    for strategy_name, script in strategies:
        for attempt in range(1, WORKER_METRICS_SCRAPE_ATTEMPTS + 1):
            try:
                raw = run_probe(script)
                if raw.strip():
                    if strategy_name == "worker_http" and not _has_provider_series(raw):
                        errors.append(f"{strategy_name}[attempt={attempt}] missing_provider_series")
                        continue
                    return raw, None
                errors.append(f"{strategy_name}[attempt={attempt}] empty_output")
            except (subprocess.SubprocessError, OSError, TimeoutError) as exc:
                errors.append(f"{strategy_name}[attempt={attempt}] {exc}")
            if attempt < WORKER_METRICS_SCRAPE_ATTEMPTS:
                time.sleep(WORKER_METRICS_BACKOFF_SECONDS)
    joined = "; ".join(errors).strip()
    return "", joined or "worker metrics scrape failed"


def _has_provider_series(raw: str) -> bool:
    return any(line.startswith("tc_provider_") and not line.startswith("#") for line in raw.splitlines())
