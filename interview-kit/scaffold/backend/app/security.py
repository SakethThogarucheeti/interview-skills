# API-key auth + per-client rate limiting, as one middleware in front of every
# route except the ops endpoints (health checks, /version, /metrics, docs).
#
#   API_KEYS="alice:<key>,bob:<key>:600"  -> name:key[:requests_per_minute]
#   RATE_LIMIT_PER_MIN=120                -> default limit (the optional third field = a tier)
#
# Send `X-API-Key: <key>` or `Authorization: Bearer <key>`. No API_KEYS -> auth is
# off (dev/test), except APP_ENV=prod refuses to start: a missing secret must not
# silently publish an open API. Limits are keyed by client name (by IP when auth
# is off), counted in Redis so every instance shares one budget.

import hashlib
import logging
import math
import threading
import time
from dataclasses import dataclass
from typing import Protocol

import redis
from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from starlette.concurrency import run_in_threadpool

from app.errors import error_response
from app.observability import SECURITY_REJECTIONS

log = logging.getLogger(__name__)

OPEN_PATHS = {"/health", "/ready", "/version", "/metrics", "/docs", "/docs/oauth2-redirect", "/openapi.json", "/redoc"}
WINDOW_SECONDS = 60


@dataclass(frozen=True)
class Client:
    name: str
    limit: int  # requests per WINDOW_SECONDS


def parse_api_keys(raw: str, default_limit: int) -> dict[str, Client]:
    """ "alice:k1,bob:k2:600" -> {sha256(key): Client}. Only hashes are kept in
    memory, and a bad entry fails at startup, not on the first request."""
    clients: dict[str, Client] = {}
    for entry in filter(None, (e.strip() for e in raw.split(","))):
        parts = entry.split(":")
        if len(parts) not in (2, 3) or not all(parts):
            raise ValueError("API_KEYS entries must be name:key or name:key:limit_per_min")
        limit = int(parts[2]) if len(parts) == 3 else default_limit
        clients[_digest(parts[1])] = Client(parts[0], limit)
    return clients


