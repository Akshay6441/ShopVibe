"""Prometheus metrics instrumentation.

Collects HTTP request counters + latency histograms via a Starlette middleware
and exposes them on ``/metrics`` in Prometheus text format.
"""
import time

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests processed",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

METRICS_PATH = "/metrics"


class MetricsMiddleware(BaseHTTPMiddleware):
    """Records a counter and a latency sample for every request."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        method = request.method
        path = request.url.path
        HTTP_REQUEST_DURATION.labels(method, path).observe(duration)
        HTTP_REQUESTS_TOTAL.labels(method, path, response.status_code).inc()
        return response


def metrics_response() -> Response:
    """Prometheus text exposition of all collected metrics."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
