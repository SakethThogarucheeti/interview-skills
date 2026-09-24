<!-- interview-kit reference file; § numbers match the index in ../SKILL.md -->

## 4. Scaffold — `scaffold/`, copy it in, then adapt

The code lives in **`scaffold/`**, beside `SKILL.md` (e.g. `~/.claude/skills/interview-kit/scaffold/`, or `interview-kit/scaffold/` in the repo). Copy the whole tree into the empty project root, dotfiles included, and adapt per §4.18:
```bash
cp -R <skill-dir>/scaffold/. .       # the trailing /. copies .github/ .do/ .cursor/ .gitignore too
./strip-ingest.sh                    # ONLY if the prompt is not ingestion/processing (removes §4.20)
rm -rf frontend                      # unless §1 said a UI is required (§4.16)
```
Read a file when you're about to change it or explain it, not up front: the map below says what each one owns. It's a production-shaped FastAPI + Postgres + Redis REST API, layered per §2, with each rubric line covered:
- **Engineering quality:** env config, validation bounds, one error envelope, no HTTP types in the service.
- **Testing:** API, unit and concurrency-regression tests, all runnable with no infrastructure.
- **Automation:** Makefile, lint/format, CI that auto-deploys every push to `main` to DigitalOcean pinned to its commit (§4.21), infrastructure as code (Terraform + App Platform spec, §4.23).
- **Operational excellence:** JSON logs with request IDs, Prometheus `/metrics`, `/health` vs `/ready`, graceful shutdown, Redis failures degrade to a cache miss, non-root container, deploy mode that keeps the DB off the internet, and every build stamped with its git SHA (`/version`, response header, logs, metric) so "which commit is live?" takes 5 seconds (§4.24).

**Verified end-to-end**: lint clean; 13 base tests + 4 add-on tests pass with no infrastructure, both with and without `strip-ingest.sh` (whose output was diffed against the verified base). The integration test runs 8 concurrent workers against real Postgres and processes 40 contended batches exactly once; removing `SKIP LOCKED` makes it fail 3/3 runs. The prod-mode compose stack came up healthy, and every endpoint was exercised with curl. A Redis outage returns `degraded` and keeps serving; a Postgres outage returns a clean 503 and recovers on restart. The worker stops cleanly on SIGTERM. Version stamping was checked on a prod-mode stack built from a real commit: `/version`, `x-app-version`, `app_build_info` and the image's OCI label all equal the SHA, and `make deployed` reports up to date, then lists the exact undeployed commit after a new one. API + worker starting together on a fresh database used to crash on concurrent `CREATE TABLE` (10/10 runs); the schema advisory lock fixed it (0/10). `infra/main.tf` passes `terraform validate`, `.do/app.yaml` passes DigitalOcean's OpenAPI schema (except documented fields the schema omits), and the workflow passes `actionlint`. **Not executed here (no DO account):** `terraform apply`, `make app-deploy`, and the CI deploy jobs. Run your first deploy early.

**File map** (paths relative to `scaffold/`; the § numbers are what the rest of this kit cites):

