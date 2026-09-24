# Structured JSON logs, a request ID on every log line and response, and
# Prometheus metrics at /metrics. Metrics are per-process: with
# WEB_CONCURRENCY > 1 each worker reports its own (say so if asked).

import json
import logging
import time
import uuid
from contextvars import ContextVar

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "route", "status"])
LATENCY = Histogram("http_request_duration_seconds", "HTTP request latency", ["method", "route"])
INGESTED = Counter("ingest_records_total", "Ingested records by outcome", ["outcome"])
SECURITY_REJECTIONS = Counter("security_rejections_total", "Requests refused by auth/rate limit", ["reason"])
BUILD_INFO = Gauge("app_build_info", "Running build; value is always 1", ["git_sha"])

_STD_ATTRS = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}
_QUIET_PATHS = ("/health", "/ready", "/metrics")


class JsonFormatter(logging.Formatter):
    def __init__(self, git_sha: str) -> None:
        super().__init__()
        self._git_sha = git_sha[:12]  # which build wrote this line -- two coexist mid-rollout

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_var.get(),
            "version": self._git_sha,
        }
        # Anything passed as logger.info(..., extra={...}) becomes a JSON field.
        payload.update({k: v for k, v in record.__dict__.items() if k not in _STD_ATTRS})
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str, git_sha: str = "dev") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(git_sha))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)


def install_observability(app: FastAPI, git_sha: str) -> None:
    log = logging.getLogger("app.http")
    BUILD_INFO.labels(git_sha).set(1)

    @app.middleware("http")
    async def observe(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        request_id_var.set(rid)  # not reset: the 500 handler runs after this returns
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["x-request-id"] = rid
            response.headers["x-app-version"] = git_sha  # which build answered -- useful mid-rollout
            return response
        finally:
            elapsed = time.perf_counter() - start
            route = getattr(request.scope.get("route"), "path", "unmatched")  # template, not raw path
            REQUESTS.labels(request.method, route, status).inc()
            LATENCY.labels(request.method, route).observe(elapsed)
            if not request.url.path.startswith(_QUIET_PATHS) or status >= 500:
                log.info(
                    "request",
                    extra={
                        "method": request.method,
                        "route": route,
                        "status": status,
                        "duration_ms": round(elapsed * 1000, 1),
                    },
                )

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
