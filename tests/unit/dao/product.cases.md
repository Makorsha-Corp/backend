# Test cases — `app/dao/product.py`

> **Spec:** `tests/unit/dao/product.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-02; nothing open). Q1 / BUG-1336 is the owner's own answer; P1, P2 were decided by Claude under the reviewer's delegation.
> **Revision:** 1 — spec revision 2026-11-03: `get_by_item` R3c is now [BUG-1338] (owner) and R3b covers the item; new R2a. PRD-GT-16 inverts to `[]`, strict xfail BUG-1338; new PRD-GT-24, GT-25 (R3b item parts), GT-23 (R2a). From `product.verify.md`: Finding 1 (R-3) → PRD-GW-57; Finding 2 (R-1) → PRD-GA-17; Finding 3 (R-2) → PRD-RS-10; Finding 5: the unused `newest` line is dropped from the default-limit card PRD-GW-45. Spec gap 2 is resolved by the owner's answer. No other card changed, none retired. Revision 1b: PRD-GW-57 no longer name one row on a query with no `ORDER BY`: `limit=2`, the page's size, the W1 set and `Z.id not in ids(result)`, so they hold under any row order and still fail when the workspace filter runs after `LIMIT` and Z, inserted first, is in the window (executor's "Order-fragile pass cards").
> **Counts:** 170 cases · 127 expected-to-pass · 43 expected-to-fail (bugs) · 19 deferred

## Reviewer summary
- **Per callable:** `get_by_workspace` 57 (17 bug) · `get_by_id_and_workspace` 13 · `get_by_factory_item_available` 21 · `_get_any_by_factory_item_available` 17 (17 bug) · `get_by_item` 25 (7 bug) · `soft_delete` 13 (2 bug) · `restore` 10 · `inherited` 14.
- **Depth:** full (skill step 1a): stock rows, a soft delete and restore of a row holding stock, and the one-row-per-key rule. `soft_delete`, `restore`, `create` and `update` each have one commit spy.
- **Expected-to-fail:** BUG-1325 8 (1 strict, 7 non-strict) · BUG-1326 3 (1 strict, 2 non-strict) · BUG-1327 9 (9 strict, 0 non-strict) · BUG-1328 3 (3 strict, 0 non-strict) · BUG-1335 2 (2 strict, 0 non-strict) · BUG-1336 17 (17 strict, 0 non-strict) · BUG-1338 1 (1 strict, 0 non-strict).
- **Notable design choices:**
  - `get_by_factory_item_available` R6 has no card of its own: it says there is nothing to choose between. The matrix points it at PRD-INH-04, INH-05, which test the constraint.
  - `_get_any_by_factory_item_available` does not exist: every GA card is strict xfail on `AttributeError` (`raises=AttributeError`, Conventions). No card can hold today, so none has a pass companion.
  - BUG-1336's stock half (restore, keep `qty`, 409) sits in the manager: Deferred. `restore` itself is tested here: `qty` stays, no ledger row.
  - "Takes no place in the page" on this unordered query uses `skip=2` on three rows and `skip=1` with a size check: the size holds in any physical order, so those cards stay strict.
  - The libc collation sorts "apple", "Banana", "Zulu" right with no `lower()`. The "Press" / "press" cards are the ones that see a case-sensitive sort; the item-id card sees a sort on the wrong key.
  - `updated_at` uses the database's `now()`, which does not move inside one transaction. So "moves" starts from `None` or from T0, and no card compares two stamps taken in a test.
  - Real states: a soft-deleted row carries all four columns `soft_delete` writes. `is_active` stays True on FD, as a factory's soft delete leaves it.
  - Mixed shapes: W2 rows on a soft-deleted W1 factory, a W2 row of a removed W1 item, catching a fix that joins on the parent's workspace.
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
  - BUG-1338 (owner, 2026-11-03): GT-16 is strict and has its two pass companions, "changes nothing" to the rows or the item and "back once the item is active".
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `PRD` = `app/dao/product.py`. `GW` get_by_workspace · `GI` get_by_id_and_workspace · `GK` get_by_factory_item_available · `GA` _get_any_by_factory_item_available · `GT` get_by_item · `SD` soft_delete · `RS` restore · `INH` inherited `BaseDAO` methods on `Product`.

**Actors and fixed values.**
- `dao` = the singleton `product_dao` (`from app.dao.product import product_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword (only `dao.get(db, <id>)` takes the id positionally). `result` = what the When call returns.
- `Product` = `app.models.product.Product`. `ProductLedger` = `app.models.product_ledger.ProductLedger`. `ProductCreate`, `ProductUpdate` = the schemas of `app.schemas.product`. `Item` = `app.models.item.Item`. `Factory` = `app.models.factory.Factory`. `Decimal` = `decimal.Decimal`. `datetime` = the `datetime` module's class. `select`, `text` = `sqlalchemy.select`, `sqlalchemy.text`.
- MISSING = `999999999`: an id that no row of any table has. T0 = `datetime(2026, 1, 15, 9, 0, 0)`, a past stamp.
- NOW = `datetime(2031, 5, 6, 7, 8, 9)`, far from today. **clock NOW** = during the When, `patch("app.dao.product.utcnow", create=True, return_value=NOW)`. The module does not import `utcnow` yet, so the patch is unused today.

**Externals.** `utcnow`, for `soft_delete` only, and only on the cards that say **clock NOW**. `created_at`, `updated_at` come from the database's `now()`, which does not move inside one test: a card that needs `updated_at` to move starts from `None` or from T0.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from the defaults below. A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending.
- These rows exist in every test and need no Given line (workspaces and profiles from `make_workspace`, `make_profile`; the rest built directly). Standing rows are not repeated in a Given; a line that changes one is a step.
  - W1, W2 = two `workspaces` rows. U1, U2 = two `profiles` rows.
  - F1 = `Factory(workspace_id=W1.id, name="Factory One", abbreviation="F1")`. F2 = the same, but `name "Factory Two"`, `abbreviation "F2"`.
  - FD = the same as F1, but `name "Old Plant"`, `abbreviation "OP"`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id` (soft-deleted; `is_active` stays True). FI = the same as F1, but `name "Idle Plant"`, `abbreviation "IP"`, `is_active False` (inactive but live). F9 = the same as F1, but `name "Far Plant"`, `abbreviation "F9"`, `workspace_id W2.id`.
  - I1 … I5 = `Item(workspace_id=W1.id, name=..., name_normalized=..., unit="pcs")` with names "Bolt", "Cam", "Disc", "Gear", "Hook" and each name in lower case as `name_normalized`.
  - IX = the same, but `name "Old Gasket"`, `name_normalized "old gasket"`, `is_active False` (removed). I9 = the same, but `name "Far Crate"`, `name_normalized "far crate"`, `workspace_id W2.id`.
- **stock** = `Product(workspace_id=W1.id, item_id=I1.id, factory_id=F1.id, qty=5)`; `is_available_for_sale` (False), `is_active`, `is_deleted` are left to their defaults; the card lists every column that differs. No `products` row exists unless the card's Given lists it. No Given holds two rows of one key, soft-deleted or not.
- A soft-deleted row in a Given carries `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`: everything `soft_delete` writes.
- **item** (a further row in a Given) = `Item(workspace_id=W1.id, unit="pcs", ...)` with the name given and that name in lower case as `name_normalized`.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned. `sorted(ids(result)) == [A.id, B.id]` is used where the order is not part of the check; the right-hand ids are written in Given order, which is ascending id order.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line). **unchanged(X) except `c`, …** = the same, leaving out the columns named.
- **nothing written** = the number of `products` rows stored (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- `pending:` lines check the row P and the session after the call, before anything expires them: `db.new`, `db.dirty`, `db.deleted` as the session holds them. A card lists them ahead of its `nothing written:` and `unchanged:` lines; keep that order.
- A `session:` line is a check on the session object or on an edited object, before anything expires it.
- `count:` lines count rows in all workspaces, with the filter stated.
- `read:` lines make a further read after the When and check what it gives.
- **Rolled back.** `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); the first checks run inside the savepoint; then `sp.rollback()` and the "after the savepoint rollback" checks.

**Errors.** `raises: DataError` = `sqlalchemy.exc.DataError`; `raises: IntegrityError` = `sqlalchemy.exc.IntegrityError`. Wrap the When: `with pytest.raises(<Type>) as exc:` then `with db.begin_nested():` then the When; keep using `db` afterwards (the savepoint is rolled back). Further `raises:` lines are assertions on `exc.value`, written after the `with` block, one `assert` per line. `NotNullViolation`, `UniqueViolation`, `ForeignKeyViolation`, `NumericValueOutOfRange` = classes of `psycopg2.errors`.

**xfail on the new lookup.** Every GA card also carries `raises=AttributeError` in its `pytest.mark.xfail`: `_get_any_by_factory_item_available` does not exist yet, and any other failure must show.

**xfail cards.** Write the call and the checks exactly as shown; add `pytest.mark.xfail(strict=True, reason="BUG-NNN")`, or `strict=False` on a card whose Expect line says `(non-strict)`. The assertion of a non-strict card is never weakened.

**seq scan.** Three steps at that place in the Given: `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`.

