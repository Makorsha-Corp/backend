# Test cases — `app/dao/profile.py`

> **Spec:** `tests/unit/dao/profile.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 (2026-11-04) — additive, from `profile.verify.md` findings 1 and 2: PRF-GE-14, GE-15 (`%` is literal: an ILIKE fix that escapes only `_` fails), PRF-GE-16, GE-17 (an inner space on the argument / stored side is not ignored: a fix that strips every space fails). All four pass today. The spec did not change; no card changed or retired.
> **Counts:** 46 cases · 33 expected-to-pass · 13 expected-to-fail (bugs) · 3 deferred

## Reviewer summary
- **Per callable:** `get_by_email` 17 (5 bug) · `create` 18 (5 bug) · `authenticate` 11 (3 bug).
- **Depth:** full. This is the account lookup of login, registration and password reset: who you are is decided here (owner's OQ-1, BUG-1860 … 1862).
- **Expected-to-fail (all strict):** BUG-1860 5 (GE-03 … GE-06 the argument side, GE-13 the stored side) + AU-02; BUG-1861 CR-15; BUG-1862 CR-17; BUG-1406 3 (CR-04 … CR-06); BUG-038 AU-04; BUG-500 AU-09.
- **Notable design choices:**
  - Case-variant rows "as older rows are" are built with `make_profile` (it stores the email as given), as the spec's Notes say.
  - Kept passing today and after the fix: an exact match (GE-01, GE-02, AU-01 log in with the stored capitals), inner text still has to match (GE-07), a part, `_` and `%` never match (GE-08, GE-09, GE-14, GE-15), an inner space on either side is not ignored (GE-16, GE-17), `user_id` equals the stored email and the domain is lowered (CR-16).
  - Every email lookup has another profile at a lower and at a higher id, so a lookup that returns "the first" or "a neighbour" fails.
  - Password bytes, not characters: `"a"*72` and `"é"*36` (72 bytes) pass; `"a"*73` and `"é"*36 + "a"` (37 characters, 73 bytes) raise.
  - The taken-email card (CR-13) asserts pgcode `23505` only, not the constraint name: BUG-1862 replaces `profiles_email_key`.
  - AU-04 (BUG-038) needs a `wraps=` patch: `Author: claude`.
- **Needs a decision:** None. Gap 1 (is `timezone` optional in `ProfileCreate`) is worked around by always sending it.

## Conventions for this module

**IDs.** `PRF` = `app/dao/profile.py`. `GE` get_by_email · `CR` create · `AU` authenticate.

**Actors and fixed values.**
- `dao` = the singleton `profile_dao` (`from app.dao.profile import profile_dao`). `db` = the test's real session, always the first argument; every other argument by keyword. `result` = what the When call returns.
- `Profile` (`app.models.profile`), `ProfileCreate` (`app.schemas.profile`), `get_password_hash`, `verify_password` (`app.core.security`), `IntegrityError` (`sqlalchemy.exc`), `PydanticValidationError` = `pydantic.ValidationError`, `select`, `func`, `text` (`sqlalchemy`), `patch` (`unittest.mock`).
- TAG = `uuid.uuid4().hex[:8]`, made once at the start of each test (lowercase hex).
- MIXED = `f"Ann.Lee.{TAG}@example.com"`. LOWER = `f"ann.lee.{TAG}@example.com"`. UPPER = `f"ANN.LEE.{TAG.upper()}@EXAMPLE.COM"`.
- EA = `f"bob.{TAG}@example.com"`, EZ = `f"zed.{TAG}@example.com"`: the neighbours' emails.
- PW = `"Correct-Horse-9"`. HPW = `get_password_hash(PW)`, computed once in the test where a card uses it.
- TZ = `"Asia/Dhaka"`. Every `ProfileCreate` in this file passes `timezone=TZ` unless the card says otherwise.

**Externals.** None. bcrypt runs for real. No clock.

**Given rows.** Inserted directly (never through `dao`), flushed one at a time in the order written, so ids rise in that order. The session does not autoflush.
- **profile(e)** = `make_profile(db, email=e)` (`tests/unit/factories.py`); its `hashed_password` is `"not-a-real-hash"`. **profile(e, h)** = `make_profile(db, email=e, hashed_password=h)`. After "but" the card lists every other column that differs.
- **neighbours** = two lines of the Given: PA = profile(EA, HPW) before the card's row, PZ = profile(EZ, HPW) after it.
- No profile with an email containing TAG exists unless the Given builds it.
- A Given line written as code is a step to run exactly. `db.add(X)` without flush leaves X pending; an attribute set "(not flushed)" stays an unflushed edit.

**Named checks.**
- **re-read X** = `db.expire_all()`, then `db.get(Profile, X.id)`; values are database values. **the new row** = `db.scalar(select(Profile).where(Profile.id == result.id))` after `db.expire_all()`.
- **count(e)** = `db.scalar(select(func.count()).select_from(Profile).where(Profile.email == e))`. **count_ci(e)** = the same with `func.lower(Profile.email) == e.lower()`.
- `pending:` / `session:` lines check `db.new`, `db.dirty`, `db.deleted` after the call, before anything expires the session; keep the card's order.
- `raises: IntegrityError on flush` = `with pytest.raises(IntegrityError) as exc:` then `with db.begin_nested():` then the When. `pgcode` = `exc.value.orig.pgcode`; `constraint` = `exc.value.orig.diag.constraint_name`.
- `raises: ValueError` / `AttributeError` = plain `with pytest.raises(<Type>) as exc:` around the call, no savepoint; `str(exc.value)` is checked with `==`.
- `raises: PydanticValidationError` (target `schema`) = `pytest.raises` around building the schema only; the DAO is not called.
- **rolled back** = `sp = db.begin_nested()` directly before the call and `with patch.object(db, "commit", wraps=db.commit) as cm:` around it; "inside" checks first, then `sp.rollback()` and the "after" checks.

**Statement recorder.** A `before_cursor_execute` listener on `db.connection()` records the statement texts sent during the When. `written` = the entries that start with `INSERT`, `UPDATE` or `DELETE` after stripping and upper-casing.

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`. Write the call and checks exactly as shown.

