#!/usr/bin/env bash
# Not in the interview's Ubuntu 24 container (e.g. your own Arch/macOS laptop)? Run the same setup in one:
#   ./dev.sh                 build the image if needed, start the container, open a shell in the project
#   ./dev.sh ./preflight.sh  run any command inside it (this is how to finish setup)
# The project is bind-mounted, so edits show up on both sides.
# The host's `gh` token is passed as GH_TOKEN on each command (no second GitHub login; without host gh, log in
# once inside), and ~/.api_keys.env is bind-mounted (same API keys). doctl auth lives in a named volume.
# DO_TOKEN is forwarded per command too, so `DO_TOKEN=<token> ./dev.sh ./preflight.sh` works. API: 127.0.0.1:8000.
set -euo pipefail
cd "$(dirname "$0")"
N=app-dev
H=/home/dev
# Recreate if it isn't running, or is running on another project (it would silently run commands there).
src=$(docker inspect -f "{{range .Mounts}}{{if eq .Destination \"$H/app\"}}{{.Source}}{{end}}{{end}}" $N 2>/dev/null || true)
if [ "$(docker inspect -f '{{.State.Running}}' $N 2>/dev/null)" != true ] || [ "$src" != "$PWD" ]; then
  [ -z "$src" ] || [ "$src" = "$PWD" ] || echo "dev.sh: $N was on $src; recreating it on $PWD" >&2
  docker rm -f $N >/dev/null 2>&1 || true
  docker build -q --build-arg UID="$(id -u)" -t $N .devcontainer >/dev/null  # cached: ~1 s unless the Dockerfile changed
  touch "$HOME/.api_keys.env"; chmod 600 "$HOME/.api_keys.env"
  docker run -d --name $N -p 127.0.0.1:8000:8000 \
    -v "$PWD:$H/app" -v "$HOME/.api_keys.env:$H/.api_keys.env" \
    -v $N-doctl:$H/.config/doctl -v $N-gh:$H/.config/gh \
    $N >/dev/null
  docker exec $N sudo chown dev:dev $H/.config/doctl $H/.config/gh
  docker exec $N gh auth setup-git 2>/dev/null || true
fi
# Tokens go per command, never into the container's config (docker inspect would show them).
export GH_TOKEN=${GH_TOKEN:-$(gh auth token 2>/dev/null || true)}
[ $# -gt 0 ] || set -- bash
T=-i; [ -t 0 ] && T=-it
exec docker exec $T ${GH_TOKEN:+-e GH_TOKEN} ${DO_TOKEN:+-e DO_TOKEN} -w $H/app $N "$@"
