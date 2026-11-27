# Spec — `app/core/limiter.py`

> **Status:** APPROVED (2026-11-03; nothing open in this spec)
> **Source commit:** e48a092

> **Review round 2026-11-03.** No owner answer in this round. **Delegated:** P1 and Q1 decided by Claude under the reviewer's delegation (2026-11-03). Neither is the owner's own answer. The deployment check found while describing P1 is parked for the owner as **OQ-7** in `docs/testing/owner-questions.md` (not blocking: it is a fact about the production server, not a rule of this module).
>
> **Verified by running** (throwaway script `v_core.py` with the harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\acctdao\`; no database write): the singleton's settings (key function, enabled, headers off, in-memory storage, fixed-window strategy, `url` key style, no default or application limits, no key prefix); `get_remote_address` with a client, with no client and with an empty host; a minimal FastAPI app using this singleton with a `2/minute` route: 200, 200, 429; the 429 body and headers; an `X-Forwarded-For` header does not change the key; an undecorated route is never limited; another client address has its own counter; `limiter.reset()` clears the counters. The repository's `.env` has no `RATELIMIT_*` key. **Read, not run:** `app/main.py` (registration), the 13 decorated endpoints, `scripts/railway_start.sh`. **Not run:** the real app, anything behind a proxy.

## Review
> All answered; applied 2026-11-03.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | Requests are counted per address of whoever connects to the server; a forwarded-for header is ignored | intended — per the audit-logger decision: the client address is what the server's trusted-proxy handling gives, never a raw header. Whether production is set up so this is the real user's address is OQ-7 (owner, not blocking) | Claude, delegated |
| Q1 | A refused request is not told when it may try again (no `Retry-After`, no rate-limit headers) | intended — limits are per minute and the screens show a fixed message | Claude, delegated |

No house rule applies: this module has no data, names, lists or money. **HR-16** — the key holds no workspace data.

### P1. The rate limit counts per connecting address — ✅ intended
**Background:** Login (10/minute), registration and forgot-password (5/minute), invitation check, waitlist sign-up, the public phone-upload pages and the payment-gateway callbacks are rate-limited with this object. The counter is kept per "key" and per request path. The key is the address of the machine that opened the connection to the server. When the app sits behind a proxy, that machine is the proxy, unless the server is told to trust the proxy's `X-Forwarded-For` header (uvicorn `--forwarded-allow-ips`). The audit-logger spec already decided which address counts as "the client": the one the server's trusted-proxy handling gives, never a raw, client-supplied `X-Forwarded-For` (audit logger Q1, best-practice default, delegated by reviewer).
**What happens today:** The key is `request.client.host`; a request with no client address uses `127.0.0.1`. `X-Forwarded-For` sent by the caller changes nothing. (Verified.)
**Example:** A user sends 11 logins in a minute, each with a different made-up `X-Forwarded-For`: the 11th is refused with 429. If the server is behind a proxy it does not trust, every user arrives from the proxy's address and they all share one login counter: the 11th login of the whole company in that minute is refused.
**Rules affected:** `limiter` R1, R2
**Answer:** intended — per audit logger Q1 precedent; the module is right to key on the address the server resolves. Production's proxy trust is a deployment matter: parked as OQ-7.
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): rules unchanged (R1 ✅, R2 ✅). OQ-7 added to `docs/testing/owner-questions.md` (not blocking).

### Q1. A refused request is not told when it may retry — ✅ intended
**Background:** Some APIs send `Retry-After` (seconds until the window resets) and `X-RateLimit-*` headers. This limiter is built with headers switched off. Switching them on in this library also requires every limited endpoint to take a `response` parameter, or it fails.
**What happens today:** No response carries `Retry-After` or `X-RateLimit-*`, including the 429. (Verified.)
**Example:** A user locked out of login for a minute sees "Rate limit exceeded: 10 per 1 minute" and does not know when the minute ends; at most 60 seconds.
**Rules affected:** `limiter` R6
**Suggested answer:** intended — every limit is per minute; the wait is short and the message names the limit.
**Answer:** intended
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): rule unchanged (R6 ✅).

## Follow-ups for other reviews
> Nothing below is a rule of this module and no bug is logged for it here.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **`app/main.py`** (not yet described) | The 429 is produced by slowapi's own `_rate_limit_exceeded_handler`: body `{"error": "Rate limit exceeded: 2 per 1 minute"}`, `Content-Type: application/json`, no `request_id`, not the problem-details shape every other error uses (exceptions spec). Whether it should be. | Verified run |
| FU-2 | **Deployment** (`scripts/railway_start.sh`) — OQ-7 | `uvicorn` is started without `--forwarded-allow-ips`; uvicorn then trusts `X-Forwarded-For` only from `127.0.0.1` (or the `FORWARDED_ALLOW_IPS` environment variable, not visible in the repository). Counters are in memory: per process, lost on restart, not shared between replicas. | P1 |

## Overview
`app/core/limiter.py` builds the one shared slowapi `Limiter` used by the whole app. `app/main.py` stores it as `app.state.limiter`, registers slowapi's 429 handler and adds `SlowAPIMiddleware`; endpoints apply limits with `@limiter.limit("N/minute")` (auth: register 5, login 10, forgot-password 5, validate-invitation 20; mobile upload: create session 10, public session 30, public sign 20, public confirm 20; payments: success / fail / cancel 30, IPN 60; waitlist join 5). The module holds no logic of its own beyond this configuration; it protects public endpoints from floods and guessing.

**Callables:** 1 specified (the `limiter` object) · 0 not specified
**Externals to mock:** none. Counters are in process memory: call `limiter.reset()` before and after each case (the object is shared by the whole test session).
**Integration-only behavior:** which endpoints carry which limit and the 429 body produced by the handler registered in `app/main.py` (FU-1).

**Notes for the test designer:**
- Import the singleton: `from app.core.limiter import limiter`. Library: slowapi 0.1.10 (`slowapi.util.get_remote_address`).
- To see limiting work, build a **minimal** `FastAPI()` app: `app.state.limiter = limiter`, `app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)`, `app.add_middleware(SlowAPIMiddleware)`, and a route decorated `@limiter.limit("2/minute")` whose function takes `request: Request`. Use `TestClient`; its client address is `testclient`. `TestClient(app, client=("5.5.5.5", 1))` gives another address. Never start `app.main.app`.
- `get_remote_address` can be called on a `starlette.requests.Request` built from a scope (`"client": ("1.2.3.4", 5)` or `None`).
- Limiter settings are private attributes of slowapi: `limiter._key_func`, `limiter.enabled`, `limiter._headers_enabled`, `limiter._storage` (`limits.storage.MemoryStorage`), `limiter._limiter` (`limits.strategies.FixedWindowRateLimiter`), `limiter._key_style`, `limiter._default_limits`, `limiter._application_limits`. R5's "no key prefix" is seen as `not limiter._key_prefix`: run from the repository root on slowapi 0.1.10 the value is `None`, not `""` (verified 2026-11-03; slowapi replaces the constructor's `""` with the `.env` lookup result, which is `None` when the key is absent), so assert falsiness, never `== ""`. R7's "storage errors are not swallowed" is seen as `limiter._swallow_errors is False` (verified).
- The library reads `RATELIMIT_*` keys from a `.env` file in the **current working directory** at import (R7). Run tests from the repository root; the repository `.env` has none.

---

## `limiter` (module-level `Limiter` instance)
**Shape:** helper (configuration object)
**Persistence:** pure (in-process counters only)
**Visibility:** public (used by: `app/main.py`; the decorators in `app/api/v1/endpoints/auth.py`, `mobile_upload.py`, `payments.py`, `waitlist.py`)

**Purpose:** Count requests per caller and refuse those over a route's limit.

**Rules:**
- **R1.** ✅ (P1) The key of a request is its connecting address, `request.client.host`, through `slowapi.util.get_remote_address`. Request headers (`X-Forwarded-For`, `X-Real-IP`) do not change it: 2 requests from one address with different `X-Forwarded-For` values share one counter.
- **R2.** ✅ (P1) A request with no client, or with an empty host, gets the key `127.0.0.1`; all such requests share one counter.
- **R3.** Only routes decorated with `@limiter.limit(...)` are limited: there are no default or application-wide limits, so an undecorated route answers every request.
- **R4.** A decorated route with "N/minute" accepts N requests per key and path in one fixed one-minute window; request N + 1 in that window is refused with HTTP 429 and the route function does not run. Another key has its own counter. The 429 body depends on the handler the app registers, not on this module: with slowapi's `_rate_limit_exceeded_handler` (as `app/main.py` does) it is `{"error": "Rate limit exceeded: 2 per 1 minute"}`; with no handler registered, `RateLimitExceeded` (an `HTTPException` subclass) does not escape the request — FastAPI's own handler answers 429 `{"detail": "2 per 1 minute"}` (verified both).
- **R5.** Counters are per request path (`key_style="url"`; no key prefix), held in process memory (`memory://`): `limiter.reset()` clears them, and they are not shared between processes.
- **R6.** ✅ (Q1) Headers are off: no response, including the 429, carries `Retry-After`, `X-RateLimit-Limit`, `X-RateLimit-Remaining` or `X-RateLimit-Reset`.
- **R7.** The limiter is enabled, errors of the storage are not swallowed, and settings come from the constructor plus `RATELIMIT_*` keys of a `.env` file in the working directory, read once at import; with the repository `.env` (none set) the values of R1–R6 hold.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| more than N requests of one key on one path in the window | `slowapi.errors.RateLimitExceeded` inside the request, turned into HTTP 429 by whichever handler the app has (R4); a test client sees the 429, never the exception | with slowapi's handler `{"error": "Rate limit exceeded: 2 per 1 minute"}`; with none, `{"detail": "2 per 1 minute"}` |

