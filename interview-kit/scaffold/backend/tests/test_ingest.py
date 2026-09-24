# Ingestion tests. Unit part uses a fake repo (no DB); the integration part
# runs the real SQL -- idempotency, SKIP LOCKED workers, atomic aggregation --
# against Postgres at TEST_DATABASE_URL (`make up && make test-int`).
import os
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.deps import get_ingest_service
from app.ingest_service import IngestService
from app.main import app

GOOD = {"event_id": "e1", "source": "s1", "metric": "cpu", "value": 1.5, "ts": "2026-01-01T00:00:00Z"}


class FakeIngestRepo:
    def __init__(self, pending: int = 0) -> None:
        self.seen: set[str] = set()
        self.pending = pending

    def insert_batch(self, batch_id, events):
        new = {e.event_id for e in events} - self.seen
        self.seen |= new
        return len(new)

    def pending_count(self):
        return self.pending


@pytest.fixture
def ingest_client():
    repo = FakeIngestRepo()
    app.dependency_overrides[get_ingest_service] = lambda: IngestService(repo, 3, 10)
    with TestClient(app) as c:
        yield c, repo
    app.dependency_overrides.clear()


def test_partial_batch_reports_each_bad_record(ingest_client):
    client, _ = ingest_client
    res = client.post(
        "/ingest",
        json={
            "records": [
                GOOD,
                {**GOOD, "event_id": "e2", "value": "NaN"},
                {**GOOD, "event_id": "e3", "ts": "2026-01-01T00:00:00"},
            ]
        },
    )
    assert res.status_code == 202
    body = res.json()
    assert (body["received"], body["accepted"]) == (3, 1)
    assert [r["index"] for r in body["rejected"]] == [1, 2]


def test_retried_batch_is_idempotent(ingest_client):
    client, _ = ingest_client
    client.post("/ingest", json={"records": [GOOD]})
    body = client.post("/ingest", json={"records": [GOOD]}).json()
    assert (body["accepted"], body["duplicates"], body["status"]) == (0, 1, "completed")


def test_oversized_batch_is_413_and_backlog_is_503(ingest_client):
    client, repo = ingest_client
    assert client.post("/ingest", json={"records": [GOOD] * 4}).status_code == 413
    repo.pending = 10
    res = client.post("/ingest", json={"records": [GOOD]})
    assert (res.status_code, res.headers["retry-after"]) == (503, "5")


def test_csv_upload_goes_through_the_same_validation(ingest_client):
    client, _ = ingest_client
    csv_body = (
        "event_id,source,metric,value,ts\nc1,s1,cpu,2.5,2026-01-01T00:00:00Z\nc2,s1,cpu,oops,2026-01-01T00:00:00Z\n"
    )
    res = client.post("/ingest/csv", files={"file": ("events.csv", csv_body, "text/csv")})
    assert res.status_code == 202
    assert (res.json()["accepted"], [r["index"] for r in res.json()["rejected"]]) == (1, [1])


DB = os.environ.get("TEST_DATABASE_URL")


@pytest.mark.integration
@pytest.mark.skipif(not DB, reason="TEST_DATABASE_URL not set")
def test_concurrent_workers_process_every_batch_exactly_once():
    from psycopg_pool import ConnectionPool

    from app.ingest_repository import PostgresIngestRepository

    pool = ConnectionPool(DB, min_size=1, max_size=10, open=True)
    with pool.connection() as conn:
        conn.execute("DROP TABLE IF EXISTS metric_totals, events, ingest_batches")
    repo = PostgresIngestRepository(pool)
    svc = IngestService(repo, 1000, 1000)

    batches, per_batch = 40, 25
    for b in range(batches):  # every batch hits the SAME (source, metric) key: max contention
        svc.ingest([{**GOOD, "event_id": f"b{b}-{i}", "value": 1.0} for i in range(per_batch)])
    assert svc.ingest([{**GOOD, "event_id": "b0-0"}]).duplicates == 1  # cross-batch dedupe

    processed: list[str] = []
    lock = threading.Lock()

    def worker():
        while (batch_id := repo.process_next(max_attempts=3)) is not None:
            with lock:
                processed.append(batch_id)

    with ThreadPoolExecutor(8) as ex:
        for f in [ex.submit(worker) for _ in range(8)]:
            f.result()

    assert len(processed) == len(set(processed)) == batches  # no batch claimed twice
    total = svc.totals("s1", 10, 0)[0]
    assert (total.count, total.total) == (batches * per_batch, float(batches * per_batch))
    assert repo.pending_count() == 0
    pool.close()
