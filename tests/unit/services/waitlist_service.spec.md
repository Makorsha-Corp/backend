# Spec — `app/services/waitlist_service.py`

> **Status:** APPROVED (2026-11-04; nothing open in this spec. OQ-9 in `docs/testing/owner-questions.md` asks the owner about the production setting behind `verify_turnstile` R1; it is not blocking: the code's rule is settled, the question is whether production sets the key.)
> **Source commit:** e48a092

> **Form.** As `tests/unit/services/department_service.spec.md`; the **Transaction contract TC1–TC6 is defined there**. This service has **no manager**: it calls `waitlist_dao` directly and holds the waitlist's rules itself, so its transaction rules are written out per method. Below it: `tests/unit/dao/waitlist.spec.md` (APPROVED), `tests/unit/dao/base.spec.md`.

> **Routed here and written as rules:** waitlist DAO FU-1 (a) HR-1 (BUG-1579); (b) the "email exists after a failed insert" path (`submit_signup` R7, R8: intended, Q2).
>
> **Decided by Claude under the reviewer's delegation (2026-11-04):** P1 (BUG-1580), Q1 (intended), Q2 (intended). House-rule line: BUG-1579. None is the owner's answer; none touches money, stock, an order workflow, or who may see or do what. **Sent to the owner, not blocking:** OQ-9 (is `TURNSTILE_SECRET_KEY` set in production?).
>
> **Verified by running** (`h.py`, `v5_wait.py`, `v6_wait2.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc2\`, one outer transaction rolled back against `marker_test`, session as the `db` fixture; `httpx.AsyncClient` replaced by a stub; nothing persisted): a filled honeypot answers success and stores nothing; a new signup is stored with the email trimmed and lower-cased, names trimmed, a blank company as `NULL`, `source` `waitlist_section`, `status PENDING`, the IP hash equal to `sha256("<salt>:<ip>")`, and survives a later rollback; the same email in other capitals answers success and changes nothing (first name and `wants_product_updates` kept); names of only spaces are stored `""`; `hash_client_ip(None)` and `("")` are `None`; an insert that fails while the email then exists answers success; a failure with a new email is re-raised; `update_status` of an unknown id → 404 `Waitlist signup not found`, of a known one → committed and returned; a 21-character status raises `DataError` and leaves the session needing a rollback; a stored status outside the four makes the whole list raise `ValidationError`; Turnstile: no key → no call; the request carries `secret`, `response` and `remoteip` only when there is an IP; `success: true` passes; `success: false` and a body without `success` → 400; an HTTP 500 and a connect timeout → 502; a body that is not JSON → `ValueError`, a JSON list → `AttributeError` (both 500 at the API). **Not run:** the real Cloudflare endpoint; two concurrent signups (the race was simulated with a patched lookup); the intended behavior of the bug rules.

## Review
> All answered; nothing pending in this spec.

### House-rule violations — applied automatically

- **HR-1** `submit_signup` R4 — first and last names of only spaces pass `WaitlistSignupRequest` (`min_length=1` before trimming), are trimmed by the service and stored `""` (verified). Intended: the schema trims `first_name` and `last_name` and refuses a blank one (422); nothing stored.
**Answer:** bug — per HR-1 (house rule)
**Resolution:** 🐞 BUG-1579 (pattern `blank-name-accepted`; per BUG-915, BUG-1526). Fix in `app/schemas/waitlist.py`. Rules: `submit_signup` R4.

### Precedent matches — accepted (decided by Claude under the reviewer's delegation (2026-11-04))

### P1. An unreadable answer from Turnstile is an internal error — 🐞 BUG-1580
**Background:** Turnstile is Cloudflare's bot check for the public signup form. The service posts the token and reads a JSON object with `success`. Network and HTTP errors become 502 "Could not verify submission". A body that is not JSON, or JSON that is not an object, is not caught. Same root cause as BUG-522 (an undecodable body raised and was not caught).
**What happens today:** a non-JSON body raises `ValueError`, a JSON list `AttributeError`: a 500 (verified with a stub).
**Example:** During a Cloudflare incident the check returns an HTML error page with status 200: signups get "internal server error" instead of "Could not verify submission".
**Rules affected:** `verify_turnstile` R5
**Answer:** bug — per BUG-522 precedent: any answer that cannot be read as a JSON object counts as "could not verify": 502 `Could not verify submission`, nothing stored. The signup is still refused, as today.
**Resolution:** 🐞 BUG-1580 (pattern `uncaught-decode-error`). Rules: `verify_turnstile` R5.

### New questions — answered (decided by Claude under the reviewer's delegation (2026-11-04))

### Q1. Signing up again does not update the earlier signup — ✅ intended
**Background:** The waitlist is public: anyone may submit any email. A second signup with an email already on the list answers the same success message and stores nothing.
**What happens today:** `ann@x.com` signed up without "send me product updates"; signing up again with it ticked changes nothing (verified).
**Example:** Ann ticks "product updates" on her second visit and still gets no updates.
**Rules affected:** `submit_signup` R6
**Answer:** intended — updating would let anyone change another person's entry, or opt them in, by typing their email; and the identical answer keeps the list from revealing who is on it. The admin can change an entry.

### Q2. Any failure on an email that turns out to exist answers success — ✅ intended
**Background:** Two signups with one email at once can both pass the "already on the list?" check; the second insert then fails on the unique email. The service rolls back, looks again, and answers success when the email is now there (waitlist DAO FU-1 (b)).
**What happens today:** any exception from the insert or the commit, not only the unique violation, answers success when the email exists afterwards (verified with a patched lookup); with a new email it is re-raised (verified).
**Example:** Two clicks on "Join" send two requests; both answer "You're on the list".
**Rules affected:** `submit_signup` R7, R8
**Answer:** intended — the email can only exist afterwards if a signup for it is stored, which is what the user asked for; any other error with a new email is still raised.

Reached through the DAO and cited, one pass-through case each, as `tests/unit/dao/waitlist.cases.md` marks them: BUG-1410 (strict), BUG-1411 (non-strict).

Checked and **not** violated: **HR-2** — the email is unique in the database and every write and lookup uses the trimmed, lower-cased email, so it is unique ignoring case. **HR-3** — `source` is a fixed list. **HR-4** — no soft delete. **HR-5** — filters before `count()` and paging (DAO). **HR-6, HR-8** — the DAO's. **HR-7** — `GET /waitlist` requires `1 <= limit <= 500`. **HR-9** — no audit columns. **HR-10** — `update_status` is a plain overwrite by an admin. **HR-11, HR-12** — the Turnstile result is verified server-to-server and an unverifiable one refuses (R4, BUG-1580). **HR-13** — the bot check starts no business process; a refused signup leaves no row, by design. **HR-16** — platform data, not workspace-scoped.

**Permission checks:** none in the service. `POST /waitlist` is public, limited to 5 requests a minute per client address (`app/core/limiter.py`, OQ-7); `GET /waitlist` and `PATCH /waitlist/{id}/status` require the waitlist admin allowlist (`get_waitlist_admin`).

## Overview
`WaitlistService` runs the landing page's waitlist: it checks the Turnstile bot token, stores a signup once per email (quietly ignoring bots caught by a hidden "website" field, and repeats), and lets waitlist admins list signups and set their follow-up status. It calls `waitlist_dao` and Cloudflare's Turnstile API, and commits itself. The public answer is always the same success message, so the form never reveals whether an email is already on the list.

**Callables:** 6 specified · 1 not specified
**Externals to mock:** `httpx.AsyncClient` in `app.services.waitlist_service` (Turnstile); `settings.TURNSTILE_SECRET_KEY`, `settings.WAITLIST_IP_HASH_SALT`, `settings.SECRET_KEY` (patch attributes on `app.core.config.settings`).
**Integration-only behavior:** the endpoint order (Turnstile first, then the signup); the rate limit; `get_waitlist_admin`; schema validation (`WaitlistSignupRequest`, `WaitlistStatusUpdateRequest`; 400 today, BUG-461); `limit`, `skip`, `search` bounds.

**Facts for the test designer**
- Import: `from app.services.waitlist_service import WaitlistService, waitlist_service, normalize_waitlist_email, hash_client_ip, TURNSTILE_VERIFY_URL, SUCCESS_MESSAGE`. `TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"`; `SUCCESS_MESSAGE = "You're on the list — we'll be in touch."` (an em dash). `verify_turnstile` is `async`. Every parameter after `db` (and after `self` for `verify_turnstile`: `token`, `remote_ip` positional) is keyword-only.
- `WaitlistSignupRequest`: `first_name`, `last_name` 1–100; `company_name` ≤ 200 or `None`; `email` (`EmailStr`); `wants_product_updates` default `False`; `turnstile_token` ≥ 1; `source` one of `waitlist_section`, `hero`, `pricing`, `nav`, `unknown` or `None`, default `waitlist_section`; `website` (the honeypot) default `None`. `WaitlistSignupResponse` = `ok` (`True`), `message`. `WaitlistSignupItem` = `id`, `first_name`, `last_name`, `company_name`, `email`, `wants_product_updates`, `source`, `status` (one of `PENDING`, `CONTACTED`, `ACCEPTED`, `DECLINED`), `created_at`.
- Table facts: waitlist DAO spec, **Model facts**. The table is shared and not scoped: give every email a unique suffix.

**Notes for the test designer**
- **Committed vs not:** after a call that commits, `db.rollback()` in the test and re-select (as `department_service.spec.md` Notes). `submit_signup`'s rollback discards uncommitted rows of the session; commit setup rows first.
- **Turnstile stub:** replace `app.services.waitlist_service.httpx.AsyncClient` with a class whose instances are async context managers with an `async post(url, data=...)` returning an object with `raise_for_status()` and `json()`; record `url` and `data`. Raise `httpx.ConnectTimeout` / `httpx.HTTPStatusError` for the 502 cases. Run with `asyncio.run(...)` or `pytest.mark.anyio` as the project does.
- **Race (R7):** patch `waitlist_dao.get_by_email` so the first call returns `None` and later calls the real method, with the row committed beforehand.
- **BUG-1579:** assert `pydantic.ValidationError` building `WaitlistSignupRequest` → strict xfail. **BUG-1580:** the stub's `json()` raises `ValueError` / returns `[1]` → strict xfail.

## Not specified
- `waitlist_service` — module-level singleton, no logic.

---

## `normalize_waitlist_email(email)`
**Shape:** mapper
**Persistence:** pure
**Visibility:** internal (used by: `submit_signup`)

**Rules:**
- **R1.** Returns the text with surrounding whitespace removed and lower-cased: `"  A@B.C "` → `"a@b.c"` (verified).

**Errors:** none. **Side effects:** none

---

## `hash_client_ip(ip)`
**Shape:** mapper
**Persistence:** pure
**Visibility:** internal (used by: `submit_signup`)

**Rules:**
- **R1.** `None` or `""` → `None` (verified).
- **R2.** Otherwise the lower-case hex SHA-256 of `"<salt>:<ip>"`, 64 characters, where `<salt>` is `settings.WAITLIST_IP_HASH_SALT`, or `settings.SECRET_KEY` when the salt is empty (verified). The same IP and salt always give the same hash; the IP is not stored.

**Errors:** none. **Side effects:** none

---

## `WaitlistService.verify_turnstile(token, remote_ip)` (async)
**Shape:** validator
**Persistence:** pure (external call)
**Visibility:** public (used by: `POST /waitlist`, before `submit_signup`)

**Purpose:** Refuse a signup that Cloudflare does not confirm as human.

**Returns:** `None` when the signup may go on.

**Rules:**
- **R1.** With `settings.TURNSTILE_SECRET_KEY` empty, nothing is checked and no request is sent (verified). (OQ-9: whether production sets the key.)
- **R2.** Otherwise one `POST` to `TURNSTILE_VERIFY_URL` with form data `secret` = the key, `response` = `token`, and `remoteip` = `remote_ip` only when it is truthy (verified both ways); timeout 10 seconds.
- **R3.** An answer with `"success": true` (truthy) → `None` (verified).
- **R4.** `"success"` false or missing → `HTTPException` 400 `Verification failed — please try again` (verified).
- **R5.** Any `httpx.HTTPError` — a network error, a timeout, or an HTTP error status (`raise_for_status`) — → `HTTPException` 502 `Could not verify submission` (verified for 500 and a connect timeout). [BUG-1580] (P1) An answer that is not a JSON object (not JSON, a list, a string) → the same 502. *(Today: `ValueError` / `AttributeError`, a 500. Verified.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not confirmed | `HTTPException` 400 | `Verification failed — please try again` |
| network / HTTP error; [BUG-1580] unreadable answer | `HTTPException` 502 | `Could not verify submission` |

**Side effects:** one request to Cloudflare (none without a key).

---

## `WaitlistService.submit_signup(db, *, payload, remote_ip, skip_turnstile=False)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `POST /waitlist`, after `verify_turnstile`; `skip_turnstile` is never passed and changes nothing)

**Purpose:** Put an email on the waitlist once.

**Returns:** `WaitlistSignupResponse(ok=True, message=SUCCESS_MESSAGE)` on every path that does not raise.

**Rules:**
- **R1.** A truthy `website` (the honeypot) → the success answer; nothing is read or stored (verified). `""` and `None` are not caught.
- **R2.** The email is `normalize_waitlist_email(str(payload.email))`; every lookup and the insert use it.
- **R3.** A new email is stored (DAO `create_signup`) with: that email; `first_name`, `last_name` trimmed; `company_name` trimmed, and `None` when missing or blank; `wants_product_updates` and `source` as sent (`source: null` stored `NULL`); `ip_hash = hash_client_ip(remote_ip)`; `status PENDING`. It is committed: it survives a later rollback (verified).
- **R4.** [BUG-1579] (HR-1) A first or last name of only whitespace is refused by `WaitlistSignupRequest` (422) and nothing is stored. *(Today: stored `""`. Verified.)*
- **R5.** `skip_turnstile` has no effect (Turnstile is the endpoint's call).
- **R6.** ✅ (Q1) An email already on the list (in any capitals, with any spaces) → the success answer; the stored signup is not changed (verified: name and `wants_product_updates` kept).
- **R7.** ✅ (Q2) If the insert or the commit raises, the session is rolled back (all its pending changes discarded), the email is looked up again, and if it is now on the list the success answer is returned (verified with a simulated race).
- **R8.** If it is still not on the list, the original exception reaches the caller unchanged (verified). A commit that raises is rolled back first (TC4).

**Errors:** R8 (e.g. `DataError` for a value longer than its column when called directly; the schema's limits prevent it through the API).

**Side effects:** at most one `waitlist_signups` row, committed.

---

## `WaitlistService.update_status(db, *, signup_id, status_value)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `PATCH /waitlist/{id}/status`, waitlist admins; the schema allows only `PENDING`, `CONTACTED`, `ACCEPTED`, `DECLINED`)

**Purpose:** Set a signup's follow-up status.

**Returns:** a `WaitlistSignupItem` of the signup after the commit.

**Rules:**
- **R1.** Unknown id → `HTTPException` 404 `Waitlist signup not found`; nothing written (verified).
- **R2.** Otherwise `status` = `status_value` (DAO `update_status` R1: nothing else changes; the same status again is accepted) and the change is committed (verified: survives a later rollback); the answer reflects the stored row. A signup whose stored status is outside the four can be set to one of them (verified).
- **R3.** A failing commit is rolled back and re-raised (TC4). A failure at the flush (a status over 20 characters, only when called directly) reaches the caller **without** a rollback: the session must be rolled back before it is used again (verified: `PendingRollbackError`). Unreachable through the API.

**Errors:** R1; `DataError` for R3.

**Side effects:** one row's `status`, committed.

---

## `WaitlistService.list_signups(db, *, skip, limit, search, wants_product_updates, status_value=None)`
**Shape:** search
**Persistence:** reads
**Visibility:** public (used by: `GET /waitlist`, waitlist admins, with every argument)

**Purpose:** One page of signups with the total.

**Returns:** `WaitlistSignupListResponse(items, total, skip, limit)`.

**Rules:**
- **R1.** `items` and `total` are DAO `list_signups` for these arguments (`status_value` passed as `status`; its R1–R7, BUG-1410, BUG-1411); `skip` and `limit` in the answer are the arguments. Verified.
- **R2.** A stored status outside the four allowed values makes the whole call raise `pydantic.ValidationError` (verified). No path of this service stores one; not tested beyond one case.
- **R3.** Read only (TC6).

**Errors:** R2; `DataError` for negative `skip` / `limit` when called directly.

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 25–26 | strip, lower | `normalize_waitlist_email` R1 |
| 29–30 | `not ip` → `None` | `hash_client_ip` R1 |
| 31–33 | salt or `SECRET_KEY`; SHA-256 hex | `hash_client_ip` R2 |
| 39–44 | no key → return | `verify_turnstile` R1 |
| 46–48 | payload; `remoteip` only if truthy | `verify_turnstile` R2 |
| 50–59 | post, `raise_for_status`, `json()`; `httpx.HTTPError` → 502; JSON errors uncaught (BUG-1580) | `verify_turnstile` R5 |
| 61–65 | `not result.get("success")` → 400 | `verify_turnstile` R3, R4 |
| 75–76 | honeypot truthy → success | `submit_signup` R1 |
| 78 | normalise email | `submit_signup` R2 |
| 79–80 | email exists → success | `submit_signup` R6 |
| 82–93 | create (trim names, blank company → `None`, hash IP) → commit | `submit_signup` R3, R4 |
| 94–99 | any exception → rollback; exists → success; else re-raise | `submit_signup` R7, R8 |
| 101 | success | `submit_signup` R3 |
| 104–109 | `get`; `None` → 404 | `update_status` R1 |
| 110–112 | DAO update (no `try`); commit; item | `update_status` R2, R3 |
| 124–137 | DAO list; response | `list_signups` R1–R3 |
| 140 | module singleton | Not specified |
