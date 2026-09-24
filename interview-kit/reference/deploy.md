<!-- interview-kit reference file; § numbers match the index in ../SKILL.md -->

## Deploy, CI/CD, IaC and "which commit is live"

### 4.19 Deploy to DigitalOcean — required, first deploy by ~minute 30

The container has `gh` + `doctl` but most likely **no Docker**, so don't build images locally: let DigitalOcean or GitHub build them. Three paths, and the same app, config and `/version` check work on all of them:

| | **A. App Platform builds from GitHub** — default | **B. GitHub Actions builds the image** | **C. Droplet** — fallback |
|---|---|---|---|
| Who builds | App Platform, from `backend/Dockerfile` | CI runner → DOCR `app:<sha>` | the Droplet (`docker compose --build`) |
| Deploys on | every `git push` to main (`deploy_on_push`) | every push to main, after tests pass | `make deploy HOST=…` |
| Spec | `.do/app.yaml` via `make app-create` | `.do/app.image.yaml` via `app_action` (§4.21) | compose |
| One-time setup | `gh auth login`, `gh repo create`, link GitHub to DO (console) | `gh repo create` + one secret + one variable | SSH key; no GitHub at all |
| Test gate | pre-commit hook (`make check`); `ci.yml`'s test job still runs on push | CI must pass before deploy | `make check` by hand |
| Data | managed PG + Valkey (Terraform) or a dev database | same | Postgres/Redis containers on the box (a SPOF, §3) |
| Walkthrough story | "managed, 2 instances, rolling health-gated deploys, alerts; push = deploy" | same, plus "tests gate every deploy and CI proves the live SHA" | "one box, clean seams; App Platform is the next step" |

**A is the default:** fewest moving parts, no CI secrets, no registry, no local Docker. Use **B** if GitHub can't be linked to the DO account (B needs only a token secret), or if you want the stronger automation story. A and B deploy the same app from different sources, so pick one. Use **C** if there's no GitHub at all, or App Platform fights you. Switching later is only a deploy-target change.

**Shared first steps:**
```bash
doctl auth init                            # paste the provided API token
export DIGITALOCEAN_TOKEN=<same token>     # Terraform reads this
(cd infra && terraform init && terraform apply -var registry_name=<globally-unique-name> -auto-approve) \
  > /tmp/tf.log 2>&1 &                     # A/B: managed DBs take ~5-10 min, so start now and build meanwhile
```
No Terraform, or short on time/credits? Replace the two `databases:` entries in the spec with a dev database (`- name: db` / `engine: PG` / `production: false`, ready in about a minute, no Terraform) and set `REDIS_URL` to `""`: the app runs without a cache and `/ready` reports only the database. Not doing ingestion? `strip-ingest.sh` already removed the `workers:` blocks.

**A. App Platform builds from GitHub:**
```bash
gh auth login                                           # device code, finish in Chrome
gh repo create interview-app --private --source=. --push  # from the project root, after the first commit on main
```
Once, in the DO console: **Apps → Create App → GitHub**, authorize DigitalOcean and give it access to this repo, then leave the wizard. `doctl` can't create a GitHub-sourced app until the account link exists. Then:
```bash
cd backend && make app-create > /tmp/app.log 2>&1; tail -5 /tmp/app.log   # first build + deploy ~5-8 min; ends with make deployed
```
From then on, **every `git push` to main builds and deploys that commit**. `make app-status` shows the build/deploy phase, with the commit as the cause, and `make deployed` shows live vs local. The spec itself isn't re-read on push, so re-run `make app-create` after editing `.do/app.yaml`. Add the pre-commit hook (§4.17) so a red `make check` never gets pushed.

**B. GitHub Actions builds the image:** see §4.21. Set-up is `gh repo create …`, `gh secret set DIGITALOCEAN_ACCESS_TOKEN`, `gh variable set DOCR_REGISTRY --body <registry_name>`, then push. If Docker does work locally, `make app-deploy REGISTRY=<name>` runs the same steps by hand.

