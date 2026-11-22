# Test cases — `app/dao/mobile_upload_session.py`

> **Spec:** `tests/unit/dao/mobile_upload_session.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-02; nothing open).
> **Revision:** 1 — the spec did not change. Additive, from `mobile_upload_session.verify.md` (case-missing Findings 1 … 5; recipes R-1 … R-5): R-1 → MUS-T-10 … MUS-T-18; R-2 → two Then lines each on MUS-T-09 and MUS-C-07, and `where` in Conventions; R-3 → MUS-C-08, MUS-C-09; R-4 → MUS-T-19, MUS-C-10; R-5 → one Then line on MUS-M-01, and MUS-M-18. New Then lines are numbered last, so no existing Then number moved. No ID retired.
> **Counts:** 51 cases · 45 expected-to-pass · 6 expected-to-fail (bugs) · 7 deferred

## Reviewer summary
- **Per callable:** `_naive_utc` 4 (2 bug) · `get_by_token_hash` 19 · `get_for_creator` 10 · `mark_expired_if_needed` 18 (4 bug).
- **Depth:** lighter target (skill step 1a) on the two reads; every named boundary of `mark_expired_if_needed` has a card. The method changes one instance in memory and writes no stock, money or order state.
- **Expected-to-fail:** BUG-1282 6, all strict: MUS-N-03, MUS-N-04, MUS-M-13, MUS-M-14, MUS-M-16, MUS-M-17. MUS-N-02 and MUS-M-15 are the passing `UTC` companions.
- **Commit spies:** none. Nothing here writes to the database; MUS-M-08 holds that for the one method that sets a value.
- **Notable design choices:**
  - Stored-row expiry cards set `SET LOCAL TIME ZONE` themselves, and expire the row so `expires_at` comes back in that zone.
  - The `waiting` rows of the two reads are past their time on purpose: neither read expires anything.
  - R3 of `mark_expired_if_needed` (Q2) has one card per status, each thirty days past.
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Revision 1:** MUS-T-10 … MUS-T-18 hold the token to an exact compare; MUS-T-09, MUS-C-07 check that no status or expiry reaches the `WHERE`; MUS-C-08, MUS-C-09 (other rows at the earlier id); MUS-T-19, MUS-C-10 (an unflushed edit stays unflushed); MUS-M-01 and MUS-M-18 (only the status changes).
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `MUS` = `app/dao/mobile_upload_session.py`. `N` _naive_utc · `T` get_by_token_hash · `C` get_for_creator · `M` mark_expired_if_needed.

**Actors and fixed values.**
- `dao` = the singleton `mobile_upload_session_dao` (`from app.dao.mobile_upload_session import mobile_upload_session_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `_naive_utc` = `from app.dao.mobile_upload_session import _naive_utc`. `MobileUploadSession` = `app.models.mobile_upload_session.MobileUploadSession`. `datetime`, `timedelta`, `timezone` = the `datetime` module's classes. `text` = `sqlalchemy.text`.
- MISSING = `999999999`: an id that no row of any table has.
- NOW = `datetime(2026, 3, 5, 12, 0, 0)`, naive. NOW_UTC = `datetime(2026, 3, 5, 12, 0, 0, tzinfo=timezone.utc)`. PAST = `datetime(2026, 3, 4, 12, 0, 0, tzinfo=timezone.utc)`. LATER = `datetime(2026, 3, 6, 12, 0, 0, tzinfo=timezone.utc)`. US = `timedelta(microseconds=1)`. P6 = `timezone(timedelta(hours=6))`, M5 = `timezone(timedelta(hours=-5))`. TK1 = `"a" * 64`, TK2 = `"b" * 64`.

**Externals.** `app.dao.mobile_upload_session.utcnow`, patched with `patch("app.dao.mobile_upload_session.utcnow", return_value=NOW)` around the When of every card whose Given says so. No other card reads the clock.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from these defaults.
- These rows exist in every test and need no Given line (from `make_workspace`, `make_profile`):
  - W1, W2 = two `workspaces` rows. U1, U2 = two `profiles` rows.
