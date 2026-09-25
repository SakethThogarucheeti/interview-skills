# Prep notes (for you, not the agent)

Read this before the day. The agent never reads it: its instructions are the project's `AGENTS.md` (the runbook)
and `interview-kit/SKILL.md` (design).

## The format

- **3 hours**: pick from a short list of prompts, build it, deploy it live on DigitalOcean before time's up. Then a
  walkthrough of design trade-offs and hypotheticals (scaling, traffic spikes, downtime, business constraints).
  You answer that part, not the agent. Study the `design-decisions.md` it writes.
- **The task** (recruiter's words): "build and deploy a functional **REST API** service that handles **data
  ingestion and processing**". So the default is API only, with the ingestion code as the core.
- **Language:** Go, Python, Java or TypeScript/Node. This kit is Python.
- **Environment:** a provided laptop with VS Code or Cursor, bridged to an Ubuntu 24 Docker container.
  Passwordless `sudo`. Preinstalled: `gh`, `doctl`, `s3cmd`, `jq`, `yq`, neovim. Probably not: Docker inside the
  container, Terraform, `uv` (preflight installs what it can).
- **AI:** Copilot, Claude Code and Cursor are all permitted, plus Chrome and docs. Cursor Enterprise's built-in
  models are Claude 3.7 Sonnet / GPT-4o with privacy mode on.
- **Cloud:** DigitalOcean credits are provided; deploying during the session is expected.

**What they watch** (DigitalOcean's own hiring writeup): where you lean on AI (boilerplate is fine) versus what
you check by hand (concurrency, blocking calls). Prompts are built so naive AI output adds a race or a blocking
call. Priority: working, deployed demo > code that looks deliberately structured > sharp walkthrough answers.

## Send the recruiter these first

1. Is a frontend expected, or is the REST API (with Swagger `/docs`) the whole deliverable?
2. Can the container run Docker (`docker compose`)?
3. Can I sign `gh` into my own GitHub account and connect it to the provided DigitalOcean account, so App Platform deploys on push?
4. Will DigitalOcean access be a console login, an API token, or both?
5. May I clone my own prep repo into the container and sign in to Claude Code with my own account?

## Time budget (3h, API only)

| Minutes | What | Runbook step |
|---|---|---|
| 0-5 | setup: README "AI agent: set this up"; human-only clicks (GitHub code, DO token, DO console link) all happen now | - |
| 5-15 | pick the prompt, one batch of questions, design | 1-3 |
| 15-30 | local green + first deploy of the untouched app | 4-5 |
| 30-150 | the prompt's features, a test per rule, commit per file, push per milestone | 6 |
| 150-165 | final deploy + `make e2e` | 7 |
| 165-180 | read `design-decisions.md`, rehearse the close | 8 |

UI required? Take ~30 min from features, never from tests or the deploy.

- **DigitalOcean's waits dominate, so overlap them.** Managed DBs ~6 min (started at minute 1 by preflight),
  first App Platform build ~5 min, each push ~3 min. Never block on one; keep building.
- **One deploy path (A).** Describe B/C and rollback in the walkthrough; don't rehearse them live.
- **Tokens scale with context x turns.** Start the interview in a fresh session, `/compact` between phases
  (build -> deploy -> defense), and ask for batched steps ("write X, check, commit, push").
- **Close:** one sentence each on what's built, how it's verified (tests, CI, live URL, `make e2e`), what's out of
  scope and why, and the first three next steps.

## Claude Code or Cursor in the container

The IDE runs on their laptop, bridged to the container where code and terminal live. Setup is the same for both.

- **Claude Code** (permitted, and the strongest option because the kit drives it): `curl -fsSL
  https://claude.ai/install.sh | bash`, then `cd ~/app && claude`, log in, paste the prompt. `CLAUDE.md` imports `AGENTS.md`.
- **Cursor** (expect a fresh Enterprise login with no rules, skills or MCP): **File > Open Folder -> `~/app`**, not
  `~/prep` or home. In Agent chat, send `/interview` plus the prompt. Don't spend time on settings.
- **Built-in models:** use the one they give you and stop switching. A weaker model makes the diff audit matter more.
- Useful Cursor features: Tab for repetitive edits; Cmd+K for small, well-specified edits; Agent (Cmd+I) for the
  rename-and-extend pass (always review the diff); Chat with `@codebase` for "where else is there a read-then-write?".
- **Fill dead time:** when waiting on an answer or a deploy, use a second chat to research the next step, but don't
  build on an assumed answer.
- **Say the audit out loud.** "The agent wrote a read-then-write here; that loses updates under concurrency, so I
  changed it to one atomic statement." That sentence is the grade.

## If you can't bring the kit

If you can't clone a public repo (question 5), write a short `AGENTS.md` from memory first: the layers, the two
audits (atomic writes, no blocking calls in `async def`), `make check` then commit, deploy early. Then have the
agent generate the app one layer at a time, one message per step, running `make check` between steps:
1. "Create backend/ with requirements.txt (fastapi, uvicorn[standard], pydantic, python-multipart, psycopg[binary],
   psycopg-pool, redis, prometheus-client), requirements-dev.txt (pytest, httpx, ruff), a Makefile with
   install/up/run/test/test-int/lint/fmt/check targets using `uv run`, pytest.ini, ruff.toml, a non-root Dockerfile
   with a /health HEALTHCHECK, and docker-compose.yml (postgres, redis with healthchecks, app)."
2. "Add app/config.py (frozen Settings dataclass from env), app/observability.py (JSON log formatter, request-id
   middleware setting x-request-id, Prometheus counter/histogram labeled by route template, /metrics),
   app/errors.py (AppError subclasses NotFound/Conflict/PayloadTooLarge/Unavailable, handlers producing
   {error:{code,message,request_id,details}} for AppError, validation errors, HTTPException,
   psycopg.OperationalError->503, Exception->500)."
3. "Add models/repository (Protocol + InMemory + Postgres with a shared psycopg_pool, atomic
   UPDATE…COALESCE…RETURNING for partial updates)/cache (Redis errors degrade to a miss)/service/deps/main for
   <entity>, with /health, /ready, paginated list. Plain def routes only."
4. "Add tests/: conftest with dependency_overrides + a fresh in-memory repo per test; API tests for CRUD, 422
   envelope, 404 envelope with request id, pagination, 500 without leaking; a threaded concurrency test proving
   concurrent PATCHes to different fields both survive."
5. For ingestion: paste the design bullets from `interview-kit/reference/scaffold.md` ("Ingestion design") and
   ask for the ingest files + tests.