**C. Droplet** (builds on the box, so no local Docker and no GitHub):
```bash
ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519
cd infra && terraform init && terraform apply -var registry_name=<name> -var create_droplet=true -var create_managed_databases=false \
  -var "ssh_public_key=$(cat ~/.ssh/id_ed25519.pub)" -auto-approve && terraform output droplet_ip
ssh root@<ip> 'mkdir -p /root/app && echo POSTGRES_PASSWORD=$(openssl rand -hex 16) > /root/app/.env'   # once, before first deploy
cd ../backend && make deploy HOST=<ip> > /tmp/deploy.log 2>&1; tail -5 /tmp/deploy.log
```
**Already applied A/B's Terraform?** Run `terraform workspace new droplet` first. The same state with `create_managed_databases=false` would *destroy* the managed databases. Wait about a minute after creation for cloud-init to install Docker (`ssh root@<ip> docker version`). Without Terraform: in the console, create a Droplet from the Marketplace "Docker on Ubuntu" image with your key. `make deploy` rsyncs the backend, builds on the box with `GIT_SHA` stamped in, runs `docker compose -f docker-compose.yml up -d --build --wait` (the override is excluded, so Postgres/Redis stay unpublished), curls `/ready`, and runs `make deployed`. Scale the worker with `ssh root@<ip> 'cd /root/app && docker compose -f docker-compose.yml up -d --scale worker=3'`.

Either way: when it's slow, `tail` the log, or check `doctl apps logs <app-id> api --type build` (or `--type run`) / `ssh root@<ip> 'cd /root/app && docker compose logs --tail 50 app'`. Don't re-run blind. Verify `/ready` plus one real golden-path request from outside before defense prep: a deployed-but-broken app is worse than none. Frontend too? Add a `static_sites:` component (`source_dir: frontend`, `build_command: npm run build`, `output_dir: dist`) on App Platform, or serve `frontend/dist` from nginx on the Droplet.

### 4.21 CI/CD (path B, optional with path A) — `.github/workflows/ci.yml`

```
push/PR ──> test job: ruff ─> unit ─> integration (Postgres service) ─> image build
push to main, tests green ──> deploy-app-platform:                         ──> deploy-droplet (alternative):
   docker build --build-arg GIT_SHA=<sha> ─> push DOCR app:<sha>              make deploy HOST=... (rsync, build on box,
   ─> app_action applies .do/app.image.yaml, IMAGE_TAG=<sha>                   --wait, /ready, make deployed)
   ─> curl <live_url>/version == <sha> or the job fails
```
- **Every commit on main is deployed automatically.** Deploys queue (`concurrency`, never cancelled mid-flight), so the last one to finish is always the newest commit.
- **What gets deployed is the commit, not "latest".** The image tag *is* the SHA, and the spec that references it is applied in the same step. The final step proves the live app reports that SHA, so a deploy that silently kept the old version fails the pipeline.
- **The IaC is applied on every push too.** `.do/app.image.yaml` goes through app_action on each deploy, so changing `instance_count`, an alert, an env var or a health check is a reviewed commit, applied by CI like code. Drift gets overwritten on the next deploy.
- **Setup (~2 min with `gh`, once):** `gh secret set DIGITALOCEAN_ACCESS_TOKEN` (read/write App Platform + registry), `gh variable set DOCR_REGISTRY --body "$(cd infra && terraform output -raw registry)"`. For the Droplet job instead: `gh variable set DROPLET_HOST --body <ip>` + `gh secret set DROPLET_SSH_KEY < ~/.ssh/id_ed25519`. Unset variables skip a deploy job rather than fail it, so the workflow is safe to commit first.
- **With path A (§4.19), leave the variables unset.** The `test` job still runs lint + unit + Postgres integration tests on every push, and App Platform does the deploying. That's free CI evidence with no secrets. Don't set `DOCR_REGISTRY` as well, or two systems will fight over the app's source.
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

### 4.23 Infrastructure as code: `infra/main.tf` + `.do/app*.yaml`

This is a two-layer split, and the split is the design point to say out loud:
- **`infra/main.tf` (Terraform)**: long-lived, stateful, slow-to-create infrastructure (registry, Postgres, Valkey, optional Droplet + firewall, project). It changes rarely and is applied deliberately.
- **`.do/app.yaml` / `.do/app.image.yaml` (App Platform spec)**: the app itself (components, scaling, health checks, alerts, env, DB attachments). It changes with the code and is applied by `make app-create` (path A) or by CI on every push, pinned to the commit (path B).

Terraform *can* manage the app too (`digitalocean_app`), but then every CI image-tag change becomes Terraform drift. This split gives each layer one owner.

