# Test cases — `app/dao/waitlist.py`

> **Spec:** `tests/unit/dao/waitlist.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-03; nothing open). BUG-1410 and BUG-1411 stand from house rules.
> **Revision:** 1 — the spec did not change. Additive, from `waitlist.verify.md` (case-missing Findings 1 … 3; recipes R-1 … R-3): R-1 → WLS-LS-26 … LS-30; R-2 → WLS-LS-31; R-3 → WLS-GE-08. The verifier's correction of the model path in Conventions (`app.models.waitlist_signup`) is kept. LS-15's emails are left as they are (the verifier's note: not required; LS-16 catches a wrong tie-break). No existing card or ID changed; none retired.
> **Counts:** 52 cases · 47 expected-to-pass · 5 expected-to-fail (bugs) · 4 deferred

## Reviewer summary
- **Per callable:** `get_by_email` 8 · `list_signups` 31 (5 bug) · `create_signup` 8 · `update_status` 5.
- **Revision 1:** the status filter gets the full exact-compare set (leading space both sides, `_`, the end of the word, `""`); the search is trimmed on the right too (LS-31); a capitalised stored email is not found by `get_by_email` (GE-08).
- **Depth:** lighter target (skill step 1a). Platform data, no stock, money or order state; plain reads and writes.
- **Expected-to-fail:** BUG-1410 3, strict (today's extra or missing match is deterministic): LS-04 (`_`), LS-05 (`%`), LS-06 (`\`). BUG-1411 2: LS-15 non-strict (the tie itself), LS-16 strict (the SQL recorder). LS-14 is the passing order card (distinct stamps).
- **Commit spies:** CS-08, US-04, one per writer.
- **Notable design choices:**
  - The table is shared and not scoped. Every email carries a per-test `TAG`, every filtered card searches for it, and the "no filter" cards (LS-01, LS-08, LS-09) compare `total` with a count taken at the start (`N0`) and check that the card's rows are in a `limit=1000` page.
  - Rows made in one test share one `created_at`, so order cards give `created_at` explicitly.
  - Exact compare of the email (`get_by_email`): capitals, leading space, a part, `_` on the argument side, a leading space on the stored side. The search's literal rules are the BUG-1410 cards; LS-03 puts the search text in the middle of the email so a "starts with" search fails.
  - The status filter is tested for capitals (stored side) and a part (argument side) only; `update_status` has the 20/21 boundary.
  - No `Author:` lines (caller's instruction). Race simulations: none.
- **Needs a decision:** None blocking. Gap 1 (the model's import path) is assumed.

## Conventions for this module

**IDs.** `WLS` = `app/dao/waitlist.py`. `GE` get_by_email · `LS` list_signups · `CS` create_signup · `US` update_status.

**Actors and fixed values.**
- `dao` = the singleton `waitlist_dao` (`from app.dao.waitlist import waitlist_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns; for `list_signups` it is the tuple, `result[0]` the items, `result[1]` the total.
- `WaitlistSignup` = `app.models.waitlist_signup.WaitlistSignup` (path corrected by the verifier, 2026-11-03; spec gap 1, executor's note). `text` = `sqlalchemy.text`. `datetime`, `timezone` = the `datetime` module's classes. `DataError`, `IntegrityError` = from `sqlalchemy.exc`.
- TAG = `uuid.uuid4().hex[:10]`, once per test (lower-case hex). T1, T2, T3 = `datetime(2026, 3, 1, 9, 0, 0, tzinfo=timezone.utc)`, `datetime(2026, 3, 2, 9, 0, 0, tzinfo=timezone.utc)`, `datetime(2026, 3, 3, 9, 0, 0, tzinfo=timezone.utc)`.
- N0 = `db.execute(text("SELECT count(*) FROM waitlist_signups")).scalar()`, read where the card's Given says.

**Externals.** None. Nothing is mocked (`created_at` is the database's `now()`).

**Given rows.** Rows are inserted directly (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. No workspace is involved.
- **signup** = `WaitlistSignup(email=…, first_name="Zed", last_name="Ray", company_name="Acme", source="landing", ip_hash="h1")`; the card always gives `email`; `wants_product_updates`, `status`, `created_at` are not passed (so `False`, `"PENDING"`, the database's now) unless the card lists them after the word "but".
- A Given line written as code is a step to run exactly as written. `db.add(...)` without `db.flush()` leaves the row pending; an attribute set "(not flushed)" stays an unflushed edit.

**Named checks.**
- **idset(items)** = `{r.id for r in items}`. **ids(items)** = `[r.id for r in items]` (order is part of the check).
- **re-read X** = `db.expire_all()`, then SELECT X by id. **unchanged(X) except `c`** = after re-read, every column of X but `c` equals its value before the call.
- **nothing written** = the number of `waitlist_signups` rows stored equals its value before the call.
- `raises: <DB error>` = `with pytest.raises(<type>) as exc:` then `with db.begin_nested():` then the When; further `raises:` lines assert on `exc.value`, after the block. `raises: TypeError` = plain `pytest.raises(TypeError)`.
- **rolled back** = `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); the first checks run inside the savepoint; then `sp.rollback()` and the "after the savepoint rollback" checks.
- `pending:` / `session:` lines check `db.new`, `db.dirty`, `db.deleted` after the call, before anything expires the session.

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`. The assertion of a non-strict card is never weakened.

**Statement recorder.** The SQL statements the session sends during the When are recorded (a `before_cursor_execute` listener). `sql` = the text of the recorded `SELECT` from `waitlist_signups` that contains `LIMIT` (the page, not the count); `order_part` = the text of `sql` after its first `ORDER BY` and before `LIMIT` (`""` when there is no `ORDER BY`); `written` = every recorded `INSERT`, `UPDATE` or `DELETE`.

**Race simulations.** None in this module.

## `WaitlistDAO.get_by_email`

### WLS-GE-01 — the signup with exactly that email is returned
- **Rules:** `get_by_email` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. B = signup, `email f"amy.{TAG}@x.com"`.
2. A = signup, `email f"zed.{TAG}@x.com"`.

**When**
- `result = dao.get_by_email(db, email=f"zed.{TAG}@x.com")`.

**Then**
1. returns: `isinstance(result, WaitlistSignup)`.
2. returns: `result.id == A.id`.

### WLS-GE-02 — the email in capitals gives None
- **Rules:** `get_by_email` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = signup, `email f"zed.{TAG}@x.com"`.

**When**
- `result = dao.get_by_email(db, email=f"Zed.{TAG}@x.com")`.

**Then**
1. returns: `result is None`.

### WLS-GE-03 — the email with a leading space gives None
- **Rules:** `get_by_email` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = signup, `email f"zed.{TAG}@x.com"`.

**When**
- `result = dao.get_by_email(db, email=f" zed.{TAG}@x.com")`.

**Then**
1. returns: `result is None`.

### WLS-GE-04 — part of an email gives None
- **Rules:** `get_by_email` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = signup, `email f"zed.{TAG}@x.com"`.

**When**
- `result = dao.get_by_email(db, email=f"zed.{TAG}@x")`.

**Then**
1. returns: `result is None`.

### WLS-GE-05 — _ is no wildcard in an email
- **Rules:** `get_by_email` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = signup, `email f"zed.{TAG}@x.com"`.

**When**
- `result = dao.get_by_email(db, email=f"zed_{TAG}@x.com")`.

**Then**
1. returns: `result is None`.

### WLS-GE-06 — a stored email with a leading space is not found without it
- **Rules:** `get_by_email` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = signup, `email f" zed.{TAG}@x.com"`.

**When**
- `result = dao.get_by_email(db, email=f"zed.{TAG}@x.com")`.

**Then**
1. returns: `result is None`.

### WLS-GE-07 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `get_by_email` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = signup, `email f"zed.{TAG}@x.com"`.
2. B = signup, `email f"amy.{TAG}@x.com"`.
3. `P = WaitlistSignup(email=f"pen.{TAG}@x.com", first_name="Pen", last_name="Ray", company_name="Acme", source="landing", ip_hash="h1")`
4. `db.add(P)` (not flushed).
5. `B.status = "CONTACTED"` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_email(db, email=f"zed.{TAG}@x.com")`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. session: `B in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. session: `not db.deleted`.
7. statement: `written == []`.

### WLS-GE-08 — a stored email with capitals is not found by the lower-case one
- **Rules:** `get_by_email` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = signup, `email f"Zed.{TAG}@x.com"`.

**When**
- `result = dao.get_by_email(db, email=f"zed.{TAG}@x.com")`.

**Then**
1. returns: `result is None`.

## `WaitlistDAO.list_signups`

### WLS-LS-01 — with no filter every signup is counted and paged
- **Rules:** `list_signups` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. N0 is read here.
2. A = signup, `email f"zed.{TAG}@x.com"`.
3. B = signup, `email f"amy.{TAG}@x.com"`, but `status "CONTACTED"`.

**When**
- `result = dao.list_signups(db, limit=1000)`.

**Then**
1. returns: `isinstance(result, tuple)`.
2. returns: `isinstance(result[0], list)`.
3. returns: `result[1] == N0 + 2`.
4. returns: `{A.id, B.id} <= idset(result[0])`.

### WLS-LS-02 — the search is trimmed and ignores case
- **Rules:** `list_signups` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = signup, `email f"BIG.{TAG}@Y.ORG"`.
2. B = signup, `email f"small.{TAG}@x.com"`.

**When**
- `result = dao.list_signups(db, search=f" big.{TAG}@")`.

**Then**
1. returns: `ids(result[0]) == [A.id]`.
2. returns: `result[1] == 1`.

### WLS-LS-03 — the search text in the middle of an email finds it
- **Rules:** `list_signups` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = signup, `email f"zed.{TAG}.mid@x.com"`.
2. B = signup, `email f"zed.{TAG}@x.com"`.

**When**
- `result = dao.list_signups(db, search=f"{TAG}.mid")`.

**Then**
1. returns: `ids(result[0]) == [A.id]`.
2. returns: `result[1] == 1`.

### WLS-LS-04 — _ in the search matches only a literal _
- **Rules:** `list_signups` R2 [BUG-1410]
- **Kind:** bug
- **Expect:** xfail BUG-1410
- **Fails today on:** Then 2 (`_` is a wildcard today: B is found too)

**Given**
1. A = signup, `email f"a_b.{TAG}@x.com"`.
2. B = signup, `email f"axb.{TAG}@x.com"`.

**When**
- `result = dao.list_signups(db, search=f"a_b.{TAG}")`.

**Then**
1. returns: `isinstance(result[0], list)`.
2. returns: `ids(result[0]) == [A.id]`.
3. returns: `result[1] == 1`.

### WLS-LS-05 — % in the search matches only a literal %
- **Rules:** `list_signups` R2 [BUG-1410]
- **Kind:** bug
- **Expect:** xfail BUG-1410
- **Fails today on:** Then 2 (`%` is a wildcard today: B is found too)

**Given**
1. A = signup, `email f"p%q.{TAG}@x.com"`.
2. B = signup, `email f"pzzq.{TAG}@x.com"`.

**When**
- `result = dao.list_signups(db, search=f"p%q.{TAG}")`.

**Then**
1. returns: `isinstance(result[0], list)`.
2. returns: `ids(result[0]) == [A.id]`.
3. returns: `result[1] == 1`.

### WLS-LS-06 — a backslash in the search matches only a literal backslash
- **Rules:** `list_signups` R2 [BUG-1410]
- **Kind:** bug
- **Expect:** xfail BUG-1410
- **Fails today on:** Then 2 (the backslash escapes the next character today: B is found, A is not)

**Given**
1. A = signup, `email "c\\d." + TAG + "@x.com"` (one backslash in the stored text).
2. B = signup, `email f"cd.{TAG}@x.com"`.

**When**
- `result = dao.list_signups(db, search="c\\d." + TAG)`.

**Then**
1. returns: `isinstance(result[0], list)`.
2. returns: `ids(result[0]) == [A.id]`.
3. returns: `result[1] == 1`.

### WLS-LS-07 — only the email is searched, not names or company
- **Rules:** `list_signups` R2a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = signup, `email f"zed.{TAG}@x.com"`, but `first_name f"n{TAG}q"`, `last_name f"n{TAG}q"`, `company_name f"n{TAG}q"`.

**When**
- `result = dao.list_signups(db, search=f"n{TAG}q")`.

**Then**
1. returns: `result[0] == []`.
2. returns: `result[1] == 0`.

### WLS-LS-08 — an empty search applies no filter
- **Rules:** `list_signups` R2a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N0 is read here.
2. A = signup, `email f"zed.{TAG}@x.com"`.
3. B = signup, `email f"amy.{TAG}@x.com"`.

**When**
- `result = dao.list_signups(db, search="", limit=1000)`.

**Then**
1. returns: `result[1] == N0 + 2`.
2. returns: `{A.id, B.id} <= idset(result[0])`.

### WLS-LS-09 — a search of only spaces matches every row
- **Rules:** `list_signups` R2a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N0 is read here.
2. A = signup, `email f"zed.{TAG}@x.com"`.
3. B = signup, `email f"amy.{TAG}@x.com"`.

**When**
- `result = dao.list_signups(db, search="   ", limit=1000)`.

**Then**
1. returns: `result[1] == N0 + 2`.
2. returns: `{A.id, B.id} <= idset(result[0])`.

### WLS-LS-10 — wants_product_updates=False keeps only rows with False
- **Rules:** `list_signups` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = signup, `email f"zed.{TAG}@x.com"`, but `wants_product_updates True`.
2. B = signup, `email f"amy.{TAG}@x.com"`, but `wants_product_updates False`.

**When**
- `result = dao.list_signups(db, search=TAG, wants_product_updates=False)`.

**Then**
1. returns: `ids(result[0]) == [B.id]`.
2. returns: `result[1] == 1`.

### WLS-LS-11 — wants_product_updates=True keeps only rows with True
- **Rules:** `list_signups` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = signup, `email f"zed.{TAG}@x.com"`, but `wants_product_updates True`.
2. B = signup, `email f"amy.{TAG}@x.com"`, but `wants_product_updates False`.

**When**
- `result = dao.list_signups(db, search=TAG, wants_product_updates=True)`.

**Then**
1. returns: `ids(result[0]) == [A.id]`.
2. returns: `result[1] == 1`.

### WLS-LS-12 — status keeps rows with exactly that text, case-sensitive
- **Rules:** `list_signups` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = signup, `email f"zed.{TAG}@x.com"`, but `status "CONTACTED"`.
2. B = signup, `email f"amy.{TAG}@x.com"`, but `status "contacted"`.

**When**
- `result = dao.list_signups(db, search=TAG, status="contacted")`.

**Then**
1. returns: `ids(result[0]) == [B.id]`.
2. returns: `result[1] == 1`.

### WLS-LS-13 — part of a status finds nothing
- **Rules:** `list_signups` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. B = signup, `email f"amy.{TAG}@x.com"`, but `status "contacted"`.

**When**
- `result = dao.list_signups(db, search=TAG, status="contact")`.

**Then**
1. returns: `result[0] == []`.
2. returns: `result[1] == 0`.

### WLS-LS-14 — newest first by created_at, whatever the ids
- **Rules:** `list_signups` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = signup, `email f"a.{TAG}@x.com"`, but `created_at T2`.
2. B = signup, `email f"b.{TAG}@x.com"`, but `created_at T3`.
3. C = signup, `email f"c.{TAG}@x.com"`, but `created_at T1`.

**When**
- `result = dao.list_signups(db, search=TAG)`.

**Then**
1. returns: `ids(result[0]) == [B.id, A.id, C.id]`.

### WLS-LS-15 — on a tie the higher id comes first, also after the lowest id was updated
- **Rules:** `list_signups` R5 [BUG-1411]
- **Kind:** bug
- **Expect:** xfail BUG-1411 (non-strict)
- **Fails today on:** Then 2 (no order among tied rows; physical order puts the updated row last)

**Given**
1. A = signup, `email f"a.{TAG}@x.com"`, but `created_at T2`.
2. B = signup, `email f"b.{TAG}@x.com"`, but `created_at T2`.
3. C = signup, `email f"c.{TAG}@x.com"`, but `created_at T2`.
4. `A.first_name = "Amy"`, then `db.flush()`.
5. `db.expire_all()`

**When**
- `result = dao.list_signups(db, search=TAG)`.

**Then**
1. returns: `len(result[0]) == 3`.
2. returns: `ids(result[0]) == [C.id, B.id, A.id]`.

### WLS-LS-16 — the query orders by created_at, then id, both descending
- **Rules:** `list_signups` R5 [BUG-1411]
- **Kind:** bug
- **Expect:** xfail BUG-1411
- **Fails today on:** Then 4 (the query orders by `created_at` alone)

**Given**
1. A = signup, `email f"a.{TAG}@x.com"`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.list_signups(db, search=TAG)`.

**Then**
1. returns: `ids(result[0]) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"created_at" in order_part`.
4. statement: `".id" in order_part`.
5. statement: `order_part.index("created_at") < order_part.index(".id")`.
6. statement: `order_part.upper().count("DESC") == 2`.
7. statement: `order_part.count(",") == 1`.

### WLS-LS-17 — total counts every match, not only the page
- **Rules:** `list_signups` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = signup, `email f"a.{TAG}@x.com"`, but `created_at T3`.
2. B = signup, `email f"b.{TAG}@x.com"`, but `created_at T2`.
3. C = signup, `email f"c.{TAG}@x.com"`, but `created_at T1`.

**When**
- `result = dao.list_signups(db, search=TAG, skip=1, limit=1)`.

**Then**
1. returns: `ids(result[0]) == [B.id]`.
2. returns: `result[1] == 3`.

### WLS-LS-18 — limit=0 gives an empty page with the total
- **Rules:** `list_signups` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = signup, `email f"a.{TAG}@x.com"`.
2. B = signup, `email f"b.{TAG}@x.com"`.

**When**
- `result = dao.list_signups(db, search=TAG, limit=0)`.

**Then**
1. returns: `result[0] == []`.
2. returns: `result[1] == 2`.

### WLS-LS-19 — with the default limit 101 matches give 100 rows and a total of 101
- **Rules:** `list_signups` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 signups E1 … E101, built with `add_all`: Ek = signup, `email f"e{k}.{TAG}@x.com"`, but `created_at datetime(2026, 3, 1, 9, k // 60, k % 60, tzinfo=timezone.utc)`.
2. `newest` = the ids of E101, E100, … E1, in that order.

**When**
- `result = dao.list_signups(db, search=TAG)`.

**Then**
1. returns: `len(result[0]) == 100`.
2. returns: `result[1] == 101`.
3. returns: `ids(result[0]) == newest[:100]`.

### WLS-LS-20 — limit=1000 gives all 101
- **Rules:** `list_signups` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 signups E1 … E101, built with `add_all`: Ek = signup, `email f"e{k}.{TAG}@x.com"`, but `created_at datetime(2026, 3, 1, 9, k // 60, k % 60, tzinfo=timezone.utc)`.

**When**
- `result = dao.list_signups(db, search=TAG, limit=1000)`.

**Then**
1. returns: `len(result[0]) == 101`.
2. returns: `result[1] == 101`.

### WLS-LS-21 — a negative limit raises DataError 2201W
- **Rules:** `list_signups` R6, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = signup, `email f"a.{TAG}@x.com"`.

**When**
- `dao.list_signups(db, search=TAG, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. nothing written: nothing written.

### WLS-LS-22 — a negative skip raises DataError 2201X
- **Rules:** `list_signups` R6, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = signup, `email f"a.{TAG}@x.com"`.

**When**
- `dao.list_signups(db, search=TAG, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. nothing written: nothing written.

### WLS-LS-23 — filters combine with AND
- **Rules:** `list_signups` R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = signup, `email f"a.{TAG}@x.com"`, but `wants_product_updates True`, `status "CONTACTED"`.
2. B = signup, `email f"b.{TAG}@x.com"`, but `wants_product_updates False`, `status "CONTACTED"`.
3. C = signup, `email f"c.{TAG}@x.com"`, but `wants_product_updates True`.
4. D = signup, `email f"d.other{TAG[:5]}@x.com"`, but `wants_product_updates True`, `status "CONTACTED"`.

**When**
- `result = dao.list_signups(db, search=TAG, wants_product_updates=True, status="CONTACTED")`.

**Then**
1. returns: `ids(result[0]) == [A.id]`.
2. returns: `result[1] == 1`.

### WLS-LS-24 — a filter is applied before the page: a hidden newer row takes no place in it
- **Rules:** `list_signups` R6, R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = signup, `email f"x.{TAG}@x.com"`, but `created_at T3`, `wants_product_updates False`.
2. A = signup, `email f"a.{TAG}@x.com"`, but `created_at T2`, `wants_product_updates True`.
3. B = signup, `email f"b.{TAG}@x.com"`, but `created_at T1`, `wants_product_updates True`.

**When**
- `result = dao.list_signups(db, search=TAG, wants_product_updates=True, skip=1, limit=1)`.

**Then**
1. returns: `ids(result[0]) == [B.id]`.
2. returns: `result[1] == 2`.

### WLS-LS-25 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `list_signups` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = signup, `email f"a.{TAG}@x.com"`.
2. B = signup, `email f"b.other@{TAG}.org"`.
3. `P = WaitlistSignup(email=f"p.{TAG}@x.com", first_name="Pen", last_name="Ray", company_name="Acme", source="landing", ip_hash="h1")`
4. `db.add(P)` (not flushed).
5. `B.status = "CONTACTED"` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.list_signups(db, search=f"a.{TAG}")`.

**Then**
1. returns: `ids(result[0]) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. session: `B in db.dirty`.
6. session: `len(db.dirty) == 1`.
7. session: `not db.deleted`.
8. statement: `written == []`.

### WLS-LS-26 — a status with a leading space finds nothing
- **Rules:** `list_signups` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. B = signup, `email f"amy.{TAG}@x.com"`, but `status "contacted"`.

**When**
- `result = dao.list_signups(db, search=TAG, status=" contacted")`.

**Then**
1. returns: `result == ([], 0)`.

### WLS-LS-27 — _ is no wildcard in a status
- **Rules:** `list_signups` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. B = signup, `email f"amy.{TAG}@x.com"`, but `status "contacted"`.

**When**
- `result = dao.list_signups(db, search=TAG, status="contacte_")`.

**Then**
1. returns: `result == ([], 0)`.

### WLS-LS-28 — the end of a status finds nothing
- **Rules:** `list_signups` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. B = signup, `email f"amy.{TAG}@x.com"`, but `status "contacted"`.

**When**
- `result = dao.list_signups(db, search=TAG, status="tacted")`.

**Then**
1. returns: `result == ([], 0)`.

### WLS-LS-29 — status="" is a filter and finds nothing
- **Rules:** `list_signups` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. B = signup, `email f"amy.{TAG}@x.com"`, but `status "contacted"`.

**When**
- `result = dao.list_signups(db, search=TAG, status="")`.

**Then**
1. returns: `result == ([], 0)`.

### WLS-LS-30 — a stored status with a leading space is not found without it
- **Rules:** `list_signups` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. B = signup, `email f"amy.{TAG}@x.com"`, but `status " contacted"`.

**When**
- `result = dao.list_signups(db, search=TAG, status="contacted")`.

**Then**
1. returns: `result == ([], 0)`.

### WLS-LS-31 — a trailing space in the search is trimmed
- **Rules:** `list_signups` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = signup, `email f"zed.{TAG}.mid@x.com"`.
2. B = signup, `email f"zed.{TAG}@x.com"`.

**When**
- `result = dao.list_signups(db, search=f"{TAG}.mid ")`.

**Then**
1. returns: `ids(result[0]) == [A.id]`.
2. returns: `result[1] == 1`.

## `WaitlistDAO.create_signup`

### WLS-CS-01 — one row with exactly the given values, nothing trimmed; PENDING; an aware created_at
- **Rules:** `create_signup` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. No signup with `email f"new.{TAG}@x.com"`.

**When**
- `result = dao.create_signup(db, email=f"new.{TAG}@x.com", first_name=" Z ", last_name="", company_name="Acme", wants_product_updates=True, source="landing", ip_hash="h1")`.

**Then**
1. returns: `isinstance(result, WaitlistSignup)`.
2. returns: `result.id is not None`.
3. returns: `result.status == "PENDING"`.
4. returns: `result.created_at.tzinfo is not None`.
5. re-read result: `email == f"new.{TAG}@x.com"`, `first_name == " Z "`, `last_name == ""`, `company_name == "Acme"`.
6. re-read result: `wants_product_updates is True`, `source == "landing"`, `ip_hash == "h1"`, `status == "PENDING"`.

### WLS-CS-02 — wants_product_updates=None is stored False
- **Rules:** `create_signup` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No signup with `email f"new.{TAG}@x.com"`.

**When**
- `result = dao.create_signup(db, email=f"new.{TAG}@x.com", first_name="Zed", last_name="Ray", company_name=None, wants_product_updates=None, source=None, ip_hash=None)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `wants_product_updates is False`, `company_name is None`.

### WLS-CS-03 — a taken email raises IntegrityError 23505 and writes nothing
- **Rules:** `create_signup` R3, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = signup, `email f"zed.{TAG}@x.com"`.

**When**
- `dao.create_signup(db, email=f"zed.{TAG}@x.com", first_name="Zed", last_name="Ray", company_name="Acme", wants_product_updates=False, source="landing", ip_hash="h1")`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. nothing written: nothing written.

### WLS-CS-04 — the same email in other capitals is a second row
- **Rules:** `create_signup` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = signup, `email f"zed.{TAG}@x.com"`.

**When**
- `result = dao.create_signup(db, email=f"Zed.{TAG}@x.com", first_name="Zed", last_name="Ray", company_name="Acme", wants_product_updates=False, source="landing", ip_hash="h1")`.

**Then**
1. returns: `result.id != A.id`.
2. re-read result: `email == f"Zed.{TAG}@x.com"`.
3. count: `waitlist_signups` has exactly 2 rows with `lower(email) == f"zed.{TAG}@x.com"`.

### WLS-CS-05 — a first name of 101 characters raises DataError 22001 and writes nothing
- **Rules:** `create_signup` R4, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. No signup with `email f"new.{TAG}@x.com"`.

**When**
- `dao.create_signup(db, email=f"new.{TAG}@x.com", first_name="f" * 101, last_name="Ray", company_name="Acme", wants_product_updates=False, source="landing", ip_hash="h1")`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "22001"`.
3. nothing written: nothing written.

### WLS-CS-06 — a first name of 100 characters is stored whole
- **Rules:** `create_signup` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No signup with `email f"new.{TAG}@x.com"`.

**When**
- `result = dao.create_signup(db, email=f"new.{TAG}@x.com", first_name="f" * 100, last_name="Ray", company_name="Acme", wants_product_updates=False, source="landing", ip_hash="h1")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `first_name == "f" * 100`.

### WLS-CS-07 — leaving out a keyword raises TypeError
- **Rules:** `create_signup` R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. No signup with `email f"new.{TAG}@x.com"`.

**When**
- `dao.create_signup(db, email=f"new.{TAG}@x.com", first_name="Zed", last_name="Ray", company_name="Acme", wants_product_updates=False, source="landing")` (no `ip_hash`), inside `raises: TypeError`.

**Then**
1. raises: `TypeError`.
2. nothing written: nothing written.

### WLS-CS-08 — the row is flushed, not committed
- **Rules:** `create_signup` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No signup with `email f"new.{TAG}@x.com"`.
2. Savepoint and commit spy per **rolled back**.

**When**
- `result = dao.create_signup(db, email=f"new.{TAG}@x.com", first_name="Zed", last_name="Ray", company_name="Acme", wants_product_updates=False, source="landing", ip_hash="h1")`.

**Then**
1. returns: `result.id is not None`.
2. count: inside the savepoint, `waitlist_signups` has exactly 1 row with `email == f"new.{TAG}@x.com"` (raw `SELECT count(*)`).
3. count: after the savepoint rollback, `waitlist_signups` has exactly 0 rows with `email == f"new.{TAG}@x.com"`.
4. mock called: the `db.commit` spy was never called.

## `WaitlistDAO.update_status`

### WLS-US-01 — the status is set and nothing else changes; the same object is returned
- **Rules:** `update_status` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = signup, `email f"zed.{TAG}@x.com"`.

**When**
- `result = dao.update_status(db, signup=S, status="CONTACTED")`.

**Then**
1. returns: `result is S`.
2. re-read S: `status == "CONTACTED"`.
3. unchanged: unchanged(S) except `status`.

### WLS-US-02 — free text of exactly 20 characters is accepted
- **Rules:** `update_status` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = signup, `email f"zed.{TAG}@x.com"`.

**When**
- `result = dao.update_status(db, signup=S, status="w" * 20)`.

**Then**
1. returns: `result is S`.
2. re-read S: `status == "w" * 20`.

### WLS-US-03 — 21 characters raise DataError 22001 and the stored status stays
- **Rules:** `update_status` R2, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. S = signup, `email f"zed.{TAG}@x.com"`.

**When**
- `dao.update_status(db, signup=S, status="w" * 21)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "22001"`.
3. re-read S: `status == "PENDING"`.

### WLS-US-04 — the change is flushed, not committed
- **Rules:** `update_status` R1, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S = signup, `email f"zed.{TAG}@x.com"`.
2. Savepoint and commit spy per **rolled back**.

**When**
- `result = dao.update_status(db, signup=S, status="ACCEPTED")`.

**Then**
1. returns: `result is S`.
2. re-read S: inside the savepoint, `db.execute(text("SELECT status FROM waitlist_signups WHERE id = :id"), {"id": S.id}).scalar() == "ACCEPTED"`.
3. re-read S: after the savepoint rollback, the same `SELECT` gives `"PENDING"`.
4. mock called: the `db.commit` spy was never called.

### WLS-US-05 — the same status again is accepted
- **Rules:** `update_status` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = signup, `email f"zed.{TAG}@x.com"`.

**When**
- `result = dao.update_status(db, signup=S, status="PENDING")`.

**Then**
1. returns: `result is S`.
2. re-read S: `status == "PENDING"`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| FU-1 (a) — HR-1: `"   "` names pass the schema and are stored `""` | `WaitlistSignupRequest` (`app/schemas/waitlist.py`), `WaitlistService.submit_signup` | Schema rule; the DAO stores what it is given (CS-01). |
| FU-1 (b) — any error on an existing email is swallowed | `WaitlistService.submit_signup` | Service rule. |
| Email lower-cased and trimmed before lookup and insert (HR-2) | `WaitlistService.submit_signup` | Here GE-02 and CS-04 hold the DAO's exact behaviour. |
| Inherited `BaseDAO` methods (`get`; `get_by_workspace` raising `AttributeError`) and the singleton | `tests/unit/dao/base.cases.md` | Not repeated here (step 1a). |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Overview / Notes | The model's import path is not given (only the table `waitlist_signups` and the class name `WaitlistSignup`). | Conventions assume `app.models.waitlist.WaitlistSignup`; a different path fails at import in every card. |
| 2 | `list_signups` R2 | How a backslash is matched today is described only as "`\` matched literally" (intended). | WLS-LS-06's "Fails today on" assumes Postgres's default `ILIKE` escape (`\`). If today's result already equals the intended one, the strict xfail will report XPASS; the executor should then report it. |
| 3 | Notes: shared table | Committed rows of other suites may make `N0` large; `limit=1000` must hold every row. | LS-01, LS-08, LS-09 check the card's rows are in the page with `limit=1000`; if the table ever holds more than 998 committed rows they fail. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_email` | Returns | WLS-GE-01 |
| `get_by_email` | R1 | WLS-GE-01, WLS-GE-02, WLS-GE-03, WLS-GE-04, WLS-GE-05, WLS-GE-06, WLS-GE-08 |
| `get_by_email` | Side effects | WLS-GE-07 |
| `list_signups` | Returns | WLS-LS-01 |
| `list_signups` | R1 | WLS-LS-01 |
| `list_signups` | R2 | WLS-LS-02, WLS-LS-03, WLS-LS-31 |
| `list_signups` | R2 [BUG-1410] | WLS-LS-04, WLS-LS-05, WLS-LS-06 |
| `list_signups` | R2a | WLS-LS-07, WLS-LS-08, WLS-LS-09 |
| `list_signups` | R3 | WLS-LS-10, WLS-LS-11 |
| `list_signups` | R4 | WLS-LS-12, WLS-LS-13, WLS-LS-26, WLS-LS-27, WLS-LS-28, WLS-LS-29, WLS-LS-30 |
| `list_signups` | R5 | WLS-LS-14 |
| `list_signups` | R5 [BUG-1411] | WLS-LS-15, WLS-LS-16 |
| `list_signups` | R6 | WLS-LS-17, WLS-LS-18, WLS-LS-19, WLS-LS-20, WLS-LS-21, WLS-LS-22, WLS-LS-24 |
| `list_signups` | R7 | WLS-LS-23, WLS-LS-24 |
| `list_signups` | Errors | WLS-LS-21, WLS-LS-22 |
| `list_signups` | Side effects | WLS-LS-25 |
| `create_signup` | Returns | WLS-CS-01 |
| `create_signup` | R1 | WLS-CS-01 |
| `create_signup` | R2 | WLS-CS-02 |
| `create_signup` | R3 | WLS-CS-03, WLS-CS-04 |
| `create_signup` | R4 | WLS-CS-05, WLS-CS-06 |
| `create_signup` | R5 | WLS-CS-07 |
| `create_signup` | Errors | WLS-CS-03, WLS-CS-05, WLS-CS-07 |
| `create_signup` | Side effects | WLS-CS-08 |
| `update_status` | Returns | WLS-US-01 |
| `update_status` | R1 | WLS-US-01, WLS-US-02, WLS-US-04, WLS-US-05 |
| `update_status` | R2 | WLS-US-03 |
| `update_status` | Errors | WLS-US-03 |
| `update_status` | Side effects | WLS-US-04 |
