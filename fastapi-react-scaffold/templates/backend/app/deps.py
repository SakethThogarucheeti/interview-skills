# Wiring: picks concrete implementations. This module is the Factory in this
# app -- env-driven so tests get InMemory + fakeredis-free stubs, and the live
# demo gets Postgres + Redis, without touching services/routes.

import os
from functools import lru_cache
import redis
from app.repository import ItemRepository, InMemoryItemRepository, PostgresItemRepository
from app.service import ItemService
from app.cache import Cache

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/app")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
USE_IN_MEMORY = os.environ.get("APP_ENV") == "test"


@lru_cache
def get_repository() -> ItemRepository:
    if USE_IN_MEMORY:
        return InMemoryItemRepository()
    return PostgresItemRepository(DATABASE_URL)


@lru_cache
def get_redis_client() -> redis.Redis:
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


@lru_cache
def get_cache() -> Cache:
    return Cache(get_redis_client())


def get_service() -> ItemService:
    # Skip Redis entirely in test mode so test_smoke.py needs no live services.
    cache = None if USE_IN_MEMORY else get_cache()
    return ItemService(get_repository(), cache)
