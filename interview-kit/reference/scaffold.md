# The app: which file owns what, and how to adapt it

The project root already holds a working FastAPI + Postgres + Redis REST API with tests, CI, Terraform and an
App Platform spec. Read a file when you are about to change or explain it, not up front. Paths are from the
project root.

## Which file owns what

| File(s) | What it owns / the decision to defend |
|---|---|
| `AGENTS.md`, `CLAUDE.md`, `.cursor/commands/interview.md` | The runbook. Cursor reads `AGENTS.md` natively, `CLAUDE.md` imports it for Claude Code, `/interview` in Cursor points at it |
| `preflight.sh` | Setup: tools, DO/GitHub login, git identity, the private repo, API keys in `~/.api_keys.env`, `terraform apply` in the background. Safe to re-run |
| `strip-ingest.sh` | Removes the ingestion code (for prompts that aren't about ingestion) |
| `backend/Makefile` | The only command surface (`make -C backend` lists the game-day targets). Recipe lines need real tabs |
| `backend/requirements.txt`, `requirements-dev.txt` | Runtime deps in the image; test/lint tools only in dev |
| `backend/Dockerfile` | Slim, non-root, `/health` HEALTHCHECK; `GIT_SHA`/`BUILD_TIME` build args |
| `backend/docker-compose.yml` | Local Postgres + Redis on 127.0.0.1 for hosts where Docker works (`make -C backend up`); otherwise `up-native` |
| `backend/app/config.py` | Every setting, read from env once at startup (a bad value fails fast). `REDIS_URL=""` disables the cache |
| `backend/app/observability.py` | JSON logs with `request_id` + `version`, `x-request-id`, Prometheus metrics by route template, `x-app-version` |
| `backend/app/errors.py` | `AppError` -> NotFound/Conflict/PayloadTooLarge/Unavailable; one envelope `{error:{code,message,request_id,details}}` for every error, 500s without leaking |
| `backend/app/models.py` | `Item` create/update/page shapes: bounds on every field, whitespace stripped, `extra="forbid"` |
| `backend/app/repository.py` | `ItemRepository` Protocol + in-memory (tests) + Postgres. `update_fields` is one atomic `UPDATE … COALESCE … RETURNING` (the graded race). Schema created at startup under an advisory lock |
| `backend/app/cache.py` | Cache-aside; every Redis error becomes a miss + a log line, never a 500 |
| `backend/app/service.py` | Business rules; depends only on the repository/cache Protocols; raises `errors.py` errors, never `HTTPException` |
| `backend/app/deps.py` | Wiring: settings -> pool -> repository/cache -> service; test mode uses in-memory |
| `backend/app/main.py` | Thin plain-`def` routes: CRUD + paginated list, `/health`, `/ready`, `/version`, `/metrics` |
| `backend/app/security.py` | API key (`X-API-Key` or `Bearer`) from `API_KEYS=name:key[:limit],…`, then a per-client sliding-window rate limit in Redis (atomic Lua). 401/429 in the envelope. `/health /ready /version /metrics /docs` stay open. Empty `API_KEYS` = auth off in dev/test, refuses to start in prod |
| `backend/app/events.py` | Redis pub/sub, not wired in. Use it only if the prompt needs live updates |
| `backend/app/ingest_*.py`, `backend/app/worker.py` | Ingestion (see "Ingestion design" below) |
| `backend/tests/` | `test_api.py` (status codes, envelope, validation, pagination), `test_service.py` (dead Redis), `test_concurrency.py` (concurrent PATCHes both survive), `test_security.py`, `test_ingest.py`. `make -C backend check` runs them in seconds with no infra |
| `backend/e2e.py` | `make -C backend e2e`: ~40 checks against the live app (auth, CRUD, ingest -> worker -> exact totals under concurrent writers, 429s). Rename its `/items` requests when you rename the entity |
| `.github/workflows/ci.yml` | Lint, tests, Postgres integration tests and an image build on every push |
| `infra/main.tf` | Terraform: managed Postgres + Valkey, applied by `./preflight.sh` |
| `.do/app.yaml` | The App Platform spec: builds from GitHub on every push, 2 API instances, worker, health checks, alerts |
| `frontend/` | Optional Vite + React UI. Delete it unless they asked for a UI; `/docs` (Swagger) is the demo UI |
| `dev.sh`, `.devcontainer/` | Ubuntu 24 dev container for practice on a non-Ubuntu host (see the last section) |

## Adapt to the prompt (rename and extend, don't rewrite)

One file at a time, in this order. After each: audit the diff, `make -C backend check`, commit.
1. **`backend/app/models.py`**: rename `Item`/`ItemCreate`/`ItemUpdate`/`ItemPage` to the real entity. Change the
   fields, keeping bounds on every field and `extra="forbid"`. A second resource gets its own module with the same shape.
2. **`backend/app/repository.py`**: rename the Protocol and classes, update the schema and SQL. Add an index for
   every new non-PK lookup. New queries go here, not in routes.
3. **`backend/app/service.py`**: the prompt's rules, raising `errors.py` errors. Any new write goes through one
   atomic repository statement like `update_fields`, never read-then-write in the service.
4. **`backend/app/main.py`**: rename routes, add endpoints. Keep them thin and plain `def`.
5. **`backend/app/config.py`**: every new limit, TTL or flag becomes a setting read from env.
6. **Tests**: rename in `test_api.py` (and the other tests that use `Item`), add one test per new rule. For a new
   counter, quota or balance, copy `test_concurrency.py`.
7. **`backend/e2e.py`**: rename the `/items` requests and payloads.
8. **Ingestion prompt?** The code is already in: rename `EventIn` in `ingest_models.py` to the prompt's record, and
   change the aggregate SQL in `ingest_repository.py` to whatever "processing" means.
9. **Frontend (only if asked)**: rename the `frontend/src/api.js` methods, replace the `App.jsx` view, inline styles only.

Don't change: the layering, Postgres live + in-memory for tests, the error envelope, `/health` vs `/ready`.

## Ingestion design

```
client --POST /ingest (JSON batch) or /ingest/csv--> [API: validate each record, dedupe, store + enqueue in ONE tx] --202 {batch_id}-->
                                                              |
                                                     [Postgres: events + ingest_batches (the queue)]
                                                              |
                                  [worker x N: claim batch FOR UPDATE SKIP LOCKED -> atomic upsert aggregate -> completed]
client --GET /ingest/{batch_id} (status) , GET /totals (results)
```
Design calls to say out loud (also `design-decisions.md` material):
- **Accept fast, process async.** The request only validates, stores and enqueues; 202 + a status URL.
- **Per-record validation, partial success.** One bad record doesn't fail the batch; rejects are listed by index with a reason.
- **Idempotent.** The client's `event_id` + `ON CONFLICT DO NOTHING` makes retries safe; duplicates are counted.
- **Postgres is the queue.** Enqueue is in the same transaction as the data, so nothing is stored but not queued,
  and there's no broker to run. `FOR UPDATE SKIP LOCKED` lets N workers share it. Claim -> process -> complete is
  one transaction, so a crashed worker's batch goes back to pending. A poison batch becomes `failed` after
  `WORKER_MAX_ATTEMPTS`. At higher scale: Redis Streams/SQS/Kafka behind the same repository.
- **Backpressure.** Batch-size cap (413) and pending-backlog cap (503 + `Retry-After`).
- **Traps already handled:** double processing (`SKIP LOCKED`), lost updates in the aggregate (atomic upsert),
  lock-order deadlocks (`ORDER BY` in the aggregate), blocking the event loop (plain `def` routes, CSV parsing included).

Files: `ingest_models.py` (record + batch shapes), `ingest_repository.py` (store + enqueue, dedupe, claim, atomic
aggregate), `ingest_service.py` (per-record validation, caps), `ingest_routes.py` (`POST /ingest`, `POST
/ingest/csv`, `GET /ingest/{batch_id}`, `GET /totals`), `worker.py` (`python -m app.worker`, stops cleanly on
SIGTERM), `tests/test_ingest.py`. `make -C backend test-int` runs the 8-worker exactly-once test against the local Postgres.

## What's been verified

Lint clean; all tests pass with and without `strip-ingest.sh`. The 8-worker integration test processes 40 contended
batches exactly once (and fails 3/3 without `SKIP LOCKED`). Redis down = `degraded` and still serving; Postgres
down = clean 503 and recovery. Deployed live on DigitalOcean (2026-09-24) and passed `make e2e`, including auth and
the rate limit shared across 2 instances.

## Non-Ubuntu host (practice only)

On Arch/macOS, preflight's `apt` installs fail, so run everything in the dev container: put `./dev.sh` in front
of every command (`./dev.sh ./preflight.sh`, `./dev.sh make -C backend check`), or `./dev.sh` alone for a shell.
It has doctl, terraform, gh, uv, Postgres and Redis, reuses the host's `gh` login, passes `DO_TOKEN` per command
(never stored), and publishes the API on `127.0.0.1:8000`.
- Run `make`, `uv` and `python` only through `./dev.sh`: `backend/.venv` is shared with the host, and a host-side
  `uv run` rebuilds it with the wrong interpreter.
- A server started with `./dev.sh bash -c '…'` dies with that command; start it with `setsid`:
  `./dev.sh bash -c 'setsid make -C backend run > /tmp/api.log 2>&1 &'`.
- Never `pkill -f <name>` from a command line that contains `<name>`: it kills its own shell.
- Running `./dev.sh` from a different project recreates the container on that project.