| § | File(s) | What it owns / the decision to defend |
|---|---|---|
| — | `.gitignore`, `.cursor/rules/interview-conventions.mdc` | Ignores (venv, node_modules, .env, tfstate); Cursor Project Rule, always applied (§5.1) |
| 4.1 | `backend/requirements.txt`, `requirements-dev.txt` | Minimum-version runtime deps in the image; test/lint tools only in dev |
| 4.2 | `backend/Dockerfile`, `.dockerignore` | Slim, non-root, `/health` HEALTHCHECK; `GIT_SHA`/`BUILD_TIME` build args → env + OCI `revision` label |
| 4.3 | `backend/docker-compose.yml`, `docker-compose.override.yml` | Postgres + Redis with healthchecks, app, worker. The override (auto-merged locally) publishes DB/Redis on 127.0.0.1; `make deploy` uses `-f docker-compose.yml` only, so on a Droplet just the app port is reachable |
| 4.4 | `backend/Makefile`, `pytest.ini`, `ruff.toml` | The one command surface: `install up up-native run test test-int lint fmt check image deploy deployed api-key app-create app-status app-deploy app-rollback`. Install, rsync/ssh and `doctl` steps have timeouts (skipped if neither `timeout` nor `gtimeout` exists). Recipe lines need real tabs if you ever retype it |
| 4.5 | `app/config.py` | Frozen `Settings` from env, parsed once at startup (a bad value fails fast); `REDIS_URL=""` disables the cache; `GIT_SHA`/`BUILD_TIME` |
| 4.6 | `app/observability.py` | JSON log lines with `request_id` + `version`; request-ID middleware (`x-request-id`); Prometheus counter/histogram labeled by route *template*; `app_build_info{git_sha}`; `x-app-version` header |
| 4.7 | `app/errors.py` | `AppError` → NotFound/Conflict/PayloadTooLarge/Unavailable; one envelope `{error:{code,message,request_id,details}}` for domain, validation, HTTP, DB-down (503) and unhandled (500, no leak) errors |
| 4.8 | `app/models.py` | `Item` create/update/page shapes: bounds on every field, whitespace-stripped, `extra="forbid"` on inputs |
| 4.9 | `app/repository.py` | `ItemRepository` Protocol + in-memory (tests) + Postgres (shared `psycopg_pool`). Partial update is one atomic `UPDATE … COALESCE … RETURNING` (the graded race). Schema DDL under a Postgres advisory lock so N processes can boot at once |
| 4.10 | `app/cache.py` | Cache-aside wrapper; every Redis error becomes a miss + a log line, never a 500 |
| 4.11 | `app/service.py` | Business rules; depends only on the repository/cache Protocols; raises domain errors, never `HTTPException` |
| 4.12 | `app/deps.py` | Wiring: settings → pool → repository/cache → service; test mode swaps in in-memory; `close_resources()` on shutdown |
| 4.13 | `app/main.py` | Thin plain-`def` routes (threadpool, no blocking in the event loop), CRUD + paginated list, `/health`, `/ready`, `/version`, `/metrics`, CORS from env, lifespan startup/shutdown |
| 4.14 | `backend/tests/` | `conftest.py` (dependency overrides, fresh in-memory repo per test), `test_api.py` (status codes, envelope, validation, pagination, request IDs, `/version`), `test_service.py` (failure modes with fakes: dead Redis, no cache), `test_concurrency.py` (threaded PATCHes to different fields both survive). `make test` runs them in ~0.1s with no infra |
| 4.15 | `app/events.py` (optional, not wired) | Redis pub/sub publisher/subscriber (Observer). Wire it in only if the prompt needs live/multi-consumer updates |
| 4.16 | `frontend/` (optional) | Vite + React: `src/api.js` (the only fetch client, error envelope → message), `src/App.jsx` (list/create/delete, loading + error states, inline styles). Delete it for an API-only brief; `/docs` (Swagger) is the demo UI |
| 4.20 | `app/ingest_*.py`, `app/worker.py`, `tests/test_ingest.py` | Ingestion add-on (below); removed by `strip-ingest.sh` |
| 4.21 | `.github/workflows/ci.yml` | Lint → tests → Postgres + Redis integration → image → auto-deploy on main (needs the `API_KEYS` secret), verified by SHA |
| 4.23 | `infra/main.tf`, `.do/app.yaml`, `.do/app.image.yaml` | Terraform (registry, managed PG + Valkey, optional Droplet + firewall) and the App Platform spec in two flavors: build from GitHub (path A) and prebuilt image (path B) |
| 4.25 | `app/security.py`, `tests/test_security.py` | One middleware before every non-ops route: API key (`X-API-Key` or `Bearer`) from `API_KEYS=name:key[:limit],…` (hashes only in memory), then a per-client sliding-window rate limit in Redis (atomic Lua; in-memory for tests). 401/429 use the error envelope; 429 has `Retry-After`, successes carry `X-RateLimit-*`. Ops paths (`/health /ready /version /metrics /docs`) stay open for health checks and the SHA check. Empty `API_KEYS` = auth off in dev/test, **refuses to start in prod**. Redis down = fail open. `/docs` gets an Authorize button. `make api-key NAME=x` mints a key |

### 4.17 Setup commands

**Preflight the container first (~1 min).** Don't assume anything beyond the listed preinstalls:
```bash
for t in git python3 uv docker make gh doctl terraform jq node; do printf '%-9s' $t; command -v $t >/dev/null && echo ok || echo MISSING; done
docker info >/dev/null 2>&1 && echo "docker daemon ok" || echo "docker daemon DOWN (expected in a container: use make up-native)"
```
- **No `uv`:** `curl -LsSf https://astral.sh/uv/install.sh | sh && export PATH=$HOME/.local/bin:$PATH`.
- **No `terraform`:** `curl -fsSLo /tmp/tf.zip https://releases.hashicorp.com/terraform/1.9.8/terraform_1.9.8_linux_$(dpkg --print-architecture).zip && sudo unzip -oq /tmp/tf.zip -d /usr/local/bin` (`sudo apt-get install -y unzip` first if missing). Or skip Terraform entirely (the dev-database route in §4.19).
- **No Docker daemon (likely):** don't fight Docker-in-Docker. `make up-native` installs Postgres + Redis with apt and starts them on the same URLs compose uses, so `make run`, `make test-int` and the worker work unchanged (verified in `ubuntu:24.04`: ~30 s). Deploy with a path where DigitalOcean builds the image (§4.19 A/B/C). `make up`, `make image` and `make app-deploy` need Docker.

Then, after the copy step at the top of §4 (`.gitignore` comes with it):
```bash
git init -b main && git add -A && git commit -m "Scaffold from interview-kit"   # -b main: deploys track main
cd backend && make install > /tmp/install.log 2>&1 && make check   # lint + tests green before touching anything
```
Then start these in the background, each logged so you can check progress without blocking. Use `uv run` (which the Makefile does), not `source .venv/bin/activate`: activation doesn't carry over to a new shell or tool call.
```bash
# from backend/
make up-native                           # or `make up` if Docker works; postgres + redis, returns when up
make run > /tmp/uvicorn.log 2>&1 &       # API on :8000, JSON logs; /docs is the demo UI
# from frontend/ (only if building one)
npm install --no-audit --no-fund > /tmp/npm-install.log 2>&1 && npm run dev > /tmp/vite.log 2>&1 &
```
Check readiness with `curl localhost:8000/ready` / `tail /tmp/uvicorn.log` instead of guessing. Optional, 10 seconds, and visible automation: `printf '#!/bin/sh\nmake -C backend check\n' > .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit`.

