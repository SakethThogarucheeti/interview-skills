---
name: fastapi-react-scaffold
description: Ready-to-copy FastAPI backend + React (Vite) frontend starter, using Postgres for storage and Redis for caching/pub-sub, pre-structured with the repository/service/route layering from lld-design-patterns, for shipping a working full-stack app in under an hour during a timed build interview. Use when the user is starting to write code for a timed full-stack interview build (e.g. DigitalOcean's format) and needs a working skeleton fast, or asks to scaffold/bootstrap a FastAPI+React app. Pairs with hld-interview-design (what to build), lld-design-patterns (why the layers are shaped this way), and cursor-interview-workflow (using this scaffold inside Cursor).
---

# FastAPI + React rapid scaffold

A copy-and-adapt starting point so the first 15 minutes of a timed build go to *renaming things to match the actual prompt*, not to boilerplate. The templates already encode the repository/service/route layering from `lld-design-patterns`, the "one box, clean seams" architecture from `hld-interview-design`, and use Postgres + Redis directly (the user's actual interview stack — not toy substitutes) — don't re-derive that structure from scratch live, copy it and adapt.

Stack: FastAPI, Postgres (via `psycopg` + a connection pool, no ORM), Redis (cache-aside for hot reads, pub/sub available for fan-out/live-update needs), React (Vite, plain JS).

## When to use this vs. writing from scratch

Use it whenever the interview prompt is a CRUD-shaped resource with a frontend (the overwhelming majority of "build an app in 2 hours" prompts: a shortener, a task board, a poll app, a bookmarking tool, a chat log, a rate limiter with a dashboard, etc.). Skip straight to custom code only if the prompt is fundamentally not CRUD (e.g. a pure algorithm/CLI tool with no persistence or UI) — then just use `lld-design-patterns` for structure.

## 0. Copy the templates

The templates live under this skill's `templates/` directory (`backend/` and `frontend/`). At the start of the interview:

```bash
cp -r <this-skill-dir>/templates/backend  <project-dir>/backend
cp -r <this-skill-dir>/templates/frontend <project-dir>/frontend
cd <project-dir>/backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cd <project-dir>/frontend && npm install
```

Start Postgres + Redis (the `docker-compose.yml` in `backend/` spins up both with the exact defaults `app/deps.py` expects — no config needed), then both dev servers, all in parallel/backgrounded so every change is visible immediately instead of context-switching later:
```bash
# from backend/
docker compose up -d          # postgres:5432, redis:6379
uvicorn app.main:app --reload --port 8000
# from frontend/
npm run dev
```
If Docker isn't available in the interview environment, point `DATABASE_URL`/`REDIS_URL` env vars (see `app/deps.py`) at whatever Postgres/Redis instance is provided instead.

## 1. Adapt to the actual prompt (the bulk of your time)

The templates model one generic `Item` entity with full CRUD. Adapting is a rename-and-extend exercise, not a rewrite:

1. **`backend/app/models.py`** — rename `Item`/`ItemCreate`/`ItemUpdate` to the real entity (e.g. `Link`, `Task`, `Poll`), and change the fields. Add a second entity file the same shape if the prompt has more than one resource (e.g. `Poll` + `Vote`).
2. **`backend/app/repository.py`** — rename the Protocol and `InMemory*`/`Postgres*` classes to match, and update the `CREATE TABLE`/SQL to the real schema. Add any query methods the prompt actually needs (e.g. `get_by_owner`, `increment_count`) — keep them on the repository, not scattered in routes.
3. **`backend/app/service.py`** — this is where the prompt's actual business rules live (uniqueness checks, state transitions, computed fields). Keep it depending only on the repository Protocol and the `Cache` wrapper, never on `psycopg`/`redis` directly. Adjust or drop the cache-aside call on `get_item` if the prompt's read pattern doesn't warrant it (§3 of `hld-interview-design` — cache the actual hot path, not every read by default).
4. **`backend/app/main.py`** — rename routes/paths to match the resource, add any non-CRUD endpoints the prompt needs (e.g. `GET /r/{code}` for a redirect, `POST /polls/{id}/vote`).
5. **`frontend/src/api.js`** — rename the client methods to match the renamed endpoints.
6. **`frontend/src/App.jsx`** — replace the generic list/create UI with whatever view the prompt actually needs. Keep the same data-fetching shape (`useEffect` + refresh function) unless the prompt needs something structurally different (e.g. a redirect page, a live-updating poll result). Keep the existing inline styles as-is — don't add a stylesheet, CSS framework, or spend time on visual design; see `interview-rapid-build`'s zero-CSS rule.

## 2. What NOT to change unless the prompt requires it

- The repository/service/route layering — this is the extensibility story, don't collapse it under time pressure even for a "simple" prompt; it costs almost nothing to keep and it's what makes your code look deliberately designed rather than improvised.
- `PostgresItemRepository` as the live default and `InMemoryItemRepository` as the test-only implementation (selected by `APP_ENV=test` in `deps.py`) — this split is what lets `test_smoke.py` run with zero live services while the demo runs against real Postgres/Redis.
- CORS/proxy setup — it's already wired (Vite proxies `/api` to `:8000`, backend has permissive CORS as a demo-only stance you should be ready to caveat verbally).
- The cache-aside pattern in `Cache.get_or_set` / the pub-sub wrapper in `events.py` — only wire `EventPublisher`/`EventSubscriber` in if the prompt needs live/multi-consumer fan-out (e.g. live results, notifications); most CRUD prompts only need the cache, not pub/sub.

## 3. Fast wins if time allows (in priority order)

1. `test_smoke.py` — already covers the golden path against `InMemoryItemRepository` (run with `APP_ENV=test pytest`, no live Postgres/Redis needed); extend it for the real entity. A green test run in the last 10 minutes is a strong signal to an interviewer watching you work.
2. A `/health` endpoint (already present) — mention it maps to the "how would you monitor this" talking point from `hld-interview-design`.
3. `Dockerfile` + `docker-compose.yml` (already present) — have them ready to show even if you don't containerize the frontend; it's evidence you're thinking about deployment, not just code.
4. Basic loading/error states in the frontend (already present in `App.jsx`) — don't strip these out when adapting, they're cheap and make the demo look finished rather than fragile.

## 4. Closing the loop

Before declaring done: actually exercise the app in the browser (create/read/update/delete through the UI, not just `curl`), and re-read `hld-interview-design`'s talking-points section so your scaling/reliability answers are ready before the interviewer asks — don't improvise those live if you don't have to.
