# Talking points for common walkthrough questions

Current state → bottleneck → concrete next step, grounded in the actual code just written, not generic vocabulary.

**Traffic spike / going viral?** Current: single stateless FastAPI process; bottleneck: DB connections/CPU on one box. By effort: (a) horizontal scale — N stateless instances behind a load balancer, immediate since there's no in-memory session state, (b) cache hot reads, (c) a queue to absorb write bursts async, (d) rate-limit/backpressure at the edge.

**How would you cache this?** Hot read path → cache key = lookup key → TTL or write-through invalidation. Redis from the start (`app/cache.py`) since an in-process cache doesn't stay consistent across N instances. Cache-aside: miss → read DB → populate → return (`Cache.get_or_set`). Mention cache stampede (coalescing or jittered TTL fixes it). Fan-out → Redis pub/sub (`app/events.py`) before a dedicated broker.

**Scale the database?** First: indexes + the connection pool already in `PostgresItemRepository`. Second: read replicas — Postgres is already behind a repository interface, so routing reads to a replica is a swap at that seam. Third: sharding, only if pushed on scale — name the shard key and the cross-shard-query tradeoff.

**Consistency / race conditions?** Name the specific race in the actual app (counter increment, double-booking) and the fix: a unique constraint/transaction, `SELECT ... FOR UPDATE`, or an atomic increment — not a vague "add a lock." Strong consistency on core writes, eventual is fine for denormalized reads/counters.

**Reliability?** Idempotency key or upsert on retryable writes. Timeouts + backoff on outbound calls. Stateless app, so a crashed instance is just replaced.

**Deploy/monitor?** Already done by the time it's asked, so describe what you built. It's containerized (non-root image with a healthcheck). Every push to main deploys that exact commit: App Platform builds it from GitHub, CI runs the tests on the same push, and `/version` names the live commit. Rollback redeploys an earlier build, with no rebuild. It emits JSON logs with request IDs, Prometheus metrics, and liveness vs readiness. Alert on symptoms: 5xx rate, p95 latency, `/ready` failing, and for ingestion, backlog depth/age (`pending_count`) plus a rising `failed` batch count. Next steps if pushed: Prometheus + Grafana scraping `/metrics`, OpenTelemetry tracing keyed on the same request ID, autoscaling, managed-DB standby nodes and read replicas, Terraform plan/apply in CI with Spaces-backed state, and DOKS if App Platform is outgrown.

**Ingestion at 100x?** Current: the API validates + stores + enqueues in one transaction, and N workers drain a Postgres queue. In order of effort:
- (a) scale API replicas and `--scale worker=N`: both are stateless, and `SKIP LOCKED` makes N workers safe;
- (b) `COPY` instead of `unnest` for huge batches, and `LISTEN/NOTIFY` instead of polling;
- (c) partition `events` by time and add a retention job;
- (d) past roughly thousands of batches/sec, move the queue to Redis Streams/SQS/Kafka with consumer groups, behind the same repository seam, keeping idempotent consumers since delivery stays at-least-once.
Name the trade-off: Postgres-as-queue buys transactional enqueue and zero extra infra at the cost of peak throughput.

**Configuration / secrets?** Everything is env (`config.py`): the same image runs in CI, locally and in prod, and bad config fails at startup. Secrets never touch git: App Platform injects DB credentials through bindable vars (`${db.DATABASE_URL}`), and `API_KEYS` is an encrypted App Platform `SECRET`. Next step: a secrets manager with rotation.

**Business trade-offs / "what would you do with more time" / downtime windows?** Expect this alongside the technical questions — DigitalOcean frames the post-build conversation as covering both. Ground it in what you actually cut, e.g. "skipped read replicas and HA — no payoff at this scale, and the repository seam makes adding one later a config change, not a rewrite." For downtime: stateless instances mean a rolling restart is zero-downtime; the one real SPOF is non-replicated Postgres/Redis, and the honest answer is a maintenance window or managed failover, not built here for time. Naming the real gap and its cost/benefit beats pretending it's handled.
