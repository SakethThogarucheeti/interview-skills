---
name: interview-kit
description: Kit for DigitalOcean's timed build-and-deploy interview (3h: build a REST API for data ingestion + processing and deploy it live on DigitalOcean, from an Ubuntu 24 dev container; Claude Code/Cursor permitted). Gates one batch of clarifying questions, runs a pitfall scan on every AI-generated diff (write races, blocking calls), hands off design-decisions.md, and ships a verified FastAPI+Postgres+Redis scaffold with an ingestion worker, tests, deploy-on-push to App Platform, Terraform, and a which-commit-is-live trail. Use when the user shares the interview prompt, asks about its design, scaling or DigitalOcean deploy, or wants the scaffold.
---

# Interview kit — timed full-stack build

## Setup — only if `reference/` isn't beside this file

This file may have been pasted in alone. Everything else lives in the repo, and one command turns it into a ready project for Cursor or Claude Code (~30 s):
```bash
git clone -q --depth 1 https://github.com/SakethThogarucheeti/interview-skills ~/prep
~/prep/interview-kit/into-project.sh ~/app            # scaffold + this playbook in ~/app/.kit + git init + ./preflight.sh
```
**Not in the interview's Ubuntu 24 container** (practising on Arch/macOS, where preflight's `apt` installs fail): after `into-project.sh`, run everything through the dev container: `./dev.sh ./preflight.sh`, `./dev.sh bash -c 'cd backend && make check'`, or `./dev.sh` for a shell. Details and gotchas: `reference/scaffold.md` §4.17.

**The DigitalOcean token** goes in once, as `DO_TOKEN=<token> ./preflight.sh` (or `./dev.sh ./preflight.sh`), which logs doctl in; Terraform reuses that login. Never echo it or write it to a file. Pasting it into chat or typing `! DO_TOKEN=…` both put it in the transcript; to avoid that, the user runs the command in a separate terminal. Revoke it after the session.

(Agents: the repo README's "AI agent: set this up" section is the full procedure, including clearing preflight's list for the user.)
Then work in `~/app` (Cursor: File > Open Folder; Claude Code: `cd ~/app && claude`). Its `AGENTS.md` is the always-on rule set and points back here (`.kit/SKILL.md`). In that project, `reference/` means `.kit/reference/`, and the scaffold is already in the project root, so skip §4's copy step.

This file holds what's needed from minute one (brief, tactics, requirements gate, pitfall audit, LLD, checklist). Deeper material is in `reference/` and the code in `scaffold/`, both beside this file; read them when the step arrives (index before §6). Flow: requirements → design → LLD → scaffold → deploy → verbal defense. Claude Code is permitted live, so this kit can drive the actual build in the container (§5).

