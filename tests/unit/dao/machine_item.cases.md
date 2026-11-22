# Test cases — `app/dao/machine_item.py`

> **Spec:** `tests/unit/dao/machine_item.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-10-30; nothing open). Q1 / BUG-983 is the owner's own answer; P1–P7 and how a violation surfaces at the DAO were decided by Claude under the reviewer's delegation.
> **Revision:** 1 — the spec did not change. Additive, from `machine_item.verify.md` (case-missing Findings 1–5, recipes P1 … P9): Finding 1 → MIT-GT-32; Finding 2 → MIT-GM-52, GT-33; Finding 3 → MIT-GM-53, GM-54; Finding 4 → MIT-GW-33, GT-34, INH-50; Finding 5 → MIT-INH-51. No existing card, Convention or ID changed, none retired.
> **Counts:** 198 cases · 156 expected-to-pass · 42 expected-to-fail (bugs) · 13 deferred

## Reviewer summary
- **Per callable:** `get_by_workspace` 33 (5 bug) · `get_by_id_and_workspace` 11 · `get_by_machine` 54 (16 bug) · `get_by_machine_and_item` 15 · `get_by_item` 34 (11 bug) · `inherited` 51 (10 bug).
- **Expected-to-fail by bug:** BUG-100 8 (GW-11, GW-12, GW-13, GW-14, INH-44, INH-45, GW-33, INH-50) · BUG-101 2 (INH-39, INH-51) · BUG-976 6 (GM-31, GM-32, GM-33, GM-34, GM-35, GM-36) · BUG-977 3 (GT-27, GT-28, GT-34) · BUG-979 4 (GM-16, GM-17, GM-18, GM-52) · BUG-980 6 (GM-25, GM-26, GM-27, GM-28, GM-53, GM-54) · BUG-981 6 (GT-13, GT-14, GT-15, GT-16, GT-17, GT-33) · BUG-982 2 (GT-25, GT-32) · BUG-983 5 (INH-10, INH-11, INH-12, INH-13, INH-14).
- **Strictness:** 28 strict, 14 non-strict (GW-11, GW-12, GW-13, GM-28, GM-31, GM-32, GM-33, GM-34, GM-35, GT-27, INH-44, GW-33, INH-50, GT-34).
- **Answers and the cards that rest on them:** Q1 / BUG-983 (owner) — MIT-INH-10 … INH-14 (refused, pgcode `23505`, no index name), INH-15 … INH-20 (R4b: what stays allowed, including the same pair under another workspace in both directions). P1, P3 — the R4a / R4b / R3a / R3b cards, pass companions R4c / R3c. P2 — GM R5 cards, pass companions R5a. P4 — MIT-GT-25, GT-26, GT-32. P5, P6 — GI-09 … GI-11, GP-13 … GP-15, GT-24, GW-07 … GW-10.
- **Notable design choices:**
  - Row order: pass cards and strict cards compare `sorted(ids(result))`, sizes, or `[]`, never physical order. Each of the four unordered queries has one **strict** SQL recorder (MIT-GW-14, GM-36, GT-28, INH-45) and non-strict cards for the order itself, including one where ids do not rise with machine or workspace (MIT-GW-33, GT-34, INH-50). Those three usually pass today: they exist for the fix.
  - Each parent state has its own card, in each method. A strict xfail's deleted-parent shape always has its pass companion: "changes nothing", "inactive hides nothing", "back once live". Live-parent rows sit in the same Given.
  - Mixed shapes: same pair in two workspaces, W2 rows on W1 parents, W1 rows on W2 parents, W2 rows on a soft-deleted W1 machine, W2 rows on a W1 machine in a soft-deleted factory, and removed items across workspaces (all hidden; catches a fix that joins on the parent's workspace).
  - Commit spy: one card per writer (`create` INH-03, `update` INH-34, `remove` INH-40), plus INH-51 on the missing-row path of BUG-101. Readers have none.
  - `R10` of `get_by_machine`, `R5` of `get_by_machine_and_item` and `R8` of `get_by_item` have no card, as the spec orders. No card holds two rows for one key except through a call the index must refuse.
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Needs a decision:** None blocking. See Spec gaps 2 (one strict-vs-non-strict conflict in the spec's Notes) and 4 (loose recorder lines).


## Conventions for this module

**IDs.** `MIT` = `app/dao/machine_item.py`. `GW` get_by_workspace · `GI` get_by_id_and_workspace · `GM` get_by_machine · `GP` get_by_machine_and_item · `GT` get_by_item · `INH` inherited `BaseDAO` methods on `MachineItem`.

**Actors and fixed values.**
- `dao` = the singleton `machine_item_dao` (`from app.dao.machine_item import machine_item_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword (only `dao.get(db, <id>)` takes the id positionally). `result` = what the When call returns.
- `MachineItem` = `app.models.machine_item.MachineItem`. `MachineItemCreate`, `MachineItemUpdate` = the schemas of `app.schemas.machine_item`. `select`, `text` = `sqlalchemy.select`, `sqlalchemy.text`.
- MISSING = `999999999`: an id that no row of any table has.

**Externals.** None. Nothing is mocked. No method reads the clock.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from these defaults.
- These rows exist in every test and need no Given line (workspaces from `make_workspace`; the rest built directly):
  - W1, W2 = two `workspaces` rows.
  - F1 = `factories` row: `workspace_id W1.id`, `name "Factory One"`, `abbreviation "F1"`, `is_active True`, `is_deleted False`.
  - FD = the same, but `name "Old Plant"`, `abbreviation "OP"`, `is_deleted True` (soft-deleted; `is_active` stays True). FI = the same as F1, but `name "Idle Plant"`, `abbreviation "IP"`, `is_active False` (inactive but live). F9 = the same as F1, but `name "Factory Nine"`, `abbreviation "F9"`, `workspace_id W2.id`.
  - M1 = `machines` row: `workspace_id W1.id`, `factory_id F1.id`, `name "Press 1"`, `is_active True`, `is_deleted False`. M2, M3 = the same, but `name "Press 2"`, `"Press 3"`.
  - MD = the same as M1, but `name "Press 4"`, `is_active False`, `is_deleted True` (soft-deleted). MI = the same as M1, but `name "Idle Press"`, `is_active False` (inactive but live).
  - MF = the same as M1, but `name "Lost Press"`, `factory_id FD.id` (live, in a soft-deleted factory). MG = the same as M1, but `name "Quiet Press"`, `factory_id FI.id` (live, in an inactive factory). M9 = the same as M1, but `name "Far Press"`, `workspace_id W2.id`, `factory_id F9.id`.
  - I1 = `items` row: `workspace_id W1.id`, `name "Bolt"`, `name_normalized "bolt"`, `unit "pcs"`, `is_active True`. I2 = the same, but `name "Washer"`, `name_normalized "washer"`, `unit "kg"`. I3 = the same, but `name "Spring"`, `name_normalized "spring"`, `unit "box"`.
  - IX = the same as I1, but `name "Old Gasket"`, `name_normalized "old gasket"`, `unit "m"`, `is_active False` (removed). I9 = the same as I1, but `name "Far Crate"`, `name_normalized "far crate"`, `unit "set"`, `workspace_id W2.id`.
- **stock** = `machine_items` row built with `MachineItem`: `workspace_id W1.id`, `qty 5`, `req_qty None`, `defective_qty None`. The card always gives `machine_id` and `item_id`; after the word "but" it lists every other column that differs. No `machine_items` row exists unless the card's Given lists it.
- **item** (a further row in a Given) = `items` row with `workspace_id W1.id` and the columns the card lists.
- A Given line written as code (`A.qty = 6`, then `db.flush()`) is a step to run exactly as written, at that place in the order.

**Named checks.**
- **ids(result)** = `[r.id for r in result]`, **item_names(result)** = `[r.item_name for r in result]` — lists in the order returned (the order is part of the check). `sorted(ids(result)) == [A.id, B.id]` is used where the order is not part of the check; the right-hand ids are written in Given order, which is ascending id order.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line, before the call; or at the Given line "Snapshot of X taken here").
- **nothing written** = the number of `machine_items` rows (all workspaces) equals its value before the call.
- `count:` lines count rows in all workspaces, with the filter stated.
- `raises: DataError` = `sqlalchemy.exc.DataError`; `raises: IntegrityError` = `sqlalchemy.exc.IntegrityError`. Wrap the call for both: `with pytest.raises(<Type>) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards (the savepoint is rolled back). A negative `limit` / `skip` raises when the query runs: the same wrapping applies. `NotNullViolation`, `ForeignKeyViolation`, `UniqueViolation`, `NumericValueOutOfRange`, `InvalidRowCountInLimitClause`, `InvalidRowCountInResultOffsetClause` = classes of `psycopg2.errors`.
- Further `raises:` lines of the same card are assertions on `exc.value`, written after the `with` block, one `assert` per line.

**xfail cards.** Write the call and the checks exactly as shown; add `pytest.mark.xfail(strict=True, reason="BUG-NNN")`, or `strict=False` on a card whose Expect line says `(non-strict)`. The assertion of a non-strict card is never weakened.

**Rolled back.** `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); the first checks run inside the savepoint; then `sp.rollback()` and the "after the savepoint rollback" checks.

**Statement recorder.** The SQL statements the session sends are recorded. `sql` = the text of the one `SELECT` from `machine_items` sent during the When; `order_part` = the text of `sql` after `ORDER BY` (`""` when there is none); `selects` = every `SELECT` recorded. A `statement:` line is a check on these.

**Race simulations.** None in this module.


## `DAOMachineItem.get_by_workspace`

### MIT-GW-01 — returns a list of the workspace's stock rows and writes nothing
- **Rules:** `get_by_workspace` R1, Returns, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I2.id`.
3. C = stock, `machine_id M2.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [A.id, B.id, C.id]`.
3. returns: `isinstance(result[0], MachineItem)`.
4. nothing written: nothing written.
5. unchanged: unchanged(A).

### MIT-GW-02 — a row of another workspace does not appear, although it would fit on the page
- **Rules:** `get_by_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. Z = stock, `machine_id M9.id`, `item_id I9.id`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. unchanged: unchanged(Z).

### MIT-GW-03 — the other workspace gets only its own row
- **Rules:** `get_by_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. Z = stock, `machine_id M9.id`, `item_id I9.id`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [Z.id]`.

