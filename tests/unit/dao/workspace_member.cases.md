# Test cases — `app/dao/workspace_member.py`

> **Spec:** `tests/unit/dao/workspace_member.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-03; nothing open). BUG-1400's order (`id` ascending) was decided by Claude under the reviewer's delegation.
> **Revision:** 1 — the spec did not change. Additive, from `workspace_member.verify.md` (case-missing Findings 1 … 5; recipes R-1 … R-5): R-1 → WSM-WU-09, WSM-HA-07 (the access gate: a non-member with a higher id than the member); R-2 → WSM-GU-07; R-3 → WSM-GM-14, WSM-CA-05; R-4 → WSM-HA-08 … HA-11; R-5 → WSM-CA-06. WU-09 and HA-07 also count that U2 has no membership, so the card cannot pass by a stray row. No existing card, Convention or ID changed; none retired.
> **Counts:** 54 cases · 49 expected-to-pass · 5 expected-to-fail (bugs) · 5 deferred

## Reviewer summary
- **Per callable:** `get_by_workspace_and_user` 9 · `get_by_user` 7 (2 bug) · `get_workspace_members` 14 (2 bug) · `get_by_workspace` 7 (1 bug) · `count_active_members` 6 · `has_access` 11.
- **Revision 1:** every "other user" and "other workspace" negative now also has the other row at the *lower* id (WU-09, HA-07, GU-07, GM-14, CA-05), so a `<=` in place of `==` fails. HA-07 is the access gate of every workspace request. `has_access` and `count_active_members` get the stored-side exact compare (`""`, leading and trailing space, a part, a longer word).
- **Depth:** lighter target (skill step 1a). Six plain filtered reads; nothing here writes stock, money or order state.
- **Expected-to-fail:** BUG-1400 5 cards: GU-04, GM-11 non-strict (the order itself, under a forced sequential scan); GU-05, GM-12, GW-02 strict (the SQL recorder, the alarm that goes off when the bug is fixed). `get_by_workspace` delegates to `get_workspace_members`, so it gets the alarm only.
- **Commit spies:** none. Every method only reads.
- **Notable design choices:**
  - Everywhere except the bug cards, lists are compared as **sets** of ids: no pass card compares an order produced without `ORDER BY`.
  - "No cap" has one 101-row card per query: `get_by_user` (101 workspaces), `get_workspace_members` and `get_by_workspace` (101 profiles each). `get_by_workspace` gets its own because it replaces the base method, whose default `limit` is 100.
  - Exact compare of `status` (argument side) is tested once, on `get_workspace_members` (GM-05 … GM-08); the stored side (`'Active'`, `' active'`, `'inactive'`) sits in GM-01, CA-01, HA-02, HA-03.
  - By-id reads (WU-02, WU-03): the other workspace's row is once the earlier and once the later id.
  - "Writes nothing": one card per query, a pending row and an unflushed edit in the session together.
  - WU-06 (R3, the unique pair) has a flush, not a DAO call, in its When: the rule is a database fact.
  - Size: 54 cards on about 70 source lines, over the one-per-two aim, because the 101-row and exact-compare shapes each need their own card.
  - No `Author:` lines (caller's instruction). Race simulations: none.
- **Needs a decision:** None blocking. Gap 1 (role text) and gap 2 (cost of 101 workspaces) are setup choices made here.

## Conventions for this module

**IDs.** `WSM` = `app/dao/workspace_member.py`. `WU` get_by_workspace_and_user · `GU` get_by_user · `GM` get_workspace_members · `GW` get_by_workspace · `CA` count_active_members · `HA` has_access.

**Actors and fixed values.**
- `dao` = the singleton `workspace_member_dao` (`from app.dao.workspace_member import workspace_member_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword unless the card says "positional". `result` = what the When call returns.
- `WorkspaceMember` = `app.models.workspace_member.WorkspaceMember`. `text` = `sqlalchemy.text`. `IntegrityError` = `sqlalchemy.exc.IntegrityError`.
- MISSING = `999999999`: an id that no row of any table has.

**Externals.** None. Nothing is mocked. No method reads the clock.

