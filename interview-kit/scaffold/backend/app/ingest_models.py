# Ingestion shapes. Rename EventIn's fields to the prompt's record (transaction,
# reading, log line...). Records are validated ONE AT A TIME in the service so
# one bad record is reported back, not a 422 for the whole batch.

from datetime import datetime
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class EventIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    event_id: str = Field(min_length=1, max_length=64)  # client-supplied -> idempotent retries
    source: str = Field(min_length=1, max_length=64)
    metric: str = Field(min_length=1, max_length=64)
    value: float = Field(allow_inf_nan=False)
    ts: AwareDatetime  # naive timestamps rejected: no guessing timezones


class IngestRequest(BaseModel):
    records: list[dict[str, Any]] = Field(min_length=1)


class RejectedRecord(BaseModel):
    index: int
    errors: list[str]


class IngestResult(BaseModel):
    batch_id: str
    status: str
    received: int
    accepted: int
    duplicates: int
    rejected: list[RejectedRecord]


class BatchStatus(BaseModel):
    id: str
    status: str  # pending -> completed | failed
    accepted: int
    attempts: int
    error: str | None
    created_at: datetime


class MetricTotal(BaseModel):
    source: str
    metric: str
    count: int
    total: float