### MIT-GW-04 — the same machine and item in two workspaces: W1 gets only its own row
- **Rules:** `get_by_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. Z = stock, `machine_id M1.id`, `item_id I1.id`, but `workspace_id W2.id`. (Same machine and item as A on purpose: another key, the workspace differs.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MIT-GW-05 — the same machine and item in two workspaces: W2 gets only its own row
- **Rules:** `get_by_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. Z = stock, `machine_id M1.id`, `item_id I1.id`, but `workspace_id W2.id`. (Same machine and item as A on purpose: another key, the workspace differs.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [Z.id]`.

### MIT-GW-06 — rows are returned whatever their quantities
- **Rules:** `get_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`, but `qty 0`.
2. B = stock, `machine_id M1.id`, `item_id I2.id`, but `qty -4`.
3. C = stock, `machine_id M1.id`, `item_id I3.id`, but `qty 3`, `req_qty 9`, `defective_qty 1`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id, C.id]`.

### MIT-GW-07 — the row of a soft-deleted machine is returned and left as it was
- **Rules:** `get_by_workspace` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `machine_id MD.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. unchanged: unchanged(A).

### MIT-GW-08 — the row of a machine in a soft-deleted factory is returned and left as it was
- **Rules:** `get_by_workspace` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `machine_id MF.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. unchanged: unchanged(A).

### MIT-GW-09 — the row of a removed item is returned and left as it was
- **Rules:** `get_by_workspace` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id IX.id`.
2. B = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. unchanged: unchanged(A).

### MIT-GW-10 — rows of deleted parents take a place in the page
- **Rules:** `get_by_workspace` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `machine_id MD.id`, `item_id I1.id`.
2. B = stock, `machine_id MF.id`, `item_id I1.id`.
3. C = stock, `machine_id M1.id`, `item_id IX.id`.
4. D = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=3)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `set(ids(result)) <= {A.id, B.id, C.id, D.id}`.

### MIT-GW-11 — rows come back in id order
- **Rules:** `get_by_workspace` R3 [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; the updated row A usually comes back after B, giving [B.id, A.id] — but the physical row order can match the intended order by accident)

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I2.id`.
3. `A.qty = 6`, then `db.flush()`. (Changed after the later rows were created: this usually moves A physically behind them.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. returns: `ids(result) == [A.id, B.id]`.

### MIT-GW-12 — the first of two windows holds the two lowest ids
- **Rules:** `get_by_workspace` R3 [BUG-100], R4
- **Kind:** bug
- **Expect:** xfail BUG-100 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; the updated row A usually lands in the second window — but the physical row order can match the intended order by accident)

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I2.id`.
3. C = stock, `machine_id M1.id`, `item_id I3.id`.
4. D = stock, `machine_id M2.id`, `item_id I1.id`.
5. `A.qty = 6`, then `db.flush()`. (Changed after the later rows were created: this usually moves A physically behind them.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=0, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [A.id, B.id]`.

### MIT-GW-13 — the second of two windows holds the two highest ids
- **Rules:** `get_by_workspace` R3 [BUG-100], R4
- **Kind:** bug
- **Expect:** xfail BUG-100 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; the updated row A usually lands in this window — but the physical row order can match the intended order by accident)

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I2.id`.
3. C = stock, `machine_id M1.id`, `item_id I3.id`.
4. D = stock, `machine_id M2.id`, `item_id I1.id`.
5. `A.qty = 6`, then `db.flush()`. (Changed after the later rows were created: this usually moves A physically behind them.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=2, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [C.id, D.id]`.

