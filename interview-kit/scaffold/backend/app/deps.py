# Wiring: picks concrete implementations. This module is the Factory in this
# app -- env-driven (config.py) so tests get InMemory with no cache, and the
# live demo gets Postgres + Redis, without touching services/routes.

from functools import lru_cache

import redis
from psycopg_pool import ConnectionPool

from app.cache import Cache
from app.config import get_settings
from app.ingest_repository import IngestRepository, PostgresIngestRepository
from app.ingest_service import IngestService
from app.repository import InMemoryItemRepository, ItemRepository, PostgresItemRepository
from app.security import InMemoryRateLimiter, RateLimiter, RedisRateLimiter
from app.service import ItemService


def _test_mode() -> bool:
    return get_settings().app_env == "test"


@lru_cache
def get_pool() -> ConnectionPool:
    # One pool shared by every repository. timeout= bounds the wait for a free
    # connection, so a DB outage becomes a fast 503, not a hung request.
    return ConnectionPool(get_settings().database_url, min_size=1, max_size=10, timeout=5, open=True)


@lru_cache
def get_repository() -> ItemRepository:
    if _test_mode():
        return InMemoryItemRepository()
    return PostgresItemRepository(get_pool())


@lru_cache
def get_redis_client() -> redis.Redis:
    # Short socket timeouts: a dead Redis must degrade to a cache miss quickly.
    return redis.Redis.from_url(
        get_settings().redis_url, decode_responses=True, socket_timeout=0.5, socket_connect_timeout=0.5
    )


@lru_cache
def get_cache() -> Cache:
    return Cache(get_redis_client(), default_ttl=get_settings().cache_ttl)


def get_service() -> ItemService:
    # No Redis in test mode (tests need no live services) or when REDIS_URL="".
    cache = None if _test_mode() or not get_settings().redis_url else get_cache()
    return ItemService(get_repository(), cache, get_settings().cache_ttl)


def get_rate_limiter() -> RateLimiter:
    # Redis-backed so N instances share one budget; in-memory for tests and Redis-less dev.
    if _test_mode() or not get_settings().redis_url:
        return InMemoryRateLimiter()
    return RedisRateLimiter(get_redis_client())


def close_resources() -> None:
    """Called on shutdown (main.py lifespan) -- release connections cleanly."""
    if get_pool.cache_info().currsize:
        get_pool().close()
    if get_redis_client.cache_info().currsize:
        get_redis_client().close()


@lru_cache
def get_ingest_repository() -> IngestRepository:
    return PostgresIngestRepository(get_pool())


def get_ingest_service() -> IngestService:
    s = get_settings()
    return IngestService(get_ingest_repository(), s.max_batch_size, s.max_pending_batches)