- **`infra/main.tf`** variables: `registry_name` (required, globally unique), `name` (`interview`), `region` (`nyc3`), `create_managed_databases` (true), `create_droplet` (false), `ssh_public_key`. It creates a DOCR registry (basic tier), `interview-pg` (PG 16) and `interview-cache` (Valkey 8) single-node clusters, an optional Droplet (Docker via cloud-init) + Cloud Firewall (22/80 in), and a Project grouping them.
- **`.do/app.yaml`** / **`.do/app.image.yaml`**: identical except the source (`github:` repo + `deploy_on_push` + `GIT_SHA: ${_self.COMMIT_HASH}`, vs DOCR `app:${IMAGE_TAG}`). `api` service ( ×2 `apps-s-1vcpu-1gb`, readiness `/ready`, liveness `/health`, CPU and p95 alerts), `worker` (same image, `python -m app.worker`), `db`/`cache` attached to the Terraform clusters, env from bindable vars, and app-level deploy/domain-failure alerts.
- **`cluster_name`s** in the spec must match Terraform's `${var.name}-pg` / `-cache`. Keep the default `name = "interview"`, or change both.
- **The database** is Postgres's default `defaultdb` as `doadmin`, reached via `${db.DATABASE_URL}` (TLS, `sslmode=require` included). A dedicated DB/user is `db_name`/`db_user` in the spec: a 2-line hardening step.
- **Schema setup** runs in each process at startup under a Postgres advisory lock (§4.9). Without the lock, `api` ×2 + `worker` booting together crash on `CREATE TABLE IF NOT EXISTS` (reproduced 10/10). The production answer is a real migration tool (Alembic) run once per deploy as a `jobs:` entry with `kind: PRE_DEPLOY`.
- **Validation:** Terraform passes `validate` + `fmt`. The app spec was checked strictly against DigitalOcean's OpenAPI schema: every field and enum passes, except top-level `alerts`/`envs` and service `alerts`, which the public schema omits but the App Spec reference documents. Neither has been applied to a real account yet. The first real `terraform apply` / `make app-deploy` is the smoke test, so do it early.

### 4.24 Which commit is live? (answer it in 5 seconds, from anywhere)

Every build knows its commit. Paths B/C stamp it at build time (`GIT_SHA` Docker build arg from `git rev-parse HEAD`; `-dirty` means uncommitted changes, so it matches no commit). Path A gets it from App Platform: `GIT_SHA: ${_self.COMMIT_HASH}` in the spec. Locally, `make run` exports it too:

| Where | How | Answers |
|---|---|---|
| **The app itself** | `curl $URL/version` → `{"git_sha", "build_time", "env"}` | What is running right now |
| **Every response** | `x-app-version` header | Which build served *this* request (both versions answer during a rolling deploy) |
| **Every log line** | `"version": "<sha12>"` field | Which build logged this error |
| **Metrics** | `app_build_info{git_sha="…"} 1` | Graph the rollout; alert if two versions coexist too long |
| **vs. your checkout** | `make deployed URL=$URL` | `UP TO DATE`, or `DIFFERENT` + `git log` of exactly the commits not yet live |
| **CI** | the deploy job's final step asserts `/version == github.sha`; GitHub → *Environments → production* lists each deployment with its commit and URL | What was deployed when, and that it actually took |
| **App Platform** | `make app-status` (path A: Cause names the pushed commit); `doctl apps list-deployments <app-id> --format ID,Cause,Phase,Created`; `doctl apps get <app-id> -o json \| jq -r '.[0].active_deployment.spec.services[] \| "\(.name) \(.image.tag)"'` | Deployment history; the SHA each component runs |
| **Registry** | `doctl registry repository list-tags app` | Every SHA ever built (all rollback candidates) |
| **Droplet** | `ssh root@<ip> "docker inspect \$(docker ps -qf name=app) --format '{{index .Config.Labels \"org.opencontainers.image.revision\"}}'"` | The image's OCI revision label |

**Rollback.**
- **Path A:** *Rollback* on a previous deployment in the App Platform console (redeploys that exact build, no rebuild). Or `git revert` + push, which is auditable and goes through the normal build.
- **Path B:** re-point at an image that already exists, with no rebuild: `make app-rollback REGISTRY=<name> SHA=<old sha>`.
- **Droplet:** `git checkout <sha> && make deploy HOST=…`.