### MIT-GW-14 — the workspace list query asks the database for id order
- **Rules:** `get_by_workspace` R3 [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"machine_items.id" in order_part`.
4. statement: `"DESC" not in order_part`.

### MIT-GW-15 — with the default limit 101 rows give exactly 100
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 items N1 … N101 (W1), inserted in that order: Nk (k = 1 … 101) has `name` = `f"Part {k:03d}"`, `name_normalized` = `f"part {k:03d}"`, `unit "pcs"`, `is_active True`.
2. 101 stock rows S1 … S101, built with `add_all`: Sk = stock, `machine_id M1.id`, `item_id Nk.id`. `all_ids` = their ids.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `set(ids(result)) <= set(all_ids)`.

### MIT-GW-16 — with the default limit 100 rows give all 100
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 100 items N1 … N100 (W1), inserted in that order: Nk (k = 1 … 100) has `name` = `f"Part {k:03d}"`, `name_normalized` = `f"part {k:03d}"`, `unit "pcs"`, `is_active True`.
2. 100 stock rows S1 … S100, built with `add_all`: Sk = stock, `machine_id M1.id`, `item_id Nk.id`. `all_ids` = their ids.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `sorted(ids(result)) == sorted(all_ids)`.

### MIT-GW-17 — an explicit limit of 101 gives all 101 rows
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 items N1 … N101 (W1), inserted in that order: Nk (k = 1 … 101) has `name` = `f"Part {k:03d}"`, `name_normalized` = `f"part {k:03d}"`, `unit "pcs"`, `is_active True`.
2. 101 stock rows S1 … S101, built with `add_all`: Sk = stock, `machine_id M1.id`, `item_id Nk.id`. `all_ids` = their ids.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=101)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `sorted(ids(result)) == sorted(all_ids)`.

### MIT-GW-18 — limit=2 of three rows gives two of them
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I2.id`.
3. C = stock, `machine_id M1.id`, `item_id I3.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `set(ids(result)) <= {A.id, B.id, C.id}`.

### MIT-GW-19 — skip=1 of three rows gives two of them
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I2.id`.
3. C = stock, `machine_id M1.id`, `item_id I3.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `set(ids(result)) <= {A.id, B.id, C.id}`.

### MIT-GW-20 — skip=1 and limit=1 of three rows gives one of them
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I2.id`.
3. C = stock, `machine_id M1.id`, `item_id I3.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `set(ids(result)) <= {A.id, B.id, C.id}`.

### MIT-GW-21 — an unknown workspace returns an empty list
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### MIT-GW-22 — a workspace with no rows returns an empty list
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`. (W2 has no stock rows.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### MIT-GW-23 — skip equal to the number of rows returns an empty list
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### MIT-GW-24 — skip past the number of rows returns an empty list
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=3)`.

**Then**
1. returns: `result == []`.

### MIT-GW-25 — skip one below the number of rows returns one row
- **Rules:** `get_by_workspace` R5, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `set(ids(result)) <= {A.id, B.id}`.

### MIT-GW-26 — limit=0 returns an empty list
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### MIT-GW-27 — limit=1 returns one row
- **Rules:** `get_by_workspace` R5, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `set(ids(result)) <= {A.id, B.id}`.

### MIT-GW-28 — a negative limit is rejected by Postgres
- **Rules:** `get_by_workspace` R6, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `dao.get_by_workspace(db, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError` when the query runs.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `exc.value.orig.pgcode == "2201W"`.
4. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MIT-GW-29 — a negative skip is rejected by Postgres
- **Rules:** `get_by_workspace` R6, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `dao.get_by_workspace(db, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError` when the query runs.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `exc.value.orig.pgcode == "2201X"`.
4. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MIT-GW-30 — a row carries the name and unit of its item
- **Rules:** `get_by_workspace` R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `result[0].item_name == "Bolt"`.
3. returns: `result[0].item_unit == "pcs"`.

### MIT-GW-31 — a row of a removed item carries that item's name and unit
- **Rules:** `get_by_workspace` R7
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id IX.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `result[0].item_name == "Old Gasket"`.
3. returns: `result[0].item_unit == "m"`.

### MIT-GW-32 — reading a row's item name and unit needs no further query
- **Rules:** `get_by_workspace` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. `w1_id = W1.id`
3. `db.expire_all()` (nothing stays loaded in the session).
4. A recorder for the SQL statements the session sends from here to the last Then line.

**When**
- `result = dao.get_by_workspace(db, workspace_id=w1_id)`.

**Then**
1. returns: `result[0].item_name == "Bolt"`.
2. returns: `result[0].item_unit == "pcs"`.
3. statement: `len(selects) == 1`.

### MIT-GW-33 — id order holds when the lower id sits on the higher machine and item
- **Rules:** `get_by_workspace` R3 [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; on today's plan the rows usually come back in insertion order, which is the intended order here, so this card usually passes today — it exists for the fix)

**Given**
1. A = stock, `machine_id M2.id`, `item_id I2.id`.
2. B = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. returns: `ids(result) == [A.id, B.id]`.


## `DAOMachineItem.get_by_id_and_workspace`

### MIT-GI-01 — returns the session's row with that id and writes nothing
- **Rules:** `get_by_id_and_workspace` R1, Returns, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I2.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=B.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is B`.
2. returns: `isinstance(result, MachineItem)`.
3. nothing written: nothing written.
4. unchanged: unchanged(B).

### MIT-GI-02 — a row of another workspace is not found
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = stock, `machine_id M9.id`, `item_id I9.id`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(Z).

### MIT-GI-03 — a W1 row asked for under W2 is not found
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### MIT-GI-04 — a row is found under its own workspace
- **Rules:** `get_by_id_and_workspace` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = stock, `machine_id M9.id`, `item_id I9.id`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=Z.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is Z`.

### MIT-GI-05 — the W2 row of a machine and item W1 also holds is not found under W1
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. Z = stock, `machine_id M1.id`, `item_id I1.id`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### MIT-GI-06 — an unknown workspace finds nothing
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=MISSING)`.

**Then**
1. returns: `result is None`.

### MIT-GI-07 — an unknown id returns None and writes nothing
- **Rules:** `get_by_id_and_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### MIT-GI-08 — id=0 returns None and writes nothing
- **Rules:** `get_by_id_and_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### MIT-GI-09 — the row of a soft-deleted machine is found
- **Rules:** `get_by_id_and_workspace` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `machine_id MD.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is A`.
2. unchanged: unchanged(A).

### MIT-GI-10 — the row of a machine in a soft-deleted factory is found
- **Rules:** `get_by_id_and_workspace` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `machine_id MF.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is A`.
2. unchanged: unchanged(A).

### MIT-GI-11 — the row of a removed item is found
- **Rules:** `get_by_id_and_workspace` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id IX.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is A`.
2. unchanged: unchanged(A).


## `DAOMachineItem.get_by_machine`

### MIT-GM-01 — returns a list of the machine's rows and writes nothing
- **Rules:** `get_by_machine` R1, Returns, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I2.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [A.id, B.id]`.
3. returns: `isinstance(result[0], MachineItem)`.
4. nothing written: nothing written.
5. unchanged: unchanged(A).

### MIT-GM-02 — a row of another machine is not returned
- **Rules:** `get_by_machine` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. C = stock, `machine_id M2.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. unchanged: unchanged(C).

### MIT-GM-03 — the other machine gets only its own row
- **Rules:** `get_by_machine` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. C = stock, `machine_id M2.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### MIT-GM-04 — rows of another machine or workspace take no place in the page
- **Rules:** `get_by_machine` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. C = stock, `machine_id M2.id`, `item_id I1.id`.
2. Z = stock, `machine_id M1.id`, `item_id I1.id`, but `workspace_id W2.id`.
3. A = stock, `machine_id M1.id`, `item_id I1.id`.
4. B = stock, `machine_id M1.id`, `item_id I2.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.

### MIT-GM-05 — the right machine under another workspace returns an empty list
- **Rules:** `get_by_machine` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### MIT-GM-06 — a W2 row on a machine of W1 is returned for W2
- **Rules:** `get_by_machine` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = stock, `machine_id M1.id`, `item_id I1.id`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [Z.id]`.

### MIT-GM-07 — a W2 row on a machine of W1 is not returned for W1
- **Rules:** `get_by_machine` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = stock, `machine_id M1.id`, `item_id I1.id`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIT-GM-08 — the same machine and item in two workspaces: W1 gets only its own row
- **Rules:** `get_by_machine` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. Z = stock, `machine_id M1.id`, `item_id I1.id`, but `workspace_id W2.id`. (Same machine and item as A on purpose: another key, the workspace differs.)

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MIT-GM-09 — the same machine and item in two workspaces: W2 gets only its own row
- **Rules:** `get_by_machine` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. Z = stock, `machine_id M1.id`, `item_id I1.id`, but `workspace_id W2.id`. (Same machine and item as A on purpose: another key, the workspace differs.)

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [Z.id]`.

### MIT-GM-10 — a W1 row on a machine of W2 is returned for W1
- **Rules:** `get_by_machine` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stock, `machine_id M9.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M9.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MIT-GM-11 — a W1 row of an item of W2 is returned for W1
- **Rules:** `get_by_machine` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I9.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MIT-GM-12 — rows are returned whatever their quantities
- **Rules:** `get_by_machine` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`, but `qty 0`.
2. B = stock, `machine_id M1.id`, `item_id I2.id`, but `qty -4`.
3. C = stock, `machine_id M1.id`, `item_id I3.id`, but `qty 3`, `req_qty 9`, `defective_qty 1`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id, C.id]`.

### MIT-GM-13 — an unknown machine id returns an empty list
- **Rules:** `get_by_machine` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIT-GM-14 — machine_id=0 returns an empty list
- **Rules:** `get_by_machine` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIT-GM-15 — a machine with no rows returns an empty list
- **Rules:** `get_by_machine` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIT-GM-16 — the rows of a soft-deleted machine are hidden
- **Rules:** `get_by_machine` R4a [BUG-979]
- **Kind:** bug
- **Expect:** xfail BUG-979
- **Fails today on:** Then 1 (the row A is returned)

**Given**
1. A = stock, `machine_id MD.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=MD.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIT-GM-17 — a W2 row on a soft-deleted machine of W1 is hidden too
- **Rules:** `get_by_machine` R4a [BUG-979], R2
- **Kind:** bug
- **Expect:** xfail BUG-979
- **Fails today on:** Then 1 (the row Z is returned)

**Given**
1. Z = stock, `machine_id MD.id`, `item_id I1.id`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=MD.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### MIT-GM-18 — the rows of a live machine in a soft-deleted factory are hidden
- **Rules:** `get_by_machine` R4b [BUG-979]
- **Kind:** bug
- **Expect:** xfail BUG-979
- **Fails today on:** Then 1 (the row A is returned)

**Given**
1. A = stock, `machine_id MF.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=MF.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIT-GM-19 — listing a soft-deleted machine changes nothing
- **Rules:** `get_by_machine` R4c
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `machine_id MD.id`, `item_id I1.id`, but `req_qty 7`, `defective_qty 1`.

**When**
- `result = dao.get_by_machine(db, machine_id=MD.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. unchanged: unchanged(A).
3. unchanged: unchanged(MD).
4. nothing written: nothing written.

### MIT-GM-20 — listing a machine in a soft-deleted factory changes nothing
- **Rules:** `get_by_machine` R4c
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `machine_id MF.id`, `item_id I1.id`, but `req_qty 7`, `defective_qty 1`.

**When**
- `result = dao.get_by_machine(db, machine_id=MF.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. unchanged: unchanged(A).
3. unchanged: unchanged(MF).
4. unchanged: unchanged(FD).
5. nothing written: nothing written.

### MIT-GM-21 — an inactive but live machine hides nothing
- **Rules:** `get_by_machine` R4c
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `machine_id MI.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=MI.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MIT-GM-22 — a live machine in an inactive but live factory hides nothing
- **Rules:** `get_by_machine` R4c
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `machine_id MG.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=MG.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MIT-GM-23 — the rows are back, unchanged, once the machine is no longer deleted
- **Rules:** `get_by_machine` R4c
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `machine_id MD.id`, `item_id I1.id`, but `req_qty 7`.
2. Snapshot of A taken here.
3. `MD.is_deleted = False`, `MD.is_active = True`, then `db.flush()`.

**When**
- `result = dao.get_by_machine(db, machine_id=MD.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. unchanged: unchanged(A).
3. re-read A: `qty == 5`, `req_qty == 7`.

### MIT-GM-24 — the rows are back, unchanged, once the factory is no longer deleted
- **Rules:** `get_by_machine` R4c
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `machine_id MF.id`, `item_id I1.id`, but `req_qty 7`.
2. Snapshot of A taken here.
3. `FD.is_deleted = False`, then `db.flush()`.

**When**
- `result = dao.get_by_machine(db, machine_id=MF.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. unchanged: unchanged(A).
3. re-read A: `qty == 5`, `req_qty == 7`.

### MIT-GM-25 — the row of a removed item is not returned, the other row is
- **Rules:** `get_by_machine` R5 [BUG-980]
- **Kind:** bug
- **Expect:** xfail BUG-980
- **Fails today on:** Then 1 (the row A is returned too)

**Given**
1. A = stock, `machine_id M1.id`, `item_id IX.id`.
2. B = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [B.id]`.

### MIT-GM-26 — a machine holding only a removed item returns an empty list
- **Rules:** `get_by_machine` R5 [BUG-980]
- **Kind:** bug
- **Expect:** xfail BUG-980
- **Fails today on:** Then 1 (the row A is returned)

**Given**
1. A = stock, `machine_id M1.id`, `item_id IX.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIT-GM-27 — the row of a removed item takes no place in the page: skip=2 of two visible rows is empty
- **Rules:** `get_by_machine` R5 [BUG-980]
- **Kind:** bug
- **Expect:** xfail BUG-980
- **Fails today on:** Then 1 (the removed row counts: one of the three rows is left after skipping two)

**Given**
1. A = stock, `machine_id M1.id`, `item_id IX.id`.
2. B = stock, `machine_id M1.id`, `item_id I1.id`.
3. C = stock, `machine_id M1.id`, `item_id I2.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### MIT-GM-28 — Anvil removed, Bolt active: limit=1 returns the Bolt row
- **Rules:** `get_by_machine` R5 [BUG-980]
- **Kind:** bug
- **Expect:** xfail BUG-980 (non-strict)
- **Fails today on:** Then 2 (the removed row counts in the page and usually comes first — but which row `limit=1` keeps today rests on physical order)

**Given**
1. IA = item, `name "Anvil"`, `name_normalized "anvil"`, `unit "pcs"`, `is_active False`.
2. A = stock, `machine_id M1.id`, `item_id IA.id`.
3. B = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `ids(result) == [B.id]`.

### MIT-GM-29 — listing leaves the row of a removed item and the item as they were
- **Rules:** `get_by_machine` R5a
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id IX.id`, but `req_qty 7`.
2. B = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. unchanged: unchanged(A).
3. unchanged: unchanged(IX).
4. nothing written: nothing written.

### MIT-GM-30 — the row is back, unchanged, once the item is active again
- **Rules:** `get_by_machine` R5a
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id IX.id`, but `req_qty 7`.
2. Snapshot of A taken here.
3. `IX.is_active = True`, then `db.flush()`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. unchanged: unchanged(A).
3. re-read A: `qty == 5`, `req_qty == 7`.

### MIT-GM-31 — rows come back by item name, case-insensitive
- **Rules:** `get_by_machine` R6 [BUG-976]
- **Kind:** bug
- **Expect:** xfail BUG-976 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; the rows usually come back in insertion order ["Zulu", "apple", "Banana"] — but the physical row order can match the intended order by accident)

**Given**
1. IZ = item, `name "Zulu"`, `name_normalized "zulu"`, `unit "pcs"`, `is_active True`.
2. IA = item, `name "apple"`, `name_normalized "apple"`, `unit "pcs"`, `is_active True`.
3. IB = item, `name "Banana"`, `name_normalized "banana"`, `unit "pcs"`, `is_active True`.
4. A = stock, `machine_id M1.id`, `item_id IZ.id`.
5. B = stock, `machine_id M1.id`, `item_id IA.id`.
6. C = stock, `machine_id M1.id`, `item_id IB.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id, C.id]`.
2. returns: `item_names(result) == ["apple", "Banana", "Zulu"]`.

### MIT-GM-32 — items "Bolt" and "bolt": lower row id first, the capital one holding it
- **Rules:** `get_by_machine` R6 [BUG-976]
- **Kind:** bug
- **Expect:** xfail BUG-976 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; the updated row A usually comes back after B — but the physical row order can match the intended order by accident)

**Given**
1. IB1 = item, `name "Bolt"`, `name_normalized "bolt"`, `unit "pcs"`, `is_active True`.
2. IB2 = item, `name "bolt"`, `name_normalized "bolt"`, `unit "pcs"`, `is_active True`. (The "Bolt" / "bolt" pair is on purpose: equal ignoring case, so only the row id decides.)
3. A = stock, `machine_id M1.id`, `item_id IB1.id`.
4. B = stock, `machine_id M1.id`, `item_id IB2.id`.
5. `A.qty = 6`, then `db.flush()`. (Changed after the later rows were created: this usually moves A physically behind them.)

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. returns: `ids(result) == [A.id, B.id]`.

### MIT-GM-33 — items "Bolt" and "bolt": lower row id first, the lower-case one holding it
- **Rules:** `get_by_machine` R6 [BUG-976]
- **Kind:** bug
- **Expect:** xfail BUG-976 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; the updated row A usually comes back after B — but the physical row order can match the intended order by accident)

**Given**
1. IB1 = item, `name "Bolt"`, `name_normalized "bolt"`, `unit "pcs"`, `is_active True`.
2. IB2 = item, `name "bolt"`, `name_normalized "bolt"`, `unit "pcs"`, `is_active True`. (The "Bolt" / "bolt" pair is on purpose: equal ignoring case, so only the row id decides.)
3. A = stock, `machine_id M1.id`, `item_id IB2.id`.
4. B = stock, `machine_id M1.id`, `item_id IB1.id`.
5. `A.qty = 6`, then `db.flush()`. (Changed after the later rows were created: this usually moves A physically behind them.)

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. returns: `ids(result) == [A.id, B.id]`.

### MIT-GM-34 — the order is applied before paging: first window
- **Rules:** `get_by_machine` R6 [BUG-976], R7
- **Kind:** bug
- **Expect:** xfail BUG-976 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; the window usually holds ["Zulu", "apple"] — but the physical row order can match the intended order by accident)

**Given**
1. IZ = item, `name "Zulu"`, `name_normalized "zulu"`, `unit "pcs"`, `is_active True`.
2. IA = item, `name "apple"`, `name_normalized "apple"`, `unit "pcs"`, `is_active True`.
3. IB = item, `name "Banana"`, `name_normalized "banana"`, `unit "pcs"`, `is_active True`.
4. IM = item, `name "mango"`, `name_normalized "mango"`, `unit "pcs"`, `is_active True`.
5. A = stock, `machine_id M1.id`, `item_id IZ.id`.
6. B = stock, `machine_id M1.id`, `item_id IA.id`.
7. C = stock, `machine_id M1.id`, `item_id IB.id`.
8. D = stock, `machine_id M1.id`, `item_id IM.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, skip=0, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `item_names(result) == ["apple", "Banana"]`.

### MIT-GM-35 — the order is applied before paging: second window, no repeats and no gaps
- **Rules:** `get_by_machine` R6 [BUG-976], R7
- **Kind:** bug
- **Expect:** xfail BUG-976 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; the window usually holds ["Banana", "mango"] — but the physical row order can match the intended order by accident)

**Given**
1. IZ = item, `name "Zulu"`, `name_normalized "zulu"`, `unit "pcs"`, `is_active True`.
2. IA = item, `name "apple"`, `name_normalized "apple"`, `unit "pcs"`, `is_active True`.
3. IB = item, `name "Banana"`, `name_normalized "banana"`, `unit "pcs"`, `is_active True`.
4. IM = item, `name "mango"`, `name_normalized "mango"`, `unit "pcs"`, `is_active True`.
5. A = stock, `machine_id M1.id`, `item_id IZ.id`.
6. B = stock, `machine_id M1.id`, `item_id IA.id`.
7. C = stock, `machine_id M1.id`, `item_id IB.id`.
8. D = stock, `machine_id M1.id`, `item_id IM.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, skip=2, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `item_names(result) == ["mango", "Zulu"]`.

### MIT-GM-36 — the machine list query asks for item name case-insensitive, then row id
- **Rules:** `get_by_machine` R6 [BUG-976]
- **Kind:** bug
- **Expect:** xfail BUG-976
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"lower(" in order_part.lower()`.
4. statement: `".name" in order_part`.
5. statement: `"machine_items.id" in order_part`.
6. statement: `order_part.index(".name") < order_part.index("machine_items.id")`.
7. statement: `"DESC" not in order_part`.

### MIT-GM-37 — with the default limit 101 rows give exactly 100
- **Rules:** `get_by_machine` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 items N1 … N101 (W1), inserted in that order: Nk (k = 1 … 101) has `name` = `f"Part {k:03d}"`, `name_normalized` = `f"part {k:03d}"`, `unit "pcs"`, `is_active True`.
2. 101 stock rows S1 … S101, built with `add_all`: Sk = stock, `machine_id M1.id`, `item_id Nk.id`. `all_ids` = their ids.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `set(ids(result)) <= set(all_ids)`.

### MIT-GM-38 — with the default limit 100 rows give all 100
- **Rules:** `get_by_machine` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 100 items N1 … N100 (W1), inserted in that order: Nk (k = 1 … 100) has `name` = `f"Part {k:03d}"`, `name_normalized` = `f"part {k:03d}"`, `unit "pcs"`, `is_active True`.
2. 100 stock rows S1 … S100, built with `add_all`: Sk = stock, `machine_id M1.id`, `item_id Nk.id`. `all_ids` = their ids.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `sorted(ids(result)) == sorted(all_ids)`.

### MIT-GM-39 — an explicit limit of 101 gives all 101 rows
- **Rules:** `get_by_machine` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 items N1 … N101 (W1), inserted in that order: Nk (k = 1 … 101) has `name` = `f"Part {k:03d}"`, `name_normalized` = `f"part {k:03d}"`, `unit "pcs"`, `is_active True`.
2. 101 stock rows S1 … S101, built with `add_all`: Sk = stock, `machine_id M1.id`, `item_id Nk.id`. `all_ids` = their ids.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, limit=101)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `sorted(ids(result)) == sorted(all_ids)`.

### MIT-GM-40 — limit=2 of three rows gives two of them
- **Rules:** `get_by_machine` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I2.id`.
3. C = stock, `machine_id M1.id`, `item_id I3.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `set(ids(result)) <= {A.id, B.id, C.id}`.

### MIT-GM-41 — skip=1 of three rows gives two of them
- **Rules:** `get_by_machine` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I2.id`.
3. C = stock, `machine_id M1.id`, `item_id I3.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `set(ids(result)) <= {A.id, B.id, C.id}`.

### MIT-GM-42 — skip=1 and limit=1 of three rows gives one of them
- **Rules:** `get_by_machine` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I2.id`.
3. C = stock, `machine_id M1.id`, `item_id I3.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `set(ids(result)) <= {A.id, B.id, C.id}`.

### MIT-GM-43 — limit=0 returns an empty list
- **Rules:** `get_by_machine` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I2.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### MIT-GM-44 — limit=1 returns one row
- **Rules:** `get_by_machine` R8, R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I2.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `set(ids(result)) <= {A.id, B.id}`.

### MIT-GM-45 — skip equal to the number of matching rows returns an empty list
- **Rules:** `get_by_machine` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I2.id`.
3. C = stock, `machine_id M2.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### MIT-GM-46 — skip past the number of matching rows returns an empty list
- **Rules:** `get_by_machine` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I2.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, skip=3)`.

**Then**
1. returns: `result == []`.

### MIT-GM-47 — skip one below the number of matching rows returns one row
- **Rules:** `get_by_machine` R8, R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I2.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `set(ids(result)) <= {A.id, B.id}`.

### MIT-GM-48 — a negative limit is rejected by Postgres
- **Rules:** `get_by_machine` R9, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError` when the query runs.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `exc.value.orig.pgcode == "2201W"`.
4. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MIT-GM-49 — a negative skip is rejected by Postgres
- **Rules:** `get_by_machine` R9, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError` when the query runs.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `exc.value.orig.pgcode == "2201X"`.
4. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MIT-GM-50 — a row carries the name and unit of its item
- **Rules:** `get_by_machine` R11
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I2.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `result[0].item_name == "Washer"`.
3. returns: `result[0].item_unit == "kg"`.

### MIT-GM-51 — reading a row's item name and unit needs no further query
- **Rules:** `get_by_machine` R11
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. `w1_id = W1.id`
3. `m1_id = M1.id`
4. `db.expire_all()` (nothing stays loaded in the session).
5. A recorder for the SQL statements the session sends from here to the last Then line.

**When**
- `result = dao.get_by_machine(db, machine_id=m1_id, workspace_id=w1_id)`.

**Then**
1. returns: `result[0].item_name == "Bolt"`.
2. returns: `result[0].item_unit == "pcs"`.
3. statement: `len(selects) == 1`.

### MIT-GM-52 — a W2 row on a W1 machine in a soft-deleted factory is hidden too
- **Rules:** `get_by_machine` R4b [BUG-979], R2
- **Kind:** bug
- **Expect:** xfail BUG-979
- **Fails today on:** Then 1 (the row Z is returned)

**Given**
1. Z = stock, `machine_id MF.id`, `item_id I1.id`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=MF.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### MIT-GM-53 — a W1 row of a removed item of W2 is hidden, the other row is returned
- **Rules:** `get_by_machine` R5 [BUG-980], R2
- **Kind:** bug
- **Expect:** xfail BUG-980
- **Fails today on:** Then 1 (the row A is returned too)

**Given**
1. IR = item, but `workspace_id W2.id`, `name "Far Gasket"`, `name_normalized "far gasket"`, `unit "m"`, `is_active False`.
2. A = stock, `machine_id M1.id`, `item_id IR.id`.
3. B = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [B.id]`.

### MIT-GM-54 — a W2 row of a removed item of W1 is hidden
- **Rules:** `get_by_machine` R5 [BUG-980], R2
- **Kind:** bug
- **Expect:** xfail BUG-980
- **Fails today on:** Then 1 (the row Z is returned)

**Given**
1. Z = stock, `machine_id M1.id`, `item_id IX.id`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.


## `DAOMachineItem.get_by_machine_and_item`

### MIT-GP-01 — returns the session's row of that machine and item and writes nothing
- **Rules:** `get_by_machine_and_item` R1, Returns, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I2.id`.
3. C = stock, `machine_id M2.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is A`.
2. returns: `isinstance(result, MachineItem)`.
3. nothing written: nothing written.
4. unchanged: unchanged(A).

### MIT-GP-02 — the same machine with another item is not matched
- **Rules:** `get_by_machine_and_item` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. B = stock, `machine_id M1.id`, `item_id I2.id`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### MIT-GP-03 — the same item on another machine is not matched
- **Rules:** `get_by_machine_and_item` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. C = stock, `machine_id M2.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### MIT-GP-04 — the same pair in another workspace is not matched
- **Rules:** `get_by_machine_and_item` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = stock, `machine_id M1.id`, `item_id I1.id`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.
3. unchanged: unchanged(Z).

### MIT-GP-05 — the same pair in two workspaces: W1 finds its own row
- **Rules:** `get_by_machine_and_item` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. Z = stock, `machine_id M1.id`, `item_id I1.id`, but `workspace_id W2.id`. (Same machine and item as A on purpose: another key, the workspace differs.)

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is A`.

### MIT-GP-06 — the same pair in two workspaces: W2 finds its own row
- **Rules:** `get_by_machine_and_item` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. Z = stock, `machine_id M1.id`, `item_id I1.id`, but `workspace_id W2.id`. (Same machine and item as A on purpose: another key, the workspace differs.)

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is Z`.

### MIT-GP-07 — machine_id=0 returns None and creates nothing
- **Rules:** `get_by_machine_and_item` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=0, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### MIT-GP-08 — item_id=0 returns None and creates nothing
- **Rules:** `get_by_machine_and_item` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### MIT-GP-09 — an unknown machine id returns None and creates nothing
- **Rules:** `get_by_machine_and_item` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=MISSING, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### MIT-GP-10 — an unknown item id returns None and creates nothing
- **Rules:** `get_by_machine_and_item` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### MIT-GP-11 — an unknown workspace returns None and creates nothing
- **Rules:** `get_by_machine_and_item` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=MISSING)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### MIT-GP-12 — no stock row at all: None, and no row is created
- **Rules:** `get_by_machine_and_item` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No stock row exists.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. count: `machine_items` has exactly 0 rows.

