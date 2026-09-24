# Repository pattern (see LLD, section 2): the ONLY place that talks to
# storage. Swap InMemoryItemRepository -> PostgresItemRepository without
# touching services or routes -- this is the seam the scaling talking points
# (section 3) point at.

import threading
from typing import Protocol

import psycopg
from psycopg_pool import ConnectionPool

from app.models import Item

# Every process runs its schema DDL at startup. Concurrent CREATE TABLE IF NOT
# EXISTS from N instances (API + workers booting together) fails with
# UniqueViolation on pg_type -- reproduced 10/10 -- so each schema block takes
# this transaction-scoped advisory lock first. (Next step: a migration tool run
# once per deploy, e.g. an App Platform PRE_DEPLOY job.)
SCHEMA_LOCK_ID = 7_331_001


class ItemRepository(Protocol):
    def list(self, limit: int, offset: int) -> list[Item]: ...
    def get(self, item_id: str) -> Item | None: ...
    def save(self, item: Item) -> None: ...
    def update_fields(self, item_id: str, fields: dict) -> Item | None: ...
    def delete(self, item_id: str) -> bool: ...
    def ping(self) -> bool: ...


class InMemoryItemRepository:
    """Zero setup -- the tests use this so they don't need a real Postgres.
    Not used for the live demo; PostgresItemRepository is the default (deps.py)."""

    def __init__(self) -> None:
        self._data: dict[str, Item] = {}
        self._lock = threading.Lock()

    def list(self, limit: int, offset: int) -> list[Item]:
        items = sorted(self._data.values(), key=lambda i: (i.created_at, i.id), reverse=True)
        return items[offset : offset + limit]

    def get(self, item_id: str) -> Item | None:
        return self._data.get(item_id)

    def save(self, item: Item) -> None:
        self._data[item.id] = item

    def update_fields(self, item_id: str, fields: dict) -> Item | None:
        # Lock, not read-then-write: FastAPI runs these plain `def` handlers in a
        # threadpool, so two concurrent PATCHes really do interleave here.
        with self._lock:
            item = self._data.get(item_id)
            if item is None:
                return None
            updated = item.model_copy(update=fields)
            self._data[item_id] = updated
            return updated

    def delete(self, item_id: str) -> bool:
        return self._data.pop(item_id, None) is not None

    def ping(self) -> bool:
        return True


def _row_to_item(r) -> Item:
    return Item(id=r[0], title=r[1], body=r[2], created_at=r[3])


class PostgresItemRepository:
    """Live-demo default. psycopg3 over a shared connection pool (deps.py) -- no
    ORM, so nothing extra to learn under time pressure, and the raw-SQL surface
    is isolated to this one class (DRY: the only place that knows the `items`
    table shape). Each `with pool.connection()` block is one transaction."""

    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool
        with self._pool.connection() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(%s)", (SCHEMA_LOCK_ID,))
            conn.execute(
                """CREATE TABLE IF NOT EXISTS items (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )"""
            )
            # Backs the paginated list's ORDER BY -- no full-table sort per page.
            conn.execute("CREATE INDEX IF NOT EXISTS items_created_at_idx ON items (created_at DESC, id)")

    def list(self, limit: int, offset: int) -> list[Item]:
        with self._pool.connection() as conn:
            rows = conn.execute(
                """SELECT id, title, body, created_at FROM items
                   ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s""",
                (limit, offset),
            ).fetchall()
        return [_row_to_item(r) for r in rows]

    def get(self, item_id: str) -> Item | None:
        with self._pool.connection() as conn:
            row = conn.execute("SELECT id, title, body, created_at FROM items WHERE id = %s", (item_id,)).fetchone()
        return _row_to_item(row) if row else None

    def save(self, item: Item) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                """INSERT INTO items (id, title, body, created_at) VALUES (%s, %s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, body = EXCLUDED.body""",
                (item.id, item.title, item.body, item.created_at),
            )

    def update_fields(self, item_id: str, fields: dict) -> Item | None:
        """Partial update as ONE atomic statement -- NOT read-modify-write.
        Two concurrent PATCHes to different fields both survive; the read-then-
        write version silently loses one (this is precisely the graded write
        race from section 1's pitfall table). COALESCE keeps any column whose
        key is absent from `fields`; if a field must be settable to NULL, use a
        sentinel or build the SET clause dynamically instead."""
        if not fields:
            return self.get(item_id)
        with self._pool.connection() as conn:
            row = conn.execute(
                """UPDATE items SET title = COALESCE(%s, title), body = COALESCE(%s, body)
                   WHERE id = %s RETURNING id, title, body, created_at""",
                (fields.get("title"), fields.get("body"), item_id),
            ).fetchone()
        return _row_to_item(row) if row else None

    def delete(self, item_id: str) -> bool:
        with self._pool.connection() as conn:
            return conn.execute("DELETE FROM items WHERE id = %s", (item_id,)).rowcount > 0

    def ping(self) -> bool:
        try:
            with self._pool.connection(timeout=2) as conn:
                conn.execute("SELECT 1")
            return True
        except (psycopg.Error, OSError):
            return False
