from prometheus_client import (
    Counter, Histogram, Gauge,
    generate_latest, CONTENT_TYPE_LATEST
)
from fastapi import FastAPI, Request, Response
from fastapi.routing import APIRoute
from starlette.middleware.base import BaseHTTPMiddleware
import time

# ========== HTTP METRICS ==========
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP Requests",
    ["method", "endpoint", "status"]
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP Request Latency (seconds)",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10]  # buckets مناسبة للـ APIs
)

REQUEST_SIZE = Histogram(
    "http_request_size_bytes",
    "Size of HTTP Requests",
    ["method", "endpoint"],
    buckets=[100, 500, 1_000, 10_000, 100_000, 1_000_000]
)

RESPONSE_SIZE = Histogram(
    "http_response_size_bytes",
    "Size of HTTP Responses",
    ["method", "endpoint"],
    buckets=[100, 500, 1_000, 10_000, 100_000, 1_000_000]
)

IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests currently in progress",
    ["method", "endpoint"]
)

SPARSE_EMBEDDINGS_COUNT = Counter(
    "sparse_embeddings_generated_total",
    "Total sparse embeddings generated"
)

ERROR_COUNT = Counter(
    "http_errors_total",
    "Total HTTP Errors",
    ["method", "endpoint", "status"]
)

# ========== RAG-SPECIFIC METRICS ==========
DOCS_INDEXED = Counter(
    "documents_indexed_total",
    "Total documents indexed into the vector database"
)

EMBEDDINGS_COUNT = Counter(
    "embeddings_generated_total",
    "Total embeddings generated"
)

CHUNKS_PER_QUERY = Histogram(
    "retrieved_chunks_per_query",
    "Number of chunks retrieved per query",
    buckets=[1, 2, 5, 10, 20, 50, 100]
)

ANSWER_CONFIDENCE = Histogram(
    "answer_confidence_score",
    "Confidence score of answers",
    buckets=[0.1, 0.3, 0.5, 0.7, 0.9, 1.0]
)

# ========== HELPERS ==========
def get_route_name(request: Request) -> str:
    """
    Normalize endpoint path: /users/123 -> /users/{id}
    """
    for route in request.app.routes:
        if isinstance(route, APIRoute):
            match, _ = route.matches(request.scope)
            if match.value == "full":
                return route.path
    return request.url.path

# ========== MIDDLEWARE ==========
class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        endpoint = get_route_name(request)

        # in-progress
        IN_PROGRESS.labels(request.method, endpoint).inc()

        try:
            response = await call_next(request)
        finally:
            IN_PROGRESS.labels(request.method, endpoint).dec()

        # duration
        duration = time.perf_counter() - start_time
        REQUEST_LATENCY.labels(method=request.method, endpoint=endpoint).observe(duration)

        # count
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=endpoint,
            status=response.status_code
        ).inc()

        # errors
        if response.status_code >= 400:
            ERROR_COUNT.labels(
                method=request.method,
                endpoint=endpoint,
                status=response.status_code
            ).inc()

        # sizes
        req_size = int(request.headers.get("content-length", 0))
        REQUEST_SIZE.labels(method=request.method, endpoint=endpoint).observe(req_size)

        res_size = int(response.headers.get("content-length", 0) or 0)
        RESPONSE_SIZE.labels(method=request.method, endpoint=endpoint).observe(res_size)

        return response

# ========== SETUP ==========
def setup_metrics(app: FastAPI):
    """
    Setup Prometheus metrics middleware and endpoint
    """
    app.add_middleware(PrometheusMiddleware)

    @app.get("/TrhBVe_m5gg2002_E5VVqS", include_in_schema=False)
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