**Statement recorder.** The SQL statements the session sends from the start of the When to the end of the test are recorded. `sql` = the text of the one `SELECT` from `products`; `order_part` = the text of `sql` after its first `ORDER BY` and before any `LIMIT` (`""` when there is no `ORDER BY`); `selects` = every `SELECT` recorded; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `ProductDAO.get_by_workspace`

### PRD-GW-01 — returns a list of the live rows
- **Rules:** `get_by_workspace` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = stock, `item_id I1.id`.
2. B = stock, `item_id I2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [A.id, B.id]`.
3. returns: `isinstance(result[0], Product)`.

### PRD-GW-02 — a row of another workspace with a later id is not returned
- **Rules:** `get_by_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stock, `item_id I1.id`.
2. Z = stock, `workspace_id W2.id`, `item_id I9.id`, `factory_id F9.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PRD-GW-03 — a row of another workspace with an earlier id is not returned
- **Rules:** `get_by_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = stock, `workspace_id W2.id`, `item_id I9.id`, `factory_id F9.id`.
2. A = stock, `item_id I1.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PRD-GW-04 — a soft-deleted row is not returned
- **Rules:** `get_by_workspace` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. X = stock, `item_id I1.id`, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.
2. A = stock, `item_id I2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PRD-GW-05 — the soft-delete filter runs before the page: skip=2 past the two visible rows gives nothing
- **Rules:** `get_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = stock, `item_id I1.id`, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.
2. A = stock, `item_id I2.id`.
3. B = stock, `item_id I3.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### PRD-GW-06 — the soft-delete filter runs before the page: skip=1 leaves one visible row
- **Rules:** `get_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = stock, `item_id I1.id`, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.
2. A = stock, `item_id I2.id`.
3. B = stock, `item_id I3.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `X.id not in ids(result)`.

### PRD-GW-07 — a row with is_active False, is_deleted False is returned
- **Rules:** `get_by_workspace` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `item_id I1.id`, `is_active False`.
2. B = stock, `item_id I2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.

### PRD-GW-08 — factory_id narrows to that factory
- **Rules:** `get_by_workspace` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. X = stock, `item_id I1.id`, `factory_id F2.id`.
2. A = stock, `item_id I2.id`.
3. B = stock, `item_id I3.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, factory_id=F1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.

### PRD-GW-09 — factory_id=0 returns an empty list: 0 is a filter
- **Rules:** `get_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `item_id I1.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, factory_id=0)`.

**Then**
1. returns: `result == []`.

### PRD-GW-10 — factory_id=None applies no filter
- **Rules:** `get_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `item_id I1.id`.
2. B = stock, `item_id I2.id`, `factory_id F2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, factory_id=None)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.

### PRD-GW-11 — the factory filter runs before the page: skip=2 past the two visible rows gives nothing
- **Rules:** `get_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = stock, `item_id I1.id`, `factory_id F2.id`.
2. A = stock, `item_id I2.id`.
3. B = stock, `item_id I3.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, factory_id=F1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### PRD-GW-12 — the factory filter runs before the page: skip=1 leaves one visible row
- **Rules:** `get_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = stock, `item_id I1.id`, `factory_id F2.id`.
2. A = stock, `item_id I2.id`.
3. B = stock, `item_id I3.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, factory_id=F1.id, skip=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `X.id not in ids(result)`.

### PRD-GW-13 — is_available_for_sale=True returns only the for-sale rows
- **Rules:** `get_by_workspace` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. X = stock, `item_id I1.id`.
2. A = stock, `item_id I2.id`, `is_available_for_sale True`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, is_available_for_sale=True)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PRD-GW-14 — is_available_for_sale=False is a filter, not "no filter"
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = stock, `item_id I1.id`, `is_available_for_sale True`.
2. A = stock, `item_id I2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, is_available_for_sale=False)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PRD-GW-15 — is_available_for_sale=None returns both
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `item_id I1.id`, `is_available_for_sale True`.
2. B = stock, `item_id I1.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, is_available_for_sale=None)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.

### PRD-GW-16 — the sale filter runs before the page: skip=2 past the two visible rows gives nothing
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = stock, `item_id I1.id`, `is_available_for_sale True`.
2. A = stock, `item_id I2.id`.
3. B = stock, `item_id I3.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, is_available_for_sale=False, skip=2)`.

**Then**
1. returns: `result == []`.

