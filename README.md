# interview-skills

A single self-contained Claude Code skill for a timed full-stack build
interview (e.g. DigitalOcean's "build an app in ~2 hours" format). Gets from
a problem statement to a working, defensible app — Postgres + Redis backed
FastAPI/React stack — without over-engineering or losing time to boilerplate.

## `interview-kit`

One file (`interview-kit/SKILL.md`, ~39KB, 806 lines), covering:
- Time-compression tactics (batch questions, parallelize dead time, zero-CSS rule)
- HLD: architecture + scripted answers for scaling/traffic-spike/reliability follow-ups
- LLD: SOLID/DRY applied pragmatically + the GoF patterns worth using (Repository, Strategy, Factory, Observer, Decorator, Adapter)
- A full FastAPI + Postgres + Redis + React scaffold, every file inlined as copy-paste code blocks (verified: installs clean, smoke tests pass)
- A Cursor workflow section — the actual interview runs in Cursor, not Claude Code, so this covers porting the same conventions into a `.cursor/rules/*.mdc` file and which Cursor features are worth reaching for live
- An orchestration checklist tying it all together

It's one file specifically so it survives a "can't reach GitHub" scenario —
copy-paste the whole thing into a new skill file (or straight into a Cursor
rules file / chat) and it's self-contained, no other file in this repo required.

## Usage

Copy `interview-kit/SKILL.md` into `~/.claude/skills/interview-kit/SKILL.md`,
or work from inside this repo where it's picked up as a project skill.

For the interview itself: read section 5 (Cursor workflow) ahead of time and
stage `.cursor/rules/interview-conventions.mdc` plus the section 4 scaffold
files into your starting project before the clock starts.
