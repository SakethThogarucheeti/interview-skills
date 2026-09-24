# interview-skills

A kit for DigitalOcean's timed build-and-deploy interview: 3 hours to build a REST API
(data ingestion + processing), deploy it live on DigitalOcean, then defend the design.
It works with Claude Code or Cursor inside the provided Ubuntu 24 container.

## Game day

```bash
gh auth login                                                    # if needed
gh repo clone SakethThogarucheeti/interview-skills ~/prep -- --depth 1 -q
~/prep/interview-kit/into-project.sh ~/app                       # project + playbook + git + preflight
```
Do what preflight lists under "still needs you" (`doctl auth init`, the GitHub link in the DO console),
then open `~/app`:
- **Cursor:** File > Open Folder → `~/app`, then send `/interview` plus the prompt in Agent chat.
- **Claude Code:** `cd ~/app && claude`, then paste the prompt.

Both tools load `~/app/AGENTS.md` (the rules, plus a pointer to the playbook in `~/app/.kit/`).
Nothing else needs installing or configuring.

## What's in `interview-kit/`

| Path | What it is |
|---|---|
| `SKILL.md` | The playbook (~8k tokens): brief, question gate, pitfall audit, design, checklist, game-day budget |
| `reference/` | Read on demand: scaffold file map, deploy paths + IaC, talking points, DO products, live-build tips |
| `scaffold/` | Verified FastAPI + Postgres + Redis app with ingestion worker, API-key auth + rate limit, tests, CI, Terraform, App Platform specs, `preflight.sh`, `make e2e`, `AGENTS.md` |
| `into-project.sh` | The one setup command above |

All three deploy paths (App Platform from GitHub, CI-built image, Droplet) were run live on DigitalOcean
and pass `make e2e`, including auth and the rate limit.

Before the day: read `SKILL.md` §0–§2 and `reference/live-build.md`, and ask the recruiter whether
you can clone a personal repo in the container (§0). If you can't, §5.1 covers working without the kit.
