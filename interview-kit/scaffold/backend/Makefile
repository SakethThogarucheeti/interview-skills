# One entry point for humans and CI alike -- the CI workflow calls these targets.
# Run from the project root as `make -C backend <target>`; plain `make -C backend` lists them.
.PHONY: help preflight install up up-native run test test-int lint fmt check image deployed e2e api-key app-create app-status
DB ?= postgresql://postgres:postgres@localhost:5432/app
REDIS ?= redis://localhost:6379/15
# `make run` and CI's image build are stamped with the commit (served at /version; App Platform
# sets it from the pushed commit).
# "-dirty" marks a build with uncommitted changes -- it matches no commit.
GIT_SHA ?= $(shell if git rev-parse -q --verify HEAD >/dev/null 2>&1; then \
	printf %s "$$(git rev-parse HEAD)"; git diff --quiet HEAD || printf -- -dirty; else echo dev; fi)
BUILD_TIME := $(shell date -u +%Y-%m-%dT%H:%M:%SZ)
export GIT_SHA BUILD_TIME
APP_NAME := $(shell awk '/^name:/ {print $$2; exit}' ../.do/app.yaml 2>/dev/null)
# Looked up only when a target uses them (recursive =), so no doctl/gh call otherwise.
APP_ID = $(shell doctl apps list --format ID,Spec.Name --no-header | awk -v n=$(APP_NAME) '$$2==n {print $$1}')
APP_URL = $(shell doctl apps list --format Spec.Name,DefaultIngress --no-header | awk -v n=$(APP_NAME) '$$1==n {print $$2}')
REPO ?= $(shell gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)
URL ?= $(APP_URL)
# macOS has no `timeout`; use coreutils' gtimeout if present, else run unbounded.
TIMEOUT := $(shell command -v timeout || command -v gtimeout)
to = $(if $(TIMEOUT),$(TIMEOUT) $(1))
# Fill the spec's placeholders. API_KEYS is read from the environment by the shell ($$),
# so the secret never shows up in make's echoed command or in a log.
fill = sed -e 's|$${GITHUB_REPO}|$(REPO)|g' -e "s|\$${API_KEYS}|$$API_KEYS|g" $(1)
# Load API_KEYS from ./preflight.sh's ~/.api_keys.env unless the shell already has it. Prefix the
# recipe line that needs the keys, since every recipe line is its own shell.
load-keys = { [ -n "$$API_KEYS" ] || { [ ! -f "$(HOME)/.api_keys.env" ] || { set -a; . "$(HOME)/.api_keys.env"; set +a; }; }; };
with-keys = $(load-keys) { [ -n "$$API_KEYS" ] || { echo 'no API_KEYS: run ./preflight.sh (writes ~/.api_keys.env)'; exit 1; }; };

help:  # the default target
	@echo 'Game day (run from the project root):'
	@echo '  make -C backend install      create .venv and install deps'
	@echo '  make -C backend check        lint + unit tests (must be green before every commit)'
	@echo '  make -C backend up-native    start Postgres + Redis without Docker'
	@echo '  make -C backend run          API on :8000 (run it in the background with a log)'
	@echo '  make -C backend test-int     integration tests against the local Postgres + Redis'
	@echo '  make -C backend app-create   create/update the App Platform app (once, and after editing .do/app.yaml)'
	@echo '  make -C backend deployed     is the live app running local HEAD?'
	@echo '  make -C backend e2e          ~40 live checks against the deployed app'
	@echo '  make -C backend app-status   recent App Platform deployments'
	@echo 'Also: up (Postgres + Redis via Docker, if it works), test, lint, fmt, image (CI), api-key'

preflight:  # game-day minute 0: tools, auth, keys, background terraform, then a human checklist
	@../preflight.sh
install:
	$(call to,60) uv venv -q --allow-existing .venv
	$(call to,180) uv pip install -q -r requirements-dev.txt
up:
	docker compose up -d --wait postgres redis
