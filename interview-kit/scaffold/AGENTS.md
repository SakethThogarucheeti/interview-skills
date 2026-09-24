# Agent instructions (Cursor and Claude Code both load this file)

Timed interview build: a REST API for data ingestion + processing, deployed live on DigitalOcean.
The playbook is `.kit/SKILL.md`, with deeper docs in `.kit/reference/` read on demand. Nothing outside
this folder is set up (no user rules, skills or MCP), so this file and `.kit/` are all you have.

## When the interview prompt arrives (or the user types /interview)
1. Read `.kit/SKILL.md` §0–§2 and §6 before touching any code.
2. Restate the entities and actions in 1–2 sentences. Then ask ONE batch of clarifying questions
   (functional + non-functional, each with a default lean) and STOP until they answer or say "use your judgment".
3. Then follow §6: design + pitfall scan → `make install && make check` → first deploy by ~minute 30 →
   rename-and-extend starting at `backend/app/models.py` (`.kit/reference/scaffold.md` §4.18).

## Architecture: keep the layers
`main.py` thin plain-`def` routes → `service.py` business rules (raises `errors.py` domain errors, never
`HTTPException`) → `repository.py` (the only code touching Postgres) → `cache.py` (Redis; a Redis failure is a
cache miss, never a 500). `config.py` = every setting from env; `errors.py` = one JSON error envelope with
`request_id`; `observability.py` = JSON logs, request IDs, `/metrics`; `security.py` = API key + rate limit.
`/health` = liveness, `/ready` = dependency checks, `/version` = the live commit. Don't remove any of them.

Inputs: bounds on every field, `extra="forbid"`, a max on every `limit`, an index for every non-PK lookup.
Ingestion: validate per record (report rejects by index), dedupe on the client id (`ON CONFLICT DO NOTHING`),
return 202 + a status URL, cap batch size (413) and backlog (503). The worker claims with `FOR UPDATE SKIP LOCKED`.

## Audit every generated diff before accepting it (this is what's graded)
1. **Read-modify-write / check-then-act races** → one atomic SQL statement (`UPDATE … SET n = n + 1 … RETURNING`,
   `ON CONFLICT … DO UPDATE`, `SKIP LOCKED`), never read in Python then write back.
2. **Blocking calls inside `async def`** → routes stay plain `def`; sync I/O in async code goes through
   `run_in_threadpool`.
Say it out loud when you catch one: "this read-then-write loses updates under concurrency, so it's one statement now."

## Working rules
- `make` is the command surface (uv underneath; never bare `pip` or `source .venv/bin/activate`).
  `make check` green → commit, after every file. New behavior = a test in the same commit;
  new counter/quota/aggregate = a concurrency test like `tests/test_concurrency.py`.
- Host isn't Ubuntu (no apt)? Run commands through the dev container: `./dev.sh <cmd>` (doctl, terraform, gh, uv, Postgres, Redis inside; project mounted; :8000 published). Inside the interview's own container, run them directly.
- Every command gets a timeout. Anything slow runs in the background with a log file you `tail`.
  No Docker daemon: `make up-native`.
- Deploy early and at each milestone (path A: `git push` to main). Verify with `make deployed` and `make e2e URL=…`.
- New tunables go in `config.py`, infra changes in `infra/main.tf` or `.do/app*.yaml`, never the console.
- No new infrastructure, dependencies or big refactors. Frontend only if they confirmed a UI.
  If behind, cut features before tests, observability or the deploy.
