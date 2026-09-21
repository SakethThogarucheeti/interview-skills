---
name: interview-kit
description: Single self-contained kit for a timed "build a full-stack app in ~2 hours" interview (e.g. DigitalOcean's format) — covers HLD talking points for scaling/traffic-spike/reliability questions, SOLID/DRY/GoF LLD patterns, a complete copy-paste FastAPI+Postgres+Redis+React scaffold (every file inlined below), a Cursor workflow section (the interview runs in Cursor, not here), and time-compression tactics throughout. Use as soon as the user shares the interview prompt and wants to start building, asks about system design/scaling questions for this interview, wants the scaffold code, or asks about using Cursor for it. Everything needed lives in this one file — no other skill or template directory required.
---

# Interview kit — 2-hour full-stack build

One file, because the interview machine may not have GitHub access: this covers requirements → architecture → code structure → the actual scaffold (inlined as copy-paste files below) → Cursor workflow → verbal defense, end to end.

You are pairing with the user to *prepare for and rehearse*, and possibly to co-drive, a live timed interview. The actual build happens in Cursor (§5), so treat a Claude Code session as prep/dry-run unless told otherwise. Optimize in this order: something working and demoable > a codebase that looks deliberately structured on a skim > the user having sharp, ready answers for scaling/reliability questions. A brilliant architecture that isn't running loses to a plain CRUD app that works and whose author can clearly explain how they'd scale it.

## 0. Time-compression tactics (apply throughout, not just once)

The real enemy in a 2-hour window is idle/serial time, not typing speed.

- **Never block on a single open question.** Batch every clarifying question into one shot, not a back-and-forth — most requirements questions are independent, there's no reason to serialize them.
- **Use dead time for research, not idling.** The moment a question is pending, or a slow command is running (`docker compose up`, `npm install`, a migration), that wait is wasted unless filled. Fire a parallel background task the instant you ask the question, not after the answer lands: look up a library API/syntax you'll need next, check a reference pattern, or pre-draft the next file. In Claude Code: launch a `fork`/background Agent in the *same turn* as the clarifying question. In Cursor during the live interview: open a second chat tab or Background Agent to research while the main thread waits (see §5.3).
- **Decide, don't deliberate.** Any choice that doesn't change the interview's outcome (which UUID helper, which HTTP status convention) gets a reasonable default instantly, not a question. Reserve real questions for things that change scope or that only the user/interviewer can answer.
- **Zero visual design time.** No CSS framework, no stylesheet, no color/spacing decisions beyond the inline styles already in the scaffold below. This is a hard rule from the start, not a fallback for leftover time — spend any saved time on a second feature or on rehearsing the scaling talking points instead.
- **Time budget** (2 hours, adjust if told otherwise): ~10 min requirements+design (§1), ~5 min scaffold copy-in (§4), ~45-50 min backend, ~30-40 min frontend, ~15-20 min polish + defense prep (§3), buffer.

## 1. Requirements & HLD (~10 min, don't exceed)

Ask every open question in one batch, not one at a time; skip asking anything that doesn't change scope and just state the assumption. Cover:
- **Core entities & actions** — what does the user create/read/update/delete?
- **Read vs write ratio** — most prompts (shorteners, polls, chat, task boards, rate limiters, notification systems) are read-heavy or write-bursty; say which, it drives the caching/scaling story.
- **Consistency requirement** — strongly consistent (payments, inventory) or eventually consistent (view counts, feeds, likes)? Most interview prompts tolerate eventual consistency — say so, it simplifies everything downstream.
- **Explicit non-goals** — state what you're NOT building (multi-region, multi-tenant auth, billing) so scope reads as deliberate, not accidental.

### Default architecture: "one box, clean seams"

```
[React SPA] --HTTP/JSON--> [FastAPI monolith] --> [Postgres]
                                  |
                                  +--> [Redis: cache-aside for hot reads]
                                  +--> [Redis: pub/sub for fan-out, if the prompt needs live updates]
```

Postgres + Redis are provisioned from minute one via the scaffold's `docker-compose.yml` (§4), not swapped in later. Why this architecture wins in a 2-hour format: one deployable, no network calls between your own services to debug under time pressure, and every "how would you scale this" question has a crisp, concrete answer (§3) because the seams (repository, cache, pub/sub) are already there in the code. Do **not** start with microservices, message queues, or multi-region — that costs implementation time you don't have and reads as a red flag, not a strength, in a 2-hour app.

If the prompt is small (a simple CRUD tool), say so explicitly and skip straight to §4 — don't invent structure the app doesn't need.

## 2. LLD: SOLID/DRY + patterns, applied pragmatically

**The rule that overrides every pattern below**: apply a pattern only when you can already name a second variant it needs to accommodate. An interface with one implementation "for future extensibility" is YAGNI and costs typing time you need elsewhere.

**SOLID, briefly**: split by *reason to change* (route handler / service / repository are three separate reasons, so three separate functions even in a small app — this alone is most of what makes the code look professional on a skim). Route handlers depend on an abstraction (a `Protocol`/`Depends`-injected interface), never directly on `psycopg`/`redis` — this is the single highest-value habit here, it's what makes "how would you swap X" be "change one function," not "rewrite the app."

**DRY, briefly**: duplication across 2 call sites is fine (rule of three). Never duplicate: validation/business rules, response shapes (use Pydantic models), or DB access for one entity (one repository, not scattered raw queries).

**Pattern shortlist** (Python: use `typing.Protocol`, no inheritance ceremony):
- **Repository** — use almost always. Isolates storage behind an interface; it's *the* seam the scaling story leans on, and it makes the app testable without a real DB. See `app/repository.py` in §4.
- **Strategy** — use when there are genuinely interchangeable algorithms (e.g. multiple short-code generation strategies, multiple ranking rules). Skip it if there's only one way to do the thing.
- **Factory** — use for branching construction logic (e.g. picking a repository impl by env). A plain function or FastAPI `Depends` provider usually *is* the factory; you rarely need a dedicated Factory class at this scale. See `app/deps.py`.
- **Decorator** — cross-cutting concerns on functions (logging, timing, rate-limiting). Python decorators are the natural fit regardless of whether you narrate it as "the pattern."
- **Observer** — one action triggers multiple independent side effects (e.g. signup → email + analytics + provisioning), or fan-out via Redis pub/sub. See `app/events.py`.
- **Adapter** — wrapping a third-party SDK/API (DigitalOcean API, payment provider) behind your own narrow interface so business logic doesn't import the SDK directly.
- **Avoid**: Abstract Factory, Visitor, Chain of Responsibility, Builder, multi-level class hierarchies — these cost more typing than they buy clarity at this scale and read as a junior-engineer tell to a reviewer skimming interview code.

**Code layout** (what the scaffold in §4 already gives you): `main.py` thin routes → `service.py` business logic (depends only on repository/cache interfaces) → `repository.py` the only place touching Postgres → `cache.py`/`events.py` Redis, wrapped → `models.py` one Pydantic shape per concept, reused everywhere → `deps.py` wiring/env-driven implementation choice. New feature = new service function; new storage backend = new repository implementation; nothing else changes. That layering *is* the LLD answer to "how is this extensible."

## 3. Talking points for common HLD follow-ups

State current state → bottleneck → concrete next step, grounded in the actual code just written, not generic vocabulary.

**"How do you handle a traffic spike / going viral?"** Current: single stateless FastAPI process. Bottleneck: DB connections/CPU on one box. Next, in order of effort: (a) horizontal scale — N identical stateless instances behind a load balancer, works immediately *because* the app holds no in-memory session state (mention this is why stateless token auth over server-side sessions), (b) cache hot reads (below), (c) a queue to absorb write bursts asynchronously, (d) rate-limit/backpressure at the edge so a spike degrades gracefully instead of falling over.

**"How would you cache this?"** Identify the hot read path; cache key = the lookup key; TTL or write-through invalidation on update. Already using Redis from the start (`app/cache.py`), specifically because an in-process cache doesn't stay consistent once you scale to N app instances. Cache-aside: check cache → miss → read DB → populate → return (exactly what `Cache.get_or_set` does). Mention cache stampede (many misses on a hot key at once) as a known failure mode; fix is request coalescing or a short jittered TTL. If the prompt needs live/multi-consumer fan-out, the same Redis instance's pub/sub (`app/events.py`) is the low-effort answer before reaching for a dedicated broker.

**"How would you scale the database?"** First: indexes on actual query patterns, and the connection pool already in `PostgresItemRepository` (bounds concurrent connections instead of exhausting Postgres under a spike). Second: read replicas — the API already treats Postgres behind a repository interface, so routing reads to a replica is a swap at that seam, not a rewrite. Third: sharding only if asked explicitly about very large scale — name the shard key (e.g. user id) and that it trades cross-shard queries for write capacity; don't volunteer this unprompted.

**"What about consistency / race conditions?"** Name the specific race in the actual app (two requests incrementing a counter, double-booking a slot) and how you'd close it: a DB unique constraint/transaction, `SELECT ... FOR UPDATE`, or an atomic increment — not a vague "add a lock." Distinguish where strong consistency is needed (writes to the core entity) vs. where eventual consistency is fine (denormalized reads, counters).

**"How do you make this reliable?"** Idempotency on retry-able write endpoints (client idempotency key, or natural idempotency via upsert). Timeouts + backoff on outbound calls. Stateless app so a crashed instance is just replaced, not a data-loss event.

**"How would you deploy/monitor this?"** Containerize (Dockerfile in §4), N replicas behind a load balancer (DigitalOcean App Platform or DO Load Balancer + Droplets is the on-brand answer), structured logging + `/health` (already present), latency/error-rate metrics.

## 4. Scaffold — copy these files verbatim, then adapt

Create this directory layout, paste each block into the named file, then adapt per §4.9. This is a full working FastAPI + Postgres + Redis backend and a React (Vite) frontend, already layered per §2 — it has been installed and its smoke test run successfully.

```
backend/
  requirements.txt
  Dockerfile
  docker-compose.yml
  test_smoke.py
  app/
    __init__.py
    models.py
    repository.py
    cache.py
    events.py
    service.py
    deps.py
    main.py
frontend/
  package.json
  vite.config.js
  index.html
  src/
    main.jsx
    api.js
    App.jsx
```

### 4.1 `backend/requirements.txt`
```
fastapi>=0.115
uvicorn[standard]>=0.30
pydantic>=2.9
python-multipart>=0.0.9
psycopg[binary]>=3.2
psycopg-pool>=3.2
redis>=5.0
```

### 4.2 `backend/Dockerfile`
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
# DATABASE_URL / REDIS_URL default to localhost in app/deps.py -- override with
# --env or docker-compose networking (e.g. postgresql://postgres:postgres@postgres:5432/app)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 4.3 `backend/docker-compose.yml`
```yaml
# Local Postgres + Redis for the live demo. Start with: docker compose up -d
# Then run the backend normally (uvicorn) against the default DATABASE_URL /
# REDIS_URL in app/deps.py -- no other config needed.
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: app
    ports:
      - "5432:5432"
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

### 4.4 `backend/app/models.py`
```python
# Domain + API models for a generic "Item" resource.
# Rename Item -> your actual entity (Link, Task, Poll, ...) and adjust fields.
# Keep ONE definition of each shape (DRY) and reuse it across create/read/update.

from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from pydantic import BaseModel, Field


class Item(BaseModel):
    """Domain object -- what's actually stored."""
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    title: str
    body: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ItemCreate(BaseModel):
    """Request shape for POST -- never reuse Item directly for input (id/created_at aren't client-supplied)."""
    title: str
    body: str = ""


class ItemUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
```

### 4.5 `backend/app/repository.py`
```python
# Repository pattern (see LLD, section 2): the ONLY place that talks to
# storage. Swap InMemoryItemRepository -> PostgresItemRepository without
# touching services or routes -- this is the seam the scaling talking points
# (section 3) point at.

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
```

### 4.6 `backend/app/cache.py`
```python
# Cache-aside helper backed by Redis (section 3's caching talking points).
# Thin wrapper so services never import redis directly -- same Dependency
# Inversion habit as the repository.

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
```

### 4.7 `backend/app/events.py`
```python
# Observer pattern over Redis pub/sub -- use when one write should fan out to
# independent reactions (e.g. notify connected clients via websocket, or
# invalidate caches in other app instances). Only wire this in if the prompt
# actually needs live/multi-consumer updates -- most CRUD prompts don't.

import json
import redis


class EventPublisher:
    def __init__(self, client: redis.Redis) -> None:
        self._client = client

    def publish(self, channel: str, payload: dict) -> None:
        self._client.publish(channel, json.dumps(payload))


class EventSubscriber:
    """Run in a background task (e.g. FastAPI startup event / asyncio task) to
    react to published events -- e.g. push to a websocket, update a live counter."""

    def __init__(self, client: redis.Redis) -> None:
        self._client = client

    def listen(self, channel: str):
        pubsub = self._client.pubsub()
        pubsub.subscribe(channel)
        for message in pubsub.listen():
            if message["type"] == "message":
                yield json.loads(message["data"])
```

### 4.8 `backend/app/service.py`
```python
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
        # single-key lookup. Cache the hot single-item read path instead.
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
```

### 4.9 `backend/app/deps.py`
```python
# Wiring: picks concrete implementations. This module is the Factory in this
# app -- env-driven so tests get InMemory with no cache, and the live demo
# gets Postgres + Redis, without touching services/routes.

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
```

### 4.10 `backend/app/main.py`
```python
# Route layer: thin. Parse request -> call service -> return. No business logic here.

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.models import Item, ItemCreate, ItemUpdate
from app.service import ItemService
from app.deps import get_service

app = FastAPI(title="Interview App")

# Wide-open CORS for a same-session demo (frontend on a different port).
# Say out loud this would be scoped to the real frontend origin in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/items", response_model=list[Item])
def list_items(svc: ItemService = Depends(get_service)):
    return svc.list_items()


@app.get("/items/{item_id}", response_model=Item)
def get_item(item_id: str, svc: ItemService = Depends(get_service)):
    return svc.get_item(item_id)


@app.post("/items", response_model=Item, status_code=201)
def create_item(data: ItemCreate, svc: ItemService = Depends(get_service)):
    return svc.create_item(data)


@app.patch("/items/{item_id}", response_model=Item)
def update_item(item_id: str, data: ItemUpdate, svc: ItemService = Depends(get_service)):
    return svc.update_item(item_id, data)


@app.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: str, svc: ItemService = Depends(get_service)):
    svc.delete_item(item_id)