### MIT-GP-13 — the row of a soft-deleted machine is found
- **Rules:** `get_by_machine_and_item` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `machine_id MD.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=MD.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is A`.
2. unchanged: unchanged(A).

### MIT-GP-14 — the row of a machine in a soft-deleted factory is found
- **Rules:** `get_by_machine_and_item` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `machine_id MF.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=MF.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is A`.
2. unchanged: unchanged(A).

### MIT-GP-15 — the row of a removed item is found
- **Rules:** `get_by_machine_and_item` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id IX.id`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=IX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is A`.
2. unchanged: unchanged(A).


## `DAOMachineItem.get_by_item`

### MIT-GT-01 — returns a list of the item's rows and writes nothing
- **Rules:** `get_by_item` R1, Returns, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M2.id`, `item_id I1.id`.
3. C = stock, `machine_id M1.id`, `item_id I2.id`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [A.id, B.id]`.
3. returns: `isinstance(result[0], MachineItem)`.
4. nothing written: nothing written.
5. unchanged: unchanged(A).

### MIT-GT-02 — the other item gets only its own row
- **Rules:** `get_by_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M2.id`, `item_id I1.id`.
3. C = stock, `machine_id M1.id`, `item_id I2.id`.

**When**
- `result = dao.get_by_item(db, item_id=I2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### MIT-GT-03 — rows are returned whatever their quantities
- **Rules:** `get_by_item` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`, but `qty 0`.
2. B = stock, `machine_id M2.id`, `item_id I1.id`, but `qty -4`.
3. C = stock, `machine_id M3.id`, `item_id I1.id`, but `qty 3`, `req_qty 9`, `defective_qty 1`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id, C.id]`.

### MIT-GT-04 — the right item under another workspace returns an empty list
- **Rules:** `get_by_item` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### MIT-GT-05 — a W2 row of an item of W1 is returned for W2
- **Rules:** `get_by_item` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = stock, `machine_id M1.id`, `item_id I1.id`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [Z.id]`.

### MIT-GT-06 — a W2 row of an item of W1 is not returned for W1
- **Rules:** `get_by_item` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = stock, `machine_id M1.id`, `item_id I1.id`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIT-GT-07 — the same machine and item in two workspaces: W1 gets only its own row
- **Rules:** `get_by_item` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. Z = stock, `machine_id M1.id`, `item_id I1.id`, but `workspace_id W2.id`. (Same machine and item as A on purpose: another key, the workspace differs.)

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MIT-GT-08 — the same machine and item in two workspaces: W2 gets only its own row
- **Rules:** `get_by_item` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. Z = stock, `machine_id M1.id`, `item_id I1.id`, but `workspace_id W2.id`. (Same machine and item as A on purpose: another key, the workspace differs.)

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [Z.id]`.

### MIT-GT-09 — a W1 row of an item of W2 is returned for W1
- **Rules:** `get_by_item` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I9.id`.

**When**
- `result = dao.get_by_item(db, item_id=I9.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MIT-GT-10 — an unknown item id returns an empty list
- **Rules:** `get_by_item` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_item(db, item_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIT-GT-11 — item_id=0 returns an empty list
- **Rules:** `get_by_item` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_item(db, item_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIT-GT-12 — an item with no rows returns an empty list
- **Rules:** `get_by_item` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_item(db, item_id=I2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIT-GT-13 — on a live and on a soft-deleted machine: only the live machine's row
- **Rules:** `get_by_item` R3a [BUG-981]
- **Kind:** bug
- **Expect:** xfail BUG-981
- **Fails today on:** Then 1 (the row B is returned too)

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id MD.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### MIT-GT-14 — only on a soft-deleted machine: an empty list
- **Rules:** `get_by_item` R3a [BUG-981]
- **Kind:** bug
- **Expect:** xfail BUG-981
- **Fails today on:** Then 1 (the row B is returned)

**Given**
1. B = stock, `machine_id MD.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIT-GT-15 — a W2 row on a soft-deleted machine of W1 is hidden too
- **Rules:** `get_by_item` R3a [BUG-981], R2
- **Kind:** bug
- **Expect:** xfail BUG-981
- **Fails today on:** Then 1 (the row Z is returned)

