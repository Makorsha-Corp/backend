# Test cases — `app/dao/access_control.py`

> **Spec:** `tests/unit/dao/access_control.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-03; nothing open). BUG-1408's order (`id` ascending) was decided by Claude under the reviewer's delegation.
> **Counts:** 35 cases · 31 expected-to-pass · 4 expected-to-fail (bugs) · 5 deferred

## Reviewer summary
- **Per callable:** `get_by_role` 19 (2 bug) · `get_by_type` 16 (2 bug).
- **Depth:** lighter target (skill step 1a). Two paged, filtered reads; nothing here writes stock, money or order state.
- **Expected-to-fail:** BUG-1408 4: GR-07, GT-08 non-strict (the order itself, under a forced sequential scan after the lowest id was updated), GR-08, GT-09 strict (the SQL recorder, the alarm that goes off when the bug is fixed).
- **Commit spies:** none. Both methods only read.
- **Notable design choices:**
  - Pass cards never compare an order: they compare sets, or a length plus membership, because today's order rests on physical row order.
  - Filter before paging (GR-02, GT-06): the other workspace's row has the lowest id, so it sorts ahead of the skipped row today and after the fix; a filter applied after paging returns two rows instead of one.
  - The default cap (100 of 101) and `limit=1000` each have a card on both methods. `skip` boundaries are on `get_by_role` only; `get_by_type` shares the paging code shape and gets `limit=0` and the negatives (step 1a).
  - Role and type are enums, so the exact-compare shape is the enum coercion: enum, value, name, and an unknown string (`DataError`).
  - BUG-1409 (`limit >= 1` at the API) is the endpoint's: a Deferred entry. The DAO's own negatives are GR-16, GR-17, GT-13, GT-14.
  - No `Author:` lines (caller's instruction). Race simulations: none.
- **Needs a decision:** None blocking. Gap 1 (the type enum's class name) is assumed.

## Conventions for this module

**IDs.** `ACL` = `app/dao/access_control.py`. `GR` get_by_role · `GT` get_by_type.

**Actors and fixed values.**
- `dao` = the singleton `access_control_dao` (`from app.dao.access_control import access_control_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword unless the card says "positional". `result` = what the When call returns.
- `AccessControl` = `app.models.access_control.AccessControl`. `RoleEnum`, `AccessControlTypeEnum` = from `app.models.enums`. OWNER = `RoleEnum.OWNER`, FINANCE = `RoleEnum.FINANCE`. PAGE = `AccessControlTypeEnum.PAGE`, FEATURE = `AccessControlTypeEnum.FEATURE`. `text` = `sqlalchemy.text`. `DataError` = `sqlalchemy.exc.DataError`.
- MISSING = `999999999`.

**Externals.** None. Nothing is mocked. No method reads the clock.

