# Minimal smoke test -- run with: APP_ENV=test pytest test_smoke.py
# APP_ENV=test makes deps.py hand out InMemoryItemRepository and no real cache,
# so this runs with no Postgres/Redis needed (demonstrates why repo+cache are
# behind Protocols/optional in service.py).
import os

os.environ["APP_ENV"] = "test"

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").status_code == 200


def test_crud_flow():
    created = client.post("/items", json={"title": "test", "body": "hi"}).json()
    item_id = created["id"]

    assert client.get(f"/items/{item_id}").json()["title"] == "test"
    assert client.patch(f"/items/{item_id}", json={"title": "updated"}).json()["title"] == "updated"
    assert client.delete(f"/items/{item_id}").status_code == 204
    assert client.get(f"/items/{item_id}").status_code == 404