**Race simulations.** None in this module.

## `DAOProfile.get_by_email`

### PRF-GE-01 — the profile stored with exactly that text is found, not a neighbour
- **Rules:** `get_by_email` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. PA = profile(EA).
2. P = profile(MIXED).
3. PZ = profile(EZ).

**When**
- `result = dao.get_by_email(db, email=MIXED)`.

**Then**
1. returns: `isinstance(result, Profile)`.
2. returns: `result.id == P.id`.
3. returns: `result.email == MIXED`.

### PRF-GE-02 — a lower-case stored email is found by the same lower-case text
- **Rules:** `get_by_email` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. PA = profile(EA).
2. P = profile(LOWER).
3. PZ = profile(EZ).

**When**
- `result = dao.get_by_email(db, email=LOWER)`.

**Then**
1. returns: `result.id == P.id`.

### PRF-GE-03 — other capitals in the argument find a mixed-case stored email
- **Rules:** `get_by_email` R1a [BUG-1860]
- **Kind:** bug
- **Expect:** xfail BUG-1860
- **Fails today on:** Then 1 (exact match: `None`)

**Given**
1. PA = profile(EA).
2. P = profile(MIXED).
3. PZ = profile(EZ).

**When**
- `result = dao.get_by_email(db, email=LOWER)`.

**Then**
1. returns: `result is not None`.
2. returns: `result.id == P.id`.

### PRF-GE-04 — an all-capitals argument finds a mixed-case stored email
- **Rules:** `get_by_email` R1a [BUG-1860]
- **Kind:** bug
- **Expect:** xfail BUG-1860
- **Fails today on:** Then 1 (exact match: `None`)

**Given**
1. PA = profile(EA).
2. P = profile(MIXED).
3. PZ = profile(EZ).

**When**
- `result = dao.get_by_email(db, email=UPPER)`.

**Then**
1. returns: `result is not None`.
2. returns: `result.id == P.id`.

### PRF-GE-05 — outer spaces around the argument are ignored
- **Rules:** `get_by_email` R1a [BUG-1860]
- **Kind:** bug
- **Expect:** xfail BUG-1860
- **Fails today on:** Then 1 (exact match: `None`)

**Given**
1. PA = profile(EA).
2. P = profile(MIXED).
3. PZ = profile(EZ).

**When**
- `result = dao.get_by_email(db, email=f" {MIXED} ")`.

