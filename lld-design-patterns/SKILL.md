---
name: lld-design-patterns
description: Low-level/code-level design for a timed build interview — applies SOLID and DRY pragmatically and reaches for the small set of GoF patterns (Strategy, Factory, Repository, Observer, Decorator, Adapter) that pay for themselves in a ~2-hour build, in Python/FastAPI. Use when structuring backend code during a timed interview build, when asked "where would you use a design pattern here," or when translating an HLD architecture (see hld-interview-design) into an actual class/module layout. Pairs with hld-interview-design (the system-level design this implements) and fastapi-react-scaffold (the running template this structures).
---

# LLD for timed build interviews (Python/FastAPI)

Goal: code that is obviously well-structured to a reviewer skimming it for 5 minutes, without spending interview time on abstractions the app doesn't need yet. Every pattern below has a **"use it when / skip it when"** — the failure mode this skill guards against is not "too little structure," it's *pattern soup in a 2-hour app*, which reads worse than plain code.

## 0. The rule that overrides every pattern below

Apply a pattern only when you already have (or can name) a second variant it needs to accommodate. One implementation behind an interface "for future extensibility" that you can't name a second case for is YAGNI, not good design — and it costs you typing time you need elsewhere. The interviewer's actual signal here is: *did you put a seam at the place that will obviously change* (e.g. storage backend, notification channel, pricing rule), not *did you use every pattern you know*.

## 1. SOLID, applied pragmatically

