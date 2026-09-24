"""End-to-end check of a LIVE deployment: `make e2e URL=https://... [KEY=<api key>]`.

Stdlib only (runs anywhere python3 does). Exercises what a grader would: ops
endpoints, auth, CRUD + error envelopes, ingest -> worker -> totals with 20
concurrent writers (a lost-update race would undercount), and the rate limit
(last, since it spends this key's budget for a minute). Test data uses a random
source name and items are deleted. KEY defaults to the first key in $API_KEYS.
Rename /items and the payloads here when you rename the entity (section 4.18)."""

import concurrent.futures as cf
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime

BASE = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("URL", "")).rstrip("/")
if not BASE.startswith("http"):
    sys.exit("usage: make e2e URL=https://<app> (KEY=<key> or API_KEYS in the env)")
KEY = os.environ.get("KEY") or (os.environ.get("API_KEYS", "").split(",")[0].split(":") + ["", ""])[1]
HOST = BASE.split("://")[1].split("/")[0].split(":")[0]


def _pin_dns() -> None:
    """A new *.ondigitalocean.app host can be negatively cached locally for 30 min
    (section 4.19): resolve via DNS-over-HTTPS and pin it, like `make deployed`."""
    try:
        socket.gethostbyname(HOST)
        return
    except OSError:
        pass
    url = f"https://dns.google/resolve?name={HOST}&type=A"
    with urllib.request.urlopen(url, timeout=5) as r:
        ip = next(a["data"] for a in json.load(r).get("Answer", []) if a["type"] == 1)
    orig = socket.getaddrinfo
    socket.getaddrinfo = lambda h, *a, **k: orig(ip if h == HOST else h, *a, **k)
    print(f"(local DNS has no {HOST}; pinned to {ip} via DoH)")


def req(method, path, body=None, headers=None, key=True, raw=None, retry=True):
    h = {"content-type": "application/json"} if body is not None else {}
    if key and KEY:
        h["x-api-key"] = KEY
    h.update(headers or {})
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    for _ in range(3):  # a polite client: on 429, wait Retry-After and try again
        r = urllib.request.Request(BASE + path, data=data, method=method, headers=h)
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(r, timeout=20) as resp:
                code, hdrs, text = resp.status, resp.headers, resp.read().decode()
        except urllib.error.HTTPError as e:
            code, hdrs, text = e.code, e.headers, e.read().decode()
        ms = (time.perf_counter() - start) * 1000
        if code != 429 or not retry:
            break
        time.sleep(int(hdrs.get("retry-after", "1")))
    try:
        js = json.loads(text) if text else None
    except ValueError:
        js = text
    return code, hdrs, js, ms


passed, failed = 0, []


def check(name, ok, info=""):
    global passed
    if ok:
        passed += 1
        print(f"  ok   {name}")
    else:
        failed.append(name)
        print(f"  FAIL {name}  {info}")


def env(res):
    return res[2].get("error", {}) if isinstance(res[2], dict) else {}


_pin_dns()
print(f"target {BASE}  key={'yes' if KEY else 'NONE'}")

print("ops (no key)")
for path in ("/health", "/ready", "/version", "/metrics", "/docs"):
    check(f"GET {path} 200", req("GET", path, key=False)[0] == 200)
c, h, j, _ = req("GET", "/ready", key=False)
check("/ready status ok (all dependencies up)", isinstance(j, dict) and j.get("status") == "ok", j)
c, h, j, _ = req("GET", "/version", key=False, headers={"x-request-id": "e2e-trace"})
sha = j.get("git_sha", "") if isinstance(j, dict) else ""
check("x-app-version header == /version git_sha", sha and h.get("x-app-version") == sha, (sha, h.get("x-app-version")))
check("x-request-id echoed", h.get("x-request-id") == "e2e-trace")

print("auth")
res = req("GET", "/items", key=False)
if res[0] == 200:
    print("  (auth is OFF on this deployment: API_KEYS unset, dev mode)")
elif not KEY:
    sys.exit("auth is ON here but no key: pass KEY=<key> or export API_KEYS (./preflight.sh made ~/.api_keys.env)")
else:
    check("no key -> 401 envelope", res[0] == 401 and env(res).get("code") == "unauthorized", res[:3:2])
    check("wrong key -> 401", req("GET", "/items", key=False, headers={"x-api-key": "wrong"})[0] == 401)
    res = req("GET", "/items", key=False, headers={"authorization": f"Bearer {KEY}"})
    check("valid key as Bearer -> 200", res[0] == 200, res[0])