**Given**
1. Z = stock, `machine_id MD.id`, `item_id I1.id`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### MIT-GT-16 — on a live machine and on one in a soft-deleted factory: only the first row
- **Rules:** `get_by_item` R3b [BUG-981]
- **Kind:** bug
- **Expect:** xfail BUG-981
- **Fails today on:** Then 1 (the row B is returned too)

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id MF.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id]`.

### MIT-GT-17 — only on a machine in a soft-deleted factory: an empty list
- **Rules:** `get_by_item` R3b [BUG-981]
- **Kind:** bug
- **Expect:** xfail BUG-981
- **Fails today on:** Then 1 (the row B is returned)

**Given**
1. B = stock, `machine_id MF.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIT-GT-18 — the rows of a soft-deleted machine stay as they were
- **Rules:** `get_by_item` R3c
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. B = stock, `machine_id MD.id`, `item_id I1.id`, but `req_qty 7`, `defective_qty 1`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. unchanged: unchanged(B).
3. unchanged: unchanged(MD).
4. nothing written: nothing written.

### MIT-GT-19 — the rows of a machine in a soft-deleted factory stay as they were
- **Rules:** `get_by_item` R3c
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. B = stock, `machine_id MF.id`, `item_id I1.id`, but `req_qty 7`, `defective_qty 1`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. unchanged: unchanged(B).
3. unchanged: unchanged(MF).
4. unchanged: unchanged(FD).
5. nothing written: nothing written.

### MIT-GT-20 — an inactive but live machine hides nothing
- **Rules:** `get_by_item` R3c
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id MI.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.

### MIT-GT-21 — a live machine in an inactive but live factory hides nothing
- **Rules:** `get_by_item` R3c
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id MG.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.

### MIT-GT-22 — the row is back, unchanged, once the machine is no longer deleted
- **Rules:** `get_by_item` R3c
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. B = stock, `machine_id MD.id`, `item_id I1.id`, but `req_qty 7`.
2. Snapshot of B taken here.
3. `MD.is_deleted = False`, `MD.is_active = True`, then `db.flush()`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id]`.
2. unchanged: unchanged(B).
3. re-read B: `qty == 5`, `req_qty == 7`.

### MIT-GT-23 — the row is back, unchanged, once the factory is no longer deleted
- **Rules:** `get_by_item` R3c
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. B = stock, `machine_id MF.id`, `item_id I1.id`, but `req_qty 7`.
2. Snapshot of B taken here.
3. `FD.is_deleted = False`, then `db.flush()`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id]`.
2. unchanged: unchanged(B).
3. re-read B: `qty == 5`, `req_qty == 7`.

### MIT-GT-24 — a removed item's rows are returned like any other
- **Rules:** `get_by_item` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id IX.id`.
2. B = stock, `machine_id M2.id`, `item_id IX.id`.

**When**
- `result = dao.get_by_item(db, item_id=IX.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. unchanged: unchanged(A).
3. unchanged: unchanged(IX).

### MIT-GT-25 — 501 machines holding the item: all 501 rows
- **Rules:** `get_by_item` R5 [BUG-982]
- **Kind:** bug
- **Expect:** xfail BUG-982
- **Fails today on:** Then 1 (at most 500 rows come back)

**Given**
1. 501 machines P1 … P501 (each a machine, `workspace_id W1.id`, `factory_id F1.id`, `name` = `f"Press {k:03d}"`, `is_active True`, `is_deleted False`), built with `add_all`.
2. 501 stock rows S1 … S501, built with `add_all`: Sk = stock, `machine_id Pk.id`, `item_id I1.id`. `all_ids` = their ids.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 501`.
2. returns: `sorted(ids(result)) == sorted(all_ids)`.

### MIT-GT-26 — 500 machines holding the item: all 500 rows
- **Rules:** `get_by_item` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 500 machines P1 … P500 (each a machine, `workspace_id W1.id`, `factory_id F1.id`, `name` = `f"Press {k:03d}"`, `is_active True`, `is_deleted False`), built with `add_all`.
2. 500 stock rows S1 … S500, built with `add_all`: Sk = stock, `machine_id Pk.id`, `item_id I1.id`. `all_ids` = their ids.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 500`.
2. returns: `sorted(ids(result)) == sorted(all_ids)`.

### MIT-GT-27 — rows come back in id order
- **Rules:** `get_by_item` R6 [BUG-977]
- **Kind:** bug
- **Expect:** xfail BUG-977 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; the updated row A usually comes back after B — but the physical row order can match the intended order by accident)

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M2.id`, `item_id I1.id`.
3. `A.qty = 6`, then `db.flush()`. (Changed after the later rows were created: this usually moves A physically behind them.)

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. returns: `ids(result) == [A.id, B.id]`.

### MIT-GT-28 — the item query asks the database for id order
- **Rules:** `get_by_item` R6 [BUG-977]
- **Kind:** bug
- **Expect:** xfail BUG-977
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"machine_items.id" in order_part`.
4. statement: `"DESC" not in order_part`.

### MIT-GT-29 — a row carries the name and unit of its item
- **Rules:** `get_by_item` R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I2.id`.

**When**
- `result = dao.get_by_item(db, item_id=I2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `result[0].item_name == "Washer"`.
3. returns: `result[0].item_unit == "kg"`.

### MIT-GT-30 — a row of a removed item carries that item's name and unit
- **Rules:** `get_by_item` R7
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id IX.id`.

**When**
- `result = dao.get_by_item(db, item_id=IX.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `result[0].item_name == "Old Gasket"`.
3. returns: `result[0].item_unit == "m"`.

### MIT-GT-31 — reading a row's item name and unit needs no further query
- **Rules:** `get_by_item` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. `w1_id = W1.id`
3. `i1_id = I1.id`
4. `db.expire_all()` (nothing stays loaded in the session).
5. A recorder for the SQL statements the session sends from here to the last Then line.

**When**
- `result = dao.get_by_item(db, item_id=i1_id, workspace_id=w1_id)`.

**Then**
1. returns: `result[0].item_name == "Bolt"`.
2. returns: `result[0].item_unit == "pcs"`.
3. statement: `len(selects) == 1`.

### MIT-GT-32 — the item query carries no LIMIT and no OFFSET, so no cap of any size exists
- **Rules:** `get_by_item` R5 [BUG-982]
- **Kind:** bug
- **Expect:** xfail BUG-982
- **Fails today on:** Then 2 (the query carries `LIMIT` and `OFFSET`)

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"LIMIT" not in sql`.
3. statement: `"OFFSET" not in sql`.

### MIT-GT-33 — a W2 row on a W1 machine in a soft-deleted factory is hidden too
- **Rules:** `get_by_item` R3b [BUG-981], R2
- **Kind:** bug
- **Expect:** xfail BUG-981
- **Fails today on:** Then 1 (the row Z is returned)

**Given**
1. Z = stock, `machine_id MF.id`, `item_id I1.id`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### MIT-GT-34 — id order holds when the lower id sits on the higher machine
- **Rules:** `get_by_item` R6 [BUG-977]
- **Kind:** bug
- **Expect:** xfail BUG-977 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; on today's plan the rows usually come back in insertion order, which is the intended order here, so this card usually passes today — it exists for the fix)

**Given**
1. A = stock, `machine_id M2.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. returns: `ids(result) == [A.id, B.id]`.


## Inherited `BaseDAO` methods on `MachineItem`

### MIT-INH-01 — create with a dict stores a row with the defaults and writes no ledger row
- **Rules:** `inherited` R1, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. No stock row exists.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "machine_id": M1.id, "item_id": I1.id})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `machine_id == M1.id`, `item_id == I1.id`.
3. re-read the returned row: `qty == 0`, `req_qty is None`, `defective_qty is None`.
4. count: `machine_items` has exactly 1 row.
5. count: `machine_item_ledger` has exactly 0 rows (`db.scalar(text("select count(*) from machine_item_ledger"))`).

### MIT-INH-02 — create with qty=None gives 0
- **Rules:** `inherited` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No stock row exists.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "machine_id": M1.id, "item_id": I1.id, "qty": None})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `qty == 0`.

### MIT-INH-03 — create is flushed, not committed: a rollback removes the row
- **Rules:** `inherited` R1, Overview (never commits)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No stock row exists.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "machine_id": M1.id, "item_id": I1.id})`.

**Then**
1. returns: `result.id is not None`.
2. count: inside the savepoint, `machine_items` has exactly 1 row.
3. count: after the savepoint rollback, `machine_items` has exactly 0 rows.
4. mock called: the `db.commit` spy was never called.

### MIT-INH-04 — create with a MachineItemCreate fails on flush and saves nothing
- **Rules:** `inherited` R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No stock row exists.

**When**
- `dao.create(db, obj_in=MachineItemCreate(machine_id=M1.id, item_id=I1.id))`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `exc.value.orig.pgcode == "23502"`.
4. raises: `'column "workspace_id"' in str(exc.value.orig)`.
5. count: `machine_items` has exactly 0 rows.

### MIT-INH-05 — create with a dict without workspace_id fails on flush and saves nothing
- **Rules:** `inherited` R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No stock row exists.

**When**
- `dao.create(db, obj_in={"machine_id": M1.id, "item_id": I1.id})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `'column "workspace_id"' in str(exc.value.orig)`.
4. count: `machine_items` has exactly 0 rows.

### MIT-INH-06 — create with an unknown machine_id fails on flush and saves nothing
- **Rules:** `inherited` R3, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. No stock row exists.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "machine_id": MISSING, "item_id": I1.id})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `exc.value.orig.pgcode == "23503"`.
4. raises: `"machine_items_machine_id_fkey" in str(exc.value.orig)`.
5. count: `machine_items` has exactly 0 rows.

### MIT-INH-07 — create with an unknown item_id fails on flush and saves nothing
- **Rules:** `inherited` R3, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. No stock row exists.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "machine_id": M1.id, "item_id": MISSING})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `exc.value.orig.pgcode == "23503"`.
4. raises: `"machine_items_item_id_fkey" in str(exc.value.orig)`.
5. count: `machine_items` has exactly 0 rows.

### MIT-INH-08 — create with an unknown workspace_id fails on flush and saves nothing
- **Rules:** `inherited` R3, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. No stock row exists.

**When**
- `dao.create(db, obj_in={"workspace_id": MISSING, "machine_id": M1.id, "item_id": I1.id})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `exc.value.orig.pgcode == "23503"`.
4. raises: `"machine_items_workspace_id_fkey" in str(exc.value.orig)`.
5. count: `machine_items` has exactly 0 rows.

### MIT-INH-09 — create with a key that is no attribute of the model raises TypeError and adds nothing
- **Rules:** `inherited` R3, Errors row 4
- **Kind:** error
- **Expect:** pass

**Given**
1. No stock row exists.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "machine_id": M1.id, "item_id": I1.id, "avg_price": 5})`.

**Then**
1. raises: `TypeError` (plain `with pytest.raises(TypeError):`, no savepoint).
2. count: `machine_items` has exactly 0 rows.
3. returns: `len(db.new) == 0`.

