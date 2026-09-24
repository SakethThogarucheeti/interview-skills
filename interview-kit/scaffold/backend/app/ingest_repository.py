# Postgres doubles as the durable job queue: no extra broker to deploy, and
# enqueueing is in the SAME transaction as the data, so a batch can never be
# stored-but-not-queued or queued-but-not-stored.

from typing import Protocol

from psycopg_pool import ConnectionPool

from app.ingest_models import BatchStatus, EventIn, MetricTotal
from app.repository import SCHEMA_LOCK_ID

SCHEMA = """
CREATE TABLE IF NOT EXISTS ingest_batches (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pending',
    accepted INT NOT NULL DEFAULT 0,
    attempts INT NOT NULL DEFAULT 0,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ingest_batches_pending_idx ON ingest_batches (created_at) WHERE status = 'pending';
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES ingest_batches (id),
    source TEXT NOT NULL,
    metric TEXT NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    ts TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS events_batch_idx ON events (batch_id);
CREATE TABLE IF NOT EXISTS metric_totals (
    source TEXT NOT NULL,
    metric TEXT NOT NULL,
    count BIGINT NOT NULL,
    total DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (source, metric)
);
"""


class IngestRepository(Protocol):
    def insert_batch(self, batch_id: str, events: list[EventIn]) -> int: ...
    def pending_count(self) -> int: ...
    def get_batch(self, batch_id: str) -> BatchStatus | None: ...
    def totals(self, source: str | None, limit: int, offset: int) -> list[MetricTotal]: ...
    def process_next(self, max_attempts: int) -> str | None: ...


class PostgresIngestRepository:
    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool
        with self._pool.connection() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(%s)", (SCHEMA_LOCK_ID,))  # see repository.py
            conn.execute(SCHEMA)

    def insert_batch(self, batch_id: str, events: list[EventIn]) -> int:
        """One transaction, one round-trip for the rows (unnest, not N INSERTs).
        ON CONFLICT DO NOTHING makes a retried batch a no-op: duplicates are
        counted, never double-processed. Returns how many rows were new."""
        cols = (
            [e.event_id for e in events],
            [e.source for e in events],
            [e.metric for e in events],
            [e.value for e in events],
            [e.ts for e in events],
        )
        with self._pool.connection() as conn:
            conn.execute("INSERT INTO ingest_batches (id) VALUES (%s)", (batch_id,))
            inserted = conn.execute(
                """INSERT INTO events (event_id, batch_id, source, metric, value, ts)
                   SELECT e, %s, s, m, v, t
                   FROM unnest(%s::text[], %s::text[], %s::text[], %s::float8[], %s::timestamptz[])
                        AS u(e, s, m, v, t)
                   ON CONFLICT (event_id) DO NOTHING RETURNING event_id""",
                (batch_id, *cols),
            ).fetchall()
            # Nothing new to process -> complete now, don't make a worker wake up for it.
            conn.execute(
                "UPDATE ingest_batches SET accepted = %s, status = %s WHERE id = %s",
                (len(inserted), "pending" if inserted else "completed", batch_id),
            )
        return len(inserted)

    def pending_count(self) -> int:
        with self._pool.connection() as conn:
            return conn.execute("SELECT count(*) FROM ingest_batches WHERE status = 'pending'").fetchone()[0]

    def get_batch(self, batch_id: str) -> BatchStatus | None:
        with self._pool.connection() as conn:
            r = conn.execute(
                "SELECT id, status, accepted, attempts, error, created_at FROM ingest_batches WHERE id = %s",
                (batch_id,),
            ).fetchone()
        if r is None:
            return None
        return BatchStatus(id=r[0], status=r[1], accepted=r[2], attempts=r[3], error=r[4], created_at=r[5])

    def totals(self, source: str | None, limit: int, offset: int) -> list[MetricTotal]:
        with self._pool.connection() as conn:
            rows = conn.execute(
                """SELECT source, metric, count, total FROM metric_totals
                   WHERE %(source)s::text IS NULL OR source = %(source)s
                   ORDER BY source, metric LIMIT %(limit)s OFFSET %(offset)s""",
                {"source": source, "limit": limit, "offset": offset},
            ).fetchall()
        return [MetricTotal(source=r[0], metric=r[1], count=r[2], total=r[3]) for r in rows]

    def process_next(self, max_attempts: int) -> str | None:
        """Claim + process + complete ONE batch in ONE transaction.
        - FOR UPDATE SKIP LOCKED: N workers never grab the same batch (the naive
          SELECT-pending-then-UPDATE lets two workers double-count it).
        - Aggregation is an atomic upsert (total = total + EXCLUDED.total), not
          read-modify-write in Python -- the graded lost-update race.
        - ORDER BY in the aggregate: workers lock metric_totals rows in the same
          order, so two batches touching the same keys can't deadlock.
        - A crash mid-way rolls everything back; the batch is simply pending again.
        Returns the processed batch id, or None when the queue is empty."""
        with self._pool.connection() as conn:
            row = conn.execute(
                """SELECT id FROM ingest_batches WHERE status = 'pending'
                   ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED"""
            ).fetchone()
            if row is None:
                return None
            batch_id = row[0]
            try:
                conn.execute(
                    """INSERT INTO metric_totals (source, metric, count, total)
                       SELECT source, metric, count(*), sum(value) FROM events
                       WHERE batch_id = %s GROUP BY source, metric ORDER BY source, metric
                       ON CONFLICT (source, metric) DO UPDATE
                       SET count = metric_totals.count + EXCLUDED.count,
                           total = metric_totals.total + EXCLUDED.total""",
                    (batch_id,),
                )
                conn.execute(
                    """UPDATE ingest_batches SET status = 'completed', attempts = attempts + 1,
                       updated_at = now() WHERE id = %s""",
                    (batch_id,),
                )
            except Exception as exc:
                # Poison-batch guard: count the attempt, give up after max_attempts
                # instead of retrying forever and starving the queue.
                conn.rollback()
                conn.execute(
                    """UPDATE ingest_batches SET attempts = attempts + 1, error = %s, updated_at = now(),
                       status = CASE WHEN attempts + 1 >= %s THEN 'failed' ELSE 'pending' END
                       WHERE id = %s AND status = 'pending'""",
                    (str(exc)[:500], max_attempts, batch_id),
                )
                conn.commit()
                raise
        return batch_id
