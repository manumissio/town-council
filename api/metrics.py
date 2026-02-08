"""
Prometheus metrics for the FastAPI service.

Key decision:
We label requests by route template (e.g. "/segment/{catalog_id}") instead of
raw URLs (e.g. "/segment/401") to avoid high-cardinality metrics that can
overwhelm Prometheus and make dashboards unusable.
"""

from __future__ import annotations

import time
from typing import Optional

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.responses import Response


HTTP_REQUESTS_TOTAL = Counter(
    "tc_http_requests_total",
    "Total HTTP requests served by the API.",
    labelnames=("method", "path", "status"),
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "tc_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    labelnames=("method", "path"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

HTTP_REQUESTS_IN_FLIGHT = Gauge(
    "tc_http_requests_in_flight",
    "Number of requests currently being handled by the API.",
)


def _path_template_from_scope(scope) -> str:
    route = scope.get("route")
    if route is not None and getattr(route, "path", None):
        return str(route.path)
    # Fallback: still bounded enough for local dev, but less ideal than templates.
    return str(scope.get("path") or "/")


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def instrument_app(app) -> None:
    """
    Register the /metrics endpoint and record request count/latency.
    """

    @app.get("/metrics", include_in_schema=False)
    def _metrics_endpoint():
        return metrics_response()

    @app.middleware("http")
    async def _prometheus_middleware(request, call_next):
        # Avoid self-observation loops.
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        path_template = _path_template_from_scope(request.scope)

        start = time.perf_counter()
        HTTP_REQUESTS_IN_FLIGHT.inc()
        status = "500"
        try:
            response = await call_next(request)
            status = str(getattr(response, "status_code", 200))
            return response
        except Exception:
            # We record a 500 even if another middleware converts the exception
            # into an HTTP response. This keeps error-rate dashboards useful.
            status = "500"
            raise
        finally:
            elapsed = max(0.0, time.perf_counter() - start)
            HTTP_REQUESTS_TOTAL.labels(method=method, path=path_template, status=status).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path_template).observe(elapsed)
            HTTP_REQUESTS_IN_FLIGHT.dec()

