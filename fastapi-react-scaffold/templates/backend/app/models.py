# Domain + API models for a generic "Item" resource.
# Rename Item -> your actual entity (Link, Task, Poll, ...) and adjust fields.
# Keep ONE definition of each shape (DRY) and reuse it across create/read/update.

from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from pydantic import BaseModel, Field


class Item(BaseModel):
    """Domain object — what's actually stored."""
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    title: str
    body: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ItemCreate(BaseModel):
    """Request shape for POST — never reuse Item directly for input (id/created_at aren't client-supplied)."""
    title: str
    body: str = ""


class ItemUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
