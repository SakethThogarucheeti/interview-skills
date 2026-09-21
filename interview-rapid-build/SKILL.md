---
name: interview-rapid-build
description: End-to-end orchestrator for a timed "build a full-stack app in ~2 hours" interview (e.g. DigitalOcean's format) — runs the whole session from reading the prompt to a demoable, defensible app: quick requirements pass, HLD talking points, scaffolded FastAPI+React+Postgres+Redis code structured with SOLID/DRY/GoF patterns, and a pre-built answer set for scaling/traffic-spike/reliability follow-ups. Use as soon as the user shares the interview prompt/problem statement and wants to start building, or says things like "help me build this in the interview", "let's do the DO interview build". Orchestrates hld-interview-design (architecture + talking points), lld-design-patterns (code structure), fastapi-react-scaffold (the running template), and cursor-interview-workflow (since the actual interview runs in Cursor, not here) — read those for the details this skill delegates to.
---

# Interview rapid build — 2-hour orchestrator

You are pairing with the user to *prepare for and rehearse* a live, timed interview — the actual build happens in Cursor (see `cursor-interview-workflow`), so treat sessions here as either a full dry run or prep work (scaffold refinement, Q&A rehearsal) ahead of the real thing. Optimize for: something working and demoable by the end, a codebase that looks deliberately structured on a skim, and the user having sharp, ready answers for scaling/reliability questions — in that priority order. A brilliant architecture that isn't running loses to a plain CRUD app that works and whose author can clearly explain how they'd scale it.

## 0. Read the prompt, state the plan, start the clock

The moment the user shares the problem statement:
1. Restate the core entities/actions in one or two sentences to confirm you understood it the same way they did.
2. Name the time budget out loud (assume 2 hours unless told otherwise) and the phase breakdown from `hld-interview-design` (§0): ~10 min design, ~45-50 min backend, ~30-40 min frontend, ~15-20 min polish, buffer.
3. Do not spend more than the budgeted design time on architecture — see step 1 below for what "done" looks like at that stage.

## 1. Design phase (~10 min)

Invoke `hld-interview-design`. Concretely, produce:
- A one-paragraph statement of core entities, read/write ratio, and consistency requirements (its §1).
- The "one box, clean seams" architecture sketch (its §2) — adapt the generic diagram to the actual prompt's boxes.
- Explicit non-goals stated out loud, so scope is deliberate.

Stop as soon as you have this — do not iterate on the diagram. If the prompt is small (a simple CRUD tool), say so explicitly and move on immediately (its §5).

## 2. Scaffold (~5 min)

Invoke `fastapi-react-scaffold` to copy the backend/frontend templates into the project, start Postgres+Redis (`docker compose up -d`), and get both dev servers running in the background before writing any custom code. Confirm `GET /health` and the frontend root both load before proceeding — catching a broken toolchain now costs 2 minutes; catching it at minute 90 costs the interview. If this is prep work ahead of the real interview (not the interview itself), also apply `cursor-interview-workflow`'s §1 now: drop `.cursor/rules/interview-conventions.mdc` into the template repo so Cursor is pre-configured before the clock starts.

## 3. Backend build (~45-50 min)

Adapt the scaffold per `fastapi-react-scaffold`'s §1 (rename entities, extend repository/service/routes). Apply `lld-design-patterns` judgment as you go:
- Keep the repository/service/route layering from the templates — don't collapse it under time pressure.
- Reach for Strategy/Factory/Observer/Adapter/Decorator only where §1 of that skill's "genuinely interchangeable" test is met by the actual prompt (e.g. a shortener prompt with multiple code-generation strategies genuinely wants Strategy; a plain todo list does not need any of them beyond the repository).
- Run `test_smoke.py` (adapted) as you finish each endpoint, not all at the end — a failing test found at minute 40 is cheap, found at minute 110 is not.

Checkpoint: by the time-budget midpoint, the backend's core CRUD/flows should be reachable via `curl` or the FastAPI `/docs` page, even before the frontend exists.

## 4. Frontend build (~30-40 min)

Adapt `App.jsx`/`api.js` per the scaffold skill's §1. Priorities in order: golden path working end-to-end in the browser > loading/error states > visual polish. A plain-but-functional UI beats a half-built styled one every time in this format — do not spend interview time on CSS beyond basic legibility unless everything else is done early.

## 5. Prep the verbal defense (~10-15 min, can overlap with polish)

Before time runs out, make sure the user can answer — without improvising from zero — the questions in `hld-interview-design` §3: traffic spikes, caching, DB scaling, consistency/race conditions, reliability, deployment/monitoring. Ground every answer in the actual code just written (name the real seam — "swap `InMemoryItemRepository` for `SqliteItemRepository` here", "this `ItemService.create_item` is where I'd add the idempotency check") rather than generic system-design vocabulary. Concrete beats generic every time an interviewer probes.

## 6. Final pass (last ~10 min)

1. Exercise the full golden path once in the browser, not just via curl/tests.
2. Confirm `/health` responds and both servers start cleanly from a fresh terminal (in case they ask you to restart/demo from scratch).
3. One-sentence summary ready to say out loud: what's built, what's explicitly out of scope and why (ties back to the non-goals from step 1), and the first three things you'd do next with more time (this is a strong close — it shows judgment about prioritization, not just "ran out of time").

## Boundaries

- Don't let architecture discussion eat backend/frontend time — if design is running long, say "let's lock this in and adjust as we build" and move.
- Don't introduce infrastructure (real Redis, real message queues, Docker Compose orchestration, CI) unless the prompt or interviewer explicitly asks for it live — these are talking points (`hld-interview-design` §3), not build tasks, in a 2-hour window.
- If the user is behind schedule at a checkpoint, cut scope (fewer entity fields, fewer endpoints, simpler UI) before cutting the layering/testing habits — a smaller well-structured app outscores a larger messy one.
