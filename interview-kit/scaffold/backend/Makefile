# One entry point for humans and CI alike -- the CI workflow calls these targets.
.PHONY: preflight install up up-native run test test-int lint fmt check image deploy deployed e2e api-key app-create app-status app-deploy app-rollback
DB ?= postgresql://postgres:postgres@localhost:5432/app
REDIS ?= redis://localhost:6379/15
# Every image is stamped with the commit it was built from (served at /version).
# "-dirty" marks a build with uncommitted changes -- it matches no commit.
GIT_SHA ?= $(shell if git rev-parse -q --verify HEAD >/dev/null 2>&1; then \
	printf %s "$$(git rev-parse HEAD)"; git diff --quiet HEAD || printf -- -dirty; else echo dev; fi)
BUILD_TIME := $(shell date -u +%Y-%m-%dT%H:%M:%SZ)
export GIT_SHA BUILD_TIME
APP_NAME := $(shell awk '/^name:/ {print $$2; exit}' ../.do/app.yaml 2>/dev/null)
APP_IMAGE = registry.digitalocean.com/$(REGISTRY)/app:$(GIT_SHA)
# Looked up only when a target uses them (recursive =), so no doctl/gh call otherwise.
APP_ID = $(shell doctl apps list --format ID,Spec.Name --no-header | awk -v n=$(APP_NAME) '$$2==n {print $$1}')
APP_URL = $(shell doctl apps list --format Spec.Name,DefaultIngress --no-header | awk -v n=$(APP_NAME) '$$1==n {print $$2}')
REPO ?= $(shell gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)
URL ?= $(APP_URL)
# macOS has no `timeout`; use coreutils' gtimeout if present, else run unbounded.
TIMEOUT := $(shell command -v timeout || command -v gtimeout)
to = $(if $(TIMEOUT),$(TIMEOUT) $(1))
# Fill a spec's placeholders. API_KEYS is read from the environment by the shell ($$),
# so the secret never shows up in make's echoed command or in a log.
fill = sed -e 's|$${GITHUB_REPO}|$(REPO)|g' -e 's|$${IMAGE_TAG}|$(1)|g' -e "s|\$${API_KEYS}|$$API_KEYS|g" $(2)
need-keys = @test -n "$$API_KEYS" || { echo 'export API_KEYS=name:key,... first (make api-key NAME=you)'; exit 1; }

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
deploy:  # make deploy HOST=<droplet-ip>
	$(call to,120) rsync -az --delete --exclude .venv --exclude __pycache__ --exclude .env ./ root@$(HOST):/root/app/
	$(call to,300) ssh root@$(HOST) "cd /root/app && GIT_SHA=$(GIT_SHA) BUILD_TIME=$(BUILD_TIME) APP_PORT=80 \
		docker compose -f docker-compose.yml up -d --build --wait"
	$(call to,10) curl -fsS http://$(HOST)/ready
	@$(MAKE) --no-print-directory deployed URL=http://$(HOST)
deployed:  # is live == local HEAD? URL defaults to this App Platform app; pass URL=http://<droplet-ip> otherwise
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
	python3 e2e.py $(URL)
api-key:  # make api-key NAME=alice -> one name:key entry for API_KEYS (comma-join several)
	@python3 -c 'import secrets, sys; print(sys.argv[1] + ":" + secrets.token_urlsafe(24))' $(or $(NAME),client)
# make app-create -- App Platform builds from your GitHub repo (REPO defaults to the
# gh remote) and redeploys on every push to main. Re-run after editing .do/app.yaml.
app-create:
	@test -n "$(REPO)" || { echo "no GitHub repo: gh repo create <name> --private --source=.. --push"; exit 1; }
	$(need-keys)
	$(call fill,,../.do/app.yaml) | $(call to,1200) doctl apps create --spec - --upsert --wait
	@$(MAKE) --no-print-directory deployed
# Recent deployments: Cause names the commit for GitHub-built deploys.
app-status:
	doctl apps list-deployments $(APP_ID) --format ID,Cause,Phase,Created --no-header | head -5
# make app-deploy REGISTRY=<docr-name> -- the CI App Platform job, run where Docker works.
# --platform: App Platform runs amd64; a Mac builds arm64 by default and the app
# would crash-loop. fill replaces IMAGE_TAG and API_KEYS; the db./cache. bindable
# variables in the spec are App Platform's to resolve at deploy time.
app-deploy:
	doctl registry login --expiry-seconds 1200
	docker build -q --platform linux/amd64 --build-arg GIT_SHA --build-arg BUILD_TIME -t $(APP_IMAGE) .
	docker push -q $(APP_IMAGE)
	$(need-keys)
	$(call fill,$(GIT_SHA),../.do/app.image.yaml) | $(call to,900) doctl apps create --spec - --upsert --wait
	@$(MAKE) --no-print-directory deployed
# make app-rollback REGISTRY=<name> SHA=<old full sha> -- re-point the app at an
# image that's already in the registry (every deploy pushed one). No rebuild, so
# the rollback runs exactly the bits that ran before.
app-rollback:
	$(need-keys)
	$(call fill,$(SHA),../.do/app.image.yaml) | $(call to,900) doctl apps create --spec - --upsert --wait
