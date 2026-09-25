---
name: interview-kit
description: Design playbook for DigitalOcean's timed build-and-deploy interview (3h: build a REST API for data ingestion + processing and deploy it live on DigitalOcean). Holds the one batch of clarifying questions, default assumptions, the pitfall audit (write races, blocking calls), the design-decisions.md outline and likely prompts. The step-by-step runbook is the project's AGENTS.md. Use when the user shares the interview prompt or asks about its design, scaling or DigitalOcean deploy.
---

# Interview kit: design playbook

The project's `AGENTS.md` is the step-by-step runbook, and this file is what its steps point to. If you are
reading this without a project around it (no `AGENTS.md` beside `.kit/`), set up first: follow "AI agent: set
this up" in https://github.com/SakethThogarucheeti/interview-skills (README).

**What's graded.** "Production-ready thinking rather than just a working script." DigitalOcean watches what you
check by hand. Prompts are built so naive AI output introduces a **write race** or a **blocking call in `async
def`**, to see whether you catch it. Audit every generated diff against the pitfall table below. A smaller,
tested, deployed API beats a bigger unfinished one.

| Graded area | Where the app already shows it |
|---|---|
| Engineering quality | layers `main.py` -> `service.py` -> `repository.py`; field bounds + `extra="forbid"` in `models.py`; one JSON error envelope with request ID in `errors.py` (404/409/413/422/503) |
| Testing | `backend/tests/`: API, service, concurrency and Postgres-integration tests; `make -C backend check` needs no infra |
| Automation & workflow | Makefile as the only command surface, ruff, CI tests on every push, push to main = deploy, Terraform in `infra/main.tf`, app spec in `.do/app.yaml` |
| Operational excellence | JSON logs with request IDs, `/metrics`, `/health` vs `/ready`, all config from env (`config.py`), Redis failure = cache miss, `/version` = the live commit, API keys + rate limit (`security.py`) |

**Picking from a list of prompts:** take the one that matches a pattern below (ingestion first), otherwise the one
you can state in one sentence.

## Clarifying questions (one message, then stop)

Ask these in ONE message, skip what the prompt already answers, and give your default for each. Label the two
groups "functional" and "non-functional"; the interviewer listens for that split. Wait for the answer. After it,
never ask again: decide the rest yourself.

**Functional:**
- Core entities and actions: create/read/update/delete what?
- The one golden-path story that must work at the demo.
- Non-goals: I'm assuming no user accounts/OAuth (API keys are in), no multi-tenancy, no admin UI.
- API only, or a UI too?
- Ingestion prompts, also ask:
  - What does a record look like, and how does it arrive (JSON batch, CSV upload, stream)?
  - What does "processing" produce (aggregates, enrichment, alerts), and how is it queried?
  - Can records arrive duplicated or out of order? Is there a unique record id?
  - Is async processing with a status endpoint OK, or must the result be in the response?
  - Bad records: reject the whole batch, or accept the good ones and report the bad?

**Non-functional (lead with the default, "I'm assuming X unless you'd rather Y"):**
- Scale: requests/sec, data volume, max batch size. Default: demo scale, 10s-100s of concurrent users.
- Consistency: strong (payments, quotas, inventory) or eventual (counts, feeds)? Default: eventual, except the
  writes the prompt makes critical.

Then state the rest in one line without asking (the table below).

## Default assumptions (state them, don't ask)

| Area | Default |
|---|---|
| Scale | Demo scale, one region, one Postgres. Stateless app, so 10x is a config change. |
| Latency | p95 < 200 ms reads, < 500 ms writes: cache-aside is enough. |
| Availability | App Platform: 2 API instances, rolling health-gated deploys; single-node managed DBs (a standby node is the HA upgrade). |
| Durability | Postgres is the source of truth. Redis is disposable: losing it costs latency, never data. |
| Security | Server-side validation and IDs; DB/Redis not public; secrets from env; API key on every data route; per-client rate limit (429 + `Retry-After`); prod refuses to start without `API_KEYS`. `CORS_ORIGINS=*` is a named demo default. |
| Read/write mix | Read-heavy, bursty writes. |
| Delivery (ingestion) | At-least-once intake + dedupe on record id = effectively once. |
| Observability | JSON logs, request IDs, `/metrics`, `/health` vs `/ready`. Next step: OpenTelemetry + Grafana. |
| Configurability | Every setting is an env var read once at startup; one image for dev, CI and prod. |

## Architecture: one box, clean seams

```
[client] --HTTP/JSON--> [FastAPI app x2] --> [Postgres]
                               |
                               +--> [Redis: cache-aside, rate limit]
[worker x N, same image] <--claims batches from-- [Postgres]   (ingestion prompts)
```
One codebase, one image. Postgres is also the job queue (`FOR UPDATE SKIP LOCKED`). Do **not** add
microservices, a message broker or multi-region: they cost time and read as a red flag at this scope. Start
simple and add something only when the pitfall table finds a real, cheap-to-fix risk.

## Pitfall table: check the design, then every generated diff

