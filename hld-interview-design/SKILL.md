---
name: hld-interview-design
description: Framework for architecting a system design in a timed coding interview (e.g. DigitalOcean's build-an-app round) — picks the simplest architecture that still has a credible answer for scale/traffic-spike/availability follow-up questions, without over-engineering something you have to implement in the same session. Use when asked to design the system before/while building a full-stack app in a time-boxed interview, or when the user asks "how would you handle traffic spikes / scaling / caching / etc." Pairs with lld-design-patterns (implementation-level design) and fastapi-react-scaffold (turns the chosen architecture into running code).
---

# HLD for timed build-and-defend interviews

The interview isn't "design a system you'll never build" (classic HLD interviews) — it's "build a working app in ~2 hours, then defend the design as if it had to survive production traffic." That changes the goal: **pick the architecture you can actually finish, then know exactly what you'd change and why if traffic/scale/reliability requirements grew.** A design that's "perfect" on a whiteboard but unfinished at the 2-hour mark loses. A design that runs but has no answer for "what if this got 100x traffic" also loses.

## 0. Time-box the design phase itself

Spend 5-10 minutes max on design before typing code. In a 2-hour build:
- ~10 min: clarify requirements + sketch architecture (this skill)
- ~45-50 min: backend (see `fastapi-react-scaffold`, `lld-design-patterns`)
- ~30-40 min: frontend
- ~15-20 min: polish, test the golden path, prep your scaling talking points
- buffer: 10-15 min

If you're still drawing boxes at minute 15, you're over-designing. Collapse to the simplest version and move.

## 1. Clarify requirements out loud (2-3 minutes)

Ask every open question at once, in one batch, rather than one at a time — a back-and-forth burns wall-clock time you don't get back, and most of these are independent of each other. Where a question doesn't actually change scope or architecture, skip asking and just state the reasonable assumption out loud instead of waiting on it.

Cover:
- **Core entities & actions**: what does the user create/read/update/delete? (e.g. for a URL shortener: create short link, redirect, view stats)
- **Read vs write ratio**: most interview prompts (shorteners, polls, chat, task boards, rate limiters, notification systems) are read-heavy or write-bursty — say which out loud, it drives your caching/scaling story.
- **Consistency requirement**: does this need to be strongly consistent (payments, inventory) or is eventual consistency fine (view counts, feeds, likes)? Most interview prompts tolerate eventual consistency — say so, it simplifies everything downstream.
- **Explicit non-goals**: state what you're NOT building (multi-region, multi-tenant auth, billing) so the interviewer knows you scoped deliberately, not out of ignorance.

## 2. Default architecture: the "one box, clean seams" pattern

Unless requirements clearly demand otherwise, start here — it's fast to build and every scaling answer below is "here's the seam where I'd split this out":

```
[React SPA] --HTTP/JSON--> [FastAPI monolith] --> [Postgres]
                                  |
                                  +--> [Redis: cache-aside for hot reads]
                                  +--> [Redis: pub/sub for fan-out, if the prompt needs live updates]
```

(This is the default stack for this interview — Postgres + Redis are provisioned from the start via `fastapi-react-scaffold`'s `docker-compose.yml`, not swapped in later. The "swap seam" framing below still matters for follow-up questions about scaling *those* — read replicas, Redis Cluster, a real message broker for heavier queueing needs, etc.)

Why this wins in a 2-hour format:
- One deployable, one repo, no network calls between your own services to debug under time pressure.
- Every "how would you scale this" question has a crisp answer: "today it's in-process/one DB; the seam is already there — swap the cache for Redis, the queue for Celery+Redis or SQS, and put a load balancer in front of N stateless FastAPI instances." You get full credit for the answer without having to actually stand up Redis/Kafka/K8s live.
- Clean seams = you architect the code (see `lld-design-patterns`) so those swaps are isolated behind an interface, not a rewrite. That's the extensibility the interviewer is actually testing for — not whether you deployed Kafka in 90 minutes.

**Do NOT** reach for microservices, message queues, or multi-region setups as your starting build. They cost implementation time you don't have and interviewers read premature distributed-systems complexity in a 2-hour app as a red flag, not a strength.

## 3. Talking points for common follow-up questions

Keep these as a mental checklist — the interviewer is grading whether you *know* the next step, not whether you built it. State the current state, the bottleneck, and the specific next step.

**"How do you handle a traffic spike / going viral?"**
1. Current: single stateless FastAPI process behind (imagined) a load balancer.
2. Bottleneck: DB connections and CPU on one box.
3. Next steps, in order of effort: (a) horizontal scale — spin up N identical stateless app instances behind a load balancer (works immediately *because* the app holds no in-memory session state — mention this is why you chose stateless JWT/token auth over server-side sessions), (b) cache hot reads (see below), (c) add a queue to absorb write bursts asynchronously instead of blocking the request, (d) rate-limit/backpressure at the edge so a spike degrades gracefully instead of falling over.

**"How would you cache this?"**
- Identify the hot read path (e.g. redirect lookup, feed fetch). Cache key = the lookup key (short code, user id + page). TTL or write-through invalidation on update.
- You're already using Redis from the start (`app/cache.py` in `fastapi-react-scaffold`), specifically *because* an in-process cache doesn't stay consistent once you horizontally scale to N app instances — say this explicitly, it's why Redis is the default here rather than something you'd bolt on later.
- Cache-aside pattern: check cache → miss → read DB → populate cache → return (exactly what `Cache.get_or_set` does). Mention cache stampede (many misses at once on a hot key) as a known failure mode; fix is request coalescing or a short jittered TTL.
- If the prompt needs live/multi-consumer fan-out (e.g. live results, notifications), the same Redis instance's pub/sub (`app/events.py`) is the low-effort answer before reaching for a dedicated message broker.

**"How would you scale the database?"**
- First lever: indexes on your actual query patterns (mention the specific columns from your schema) and the connection pool already in `PostgresItemRepository` (bounds concurrent connections instead of exhausting Postgres under a spike).
- Second: read replicas for a read-heavy workload — your API layer already treats Postgres behind a repository/interface (see `lld-design-patterns`), so routing reads to a replica is a swap at that seam, not a rewrite.
- Third: only reach for sharding/partitioning if asked explicitly about very large scale — explain the shard key you'd pick (e.g. by user id) and that it trades cross-shard queries for horizontal write capacity. Don't volunteer this unprompted; it's rarely warranted at the scale implied by a 2-hour app and over-mentioning it can read as reciting buzzwords.

**"What about consistency / race conditions?"**
- Name the specific race in your actual app (e.g. two requests incrementing a counter, double-booking a slot) and how you'd close it: a DB-level unique constraint or transaction, `SELECT ... FOR UPDATE`, or an atomic increment, rather than "just add a lock" as a vague answer.
- Distinguish where you need strong consistency (writes to the core entity) vs where eventual consistency is fine (denormalized read models, counters, analytics) — this shows judgment, not just mechanism.

**"How do you make this reliable / handle failures?"**
- Idempotency on write endpoints that might be retried (client-supplied idempotency key, or natural idempotency via upsert).
- Timeouts + retries with backoff on any outbound call.
- Health check endpoint + the app being stateless so a crashed instance is just restarted/replaced, not a data-loss event.

**"How would you deploy/monitor this?"**
- Containerize (Dockerfile — have one ready, see `fastapi-react-scaffold`), run N replicas behind a load balancer (DigitalOcean App Platform or a DO Load Balancer + Droplets is the on-brand answer here), basic structured logging + a `/health` endpoint, metrics on request latency/error rate.

## 4. Draw it, don't just say it

Even a rough ASCII/box diagram on a shared doc or whiteboard tool beats describing boxes verbally — it gives the interviewer a artifact to probe ("what happens if this box dies") and shows you think spatially about a system, not just as a feature list. Keep it to 5-8 boxes max; more than that and you're either over-scoping or duplicating detail that belongs in the code.

## 5. Know when to *not* invoke this whole process

If the prompt is small enough that "one FastAPI file + one React file" is the honest whole design (e.g. a simple CRUD todo list), say that plainly and spend the saved time on polish and the scaling narrative instead of inventing structure the app doesn't need. Over-architecting a trivial prompt is exactly the failure mode this skill exists to prevent.
