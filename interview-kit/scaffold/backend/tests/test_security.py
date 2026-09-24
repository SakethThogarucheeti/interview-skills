# Auth + rate limiting. Unit part swaps app.state.guard for known keys and an
# in-memory limiter on a fake clock; the integration part proves the Redis
# limiter holds its limit under concurrency (`make up && make test-int`).
import os
import threading

import pytest

from app.main import app
from app.security import Guard, InMemoryRateLimiter, RedisRateLimiter, install_security, parse_api_keys

ALICE, BOB = {"X-API-Key": "alice-key"}, {"Authorization": "Bearer bob-key"}


class Clock:
    def __init__(self, t: float = 6000.0) -> None:  # 6000 = start of a 60s window
        self.t = t

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def secured(client, clock):
    saved = app.state.guard
    app.state.guard = Guard(parse_api_keys("alice:alice-key:3,bob:bob-key", 5), InMemoryRateLimiter(clock), 5)
    yield client
    app.state.guard = saved


def test_ops_endpoints_need_no_key(secured):
    for path in ("/health", "/ready", "/version", "/metrics", "/openapi.json"):
        assert secured.get(path).status_code == 200, path


def test_missing_or_wrong_key_is_401_envelope(secured):
    for headers in ({}, {"X-API-Key": "nope"}, {"Authorization": "Bearer nope"}):
        res = secured.get("/items", headers=headers)
        assert res.status_code == 401, headers
        assert res.json()["error"]["code"] == "unauthorized"
        assert res.json()["error"]["request_id"]
        assert res.headers["www-authenticate"] == "Bearer"


def test_both_header_styles_accepted(secured):
    assert secured.get("/items", headers=ALICE).status_code == 200
    assert secured.get("/items", headers=BOB).status_code == 200


def test_limit_is_per_client_with_tier_override_and_retry_after(secured):
    remaining = [secured.get("/items", headers=ALICE).headers["x-ratelimit-remaining"] for _ in range(3)]
    assert remaining == ["2", "1", "0"]  # alice's own tier: 3/min
    res = secured.get("/items", headers=ALICE)
    assert res.status_code == 429
    assert res.json()["error"]["code"] == "rate_limited"
    assert 1 <= int(res.headers["retry-after"]) <= 60
    assert secured.get("/items", headers=BOB).headers["x-ratelimit-limit"] == "5"  # bob unaffected, default limit


def test_sliding_window_carries_over_previous_window():
    clock = Clock()
    rl = InMemoryRateLimiter(clock)
    assert all(rl.hit("c", 10)[0] for _ in range(10))
    assert not rl.hit("c", 10)[0]
    clock.t += 60 + 30  # halfway into the next window: half of the 10 still counts
    assert [rl.hit("c", 10)[0] for _ in range(6)] == [True] * 5 + [False]
    clock.t += 60  # the full window has passed
    assert rl.hit("c", 10)[0]


def test_bad_api_keys_fail_at_startup():
    for bad in ("nokey", "a:", ":k", "a:k:notanumber", "a:k:1:extra"):
        with pytest.raises(ValueError):
            parse_api_keys(bad, 10)


def test_prod_refuses_to_start_without_keys():
    from fastapi import FastAPI

    with pytest.raises(RuntimeError):
        install_security(FastAPI(), "", 10, InMemoryRateLimiter(), "prod")


REDIS = os.environ.get("TEST_REDIS_URL")


@pytest.mark.integration
@pytest.mark.skipif(not REDIS, reason="TEST_REDIS_URL not set")
def test_redis_limiter_never_over_admits_under_concurrency():
    import redis

    r = redis.Redis.from_url(REDIS)
    r.delete(*r.keys("rl:race:*") or ["_"])
    rl = RedisRateLimiter(r, Clock())
    allowed: list[bool] = []
    lock = threading.Lock()

    def hammer():
        for _ in range(10):
            ok = rl.hit("race", 25)[0]
            with lock:
                allowed.append(ok)

    threads = [threading.Thread(target=hammer) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert allowed.count(True) == 25  # 200 concurrent attempts, exactly the limit admitted
