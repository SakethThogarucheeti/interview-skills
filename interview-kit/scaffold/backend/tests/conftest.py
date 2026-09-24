# Shared fixtures. Every test gets a FRESH in-memory repository via
# dependency_overrides -- no shared state between tests, no Postgres/Redis.
import os

os.environ.setdefault("APP_ENV", "test")

import pytest
from fastapi.testclient import TestClient

from app.deps import get_service
from app.main import app
from app.repository import InMemoryItemRepository
from app.service import ItemService


@pytest.fixture
def repo() -> InMemoryItemRepository:
    return InMemoryItemRepository()


@pytest.fixture
def client(repo):
    app.dependency_overrides[get_service] = lambda: ItemService(repo)
    # raise_server_exceptions=False: assert on the real 500 response a client would see.
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()
