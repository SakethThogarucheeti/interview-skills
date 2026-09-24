# Unit tests: service logic and failure modes, no HTTP, no real infrastructure.
import pytest
import redis

from app import deps
from app.cache import Cache
from app.config import get_settings
from app.errors import NotFoundError
from app.models import ItemCreate, ItemUpdate
from app.repository import InMemoryItemRepository
from app.service import ItemService


class DeadRedis:
    """Every call fails the way a down Redis does."""

    def __getattr__(self, _):
        def fail(*_, **__):
            raise redis.ConnectionError("connection refused")

        return fail


def test_update_missing_item_raises_not_found():
    with pytest.raises(NotFoundError):
        ItemService(InMemoryItemRepository()).update_item("missing", ItemUpdate(title="x"))


def test_redis_outage_degrades_to_database_reads():
    svc = ItemService(InMemoryItemRepository(), Cache(DeadRedis()))
    item = svc.create_item(ItemCreate(title="still works"))
    assert svc.get_item(item.id).title == "still works"
    svc.update_item(item.id, ItemUpdate(title="and writes"))  # invalidate failure is logged, not raised
    assert svc.check_dependencies() == {"database": True, "cache": False}


def test_empty_redis_url_runs_without_a_cache(monkeypatch):
    # e.g. App Platform with only a dev Postgres attached: REDIS_URL="" -> no cache, not a broken one.
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.setattr(deps, "get_repository", InMemoryItemRepository)
    get_settings.cache_clear()
    try:
        assert deps.get_service().check_dependencies() == {"database": True}
    finally:
        get_settings.cache_clear()
