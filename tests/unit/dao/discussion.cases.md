# Test cases — `app/dao/discussion.py`

> **Spec:** `tests/unit/dao/discussion.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-03; nothing open). P1 was decided by Claude under the reviewer's delegation.
> **Revision:** 1 — the spec now tags R6 with BUG-1490 as well as BUG-1439. Additive, from `discussion.verify.md` (case-missing Findings 1 … 4; recipes R-1 … R-4): R-1 → DSC-GE-31; R-2 → DSC-GE-32; R-3 → DSC-GE-33; R-4 → DSC-CR-11. DSC-GE-26's Rules line names BUG-1490 too (its Expect and Fails lines were updated at the coordinator's request); the matrix gives it its own row `R6 [BUG-1439] [BUG-1490]`. No other card changed; no ID retired.
> **Counts:** 52 cases · 46 expected-to-pass · 6 expected-to-fail (bugs) · 7 deferred

## Reviewer summary
- **Per callable:** `get_by_entity` 33 (6 bug) · `get_by_id` 8 · `create` 11.
- **Depth:** lighter target (skill step 1a). Comment threads: one paged read with its count and loaded replies, one by-id read, one insert; no stock, money or order state.
- **Expected-to-fail:** BUG-1438 3: DSC-GE-19, GE-20 non-strict, GE-21 strict (the page's SQL). BUG-1439 3: DSC-GE-24, GE-25 non-strict, GE-26 strict (the replies' SQL; it also names BUG-1490, as no replies query is sent with the page today). DSC-GE-17, GE-18, GE-27 are the passing companions.
- **Commit spies:** `create` 1 (DSC-CR-10).
- **Notable design choices:**
  - Posts of one transaction share `created_at`; order cards use `older`, and the older row has the higher id where it matters.
  - Exact compare of `entity_type`: capitals, a part and `_` on the argument side, a leading space on the stored side.
  - Both filter-before-paging cards (a reply, another entity) put the hidden row oldest, so it would take the skipped place.
  - Cards that read `replies` expire the session in their Given, so the call loads them fresh.
  - Positional calls are used once per callable, as the spec allows them.
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `DSC` = `app/dao/discussion.py`. `GE` get_by_entity · `GI` get_by_id · `CR` create.

**Actors and fixed values.**
- `dao` = the singleton `discussion_dao` (`from app.dao.discussion import discussion_dao`). `db` = the test's real database session, always the first argument; other arguments are passed by keyword unless the card says "positionally". `result` = what the When call returns.
- `Discussion` = `app.models.discussion.Discussion`. `IntegrityError`, `DataError` = `sqlalchemy.exc` classes. `text` = `sqlalchemy.text`.
- MISSING = `999999999`: an id that no row of any table has.

**Externals.** None. Nothing is mocked. `created_at` comes from the database.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from these defaults.
- These rows exist in every test and need no Given line: W1, W2 = two `workspaces` rows (`make_workspace`); U1 = a `profiles` row (`make_profile`).
- **msg** = `Discussion(workspace_id=W1.id, entity_type="project", entity_id=501, user_id=U1.id, message="Hello")`; after "but" the card lists every column that differs. **reply on X** = msg, but `parent_id X.id`. No `discussions` row exists unless the Given lists it. No project 501 exists, nor is one needed.
- **older(X, h)** = `db.execute(text("UPDATE discussions SET created_at = now() - make_interval(hours => :h) WHERE id = :i"), {"h": h, "i": X.id})`, then `db.expire_all()`.
- **bumpD(X)** = `db.execute(text("UPDATE discussions SET message = message || '!' WHERE id = :i"), {"i": X.id})`, then `db.expire_all()`.
- **seqscan** = run, in this order, `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`.
- A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending.

**Named checks.**
- For `get_by_entity`: **items** = `result[0]`, **total** = `result[1]`; **ids(x)** = `[r.id for r in x]` — the order is part of the check; **reply_ids(r)** = `[x.id for x in r.replies]`.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values. **NOW_DB** = `db.scalar(text("SELECT now()"))`.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line).
- **nothing written** = the number of `discussions` rows stored (all workspaces) equals its value before the call.
- `pending:` lines check the session after the call, before anything expires it. A card lists them ahead of its `nothing written:` and `unchanged:` lines.
- `raises: E` (`IntegrityError` or `DataError`) = wrap the call: `with pytest.raises(E) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards. Further `raises:` lines are assertions on `exc.value`, one `assert` per line.
- **rolled back** = `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); "inside the savepoint" checks first; then `sp.rollback()` and the "after the savepoint rollback" checks.

**xfail cards.** `Expect: xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`. The assertion is never weakened.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `page_sql` = the text of the recorded `SELECT` that contains `LIMIT` (the page of roots); `order_part` = the text of `page_sql` after its first `ORDER BY` and before `LIMIT`; `reply_sql` = the text of the recorded `SELECT` that contains `parent_id IN` (the replies' load); `sql` = the text of the one `SELECT` from `discussions` sent by `get_by_id`; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `DiscussionDAO.get_by_entity`

### DSC-GE-01 — returns the record's roots with their replies, and the number of roots
- **Rules:** `get_by_entity` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = msg.
2. B = msg, but `message "Second"`.
3. R = reply on A.
4. `db.expire_all()`

**When**
- `result = dao.get_by_entity(db, workspace_id=W1.id, entity_type="project", entity_id=501)`.

**Then**
1. returns: `isinstance(result, tuple)`.
2. returns: `len(result) == 2`.
3. returns: `isinstance(items, list)`.
4. returns: `isinstance(total, int)`.
5. returns: `set(ids(items)) == {A.id, B.id}`.
6. returns: `total == 2`.
7. returns: `[i for i in items if i.id == A.id][0].replies[0].id == R.id`.

### DSC-GE-02 — a root of another workspace is not matched
- **Rules:** `get_by_entity` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = msg.
2. X = msg, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_entity(db, workspace_id=W1.id, entity_type="project", entity_id=501)`.

