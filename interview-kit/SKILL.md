---
name: interview-kit
description: Self-contained kit for a timed build-and-deploy interview (DigitalOcean: 3h, build a REST API for data ingestion and processing, deploy it live on DigitalOcean, on a provided Cursor laptop). Graded on engineering quality, testing, automation, operational excellence, and on catching AI-introduced race conditions and blocking calls. Gates one batched round of functional and non-functional clarifying questions before any code, then builds without reopening it. Spawns a subagent to write design-decisions.md, since the user, not the agent, answers the post-build walkthrough. Covers goal-scoping, a pitfall scan re-run against every AI-generated diff, HLD talking points, SOLID/DRY/GoF, a verified production-shaped FastAPI+Postgres+Redis scaffold (env config, validation, error envelope, JSON logs, metrics, health/readiness, tests, Makefile) with an ingestion/worker add-on, DigitalOcean deployment (App Platform or Droplet) with IaC (Terraform + app spec) and CI that auto-deploys every push pinned to its commit, a /version trail for which commit is live, a catalog of DO's cloud offerings, provided-laptop preflight, a Cursor bridge, and time-compression and git-discipline tactics. Use as soon as the user shares the prompt, asks about this interview's design or scaling, wants the scaffold, needs to deploy to DigitalOcean, or asks about Cursor for it. The scaffold code ships beside this file in scaffold/.
---

# Interview kit — timed full-stack build

This file plus the `scaffold/` folder beside it (all the code; §4 maps it), no GitHub dependency: requirements → design → LLD → scaffold → Cursor workflow → deployment → verbal defense. Prep/rehearse here; the actual build runs in Cursor (§5) unless told otherwise.

**Format** (DigitalOcean's confirmed shape): a 3-hour session, pick from a short list of assigned prompts, build it, deploy it live on DigitalOcean before time's up (§4.19). Then comes a walkthrough of design trade-offs and hypotheticals on scaling, traffic spikes, downtime and business constraints. The user, not the agent, answers that walkthrough, so hand off a `design-decisions.md` for them to study (§1).

**This session's brief (from the recruiter):**
- **The task:** "build and deploy a functional **REST API** service that handles **data ingestion and processing**". So the default is API-only, and the §4.20 ingestion add-on is the likely core.
- **Language:** Go or Python preferred. This kit is Python.
- **Machine:** a **provided laptop** with Cursor Enterprise (Claude 3.7 Sonnet / GPT-4o built in, privacy mode on). Nothing from your own machine is there, so preflight it (§4.17).
- **Cloud:** DigitalOcean credits provided, and deploying during the session is expected.

**The rubric, and where the kit already covers it.** "Production-ready thinking rather than just a working script":

| Graded area | What they look for | Covered by |
|---|---|---|
| **Engineering quality** | clean organization, sensible validation, meaningful error handling | route/service/repository layering (§2); field bounds + `extra="forbid"` (§4.8); domain errors → one JSON error envelope with request ID, 404/409/413/422/503 (§4.7) |
| **Testing** | a *structured* approach to automated verification | API / unit / concurrency-regression / Postgres-integration tests, isolated fixtures, no infra needed (§4.14, §4.20) |
| **Automation & workflow** | consistent delivery, streamlined lifecycle | Makefile as the single command surface, ruff lint/format, pre-commit hook, CI → auto-deploy every push to main, verified live by SHA (§4.21); IaC: `infra/main.tf` + `.do/app.yaml` (§4.23); one-command deploy/rollback (§4.19, §4.24) |
| **Operational excellence** | observability, configurability, scalability in a live environment | JSON logs + request IDs, Prometheus `/metrics`, `/health` vs `/ready` (§4.6, §4.13); all config from env (§4.5); graceful degradation + shutdown; stateless app + horizontally scalable workers (§4.20); DB never exposed (§4.3); `/version` + `x-app-version` + log `version` field answer "which commit is live?" (§4.24) |

Keep the scaffold's quality features even when you're behind. Cut features, never these: they *are* the grade. Name each one out loud in the walkthrough.

**Priority order**: working, deployed demo > code that looks deliberately structured on a skim > sharp answers to those questions. Working-but-plain beats brilliant-but-unfinished; undeployed beats nothing.

**What's actually graded**: DigitalOcean's own hiring writeup says they watch where you lean on AI (boilerplate — fine) vs. what you check by hand (concurrency, blocking calls) — prompts are deliberately structured so naive AI output confidently introduces a race condition or a blocking call, to see if you catch it. Audit every AI-generated chunk against §1's pitfall scan before accepting it — that audit *is* the interview.

## 0. Time-compression tactics (apply throughout)

The real enemy in a 3-hour window is idle/serial time, not typing speed — and a portion of it now has to include a working deployment, so there's less slack than "3 hours" sounds like.

- **Ask once, then move on.** Clarifying questions (§1) are a hard gate — batch them into one shot, wait for the answer, don't implement before it. But it's one gate, not a habit: once answered, decide every remaining gap yourself and build.
- **Fill dead time, never idle.** The moment a question is asked, fire a parallel task on what you'll need next — Claude Code: a `fork`/background Agent; Cursor: a second chat tab or Background Agent (§5.3). This fills the wait, it doesn't replace it — still don't build on an assumed answer.
- **Decide, don't deliberate.** Default any choice that doesn't change the outcome; only ask what changes scope.
- **Timeout everything; log anything backgrounded.** A hung command with no timeout eats the clock silently; a slow one with no log forces you to babysit it. Wrap anything that could hang (installs, network/DB calls) in a timeout — the Bash tool's own parameter in Claude Code, or shell `timeout <n>s <cmd>` in Cursor (stock macOS has no `timeout`: `gtimeout` via `brew install coreutils`, and the Makefile falls back automatically, §4.4). Redirect backgrounded processes (`uvicorn`, `npm run dev`, `docker compose up`) to a log file (`... > /tmp/x.log 2>&1 &`) so progress is checkable with `tail`/`grep` instead of blocking on it. Scope greps/finds to the relevant directory (`grep -r pattern app/`), never the repo root — crawling `node_modules`/`.venv`/`.git` wastes real time for zero signal.
- **Zero CSS.** No framework, no stylesheet, nothing beyond the scaffold's inline styles — hard rule from the start.
- **Use git, committed at every milestone and passing test.** `.gitignore` + `git init` before the scaffold goes in (§4.17), then a commit after each milestone/passing test — small and frequent, not one giant commit at the end. Makes a bad edit or a sideways tool call a `git checkout` away, not a rebuild. Commit history is also visible "workflow" evidence for the rubric.
- **Deploy early, redeploy often.** Get the untouched scaffold live (§4.19) right after it's running locally, then redeploy at each milestone (with CI, that's just `git push`). A deploy problem found at minute 30 is an annoyance; at minute 170 it's a fail.
- **Budget** (3h, API-only brief): ~5 min preflight the laptop (§4.17), ~5 min pick the prompt, ~10 min questions + design (§1), ~10 min scaffold in + green + **first deploy** (§4.17, §4.19; start `terraform apply` in the background right after preflight, since managed DBs take ~5-10 min), ~70 min core feature + tests (§4.18/§4.20), ~20 min CI + observability touches (§4.21), ~15 min final deploy + verify, ~20 min defense prep (§3), buffer. If a frontend is required, take ~30 min from the core feature, not from tests or deploy.

