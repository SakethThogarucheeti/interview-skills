#!/usr/bin/env bash
# Game-day minute 0: `./preflight.sh` (or `make -C backend preflight`) from the project root.
# Does everything automatable, starts the slow cloud step in the background, and ends
# with a checklist of only what still needs a human. Safe to re-run at any point.
#   REGISTRY=<globally-unique-name>  also create a DOCR registry (path B only)
#   TF=0                             skip Terraform (dev-database route, or path C)
set -uo pipefail
cd "$(dirname "$0")"
todo=()
ok() { printf '  ok    %s\n' "$*"; }
fix() { printf '  FIXED %s\n' "$*"; }
need() { printf '  TODO  %s\n' "$1"; todo+=("$2"); }

echo "tools"
export PATH="$HOME/.local/bin:$PATH"
for t in git python3 make gh doctl jq curl; do command -v $t >/dev/null && ok "$t" || need "$t missing" "sudo apt-get install -y $t"; done
if ! command -v uv >/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1 && fix "uv installed (~/.local/bin; new shells: export PATH=\$HOME/.local/bin:\$PATH)" || need "uv install failed" "curl -LsSf https://astral.sh/uv/install.sh | sh"
else ok "uv"; fi
if [ "${TF:-1}" != 0 ] && ! command -v terraform >/dev/null; then
  command -v unzip >/dev/null || sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq unzip >/dev/null 2>&1
  curl -fsSLo /tmp/tf.zip "https://releases.hashicorp.com/terraform/1.9.8/terraform_1.9.8_linux_$(dpkg --print-architecture).zip" \
    && sudo unzip -oq /tmp/tf.zip -d /usr/local/bin && fix "terraform installed" || need "terraform install failed" "see reference/scaffold.md 4.17, or TF=0 and use a dev database"
elif command -v terraform >/dev/null; then ok "terraform"; fi
command -v node >/dev/null && ok "node" || echo "  --    node (only needed for a frontend)"
docker info >/dev/null 2>&1 && ok "docker daemon" || echo "  --    no docker daemon (expected in the container: make up-native; DO builds the images)"

echo "accounts"
if doctl account get --format Email --no-header >/dev/null 2>&1; then ok "doctl: $(doctl account get --format Email --no-header)"
else need "doctl not authenticated" "doctl auth init    # paste the DO token you were given, then re-run ./preflight.sh"; fi
if gh auth status >/dev/null 2>&1; then ok "gh: $(gh api user -q .login 2>/dev/null)"
else need "gh not authenticated" "gh auth login      # device code, finish in the browser"; fi

echo "api keys"
KEYS_FILE="$HOME/.api_keys.env"  # outside the repo on purpose: never committed
if [ -n "${API_KEYS:-}" ]; then ok "API_KEYS set in this shell"
elif [ -s "$KEYS_FILE" ]; then ok "keys in $KEYS_FILE"
else
  (umask 077; python3 -c 'import secrets as s; print("API_KEYS=me:%s,interviewer:%s" % (s.token_urlsafe(24), s.token_urlsafe(24)))' > "$KEYS_FILE")
  fix "generated keys for 'me' and 'interviewer' in $KEYS_FILE (mode 600)"
fi
[ -n "${API_KEYS:-}" ] || todo+=("set -a; . $KEYS_FILE; set +a   # loads API_KEYS into this shell (make app-create reads it)")

echo "infrastructure"
if [ "${TF:-1}" = 0 ]; then echo "  --    skipped (TF=0)"
elif kill -0 "$(cat /tmp/tf.pid 2>/dev/null)" 2>/dev/null; then ok "terraform (init+apply) already running: tail -f /tmp/tf.log"
elif ! doctl account get >/dev/null 2>&1 || ! command -v terraform >/dev/null; then need "terraform not started (needs doctl auth + terraform)" "re-run ./preflight.sh after the items above"
else
  # Terraform reads DIGITALOCEAN_TOKEN; reuse doctl's stored token so it's pasted once.
  export DIGITALOCEAN_TOKEN="${DIGITALOCEAN_TOKEN:-$(sed -n 's/^access-token: *//p' "$HOME/.config/doctl/config.yaml" 2>/dev/null | head -1)}"
  apply() { terraform apply -input=false -auto-approve -no-color ${REGISTRY:+-var registry_name=$REGISTRY}; }
  (cd infra && terraform init -input=false -no-color >/dev/null \
     && { apply || { echo "RETRY (fresh-account 412s are transient)"; apply; }; }) > /tmp/tf.log 2>&1 &
  echo $! > /tmp/tf.pid  # the whole init+apply job, so a re-run never starts a second one
  fix "terraform apply started in background (managed PG + Valkey, ~6 min): tail -f /tmp/tf.log"
  echo "        watch: doctl databases list --format Name,Engine,Status"
fi

echo
echo "still needs you:"
[ ${#todo[@]} -eq 0 ] || printf '  - %s\n' "${todo[@]}"
cat <<'EOF'
  - Path A, once per DO account: console -> Apps -> Create App -> GitHub, authorize DigitalOcean
    for the repo, then leave the wizard ("No components detected" is expected).
  - After the first commit: gh repo create <name> --private --source=. --push
next: cd backend && make install && make check && make up-native, then (A) make app-create once /tmp/tf.log says Apply complete.
EOF
