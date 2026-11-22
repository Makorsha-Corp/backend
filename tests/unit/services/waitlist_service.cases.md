# Test cases — `app/services/waitlist_service.py`

> **Spec:** `tests/unit/services/waitlist_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Counts:** 35 cases · 30 expected-to-pass · 5 expected-to-fail (bugs) · 6 deferred
> **Revision:** 2 (2026-11-04) — no spec change. Verifier Finding 1 / mutant #2 (`waitlist_service.verify.md`): WSV-S-01 Then 2 now asserts the literal success text from the spec's Facts, `"You're on the list — we'll be in touch."`, instead of the module's `SUCCESS_MESSAGE` constant. No card added, none retired.

## Reviewer summary
- **Per callable:** `normalize_waitlist_email` 1 · `hash_client_ip` 4 · `verify_turnstile` 9 (2 bug) · `submit_signup` 9 (1 bug) · `update_status` 5 · `list_signups` 7 (2 bug).
- **Depth:** lighter target (skill step 1a): platform data, no stock, money or order state, and no manager. The service's own rules (honeypot, normalising, the once-per-email answer, the race path, the Turnstile answers) each get one card per rule and per answer shape; the DAO's filters are not re-tested beyond one card per argument passed on, plus one pass-through card per DAO bug (BUG-1410 strict, BUG-1411 non-strict, as `dao/waitlist.cases.md`).
- **Notable design choices:**
  - Turnstile is replaced by a stub class (Conventions); every `verify_turnstile` card runs the coroutine with `asyncio.run`.
  - `WAITLIST_IP_HASH_SALT` is patched to `"pepper"` in every `submit_signup` card so the stored `ip_hash` is a literal.
  - **Race simulation** S-06 (R7) patches `waitlist_dao.get_by_email` so its first call answers `None`, as the spec's Notes prescribe.
  - S-01 checks the success text as a literal from the spec; the other cards compare with `SUCCESS_MESSAGE`, so a changed public text fails S-01 only.
  - S-07 reaches R8 (a failure with a new email is re-raised) through a failing commit, which is also the TC4 case.
  - The table is shared and not scoped: every email carries a per-test `TAG`, and list cards search for it.
  - `update_status`'s 20-character side of the status length is not reachable through the service (the answer would fail the four-value schema); the DAO's cards hold that boundary.
- **Needs a decision:** gap 1 (where the 10-second timeout is passed). No card rests on it; the timeout is not asserted.

## Conventions for this module

**IDs.** `WSV` = `app/services/waitlist_service.py`. `N` normalize_waitlist_email · `H` hash_client_ip · `T` verify_turnstile · `S` submit_signup · `U` update_status · `L` list_signups.

**Actors and fixed values.**
- `svc` = the singleton `waitlist_service`; `from app.services.waitlist_service import WaitlistService, waitlist_service, normalize_waitlist_email, hash_client_ip, TURNSTILE_VERIFY_URL, SUCCESS_MESSAGE`. `db` = the test's real session, always the first argument; every other argument by keyword (`verify_turnstile` takes `token`, `remote_ip` by keyword too). `result` = what the When call returns.
- `WaitlistSignup` (`app.models.waitlist_signup`), `waitlist_dao` (`app.dao.waitlist`), `WaitlistSignupRequest`, `WaitlistSignupItem` (`app.schemas.waitlist`), `settings` (`app.core.config`), `HTTPException` (`fastapi`), `PydanticValidationError` = `pydantic.ValidationError`, `DataError`, `PendingRollbackError` (`sqlalchemy.exc`), `text` (`sqlalchemy`), `patch` (`unittest.mock`), `httpx`, `asyncio`.
- TAG = `uuid.uuid4().hex[:10]`, once per test. IP = `"203.0.113.7"`. T1, T2, T3 = `datetime(2026, 3, 1, 9, 0, 0, tzinfo=timezone.utc)`, `… 3, 2 …`, `… 3, 3 …` (same time, days 1, 2, 3).
- H_PEPPER = `"e0dc27fa1b25a23ba014e36d2a1f1f84450214ba108029b8c207dfaeb0e046f4"` (SHA-256 of `"pepper:203.0.113.7"`). H_SEKRIT = `"1fce02c50e4d38a3e4015d6ff683713903f589a12a67afffe499b5814f841882"` (SHA-256 of `"sekrit:203.0.113.7"`).

**Externals.**
- **salt pepper** = `patch.object(settings, "WAITLIST_IP_HASH_SALT", "pepper")`, active in every `S-` card and named in `H-` cards.
- **key set** = `patch.object(settings, "TURNSTILE_SECRET_KEY", "sk-test")`; **no key** = the same with `""`.
- **stub(…)** = `patch("app.services.waitlist_service.httpx.AsyncClient", Stub)` where `Stub(*a, **kw)` is an async context manager whose `async post(url, data=None, **kw)` appends `(url, data)` to the list `posts` and then: with **error E at post**, raises E; else returns a response whose `raise_for_status()` raises the card's **status error** if given (else nothing) and whose `json()` returns the card's **body**, or raises the card's **json error**. `posts` is empty before the When.
- **HTTP500** = `httpx.HTTPStatusError("500", request=httpx.Request("POST", TURNSTILE_VERIFY_URL), response=httpx.Response(500, request=httpx.Request("POST", TURNSTILE_VERIFY_URL)))`. **TIMEOUT** = `httpx.ConnectTimeout("timed out")`.
- `verify_turnstile` cards: When = `result = asyncio.run(svc.verify_turnstile(token=…, remote_ip=…))`; a `raises:` wrap goes around the `asyncio.run`.

**Given rows.** Built directly (never through `svc`), flushed one at a time in the order written.
- **signup** = `WaitlistSignup(email=…, first_name="Zed", last_name="Ray", company_name="Acme", source="hero", ip_hash="h1")`; the card gives `email`; `wants_product_updates`, `status`, `created_at` default (`False`, `"PENDING"`, now) unless listed after "but".
- **req** = `WaitlistSignupRequest(first_name="Ann", last_name="Lee", company_name="Acme", email=…, wants_product_updates=False, turnstile_token="tok-1")` (`source`, `website` not sent); the card gives `email` and after "but" every field that differs.
- **commit point** = after the last Given line the test runs `db.commit()` (a savepoint release under the `db` fixture). A Given line marked "(after the commit point)" runs after it, is flushed, and stays uncommitted.

**Named checks.**
- **row(e)** = a fresh `SELECT` of `waitlist_signups` with `email == e` (after `db.expire_all()`); `count(e)` = the number of such rows.
- **re-read X** = `db.expire_all()`, then SELECT X by id. **unchanged(X)** = every column of X equals its value at the commit point.
- `committed:` lines: before the first one the test runs `db.rollback()` once; each line then re-reads or counts with a fresh query.
- `session:` lines check `db` itself; "usable" = `db.execute(text("SELECT 1")).scalar() == 1`.
- `raises: <Type>`: plain `with pytest.raises(<Type>) as exc:` around the call, no savepoint. Further `raises:` lines assert on `exc.value` after the block.
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When.
- **ids(x)** = `[r.id for r in x]` (order is part of the check).

**xfail cards.** Strict unless the Expect line says `(non-strict)`.

**Race simulations.** WSV-S-06 only (`submit_signup` R7): `real = waitlist_dao.get_by_email`; `patch.object(waitlist_dao, "get_by_email", side_effect=[None, real-call])` written as a function that returns `None` on its first call and `real(*a, **kw)` on every later call; around the When.

## `normalize_waitlist_email`

### WSV-N-01 — the email is trimmed and lower-cased
- **Rules:** `normalize_waitlist_email` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing.

**When**
- `result = normalize_waitlist_email("  A@B.C ")`.

**Then**
1. returns: `result == "a@b.c"`.

## `hash_client_ip`

### WSV-H-01 — None gives None
- **Rules:** `hash_client_ip` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. salt pepper active.

**When**
- `result = hash_client_ip(None)`.

**Then**
1. returns: `result is None`.

### WSV-H-02 — an empty text gives None
- **Rules:** `hash_client_ip` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. salt pepper active.

**When**
- `result = hash_client_ip("")`.

**Then**
1. returns: `result is None`.

### WSV-H-03 — an IP is hashed with the salt
- **Rules:** `hash_client_ip` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. salt pepper active; also `patch.object(settings, "SECRET_KEY", "sekrit")`.

**When**
- `result = hash_client_ip("203.0.113.7")`.

**Then**
1. returns: `result == H_PEPPER`.
2. returns: `len(result) == 64`.

### WSV-H-04 — with an empty salt the secret key is the salt
- **Rules:** `hash_client_ip` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `patch.object(settings, "WAITLIST_IP_HASH_SALT", "")` and `patch.object(settings, "SECRET_KEY", "sekrit")`.

**When**
- `result = hash_client_ip("203.0.113.7")`.

**Then**
1. returns: `result == H_SEKRIT`.

## `WaitlistService.verify_turnstile`

### WSV-T-01 — without a key nothing is checked and nothing is sent
- **Rules:** `verify_turnstile` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. no key; stub with body `{"success": False}`.

**When**
- `result = asyncio.run(svc.verify_turnstile(token="tok-1", remote_ip=IP))`.

**Then**
1. returns: `result is None`.
2. mock called: `posts == []`.

### WSV-T-02 — a confirmed token passes; the request carries secret, token and IP
- **Rules:** `verify_turnstile` R2, R3, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. key set; stub with body `{"success": True}`.

**When**
- `result = asyncio.run(svc.verify_turnstile(token="tok-1", remote_ip=IP))`.

**Then**
1. returns: `result is None`.
2. mock called: `len(posts) == 1`.
3. mock called: `posts[0][0] == "https://challenges.cloudflare.com/turnstile/v0/siteverify"`.
4. mock called: `posts[0][1] == {"secret": "sk-test", "response": "tok-1", "remoteip": "203.0.113.7"}`.

### WSV-T-03 — an empty IP is not sent
- **Rules:** `verify_turnstile` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. key set; stub with body `{"success": True}`.

**When**
- `result = asyncio.run(svc.verify_turnstile(token="tok-1", remote_ip=""))`.

**Then**
1. returns: `result is None`.
2. mock called: `posts[0][1] == {"secret": "sk-test", "response": "tok-1"}`.

### WSV-T-04 — success false is refused with 400
- **Rules:** `verify_turnstile` R4, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. key set; stub with body `{"success": False}`.

**When**
- `asyncio.run(svc.verify_turnstile(token="tok-1", remote_ip=IP))`, inside `raises: HTTPException`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Verification failed — please try again"`.