### MIT-INH-10 — a second row for a taken key is refused and the first row stays
- **Rules:** `inherited` R4 [BUG-983], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-983
- **Fails today on:** Then 1 (nothing is refused: the second row is saved)

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`, but `req_qty 7`, `defective_qty 1`.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "machine_id": M1.id, "item_id": I1.id, "qty": 9})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, UniqueViolation)`.
3. raises: `exc.value.orig.pgcode == "23505"`.
4. count: `machine_items` rows with `workspace_id == W1.id`, `machine_id == M1.id`, `item_id == I1.id`: exactly 1.
5. unchanged: unchanged(A).
6. re-read A: `qty == 5`, `req_qty == 7`, `defective_qty == 1`.

### MIT-INH-11 — a taken key of W2 is refused while W1 holds the same pair
- **Rules:** `inherited` R4 [BUG-983], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-983
- **Fails today on:** Then 1 (nothing is refused: a second W2 row is saved)

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. Z = stock, `machine_id M1.id`, `item_id I1.id`, but `workspace_id W2.id`.

**When**
- `dao.create(db, obj_in={"workspace_id": W2.id, "machine_id": M1.id, "item_id": I1.id})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, UniqueViolation)`.
3. raises: `exc.value.orig.pgcode == "23505"`.
4. count: `machine_items` rows with `workspace_id == W2.id`, `machine_id == M1.id`, `item_id == I1.id`: exactly 1.
5. count: `machine_items` rows with `workspace_id == W1.id`, `machine_id == M1.id`, `item_id == I1.id`: exactly 1.
6. unchanged: unchanged(Z).

### MIT-INH-12 — update moving a row onto a taken key by its machine is refused
- **Rules:** `inherited` R4a [BUG-983], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-983
- **Fails today on:** Then 1 (nothing is refused: the move is saved and the key has two rows)

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M2.id`, `item_id I1.id`, but `qty 3`.

**When**
- `dao.update(db, db_obj=B, obj_in={"machine_id": M1.id})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, UniqueViolation)`.
3. raises: `exc.value.orig.pgcode == "23505"`.
4. re-read after `db.refresh(B)`: `B.machine_id == M2.id`, `B.item_id == I1.id`, `B.workspace_id == W1.id`, `B.qty == 3`.
5. unchanged: unchanged(A).
6. count: `machine_items` rows with `workspace_id == W1.id`, `machine_id == M1.id`, `item_id == I1.id`: exactly 1.

### MIT-INH-13 — update moving a row onto a taken key by its item is refused
- **Rules:** `inherited` R4a [BUG-983], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-983
- **Fails today on:** Then 1 (nothing is refused: the move is saved and the key has two rows)

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I2.id`, but `qty 3`.

**When**
- `dao.update(db, db_obj=B, obj_in={"item_id": I1.id})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, UniqueViolation)`.
3. raises: `exc.value.orig.pgcode == "23505"`.
4. re-read after `db.refresh(B)`: `B.machine_id == M1.id`, `B.item_id == I2.id`, `B.workspace_id == W1.id`, `B.qty == 3`.
5. unchanged: unchanged(A).
6. count: `machine_items` rows with `workspace_id == W1.id`, `machine_id == M1.id`, `item_id == I1.id`: exactly 1.

### MIT-INH-14 — update moving a row onto a taken key by its workspace is refused
- **Rules:** `inherited` R4a [BUG-983], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-983
- **Fails today on:** Then 1 (nothing is refused: the move is saved and the key has two rows)

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. Z = stock, `machine_id M1.id`, `item_id I1.id`, but `workspace_id W2.id`, `qty 3`.

**When**
- `dao.update(db, db_obj=Z, obj_in={"workspace_id": W1.id})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, UniqueViolation)`.
3. raises: `exc.value.orig.pgcode == "23505"`.
4. re-read after `db.refresh(Z)`: `Z.machine_id == M1.id`, `Z.item_id == I1.id`, `Z.workspace_id == W2.id`, `Z.qty == 3`.
5. unchanged: unchanged(A).
6. count: `machine_items` rows with `workspace_id == W1.id`, `machine_id == M1.id`, `item_id == I1.id`: exactly 1.

### MIT-INH-15 — the same item on another machine stays allowed
- **Rules:** `inherited` R4b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "machine_id": M2.id, "item_id": I1.id})`.

**Then**
1. returns: `result.id != A.id`.
2. count: `machine_items` has exactly 2 rows.
3. unchanged: unchanged(A).

### MIT-INH-16 — another item on the same machine stays allowed
- **Rules:** `inherited` R4b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "machine_id": M1.id, "item_id": I2.id})`.

**Then**
1. returns: `result.id != A.id`.
2. count: `machine_items` has exactly 2 rows.
3. unchanged: unchanged(A).

### MIT-INH-17 — the same machine and item under W2 stay allowed while W1 holds them
- **Rules:** `inherited` R4b, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W2.id, "machine_id": M1.id, "item_id": I1.id})`.

**Then**
1. returns: `result.id != A.id`.
2. re-read the returned row: `workspace_id == W2.id`, `machine_id == M1.id`, `item_id == I1.id`.
3. count: `machine_items` has exactly 2 rows.
4. unchanged: unchanged(A).

### MIT-INH-18 — the same machine and item under W1 stay allowed while W2 holds them
- **Rules:** `inherited` R4b, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Z = stock, `machine_id M1.id`, `item_id I1.id`, but `workspace_id W2.id`.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "machine_id": M1.id, "item_id": I1.id})`.

**Then**
1. returns: `result.id != Z.id`.
2. re-read the returned row: `workspace_id == W1.id`, `machine_id == M1.id`, `item_id == I1.id`.
3. count: `machine_items` has exactly 2 rows.
4. unchanged: unchanged(Z).

### MIT-INH-19 — update onto a pair W1 holds stays allowed when the row moves to W2
- **Rules:** `inherited` R4b, R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M2.id`, `item_id I1.id`.

**When**
- `result = dao.update(db, db_obj=B, obj_in={"workspace_id": W2.id, "machine_id": M1.id})`.

**Then**
1. returns: `result is B`.
2. re-read B: `workspace_id == W2.id`, `machine_id == M1.id`, `item_id == I1.id`.
3. unchanged: unchanged(A).

### MIT-INH-20 — update naming the row's own key stays allowed
- **Rules:** `inherited` R4b, R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.update(db, db_obj=A, obj_in={"workspace_id": W1.id, "machine_id": M1.id, "item_id": I1.id, "qty": 9})`.

**Then**
1. returns: `result is A`.
2. re-read A: `machine_id == M1.id`, `item_id == I1.id`, `qty == 9`.
3. count: `machine_items` has exactly 1 row.

### MIT-INH-21 — negative quantities are stored
- **Rules:** `inherited` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No stock row exists.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "machine_id": M1.id, "item_id": I1.id, "qty": -4, "req_qty": -4, "defective_qty": -4})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `qty == -4`, `req_qty == -4`, `defective_qty == -4`.

### MIT-INH-22 — qty of 2147483648 is outside the 32-bit range and nothing is saved
- **Rules:** `inherited` R5, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. No stock row exists.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "machine_id": M1.id, "item_id": I1.id, "qty": 2147483648})`.

**Then**
1. raises: `DataError` on flush.
2. raises: `isinstance(exc.value.orig, NumericValueOutOfRange)`.
3. raises: `exc.value.orig.pgcode == "22003"`.
4. count: `machine_items` has exactly 0 rows.

### MIT-INH-23 — req_qty of 2147483648 is outside the 32-bit range and nothing is saved
- **Rules:** `inherited` R5, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. No stock row exists.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "machine_id": M1.id, "item_id": I1.id, "req_qty": 2147483648})`.

**Then**
1. raises: `DataError` on flush.
2. raises: `isinstance(exc.value.orig, NumericValueOutOfRange)`.
3. raises: `exc.value.orig.pgcode == "22003"`.
4. count: `machine_items` has exactly 0 rows.

### MIT-INH-24 — defective_qty of 2147483648 is outside the 32-bit range and nothing is saved
- **Rules:** `inherited` R5, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. No stock row exists.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "machine_id": M1.id, "item_id": I1.id, "defective_qty": 2147483648})`.

**Then**
1. raises: `DataError` on flush.
2. raises: `isinstance(exc.value.orig, NumericValueOutOfRange)`.
3. raises: `exc.value.orig.pgcode == "22003"`.
4. count: `machine_items` has exactly 0 rows.

### MIT-INH-25 — qty of -2147483649 is outside the 32-bit range and nothing is saved
- **Rules:** `inherited` R5, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. No stock row exists.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "machine_id": M1.id, "item_id": I1.id, "qty": -2147483649})`.

**Then**
1. raises: `DataError` on flush.
2. raises: `isinstance(exc.value.orig, NumericValueOutOfRange)`.
3. raises: `exc.value.orig.pgcode == "22003"`.
4. count: `machine_items` has exactly 0 rows.

### MIT-INH-26 — the 32-bit maximum is stored in all three quantities
- **Rules:** `inherited` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No stock row exists.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "machine_id": M1.id, "item_id": I1.id, "qty": 2147483647, "req_qty": 2147483647, "defective_qty": 2147483647})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `qty == 2147483647`, `req_qty == 2147483647`, `defective_qty == 2147483647`.

### MIT-INH-27 — the 32-bit minimum is stored in all three quantities
- **Rules:** `inherited` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No stock row exists.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "machine_id": M1.id, "item_id": I1.id, "qty": -2147483648, "req_qty": -2147483648, "defective_qty": -2147483648})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `qty == -2147483648`, `req_qty == -2147483648`, `defective_qty == -2147483648`.

### MIT-INH-28 — create saves a row for a soft-deleted machine
- **Rules:** `inherited` R6
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. No stock row exists.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "machine_id": MD.id, "item_id": I1.id})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `machine_id == MD.id`.
3. unchanged: unchanged(MD).

### MIT-INH-29 — create saves a row for a removed item
- **Rules:** `inherited` R6
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. No stock row exists.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "machine_id": M1.id, "item_id": IX.id})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `item_id == IX.id`.
3. unchanged: unchanged(IX).

### MIT-INH-30 — create saves a row for an item of another workspace, and item_name gives that item's name
- **Rules:** `inherited` R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No stock row exists.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "machine_id": M1.id, "item_id": I9.id})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `item_id == I9.id`.
3. re-read the returned row: `item_name == "Far Crate"`.

### MIT-INH-31 — update with a MachineItemUpdate applies qty and keeps fields sent as None
- **Rules:** `inherited` R7, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`, but `qty 5`, `req_qty 7`, `defective_qty 1`.

**When**
- `result = dao.update(db, db_obj=A, obj_in=MachineItemUpdate(qty=6, req_qty=None))`.

**Then**
1. returns: `result is A`.
2. re-read A: `qty == 6`, `req_qty == 7`, `defective_qty == 1`.
3. re-read A: `machine_id == M1.id`, `item_id == I1.id`, `workspace_id == W1.id`.
4. count: `machine_item_ledger` has exactly 0 rows (`db.scalar(text("select count(*) from machine_item_ledger"))`).

### MIT-INH-32 — update with a MachineItemUpdate applies qty=0
- **Rules:** `inherited` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.update(db, db_obj=A, obj_in=MachineItemUpdate(qty=0))`.

**Then**
1. returns: `result is A`.
2. re-read A: `qty == 0`.

