# Ingestion endpoints. Wire in with one line in main.py:
#   app.include_router(ingest_router)

import csv
import io

from fastapi import APIRouter, Depends, Query, UploadFile

from app.deps import get_ingest_service
from app.ingest_models import BatchStatus, IngestRequest, IngestResult, MetricTotal
from app.ingest_service import IngestService

ingest_router = APIRouter(tags=["ingest"])


@ingest_router.post("/ingest", response_model=IngestResult, status_code=202)
def ingest(req: IngestRequest, svc: IngestService = Depends(get_ingest_service)):
    """202 Accepted: stored and queued, not yet processed -- poll the batch."""
    return svc.ingest(req.records)


@ingest_router.post("/ingest/csv", response_model=IngestResult, status_code=202)
def ingest_csv(file: UploadFile, svc: IngestService = Depends(get_ingest_service)):
    """File-upload variant: header row = EventIn field names. Plain `def` on
    purpose -- CSV parsing is sync work, so it runs in the threadpool instead
    of blocking the event loop (the graded blocking-call trap)."""
    rows = list(csv.DictReader(io.TextIOWrapper(file.file, encoding="utf-8")))
    return svc.ingest(rows)


@ingest_router.get("/ingest/{batch_id}", response_model=BatchStatus)
def get_batch(batch_id: str, svc: IngestService = Depends(get_ingest_service)):
    return svc.get_batch(batch_id)


@ingest_router.get("/totals", response_model=list[MetricTotal])
def totals(
    source: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    svc: IngestService = Depends(get_ingest_service),
):
    return svc.totals(source, limit, offset)