**Then**
1. returns: `ids(items) == [A.id]`.
2. returns: `total == 1`.

### DSC-GE-03 — a root of another entity id is not matched
- **Rules:** `get_by_entity` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = msg.
2. X = msg, but `entity_id 502`.

**When**
- `result = dao.get_by_entity(db, workspace_id=W1.id, entity_type="project", entity_id=501)`.

**Then**
1. returns: `ids(items) == [A.id]`.
2. returns: `total == 1`.

### DSC-GE-04 — a root of another entity type is not matched
- **Rules:** `get_by_entity` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = msg.
2. X = msg, but `entity_type "machine"`.

**When**
- `result = dao.get_by_entity(db, workspace_id=W1.id, entity_type="project", entity_id=501)`.

**Then**
1. returns: `ids(items) == [A.id]`.
2. returns: `total == 1`.

### DSC-GE-05 — the entity type with a capital matches nothing
- **Rules:** `get_by_entity` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = msg.

**When**
- `result = dao.get_by_entity(db, workspace_id=W1.id, entity_type="Project", entity_id=501)`.

**Then**
1. returns: `result == ([], 0)`.

### DSC-GE-06 — a part of the entity type matches nothing
- **Rules:** `get_by_entity` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = msg.

**When**
- `result = dao.get_by_entity(db, workspace_id=W1.id, entity_type="proj", entity_id=501)`.

**Then**
1. returns: `result == ([], 0)`.

### DSC-GE-07 — _ is no wildcard: a stored "purchase-order" is not matched
- **Rules:** `get_by_entity` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = msg, but `entity_type "purchase-order"`.

**When**
- `result = dao.get_by_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501)`.

**Then**
1. returns: `result == ([], 0)`.

### DSC-GE-08 — a stored type with a leading space is not matched
- **Rules:** `get_by_entity` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = msg.
2. X = msg, but `entity_type " project"`.