**Format** (DigitalOcean's confirmed shape): a 3-hour session, pick from a short list of assigned prompts, build it, deploy it live on DigitalOcean before time's up (§4.19). Then comes a walkthrough of design trade-offs and hypotheticals on scaling, traffic spikes, downtime and business constraints. The user, not the agent, answers that walkthrough, so hand off a `design-decisions.md` for them to study (§1).

**This session's brief (from the recruiter):**
- **The task:** "build and deploy a functional **REST API** service that handles **data ingestion and processing**". So the default is API-only, and the §4.20 ingestion add-on is the likely core.
- **Language:** Go, Python, Java or TypeScript/Node. This kit is Python.
- **Environment:** a provided laptop running **VS Code or Cursor, bridged to an Ubuntu 24 Docker container**. Passwordless `sudo` (apt/brew). Preinstalled: `gh`, `doctl`, `s3cmd`, `jq`, `yq`, neovim. Not listed, so assume absent until preflight (§4.17): Docker inside the container, Terraform, `uv`. (Preflight installs `doctl`, Terraform and `uv` if missing; on a non-Ubuntu host use `./dev.sh`, see Setup.)
- **AI:** GitHub Copilot, **Claude Code** and Cursor are all permitted, plus Chrome and docs. You own every generated line (§1's audit). Cursor Enterprise's built-in models are Claude 3.7 Sonnet / GPT-4o with privacy mode on.
- **Cloud:** DigitalOcean credits provided, and deploying during the session is expected.

**The rubric, and where the kit already covers it.** "Production-ready thinking rather than just a working script":

| Graded area | What they look for | Covered by |
|---|---|---|
| **Engineering quality** | clean organization, sensible validation, meaningful error handling | route/service/repository layering (§2); field bounds + `extra="forbid"` (§4.8); domain errors → one JSON error envelope with request ID, 404/409/413/422/503 (§4.7) |
| **Testing** | a *structured* approach to automated verification | API / unit / concurrency-regression / Postgres-integration tests, isolated fixtures, no infra needed (§4.14, §4.20) |
| **Automation & workflow** | consistent delivery, streamlined lifecycle | Makefile as the single command surface, ruff lint/format, pre-commit hook, every push to main auto-deploys (App Platform builds from GitHub, or CI builds and verifies by SHA; §4.19, §4.21); IaC: `infra/main.tf` + `.do/app.yaml` (§4.23); one-command deploy/rollback (§4.19, §4.24) |
| **Operational excellence** | observability, configurability, scalability in a live environment | JSON logs + request IDs, Prometheus `/metrics`, `/health` vs `/ready` (§4.6, §4.13); all config from env (§4.5); graceful degradation + shutdown; stateless app + horizontally scalable workers (§4.20); DB never exposed (§4.3); `/version` + `x-app-version` + log `version` field answer "which commit is live?" (§4.24) |

Keep the scaffold's quality features even when you're behind. Cut features, never these: they *are* the grade. Name each one out loud in the walkthrough.

**Priority order**: working, deployed demo > code that looks deliberately structured on a skim > sharp answers to those questions. Working-but-plain beats brilliant-but-unfinished; undeployed beats nothing.

**What's actually graded**: DigitalOcean's own hiring writeup says they watch where you lean on AI (boilerplate — fine) vs. what you check by hand (concurrency, blocking calls) — prompts are deliberately structured so naive AI output confidently introduces a race condition or a blocking call, to see if you catch it. Audit every AI-generated chunk against §1's pitfall scan before accepting it — that audit *is* the interview.

## 0. Time-compression tactics (apply throughout)

The real enemy in a 3-hour window is idle/serial time, not typing speed — and a portion of it now has to include a working deployment, so there's less slack than "3 hours" sounds like.

- **Ask once, then move on.** Clarifying questions (§1) are a hard gate — batch them into one shot, wait for the answer, don't implement before it. But it's one gate, not a habit: once answered, decide every remaining gap yourself and build.
- **Fill dead time, never idle.** The moment a question is asked, fire a parallel task on what you'll need next — Claude Code: a `fork`/background Agent; Cursor: a second chat tab or Background Agent (§5.3). This fills the wait, it doesn't replace it — still don't build on an assumed answer.
- **Decide, don't deliberate.** Default any choice that doesn't change the outcome; only ask what changes scope.
- **Timeout everything; log anything backgrounded.** A hung command with no timeout eats the clock silently; a slow one with no log forces you to babysit it. Wrap anything that could hang (installs, network/DB calls) in a timeout — the Bash tool's own parameter in Claude Code, or shell `timeout <n>s <cmd>` in an IDE terminal (the Ubuntu container has it). Redirect backgrounded processes (`uvicorn`, `npm run dev`, `docker compose up`) to a log file (`... > /tmp/x.log 2>&1 &`) so progress is checkable with `tail`/`grep` instead of blocking on it. Scope greps/finds to the relevant directory (`grep -r pattern app/`), never the repo root — crawling `node_modules`/`.venv`/`.git` wastes real time for zero signal.
- **Zero CSS.** No framework, no stylesheet, nothing beyond the scaffold's inline styles — hard rule from the start.
- **Use git, committed at every milestone and passing test.** `.gitignore` + `git init` before the scaffold goes in (§4.17), then a commit after each milestone/passing test — small and frequent, not one giant commit at the end. Makes a bad edit or a sideways tool call a `git checkout` away, not a rebuild. Commit history is also visible "workflow" evidence for the rubric.
- **Deploy early, redeploy often.** Get the untouched scaffold live (§4.19) right after it's running locally, then redeploy at each milestone (with App Platform building from GitHub, that's just `git push`). A deploy problem found at minute 30 is an annoyance; at minute 170 it's a fail.
- **Budget** (3h, API-only brief): ~5 min preflight the container (§4.17), ~5 min pick the prompt, ~10 min questions + design (§1), ~10 min scaffold in + green + **first deploy** (§4.17, §4.19; start `terraform apply` in the background right after preflight, since managed DBs take ~5-10 min), ~70 min core feature + tests (§4.18/§4.20), ~20 min automation + observability touches (§4.21), ~15 min final deploy + verify, ~20 min defense prep (§3), buffer. If a frontend is required, take ~30 min from the core feature, not from tests or deploy.

**Before the day: send the recruiter these (they invited questions).** Each answer removes a live unknown:
1. Is a frontend expected, or is the REST API (with Swagger `/docs`) the whole deliverable?
2. Can the container run Docker (`docker compose`)? It decides the local-DB and image-build paths (§4.17, §4.19).
3. Can I sign `gh` into my own GitHub account and connect it to the provided DigitalOcean account, so App Platform deploys on push?
4. Will DigitalOcean access be a console login, an API token, or both?
5. May I clone my own prep repo (this kit + scaffold) into the container and sign in to Claude Code with my own account?

## 1. Requirements & HLD (~10 min, don't exceed)

**If given a short list of prompts, pick one first.** Prefer whichever matches a pattern you've prepped ("Likely prompt patterns" below) or, failing that, the smallest, clearest scope — a prompt you can state in one sentence beats an ambiguous one, since ambiguity costs clarifying-question time you don't get back.

**Hard gate: ask before building — once.** The moment the prompt is shared, ask the batch of clarifying questions below in a single message and stop — no scaffolding, no code, until the user answers or says to use your judgment. This is a real stop: no implementation happens between asking and the response. Use dead time (§0) to research while waiting, not to build on assumed answers. Skip only what the prompt already answered.

**Once answered, stop asking and start building.** The gate fires exactly once, not per-decision. After the batch is answered (even partially), decide every remaining gap yourself (§0's "decide, don't deliberate") and move straight to design/build — no second round. Circling back costs more than a wrong default and reads as indecision. Exception: something that would force a visible do-over if guessed wrong (e.g. the prompt is ambiguous between two fundamentally different apps).

**Ask for functional *and* non-functional requirements — explicitly, by name.** Most candidates ask only "what should it do" and get graded down for never establishing scale, latency, or consistency targets. Cover both categories in the one batch, and say the words "functional" and "non-functional" out loud — the interviewer is listening for whether you separate them.

Batch every open question; skip only what doesn't change scope, stating that assumption instead. Output a short, explicit goals/non-goals statement — a decision to hold the build to.

**Functional — always ask, these change what you build:**
- **Core entities & actions** — create/read/update/delete what?
- **The one golden-path user story** — what must demonstrably work end-to-end at the demo?
- **Non-goals** — what you're explicitly not building (user accounts/OAuth — API keys are in, multi-tenancy, admin UI…).
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
| **Security** | Server-side validation/generated IDs; DB/Redis never exposed publicly (§4.3); DB password from env, not code; API-key auth + a per-client Redis rate limit ship in the scaffold (§4.25): every data route needs a key, prod refuses to start without `API_KEYS`, 429 + `Retry-After` over the limit. User accounts/OAuth only if asked. `CORS_ORIGINS=*` is a named demo default (§4.13). |
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
| **Spiky/bursty traffic** on a specific endpoint the prompt implies (viral link, vote surge) | **Already built**: per-client rate limit on every data route (§4.25); for a genuinely hot endpoint, give it its own tighter limit + confirm that read path uses the cache-aside. Otherwise **mention it**. |
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
- **Rate limiter with tier-based quotas** — sliding-window algorithm, free/pro tiers with different limits, sub-50ms responses, per-client concurrency safety. Store window state in Redis (`INCR` + `EXPIRE`, or a sorted set for a true sliding window), not in-process — the app is meant to scale horizontally and in-memory counters don't survive that. The graded trap here is the same check-then-act race as the quota manager: use `INCR`'s atomicity (or a Lua script for multi-step logic) instead of `GET` then compare-and-`SET`. Start from `app/security.py` (§4.25): it already has tiers (`name:key:limit`), a sliding-window counter in one atomic Lua script, 429 + `Retry-After`, and a 200-thread race test. Adapt the tier source (a table instead of env) and add per-endpoint limits if asked.

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

## 3–5. Reference files — read the one you need, when you need it

These sit next to this file (`.kit/reference/` in a project built by `into-project.sh`). § references elsewhere in the kit resolve here:

| § | File | Read it when |
|---|---|---|
| §3 | `reference/talking-points.md` | defense prep / writing `design-decisions.md`: scaling, spikes, downtime, deploy/monitor, consistency, config/secrets answers |
| §4, 4.1–4.18, 4.20, 4.25 | `reference/scaffold.md` | scaffolding: copy command, file map (what each `scaffold/` file owns), container preflight + setup (4.17), adapt-to-prompt pass (4.18), ingestion add-on design (4.20) |
| §4.19, 4.21, 4.23, 4.24 | `reference/deploy.md` | first deploy: paths A (App Platform from GitHub) / B (CI image) / C (Droplet), CI/CD, Terraform + app spec, which commit is live, rollback |
| §4.22 | `reference/do-offerings.md` | a walkthrough question about DigitalOcean products (managed DBs, Spaces, DOKS, LBs, monitoring) |
| §5 | `reference/live-build.md` | before the session: Claude Code vs Cursor in the container, working without the kit, tool-use etiquette |

The code itself is in `scaffold/`; `into-project.sh` puts it in the project root (Setup, top of this file).

## 6. Orchestration checklist

1. **Set up + preflight (~5 min)** — `into-project.sh ~/app` (Setup, top) builds the project and runs `./preflight.sh`, which checks tools, installs `uv` + Terraform, generates `API_KEYS` into `~/.api_keys.env`, starts `terraform apply` in the background once `doctl` is authed, and prints only what needs you (`doctl auth init`, `gh auth login`, the one-time GitHub link in the DO console). Do those, re-run `./preflight.sh`, open `~/app` in Cursor or run `claude` there (§5), move on.
2. **Pick the prompt, if given a list** — §1: favor a prepped pattern (ingestion first) or the smallest clear scope.
3. **Read the prompt** — restate entities/actions in 1-2 sentences, name the time budget (§0) out loud.
4. **Ask once, then stop asking** — §1's batch of clarifying questions, in one shot, covering **functional** requirements (plus the ingestion questions if it's that shape) and **non-functional** ones. Ask scale and consistency with a default lean; assume and state the rest in one line. Wait for the answer (or an explicit "use your judgment") before doing anything below, then don't reopen it.
5. **Design (~10 min)** — §1: sketch the simplest architecture, state goals/non-goals, run the pitfall scan. The moment this is locked in, spawn the background subagent that writes `design-decisions.md` — don't wait for it, move to scaffolding.
6. **Scaffold + first deploy (~10-15 min)** — §4: the scaffold is already in `~/app` (run `./strip-ingest.sh` / `rm -rf frontend` if the prompt says so, then commit). `make install && make check` green, `make up`, `make run`, `curl /ready`. Then deploy the untouched scaffold (§4.19): path A `gh repo create … --push` + `make app-create` once Terraform finishes, or path B/C. Finish with `make deployed URL=…`. Commit.
7. **Core feature (~70 min)** — §4.18 adapt pass (+ §4.20 for ingestion) + §2 judgment. For every endpoint, add a test in the same commit. Before accepting any AI-generated chunk, check it against §1's pitfall table, especially the write-race, double-processing and blocking-call rows — that check is what's graded. `make check` then commit after each adapted file; redeploy at each working milestone (`git push` on paths A/B, `make deploy` on C).
8. **Automation + ops touches (~15-20 min)** — `.github/workflows/ci.yml` is already in (§4.21): on path A its test job runs on every push; on path B set the secret + variable; add the pre-commit hook; confirm `/metrics`, JSON logs with request IDs, `/ready` degrading when Redis is stopped. Put any new tunable in `config.py`.
9. **Frontend (only if §1 said so, ~30 min)** — golden path > loading/error > (no) polish, per §0's zero-CSS rule.
10. **Final deploy + verify (~10 min, required)** — push (or `make deploy` on C), `make deployed` shows UP TO DATE, then `make e2e URL=…`: ~30 live checks (auth, CRUD + error envelopes, ingest → worker → exact totals under 20 concurrent writers, 429s) in about a minute. Rename its `/items` payloads when you rename the entity. Commit once verified live.
11. **Defense prep (~15-20 min, can overlap with deploy waits)** — refresh `design-decisions.md` against what actually got built, including the rubric walkthrough (§1). Then read through it: that's the user's prep, since the user answers the walkthrough, not the agent. If time allows, also hand over `API.md`: one curl example per endpoint against the live URL, so the user can drive the API themselves during the walkthrough. `make e2e` already covers the checks.
12. **Final pass** — have a one-sentence close ready: what's built, how it's verified (tests, CI, live URL), what's out of scope and why, first three next steps.

**Game-day time and token budget** (measured on a full live rehearsal):
- **Waits are DigitalOcean's, so overlap them.** Managed DBs ~6 min (start in minute 1 via `./preflight.sh`), first App Platform build ~5 min, each push ~3 min, CI deploy ~2.5 min. Never block on one in the foreground: log to a file, keep building, check the log.
- **One path.** Path A only; don't rehearse B/C or rollback live — describe them.
- **Tokens scale with context × turns, not command output.** Every turn re-reads the whole conversation (the rehearsal: 54M cached-read tokens vs 27k of tool output). Start the interview in a fresh session, `/compact` between phases (build → deploy → defense prep), and ask for batched steps ("write X, `make check`, commit, push") instead of many small checks.
- **Read by file map, not by sweep.** Name the files from §4's table in the request; don't let the agent read the whole scaffold.
- **Human-only steps come first**, all in minutes 0–5 (`doctl auth init`, `gh auth login`, the DO↔GitHub link), so nothing later waits on you.

**Boundaries**: don't let architecture discussion eat build time — lock it in and adjust as you build. Don't introduce infrastructure beyond Postgres+Redis unless asked live. If behind schedule, cut features before cutting validation, error handling, tests, observability or the deployment step. Those are the rubric: a smaller, well-structured, tested, actually-deployed API outscores a larger messy or undeployed one.