**Then**
1. returns: `result is not None`.
2. returns: `result.id == P.id`.

### PRF-GE-06 — a mixed-case argument finds a lower-case stored email
- **Rules:** `get_by_email` R1a [BUG-1860]
- **Kind:** bug
- **Expect:** xfail BUG-1860
- **Fails today on:** Then 1 (exact match: `None`)

**Given**
1. PA = profile(EA).
2. P = profile(LOWER).
3. PZ = profile(EZ).

**When**
- `result = dao.get_by_email(db, email=MIXED)`.

**Then**
1. returns: `result is not None`.
2. returns: `result.id == P.id`.

### PRF-GE-07 — inner text must still match: one more character gives None
- **Rules:** `get_by_email` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = profile(EA).
2. P = profile(MIXED).
3. PZ = profile(EZ).

**When**
- `result = dao.get_by_email(db, email=f"ann.lee2.{TAG}@example.com")`.

**Then**
1. returns: `result is None`.

### PRF-GE-08 — a part of the stored email gives None
- **Rules:** `get_by_email` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = profile(EA).
2. P = profile(MIXED).
3. PZ = profile(EZ).

**When**
- `result = dao.get_by_email(db, email=f"Ann.Lee.{TAG}@example")`.

**Then**
1. returns: `result is None`.

### PRF-GE-09 — `_` in the argument is a literal character, not a wildcard
- **Rules:** `get_by_email` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = profile(EA).
2. P = profile(MIXED).
3. PZ = profile(EZ).

**When**
- `result = dao.get_by_email(db, email=f"Ann_Lee.{TAG}@example.com")`.

**Then**
1. returns: `result is None`.

### PRF-GE-10 — an unknown email gives None, no error
- **Rules:** `get_by_email` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. PA = profile(EA).
2. PZ = profile(EZ).

**When**
- `result = dao.get_by_email(db, email=f"nobody.{TAG}@example.com")`.

**Then**
1. returns: `result is None`.

### PRF-GE-11 — an empty email gives None, no error
- **Rules:** `get_by_email` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = profile(EA).
2. PZ = profile(EZ).

**When**
- `result = dao.get_by_email(db, email="")`.

**Then**
1. returns: `result is None`.

### PRF-GE-12 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `get_by_email` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P = profile(MIXED).
2. B = profile(EZ).
3. `N = Profile(name="New", email=f"new.{TAG}@example.com", user_id=f"new-{TAG}", hashed_password="x")`
4. `db.add(N)` (not flushed).
5. `B.name = "Changed"` (not flushed).
6. The statement recorder.

**When**
- `result = dao.get_by_email(db, email=MIXED)`.

