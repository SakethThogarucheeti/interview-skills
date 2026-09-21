# interview-skills

Claude Code skills for a timed full-stack build interview (e.g. DigitalOcean's
"build an app in ~2 hours" format). Designed to get from a problem statement
to a working, defensible app — with a Postgres + Redis backed FastAPI/React
stack — without over-engineering or running out of time on boilerplate.

## Skills

- **`interview-rapid-build`** — the orchestrator; run this first. Walks the
  full session: requirements → design → scaffold → build → verbal defense prep.
- **`hld-interview-design`** — how to architect something simple enough to
  finish and extensible enough to answer scaling/traffic-spike/reliability
  follow-up questions credibly.
- **`lld-design-patterns`** — SOLID/DRY applied pragmatically, plus the small
  set of GoF patterns (Repository, Strategy, Factory, Observer, Decorator,
  Adapter) that pay for themselves in a 2-hour build.
- **`fastapi-react-scaffold`** — copy-and-adapt starter templates: FastAPI +
  Postgres + Redis backend (repository/service/route layered), React (Vite)
  frontend, Docker Compose for local Postgres/Redis, a smoke test.
- **`cursor-interview-workflow`** — since the actual interview runs in Cursor
  (not Claude Code), this covers porting the same conventions into Cursor via
  a `.cursor/rules/*.mdc` file, and which Cursor features (Tab, Cmd+K, Agent)
  are worth reaching for live.

## Usage

These are installed as Claude Code skills. Either:
- symlink/copy each `*/SKILL.md` directory into `~/.claude/skills/`, or
- work from inside this repo, where they're picked up as project skills.

For the interview itself, use `cursor-interview-workflow` to stage
`.cursor/rules/interview-conventions.mdc` and the `fastapi-react-scaffold`
templates into your starting project ahead of time.
