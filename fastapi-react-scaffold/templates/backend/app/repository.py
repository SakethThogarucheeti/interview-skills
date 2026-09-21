# Repository pattern (see lld-design-patterns skill): the ONLY place that talks
# to storage. Swap InMemoryItemRepository -> PostgresItemRepository without
# touching services or routes -- this is the seam your "how would you scale the
# DB" answer points at (read replicas, connection pooling, etc. all live here).

from typing import Protocol
from app.models import Item


class ItemRepository(Protocol):
    def list(self) -> list[Item]: ...
    def get(self, item_id: str) -> Item | None: ...
    def save(self, item: Item) -> None: ...
    def delete(self, item_id: str) -> bool: ...


class InMemoryItemRepository:
    """Zero setup -- use this in tests (test_smoke.py) so they don't need a real
    Postgres instance. Not used for the live demo; PostgresItemRepository is the
    default (see deps.py) since Postgres is already the target DB."""

    def __init__(self) -> None:
        self._data: dict[str, Item] = {}

    def list(self) -> list[Item]:
        return list(self._data.values())

    def get(self, item_id: str) -> Item | None:
        return self._data.get(item_id)

    def save(self, item: Item) -> None:
        self._data[item.id] = item

    def delete(self, item_id: str) -> bool:
        return self._data.pop(item_id, None) is not None


class PostgresItemRepository:
    """Live-demo default. Uses psycopg3 with a small connection pool -- no ORM,
    so there's nothing extra to learn under time pressure, but the raw-SQL
    surface is small and isolated to this one class (DRY: the only place
    that knows the `items` table shape)."""

    def __init__(self, dsn: str) -> None:
        from psycopg_pool import ConnectionPool

        self._pool = ConnectionPool(dsn, min_size=1, max_size=10, open=True)
        with self._pool.connection() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS items (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT, created_at TIMESTAMPTZ
                )"""
            )

    def list(self) -> list[Item]:
        with self._pool.connection() as conn:
            rows = conn.execute("SELECT id, title, body, created_at FROM items").fetchall()
        return [Item(id=r[0], title=r[1], body=r[2], created_at=r[3]) for r in rows]

    def get(self, item_id: str) -> Item | None:
        with self._pool.connection() as conn:
            row = conn.execute(
                "SELECT id, title, body, created_at FROM items WHERE id = %s", (item_id,)
            ).fetchone()
        return Item(id=row[0], title=row[1], body=row[2], created_at=row[3]) if row else None

    def save(self, item: Item) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                """INSERT INTO items (id, title, body, created_at) VALUES (%s, %s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, body = EXCLUDED.body""",
                (item.id, item.title, item.body, item.created_at),
            )

    def delete(self, item_id: str) -> bool:
        with self._pool.connection() as conn:
            cur = conn.execute("DELETE FROM items WHERE id = %s", (item_id,))
            return cur.rowcount > 0