**Then**
1. returns: `result.id == P.id`.
2. pending: `N in db.new`.
3. pending: `len(db.new) == 1`.
4. session: `B in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. session: `not db.deleted`.
7. statement: `written == []`.

### PRF-GE-13 — an outer space on the stored side is ignored too
- **Rules:** `get_by_email` R1a [BUG-1860]
- **Kind:** bug
- **Expect:** xfail BUG-1860
- **Fails today on:** Then 1 (exact match: `None`)

**Given**
1. PA = profile(EA).
2. P = profile(f" {LOWER}").
3. PZ = profile(EZ).

**When**
- `result = dao.get_by_email(db, email=LOWER)`.

**Then**
1. returns: `result is not None`.
2. returns: `result.id == P.id`.

### PRF-GE-14 — `%` in the local part is a literal character, not a wildcard
- **Rules:** `get_by_email` R1, R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = profile(EA).
2. P = profile(MIXED).
3. PZ = profile(EZ).

**When**
- `result = dao.get_by_email(db, email=f"%.{TAG}@example.com")`.

**Then**
1. returns: `result is None`.

### PRF-GE-15 — `%` alone before the domain finds no account
- **Rules:** `get_by_email` R1, R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = profile(EA).
2. P = profile(MIXED).
3. PZ = profile(EZ).

**When**
- `result = dao.get_by_email(db, email="%@example.com")`.

**Then**
1. returns: `result is None`.

### PRF-GE-16 — an inner space in the argument is not ignored
- **Rules:** `get_by_email` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = profile(EA).
2. P = profile(MIXED).
3. PZ = profile(EZ).

**When**
- `result = dao.get_by_email(db, email=f"Ann.Lee .{TAG}@example.com")`.

**Then**
1. returns: `result is None`.

### PRF-GE-17 — an inner space on the stored side is not ignored
- **Rules:** `get_by_email` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = profile(EA).
2. P = profile(f"Ann. Lee.{TAG}@example.com").
3. PZ = profile(EZ).

**When**
- `result = dao.get_by_email(db, email=MIXED)`.

**Then**
1. returns: `result is None`.

## `DAOProfile.create`

### PRF-CR-01 — one profile is inserted with every field set as stated
- **Rules:** `create` R1, Returns, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. No profile with an email containing TAG.

**When**
- `result = dao.create(db, obj_in=ProfileCreate(name="Ann Lee", email=LOWER, password=PW, timezone=TZ))`.

**Then**
1. returns: `isinstance(result, Profile)`.
2. returns: `result.id is not None`.
3. re-read the new row: `name == "Ann Lee"`, `email == LOWER`, `user_id == LOWER`, `timezone == "Asia/Dhaka"`.
4. re-read the new row: `is_platform_admin is False`, `saved_stamp is None`.
5. re-read the new row: `hashed_password.startswith("$2")`.
6. re-read the new row: `verify_password(PW, hashed_password) is True`.
7. re-read the new row: `hashed_password != PW`.
8. count: `count(LOWER) == 1`.

### PRF-CR-02 — the same password hashed twice gives two different hashes
- **Rules:** `create` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. `first = dao.create(db, obj_in=ProfileCreate(name="Ann", email=EA, password=PW, timezone=TZ))`.

**When**
- `result = dao.create(db, obj_in=ProfileCreate(name="Zed", email=EZ, password=PW, timezone=TZ))`.

**Then**
1. returns: `result.id != first.id`.
2. re-read result and first: `result.hashed_password != first.hashed_password`.
3. re-read result: `verify_password(PW, result.hashed_password) is True`.
4. re-read first: `verify_password(PW, first.hashed_password) is True`.

### PRF-CR-03 — create flushes but never commits
- **Rules:** `create` Returns, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No profile with an email containing TAG.

**When**
- rolled back: `result = dao.create(db, obj_in=ProfileCreate(name="Ann", email=LOWER, password=PW, timezone=TZ))`.

**Then**
1. returns (inside): `result.id is not None`.
2. count (inside): `count(LOWER) == 1`.
3. session: `cm.call_count == 0`.
4. count (after the savepoint rollback): `count(LOWER) == 0`.

### PRF-CR-04 — outer spaces of the name are removed before storing
- **Rules:** `create` R2 [BUG-1406]
- **Kind:** bug
- **Expect:** xfail BUG-1406
- **Fails today on:** Then 2 (stored as typed: `"  Ann "`)

**Given**
1. No profile with an email containing TAG.

**When**
- `result = dao.create(db, obj_in=ProfileCreate(name="  Ann ", email=LOWER, password=PW, timezone=TZ))`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new row: `name == "Ann"`.

### PRF-CR-05 — a whitespace-only name is refused by the schema
- **Rules:** `create` R2 [BUG-1406]
- **Kind:** bug
- **Expect:** xfail BUG-1406
- **Fails today on:** Then 1 (the schema accepts `"   "`)

**Given**
1. No profile with an email containing TAG.

**When**
- build `ProfileCreate(name="   ", email=LOWER, password=PW, timezone=TZ)` (target `schema`; the DAO is not called).

**Then**
1. raises: `PydanticValidationError`.
2. count: `count(LOWER) == 0`.

### PRF-CR-06 — an empty name is refused by the schema
- **Rules:** `create` R2 [BUG-1406]
- **Kind:** bug
- **Expect:** xfail BUG-1406
- **Fails today on:** Then 1 (the schema accepts `""`)

**Given**
1. No profile with an email containing TAG.

**When**
- build `ProfileCreate(name="", email=LOWER, password=PW, timezone=TZ)` (target `schema`; the DAO is not called).

**Then**
1. raises: `PydanticValidationError`.
2. count: `count(LOWER) == 0`.

### PRF-CR-07 — inner spaces and capitals of the name are kept
- **Rules:** `create` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No profile with an email containing TAG.

**When**
- `result = dao.create(db, obj_in=ProfileCreate(name="Ann  LEE", email=LOWER, password=PW, timezone=TZ))`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new row: `name == "Ann  LEE"`.

### PRF-CR-08 — an empty password is hashed and stored
- **Rules:** `create` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No profile with an email containing TAG.

**When**
- `result = dao.create(db, obj_in=ProfileCreate(name="Ann", email=LOWER, password="", timezone=TZ))`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new row: `hashed_password.startswith("$2")`.
3. re-read the new row: `verify_password("", hashed_password) is True`.

### PRF-CR-09 — a password of 72 ASCII bytes is accepted
- **Rules:** `create` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No profile with an email containing TAG.

**When**
- `result = dao.create(db, obj_in=ProfileCreate(name="Ann", email=LOWER, password="a" * 72, timezone=TZ))`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new row: `verify_password("a" * 72, hashed_password) is True`.

### PRF-CR-10 — a password of 36 two-byte characters (72 bytes) is accepted
- **Rules:** `create` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No profile with an email containing TAG.

**When**
- `result = dao.create(db, obj_in=ProfileCreate(name="Ann", email=LOWER, password="é" * 36, timezone=TZ))`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new row: `verify_password("é" * 36, hashed_password) is True`.

### PRF-CR-11 — a password of 73 ASCII bytes raises before anything is added
- **Rules:** `create` R3, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No profile with an email containing TAG.

**When**
- `dao.create(db, obj_in=ProfileCreate(name="Ann", email=LOWER, password="a" * 73, timezone=TZ))`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Password exceeds bcrypt's 72-byte limit"`.
3. pending: `len(db.new) == 0`.
4. count: `count(LOWER) == 0`.

