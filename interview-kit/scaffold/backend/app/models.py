# Domain + API models for a generic "Item" resource.
# Rename Item -> your actual entity (Link, Task, Poll, ...) and adjust fields.
# Keep ONE definition of each shape (DRY) and reuse it across create/read/update.
# Validation lives here, declaratively -- bounds on every string, unknown
# fields rejected -- so bad input is a 422 before it reaches the service.

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

_INPUT = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Item(BaseModel):
    """Domain object -- what's actually stored."""

    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    title: str
    body: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ItemCreate(BaseModel):
    """Request shape for POST -- never reuse Item for input (id/created_at aren't client-supplied)."""

    model_config = _INPUT
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=10_000)


class ItemUpdate(BaseModel):
    model_config = _INPUT
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, max_length=10_000)


class ItemPage(BaseModel):
    items: list[Item]
    limit: int
    offset: int
