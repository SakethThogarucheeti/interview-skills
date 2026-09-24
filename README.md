# interview-skills

A self-contained Claude Code skill for DigitalOcean's timed
full-stack build interview: a 3-hour session, pick from a short list of
assigned prompts, build it, and **deploy it live on DigitalOcean** before
time's up — followed by a design walkthrough covering both scaling and
business trade-offs. Gets from a problem statement to a working, deployed,
defensible app — Postgres + Redis backed FastAPI/React stack — without
over-engineering or losing time to boilerplate.

## `interview-kit`

`interview-kit/SKILL.md` (the always-loaded core, ~8k tokens), `interview-kit/reference/` (deploy, scaffold map, talking points, DO catalog, live-build notes, read on demand) and `interview-kit/scaffold/` (the verified code), covering:
- Time-compression tactics (batch questions, parallelize dead time, zero-CSS rule)
- HLD: architecture + a pitfall scan (SPOF, spiky traffic, write races, blocking async calls, missing indexes/pagination) + scripted answers for scaling/reliability/business-tradeoff follow-ups
- LLD: SOLID/DRY applied pragmatically + the GoF patterns worth using (Repository, Strategy, Factory, Observer, Decorator, Adapter)
- The recruiter's brief (REST API for data ingestion + processing, provided Cursor laptop, DO deploy) and a rubric map: engineering quality, testing, automation, operational excellence → the exact scaffold feature covering each
- A production-shaped FastAPI + Postgres + Redis scaffold in `scaffold/`, copied in with one `cp -R` (`strip-ingest.sh` drops the ingestion add-on for other prompts): env config, validation bounds, one JSON error envelope, JSON logs + request IDs, Prometheus metrics, liveness/readiness, graceful Redis/DB degradation, structured tests (API/unit/concurrency/integration), Makefile, ruff (verified: lint clean, tests pass, full compose stack exercised incl. outage behavior)
- An ingestion + processing add-on: per-record validation, idempotent dedupe, Postgres `SKIP LOCKED` job queue, horizontally scalable worker, backpressure, CSV upload (verified: 8 concurrent workers process contended batches exactly once)
- Deploy-on-push without local Docker (the dev env is an Ubuntu 24 container): App Platform builds straight from GitHub by default, or a CI/CD workflow (lint → tests → Postgres integration → image → deploy pinned to the commit SHA, verified live), or a Droplet; `make up-native` runs Postgres/Redis via apt when Docker is unavailable (verified in `ubuntu:24.04`), provided-laptop preflight (no uv/timeout/Docker/doctl fallbacks), and questions to send the recruiter beforehand
- Optional React frontend
- A required deployment section — getting the prototype live on DigitalOcean App Platform (recommended) or a Droplet before the session ends
- Infrastructure as code: Terraform (`infra/main.tf`: registry, managed Postgres + Valkey, optional Droplet + firewall, Spaces remote-state backend) plus an App Platform spec in two flavors (`.do/app.yaml` builds from GitHub, `.do/app.image.yaml` takes CI's image; API ×2, worker, health checks, alerts) (verified: `terraform validate`, spec checked against DO's OpenAPI schema, `actionlint`)
- "Which commit is live?": every build is stamped with its git SHA (`/version`, `x-app-version` header, log field, `app_build_info` metric, OCI label), `make deployed` lists undeployed commits, and rollback reuses an existing image without rebuilding it
- A catalog of DigitalOcean's cloud offerings (compute, managed DBs, storage, networking, monitoring) and when to name each one in the walkthrough
- An explicit AI-output-audit habit: DigitalOcean's own hiring team has said prompts are structured so AI-generated code confidently introduces a write race or a blocking call in async code, specifically to see if the candidate catches it — the pitfall-scan table doubles as that audit checklist
- A live-build section — the container allows Claude Code (install it + this kit and let it drive), Cursor or Copilot; covers the `.cursor/rules/*.mdc` conventions file and which Cursor features are worth reaching for
- An orchestration checklist tying it all together, prompt-selection through final deployed demo

SKILL.md holds only what's needed from the first minute; everything else is
read when its step arrives, so loading the skill costs ~8k tokens instead of
~40k. The folder is self-contained: copy `interview-kit/` anywhere (or zip it)
and nothing else in this repo is needed.

## Usage

Copy the whole `interview-kit/` folder to `~/.claude/skills/interview-kit/`,
or work from inside this repo where it's picked up as a project skill.

For the interview itself: read section 5 (the live-build workflow) ahead of time and
get this repo into the provided Ubuntu container (`gh repo clone`, if the
recruiter allows it). Claude Code is permitted there, so copy `interview-kit/`
to `~/.claude/skills/` and let it drive; the scaffold also carries a Cursor
rules file (`.cursor/rules/interview-conventions.mdc`). `gh`, `doctl`, `jq`
and `yq` are preinstalled there; `uv` and Terraform are not (one command
each, section 4.17), and Docker probably isn't available.