```

### 4.11 `backend/app/__init__.py`
Empty file.

### 4.12 `backend/test_smoke.py`
```python
# Minimal smoke test -- run with: APP_ENV=test pytest test_smoke.py
# APP_ENV=test makes deps.py hand out InMemoryItemRepository and no real cache,
# so this runs with no Postgres/Redis needed.
import os

os.environ["APP_ENV"] = "test"

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").status_code == 200


def test_crud_flow():
    created = client.post("/items", json={"title": "test", "body": "hi"}).json()
    item_id = created["id"]

    assert client.get(f"/items/{item_id}").json()["title"] == "test"
    assert client.patch(f"/items/{item_id}", json={"title": "updated"}).json()["title"] == "updated"
    assert client.delete(f"/items/{item_id}").status_code == 204
    assert client.get(f"/items/{item_id}").status_code == 404
```

### 4.13 `frontend/package.json`
```json
{
  "name": "interview-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.1",
    "vite": "^5.4.8"
  }
}
```

### 4.14 `frontend/vite.config.js`
```javascript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy /api to the FastAPI backend so the frontend can call relative paths
// (avoids CORS fiddling during the demo).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
```

### 4.15 `frontend/index.html`
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <title>Interview App</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

### 4.16 `frontend/src/main.jsx`
```jsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

