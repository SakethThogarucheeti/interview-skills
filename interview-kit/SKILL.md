---
name: interview-kit
description: Self-contained kit for a timed build-and-deploy interview (DigitalOcean's format: 3h, pick from assigned prompts, deploy live before time's up, graded partly on catching AI-introduced race conditions/blocking calls rather than trusting them). Hard-gates one batched round of clarifying questions before any code, then commits to building without reopening it. Once design is locked, spawns a subagent to write design-decisions.md (HLD, LLD choices, pitfall-scan results, scaling and business-tradeoff notes) since the user, not the agent, answers the post-build walkthrough. Covers requirements/goal-scoping, a pitfall scan (SPOF, spiky traffic, write races, blocking async calls, missing indexes/pagination) re-run against every AI-generated diff, HLD talking points, SOLID/DRY/GoF LLD patterns, a complete copy-paste FastAPI+Postgres+Redis+React scaffold (every file inlined below), a DigitalOcean deployment section, a Cursor workflow bridge, and time-compression/git-discipline tactics throughout. Use as soon as the user shares the interview prompt and wants to build, asks about this interview's system design/scaling questions, wants the scaffold, needs to deploy to DigitalOcean, or asks about using Cursor for it. Everything needed lives in this one file — no other skill or template directory required.
---

# Interview kit — timed full-stack build

One file, no GitHub dependency: requirements → design → LLD → scaffold code (inlined below) → Cursor workflow → deployment → verbal defense. Prep/rehearse here; the actual build runs in Cursor (§5) unless told otherwise.

