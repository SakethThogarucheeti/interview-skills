# Agent runbook (Cursor and Claude Code both load this file)

Timed interview, 3 hours: build a REST API for data ingestion + processing and deploy it live on DigitalOcean.
This folder already holds a working, tested app (FastAPI + Postgres + Redis) that you rename and extend. Do
not rewrite it. Follow the steps below in order. Each step says what to run, what success looks like, and
what to do if it fails. Nothing outside this folder is set up for you: this file and `.kit/` are all you have.

- Run every command from the project root (the folder holding this file). Make targets: `make -C backend <target>`.
- Give every command a timeout. Run anything slow in the background, logging to `/tmp/<name>.log`, and check the log with `tail`.
- Host isn't Ubuntu (no `apt`, practice only)? Put `./dev.sh` in front of every command, e.g.
  `./dev.sh make -C backend check`. Details: `.kit/reference/scaffold.md`, "Non-Ubuntu host".
- Setup (clone, `./preflight.sh`, GitHub login, DO token) is in the kit's README. If `./preflight.sh`
  still lists something under "still needs you", finish that before step 1.

## The steps

**Step 1. Ask the questions (at minute ~0-10).** When the user pastes the interview prompt (or types /interview):
1. Restate the entities and actions in 1-2 sentences.
2. Send ONE message of clarifying questions. Use the list in `.kit/SKILL.md`, "Clarifying questions". Label the
   **functional** and **non-functional** questions, and give each one your default answer.
3. STOP and wait for the answer (or "use your judgment"). Do not write code before that. After the answer, never
   ask a second round: decide everything else yourself.

**Step 2. Pick the scope, then commit.**
- Not about ingesting/processing data? Run `./strip-ingest.sh`. Otherwise keep the ingestion code.
- They did not ask for a UI? Run `rm -rf frontend`.
- Success: `make -C backend check` is green. Then `git add -A && git commit -m "Scope: <one line>"`.

**Step 3. Write `design-decisions.md` (5 min).** Use the outline in `.kit/SKILL.md`, "design-decisions.md". Go
through the pitfall table in `.kit/SKILL.md` and mark each row "build it" or "mention it". Commit.

**Step 4. Run it locally (minute ~15).**
```bash
make -C backend install > /tmp/install.log 2>&1; tail -3 /tmp/install.log
make -C backend check                                  # success: "N passed", ruff clean
make -C backend up-native                              # Postgres + Redis (use `make -C backend up` if Docker works)
make -C backend run > /tmp/api.log 2>&1 &              # background
curl -s localhost:8000/ready                           # success: {"status":"ok",...}
```
If `check` fails: read the last 20 lines of output, fix only what they name, and run it again.

**Step 5. First deploy (by minute ~30). Deploy the untouched app before changing anything.**
1. Terraform must be done: `grep -E "Apply complete|Error" /tmp/tf.log`. If it's still running, go to step 6 and come back.
2. The user must have done the DigitalOcean console link that `./preflight.sh` printed (Apps -> Create App -> GitHub).
3. `make -C backend app-create > /tmp/app.log 2>&1` in the background (5-8 min), then `tail -5 /tmp/app.log`.
   Success: it ends with `UP TO DATE`.
4. `make -C backend e2e`. Success: every check passes.
If it fails: `.kit/reference/deploy.md`, "When it fails". Don't re-run blind.
From now on, every `git push` to main deploys that commit (about 3 min). There is no other deploy command.

**Step 6. Build the prompt's features (minute ~30-150), one file at a time.** Follow the order in
`.kit/reference/scaffold.md`, "Adapt to the prompt": `models.py` -> `repository.py` -> `service.py` -> `main.py` ->
`config.py` -> tests. After EACH file:
1. Audit the diff against the two rules below.
2. `make -C backend check` until green.
3. `git add -A && git commit -m "<what changed>"`.
At each working milestone: `git push`, then `make -C backend deployed` once the build is done (success: `UP TO DATE`).

**Step 7. Final deploy and verify (by minute ~160, required).**
1. Rename the `/items` requests in `backend/e2e.py` to match your routes, if you haven't already.
2. `git push`, wait for `make -C backend deployed` to print `UP TO DATE`, then `make -C backend e2e` until every check passes.

**Step 8. Defense prep (in the remaining time).** Update `design-decisions.md` to match what was built. The user
answers the walkthrough, not you, so make it easy to study. Talking points: `.kit/reference/talking-points.md`.

## Audit every diff before you accept it (this is what's graded)
1. **Read-then-write race.** Code that reads a value in Python and then writes it back (counters, quotas,
   balances, "check if it exists, then insert") loses updates under concurrency. Rewrite it as ONE SQL statement:
   `UPDATE t SET n = n + 1 WHERE id = %s AND n < max RETURNING n`, `INSERT … ON CONFLICT … DO UPDATE`, or
   `FOR UPDATE SKIP LOCKED` for claiming jobs. Copy `update_fields` in `backend/app/repository.py`, and copy
   `backend/tests/test_concurrency.py` to test it.
2. **Blocking call in `async def`.** Routes stay plain `def`. Never write `async def` around psycopg, redis,
   `requests`, `time.sleep` or file I/O.
When you catch one, say it out loud: "this read-then-write loses updates under concurrency, so it's one statement now."

## Rules
- Keep the layers. `main.py` (thin `def` routes) -> `service.py` (rules; raises `errors.py` errors, never
  `HTTPException`) -> `repository.py` (the only code that touches Postgres) -> `cache.py` (a Redis error is a
  cache miss, never a 500). Don't remove `/health`, `/ready`, `/version`, `/metrics`, the error envelope, API-key
  auth or the rate limit.
- Inputs: bounds on every field, `extra="forbid"`, a max on every `limit`, an index for every non-PK lookup.
- Ingestion: validate each record (report rejects by index), dedupe on the client's id (`ON CONFLICT DO NOTHING`),
  return 202 + a status URL, cap the batch size (413) and the backlog (503).
- New behavior needs a test in the same commit. A new counter, quota or aggregate needs a concurrency test.
- New settings go in `backend/app/config.py` (read from env). Infra changes go in `infra/main.tf` or `.do/app.yaml`, never the console.
- Use `make` (uv underneath). Never bare `pip` or `source .venv/bin/activate`.
- DO token: only ever `DO_TOKEN=<token> ./preflight.sh`. Never echo it, log it or write it to a file.
- No new infrastructure, dependencies or big refactors. Behind schedule? Cut features, never the tests,
  error handling, observability or the deploy.
