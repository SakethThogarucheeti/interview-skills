# /interview

We are in DigitalOcean's timed build-and-deploy interview on a **fresh Cursor login**.

1. Read `.cursor/skills/interview-kit/SKILL.md` (copied here by `into-project.sh`). If it is missing, stop and tell the user to run that script from the prep clone.
2. If a prompt is in the chat: restate entities in 1–2 sentences, ask the **one** clarifying-question batch from the skill (functional + non-functional), and **stop**. Do not edit app code until they answer.
3. After answers: pitfall scan, `make install && make check`, `make up` or `make up-native`, `make run`, first DigitalOcean deploy, then rename-and-extend starting at `backend/app/models.py`.
4. Audit every AI diff for write races and blocking `async def`. Routes stay plain `def`. Cut features before tests, observability, or deploy.