**Format** (DigitalOcean's confirmed shape): a 3-hour session, pick from a short list of assigned prompts, build it, deploy it live on DigitalOcean before time's up (§4.21) — then a walkthrough of design trade-offs and hypotheticals on scaling, traffic spikes, downtime, and business constraints. The user, not the agent, answers that walkthrough, so hand off a `design-decisions.md` for them to study (§1).

**Priority order**: working, deployed demo > code that looks deliberately structured on a skim > sharp answers to those questions. Working-but-plain beats brilliant-but-unfinished; undeployed beats nothing.

**What's actually graded**: DigitalOcean's own hiring writeup says they watch where you lean on AI (boilerplate — fine) vs. what you check by hand (concurrency, blocking calls) — prompts are deliberately structured so naive AI output confidently introduces a race condition or a blocking call, to see if you catch it. Audit every AI-generated chunk against §1's pitfall scan before accepting it — that audit *is* the interview.

## 0. Time-compression tactics (apply throughout)

The real enemy in a 3-hour window is idle/serial time, not typing speed — and a portion of it now has to include a working deployment, so there's less slack than "3 hours" sounds like.

- **Ask once, then move on.** Clarifying questions (§1) are a hard gate — batch them into one shot, wait for the answer, don't implement before it. But it's one gate, not a habit: once answered, decide every remaining gap yourself and build.
- **Fill dead time, never idle.** The moment a question is asked, fire a parallel task on what you'll need next — Claude Code: a `fork`/background Agent; Cursor: a second chat tab or Background Agent (§5.3). This fills the wait, it doesn't replace it — still don't build on an assumed answer.
- **Decide, don't deliberate.** Default any choice that doesn't change the outcome; only ask what changes scope.
- **Timeout everything; log anything backgrounded.** A hung command with no timeout eats the clock silently; a slow one with no log forces you to babysit it. Wrap anything that could hang (installs, network/DB calls) in a timeout — the Bash tool's own parameter in Claude Code, or shell `timeout <n>s <cmd>` in Cursor. Redirect backgrounded processes (`uvicorn`, `npm run dev`, `docker compose up`) to a log file (`... > /tmp/x.log 2>&1 &`) so progress is checkable with `tail`/`grep` instead of blocking on it. Scope greps/finds to the relevant directory (`grep -r pattern app/`), never the repo root — crawling `node_modules`/`.venv`/`.git` wastes real time for zero signal.
- **Zero CSS.** No framework, no stylesheet, nothing beyond the scaffold's inline styles — hard rule from the start.
- **Use git, committed at every milestone and passing test.** `.gitignore` + `git init` before the scaffold goes in (§4.19), then a commit after each milestone/passing test — small and frequent, not one giant commit at the end. Makes a bad edit or a sideways tool call a `git checkout` away, not a rebuild.
- **Budget** (3h default — DigitalOcean's confirmed format, adjust if told otherwise): ~5 min pick the prompt (§1), ~10 min design (§1), ~5 min scaffold copy-in (§4), ~50-60 min backend, ~30-40 min frontend, ~20 min deploy (required, §4.21), ~20 min polish + defense prep (§3), buffer.

## 1. Requirements & HLD (~10 min, don't exceed)

**If given a short list of prompts, pick one first.** Prefer whichever matches a pattern you've prepped ("Likely prompt patterns" below) or, failing that, the smallest, clearest scope — a prompt you can state in one sentence beats an ambiguous one, since ambiguity costs clarifying-question time you don't get back.

**Hard gate: ask before building — once.** The moment the prompt is shared, ask the batch of clarifying questions below in a single message and stop — no scaffolding, no code, until the user answers or says to use your judgment. This is a real stop: no implementation happens between asking and the response. Use dead time (§0) to research while waiting, not to build on assumed answers. Skip only what the prompt already answered.

**Once answered, stop asking and start building.** The gate fires exactly once, not per-decision. After the batch is answered (even partially), decide every remaining gap yourself (§0's "decide, don't deliberate") and move straight to design/build — no second round. Circling back costs more than a wrong default and reads as indecision. Exception: something that would force a visible do-over if guessed wrong (e.g. the prompt is ambiguous between two fundamentally different apps).

Batch every open question; skip only what doesn't change scope, stating that assumption instead. Output a short, explicit goals/non-goals statement — a decision to hold the build to. Cover:
- **Core entities & actions** — create/read/update/delete what?
- **Read vs write ratio** — most prompts (shorteners, polls, task boards, rate limiters) skew read-heavy or write-bursty; name which, it drives the caching story.
- **Consistency** — strong (payments, inventory) or eventual (counts, feeds, likes)? Most prompts tolerate eventual.
- **The specific spiky-traffic risk this prompt implies**, if any — naming it now targets the pitfall scan below.
- **Non-goals** — what you're explicitly not building.
- **What "deployed" means** — backend API only, or the frontend too? Changes the §4.21 deploy plan.

### Default architecture: "one box, clean seams"

```
[React SPA] --HTTP/JSON--> [FastAPI monolith] --> [Postgres]
                                  |
                                  +--> [Redis: cache-aside for hot reads]
                                  +--> [Redis: pub/sub for fan-out, if the prompt needs live updates]
```

Postgres + Redis are provisioned from minute one via `docker-compose.yml` (§4), not swapped in later. One deployable (also the easiest shape to get live on DigitalOcean within budget, §4.21), nothing between-your-own-services to debug, and every "how would you scale this" question has a crisp answer (§3) because the seams already exist. Do **not** start with microservices, message queues, or multi-region — costs build time you don't have and reads as a red flag here, not a strength.

**Start from the simplest version that satisfies the goals above.** Add complexity only because the pitfall scan below finds a real, cheap-to-fix risk — never because it seems "more correct."

### Pitfall scan — before writing any code

Check the simple design against this list. Tag each **build it** (cheap, clearly implied by the prompt) or **mention it** (real, but a §3 talking point) — don't blanket-apply it, that's scope creep the other way.

| Risk | Default call |
|---|---|
| **Single point of failure** — one app/DB/cache process | **Mention it.** Stateless app scales horizontally behind a load balancer as a config change; managed Postgres/Redis with failover is the prod answer. Don't build HA in this window. |
| **Spiky/bursty traffic** on a specific endpoint the prompt implies (viral link, vote surge) | **Build it** if there's a genuinely hot endpoint: rate limiting (Decorator, ~10-15 min) + confirm that read path uses the cache-aside. Otherwise **mention it**. |
| **Write races** — duplicate unique values, double-vote/booking, read-modify-write counters | **Build it** wherever the prompt has one: a DB unique constraint + conflict handling, or an atomic `UPDATE ... SET n = n + 1` instead of read-then-write. A correctness bug, not just a scaling nicety. |
| **Unbounded list growth** — no pagination on a real list feature | **Build it**: basic `limit`/`offset`. Cheap now, awkward to bolt on later. |
| **Missing index** on any non-PK lookup (by owner, code, status) | **Build it** — one `CREATE INDEX` line. |
| **Trusting client input** for IDs/prices/ownership | **Build it**: generate/validate server-side (scaffold already does this for `Item.id`). |
| **No idempotency** on a retryable POST | **Build it** only if retries plausibly matter (payments, orders); otherwise **mention it**. |
| **Cache/DB divergence** — no invalidation on write | Already handled (`Cache.invalidate`, §4) — reuse the pattern for any new cached read. |
| **Blocking calls inside an `async def`** — a sync DB/network call blocks the whole event loop | **Already avoided**: the scaffold's routes/services are plain `def`, so FastAPI runs them in a threadpool safely. If you (or the AI) convert something to `async def`, every call inside must go async too (`asyncpg`, `redis.asyncio`) — never mix. One of the two bugs DigitalOcean is reported to specifically grade for. |

**This table is the audit checklist DigitalOcean is reported to grade on, not just a design-phase exercise.** Prompts are reportedly structured so AI-generated code confidently produces exactly two bugs from this table — a write race or a blocking async call — to see whether you catch them rather than accept the output at face value. Re-run this table against any AI-generated diff, not just at design time.

If the prompt is small with none of the above genuinely in play, say so, keep it simple, and skip to §4.

### Likely prompt patterns (unofficial — third-party-sourced, not confirmed by DigitalOcean; a bonus, not a substitute for the process above)

- **Cloud Resource Quota / Usage Limit Manager** — cap usage against a preset quota. The natural AI-generated bug is the write-race trap above: `check quota, then create` races under concurrency. Fix: one atomic statement — `UPDATE ... SET used = used + 1 WHERE used < limit RETURNING used`, not two steps.
- **High-frequency telemetry / cache with origin-outage resilience** — must keep serving through an origin/DB outage instead of cascading the failure. Extend `app/cache.py`'s `get_or_set`: on loader failure, fall back to the last-known-good cached value (even past TTL), plus a small circuit breaker (stop calling after N failures, retry after a cooldown).

If told which prompt you drew, jump to the matching notes; otherwise the general scaffold and pitfall scan (§1/§2/§4) cover any prompt in this format.

### Once design decisions are locked: hand off a review doc

The moment goals/non-goals, architecture, and the pitfall-scan calls are locked in, spawn a background subagent to write `design-decisions.md` at the project root — the user studies it before the walkthrough (intro), so start this now, not at the end of the build, and don't write it inline yourself; that's foreground time better spent on §4/§4.21.

Give the subagent the locked-in goals/non-goals, architecture, and every pitfall-scan row with its call and reasoning. Have it cover:
- **Goals & non-goals** — what's in scope, and what was deliberately left out and why.
- **Architecture** — the diagram and why it beats the alternatives (microservices, queue, multi-region) at this scope.
- **LLD choices** — which §2 patterns were used, and which were deliberately skipped.
- **Pitfall-scan results** — every risk row, tagged build/mention, one sentence on the actual mitigation.
- **Scaling talking points** — §3's answers, rewritten in first person against the code that actually got built.
- **Business trade-offs** — what was cut for time and what adding it back would take (§3), plus the downtime answer.

Keep it skimmable — bullets over prose, one screen per section. Refresh it as the build deviates from the original design (it will); the §4.21 deploy wait is a natural point to do that.

## 2. LLD: SOLID/DRY + patterns, applied pragmatically

**Overriding rule**: use a pattern only when you can name a second variant it needs to accommodate. One implementation behind an interface "for future extensibility" is YAGNI.

**SOLID, briefly**: split by *reason to change* — route handler / service / repository are three separate reasons even in a small app. Route handlers depend on an abstraction (`Protocol`/`Depends`), never directly on `psycopg`/`redis` — turns "how would you swap X" into "change one function."

**DRY, briefly**: duplication across 2 call sites is fine (rule of three). Never duplicate validation rules, response shapes, or DB access for one entity.

**Pattern shortlist** (Python: `typing.Protocol`, no inheritance ceremony):
- **Repository** — use almost always; the seam the scaling story leans on, and makes the app testable without a real DB. `app/repository.py`.
- **Strategy** — only with genuinely interchangeable algorithms. Skip if there's only one way to do it.
- **Factory** — branching construction logic; a plain function/`Depends` provider usually *is* the factory. `app/deps.py`.
- **Decorator** — cross-cutting concerns (logging, timing, rate-limiting) — just use Python decorators.
- **Observer** — one action fans out to independent side effects, or Redis pub/sub. `app/events.py`.
- **Adapter** — wrap a third-party SDK/API behind your own narrow interface.
- **Avoid**: Abstract Factory, Visitor, Chain of Responsibility, Builder, multi-level hierarchies — cost more typing than clarity here.

**Code layout** (already in §4): `main.py` thin routes → `service.py` business logic (interfaces only) → `repository.py` only place touching Postgres → `cache.py`/`events.py` Redis, wrapped → `models.py` one Pydantic shape per concept → `deps.py` wiring. New feature = new service function; new storage backend = new repository implementation. That layering *is* the extensibility answer.

## 3. Talking points for common HLD follow-ups

Current state → bottleneck → concrete next step, grounded in the actual code just written, not generic vocabulary.

**Traffic spike / going viral?** Current: single stateless FastAPI process; bottleneck: DB connections/CPU on one box. By effort: (a) horizontal scale — N stateless instances behind a load balancer, works immediately since there's no in-memory session state, (b) cache hot reads, (c) a queue to absorb write bursts async, (d) rate-limit/backpressure at the edge.

**How would you cache this?** Hot read path → cache key = lookup key → TTL or write-through invalidation. Redis from the start (`app/cache.py`) since an in-process cache doesn't stay consistent across N instances. Cache-aside: miss → read DB → populate → return (`Cache.get_or_set`). Mention cache stampede (fix: coalescing or jittered TTL). Fan-out → same Redis instance's pub/sub (`app/events.py`) before a dedicated broker.

**Scale the database?** First: indexes + the connection pool already in `PostgresItemRepository`. Second: read replicas — Postgres is already behind a repository interface, so routing reads to a replica is a swap at that seam. Third: sharding, only if pushed on very large scale — name the shard key and the cross-shard-query tradeoff.

**Consistency / race conditions?** Name the specific race in the actual app (counter increment, double-booking) and the fix: a unique constraint/transaction, `SELECT ... FOR UPDATE`, or an atomic increment — not a vague "add a lock." Strong consistency on core writes, eventual is fine for denormalized reads/counters.

**Reliability?** Idempotency on retryable writes (idempotency key or upsert). Timeouts + backoff on outbound calls. Stateless app so a crashed instance is just replaced.

**Deploy/monitor?** Already done by the time it's asked (§4.21) — describe what you built: containerized (Dockerfile, §4), live on a DO Droplet/App Platform, structured logging + `/health`. Next step if pushed: N replicas behind a load balancer, latency/error-rate metrics, managed Postgres/Redis with failover.

**Business trade-offs / "what would you do with more time" / downtime windows?** Expect this alongside the technical questions — DigitalOcean's writeup frames the post-build conversation as covering both. Ground it in what you actually cut: e.g. "I skipped read replicas and HA — no payoff at this scale, and the repository seam means adding one later is a config change, not a rewrite" (§2). For downtime: stateless app instances mean a rolling restart has zero downtime; a single non-replicated Postgres/Redis is the one real SPOF, and the honest answer is a maintenance window or a managed failover DB, not built here for time. Don't oversell what you didn't build — naming the real gap and its cost/benefit reads better than pretending it's handled.

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
cat > .gitignore <<'EOF'
.venv/
node_modules/
__pycache__/
*.pyc
.env
EOF
git init && git add -A && git commit -m "Scaffold from interview-kit"
cd backend && timeout 120 python -m venv .venv && source .venv/bin/activate \
  && timeout 180 pip install -r requirements.txt > /tmp/pip-install.log 2>&1
cd ../frontend && timeout 180 npm install > /tmp/npm-install.log 2>&1
```
Then, all backgrounded/parallel, each logged so progress is checkable without blocking:
```bash
# from backend/
docker compose up -d          # postgres:5432, redis:6379 -- already detached, no log needed
uvicorn app.main:app --reload --port 8000 > /tmp/uvicorn.log 2>&1 &
# from frontend/
npm run dev > /tmp/vite.log 2>&1 &
```
Check readiness with `tail -f /tmp/uvicorn.log` / `curl localhost:8000/health` instead of guessing. If Docker isn't available, point `DATABASE_URL`/`REDIS_URL` (see `deps.py`) at whatever Postgres/Redis instance is provided instead.

### 4.20 Adapt to the actual prompt (rename-and-extend, not a rewrite)

1. **`models.py`** — rename `Item`/`ItemCreate`/`ItemUpdate` to the real entity, change fields. Add a second entity module the same shape if the prompt has more than one resource.
2. **`repository.py`** — rename the Protocol and classes, update the `CREATE TABLE`/SQL to the real schema, add query methods the prompt needs — keep them on the repository, not scattered in routes.
3. **`service.py`** — the prompt's actual business rules live here. Drop the cache-aside call on `get_item` if the read pattern doesn't warrant it.
4. **`main.py`** — rename routes, add any non-CRUD endpoints the prompt needs.
5. **`api.js`** — rename client methods to match.
6. **`App.jsx`** — replace the list/create UI with whatever view the prompt needs; keep the inline-styles-only rule.

**Don't change unless required**: the repository/service/route layering; `PostgresItemRepository` as live default + `InMemoryItemRepository` for tests (`APP_ENV=test`); the CORS/proxy setup; whether `EventPublisher`/`EventSubscriber` get wired in.

**Fast wins if time allows, in order**: extend `test_smoke.py` for the real entity → `/health` already present → `Dockerfile`/`docker-compose.yml` already present → keep the frontend's loading/error states, don't strip them.

### 4.21 Deploy to DigitalOcean — required, ~20 min, do this with time to spare

DigitalOcean's format requires the prototype live on their platform before the session ends — not just running locally. Fastest reliable path: one Droplet running the whole stack via Docker Compose, reusing `docker-compose.yml` (§4.3) plus one added service.

```bash
# One-time, from your local machine (doctl already authenticated: `doctl auth init`)
timeout 300 doctl compute droplet create interview-app \
  --image docker-20-04 --size s-1vcpu-2gb --region nyc3 \
  --ssh-keys <your-key-fingerprint> --wait --format ID,PublicIPv4 \
  | tee /tmp/droplet-create.log

# Ship the code (run from the project root)
timeout 120 rsync -av --exclude node_modules --exclude .venv --exclude __pycache__ \
  ./ root@<droplet-ip>:/root/app/ > /tmp/rsync.log 2>&1
```

Add the backend as a third service in `backend/docker-compose.yml` (append, don't replace `postgres`/`redis`):
```yaml
  app:
    build: .
    ports:
      - "80:8000"
    environment:
      DATABASE_URL: postgresql://postgres:postgres@postgres:5432/app
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - postgres
      - redis
```
```bash
timeout 240 ssh root@<droplet-ip> "cd /root/app/backend && docker compose up -d --build" \
  > /tmp/deploy-build.log 2>&1
timeout 10 curl http://<droplet-ip>/health   # confirm {"status":"ok"} before calling it done
```
If the build is still running at the timeout, check `cat /tmp/deploy-build.log` (or `ssh root@<droplet-ip> "docker compose logs --tail 50"`) rather than re-running blind.

For the frontend, if the interviewer expects it live too: point `frontend/vite.config.js`'s API proxy at `http://<droplet-ip>` and either build + serve the static output from the same Droplet (a tiny `nginx`/`serve` container) or run it locally against the deployed API — whichever §1's clarifying batch settled on. A deployed-but-broken app is worse than none, since it's the last thing the interviewer sees — always verify `/health` and one real request before defense prep.

If a GitHub repo and DO Container Registry are already set up, App Platform (`doctl apps create --spec app.yaml` against a pushed image) is the on-brand alternative — use whichever you can execute fastest; the Droplet route just has the fewest moving pieces to fail.

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

React SPA -> FastAPI -> Postgres, with Redis for cache-aside on hot reads and
optionally pub/sub for fan-out. No microservices, message broker, or
multi-region -- talking points, not build tasks, here.

Layering (do not collapse): main.py routes (thin) -> service.py (business
logic, depends only on repository/cache Protocols) -> repository.py (only
place touching Postgres) -> cache.py/events.py (Redis, wrapped) ->
models.py (one Pydantic shape per concept) -> deps.py (wiring).

Apply the Repository pattern to every entity by default. Reach for Strategy,
Factory, Observer, Decorator, or Adapter only with two genuinely
interchangeable implementations to justify it -- no interface with one
implementation "for future extensibility."

Every new endpoint gets a smoke test using an in-memory repository via
APP_ENV=test, so tests never need live Postgres/Redis.

Frontend: plain React + fetch via a single api.js client, one function per
endpoint. Golden path > loading/error states > visual polish. Do NOT add a
CSS framework, stylesheet, or custom colors/typography -- inline styles
only, hard rule.

Timed build: no large refactors, no extra dependencies, no gold-plating.
When a decision doesn't change the outcome, make it and move on. Never
leave the editor/chat idle -- if a question is pending or a command is
running, use a second chat thread for research that unblocks the next step.

The prototype must be deployed live on DigitalOcean before the session
ends -- hard requirement, not a stretch goal. Budget time for it up front.

Do not accept AI-generated code at face value. Before moving on from any
generated chunk, check it for a check-then-act write race (should be one
atomic DB statement) and a blocking sync call inside an async def (route
handlers here are plain def on purpose so sync psycopg/redis calls are
safe -- never mix). Catching these two is reported to be specifically what's
graded.

Every command gets a timeout -- a hung install or network call should fail
loud, not eat the clock silently. Anything backgrounded (uvicorn, npm run
dev, docker compose) redirects output to a log file so progress is
checkable with tail/grep instead of blocking on it. Scope greps/finds to
the relevant directory, never the whole repo root.

Use git. Add a .gitignore (.venv/, node_modules/, __pycache__/, *.pyc, .env)
before the first commit, then commit at every milestone and every passing
test -- scaffold in, each adapted file, each green test run, backend done,
frontend done, deployed. Small frequent commits, not one at the end.
```

Pre-stage the §4 scaffold files too if the format allows a personal template repo (confirm with the interviewer first); if not, recreate the structure quickly from this file — the layering should be a habit going in, not looked up live.

### 5.2 Cursor features worth using live

- **Tab** — always on, free. Best for repetitive shape-following code.
- **Cmd+K** — small, localized, well-specified edits; faster than a chat round-trip.
- **Agent/Composer** — initial scaffold generation if not pre-staged, and the §4.20 rename-and-extend pass. Always review the diff — a wrong assumption compounds across files fast.
- **@-mentions** — reference existing code instead of re-pasting it.
- **Checkpoints** — skim the changed-files list after any multi-file edit before moving on.

### 5.3 Use dead time: parallelize research instead of idling

Any time blocked on something other than typing is wasted unless filled: open a second chat tab (or Background Agent) the moment you ask a clarifying question and research what comes next regardless of the answer. Batch questions (§0) so idle moments aren't recurring. Queue/write the next file while a slow command runs instead of watching the terminal. Don't let research become its own rabbit hole.

### 5.4 What NOT to reach for live

Don't hand-tune Cursor settings/models mid-interview. Don't send Agent mode a large open-ended ask without the specific layering/entity first — an unscoped prompt needs a costly second pass. Don't fight Tab over stylistic preferences that don't matter.

### 5.5 Talking to the interviewer about tool use

Being transparent that you're using Cursor's AI deliberately (Tab for boilerplate, Agent for scoped multi-file changes) is a fair, often positive signal — what matters is whether *you* made the architecture/pattern decisions (§1-§3) while the tool accelerated typing.

## 6. Orchestration checklist

1. **Pick the prompt, if given a list** — §1: favor a prepped pattern or the smallest clear scope.
2. **Read the prompt** — restate entities/actions in 1-2 sentences, name the time budget (§0) out loud.
3. **Ask once, then stop asking** — §1's batch of clarifying questions, in one shot. Wait for the answer (or explicit "use your judgment") before doing anything below — then don't reopen it.
4. **Design (~10 min)** — §1: sketch the simplest architecture, state goals/non-goals, run the pitfall scan. The moment this is locked in, spawn the background subagent that writes `design-decisions.md` — don't wait for it, move to scaffolding.
5. **Scaffold (~5 min)** — §4: copy files in, add `.gitignore` + `git init` + commit (§4.19), start Postgres+Redis, get both dev servers running. Confirm `/health` and the frontend root load. Commit again once it all works.
6. **Backend (~50-60 min)** — §4.20 adapt pass + §2 judgment. Test each endpoint as you finish it. Before accepting any AI-generated chunk, check it against §1's pitfall table, especially the write-race and blocking-call rows — that check is what's graded. Commit after each adapted file and after every passing `test_smoke.py` run.
7. **Frontend (~30-40 min)** — golden path > loading/error > (no) polish, per §0's zero-CSS rule. Commit once the golden path works end-to-end.
8. **Deploy (~20 min, required)** — §4.21: get it live on DigitalOcean, verify `/health` and one real request from outside your machine. Not optional. Commit once verified live.
9. **Defense prep (~15-20 min, can overlap with deploy waits)** — refresh `design-decisions.md` against what actually got built, then read through it — that's the user's prep, since the user answers the walkthrough, not the agent.
10. **Final pass (~10 min)** — exercise the golden path against the deployed URL, confirm both servers start clean from a fresh terminal, have a one-sentence close ready: what's built, what's out of scope and why, first three next steps.

**Boundaries**: don't let architecture discussion eat build time — lock it in and adjust as you build. Don't introduce infrastructure beyond Postgres+Redis unless asked live. If behind schedule, cut scope before cutting layering/testing habits or the deployment step — a smaller, well-structured, actually-deployed app outscores a larger messy or undeployed one.
