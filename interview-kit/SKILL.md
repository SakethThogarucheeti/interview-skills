---
name: interview-kit
description: Single self-contained kit for a timed "build a full-stack app in ~2 hours" interview (e.g. DigitalOcean's format). Always asks a batched round of clarifying questions and waits for an answer before any implementation begins — then covers requirements/goal-scoping and a pitfall scan (single points of failure, spiky-traffic tradeoffs, race conditions, missing indexes/pagination) run during the design phase itself, HLD talking points for scaling/reliability follow-ups, SOLID/DRY/GoF LLD patterns, a complete copy-paste FastAPI+Postgres+Redis+React scaffold (every file inlined below), a Cursor workflow section (the interview runs in Cursor, not here), and time-compression tactics throughout. Use as soon as the user shares the interview prompt and wants to start building, asks about system design/scaling questions for this interview, wants the scaffold code, or asks about using Cursor for it. Everything needed lives in this one file — no other skill or template directory required.
---

# Interview kit — 2-hour full-stack build

One file, no GitHub dependency: requirements → design → LLD → scaffold code (inlined below) → Cursor workflow → verbal defense.

Prep/rehearse here; the actual build runs in Cursor (§5) unless told otherwise. Priority order: working demo > code that looks deliberately structured on a skim > sharp, ready answers to scaling/reliability questions. Working-but-plain beats brilliant-but-unfinished.

## 0. Time-compression tactics (apply throughout)

The real enemy in a 2-hour window is idle/serial time, not typing speed.

- **Ask before building, always.** Clarifying questions (§1) are a hard gate, not optional politeness — batch them into one shot and wait for the answer before starting any implementation. This doesn't conflict with speed: batching means one round trip, not zero.
- **Use dead time for research while you wait, never idle.** Once the question is asked, that wait is dead time unless filled. Fire a parallel task to look up what you'll need next — don't wait for the answer to start it. Claude Code: a `fork`/background Agent in the same turn as the question. Cursor: a second chat tab or Background Agent (§5.3). This fills the wait; it doesn't replace it — still don't start implementing on an assumed answer.
- **Decide, don't deliberate.** Default any choice that doesn't change the outcome; only ask what changes scope.
- **Zero CSS.** No framework, no stylesheet, nothing beyond the scaffold's inline styles — hard rule from the start, not a fallback. Spend saved time on a feature or on defense rehearsal instead.
- **Budget** (2h, adjust as told): ~10 min design (§1), ~5 min scaffold copy-in (§4), ~45-50 min backend, ~30-40 min frontend, ~15-20 min polish + defense (§3), buffer.

## 1. Requirements & HLD (~10 min, don't exceed)

**Hard gate: ask before building.** The moment the prompt is shared, ask the batch of clarifying questions below in a single message and stop — do not scaffold, write code, or touch §4 until the user answers or explicitly says to use your judgment/defaults. This is a real stop, not a rhetorical one: no implementation work happens between asking and getting a response. Use the dead-time tactic (§0) to do something useful *while waiting* (research, pre-reading this file's scaffold section), but don't start building on assumed answers. Only skip asking outright if the user's own prompt already answered a question — don't re-ask what they already told you.

Batch every open question; skip asking only what doesn't change scope, and state that assumption explicitly instead. Output: a short, explicit statement of goals and non-goals — a decision to hold the build to, not just gathered info. Cover:
- **Core entities & actions** — create/read/update/delete what?
- **Read vs write ratio** — most prompts (shorteners, polls, task boards, rate limiters) are read-heavy or write-bursty; name which, it drives the caching story.
- **Consistency** — strong (payments, inventory) or eventual (counts, feeds, likes)? Most prompts tolerate eventual — say so, it simplifies everything downstream.
- **The specific spiky-traffic risk this prompt implies**, if any (a link going viral, a vote surge) — naming it now is what makes the pitfall scan below targeted, not generic.
- **Non-goals** — state what you're NOT building, so scope reads as deliberate.

### Default architecture: "one box, clean seams"

```
[React SPA] --HTTP/JSON--> [FastAPI monolith] --> [Postgres]
                                  |
                                  +--> [Redis: cache-aside for hot reads]
                                  +--> [Redis: pub/sub for fan-out, if the prompt needs live updates]
```

Postgres + Redis are provisioned from minute one via `docker-compose.yml` (§4), not swapped in later. This wins in a 2-hour format: one deployable, nothing between-your-own-services to debug, and every "how would you scale this" question has a crisp answer (§3) because the seams (repository, cache, pub/sub) already exist in the code. Do **not** start with microservices, message queues, or multi-region — that costs build time you don't have and reads as a red flag here, not a strength.

**Start from the simplest version that satisfies the goals above — simple designs scale further than expected, and it's the only version you can finish.** Add complexity only because the pitfall scan below finds a real, cheap-to-fix risk — never because it seems "more correct."

### Pitfall scan — before writing any code

Check the simple design against this list. Tag each **build it** (cheap, minutes, clearly implied by the prompt) or **mention it** (real, but a §3 talking point, not worth the build time) — don't blanket-apply the whole list, that's scope creep in the other direction. Doing this now turns real risks into one-line changes instead of mid-build rewrites.

| Risk | Default call |
|---|---|
| **Single point of failure** — one app/DB/cache process | **Mention it.** App is already stateless, so horizontal scaling behind a load balancer is a config change; managed Postgres/Redis with failover is the prod answer. Don't build HA in 2 hours. |
| **Spiky/bursty traffic** on a specific endpoint the prompt implies (viral link, vote surge) | **Build it** if there's a genuinely hot endpoint: rate limiting (Decorator, ~10-15 min) + make sure that read path uses the cache-aside. Otherwise **mention it** — don't rate-limit everywhere speculatively. |
| **Write races** — duplicate unique values, double-vote/booking, read-modify-write counters | **Build it** wherever the prompt has one: a DB unique constraint + conflict handling, or an atomic `UPDATE ... SET n = n + 1` instead of read-then-write. This is a correctness bug, not just a scaling nicety. |
| **Unbounded list growth** — no pagination on a real list feature | **Build it**: basic `limit`/`offset`. Cheap now, awkward to bolt on live later. |
| **Missing index** on any non-PK lookup (by owner, code, status) | **Build it** — one `CREATE INDEX` line, preempts the "scale the DB" question being a real bug. |
| **Trusting client input** for IDs/prices/ownership | **Build it**: generate/validate server-side (scaffold already does this for `Item.id`). |
| **No idempotency** on a retryable POST | **Build it** only if retries plausibly matter (payments, orders); otherwise **mention it**. |
| **Cache/DB divergence** — no invalidation on write | Already handled (`Cache.invalidate`, §4) — carry the same pattern into any new cached read. |

If the prompt is small with none of the above genuinely in play, say so, keep it simple, and skip straight to §4.

## 2. LLD: SOLID/DRY + patterns, applied pragmatically

**Overriding rule**: use a pattern only when you can name a second variant it needs to accommodate. One implementation behind an interface "for future extensibility" is YAGNI and costs time you need elsewhere.

**SOLID, briefly**: split by *reason to change* — route handler / service / repository are three separate reasons even in a small app; this alone makes the code look professional on a skim. Route handlers depend on an abstraction (`Protocol`/`Depends`), never directly on `psycopg`/`redis` — the highest-value habit here, since it turns "how would you swap X" into "change one function."

**DRY, briefly**: duplication across 2 call sites is fine (rule of three). Never duplicate validation rules, response shapes (Pydantic models), or DB access for one entity (one repository).

**Pattern shortlist** (Python: `typing.Protocol`, no inheritance ceremony):
- **Repository** — use almost always; *the* seam the scaling story leans on, and makes the app testable without a real DB. `app/repository.py`.
- **Strategy** — only with genuinely interchangeable algorithms (e.g. multiple code-gen or ranking rules). Skip if there's only one way to do it.
- **Factory** — branching construction logic (e.g. repo impl by env). A plain function/`Depends` provider usually *is* the factory. `app/deps.py`.
- **Decorator** — cross-cutting concerns (logging, timing, rate-limiting) — just use Python decorators.
- **Observer** — one action fans out to independent side effects, or Redis pub/sub. `app/events.py`.
- **Adapter** — wrap a third-party SDK/API behind your own narrow interface.
- **Avoid**: Abstract Factory, Visitor, Chain of Responsibility, Builder, multi-level hierarchies — cost more typing than clarity here and read as a junior-engineer tell.

**Code layout** (already in §4): `main.py` thin routes → `service.py` business logic (depends only on interfaces) → `repository.py` only place touching Postgres → `cache.py`/`events.py` Redis, wrapped → `models.py` one Pydantic shape per concept → `deps.py` wiring. New feature = new service function; new storage backend = new repository implementation; nothing else changes. That layering *is* the extensibility answer.

## 3. Talking points for common HLD follow-ups

Current state → bottleneck → concrete next step, grounded in the actual code just written, not generic vocabulary.

**Traffic spike / going viral?** Current: single stateless FastAPI process; bottleneck: DB connections/CPU on one box. Next, by effort: (a) horizontal scale — N stateless instances behind a load balancer, works immediately because there's no in-memory session state, (b) cache hot reads, (c) a queue to absorb write bursts async, (d) rate-limit/backpressure at the edge.

**How would you cache this?** Hot read path → cache key = lookup key → TTL or write-through invalidation. Redis from the start (`app/cache.py`) because an in-process cache doesn't stay consistent across N instances. Cache-aside: miss → read DB → populate → return (`Cache.get_or_set`). Mention cache stampede (fix: coalescing or jittered TTL). Live/multi-consumer fan-out → same Redis instance's pub/sub (`app/events.py`) before a dedicated broker.

**Scale the database?** First: indexes + the connection pool already in `PostgresItemRepository`. Second: read replicas — Postgres is already behind a repository interface, so routing reads to a replica is a swap at that seam. Third: sharding, only if asked about very large scale — name the shard key and the cross-shard-query tradeoff; don't volunteer it.

**Consistency / race conditions?** Name the specific race in the actual app (two requests incrementing a counter, double-booking) and the fix: a unique constraint/transaction, `SELECT ... FOR UPDATE`, or an atomic increment — not a vague "add a lock." Strong consistency on core writes, eventual is fine for denormalized reads/counters.

**Reliability?** Idempotency on retryable writes (idempotency key or upsert). Timeouts + backoff on outbound calls. Stateless app so a crashed instance is just replaced.

**Deploy/monitor?** Containerize (Dockerfile, §4), N replicas behind a load balancer (DO App Platform or DO Load Balancer + Droplets), structured logging + `/health` (present), latency/error-rate metrics.

## 4. Scaffold — copy these files verbatim, then adapt

Create this directory layout, paste each block into the named file, then adapt per §4.20. This is a full working FastAPI + Postgres + Redis backend and a React (Vite) frontend, already layered per §2 — it has been installed and its smoke test run successfully.

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

The interview itself runs in Cursor, not Claude Code — this section is the bridge.

### 5.1 Before the interview: port these conventions into Cursor

Cursor reads **Project Rules** — `.mdc` files under `.cursor/rules/`, auto-attached to its chat/agent/Tab context. Create `.cursor/rules/interview-conventions.mdc` ahead of time:

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

Pre-stage the §4 scaffold files too if the format allows a personal template repo (confirm with the interviewer first); if not, recreate the structure quickly from this file — the layering should be a habit going in, not looked up live.

### 5.2 Cursor features worth using live

- **Tab** — always on, free. Best for repetitive shape-following code.
- **Cmd+K** — small, localized, well-specified edits; faster than a chat round-trip for anything scoped to the current selection.
- **Agent/Composer** — initial scaffold generation if not pre-staged, and the §4.20 rename-and-extend pass (paste that checklist into the prompt). Always review the diff — a wrong assumption compounds across files fast.
- **@-mentions** — reference existing code instead of re-pasting it.
- **Checkpoints** — skim the changed-files list after any multi-file edit before moving on.

### 5.3 Use dead time: parallelize research instead of idling

Any time blocked on something other than typing is wasted unless filled: open a second chat tab (or Background Agent) the moment you ask a clarifying question and research what comes next regardless of the answer — don't wait for the reply to start. Batch questions (§0) so idle moments aren't recurring. Queue/write the next file while a slow command runs instead of watching the terminal. Don't let research become its own rabbit hole — pull the one fact needed and get back to building.

### 5.4 What NOT to reach for live

Don't hand-tune Cursor settings/models mid-interview. Don't send Agent mode a large open-ended ask ("build the whole backend") without the specific layering/entity first — an unscoped prompt needs a costly second pass. Don't fight Tab over stylistic preferences that don't matter.

### 5.5 Talking to the interviewer about tool use

Being transparent that you're using Cursor's AI deliberately (Tab for boilerplate, Agent for scoped multi-file changes) is a fair, often positive signal — what matters to them is whether *you* made the architecture/pattern decisions (§1-§3) while the tool accelerated typing.

## 6. Orchestration checklist

1. **Read the prompt** — restate entities/actions in 1-2 sentences, name the time budget/phases (§0) out loud.
2. **Ask, then stop** — §1's batch of clarifying questions, in one shot. Wait for the answer (or explicit "use your judgment") before doing anything below — this is a hard gate, not a formality.
3. **Design (~10 min from here)** — §1: sketch the simplest architecture, state goals/non-goals, run the pitfall scan. Stop as soon as you have it.
4. **Scaffold (~5 min)** — §4: copy files in, start Postgres+Redis, get both dev servers running before writing custom code. Confirm `/health` and the frontend root load — catching a broken toolchain now costs 2 minutes, at minute 90 it costs the interview.
5. **Backend (~45-50 min)** — §4.20 adapt pass + §2 judgment. Test each endpoint as you finish it. Checkpoint: by the midpoint, core flows reachable via `curl`/`/docs` even before the frontend exists.
6. **Frontend (~30-40 min)** — golden path > loading/error > (no) polish, per §0's zero-CSS rule.
7. **Defense prep (~10-15 min, can overlap)** — §3's answers ready, grounded in the code just written.
8. **Final pass (~10 min)** — exercise the golden path in the browser, confirm both servers start clean from a fresh terminal, have a one-sentence close ready: what's built, what's out of scope and why, first three next steps.

**Boundaries**: don't let architecture discussion eat build time — lock it in and adjust as you build. Don't introduce infrastructure beyond Postgres+Redis unless asked live. If behind schedule, cut scope before cutting layering/testing habits — a smaller well-structured app outscores a larger messy one.