**When**
- `result = dao.get_by_entity(db, workspace_id=W1.id, entity_type="project", entity_id=501)`.

**Then**
1. returns: `ids(items) == [A.id]`.
2. returns: `total == 1`.

### DSC-GE-09 — with the default limit 51 roots give 50 items and a total of 51
- **Rules:** `get_by_entity` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 51 roots E1 … E51, built with `add_all` and flushed: Ek = msg, but `message` = `f"Post {k}"`.

**When**
- `result = dao.get_by_entity(db, workspace_id=W1.id, entity_type="project", entity_id=501)`.

**Then**
1. returns: `len(items) == 50`.
2. returns: `total == 51`.

### DSC-GE-10 — limit=1000 gives all 51 roots
- **Rules:** `get_by_entity` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 51 roots E1 … E51, built with `add_all` and flushed: Ek = msg, but `message` = `f"Post {k}"`.

**When**
- `result = dao.get_by_entity(db, workspace_id=W1.id, entity_type="project", entity_id=501, limit=1000)`.

**Then**
1. returns: `len(items) == 51`.
2. returns: `total == 51`.

### DSC-GE-11 — limit=0 gives no items and the full total
- **Rules:** `get_by_entity` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = msg.
2. B = msg, but `message "Second"`.

**When**
- `result = dao.get_by_entity(db, workspace_id=W1.id, entity_type="project", entity_id=501, limit=0)`.

**Then**
1. returns: `items == []`.
2. returns: `total == 2`.

### DSC-GE-12 — skip past the end gives no items and the full total
- **Rules:** `get_by_entity` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = msg.
2. B = msg, but `message "Second"`.

**When**
- `result = dao.get_by_entity(db, workspace_id=W1.id, entity_type="project", entity_id=501, skip=2)`.

**Then**
1. returns: `items == []`.
2. returns: `total == 2`.

### DSC-GE-13 — skip at the last root returns it
- **Rules:** `get_by_entity` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = msg.
2. B = msg, but `message "Second"`.
3. older(A, 1).

**When**
- `result = dao.get_by_entity(db, workspace_id=W1.id, entity_type="project", entity_id=501, skip=1)`.

**Then**
1. returns: `ids(items) == [B.id]`.
2. returns: `total == 2`.

### DSC-GE-14 — limit=1 returns one root
- **Rules:** `get_by_entity` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = msg.
2. B = msg, but `message "Second"`.

**When**
- `result = dao.get_by_entity(db, workspace_id=W1.id, entity_type="project", entity_id=501, limit=1)`.

**Then**
1. returns: `len(items) == 1`.
2. returns: `total == 2`.

### DSC-GE-15 — a negative limit raises DataError
- **Rules:** `get_by_entity` R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = msg.

**When**
- `dao.get_by_entity(db, workspace_id=W1.id, entity_type="project", entity_id=501, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "2201W"`.
2. nothing written: nothing written.

### DSC-GE-16 — a negative skip raises DataError
- **Rules:** `get_by_entity` R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = msg.

**When**
- `dao.get_by_entity(db, workspace_id=W1.id, entity_type="project", entity_id=501, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "2201X"`.
2. nothing written: nothing written.

### DSC-GE-17 — roots come oldest first, whatever the ids
- **Rules:** `get_by_entity` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = msg.
2. B = msg, but `message "Second"`.
3. C = msg, but `message "Third"`.
4. older(B, 2).
5. older(C, 1).

**When**
- `result = dao.get_by_entity(db, workspace_id=W1.id, entity_type="project", entity_id=501)`.

**Then**
1. returns: `ids(items) == [B.id, C.id, A.id]`.

### DSC-GE-18 — the hour-older root comes first, then the tied ones
- **Rules:** `get_by_entity` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = msg.
2. B = msg, but `message "Second"`.
3. C = msg, but `message "Third"`.
4. D = msg, but `message "Old"`.
5. older(D, 1).