**Given rows.** Rows are inserted directly (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush.
- Standing rows, no Given line: W1, W2 = two `workspaces` rows from `make_workspace(db)`. No `access_control` row of W1 or W2 exists unless the card's Given lists it; rows with no workspace may already exist (gap 2).
- **rule** = `AccessControl(workspace_id=W1.id, type=PAGE, target="/orders", role=OWNER)`. After the word "but" the card lists every column that differs.
- A Given line written as code is a step to run exactly as written. `db.add(...)` without `db.flush()` leaves the row pending; an attribute set "(not flushed)" stays an unflushed edit.

**Named checks.**
- **idset(result)** = `{r.id for r in result}`. **ids(result)** = `[r.id for r in result]` (order is part of the check).
- **nothing written** = the number of `access_control` rows stored equals its value before the call.
- **seqscan** = run, in this order, `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`. Today's read then follows physical row order.
- `raises: DataError` = `with pytest.raises(DataError) as exc:` then `with db.begin_nested():` then the When; further `raises:` lines assert on `exc.value`, after the block. `raises: TypeError` = plain `pytest.raises(TypeError)`.
- `pending:` / `session:` lines check `db.new`, `db.dirty`, `db.deleted` after the call, before anything expires the session.

**xfail cards.** `xfail BUG-1408` = `pytest.mark.xfail(strict=True, reason="BUG-1408")`; `(non-strict)` = `strict=False`. The assertion of a non-strict card is never weakened.

**Statement recorder.** The SQL statements the session sends during the When are recorded (a `before_cursor_execute` listener). `sql` = the text of the one `SELECT` from `access_control`; `order_part` = the text of `sql` after its first `ORDER BY` and before any `LIMIT` (`""` when there is no `ORDER BY`); `written` = every recorded `INSERT`, `UPDATE` or `DELETE`.

**Race simulations.** None in this module.

## `DAOAccessControl.get_by_role`

### ACL-GR-01 — the role's rows of the workspace, every type, duplicates each returned
- **Rules:** `get_by_role` R1, R3, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. N = rule, but `workspace_id None`.
2. A = rule.
3. B = rule, but `type FEATURE`, `target "reports"`.
4. C = rule, but `role FINANCE`.
5. D = rule.
6. Z = rule, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_role(db, role=OWNER, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `idset(result) == {A.id, B.id, D.id}`.
3. returns: `len(result) == 3`.

### ACL-GR-02 — the workspace filter is applied before the page
- **Rules:** `get_by_role` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = rule, but `workspace_id W2.id`.
2. A = rule.
3. B = rule, but `target "/sales"`.

**When**
- `result = dao.get_by_role(db, role=OWNER, workspace_id=W1.id, skip=1, limit=1000)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in {A.id, B.id}`.

### ACL-GR-03 — the role as its value "owner" matches the same rows
- **Rules:** `get_by_role` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = rule.
2. C = rule, but `role FINANCE`.

**When**
- `result = dao.get_by_role(db, role="owner", workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {A.id}`.

### ACL-GR-04 — the role as its name "OWNER" matches the same rows
- **Rules:** `get_by_role` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = rule.
2. C = rule, but `role FINANCE`.

**When**
- `result = dao.get_by_role(db, role="OWNER", workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {A.id}`.

### ACL-GR-05 — a string that is not a role raises DataError 22P02
- **Rules:** `get_by_role` R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = rule.

**When**
- `dao.get_by_role(db, role="nobody", workspace_id=W1.id)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "22P02"`.
3. nothing written: nothing written.

### ACL-GR-06 — workspace_id=None returns the rows with no workspace
- **Rules:** `get_by_role` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = rule.
2. N = rule, but `workspace_id None`.

**When**
- `result = dao.get_by_role(db, role=OWNER, workspace_id=None)`.

**Then**
1. returns: `N.id in idset(result)`.
2. returns: `A.id not in idset(result)`.
3. returns: `all(r.workspace_id is None for r in result)`.

### ACL-GR-07 — rows come id ascending, also after the lowest id was updated
- **Rules:** `get_by_role` R4 [BUG-1408]
- **Kind:** bug
- **Expect:** xfail BUG-1408 (non-strict)
- **Fails today on:** Then 2 (no `ORDER BY`; the updated row comes back last in physical order)

**Given**
1. seqscan.
2. A = rule.
3. B = rule, but `target "/sales"`.
4. C = rule, but `target "/stock"`.
5. D = rule, but `target "/people"`.
6. `A.target = "/changed"`, then `db.flush()`.
7. `db.expire_all()`

**When**
- `result = dao.get_by_role(db, role=OWNER, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `ids(result) == [A.id, B.id, C.id, D.id]`.

### ACL-GR-08 — the query orders by id ascending
- **Rules:** `get_by_role` R4 [BUG-1408]
- **Kind:** bug
- **Expect:** xfail BUG-1408
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. A = rule.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_role(db, role=OWNER, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `".id" in order_part`.
4. statement: `"DESC" not in order_part.upper()`.
5. statement: `order_part.count(",") == 0`.

### ACL-GR-09 — with the defaults 101 rows give 100
- **Rules:** `get_by_role` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 rules E1 … E101, built with `add_all`: Ek = rule, but `target f"/p{k}"`.

**When**
- `result = dao.get_by_role(db, role=OWNER, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `idset(result) <= {E1.id, …, E101.id}`.

### ACL-GR-10 — limit=1000 gives all 101
- **Rules:** `get_by_role` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 rules E1 … E101, built with `add_all`: Ek = rule, but `target f"/p{k}"`.

**When**
- `result = dao.get_by_role(db, role=OWNER, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `idset(result) == {E1.id, …, E101.id}`.

### ACL-GR-11 — limit=0 returns an empty list
- **Rules:** `get_by_role` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = rule.
2. B = rule, but `target "/sales"`.

**When**
- `result = dao.get_by_role(db, role=OWNER, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### ACL-GR-12 — limit=1 returns one row
- **Rules:** `get_by_role` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = rule.
2. B = rule, but `target "/sales"`.

**When**
- `result = dao.get_by_role(db, role=OWNER, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in {A.id, B.id}`.

### ACL-GR-13 — skip past the end returns an empty list
- **Rules:** `get_by_role` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = rule.
2. B = rule, but `target "/sales"`.

**When**
- `result = dao.get_by_role(db, role=OWNER, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### ACL-GR-14 — skip at the last row returns one row
- **Rules:** `get_by_role` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = rule.
2. B = rule, but `target "/sales"`.

**When**
- `result = dao.get_by_role(db, role=OWNER, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in {A.id, B.id}`.

### ACL-GR-15 — workspace id 0 returns an empty list
- **Rules:** `get_by_role` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = rule.

**When**
- `result = dao.get_by_role(db, role=OWNER, workspace_id=0)`.

**Then**
1. returns: `result == []`.

### ACL-GR-16 — a negative limit raises DataError 2201W
- **Rules:** `get_by_role` R5, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = rule.

**When**
- `dao.get_by_role(db, role=OWNER, workspace_id=W1.id, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### ACL-GR-17 — a negative skip raises DataError 2201X
- **Rules:** `get_by_role` R5, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = rule.

**When**
- `dao.get_by_role(db, role=OWNER, workspace_id=W1.id, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### ACL-GR-18 — positional arguments raise TypeError
- **Rules:** `get_by_role` Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = rule.

**When**
- `dao.get_by_role(db, OWNER, W1.id)` (positional), inside `raises: TypeError`.

**Then**
1. raises: `TypeError`.

### ACL-GR-19 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `get_by_role` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = rule.
2. B = rule, but `workspace_id W2.id`.
3. `P = AccessControl(workspace_id=W1.id, type=PAGE, target="/pending", role=OWNER)`
4. `db.add(P)` (not flushed).
5. `B.target = "/edited"` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_role(db, role=OWNER, workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {A.id}`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. session: `B in db.dirty`.
6. session: `len(db.dirty) == 1`.
7. session: `not db.deleted`.
8. statement: `written == []`.

## `DAOAccessControl.get_by_type`

### ACL-GT-01 — the type's rows of the workspace, every role, duplicates each returned
- **Rules:** `get_by_type` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. N = rule, but `workspace_id None`.
2. A = rule.
3. B = rule, but `role FINANCE`.
4. C = rule, but `type FEATURE`, `target "reports"`.
5. D = rule.
6. Z = rule, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_type(db, access_type=PAGE, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `idset(result) == {A.id, B.id, D.id}`.
3. returns: `len(result) == 3`.

### ACL-GT-02 — the type as its value "page" matches the same rows
- **Rules:** `get_by_type` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = rule.
2. C = rule, but `type FEATURE`, `target "reports"`.

**When**
- `result = dao.get_by_type(db, access_type="page", workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {A.id}`.

### ACL-GT-03 — the type as its name "PAGE" matches the same rows
- **Rules:** `get_by_type` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = rule.
2. C = rule, but `type FEATURE`, `target "reports"`.

**When**
- `result = dao.get_by_type(db, access_type="PAGE", workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {A.id}`.

### ACL-GT-04 — a string that is not a type raises DataError 22P02
- **Rules:** `get_by_type` R2, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = rule.

**When**
- `dao.get_by_type(db, access_type="nobody", workspace_id=W1.id)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "22P02"`.
3. nothing written: nothing written.

### ACL-GT-05 — a row whose type was updated moves to the other type's results
- **Rules:** `get_by_type` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = rule.
2. B = rule, but `target "/sales"`.
3. `A.type = FEATURE`, then `db.flush()`.

**When**
- `result = dao.get_by_type(db, access_type=PAGE, workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {B.id}`.

### ACL-GT-06 — the workspace filter is applied before the page
- **Rules:** `get_by_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = rule, but `workspace_id W2.id`.
2. A = rule.
3. B = rule, but `target "/sales"`.

**When**
- `result = dao.get_by_type(db, access_type=PAGE, workspace_id=W1.id, skip=1, limit=1000)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in {A.id, B.id}`.

### ACL-GT-07 — workspace_id=None returns the rows with no workspace
- **Rules:** `get_by_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = rule.
2. N = rule, but `workspace_id None`.

**When**
- `result = dao.get_by_type(db, access_type=PAGE, workspace_id=None)`.

**Then**
1. returns: `N.id in idset(result)`.
2. returns: `A.id not in idset(result)`.
3. returns: `all(r.workspace_id is None for r in result)`.

### ACL-GT-08 — rows come id ascending, also after the lowest id was updated
- **Rules:** `get_by_type` R4 [BUG-1408]
- **Kind:** bug
- **Expect:** xfail BUG-1408 (non-strict)
- **Fails today on:** Then 2 (no `ORDER BY`; the updated row comes back last in physical order)

**Given**
1. seqscan.
2. A = rule.
3. B = rule, but `target "/sales"`.
4. C = rule, but `target "/stock"`.
5. D = rule, but `target "/people"`.
6. `A.target = "/changed"`, then `db.flush()`.
7. `db.expire_all()`

**When**
- `result = dao.get_by_type(db, access_type=PAGE, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `ids(result) == [A.id, B.id, C.id, D.id]`.

### ACL-GT-09 — the query orders by id ascending
- **Rules:** `get_by_type` R4 [BUG-1408]
- **Kind:** bug
- **Expect:** xfail BUG-1408
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. A = rule.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_type(db, access_type=PAGE, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `".id" in order_part`.
4. statement: `"DESC" not in order_part.upper()`.
5. statement: `order_part.count(",") == 0`.

### ACL-GT-10 — with the defaults 101 rows give 100
- **Rules:** `get_by_type` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 rules E1 … E101, built with `add_all`: Ek = rule, but `target f"/p{k}"`.

**When**
- `result = dao.get_by_type(db, access_type=PAGE, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `idset(result) <= {E1.id, …, E101.id}`.

### ACL-GT-11 — limit=1000 gives all 101
- **Rules:** `get_by_type` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 rules E1 … E101, built with `add_all`: Ek = rule, but `target f"/p{k}"`.

**When**
- `result = dao.get_by_type(db, access_type=PAGE, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `idset(result) == {E1.id, …, E101.id}`.

### ACL-GT-12 — limit=0 returns an empty list
- **Rules:** `get_by_type` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = rule.
2. B = rule, but `target "/sales"`.

**When**
- `result = dao.get_by_type(db, access_type=PAGE, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### ACL-GT-13 — a negative limit raises DataError 2201W
- **Rules:** `get_by_type` R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = rule.

**When**
- `dao.get_by_type(db, access_type=PAGE, workspace_id=W1.id, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. nothing written: nothing written.

### ACL-GT-14 — a negative skip raises DataError 2201X
- **Rules:** `get_by_type` R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = rule.

**When**
- `dao.get_by_type(db, access_type=PAGE, workspace_id=W1.id, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. nothing written: nothing written.

### ACL-GT-15 — positional arguments raise TypeError
- **Rules:** `get_by_type` Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = rule.

**When**
- `dao.get_by_type(db, PAGE, W1.id)` (positional), inside `raises: TypeError`.

**Then**
1. raises: `TypeError`.

### ACL-GT-16 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `get_by_type` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = rule.
2. B = rule, but `workspace_id W2.id`.
3. `P = AccessControl(workspace_id=W1.id, type=PAGE, target="/pending", role=OWNER)`
4. `db.add(P)` (not flushed).
5. `B.target = "/edited"` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_type(db, access_type=PAGE, workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {A.id}`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. session: `B in db.dirty`.
6. session: `len(db.dirty) == 1`.
7. session: `not db.deleted`.
8. statement: `written == []`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| BUG-1409 (HR-7) — `GET /access-control/` requires `limit >= 1` (422) | `app/api/v1/endpoints/access_control.py` | `limit=0` and `limit=-1` answer 422. |
| FU-1 (a), (b) — any member can change permission rows; nothing in the backend reads them (OQ-4) | access-control endpoint / service | Owner question OQ-4. |
| FU-1 (c) — the same `type` + `target` + `role` can be stored twice | `AccessControlService` | Uniqueness, if wanted. Here GR-01, GT-01 hold today's "duplicates each returned". |
| FU-1 (d) — with both `role` and `access_type`, `access_type` is ignored | `AccessControlService.get_controls` | Branch choice. |
| Inherited `BaseDAO` methods (`get_by_workspace`, `get_by_id_and_workspace`, `create`, `update`, `remove`) and the singleton | `tests/unit/dao/base.cases.md` | Not repeated here (step 1a). |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Notes: "enums from `app.models.enums`" | The type enum's class name is not given (Postgres `accesscontroltypeenum`). Its member values are given only as `page`, `manage-order-status`, `feature`. | Conventions assume `AccessControlTypeEnum`; a different name fails at import in every `get_by_type` card. |
| 2 | `get_by_role` R3 | "returned only when `workspace_id=None`": other modules' rows with no workspace may exist in the shared test database. | GR-06, GT-07 check membership and that every row returned has no workspace, not an exact set. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_role` | Returns | ACL-GR-01 |
| `get_by_role` | R1 | ACL-GR-01, ACL-GR-02 |
| `get_by_role` | R2 | ACL-GR-03, ACL-GR-04, ACL-GR-05 |
| `get_by_role` | R3 | ACL-GR-01, ACL-GR-06 |
| `get_by_role` | R4 [BUG-1408] | ACL-GR-07, ACL-GR-08 |
| `get_by_role` | R5 | ACL-GR-09, ACL-GR-10, ACL-GR-11, ACL-GR-12, ACL-GR-13, ACL-GR-14, ACL-GR-15, ACL-GR-16, ACL-GR-17 |
| `get_by_role` | Errors row 1 | ACL-GR-05 |
| `get_by_role` | Errors row 2 | ACL-GR-16, ACL-GR-17 |
| `get_by_role` | Errors row 3 | ACL-GR-18 |
| `get_by_role` | Side effects | ACL-GR-19 |
| `get_by_type` | Returns | ACL-GT-01 |
| `get_by_type` | R1 | ACL-GT-01, ACL-GT-06, ACL-GT-07 |
| `get_by_type` | R2 | ACL-GT-02, ACL-GT-03, ACL-GT-04 |
| `get_by_type` | R3 | ACL-GT-05 |
| `get_by_type` | R4 [BUG-1408] | ACL-GT-08, ACL-GT-09 |
| `get_by_type` | R5 | ACL-GT-10, ACL-GT-11, ACL-GT-12, ACL-GT-13, ACL-GT-14 |
| `get_by_type` | Errors | ACL-GT-04, ACL-GT-13, ACL-GT-14, ACL-GT-15 |
| `get_by_type` | Side effects | ACL-GT-16 |
