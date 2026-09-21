# interview-skills

A single self-contained Claude Code skill for DigitalOcean's timed
full-stack build interview: a 3-hour session, pick from a short list of
assigned prompts, build it, and **deploy it live on DigitalOcean** before
time's up — followed by a design walkthrough covering both scaling and
business trade-offs. Gets from a problem statement to a working, deployed,
defensible app — Postgres + Redis backed FastAPI/React stack — without
over-engineering or losing time to boilerplate.

## `interview-kit`

One file (`interview-kit/SKILL.md`), covering:
- Time-compression tactics (batch questions, parallelize dead time, zero-CSS rule)
- HLD: architecture + a pitfall scan (SPOF, spiky traffic, write races, blocking async calls, missing indexes/pagination) + scripted answers for scaling/reliability/business-tradeoff follow-ups
- LLD: SOLID/DRY applied pragmatically + the GoF patterns worth using (Repository, Strategy, Factory, Observer, Decorator, Adapter)
- A full FastAPI + Postgres + Redis + React scaffold, every file inlined as copy-paste code blocks (verified: installs clean, smoke tests pass)
- A required deployment section — getting the prototype live on a DigitalOcean Droplet/App Platform before the session ends
- An explicit AI-output-audit habit: DigitalOcean's own hiring team has said prompts are structured so AI-generated code confidently introduces a write race or a blocking call in async code, specifically to see if the candidate catches it — the pitfall-scan table doubles as that audit checklist
- A Cursor workflow section — the actual interview runs in Cursor, not Claude Code, so this covers porting the same conventions into a `.cursor/rules/*.mdc` file and which Cursor features are worth reaching for live
- An orchestration checklist tying it all together, prompt-selection through final deployed demo

It's one file specifically so it survives a "can't reach GitHub" scenario —
copy-paste the whole thing into a new skill file (or straight into a Cursor
rules file / chat) and it's self-contained, no other file in this repo required.

## Usage

Copy `interview-kit/SKILL.md` into `~/.claude/skills/interview-kit/SKILL.md`,
or work from inside this repo where it's picked up as a project skill.

For the interview itself: read section 5 (Cursor workflow) ahead of time and
stage `.cursor/rules/interview-conventions.mdc` plus the section 4 scaffold
files into your starting project before the clock starts. Also make sure
`doctl` is installed and authenticated (`doctl auth init`), and `uv`
(the scaffold's venv/dependency manager, section 4.19/4.21) is installed,
beforehand — setting either up mid-session eats into the build/deploy budget.