def _digest(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


class RateLimiter(Protocol):
    def hit(self, client: str, limit: int) -> tuple[bool, int, int]:
        """Count one request. Returns (allowed, remaining, retry_after_seconds)."""
        ...


# Sliding-window counter: estimate = previous window's count x the fraction of it
# still inside the last 60s + the current window's count. O(1) memory per client,
# no fixed-window 2x burst at the boundary. The check and the increment are one
# atomic Lua call, so concurrent requests on any instance can't both slip under
# the limit (the check-then-act race).
_LUA = """
local cur = tonumber(redis.call('GET', KEYS[1]) or '0')
local prev = tonumber(redis.call('GET', KEYS[2]) or '0')
local used = math.floor(prev * tonumber(ARGV[2]) + cur)
if used >= tonumber(ARGV[1]) then return {0, used} end
redis.call('INCR', KEYS[1])
redis.call('EXPIRE', KEYS[1], ARGV[3])
return {1, used + 1}
"""


def _window(now: float) -> tuple[int, float, int]:
    """-> (window index, weight of the previous window, seconds until this one ends)"""
    idx, into = divmod(now, WINDOW_SECONDS)
    return int(idx), 1 - into / WINDOW_SECONDS, max(1, math.ceil(WINDOW_SECONDS - into))


class RedisRateLimiter:
    def __init__(self, client: redis.Redis, clock=time.time) -> None:
        self._script = client.register_script(_LUA)
        self._clock = clock

    def hit(self, client: str, limit: int) -> tuple[bool, int, int]:
        idx, weight, reset = _window(self._clock())
        try:
            allowed, used = self._script(
                keys=[f"rl:{client}:{idx}", f"rl:{client}:{idx - 1}"],
                args=[limit, f"{weight:.4f}", WINDOW_SECONDS * 2],
            )
        except redis.RedisError as exc:
            # Fail open: a Redis outage degrades protection, not availability
            # (same call as the cache). Fail closed instead if abuse costs more than downtime.
            log.warning("rate limiter unavailable, allowing request", extra={"error": str(exc)})
            return True, limit, 0
        return bool(allowed), max(0, limit - used), reset


class InMemoryRateLimiter:
    """Same algorithm, one process only: tests and Redis-less dev. With N
    instances each would allow N x the limit -- that's why prod uses Redis."""

    def __init__(self, clock=time.time) -> None:
        self._counts: dict[tuple[str, int], int] = {}
        self._lock = threading.Lock()
        self._clock = clock

    def hit(self, client: str, limit: int) -> tuple[bool, int, int]:
        idx, weight, reset = _window(self._clock())
        with self._lock:
            used = math.floor(self._counts.get((client, idx - 1), 0) * weight + self._counts.get((client, idx), 0))
            if used >= limit:
                return False, 0, reset
            self._counts[(client, idx)] = self._counts.get((client, idx), 0) + 1
            return True, max(0, limit - used - 1), reset


@dataclass
class Guard:
    keys: dict[str, Client]  # empty = auth off
    limiter: RateLimiter
    default_limit: int


def _presented_key(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.headers.get("x-api-key")


def _client_ip(request: Request) -> str:
    # App Platform puts the real client IP in do-connecting-ip. Absent when the
    # app is reached directly (local runs), so fall back to the socket peer.
    return request.headers.get("do-connecting-ip") or (request.client.host if request.client else "unknown")


def install_security(app: FastAPI, api_keys: str, default_limit: int, limiter: RateLimiter, app_env: str) -> None:
    keys = parse_api_keys(api_keys, default_limit)
    if not keys and app_env == "prod":
        raise RuntimeError("API_KEYS is empty in prod: refusing to start with an open API (see app/security.py)")
    if not keys:
        log.warning("API_KEYS not set: authentication is OFF (dev/test only)")
    app.state.guard = Guard(keys, limiter, default_limit)

    # Registered before install_observability, so it runs inside it: 401s/429s
    # still get a request ID, a log line and a metric.
    @app.middleware("http")
    async def guard(request: Request, call_next):
        if request.url.path in OPEN_PATHS or request.method == "OPTIONS":
            return await call_next(request)
        g: Guard = request.app.state.guard
        if g.keys:
            key = _presented_key(request)
            client = g.keys.get(_digest(key)) if key else None
            if client is None:
                SECURITY_REJECTIONS.labels("unauthorized").inc()
                log.warning("auth rejected", extra={"ip": _client_ip(request), "key_sent": bool(key)})
                resp = error_response(401, "unauthorized", "Missing or invalid API key (X-API-Key header)")
                resp.headers["WWW-Authenticate"] = "Bearer"
                return resp
            name, limit = client.name, client.limit
        else:
            name, limit = f"ip:{_client_ip(request)}", g.default_limit
        request.state.client = name
        # The limiter is sync Redis I/O: run it in the threadpool, never on the
        # event loop (the graded blocking-call trap -- one slow Redis would stall every request).
        allowed, remaining, reset = await run_in_threadpool(g.limiter.hit, name, limit)
        if not allowed:
            SECURITY_REJECTIONS.labels("rate_limited").inc()
            log.info("rate limited", extra={"client": name, "limit": limit})
            resp = error_response(429, "rate_limited", f"Rate limit exceeded: {limit} requests per minute")
            resp.headers.update({"Retry-After": str(reset), "X-RateLimit-Limit": str(limit)})
            resp.headers["X-RateLimit-Remaining"] = "0"
            return resp
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response

    def openapi():  # adds the "Authorize" button to /docs
        if not app.openapi_schema:
            schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
            schema.setdefault("components", {})["securitySchemes"] = {
                "ApiKey": {"type": "apiKey", "in": "header", "name": "X-API-Key"}
            }
            for path, ops in schema["paths"].items():
                if path not in OPEN_PATHS:
                    for op in ops.values():
                        op["security"] = [{"ApiKey": []}]
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = openapi