- **session** = `mobile_upload_sessions` row built with `MobileUploadSession`: `workspace_id W1.id`, `created_by U1.id`, `entity_type "purchase_order"`, `entity_id 1`, `token_hash TK1`, `expires_at LATER`; `status`, `delivery_type` are not passed, so `waiting`, `authenticated`. After the word "but" the card lists every other column that differs.
- `S = MobileUploadSession(...)` written as code in a Given is an unsaved instance: never added to the session, no database involved.
- No `mobile_upload_sessions` row exists unless the card's Given lists it.
- A row is read back in the zone of the session. A card that sets `SET LOCAL TIME ZONE` does so before its row.
- A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending. "it is a standing row" means that row is not inserted again; the line only says what it holds.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line).
- **nothing written** = the number of `mobile_upload_sessions` rows stored (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- `pending:` lines check the row P and the session after the call, before anything expires it: `db.new`, `db.dirty`, `db.deleted` as the session holds them. A card lists them ahead of its `nothing written:` and `unchanged:` lines; keep that order.

**xfail cards.** Write the call and the checks exactly as shown. `Expect: xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `xfail BUG-n (non-strict)` = `strict=False`, for a card comparing an order that rests on physical row order. The assertion of a non-strict card is never weakened. Bugs here: BUG-1282.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT` from `mobile_upload_sessions`; `where` = the text of `sql` after its `WHERE`; `order_part` = the text of `sql` after its first `ORDER BY` (`""` when there is none); `selects` = every `SELECT` recorded; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `_naive_utc`

### MUS-N-01 — a naive value comes back unchanged
- **Rules:** `_naive_utc` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `result = _naive_utc(datetime(2026, 1, 1, 0, 0, 0))`.

**Then**
1. returns: `result == datetime(2026, 1, 1, 0, 0, 0)`.
2. returns: `result.tzinfo is None`.

### MUS-N-02 — a +00:00 value keeps its clock time and loses its zone
- **Rules:** `_naive_utc` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `result = _naive_utc(datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc))`.

**Then**
1. returns: `result == datetime(2026, 1, 1, 0, 0, 0)`.
2. returns: `result.tzinfo is None`.

### MUS-N-03 — a +06:00 value is converted to UTC
- **Rules:** `_naive_utc` R2 [BUG-1282]
- **Kind:** bug
- **Expect:** xfail BUG-1282
- **Fails today on:** Then 2 (the zone is removed with no conversion: `2026-01-01 00:00`)

**Given**
1. No row beyond the standing rows.

**When**
- `result = _naive_utc(datetime(2026, 1, 1, 0, 0, 0, tzinfo=P6))`.

**Then**
1. returns: `result.tzinfo is None`.
2. returns: `result == datetime(2025, 12, 31, 18, 0, 0)`.

### MUS-N-04 — a -05:00 value is converted to UTC
- **Rules:** `_naive_utc` R2 [BUG-1282]
- **Kind:** bug
- **Expect:** xfail BUG-1282
- **Fails today on:** Then 2 (the zone is removed with no conversion: `2026-01-01 08:00`)

**Given**
1. No row beyond the standing rows.

**When**
- `result = _naive_utc(datetime(2026, 1, 1, 8, 0, 0, tzinfo=M5))`.

**Then**
1. returns: `result.tzinfo is None`.
2. returns: `result == datetime(2026, 1, 1, 13, 0, 0)`.


## `MobileUploadSessionDAO.get_by_token_hash`

### MUS-T-01 — returns the row with exactly that hash, not the first row
- **Rules:** `get_by_token_hash` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = session.
2. B = session, but `token_hash TK2`.

**When**
- `result = dao.get_by_token_hash(db, token_hash=TK2)`.

**Then**
1. returns: `result.id == B.id`.
2. returns: `isinstance(result, MobileUploadSession)`.

### MUS-T-02 — a session of another workspace is returned: no workspace filter, by design
- **Rules:** `get_by_token_hash` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = session, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_token_hash(db, token_hash=TK1)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.workspace_id == W2.id`.

### MUS-T-03 — an unknown hash returns None and nothing is created
- **Rules:** `get_by_token_hash` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = session.

**When**
- `result = dao.get_by_token_hash(db, token_hash=TK2)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### MUS-T-04 — an empty hash returns None
- **Rules:** `get_by_token_hash` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = session.

**When**
- `result = dao.get_by_token_hash(db, token_hash="")`.

**Then**
1. returns: `result is None`.

### MUS-T-05 — the hash in another case returns None
- **Rules:** `get_by_token_hash` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = session.

**When**
- `result = dao.get_by_token_hash(db, token_hash=TK1.upper())`.

**Then**
1. returns: `result is None`.

### MUS-T-06 — a cancelled session past its time is returned
- **Rules:** `get_by_token_hash` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = session, but `status "cancelled"`, `expires_at PAST`.

**When**
- `result = dao.get_by_token_hash(db, token_hash=TK1)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.status == "cancelled"`.

### MUS-T-07 — an expired session is returned
- **Rules:** `get_by_token_hash` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = session, but `status "expired"`, `expires_at PAST`.

**When**
- `result = dao.get_by_token_hash(db, token_hash=TK1)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.status == "expired"`.

### MUS-T-08 — a waiting session past its time is returned, still waiting
- **Rules:** `get_by_token_hash` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = session, but `expires_at PAST`.

**When**
- `result = dao.get_by_token_hash(db, token_hash=TK1)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.status == "waiting"`.

### MUS-T-09 — writes nothing: a read that finds its session leaves the session object as it was
- **Rules:** `get_by_token_hash` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = session.
2. `P = MobileUploadSession(workspace_id=W1.id, created_by=U1.id, entity_type="purchase_order", entity_id=1, token_hash=TK2, expires_at=LATER)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_token_hash(db, token_hash=TK1)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. pending: `not db.dirty`.
6. pending: `not db.deleted`.
7. statement: `written == []`.
8. statement: `len(selects) == 1`.
9. statement: `"FOR UPDATE" not in sql.upper()`.
10. nothing written: nothing written.
11. unchanged: unchanged(A).
12. statement: `"status" not in where`.
13. statement: `"expires_at" not in where`.

### MUS-T-10 — token_hash="a" * 63 returns None: the compare is exact
- **Rules:** `get_by_token_hash` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = session.

**When**
- `result = dao.get_by_token_hash(db, token_hash="a" * 63)`.

**Then**
1. returns: `result is None`.

### MUS-T-11 — token_hash=" " + "a" * 64 returns None: the compare is exact
- **Rules:** `get_by_token_hash` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = session.

**When**
- `result = dao.get_by_token_hash(db, token_hash=" " + "a" * 64)`.

**Then**
1. returns: `result is None`.

### MUS-T-12 — token_hash="a" * 64 + " " returns None: the compare is exact
- **Rules:** `get_by_token_hash` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = session.

**When**
- `result = dao.get_by_token_hash(db, token_hash="a" * 64 + " ")`.

**Then**
1. returns: `result is None`.

### MUS-T-13 — token_hash="a%" returns None: the compare is exact
- **Rules:** `get_by_token_hash` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = session.

**When**
- `result = dao.get_by_token_hash(db, token_hash="a%")`.

**Then**
1. returns: `result is None`.

### MUS-T-14 — token_hash="a" * 63 + "_" returns None: the compare is exact
- **Rules:** `get_by_token_hash` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = session.

**When**
- `result = dao.get_by_token_hash(db, token_hash="a" * 63 + "_")`.

**Then**
1. returns: `result is None`.

### MUS-T-15 — a stored hash "A" * 64 is not found by "a" * 64
- **Rules:** `get_by_token_hash` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = session, but `token_hash "A" * 64`.

**When**
- `result = dao.get_by_token_hash(db, token_hash="a" * 64)`.

**Then**
1. returns: `result is None`.

### MUS-T-16 — a stored hash " " + "a" * 63 is not found by "a" * 63
- **Rules:** `get_by_token_hash` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = session, but `token_hash " " + "a" * 63`.

**When**
- `result = dao.get_by_token_hash(db, token_hash="a" * 63)`.

**Then**
1. returns: `result is None`.

### MUS-T-17 — a stored hash "a" * 63 + " " is not found by "a" * 63
- **Rules:** `get_by_token_hash` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = session, but `token_hash "a" * 63 + " "`.

**When**
- `result = dao.get_by_token_hash(db, token_hash="a" * 63)`.

**Then**
1. returns: `result is None`.

### MUS-T-18 — a stored hash "xy" + "a" * 62 is not found by "a" * 62
- **Rules:** `get_by_token_hash` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = session, but `token_hash "xy" + "a" * 62`.

**When**
- `result = dao.get_by_token_hash(db, token_hash="a" * 62)`.

**Then**
1. returns: `result is None`.

### MUS-T-19 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded
- **Rules:** `get_by_token_hash` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = session.
2. B = session, but `token_hash TK2`.
3. `B.status = "cancelled"` (not flushed).

**When**
- `result = dao.get_by_token_hash(db, token_hash=TK1)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `B in db.dirty`.
3. pending: `len(db.dirty) == 1`.
4. pending: `B.status == "cancelled"`.


## `MobileUploadSessionDAO.get_for_creator`

### MUS-C-01 — returns the row matching id, workspace and creator, not the first row
- **Rules:** `get_for_creator` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = session.
2. B = session, but `token_hash TK2`.

**When**
- `result = dao.get_for_creator(db, session_id=B.id, workspace_id=W1.id, created_by=U1.id)`.

**Then**
1. returns: `result.id == B.id`.
2. returns: `isinstance(result, MobileUploadSession)`.

### MUS-C-02 — another workspace returns None
- **Rules:** `get_for_creator` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = session.

**When**
- `result = dao.get_for_creator(db, session_id=A.id, workspace_id=W2.id, created_by=U1.id)`.

**Then**
1. returns: `result is None`.

### MUS-C-03 — another user of the same workspace returns None
- **Rules:** `get_for_creator` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = session.

**When**
- `result = dao.get_for_creator(db, session_id=A.id, workspace_id=W1.id, created_by=U2.id)`.

**Then**
1. returns: `result is None`.

### MUS-C-04 — an unknown id returns None and nothing is created
- **Rules:** `get_for_creator` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = session.

**When**
- `result = dao.get_for_creator(db, session_id=MISSING, workspace_id=W1.id, created_by=U1.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### MUS-C-05 — a cancelled session past its time is returned
- **Rules:** `get_for_creator` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = session, but `status "cancelled"`, `expires_at PAST`.

**When**
- `result = dao.get_for_creator(db, session_id=A.id, workspace_id=W1.id, created_by=U1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.status == "cancelled"`.

### MUS-C-06 — a waiting session past its time is returned, still waiting
- **Rules:** `get_for_creator` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = session, but `expires_at PAST`.

**When**
- `result = dao.get_for_creator(db, session_id=A.id, workspace_id=W1.id, created_by=U1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.status == "waiting"`.

### MUS-C-07 — writes nothing: a read that finds its session leaves the session object as it was
- **Rules:** `get_for_creator` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = session.
2. `P = MobileUploadSession(workspace_id=W1.id, created_by=U1.id, entity_type="purchase_order", entity_id=1, token_hash=TK2, expires_at=LATER)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_for_creator(db, session_id=A.id, workspace_id=W1.id, created_by=U1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. pending: `not db.dirty`.
6. pending: `not db.deleted`.
7. statement: `written == []`.
8. statement: `len(selects) == 1`.
9. statement: `"FOR UPDATE" not in sql.upper()`.
10. nothing written: nothing written.
11. unchanged: unchanged(A).
12. statement: `"status" not in where`.
13. statement: `"expires_at" not in where`.

### MUS-C-08 — a W2 session at the earlier id is not returned for W1
- **Rules:** `get_for_creator` R2, R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = session, but `workspace_id W2.id`.
2. A = session, but `token_hash TK2`.

**When**
- `result = dao.get_for_creator(db, session_id=Z.id, workspace_id=W1.id, created_by=U1.id)`.

**Then**
1. returns: `result is None`.

### MUS-C-09 — another user's session at the earlier id is not returned
- **Rules:** `get_for_creator` R2, R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = session, but `created_by U2.id`.
2. A = session, but `token_hash TK2`.

**When**
- `result = dao.get_for_creator(db, session_id=Z.id, workspace_id=W1.id, created_by=U1.id)`.

**Then**
1. returns: `result is None`.

### MUS-C-10 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded
- **Rules:** `get_for_creator` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = session.
2. B = session, but `token_hash TK2`.
3. `B.status = "cancelled"` (not flushed).

**When**
- `result = dao.get_for_creator(db, session_id=A.id, workspace_id=W1.id, created_by=U1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `B in db.dirty`.
3. pending: `len(db.dirty) == 1`.
4. pending: `B.status == "cancelled"`.


## `MobileUploadSessionDAO.mark_expired_if_needed`

### MUS-M-01 — a waiting session past its time becomes expired, on the same instance
- **Rules:** `mark_expired_if_needed` R1, Returns, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. `mark_expired_if_needed` runs with `utcnow` patched to NOW.
2. `S = MobileUploadSession(status="waiting", expires_at=NOW - timedelta(minutes=1))`

**When**
- `result = dao.mark_expired_if_needed(S)`.

**Then**
1. returns: `result is S`.
2. returns: `S.status == "expired"`.
3. returns: `S.expires_at == NOW - timedelta(minutes=1)`.

### MUS-M-02 — expires_at exactly now becomes expired
- **Rules:** `mark_expired_if_needed` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `mark_expired_if_needed` runs with `utcnow` patched to NOW.
2. `S = MobileUploadSession(status="waiting", expires_at=NOW)`

**When**
- `result = dao.mark_expired_if_needed(S)`.

**Then**
1. returns: `result is S`.
2. returns: `S.status == "expired"`.

### MUS-M-03 — expires_at one microsecond later stays waiting
- **Rules:** `mark_expired_if_needed` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `mark_expired_if_needed` runs with `utcnow` patched to NOW.
2. `S = MobileUploadSession(status="waiting", expires_at=NOW + US)`

**When**
- `result = dao.mark_expired_if_needed(S)`.

**Then**
1. returns: `result is S`.
2. returns: `S.status == "waiting"`.

### MUS-M-04 — an uploaded session far past its time is left as it is
- **Rules:** `mark_expired_if_needed` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `mark_expired_if_needed` runs with `utcnow` patched to NOW.
2. `S = MobileUploadSession(status="uploaded", expires_at=NOW - timedelta(days=30))`

**When**
- `result = dao.mark_expired_if_needed(S)`.

**Then**
1. returns: `result is S`.
2. returns: `S.status == "uploaded"`.

### MUS-M-05 — a consumed session far past its time is left as it is
- **Rules:** `mark_expired_if_needed` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `mark_expired_if_needed` runs with `utcnow` patched to NOW.
2. `S = MobileUploadSession(status="consumed", expires_at=NOW - timedelta(days=30))`

**When**
- `result = dao.mark_expired_if_needed(S)`.

**Then**
1. returns: `result is S`.
2. returns: `S.status == "consumed"`.

### MUS-M-06 — a cancelled session far past its time is left as it is
- **Rules:** `mark_expired_if_needed` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `mark_expired_if_needed` runs with `utcnow` patched to NOW.
2. `S = MobileUploadSession(status="cancelled", expires_at=NOW - timedelta(days=30))`

**When**
- `result = dao.mark_expired_if_needed(S)`.

**Then**
1. returns: `result is S`.
2. returns: `S.status == "cancelled"`.

### MUS-M-07 — an expired session far past its time is left as it is
- **Rules:** `mark_expired_if_needed` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `mark_expired_if_needed` runs with `utcnow` patched to NOW.
2. `S = MobileUploadSession(status="expired", expires_at=NOW - timedelta(days=30))`

**When**
- `result = dao.mark_expired_if_needed(S)`.

**Then**
1. returns: `result is S`.
2. returns: `S.status == "expired"`.

### MUS-M-08 — nothing is written: the row is dirty in the session, and a query still reads waiting
- **Rules:** `mark_expired_if_needed` R4, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'UTC'"))`
2. `mark_expired_if_needed` runs with `utcnow` patched to NOW.
3. S = session, but `expires_at PAST`.
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.mark_expired_if_needed(S)`.

**Then**
1. returns: `result is S`.
2. returns: `S.status == "expired"`.
3. pending: `S in db.dirty`.
4. statement: `written == []`.
5. re-read S by raw SQL, with no flush: `db.scalar(text("SELECT status FROM mobile_upload_sessions WHERE id = :i"), {"i": S.id}) == "waiting"`.

### MUS-M-09 — a naive value past its time becomes expired
- **Rules:** `mark_expired_if_needed` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `mark_expired_if_needed` runs with `utcnow` patched to NOW.
2. `S = MobileUploadSession(status="waiting", expires_at=datetime(2026, 3, 5, 11, 59, 59))`

**When**
- `result = dao.mark_expired_if_needed(S)`.

**Then**
1. returns: `result is S`.
2. returns: `S.status == "expired"`.

### MUS-M-10 — a naive value later than now stays waiting
- **Rules:** `mark_expired_if_needed` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `mark_expired_if_needed` runs with `utcnow` patched to NOW.
2. `S = MobileUploadSession(status="waiting", expires_at=datetime(2026, 3, 5, 12, 0, 1))`

**When**
- `result = dao.mark_expired_if_needed(S)`.

**Then**
1. returns: `result is S`.
2. returns: `S.status == "waiting"`.

### MUS-M-11 — a UTC value exactly now becomes expired
- **Rules:** `mark_expired_if_needed` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `mark_expired_if_needed` runs with `utcnow` patched to NOW.
2. `S = MobileUploadSession(status="waiting", expires_at=datetime(2026, 3, 5, 12, 0, 0, tzinfo=timezone.utc))`

**When**
- `result = dao.mark_expired_if_needed(S)`.

**Then**
1. returns: `result is S`.
2. returns: `S.status == "expired"`.

### MUS-M-12 — a UTC value one microsecond later stays waiting
- **Rules:** `mark_expired_if_needed` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `mark_expired_if_needed` runs with `utcnow` patched to NOW.
2. `S = MobileUploadSession(status="waiting", expires_at=datetime(2026, 3, 5, 12, 0, 0, 1, tzinfo=timezone.utc))`

**When**
- `result = dao.mark_expired_if_needed(S)`.

**Then**
1. returns: `result is S`.
2. returns: `S.status == "waiting"`.

### MUS-M-13 — a +06:00 value past its true moment becomes expired
- **Rules:** `mark_expired_if_needed` R5a [BUG-1282]
- **Kind:** bug
- **Expect:** xfail BUG-1282
- **Fails today on:** Then 2 (compared by clock time, 17:59:59 against 12:00, so it stays `waiting`)

**Given**
1. `mark_expired_if_needed` runs with `utcnow` patched to NOW.
2. `S = MobileUploadSession(status="waiting", expires_at=datetime(2026, 3, 5, 17, 59, 59, tzinfo=P6))`

**When**
- `result = dao.mark_expired_if_needed(S)`.

**Then**
1. returns: `result is S`.
2. returns: `S.status == "expired"`.

### MUS-M-14 — a -05:00 value before its true moment stays waiting
- **Rules:** `mark_expired_if_needed` R5a [BUG-1282]
- **Kind:** bug
- **Expect:** xfail BUG-1282
- **Fails today on:** Then 2 (compared by clock time, 08:00 against 12:00, so it becomes `expired`)

**Given**
1. `mark_expired_if_needed` runs with `utcnow` patched to NOW.
2. `S = MobileUploadSession(status="waiting", expires_at=datetime(2026, 3, 5, 8, 0, 0, tzinfo=M5))`

**When**
- `result = dao.mark_expired_if_needed(S)`.

**Then**
1. returns: `result is S`.
2. returns: `S.status == "waiting"`.

### MUS-M-15 — a row read back under UTC compares by its true moment
- **Rules:** `mark_expired_if_needed` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'UTC'"))`
2. `mark_expired_if_needed` runs with `utcnow` patched to NOW.
3. S = session, but `expires_at NOW_UTC - timedelta(seconds=1)`.
4. `db.expire_all()`.

**When**
- `result = dao.mark_expired_if_needed(S)`.

**Then**
1. returns: `result is S`.
2. returns: `S.status == "expired"`.

### MUS-M-16 — a row read back under Asia/Dhaka past its true moment becomes expired
- **Rules:** `mark_expired_if_needed` R5a [BUG-1282]
- **Kind:** bug
- **Expect:** xfail BUG-1282
- **Fails today on:** Then 2 (read back as 17:59:59+06:00 and compared by clock time, so it stays `waiting`)

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))`
2. `mark_expired_if_needed` runs with `utcnow` patched to NOW.
3. S = session, but `expires_at NOW_UTC - timedelta(seconds=1)`.
4. `db.expire_all()`.

**When**
- `result = dao.mark_expired_if_needed(S)`.

**Then**
1. returns: `result is S`.
2. returns: `S.status == "expired"`.

### MUS-M-17 — a row read back under America/New_York before its true moment stays waiting
- **Rules:** `mark_expired_if_needed` R5a [BUG-1282]
- **Kind:** bug
- **Expect:** xfail BUG-1282
- **Fails today on:** Then 2 (read back as 08:00-05:00 and compared by clock time, so it becomes `expired`)

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))`
2. `mark_expired_if_needed` runs with `utcnow` patched to NOW.
3. S = session, but `expires_at NOW_UTC + timedelta(hours=1)`.
4. `db.expire_all()`.

**When**
- `result = dao.mark_expired_if_needed(S)`.

**Then**
1. returns: `result is S`.
2. returns: `S.status == "waiting"`.

### MUS-M-18 — only the status changes: a pending row of the caller is left alone
- **Rules:** `mark_expired_if_needed` R4, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'UTC'"))`
2. `mark_expired_if_needed` runs with `utcnow` patched to NOW.
3. A = session, but `expires_at PAST`.
4. `P = MobileUploadSession(workspace_id=W1.id, created_by=U1.id, entity_type="purchase_order", entity_id=1, token_hash=TK2, expires_at=LATER)`
5. `db.add(P)` (not flushed).

**When**
- `result = dao.mark_expired_if_needed(A)`.

**Then**
1. returns: `result is A`.
2. returns: `A.status == "expired"`.
3. pending: `P in db.new`.
4. pending: `P.id is None`.
5. pending: `len(db.new) == 1`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `_naive_utc` R2, `mark_expired_if_needed` R5a — BUG-1282, the write side: `create_session` writes `expires_at` as aware UTC | `MobileUploadSessionManager.create_session` (spec FU-2) | The manager's spec carries the write rule and the tag. |
| `_naive_utc` — `_ensure_active` follows R2 | `MobileUploadSessionManager._ensure_active` (spec FU-2) | It imports `_naive_utc`, so it follows R2 here. |
| `mark_expired_if_needed` R3 (Q2) — the phone's path answers "Upload session has expired." for an `uploaded` session past its time | `MobileUploadSessionManager._ensure_active` | Here the desktop's side only. |
| Spec FU-1 (a) — `expired` set in memory, no commit follows, so the row stays `waiting` | `MobileUploadSessionManager.get_for_creator`, `_ensure_active` | A consequence for any report that reads the column; here R4. |
| Spec FU-1 (b) — `delivery_type` NOT NULL in the model, nullable in the database | `MobileUploadSessionManager`, the migrations | Not a rule of this DAO. |
| Overview — inherited `create` with a plain dict | `tests/unit/dao/base.spec.md` | Generic behavior, not repeated. |
| Module singleton | none (no logic) | Only used as the entry point of every card. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Model facts | `status` values are spelled in the rules. `entity_type`, `entity_id` take no named value; `"purchase_order"` follows `tests/test_mobile_upload.py`. | Conventions use it. |
| 2 | `_naive_utc` | `None` as input is not specified. | No card. |
| 3 | `mark_expired_if_needed` R5a | The rule gives unsaved values only. MUS-M-16, MUS-M-17 carry the same two moments through a stored row, as the spec's Q1 describes. | Designed; they fail today for the same reason. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_naive_utc` | Returns | MUS-N-01 |
| `_naive_utc` | R1 | MUS-N-01 |
| `_naive_utc` | R2 | MUS-N-02 |
| `_naive_utc` | R2 [BUG-1282] | MUS-N-03, MUS-N-04 |
| `get_by_token_hash` | Returns | MUS-T-01 |
| `get_by_token_hash` | R1 | MUS-T-01, MUS-T-02 |
| `get_by_token_hash` | R2 | MUS-T-03, MUS-T-04, MUS-T-05, MUS-T-10, MUS-T-11, MUS-T-12, MUS-T-13, MUS-T-14, MUS-T-15, MUS-T-16, MUS-T-17, MUS-T-18 |
| `get_by_token_hash` | R3 | MUS-T-06, MUS-T-07, MUS-T-08 |
| `get_by_token_hash` | Side effects | MUS-T-09, MUS-T-19 |
| `get_for_creator` | Returns | MUS-C-01 |
| `get_for_creator` | R1 | MUS-C-01, MUS-C-08, MUS-C-09 |
| `get_for_creator` | R2 | MUS-C-02, MUS-C-03, MUS-C-04, MUS-C-08, MUS-C-09 |
| `get_for_creator` | R3 | MUS-C-05, MUS-C-06 |
| `get_for_creator` | Side effects | MUS-C-07, MUS-C-10 |
| `mark_expired_if_needed` | Returns | MUS-M-01 |
| `mark_expired_if_needed` | R1 | MUS-M-01 |
| `mark_expired_if_needed` | R2 | MUS-M-02, MUS-M-03 |
| `mark_expired_if_needed` | R3 | MUS-M-04, MUS-M-05, MUS-M-06, MUS-M-07 |
| `mark_expired_if_needed` | R4 | MUS-M-08, MUS-M-18 |
| `mark_expired_if_needed` | R5 | MUS-M-09, MUS-M-10, MUS-M-11, MUS-M-12, MUS-M-15 |
| `mark_expired_if_needed` | R5a [BUG-1282] | MUS-M-13, MUS-M-14, MUS-M-16, MUS-M-17 |
| `mark_expired_if_needed` | Side effects | MUS-M-01, MUS-M-08, MUS-M-18 |
