# Business logic / orchestration layer. Depends only on the ItemRepository
# Protocol and the Cache wrapper -- never imports psycopg/redis directly
# (Dependency Inversion). Route handlers stay thin and call into here.

from fastapi import HTTPException
from app.models import Item, ItemCreate, ItemUpdate
from app.repository import ItemRepository
from app.cache import Cache


class ItemService:
    def __init__(self, repo: ItemRepository, cache: Cache | None = None) -> None:
        self._repo = repo
        self._cache = cache

    def list_items(self) -> list[Item]:
        # Not cached: a list endpoint is harder to invalidate correctly than a
        # single-key lookup (cache/write patterns section, hld-interview-design).
        # Cache the hot single-item read path instead (get_item below).
        return self._repo.list()

    def get_item(self, item_id: str) -> Item:
        if self._cache is None:
            return self._get_item_uncached(item_id)

        def loader():
            return self._get_item_uncached(item_id).model_dump(mode="json")

        data = self._cache.get_or_set(f"item:{item_id}", loader, ttl=60)
        return Item.model_validate(data)

    def _get_item_uncached(self, item_id: str) -> Item:
        item = self._repo.get(item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Item not found")
        return item

    def create_item(self, data: ItemCreate) -> Item:
        item = Item(title=data.title, body=data.body)
        self._repo.save(item)
        return item

    def update_item(self, item_id: str, data: ItemUpdate) -> Item:
        item = self._get_item_uncached(item_id)
        updated = item.model_copy(
            update={k: v for k, v in data.model_dump(exclude_unset=True).items()}
        )
        self._repo.save(updated)
        if self._cache:
            self._cache.invalidate(f"item:{item_id}")
        return updated

    def delete_item(self, item_id: str) -> None:
        if not self._repo.delete(item_id):
            raise HTTPException(status_code=404, detail="Item not found")
        if self._cache:
            self._cache.invalidate(f"item:{item_id}")
