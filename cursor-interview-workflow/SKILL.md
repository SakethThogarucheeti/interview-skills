---
name: cursor-interview-workflow
description: How to use Cursor (enterprise access) effectively during a timed full-stack build interview — which Cursor features save real time (Tab completion, Cmd+K inline edit, Agent/Composer for multi-file scaffolding, @-mentions for context) and how to port the interview-rapid-build conventions (HLD/LLD layering, Postgres+Redis stack) into Cursor as a Project Rules file so Cursor's own AI follows the same structure during the actual interview. Use when the user asks about using Cursor for the interview, wants Cursor rules set up, or asks how to get the most out of Cursor's agent mode under time pressure. Pairs with interview-rapid-build (the overall workflow this executes inside), hld-interview-design, lld-design-patterns, and fastapi-react-scaffold (the conventions being ported).
---

# Using Cursor for the timed build

Claude Code (this session) is for prep — designing the approach, building/refining the scaffold and skill content beforehand. The actual interview will run inside Cursor. This skill is the bridge: get Cursor configured with the same conventions before the clock starts, and know which Cursor features are worth reaching for live versus which cost more time than they save under pressure.

## 1. Before the interview: port the conventions into Cursor

Cursor doesn't read Claude Code skills. Instead it reads **Project Rules** — `.mdc` files under `.cursor/rules/` in the repo, auto-attached to Cursor's chat/agent/Tab context. Set this up once, ahead of time, in whatever repo/template you'll start the interview from:

```bash
mkdir -p <project-dir>/.cursor/rules
cp <this-skill-dir>/templates/interview-conventions.mdc <project-dir>/.cursor/rules/
```

That file (`alwaysApply: true`) encodes the same architecture/layering/stack conventions as `hld-interview-design`, `lld-design-patterns`, and `fastapi-react-scaffold` — so when Cursor's Tab/Agent suggests code, it defaults to the repository/service/route split and Postgres+Redis stack instead of generic scaffolding. Also copy the `fastapi-react-scaffold` templates into the project ahead of time if the interview format allows pre-staged boilerplate — confirm with the interviewer whether starting from a personal template repo is allowed; if not, you'll paste/recreate the structure quickly from memory of these skills instead, which is exactly why the layering should be a habit going in, not something you look up live.

## 2. Cursor features worth using live, and when

**Tab (autocomplete)** — always on, costs nothing. Best for repetitive shape-following code: a second Pydantic model matching the pattern of the first, a fourth route matching the shape of the first three. Let it finish these instead of typing them out.

**Cmd+K (inline edit)** — best for small, localized, well-specified changes to code you're looking at: "add validation that title is non-empty," "convert this to use the connection pool." Faster than a chat round-trip for anything scoped to the current file/selection. Keep instructions specific and short; vague Cmd+K prompts on a big selection waste more time reviewing the diff than they save typing.

**Agent / Composer mode (multi-file)** — best for the two big multi-file moves in this workflow: (a) initial scaffold generation if you didn't pre-stage the template, prompted with the exact layering from `interview-conventions.mdc`, and (b) a rename-and-extend pass across `models.py`/`repository.py`/`service.py`/`main.py`/`api.js`/`App.jsx` when adapting the generic scaffold to the real entity (mirrors `fastapi-react-scaffold`'s §1 checklist — paste that checklist into the Agent prompt directly). Always review the diff before accepting; don't rubber-stamp a multi-file agent edit under time pressure, a wrong assumption compounds across files fast.

**@-mentions for context** — `@filename` or `@codebase` when asking Cursor chat/agent a question that depends on existing code, instead of re-pasting code into the prompt. Cheap and prevents Cursor guessing at a shape you already defined elsewhere.

**Checkpoints / diff review** — after any Agent multi-file edit, skim the changed-files list before moving on. This is the one habit most worth keeping even when rushed: an unreviewed bad multi-file edit costs far more time to debug later than the 20 seconds to skim it now.

## 3. What NOT to reach for live

- Don't hand-tune Cursor settings/models mid-interview — pick a model once at the start (favor a fast, capable default) and move on.
- Don't use Agent mode for large open-ended asks ("build the whole backend") without first giving it the specific layering/entity — an unscoped prompt produces generic CRUD that then needs a second pass to align with the conventions, costing more net time than scoping it correctly once.
- Don't fight Tab's suggestions into submission for stylistic preferences that don't matter (quote style, minor formatting) — accept-and-move-on beats a perfect diff in this format.

## 4. Talking to the interviewer about tool use

If asked about your workflow/tools during the interview, it's fair and often a positive signal to be transparent that you're using Cursor's AI features deliberately (Tab for boilerplate, Agent for scoped multi-file changes) rather than writing everything by hand — the interesting signal for them is whether *you* made the architecture and pattern decisions (which this skill set prepared you to explain clearly, see `hld-interview-design` §3) while the tool accelerated typing, not whether the tool designed the system.
