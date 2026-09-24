<!-- interview-kit reference file; § numbers match the index in ../SKILL.md -->

### 4.22 DigitalOcean's cloud offerings — what exists and when to reach for it

| Category | Product | What it is | In this interview |
|---|---|---|---|
| **Compute** | **Droplets** | VMs (Basic, General Purpose, CPU-/Memory-Optimized, GPU); Marketplace images like "Docker on Ubuntu" | Fallback deploy target (§4.19) |
| | **App Platform** | PaaS for containers/buildpacks: `services` (HTTP), `workers`, `jobs` (PRE/POST_DEPLOY, scheduled), `static_sites`, `functions`. TLS, rolling deploys, health checks, alerts, logs, autoscaling on dedicated instances | **Recommended target**; spec = `.do/app.yaml` |
| | **DOKS** (Kubernetes) | Managed Kubernetes, free control plane (HA control plane optional) | Mention only: "if we outgrew App Platform or needed custom networking/sidecars" |
| | **Functions** | Serverless functions | Mention only (event hooks, cron) |
| **Data** | **Managed Databases** | PostgreSQL, MySQL, MongoDB, **Valkey** (Redis-compatible; replaced Managed Redis in 2025), Kafka, OpenSearch. Automated backups + point-in-time recovery, standby nodes for automatic failover, read-only replicas, PgBouncer connection pools, trusted sources, VPC | PG = source of truth, Valkey = cache (`infra/main.tf`). "HA?" → standby node (`node_count = 2`); "read scale?" → read replica behind the repository seam |
| | App Platform **dev database** | Single small Postgres attached to one app (~$7/mo), no HA | The fast/cheap path (§4.19) |
| **Storage** | **Spaces** | S3-compatible object storage with built-in CDN | Raw uploads/archives for ingestion at scale; Terraform remote state (§4.21) |
| | **Volumes** | Block storage attached to Droplets | Only for Droplet-hosted Postgres data |
| **Containers** | **Container Registry (DOCR)** | Private registry; starter (free, 1 repo, 500 MiB), basic ($5, 5 repos, 5 GiB), professional | Holds `app:<sha>` images (basic tier: starter fills after a few pushes; untagged layers count until garbage-collected) |
| **Networking** | **VPC** | Private network per region (default one exists) | App Platform ↔ managed DBs traffic stays private |
| | **Load Balancers** | Regional L4/L7 LBs with health checks (Droplets/DOKS) | "N Droplets behind an LB" answer; App Platform has one built in |
| | **Cloud Firewalls** | Stateful allow-lists attached to Droplets or tags | Droplet target: only 22/80 in (`infra/main.tf`) |
| | **Reserved IPs, DNS** | Static IPs you can move between Droplets; managed DNS | Blue/green on Droplets: swap the reserved IP |
| **Ops** | **Monitoring** | Droplet metrics + alert policies (CPU/mem/disk/bandwidth); App Platform per-component metrics and alerts | App alerts in `.do/app*.yaml` (deploy failed, CPU, p95) |
| | **Uptime** | External HTTP checks from multiple regions + latency/down/SSL-expiry alerts | 1 min in the console on `/ready`; name it as the SLO probe |
| | **Log forwarding** | App Platform log destinations (Datadog, Logtail, Papertrail, OpenSearch) | Our JSON logs are ready to forward, unchanged |
| **Access / IaC** | API tokens (scoped), Projects, Teams; `doctl`, Terraform provider, Pulumi, app spec, GitHub Actions (`app_action`, `action-doctl`) | Everything in §4.19–§4.23 |

Talking-point shape: "I used App Platform because the managed pieces (TLS, rolling deploys, health-gated traffic, managed DB failover and backups) are exactly what I'd otherwise hand-build, and the app spec keeps it all in git. If requirements outgrew it, DOKS is the step up, and the app wouldn't change: same image, same env config."