### MIT-INH-33 — req_qty and defective_qty cannot be cleared through the schema
- **Rules:** `inherited` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`, but `req_qty 7`, `defective_qty 1`.

**When**
- `result = dao.update(db, db_obj=A, obj_in=MachineItemUpdate(req_qty=None, defective_qty=None))`.

**Then**
1. returns: `result is A`.
2. re-read A: `req_qty == 7`, `defective_qty == 1`, `qty == 5`.

### MIT-INH-34 — update is flushed, not committed: a rollback restores the old value
- **Rules:** `inherited` R7, Overview (never commits)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.update(db, db_obj=A, obj_in={"qty": 9})`.

**Then**
1. returns: `result is A`.
2. count: inside the savepoint, `machine_items` rows with `id == A.id` and `qty == 9`: exactly 1.
3. re-read A after the savepoint rollback: `qty == 5`.
4. mock called: the `db.commit` spy was never called.

### MIT-INH-35 — update with a dict clears req_qty and defective_qty
- **Rules:** `inherited` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`, but `req_qty 7`, `defective_qty 1`.

**When**
- `result = dao.update(db, db_obj=A, obj_in={"req_qty": None, "defective_qty": None})`.

**Then**
1. returns: `result is A`.
2. re-read A: `req_qty is None`, `defective_qty is None`, `qty == 5`.

### MIT-INH-36 — update with a dict moves the row to a machine with a free key
- **Rules:** `inherited` R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.update(db, db_obj=A, obj_in={"machine_id": M2.id})`.

**Then**
1. returns: `result is A`.
2. re-read A: `machine_id == M2.id`, `item_id == I1.id`, `qty == 5`.

### MIT-INH-37 — update with qty=None in a dict fails on flush and the row stays
- **Rules:** `inherited` R8, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `dao.update(db, db_obj=A, obj_in={"qty": None})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `'column "qty"' in str(exc.value.orig)`.
4. unchanged: unchanged(A).
5. re-read A: `qty == 5`.

### MIT-INH-38 — remove hard-deletes the row and returns it; nothing else goes
- **Rules:** `inherited` R9, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I2.id`.
3. `a_id = A.id`

**When**
- `result = dao.remove(db, id=a_id)`.

**Then**
1. returns: `result.id == a_id`.
2. count: `machine_items` rows with `id == a_id`: exactly 0.
3. unchanged: unchanged(B).
4. unchanged: unchanged(M1).
5. unchanged: unchanged(I1).
6. count: `machine_item_ledger` has exactly 0 rows (`db.scalar(text("select count(*) from machine_item_ledger"))`).

