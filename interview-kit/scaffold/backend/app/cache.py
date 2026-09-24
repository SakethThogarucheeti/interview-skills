# Cache-aside helper backed by Redis (section 3's caching talking points).
# Thin wrapper so services never import redis directly -- same Dependency
# Inversion habit as the repository. Redis is disposable by design: every
# Redis failure degrades to a cache miss (slower), never to a 500.

import json
import logging
from collections.abc import Callable
from typing import TypeVar

import redis

T = TypeVar("T")
log = logging.getLogger(__name__)


class Cache:
    def __init__(self, client: redis.Redis, default_ttl: int = 60) -> None:
        self._client = client
        self._default_ttl = default_ttl

    def get_or_set(self, key: str, loader: Callable[[], T], ttl: int | None = None) -> T:
        """Cache-aside: check cache -> miss -> call loader -> populate -> return.
        loader must return a JSON-serializable value (e.g. a dict from
        `item.model_dump(mode="json")`), since Redis stores strings/bytes."""
        try:
            cached = self._client.get(key)
        except redis.RedisError as exc:
            log.warning("cache read failed, bypassing", extra={"key": key, "error": str(exc)})
            return loader()
        if cached is not None:
            return json.loads(cached)
        value = loader()
        try:
            self._client.set(key, json.dumps(value), ex=ttl or self._default_ttl)
        except redis.RedisError as exc:
            log.warning("cache write failed", extra={"key": key, "error": str(exc)})
        return value

    def invalidate(self, key: str) -> None:
        """Call on write (update/delete) so the cache never serves stale data
        past a single TTL window -- write-through invalidation, not just TTL.
        If Redis is down the delete is lost; the TTL bounds that staleness."""
        try:
            self._client.delete(key)
        except redis.RedisError as exc:
            log.warning("cache invalidate failed", extra={"key": key, "error": str(exc)})

    def ping(self) -> bool:
        try:
            return bool(self._client.ping())
        except redis.RedisError:
            return False