**Given rows.** Rows are inserted directly (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush.
- Standing rows, in every test, no Given line: W1, W2 = two `workspaces` rows from `make_workspace(db)`; U1, U2, U3 = three `profiles` rows from `make_profile(db)` (`tests/unit/factories.py`). No `workspace_members` row exists unless the card's Given lists it.
- More workspaces or profiles: `Wk = make_workspace(db)`, `Pk = make_profile(db)`, as the card says.
- **member** = `WorkspaceMember(workspace_id=W1.id, user_id=U1.id, role="member", status="active")`. After the word "but" the card lists every column that differs.
- A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending; an attribute set "(not flushed)" stays an unflushed edit.

**Named checks.**
- **idset(result)** = `{r.id for r in result}`. **ids(result)** = `[r.id for r in result]` (order is part of the check).
- **re-read X** = `db.expire_all()`, then SELECT X by id.
- `pending:` / `session:` lines check `db.new`, `db.dirty`, `db.deleted` after the call, before anything expires the session; keep the card's order.
- **seqscan** = run, in this order, `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`. Today's read then follows physical row order.
- `raises: TypeError` = plain `with pytest.raises(TypeError):` around the call. `raises: IntegrityError on flush` = `with pytest.raises(IntegrityError) as exc:` then `with db.begin_nested():` then the When; further `raises:` lines assert on `exc.value`, after the block.

**xfail cards.** Write the call and the checks exactly as shown. `xfail BUG-1400` = `pytest.mark.xfail(strict=True, reason="BUG-1400")`; `(non-strict)` = `strict=False`. The assertion of a non-strict card is never weakened.

**Statement recorder.** The SQL statements the session sends during the When are recorded (a `before_cursor_execute` listener). `sql` = the text of the one `SELECT` from `workspace_members`; `order_part` = the text of `sql` after its first `ORDER BY` (`""` when there is none); `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `WorkspaceMemberDAO.get_by_workspace_and_user`

### WSM-WU-01 — the row of that user in that workspace is returned, whatever its status
- **Rules:** `get_by_workspace_and_user` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. Z = member, but `workspace_id W2.id`.
2. A = member, but `status "inactive"`.

**When**
- `result = dao.get_by_workspace_and_user(db, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `isinstance(result, WorkspaceMember)`.
2. returns: `result.id == A.id`.
3. returns: `result.status == "inactive"`, `result.role == "member"`.

### WSM-WU-02 — the user's row in another workspace, the earlier id, is not matched
- **Rules:** `get_by_workspace_and_user` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = member, but `workspace_id W2.id`.
2. A = member, but `user_id U2.id`.

**When**
- `result = dao.get_by_workspace_and_user(db, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result is None`.

### WSM-WU-03 — the user's row in another workspace, the later id, is not matched
- **Rules:** `get_by_workspace_and_user` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = member, but `user_id U2.id`.
2. Z = member, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_workspace_and_user(db, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result is None`.

### WSM-WU-04 — user id 0 gives None, no error
- **Rules:** `get_by_workspace_and_user` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = member.

**When**
- `result = dao.get_by_workspace_and_user(db, workspace_id=W1.id, user_id=0)`.

**Then**
1. returns: `result is None`.

### WSM-WU-05 — an unknown workspace gives None, no error
- **Rules:** `get_by_workspace_and_user` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = member.

**When**
- `result = dao.get_by_workspace_and_user(db, workspace_id=MISSING, user_id=U1.id)`.

**Then**
1. returns: `result is None`.

### WSM-WU-06 — a second row for one workspace and user is refused by the database
- **Rules:** `get_by_workspace_and_user` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = member.
2. `P = WorkspaceMember(workspace_id=W1.id, user_id=U1.id, role="admin", status="active")`

**When**
- `db.add(P); db.flush()`, inside the wrap of `raises: IntegrityError on flush`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. raises: `"uq_workspace_user" in str(exc.value.orig)`.
4. count: `workspace_members` has exactly 1 row with `workspace_id == W1.id` and `user_id == U1.id`.

### WSM-WU-07 — positional arguments raise TypeError
- **Rules:** `get_by_workspace_and_user` Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = member.

**When**
- `dao.get_by_workspace_and_user(db, W1.id, U1.id)` (positional), inside `raises: TypeError`.

**Then**
1. raises: `TypeError`.

### WSM-WU-08 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `get_by_workspace_and_user` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = member.
2. B = member, but `user_id U2.id`.
3. `P = WorkspaceMember(workspace_id=W1.id, user_id=U3.id, role="member", status="active")`
4. `db.add(P)` (not flushed).
5. `B.role = "admin"` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_workspace_and_user(db, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. session: `B in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. session: `not db.deleted`.
7. statement: `written == []`.

### WSM-WU-09 — another user with a lower id in this workspace is not matched
- **Rules:** `get_by_workspace_and_user` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = member.

**When**
- `result = dao.get_by_workspace_and_user(db, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: `workspace_members` has exactly 0 rows with `user_id == U2.id`.

## `WorkspaceMemberDAO.get_by_user`

### WSM-GU-01 — every membership of the user, in every workspace, whatever the status
- **Rules:** `get_by_user` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = member.
2. X = member, but `user_id U2.id`.
3. B = member, but `workspace_id W2.id`, `status "inactive"`.

**When**
- `result = dao.get_by_user(db, user_id=U1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `idset(result) == {A.id, B.id}`.
3. returns: `len(result) == 2`.

### WSM-GU-02 — user id 0 returns an empty list
- **Rules:** `get_by_user` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = member.

**When**
- `result = dao.get_by_user(db, user_id=0)`.

**Then**
1. returns: `result == []`.

### WSM-GU-03 — no cap: 101 memberships give 101 rows
- **Rules:** `get_by_user` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 workspaces V1 … V101, each `Vk = make_workspace(db)`.
2. 101 members M1 … M101: Mk = member, but `workspace_id Vk.id`.

**When**
- `result = dao.get_by_user(db, user_id=U1.id)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `idset(result) == {M1.id, …, M101.id}`.

### WSM-GU-04 — rows come id ascending, also after the lowest id was updated
- **Rules:** `get_by_user` R3 [BUG-1400]
- **Kind:** bug
- **Expect:** xfail BUG-1400 (non-strict)
- **Fails today on:** Then 2 (no `ORDER BY`; the updated row comes back last in physical order)

**Given**
1. W3 = `make_workspace(db)`. W4 = `make_workspace(db)`.
2. seqscan.
3. A = member.
4. B = member, but `workspace_id W2.id`.
5. C = member, but `workspace_id W3.id`.
6. D = member, but `workspace_id W4.id`.
7. `A.role = "admin"`, then `db.flush()`.
8. `db.expire_all()`

**When**
- `result = dao.get_by_user(db, user_id=U1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `ids(result) == [A.id, B.id, C.id, D.id]`.

### WSM-GU-05 — the query orders by id ascending
- **Rules:** `get_by_user` R3 [BUG-1400]
- **Kind:** bug
- **Expect:** xfail BUG-1400
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. A = member.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_user(db, user_id=U1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `".id" in order_part`.
4. statement: `"DESC" not in order_part.upper()`.
5. statement: `order_part.count(",") == 0`.

### WSM-GU-06 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `get_by_user` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = member.
2. B = member, but `user_id U2.id`.
3. `P = WorkspaceMember(workspace_id=W2.id, user_id=U1.id, role="member", status="active")`
4. `db.add(P)` (not flushed).
5. `B.role = "admin"` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_user(db, user_id=U1.id)`.

**Then**
1. returns: `idset(result) == {A.id}`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. session: `B in db.dirty`.
6. session: `len(db.dirty) == 1`.
7. session: `not db.deleted`.
8. statement: `written == []`.

### WSM-GU-07 — another user's row with a lower user id is not returned
- **Rules:** `get_by_user` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X = member.
2. A = member, but `user_id U2.id`, `workspace_id W2.id`.

**When**
- `result = dao.get_by_user(db, user_id=U2.id)`.

**Then**
1. returns: `idset(result) == {A.id}`.

## `WorkspaceMemberDAO.get_workspace_members`

### WSM-GM-01 — by default only rows with status exactly 'active'
- **Rules:** `get_workspace_members` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = member.
2. B = member, but `user_id U2.id`, `status "Active"`.
3. C = member, but `user_id U3.id`, `status "inactive"`.
4. P4 = `make_profile(db)`. D = member, but `user_id P4.id`, `status " active"`.
5. P5 = `make_profile(db)`. E = member, but `user_id P5.id`, `status "suspended"`.
6. P6 = `make_profile(db)`. F = member, but `user_id P6.id`, `status "invited"`.

**When**
- `result = dao.get_workspace_members(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `idset(result) == {A.id}`.

### WSM-GM-02 — status=None returns every row of the workspace, and none of another
- **Rules:** `get_workspace_members` R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = member.
2. B = member, but `user_id U2.id`, `status "inactive"`.
3. C = member, but `user_id U3.id`, `status ""`.
4. Z = member, but `workspace_id W2.id`.

**When**
- `result = dao.get_workspace_members(db, workspace_id=W1.id, status=None)`.

**Then**
1. returns: `idset(result) == {A.id, B.id, C.id}`.

### WSM-GM-03 — status="" returns the rows whose status is the empty string, not every row
- **Rules:** `get_workspace_members` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = member.
2. B = member, but `user_id U2.id`, `status ""`.

**When**
- `result = dao.get_workspace_members(db, workspace_id=W1.id, status="")`.

**Then**
1. returns: `idset(result) == {B.id}`.

### WSM-GM-04 — another status keeps exactly the rows with that status
- **Rules:** `get_workspace_members` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = member.
2. B = member, but `user_id U2.id`, `status "suspended"`.
3. Z = member, but `workspace_id W2.id`, `status "suspended"`.

**When**
- `result = dao.get_workspace_members(db, workspace_id=W1.id, status="suspended")`.

**Then**
1. returns: `idset(result) == {B.id}`.

### WSM-GM-05 — status in capitals finds nothing
- **Rules:** `get_workspace_members` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. B = member, but `status "suspended"`.

**When**
- `result = dao.get_workspace_members(db, workspace_id=W1.id, status="Suspended")`.

**Then**
1. returns: `result == []`.

### WSM-GM-06 — status with a leading space finds nothing
- **Rules:** `get_workspace_members` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. B = member, but `status "suspended"`.

**When**
- `result = dao.get_workspace_members(db, workspace_id=W1.id, status=" suspended")`.

**Then**
1. returns: `result == []`.

### WSM-GM-07 — part of a status finds nothing
- **Rules:** `get_workspace_members` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. B = member, but `status "suspended"`.

**When**
- `result = dao.get_workspace_members(db, workspace_id=W1.id, status="suspend")`.

**Then**
1. returns: `result == []`.

### WSM-GM-08 — _ is no wildcard in a status
- **Rules:** `get_workspace_members` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. B = member, but `status "suspended"`.

**When**
- `result = dao.get_workspace_members(db, workspace_id=W1.id, status="suspende_")`.

**Then**
1. returns: `result == []`.

### WSM-GM-09 — workspace id 0 returns an empty list
- **Rules:** `get_workspace_members` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = member.

**When**
- `result = dao.get_workspace_members(db, workspace_id=0, status=None)`.

**Then**
1. returns: `result == []`.

### WSM-GM-10 — no cap: 101 active members give 101 rows
- **Rules:** `get_workspace_members` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 profiles P1 … P101, each `Pk = make_profile(db)`.
2. 101 members M1 … M101: Mk = member, but `user_id Pk.id`.

**When**
- `result = dao.get_workspace_members(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `idset(result) == {M1.id, …, M101.id}`.

### WSM-GM-11 — rows come id ascending, also after the lowest id was updated
- **Rules:** `get_workspace_members` R4 [BUG-1400]
- **Kind:** bug
- **Expect:** xfail BUG-1400 (non-strict)
- **Fails today on:** Then 2 (no `ORDER BY`; the updated row comes back last in physical order)

**Given**
1. P4 = `make_profile(db)`.
2. seqscan.
3. A = member.
4. B = member, but `user_id U2.id`.
5. C = member, but `user_id U3.id`.
6. D = member, but `user_id P4.id`.
7. `A.role = "admin"`, then `db.flush()`.
8. `db.expire_all()`

**When**
- `result = dao.get_workspace_members(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `ids(result) == [A.id, B.id, C.id, D.id]`.

### WSM-GM-12 — the query orders by id ascending
- **Rules:** `get_workspace_members` R4 [BUG-1400]
- **Kind:** bug
- **Expect:** xfail BUG-1400
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. A = member.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_workspace_members(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `".id" in order_part`.
4. statement: `"DESC" not in order_part.upper()`.
5. statement: `order_part.count(",") == 0`.

### WSM-GM-13 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `get_workspace_members` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = member.
2. B = member, but `workspace_id W2.id`.
3. `P = WorkspaceMember(workspace_id=W1.id, user_id=U2.id, role="member", status="active")`
4. `db.add(P)` (not flushed).
5. `B.role = "admin"` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_workspace_members(db, workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {A.id}`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. session: `B in db.dirty`.
6. session: `len(db.dirty) == 1`.
7. session: `not db.deleted`.
8. statement: `written == []`.

### WSM-GM-14 — a row of a workspace with a lower id is not returned
- **Rules:** `get_workspace_members` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = member.
2. A = member, but `workspace_id W2.id`.

**When**
- `result = dao.get_workspace_members(db, workspace_id=W2.id, status=None)`.

**Then**
1. returns: `idset(result) == {A.id}`.

## `WorkspaceMemberDAO.get_by_workspace`

### WSM-GW-01 — every row of the workspace, whatever the status, none of another
- **Rules:** `get_by_workspace` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = member.
2. B = member, but `user_id U2.id`, `status "inactive"`.
3. C = member, but `user_id U3.id`, `status "Active"`.
4. Z = member, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `idset(result) == {A.id, B.id, C.id}`.

### WSM-GW-02 — the query orders by id ascending
- **Rules:** `get_by_workspace` R2 [BUG-1400]
- **Kind:** bug
- **Expect:** xfail BUG-1400
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. A = member.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `".id" in order_part`.
4. statement: `"DESC" not in order_part.upper()`.
5. statement: `order_part.count(",") == 0`.

### WSM-GW-03 — skip is refused
- **Rules:** `get_by_workspace` R3, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = member.

**When**
- `dao.get_by_workspace(db, workspace_id=W1.id, skip=0)`, inside `raises: TypeError`.

**Then**
1. raises: `TypeError`.

### WSM-GW-04 — limit is refused
- **Rules:** `get_by_workspace` R3, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = member.

**When**
- `dao.get_by_workspace(db, workspace_id=W1.id, limit=100)`, inside `raises: TypeError`.

**Then**
1. raises: `TypeError`.

### WSM-GW-05 — a positional workspace id is refused
- **Rules:** `get_by_workspace` Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = member.

**When**
- `dao.get_by_workspace(db, W1.id)` (positional), inside `raises: TypeError`.

**Then**
1. raises: `TypeError`.

### WSM-GW-06 — no cap: 101 members give 101 rows (the base method stopped at 100)
- **Rules:** `get_by_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 profiles P1 … P101, each `Pk = make_profile(db)`.
2. 101 members M1 … M101: Mk = member, but `user_id Pk.id`, `status "inactive"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `idset(result) == {M1.id, …, M101.id}`.

### WSM-GW-07 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `get_by_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = member.
2. B = member, but `workspace_id W2.id`.
3. `P = WorkspaceMember(workspace_id=W1.id, user_id=U2.id, role="member", status="active")`
4. `db.add(P)` (not flushed).
5. `B.role = "admin"` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {A.id}`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. session: `B in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. session: `not db.deleted`.
7. statement: `written == []`.

## `WorkspaceMemberDAO.count_active_members`

### WSM-CA-01 — counts the rows with status exactly 'active', the owner's included
- **Rules:** `count_active_members` R1, R2, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = member, but `role "owner"`.
2. B = member, but `user_id U2.id`.
3. C = member, but `user_id U3.id`, `status "Active"`.
4. P4 = `make_profile(db)`. D = member, but `user_id P4.id`, `status "inactive"`.
5. P5 = `make_profile(db)`. E = member, but `user_id P5.id`, `status " active"`.
6. Z = member, but `workspace_id W2.id`.

**When**
- `result = dao.count_active_members(db, workspace_id=W1.id)`.

**Then**
1. returns: `type(result) is int`.
2. returns: `result == 2`.

### WSM-CA-02 — a workspace with no active member gives 0
- **Rules:** `count_active_members` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = member, but `status "inactive"`.
2. Z = member, but `workspace_id W2.id`.

**When**
- `result = dao.count_active_members(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == 0`.

### WSM-CA-03 — workspace id 0 gives 0
- **Rules:** `count_active_members` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = member.

**When**
- `result = dao.count_active_members(db, workspace_id=0)`.

**Then**
1. returns: `result == 0`.

### WSM-CA-04 — writes nothing: a pending row stays pending and is not counted
- **Rules:** `count_active_members` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = member.
2. B = member, but `workspace_id W2.id`.
3. `P = WorkspaceMember(workspace_id=W1.id, user_id=U2.id, role="member", status="active")`
4. `db.add(P)` (not flushed).
5. `B.role = "admin"` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.count_active_members(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == 1`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. session: `B in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. statement: `written == []`.

### WSM-CA-05 — an active row of a workspace with a lower id is not counted
- **Rules:** `count_active_members` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = member.
2. A = member, but `workspace_id W2.id`.

**When**
- `result = dao.count_active_members(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == 1`.

### WSM-CA-06 — a part of 'active', or a longer word, is not counted
- **Rules:** `count_active_members` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = member, but `status "activ"`.
2. B = member, but `user_id U2.id`, `status "actives"`.

**When**
- `result = dao.count_active_members(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == 0`.

## `WorkspaceMemberDAO.has_access`

### WSM-HA-01 — an active member has access
- **Rules:** `has_access` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. Z = member, but `workspace_id W2.id`, `status "inactive"`.
2. A = member.

**When**
- `result = dao.has_access(db, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.

### WSM-HA-02 — status 'Active' in capitals gives False
- **Rules:** `has_access` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = member, but `status "Active"`.

**When**
- `result = dao.has_access(db, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### WSM-HA-03 — status 'inactive' gives False
- **Rules:** `has_access` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = member, but `status "inactive"`.

**When**
- `result = dao.has_access(db, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### WSM-HA-04 — an active member of another workspace only gives False
- **Rules:** `has_access` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = member, but `workspace_id W2.id`.
2. A = member, but `user_id U2.id`.

**When**
- `result = dao.has_access(db, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### WSM-HA-05 — user id 0 gives False
- **Rules:** `has_access` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = member.

**When**
- `result = dao.has_access(db, user_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### WSM-HA-06 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `has_access` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = member.
2. B = member, but `user_id U2.id`.
3. `P = WorkspaceMember(workspace_id=W1.id, user_id=U3.id, role="member", status="active")`
4. `db.add(P)` (not flushed).
5. `B.status = "inactive"` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.has_access(db, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. session: `B in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. statement: `written == []`.

### WSM-HA-07 — the access gate: a non-member with a higher id than the only member gets False
- **Rules:** `has_access` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = member.

**When**
- `result = dao.has_access(db, user_id=U2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.
2. count: `workspace_members` has exactly 0 rows with `user_id == U2.id`.

### WSM-HA-08 — status "" gives False
- **Rules:** `has_access` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = member, but `status ""`.

**When**
- `result = dao.has_access(db, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### WSM-HA-09 — status " active" with a leading space gives False
- **Rules:** `has_access` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = member, but `status " active"`.

**When**
- `result = dao.has_access(db, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### WSM-HA-10 — status "active " with a trailing space gives False
- **Rules:** `has_access` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = member, but `status "active "`.

**When**
- `result = dao.has_access(db, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### WSM-HA-11 — status "activ", a part of the word, gives False
- **Rules:** `has_access` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = member, but `status "activ"`.

**When**
- `result = dao.has_access(db, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| FU-1 (a) — `list_members` filters `active` in Python; display order member name, then `id` | `WorkspaceService.list_members` | Display order and the `include_inactive` path. |
| FU-1 (b) — `list_user_workspaces` reads workspaces one by one; order by workspace name | `WorkspaceService.list_user_workspaces` | Display order. |
| FU-2 — `max_members = -1` refuses every invitation and add; read-then-insert with no lock (OQ-2) | `WorkspaceManager.add_member_to_workspace`, `create_invitation` | Owner question OQ-2; plan limits. |
| FU-3 — non-member told 404 (BUG-440) | `app/core/deps.py` (`deps.cases.md`) | Already there. |
| Inherited `BaseDAO` methods (`create`, `update`, `get`, `get_multi`, `remove`, `get_by_id_and_workspace`) and the singleton | `tests/unit/dao/base.cases.md` | Not repeated here (step 1a). |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Model facts | `role` is free text; no value is named as typical. | Conventions use `"member"`, `"admin"`, `"owner"`. Not a blocker. |
| 2 | `get_by_user` R2 "no cap" | No number. 101 rows of one user need 101 workspaces (unique pair). | WSM-GU-03 builds 101 workspaces with `make_workspace`; slow but honest. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_workspace_and_user` | Returns | WSM-WU-01 |
| `get_by_workspace_and_user` | R1 | WSM-WU-01 |
| `get_by_workspace_and_user` | R2 | WSM-WU-02, WSM-WU-03, WSM-WU-04, WSM-WU-05, WSM-WU-09 |
| `get_by_workspace_and_user` | R3 | WSM-WU-06 |
| `get_by_workspace_and_user` | Errors | WSM-WU-07 |
| `get_by_workspace_and_user` | Side effects | WSM-WU-08 |
| `get_by_user` | Returns | WSM-GU-01 |
| `get_by_user` | R1 | WSM-GU-01, WSM-GU-07 |
| `get_by_user` | R2 | WSM-GU-02, WSM-GU-03 |
| `get_by_user` | R3 [BUG-1400] | WSM-GU-04, WSM-GU-05 |
| `get_by_user` | Side effects | WSM-GU-06 |
| `get_workspace_members` | Returns | WSM-GM-01 |
| `get_workspace_members` | R1 | WSM-GM-01 |
| `get_workspace_members` | R2 | WSM-GM-02, WSM-GM-03, WSM-GM-04, WSM-GM-05, WSM-GM-06, WSM-GM-07, WSM-GM-08 |
| `get_workspace_members` | R3 | WSM-GM-02, WSM-GM-09, WSM-GM-10, WSM-GM-14 |
| `get_workspace_members` | R4 [BUG-1400] | WSM-GM-11, WSM-GM-12 |
| `get_workspace_members` | Side effects | WSM-GM-13 |
| `get_by_workspace` | R1 | WSM-GW-01, WSM-GW-06 |
| `get_by_workspace` | R2 [BUG-1400] | WSM-GW-02 |
| `get_by_workspace` | R3 | WSM-GW-03, WSM-GW-04 |
| `get_by_workspace` | Errors | WSM-GW-03, WSM-GW-04, WSM-GW-05 |
| `get_by_workspace` | Side effects | WSM-GW-07 |
| `count_active_members` | Returns | WSM-CA-01 |
| `count_active_members` | R1 | WSM-CA-01, WSM-CA-06 |
| `count_active_members` | R2 | WSM-CA-01, WSM-CA-02, WSM-CA-03, WSM-CA-05 |
| `count_active_members` | Side effects | WSM-CA-04 |
| `has_access` | Returns | WSM-HA-01 |
| `has_access` | R1 | WSM-HA-01 |
| `has_access` | R2 | WSM-HA-02, WSM-HA-03, WSM-HA-04, WSM-HA-05, WSM-HA-07, WSM-HA-08, WSM-HA-09, WSM-HA-10, WSM-HA-11 |
| `has_access` | Side effects | WSM-HA-06 |