### PRF-CR-12 — 37 characters that are 73 bytes raise: bytes are counted, not characters
- **Rules:** `create` R3, Errors row 1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No profile with an email containing TAG.

**When**
- `dao.create(db, obj_in=ProfileCreate(name="Ann", email=LOWER, password="é" * 36 + "a", timezone=TZ))`.

**Then**
1. raises: `ValueError`.
2. raises: `str(exc.value) == "Password exceeds bcrypt's 72-byte limit"`.
3. pending: `len(db.new) == 0`.
4. count: `count(LOWER) == 0`.

### PRF-CR-13 — an email already taken with the same text fails at the flush
- **Rules:** `create` R4, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. PA = profile(EA).
2. P = profile(LOWER), but `name "Ann"`.
3. PZ = profile(EZ).

**When**
- `dao.create(db, obj_in=ProfileCreate(name="Ann Two", email=LOWER, password=PW, timezone=TZ))`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `pgcode == "23505"`.
3. count: `count(LOWER) == 1`.
4. re-read P: `name == "Ann"`, `email == LOWER`.

### PRF-CR-14 — an email equal to another profile's user_id fails on the user_id constraint
- **Rules:** `create` R4, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. Q = profile(EA), but `user_id LOWER`.

**When**
- `dao.create(db, obj_in=ProfileCreate(name="Ann", email=LOWER, password=PW, timezone=TZ))`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `pgcode == "23505"`.
3. raises: `constraint == "profiles_user_id_key"`.
4. count: `count(LOWER) == 0`.

### PRF-CR-15 — the email is stored lower-cased, and user_id with it
- **Rules:** `create` R4a [BUG-1861]
- **Kind:** bug
- **Expect:** xfail BUG-1861
- **Fails today on:** Then 2 (stored `Ann.Lee.<tag>@example.com`: only the domain is lowered)

**Given**
1. No profile with an email containing TAG.

**When**
- `result = dao.create(db, obj_in=ProfileCreate(name="Ann", email=f"Ann.Lee.{TAG}@Example.COM", password=PW, timezone=TZ))`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new row: `email == LOWER`.
3. re-read the new row: `user_id == LOWER`.

### PRF-CR-16 — user_id equals the stored email and the domain is lower-case
- **Rules:** `create` R1, R4a
- **Kind:** happy
- **Expect:** pass

**Given**
1. No profile with an email containing TAG.

**When**
- `result = dao.create(db, obj_in=ProfileCreate(name="Ann", email=f"Ann.Lee.{TAG}@Example.COM", password=PW, timezone=TZ))`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new row: `user_id == email`.
3. re-read the new row: `email.endswith("@example.com")`.
4. re-read the new row: `email.lower() == LOWER`.