- **Single Responsibility**: split by *reason to change* — a route handler function, a service/use-case function, a repository/data-access function are three different reasons to change, so they're three different functions/classes even in a small app. This alone is 80% of what makes an interview codebase look professional in a skim.
- **Open/Closed**: only where you already identified a variation point (see §2). Don't preemptively make everything a subclass.
- **Liskov Substitution**: if you do use inheritance/protocols for a variation point, every implementation must be swappable without the caller knowing which one it got — enforce this by having the caller depend only on the interface/Protocol, never on a concrete subclass's extra methods.
- **Interface Segregation**: keep your Protocols/ABCs narrow (e.g. a `Notifier` with just `send(message)`, not a fat interface with unrelated methods). Small interfaces are also just faster to fake in a stub if you get to testing.
- **Dependency Inversion**: route handlers depend on an abstraction (a Protocol/ABC or just a function passed in / injected via FastAPI's `Depends`), never directly on a concrete DB client or third-party SDK call buried inside business logic. This is the single highest-value habit for this format — it's what makes your "how would you swap Postgres for X" answer be "change one function" instead of "rewrite the app."

## 2. DRY, applied pragmatically

Duplication across 2 call sites is fine and often clearer than a premature abstraction (rule of three — see `refactoring-process` if installed). What you must not duplicate, even once:
- Validation/business rules (e.g. "a username must be unique" checked in two different handlers) — one source of truth, always.
- The shape of a response — use Pydantic models, not hand-built dicts in multiple places.
- DB access for the same entity — one repository/module per entity, not raw queries scattered across route handlers.

## 3. The pattern shortlist (Python/FastAPI-flavored)

Use `typing.Protocol` for interfaces in Python — it's structural typing, no inheritance ceremony, fast to write under time pressure.

### Repository pattern — use almost always
Isolates persistence behind an interface so route/service code never imports a DB driver directly.
```python
from typing import Protocol

class LinkRepository(Protocol):
    def get(self, code: str) -> Link | None: ...
    def save(self, link: Link) -> None: ...

class PostgresLinkRepository:
    def __init__(self, pool): self.pool = pool
    def get(self, code): ...   # real SQL via the pool
    def save(self, link): ...  # real SQL via the pool

class InMemoryLinkRepository:
    """Test-only stand-in -- see fastapi-react-scaffold's deps.py for the
    APP_ENV=test switch that wires this in instead of Postgres."""
    def __init__(self): self._data: dict[str, Link] = {}
    def get(self, code): return self._data.get(code)
    def save(self, link): self._data[link.code] = link
```
Why here: it's *the* seam the HLD scaling story leans on ("add a read replica / connection pool tuning" = change inside `PostgresLinkRepository`, not touch the routes), and it makes the app trivially testable without a real DB (`InMemoryLinkRepository` in tests). Wire the concrete choice via FastAPI's `Depends`.

### Strategy pattern — use when there are genuinely interchangeable algorithms/rules
E.g. multiple ways to generate a short code (random vs. hash-based), multiple pricing/ranking rules, multiple auth strategies.
```python
class CodeGenerator(Protocol):
    def generate(self, url: str) -> str: ...

class RandomCodeGenerator:
    def generate(self, url: str) -> str: return secrets.token_urlsafe(6)

class HashCodeGenerator:
    def generate(self, url: str) -> str: return hashlib.sha256(url.encode()).hexdigest()[:8]
```
Skip it if there's genuinely only one way to do the thing and no one asked about alternatives — don't invent a second strategy just to justify the pattern.

### Factory pattern — use when object construction has real branching logic
E.g. picking a notification channel implementation based on config/environment, or constructing the right repository implementation (in-memory for tests, SQL for real) based on an env var. A plain `if`/`match` returning the right object, or a FastAPI `Depends` provider function, usually *is* the factory — you rarely need a dedicated Factory *class* in an app this size.
```python
def get_link_repository(settings: Settings = Depends(get_settings)) -> LinkRepository:
    if settings.env == "test":
        return InMemoryLinkRepository()
    return PostgresLinkRepository(get_pool(settings.database_url))
```

### Decorator pattern — use for cross-cutting concerns on functions/handlers
Logging, timing, rate-limiting, auth checks. Python decorators are the natural fit — you likely want this regardless of whether you narrate it as "the Decorator pattern":
```python
def rate_limited(max_per_minute: int):
    def wrap(fn):
        @wraps(fn)
        async def inner(*args, **kwargs):
            ...  # check + raise HTTPException(429) if exceeded
            return await fn(*args, **kwargs)
        return inner
    return wrap
```

### Observer pattern — use when one action should trigger multiple independent side effects
E.g. "on user signup: send welcome email AND log analytics event AND provision a default resource" — decouple the triggering code from the list of reactions.
```python
class EventBus:
    def __init__(self): self._handlers: dict[str, list[Callable]] = defaultdict(list)
    def subscribe(self, event: str, handler: Callable): self._handlers[event].append(handler)
    def publish(self, event: str, payload): 
        for h in self._handlers[event]: h(payload)
```
This is also your answer to "how would this become async/event-driven at scale" — today `publish` calls handlers in-process; the seam is swapping it for a real queue publish.

### Adapter pattern — use when wrapping a third-party SDK/API
Wrap the DigitalOcean API, a payment provider, an email service, etc. behind your own narrow interface so your business logic doesn't import the SDK directly, and so you can fake it in a demo without real credentials.

### Patterns to actively avoid reaching for in this format
Abstract Factory, Visitor, Chain of Responsibility, Builder (unless an object genuinely has 5+ optional constructor params — Pydantic models already solve most of what Builder solves in Python), and any pattern requiring a class hierarchy more than one level deep. These cost more typing time than they buy clarity at this scale, and reviewers reading interview code read over-use of GoF ceremony as a junior-engineer tell, not a senior one.

## 4. What "good LLD" looks like when the interviewer skims your code

- `routers/` or route functions: thin — parse request, call a service function, return response. No business logic, no direct DB calls.
- `services/` or plain functions: business logic and orchestration, depends only on repository/adapter interfaces (never concrete DB/SDK clients).
- `repositories/`: the only place that talks to the DB.
- `models.py`: Pydantic models for request/response, plus your domain dataclasses — one definition of each shape, reused everywhere (DRY).
- `main.py`: wiring — FastAPI app, `Depends` providers choosing concrete implementations.

This layering *is* the LLD answer to "how is this extensible" — new feature = new service function using existing repository interfaces; new storage backend = new repository implementation; nothing else changes.