**Side effects:** in-memory counter per key and path.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 5 | `key_func=get_remote_address` | R1 |
| slowapi `get_remote_address` | no client or empty host → `127.0.0.1` / host | R1, R2 |
| 5 (constructor defaults) | `default_limits=[]`, `application_limits=[]` | R3 |
| slowapi `__evaluate_limits` | counter under limit → pass / over → raise | R4 |
| 5 (defaults) | `key_style="url"`, `storage_uri=None` → `memory://`, strategy fixed-window | R4, R5 |
| 5 (defaults) | `headers_enabled=False` | R6 |
| slowapi `Limiter.__init__` | `.env` present → read `RATELIMIT_*`; `enabled=True` | R7 |

## Gap log
- G1 (`limiter.notes.md` discrepancy, executor 2026-11-03) — Fact — re-verified (`v_gaps.py`): with no 429 handler registered, `RateLimitExceeded` does not escape the request; FastAPI answers 429 `{"detail": "2 per 1 minute"}`. R4 and Errors row 1 rewritten: the refusal is a 429 whose body depends on the registered handler; both bodies stated. No question, status unchanged.
- G2 (`limiter.cases.md` spec gap 2, verifier finding) — Fact — Notes name how R5 and R7 are observed. Re-verified: `limiter._swallow_errors is False`; `limiter._key_prefix` is `None` from the repository root (not `""` as reported), so the Note says to assert falsiness. Status unchanged.