### 4.17 `frontend/src/api.js`
```javascript
// Thin API client -- one function per endpoint, one place that knows the base
// URL and error handling. Rename Item -> your entity everywhere below.
const BASE = "/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  listItems: () => request("/items"),
  getItem: (id) => request(`/items/${id}`),
  createItem: (data) => request("/items", { method: "POST", body: JSON.stringify(data) }),
  updateItem: (id, data) => request(`/items/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteItem: (id) => request(`/items/${id}`, { method: "DELETE" }),
};
```

### 4.18 `frontend/src/App.jsx`
```jsx
import { useEffect, useState } from "react";
import { api } from "./api.js";

// Minimal list + create + delete UI. Extend with edit/detail views as the
// prompt requires. Do NOT add a stylesheet/CSS framework -- keep these inline
// styles as-is (section 0's zero-CSS rule).
export default function App() {
  const [items, setItems] = useState([]);
  const [title, setTitle] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = () =>
    api
      .listItems()
      .then(setItems)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));

  useEffect(() => {
    refresh();
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!title.trim()) return;
    try {
      await api.createItem({ title });
      setTitle("");
      refresh();
    } catch (e) {
      setError(e.message);
    }
  };

  const handleDelete = async (id) => {
    try {
      await api.deleteItem(id);
      refresh();
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div style={{ maxWidth: 480, margin: "2rem auto", fontFamily: "system-ui" }}>
      <h1>Items</h1>
      {error && <p style={{ color: "crimson" }}>{error}</p>}
      <form onSubmit={handleCreate} style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="New item title"
          style={{ flex: 1 }}
        />
        <button type="submit">Add</button>
      </form>
      {loading ? (
        <p>Loading…</p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0 }}>
          {items.map((item) => (
            <li
              key={item.id}
              style={{ display: "flex", justifyContent: "space-between", padding: "6px 0" }}
            >
              <span>{item.title}</span>
              <button onClick={() => handleDelete(item.id)}>Delete</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

### 4.19 Setup commands

```bash
cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cd ../frontend && npm install
```
Then, all backgrounded/parallel:
```bash
# from backend/
docker compose up -d          # postgres:5432, redis:6379
uvicorn app.main:app --reload --port 8000
# from frontend/
npm run dev
```
If Docker isn't available, point `DATABASE_URL`/`REDIS_URL` env vars (see `deps.py`) at whatever Postgres/Redis instance is provided instead.

### 4.20 Adapt to the actual prompt (rename-and-extend, not a rewrite)

1. **`models.py`** — rename `Item`/`ItemCreate`/`ItemUpdate` to the real entity, change fields. Add a second entity module the same shape if the prompt has more than one resource.
2. **`repository.py`** — rename the Protocol and classes, update the `CREATE TABLE`/SQL to the real schema, add query methods the prompt needs (e.g. `get_by_owner`) — keep them on the repository, not scattered in routes.
3. **`service.py`** — the prompt's actual business rules live here (uniqueness checks, state transitions, computed fields). Drop the cache-aside call on `get_item` if the read pattern doesn't warrant it — cache the actual hot path, not every read by default.
4. **`main.py`** — rename routes, add any non-CRUD endpoints the prompt needs (e.g. `GET /r/{code}` for a redirect).
5. **`api.js`** — rename client methods to match.
6. **`App.jsx`** — replace the list/create UI with whatever view the prompt needs; keep the inline-styles-only rule.

**Don't change unless the prompt requires it**: the repository/service/route layering; `PostgresItemRepository` as live default + `InMemoryItemRepository` for tests (`APP_ENV=test`); the CORS/proxy setup; whether `EventPublisher`/`EventSubscriber` get wired in (only if the prompt needs live/multi-consumer fan-out).

**Fast wins if time allows, in order**: extend `test_smoke.py` for the real entity (green tests are a strong signal) → `/health` already present, ties to the monitoring talking point → `Dockerfile`/`docker-compose.yml` already present, evidence of deployment thinking → keep the loading/error states in the frontend, don't strip them.

## 5. Using Cursor for the live build

The interview itself runs in Cursor, not Claude Code. This section is the bridge.

### 5.1 Before the interview: port these conventions into Cursor

Cursor reads **Project Rules** — `.mdc` files under `.cursor/rules/`, auto-attached to its chat/agent/Tab context. Create `.cursor/rules/interview-conventions.mdc` ahead of time with this content:

```markdown
---
description: Conventions for the timed full-stack interview build. Always apply.
alwaysApply: true
---

# Interview build conventions

Single FastAPI backend + single React (Vite) frontend: React SPA -> FastAPI ->
Postgres, with Redis for cache-aside on hot reads and optionally pub/sub for
fan-out. No microservices, no message broker, no multi-region -- those are
verbal talking points, not build tasks, in this window.

Backend layering (do not collapse): main.py routes (thin) -> service.py
(business logic, depends only on repository/cache Protocols) ->
repository.py (only place touching Postgres) -> cache.py/events.py (Redis,
wrapped) -> models.py (one Pydantic shape per concept) -> deps.py (wiring).

Apply the Repository pattern to every entity by default. Reach for Strategy,
Factory, Observer, Decorator, or Adapter only with two genuinely interchangeable
implementations to justify it -- no interface with one implementation "for
future extensibility."

Every new endpoint gets a smoke test using an in-memory repository via
APP_ENV=test, so tests never need live Postgres/Redis.

Frontend: plain React + fetch via a single api.js client, one function per
endpoint. Golden path > loading/error states > visual polish. Do NOT add a
CSS framework, stylesheet, or custom colors/typography -- keep inline styles
only. This is a hard rule, not a fallback for leftover time.

This is a timed build: no large refactors, no extra dependencies, no
gold-plating. When a decision doesn't change the outcome, make it and move
on. Never leave the editor/chat idle while something else could be
happening -- if a clarifying question is pending or a command is running,
use a second chat thread for research that unblocks the next step.
```

Also pre-stage the §4 scaffold files into the starting project if the interview format allows a personal template repo — confirm with the interviewer first; if not, recreate the structure quickly from this file, which is exactly why the layering should be a habit going in, not something looked up live.

### 5.2 Cursor features worth using live

- **Tab (autocomplete)** — always on, free. Best for repetitive shape-following code (a second Pydantic model matching the first, a fourth route matching the first three).
- **Cmd+K (inline edit)** — small, localized, well-specified changes to code you're looking at. Faster than a chat round-trip for anything scoped to the current file/selection.
- **Agent/Composer (multi-file)** — the two big moves here: (a) initial scaffold generation if not pre-staged, prompted with the `.mdc` layering, and (b) the §4.20 rename-and-extend pass across files, pasting that checklist directly into the prompt. Always review the diff before accepting — a wrong assumption compounds across files fast.
- **@-mentions** (`@filename`/`@codebase`) — for any chat/agent question that depends on existing code, instead of re-pasting code.
- **Checkpoints** — skim the changed-files list after any multi-file Agent edit before moving on; cheap insurance against a bad assumption compounding.

### 5.3 Use dead time: parallelize research instead of idling

Any time blocked on something other than typing (waiting on the interviewer's answer, `docker compose up` pulling images, `npm install`) is wasted unless filled:
- Open a second chat tab (or Background Agent) the moment you ask a clarifying question, and research whatever comes next regardless of the answer — don't wait for the reply to start.
- Batch clarifying questions (§0) so you're not creating a new idle moment every few minutes.
- Queue the next file while a slow command runs — write/adapt it by hand or via Cmd+K instead of watching the terminal.
- Don't let research become its own rabbit hole — pull the one fact needed and get back to building; if a lookup is taking longer than what it was meant to save, abandon it and make a reasonable call.

### 5.4 What NOT to reach for live

Don't hand-tune Cursor settings/models mid-interview. Don't use Agent mode for large open-ended asks ("build the whole backend") without giving it the specific layering/entity first — an unscoped prompt produces generic CRUD needing a second pass, costing more net time. Don't fight Tab's suggestions over stylistic preferences that don't matter.

### 5.5 Talking to the interviewer about tool use

Being transparent that you're using Cursor's AI features deliberately (Tab for boilerplate, Agent for scoped multi-file changes) is a fair, often positive signal — the interesting thing for them is whether *you* made the architecture/pattern decisions (§1-§3) while the tool accelerated typing, not whether the tool designed the system.

## 6. Orchestration checklist (run through this during the actual build)

1. **Read the prompt** — restate core entities/actions in 1-2 sentences, name the time budget and phase breakdown (§0) out loud.
2. **Design (~10 min)** — §1: batch questions, sketch the architecture, state non-goals. Stop as soon as you have it; don't iterate the diagram.
3. **Scaffold (~5 min)** — §4: copy files in, start Postgres+Redis, get both dev servers running before writing custom code. Confirm `/health` and the frontend root both load — catching a broken toolchain now costs 2 minutes, at minute 90 it costs the interview.
4. **Backend (~45-50 min)** — §4.20 adapt pass + §2 pattern judgment. Run tests as you finish each endpoint, not all at the end. Checkpoint: by the midpoint, core flows reachable via `curl`/`/docs` even before the frontend exists.
5. **Frontend (~30-40 min)** — golden path > loading/error > (no) polish, per §0's zero-CSS rule.
6. **Defense prep (~10-15 min, can overlap with polish)** — make sure §3's answers are ready, grounded in the real code just written, not generic vocabulary.
7. **Final pass (last ~10 min)** — exercise the full golden path in the browser, confirm both servers start cleanly from a fresh terminal, have a one-sentence close ready: what's built, what's explicitly out of scope and why, and the first three things you'd do next with more time.

**Boundaries**: don't let architecture discussion eat build time — lock it in and adjust as you build. Don't introduce infrastructure beyond Postgres+Redis unless asked live. If behind schedule, cut scope (fewer fields/endpoints/views) before cutting layering/testing habits — a smaller well-structured app outscores a larger messy one.