### PRF-CR-17 — a second account for the same address in other capitals is refused by the database
- **Rules:** `create` R4b [BUG-1862]
- **Kind:** bug
- **Expect:** xfail BUG-1862
- **Fails today on:** Then 1 (accepted as a second account)

**Given**
1. PA = profile(EA).
2. P = profile(MIXED).
3. PZ = profile(EZ).

**When**
- `dao.create(db, obj_in=ProfileCreate(name="Ann Two", email=LOWER, password=PW, timezone=TZ))`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `pgcode == "23505"`.
3. count: `count_ci(LOWER) == 1`.

### PRF-CR-18 — a plain dict raises AttributeError before anything is added
- **Rules:** `create` R5, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. No profile with an email containing TAG.

**When**
- `dao.create(db, obj_in={"name": "Ann", "email": LOWER, "password": PW, "timezone": TZ})`.

**Then**
1. raises: `AttributeError`.
2. raises: `str(exc.value) == "'dict' object has no attribute 'name'"`.
3. pending: `len(db.new) == 0`.
4. count: `count(LOWER) == 0`.

## `DAOProfile.authenticate`

### PRF-AU-01 — the right email and password return that profile, not a neighbour with the same password
- **Rules:** `authenticate` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. PA = profile(EA, HPW).
2. P = profile(MIXED, HPW).
3. PZ = profile(EZ, HPW).

**When**
- `result = dao.authenticate(db, email=MIXED, password=PW)`.

**Then**
1. returns: `isinstance(result, Profile)`.
2. returns: `result.id == P.id`.

### PRF-AU-02 — logging in with other capitals finds the account
- **Rules:** `authenticate` R1a [BUG-1860]
- **Kind:** bug
- **Expect:** xfail BUG-1860
- **Fails today on:** Then 1 (exact match: `None`)

**Given**
1. PA = profile(EA, HPW).
2. P = profile(MIXED, HPW).
3. PZ = profile(EZ, HPW).

**When**
- `result = dao.authenticate(db, email=UPPER, password=PW)`.

**Then**
1. returns: `result is not None`.
2. returns: `result.id == P.id`.

### PRF-AU-03 — an unknown email gives None
- **Rules:** `authenticate` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. PA = profile(EA, HPW).
2. PZ = profile(EZ, HPW).

**When**
- `result = dao.authenticate(db, email=f"nobody.{TAG}@example.com", password=PW)`.

**Then**
1. returns: `result is None`.

### PRF-AU-04 — for an unknown email a password check still runs once
- **Rules:** `authenticate` R2a [BUG-038]
- **Kind:** bug
- **Expect:** xfail BUG-038
- **Author:** claude
- **Fails today on:** Then 2 (no password check runs for an unknown email)

**Given**
1. PA = profile(EA, HPW).
2. `spy = patch("app.core.security.verify_password", wraps=verify_password)`, active around the When.

**When**
- `result = dao.authenticate(db, email=f"nobody.{TAG}@example.com", password=PW)`.

**Then**
1. returns: `result is None`.
2. mock called: `spy.call_count == 1`.

### PRF-AU-05 — a wrong password gives None
- **Rules:** `authenticate` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. P = profile(MIXED, HPW).

**When**
- `result = dao.authenticate(db, email=MIXED, password="correct-horse-9")`.

**Then**
1. returns: `result is None`.

### PRF-AU-06 — an empty stored hash gives None, no error
- **Rules:** `authenticate` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. P = profile(MIXED, "").

**When**
- `result = dao.authenticate(db, email=MIXED, password=PW)`.

**Then**
1. returns: `result is None`.

### PRF-AU-07 — a stored value that is not a bcrypt hash gives None, no error
- **Rules:** `authenticate` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. P = profile(MIXED, "not-a-hash").

**When**
- `result = dao.authenticate(db, email=MIXED, password=PW)`.

**Then**
1. returns: `result is None`.

### PRF-AU-08 — an empty password against a real hash gives None
- **Rules:** `authenticate` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = profile(MIXED, HPW).

**When**
- `result = dao.authenticate(db, email=MIXED, password="")`.

**Then**
1. returns: `result is None`.

