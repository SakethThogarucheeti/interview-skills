#!/usr/bin/env bash
# Not in the interview's Ubuntu 24 container (e.g. your own Arch/macOS laptop)? Run the same setup in one:
#   ./dev.sh                 build the image if needed, start the container, open a shell in the project
#   ./dev.sh ./preflight.sh  run any command inside it (this is how to finish setup)
# The project is bind-mounted, so edits show up on both sides.
# The host's `gh` token is passed in as GH_TOKEN (no second GitHub login; without host gh, log in
# once inside), and ~/.api_keys.env is bind-mounted (same API keys). doctl auth lives in a named volume.
# DO_TOKEN (and only it) is forwarded per command, so `DO_TOKEN=<token> ./dev.sh ./preflight.sh` works. API is on :8000.
set -euo pipefail
cd "$(dirname "$0")"
N=app-dev
H=/home/dev
docker image inspect $N >/dev/null 2>&1 || docker build -q -t $N .devcontainer >/dev/null
if [ "$(docker inspect -f '{{.State.Running}}' $N 2>/dev/null)" != true ]; then
  docker rm -f $N >/dev/null 2>&1 || true
  touch "$HOME/.api_keys.env"; chmod 600 "$HOME/.api_keys.env"
  export GH_TOKEN=${GH_TOKEN:-$(gh auth token 2>/dev/null || true)}
  docker run -d --name $N -p 8000:8000 \
    -v "$PWD:$H/app" ${GH_TOKEN:+-e GH_TOKEN} -v "$HOME/.api_keys.env:$H/.api_keys.env" \
    -v $N-doctl:$H/.config/doctl -v $N-gh:$H/.config/gh \
    $N >/dev/null
  docker exec $N sudo chown dev:dev $H/.config/doctl $H/.config/gh
  docker exec $N gh auth setup-git 2>/dev/null || true
fi
[ $# -gt 0 ] || set -- bash
T=-i; [ -t 0 ] && T=-it
exec docker exec $T ${DO_TOKEN:+-e DO_TOKEN} -w $H/app $N "$@"
