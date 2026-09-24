# Business logic / orchestration layer. Depends only on the ItemRepository
# Protocol and the Cache wrapper -- never imports psycopg/redis/FastAPI
# (Dependency Inversion). Raises domain errors (errors.py); route handlers
# stay thin and call into here.

from app.cache import Cache
from app.errors import NotFoundError
from app.models import Item, ItemCreate, ItemUpdate
from app.repository import ItemRepository


class ItemService:
    def __init__(self, repo: ItemRepository, cache: Cache | None = None, cache_ttl: int = 60) -> None:
        self._repo = repo
        self._cache = cache
        self._cache_ttl = cache_ttl

    def list_items(self, limit: int, offset: int) -> list[Item]:
        # Not cached: a list endpoint is harder to invalidate correctly than a
        # single-key lookup. Cache the hot single-item read path instead.
        return self._repo.list(limit, offset)

    def get_item(self, item_id: str) -> Item:
        if self._cache is None:
            return self._get_item_uncached(item_id)

        def loader():
            return self._get_item_uncached(item_id).model_dump(mode="json")

        data = self._cache.get_or_set(f"item:{item_id}", loader, ttl=self._cache_ttl)
        return Item.model_validate(data)

    def _get_item_uncached(self, item_id: str) -> Item:
        item = self._repo.get(item_id)
        if item is None:
            raise NotFoundError(f"Item {item_id} not found")
        return item

    def create_item(self, data: ItemCreate) -> Item:
        item = Item(title=data.title, body=data.body)
        self._repo.save(item)
        return item

    def update_item(self, item_id: str, data: ItemUpdate) -> Item:
        # Delegates to the repository's atomic partial update rather than
        # read -> model_copy -> save. The read-modify-write shape loses one of
        # two concurrent PATCHes every time -- see repository.update_fields.
        # exclude_none: an explicit {"title": null} means "leave it", not "null it".
        fields = data.model_dump(exclude_unset=True, exclude_none=True)
        updated = self._repo.update_fields(item_id, fields)
        if updated is None:
            raise NotFoundError(f"Item {item_id} not found")
        if self._cache:
            self._cache.invalidate(f"item:{item_id}")
        return updated

    def delete_item(self, item_id: str) -> None:
        if not self._repo.delete(item_id):
            raise NotFoundError(f"Item {item_id} not found")
        if self._cache:
            self._cache.invalidate(f"item:{item_id}")

    def check_dependencies(self) -> dict[str, bool]:
        checks = {"database": self._repo.ping()}
        if self._cache is not None:
            checks["cache"] = self._cache.ping()
        return checks
