#!/usr/bin/env bash
# Interview laptop, new Cursor login: copy scaffold + skill into an empty app dir
# so Cursor finds AGENTS.md, .cursor/rules, .cursor/skills, .cursor/commands with
# no user-level sync. Usage: ./into-project.sh ~/app
set -euo pipefail
K=$(cd "$(dirname "$0")" && pwd)
DEST=${1:-}
if [ -z "$DEST" ]; then
  echo "usage: $0 <empty-project-dir>" >&2
  exit 1
fi
mkdir -p "$DEST"
cp -R "$K/scaffold/." "$DEST/"
mkdir -p "$DEST/.cursor/skills/interview-kit"
cp "$K/SKILL.md" "$DEST/.cursor/skills/interview-kit/"
cp -R "$K/reference" "$DEST/.cursor/skills/interview-kit/"
echo "Open this folder in Cursor (File > Open Folder), then send /interview and paste the prompt:"
echo "  $DEST"
