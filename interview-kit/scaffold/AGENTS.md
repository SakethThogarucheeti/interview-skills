# Interview project

Fresh Cursor login: nothing outside this folder is ours.

1. Read `.cursor/skills/interview-kit/SKILL.md` before writing app code. If that file is missing, the install step was skipped — tell the user to run `into-project.sh`.
2. Prompt just pasted? Ask the clarifying-question batch **once** and stop. No scaffold edits until they answer.
3. Layering: thin `main.py` → `service.py` (domain errors, never HTTPException) → `repository.py` (only Postgres) → `cache.py` (Redis miss on failure). Routes stay plain `def`.
4. New mutations = one atomic SQL statement (or `SKIP LOCKED` claim). Never read-modify-write.
5. `make check` green after each file; commit; deploy early (`git push` or `make deploy`). `make up-native` if Docker is missing. Keep `/version` working.

`/interview` re-runs the checklist. Frontend only if they confirmed a UI.