**When**
- `result = dao.get_by_entity(db, workspace_id=W1.id, entity_type="project", entity_id=501)`.

**Then**
1. returns: `len(items) == 4`.
2. returns: `items[0].id == D.id`.
3. returns: `set(ids(items)[1:]) == {A.id, B.id, C.id}`.

### DSC-GE-19 — tied roots come in id order, also after the first was updated
- **Rules:** `get_by_entity` R4 [BUG-1438]
- **Kind:** bug
- **Expect:** xfail BUG-1438 (non-strict)
- **Fails today on:** Then 2 (no tie-break; the updated lowest id moves last by physical order)

**Given**
1. A = msg.
2. B = msg, but `message "Second"`.
3. C = msg, but `message "Third"`.
4. D = msg, but `message "Old"`.
5. older(D, 1).
6. seqscan.
7. bumpD(A).

**When**
- `result = dao.get_by_entity(db, workspace_id=W1.id, entity_type="project", entity_id=501)`.

**Then**
1. returns: `len(items) == 4`.
2. returns: `ids(items) == [D.id, A.id, B.id, C.id]`.

### DSC-GE-20 — tied roots paged one at a time neither repeat nor miss a root
- **Rules:** `get_by_entity` R4 [BUG-1438]
- **Kind:** bug
- **Expect:** xfail BUG-1438 (non-strict)
- **Fails today on:** Then 2 (no tie-break; pages follow physical order)

**Given**
1. A = msg.
2. B = msg, but `message "Second"`.
3. C = msg, but `message "Third"`.
4. D = msg, but `message "Fourth"`.
5. seqscan.
6. bumpD(A).

**When**
- `pages = [dao.get_by_entity(db, workspace_id=W1.id, entity_type="project", entity_id=501, skip=k, limit=1)[0] for k in range(4)]` (one list comprehension).

**Then**
1. returns: `[len(p) for p in pages] == [1, 1, 1, 1]`.
2. returns: `[p[0].id for p in pages] == [A.id, B.id, C.id, D.id]`.

### DSC-GE-21 — the page query orders by created_at, then id, ascending
- **Rules:** `get_by_entity` R4 [BUG-1438]
- **Kind:** bug
- **Expect:** xfail BUG-1438
- **Fails today on:** Then 3 (the page is ordered by `created_at` alone)