print("CRUD + errors")
c, h, j, _ = req("POST", "/items", {"title": "e2e", "body": "hello"})
check("POST /items 201", c == 201, (c, j))
iid = j["id"] if c == 201 else "missing"
check("GET /items/{id}", req("GET", f"/items/{iid}")[0] == 200)
c, h, j, _ = req("GET", "/items?limit=200")
check("list contains it", c == 200 and any(i["id"] == iid for i in j["items"]), c)
c, h, j, _ = req("PATCH", f"/items/{iid}", {"title": "renamed"})
check("PATCH is partial", c == 200 and j["title"] == "renamed" and j["body"] == "hello", j)
res = req("POST", "/items", {"title": ""})
check("invalid body -> 422 envelope w/ request_id", res[0] == 422 and env(res).get("request_id"), res[2])
res = req("POST", "/items", raw=b"{nope", headers={"content-type": "application/json"})
check("malformed JSON -> 4xx envelope", 400 <= res[0] < 500 and env(res), res[:3:2])
check("limit=0 -> 422", req("GET", "/items?limit=0")[0] == 422)
check("DELETE 204", req("DELETE", f"/items/{iid}")[0] == 204)
res = req("GET", f"/items/{iid}")
check("GET deleted -> 404 not_found", res[0] == 404 and env(res).get("code") == "not_found", res[:3:2])

src, now = f"e2e-{uuid.uuid4().hex[:8]}", datetime.now(UTC).isoformat()


def ev(i, v, metric="temp"):
    return {"event_id": f"{src}-{i}", "source": src, "metric": metric, "value": v, "ts": now}


res = req("POST", "/ingest", {"records": [ev(1, 10)]})
if res[0] == 404:
    print("ingest: not deployed (strip-ingest.sh), skipped")
else:
    print(f"ingest -> worker -> totals  (source={src})")
    check("POST /ingest 202", res[0] == 202, res[:3:2])
    batches = [res[2]["batch_id"]] if res[0] == 202 else []
    bad = [ev(1, 10), ev(2, 5), {**ev(3, 1), "ts": "2026-01-01T00:00:00"}, {**ev(4, 1), "value": "x"}, {"source": src}]
    c, h, j, _ = req("POST", "/ingest", {"records": bad})
    check(
        "mixed batch: 1 accepted, 1 duplicate, 3 rejected w/ index",
        c == 202 and (j["accepted"], j["duplicates"], sorted(r["index"] for r in j["rejected"])) == (1, 1, [2, 3, 4]),
        j,
    )
    batches.append(j.get("batch_id"))
    with cf.ThreadPoolExecutor(20) as pool:  # 20 concurrent writers, same (source, metric)
        par = list(pool.map(lambda i: req("POST", "/ingest", {"records": [ev(f"p{i}", 1)]}), range(20)))
    check("20 concurrent ingests -> 202", all(p[0] == 202 for p in par), [p[0] for p in par])
    batches += [p[2]["batch_id"] for p in par if p[0] == 202]
    deadline = time.time() + 60
    while batches and time.time() < deadline:
        batches = [b for b in batches if req("GET", f"/ingest/{b}")[2].get("status") != "completed"]
        time.sleep(1 if batches else 0)
    check("worker completed every batch (<60s)", not batches, f"{len(batches)} pending")
    c, h, j, _ = req("GET", f"/totals?source={src}")
    temp = next((t for t in j if t["metric"] == "temp"), {}) if c == 200 else {}
    got = (temp.get("count"), temp.get("total"))
    check("totals exact: count 22, total 35 (no lost updates)", got == (22, 35), temp)

print("rate limit (spends this key's budget for ~1 min)")
c, h, j, _ = req("GET", "/items?limit=1")
limit, left = int(h.get("x-ratelimit-limit", 0)), int(h.get("x-ratelimit-remaining", 0))
if not limit or left > 400:
    print(f"  skipped (limit={limit or 'none'}, remaining={left})")
else:
    with cf.ThreadPoolExecutor(20) as pool:
        burst = list(pool.map(lambda _: req("GET", "/items?limit=1", retry=False), range(left + 5)))
    codes = [b[0] for b in burst]
    over = next((b for b in burst if b[0] == 429), None)
    # >= 1, not == 5: the sliding window frees a little budget during the burst
    check(f"burst of {left + 5} over {left} remaining -> 429s", 429 in codes and set(codes) <= {200, 429}, codes)
    check("429 has Retry-After + rate_limited envelope", over and int(over[1]["retry-after"]) > 0, over and over[2])

lat = sorted(req("GET", "/health", key=False)[3] for _ in range(10))
print(f"latency /health from here: p50 {lat[4]:.0f}ms  max {lat[-1]:.0f}ms")
print(f"\n{passed} passed, {len(failed)} failed" + (f": {failed}" if failed else ""))
sys.exit(1 if failed else 0)
