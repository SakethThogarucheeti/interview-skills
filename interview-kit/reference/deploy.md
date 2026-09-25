# Deploy: App Platform from GitHub

Every `git push` to main builds and deploys that commit. The container has no Docker, so DigitalOcean builds the
image from `backend/Dockerfile`. Commands run from the project root.

## First deploy (runbook step 5)

`./preflight.sh` already did the setup: doctl login, the private GitHub repo, API keys in `~/.api_keys.env`, and
`terraform apply` for managed Postgres + Valkey (in the background, ~6 min, log in `/tmp/tf.log`). What's left:
1. **Terraform finished:** `grep -E "Apply complete|Error" /tmp/tf.log`. Or watch
   `doctl databases list --format Name,Engine,Status` until both are `online`.
2. **The DigitalOcean console link (the user does it, once per account):** cloud.digitalocean.com -> Apps ->
   Create App -> GitHub, authorize DigitalOcean for this repo, then leave the wizard. "No components detected" is
   expected: the spec's `source_dir` handles it.
3. **Create the app:** `make -C backend app-create > /tmp/app.log 2>&1` in the background, then `tail -5 /tmp/app.log`.
   The first build + deploy takes 5-8 min and ends with `make deployed` printing `UP TO DATE`. It reads the API keys
   from `~/.api_keys.env` into the spec as an encrypted secret (never echoed).
4. **Verify from outside:** `make -C backend e2e`. It uses the first key in `~/.api_keys.env`.

After that:
- **Deploy = `git push`** (~3 min). `make -C backend app-status` shows the build phase with the commit as the cause;
  `make -C backend deployed` prints `UP TO DATE` once the pushed commit is live.
- **Changed `.do/app.yaml`?** Pushing doesn't re-read the spec. Run `make -C backend app-create` again.
- **The keys:** every data route needs `-H "X-API-Key: <key>"`. `/health`, `/ready`, `/version`, `/metrics` and
  `/docs` stay open. Give the interviewer the `interviewer` key from `~/.api_keys.env` and point them at `/docs` -> **Authorize**.
- **UI too?** Add a `static_sites:` component to `.do/app.yaml` (`source_dir: frontend`, `build_command: npm run
  build`, `output_dir: dist`) and re-run `app-create`.

## When it fails

Read the log before re-running anything.

| Symptom | Fix |
|---|---|
| `terraform` failed with `412 user is not a member of the project` | Transient on a fresh account. Re-run `./preflight.sh` (or `cd infra && terraform apply -auto-approve`): it creates only what's missing |
| No time or credits for managed DBs | In `.do/app.yaml`, replace the two `databases:` entries with a dev database (`- name: db`, `engine: PG`, `production: false`, ready in ~1 min) and set `REDIS_URL` to `""` (the app runs without a cache). Then `app-create` |
| `app-create`: can't access the GitHub repo | The console link (step 2) isn't done, or wasn't given access to this repo |
| `no API_KEYS` | Re-run `./preflight.sh`, which writes `~/.api_keys.env` |
| Build failed | `doctl apps list` for the id, then `doctl apps logs <app-id> api --type build` |
| Deployed but crashing | `doctl apps logs <app-id> api --type run`. Usually a missing env var or a bad `DATABASE_URL` |
| `deployed` says UNREACHABLE for a new app | DNS for `*.ondigitalocean.app` is cached as "doesn't exist" for up to 30 min if looked up too early. `make deployed` and `make e2e` already work around it. For manual curls: `ip=$(curl -s "https://dns.google/resolve?name=<host>&type=A" \| jq -r '.Answer[0].data'); curl --resolve <host>:443:$ip https://<host>/ready`. The browser usually works |
| `deployed` says DIFFERENT | The push hasn't finished deploying (`make -C backend app-status`), or there are unpushed commits |

## CI: `.github/workflows/ci.yml`

On every push: ruff -> unit tests -> integration tests against Postgres + Redis service containers -> image build.
It doesn't deploy: App Platform does, from the same push. So CI is test evidence with no secrets to set up.

## Infrastructure as code: `infra/main.tf` + `.do/app.yaml`

Two layers, and the split is the design point to say out loud:
- **`infra/main.tf` (Terraform)**: long-lived, slow-to-create infrastructure: `interview-pg` (Postgres 16) and
  `interview-cache` (Valkey 8) single-node clusters, and a Project grouping them. Changes rarely, applied deliberately.
  State is local; shared state for a team would go in Spaces (S3-compatible) with plan-on-PR, apply-on-main in CI.
- **`.do/app.yaml` (App Platform spec)**: the app itself: `api` service (x2 `apps-s-1vcpu-1gb`, readiness `/ready`,
  liveness `/health`, CPU and p95 alerts), `worker` (same image, `python -m app.worker`), the database attachments,
  env from bindable variables (`${db.DATABASE_URL}`), `GIT_SHA: ${_self.COMMIT_HASH}`. Changes with the code.
- Terraform *could* manage the app too, but then every deploy becomes Terraform drift. Each layer has one owner.
- The spec's `cluster_name`s must match Terraform's `${var.name}-pg` / `-cache`. Keep the default `name = "interview"`.
- The database is `defaultdb` as `doadmin` over TLS. A dedicated DB/user (`db_name`/`db_user`) is a 2-line hardening step.
- The schema is created at startup under a Postgres advisory lock (without it, 2 API instances + the worker booting
  together crash on `CREATE TABLE IF NOT EXISTS`). The production answer is a migration tool (Alembic) run once per
  deploy as a `PRE_DEPLOY` job.

## Which commit is live?

Every build knows its commit: App Platform sets `GIT_SHA` from `${_self.COMMIT_HASH}`.

| Where | How |
|---|---|
| The app | `curl $URL/version` -> `{"git_sha", "build_time", "env"}` |
| Every response | `x-app-version` header (both versions answer during a rolling deploy) |
| Every log line | `"version": "<sha12>"` |
| Metrics | `app_build_info{git_sha="…"} 1` |
| vs. your checkout | `make -C backend deployed`: `UP TO DATE`, or `DIFFERENT` plus the commits not yet live |
| App Platform | `make -C backend app-status`: recent deployments, each with the commit that caused it |

**Rollback:** in the console, *Rollback* on an earlier deployment (redeploys that exact build, no rebuild). Or
`git revert` + push, which is auditable and goes through the normal build.

