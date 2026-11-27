"""Unit tests for app/core/limiter.py.

Implements tests/unit/core/limiter.cases.md, one test per case, in card order.
No database session. Limiting is seen through a minimal FastAPI app built per
test (Conventions APP / APP_NO_HANDLER); `app.main.app` is never started.
Nothing is mocked (Conventions, Externals: None).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
import itertools

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from limits.storage import MemoryStorage
from limits.strategies import FixedWindowRateLimiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.core.limiter import limiter

# Convention "RL_HEADERS"
RL_HEADERS = ["retry-after", "x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset"]


# Convention "Every test calls limiter.reset() first and last (also when it fails)"
@pytest.fixture(autouse=True)
def reset_limiter():
    limiter.reset()
    yield
    limiter.reset()


# slowapi registers a decorated route's limits under "<module>.<function name>" on the
# shared limiter, and a second registration under the same name adds the limit again.
# Each built app therefore names its route functions uniquely; paths and limits are the
# Conventions' own. (Harness hygiene only: the limiter's settings are not touched.)
_app_seq = itertools.count(1)


def _named(func, name):
    func.__name__ = name
    func.__qualname__ = name
    return func


# Convention "APP" (with_handler=True) and "APP_NO_HANDLER" (with_handler=False)
def build_app(with_handler=True, calls=None):
    """Convention "CALLS": a fresh {"limited": 0} per built app unless the test passes its own."""
    n = next(_app_seq)
    if calls is None:
        calls = {"limited": 0}
    app = FastAPI()
    app.state.limiter = limiter
    if with_handler:
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    def limited(request: Request):
        calls["limited"] += 1
        return {"ok": True}

    def second(request: Request):
        return {"ok": True}

    def free():
        return {"ok": True}

    limited = limiter.limit("2/minute")(_named(limited, f"limited_{n}"))
    second = limiter.limit("2/minute")(_named(second, f"second_{n}"))
    free = _named(free, f"free_{n}")
    app.get("/limited")(limited)
    app.get("/second")(second)
    app.get("/free")(free)
    return app


# Convention "req(client)"
def req(client, headers=()):
    return Request({"type": "http", "method": "GET", "path": "/", "headers": list(headers), "client": client})


# --------------------------------------------------------------------------- #
# limiter
# --------------------------------------------------------------------------- #


# [claude] LIM-01
def test_lim_01__the_singleton_s_settings():
    """LIM-01 — the singleton's settings.
    Rules: `limiter` R1, R3, R5, R6, R7 (incl. no key prefix, storage errors not swallowed)"""
    lim = limiter

    # Then 1
    assert lim._key_func is get_remote_address
    # Then 2
    assert lim.enabled is True
    # Then 3
    assert lim._headers_enabled is False
    # Then 4
    assert isinstance(lim._storage, MemoryStorage)
    # Then 5
    assert isinstance(lim._limiter, FixedWindowRateLimiter)
    # Then 6
    assert lim._key_style == "url"
    # Then 7
    assert list(lim._default_limits) == []
    # Then 8
    assert list(lim._application_limits) == []
    # Then 9
    assert not lim._key_prefix
    # Then 10
    assert lim._swallow_errors is False


# [claude] LIM-02
def test_lim_02__the_key_is_the_connecting_address_x_forwarded_for_and_x_real_ip_are_ignored():
    """LIM-02 — the key is the connecting address; X-Forwarded-For and X-Real-IP are ignored.
    Rules: `limiter` R1"""
    r = req(("1.2.3.4", 5), headers=[(b"x-forwarded-for", b"9.9.9.9"), (b"x-real-ip", b"8.8.8.8")])

    key = get_remote_address(r)

    # Then 1
    assert key == "1.2.3.4"


# [claude] LIM-03
def test_lim_03__two_requests_with_different_x_forwarded_for_share_one_counter():
    """LIM-03 — two requests with different X-Forwarded-For share one counter.
    Rules: `limiter` R1, R4"""
    c1 = TestClient(build_app())
    assert c1.get("/limited", headers={"X-Forwarded-For": "10.0.0.1"}).status_code == 200
    assert c1.get("/limited", headers={"X-Forwarded-For": "10.0.0.2"}).status_code == 200

    resp = c1.get("/limited", headers={"X-Forwarded-For": "10.0.0.3"})

    # Then 1
    assert resp.status_code == 429


# [claude] LIM-04
def test_lim_04__no_client_gives_the_key_127_0_0_1():
    """LIM-04 — no client gives the key 127.0.0.1.
    Rules: `limiter` R2"""
    r = req(None)

    key = get_remote_address(r)

    # Then 1
    assert key == "127.0.0.1"


# [claude] LIM-05
def test_lim_05__an_empty_host_gives_the_key_127_0_0_1():
    """LIM-05 — an empty host gives the key 127.0.0.1.
    Rules: `limiter` R2"""
    r = req(("", 5))

    key = get_remote_address(r)

    # Then 1
    assert key == "127.0.0.1"


# [claude] LIM-06
def test_lim_06__an_undecorated_route_answers_every_request():
    """LIM-06 — an undecorated route answers every request.
    Rules: `limiter` R3"""
    c1 = TestClient(build_app())
    for _ in range(5):
        assert c1.get("/free").status_code == 200

    resp = c1.get("/free")

    # Then 1
    assert resp.status_code == 200
    # Then 2
    assert resp.json() == {"ok": True}


# [claude] LIM-07
def test_lim_07__2_minute_2_pass_the_third_is_refused_with_429_and_the_slowapi_body_with_no():
    """LIM-07 — "2/minute": 2 pass, the third is refused with 429 and the slowapi body, with no rate-limit headers.
    Rules: `limiter` R4, R6"""
    c1 = TestClient(build_app())
    first = c1.get("/limited")
    second = c1.get("/limited")

    third = c1.get("/limited")

    # Then 1
    assert first.status_code == 200
    # Then 2
    assert second.status_code == 200
    # Then 3
    assert third.status_code == 429
    # Then 4
    assert third.json() == {"error": "Rate limit exceeded: 2 per 1 minute"}
    # Then 5
    assert [h for h in RL_HEADERS if h in third.headers] == []
    # Then 6
    assert [h for h in RL_HEADERS if h in second.headers] == []


# [claude] LIM-08
def test_lim_08__with_no_429_handler_registered_the_refusal_is_still_a_429_naming_the_limit():
    """LIM-08 — with no 429 handler registered, the refusal is still a 429 naming the limit, and the route does not run.
    Rules: `limiter` R4, Errors row 1"""
    calls = {"limited": 0}
    cn = TestClient(build_app(with_handler=False, calls=calls))
    for _ in range(2):
        assert cn.get("/limited").status_code == 200

    resp = cn.get("/limited")

    # Then 1
    assert resp.status_code == 429
    # Then 2
    assert resp.json() == {"detail": "2 per 1 minute"}
    # Then 3
    assert calls["limited"] == 2


# [claude] LIM-09
def test_lim_09__another_address_has_its_own_counter():
    """LIM-09 — another address has its own counter.
    Rules: `limiter` R4"""
    app = build_app()
    c1 = TestClient(app)
    c5 = TestClient(app, client=("5.5.5.5", 1))
    statuses = [c1.get("/limited").status_code for _ in range(3)]
    assert statuses[2] == 429

    resp = c5.get("/limited")

    # Then 1
    assert resp.status_code == 200


# [claude] LIM-10
def test_lim_10__counters_are_per_path_another_decorated_path_is_not_affected():
    """LIM-10 — counters are per path: another decorated path is not affected.
    Rules: `limiter` R5"""
    c1 = TestClient(build_app())
    statuses = [c1.get("/limited").status_code for _ in range(3)]
    assert statuses[2] == 429

    resp = c1.get("/second")

    # Then 1
    assert resp.status_code == 200


# [claude] LIM-11
def test_lim_11__reset_clears_the_counters():
    """LIM-11 — reset clears the counters.
    Rules: `limiter` R5"""
    c1 = TestClient(build_app())
    statuses = [c1.get("/limited").status_code for _ in range(3)]
    assert statuses[2] == 429

    limiter.reset()

    # Then 1
    assert c1.get("/limited").status_code == 200