### 4.18 Adapt to the actual prompt (rename-and-extend, not a rewrite)

1. **`models.py`** — rename `Item`/`ItemCreate`/`ItemUpdate`/`ItemPage` to the real entity. Change the fields, keeping bounds on every field and `extra="forbid"` on inputs. Add a second entity module with the same shape if the prompt has more than one resource.
2. **`repository.py`** — rename the Protocol and classes and update the schema/SQL. Add an index for every new non-PK lookup. Query methods the prompt needs go here, not in routes.
3. **`service.py`** — the prompt's business rules live here and raise `errors.py` types, never `HTTPException`. Any *new* mutating operation goes through one atomic repository statement like `update_fields`, never read-then-write in the service. That's the graded bug (§1).
4. **`main.py`** — rename routes and add non-CRUD endpoints. Keep them thin.
5. **`config.py`** — every new tunable (limits, TTLs, feature flags) becomes a `Settings` field read from env, never a magic number in code.
6. **Tests** — rename in `test_api.py` and add one test per new rule. For any new counter, quota or balance, copy `test_concurrency.py`'s shape.
7. **Ingestion prompt?** §4.20 is already in (don't run `strip-ingest.sh`); rename `EventIn` to the prompt's record type, and change the aggregate SQL to whatever "processing" means in the prompt.
8. **Frontend (if any)** — rename `api.js` methods and replace the `App.jsx` view. Inline styles only.

**Don't change unless required**: the layering; Postgres as the live default + in-memory for tests; the error envelope; `/health` vs `/ready`; the compose override split.

### 4.20 Ingestion & processing add-on (the recruiter's brief: "data ingestion and processing")

```
client --POST /ingest (JSON batch) or /ingest/csv--> [API: validate each record, dedupe, store + enqueue in ONE tx] --202 {batch_id}-->
                                                              |
                                                     [Postgres: events + ingest_batches (the queue)]
                                                              |
                                  [worker x N: claim batch FOR UPDATE SKIP LOCKED -> atomic upsert aggregate -> completed]
client --GET /ingest/{batch_id} (status) , GET /totals (results)
```

Design calls to say out loud (they're also `design-decisions.md` material):
- **Accept fast, process async.** The request only validates, stores and enqueues, so latency stays bounded whatever processing costs. `202 Accepted` + a status URL is the honest contract.
- **Per-record validation, partial success.** One bad record doesn't 422 the whole batch. The response lists each rejected index with its reason.
- **Idempotent by design.** A client-supplied `event_id` + `ON CONFLICT DO NOTHING` makes retries safe, and duplicates are counted and reported.
- **Postgres as the queue.** Enqueueing happens in the same transaction as the data, so there's no stored-but-not-queued state and no extra broker to deploy. `FOR UPDATE SKIP LOCKED` lets N workers share it safely. The whole claim → process → complete runs in one transaction, so a crashed worker's batch just becomes pending again. A poison batch is marked `failed` after `WORKER_MAX_ATTEMPTS`. At higher scale, move to Redis Streams / SQS / Kafka with consumer groups; the repository seam is where that swap happens.
- **Backpressure.** A batch-size cap (413) and a pending-backlog cap (503 + `Retry-After`) shed load instead of queueing without bound.
- **The graded traps, pre-empted:** two workers double-processing a batch (fixed by `SKIP LOCKED`), a lost update in the aggregate (fixed by an atomic upsert, not read-modify-write in Python), lock-order deadlocks (fixed by `ORDER BY` in the aggregate), and a blocking call in the event loop (fixed by plain `def` routes, including CSV parsing).

Files: `app/ingest_models.py` (`EventIn` record + batch shapes, per-record bounds), `app/ingest_repository.py` (store + enqueue in one transaction, `ON CONFLICT DO NOTHING` dedupe, `FOR UPDATE SKIP LOCKED` claim, atomic upsert aggregate with `ORDER BY`, attempts → `failed`), `app/ingest_service.py` (per-record validation, batch and backlog caps), `app/ingest_routes.py` (`POST /ingest`, `POST /ingest/csv`, `GET /ingest/{batch_id}`, `GET /totals`, all plain `def`), `app/worker.py` (`python -m app.worker`, graceful SIGTERM, backoff on errors), `tests/test_ingest.py` (partial success, dedupe, caps, and the `integration`-marked 8-worker exactly-once test). Wired in via `deps.py`, `main.py`, the compose `worker` service and the `.do/app.yaml` `workers:` block; `strip-ingest.sh` removes all of it.

Verify: `make test` (unit, no infra), then `make up && make test-int`, which runs the concurrent-workers exactly-once test against real Postgres.
