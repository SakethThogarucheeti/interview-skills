<!-- interview-kit reference file; § numbers match the index in ../SKILL.md -->

## 5. The live build: Claude Code or Cursor in the container

The IDE runs on their laptop, bridged to an Ubuntu 24 container where the code and terminal live. Setup is identical for both tools: `into-project.sh ~/app` (SKILL.md, Setup) builds a project whose `AGENTS.md` carries the rules and points at the playbook in `.kit/`. Nothing from your own machine or accounts is there, and nothing needs to be.

- **Claude Code** (permitted, and the strongest option because the kit drives the build): `curl -fsSL https://claude.ai/install.sh | bash`, then `cd ~/app && claude`, log in with your own account and paste the prompt. `CLAUDE.md` imports `AGENTS.md`.
- **Cursor** (a new Enterprise login is expected: no user rules, skills, MCP or settings): **File > Open Folder → `~/app`**, not `~/prep` or the home directory. In the Agent chat, send `/interview` plus the prompt. Don't log into a personal account unless they say so, and don't spend time on Settings or MCP.
- **Built-in/Enterprise models:** use the one they give you and stop switching. Weaker models make the §1 audit (races, blocking `async def`) *more* important. No Background Agents (privacy mode)? Use a second Agent chat for §5.3.

Either way, keep Tab/Copilot completions for small edits.

### 5.1 If you can't bring the kit

This depends on recruiter question 5 (§0). If you can't clone a personal repo, create `AGENTS.md` first from memory: the layers, the two audits (atomic writes, no blocking calls in `async def`), `make check` then commit, deploy early. Know `scaffold/AGENTS.md` well enough to retype a short version. Then have the Agent generate §4 one layer at a time with the prompt below, reviewing every file against the pitfall table.

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
