#!/usr/bin/env bash
# The one setup command, for Cursor and Claude Code alike:
#   git clone -q --depth 1 https://github.com/SakethThogarucheeti/interview-skills ~/prep
#   ~/prep/interview-kit/into-project.sh ~/app
# Builds the project: scaffold in the root, this playbook in .kit/ (AGENTS.md points
# there; Cursor reads AGENTS.md, Claude Code reads it via CLAUDE.md), git init + first
# commit, then ./preflight.sh. Then open ~/app in Cursor, or `cd ~/app && claude`.
set -euo pipefail
K=$(cd "$(dirname "$0")" && pwd)
DEST=${1:?usage: into-project.sh <new-project-dir>}
# Empty, or only editor/git dotdirs: it can be the folder already open in Cursor.
if [ -n "$(ls -A "$DEST" 2>/dev/null | grep -vxE '\.cursor|\.vscode|\.git|\.DS_Store')" ]; then
  echo "$DEST is not empty; pick a new directory (nothing was copied)" >&2
  exit 1
fi
mkdir -p "$DEST/.kit"
cp -R "$K/scaffold/." "$DEST/"
cp -R "$K/SKILL.md" "$K/reference" "$DEST/.kit/"
HERE=$PWD
cd "$DEST"
[ -d .git ] || git init -q -b main
if git config user.email >/dev/null; then
  git add -A && git commit -q -m "Scaffold from interview-kit" && echo "created $DEST (git: first commit on main)"
else
  echo "created $DEST -- set a git identity, then commit:"
  echo "  git config --global user.name '<you>' && git config --global user.email '<you@example.com>'"
  echo "  git add -A && git commit -m 'Scaffold from interview-kit'"
fi
echo
./preflight.sh
echo
if [ "$PWD" = "$(cd "$HERE" && pwd)" ]; then
  echo "built in the open folder: clear the 'still needs you' list, then paste the interview prompt"
else
  echo "open it: Cursor -> File > Open Folder -> $DEST, then /interview + the prompt"
  echo "         Claude Code -> cd $DEST && claude, then paste the prompt"
fi