**Given**
1. A = msg.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_entity(db, workspace_id=W1.id, entity_type="project", entity_id=501)`.

**Then**
1. returns: `ids(items) == [A.id]`.
2. statement: `"created_at" in order_part`.
3. statement: `".id" in order_part`.
4. statement: `order_part.index("created_at") < order_part.index(".id")`.
5. statement: `"DESC" not in order_part.upper()`.

### DSC-GE-22 — replies are filtered before the page: an older reply takes no place
- **Rules:** `get_by_entity` R1, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = msg.
2. B = msg, but `message "Second"`.
3. X = reply on A.
4. older(X, 3).
5. older(A, 2).
6. older(B, 1).

**When**
- `result = dao.get_by_entity(db, workspace_id=W1.id, entity_type="project", entity_id=501, skip=1, limit=1)`.

**Then**
1. returns: `ids(items) == [B.id]`.
2. returns: `total == 2`.

### DSC-GE-23 — another entity's root is filtered before the page and takes no place
- **Rules:** `get_by_entity` R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = msg, but `entity_id 502`.
2. A = msg.
3. B = msg, but `message "Second"`.
4. older(X, 3).
5. older(A, 2).
6. older(B, 1).

**When**
- `result = dao.get_by_entity(db, workspace_id=W1.id, entity_type="project", entity_id=501, skip=1, limit=1)`.

**Then**
1. returns: `ids(items) == [B.id]`.
2. returns: `total == 2`.

### DSC-GE-24 — tied replies come in id order, also after the first was updated
- **Rules:** `get_by_entity` R6 [BUG-1439]
- **Kind:** bug
- **Expect:** xfail BUG-1439 (non-strict)
- **Fails today on:** Then 2 (replies have no order; the updated first reply moves last by physical order)

**Given**
1. A = msg.
2. R1 = reply on A.
3. R2 = reply on A, but `message "Two"`.
4. R3 = reply on A, but `message "Three"`.
5. seqscan.
6. bumpD(R1).

**When**
- `result = dao.get_by_entity(db, workspace_id=W1.id, entity_type="project", entity_id=501)`.

**Then**
1. returns: `ids(items) == [A.id]`.
2. returns: `reply_ids(items[0]) == [R1.id, R2.id, R3.id]`.

### DSC-GE-25 — replies come oldest first, whatever the ids
- **Rules:** `get_by_entity` R6 [BUG-1439]
- **Kind:** bug
- **Expect:** xfail BUG-1439 (non-strict)
- **Fails today on:** Then 2 (replies have no order; today they follow physical order R1, R2, R3)

**Given**
1. A = msg.
2. R1 = reply on A.
3. R2 = reply on A, but `message "Two"`.
4. R3 = reply on A, but `message "Three"`.
5. older(R2, 2).
6. older(R3, 1).

**When**
- `result = dao.get_by_entity(db, workspace_id=W1.id, entity_type="project", entity_id=501)`.

**Then**
1. returns: `ids(items) == [A.id]`.
2. returns: `reply_ids(items[0]) == [R2.id, R3.id, R1.id]`.

### DSC-GE-26 — the replies' query has an ORDER BY
- **Rules:** `get_by_entity` R6 [BUG-1439] [BUG-1490]
- **Kind:** bug
- **Expect:** xfail BUG-1439, BUG-1490
- **Fails today on:** Then 2 (BUG-1490: no replies query is sent with the page, the self-referential `selectin` without `join_depth` is skipped; BUG-1439: once it is sent, it carries no `ORDER BY`)

**Given**
1. A = msg.
2. R1 = reply on A.
3. `db.expire_all()`
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_entity(db, workspace_id=W1.id, entity_type="project", entity_id=501)`.

**Then**
1. returns: `reply_ids(items[0]) == [R1.id]`.
2. statement: `"parent_id IN" in reply_sql`.
3. statement: `"ORDER BY" in reply_sql`.

### DSC-GE-27 — every reply of the root is loaded, none is an item
- **Rules:** `get_by_entity` R1, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = msg.
2. R1 = reply on A.
3. R2 = reply on A, but `message "Two"`.
4. R3 = reply on A, but `message "Three"`.
5. `db.expire_all()`

**When**
- `result = dao.get_by_entity(db, workspace_id=W1.id, entity_type="project", entity_id=501)`.

**Then**
1. returns: `ids(items) == [A.id]`.
2. returns: `set(reply_ids(items[0])) == {R1.id, R2.id, R3.id}`.
3. returns: `total == 1`.

### DSC-GE-28 — a reply under W2 and a reply on another entity still load with the root
- **Rules:** `get_by_entity` R6a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = msg.
2. R1 = reply on A, but `workspace_id W2.id`.
3. R2 = reply on A, but `entity_id 502`.
4. `db.expire_all()`

**When**
- `result = dao.get_by_entity(db, workspace_id=W1.id, entity_type="project", entity_id=501)`.

**Then**
1. returns: `ids(items) == [A.id]`.
2. returns: `set(reply_ids(items[0])) == {R1.id, R2.id}`.

### DSC-GE-29 — the record is not looked at: an unknown type and a negative id are listed
- **Rules:** `get_by_entity` R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = msg, but `entity_type "unknown_type"`, `entity_id -5`.

**When**
- `result = dao.get_by_entity(db, workspace_id=W1.id, entity_type="unknown_type", entity_id=-5)`.

**Then**
1. returns: `ids(items) == [A.id]`.
2. returns: `total == 1`.

