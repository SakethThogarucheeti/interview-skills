#!/usr/bin/env bash
# Not an ingestion/processing prompt? Run once from the project root to remove the
# ingestion add-on (ingest API, worker, their tests, compose + App Platform worker).
set -euo pipefail
cd "$(dirname "$0")"
rm -f backend/app/ingest_*.py backend/app/worker.py backend/tests/test_ingest.py
python3 - <<'PY'
def edit(path, fn):
    s = open(path).read(); open(path, "w").write(fn(s))
edit("backend/app/main.py", lambda s: s.replace("from app.ingest_routes import ingest_router\n", "")
     .replace("app.include_router(ingest_router)\n", ""))
def strip_deps(s):
    s = s.replace("from app.ingest_repository import IngestRepository, PostgresIngestRepository\n"
                  "from app.ingest_service import IngestService\n", "")
    return s[:s.index("\n\n@lru_cache\ndef get_ingest_repository")].rstrip("\n") + "\n"
edit("backend/app/deps.py", strip_deps)
edit("backend/docker-compose.yml", lambda s: s[:s.index("  worker:")] + s[s.index("volumes:\n  pgdata"):])
for spec in (".do/app.yaml", ".do/app.image.yaml"):
    edit(spec, lambda s: s[:s.index("workers:")] + s[s.index("databases:"):])
PY
echo "ingestion add-on removed; run: make -C backend check"