### MIT-INH-39 — remove of an id with no row returns None and deletes nothing
- **Rules:** `inherited` R9 [BUG-101]
- **Kind:** bug
- **Expect:** xfail BUG-101
- **Fails today on:** Then 1 (the call raises `sqlalchemy.orm.exc.UnmappedInstanceError`: the missing row is passed to the session's delete)

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.remove(db, id=MISSING)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.
3. unchanged: unchanged(A).

### MIT-INH-40 — remove is flushed, not committed: a rollback brings the row back
- **Rules:** `inherited` R9, Overview (never commits)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. `a_id = A.id`
3. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.remove(db, id=a_id)`.

**Then**
1. returns: `result.id == a_id`.
2. count: inside the savepoint, `machine_items` rows with `id == a_id`: exactly 0.
3. count: after the savepoint rollback, `machine_items` rows with `id == a_id`: exactly 1.
4. mock called: the `db.commit` spy was never called.

### MIT-INH-41 — get returns a row of any workspace
- **Rules:** `inherited` R10
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = stock, `machine_id M9.id`, `item_id I9.id`, but `workspace_id W2.id`.

**When**
- `result = dao.get(db, Z.id)`.

**Then**
1. returns: `result.id == Z.id`.
2. returns: `result.workspace_id == W2.id`.

### MIT-INH-42 — get returns None for an unknown id
- **Rules:** `inherited` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get(db, MISSING)`.

**Then**
1. returns: `result is None`.

### MIT-INH-43 — get_multi is not scoped to a workspace
- **Rules:** `inherited` R10
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. Z = stock, `machine_id M9.id`, `item_id I9.id`, but `workspace_id W2.id`.

**When**
- `result = dao.get_multi(db)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, Z.id]`.

### MIT-INH-44 — get_multi returns the rows in id order
- **Rules:** `inherited` R10 [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; the updated row A usually comes back after B — but the physical row order can match the intended order by accident)

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. B = stock, `machine_id M1.id`, `item_id I2.id`.
3. `A.qty = 6`, then `db.flush()`. (Changed after the later rows were created: this usually moves A physically behind them.)

**When**
- `result = dao.get_multi(db)`.

**Then**
1. returns: `sorted(ids(result)) == [A.id, B.id]`.
2. returns: `ids(result) == [A.id, B.id]`.

### MIT-INH-45 — the get_multi query asks the database for id order
- **Rules:** `inherited` R10 [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_multi(db)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"machine_items.id" in order_part`.
4. statement: `"DESC" not in order_part`.

### MIT-INH-46 — a hard delete of a machine with a stock row is refused by the database
- **Rules:** `inherited` R11
- **Kind:** error
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `db.execute(text("delete from machines where id = :i"), {"i": M1.id})`.

**Then**
1. raises: `IntegrityError` when the statement runs.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"machine_items_machine_id_fkey" in str(exc.value.orig)`.
4. unchanged: unchanged(A).
5. unchanged: unchanged(M1).

### MIT-INH-47 — a hard delete of an item with a stock row is refused by the database
- **Rules:** `inherited` R11
- **Kind:** error
- **Expect:** pass

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `db.execute(text("delete from items where id = :i"), {"i": I1.id})`.

**Then**
1. raises: `IntegrityError` when the statement runs.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"machine_items_item_id_fkey" in str(exc.value.orig)`.
4. unchanged: unchanged(A).
5. unchanged: unchanged(I1).

### MIT-INH-48 — a hard delete of the workspace removes its stock rows
- **Rules:** `inherited` R11
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W3 = a third `workspaces` row with no rows of its own in any other table.
2. A = stock, `machine_id M1.id`, `item_id I1.id`.
3. B = stock, `machine_id M1.id`, `item_id I1.id`, but `workspace_id W3.id`.
4. `b_id = B.id`
5. `w3_id = W3.id`

**When**
- `db.execute(text("delete from workspaces where id = :i"), {"i": w3_id})`.

**Then**
1. count: `machine_items` rows with `id == b_id`: exactly 0.
2. unchanged: unchanged(A).
3. unchanged: unchanged(M1).
4. unchanged: unchanged(I1).

### MIT-INH-49 — without a loaded item, item_name and item_unit are None
- **Rules:** `inherited` R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `row = MachineItem(item_id=1)` (never added to the session).

**When**
- `result = (row.item_name, row.item_unit)`.

**Then**
1. returns: `result[0] is None`.
2. returns: `result[1] is None`.

### MIT-INH-50 — get_multi id order holds across workspaces, the higher workspace's row first
- **Rules:** `inherited` R10 [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; on today's plan the rows usually come back in insertion order, which is the intended order here, so this card usually passes today — it exists for the fix)

**Given**
1. Z = stock, `machine_id M9.id`, `item_id I9.id`, but `workspace_id W2.id`.
2. A = stock, `machine_id M1.id`, `item_id I1.id`.

**When**
- `result = dao.get_multi(db)`.

**Then**
1. returns: `sorted(ids(result)) == [Z.id, A.id]`.
2. returns: `ids(result) == [Z.id, A.id]`.

### MIT-INH-51 — remove of an id with no row does not commit
- **Rules:** `inherited` R9 [BUG-101], Overview (never commits)
- **Kind:** bug
- **Expect:** xfail BUG-101
- **Fails today on:** Then 1 (the call raises `sqlalchemy.orm.exc.UnmappedInstanceError`: the missing row is passed to the session's delete)

**Given**
1. A = stock, `machine_id M1.id`, `item_id I1.id`.
2. A spy that wraps `db.commit` (still callable, records calls). No savepoint: there is no write to roll back.

**When**
- `result = dao.remove(db, id=MISSING)`.

**Then**
1. returns: `result is None`.
2. mock called: the `db.commit` spy was never called.


## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| FU-1 (a) — `list_machine_items` without `machine_id` must hide rows of deleted parents, in the query, and needs a display order (P6) | `MachineItemManager` | Here `get_by_workspace` stays raw (MIT-GW-07 … GW-10). |
| FU-1 (b), (c) — `machine_id=0` treated as no filter; `create_machine_item` never checks the item | `MachineItemManager` | Here `create` accepts such items (MIT-INH-28 … INH-30). |
| FU-1 (d) — **OWNER, stock:** no minimum on the quantities, `qty` beyond 32 bits | `MachineItemCreate` / `MachineItemUpdate`, `MachineItemManager` | Here negative values are stored and range errors raised (MIT-INH-21 … INH-27). |
| FU-1 (e), (f), (g) — clearing `req_qty`; what the raw lookups answer for hidden rows; HR-10 on `update_machine_item` | `MachineItemManager` | A row lock cannot be observed with one connection. |
| FU-1 (h) — a lost race on the duplicate check answers 409, never 500 (BUG-983) | `MachineItemManager.create_machine_item` | Here the DAO lets `IntegrityError` through (MIT-INH-10). |
| FU-2 — fallbacks in `_machine_placements`, zero rows counted, a removed item's own summary | `ItemSummaryService` | Here `get_by_item` R4 (MIT-GT-24). |
| FU-3 (a), (c) — locked read of the pair; `ensure_machine_item` carries on after a lost insert race (BUG-661, BUG-643, BUG-820, BUG-983) | `inventory_movements`, `ledger_manager` | The plain read here stays unlocked. |
| FU-3 (b) — case EMI-07 inserts two rows for a key and fails once the index exists; `ensure_machine_item` R4 becomes unreachable | `tests/unit/managers/inventory_movements.*` | Must be updated with the BUG-983 fix. |
| FU-4 — a row of a deleted machine can block an item delete while no list shows it (**OWNER, stock**) | `delete_item`, `delete_machine` | No card here. |
| `scripts/merge_duplicate_machine_items.py` — the cleanup that must run before the index | BUG-983 fix | A script with no spec of its own; no card here. |
| Generic behavior of `get`, `get_multi`, `create`, `update`, `remove` | `tests/unit/dao/base.spec.md` / `base.cases.md` | Only what this model and its schemas change has cards. |
| `get_by_item` `skip` / `limit` — dead parameters, removed with BUG-982 (P7) | `docs/testing/dead-code-removal-checklist.md` | Not specified. No card calls them, so their removal needs no card change. |
| Notes: keyword-only parameters | none (no rule) | Spec gap 3. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `get_by_machine` R11 ("as `get_by_workspace` R7") | R7 says "also for a removed item", but R5 hides that row from `get_by_machine`. | R11 is tested on active items only (MIT-GM-50, GM-51). Harmless; the sentence cannot hold after BUG-980. |
| 2 | `get_by_machine` Notes ("Today's result is deterministic … strict xfail") against R5's `limit=1` example | The Notes make every BUG-980 card strict, but which row `limit=1` keeps today rests on physical order, and the skill's Missing-sort-order rule makes such a card non-strict. | MIT-GM-28 is non-strict. The strict alarm for "takes no place in the page" is MIT-GM-27, which depends only on a row count (`skip=2`). |
| 3 | Notes ("every parameter after `db` is keyword-only") | Stated as a note, not as a rule. | No card (as in `item_tag.cases.md`). |
| 4 | `get_by_machine` R6 | How the case-insensitive key looks in SQL, and which alias the item has, is not stated (`lower(items.name)`, a joined alias `items_1`, …). | MIT-GM-36 asserts `lower(` and `.name` before `machine_items.id`, nothing tighter. If the fix uses a collation instead of `lower`, those lines change with it. |
| 5 | Inherited Side effects ("no activity event") | The table of activity events is not named. | Only the ledger is counted (MIT-INH-01, INH-31, INH-38). |
| 6 | Inherited R11 ("a hard delete") | No callable does it, and whether a workspace can be deleted while it has other rows is not stated. | The action is a raw `DELETE` statement; the cascade card uses a third, otherwise empty workspace (MIT-INH-46 … INH-48). |
| 7 | Inherited Errors ("Detail message: — (not asserted)") | The Raises column and R3 name the constraints and columns, the Detail column says not asserted. | Loose `in str(exc.value.orig)` lines on the constraint or column name. Drop them if the text must not be asserted. BUG-983 cards name no index, as ordered. |
| 8 | Inherited section | The signatures of `get_multi`, `remove`, `update`, `create` are not in this spec. | Keyword forms taken from `item_tag.cases.md` / `base.cases.md`. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_workspace` | Returns | MIT-GW-01 |
| `get_by_workspace` | R1 | MIT-GW-01, MIT-GW-02, MIT-GW-03, MIT-GW-04, MIT-GW-05 |
| `get_by_workspace` | R2 | MIT-GW-06, MIT-GW-07, MIT-GW-08, MIT-GW-09, MIT-GW-10 |
| `get_by_workspace` | R3 [BUG-100] | MIT-GW-11, MIT-GW-12, MIT-GW-13, MIT-GW-14, MIT-GW-33 |
| `get_by_workspace` | R4 | MIT-GW-12, MIT-GW-13, MIT-GW-15, MIT-GW-16, MIT-GW-17, MIT-GW-18, MIT-GW-19, MIT-GW-20, MIT-GW-25, MIT-GW-27 |
| `get_by_workspace` | R5 | MIT-GW-21, MIT-GW-22, MIT-GW-23, MIT-GW-24, MIT-GW-25, MIT-GW-26, MIT-GW-27 |
| `get_by_workspace` | R6 | MIT-GW-28, MIT-GW-29 |
| `get_by_workspace` | R7 | MIT-GW-30, MIT-GW-31, MIT-GW-32 |
| `get_by_workspace` | Errors row 1 | MIT-GW-28 |
| `get_by_workspace` | Errors row 2 | MIT-GW-29 |
| `get_by_workspace` | Side effects | MIT-GW-01 |
| `get_by_id_and_workspace` | Returns | MIT-GI-01 |
| `get_by_id_and_workspace` | R1 | MIT-GI-01, MIT-GI-04 |
| `get_by_id_and_workspace` | R2 | MIT-GI-02, MIT-GI-03, MIT-GI-04, MIT-GI-05, MIT-GI-06 |
| `get_by_id_and_workspace` | R3 | MIT-GI-07, MIT-GI-08 |
| `get_by_id_and_workspace` | R4 | MIT-GI-09, MIT-GI-10, MIT-GI-11 |
| `get_by_id_and_workspace` | Side effects | MIT-GI-01 |
| `get_by_machine` | Returns | MIT-GM-01 |
| `get_by_machine` | R1 | MIT-GM-01, MIT-GM-02, MIT-GM-03, MIT-GM-04 |
| `get_by_machine` | R2 | MIT-GM-04, MIT-GM-05, MIT-GM-06, MIT-GM-07, MIT-GM-08, MIT-GM-09, MIT-GM-10, MIT-GM-11, MIT-GM-17, MIT-GM-52, MIT-GM-53, MIT-GM-54 |
| `get_by_machine` | R3 | MIT-GM-12 |
| `get_by_machine` | R4 | MIT-GM-13, MIT-GM-14, MIT-GM-15 |
| `get_by_machine` | R4a [BUG-979] | MIT-GM-16, MIT-GM-17 |
| `get_by_machine` | R4b [BUG-979] | MIT-GM-18, MIT-GM-52 |
| `get_by_machine` | R4c | MIT-GM-19, MIT-GM-20, MIT-GM-21, MIT-GM-22, MIT-GM-23, MIT-GM-24 |
| `get_by_machine` | R5 [BUG-980] | MIT-GM-25, MIT-GM-26, MIT-GM-27, MIT-GM-28, MIT-GM-53, MIT-GM-54 |
| `get_by_machine` | R5a | MIT-GM-29, MIT-GM-30 |
| `get_by_machine` | R6 [BUG-976] | MIT-GM-31, MIT-GM-32, MIT-GM-33, MIT-GM-34, MIT-GM-35, MIT-GM-36 |
| `get_by_machine` | R7 | MIT-GM-34, MIT-GM-35, MIT-GM-37, MIT-GM-38, MIT-GM-39, MIT-GM-40, MIT-GM-41, MIT-GM-42, MIT-GM-44, MIT-GM-47 |
| `get_by_machine` | R8 | MIT-GM-43, MIT-GM-44, MIT-GM-45, MIT-GM-46, MIT-GM-47 |
| `get_by_machine` | R9 | MIT-GM-48, MIT-GM-49 |
| `get_by_machine` | R10 | no case, as the spec orders (restated; MIT-INH-10 tests the index) |
| `get_by_machine` | R11 | MIT-GM-50, MIT-GM-51 |
| `get_by_machine` | Errors row 1 | MIT-GM-48 |
| `get_by_machine` | Errors row 2 | MIT-GM-49 |
| `get_by_machine` | Side effects | MIT-GM-01 |
| `get_by_machine_and_item` | Returns | MIT-GP-01 |
| `get_by_machine_and_item` | R1 | MIT-GP-01 |
| `get_by_machine_and_item` | R2 | MIT-GP-02, MIT-GP-03, MIT-GP-04, MIT-GP-05, MIT-GP-06 |
| `get_by_machine_and_item` | R3 | MIT-GP-07, MIT-GP-08, MIT-GP-09, MIT-GP-10, MIT-GP-11, MIT-GP-12 |
| `get_by_machine_and_item` | R4 | MIT-GP-13, MIT-GP-14, MIT-GP-15 |
| `get_by_machine_and_item` | R5 | no case, as the spec orders (restated; MIT-INH-10 tests the index) |
| `get_by_machine_and_item` | Side effects | MIT-GP-01 |
| `get_by_item` | Returns | MIT-GT-01 |
| `get_by_item` | R1 | MIT-GT-01, MIT-GT-02, MIT-GT-03 |
| `get_by_item` | R2 | MIT-GT-04, MIT-GT-05, MIT-GT-06, MIT-GT-07, MIT-GT-08, MIT-GT-09, MIT-GT-15, MIT-GT-33 |
| `get_by_item` | R3 | MIT-GT-10, MIT-GT-11, MIT-GT-12 |
| `get_by_item` | R3a [BUG-981] | MIT-GT-13, MIT-GT-14, MIT-GT-15 |
| `get_by_item` | R3b [BUG-981] | MIT-GT-16, MIT-GT-17, MIT-GT-33 |
| `get_by_item` | R3c | MIT-GT-18, MIT-GT-19, MIT-GT-20, MIT-GT-21, MIT-GT-22, MIT-GT-23 |
| `get_by_item` | R4 | MIT-GT-24 |
| `get_by_item` | R5 [BUG-982] | MIT-GT-25, MIT-GT-26, MIT-GT-32 |
| `get_by_item` | R6 [BUG-977] | MIT-GT-27, MIT-GT-28, MIT-GT-34 |
| `get_by_item` | R7 | MIT-GT-29, MIT-GT-30, MIT-GT-31 |
| `get_by_item` | R8 | no case, as the spec orders (restated; MIT-INH-10 tests the index) |
| `get_by_item` | Side effects | MIT-GT-01 |
| `inherited` | R1 | MIT-INH-01, MIT-INH-02, MIT-INH-03 |
| `inherited` | R2 | MIT-INH-04, MIT-INH-05 |
| `inherited` | R3 | MIT-INH-06, MIT-INH-07, MIT-INH-08, MIT-INH-09 |
| `inherited` | R4 [BUG-983] | MIT-INH-10, MIT-INH-11 |
| `inherited` | R4a [BUG-983] | MIT-INH-12, MIT-INH-13, MIT-INH-14 |
| `inherited` | R4b | MIT-INH-15, MIT-INH-16, MIT-INH-17, MIT-INH-18, MIT-INH-19, MIT-INH-20 |
| `inherited` | R5 | MIT-INH-21, MIT-INH-22, MIT-INH-23, MIT-INH-24, MIT-INH-25, MIT-INH-26, MIT-INH-27 |
| `inherited` | R6 | MIT-INH-17, MIT-INH-18, MIT-INH-28, MIT-INH-29, MIT-INH-30 |
| `inherited` | R7 | MIT-INH-31, MIT-INH-32, MIT-INH-33, MIT-INH-34 |
| `inherited` | R8 | MIT-INH-19, MIT-INH-20, MIT-INH-35, MIT-INH-36, MIT-INH-37 |
| `inherited` | R9 [BUG-101] | MIT-INH-38, MIT-INH-39, MIT-INH-40, MIT-INH-51 |
| `inherited` | R10 [BUG-100] | MIT-INH-41, MIT-INH-42, MIT-INH-43, MIT-INH-44, MIT-INH-45, MIT-INH-50 |
| `inherited` | R11 | MIT-INH-46, MIT-INH-47, MIT-INH-48 |
| `inherited` | R12 | MIT-INH-49 |
| `inherited` | Errors row 1 | MIT-INH-04, MIT-INH-05, MIT-INH-37 |
| `inherited` | Errors row 2 | MIT-INH-06, MIT-INH-07, MIT-INH-08 |
| `inherited` | Errors row 3 | MIT-INH-22, MIT-INH-23, MIT-INH-24, MIT-INH-25 |
| `inherited` | Errors row 4 | MIT-INH-09 |
| `inherited` | Errors row 5 | MIT-INH-10, MIT-INH-11, MIT-INH-12, MIT-INH-13, MIT-INH-14 |
| `inherited` | Side effects | MIT-INH-01, MIT-INH-31, MIT-INH-38 |
| `inherited` | Overview (never commits) | MIT-INH-03, MIT-INH-34, MIT-INH-40, MIT-INH-51 |
| BUG-100 | get_by_workspace R3, inherited R10 | MIT-GW-11, MIT-GW-12, MIT-GW-13, MIT-GW-14, MIT-INH-44, MIT-INH-45, MIT-GW-33, MIT-INH-50 |
| BUG-101 | inherited R9 | MIT-INH-39, MIT-INH-51 |
| BUG-976 | get_by_machine R6 | MIT-GM-31, MIT-GM-32, MIT-GM-33, MIT-GM-34, MIT-GM-35, MIT-GM-36 |
| BUG-977 | get_by_item R6 | MIT-GT-27, MIT-GT-28, MIT-GT-34 |
| BUG-979 | get_by_machine R4a, get_by_machine R4b | MIT-GM-16, MIT-GM-17, MIT-GM-18, MIT-GM-52 |
| BUG-980 | get_by_machine R5 | MIT-GM-25, MIT-GM-26, MIT-GM-27, MIT-GM-28, MIT-GM-53, MIT-GM-54 |
| BUG-981 | get_by_item R3a, get_by_item R3b | MIT-GT-13, MIT-GT-14, MIT-GT-15, MIT-GT-16, MIT-GT-17, MIT-GT-33 |
| BUG-982 | get_by_item R5 | MIT-GT-25, MIT-GT-32 |
| BUG-983 | inherited R4, inherited R4a | MIT-INH-10, MIT-INH-11, MIT-INH-12, MIT-INH-13, MIT-INH-14 |
| BUG-978 | superseded by BUG-983; no rule carries the tag | no case (see BUG-983) |
