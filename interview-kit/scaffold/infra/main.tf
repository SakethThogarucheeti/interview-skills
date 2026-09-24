# Long-lived DigitalOcean infrastructure as code. Changes rarely, so it's applied
# from a terminal (`terraform apply`), while the app itself (.do/app.yaml) is
# redeployed by CI on every push. Auth: export DIGITALOCEAN_TOKEN=<api token>.
terraform {
  required_version = ">= 1.6"
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
  }
  # Local state is fine for a one-person session. Shared/CI state: DO Spaces is
  # S3-compatible -- see the skill's section 4.23 for the backend "s3" block.
}

provider "digitalocean" {}

variable "name" {
  description = "Prefix for every resource. .do/app.yaml's cluster_name values must match."
  type        = string
  default     = "interview"
}

variable "region" {
  type    = string
  default = "nyc3"
}

variable "registry_name" {
  description = "Container registry name, globally unique across DigitalOcean. Only path B (CI-built images) needs one; empty = no registry (one per account)."
  type        = string
  default     = ""
}

variable "create_managed_databases" {
  description = "Managed Postgres + Valkey for App Platform. false for a Droplet-only deploy (it runs its own)."
  type        = bool
  default     = true
}

variable "create_droplet" {
  description = "true = also create the single-Droplet target (section 4.19) instead of / as well as App Platform."
  type        = bool
  default     = false
}

variable "ssh_public_key" {
  description = "Contents of ~/.ssh/id_ed25519.pub; only used when create_droplet = true."
  type        = string
  default     = ""
}

# One registry per account. basic = 5 repos / 5 GiB (starter's 500 MiB fills
# after ~3 pushes of this image).
resource "digitalocean_container_registry" "this" {
  count                  = var.registry_name == "" ? 0 : 1
  name                   = var.registry_name
  subscription_tier_slug = "basic"
  region                 = var.region
}

# Managed Postgres: automated backups, point-in-time recovery, patching, and
# one-click standby nodes (node_count = 2) when HA is the answer.
resource "digitalocean_database_cluster" "pg" {
  count      = var.create_managed_databases ? 1 : 0
  name       = "${var.name}-pg"
  engine     = "pg"
  version    = "16"
  size       = "db-s-1vcpu-1gb"
  region     = var.region
  node_count = 1
}

# Managed Valkey = DigitalOcean's Redis-compatible cache (it replaced Managed
# Redis in 2025). redis-py speaks to it unchanged over rediss://.
resource "digitalocean_database_cluster" "cache" {
  count      = var.create_managed_databases ? 1 : 0
  name       = "${var.name}-cache"
  engine     = "valkey"
  version    = "8"
  size       = "db-s-1vcpu-1gb"
  region     = var.region
  node_count = 1
}

# --- Optional single-Droplet target (make deploy) -------------------------
resource "digitalocean_ssh_key" "deploy" {
  count      = var.create_droplet ? 1 : 0
  name       = "${var.name}-deploy"
  public_key = var.ssh_public_key
}

resource "digitalocean_droplet" "app" {
  count    = var.create_droplet ? 1 : 0
  name     = "${var.name}-app"
  image    = "ubuntu-24-04-x64"
  size     = "s-1vcpu-2gb"
  region   = var.region
  ssh_keys = [digitalocean_ssh_key.deploy[0].fingerprint]
  # Docker via the official script; `make deploy` does the rest over SSH.
  user_data = <<-CLOUDINIT
    #!/bin/sh
    curl -fsSL https://get.docker.com | sh
  CLOUDINIT
}

# Cloud Firewall: only SSH and HTTP in. Postgres/Redis on the Droplet are
# already unpublished (compose override is dev-only); this is defense in depth.
resource "digitalocean_firewall" "app" {
  count       = var.create_droplet ? 1 : 0
  name        = "${var.name}-app"
  droplet_ids = [digitalocean_droplet.app[0].id]

  inbound_rule {
    protocol         = "tcp"
    port_range       = "22"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }
  inbound_rule {
    protocol         = "tcp"
    port_range       = "80"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }
  outbound_rule {
    protocol              = "tcp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
  outbound_rule {
    protocol              = "udp"
    port_range            = "53"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
}

# Groups everything in the DO console under one project.
resource "digitalocean_project" "this" {
  name        = var.name
  purpose     = "Web Application"
  environment = "Production"
  resources = concat(
    digitalocean_database_cluster.pg[*].urn,
    digitalocean_database_cluster.cache[*].urn,
    digitalocean_droplet.app[*].urn,
  )
}

output "registry" {
  value = one(digitalocean_container_registry.this[*].name)
}

output "pg_cluster_name" {
  value = one(digitalocean_database_cluster.pg[*].name)
}

output "cache_cluster_name" {
  value = one(digitalocean_database_cluster.cache[*].name)
}

output "droplet_ip" {
  value = one(digitalocean_droplet.app[*].ipv4_address)
}
