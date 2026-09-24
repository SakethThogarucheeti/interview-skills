<!-- interview-kit reference file; § numbers match the index in ../SKILL.md -->

## 5. The live build: Claude Code, Cursor or Copilot in the container

The IDE (VS Code or Cursor) runs on their laptop, bridged to an Ubuntu 24 container where the code and terminal live. **Claude Code is permitted**, and it's the strongest option, because this kit then drives the build directly:
```bash
curl -fsSL https://claude.ai/install.sh | bash      # or: npm install -g @anthropic-ai/claude-code
gh auth login && gh repo clone <you>/<prep-repo> ~/prep && mkdir -p ~/.claude/skills && cp -R ~/prep/interview-kit ~/.claude/skills/
claude                                              # log in with your own account, then ask it to use interview-kit
```
If that's blocked (no personal login allowed, or no network to claude.ai), use Cursor as below. Either way, keep Tab/Copilot completions for small edits.

**Cursor on a new laptop + new login (the actual interview machine).**
Nothing from your home Cursor account is there: no user skills, user rules, MCP, model defaults, or Background Agents. **Only the folder you Open** is the kit. Recruiter question 5 (§0) is what makes this possible — you must be allowed to clone this repo.

```bash
gh auth status >/dev/null 2>&1 || gh auth login          # your GitHub, device code
gh repo clone SakethThogarucheeti/interview-skills ~/prep -- --depth 1 -q
~/prep/interview-kit/into-project.sh ~/app
```
Then **File > Open Folder → `~/app`** (not `~/prep`, not the home directory). First Agent message: `/interview` and paste the prompt. That folder already has `AGENTS.md`, `.cursor/skills/interview-kit/` (full playbook + `reference/`), `.cursor/rules/interview-conventions.mdc`, and `.cursor/commands/interview.md`.

Do **not** log into your personal Cursor account unless they say you may — Enterprise login is expected. Do **not** spend time on Settings. Do **not** install MCP.

**If using Cursor's built-in / Enterprise models:**
- Use whatever Agent model they give you and stop switching. Older or weaker models make the §1 audit *more* important (races, blocking `async def`).
- **Privacy mode / no Background Agents:** use a second Agent chat tab for §5.3 instead.
- **Shortcuts:** Agent chat for multi-file + terminal; inline edit on a selection for tiny diffs; Tab for repetitive shape-following. `@`-mention files rather than pasting them.

### 5.1 Getting the conventions and scaffold into a container you don't own

This depends on recruiter question 5 (§0):
- **Allowed to clone a personal repo (`gh` is preinstalled):** `into-project.sh ~/app` (§4), Open Folder on `~/app`, `/interview`. `make install && make check` from `backend/` is green in about 2 minutes. Skill + rules come with it.
- **Not allowed:** you have no kit on disk. Create `AGENTS.md` + `.cursor/rules/interview-conventions.mdc` first (paste a short version of the points below), then have Agent generate §4 one layer at a time with the scaffold prompt below. Review every file against the pitfall table. The layering and quality checklist should be memorized going in, not looked up live.

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