Mark each row **build it** (cheap, and the prompt implies it) or **mention it** (a talking point). Don't apply all of them.

| Risk | What to do |
|---|---|
| **Write race**: read-modify-write counters, double booking, check-then-insert, partial updates | **Build it.** One atomic statement (`UPDATE … SET n = n + 1 WHERE … RETURNING`, `ON CONFLICT DO UPDATE`) or a unique constraint. Copy `update_fields` in `repository.py`; test it like `tests/test_concurrency.py`. |
| **Blocking call in `async def`** | **Already avoided**: routes are plain `def`. Never add `async def` around sync DB, Redis, HTTP or file calls. |
| **Double processing**: two workers take the same job; aggregates updated in Python | **Build it** for processing prompts: claim with `FOR UPDATE SKIP LOCKED`, aggregate with an atomic upsert (`total = total + EXCLUDED.total`), all in one transaction (see `ingest_repository.py`). |
| **Heavy work in the request** / unbounded batches | **Build it** for ingestion: validate + store + enqueue, return 202 + status URL, cap the batch (413) and backlog (503 + `Retry-After`). |
| **Spiky traffic** on one endpoint | **Already built**: per-client rate limit. For a hot endpoint, add a tighter limit and use the cache. |
| **Dependency outage** | **Already handled**: Redis down = cache miss; DB down = clean 503; `/ready` goes 503 so the load balancer drains the instance. |
| **Unbounded list** | **Build it**: `limit`/`offset` with a max. |
| **Missing index** on a non-PK lookup | **Build it**: one `CREATE INDEX`. |
| **Trusting client IDs/prices/owners** | **Build it**: generate or check them server-side. |
| **No idempotency** on a retryable POST | Build it for payments/orders/ingestion (client id + `ON CONFLICT DO NOTHING`), otherwise **mention it**. |
| **Cache/DB divergence** | **Already handled**: `Cache.invalidate` on write; reuse it for any new cached read. |
| **Single point of failure** | **Mention it**: stateless app scales out; managed DB standby nodes are the prod answer. |

## Likely prompt patterns (unofficial)

- **Data ingestion + processing** (the recruiter's own wording, most likely): batch/CSV intake -> validate ->
  store -> process/aggregate -> query. The ingestion code is already in (`app/ingest_*.py`, `app/worker.py`):
  rename `EventIn` and change the aggregate SQL. Traps: double processing, read-modify-write aggregates (both handled).
- **Quota / usage-limit manager**: trap is "check quota, then create". Fix: `UPDATE … SET used = used + 1 WHERE
  used < limit RETURNING used`, one statement.
- **Telemetry / cache that survives an origin outage**: intake as above. In `app/cache.py`'s `get_or_set`, fall
  back to the last good cached value when the loader fails, plus a small circuit breaker.
- **Rate limiter with tiers**: `app/security.py` already has tiers (`name:key:limit`), an atomic sliding window in
  Redis (Lua), 429 + `Retry-After` and a race test. Move tiers to a table and add per-endpoint limits if asked.

## design-decisions.md

The user studies this before the walkthrough, since the user (not you) answers it. Write it at the project root
right after the design is settled (runbook step 3) and update it at the end (step 8). Bullets, one screen per section:
- **Goals & non-goals**: what's in, what was left out and why.
- **Requirements**: the functional list as confirmed, and the default-assumptions table, each row marked confirmed or assumed.
- **Architecture**: the diagram, and why not microservices/a broker/multi-region.
- **Pitfall table**: every row, build or mention, one sentence on the mitigation.
- **Scaling and downtime answers**: from `.kit/reference/talking-points.md`, in first person, about this code.
- **Trade-offs**: what was cut for time and what adding it back would take.
- **Rubric walkthrough**: one bullet per graded area pointing at something to show, e.g. "validation: `models.py`
  bounds, try `POST /items {}`"; "testing: `make -C backend check`, the concurrency test and why it exists";
  "observability: `curl /metrics`, a JSON log line with its request id"; "deploy: push = deploy, `make -C backend deployed`".

## Code design rules

- Use a pattern only when you can name a second case that needs it.
- The layers: route (`main.py`) / service (`service.py`) / repository (`repository.py`). New feature = new service
  function. New storage = new repository class.
- Repository everywhere; a plain function in `deps.py` is the factory; Redis pub/sub (`app/events.py`) only if
  the prompt needs live updates. Skip Strategy/Visitor/Builder/deep class trees.
- Duplication in 2 places is fine; never duplicate validation, response shapes or DB access for one entity.

## Reference files (in `.kit/reference/`, read only when the step needs it)

| File | Read it when |
|---|---|
| `scaffold.md` | you need to know which file owns what, how to adapt the app to the prompt, or the ingestion design |
| `deploy.md` | the deploy (runbook step 5), a deploy failure, CI, Terraform, "which commit is live", rollback |
| `talking-points.md` | writing `design-decisions.md`: scaling, spikes, downtime, consistency, secrets answers |
| `do-offerings.md` | a walkthrough question about DigitalOcean products |