### DSC-GE-30 — writes nothing: a pending root stays pending, an unflushed edit stays unflushed
- **Rules:** `get_by_entity` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = msg.
2. B = msg, but `entity_id 502`.
3. `B.message = "Edited"` (not flushed).
4. `P = Discussion(workspace_id=W1.id, entity_type="project", entity_id=501, user_id=U1.id, message="Pending")`
5. `db.add(P)` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_entity(db, workspace_id=W1.id, entity_type="project", entity_id=501)`.

**Then**
1. returns: `ids(items) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. statement: `"FOR UPDATE" not in page_sql.upper()`.
8. nothing written: nothing written.

### DSC-GE-31 — asked for W2, only the W2 root is listed, though the W1 root is earlier
- **Rules:** `get_by_entity` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = msg.
2. Z = msg, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_entity(db, workspace_id=W2.id, entity_type="project", entity_id=501)`.

**Then**
1. returns: `ids(items) == [Z.id]`.
2. returns: `total == 1`.

### DSC-GE-32 — a leading space in the argument matches nothing
- **Rules:** `get_by_entity` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = msg.

**When**
- `result = dao.get_by_entity(db, workspace_id=W1.id, entity_type=" project", entity_id=501)`.

**Then**
1. returns: `result == ([], 0)`.

### DSC-GE-33 — a root of a lower entity id is not matched
- **Rules:** `get_by_entity` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = msg.
2. X = msg, but `entity_id 500`.

**When**
- `result = dao.get_by_entity(db, workspace_id=W1.id, entity_type="project", entity_id=501)`.

**Then**
1. returns: `ids(items) == [A.id]`.
2. returns: `total == 1`.

## `DiscussionDAO.get_by_id`

### DSC-GI-01 — a root is returned, the instance the session holds (positional call)
- **Rules:** `get_by_id` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. B = msg, but `message "Second"`.
2. A = msg.

**When**
- `result = dao.get_by_id(db, A.id, W1.id)` (positionally).

**Then**
1. returns: `isinstance(result, Discussion)`.
2. returns: `result is A`.

### DSC-GI-02 — a reply is returned
- **Rules:** `get_by_id` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = msg.
2. R = reply on A.

**When**
- `result = dao.get_by_id(db, discussion_id=R.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == R.id`.

### DSC-GI-03 — another workspace's id returns None, when that row is the earlier one
- **Rules:** `get_by_id` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = msg, but `workspace_id W2.id`.
2. A = msg.

**When**
- `result = dao.get_by_id(db, discussion_id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### DSC-GI-04 — another workspace's id returns None, when that row is the later one
- **Rules:** `get_by_id` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = msg.
2. Z = msg, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_id(db, discussion_id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### DSC-GI-05 — the id under another workspace returns None
- **Rules:** `get_by_id` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = msg.

**When**
- `result = dao.get_by_id(db, discussion_id=A.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### DSC-GI-06 — an unknown id returns None
- **Rules:** `get_by_id` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = msg.

**When**
- `result = dao.get_by_id(db, discussion_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### DSC-GI-07 — id 0 returns None
- **Rules:** `get_by_id` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = msg.

**When**
- `result = dao.get_by_id(db, discussion_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### DSC-GI-08 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `get_by_id` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = msg.
2. B = msg, but `message "Second"`.
3. `B.message = "Edited"` (not flushed).
4. `P = Discussion(workspace_id=W1.id, entity_type="project", entity_id=501, user_id=U1.id, message="Pending")`
5. `db.add(P)` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_id(db, discussion_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. statement: `"FOR UPDATE" not in sql.upper()`.
8. nothing written: nothing written.

## `DiscussionDAO.create`

### DSC-CR-01 — a root is stored with exactly the given values (positional call)
- **Rules:** `create` R1, R4, Returns, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. No `discussions` row exists.

**When**
- `result = dao.create(db, W1.id, "project", 501, U1.id, "Hello")` (positionally).

**Then**
1. returns: `isinstance(result, Discussion)`.
2. returns: `result.id is not None`.
3. re-read result: `workspace_id == W1.id`, `entity_type == "project"`, `entity_id == 501`.
4. re-read result: `user_id == U1.id`, `message == "Hello"`, `parent_id is None`.
5. re-read result: `created_at == NOW_DB`.
6. count: `discussions` has exactly 1 row with `entity_id == 501`.

### DSC-CR-02 — a reply stores its parent
- **Rules:** `create` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = msg.

**When**
- `result = dao.create(db, workspace_id=W1.id, entity_type="project", entity_id=501, user_id=U1.id, message="Reply", parent_id=A.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `parent_id == A.id`, `message == "Reply"`.

### DSC-CR-03 — nothing is validated: an empty message, a 30-character type, a negative id, no user
- **Rules:** `create` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No `discussions` row exists.

**When**
- `result = dao.create(db, workspace_id=W1.id, entity_type="x" * 30, entity_id=-5, user_id=None, message="")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `entity_type == "x" * 30`, `entity_id == -5`.
3. re-read result: `user_id is None`, `message == ""`.

### DSC-CR-04 — a reply to a reply, on another entity, is stored
- **Rules:** `create` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = msg.
2. R = reply on A.

**When**
- `result = dao.create(db, workspace_id=W1.id, entity_type="project", entity_id=502, user_id=U1.id, message="Deep", parent_id=R.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `parent_id == R.id`, `entity_id == 502`.

### DSC-CR-05 — a reply under another workspace than its parent is stored
- **Rules:** `create` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = msg.

**When**
- `result = dao.create(db, workspace_id=W2.id, entity_type="project", entity_id=501, user_id=U1.id, message="Far", parent_id=A.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `workspace_id == W2.id`, `parent_id == A.id`.

### DSC-CR-06 — an entity type of 31 characters raises DataError
- **Rules:** `create` R3, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. No `discussions` row exists.

**When**
- `dao.create(db, workspace_id=W1.id, entity_type="x" * 31, entity_id=501, user_id=U1.id, message="Hello")`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "22001"`.
2. nothing written: nothing written.

### DSC-CR-07 — message None raises IntegrityError 23502
- **Rules:** `create` R3, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. No `discussions` row exists.

**When**
- `dao.create(db, workspace_id=W1.id, entity_type="project", entity_id=501, user_id=U1.id, message=None)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23502"`.
2. nothing written: nothing written.

### DSC-CR-08 — an unknown parent raises IntegrityError 23503
- **Rules:** `create` R3, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. No `discussions` row exists.

**When**
- `dao.create(db, workspace_id=W1.id, entity_type="project", entity_id=501, user_id=U1.id, message="Hello", parent_id=MISSING)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. nothing written: nothing written.

### DSC-CR-09 — an unknown user raises IntegrityError 23503
- **Rules:** `create` R3, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. No `discussions` row exists.

**When**
- `dao.create(db, workspace_id=W1.id, entity_type="project", entity_id=501, user_id=MISSING, message="Hello")`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. nothing written: nothing written.

### DSC-CR-10 — flushed, not committed: a rollback removes the row
- **Rules:** `create` R5, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No `discussions` row exists.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.create(db, workspace_id=W1.id, entity_type="project", entity_id=501, user_id=U1.id, message="Hello")`.

**Then**
1. returns: `result.id is not None`.
2. count: inside the savepoint, `discussions` has exactly 1 row with `entity_id == 501`.
3. count: after the savepoint rollback, `discussions` has 0 rows with `entity_id == 501`.
4. mock called: the `db.commit` spy was never called.

### DSC-CR-11 — a message with spaces around it is stored as given
- **Rules:** `create` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No `discussions` row exists.

**When**
- `result = dao.create(db, workspace_id=W1.id, entity_type="project", entity_id=501, user_id=U1.id, message="  Hi  ")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `message == "  Hi  "`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Spec FU-1 (a) — P1, HR-16: `list` and `create` answer 404 for an unknown, other-workspace or soft-deleted record | `DiscussionService.list`, `DiscussionService.create` | The DAO keeps R7 / create R4 (DSC-GE-29, CR-01). |
| Spec FU-1 (b) — **OWNER, access:** private projects' threads readable and writable by any member; mentions notify whoever is named | `DiscussionService`, `app/api/v1/endpoints/discussions.py` | Owner item; not a DAO rule. |
| Spec FU-1 (c) — mentions limited to workspace members | notification service | Not checked here. |
| Spec FU-1 (d) — `create` commits inside the service | `DiscussionService.create` | The DAO only flushes (DSC-CR-10). |
| HR-1 — a blank message refused by `DiscussionCreate` (`message_not_empty`) | `app/schemas/discussion.py` | The DAO stores `""` (DSC-CR-03). |
| HR-7 — `GET /discussions/` requires `skip >= 0`, `1 <= limit <= 200` | `GET /discussions/` | Endpoint rule; the DAO's negatives are DSC-GE-15, GE-16. |
| Module singleton `discussion_dao` | none (no logic) | Entry point of every card. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `get_by_entity` R6a | "whatever their … depth" is not shown by an example; a reply to a reply belongs to its own parent, not to the root. | DSC-GE-28 covers workspace and entity only. |
| 2 | `get_by_entity` Returns | "each with `replies` and `author` loaded" — `author` loading has no rule of its own. | No card checks `author`. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_entity` | Returns | DSC-GE-01 |
| `get_by_entity` | R1 | DSC-GE-01, DSC-GE-22, DSC-GE-27 |
| `get_by_entity` | R2 | DSC-GE-09, DSC-GE-10, DSC-GE-11, DSC-GE-14 |
| `get_by_entity` | R3 | DSC-GE-02, DSC-GE-03, DSC-GE-04, DSC-GE-05, DSC-GE-06, DSC-GE-07, DSC-GE-08, DSC-GE-23, DSC-GE-31, DSC-GE-32, DSC-GE-33 |
| `get_by_entity` | R4 | DSC-GE-17, DSC-GE-18, DSC-GE-22, DSC-GE-23 |
| `get_by_entity` | R4 [BUG-1438] | DSC-GE-19, DSC-GE-20, DSC-GE-21 |
| `get_by_entity` | R5 | DSC-GE-12, DSC-GE-13, DSC-GE-15, DSC-GE-16 |
| `get_by_entity` | R6 | DSC-GE-27 |
| `get_by_entity` | R6 [BUG-1439] | DSC-GE-24, DSC-GE-25 |
| `get_by_entity` | R6 [BUG-1439] [BUG-1490] | DSC-GE-26 |
| `get_by_entity` | R6a | DSC-GE-28 |
| `get_by_entity` | R7 | DSC-GE-29 |
| `get_by_entity` | Errors | DSC-GE-15, DSC-GE-16 |
| `get_by_entity` | Side effects | DSC-GE-30 |
| `get_by_id` | Returns | DSC-GI-01 |
| `get_by_id` | R1 | DSC-GI-01, DSC-GI-02 |
| `get_by_id` | R2 | DSC-GI-03, DSC-GI-04, DSC-GI-05, DSC-GI-06, DSC-GI-07 |
| `get_by_id` | Side effects | DSC-GI-08 |
| `create` | Returns | DSC-CR-01 |
| `create` | R1 | DSC-CR-01, DSC-CR-02, DSC-CR-11 |
| `create` | R2 | DSC-CR-03, DSC-CR-04, DSC-CR-05, DSC-CR-11 |
| `create` | R3 | DSC-CR-06, DSC-CR-07, DSC-CR-08, DSC-CR-09 |
| `create` | R4 | DSC-CR-01 |
| `create` | R5 | DSC-CR-10 |
| `create` | Errors | DSC-CR-06, DSC-CR-07, DSC-CR-08, DSC-CR-09 |
| `create` | Side effects | DSC-CR-01, DSC-CR-10 |