### WSV-T-05 — an answer without success is refused with 400
- **Rules:** `verify_turnstile` R4, Errors row 1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. key set; stub with body `{"error-codes": []}`.

**When**
- `asyncio.run(svc.verify_turnstile(token="tok-1", remote_ip=IP))`, inside `raises: HTTPException`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Verification failed — please try again"`.

### WSV-T-06 — an HTTP error status becomes 502
- **Rules:** `verify_turnstile` R5, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. key set; stub with status error HTTP500 and body `{"success": True}`.

**When**
- `asyncio.run(svc.verify_turnstile(token="tok-1", remote_ip=IP))`, inside `raises: HTTPException`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 502`.
3. raises: `exc.value.detail == "Could not verify submission"`.

### WSV-T-07 — a connect timeout becomes 502
- **Rules:** `verify_turnstile` R5, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. key set; stub with error TIMEOUT at post.

**When**
- `asyncio.run(svc.verify_turnstile(token="tok-1", remote_ip=IP))`, inside `raises: HTTPException`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 502`.
3. raises: `exc.value.detail == "Could not verify submission"`.

### WSV-T-08 — an answer that is not JSON becomes 502
- **Rules:** `verify_turnstile` R5 [BUG-1580], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1580
- **Fails today on:** Then 1 (the `ValueError` from `json()` escapes)

