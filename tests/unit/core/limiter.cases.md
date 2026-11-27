# Test cases — `app/core/limiter.py`

> **Spec:** `tests/unit/core/limiter.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-03; nothing open). P1 and Q1 were decided by Claude under the reviewer's delegation.
> **Revision:** 2 — spec Gap log G1 (R4, Errors row 1 rewritten: the refusal is a 429 whose body depends on the registered handler; the route does not run). LIM-08 now expects a 429 `{"detail": "2 per 1 minute"}` from the app without slowapi's handler and checks the route ran only twice; `RateLimitExceeded` no longer escapes. No new card, no ID retired.
> **Revision:** 3 — two Then lines added to LIM-01: `not lim._key_prefix` (spec Gap log G2: the value is `None`, never compare with `""`) and `lim._swallow_errors is False`. Spec gap 2 closed. No new card.
> **Counts:** 11 cases · 11 expected-to-pass · 0 expected-to-fail (bugs) · 3 deferred

## Reviewer summary
- **Per callable:** `limiter` 11 (no bug).
- **Depth:** lighter target (skill step 1a). One configuration object, no data, no stock, money or order state. The source is one constructor line, so the card count is above the one-per-two-lines guide: each rule and the Errors row still needs its own card, and none is multiplied by value.
- **Notable design choices:**
  - No database. Limiting is seen through a minimal FastAPI app built per test, as the spec's Notes direct; `app.main.app` is never started.
  - `limiter.reset()` runs before and after every test (the object is shared by the whole session).
  - The fixed one-minute window (R4) is not crossed: that needs control of the library's clock, which the spec gives no recipe for (Spec gap 1). Only "N pass, N + 1 refused within the window" is tested.
  - R5's "no key prefix" is asserted as `not lim._key_prefix` (the value is `None`, spec Gap log G2) and R7's "storage errors are not swallowed" as `lim._swallow_errors is False` (LIM-01).
- **Needs a decision:** None blocking. See Spec gap 1.

## Conventions for this module

**IDs.** `LIM` = `app/core/limiter.py`. One callable; ids `LIM-NN`.

**Names.**
- `limiter` = `from app.core.limiter import limiter`. `get_remote_address` = `slowapi.util.get_remote_address`. `RateLimitExceeded` = `slowapi.errors.RateLimitExceeded`. `_rate_limit_exceeded_handler` = `slowapi._rate_limit_exceeded_handler`. `SlowAPIMiddleware` = `slowapi.middleware.SlowAPIMiddleware`. `MemoryStorage` = `limits.storage.MemoryStorage`. `FixedWindowRateLimiter` = `limits.strategies.FixedWindowRateLimiter`. `Request` = `starlette.requests.Request`. `TestClient` = `fastapi.testclient.TestClient`.
- Every test calls `limiter.reset()` first and last (also when it fails). No database session is used. Tests run from the repository root.

**APP** = a fresh `FastAPI()` built in the test, with:
- `app.state.limiter = limiter`, `app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)`, `app.add_middleware(SlowAPIMiddleware)`;
- `GET /limited` decorated `@limiter.limit("2/minute")`, function takes `request: Request`, adds 1 to `CALLS["limited"]` and returns `{"ok": True}`;
- `GET /second` decorated `@limiter.limit("2/minute")`, function takes `request: Request`, returns `{"ok": True}`;
- `GET /free`, not decorated, returns `{"ok": True}`.

**APP_NO_HANDLER** = APP, but without the `add_exception_handler` line.

**CALLS** = a dict `{"limited": 0}` created fresh in each test before the app is built; the `/limited` route counts its runs in it.

**Clients.** `C1 = TestClient(APP)` (client address `testclient`). `C5 = TestClient(APP, client=("5.5.5.5", 1))`. A card says which app a client is built on when it is not APP.

**req(client)** = `starlette.requests.Request({"type": "http", "method": "GET", "path": "/", "headers": [], "client": client})`; a card may add raw header pairs to `headers`.

**RL_HEADERS** = `["retry-after", "x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset"]`.

**Externals.** None. Nothing is mocked. **Race simulations.** None.

## `limiter`

### LIM-01 — the singleton's settings
- **Rules:** `limiter` R1, R3, R5, R6, R7 (incl. no key prefix, storage errors not swallowed)
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond Conventions.

**When**
- `lim = limiter`.

**Then**
1. returns: `lim._key_func is get_remote_address`.
2. returns: `lim.enabled is True`.
3. returns: `lim._headers_enabled is False`.
4. returns: `isinstance(lim._storage, MemoryStorage)`.
5. returns: `isinstance(lim._limiter, FixedWindowRateLimiter)`.
6. returns: `lim._key_style == "url"`.
7. returns: `list(lim._default_limits) == []`.
8. returns: `list(lim._application_limits) == []`.
9. returns: `not lim._key_prefix` (no key prefix; the value is `None` from the repository root, so never compare with `""`).
10. returns: `lim._swallow_errors is False`.

### LIM-02 — the key is the connecting address; X-Forwarded-For and X-Real-IP are ignored
- **Rules:** `limiter` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. `r = req(("1.2.3.4", 5))`, with headers `[(b"x-forwarded-for", b"9.9.9.9"), (b"x-real-ip", b"8.8.8.8")]`.

**When**
- `key = get_remote_address(r)`.

**Then**
1. returns: `key == "1.2.3.4"`.

### LIM-03 — two requests with different X-Forwarded-For share one counter
- **Rules:** `limiter` R1, R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. `C1.get("/limited", headers={"X-Forwarded-For": "10.0.0.1"})` returns 200.
2. `C1.get("/limited", headers={"X-Forwarded-For": "10.0.0.2"})` returns 200.

**When**
- `resp = C1.get("/limited", headers={"X-Forwarded-For": "10.0.0.3"})`.

**Then**
1. returns: `resp.status_code == 429`.

### LIM-04 — no client gives the key 127.0.0.1
- **Rules:** `limiter` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `r = req(None)`.

**When**
- `key = get_remote_address(r)`.

**Then**
1. returns: `key == "127.0.0.1"`.

### LIM-05 — an empty host gives the key 127.0.0.1
- **Rules:** `limiter` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `r = req(("", 5))`.

**When**
- `key = get_remote_address(r)`.

**Then**
1. returns: `key == "127.0.0.1"`.

### LIM-06 — an undecorated route answers every request
- **Rules:** `limiter` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `C1.get("/free")` called 5 times, each returns 200.

**When**
- `resp = C1.get("/free")`.

**Then**
1. returns: `resp.status_code == 200`.
2. returns: `resp.json() == {"ok": True}`.

### LIM-07 — "2/minute": 2 pass, the third is refused with 429 and the slowapi body, with no rate-limit headers
- **Rules:** `limiter` R4, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `first = C1.get("/limited")`.
2. `second = C1.get("/limited")`.

**When**
- `third = C1.get("/limited")`.

**Then**
1. returns: `first.status_code == 200`.
2. returns: `second.status_code == 200`.
3. returns: `third.status_code == 429`.
4. returns: `third.json() == {"error": "Rate limit exceeded: 2 per 1 minute"}`.
5. returns: `[h for h in RL_HEADERS if h in third.headers] == []`.
6. returns: `[h for h in RL_HEADERS if h in second.headers] == []`.

### LIM-08 — with no 429 handler registered, the refusal is still a 429 naming the limit, and the route does not run
- **Rules:** `limiter` R4, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. `CN = TestClient(APP_NO_HANDLER)` (default `raise_server_exceptions=True`).
2. `CN.get("/limited")` called 2 times, each returns 200.

**When**
- `resp = CN.get("/limited")`.

**Then**
1. returns: `resp.status_code == 429`.
2. returns: `resp.json() == {"detail": "2 per 1 minute"}`.
3. returns: `CALLS["limited"] == 2`.

### LIM-09 — another address has its own counter
- **Rules:** `limiter` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. `C1.get("/limited")` called 3 times; the third returns 429.

**When**
- `resp = C5.get("/limited")`.

**Then**
1. returns: `resp.status_code == 200`.

### LIM-10 — counters are per path: another decorated path is not affected
- **Rules:** `limiter` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. `C1.get("/limited")` called 3 times; the third returns 429.

**When**
- `resp = C1.get("/second")`.

**Then**
1. returns: `resp.status_code == 200`.

### LIM-11 — reset clears the counters
- **Rules:** `limiter` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. `C1.get("/limited")` called 3 times; the third returns 429.

**When**
- `limiter.reset()`.

**Then**
1. returns: `C1.get("/limited").status_code == 200`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| FU-1 — the 429 body produced by the handler registered in `app/main.py` and whether it should use the problem-details shape | `app/main.py` spec (not yet described) / integration tests | Here the body is checked only on the minimal app (LIM-07). |
| Which endpoints carry which limit (Overview) | endpoint specs (auth, mobile upload, payments, waitlist) / integration tests | No card here. |
| FU-2 / OQ-7 — proxy trust and per-process counters in production | deployment (`scripts/railway_start.sh`), owner question OQ-7 | Not a unit test. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `limiter` R4 ("one fixed one-minute window") | No way is given to move the library's clock (the spec lists no external to mock). | The window's end is not crossed; only N pass / N + 1 refused inside one window (LIM-07). |
| 2 | `limiter` R5 ("no key prefix"), R7 ("errors of the storage are not swallowed") | *Closed in revision 3:* the attributes are `_key_prefix` (falsy, `None` from the repository root; spec G2) and `_swallow_errors`. | LIM-01 Then 9, 10. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `limiter` | R1 | LIM-01, LIM-02, LIM-03 |
| `limiter` | R2 | LIM-04, LIM-05 |
| `limiter` | R3 | LIM-01, LIM-06 |
| `limiter` | R4 | LIM-03, LIM-07, LIM-08, LIM-09 |
| `limiter` | R5 | LIM-01, LIM-10, LIM-11 |
| `limiter` | R6 | LIM-01, LIM-07 |
| `limiter` | R7 | LIM-01 |
| `limiter` | Errors row 1 | LIM-08 |
