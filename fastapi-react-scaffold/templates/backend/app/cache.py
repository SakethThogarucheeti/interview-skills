# Cache-aside helper backed by Redis (see hld-interview-design's caching talking
# points). Thin wrapper so services never import redis directly -- same
# Dependency Inversion habit as the repository.

import json
from typing import Callable, TypeVar
import redis

T = TypeVar("T")


class Cache:
    def __init__(self, client: redis.Redis, default_ttl: int = 60) -> None:
        self._client = client
        self._default_ttl = default_ttl

    def get_or_set(self, key: str, loader: Callable[[], T], ttl: int | None = None) -> T:
        """Cache-aside: check cache -> miss -> call loader -> populate -> return.
        loader must return a JSON-serializable value (e.g. a dict from
        `item.model_dump(mode="json")`), since Redis stores strings/bytes."""
        cached = self._client.get(key)
        if cached is not None:
            return json.loads(cached)
        value = loader()
        self._client.set(key, json.dumps(value), ex=ttl or self._default_ttl)
        return value

    def invalidate(self, key: str) -> None:
        """Call on write (update/delete) so the cache never serves stale data
        past a single TTL window -- write-through invalidation, not just TTL."""
        self._client.delete(key)