### PRD-GW-17 — the sale filter runs before the page: skip=1 leaves one visible row
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = stock, `item_id I1.id`, `is_available_for_sale True`.
2. A = stock, `item_id I2.id`.
3. B = stock, `item_id I3.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, is_available_for_sale=False, skip=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `X.id not in ids(result)`.

### PRD-GW-18 — the two filters combine with AND
- **Rules:** `get_by_workspace` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = stock, `item_id I1.id`, `is_available_for_sale True`.
2. X = stock, `item_id I2.id`.
3. Y = stock, `item_id I3.id`, `factory_id F2.id`, `is_available_for_sale True`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, factory_id=F1.id, is_available_for_sale=True)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PRD-GW-19 — two filters no row meets together return an empty list
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = stock, `item_id I1.id`, `is_available_for_sale True`.
2. Y = stock, `item_id I2.id`, `factory_id F2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, factory_id=F2.id, is_available_for_sale=True)`.

**Then**
1. returns: `result == []`.

### PRD-GW-20 — a row with qty 0 is returned
- **Rules:** `get_by_workspace` R4a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `item_id I1.id`, `qty 0`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PRD-GW-21 — a row with a negative qty is returned
- **Rules:** `get_by_workspace` R4a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `item_id I1.id`, `qty -4`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PRD-GW-22 — an unknown workspace returns an empty list
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `item_id I1.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### PRD-GW-23 — a workspace with no rows returns an empty list
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `item_id I1.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### PRD-GW-24 — a row of a soft-deleted factory is not returned
- **Rules:** `get_by_workspace` R5a [BUG-1327]
- **Kind:** bug
- **Expect:** xfail BUG-1327
- **Fails today on:** Then 1 (the factory's state is not read; X is returned)

**Given**
1. X = stock, `item_id I1.id`, `factory_id FD.id`.
2. A = stock, `item_id I2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PRD-GW-25 — asked by the soft-deleted factory's id: an empty list
- **Rules:** `get_by_workspace` R5a [BUG-1327]
- **Kind:** bug
- **Expect:** xfail BUG-1327
- **Fails today on:** Then 1 (the factory's state is not read; X is returned)

**Given**
1. X = stock, `item_id I1.id`, `factory_id FD.id`.
2. A = stock, `item_id I2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, factory_id=FD.id)`.

**Then**
1. returns: `result == []`.

### PRD-GW-26 — a W2 row on a soft-deleted W1 factory is hidden too
- **Rules:** `get_by_workspace` R5a [BUG-1327]
- **Kind:** bug
- **Expect:** xfail BUG-1327
- **Fails today on:** Then 1 (the factory's state is not read; X is returned)

**Given**
1. X = stock, `workspace_id W2.id`, `item_id I9.id`, `factory_id FD.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### PRD-GW-27 — a row of a soft-deleted factory takes no place: skip=2 past the two live rows gives nothing
- **Rules:** `get_by_workspace` R5a [BUG-1327]
- **Kind:** bug
- **Expect:** xfail BUG-1327
- **Fails today on:** Then 1 (three rows are counted, so one comes back)

**Given**
1. X = stock, `item_id I1.id`, `factory_id FD.id`.
2. A = stock, `item_id I2.id`.
3. B = stock, `item_id I3.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### PRD-GW-28 — a row of a soft-deleted factory takes no place: skip=1 leaves one live row
- **Rules:** `get_by_workspace` R5a [BUG-1327]
- **Kind:** bug
- **Expect:** xfail BUG-1327
- **Fails today on:** Then 1 (three rows are counted, so two come back)

**Given**
1. X = stock, `item_id I1.id`, `factory_id FD.id`.
2. A = stock, `item_id I2.id`.
3. B = stock, `item_id I3.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `X.id not in ids(result)`.

### PRD-GW-29 — a row of a removed item is not returned
- **Rules:** `get_by_workspace` R5b [BUG-1327]
- **Kind:** bug
- **Expect:** xfail BUG-1327
- **Fails today on:** Then 1 (the item's state is not read; X is returned)

**Given**
1. X = stock, `item_id IX.id`.
2. A = stock, `item_id I2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PRD-GW-30 — a W2 row of a removed W1 item is hidden too
- **Rules:** `get_by_workspace` R5b [BUG-1327]
- **Kind:** bug
- **Expect:** xfail BUG-1327
- **Fails today on:** Then 1 (the item's state is not read; X is returned)

**Given**
1. X = stock, `workspace_id W2.id`, `item_id IX.id`, `factory_id F9.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### PRD-GW-31 — a row of a removed item takes no place: skip=2 past the two live rows gives nothing
- **Rules:** `get_by_workspace` R5b [BUG-1327]
- **Kind:** bug
- **Expect:** xfail BUG-1327
- **Fails today on:** Then 1 (three rows are counted, so one comes back)

**Given**
1. X = stock, `item_id IX.id`.
2. A = stock, `item_id I2.id`.
3. B = stock, `item_id I3.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### PRD-GW-32 — a row of a removed item takes no place: skip=1 leaves one live row
- **Rules:** `get_by_workspace` R5b [BUG-1327]
- **Kind:** bug
- **Expect:** xfail BUG-1327
- **Fails today on:** Then 1 (three rows are counted, so two come back)

**Given**
1. X = stock, `item_id IX.id`.
2. A = stock, `item_id I2.id`.
3. B = stock, `item_id I3.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `X.id not in ids(result)`.

### PRD-GW-33 — listing with a deleted factory and a removed item changes nothing
- **Rules:** `get_by_workspace` R5c
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. X = stock, `item_id I1.id`, `factory_id FD.id`.
2. Y = stock, `item_id IX.id`.
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. unchanged: unchanged(X).
3. unchanged: unchanged(Y).
4. unchanged: unchanged(FD).
5. unchanged: unchanged(IX).
6. statement: `written == []`.

### PRD-GW-34 — an inactive factory hides nothing
- **Rules:** `get_by_workspace` R5c
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `item_id I1.id`, `factory_id FI.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PRD-GW-35 — once the factory is live again the row is back, unchanged
- **Rules:** `get_by_workspace` R5c
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. X = stock, `item_id I1.id`, `factory_id FD.id`.
2. `FD.is_deleted = False`
3. `FD.deleted_at = None`
4. `FD.deleted_by = None`
5. `db.flush()`

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [X.id]`.
2. unchanged: unchanged(X).

### PRD-GW-36 — once the item is active again the row is back, unchanged
- **Rules:** `get_by_workspace` R5c
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. X = stock, `item_id IX.id`.
2. `IX.is_active = True`
3. `db.flush()`

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [X.id]`.
2. unchanged: unchanged(X).

### PRD-GW-37 — the query orders by name, then id, ascending
- **Rules:** `get_by_workspace` R6 [BUG-1325]
- **Kind:** bug
- **Expect:** xfail BUG-1325
- **Fails today on:** Then 2 (no `ORDER BY` is requested)

**Given**
1. A = stock, `item_id I1.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"name" in order_part`.
4. statement: `"products.id" in order_part`.
5. statement: `order_part.index("name") < order_part.index("products.id")`.
6. statement: `"DESC" not in order_part.upper()`.
7. statement: `order_part.count(",") == 1`.

### PRD-GW-38 — item names come back case-insensitively: "apple", "Banana", "Zulu"
- **Rules:** `get_by_workspace` R6 [BUG-1325]
- **Kind:** bug
- **Expect:** xfail BUG-1325 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. IZ = item, `name "Zulu"`.
3. IA = item, `name "apple"`.
4. IB = item, `name "Banana"`.
5. A = stock, `item_id IZ.id`.
6. B = stock, `item_id IA.id`.
7. C = stock, `item_id IB.id`.
8. `db.expire_all()`

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [B.id, C.id, A.id]`.

### PRD-GW-39 — "Press" and "press" tie on the item name: the lower row id comes first, capital first
- **Rules:** `get_by_workspace` R6 [BUG-1325]
- **Kind:** bug
- **Expect:** xfail BUG-1325 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. IP = item, `name "Press"`, `name_normalized "press one"`.
3. IQ = item, `name "press"`, `name_normalized "press two"`.
4. A = stock, `item_id IP.id`.
5. B = stock, `item_id IQ.id`.
6. `db.expire_all()`

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [A.id, B.id]`.

### PRD-GW-40 — "press" and "Press" tie on the item name: the lower row id comes first, small letter first
- **Rules:** `get_by_workspace` R6 [BUG-1325]
- **Kind:** bug
- **Expect:** xfail BUG-1325 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. IP = item, `name "press"`, `name_normalized "press one"`.
3. IQ = item, `name "Press"`, `name_normalized "press two"`.
4. A = stock, `item_id IP.id`.
5. B = stock, `item_id IQ.id`.
6. `db.expire_all()`

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [A.id, B.id]`.

### PRD-GW-41 — rows of one item tie: the row id decides, when factory, flag and qty would each sort otherwise and the lowest id was updated
- **Rules:** `get_by_workspace` R6 [BUG-1325]
- **Kind:** bug
- **Expect:** xfail BUG-1325 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = stock, `factory_id F2.id`, `qty 7`.
3. B = stock, `factory_id F1.id`, `qty 9`, `is_available_for_sale True`.
4. C = stock, `factory_id F1.id`, `qty 5`.
5. `A.qty = 8`, then `db.flush()`.
6. `db.expire_all()`

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### PRD-GW-42 — a row of a higher item id with an earlier name comes first: item id is not the key
- **Rules:** `get_by_workspace` R6 [BUG-1325]
- **Kind:** bug
- **Expect:** xfail BUG-1325 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = stock, `item_id I3.id`.
3. B = stock, `item_id I1.id`.
4. C = stock, `item_id I2.id`.
5. `db.expire_all()`

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [B.id, C.id, A.id]`.

### PRD-GW-43 — the order is applied before the page is cut
- **Rules:** `get_by_workspace` R6 [BUG-1325]
- **Kind:** bug
- **Expect:** xfail BUG-1325 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. IZ = item, `name "Zulu"`.
3. IA = item, `name "apple"`.
4. IB = item, `name "Banana"`.
5. A = stock, `item_id IZ.id`.
6. B = stock, `item_id IA.id`.
7. C = stock, `item_id IB.id`.
8. `db.expire_all()`

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `ids(result) == [C.id]`.

### PRD-GW-44 — rows paged one at a time neither repeat nor miss a row
- **Rules:** `get_by_workspace` R6 [BUG-1325], R7
- **Kind:** bug
- **Expect:** xfail BUG-1325 (non-strict)
- **Fails today on:** Then 2 (the rows have no fixed order; which row is on which page rests on physical row order)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = stock, `item_id I3.id`.
3. B = stock, `item_id I1.id`.
4. C = stock, `item_id I2.id`.
5. D = stock, `item_id I5.id`.
6. E = stock, `item_id I4.id`.
7. `B.qty = 8`, then `db.flush()`.
8. `db.expire_all()`

**When**
- `pages = [dao.get_by_workspace(db, workspace_id=W1.id, skip=k, limit=1) for k in range(5)]` (one list comprehension: a single window cannot show this).

**Then**
1. returns: `[len(p) for p in pages] == [1, 1, 1, 1, 1]`.
2. returns: `[p[0].id for p in pages] == [B.id, C.id, A.id, E.id, D.id]`.

### PRD-GW-45 — with the defaults 101 rows give 100
- **Rules:** `get_by_workspace` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 items I_1 … I_101, built with `add_all`: I_k = item, `name` = `f"Item {k:03d}"`.
2. 101 rows E1 … E101, built with `add_all`: Ek = stock, `item_id` = `I_k.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `len(set(ids(result))) == 100`.

### PRD-GW-46 — limit=1000 gives all 101
- **Rules:** `get_by_workspace` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 items I_1 … I_101, built with `add_all`: I_k = item, `name` = `f"Item {k:03d}"`.
2. 101 rows E1 … E101, built with `add_all`: Ek = stock, `item_id` = `I_k.id`.
3. `newest` = the ids of E1 … E101.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `sorted(ids(result)) == sorted(newest)`.

### PRD-GW-47 — skip and limit cut one row from the middle
- **Rules:** `get_by_workspace` R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = stock, `item_id I1.id`.
2. B = stock, `item_id I2.id`.
3. C = stock, `item_id I3.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `len(result) == 1`.

### PRD-GW-48 — limit=0 returns an empty list
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `item_id I1.id`.
2. B = stock, `item_id I2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### PRD-GW-49 — limit=1 returns one row
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `item_id I1.id`.
2. B = stock, `item_id I2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `len(result) == 1`.

### PRD-GW-50 — skip at the number of rows returns an empty list
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `item_id I1.id`.
2. B = stock, `item_id I2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### PRD-GW-51 — skip at the last row returns one row
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `item_id I1.id`.
2. B = stock, `item_id I2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 1`.

### PRD-GW-52 — a negative limit raises
- **Rules:** `get_by_workspace` R8, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = stock, `item_id I1.id`.
2. B = stock, `item_id I2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### PRD-GW-53 — a negative skip raises
- **Rules:** `get_by_workspace` R8, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = stock, `item_id I1.id`.
2. B = stock, `item_id I2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### PRD-GW-54 — each row carries its item's name and unit, with no further query
- **Rules:** `get_by_workspace` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = stock, `item_id I2.id`.
2. `w = W1.id`
3. `db.expire_all()`
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_workspace(db, workspace_id=w)`.

**Then**
1. returns: `result[0].item_name == "Cam"`.
2. returns: `result[0].item_unit == "pcs"`.
3. statement: `len(selects) == 1`.

### PRD-GW-55 — writes nothing: a pending row that would sort first stays pending and is not returned
- **Rules:** `get_by_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock, `item_id I2.id`.
2. `P = Product(workspace_id=W1.id, item_id=I5.id, factory_id=F2.id, qty=1)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. pending: `not db.dirty and not db.deleted`.
6. nothing written: nothing written.
7. unchanged: unchanged(A).
8. statement: `written == []`.

### PRD-GW-56 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_by_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock, `item_id I1.id`.
2. B = stock, `item_id I2.id`.
3. `B.note = "Edited"` (not flushed).

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `B.note == "Edited"`.

### PRD-GW-57 — another workspace's row takes no place in the page, whatever the row order
- **Rules:** `get_by_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Z = stock, `workspace_id W2.id`, `item_id I9.id`, `factory_id F9.id`.
2. A = stock, `item_id I4.id`.
3. B = stock, `item_id I5.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `sorted(ids(result)) == [A.id, B.id]`.
3. returns: `Z.id not in ids(result)`.

## `ProductDAO.get_by_id_and_workspace`

### PRD-GI-01 — returns the row with that id
- **Rules:** `get_by_id_and_workspace` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. B = stock, `item_id I2.id`.
2. A = stock, `item_id I1.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Product)`.
2. returns: `result.id == A.id`.
3. returns: `result.workspace_id == W1.id`, `result.item_id == I1.id`, `result.factory_id == F1.id`, `result.qty == 5`.

### PRD-GI-02 — another workspace's id returns None, when that row is the later one
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stock, `item_id I1.id`.
2. Z = stock, `workspace_id W2.id`, `item_id I9.id`, `factory_id F9.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PRD-GI-03 — another workspace's id returns None, when that row is the earlier one
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = stock, `workspace_id W2.id`, `item_id I9.id`, `factory_id F9.id`.
2. A = stock, `item_id I1.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PRD-GI-04 — the id under another workspace returns None
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stock, `item_id I1.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### PRD-GI-05 — an unknown id returns None
- **Rules:** `get_by_id_and_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `item_id I1.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PRD-GI-06 — id=0 returns None
- **Rules:** `get_by_id_and_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `item_id I1.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PRD-GI-07 — writes nothing: a read that finds nothing leaves the session as it was
- **Rules:** `get_by_id_and_workspace` R3, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock, `item_id I1.id`.
2. `P = Product(workspace_id=W1.id, item_id=I5.id, factory_id=F2.id, qty=1)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. pending: `not db.dirty and not db.deleted`.
6. nothing written: nothing written.
7. unchanged: unchanged(A).
8. statement: `written == []`.

### PRD-GI-08 — writes nothing: a read that finds its row leaves the session as it was
- **Rules:** `get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock, `item_id I1.id`.
2. `P = Product(workspace_id=W1.id, item_id=I5.id, factory_id=F2.id, qty=1)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. pending: `not db.dirty and not db.deleted`.
6. nothing written: nothing written.
7. unchanged: unchanged(A).
8. statement: `written == []`.

### PRD-GI-09 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock, `item_id I1.id`.
2. B = stock, `item_id I2.id`.
3. `B.note = "Edited"` (not flushed).

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `B.note == "Edited"`.

### PRD-GI-10 — a soft-deleted row is returned
- **Rules:** `get_by_id_and_workspace` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `item_id I1.id`, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.is_deleted is True`.

### PRD-GI-11 — a row of a soft-deleted factory is returned
- **Rules:** `get_by_id_and_workspace` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `item_id I1.id`, `factory_id FD.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### PRD-GI-12 — a row of a removed item is returned
- **Rules:** `get_by_id_and_workspace` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `item_id IX.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### PRD-GI-13 — the query does not read the parent tables
- **Rules:** `get_by_id_and_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `item_id I1.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. statement: `"factories" not in sql`.

## `ProductDAO.get_by_factory_item_available`

### PRD-GK-01 — returns the row with that key
- **Rules:** `get_by_factory_item_available` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. X = stock, `item_id I2.id`.
2. A = stock.

**When**
- `result = dao.get_by_factory_item_available(db, factory_id=F1.id, item_id=I1.id, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Product)`.
2. returns: `result.id == A.id`.
3. returns: `result.qty == 5`.

### PRD-GK-02 — the not-for-sale row is told from the for-sale row
- **Rules:** `get_by_factory_item_available` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. X = stock, `is_available_for_sale True`.
2. A = stock.

**When**
- `result = dao.get_by_factory_item_available(db, factory_id=F1.id, item_id=I1.id, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### PRD-GK-03 — the for-sale row is told from the not-for-sale row
- **Rules:** `get_by_factory_item_available` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = stock.
2. B = stock, `is_available_for_sale True`.

**When**
- `result = dao.get_by_factory_item_available(db, factory_id=F1.id, item_id=I1.id, is_available_for_sale=True, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == B.id`.

### PRD-GK-04 — another factory is not matched
- **Rules:** `get_by_factory_item_available` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock.

**When**
- `result = dao.get_by_factory_item_available(db, factory_id=F2.id, item_id=I1.id, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PRD-GK-05 — another item is not matched
- **Rules:** `get_by_factory_item_available` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock.

**When**
- `result = dao.get_by_factory_item_available(db, factory_id=F1.id, item_id=I2.id, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PRD-GK-06 — another sale state is not matched
- **Rules:** `get_by_factory_item_available` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock.

**When**
- `result = dao.get_by_factory_item_available(db, factory_id=F1.id, item_id=I1.id, is_available_for_sale=True, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PRD-GK-07 — is_available_for_sale=False is matched as a value
- **Rules:** `get_by_factory_item_available` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `is_available_for_sale True`.

**When**
- `result = dao.get_by_factory_item_available(db, factory_id=F1.id, item_id=I1.id, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PRD-GK-08 — another workspace is not matched
- **Rules:** `get_by_factory_item_available` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stock.

**When**
- `result = dao.get_by_factory_item_available(db, factory_id=F1.id, item_id=I1.id, is_available_for_sale=False, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### PRD-GK-09 — a W2 row of that key is not matched, when it is the earlier one
- **Rules:** `get_by_factory_item_available` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = stock, `workspace_id W2.id`.

**When**
- `result = dao.get_by_factory_item_available(db, factory_id=F1.id, item_id=I1.id, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PRD-GK-10 — a W2 row of that key is not picked over the W1 row, when it is the earlier one
- **Rules:** `get_by_factory_item_available` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = stock, `workspace_id W2.id`.
2. A = stock.

**When**
- `result = dao.get_by_factory_item_available(db, factory_id=F1.id, item_id=I1.id, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### PRD-GK-11 — the W2 row of that key answers W2, when it is the later one
- **Rules:** `get_by_factory_item_available` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stock.
2. Z = stock, `workspace_id W2.id`.

**When**
- `result = dao.get_by_factory_item_available(db, factory_id=F1.id, item_id=I1.id, is_available_for_sale=False, workspace_id=W2.id)`.

**Then**
1. returns: `result.id == Z.id`.

### PRD-GK-12 — factory_id=0 returns None
- **Rules:** `get_by_factory_item_available` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock.

**When**
- `result = dao.get_by_factory_item_available(db, factory_id=0, item_id=I1.id, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PRD-GK-13 — an unknown item returns None and creates no row
- **Rules:** `get_by_factory_item_available` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock.

**When**
- `result = dao.get_by_factory_item_available(db, factory_id=F1.id, item_id=MISSING, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. count: `products` has exactly 1 row.

### PRD-GK-14 — a soft-deleted row is not found, although it holds the key
- **Rules:** `get_by_factory_item_available` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. X = stock, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.

**When**
- `result = dao.get_by_factory_item_available(db, factory_id=F1.id, item_id=I1.id, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PRD-GK-15 — a soft-deleted for-sale row does not hide the live not-for-sale row
- **Rules:** `get_by_factory_item_available` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. X = stock, `is_available_for_sale True`, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.
2. A = stock.

**When**
- `result = dao.get_by_factory_item_available(db, factory_id=F1.id, item_id=I1.id, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### PRD-GK-16 — a row of a soft-deleted factory is found
- **Rules:** `get_by_factory_item_available` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `factory_id FD.id`.

**When**
- `result = dao.get_by_factory_item_available(db, factory_id=FD.id, item_id=I1.id, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### PRD-GK-17 — a row of a removed item is found
- **Rules:** `get_by_factory_item_available` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `item_id IX.id`.

**When**
- `result = dao.get_by_factory_item_available(db, factory_id=F1.id, item_id=IX.id, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### PRD-GK-18 — the query does not read the factory
- **Rules:** `get_by_factory_item_available` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_factory_item_available(db, factory_id=F1.id, item_id=I1.id, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. statement: `"factories" not in sql`.

### PRD-GK-19 — a row with is_active False, is_deleted False is found
- **Rules:** `get_by_factory_item_available` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `is_active False`.

**When**
- `result = dao.get_by_factory_item_available(db, factory_id=F1.id, item_id=I1.id, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### PRD-GK-20 — writes nothing: a pending row of that key stays pending and is not returned
- **Rules:** `get_by_factory_item_available` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock, `item_id I2.id`.
2. `P = Product(workspace_id=W1.id, item_id=I1.id, factory_id=F1.id, qty=1)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_factory_item_available(db, factory_id=F1.id, item_id=I1.id, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. pending: `not db.dirty and not db.deleted`.
6. nothing written: nothing written.
7. unchanged: unchanged(A).
8. statement: `written == []`.

### PRD-GK-21 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_by_factory_item_available` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock.
2. B = stock, `item_id I2.id`.
3. `B.note = "Edited"` (not flushed).

**When**
- `result = dao.get_by_factory_item_available(db, factory_id=F1.id, item_id=I1.id, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `B.note == "Edited"`.

## `ProductDAO._get_any_by_factory_item_available`

### PRD-GA-01 — returns a live row with that key
- **Rules:** `_get_any_by_factory_item_available` R1 [BUG-1336], Returns
- **Kind:** bug
- **Expect:** xfail BUG-1336
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. X = stock, `item_id I2.id`.
2. A = stock.

**When**
- `result = dao._get_any_by_factory_item_available(db, factory_id=F1.id, item_id=I1.id, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Product)`.
2. returns: `result.id == A.id`.

### PRD-GA-02 — returns a soft-deleted row with that key, with its qty
- **Rules:** `_get_any_by_factory_item_available` R1 [BUG-1336]
- **Kind:** bug
- **Expect:** xfail BUG-1336
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. A = stock, `qty 5`, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.

**When**
- `result = dao._get_any_by_factory_item_available(db, factory_id=F1.id, item_id=I1.id, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.is_deleted is True`.
3. returns: `result.qty == 5`.

### PRD-GA-03 — the not-for-sale row is told from the for-sale row
- **Rules:** `_get_any_by_factory_item_available` R1 [BUG-1336]
- **Kind:** bug
- **Expect:** xfail BUG-1336
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. X = stock, `is_available_for_sale True`.
2. A = stock.

**When**
- `result = dao._get_any_by_factory_item_available(db, factory_id=F1.id, item_id=I1.id, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### PRD-GA-04 — the for-sale row is told from the not-for-sale row, deleted
- **Rules:** `_get_any_by_factory_item_available` R1 [BUG-1336]
- **Kind:** bug
- **Expect:** xfail BUG-1336
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. A = stock.
2. B = stock, `is_available_for_sale True`, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.

**When**
- `result = dao._get_any_by_factory_item_available(db, factory_id=F1.id, item_id=I1.id, is_available_for_sale=True, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == B.id`.

### PRD-GA-05 — a row of a soft-deleted factory is found
- **Rules:** `_get_any_by_factory_item_available` R1 [BUG-1336]
- **Kind:** bug
- **Expect:** xfail BUG-1336
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. A = stock, `factory_id FD.id`.

**When**
- `result = dao._get_any_by_factory_item_available(db, factory_id=FD.id, item_id=I1.id, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### PRD-GA-06 — a row of a removed item is found
- **Rules:** `_get_any_by_factory_item_available` R1 [BUG-1336]
- **Kind:** bug
- **Expect:** xfail BUG-1336
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. A = stock, `item_id IX.id`.

**When**
- `result = dao._get_any_by_factory_item_available(db, factory_id=F1.id, item_id=IX.id, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### PRD-GA-07 — another factory is not matched
- **Rules:** `_get_any_by_factory_item_available` R2 [BUG-1336]
- **Kind:** bug
- **Expect:** xfail BUG-1336
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. A = stock, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.

**When**
- `result = dao._get_any_by_factory_item_available(db, factory_id=F2.id, item_id=I1.id, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PRD-GA-08 — another item is not matched
- **Rules:** `_get_any_by_factory_item_available` R2 [BUG-1336]
- **Kind:** bug
- **Expect:** xfail BUG-1336
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. A = stock, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.

**When**
- `result = dao._get_any_by_factory_item_available(db, factory_id=F1.id, item_id=I2.id, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PRD-GA-09 — another sale state is not matched
- **Rules:** `_get_any_by_factory_item_available` R2 [BUG-1336]
- **Kind:** bug
- **Expect:** xfail BUG-1336
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. A = stock, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.

**When**
- `result = dao._get_any_by_factory_item_available(db, factory_id=F1.id, item_id=I1.id, is_available_for_sale=True, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PRD-GA-10 — another workspace is not matched
- **Rules:** `_get_any_by_factory_item_available` R2 [BUG-1336]
- **Kind:** bug
- **Expect:** xfail BUG-1336
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. A = stock, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.

**When**
- `result = dao._get_any_by_factory_item_available(db, factory_id=F1.id, item_id=I1.id, is_available_for_sale=False, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### PRD-GA-11 — factory_id=0 returns None
- **Rules:** `_get_any_by_factory_item_available` R2 [BUG-1336]
- **Kind:** bug
- **Expect:** xfail BUG-1336
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. A = stock, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.

**When**
- `result = dao._get_any_by_factory_item_available(db, factory_id=0, item_id=I1.id, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PRD-GA-12 — a W2 row of that key is not matched, when it is the earlier one
- **Rules:** `_get_any_by_factory_item_available` R2 [BUG-1336]
- **Kind:** bug
- **Expect:** xfail BUG-1336
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. Z = stock, `workspace_id W2.id`.
2. A = stock.

**When**
- `result = dao._get_any_by_factory_item_available(db, factory_id=F1.id, item_id=I1.id, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### PRD-GA-13 — no match returns None and creates no row
- **Rules:** `_get_any_by_factory_item_available` R2 [BUG-1336]
- **Kind:** bug
- **Expect:** xfail BUG-1336
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. A = stock.

**When**
- `result = dao._get_any_by_factory_item_available(db, factory_id=F1.id, item_id=MISSING, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. count: `products` has exactly 1 row.

### PRD-GA-14 — a soft-deleted row stays soft-deleted
- **Rules:** `_get_any_by_factory_item_available` R3 [BUG-1336]
- **Kind:** bug
- **Expect:** xfail BUG-1336
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. A = stock, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao._get_any_by_factory_item_available(db, factory_id=F1.id, item_id=I1.id, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. unchanged: unchanged(A).
3. statement: `written == []`.

### PRD-GA-15 — writes nothing: a pending row of that key stays pending and is not returned
- **Rules:** `_get_any_by_factory_item_available` R3 [BUG-1336], Side effects
- **Kind:** bug
- **Expect:** xfail BUG-1336
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. A = stock, `item_id I2.id`.
2. `P = Product(workspace_id=W1.id, item_id=I1.id, factory_id=F1.id, qty=1)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao._get_any_by_factory_item_available(db, factory_id=F1.id, item_id=I1.id, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. pending: `not db.dirty and not db.deleted`.
6. nothing written: nothing written.
7. unchanged: unchanged(A).
8. statement: `written == []`.

### PRD-GA-16 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `_get_any_by_factory_item_available` R3 [BUG-1336], Side effects
- **Kind:** bug
- **Expect:** xfail BUG-1336
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. A = stock.
2. B = stock, `item_id I2.id`.
3. `B.note = "Edited"` (not flushed).

**When**
- `result = dao._get_any_by_factory_item_available(db, factory_id=F1.id, item_id=I1.id, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `B.note == "Edited"`.

### PRD-GA-17 — a W2 row is not found for W1, even soft-deleted
- **Rules:** `_get_any_by_factory_item_available` R2 [BUG-1336]
- **Kind:** bug
- **Expect:** xfail BUG-1336
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. Z = stock, `workspace_id W2.id`, `factory_id F9.id`, `item_id I9.id`, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.

**When**
- `result = dao._get_any_by_factory_item_available(db, factory_id=F9.id, item_id=I9.id, is_available_for_sale=False, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

## `ProductDAO.get_by_item`

### PRD-GT-01 — returns a list of the item's rows, for sale or not
- **Rules:** `get_by_item` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = stock.
2. B = stock, `is_available_for_sale True`.
3. C = stock, `factory_id F2.id`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [A.id, B.id, C.id]`.
3. returns: `isinstance(result[0], Product)`.

### PRD-GT-02 — rows are returned whatever their quantities
- **Rules:** `get_by_item` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `qty 0`.
2. B = stock, `is_available_for_sale True`, `qty -4`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.

### PRD-GT-03 — a row of another item is not returned
- **Rules:** `get_by_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X = stock, `item_id I2.id`.
2. A = stock.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PRD-GT-04 — the right item under another workspace returns an empty list
- **Rules:** `get_by_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stock.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### PRD-GT-05 — a W2 row of that item is not returned for W1, when it is the earlier one
- **Rules:** `get_by_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = stock, `workspace_id W2.id`, `factory_id F9.id`.
2. A = stock.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PRD-GT-06 — a soft-deleted row is not returned
- **Rules:** `get_by_item` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. X = stock, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.
2. A = stock, `is_available_for_sale True`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PRD-GT-07 — an unknown item returns an empty list
- **Rules:** `get_by_item` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock.

**When**
- `result = dao.get_by_item(db, item_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PRD-GT-08 — item_id=0 returns an empty list
- **Rules:** `get_by_item` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock.

**When**
- `result = dao.get_by_item(db, item_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PRD-GT-09 — an item with no rows returns an empty list
- **Rules:** `get_by_item` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock.

**When**
- `result = dao.get_by_item(db, item_id=I2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PRD-GT-10 — a row of a soft-deleted factory is not returned
- **Rules:** `get_by_item` R3a [BUG-1328]
- **Kind:** bug
- **Expect:** xfail BUG-1328
- **Fails today on:** Then 1 (the factory's state is not read; both rows are returned)

**Given**
1. A = stock.
2. X = stock, `factory_id FD.id`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PRD-GT-11 — only in a soft-deleted factory: an empty list
- **Rules:** `get_by_item` R3a [BUG-1328]
- **Kind:** bug
- **Expect:** xfail BUG-1328
- **Fails today on:** Then 1 (the factory's state is not read; X is returned)

**Given**
1. X = stock, `factory_id FD.id`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PRD-GT-12 — a W2 row on a soft-deleted W1 factory is hidden too
- **Rules:** `get_by_item` R3a [BUG-1328]
- **Kind:** bug
- **Expect:** xfail BUG-1328
- **Fails today on:** Then 1 (the factory's state is not read; X is returned)

**Given**
1. X = stock, `workspace_id W2.id`, `factory_id FD.id`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### PRD-GT-13 — reading with a soft-deleted factory changes nothing
- **Rules:** `get_by_item` R3b
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. X = stock, `factory_id FD.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. unchanged: unchanged(X).
3. unchanged: unchanged(FD).
4. statement: `written == []`.

### PRD-GT-14 — an inactive factory hides nothing
- **Rules:** `get_by_item` R3b
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `factory_id FI.id`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### PRD-GT-15 — once the factory is live again the row is back, unchanged
- **Rules:** `get_by_item` R3b
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. X = stock, `factory_id FD.id`.
2. `FD.is_deleted = False`
3. `FD.deleted_at = None`
4. `FD.deleted_by = None`
5. `db.flush()`

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [X.id]`.
2. unchanged: unchanged(X).

### PRD-GT-16 — the rows of a removed item are not returned
- **Rules:** `get_by_item` R3c [BUG-1338]
- **Kind:** bug
- **Expect:** xfail BUG-1338
- **Fails today on:** Then 1 (the item's state is not read; A is returned)

**Given**
1. A = stock, `item_id IX.id`.

**When**
- `result = dao.get_by_item(db, item_id=IX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PRD-GT-17 — the query orders by id, ascending
- **Rules:** `get_by_item` R4 [BUG-1326]
- **Kind:** bug
- **Expect:** xfail BUG-1326
- **Fails today on:** Then 2 (no `ORDER BY` is requested)

**Given**
1. A = stock.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `".id" in order_part`.
4. statement: `"DESC" not in order_part.upper()`.
5. statement: `order_part.count(",") == 0`.

### PRD-GT-18 — rows come back by id, when the lowest id was updated
- **Rules:** `get_by_item` R4 [BUG-1326]
- **Kind:** bug
- **Expect:** xfail BUG-1326 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = stock.
3. B = stock, `is_available_for_sale True`.
4. C = stock, `factory_id F2.id`.
5. `A.qty = 8`, then `db.flush()`.
6. `db.expire_all()`

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### PRD-GT-19 — rows come back by id, when factory, flag and qty would each sort otherwise
- **Rules:** `get_by_item` R4 [BUG-1326]
- **Kind:** bug
- **Expect:** xfail BUG-1326 (non-strict)
- **Fails today on:** Then 2 (the result rests on physical row order, which can match the intended one by accident)

**Given**
1. Force a sequential scan (**seq scan**, Conventions).
2. A = stock, `factory_id F2.id`, `is_available_for_sale True`, `qty 7`.
3. B = stock, `qty 9`.
4. C = stock, `is_available_for_sale True`, `qty 5`.
5. `db.expire_all()`

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### PRD-GT-20 — there is no cap: 101 rows give 101
- **Rules:** `get_by_item` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 51 factories F_1 … F_51, built with `add_all`: F_k = `Factory(workspace_id=W1.id, name=f"Plant {k}", abbreviation=f"P{k}")`.
2. 101 rows, built with `add_all`: for k in 1 … 50 two rows on F_k, `is_available_for_sale` False and True; one row on F_51, `is_available_for_sale False`; all stock, `item_id I1.id`.
3. `all_ids` = the ids of those 101 rows.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `sorted(ids(result)) == sorted(all_ids)`.

### PRD-GT-21 — writes nothing: a pending row that would sort first stays pending and is not returned
- **Rules:** `get_by_item` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock, `is_available_for_sale True`.
2. `P = Product(workspace_id=W1.id, item_id=I5.id, factory_id=F2.id, qty=1)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. pending: `not db.dirty and not db.deleted`.
6. nothing written: nothing written.
7. unchanged: unchanged(A).
8. statement: `written == []`.

### PRD-GT-22 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_by_item` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock.
2. B = stock, `is_available_for_sale True`.
3. `B.note = "Edited"` (not flushed).

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `B.note == "Edited"`.

### PRD-GT-23 — a row with is_active False, is_deleted False is returned
- **Rules:** `get_by_item` R2a
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `is_active False`.
2. B = stock, `is_available_for_sale True`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.

### PRD-GT-24 — reading a removed item changes nothing, to its rows or to the item
- **Rules:** `get_by_item` R3b
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock, `item_id IX.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_item(db, item_id=IX.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. unchanged: unchanged(A).
3. unchanged: unchanged(IX).
4. statement: `written == []`.

### PRD-GT-25 — once the item is active again its rows are back, unchanged
- **Rules:** `get_by_item` R3b
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `item_id IX.id`.
2. `IX.is_active = True`
3. `db.flush()`

**When**
- `result = dao.get_by_item(db, item_id=IX.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.
2. unchanged: unchanged(A).

## `ProductDAO.soft_delete`

### PRD-SD-01 — sets the three flags and returns the same object
- **Rules:** `soft_delete` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = stock.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_deleted is True`, `is_active is False`, `deleted_by == U2.id`.

### PRD-SD-02 — every other column keeps its value
- **Rules:** `soft_delete` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock, `qty 4`, `avg_cost Decimal("2.50")`, `selling_price Decimal("3.75")`, `min_order_qty 2`, `is_available_for_sale True`, `note "Keep"`, `created_by U1.id`, `updated_by U1.id`.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=U2.id)`.

**Then**
1. returns: `result is A`.
2. unchanged: unchanged(A) except `is_deleted`, `is_active`, `deleted_by`, `deleted_at`, `updated_at`.
3. re-read A: `qty == 4`, `avg_cost == Decimal("2.50")`, `selling_price == Decimal("3.75")`.

### PRD-SD-03 — no ledger row is written
- **Rules:** `soft_delete` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock, `qty 4`, `avg_cost Decimal("2.50")`, `selling_price Decimal("3.75")`, `min_order_qty 2`, `is_available_for_sale True`, `note "Keep"`, `created_by U1.id`, `updated_by U1.id`.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=U2.id)`.

**Then**
1. returns: `result is A`.
2. count: `product_ledger` has exactly 0 rows.

### PRD-SD-04 — updated_at moves from None, and updated_by stays
- **Rules:** `soft_delete` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock, `updated_by U1.id`.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `updated_at is not None`.
3. re-read A: `updated_by == U1.id`.

### PRD-SD-05 — updated_at moves from a past stamp
- **Rules:** `soft_delete` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock, `updated_at T0`.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `updated_at != T0`.

### PRD-SD-06 — deleted_at is set
- **Rules:** `soft_delete` R3a
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `deleted_at is not None`.

### PRD-SD-07 — deleted_at comes from utcnow, naive
- **Rules:** `soft_delete` R3a [BUG-1335]
- **Kind:** bug
- **Expect:** xfail BUG-1335
- **Fails today on:** Then 2 (the value is the database's `now()`)

**Given**
1. A = stock.
2. clock NOW.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `deleted_at == NOW`.

### PRD-SD-08 — deleted_at comes from utcnow under any session time zone
- **Rules:** `soft_delete` R3a [BUG-1335]
- **Kind:** bug
- **Expect:** xfail BUG-1335
- **Fails today on:** Then 2 (the value is the database's `now()`)

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))`
2. A = stock.
3. clock NOW.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `deleted_at == NOW`.

### PRD-SD-09 — the row stops being found by the three reads and is found by id
- **Rules:** `soft_delete` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=U2.id)`.

**Then**
1. returns: `result is A`.
2. read: `dao.get_by_workspace(db, workspace_id=W1.id) == []`.
3. read: `dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id) == []`.
4. read: `dao.get_by_factory_item_available(db, factory_id=F1.id, item_id=I1.id, is_available_for_sale=False, workspace_id=W1.id) is None`.
5. read: `dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id).id == A.id`.

### PRD-SD-10 — on a row already deleted it raises nothing and overwrites deleted_at and deleted_by
- **Rules:** `soft_delete` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `deleted_by == U2.id`, `deleted_at != T0`.
3. re-read A: `is_deleted is True`, `is_active is False`.

### PRD-SD-11 — not committed: a rollback restores the row
- **Rules:** `soft_delete` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=U2.id)`.

**Then**
1. returns: `result is A`.
2. count: inside the savepoint, `products` has exactly 1 row with `is_deleted` True.
3. count: after the savepoint rollback, `products` has exactly 1 row with `is_deleted` False.
4. mock called: the `db.commit` spy was never called.
5. re-read A: `is_active is True`, `deleted_by is None`, `deleted_at is None`.

### PRD-SD-12 — an unknown deleted_by fails on flush and changes nothing
- **Rules:** `soft_delete` Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = stock.

**When**
- `dao.soft_delete(db, db_obj=A, deleted_by=MISSING)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `exc.value.orig.pgcode == "23503"`.
4. unchanged: unchanged(A).

### PRD-SD-13 — one row is updated and flushed; another stays as it was
- **Rules:** `soft_delete` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock.
2. B = stock, `item_id I2.id`.
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.soft_delete(db, db_obj=A, deleted_by=U2.id)`.

**Then**
1. returns: `result is A`.
2. statement: `len(written) == 1`.
3. session: `not db.dirty`.
4. unchanged: unchanged(B).

## `ProductDAO.restore`

### PRD-RS-01 — clears the four fields and returns the same object
- **Rules:** `restore` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = stock, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_active is True`, `is_deleted is False`, `deleted_at is None`, `deleted_by is None`.

### PRD-RS-02 — qty and every other column keep their values
- **Rules:** `restore` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock, `qty 4`, `avg_cost Decimal("2.50")`, `selling_price Decimal("3.75")`, `min_order_qty 2`, `is_available_for_sale True`, `note "Keep"`, `created_by U1.id`, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. unchanged: unchanged(A) except `is_active`, `is_deleted`, `deleted_at`, `deleted_by`, `updated_at`.
3. re-read A: `qty == 4`, `avg_cost == Decimal("2.50")`.

### PRD-RS-03 — no ledger row is written
- **Rules:** `restore` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock, `qty 4`, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. count: `product_ledger` has exactly 0 rows.

### PRD-RS-04 — updated_at moves, and updated_by stays
- **Rules:** `restore` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock, `updated_at T0`, `updated_by U1.id`, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. re-read A: `updated_at != T0`.
3. re-read A: `updated_by == U1.id`.

### PRD-RS-05 — the row is found again by the three reads
- **Rules:** `restore` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. read: `dao.get_by_factory_item_available(db, factory_id=F1.id, item_id=I1.id, is_available_for_sale=False, workspace_id=W1.id).id == A.id`.
3. read: `[r.id for r in dao.get_by_workspace(db, workspace_id=W1.id)] == [A.id]`.
4. read: `[r.id for r in dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)] == [A.id]`.

### PRD-RS-06 — on a live row it raises nothing and changes no value
- **Rules:** `restore` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `qty 4`.

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_active is True`, `is_deleted is False`, `qty == 4`.

### PRD-RS-07 — a row with is_active False becomes active
- **Rules:** `restore` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `is_active False`.

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_active is True`.

### PRD-RS-08 — not committed: a rollback restores the deleted state
- **Rules:** `restore` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. count: inside the savepoint, `products` has exactly 1 row with `is_deleted` False.
3. count: after the savepoint rollback, `products` has exactly 1 row with `is_deleted` True.
4. mock called: the `db.commit` spy was never called.

### PRD-RS-09 — one row is updated and flushed; another stays as it was
- **Rules:** `restore` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.
2. B = stock, `item_id I2.id`, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. statement: `len(written) == 1`.
3. session: `not db.dirty`.
4. unchanged: unchanged(B).

### PRD-RS-10 — updated_at moves from None, and updated_by stays
- **Rules:** `restore` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock, `updated_by U1.id`, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.

**When**
- `result = dao.restore(db, db_obj=A)`.

**Then**
1. returns: `result is A`.
2. re-read A: `updated_at is not None`.
3. re-read A: `updated_by == U1.id`.

## Inherited `BaseDAO` methods on `Product`

### PRD-INH-01 — create with a dict gives the defaults
- **Rules:** `inherited` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "item_id": I1.id, "factory_id": F1.id})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `qty == 0`, `is_available_for_sale is False`.
3. re-read the returned row: `is_active is True`, `is_deleted is False`.
4. re-read the returned row: `avg_cost is None`, `updated_at is None`, `created_at is not None`.

### PRD-INH-02 — create is flushed, not committed: a rollback removes the row
- **Rules:** `inherited` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "item_id": I1.id, "factory_id": F1.id})`.

**Then**
1. returns: `result.id is not None`.
2. count: inside the savepoint, `products` has exactly 1 row.
3. count: after the savepoint rollback, `products` has exactly 0 rows.
4. mock called: the `db.commit` spy was never called.

### PRD-INH-03 — create with a ProductCreate fails on flush and saves nothing
- **Rules:** `inherited` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `dao.create(db, obj_in=ProductCreate(item_id=I1.id, factory_id=F1.id))`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `exc.value.orig.pgcode == "23502"`.
4. count: `products` has exactly 0 rows.

### PRD-INH-04 — a second row of one key is refused
- **Rules:** `inherited` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = stock.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "item_id": I1.id, "factory_id": F1.id})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, UniqueViolation)`.
3. raises: `exc.value.orig.pgcode == "23505"`.
4. count: `products` has exactly 1 row.

### PRD-INH-05 — a second row of one key is refused when the first is soft-deleted
- **Rules:** `inherited` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = stock, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "item_id": I1.id, "factory_id": F1.id})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. count: `products` has exactly 1 row.

### PRD-INH-06 — the same item and factory with the other flag is accepted
- **Rules:** `inherited` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "item_id": I1.id, "factory_id": F1.id, "is_available_for_sale": True})`.

**Then**
1. returns: `result.id != A.id`.
2. re-read the returned row: `is_available_for_sale is True`.
3. count: `products` has exactly 2 rows.

### PRD-INH-07 — a negative qty is stored
- **Rules:** `inherited` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "item_id": I1.id, "factory_id": F1.id, "qty": -4})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `qty == -4`.

### PRD-INH-08 — the top of 32 bits is stored
- **Rules:** `inherited` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "item_id": I1.id, "factory_id": F1.id, "qty": 2147483647})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `qty == 2147483647`.

### PRD-INH-09 — one above 32 bits raises
- **Rules:** `inherited` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "item_id": I1.id, "factory_id": F1.id, "qty": 2147483648})`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, NumericValueOutOfRange)`.
3. raises: `exc.value.orig.pgcode == "22003"`.
4. count: `products` has exactly 0 rows.

### PRD-INH-10 — avg_cost 0.125 reads back 0.13: the column rounds half away from zero
- **Rules:** `inherited` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "item_id": I1.id, "factory_id": F1.id, "avg_cost": Decimal("0.125")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `avg_cost == Decimal("0.13")`.

### PRD-INH-11 — avg_cost 0.124 reads back 0.12
- **Rules:** `inherited` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No row beyond the standing rows.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "item_id": I1.id, "factory_id": F1.id, "avg_cost": Decimal("0.124")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `avg_cost == Decimal("0.12")`.

### PRD-INH-12 — update with a ProductUpdate sets qty to 0 and keeps note
- **Rules:** `inherited` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = stock, `qty 4`, `note "Keep"`.

**When**
- `result = dao.update(db, db_obj=A, obj_in=ProductUpdate(qty=0, note=None))`.

**Then**
1. returns: `result.id == A.id`.
2. re-read A: `qty == 0`, `note == "Keep"`.

### PRD-INH-13 — update is flushed, not committed: a rollback restores the row
- **Rules:** `inherited` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock, `qty 4`.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.update(db, db_obj=A, obj_in=ProductUpdate(qty=0))`.

**Then**
1. returns: `result.id == A.id`.
2. count: inside the savepoint, `products` has exactly 1 row with `qty` 0.
3. count: after the savepoint rollback, `products` has exactly 1 row with `qty` 4.
4. mock called: the `db.commit` spy was never called.

### PRD-INH-14 — update changes a soft-deleted row like any other
- **Rules:** `inherited` R7
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `qty 4`, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.

**When**
- `result = dao.update(db, db_obj=A, obj_in=ProductUpdate(qty=9))`.

**Then**
1. returns: `result.id == A.id`.
2. re-read A: `qty == 9`, `is_deleted is True`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| BUG-1336, FU-1 (i) — `apply_production_output`, `apply_sale_return` find the key through the new lookup, restore a deleted row, carry on from its kept `qty`, no ledger row for the restore | `ProductManager` | **Stock, owner's answer.** |
| BUG-1336, FU-1 (i) — `create_product` on a deleted key answers 409 with the existing message, nothing written | `ProductManager.create_product` | **Stock, owner's answer.** |
| BUG-1336, FU-1 (i) — `apply_sale_deduction` keeps answering 422, and does not restore | `ProductManager.apply_sale_deduction` | **Stock, owner's answer.** |
| BUG-1040 (HR-15) — half-even `quantize` in `apply_production_output` | `ProductManager.apply_production_output` | **Money.** Existing bug. |
| BUG-1011 (HR-16) — `create_product` accepts another workspace's item | `ProductManager.create_product` | Existing bug, FU-1 (f). |
| FU-1 (a) — HR-10: four movements read unlocked and write an absolute `qty` | `ProductManager` | **Stock, owner.** Two movements at once lose one. |
| FU-1 (b) — `delete_product` deletes a row holding stock | `ProductManager.delete_product` | **Stock, owner. Verified.** 4 units leave every list with no ledger row. |
| FU-1 (c) — `get_product` returns a soft-deleted row | `ProductManager.get_product` | Pattern `get-returns-soft-deleted`. |
| FU-1 (d) — no minimums on `ProductCreate`, `ProductUpdate` | `app/schemas/product.py`, `ProductManager` | **Stock, money, owner. Verified.** `qty` -5 stored with no ledger row; negative prices. |
| FU-1 (e) — `PUT` moving `is_available_for_sale` onto a taken key is a 500; the move writes no ledger row | `ProductManager.update_product` | **Stock, owner. Verified.** |
| FU-1 (f) — `create_product` accepts a soft-deleted factory and a removed item | `ProductManager.create_product` | **Stock. Verified** for the factory. |
| FU-1 (g) — `update_product` cannot clear fields; an `avg_cost` change alone writes no ledger row | `ProductManager.update_product` | **Money.** Read, not run. |
| FU-1 (h) — `total_cost` skipped when `avg_cost` is `0` | `ProductManager.create_product`, `update_product` | **Money.** |
| FU-2 — `_product_rows` tests `prod.is_deleted`, a branch that cannot run | `ItemSummaryService._product_rows` |  |
| BUG-1338, FU-2 — the item summary of a removed item shows no stock rows | `ItemSummaryService` | **Stock, owner's answer.** The DAO half is PRD-GT-16. |
| FU-3 — minimum order reads through `get_by_factory_item_available` | `assert_meets_minimum_order_quantities` | **Order.** A deleted bucket has no minimum, a hidden one keeps it. Check it is wanted. |
| HR-7 — `1 <= limit <= 1000`, `skip >= 0` | `GET /products/` | Endpoint rule; the DAO's own negatives are the Errors cards. |
| Generic behavior of inherited methods; `get`, `get_multi`, `remove` | `tests/unit/dao/base.spec.md` / `base.cases.md` | Not restated. |
| Module singleton `product_dao` | none | No logic. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `get_by_factory_item_available` R6 | **Stock.** The spec gives it no case. Its `.first()` needs no order only while the constraint holds. | Matrix points at PRD-INH-04, INH-05. |
| 2 | `get_by_item` R3c and `get_by_workspace` R5b | **Resolved 2026-11-03.** The owner answered: the item summary hides a removed item's stock too (BUG-1338, spec revision 2026-11-03). | PRD-GT-16 is now a strict xfail; R3b gained its item cards. |
| 3 | Notes: keyword-only parameters | Stated as a note, not as a rule. | No card, as in `work_order_approver.cases.md` gap 1. |
| 4 | `get_by_workspace` R9, Branch map `models/product.py` 55–61 | The `if self.item` branch has no stated result for a row with no item, and the foreign key makes one impossible. | No card for that side. |
| 5 | Model facts: `Item` | The spec does not say whether `items` has a unique index on `name_normalized`. | The `Press` / `press` cards give each item its own `name_normalized`, which this DAO never reads. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_workspace` | Returns | PRD-GW-01 |
| `get_by_workspace` | R1 | PRD-GW-01, PRD-GW-02, PRD-GW-03, PRD-GW-57 |
| `get_by_workspace` | R2 | PRD-GW-04, PRD-GW-05, PRD-GW-06, PRD-GW-07 |
| `get_by_workspace` | R3 | PRD-GW-08, PRD-GW-09, PRD-GW-10, PRD-GW-11, PRD-GW-12 |
| `get_by_workspace` | R4 | PRD-GW-13, PRD-GW-14, PRD-GW-15, PRD-GW-16, PRD-GW-17, PRD-GW-18, PRD-GW-19 |
| `get_by_workspace` | R4a | PRD-GW-20, PRD-GW-21 |
| `get_by_workspace` | R5 | PRD-GW-22, PRD-GW-23, PRD-GW-48, PRD-GW-49, PRD-GW-50, PRD-GW-51 |
| `get_by_workspace` | R5a [BUG-1327] | PRD-GW-24, PRD-GW-25, PRD-GW-26, PRD-GW-27, PRD-GW-28 |
| `get_by_workspace` | R5b [BUG-1327] | PRD-GW-29, PRD-GW-30, PRD-GW-31, PRD-GW-32 |
| `get_by_workspace` | R5c | PRD-GW-33, PRD-GW-34, PRD-GW-35, PRD-GW-36 |
| `get_by_workspace` | R6 [BUG-1325] | PRD-GW-37, PRD-GW-38, PRD-GW-39, PRD-GW-40, PRD-GW-41, PRD-GW-42, PRD-GW-43, PRD-GW-44 |
| `get_by_workspace` | R7 | PRD-GW-44, PRD-GW-45, PRD-GW-46, PRD-GW-47 |
| `get_by_workspace` | R8 | PRD-GW-52, PRD-GW-53 |
| `get_by_workspace` | R9 | PRD-GW-54 |
| `get_by_workspace` | Errors row 1 | PRD-GW-52 |
| `get_by_workspace` | Errors row 2 | PRD-GW-53 |
| `get_by_workspace` | Side effects | PRD-GW-55, PRD-GW-56 |
| `get_by_id_and_workspace` | Returns | PRD-GI-01 |
| `get_by_id_and_workspace` | R1 | PRD-GI-01 |
| `get_by_id_and_workspace` | R2 | PRD-GI-02, PRD-GI-03, PRD-GI-04 |
| `get_by_id_and_workspace` | R3 | PRD-GI-05, PRD-GI-06, PRD-GI-07 |
| `get_by_id_and_workspace` | R4 | PRD-GI-10, PRD-GI-11, PRD-GI-12, PRD-GI-13 |
| `get_by_id_and_workspace` | Side effects | PRD-GI-07, PRD-GI-08, PRD-GI-09 |
| `get_by_factory_item_available` | Returns | PRD-GK-01 |
| `get_by_factory_item_available` | R1 | PRD-GK-01, PRD-GK-02, PRD-GK-03 |
| `get_by_factory_item_available` | R2 | PRD-GK-04, PRD-GK-05, PRD-GK-06, PRD-GK-07, PRD-GK-08, PRD-GK-09, PRD-GK-10, PRD-GK-11, PRD-GK-12, PRD-GK-13 |
| `get_by_factory_item_available` | R3 | PRD-GK-14, PRD-GK-15 |
| `get_by_factory_item_available` | R4 | PRD-GK-16, PRD-GK-17, PRD-GK-18 |
| `get_by_factory_item_available` | R5 | PRD-GK-19 |
| `get_by_factory_item_available` | R6 | PRD-INH-04, PRD-INH-05 |
| `get_by_factory_item_available` | Side effects | PRD-GK-20, PRD-GK-21 |
| `_get_any_by_factory_item_available` | Returns | PRD-GA-01 |
| `_get_any_by_factory_item_available` | R1 [BUG-1336] | PRD-GA-01, PRD-GA-02, PRD-GA-03, PRD-GA-04, PRD-GA-05, PRD-GA-06 |
| `_get_any_by_factory_item_available` | R2 [BUG-1336] | PRD-GA-07, PRD-GA-08, PRD-GA-09, PRD-GA-10, PRD-GA-11, PRD-GA-12, PRD-GA-13, PRD-GA-17 |
| `_get_any_by_factory_item_available` | R3 [BUG-1336] | PRD-GA-14, PRD-GA-15, PRD-GA-16 |
| `_get_any_by_factory_item_available` | Side effects | PRD-GA-15, PRD-GA-16 |
| `get_by_item` | Returns | PRD-GT-01 |
| `get_by_item` | R1 | PRD-GT-01, PRD-GT-02, PRD-GT-03, PRD-GT-04, PRD-GT-05 |
| `get_by_item` | R2 | PRD-GT-06 |
| `get_by_item` | R2a | PRD-GT-23 |
| `get_by_item` | R3 | PRD-GT-07, PRD-GT-08, PRD-GT-09 |
| `get_by_item` | R3a [BUG-1328] | PRD-GT-10, PRD-GT-11, PRD-GT-12 |
| `get_by_item` | R3b | PRD-GT-13, PRD-GT-14, PRD-GT-15, PRD-GT-24, PRD-GT-25 |
| `get_by_item` | R3c [BUG-1338] | PRD-GT-16 |
| `get_by_item` | R4 [BUG-1326] | PRD-GT-17, PRD-GT-18, PRD-GT-19 |
| `get_by_item` | R5 | PRD-GT-20 |
| `get_by_item` | Side effects | PRD-GT-21, PRD-GT-22 |
| `soft_delete` | Returns | PRD-SD-01 |
| `soft_delete` | R1 | PRD-SD-01 |
| `soft_delete` | R2 | PRD-SD-02, PRD-SD-03 |
| `soft_delete` | R3 | PRD-SD-04, PRD-SD-05 |
| `soft_delete` | R3a | PRD-SD-06 |
| `soft_delete` | R3a [BUG-1335] | PRD-SD-07, PRD-SD-08 |
| `soft_delete` | R4 | PRD-SD-09 |
| `soft_delete` | R5 | PRD-SD-10 |
| `soft_delete` | R6 | PRD-SD-11 |
| `soft_delete` | Errors row 1 | PRD-SD-12 |
| `soft_delete` | Side effects | PRD-SD-13 |
| `restore` | Returns | PRD-RS-01 |
| `restore` | R1 | PRD-RS-01 |
| `restore` | R2 | PRD-RS-02, PRD-RS-03, PRD-RS-04, PRD-RS-10 |
| `restore` | R3 | PRD-RS-05 |
| `restore` | R4 | PRD-RS-06, PRD-RS-07 |
| `restore` | Side effects | PRD-RS-08, PRD-RS-09 |
| `inherited` | R1 | PRD-INH-01, PRD-INH-02 |
| `inherited` | R2 | PRD-INH-03 |
| `inherited` | R3 | PRD-INH-04, PRD-INH-05, PRD-INH-06 |
| `inherited` | R4 | PRD-INH-07, PRD-INH-08, PRD-INH-09 |
| `inherited` | R5 | PRD-INH-10, PRD-INH-11 |
| `inherited` | R6 | PRD-INH-12, PRD-INH-13 |
| `inherited` | R7 | PRD-INH-14 |
