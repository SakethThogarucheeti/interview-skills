# HTTP-level tests: status codes, validation, error envelope, pagination,
# request IDs. One test per behavior, named for the behavior.
from app.deps import get_service
from app.main import app


def test_health_and_ready(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ok", "checks": {"database": True}}


def test_crud_flow(client):
    created = client.post("/items", json={"title": "test", "body": "hi"})
    assert created.status_code == 201
    item_id = created.json()["id"]

    assert client.get(f"/items/{item_id}").json()["title"] == "test"
    assert client.patch(f"/items/{item_id}", json={"title": "updated"}).json()["title"] == "updated"
    assert client.delete(f"/items/{item_id}").status_code == 204
    assert client.get(f"/items/{item_id}").status_code == 404


def test_validation_rejects_bad_input_with_envelope(client):
    for bad in ({"title": ""}, {"title": "   "}, {"title": "x" * 201}, {"title": "ok", "admin": True}, {}):
        res = client.post("/items", json=bad)
        assert res.status_code == 422, bad
        assert res.json()["error"]["code"] == "validation_error"
        assert res.json()["error"]["details"]


def test_not_found_uses_error_envelope_with_request_id(client):
    res = client.get("/items/nope", headers={"x-request-id": "abc123"})
    assert res.status_code == 404
    assert res.headers["x-request-id"] == "abc123"
    assert res.json()["error"] == {"code": "not_found", "message": "Item nope not found", "request_id": "abc123"}


def test_patch_null_field_leaves_it_unchanged(client):
    item_id = client.post("/items", json={"title": "keep", "body": "b"}).json()["id"]
    assert client.patch(f"/items/{item_id}", json={"title": None, "body": "new"}).json()["title"] == "keep"


def test_pagination_is_bounded_and_ordered_newest_first(client):
    for i in range(5):
        client.post("/items", json={"title": f"t{i}"})
    page = client.get("/items?limit=2&offset=1").json()
    assert [i["title"] for i in page["items"]] == ["t3", "t2"]
    assert client.get("/items?limit=1000").status_code == 422


def test_unhandled_error_returns_500_envelope_without_leaking(client):
    class Boom:
        def list_items(self, *_):
            raise RuntimeError("secret internals")

    app.dependency_overrides[get_service] = lambda: Boom()
    res = client.get("/items")
    assert res.status_code == 500
    assert res.json()["error"]["code"] == "internal_error"
    assert "secret" not in res.text


def test_metrics_exposed(client):
    client.get("/health")
    body = client.get("/metrics").text
    assert 'http_requests_total{method="GET",route="/health",status="200"}' in body


def test_version_identifies_the_running_build(client):
    res = client.get("/version")
    assert set(res.json()) == {"git_sha", "build_time", "env"}
    assert res.headers["x-app-version"] == res.json()["git_sha"]