**Given**
1. key set; stub with json error `ValueError("Expecting value")`.

**When**
- `asyncio.run(svc.verify_turnstile(token="tok-1", remote_ip=IP))`, inside `raises: HTTPException`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 502`.
3. raises: `exc.value.detail == "Could not verify submission"`.

### WSV-T-09 — a JSON list becomes 502
- **Rules:** `verify_turnstile` R5 [BUG-1580], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1580
- **Fails today on:** Then 1 (an `AttributeError` escapes: a list has no `get`)

**Given**
1. key set; stub with body `[1]`.

**When**
- `asyncio.run(svc.verify_turnstile(token="tok-1", remote_ip=IP))`, inside `raises: HTTPException`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 502`.
3. raises: `exc.value.detail == "Could not verify submission"`.

## `WaitlistService.submit_signup`

### WSV-S-01 — a new signup is stored normalised and committed
- **Rules:** `submit_signup` R2, R3, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. salt pepper active.
2. `data` = req, `email f"Ann.{TAG}@X.com"`, but `first_name " Ann "`, `last_name " Lee "`, `company_name " Acme "`, `wants_product_updates True`, `source "pricing"`.

**When**
- `result = svc.submit_signup(db, payload=data, remote_ip="203.0.113.7")`.

**Then**
1. returns: `result.ok is True`.
2. returns: `result.message == "You're on the list — we'll be in touch."` (the literal text, with an em dash U+2014; not the module's `SUCCESS_MESSAGE` constant).
3. committed: `count(f"ann.{TAG}@x.com") == 1`.
4. committed: row(`f"ann.{TAG}@x.com"`): `first_name == "Ann"`, `last_name == "Lee"`, `company_name == "Acme"`.
5. committed: row(`f"ann.{TAG}@x.com"`): `wants_product_updates is True`, `source == "pricing"`, `status == "PENDING"`.
6. committed: row(`f"ann.{TAG}@x.com"`): `ip_hash == H_PEPPER`.

### WSV-S-02 — a blank company, a null source and no IP are stored as NULL
- **Rules:** `submit_signup` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. salt pepper active.
2. `data` = req, `email f"bo.{TAG}@x.com"`, but `company_name "   "`, `source None`.

**When**
- `result = svc.submit_signup(db, payload=data, remote_ip=None)`.

**Then**
1. returns: `result.ok is True`.
2. committed: row(`f"bo.{TAG}@x.com"`): `company_name is None`, `source is None`, `ip_hash is None`.

### WSV-S-03 — a filled honeypot answers success and stores nothing
- **Rules:** `submit_signup` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. salt pepper active.
2. `data` = req, `email f"bot.{TAG}@x.com"`, but `website "http://spam.example"`.

**When**
- `result = svc.submit_signup(db, payload=data, remote_ip=IP)`.

**Then**
1. returns: `result.ok is True`.
2. returns: `result.message == SUCCESS_MESSAGE`.
3. count: `count(f"bot.{TAG}@x.com") == 0`.

### WSV-S-04 — an empty honeypot is not caught
- **Rules:** `submit_signup` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. salt pepper active.
2. `data` = req, `email f"cy.{TAG}@x.com"`, but `website ""`.

**When**
- `result = svc.submit_signup(db, payload=data, remote_ip=IP)`.

**Then**
1. returns: `result.ok is True`.
2. committed: `count(f"cy.{TAG}@x.com") == 1`.

### WSV-S-05 — an email already on the list, in other capitals, changes nothing
- **Rules:** `submit_signup` R2, R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. salt pepper active.
2. A = signup, `email f"ann.{TAG}@x.com"`.
3. `data` = req, `email f"ANN.{TAG}@x.com"`, but `first_name "Bob"`, `wants_product_updates True`.

**When**
- `result = svc.submit_signup(db, payload=data, remote_ip=IP)`.

**Then**
1. returns: `result.ok is True`.
2. returns: `result.message == SUCCESS_MESSAGE`.
3. committed: `count(f"ann.{TAG}@x.com") == 1`.
4. committed: re-read A: `first_name == "Zed"`, `wants_product_updates is False`, `ip_hash == "h1"`.

### WSV-S-06 — a signup that loses the race answers success; pending changes are discarded
- **Rules:** `submit_signup` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. salt pepper active.
2. A = signup, `email f"ann.{TAG}@x.com"`.
3. X = signup, `email f"extra.{TAG}@x.com"` (after the commit point).
4. `data` = req, `email f"ann.{TAG}@x.com"`, but `first_name "Bob"`.

**When**
- `result = svc.submit_signup(db, payload=data, remote_ip=IP)`, with the race simulation active.

**Then**
1. returns: `result.ok is True`.
2. returns: `result.message == SUCCESS_MESSAGE`.
3. count: `count(f"extra.{TAG}@x.com") == 0`.
4. count: `count(f"ann.{TAG}@x.com") == 1`.
5. re-read A: `first_name == "Zed"`.
6. session: usable.

### WSV-S-07 — a failing commit with a new email is rolled back and re-raised
- **Rules:** `submit_signup` R7, R8; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. salt pepper active.
2. `data` = req, `email f"dee.{TAG}@x.com"`.

**When**
- `svc.submit_signup(db, payload=data, remote_ip=IP)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `count(f"dee.{TAG}@x.com") == 0`.

### WSV-S-08 — skip_turnstile=True changes nothing
- **Rules:** `submit_signup` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. salt pepper active.
2. `data` = req, `email f"eve.{TAG}@x.com"`.

**When**
- `result = svc.submit_signup(db, payload=data, remote_ip=IP, skip_turnstile=True)`.

**Then**
1. returns: `result.ok is True`.
2. committed: row(`f"eve.{TAG}@x.com"`): `first_name == "Ann"`, `status == "PENDING"`.

### WSV-S-09 — a first name of only spaces is refused by the schema
- **Rules:** `submit_signup` R4 [BUG-1579]
- **Kind:** bug
- **Expect:** xfail BUG-1579
- **Fails today on:** Then 1 (the schema accepts it; `"   "` has length 3)

**Given**
1. Nothing.

**When**
- build `WaitlistSignupRequest(first_name="   ", last_name="Lee", email=f"fay.{TAG}@x.com", turnstile_token="tok-1")` (target `schema`; `svc` is not called).

**Then**
1. raises: `PydanticValidationError`.
2. count: `count(f"fay.{TAG}@x.com") == 0`.

## `WaitlistService.update_status`

### WSV-U-01 — an unknown id is answered with 404
- **Rules:** `update_status` R1, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = signup, `email f"ann.{TAG}@x.com"`.

**When**
- `svc.update_status(db, signup_id=999999999, status_value="CONTACTED")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Waitlist signup not found"`.
4. unchanged: unchanged(A).

### WSV-U-02 — the status is set, committed and returned as an item
- **Rules:** `update_status` R2, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = signup, `email f"ann.{TAG}@x.com"`.

**When**
- `result = svc.update_status(db, signup_id=A.id, status_value="CONTACTED")`.

**Then**
1. returns: `isinstance(result, WaitlistSignupItem)`.
2. returns: `result.id == A.id`, `result.status == "CONTACTED"`, `result.email == f"ann.{TAG}@x.com"`.
3. committed: re-read A: `status == "CONTACTED"`.
4. committed: re-read A: `first_name == "Zed"`, `wants_product_updates is False`, `ip_hash == "h1"`.

### WSV-U-03 — a stored status outside the four can be set to one of them
- **Rules:** `update_status` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = signup, `email f"ann.{TAG}@x.com"`, but `status "legacy"`.

**When**
- `result = svc.update_status(db, signup_id=A.id, status_value="ACCEPTED")`.

**Then**
1. returns: `result.status == "ACCEPTED"`.
2. committed: re-read A: `status == "ACCEPTED"`.

### WSV-U-04 — a failing commit is rolled back and re-raised
- **Rules:** `update_status` R3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. A = signup, `email f"ann.{TAG}@x.com"`.

**When**
- `svc.update_status(db, signup_id=A.id, status_value="DECLINED")`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read A: `status == "PENDING"`.

### WSV-U-05 — a status over 20 characters fails at the flush and leaves the session needing a rollback
- **Rules:** `update_status` R3, Errors
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = signup, `email f"ann.{TAG}@x.com"`.

**When**
- `svc.update_status(db, signup_id=A.id, status_value="X" * 21)`, inside `raises: DataError`.

**Then**
1. raises: `DataError`.
2. session: `with pytest.raises(PendingRollbackError): db.execute(text("SELECT 1"))`.
3. re-read A (after a test-level `db.rollback()`): `status == "PENDING"`.

## `WaitlistService.list_signups`

### WSV-L-01 — items and total come from the DAO; skip and limit are echoed
- **Rules:** `list_signups` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = signup, `email f"a.{TAG}@x.com"`, but `created_at T2`.
2. B = signup, `email f"b.{TAG}@x.com"`, but `created_at T3`.
3. C = signup, `email f"c.{TAG}@x.com"`, but `created_at T1`.

**When**
- `result = svc.list_signups(db, skip=1, limit=1, search=TAG, wants_product_updates=None)`.

**Then**
1. returns: `result.total == 3`.
2. returns: `result.skip == 1`, `result.limit == 1`.
3. returns: `ids(result.items) == [A.id]`.
4. returns: `isinstance(result.items[0], WaitlistSignupItem)`.

### WSV-L-02 — status_value reaches the DAO as the status filter
- **Rules:** `list_signups` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = signup, `email f"a.{TAG}@x.com"`, but `status "CONTACTED"`.
2. B = signup, `email f"b.{TAG}@x.com"`.

**When**
- `result = svc.list_signups(db, skip=0, limit=1000, search=TAG, wants_product_updates=None, status_value="CONTACTED")`.

**Then**
1. returns: `ids(result.items) == [A.id]`.
2. returns: `result.total == 1`.

### WSV-L-03 — wants_product_updates reaches the DAO
- **Rules:** `list_signups` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = signup, `email f"a.{TAG}@x.com"`, but `wants_product_updates True`.
2. B = signup, `email f"b.{TAG}@x.com"`.

**When**
- `result = svc.list_signups(db, skip=0, limit=1000, search=TAG, wants_product_updates=False)`.

**Then**
1. returns: `ids(result.items) == [B.id]`.
2. returns: `result.total == 1`.

### WSV-L-04 — a stored status outside the four makes the list fail
- **Rules:** `list_signups` R2, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = signup, `email f"a.{TAG}@x.com"`, but `status "legacy"`.

**When**
- `svc.list_signups(db, skip=0, limit=1000, search=TAG, wants_product_updates=None)`, inside `raises: PydanticValidationError`.

**Then**
1. raises: `PydanticValidationError`.
2. re-read A: `status == "legacy"`.

### WSV-L-05 — the list neither commits nor rolls back
- **Rules:** `list_signups` R3; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = signup, `email f"a.{TAG}@x.com"`.
2. B = signup, `email f"b.{TAG}@x.com"`.
3. P = signup, `email f"p.{TAG}@x.com"` (after the commit point).
4. `B.first_name = "Edited"` (after the commit point, not flushed).

**When**
- `result = svc.list_signups(db, skip=0, limit=1000, search=f"a.{TAG}", wants_product_updates=None)`.

**Then**
1. returns: `ids(result.items) == [A.id]`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. committed: `count(f"p.{TAG}@x.com") == 0`.
5. committed: re-read B: `first_name == "Zed"`.

### WSV-L-06 — pass-through BUG-1410: _ in the search matches only a literal _
- **Rules:** `list_signups` R1 [BUG-1410]
- **Kind:** bug
- **Expect:** xfail BUG-1410
- **Fails today on:** Then 2 (`_` is a wildcard today: B is found too)

**Given**
1. A = signup, `email f"a_b.{TAG}@x.com"`.
2. B = signup, `email f"axb.{TAG}@x.com"`.

**When**
- `result = svc.list_signups(db, skip=0, limit=1000, search=f"a_b.{TAG}", wants_product_updates=None)`.

**Then**
1. returns: `isinstance(result.items, list)`.
2. returns: `ids(result.items) == [A.id]`.
3. returns: `result.total == 1`.

### WSV-L-07 — pass-through BUG-1411: on a created_at tie the higher id comes first
- **Rules:** `list_signups` R1 [BUG-1411]
- **Kind:** bug
- **Expect:** xfail BUG-1411 (non-strict)
- **Fails today on:** Then 2 (no order among tied rows; physical order puts the updated row last)

**Given**
1. A = signup, `email f"a.{TAG}@x.com"`, but `created_at T2`.
2. B = signup, `email f"b.{TAG}@x.com"`, but `created_at T2`.
3. C = signup, `email f"c.{TAG}@x.com"`, but `created_at T2`.
4. `A.first_name = "Amy"`, then `db.flush()`.

**When**
- `result = svc.list_signups(db, skip=0, limit=1000, search=TAG, wants_product_updates=None)`.

**Then**
1. returns: `len(result.items) == 3`.
2. returns: `ids(result.items) == [C.id, B.id, A.id]`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Endpoint order (Turnstile before the signup), rate limit, `get_waitlist_admin` | `POST /waitlist`, `GET /waitlist`, `PATCH /waitlist/{id}/status` (integration) | Integration-only. |
| BUG-1579 / BUG-461 — schema errors answer 422 | `POST /waitlist` | Integration-only; the schema half is WSV-S-09. |
| `limit`, `skip`, `search` bounds (HR-7) | `GET /waitlist` | Endpoint bounds. |
| DAO rules R1–R7 (search, filters, order, paging) beyond one card per argument and one per bug | `tests/unit/dao/waitlist.cases.md` | Not re-tested here. |
| BUG-1411 strict `ORDER BY` recorder | `dao/waitlist.cases.md` WLS-LS-16 | The query is the DAO's; WSV-L-07 is the pass-through only. |
| `update_status` 20-character side of the status length | `dao/waitlist.cases.md` (`update_status`) | Not reachable through the service: a 20-character status fails the item schema. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `verify_turnstile` R2 | "timeout 10 seconds" does not say where it is passed (the `AsyncClient(...)` constructor or `post(...)`). | The timeout is not asserted; no card. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `normalize_waitlist_email` | R1 | WSV-N-01, WSV-S-05 |
| `hash_client_ip` | R1 | WSV-H-01, WSV-H-02 |
| `hash_client_ip` | R2 | WSV-H-03, WSV-H-04 |
| `verify_turnstile` | R1 | WSV-T-01 |
| `verify_turnstile` | R2 | WSV-T-02, WSV-T-03 |
| `verify_turnstile` | R3 | WSV-T-02 |
| `verify_turnstile` | R4 | WSV-T-04, WSV-T-05 |
| `verify_turnstile` | R5 | WSV-T-06, WSV-T-07 |
| `verify_turnstile` | R5 [BUG-1580] | WSV-T-08, WSV-T-09 |
| `verify_turnstile` | Errors row 1 | WSV-T-04, WSV-T-05 |
| `verify_turnstile` | Errors row 2 | WSV-T-06, WSV-T-07, WSV-T-08, WSV-T-09 |
| `verify_turnstile` | Returns | WSV-T-02 |
| `submit_signup` | R1 | WSV-S-03, WSV-S-04 |
| `submit_signup` | R2 | WSV-S-01, WSV-S-05 |
| `submit_signup` | R3 | WSV-S-01, WSV-S-02 |
| `submit_signup` | R4 [BUG-1579] | WSV-S-09 |
| `submit_signup` | R5 | WSV-S-08 |
| `submit_signup` | R6 | WSV-S-05 |
| `submit_signup` | R7 | WSV-S-06, WSV-S-07 |
| `submit_signup` | R8 | WSV-S-07 |
| `submit_signup` | Returns | WSV-S-01, WSV-S-03 |
| `update_status` | R1 | WSV-U-01 |
| `update_status` | R2 | WSV-U-02, WSV-U-03 |
| `update_status` | R3 | WSV-U-04, WSV-U-05 |
| `update_status` | Errors | WSV-U-01, WSV-U-05 |
| `update_status` | Returns | WSV-U-02 |
| `list_signups` | R1 | WSV-L-01, WSV-L-02, WSV-L-03 |
| `list_signups` | R1 [BUG-1410] | WSV-L-06 |
| `list_signups` | R1 [BUG-1411] | WSV-L-07 |
| `list_signups` | R2 | WSV-L-04 |
| `list_signups` | R3 | WSV-L-05 |
| `list_signups` | Errors | WSV-L-04 |
| `list_signups` | Returns | WSV-L-01 |
| Transaction contract | TC1 | WSV-S-01, WSV-U-02 |
| Transaction contract | TC2 | Not applicable: no re-read with `refresh`; `update_status` answers from the row (WSV-U-02) |
| Transaction contract | TC3 | WSV-S-06 (pending changes discarded) |
| Transaction contract | TC4 | WSV-S-07, WSV-U-04 |
| Transaction contract | TC5 | Not applicable: no re-read after the commit |
| Transaction contract | TC6 | WSV-L-05 |