# No Docker (e.g. inside a dev container): apt Postgres + Redis, same URLs as compose.
up-native:
	command -v pg_ctlcluster >/dev/null || { sudo apt-get update -qq && sudo DEBIAN_FRONTEND=noninteractive \
		$(call to,300) apt-get install -y -qq postgresql redis-server >/dev/null; }
	sudo service postgresql start && sudo service redis-server start
	sudo -u postgres psql -qc "ALTER USER postgres PASSWORD 'postgres'"
	sudo -u postgres createdb app 2>/dev/null || true
run:
	uv run uvicorn app.main:app --reload --port 8000 --no-access-log
test:
	APP_ENV=test uv run pytest -q -m "not integration"
test-int:
	APP_ENV=test TEST_DATABASE_URL=$(DB) TEST_REDIS_URL=$(REDIS) uv run pytest -q -m integration
lint:
	uv run ruff check . && uv run ruff format --check .
fmt:
	uv run ruff check --fix . && uv run ruff format .
check: lint test
image:
	docker build -q --build-arg GIT_SHA --build-arg BUILD_TIME -t app:$(GIT_SHA) .
deployed:  # is live == local HEAD? URL defaults to this App Platform app
	@test -n "$(URL)" || { echo "no URL: pass URL=... (or create the app first)"; exit 1; }
	@# A new app's hostname can be negatively cached locally for 30 min if looked up before its DNS
	@# record existed, so resolve it via public DNS-over-HTTPS and pin the IP with curl --resolve.
	@h=$$(echo "$(URL)" | sed -E 's#^https?://##; s#[/:].*##'); \
	for i in $$(seq 1 24); do \
		ip=$$(curl -fsS -m 5 "https://dns.google/resolve?name=$$h&type=A" 2>/dev/null | python3 -c \
			'import sys,json; a=[x["data"] for x in json.load(sys.stdin).get("Answer",[]) if x["type"]==1]; print(a[0] if a else "")' 2>/dev/null); \
		pin=$${ip:+--resolve $$h:443:$$ip --resolve $$h:80:$$ip}; \
		live=$$(curl -fsS -m 10 $$pin $(URL)/version 2>/dev/null | python3 -c 'import sys,json; print(json.load(sys.stdin)["git_sha"])' 2>/dev/null) \
		&& [ -n "$$live" ] && break; sleep 5; done; \
	if [ -z "$$live" ]; then echo "live:  UNREACHABLE at $(URL)/version after 2 min (new app: DNS can lag; check the console)"; exit 1; fi; \
	echo "live:  $$live"; echo "local: $(GIT_SHA)"; \
	if [ "$$live" = "$(GIT_SHA)" ]; then echo "UP TO DATE"; \
	elif [ "$$live-dirty" = "$(GIT_SHA)" ]; then echo "LIVE = HEAD, plus uncommitted local changes"; \
	else echo "DIFFERENT -- changes since live:"; \
	git log --oneline $$live..HEAD 2>/dev/null || echo "(live sha not in local history)"; fi
e2e:  # make e2e [URL=...] [KEY=...] -- 40-ish live checks incl. auth, races, rate limit (key: KEY or first of $$API_KEYS)
	@test -n "$(URL)" || { echo "no URL: pass URL=... (or create the app first)"; exit 1; }
	@$(load-keys) python3 e2e.py $(URL)
api-key:  # make api-key NAME=alice -> one name:key entry for API_KEYS (comma-join several)
	@python3 -c 'import secrets, sys; print(sys.argv[1] + ":" + secrets.token_urlsafe(24))' $(or $(NAME),client)
# make app-create -- App Platform builds from your GitHub repo (REPO defaults to the
# gh remote) and redeploys on every push to main. Re-run after editing .do/app.yaml.
app-create:
	@test -n "$(REPO)" || { echo "no GitHub repo: gh repo create <name> --private --source=.. --push"; exit 1; }
	$(with-keys) $(call fill,../.do/app.yaml) | $(call to,1200) doctl apps create --spec - --upsert --wait
	@$(MAKE) --no-print-directory deployed
# Recent deployments: Cause names the commit for GitHub-built deploys.
app-status:
	doctl apps list-deployments $(APP_ID) --format ID,Cause,Phase,Created --no-header | head -5
