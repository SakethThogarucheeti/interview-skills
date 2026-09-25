# Long-lived DigitalOcean infrastructure as code. Changes rarely, so it's applied
# once by ./preflight.sh (in the background), while the app itself (.do/app.yaml) is
# applied by `make app-create`. Auth: DIGITALOCEAN_TOKEN (preflight reuses doctl's login).
terraform {
  required_version = ">= 1.6"
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
  }
  # Local state is fine for a one-person session. Shared state would live in DO
  # Spaces (S3-compatible) via a backend "s3" block.
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

# Managed Postgres: automated backups, point-in-time recovery, patching, and
# one-click standby nodes (node_count = 2) when HA is the answer.
resource "digitalocean_database_cluster" "pg" {
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
  name       = "${var.name}-cache"
  engine     = "valkey"
  version    = "8"
  size       = "db-s-1vcpu-1gb"
  region     = var.region
  node_count = 1
}

# Groups everything in the DO console under one project.
resource "digitalocean_project" "this" {
  name        = var.name
  purpose     = "Web Application"
  environment = "Production"
  resources = [
    digitalocean_database_cluster.pg.urn,
    digitalocean_database_cluster.cache.urn,
  ]
}

output "pg_cluster_name" {
  value = digitalocean_database_cluster.pg.name
}

output "cache_cluster_name" {
  value = digitalocean_database_cluster.cache.name
}

