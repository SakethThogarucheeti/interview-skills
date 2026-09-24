# Ubuntu 24.04 dev container matching the interview environment, with every tool preflight needs
# baked in (doctl, terraform, gh, uv, Postgres + Redis for `make up-native`). Built by ../dev.sh.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
      sudo git python3 python3-venv make curl jq unzip ca-certificates rsync openssh-client gh \
      postgresql redis-server nodejs npm \
    && rm -rf /var/lib/apt/lists/*
# doctl (not in Ubuntu's repos): latest GitHub release, arch-aware
RUN set -e; a=$(dpkg --print-architecture); \
    v=$(curl -fsSL https://api.github.com/repos/digitalocean/doctl/releases/latest | jq -r .tag_name | tr -d v); \
    curl -fsSL "https://github.com/digitalocean/doctl/releases/download/v${v}/doctl-${v}-linux-${a}.tar.gz" | tar -xz -C /usr/local/bin doctl
# terraform, pinned to the version the kit was verified with
RUN set -e; a=$(dpkg --print-architecture); \
    curl -fsSLo /tmp/tf.zip "https://releases.hashicorp.com/terraform/1.9.8/terraform_1.9.8_linux_${a}.zip" \
    && unzip -oq /tmp/tf.zip -d /usr/local/bin && rm /tmp/tf.zip
# passwordless-sudo user; uid 1000 so files written to the bind-mounted project stay yours on the host
RUN userdel -r ubuntu 2>/dev/null || true; \
    useradd -m -u 1000 -s /bin/bash dev && echo 'dev ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/dev
USER dev
ENV HOME=/home/dev PATH=/home/dev/.local/bin:$PATH
RUN curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1
WORKDIR /home/dev/app
CMD ["sleep", "infinity"]
