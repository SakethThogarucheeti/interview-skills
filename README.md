# interview-skills

A kit for DigitalOcean's timed build-and-deploy interview: 3 hours to build a REST API
(data ingestion + processing), deploy it live on DigitalOcean, then defend the design.
It works with Claude Code or Cursor inside the provided Ubuntu 24 container.

**Game day: paste this repo's URL into the agent chat and say "set this up".** The agent follows the section below.

## AI agent: set this up

You were given this repo's URL in an interview environment (VS Code/Cursor bridged to an Ubuntu 24
container). Do all of the following yourself in the terminal. The user should only click links, paste
the DigitalOcean token when you ask, and then paste the interview prompt.

1. **Get the kit:** `git clone -q --depth 1 https://github.com/SakethThogarucheeti/interview-skills ~/prep`
   (skip if `~/prep` exists).
2. **Build the project in the folder open in the editor:** `~/prep/interview-kit/into-project.sh "$PWD"`.
   It needs an empty folder (editor/git dotdirs are fine). If the open folder has other files or is the home
   directory, run `~/prep/interview-kit/into-project.sh ~/app` instead, and tell the user to open `~/app`
   (File > Open Folder) and say "continue setup" in a new chat there.
   **Update: if the host isn't Ubuntu** (no `apt`/`dpkg`, e.g. Arch or macOS), do steps 3-4 inside the dev container the
   scaffold ships: prefix commands with `./dev.sh` (`./dev.sh ./preflight.sh`, `./dev.sh bash -c 'cd backend && make check'`).
   It has `doctl`, `terraform`, `gh`, `uv`, Postgres and Redis preinstalled and reuses the host's `gh` login.
3. **Clear the "still needs you" list that `./preflight.sh` prints,** one item at a time, re-running
   `./preflight.sh` after each:
   - GitHub login: preflight starts it and prints a code; give the user the link and the code.
   - DigitalOcean: ask for the provided API token, then run `DO_TOKEN='<token>' ./preflight.sh`. Never echo it.
   - Preflight then sets the git identity, creates and pushes the private GitHub repo, and starts
     Terraform (managed Postgres + Valkey, ~6 min) in the background.
   - The one step that can't be scripted: give the user the DigitalOcean console click-path it prints.
4. **Hand over:** read `AGENTS.md` and `.kit/SKILL.md`, confirm setup in 2–3 lines, and ask for the
   interview prompt. From then on, `AGENTS.md` drives.

## Manual setup (same thing, by hand)

```bash
git clone -q --depth 1 https://github.com/SakethThogarucheeti/interview-skills ~/prep
~/prep/interview-kit/into-project.sh ~/app          # project + playbook + git + preflight
```
Not on Ubuntu? Then `cd ~/app && ./dev.sh ./preflight.sh` runs it all in an `ubuntu:24.04` container with `doctl` installed.
Then do what preflight lists, and open `~/app` (Cursor: File > Open Folder, then `/interview` plus the
prompt; Claude Code: `cd ~/app && claude`). Both tools load `~/app/AGENTS.md`.

## What's in `interview-kit/`

| Path | What it is |
|---|---|
| `SKILL.md` | The playbook (~8k tokens): brief, question gate, pitfall audit, design, checklist, game-day budget |
| `reference/` | Read on demand: scaffold file map, deploy paths + IaC, talking points, DO products, live-build tips |
| `scaffold/` | Verified FastAPI + Postgres + Redis app with ingestion worker, API-key auth + rate limit, tests, CI, Terraform, App Platform specs, `preflight.sh`, `make e2e`, `AGENTS.md` |
| `scaffold/dev.sh` + `.devcontainer/` | Update: Ubuntu 24 dev container (doctl, terraform, gh, uv, Postgres, Redis) for hosts that aren't Ubuntu; `./dev.sh <cmd>` runs in it |
| `into-project.sh` | The one setup command above |

All three deploy paths (App Platform from GitHub, CI-built image, Droplet) were run live on DigitalOcean
and pass `make e2e`, including auth and the rate limit.

Before the day: read `SKILL.md` §0–§2 and `reference/live-build.md`, and ask the recruiter whether
you can clone a public repo in the container (§0). If you can't, §5.1 covers working without the kit.