**Before the day: send the recruiter these (they invited questions).** Each answer removes a live unknown:
1. Is a frontend expected, or is the REST API (with Swagger `/docs`) the whole deliverable?
2. Is anything preinstalled on the laptop besides Cursor: Docker, Python/uv, Node, `doctl`, git? Is it macOS?
3. Can I push to my own GitHub (for CI and App Platform), or should everything stay local/on DO?
4. Will DigitalOcean access be a console login, an API token, or both?
5. May I bring a personal template/rules file (e.g. clone a repo), or should everything be written live?

## 1. Requirements & HLD (~10 min, don't exceed)

**If given a short list of prompts, pick one first.** Prefer whichever matches a pattern you've prepped ("Likely prompt patterns" below) or, failing that, the smallest, clearest scope — a prompt you can state in one sentence beats an ambiguous one, since ambiguity costs clarifying-question time you don't get back.

**Hard gate: ask before building — once.** The moment the prompt is shared, ask the batch of clarifying questions below in a single message and stop — no scaffolding, no code, until the user answers or says to use your judgment. This is a real stop: no implementation happens between asking and the response. Use dead time (§0) to research while waiting, not to build on assumed answers. Skip only what the prompt already answered.

**Once answered, stop asking and start building.** The gate fires exactly once, not per-decision. After the batch is answered (even partially), decide every remaining gap yourself (§0's "decide, don't deliberate") and move straight to design/build — no second round. Circling back costs more than a wrong default and reads as indecision. Exception: something that would force a visible do-over if guessed wrong (e.g. the prompt is ambiguous between two fundamentally different apps).

**Ask for functional *and* non-functional requirements — explicitly, by name.** Most candidates ask only "what should it do" and get graded down for never establishing scale, latency, or consistency targets. Cover both categories in the one batch, and say the words "functional" and "non-functional" out loud — the interviewer is listening for whether you separate them.

Batch every open question; skip only what doesn't change scope, stating that assumption instead. Output a short, explicit goals/non-goals statement — a decision to hold the build to.

**Functional — always ask, these change what you build:**
- **Core entities & actions** — create/read/update/delete what?
- **The one golden-path user story** — what must demonstrably work end-to-end at the demo?
- **Non-goals** — what you're explicitly not building (auth, multi-tenancy, admin UI…).
- **What "deployed" means** — backend API only, or the frontend too? Changes the §4.19 deploy plan.
- **For an ingestion prompt, add these (each changes the §4.20 design):**
  - What does a record look like, and where do records come from (JSON batch, CSV/file upload, stream)?
  - What does "processing" produce (aggregates, enrichment, forwarding, alerts), and how is the result queried?
  - Can records arrive duplicated or out of order? Is there a natural unique ID for idempotency?
  - Must processing be synchronous (the result in the response), or is async with a status endpoint fine?
  - What happens to invalid records: reject the whole batch, or accept the good ones and report the bad?

**Non-functional — ask, but lead with your assumption.** Phrase each as "I'm assuming X unless you'd rather Y" so a non-answer still unblocks you. Only two genuinely change the design here:
- **Scale** — concurrent users/RPS and data volume; for ingestion, records/sec and max batch/file size. Drives whether caching and pagination are build-it or mention-it, and sets `MAX_BATCH_SIZE`.
- **Consistency** — strong (payments, inventory, quotas) or eventual (counts, feeds, likes)? Most prompts tolerate eventual; the exceptions are exactly where the graded write race lives.

Also name the prompt's specific spiky-traffic risk, if any — it targets the pitfall scan below.

**Assume the rest without asking — state once, in one line, move on.** Asking about these reads as inexperience, not diligence. Revise only if the prompt or interviewer contradicts one:

| NFR | Default to state |
|---|---|
| **Scale** | Demo scale — 10s-100s concurrent users, single region, fits one Postgres box. Seams (§2) make 10x a config change, not a rebuild. |
| **Latency** | p95 < 200ms reads, < 500ms writes — justifies cache-aside, not more. |
| **Availability** | App Platform: 2 API instances with rolling, health-gated deploys; single-node managed DBs (standby node = the HA upgrade). Droplet: one box, a SPOF named in §3, not hidden. |
| **Durability** | Postgres is source of truth; Redis is disposable — losing it costs latency, never data. |
| **Security** | Server-side validation/generated IDs; DB/Redis never exposed publicly (§4.3); DB password from env, not code; no authn/authz unless asked (an API-key header is the 10-min answer if pushed). `CORS_ORIGINS=*` is a named demo default (§4.13). |
| **Read/write mix** | Read-heavy, write-bursty — the shape of most prompts. Drives the caching story. |
| **Delivery semantics** (ingestion) | At-least-once intake + idempotent dedupe by record ID = effectively-once results (§4.20). |
| **Observability** | JSON logs with request IDs, Prometheus `/metrics` (rate, errors, latency, ingest outcomes), `/health` liveness vs `/ready` readiness. No tracing/dashboards stack in 3 hours — name OpenTelemetry + Grafana as the next step. |
| **Configurability** | Every tunable is an env var read once at startup (§4.5); same image runs dev/CI/prod. |

Carry this table into `design-decisions.md` — "what did you assume, and what breaks at 100x?" is a standard walkthrough question this answers.

### Default architecture: "one box, clean seams"

```
[React SPA] --HTTP/JSON--> [FastAPI monolith] --> [Postgres]
                                  |
                                  +--> [Redis: cache-aside for hot reads]
                                  +--> [Redis: pub/sub for fan-out, if the prompt needs live updates]
[worker process(es), same image] <--claims jobs from-- [Postgres]   (ingestion/processing prompts, §4.20)
```

Postgres + Redis are provisioned from minute one via `docker-compose.yml` (§4), not swapped in later. It's one codebase and one image (also the easiest shape to get live on DigitalOcean within budget, §4.19), with nothing between-your-own-services to debug. Every "how would you scale this" question has a crisp answer (§3) because the seams already exist. Do **not** start with microservices, a separate message broker (Postgres `SKIP LOCKED` is the queue, §4.20), or multi-region: they cost build time you don't have and read as a red flag here, not a strength.

**Start from the simplest version that satisfies the goals above.** Add complexity only because the pitfall scan below finds a real, cheap-to-fix risk — never because it seems "more correct."

### Pitfall scan — before writing any code

Check the simple design against this list. Tag each **build it** (cheap, clearly implied by the prompt) or **mention it** (real, but a §3 talking point) — don't blanket-apply it, that's scope creep the other way.

| Risk | Default call |
|---|---|
| **Single point of failure** — one app/DB/cache process | **Mention it.** Stateless app scales horizontally behind a load balancer as a config change; managed Postgres/Redis with failover is the prod answer. Don't build HA in this window. |
| **Spiky/bursty traffic** on a specific endpoint the prompt implies (viral link, vote surge) | **Build it** if there's a genuinely hot endpoint: rate limiting (Decorator, ~10-15 min) + confirm that read path uses the cache-aside. Otherwise **mention it**. |
| **Write races** — duplicate unique values, double-vote/booking, read-modify-write counters, partial updates | **Build it** wherever the prompt has one: a DB unique constraint + conflict handling, or one atomic `UPDATE ... SET n = n + 1 ... RETURNING` instead of read-then-write. A correctness bug, not just a scaling nicety. **Worked example in the scaffold**: `repository.update_fields` (§4.9) does a partial update in a single statement precisely because the read → `model_copy` → `save` version loses one of two concurrent PATCHes *every single time* — copy that shape for any new mutating endpoint, and `test_concurrency.py`'s shape for its test. |
| **Double processing** — two workers/requests claim the same job; aggregates updated read-modify-write | **Build it** for any processing prompt: claim with `FOR UPDATE SKIP LOCKED`, aggregate with an atomic upsert (`total = total + EXCLUDED.total`), claim + work + complete in one transaction (§4.20). |
| **Processing in the request path** — heavy work inside the POST, unbounded batch/file size | **Build it** for ingestion: validate + store + enqueue, return `202` + status URL, cap batch size (413) and backlog (503 + `Retry-After`) (§4.20). |
| **Dependency outage cascades** — Redis/DB down turns every request into a hang or opaque 500 | **Already handled**: Redis errors degrade to a cache miss, pool/socket timeouts bound waits, DB-down is a clean 503, `/ready` goes 503 so a load balancer drains the instance (§4.10, §4.7, §4.13). |
| **Unbounded list growth** — no pagination on a real list feature | **Build it**: basic `limit`/`offset`. Cheap now, awkward to bolt on later. |
| **Missing index** on any non-PK lookup (by owner, code, status) | **Build it** — one `CREATE INDEX` line. |
| **Trusting client input** for IDs/prices/ownership | **Build it**: generate/validate server-side (scaffold already does this for `Item.id`). |
| **No idempotency** on a retryable POST | **Build it** only if retries plausibly matter (payments, orders); otherwise **mention it**. |
| **Cache/DB divergence** — no invalidation on write | Already handled (`Cache.invalidate`, §4) — reuse the pattern for any new cached read. |
| **Blocking calls inside an `async def`** — a sync DB/network call blocks the whole event loop | **Already avoided**: the scaffold's routes/services are plain `def`, so FastAPI runs them in a threadpool safely. If you (or the AI) convert something to `async def`, every call inside must go async too (`asyncpg`, `redis.asyncio`) — never mix. One of the two bugs DigitalOcean is reported to specifically grade for. |

**This table is the audit checklist DigitalOcean is reported to grade on, not just a design-phase exercise.** Prompts are reportedly structured so AI-generated code confidently produces exactly two bugs from this table — a write race or a blocking async call — to see whether you catch them rather than accept the output at face value. Re-run this table against any AI-generated diff, not just at design time.

If the prompt is small with none of the above genuinely in play, say so, keep it simple, and skip to §4.

### Likely prompt patterns (unofficial — third-party-sourced, not confirmed by DigitalOcean; a bonus, not a substitute for the process above)

- **Data ingestion + processing API** (the recruiter's own wording, so the most likely shape): batch/file intake → validate → persist → process/aggregate → query results. Start from §4.20 and rename `EventIn` and the aggregate. The graded traps are double processing by concurrent workers and read-modify-write aggregates, both pre-empted there.
- **Cloud Resource Quota / Usage Limit Manager** — cap usage against a preset quota. The natural AI-generated bug is the write-race trap above: `check quota, then create` races under concurrency. Fix: one atomic statement — `UPDATE ... SET used = used + 1 WHERE used < limit RETURNING used`, not two steps.
- **High-frequency telemetry / cache with origin-outage resilience** — must keep serving through an origin/DB outage instead of cascading the failure. Intake is §4.20. For the serving side, extend `app/cache.py`'s `get_or_set` so that on loader failure it falls back to the last-known-good cached value (even past TTL), and add a small circuit breaker (stop calling after N failures, retry after a cooldown).
- **Rate limiter with tier-based quotas** — sliding-window algorithm, free/pro tiers with different limits, sub-50ms responses, per-client concurrency safety. Store window state in Redis (`INCR` + `EXPIRE`, or a sorted set for a true sliding window), not in-process — the app is meant to scale horizontally and in-memory counters don't survive that. The graded trap here is the same check-then-act race as the quota manager: use `INCR`'s atomicity (or a Lua script for multi-step logic) instead of `GET` then compare-and-`SET`. Per-client key = tier lookup + fixed window/bucket math, no locks needed since Redis ops are already atomic.

If told which prompt you drew, jump to the matching notes; otherwise the general scaffold and pitfall scan (§1/§2/§4) cover any prompt in this format.

### Once design decisions are locked: hand off a review doc

The moment goals/non-goals, architecture, and the pitfall-scan calls are locked in, spawn a background subagent to write `design-decisions.md` at the project root — the user studies it before the walkthrough (intro), so start this now, not at the end of the build, and don't write it inline yourself; that's foreground time better spent on §4/§4.19.

Give the subagent the locked-in goals/non-goals, architecture, and every pitfall-scan row with its call and reasoning. Have it cover:
- **Goals & non-goals** — what's in scope, and what was deliberately left out and why.
- **Functional & non-functional requirements** — the functional list as confirmed, and the NFR table from §1 with every assumed default stated plainly, marking which were confirmed by the interviewer vs. assumed. "What did you assume, and what breaks at 100x?" is a standard walkthrough question.
- **Architecture** — the diagram and why it beats the alternatives (microservices, queue, multi-region) at this scope.
- **LLD choices** — which §2 patterns were used, and which were deliberately skipped.
- **Pitfall-scan results** — every risk row, tagged build/mention, one sentence on the actual mitigation.
- **Scaling talking points** — §3's answers, rewritten in first person against the code that actually got built.
- **Business trade-offs** — what was cut for time and what adding it back would take (§3), plus the downtime answer.
- **Rubric walkthrough** — one bullet per rubric row (intro table) pointing at the concrete file/endpoint/test that demonstrates it, so the user can show rather than tell: "validation: `models.py` bounds, try `POST /items {}`"; "observability: `curl /metrics`, the JSON log line with its request ID"; "testing: `make check`, the concurrency test and why it exists"; "automation: Makefile, CI file, one-command deploy".

Keep it skimmable — bullets over prose, one screen per section. Refresh it as the build deviates from the original design (it will); the §4.19 deploy wait is a natural point to do that.

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

**Code layout** (already in §4):
- `main.py`: thin routes.
- `service.py`: business logic, interfaces only, raises domain errors.
- `repository.py`: the only place touching Postgres.
- `cache.py`/`events.py`: Redis, wrapped.
- `models.py`: one Pydantic shape per concept, with validation.
- `deps.py`: wiring.

Cross-cutting concerns each get one module: `config.py` (env), `errors.py` (error → HTTP mapping), `observability.py` (logs/metrics/request IDs). New feature = new service function; new storage backend = new repository implementation. That layering *is* the extensibility answer.

## 3. Talking points for common HLD follow-ups

Current state → bottleneck → concrete next step, grounded in the actual code just written, not generic vocabulary.

**Traffic spike / going viral?** Current: single stateless FastAPI process; bottleneck: DB connections/CPU on one box. By effort: (a) horizontal scale — N stateless instances behind a load balancer, immediate since there's no in-memory session state, (b) cache hot reads, (c) a queue to absorb write bursts async, (d) rate-limit/backpressure at the edge.

**How would you cache this?** Hot read path → cache key = lookup key → TTL or write-through invalidation. Redis from the start (`app/cache.py`) since an in-process cache doesn't stay consistent across N instances. Cache-aside: miss → read DB → populate → return (`Cache.get_or_set`). Mention cache stampede (coalescing or jittered TTL fixes it). Fan-out → Redis pub/sub (`app/events.py`) before a dedicated broker.

**Scale the database?** First: indexes + the connection pool already in `PostgresItemRepository`. Second: read replicas — Postgres is already behind a repository interface, so routing reads to a replica is a swap at that seam. Third: sharding, only if pushed on scale — name the shard key and the cross-shard-query tradeoff.

**Consistency / race conditions?** Name the specific race in the actual app (counter increment, double-booking) and the fix: a unique constraint/transaction, `SELECT ... FOR UPDATE`, or an atomic increment — not a vague "add a lock." Strong consistency on core writes, eventual is fine for denormalized reads/counters.

**Reliability?** Idempotency key or upsert on retryable writes. Timeouts + backoff on outbound calls. Stateless app, so a crashed instance is just replaced.

**Deploy/monitor?** Already done by the time it's asked (§4.19), so describe what you built. It's containerized (non-root image with a healthcheck). Every push to main builds `app:<sha>`, applies `.do/app.yaml` pinned to that tag, and fails CI unless the live `/version` reports that SHA (§4.21); rollback is re-pointing at an older SHA, with no rebuild (§4.24). It emits JSON logs with request IDs, Prometheus metrics, and liveness vs readiness. Alert on symptoms: 5xx rate, p95 latency, `/ready` failing, and for ingestion, backlog depth/age (`pending_count`) plus a rising `failed` batch count. Next steps if pushed: Prometheus + Grafana scraping `/metrics`, OpenTelemetry tracing keyed on the same request ID, autoscaling, managed-DB standby nodes and read replicas, Terraform plan/apply in CI with Spaces-backed state (§4.21), and DOKS if App Platform is outgrown (§4.22).

**Ingestion at 100x?** Current: the API validates + stores + enqueues in one transaction, and N workers drain a Postgres queue. In order of effort:
- (a) scale API replicas and `--scale worker=N`: both are stateless, and `SKIP LOCKED` makes N workers safe;
- (b) `COPY` instead of `unnest` for huge batches, and `LISTEN/NOTIFY` instead of polling;
- (c) partition `events` by time and add a retention job;
- (d) past roughly thousands of batches/sec, move the queue to Redis Streams/SQS/Kafka with consumer groups, behind the same repository seam, keeping idempotent consumers since delivery stays at-least-once.
Name the trade-off: Postgres-as-queue buys transactional enqueue and zero extra infra at the cost of peak throughput.

**Configuration / secrets?** Everything is env (§4.5): the same image runs in CI, locally and in prod, and bad config fails at startup. Secrets never touch git: App Platform injects DB credentials through bindable vars (`${db.DATABASE_URL}`), CI holds the DO token as a secret, and the Droplet has a `.env`. Next step: App Platform `type: SECRET` env vars or a secrets manager.

**Business trade-offs / "what would you do with more time" / downtime windows?** Expect this alongside the technical questions — DigitalOcean frames the post-build conversation as covering both. Ground it in what you actually cut, e.g. "skipped read replicas and HA — no payoff at this scale, and the repository seam (§2) makes adding one later a config change, not a rewrite." For downtime: stateless instances mean a rolling restart is zero-downtime; the one real SPOF is non-replicated Postgres/Redis, and the honest answer is a maintenance window or managed failover, not built here for time. Naming the real gap and its cost/benefit beats pretending it's handled.

## 4. Scaffold — `scaffold/`, copy it in, then adapt

The code lives next to this file in **`scaffold/`** (e.g. `~/.claude/skills/interview-kit/scaffold/`, or `interview-kit/scaffold/` in the repo). Copy the whole tree into the empty project root, dotfiles included, and adapt per §4.18:
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
| 4.4 | `backend/Makefile`, `pytest.ini`, `ruff.toml` | The one command surface: `install up run test test-int lint fmt check image deploy app-deploy app-rollback deployed`. Install, rsync/ssh and `doctl` steps have timeouts (skipped if neither `timeout` nor `gtimeout` exists). Recipe lines need real tabs if you ever retype it |
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
| 4.21 | `.github/workflows/ci.yml` | Lint → tests → Postgres integration → image → auto-deploy on main, verified by SHA |
| 4.23 | `infra/main.tf`, `.do/app.yaml` | Terraform (registry, managed PG + Valkey, optional Droplet + firewall) and the App Platform spec |

### 4.17 Setup commands

**Preflight the provided laptop first (~1 min).** Don't assume anything from your own machine exists on it:
```bash
for t in git python3 uv docker node make doctl terraform jq ssh timeout gtimeout; do printf '%-9s' $t; command -v $t >/dev/null && echo ok || echo MISSING; done
docker info >/dev/null 2>&1 && echo "docker daemon ok" || echo "docker daemon DOWN"
```
- **No `uv`:** `curl -LsSf https://astral.sh/uv/install.sh | sh` (or `brew install uv`, or `python3 -m pip install --user uv`).
- **No `timeout` (stock macOS):** the Makefile falls back to running unbounded. For ad-hoc commands, use `gtimeout` from `brew install coreutils`, or just watch for hangs.
- **No Docker locally:** unit tests don't need it (`make test`). For a real DB, create the Droplet early (§4.19), run `docker compose up -d --wait postgres redis` there, and tunnel with `ssh -N -L 5432:127.0.0.1:5432 -L 6379:127.0.0.1:6379 root@<ip> &`. `deps.py`'s localhost defaults then just work.
- **No `doctl`/`terraform`:** `brew install doctl terraform`, or use the DigitalOcean web console (§4.19).

Then, after the copy step at the top of §4 (`.gitignore` comes with it):
```bash
git init && git add -A && git commit -m "Scaffold from interview-kit"
cd backend && make install > /tmp/install.log 2>&1 && make check   # lint + tests green before touching anything
```
Then start these in the background, each logged so you can check progress without blocking. Use `uv run` (which the Makefile does), not `source .venv/bin/activate`: activation doesn't carry over to a new shell or tool call.
```bash
# from backend/
make up                                  # postgres + redis, blocks until healthy
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

### 4.19 Deploy to DigitalOcean — required, first deploy by ~minute 30

DigitalOcean requires the prototype live on their platform. There are two targets, and the same image, config and `/version` check work on both:

| | **App Platform (PaaS)** — recommended | **Droplet (IaaS VM)** — fallback |
|---|---|---|
| What runs it | DO runs your container: `api` ×2 + `worker`, TLS, rolling deploys, health-gated traffic, restarts, alerts | Your VM runs `docker compose` |
| Data | Managed Postgres + Managed Valkey (backups, failover option, private networking) | Postgres/Redis containers on the same box (a SPOF, named in §3) |
| Infra as code | `infra/main.tf` (clusters, registry) + `.do/app.yaml` (the app) | `infra/main.tf` with `create_droplet=true` (Droplet + Cloud Firewall) |
| Auto-deploy on push | CI → DOCR image tagged with the SHA → app_action applies the spec (§4.21) | CI → `make deploy` over SSH (§4.21) |
| Without GitHub | `make app-deploy REGISTRY=…` | `make deploy HOST=…` |
| Time to first deploy | ~15 min (managed DBs take ~5-10 min to provision; start them first, in the background) | ~5-10 min |
| Walkthrough story | "managed, horizontally scaled, zero-downtime, alerting — the production answer" | "one box, clean seams; App Platform is the next step" |

Pick App Platform when the DO token works and there's ~15 min of slack before the first deploy is due. Pick the Droplet when time is tight or anything about App Platform fights you. Switching later is only a deploy target change: same image, same env vars.

**Shared first steps (both targets):**
```bash
ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519     # provided laptop has no key
doctl auth init                                       # paste the provided API token (or: export DIGITALOCEAN_TOKEN=...)
export DIGITALOCEAN_TOKEN=<same token>                # Terraform reads this
```
No `doctl`? `brew install doctl`, or do the console equivalents: Create → Databases / Container Registry / Apps. No Terraform? `brew install terraform`, or use the console; the resources are the same and `.do/app.yaml` still applies.

**App Platform target:**
```bash
(cd infra && terraform init && terraform apply -var registry_name=<globally-unique-name> -auto-approve) \
  > /tmp/tf.log 2>&1 &            # ~5-10 min for the DB clusters: build features meanwhile
# when `tail /tmp/tf.log` shows "Apply complete":
cd backend && make app-deploy REGISTRY=<registry_name> > /tmp/app-deploy.log 2>&1; tail -5 /tmp/app-deploy.log
```
`make app-deploy` builds for `linux/amd64` (a Mac builds arm64, which App Platform can't run), pushes `app:<sha>`, applies `.do/app.yaml` with `doctl apps create --upsert --wait`, and finishes with `make deployed` against the live URL. Not doing ingestion? Delete the `workers:` block from `.do/app.yaml`. Short on time or credits? Replace the two `databases:` entries with a dev database (`- name: db` / `engine: PG` / `production: false`, provisioned in about a minute, no Terraform) and set `REDIS_URL` to `""`: the app runs without a cache and `/ready` reports only the database.

**Droplet target:**
```bash
cd infra && terraform init && terraform apply -var registry_name=<name> -var create_droplet=true -var create_managed_databases=false \
  -var "ssh_public_key=$(cat ~/.ssh/id_ed25519.pub)" -auto-approve && terraform output droplet_ip
ssh root@<ip> 'mkdir -p /root/app && echo POSTGRES_PASSWORD=$(openssl rand -hex 16) > /root/app/.env'   # once, before first deploy
cd ../backend && make deploy HOST=<ip> > /tmp/deploy.log 2>&1; tail -5 /tmp/deploy.log
```
Wait about a minute after creation for cloud-init to install Docker (`ssh root@<ip> docker version`). Without Terraform: in the console, create a Droplet from Marketplace "Docker on Ubuntu" with your key. `make deploy` rsyncs the backend, builds on the box with `GIT_SHA` stamped in, runs `docker compose -f docker-compose.yml up -d --build --wait` (the override is excluded, so Postgres/Redis stay unpublished), curls `/ready`, and runs `make deployed`. Scale the worker with `ssh root@<ip> 'cd /root/app && docker compose -f docker-compose.yml up -d --scale worker=3'`.

Either way: when it's slow, `tail` the log, or check `doctl apps logs <app-id> api --type run` / `ssh root@<ip> 'cd /root/app && docker compose logs --tail 50 app'`. Don't re-run blind. Verify `/ready` plus one real golden-path request from outside before defense prep: a deployed-but-broken app is worse than none. Frontend too? `npm run build` and add a `static_sites:` component (App Platform) or serve `frontend/dist` from nginx (Droplet).

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

### 4.21 CI/CD: every push to `main` deploys, pinned to its commit — `.github/workflows/ci.yml`

```
push/PR ──> test job: ruff ─> unit ─> integration (Postgres service) ─> image build
push to main, tests green ──> deploy-app-platform:                         ──> deploy-droplet (alternative):
   docker build --build-arg GIT_SHA=<sha> ─> push DOCR app:<sha>              make deploy HOST=... (rsync, build on box,
   ─> app_action applies .do/app.yaml with IMAGE_TAG=<sha>                    --wait, /ready, make deployed)
   ─> curl <live_url>/version == <sha> or the job fails
```
- **Every commit on main is deployed automatically.** Deploys queue (`concurrency`, never cancelled mid-flight), so the last one to finish is always the newest commit.
- **What gets deployed is the commit, not "latest".** The image tag *is* the SHA, and the spec that references it is applied in the same step. The final step proves the live app reports that SHA, so a deploy that silently kept the old version fails the pipeline.
- **The IaC is applied on every push too.** `.do/app.yaml` goes through app_action on each deploy, so changing `instance_count`, an alert, an env var or a health check is a reviewed commit, applied by CI like code. Drift gets overwritten on the next deploy.
- **Setup (3 min, once):**
  1. Repo secret `DIGITALOCEAN_ACCESS_TOKEN` (read/write App Platform + registry).
  2. Repo variable `DOCR_REGISTRY` (from `terraform output registry`).
  3. For the Droplet job instead: variable `DROPLET_HOST` + secret `DROPLET_SSH_KEY`.
  Unset variables skip the job rather than fail it, so the workflow is safe to commit first.
- Needs a GitHub repo you can push to from the provided laptop (recruiter question 3, §0). Without one, `make app-deploy` / `make deploy` run the same steps by hand. Commit the workflow anyway: it's reviewable evidence of the pipeline.
- Validated with `actionlint`; not executed on GitHub. Jobs: `test` (Postgres service container), `deploy-app-platform` (runs when `vars.DOCR_REGISTRY` is set), `deploy-droplet` (when `vars.DROPLET_HOST` is set); both deploy jobs use `environment: production` and one `deploy-production` concurrency group.

**Infra changes through CI too (next step, not needed in 3 hours):** Terraform state has to be shared first. DO Spaces is S3-compatible, so put this in `infra/main.tf`'s `terraform {}` block (validated with `terraform validate`):
```hcl
  backend "s3" {
    endpoints                   = { s3 = "https://nyc3.digitaloceanspaces.com" }
    bucket                      = "<spaces-bucket>"
    key                         = "interview/terraform.tfstate"
    region                      = "us-east-1" # ignored by Spaces, required by the backend
    skip_credentials_validation = true
    skip_requesting_account_id  = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_s3_checksum            = true
  }
```
Export the Spaces access keys as `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`. Then add a job that runs `terraform plan` on PRs touching `infra/` (posted for review) and `terraform apply -auto-approve` on main. Say it rather than build it: in a one-person 3-hour session, local state + `.do/app.yaml` through CI is the right cut.

### 4.22 DigitalOcean's cloud offerings — what exists and when to reach for it

| Category | Product | What it is | In this interview |
|---|---|---|---|
| **Compute** | **Droplets** | VMs (Basic, General Purpose, CPU-/Memory-Optimized, GPU); Marketplace images like "Docker on Ubuntu" | Fallback deploy target (§4.19) |
| | **App Platform** | PaaS for containers/buildpacks: `services` (HTTP), `workers`, `jobs` (PRE/POST_DEPLOY, scheduled), `static_sites`, `functions`. TLS, rolling deploys, health checks, alerts, logs, autoscaling on dedicated instances | **Recommended target**; spec = `.do/app.yaml` |
| | **DOKS** (Kubernetes) | Managed Kubernetes, free control plane (HA control plane optional) | Mention only: "if we outgrew App Platform or needed custom networking/sidecars" |
| | **Functions** | Serverless functions | Mention only (event hooks, cron) |
| **Data** | **Managed Databases** | PostgreSQL, MySQL, MongoDB, **Valkey** (Redis-compatible; replaced Managed Redis in 2025), Kafka, OpenSearch. Automated backups + point-in-time recovery, standby nodes for automatic failover, read-only replicas, PgBouncer connection pools, trusted sources, VPC | PG = source of truth, Valkey = cache (`infra/main.tf`). "HA?" → standby node (`node_count = 2`); "read scale?" → read replica behind the repository seam |
| | App Platform **dev database** | Single small Postgres attached to one app (~$7/mo), no HA | The fast/cheap path (§4.19) |
| **Storage** | **Spaces** | S3-compatible object storage with built-in CDN | Raw uploads/archives for ingestion at scale; Terraform remote state (§4.21) |
| | **Volumes** | Block storage attached to Droplets | Only for Droplet-hosted Postgres data |
| **Containers** | **Container Registry (DOCR)** | Private registry; starter (free, 1 repo, 500 MiB), basic ($5, 5 repos, 5 GiB), professional | Holds `app:<sha>` images (basic tier: starter fills after a few pushes; untagged layers count until garbage-collected) |
| **Networking** | **VPC** | Private network per region (default one exists) | App Platform ↔ managed DBs traffic stays private |
| | **Load Balancers** | Regional L4/L7 LBs with health checks (Droplets/DOKS) | "N Droplets behind an LB" answer; App Platform has one built in |
| | **Cloud Firewalls** | Stateful allow-lists attached to Droplets or tags | Droplet target: only 22/80 in (`infra/main.tf`) |
| | **Reserved IPs, DNS** | Static IPs you can move between Droplets; managed DNS | Blue/green on Droplets: swap the reserved IP |
| **Ops** | **Monitoring** | Droplet metrics + alert policies (CPU/mem/disk/bandwidth); App Platform per-component metrics and alerts | App alerts in `.do/app.yaml` (deploy failed, CPU, p95) |
| | **Uptime** | External HTTP checks from multiple regions + latency/down/SSL-expiry alerts | 1 min in the console on `/ready`; name it as the SLO probe |
| | **Log forwarding** | App Platform log destinations (Datadog, Logtail, Papertrail, OpenSearch) | Our JSON logs are ready to forward, unchanged |
| **Access / IaC** | API tokens (scoped), Projects, Teams; `doctl`, Terraform provider, Pulumi, app spec, GitHub Actions (`app_action`, `action-doctl`) | Everything in §4.19–§4.23 |

Talking-point shape: "I used App Platform because the managed pieces (TLS, rolling deploys, health-gated traffic, managed DB failover and backups) are exactly what I'd otherwise hand-build, and the app spec keeps it all in git. If requirements outgrew it, DOKS is the step up, and the app wouldn't change: same image, same env config."

### 4.23 Infrastructure as code: `infra/main.tf` + `.do/app.yaml`

This is a two-layer split, and the split is the design point to say out loud:
- **`infra/main.tf` (Terraform)**: long-lived, stateful, slow-to-create infrastructure (registry, Postgres, Valkey, optional Droplet + firewall, project). It changes rarely and is applied deliberately.
- **`.do/app.yaml` (App Platform spec)**: the app itself (components, scaling, health checks, alerts, env, DB attachments). It changes with the code, so CI applies it on every push, pinned to the commit.

Terraform *can* manage the app too (`digitalocean_app`), but then every CI image-tag change becomes Terraform drift. This split gives each layer one owner.

- **`infra/main.tf`** variables: `registry_name` (required, globally unique), `name` (`interview`), `region` (`nyc3`), `create_managed_databases` (true), `create_droplet` (false), `ssh_public_key`. It creates a DOCR registry (basic tier), `interview-pg` (PG 16) and `interview-cache` (Valkey 8) single-node clusters, an optional Droplet (Docker via cloud-init) + Cloud Firewall (22/80 in), and a Project grouping them.
- **`.do/app.yaml`**: `api` service (DOCR `app:${IMAGE_TAG}`, ×2 `apps-s-1vcpu-1gb`, readiness `/ready`, liveness `/health`, CPU and p95 alerts), `worker` (same image, `python -m app.worker`), `db`/`cache` attached to the Terraform clusters, env from bindable vars, and app-level deploy/domain-failure alerts.
- **`cluster_name`s** in the spec must match Terraform's `${var.name}-pg` / `-cache`. Keep the default `name = "interview"`, or change both.
- **The database** is Postgres's default `defaultdb` as `doadmin`, reached via `${db.DATABASE_URL}` (TLS, `sslmode=require` included). A dedicated DB/user is `db_name`/`db_user` in the spec: a 2-line hardening step.
- **Schema setup** runs in each process at startup under a Postgres advisory lock (§4.9). Without the lock, `api` ×2 + `worker` booting together crash on `CREATE TABLE IF NOT EXISTS` (reproduced 10/10). The production answer is a real migration tool (Alembic) run once per deploy as a `jobs:` entry with `kind: PRE_DEPLOY`.
- **Validation:** Terraform passes `validate` + `fmt`. The app spec was checked strictly against DigitalOcean's OpenAPI schema: every field and enum passes, except top-level `alerts`/`envs` and service `alerts`, which the public schema omits but the App Spec reference documents. Neither has been applied to a real account yet. The first real `terraform apply` / `make app-deploy` is the smoke test, so do it early.

### 4.24 Which commit is live? (answer it in 5 seconds, from anywhere)

Every build is stamped at build time (`GIT_SHA` Docker build arg, from `git rev-parse HEAD`; `-dirty` if the tree had uncommitted changes, meaning it matches no commit):

| Where | How | Answers |
|---|---|---|
| **The app itself** | `curl $URL/version` → `{"git_sha", "build_time", "env"}` | What is running right now |
| **Every response** | `x-app-version` header | Which build served *this* request (both versions answer during a rolling deploy) |
| **Every log line** | `"version": "<sha12>"` field | Which build logged this error |
| **Metrics** | `app_build_info{git_sha="…"} 1` | Graph the rollout; alert if two versions coexist too long |
| **vs. your checkout** | `make deployed URL=$URL` | `UP TO DATE`, or `DIFFERENT` + `git log` of exactly the commits not yet live |
| **CI** | the deploy job's final step asserts `/version == github.sha`; GitHub → *Environments → production* lists each deployment with its commit and URL | What was deployed when, and that it actually took |
| **App Platform** | `doctl apps list-deployments <app-id> --format ID,Cause,Phase,Created`; `doctl apps get <app-id> -o json \| jq -r '.[0].active_deployment.spec.services[] \| "\(.name) \(.image.tag)"'` | Deployment history; the SHA each component runs |
| **Registry** | `doctl registry repository list-tags app` | Every SHA ever built (all rollback candidates) |
| **Droplet** | `ssh root@<ip> "docker inspect \$(docker ps -qf name=app) --format '{{index .Config.Labels \"org.opencontainers.image.revision\"}}'"` | The image's OCI revision label |

**Rollback** = point the app at an older SHA whose image already exists, with no rebuild: `make app-rollback REGISTRY=<name> SHA=<old sha>` (or *Rollback* on a previous deployment in the App Platform console). On the Droplet, `git checkout <sha> && make deploy HOST=…`. With CI, a `git revert` pushed to main is the auditable rollback: it redeploys through the same verified pipeline.

## 5. Using Cursor for the live build

The interview runs in Cursor Enterprise on **their** laptop, not Claude Code on yours. This section is the bridge.

**What the recruiter's note tells you:**
- **Models:** built-in Claude 3.7 Sonnet and GPT-4o. Pick Claude 3.7 Sonnet for Agent/multi-file work and stop thinking about it (§5.4). Both are older models, so expect confident race conditions and blocking calls: the §1 audit matters more, not less.
- **Privacy mode is on:** no effect on the workflow, except Background Agents may be unavailable. Use a second chat tab for §5.3 instead.
- **Shortcuts they named:** **Cmd+L** chat (`@codebase` for repo-wide questions), **Cmd+K** inline edit on a selection, **Cmd+I** Composer/Agent (multi-file edits + terminal). Use Cmd on macOS, Ctrl elsewhere.

### 5.1 Getting the conventions and scaffold onto a laptop you don't own

This depends on recruiter question 5 (§0):
- **Allowed to clone/fetch a personal repo or gist:** keep this `SKILL.md` and `scaffold/` in it. `git clone`, copy `scaffold/.` into the project (§4), then `make install && make check` gets you green in about 2 minutes. The rules file comes with it.
- **Not allowed:** create the rules file first (Cursor Agent: "create `.cursor/rules/interview-conventions.mdc` with …", then type or dictate the short version below). Then have Agent generate §4 one layer at a time with the scaffold prompt below. Review every file against the pitfall table. The layering and quality checklist should be memorized going in, not looked up live.

Cursor reads **Project Rules**: `.mdc` files under `.cursor/rules/`, auto-attached to chat/agent/Tab context. The kit's is `scaffold/.cursor/rules/interview-conventions.mdc` (always applied): the layering, validation and ingestion rules, the two graded AI bugs to audit for (read-modify-write races, blocking calls in `async def`), and the timed-build habits (timeouts, uv only, small commits, deploy early, keep `/version` working, infra changes only in IaC). Know its points well enough to retype a short version if you can't bring files.

**Scaffold prompt for Agent (Cmd+I)**, used only when you can't bring §4's files. Send one message per step, and review and run `make check` between steps:
1. "Create backend/ with requirements.txt (fastapi, uvicorn[standard], pydantic, python-multipart, psycopg[binary], psycopg-pool, redis, prometheus-client), requirements-dev.txt (pytest, httpx, ruff), a Makefile with install/up/run/test/test-int/lint/fmt/check/deploy/app-deploy/deployed targets using `uv run` (GIT_SHA from git passed as a Docker build arg), pytest.ini, ruff.toml, a non-root Dockerfile with a /health HEALTHCHECK, and docker-compose.yml (postgres, redis with healthchecks, app) plus a docker-compose.override.yml that publishes postgres/redis on 127.0.0.1 only."
2. "Add app/config.py (frozen Settings dataclass from env), app/observability.py (JSON log formatter, request-id contextvar + middleware setting x-request-id, Prometheus counter/histogram labeled by route template, /metrics), app/errors.py (AppError subclasses NotFound/Conflict/PayloadTooLarge/Unavailable, handlers producing {error:{code,message,request_id,details}} for AppError, validation errors, HTTPException, psycopg.OperationalError→503, Exception→500)."
3. "Add models/repository (Protocol + InMemory + Postgres with a shared psycopg_pool, atomic UPDATE…COALESCE…RETURNING for partial updates)/cache (Redis errors degrade to a miss)/service/deps/main for <entity>, with /health, /ready, paginated list. Plain def routes only."
4. "Add tests/: conftest with dependency_overrides + fresh in-memory repo per test; API tests for CRUD, 422 envelope, 404 envelope with request id, pagination, 500 without leaking; a threaded concurrency test proving concurrent PATCHes to different fields both survive."
5. For ingestion: describe §4.20's design bullets verbatim and ask for the five ingest files + tests.

### 5.2 Cursor features worth using live

- **Tab** — always on, free. Best for repetitive shape-following code.
- **Cmd+K** — small, localized, well-specified edits; faster than a chat round-trip.
- **Agent/Composer (Cmd+I)** — the §5.1 scaffold steps if not pre-staged, and the §4.18 rename-and-extend pass. Always review the diff — a wrong assumption compounds across files fast.
- **Chat (Cmd+L) with `@codebase`** — "where else does this read-then-write pattern appear?" is a cheap audit sweep before each commit.
- **@-mentions** — reference existing code instead of re-pasting it.
- **Checkpoints** — skim the changed-files list after any multi-file edit before moving on.

### 5.3 Use dead time: parallelize research instead of idling

Any time you're blocked on something other than typing is wasted unless you fill it. The moment you ask a clarifying question, open a second chat tab (or a Background Agent, if privacy mode allows it) and research what comes next regardless of the answer. Batch questions (§0) so idle moments don't recur. Write the next file while a slow command runs instead of watching the terminal. Don't let research become its own rabbit hole.

### 5.4 What NOT to reach for live

Don't hand-tune Cursor settings/models mid-interview. Don't send Agent mode a large open-ended ask without the specific layering/entity first — an unscoped prompt needs a costly second pass. Don't fight Tab over stylistic preferences that don't matter.

### 5.5 Talking to the interviewer about tool use

The recruiter explicitly encourages the built-in AI, so use it openly. What matters is visibly making the architecture/pattern decisions yourself (§1-§3) and visibly auditing the output. Say "the agent wrote a read-then-write here; that loses updates under concurrency, so I changed it to one atomic statement" out loud when it happens. That sentence is the grade.

## 6. Orchestration checklist

1. **Preflight the laptop (~5 min)** — §4.17's tool check; install `uv` if missing; generate an SSH key; confirm DigitalOcean access works (console login or `doctl auth init`). Get the rules file in place (§5.1).
2. **Pick the prompt, if given a list** — §1: favor a prepped pattern (ingestion first) or the smallest clear scope.
3. **Read the prompt** — restate entities/actions in 1-2 sentences, name the time budget (§0) out loud.
4. **Ask once, then stop asking** — §1's batch of clarifying questions, in one shot, covering **functional** requirements (plus the ingestion questions if it's that shape) and **non-functional** ones. Ask scale and consistency with a default lean; assume and state the rest in one line. Wait for the answer (or an explicit "use your judgment") before doing anything below, then don't reopen it.
5. **Design (~10 min)** — §1: sketch the simplest architecture, state goals/non-goals, run the pitfall scan. The moment this is locked in, spawn the background subagent that writes `design-decisions.md` — don't wait for it, move to scaffolding.
6. **Scaffold + first deploy (~10-15 min)** — §4: copy `scaffold/.` in (+ `strip-ingest.sh` / `rm -rf frontend` as needed), `git init` + commit (§4.17), `make install && make check` green, `make up`, `make run`, `curl /ready`. Then deploy the untouched scaffold (§4.19): `terraform apply` (already running in the background since preflight) → `make app-deploy REGISTRY=…`, or the Droplet path. Finish with `make deployed URL=…`. Commit.
7. **Core feature (~70 min)** — §4.18 adapt pass (+ §4.20 for ingestion) + §2 judgment. For every endpoint, add a test in the same commit. Before accepting any AI-generated chunk, check it against §1's pitfall table, especially the write-race, double-processing and blocking-call rows — that check is what's graded. `make check` then commit after each adapted file; redeploy at each working milestone (`git push` with CI, else `make app-deploy`/`make deploy`).
8. **Automation + ops touches (~15-20 min)** — commit `.github/workflows/ci.yml` (§4.21), set `DOCR_REGISTRY` + `DIGITALOCEAN_ACCESS_TOKEN` and push if a repo is available (every later push auto-deploys); add the pre-commit hook; confirm `/metrics`, JSON logs with request IDs, `/ready` degrading when Redis is stopped. Put any new tunable in `config.py`.
9. **Frontend (only if §1 said so, ~30 min)** — golden path > loading/error > (no) polish, per §0's zero-CSS rule.
10. **Final deploy + verify (~10 min, required)** — push (or `make app-deploy`/`make deploy`), `make deployed URL=…` shows UP TO DATE, then from outside: `/ready`, one real golden-path request, `/metrics`. Commit once verified live.
11. **Defense prep (~15-20 min, can overlap with deploy waits)** — refresh `design-decisions.md` against what actually got built, including the rubric walkthrough (§1). Then read through it: that's the user's prep, since the user answers the walkthrough, not the agent.
12. **Final pass** — have a one-sentence close ready: what's built, how it's verified (tests, CI, live URL), what's out of scope and why, first three next steps.

**Boundaries**: don't let architecture discussion eat build time — lock it in and adjust as you build. Don't introduce infrastructure beyond Postgres+Redis unless asked live. If behind schedule, cut features before cutting validation, error handling, tests, observability or the deployment step. Those are the rubric: a smaller, well-structured, tested, actually-deployed API outscores a larger messy or undeployed one.