### PRF-AU-09 — a password over 72 bytes for a known email gives None, not an error
- **Rules:** `authenticate` R4 [BUG-500], Errors
- **Kind:** bug
- **Expect:** xfail BUG-500
- **Fails today on:** Then 1 (the call raises ValueError: "Password exceeds bcrypt's 72-byte limit")

**Given**
1. P = profile(MIXED, HPW).

**When**
- `result = dao.authenticate(db, email=MIXED, password="a" * 73)`.

**Then**
1. returns: `result is None`.

### PRF-AU-10 — a password over 72 bytes for an unknown email gives None
- **Rules:** `authenticate` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PA = profile(EA, HPW).

**When**
- `result = dao.authenticate(db, email=f"nobody.{TAG}@example.com", password="a" * 73)`.

**Then**
1. returns: `result is None`.

### PRF-AU-11 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `authenticate` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P = profile(MIXED, HPW).
2. B = profile(EZ).
3. `N = Profile(name="New", email=f"new.{TAG}@example.com", user_id=f"new-{TAG}", hashed_password="x")`
4. `db.add(N)` (not flushed).
5. `B.name = "Changed"` (not flushed).
6. The statement recorder.

**When**
- `result = dao.authenticate(db, email=MIXED, password=PW)`.

**Then**
1. returns: `result.id == P.id`.
2. pending: `N in db.new`.
3. pending: `len(db.new) == 1`.
4. session: `B in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. session: `not db.deleted`.
7. statement: `written == []`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| FU-1 (a) — reset and registration use the same matching; registration stores lower-case | `AuthService` (`request_password_reset`, `register_user`), `WorkspaceManager.create_invitation` | a mixed-case reset / register / invitation finds the existing account (BUG-1860, BUG-1861) |
| FU-1 (b) — `ProfileMeUpdate.name` trimmed, never blank (BUG-1406) | `AuthService.update_current_user` | `"  Ann "` stored `"Ann"`, `"   "` refused |
| BUG-1862 listing script for existing case-variant pairs | the fix | not part of this spec |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `create` Inputs | Whether `ProfileCreate.timezone` is optional (has a default) | Not blocking: every card sends `timezone="Asia/Dhaka"`. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_email` | R1 | PRF-GE-01, PRF-GE-02, PRF-GE-08, PRF-GE-09, PRF-GE-14, PRF-GE-15 |
| `get_by_email` | R1a [BUG-1860] | PRF-GE-03, PRF-GE-04, PRF-GE-05, PRF-GE-06, PRF-GE-13; inner text PRF-GE-07, PRF-GE-16, PRF-GE-17 |
| `get_by_email` | R2 | PRF-GE-10, PRF-GE-11 |
| `get_by_email` | Side effects | PRF-GE-12 |
| `create` | R1 | PRF-CR-01, PRF-CR-02, PRF-CR-16 |
| `create` | R2 [BUG-1406] | PRF-CR-04, PRF-CR-05, PRF-CR-06; kept PRF-CR-07 |
| `create` | R3 | PRF-CR-08, PRF-CR-09, PRF-CR-10, PRF-CR-11, PRF-CR-12 |
| `create` | R4 | PRF-CR-13, PRF-CR-14 |
| `create` | R4a [BUG-1861] | PRF-CR-15; working part PRF-CR-16 |
| `create` | R4b [BUG-1862] | PRF-CR-17 |
| `create` | R5 | PRF-CR-18 |
| `create` | Errors: over 72 bytes | PRF-CR-11, PRF-CR-12 |
| `create` | Errors: taken email / user_id | PRF-CR-13, PRF-CR-14 |
| `create` | Errors: dict | PRF-CR-18 |
| `create` | Side effects (flushed, not committed) | PRF-CR-01, PRF-CR-03 |
| `authenticate` | R1 | PRF-AU-01 |
| `authenticate` | R1a [BUG-1860] | PRF-AU-02 |
| `authenticate` | R2 | PRF-AU-03 |
| `authenticate` | R2a [BUG-038] | PRF-AU-04 |
| `authenticate` | R3 | PRF-AU-05, PRF-AU-06, PRF-AU-07, PRF-AU-08 |
| `authenticate` | R4 [BUG-500] | PRF-AU-09; unknown email PRF-AU-10 |
| `authenticate` | R5 | PRF-AU-11 |
