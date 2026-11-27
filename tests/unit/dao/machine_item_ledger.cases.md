# Test cases — `app/dao/machine_item_ledger.py`

> **Spec:** `tests/unit/dao/machine_item_ledger.spec.md` (source commit e48a092)
> **Status:** READY — designed against the **APPROVED** spec (2026-10-30). Q1 is the owner's own answer; P1–P3 and Q2–Q6 were decided by Claude under the reviewer's delegation.
> **Revision:** 1 — spec fill-gaps round (Gap log G1–G11). New cards: R1a of the response, inherited R1a and R1b, `get_by_performer` R3 and R4, `get_by_date_range` R3a. Existing cards keep their IDs; three changed: MIL-INH-34, INH-35, INH-38 (rule tags for the new R1b and Errors rows; INH-35 also checks the error text). MIL-DR-19's caveat is gone from the summary; the card is unchanged. No ID retired.
> **Revision:** 2 — `machine_item_ledger.verify.md` findings 1–4, all `case-missing`. Finding 1: MIL-MI-31, TT-58, DR-62, MA-29, LE-24, PF-28 (pending row), LE-25 (commit spy). Finding 2: RS-26. Finding 3: RS-27, RS-28. Finding 4: INH-77 … INH-81. Spec gaps 12 and 13 closed; rounding wording follows the owner's answer. No existing card changed, no ID retired.
> **Counts:** 401 cases · 343 expected-to-pass · 58 expected-to-fail (bugs) · 14 deferred

## Reviewer summary
- **Per callable:** `get_by_item` 30 (2 bug) · `get_by_machine_and_item` 31 (2 bug) · `get_by_transaction_type` 58 (2 bug) · `get_by_date_range` 62 (9 bug) · `get_by_machine` 29 (2 bug) · `calculate_balance` 29 (2 bug) · `get_latest_entry` 25 (2 bug) · `get_by_performer` 28 (28 bug) · inherited 81 (2 bug) · response schema 28 (7 bug).
- **Expected-to-fail by bug:** BUG-100 1 strict + 1 non-strict · BUG-640 5 strict + 5 non-strict · BUG-641 1 strict + 1 non-strict · BUG-645 28 strict · BUG-664 1 strict + 1 non-strict · BUG-990 7 strict · BUG-992 7 strict. BUG-991 is integration-only (deferred); BUG-993 has no card here (machine item manager, deferred).
- **Delegated answers and the cards that rest on them:** P1, P2 (a ledger is history) — the soft-delete cards of the five lists. P3 — MIL-BAL and MIL-LE soft-delete cards. Q2 / BUG-990 — MIL-RS-09 … RS-15. Q3 / BUG-991 — deferred; DR-07, DR-08 pin the DAO half. Q4 / BUG-992 — the R3a cards. Q6 — MIL-TT-28.
- **Notable design choices:**
  - Sort order follows the skill: each of the eight queries has one **strict** statement-recorder card, and every card comparing a tie order produced today is **non-strict**. Five lists, `calculate_balance`, `get_latest_entry` and `get_by_workspace` each have both. A pass card per query keeps what holds today (tied rows sit between the newer and the older one).
  - `get_by_performer` does not exist: all its cards are strict xfails failing in the call, tie order included. They hold no assertion to mirror in a pass card.
  - One card per type on `get_by_transaction_type` (14 types), each next to a look-alike type (`consumption` / `consumption_reversal`), and one response-schema card per type: the 8 allowed types pass, the 6 written types plus `sale` are xfail.
  - BUG-992 cards set `SET LOCAL TIME ZONE` explicitly. MIL-DR-59 (naive start, aware end) is the one strict card the spec's `Today` note does not list; it follows from the same note. The `+06:00` pass control MIL-DR-21 under `UTC` catches a fix that cuts off the zone instead of converting.
  - The pass cards MIL-DR-23, DR-24 (`None` bound raises `ArgumentError`) pin behavior the BUG-341 fix is meant to change; the spec states this, and they must be rewritten with that fix.
  - Inherited R1a cards follow the rule the owner chose on 2026-10-30, half up (BUG-1040, HR-15): the database already rounds that way, so they stand.
  - MIL-LE-25 is a commit spy on a reader, which the skill does not ask for: verify finding 1, because this lookup runs inside every machine stock movement and a commit there would save half a movement.
  - No card for "the schema rejects six types" (inherited R2, last sentence): Q2 calls that irrelevant and the BUG-990 fix may remove it. Hard deletes of a machine, item or profile use a `DELETE` statement.
- **Needs a decision:** None. Every spec gap is closed; FU-6 is answered, half up.


## Conventions for this module

**IDs.** `MIL` = `app/dao/machine_item_ledger.py`. `IT` get_by_item · `MI` get_by_machine_and_item · `TT` get_by_transaction_type · `DR` get_by_date_range · `MA` get_by_machine · `BAL` calculate_balance · `LE` get_latest_entry · `PF` get_by_performer · `INH` inherited `BaseDAO` methods · `RS` response schema.

**Actors and fixed values.**
- `dao` = the singleton `machine_item_ledger_dao` (`from app.dao.machine_item_ledger import machine_item_ledger_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword (only `dao.get(db, <id>)` takes the id positionally). `result` = what the When call returns.
- W1, W2 = two `workspaces` rows, U1, U2 = two `profiles` rows (`make_workspace`, `make_profile` of `tests/unit/factories.py`).
- `MachineItemLedger` = `app.models.machine_item_ledger.MachineItemLedger`. `MachineItemLedgerCreate`, `MachineItemLedgerUpdate`, `MachineItemLedgerResponse` = the schemas of `app.schemas.machine_item_ledger`. `select`, `text` = `sqlalchemy.select`, `sqlalchemy.text`.
- MISSING = `999999999`: an id that no row of any table has.
- T1 = `datetime(2026, 1, 1, 9, 0, 0)`, T2 = `datetime(2026, 1, 1, 10, 0, 0)`, T3 = `datetime(2026, 1, 1, 11, 0, 0)`, T4 = `datetime(2026, 1, 1, 12, 0, 0)`, T5 = `datetime(2026, 1, 1, 13, 0, 0)` (all naive; January, so New York is UTC-5).
- Z1130 = `datetime(2026, 1, 1, 11, 30, tzinfo=timezone.utc)`, Z1230 = `datetime(2026, 1, 1, 12, 30, tzinfo=timezone.utc)`.
- P1730 = `datetime(2026, 1, 1, 17, 30, tzinfo=timezone(timedelta(hours=6)))`, P1830 = `datetime(2026, 1, 1, 18, 30, tzinfo=timezone(timedelta(hours=6)))` (the same two instants as Z1130, Z1230).
- HIGH_ID = `max(greatest machine_item_ledger.id or 0, last_value of machine_item_ledger_id_seq) + 1000001`, read when the row is built.
- FULL = `{"workspace_id": W1.id, "machine_id": M1.id, "item_id": I1.id, "transaction_type": "manual_add", "quantity": 3, "unit_cost": Decimal("2.50"), "total_cost": Decimal("7.50"), "qty_before": 4, "qty_after": 7, "source_type": "manual", "performed_by": U1.id}`.

**Externals.** None. Nothing is mocked and no clock is patched; `performed_at` is always set explicitly on Given rows.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so sequence ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from these defaults.
- These rows exist in every test and need no Given line:
  - F1 = `Factory(workspace_id=W1.id, name="Factory One", abbreviation="F1")`. F9 = the same, `workspace_id W2.id`, `name "Factory Nine"`, `abbreviation "F9"`. FD = the same as F1, `name "Old Plant"`, `abbreviation "OP"`, `is_deleted True`.
  - M1, M2 = `Machine(workspace_id=W1.id, factory_id=F1.id, name=...)`, `name "Press 1"`, `"Press 2"`. MD = the same, `name "Press 4"`, `is_deleted True`. MF = `Machine(workspace_id=W1.id, factory_id=FD.id, name="Press 5")` (live machine of a soft-deleted factory).
  - I1, I2 = `Item(workspace_id=W1.id, name=..., name_normalized=..., unit="pcs")`, `"Bolt"` / `"bolt"`, `"Nut"` / `"nut"`. IR = the same, `"Old Gasket"` / `"old gasket"`, `is_active False`.
- Ledger entries exist only if the card's Given lists them.
- **entry** = `machine_item_ledger` row built with `MachineItemLedger`: `workspace_id W1.id`, `machine_id M1.id`, `item_id I1.id`, `transaction_type "manual_add"`, `quantity 1`, `unit_cost Decimal("2.00")`, `total_cost Decimal("2.00")`, `qty_before 4`, `qty_after 5`, `source_type "manual"`, `performed_by U1.id`, every nullable column None, sequence `id`. The card always gives `performed_at`; after the word "but" it lists every other column that differs. `performed_at T1 + timedelta(minutes=k)` is written as code.
- A Given line written as code is a step to run exactly as written, at that place in the order.

**Named checks.**
- **ids(result)** = `[row.id for row in result]` — a list in the order returned (the order is part of the check).
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line).
- **nothing written** = the numbers of rows in `machine_item_ledger`, `machines`, `items` and `factories` (all workspaces) equal their values before the call.
- **close to now** = `abs(datetime.now(timezone.utc).replace(tzinfo=None) - value) < timedelta(minutes=5)`.
- Prices and values are compared as `Decimal` values, never as strings, unless the line itself uses `str(...)`.
- `raises: DataError`, `raises: IntegrityError` = `sqlalchemy.exc.DataError`, `sqlalchemy.exc.IntegrityError`. Wrap the call: `with pytest.raises(<Type>) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards. `NotNullViolation`, `ForeignKeyViolation`, `RestrictViolation`, `StringDataRightTruncation`, `NumericValueOutOfRange`, `InvalidRowCountInLimitClause`, `InvalidRowCountInResultOffsetClause` = classes of `psycopg2.errors`.
- `raises: ValidationError` = `pydantic.ValidationError`. Plain `with pytest.raises(ValidationError) as exc:` around the call, no `begin_nested`.
- `raises: ArgumentError` = `sqlalchemy.exc.ArgumentError`. Plain `with pytest.raises(ArgumentError) as exc:` around the call, no `begin_nested` (a savepoint would send SQL).
- Further `raises:` lines of the same card are assertions on `exc.value` or `exc.value.orig`, written after the `with` block, one `assert` per line.

**xfail cards.** Write the call and the checks exactly as shown. `Expect: xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `xfail BUG-n (non-strict)` = `strict=False`, for the cards comparing an order or a tie result that rests on physical row order. Their assertions are never weakened.

**Rolled back.** `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); the first checks run inside the savepoint; then `sp.rollback()` and the "after the savepoint rollback" checks.

**Statement recorder.** The SQL statements sent during the When are recorded with `StatementRecorder` as in `tests/unit/managers/test_ledger_manager.py` (`before_cursor_execute` listener on the engine). `statements` = the list recorded; `sql` = the text of the one `SELECT` sent; `order_part` = the text of `sql` after `ORDER BY` (`""` when there is none). A `statement:` line is a check on these texts.

**Race simulations.** None in this module.


## `MachineItemLedgerDAO.get_by_item`

### MIL-IT-01 — an entry of another item is not returned
- **Rules:** `get_by_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `item_id I2.id`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-IT-02 — an entry of another workspace with the same item and machine ids is not returned
- **Rules:** `get_by_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. X9 = entry, `performed_at T5`, but `workspace_id W2.id`. (Same machine and item ids as a W1 entry, on purpose.)

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-IT-03 — the other workspace gets only its own entry
- **Rules:** `get_by_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. X9 = entry, `performed_at T5`, but `workspace_id W2.id`. (Same machine and item ids as a W1 entry, on purpose.)

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [X9.id]`.

### MIL-IT-04 — an unknown workspace id returns an empty list
- **Rules:** `get_by_item` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### MIL-IT-05 — an unknown item id returns an empty list
- **Rules:** `get_by_item` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_item(db, item_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIL-IT-06 — an item without entries returns an empty list
- **Rules:** `get_by_item` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_item(db, item_id=I2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIL-IT-07 — entries of every machine, transaction type and performer are returned
- **Rules:** `get_by_item` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `machine_id M2.id`.
3. E3 = entry, `performed_at T3`, but `transaction_type "consumption"`.
4. E4 = entry, `performed_at T4`, but `performed_by U2.id`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E4.id, E3.id, E2.id, E1.id]`.

### MIL-IT-08 — item_id 0 returns an empty list and raises nothing
- **Rules:** `get_by_item` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_item(db, item_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIL-IT-09 — item_id None returns an empty list and raises nothing
- **Rules:** `get_by_item` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_item(db, item_id=None, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIL-IT-10 — an entry not yet flushed is not seen
- **Rules:** `get_by_item` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, added with `db.add(E2)` and not flushed.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-IT-11 — returns a list of ledger rows, newest first whatever the insertion order, and writes nothing
- **Rules:** `get_by_item` R4, R9, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `isinstance(result[0], MachineItemLedger)`.
3. returns: `ids(result) == [E2.id, E3.id, E1.id]`.
4. nothing written: nothing written.
5. unchanged: unchanged(E1).

### MIL-IT-12 — skip 1 and limit 1 return exactly the middle entry
- **Rules:** `get_by_item` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E3.id]`.

### MIL-IT-13 — limit 2 returns the two newest entries
- **Rules:** `get_by_item` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `ids(result) == [E2.id, E3.id]`.

### MIL-IT-14 — limit 1 returns only the newest entry
- **Rules:** `get_by_item` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### MIL-IT-15 — skip one below the number of entries returns the oldest entry
- **Rules:** `get_by_item` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-IT-16 — skip equal to the number of entries returns an empty list
- **Rules:** `get_by_item` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id, skip=3)`.

**Then**
1. returns: `result == []`.

### MIL-IT-17 — skip past the number of entries returns an empty list
- **Rules:** `get_by_item` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id, skip=4)`.

**Then**
1. returns: `result == []`.

### MIL-IT-18 — limit 0 returns an empty list
- **Rules:** `get_by_item` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### MIL-IT-19 — paging counts matching entries only: newer entries left out by the filters use no place on the page
- **Rules:** `get_by_item` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.
3. EX = entry, `performed_at T3`, but `item_id I2.id`.
4. X9 = entry, `performed_at T5`, but `workspace_id W2.id`. (Same machine and item ids as a W1 entry, on purpose.)

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-IT-20 — by default at most the 100 newest of 101 entries are returned; the oldest is missing
- **Rules:** `get_by_item` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 entries N1 … N101, inserted in that order; Nk (k = 1 … 101) = entry, `performed_at T1 + timedelta(minutes=k)`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result)` == the ids of N101, N100, … N2, in that order.
3. returns: `N1.id not in ids(result)`.

### MIL-IT-21 — exactly 100 entries are all returned by default
- **Rules:** `get_by_item` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 100 entries N1 … N100, inserted in that order; Nk (k = 1 … 100) = entry, `performed_at T1 + timedelta(minutes=k)`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result)` == the ids of N100, N99, … N1, in that order.

### MIL-IT-22 — limit 101 returns all 101 entries: the method has no upper cap
- **Rules:** `get_by_item` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 entries N1 … N101, inserted in that order; Nk (k = 1 … 101) = entry, `performed_at T1 + timedelta(minutes=k)`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id, limit=101)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result)` == the ids of N101, N100, … N1, in that order.

### MIL-IT-23 — a negative limit makes the database reject the query
- **Rules:** `get_by_item` R7, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `exc.value.orig.pgcode == "2201W"`.
4. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MIL-IT-24 — a negative skip makes the database reject the query
- **Rules:** `get_by_item` R7, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `exc.value.orig.pgcode == "2201X"`.
4. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MIL-IT-25 — tied entries are each returned once, between the newer and the older entry
- **Rules:** `get_by_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = entry, `performed_at T1`.
2. N = entry, `performed_at T3`.
3. B = entry, `performed_at T2`, but `qty_after 15`, `value_after Decimal("150.00")`.
4. C = entry, `performed_at T2`, but `id HIGH_ID`, `qty_after 10`, `value_after Decimal("100.00")`.
5. A = entry, `performed_at T2`, but `qty_after 99`, `value_after Decimal("990.00")`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 5`.
2. returns: `result[0].id == N.id`.
3. returns: `result[-1].id == O.id`.
4. returns: `sorted(ids(result)[1:4]) == sorted([B.id, C.id, A.id])`.

### MIL-IT-26 — entries with the same performed_at come back by id, highest first
- **Rules:** `get_by_item` R4a
- **Kind:** bug
- **Expect:** xfail BUG-640 (non-strict)
- **Fails today on:** Then 2 (no second sort key; usually [B, C, A] today, but the physical row order can match the intended order by accident)

**Given**
1. B = entry, `performed_at T2`, but `qty_after 15`, `value_after Decimal("150.00")`.
2. C = entry, `performed_at T2`, but `id HIGH_ID`, `qty_after 10`, `value_after Decimal("100.00")`.
3. A = entry, `performed_at T2`, but `qty_after 99`, `value_after Decimal("990.00")`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == sorted([B.id, C.id, A.id])`.
2. returns: `ids(result) == [C.id, A.id, B.id]`.

### MIL-IT-27 — the query asks the database for performed_at newest first, then id highest first
- **Rules:** `get_by_item` R4a
- **Kind:** bug
- **Expect:** xfail BUG-640
- **Fails today on:** Then 4 (the clause ends at `performed_at DESC`: no second sort key)

**Given**
1. E1 = entry, `performed_at T1`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"machine_item_ledger.performed_at DESC" in order_part`.
4. statement: `"machine_item_ledger.performed_at DESC, machine_item_ledger.id DESC" in order_part`.

### MIL-IT-28 — an entry of a soft-deleted machine is returned
- **Rules:** `get_by_item` R8
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `machine_id MD.id`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. unchanged: unchanged(E1).

### MIL-IT-29 — an entry of a live machine in a soft-deleted factory is returned
- **Rules:** `get_by_item` R8
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `machine_id MF.id`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. unchanged: unchanged(E1).

### MIL-IT-30 — an entry of a removed item is returned
- **Rules:** `get_by_item` R8
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `item_id IR.id`.

**When**
- `result = dao.get_by_item(db, item_id=IR.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. unchanged: unchanged(E1).


## `MachineItemLedgerDAO.get_by_machine_and_item`

### MIL-MI-01 — an entry of another machine is not returned
- **Rules:** `get_by_machine_and_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `machine_id M2.id`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-MI-02 — an entry of another item is not returned
- **Rules:** `get_by_machine_and_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `item_id I2.id`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-MI-03 — an entry of another workspace with the same machine and item ids is not returned
- **Rules:** `get_by_machine_and_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. X9 = entry, `performed_at T5`, but `workspace_id W2.id`. (Same machine and item ids as a W1 entry, on purpose.)

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-MI-04 — the other workspace gets only its own entry
- **Rules:** `get_by_machine_and_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. X9 = entry, `performed_at T5`, but `workspace_id W2.id`. (Same machine and item ids as a W1 entry, on purpose.)

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [X9.id]`.

### MIL-MI-05 — a machine and an item that have entries, but none together, return an empty list
- **Rules:** `get_by_machine_and_item` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `item_id I2.id`.
2. E2 = entry, `performed_at T2`, but `machine_id M2.id`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIL-MI-06 — an unknown machine id returns an empty list
- **Rules:** `get_by_machine_and_item` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=MISSING, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIL-MI-07 — an unknown item id returns an empty list
- **Rules:** `get_by_machine_and_item` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIL-MI-08 — an unknown workspace id returns an empty list
- **Rules:** `get_by_machine_and_item` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### MIL-MI-09 — machine_id 0 returns an empty list
- **Rules:** `get_by_machine_and_item` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=0, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIL-MI-10 — item_id 0 returns an empty list
- **Rules:** `get_by_machine_and_item` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIL-MI-11 — returns a list of ledger rows, newest first whatever the insertion order, and writes nothing
- **Rules:** `get_by_machine_and_item` R3, R6, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `isinstance(result[0], MachineItemLedger)`.
3. returns: `ids(result) == [E2.id, E3.id, E1.id]`.
4. nothing written: nothing written.
5. unchanged: unchanged(E1).

### MIL-MI-12 — skip 1 and limit 1 return exactly the middle entry
- **Rules:** `get_by_machine_and_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E3.id]`.

### MIL-MI-13 — limit 2 returns the two newest entries
- **Rules:** `get_by_machine_and_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `ids(result) == [E2.id, E3.id]`.

### MIL-MI-14 — limit 1 returns only the newest entry
- **Rules:** `get_by_machine_and_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### MIL-MI-15 — skip one below the number of entries returns the oldest entry
- **Rules:** `get_by_machine_and_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-MI-16 — skip equal to the number of entries returns an empty list
- **Rules:** `get_by_machine_and_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id, skip=3)`.

**Then**
1. returns: `result == []`.

### MIL-MI-17 — skip past the number of entries returns an empty list
- **Rules:** `get_by_machine_and_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id, skip=4)`.

**Then**
1. returns: `result == []`.

### MIL-MI-18 — limit 0 returns an empty list
- **Rules:** `get_by_machine_and_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### MIL-MI-19 — paging counts matching entries only: newer entries left out by the filters use no place on the page
- **Rules:** `get_by_machine_and_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.
3. EX = entry, `performed_at T3`, but `machine_id M2.id`.
4. X9 = entry, `performed_at T5`, but `workspace_id W2.id`. (Same machine and item ids as a W1 entry, on purpose.)

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-MI-20 — by default at most the 100 newest of 101 entries are returned; the oldest is missing
- **Rules:** `get_by_machine_and_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 entries N1 … N101, inserted in that order; Nk (k = 1 … 101) = entry, `performed_at T1 + timedelta(minutes=k)`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result)` == the ids of N101, N100, … N2, in that order.
3. returns: `N1.id not in ids(result)`.

### MIL-MI-21 — exactly 100 entries are all returned by default
- **Rules:** `get_by_machine_and_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 100 entries N1 … N100, inserted in that order; Nk (k = 1 … 100) = entry, `performed_at T1 + timedelta(minutes=k)`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result)` == the ids of N100, N99, … N1, in that order.

### MIL-MI-22 — limit 101 returns all 101 entries: the method has no upper cap
- **Rules:** `get_by_machine_and_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 entries N1 … N101, inserted in that order; Nk (k = 1 … 101) = entry, `performed_at T1 + timedelta(minutes=k)`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id, limit=101)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result)` == the ids of N101, N100, … N1, in that order.

### MIL-MI-23 — a negative limit makes the database reject the query
- **Rules:** `get_by_machine_and_item` R4, Errors (as get_by_item)
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `exc.value.orig.pgcode == "2201W"`.
4. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MIL-MI-24 — a negative skip makes the database reject the query
- **Rules:** `get_by_machine_and_item` R4, Errors (as get_by_item)
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `exc.value.orig.pgcode == "2201X"`.
4. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MIL-MI-25 — tied entries are each returned once, between the newer and the older entry
- **Rules:** `get_by_machine_and_item` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = entry, `performed_at T1`.
2. N = entry, `performed_at T3`.
3. B = entry, `performed_at T2`, but `qty_after 15`, `value_after Decimal("150.00")`.
4. C = entry, `performed_at T2`, but `id HIGH_ID`, `qty_after 10`, `value_after Decimal("100.00")`.
5. A = entry, `performed_at T2`, but `qty_after 99`, `value_after Decimal("990.00")`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 5`.
2. returns: `result[0].id == N.id`.
3. returns: `result[-1].id == O.id`.
4. returns: `sorted(ids(result)[1:4]) == sorted([B.id, C.id, A.id])`.

### MIL-MI-26 — entries with the same performed_at come back by id, highest first
- **Rules:** `get_by_machine_and_item` R3a
- **Kind:** bug
- **Expect:** xfail BUG-640 (non-strict)
- **Fails today on:** Then 2 (no second sort key; usually [B, C, A] today, but the physical row order can match the intended order by accident)

**Given**
1. B = entry, `performed_at T2`, but `qty_after 15`, `value_after Decimal("150.00")`.
2. C = entry, `performed_at T2`, but `id HIGH_ID`, `qty_after 10`, `value_after Decimal("100.00")`.
3. A = entry, `performed_at T2`, but `qty_after 99`, `value_after Decimal("990.00")`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == sorted([B.id, C.id, A.id])`.
2. returns: `ids(result) == [C.id, A.id, B.id]`.

### MIL-MI-27 — the query asks the database for performed_at newest first, then id highest first
- **Rules:** `get_by_machine_and_item` R3a
- **Kind:** bug
- **Expect:** xfail BUG-640
- **Fails today on:** Then 4 (the clause ends at `performed_at DESC`: no second sort key)

**Given**
1. E1 = entry, `performed_at T1`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"machine_item_ledger.performed_at DESC" in order_part`.
4. statement: `"machine_item_ledger.performed_at DESC, machine_item_ledger.id DESC" in order_part`.

### MIL-MI-28 — an entry of a soft-deleted machine is returned
- **Rules:** `get_by_machine_and_item` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `machine_id MD.id`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=MD.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. unchanged: unchanged(E1).

### MIL-MI-29 — an entry of a live machine in a soft-deleted factory is returned
- **Rules:** `get_by_machine_and_item` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `machine_id MF.id`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=MF.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. unchanged: unchanged(E1).

### MIL-MI-30 — an entry of a removed item is returned
- **Rules:** `get_by_machine_and_item` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `item_id IR.id`.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=IR.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. unchanged: unchanged(E1).

### MIL-MI-31 — a pending entry stays pending and is not seen: the call writes nothing
- **Rules:** `get_by_machine_and_item` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, added with `db.add(E2)` and not flushed.

**When**
- `result = dao.get_by_machine_and_item(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. returns: `E2 in db.new` (still pending: the call flushed nothing).


## `MachineItemLedgerDAO.get_by_transaction_type`

### MIL-TT-01 — "purchase_order" finds its entry and not an entry of "purchase_return"
- **Rules:** `get_by_transaction_type` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "purchase_order"`.
2. E2 = entry, `performed_at T2`, but `transaction_type "purchase_return"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="purchase_order", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-TT-02 — "purchase_return" finds its entry and not an entry of "purchase_order"
- **Rules:** `get_by_transaction_type` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "purchase_return"`.
2. E2 = entry, `performed_at T2`, but `transaction_type "purchase_order"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="purchase_return", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-TT-03 — "manual_add" finds its entry and not an entry of "consumption"
- **Rules:** `get_by_transaction_type` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "manual_add"`.
2. E2 = entry, `performed_at T2`, but `transaction_type "consumption"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-TT-04 — "inventory_adjustment" finds its entry and not an entry of "cost_adjustment"
- **Rules:** `get_by_transaction_type` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "inventory_adjustment"`.
2. E2 = entry, `performed_at T2`, but `transaction_type "cost_adjustment"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="inventory_adjustment", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-TT-05 — "transfer_in" finds its entry and not an entry of "transfer_out"
- **Rules:** `get_by_transaction_type` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "transfer_in"`.
2. E2 = entry, `performed_at T2`, but `transaction_type "transfer_out"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-TT-06 — "transfer_out" finds its entry and not an entry of "transfer_in"
- **Rules:** `get_by_transaction_type` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "transfer_out"`.
2. E2 = entry, `performed_at T2`, but `transaction_type "transfer_in"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_out", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-TT-07 — "consumption" finds its entry and not an entry of "consumption_reversal"
- **Rules:** `get_by_transaction_type` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "consumption"`.
2. E2 = entry, `performed_at T2`, but `transaction_type "consumption_reversal"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="consumption", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-TT-08 — "consumption_reversal" finds its entry and not an entry of "consumption"
- **Rules:** `get_by_transaction_type` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "consumption_reversal"`.
2. E2 = entry, `performed_at T2`, but `transaction_type "consumption"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="consumption_reversal", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-TT-09 — "work_order_install" finds its entry and not an entry of "work_order_borrow_returned"
- **Rules:** `get_by_transaction_type` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "work_order_install"`.
2. E2 = entry, `performed_at T2`, but `transaction_type "work_order_borrow_returned"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="work_order_install", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-TT-10 — "work_order_replace_out" finds its entry and not an entry of "work_order_replace_in"
- **Rules:** `get_by_transaction_type` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "work_order_replace_out"`.
2. E2 = entry, `performed_at T2`, but `transaction_type "work_order_replace_in"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="work_order_replace_out", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-TT-11 — "work_order_replace_in" finds its entry and not an entry of "work_order_replace_out"
- **Rules:** `get_by_transaction_type` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "work_order_replace_in"`.
2. E2 = entry, `performed_at T2`, but `transaction_type "work_order_replace_out"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="work_order_replace_in", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-TT-12 — "work_order_borrow_returned" finds its entry and not an entry of "work_order_install"
- **Rules:** `get_by_transaction_type` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "work_order_borrow_returned"`.
2. E2 = entry, `performed_at T2`, but `transaction_type "work_order_install"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="work_order_borrow_returned", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-TT-13 — "damaged" finds its entry and not an entry of "consumption"
- **Rules:** `get_by_transaction_type` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "damaged"`.
2. E2 = entry, `performed_at T2`, but `transaction_type "consumption"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="damaged", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-TT-14 — "cost_adjustment" finds its entry and not an entry of "inventory_adjustment"
- **Rules:** `get_by_transaction_type` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "cost_adjustment"`.
2. E2 = entry, `performed_at T2`, but `transaction_type "inventory_adjustment"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="cost_adjustment", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-TT-15 — the type in capitals returns an empty list
- **Rules:** `get_by_transaction_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "consumption"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="CONSUMPTION", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIL-TT-16 — the type with a capital first letter returns an empty list
- **Rules:** `get_by_transaction_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "consumption"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="Consumption", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIL-TT-17 — a trailing space returns an empty list
- **Rules:** `get_by_transaction_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "consumption"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="consumption ", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIL-TT-18 — a leading space returns an empty list
- **Rules:** `get_by_transaction_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "consumption"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type=" consumption", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIL-TT-19 — a % in the type returns an empty list
- **Rules:** `get_by_transaction_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "consumption"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="consum%", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIL-TT-20 — an _ in the type returns an empty list
- **Rules:** `get_by_transaction_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "consumption"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="consu_ption", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIL-TT-21 — a prefix of the type returns an empty list
- **Rules:** `get_by_transaction_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "consumption"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="consum", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIL-TT-22 — an unknown type returns an empty list
- **Rules:** `get_by_transaction_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "consumption"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="no_such_type", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIL-TT-23 — an empty type returns an empty list and raises nothing
- **Rules:** `get_by_transaction_type` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIL-TT-24 — a type of None returns an empty list and raises nothing
- **Rules:** `get_by_transaction_type` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type=None, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIL-TT-25 — an entry of another workspace is not returned
- **Rules:** `get_by_transaction_type` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. X9 = entry, `performed_at T5`, but `workspace_id W2.id`. (Same machine and item ids as a W1 entry, on purpose.)

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-TT-26 — the other workspace gets only its own entry
- **Rules:** `get_by_transaction_type` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. X9 = entry, `performed_at T5`, but `workspace_id W2.id`. (Same machine and item ids as a W1 entry, on purpose.)

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [X9.id]`.

### MIL-TT-27 — an unknown workspace id returns an empty list
- **Rules:** `get_by_transaction_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### MIL-TT-28 — with no machine and no item, entries of every machine and item of the workspace are returned
- **Rules:** `get_by_transaction_type` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `item_id I2.id`.
3. E3 = entry, `performed_at T3`, but `machine_id M2.id`.
4. E4 = entry, `performed_at T4`, but `machine_id M2.id`, `item_id I2.id`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E4.id, E3.id, E2.id, E1.id]`.

### MIL-TT-29 — a given machine narrows to that machine, for every item
- **Rules:** `get_by_transaction_type` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `item_id I2.id`.
3. E3 = entry, `performed_at T3`, but `machine_id M2.id`.
4. E4 = entry, `performed_at T4`, but `machine_id M2.id`, `item_id I2.id`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, machine_id=M1.id)`.

**Then**
1. returns: `ids(result) == [E2.id, E1.id]`.

### MIL-TT-30 — a given item narrows to that item, on every machine
- **Rules:** `get_by_transaction_type` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `item_id I2.id`.
3. E3 = entry, `performed_at T3`, but `machine_id M2.id`.
4. E4 = entry, `performed_at T4`, but `machine_id M2.id`, `item_id I2.id`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, item_id=I1.id)`.

**Then**
1. returns: `ids(result) == [E3.id, E1.id]`.

### MIL-TT-31 — a given machine and item combine with AND
- **Rules:** `get_by_transaction_type` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `item_id I2.id`.
3. E3 = entry, `performed_at T3`, but `machine_id M2.id`.
4. E4 = entry, `performed_at T4`, but `machine_id M2.id`, `item_id I2.id`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, machine_id=M2.id, item_id=I1.id)`.

**Then**
1. returns: `ids(result) == [E3.id]`.

### MIL-TT-32 — machine and item without a common entry return an empty list
- **Rules:** `get_by_transaction_type` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `machine_id M2.id`, `item_id I2.id`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, machine_id=M1.id, item_id=I2.id)`.

**Then**
1. returns: `result == []`.

### MIL-TT-33 — machine filter and type filter combine: another type on that machine is left out
- **Rules:** `get_by_transaction_type` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `transaction_type "consumption"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, machine_id=M1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-TT-34 — machine_id 0 filters like any integer and returns an empty list
- **Rules:** `get_by_transaction_type` R4a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, machine_id=0)`.

**Then**
1. returns: `result == []`.

### MIL-TT-35 — item_id 0 filters like any integer and returns an empty list
- **Rules:** `get_by_transaction_type` R4a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, item_id=0)`.

**Then**
1. returns: `result == []`.

### MIL-TT-36 — returns a list of ledger rows, newest first whatever the insertion order, and writes nothing
- **Rules:** `get_by_transaction_type` R5, R8, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `isinstance(result[0], MachineItemLedger)`.
3. returns: `ids(result) == [E2.id, E3.id, E1.id]`.
4. nothing written: nothing written.
5. unchanged: unchanged(E1).

### MIL-TT-37 — skip 1 and limit 1 return exactly the middle entry
- **Rules:** `get_by_transaction_type` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E3.id]`.

### MIL-TT-38 — limit 2 returns the two newest entries
- **Rules:** `get_by_transaction_type` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `ids(result) == [E2.id, E3.id]`.

### MIL-TT-39 — limit 1 returns only the newest entry
- **Rules:** `get_by_transaction_type` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### MIL-TT-40 — skip one below the number of entries returns the oldest entry
- **Rules:** `get_by_transaction_type` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-TT-41 — skip equal to the number of entries returns an empty list
- **Rules:** `get_by_transaction_type` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, skip=3)`.

**Then**
1. returns: `result == []`.

### MIL-TT-42 — skip past the number of entries returns an empty list
- **Rules:** `get_by_transaction_type` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, skip=4)`.

**Then**
1. returns: `result == []`.

### MIL-TT-43 — limit 0 returns an empty list
- **Rules:** `get_by_transaction_type` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### MIL-TT-44 — paging counts matching entries only: newer entries left out by the filters use no place on the page
- **Rules:** `get_by_transaction_type` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.
3. EX = entry, `performed_at T3`, but `transaction_type "consumption"`.
4. X9 = entry, `performed_at T5`, but `workspace_id W2.id`. (Same machine and item ids as a W1 entry, on purpose.)

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-TT-45 — by default at most the 100 newest of 101 entries are returned; the oldest is missing
- **Rules:** `get_by_transaction_type` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 entries N1 … N101, inserted in that order; Nk (k = 1 … 101) = entry, `performed_at T1 + timedelta(minutes=k)`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result)` == the ids of N101, N100, … N2, in that order.
3. returns: `N1.id not in ids(result)`.

### MIL-TT-46 — exactly 100 entries are all returned by default
- **Rules:** `get_by_transaction_type` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 100 entries N1 … N100, inserted in that order; Nk (k = 1 … 100) = entry, `performed_at T1 + timedelta(minutes=k)`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result)` == the ids of N100, N99, … N1, in that order.

### MIL-TT-47 — limit 101 returns all 101 entries: the method has no upper cap
- **Rules:** `get_by_transaction_type` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 entries N1 … N101, inserted in that order; Nk (k = 1 … 101) = entry, `performed_at T1 + timedelta(minutes=k)`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, limit=101)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result)` == the ids of N101, N100, … N1, in that order.

### MIL-TT-48 — a negative limit makes the database reject the query
- **Rules:** `get_by_transaction_type` R6, Errors (as get_by_item)
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `exc.value.orig.pgcode == "2201W"`.
4. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MIL-TT-49 — a negative skip makes the database reject the query
- **Rules:** `get_by_transaction_type` R6, Errors (as get_by_item)
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `exc.value.orig.pgcode == "2201X"`.
4. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MIL-TT-50 — tied entries are each returned once, between the newer and the older entry
- **Rules:** `get_by_transaction_type` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = entry, `performed_at T1`.
2. N = entry, `performed_at T3`.
3. B = entry, `performed_at T2`, but `qty_after 15`, `value_after Decimal("150.00")`.
4. C = entry, `performed_at T2`, but `id HIGH_ID`, `qty_after 10`, `value_after Decimal("100.00")`.
5. A = entry, `performed_at T2`, but `qty_after 99`, `value_after Decimal("990.00")`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 5`.
2. returns: `result[0].id == N.id`.
3. returns: `result[-1].id == O.id`.
4. returns: `sorted(ids(result)[1:4]) == sorted([B.id, C.id, A.id])`.

### MIL-TT-51 — entries with the same performed_at come back by id, highest first
- **Rules:** `get_by_transaction_type` R5a
- **Kind:** bug
- **Expect:** xfail BUG-640 (non-strict)
- **Fails today on:** Then 2 (no second sort key; usually [B, C, A] today, but the physical row order can match the intended order by accident)

**Given**
1. B = entry, `performed_at T2`, but `qty_after 15`, `value_after Decimal("150.00")`.
2. C = entry, `performed_at T2`, but `id HIGH_ID`, `qty_after 10`, `value_after Decimal("100.00")`.
3. A = entry, `performed_at T2`, but `qty_after 99`, `value_after Decimal("990.00")`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == sorted([B.id, C.id, A.id])`.
2. returns: `ids(result) == [C.id, A.id, B.id]`.

### MIL-TT-52 — the query asks the database for performed_at newest first, then id highest first
- **Rules:** `get_by_transaction_type` R5a
- **Kind:** bug
- **Expect:** xfail BUG-640
- **Fails today on:** Then 4 (the clause ends at `performed_at DESC`: no second sort key)

**Given**
1. E1 = entry, `performed_at T1`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"machine_item_ledger.performed_at DESC" in order_part`.
4. statement: `"machine_item_ledger.performed_at DESC, machine_item_ledger.id DESC" in order_part`.

### MIL-TT-53 — an entry of a soft-deleted machine is returned with no machine filter
- **Rules:** `get_by_transaction_type` R7
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `machine_id MD.id`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. unchanged: unchanged(E1).

### MIL-TT-54 — an entry of a soft-deleted machine is returned with that machine as filter
- **Rules:** `get_by_transaction_type` R7
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `machine_id MD.id`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, machine_id=MD.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. unchanged: unchanged(E1).

### MIL-TT-55 — an entry of a live machine in a soft-deleted factory is returned
- **Rules:** `get_by_transaction_type` R7
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `machine_id MF.id`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, machine_id=MF.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. unchanged: unchanged(E1).

### MIL-TT-56 — an entry of a removed item is returned with no item filter
- **Rules:** `get_by_transaction_type` R7
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `item_id IR.id`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. unchanged: unchanged(E1).

### MIL-TT-57 — an entry of a removed item is returned with that item as filter
- **Rules:** `get_by_transaction_type` R7
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `item_id IR.id`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, item_id=IR.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. unchanged: unchanged(E1).

### MIL-TT-58 — a pending entry stays pending and is not seen: the call writes nothing
- **Rules:** `get_by_transaction_type` R8
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, added with `db.add(E2)` and not flushed.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. returns: `E2 in db.new` (still pending: the call flushed nothing).


## `MachineItemLedgerDAO.get_by_date_range`

### MIL-DR-01 — both bounds are inclusive: range T1 to T3 returns all three entries
- **Rules:** `get_by_date_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T3)`.

**Then**
1. returns: `ids(result) == [E2.id, E3.id, E1.id]`.

### MIL-DR-02 — bounds one microsecond inside keep only the middle entry
- **Rules:** `get_by_date_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=datetime(2026, 1, 1, 9, 0, 0, 1), end_date=datetime(2026, 1, 1, 10, 59, 59, 999999))`.

**Then**
1. returns: `ids(result) == [E3.id]`.

### MIL-DR-03 — start exactly at the entry keeps it
- **Rules:** `get_by_date_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T2, end_date=T5)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### MIL-DR-04 — start one microsecond after the entry leaves it out
- **Rules:** `get_by_date_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=datetime(2026, 1, 1, 10, 0, 0, 1), end_date=T5)`.

**Then**
1. returns: `result == []`.

### MIL-DR-05 — end exactly at the entry keeps it
- **Rules:** `get_by_date_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E2 = entry, `performed_at T2`.
2. E3 = entry, `performed_at T3`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T2)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### MIL-DR-06 — end one microsecond before the entry leaves it out
- **Rules:** `get_by_date_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=datetime(2026, 1, 1, 9, 59, 59, 999999))`.

**Then**
1. returns: `result == []`.

### MIL-DR-07 — a midnight end date stays exact at the DAO: that day's entry is left out
- **Rules:** `get_by_date_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at datetime(2026, 9, 29, 10, 0, 0)`.
2. E2 = entry, `performed_at datetime(2026, 9, 30, 10, 0, 0)`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=datetime(2026, 9, 29, 0, 0, 0), end_date=datetime(2026, 9, 30, 0, 0, 0))`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-DR-08 — an end at the last microsecond of the day keeps that day's entry
- **Rules:** `get_by_date_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at datetime(2026, 9, 29, 10, 0, 0)`.
2. E2 = entry, `performed_at datetime(2026, 9, 30, 10, 0, 0)`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=datetime(2026, 9, 29, 0, 0, 0), end_date=datetime(2026, 9, 30, 23, 59, 59, 999999))`.

**Then**
1. returns: `ids(result) == [E2.id, E1.id]`.

### MIL-DR-09 — equal bounds return exactly the entry at that instant
- **Rules:** `get_by_date_range` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T2, end_date=T2)`.

**Then**
1. returns: `ids(result) == [E3.id]`.

### MIL-DR-10 — equal bounds at an instant without an entry return an empty list
- **Rules:** `get_by_date_range` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=datetime(2026, 1, 1, 9, 30, 0, 0), end_date=datetime(2026, 1, 1, 9, 30, 0, 0))`.

**Then**
1. returns: `result == []`.

### MIL-DR-11 — a start later than the end returns an empty list and raises nothing
- **Rules:** `get_by_date_range` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T3, end_date=T1)`.

**Then**
1. returns: `result == []`.

### MIL-DR-12 — naive bounds are compared as stored UTC under the session zone America/New_York
- **Rules:** `get_by_date_range` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T4`.
2. `db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=datetime(2026, 1, 1, 11, 30, 0, 0), end_date=datetime(2026, 1, 1, 12, 30, 0, 0))`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-DR-13 — naive bounds are compared as stored UTC under the session zone Asia/Dhaka
- **Rules:** `get_by_date_range` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T4`.
2. `db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=datetime(2026, 1, 1, 11, 30, 0, 0), end_date=datetime(2026, 1, 1, 12, 30, 0, 0))`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-DR-14 — naive bounds are compared as stored UTC under the session zone UTC
- **Rules:** `get_by_date_range` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T4`.
2. `db.execute(text("SET LOCAL TIME ZONE 'UTC'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=datetime(2026, 1, 1, 11, 30, 0, 0), end_date=datetime(2026, 1, 1, 12, 30, 0, 0))`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-DR-15 — naive bounds that miss the stored time return an empty list under a shifted session zone
- **Rules:** `get_by_date_range` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T4`.
2. `db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=datetime(2026, 1, 1, 16, 30, 0, 0), end_date=datetime(2026, 1, 1, 17, 30, 0, 0))`.

**Then**
1. returns: `result == []`.

### MIL-DR-16 — aware bounds in UTC find the entry under the session zone America/New_York
- **Rules:** `get_by_date_range` R3a
- **Kind:** bug
- **Expect:** xfail BUG-992
- **Fails today on:** Then 1 (the stored value is read in the session zone, so `result == []` under America/New_York)

**Given**
1. E1 = entry, `performed_at T4`.
2. `db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=Z1130, end_date=Z1230)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-DR-17 — aware bounds in UTC find the entry under the session zone Asia/Dhaka
- **Rules:** `get_by_date_range` R3a
- **Kind:** bug
- **Expect:** xfail BUG-992
- **Fails today on:** Then 1 (the stored value is read in the session zone, so `result == []` under Asia/Dhaka)

**Given**
1. E1 = entry, `performed_at T4`.
2. `db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=Z1130, end_date=Z1230)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-DR-18 — aware bounds with an offset find the entry under a session zone of America/New_York
- **Rules:** `get_by_date_range` R3a
- **Kind:** bug
- **Expect:** xfail BUG-992
- **Fails today on:** Then 1 (the stored value is read in the session zone, so `result == []` under America/New_York)

**Given**
1. E1 = entry, `performed_at T4`.
2. `db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=P1730, end_date=P1830)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-DR-19 — aware bounds do not catch an entry outside the UTC window under a shifted session zone
- **Rules:** `get_by_date_range` R3a
- **Kind:** bug
- **Expect:** xfail BUG-992
- **Fails today on:** Then 1 (07:00 read as New York time is 12:00 UTC: E2 comes back and E1 does not)

**Given**
1. E1 = entry, `performed_at T4`.
2. E2 = entry, `performed_at datetime(2026, 1, 1, 7, 0, 0, 0)`.
3. `db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=Z1130, end_date=Z1230)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-DR-20 — control: aware UTC bounds find the entry under the session zone UTC
- **Rules:** `get_by_date_range` R3a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T4`.
2. `db.execute(text("SET LOCAL TIME ZONE 'UTC'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=Z1130, end_date=Z1230)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-DR-21 — control: aware bounds with an offset are converted, not cut off, under the session zone UTC
- **Rules:** `get_by_date_range` R3a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T4`.
2. `db.execute(text("SET LOCAL TIME ZONE 'UTC'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=P1730, end_date=P1830)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-DR-22 — control: aware UTC bounds leave out an entry outside the window under the session zone UTC
- **Rules:** `get_by_date_range` R3a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T5`.
2. `db.execute(text("SET LOCAL TIME ZONE 'UTC'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=Z1130, end_date=Z1230)`.

**Then**
1. returns: `result == []`.

### MIL-DR-23 — start_date None raises ArgumentError before any query is sent
- **Rules:** `get_by_date_range` R4, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=None, end_date=T3)`.

**Then**
1. raises: `ArgumentError`.
2. raises: `str(exc.value).startswith("Only '=', '!=', 'is_()', 'is_not()', 'is_distinct_from()', 'is_not_distinct_from()' operators can be used with None/True/False")`.
3. statement: `statements == []`.
4. nothing written: nothing written.

### MIL-DR-24 — end_date None raises ArgumentError before any query is sent
- **Rules:** `get_by_date_range` R4, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=None)`.

**Then**
1. raises: `ArgumentError`.
2. raises: `str(exc.value).startswith("Only '=', '!=', 'is_()', 'is_not()', 'is_distinct_from()', 'is_not_distinct_from()' operators can be used with None/True/False")`.
3. statement: `statements == []`.
4. nothing written: nothing written.

### MIL-DR-25 — an entry of another workspace inside the window is not returned
- **Rules:** `get_by_date_range` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. X9 = entry, `performed_at T5`, but `workspace_id W2.id`. (Same machine and item ids as a W1 entry, on purpose.)

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-DR-26 — the other workspace gets only its own entry
- **Rules:** `get_by_date_range` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. X9 = entry, `performed_at T5`, but `workspace_id W2.id`. (Same machine and item ids as a W1 entry, on purpose.)

**When**
- `result = dao.get_by_date_range(db, workspace_id=W2.id, start_date=T1, end_date=T5)`.

**Then**
1. returns: `ids(result) == [X9.id]`.

### MIL-DR-27 — an unknown workspace id returns an empty list
- **Rules:** `get_by_date_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=MISSING, start_date=T1, end_date=T5)`.

**Then**
1. returns: `result == []`.

### MIL-DR-28 — with no machine and no item, entries of every machine and item in the window are returned
- **Rules:** `get_by_date_range` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `item_id I2.id`.
3. E3 = entry, `performed_at T3`, but `machine_id M2.id`.
4. E4 = entry, `performed_at T4`, but `machine_id M2.id`, `item_id I2.id`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5)`.

**Then**
1. returns: `ids(result) == [E4.id, E3.id, E2.id, E1.id]`.

### MIL-DR-29 — a given machine narrows to that machine, for every item
- **Rules:** `get_by_date_range` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `item_id I2.id`.
3. E3 = entry, `performed_at T3`, but `machine_id M2.id`.
4. E4 = entry, `performed_at T4`, but `machine_id M2.id`, `item_id I2.id`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5, machine_id=M1.id)`.

**Then**
1. returns: `ids(result) == [E2.id, E1.id]`.

### MIL-DR-30 — a given item narrows to that item, on every machine
- **Rules:** `get_by_date_range` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `item_id I2.id`.
3. E3 = entry, `performed_at T3`, but `machine_id M2.id`.
4. E4 = entry, `performed_at T4`, but `machine_id M2.id`, `item_id I2.id`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5, item_id=I1.id)`.

**Then**
1. returns: `ids(result) == [E3.id, E1.id]`.

### MIL-DR-31 — a given machine and item combine with AND
- **Rules:** `get_by_date_range` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `item_id I2.id`.
3. E3 = entry, `performed_at T3`, but `machine_id M2.id`.
4. E4 = entry, `performed_at T4`, but `machine_id M2.id`, `item_id I2.id`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5, machine_id=M2.id, item_id=I1.id)`.

**Then**
1. returns: `ids(result) == [E3.id]`.

### MIL-DR-32 — the machine filter does not widen the window: that machine's entry outside it is left out
- **Rules:** `get_by_date_range` R6, R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T5`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T3, machine_id=M1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-DR-33 — machine_id 0 filters like any integer and returns an empty list
- **Rules:** `get_by_date_range` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5, machine_id=0)`.

**Then**
1. returns: `result == []`.

### MIL-DR-34 — item_id 0 filters like any integer and returns an empty list
- **Rules:** `get_by_date_range` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5, item_id=0)`.

**Then**
1. returns: `result == []`.

### MIL-DR-35 — returns a list of ledger rows, newest first whatever the insertion order, and writes nothing
- **Rules:** `get_by_date_range` R5, R8, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `isinstance(result[0], MachineItemLedger)`.
3. returns: `ids(result) == [E2.id, E3.id, E1.id]`.
4. nothing written: nothing written.
5. unchanged: unchanged(E1).

### MIL-DR-36 — skip 1 and limit 1 return exactly the middle entry
- **Rules:** `get_by_date_range` R6a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E3.id]`.

### MIL-DR-37 — limit 2 returns the two newest entries
- **Rules:** `get_by_date_range` R6a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5, limit=2)`.

**Then**
1. returns: `ids(result) == [E2.id, E3.id]`.

### MIL-DR-38 — limit 1 returns only the newest entry
- **Rules:** `get_by_date_range` R6a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5, limit=1)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### MIL-DR-39 — skip one below the number of entries returns the oldest entry
- **Rules:** `get_by_date_range` R6a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5, skip=2)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-DR-40 — skip equal to the number of entries returns an empty list
- **Rules:** `get_by_date_range` R6a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5, skip=3)`.

**Then**
1. returns: `result == []`.

### MIL-DR-41 — skip past the number of entries returns an empty list
- **Rules:** `get_by_date_range` R6a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5, skip=4)`.

**Then**
1. returns: `result == []`.

### MIL-DR-42 — limit 0 returns an empty list
- **Rules:** `get_by_date_range` R6a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5, limit=0)`.

**Then**
1. returns: `result == []`.

### MIL-DR-43 — paging counts matching entries only: newer entries left out by the filters use no place on the page
- **Rules:** `get_by_date_range` R6a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.
3. EX = entry, `performed_at T4`.
4. X9 = entry, `performed_at T5`, but `workspace_id W2.id`. (Same machine and item ids as a W1 entry, on purpose.)

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T3, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-DR-44 — by default at most the 100 newest of 101 entries are returned; the oldest is missing
- **Rules:** `get_by_date_range` R6a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 entries N1 … N101, inserted in that order; Nk (k = 1 … 101) = entry, `performed_at T1 + timedelta(minutes=k)`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result)` == the ids of N101, N100, … N2, in that order.
3. returns: `N1.id not in ids(result)`.

### MIL-DR-45 — exactly 100 entries are all returned by default
- **Rules:** `get_by_date_range` R6a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 100 entries N1 … N100, inserted in that order; Nk (k = 1 … 100) = entry, `performed_at T1 + timedelta(minutes=k)`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result)` == the ids of N100, N99, … N1, in that order.

### MIL-DR-46 — limit 101 returns all 101 entries: the method has no upper cap
- **Rules:** `get_by_date_range` R6a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 entries N1 … N101, inserted in that order; Nk (k = 1 … 101) = entry, `performed_at T1 + timedelta(minutes=k)`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5, limit=101)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result)` == the ids of N101, N100, … N1, in that order.

### MIL-DR-47 — a negative limit makes the database reject the query
- **Rules:** `get_by_date_range` R6a, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `exc.value.orig.pgcode == "2201W"`.
4. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MIL-DR-48 — a negative skip makes the database reject the query
- **Rules:** `get_by_date_range` R6a, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `exc.value.orig.pgcode == "2201X"`.
4. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MIL-DR-49 — tied entries are each returned once, between the newer and the older entry
- **Rules:** `get_by_date_range` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = entry, `performed_at T1`.
2. N = entry, `performed_at T3`.
3. B = entry, `performed_at T2`, but `qty_after 15`, `value_after Decimal("150.00")`.
4. C = entry, `performed_at T2`, but `id HIGH_ID`, `qty_after 10`, `value_after Decimal("100.00")`.
5. A = entry, `performed_at T2`, but `qty_after 99`, `value_after Decimal("990.00")`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5)`.

**Then**
1. returns: `len(result) == 5`.
2. returns: `result[0].id == N.id`.
3. returns: `result[-1].id == O.id`.
4. returns: `sorted(ids(result)[1:4]) == sorted([B.id, C.id, A.id])`.

### MIL-DR-50 — entries with the same performed_at come back by id, highest first
- **Rules:** `get_by_date_range` R5a
- **Kind:** bug
- **Expect:** xfail BUG-640 (non-strict)
- **Fails today on:** Then 2 (no second sort key; usually [B, C, A] today, but the physical row order can match the intended order by accident)

**Given**
1. B = entry, `performed_at T2`, but `qty_after 15`, `value_after Decimal("150.00")`.
2. C = entry, `performed_at T2`, but `id HIGH_ID`, `qty_after 10`, `value_after Decimal("100.00")`.
3. A = entry, `performed_at T2`, but `qty_after 99`, `value_after Decimal("990.00")`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5)`.

**Then**
1. returns: `sorted(ids(result)) == sorted([B.id, C.id, A.id])`.
2. returns: `ids(result) == [C.id, A.id, B.id]`.

### MIL-DR-51 — the query asks the database for performed_at newest first, then id highest first
- **Rules:** `get_by_date_range` R5a
- **Kind:** bug
- **Expect:** xfail BUG-640
- **Fails today on:** Then 4 (the clause ends at `performed_at DESC`: no second sort key)

**Given**
1. E1 = entry, `performed_at T1`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"machine_item_ledger.performed_at DESC" in order_part`.
4. statement: `"machine_item_ledger.performed_at DESC, machine_item_ledger.id DESC" in order_part`.

### MIL-DR-52 — an entry of a soft-deleted machine is returned with no machine filter
- **Rules:** `get_by_date_range` R7
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `machine_id MD.id`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. unchanged: unchanged(E1).

### MIL-DR-53 — an entry of a soft-deleted machine is returned with that machine as filter
- **Rules:** `get_by_date_range` R7
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `machine_id MD.id`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5, machine_id=MD.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. unchanged: unchanged(E1).

### MIL-DR-54 — an entry of a live machine in a soft-deleted factory is returned
- **Rules:** `get_by_date_range` R7
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `machine_id MF.id`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5, machine_id=MF.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. unchanged: unchanged(E1).

### MIL-DR-55 — an entry of a removed item is returned with no item filter
- **Rules:** `get_by_date_range` R7
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `item_id IR.id`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. unchanged: unchanged(E1).

### MIL-DR-56 — an entry of a removed item is returned with that item as filter
- **Rules:** `get_by_date_range` R7
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `item_id IR.id`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5, item_id=IR.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. unchanged: unchanged(E1).

### MIL-DR-57 — aware bounds keep only the entry in the UTC window under the session zone Asia/Dhaka
- **Rules:** `get_by_date_range` R3a
- **Kind:** bug
- **Expect:** xfail BUG-992
- **Fails today on:** Then 1 (the window moves with the session zone: E3 at 18:00 comes back and E2 goes missing)

**Given**
1. E1 = entry, `performed_at datetime(2026, 1, 1, 7, 0, 0)`.
2. E2 = entry, `performed_at T4`.
3. E3 = entry, `performed_at datetime(2026, 1, 1, 18, 0, 0)`.
4. `db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=Z1130, end_date=Z1230)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### MIL-DR-58 — aware start, naive end: the naive bound stays as given under America/New_York
- **Rules:** `get_by_date_range` R3a
- **Kind:** bug
- **Expect:** xfail BUG-992
- **Fails today on:** Then 1 (the aware start is compared in the session zone: E1 at 07:00 comes back too, giving [E2.id, E1.id])

**Given**
1. E1 = entry, `performed_at datetime(2026, 1, 1, 7, 0, 0)`.
2. E2 = entry, `performed_at T4`.
3. E3 = entry, `performed_at datetime(2026, 1, 1, 18, 0, 0)`.
4. `db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=Z1130, end_date=datetime(2026, 1, 1, 12, 30, 0, 0))`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### MIL-DR-59 — naive start, aware end: the naive bound stays as given under America/New_York
- **Rules:** `get_by_date_range` R3a
- **Kind:** bug
- **Expect:** xfail BUG-992
- **Fails today on:** Then 1 (the aware end is compared in the session zone: 12:00 read as New York time is after 12:30 UTC, so `result == []`)

**Given**
1. E1 = entry, `performed_at datetime(2026, 1, 1, 7, 0, 0)`.
2. E2 = entry, `performed_at T4`.
3. E3 = entry, `performed_at datetime(2026, 1, 1, 18, 0, 0)`.
4. `db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=datetime(2026, 1, 1, 11, 30, 0, 0), end_date=Z1230)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### MIL-DR-60 — control: aware bounds keep only the entry in the UTC window under the session zone UTC
- **Rules:** `get_by_date_range` R3a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at datetime(2026, 1, 1, 7, 0, 0)`.
2. E2 = entry, `performed_at T4`.
3. E3 = entry, `performed_at datetime(2026, 1, 1, 18, 0, 0)`.
4. `db.execute(text("SET LOCAL TIME ZONE 'UTC'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=Z1130, end_date=Z1230)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### MIL-DR-61 — control: an aware start with a naive end keeps only the entry in the window under the session zone UTC
- **Rules:** `get_by_date_range` R3a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at datetime(2026, 1, 1, 7, 0, 0)`.
2. E2 = entry, `performed_at T4`.
3. E3 = entry, `performed_at datetime(2026, 1, 1, 18, 0, 0)`.
4. `db.execute(text("SET LOCAL TIME ZONE 'UTC'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=Z1130, end_date=datetime(2026, 1, 1, 12, 30, 0, 0))`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### MIL-DR-62 — a pending entry stays pending and is not seen: the call writes nothing
- **Rules:** `get_by_date_range` R8
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, added with `db.add(E2)` and not flushed.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T2)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. returns: `E2 in db.new` (still pending: the call flushed nothing).


## `MachineItemLedgerDAO.get_by_machine`

### MIL-MA-01 — entries of every item and transaction type of the machine are returned
- **Rules:** `get_by_machine` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `item_id I2.id`.
3. E3 = entry, `performed_at T3`, but `transaction_type "consumption"`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E3.id, E2.id, E1.id]`.

### MIL-MA-02 — an entry of another machine is not returned
- **Rules:** `get_by_machine` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `machine_id M2.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-MA-03 — an entry with that machine id in another workspace is not returned
- **Rules:** `get_by_machine` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. X9 = entry, `performed_at T5`, but `workspace_id W2.id`. (Same machine and item ids as a W1 entry, on purpose.)

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-MA-04 — the other workspace gets only its own entry
- **Rules:** `get_by_machine` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. X9 = entry, `performed_at T5`, but `workspace_id W2.id`. (Same machine and item ids as a W1 entry, on purpose.)

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [X9.id]`.

### MIL-MA-05 — an unknown workspace id returns an empty list
- **Rules:** `get_by_machine` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### MIL-MA-06 — machine_id 0 returns an empty list
- **Rules:** `get_by_machine` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_machine(db, machine_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIL-MA-07 — an unknown machine id returns an empty list
- **Rules:** `get_by_machine` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_machine(db, machine_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIL-MA-08 — a machine with no entries returns an empty list
- **Rules:** `get_by_machine` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_machine(db, machine_id=M2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIL-MA-09 — returns a list of ledger rows, newest first whatever the insertion order, and writes nothing
- **Rules:** `get_by_machine` R3, R6, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `isinstance(result[0], MachineItemLedger)`.
3. returns: `ids(result) == [E2.id, E3.id, E1.id]`.
4. nothing written: nothing written.
5. unchanged: unchanged(E1).

### MIL-MA-10 — skip 1 and limit 1 return exactly the middle entry
- **Rules:** `get_by_machine` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E3.id]`.

### MIL-MA-11 — limit 2 returns the two newest entries
- **Rules:** `get_by_machine` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `ids(result) == [E2.id, E3.id]`.

### MIL-MA-12 — limit 1 returns only the newest entry
- **Rules:** `get_by_machine` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### MIL-MA-13 — skip one below the number of entries returns the oldest entry
- **Rules:** `get_by_machine` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-MA-14 — skip equal to the number of entries returns an empty list
- **Rules:** `get_by_machine` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, skip=3)`.

**Then**
1. returns: `result == []`.

### MIL-MA-15 — skip past the number of entries returns an empty list
- **Rules:** `get_by_machine` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, skip=4)`.

**Then**
1. returns: `result == []`.

### MIL-MA-16 — limit 0 returns an empty list
- **Rules:** `get_by_machine` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### MIL-MA-17 — paging counts matching entries only: newer entries left out by the filters use no place on the page
- **Rules:** `get_by_machine` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.
3. EX = entry, `performed_at T3`, but `machine_id M2.id`.
4. X9 = entry, `performed_at T5`, but `workspace_id W2.id`. (Same machine and item ids as a W1 entry, on purpose.)

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-MA-18 — by default at most the 100 newest of 101 entries are returned; the oldest is missing
- **Rules:** `get_by_machine` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 entries N1 … N101, inserted in that order; Nk (k = 1 … 101) = entry, `performed_at T1 + timedelta(minutes=k)`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result)` == the ids of N101, N100, … N2, in that order.
3. returns: `N1.id not in ids(result)`.

### MIL-MA-19 — exactly 100 entries are all returned by default
- **Rules:** `get_by_machine` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 100 entries N1 … N100, inserted in that order; Nk (k = 1 … 100) = entry, `performed_at T1 + timedelta(minutes=k)`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result)` == the ids of N100, N99, … N1, in that order.

### MIL-MA-20 — limit 101 returns all 101 entries: the method has no upper cap
- **Rules:** `get_by_machine` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 entries N1 … N101, inserted in that order; Nk (k = 1 … 101) = entry, `performed_at T1 + timedelta(minutes=k)`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, limit=101)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result)` == the ids of N101, N100, … N1, in that order.

### MIL-MA-21 — a negative limit makes the database reject the query
- **Rules:** `get_by_machine` R4, Errors (as get_by_item)
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `exc.value.orig.pgcode == "2201W"`.
4. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MIL-MA-22 — a negative skip makes the database reject the query
- **Rules:** `get_by_machine` R4, Errors (as get_by_item)
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `exc.value.orig.pgcode == "2201X"`.
4. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MIL-MA-23 — tied entries are each returned once, between the newer and the older entry
- **Rules:** `get_by_machine` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = entry, `performed_at T1`.
2. N = entry, `performed_at T3`.
3. B = entry, `performed_at T2`, but `qty_after 15`, `value_after Decimal("150.00")`.
4. C = entry, `performed_at T2`, but `id HIGH_ID`, `qty_after 10`, `value_after Decimal("100.00")`.
5. A = entry, `performed_at T2`, but `qty_after 99`, `value_after Decimal("990.00")`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 5`.
2. returns: `result[0].id == N.id`.
3. returns: `result[-1].id == O.id`.
4. returns: `sorted(ids(result)[1:4]) == sorted([B.id, C.id, A.id])`.

### MIL-MA-24 — entries with the same performed_at come back by id, highest first
- **Rules:** `get_by_machine` R3a
- **Kind:** bug
- **Expect:** xfail BUG-640 (non-strict)
- **Fails today on:** Then 2 (no second sort key; usually [B, C, A] today, but the physical row order can match the intended order by accident)

**Given**
1. B = entry, `performed_at T2`, but `qty_after 15`, `value_after Decimal("150.00")`.
2. C = entry, `performed_at T2`, but `id HIGH_ID`, `qty_after 10`, `value_after Decimal("100.00")`.
3. A = entry, `performed_at T2`, but `qty_after 99`, `value_after Decimal("990.00")`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == sorted([B.id, C.id, A.id])`.
2. returns: `ids(result) == [C.id, A.id, B.id]`.

### MIL-MA-25 — the query asks the database for performed_at newest first, then id highest first
- **Rules:** `get_by_machine` R3a
- **Kind:** bug
- **Expect:** xfail BUG-640
- **Fails today on:** Then 4 (the clause ends at `performed_at DESC`: no second sort key)

**Given**
1. E1 = entry, `performed_at T1`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"machine_item_ledger.performed_at DESC" in order_part`.
4. statement: `"machine_item_ledger.performed_at DESC, machine_item_ledger.id DESC" in order_part`.

### MIL-MA-26 — an entry of a soft-deleted machine is returned
- **Rules:** `get_by_machine` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `machine_id MD.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=MD.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. unchanged: unchanged(E1).

### MIL-MA-27 — an entry of a live machine in a soft-deleted factory is returned
- **Rules:** `get_by_machine` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `machine_id MF.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=MF.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. unchanged: unchanged(E1).

### MIL-MA-28 — an entry of a removed item is returned
- **Rules:** `get_by_machine` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `item_id IR.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. unchanged: unchanged(E1).

### MIL-MA-29 — a pending entry stays pending and is not seen: the call writes nothing
- **Rules:** `get_by_machine` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, added with `db.add(E2)` and not flushed.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. returns: `E2 in db.new` (still pending: the call flushed nothing).


## `MachineItemLedgerDAO.calculate_balance`

### MIL-BAL-01 — with no entry the result is the tuple (0, 0.00)
- **Rules:** `calculate_balance` R1, Returns
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No entry exists for M1 and I1 in W1.

**When**
- `result = dao.calculate_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, tuple)`.
2. returns: `result == (0, Decimal("0.00"))`.
3. returns: `str(result[1]) == "0.00"`.

### MIL-BAL-02 — the latest entry's quantity and value are returned; nothing is summed
- **Rules:** `calculate_balance` R2, R7, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 30`, `value_after Decimal("210.00")`.
2. E2 = entry, `performed_at T3`, but `qty_after 20`, `value_after Decimal("120.00")`.
3. E3 = entry, `performed_at T2`, but `qty_after 10`, `value_after Decimal("40.00")`.

**When**
- `result = dao.calculate_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, tuple)`.
2. returns: `isinstance(result[0], int)`.
3. returns: `isinstance(result[1], Decimal)`.
4. returns: `result == (20, Decimal("120.00"))`.
5. nothing written: nothing written.
6. unchanged: unchanged(E2).

### MIL-BAL-03 — the latest entry wins when it has the lowest id
- **Rules:** `calculate_balance` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T3`, but `qty_after 20`, `value_after Decimal("120.00")`.
2. E2 = entry, `performed_at T1`, but `qty_after 30`, `value_after Decimal("210.00")`.

**When**
- `result = dao.calculate_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (20, Decimal("120.00"))`.

### MIL-BAL-04 — the latest entry wins when it has the highest id
- **Rules:** `calculate_balance` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 30`, `value_after Decimal("210.00")`.
2. E2 = entry, `performed_at T3`, but `qty_after 20`, `value_after Decimal("120.00")`.

**When**
- `result = dao.calculate_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (20, Decimal("120.00"))`.

### MIL-BAL-05 — negative stored values are returned as they are
- **Rules:** `calculate_balance` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after -3`, `value_after Decimal("-12.50")`.

**When**
- `result = dao.calculate_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (-3, Decimal("-12.50"))`.

### MIL-BAL-06 — an emptied machine: a latest quantity of 0 is returned, not treated as no entry
- **Rules:** `calculate_balance` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 30`, `value_after Decimal("210.00")`.
2. E2 = entry, `performed_at T2`, but `qty_after 0`, `value_after Decimal("7.00")`.

**When**
- `result = dao.calculate_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (0, Decimal("7.00"))`.

### MIL-BAL-07 — an empty value_after gives 0.00 and keeps qty_after
- **Rules:** `calculate_balance` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 5`, `value_after None`.

**When**
- `result = dao.calculate_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (5, Decimal("0.00"))`.
2. returns: `isinstance(result[1], Decimal)`.

### MIL-BAL-08 — a stored value_after of 0 gives 0.00 and keeps qty_after
- **Rules:** `calculate_balance` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 5`, `value_after Decimal("0")`.

**When**
- `result = dao.calculate_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (5, Decimal("0.00"))`.

### MIL-BAL-09 — an empty value on the latest entry does not fall back to an earlier entry
- **Rules:** `calculate_balance` R3, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 30`, `value_after Decimal("210.00")`.
2. E2 = entry, `performed_at T2`, but `qty_after 5`, `value_after None`.

**When**
- `result = dao.calculate_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (5, Decimal("0.00"))`.

### MIL-BAL-10 — tied entries: the result is the figures of one of them, never of an older entry
- **Rules:** `calculate_balance` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = entry, `performed_at T1`, but `qty_after 1`, `value_after Decimal("1.00")`.
2. B = entry, `performed_at T2`, but `qty_after 15`, `value_after Decimal("150.00")`.
3. C = entry, `performed_at T2`, but `id HIGH_ID`, `qty_after 10`, `value_after Decimal("100.00")`.
4. A = entry, `performed_at T2`, but `qty_after 99`, `value_after Decimal("990.00")`.

**When**
- `result = dao.calculate_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result in [(15, Decimal("150.00")), (10, Decimal("100.00")), (99, Decimal("990.00"))]`.

### MIL-BAL-11 — among tied entries the greatest id decides the balance
- **Rules:** `calculate_balance` R4
- **Kind:** bug
- **Expect:** xfail BUG-641 (non-strict)
- **Fails today on:** Then 2 (no second sort key; usually B decides, giving (15, 150.00), but the physical row order can match the intended result by accident)

**Given**
1. B = entry, `performed_at T2`, but `qty_after 15`, `value_after Decimal("150.00")`.
2. C = entry, `performed_at T2`, but `id HIGH_ID`, `qty_after 10`, `value_after Decimal("100.00")`.
3. A = entry, `performed_at T2`, but `qty_after 99`, `value_after Decimal("990.00")`.

**When**
- `result = dao.calculate_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result in [(15, Decimal("150.00")), (10, Decimal("100.00")), (99, Decimal("990.00"))]`.
2. returns: `result == (10, Decimal("100.00"))`.

### MIL-BAL-12 — the query asks the database for performed_at newest first, then id highest first
- **Rules:** `calculate_balance` R4
- **Kind:** bug
- **Expect:** xfail BUG-641
- **Fails today on:** Then 4 (the clause ends at `performed_at DESC`: no second sort key)

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 5`, `value_after Decimal("10.00")`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.calculate_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (5, Decimal("10.00"))`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"machine_item_ledger.performed_at DESC" in order_part`.
4. statement: `"machine_item_ledger.performed_at DESC, machine_item_ledger.id DESC" in order_part`.

### MIL-BAL-13 — a newer entry of another machine does not change the result
- **Rules:** `calculate_balance` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 5`, `value_after Decimal("10.00")`.
2. E2 = entry, `performed_at T2`, but `machine_id M2.id`, `qty_after 9`, `value_after Decimal("99.00")`.

**When**
- `result = dao.calculate_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (5, Decimal("10.00"))`.

### MIL-BAL-14 — when only an entry of another machine exists the result is (0, 0.00)
- **Rules:** `calculate_balance` R5, R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E2 = entry, `performed_at T2`, but `machine_id M2.id`, `qty_after 9`, `value_after Decimal("99.00")`.

**When**
- `result = dao.calculate_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (0, Decimal("0.00"))`.

### MIL-BAL-15 — a newer entry of another item does not change the result
- **Rules:** `calculate_balance` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 5`, `value_after Decimal("10.00")`.
2. E2 = entry, `performed_at T2`, but `item_id I2.id`, `qty_after 9`, `value_after Decimal("99.00")`.

**When**
- `result = dao.calculate_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (5, Decimal("10.00"))`.

### MIL-BAL-16 — when only an entry of another item exists the result is (0, 0.00)
- **Rules:** `calculate_balance` R5, R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E2 = entry, `performed_at T2`, but `item_id I2.id`, `qty_after 9`, `value_after Decimal("99.00")`.

**When**
- `result = dao.calculate_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (0, Decimal("0.00"))`.

### MIL-BAL-17 — a newer entry of another workspace does not change the result
- **Rules:** `calculate_balance` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 5`, `value_after Decimal("10.00")`.
2. E2 = entry, `performed_at T2`, but `workspace_id W2.id`, `qty_after 9`, `value_after Decimal("99.00")`.

**When**
- `result = dao.calculate_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (5, Decimal("10.00"))`.

### MIL-BAL-18 — when only an entry of another workspace exists the result is (0, 0.00)
- **Rules:** `calculate_balance` R5, R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E2 = entry, `performed_at T2`, but `workspace_id W2.id`, `qty_after 9`, `value_after Decimal("99.00")`.

**When**
- `result = dao.calculate_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (0, Decimal("0.00"))`.

### MIL-BAL-19 — the other workspace gets its own balance
- **Rules:** `calculate_balance` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 5`, `value_after Decimal("10.00")`.
2. E2 = entry, `performed_at T2`, but `workspace_id W2.id`, `qty_after 9`, `value_after Decimal("99.00")`.

**When**
- `result = dao.calculate_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == (9, Decimal("99.00"))`.

### MIL-BAL-20 — an unknown machine id gives (0, 0.00)
- **Rules:** `calculate_balance` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 5`, `value_after Decimal("10.00")`.

**When**
- `result = dao.calculate_balance(db, machine_id=MISSING, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (0, Decimal("0.00"))`.

### MIL-BAL-21 — an unknown item id gives (0, 0.00)
- **Rules:** `calculate_balance` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 5`, `value_after Decimal("10.00")`.

**When**
- `result = dao.calculate_balance(db, machine_id=M1.id, item_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == (0, Decimal("0.00"))`.

### MIL-BAL-22 — an unknown workspace id gives (0, 0.00)
- **Rules:** `calculate_balance` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 5`, `value_after Decimal("10.00")`.

**When**
- `result = dao.calculate_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=MISSING)`.

**Then**
1. returns: `result == (0, Decimal("0.00"))`.

### MIL-BAL-23 — machine_id 0 gives (0, 0.00)
- **Rules:** `calculate_balance` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 5`, `value_after Decimal("10.00")`.

**When**
- `result = dao.calculate_balance(db, machine_id=0, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (0, Decimal("0.00"))`.

### MIL-BAL-24 — item_id 0 gives (0, 0.00)
- **Rules:** `calculate_balance` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 5`, `value_after Decimal("10.00")`.

**When**
- `result = dao.calculate_balance(db, machine_id=M1.id, item_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == (0, Decimal("0.00"))`.

### MIL-BAL-25 — the balance of a soft-deleted machine is returned
- **Rules:** `calculate_balance` R6
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `machine_id MD.id`, `qty_after 4`, `value_after Decimal("8.00")`.

**When**
- `result = dao.calculate_balance(db, machine_id=MD.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (4, Decimal("8.00"))`.
2. unchanged: unchanged(E1).

### MIL-BAL-26 — the balance of a live machine in a soft-deleted factory is returned
- **Rules:** `calculate_balance` R6
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `machine_id MF.id`, `qty_after 4`, `value_after Decimal("8.00")`.

**When**
- `result = dao.calculate_balance(db, machine_id=MF.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (4, Decimal("8.00"))`.
2. unchanged: unchanged(E1).

### MIL-BAL-27 — the balance of a removed item is returned
- **Rules:** `calculate_balance` R6
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `item_id IR.id`, `qty_after 4`, `value_after Decimal("8.00")`.

**When**
- `result = dao.calculate_balance(db, machine_id=M1.id, item_id=IR.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (4, Decimal("8.00"))`.
2. unchanged: unchanged(E1).

### MIL-BAL-28 — a newer entry not yet flushed is not seen
- **Rules:** `calculate_balance` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 5`, `value_after Decimal("10.00")`.
2. E2 = entry, `performed_at T2`, `qty_after 9`, `value_after Decimal("99.00")`, added with `db.add(E2)` and not flushed.

**When**
- `result = dao.calculate_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (5, Decimal("10.00"))`.

### MIL-BAL-29 — the same newer entry is seen after the flush
- **Rules:** `calculate_balance` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 5`, `value_after Decimal("10.00")`.
2. E2 = entry, `performed_at T2`, `qty_after 9`, `value_after Decimal("99.00")`, added with `db.add(E2)` and not flushed.
3. `db.flush()`

**When**
- `result = dao.calculate_balance(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (9, Decimal("99.00"))`.


## `MachineItemLedgerDAO.get_latest_entry`

### MIL-LE-01 — with no entry the result is None
- **Rules:** `get_latest_entry` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No entry exists for M1 and I1 in W1.

**When**
- `result = dao.get_latest_entry(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### MIL-LE-02 — the newest entry is returned when it has the middle id, and nothing is written
- **Rules:** `get_latest_entry` R2, R6, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_latest_entry(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, MachineItemLedger)`.
2. returns: `result.id == E2.id`.
3. nothing written: nothing written.
4. unchanged: unchanged(E2).

### MIL-LE-03 — the newest entry is returned when it has the lowest id
- **Rules:** `get_latest_entry` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T3`.
2. E2 = entry, `performed_at T1`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_latest_entry(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.

### MIL-LE-04 — the newest entry is returned when it has the highest id
- **Rules:** `get_latest_entry` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.
3. E3 = entry, `performed_at T3`.

**When**
- `result = dao.get_latest_entry(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E3.id`.

### MIL-LE-05 — the full row is returned with its prices and values as stored
- **Rules:** `get_latest_entry` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `value_before Decimal("7.00")`, `value_after Decimal("10.00")`, `avg_price_before Decimal("1.75")`, `avg_price_after Decimal("2.00")`, `notes "Counted"`.

**When**
- `result = dao.get_latest_entry(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.
2. returns: `result.value_before == Decimal("7.00")`, `result.value_after == Decimal("10.00")`.
3. returns: `result.avg_price_before == Decimal("1.75")`, `result.avg_price_after == Decimal("2.00")`.
4. returns: `result.notes == "Counted"`.
5. returns: `result.performed_at == T1`.

### MIL-LE-06 — empty prices and values come back as None
- **Rules:** `get_latest_entry` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_latest_entry(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.
2. returns: `result.avg_price_after is None`.
3. returns: `result.value_after is None`.

### MIL-LE-07 — an older entry with the highest id does not win
- **Rules:** `get_latest_entry` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T3`.
2. O = entry, `performed_at T1`, but `id HIGH_ID`.

**When**
- `result = dao.get_latest_entry(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.

### MIL-LE-08 — tied entries: one of them is returned, never an older entry
- **Rules:** `get_latest_entry` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = entry, `performed_at T1`.
2. B = entry, `performed_at T2`, but `qty_after 15`, `value_after Decimal("150.00")`.
3. C = entry, `performed_at T2`, but `id HIGH_ID`, `qty_after 10`, `value_after Decimal("100.00")`.
4. A = entry, `performed_at T2`, but `qty_after 99`, `value_after Decimal("990.00")`.

**When**
- `result = dao.get_latest_entry(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id in [B.id, C.id, A.id]`.

### MIL-LE-09 — among tied entries the greatest id is returned
- **Rules:** `get_latest_entry` R3
- **Kind:** bug
- **Expect:** xfail BUG-664 (non-strict)
- **Fails today on:** Then 2 (no second sort key; usually B is returned, but the physical row order can match the intended result by accident)

**Given**
1. B = entry, `performed_at T2`, but `qty_after 15`, `value_after Decimal("150.00")`.
2. C = entry, `performed_at T2`, but `id HIGH_ID`, `qty_after 10`, `value_after Decimal("100.00")`.
3. A = entry, `performed_at T2`, but `qty_after 99`, `value_after Decimal("990.00")`.

**When**
- `result = dao.get_latest_entry(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id in [B.id, C.id, A.id]`.
2. returns: `result.id == C.id`.

### MIL-LE-10 — the query asks the database for performed_at newest first, then id highest first
- **Rules:** `get_latest_entry` R3
- **Kind:** bug
- **Expect:** xfail BUG-664
- **Fails today on:** Then 4 (the clause ends at `performed_at DESC`: no second sort key)

**Given**
1. E1 = entry, `performed_at T1`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_latest_entry(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"machine_item_ledger.performed_at DESC" in order_part`.
4. statement: `"machine_item_ledger.performed_at DESC, machine_item_ledger.id DESC" in order_part`.

### MIL-LE-11 — a newer entry of another machine is not considered
- **Rules:** `get_latest_entry` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `machine_id M2.id`.

**When**
- `result = dao.get_latest_entry(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.

### MIL-LE-12 — when only an entry of another machine exists the result is None
- **Rules:** `get_latest_entry` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E2 = entry, `performed_at T2`, but `machine_id M2.id`.

**When**
- `result = dao.get_latest_entry(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### MIL-LE-13 — a newer entry of another item is not considered
- **Rules:** `get_latest_entry` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `item_id I2.id`.

**When**
- `result = dao.get_latest_entry(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.

### MIL-LE-14 — when only an entry of another item exists the result is None
- **Rules:** `get_latest_entry` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E2 = entry, `performed_at T2`, but `item_id I2.id`.

**When**
- `result = dao.get_latest_entry(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### MIL-LE-15 — a newer entry of another workspace is not considered
- **Rules:** `get_latest_entry` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `workspace_id W2.id`.

**When**
- `result = dao.get_latest_entry(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.

### MIL-LE-16 — when only an entry of another workspace exists the result is None
- **Rules:** `get_latest_entry` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E2 = entry, `performed_at T2`, but `workspace_id W2.id`.

**When**
- `result = dao.get_latest_entry(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### MIL-LE-17 — the other workspace gets its own entry
- **Rules:** `get_latest_entry` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `workspace_id W2.id`.

**When**
- `result = dao.get_latest_entry(db, machine_id=M1.id, item_id=I1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result.id == E2.id`.

### MIL-LE-18 — an unknown machine id gives None
- **Rules:** `get_latest_entry` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_latest_entry(db, machine_id=MISSING, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### MIL-LE-19 — an unknown item id gives None
- **Rules:** `get_latest_entry` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_latest_entry(db, machine_id=M1.id, item_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### MIL-LE-20 — an unknown workspace id gives None
- **Rules:** `get_latest_entry` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_latest_entry(db, machine_id=M1.id, item_id=I1.id, workspace_id=MISSING)`.

**Then**
1. returns: `result is None`.

### MIL-LE-21 — the latest entry of a soft-deleted machine is returned
- **Rules:** `get_latest_entry` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `machine_id MD.id`.

**When**
- `result = dao.get_latest_entry(db, machine_id=MD.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.
2. unchanged: unchanged(E1).

### MIL-LE-22 — the latest entry of a live machine in a soft-deleted factory is returned
- **Rules:** `get_latest_entry` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `machine_id MF.id`.

**When**
- `result = dao.get_latest_entry(db, machine_id=MF.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.
2. unchanged: unchanged(E1).

### MIL-LE-23 — the latest entry of a removed item is returned
- **Rules:** `get_latest_entry` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `item_id IR.id`.

**When**
- `result = dao.get_latest_entry(db, machine_id=M1.id, item_id=IR.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.
2. unchanged: unchanged(E1).

### MIL-LE-24 — a pending entry stays pending and is not seen: the call writes nothing
- **Rules:** `get_latest_entry` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, added with `db.add(E2)` and not flushed.

**When**
- `result = dao.get_latest_entry(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.
2. returns: `E2 in db.new` (still pending: the call flushed nothing).

### MIL-LE-25 — the lookup never commits
- **Rules:** `get_latest_entry` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.get_latest_entry(db, machine_id=M1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.
2. re-read E1 after the savepoint rollback: `performed_at == T1`.
3. mock called: the `db.commit` spy was never called.


## `MachineItemLedgerDAO.get_by_performer`

### MIL-PF-01 — entries of every machine, item and transaction type of that user are returned
- **Rules:** `get_by_performer` R1
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: 'MachineItemLedgerDAO' object has no attribute 'get_by_performer')

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `machine_id M2.id`.
3. E3 = entry, `performed_at T3`, but `item_id I2.id`.
4. E4 = entry, `performed_at T4`, but `transaction_type "consumption"`.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E4.id, E3.id, E2.id, E1.id]`.

### MIL-PF-02 — an entry of another performer is not returned
- **Rules:** `get_by_performer` R1
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: 'MachineItemLedgerDAO' object has no attribute 'get_by_performer')

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `performed_by U2.id`.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-PF-03 — the same user's entry in another workspace is not returned
- **Rules:** `get_by_performer` R1
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: 'MachineItemLedgerDAO' object has no attribute 'get_by_performer')

**Given**
1. E1 = entry, `performed_at T1`.
2. X9 = entry, `performed_at T5`, but `workspace_id W2.id`. (Same machine and item ids as a W1 entry, on purpose.)

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-PF-04 — the other workspace gets only its own entry
- **Rules:** `get_by_performer` R1
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: 'MachineItemLedgerDAO' object has no attribute 'get_by_performer')

**Given**
1. E1 = entry, `performed_at T1`.
2. X9 = entry, `performed_at T5`, but `workspace_id W2.id`. (Same machine and item ids as a W1 entry, on purpose.)

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [X9.id]`.

### MIL-PF-05 — an unknown profile id returns an empty list
- **Rules:** `get_by_performer` R1
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: 'MachineItemLedgerDAO' object has no attribute 'get_by_performer')

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_performer(db, performed_by=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIL-PF-06 — profile id 0 returns an empty list
- **Rules:** `get_by_performer` R1
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: 'MachineItemLedgerDAO' object has no attribute 'get_by_performer')

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_performer(db, performed_by=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIL-PF-07 — returns a list of ledger rows, newest first whatever the insertion order, and writes nothing
- **Rules:** `get_by_performer` R2, R1
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: 'MachineItemLedgerDAO' object has no attribute 'get_by_performer')

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `isinstance(result[0], MachineItemLedger)`.
3. returns: `ids(result) == [E2.id, E3.id, E1.id]`.
4. nothing written: nothing written.
5. unchanged: unchanged(E1).

### MIL-PF-08 — skip 1 and limit 1 return exactly the middle entry
- **Rules:** `get_by_performer` R2
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: 'MachineItemLedgerDAO' object has no attribute 'get_by_performer')

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E3.id]`.

### MIL-PF-09 — limit 2 returns the two newest entries
- **Rules:** `get_by_performer` R2
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: 'MachineItemLedgerDAO' object has no attribute 'get_by_performer')

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `ids(result) == [E2.id, E3.id]`.

### MIL-PF-10 — limit 1 returns only the newest entry
- **Rules:** `get_by_performer` R2
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: 'MachineItemLedgerDAO' object has no attribute 'get_by_performer')

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### MIL-PF-11 — skip one below the number of entries returns the oldest entry
- **Rules:** `get_by_performer` R2
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: 'MachineItemLedgerDAO' object has no attribute 'get_by_performer')

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-PF-12 — skip equal to the number of entries returns an empty list
- **Rules:** `get_by_performer` R2
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: 'MachineItemLedgerDAO' object has no attribute 'get_by_performer')

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id, skip=3)`.

**Then**
1. returns: `result == []`.

### MIL-PF-13 — skip past the number of entries returns an empty list
- **Rules:** `get_by_performer` R2
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: 'MachineItemLedgerDAO' object has no attribute 'get_by_performer')

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id, skip=4)`.

**Then**
1. returns: `result == []`.

### MIL-PF-14 — limit 0 returns an empty list
- **Rules:** `get_by_performer` R2
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: 'MachineItemLedgerDAO' object has no attribute 'get_by_performer')

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### MIL-PF-15 — paging counts matching entries only: newer entries left out by the filters use no place on the page
- **Rules:** `get_by_performer` R2
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: 'MachineItemLedgerDAO' object has no attribute 'get_by_performer')

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.
3. EX = entry, `performed_at T3`, but `performed_by U2.id`.
4. X9 = entry, `performed_at T5`, but `workspace_id W2.id`. (Same machine and item ids as a W1 entry, on purpose.)

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### MIL-PF-16 — by default at most the 100 newest of 101 entries are returned; the oldest is missing
- **Rules:** `get_by_performer` R2
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: 'MachineItemLedgerDAO' object has no attribute 'get_by_performer')

**Given**
1. 101 entries N1 … N101, inserted in that order; Nk (k = 1 … 101) = entry, `performed_at T1 + timedelta(minutes=k)`.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result)` == the ids of N101, N100, … N2, in that order.
3. returns: `N1.id not in ids(result)`.

### MIL-PF-17 — exactly 100 entries are all returned by default
- **Rules:** `get_by_performer` R2
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: 'MachineItemLedgerDAO' object has no attribute 'get_by_performer')

**Given**
1. 100 entries N1 … N100, inserted in that order; Nk (k = 1 … 100) = entry, `performed_at T1 + timedelta(minutes=k)`.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result)` == the ids of N100, N99, … N1, in that order.

### MIL-PF-18 — limit 101 returns all 101 entries: the method has no upper cap
- **Rules:** `get_by_performer` R2
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: 'MachineItemLedgerDAO' object has no attribute 'get_by_performer')

**Given**
1. 101 entries N1 … N101, inserted in that order; Nk (k = 1 … 101) = entry, `performed_at T1 + timedelta(minutes=k)`.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id, limit=101)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result)` == the ids of N101, N100, … N1, in that order.

### MIL-PF-19 — a negative limit makes the database reject the query
- **Rules:** `get_by_performer` R2, Errors (as get_by_item)
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: 'MachineItemLedgerDAO' object has no attribute 'get_by_performer')

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `exc.value.orig.pgcode == "2201W"`.
4. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MIL-PF-20 — a negative skip makes the database reject the query
- **Rules:** `get_by_performer` R2, Errors (as get_by_item)
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: 'MachineItemLedgerDAO' object has no attribute 'get_by_performer')

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `exc.value.orig.pgcode == "2201X"`.
4. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MIL-PF-21 — entries with the same performed_at come back by id, highest first
- **Rules:** `get_by_performer` R2
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: 'MachineItemLedgerDAO' object has no attribute 'get_by_performer')

**Given**
1. B = entry, `performed_at T2`, but `qty_after 15`, `value_after Decimal("150.00")`.
2. C = entry, `performed_at T2`, but `id HIGH_ID`, `qty_after 10`, `value_after Decimal("100.00")`.
3. A = entry, `performed_at T2`, but `qty_after 99`, `value_after Decimal("990.00")`.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [C.id, A.id, B.id]`.

### MIL-PF-22 — the query asks the database for performed_at newest first, then id highest first
- **Rules:** `get_by_performer` R2
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: 'MachineItemLedgerDAO' object has no attribute 'get_by_performer')

**Given**
1. E1 = entry, `performed_at T1`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"machine_item_ledger.performed_at DESC" in order_part`.
4. statement: `"machine_item_ledger.performed_at DESC, machine_item_ledger.id DESC" in order_part`.

### MIL-PF-23 — an entry of a soft-deleted machine is returned
- **Rules:** `get_by_performer` R3
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: 'MachineItemLedgerDAO' object has no attribute 'get_by_performer')

**Given**
1. E1 = entry, `performed_at T1`, but `machine_id MD.id`.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. unchanged: unchanged(E1).

### MIL-PF-24 — an entry of a live machine in a soft-deleted factory is returned
- **Rules:** `get_by_performer` R3
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: 'MachineItemLedgerDAO' object has no attribute 'get_by_performer')

**Given**
1. E1 = entry, `performed_at T1`, but `machine_id MF.id`.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. unchanged: unchanged(E1).

### MIL-PF-25 — an entry of a removed item is returned
- **Rules:** `get_by_performer` R3
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: 'MachineItemLedgerDAO' object has no attribute 'get_by_performer')

**Given**
1. E1 = entry, `performed_at T1`, but `item_id IR.id`.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. unchanged: unchanged(E1).

### MIL-PF-26 — the call writes nothing
- **Rules:** `get_by_performer` R3
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: 'MachineItemLedgerDAO' object has no attribute 'get_by_performer')

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E2.id, E1.id]`.
2. nothing written: nothing written.
3. unchanged: unchanged(E1).

### MIL-PF-27 — performed_by None returns an empty list and raises nothing
- **Rules:** `get_by_performer` R4
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: 'MachineItemLedgerDAO' object has no attribute 'get_by_performer')

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_performer(db, performed_by=None, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MIL-PF-28 — a pending entry stays pending and is not seen: the call writes nothing
- **Rules:** `get_by_performer` R3
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: 'MachineItemLedgerDAO' object has no attribute 'get_by_performer')

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, added with `db.add(E2)` and not flushed.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. returns: `E2 in db.new` (still pending: the call flushed nothing).


## Inherited `BaseDAO` methods on `MachineItemLedger`

### MIL-INH-01 — create with a dict saves the row with the required columns as given
- **Rules:** `inherited` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `result = dao.create(db, obj_in=FULL)`.

**Then**
1. returns: `result.id is not None`.
2. returns: `isinstance(result, MachineItemLedger)`.
3. count: `machine_item_ledger` rows with `workspace_id == W1.id`: exactly 1.
4. re-read the returned row: `workspace_id == W1.id`, `machine_id == M1.id`, `item_id == I1.id`, `performed_by == U1.id`.
5. re-read the returned row: `transaction_type == "manual_add"`, `source_type == "manual"`.
6. re-read the returned row: `quantity == 3`, `qty_before == 4`, `qty_after == 7`.
7. re-read the returned row: `unit_cost == Decimal("2.50")`, `total_cost == Decimal("7.50")`.

### MIL-INH-02 — create leaves every nullable column empty
- **Rules:** `inherited` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `result = dao.create(db, obj_in=FULL)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `value_before is None`, `value_after is None`, `avg_price_before is None`, `avg_price_after is None`.
3. re-read the returned row: `source_id is None`, `order_id is None`, `order_type is None`, `invoice_id is None`, `notes is None`.
4. re-read the returned row: `transfer_source_id is None`, `transfer_source_type is None`, `transfer_destination_id is None`, `transfer_destination_type is None`.

### MIL-INH-03 — create fills performed_at with a naive UTC time at flush
- **Rules:** `inherited` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `result = dao.create(db, obj_in=FULL)`.

**Then**
1. returns: `result.performed_at is not None`.
2. re-read the returned row: `performed_at.tzinfo is None`.
3. re-read the returned row: `performed_at` is close to now.

### MIL-INH-04 — create computes nothing: inconsistent figures are stored as given
- **Rules:** `inherited` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `result = dao.create(db, obj_in={**FULL, "total_cost": Decimal("999.00"), "qty_after": 50, "value_after": Decimal("1.00"), "avg_price_after": Decimal("3.00")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `total_cost == Decimal("999.00")`, `qty_after == 50`.
3. re-read the returned row: `value_after == Decimal("1.00")`, `avg_price_after == Decimal("3.00")`.

### MIL-INH-05 — create stores the optional columns given
- **Rules:** `inherited` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `result = dao.create(db, obj_in={**FULL, "source_id": 77, "notes": "From the count", "value_before": Decimal("8.00"), "avg_price_before": Decimal("2.00")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `source_id == 77`, `notes == "From the count"`.
3. re-read the returned row: `value_before == Decimal("8.00")`, `avg_price_before == Decimal("2.00")`.

### MIL-INH-06 — create is flushed, not committed: a rollback removes the row
- **Rules:** `inherited` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No entry exists in W1.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.create(db, obj_in=FULL)`.

**Then**
1. returns: `result.id is not None`.
2. count: inside the savepoint, `machine_item_ledger` rows with `workspace_id == W1.id`: exactly 1.
3. count: after the savepoint rollback, `machine_item_ledger` rows with `workspace_id == W1.id`: exactly 0.
4. mock called: the `db.commit` spy was never called.

### MIL-INH-07 — create with MachineItemLedgerCreate fails on flush and saves nothing
- **Rules:** `inherited` R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in=MachineItemLedgerCreate(machine_id=M1.id, item_id=I1.id, transaction_type="manual_add", quantity=3, unit_cost=Decimal("2.50"), total_cost=Decimal("7.50"), qty_before=4, qty_after=7, source_type="manual"))`. (The schema has no `workspace_id` or `performed_by`. Field list: Spec gap 1.)

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `'column "workspace_id"' in str(exc.value.orig)`.
4. nothing written: nothing written.

### MIL-INH-08 — an unknown workspace_id fails on flush and saves nothing
- **Rules:** `inherited` R3, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={**FULL, "workspace_id": MISSING})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"machine_item_ledger_workspace_id_fkey" in str(exc.value.orig)`.
4. nothing written: nothing written.

### MIL-INH-09 — an unknown machine_id fails on flush and saves nothing
- **Rules:** `inherited` R3, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={**FULL, "machine_id": MISSING})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"machine_item_ledger_machine_id_fkey" in str(exc.value.orig)`.
4. nothing written: nothing written.

### MIL-INH-10 — an unknown item_id fails on flush and saves nothing
- **Rules:** `inherited` R3, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={**FULL, "item_id": MISSING})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"machine_item_ledger_item_id_fkey" in str(exc.value.orig)`.
4. nothing written: nothing written.

### MIL-INH-11 — an unknown performed_by fails on flush and saves nothing
- **Rules:** `inherited` R3, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={**FULL, "performed_by": MISSING})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"machine_item_ledger_performed_by_fkey" in str(exc.value.orig)`.
4. nothing written: nothing written.

### MIL-INH-12 — an unknown invoice_id fails on flush and saves nothing
- **Rules:** `inherited` R3, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={**FULL, "invoice_id": MISSING})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"machine_item_ledger_invoice_id_fkey" in str(exc.value.orig)`.
4. nothing written: nothing written.

### MIL-INH-13 — performed_by None fails on flush and saves nothing
- **Rules:** `inherited` R3, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={**FULL, "performed_by": None})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `'column "performed_by"' in str(exc.value.orig)`.
4. nothing written: nothing written.

### MIL-INH-14 — a missing workspace_id fails on flush and saves nothing
- **Rules:** `inherited` R3, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={k: v for k, v in FULL.items() if k != "workspace_id"})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `'column "workspace_id"' in str(exc.value.orig)`.
4. nothing written: nothing written.

### MIL-INH-15 — a missing machine_id fails on flush and saves nothing
- **Rules:** `inherited` R3, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={k: v for k, v in FULL.items() if k != "machine_id"})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `'column "machine_id"' in str(exc.value.orig)`.
4. nothing written: nothing written.

### MIL-INH-16 — a missing item_id fails on flush and saves nothing
- **Rules:** `inherited` R3, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={k: v for k, v in FULL.items() if k != "item_id"})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `'column "item_id"' in str(exc.value.orig)`.
4. nothing written: nothing written.

### MIL-INH-17 — a missing transaction_type fails on flush and saves nothing
- **Rules:** `inherited` R3, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={k: v for k, v in FULL.items() if k != "transaction_type"})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `'column "transaction_type"' in str(exc.value.orig)`.
4. nothing written: nothing written.

### MIL-INH-18 — a missing quantity fails on flush and saves nothing
- **Rules:** `inherited` R3, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={k: v for k, v in FULL.items() if k != "quantity"})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `'column "quantity"' in str(exc.value.orig)`.
4. nothing written: nothing written.

### MIL-INH-19 — a missing qty_before fails on flush and saves nothing
- **Rules:** `inherited` R3, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={k: v for k, v in FULL.items() if k != "qty_before"})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `'column "qty_before"' in str(exc.value.orig)`.
4. nothing written: nothing written.

### MIL-INH-20 — a missing qty_after fails on flush and saves nothing
- **Rules:** `inherited` R3, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={k: v for k, v in FULL.items() if k != "qty_after"})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `'column "qty_after"' in str(exc.value.orig)`.
4. nothing written: nothing written.

### MIL-INH-21 — a missing unit_cost fails on flush and saves nothing
- **Rules:** `inherited` R3, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={k: v for k, v in FULL.items() if k != "unit_cost"})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `'column "unit_cost"' in str(exc.value.orig)`.
4. nothing written: nothing written.

### MIL-INH-22 — a missing total_cost fails on flush and saves nothing
- **Rules:** `inherited` R3, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={k: v for k, v in FULL.items() if k != "total_cost"})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `'column "total_cost"' in str(exc.value.orig)`.
4. nothing written: nothing written.

### MIL-INH-23 — a missing source_type fails on flush and saves nothing
- **Rules:** `inherited` R3, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={k: v for k, v in FULL.items() if k != "source_type"})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `'column "source_type"' in str(exc.value.orig)`.
4. nothing written: nothing written.

### MIL-INH-24 — any string is saved as transaction_type
- **Rules:** `inherited` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `result = dao.create(db, obj_in={**FULL, "transaction_type": "not a real type"})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `transaction_type == "not a real type"`.

### MIL-INH-25 — a negative quantity is saved
- **Rules:** `inherited` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `result = dao.create(db, obj_in={**FULL, "quantity": -5})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `quantity == -5`.

### MIL-INH-26 — a negative unit_cost and total_cost are saved
- **Rules:** `inherited` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `result = dao.create(db, obj_in={**FULL, "unit_cost": Decimal("-2.50"), "total_cost": Decimal("-7.50")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `unit_cost == Decimal("-2.50")`, `total_cost == Decimal("-7.50")`.

### MIL-INH-27 — machine and item need not belong to the entry's workspace
- **Rules:** `inherited` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No entry exists in W2.

**When**
- `result = dao.create(db, obj_in={**FULL, "workspace_id": W2.id})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W2.id`, `machine_id == M1.id`, `item_id == I1.id`.

### MIL-INH-28 — every text column accepts a value of exactly its limit
- **Rules:** `inherited` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `result = dao.create(db, obj_in={**FULL, "transaction_type": "t" * 50, "source_type": "s" * 50, "order_type": "o" * 30, "transfer_source_type": "a" * 50, "transfer_destination_type": "b" * 50})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `transaction_type == "t" * 50`, `source_type == "s" * 50`, `order_type == "o" * 30`.
3. re-read the returned row: `transfer_source_type == "a" * 50`, `transfer_destination_type == "b" * 50`.

### MIL-INH-29 — a transaction_type of 51 characters is too long and nothing is saved
- **Rules:** `inherited` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={**FULL, "transaction_type": "t" * 51})`.

**Then**
1. raises: `DataError` on flush.
2. raises: `isinstance(exc.value.orig, StringDataRightTruncation)`.
3. raises: `exc.value.orig.pgcode == "22001"`.
4. nothing written: nothing written.

### MIL-INH-30 — a source_type of 51 characters is too long and nothing is saved
- **Rules:** `inherited` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={**FULL, "source_type": "s" * 51})`.

**Then**
1. raises: `DataError` on flush.
2. raises: `isinstance(exc.value.orig, StringDataRightTruncation)`.
3. raises: `exc.value.orig.pgcode == "22001"`.
4. nothing written: nothing written.

### MIL-INH-31 — a order_type of 31 characters is too long and nothing is saved
- **Rules:** `inherited` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={**FULL, "order_type": "o" * 31})`.

**Then**
1. raises: `DataError` on flush.
2. raises: `isinstance(exc.value.orig, StringDataRightTruncation)`.
3. raises: `exc.value.orig.pgcode == "22001"`.
4. nothing written: nothing written.

### MIL-INH-32 — a transfer_source_type of 51 characters is too long and nothing is saved
- **Rules:** `inherited` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={**FULL, "transfer_source_type": "a" * 51})`.

**Then**
1. raises: `DataError` on flush.
2. raises: `isinstance(exc.value.orig, StringDataRightTruncation)`.
3. raises: `exc.value.orig.pgcode == "22001"`.
4. nothing written: nothing written.

### MIL-INH-33 — a transfer_destination_type of 51 characters is too long and nothing is saved
- **Rules:** `inherited` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={**FULL, "transfer_destination_type": "b" * 51})`.

**Then**
1. raises: `DataError` on flush.
2. raises: `isinstance(exc.value.orig, StringDataRightTruncation)`.
3. raises: `exc.value.orig.pgcode == "22001"`.
4. nothing written: nothing written.

### MIL-INH-34 — the greatest amount a cost column holds is saved
- **Rules:** `inherited` R1b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `result = dao.create(db, obj_in={**FULL, "unit_cost": Decimal("9999999999999.99")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `unit_cost == Decimal("9999999999999.99")`.

### MIL-INH-35 — an amount with one more digit is too big and nothing is saved
- **Rules:** `inherited` R1b, Errors row 5
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={**FULL, "unit_cost": Decimal("10000000000000.00")})`.

**Then**
1. raises: `DataError` on flush.
2. raises: `isinstance(exc.value.orig, NumericValueOutOfRange)`.
3. raises: `exc.value.orig.pgcode == "22003"`.
4. raises: `"numeric field overflow" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MIL-INH-36 — hard-deleting a machine that has entries fails and changes nothing
- **Rules:** `inherited` R5, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `machine_id M2.id`.

**When**
- `db.execute(text("delete from machines where id = :i"), {"i": M2.id})`.

**Then**
1. raises: `IntegrityError`.
2. raises: `isinstance(exc.value.orig, RestrictViolation)`.
3. raises: `"machine_item_ledger_machine_id_fkey" in str(exc.value.orig)`.
4. nothing written: nothing written.
5. unchanged: unchanged(E1).

### MIL-INH-37 — hard-deleting an item that has entries fails and changes nothing
- **Rules:** `inherited` R5, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `item_id I2.id`.

**When**
- `db.execute(text("delete from items where id = :i"), {"i": I2.id})`.

**Then**
1. raises: `IntegrityError`.
2. raises: `isinstance(exc.value.orig, RestrictViolation)`.
3. raises: `"machine_item_ledger_item_id_fkey" in str(exc.value.orig)`.
4. nothing written: nothing written.
5. unchanged: unchanged(E1).

### MIL-INH-38 — hard-deleting a profile that has entries fails on the NOT NULL column and changes nothing
- **Rules:** `inherited` R5, Errors row 4
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `performed_by U2.id`.

**When**
- `db.execute(text("delete from profiles where id = :i"), {"i": U2.id})`.

**Then**
1. raises: `IntegrityError`.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `'column "performed_by"' in str(exc.value.orig)`.
4. nothing written: nothing written.
5. unchanged: unchanged(E1).

### MIL-INH-39 — get_by_workspace returns the workspace's entries and none of another workspace
- **Rules:** `inherited` R6, R8
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.
3. X9 = entry, `performed_at T5`, but `workspace_id W2.id`. (Same machine and item ids as a W1 entry, on purpose.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == sorted([E1.id, E2.id])`.
2. returns: `len(result) == 2`.

### MIL-INH-40 — get_by_workspace applies skip and limit to the workspace's entries
- **Rules:** `inherited` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.
3. E3 = entry, `performed_at T3`.
4. X9 = entry, `performed_at T5`, but `workspace_id W2.id`. (Same machine and item ids as a W1 entry, on purpose.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in [E1.id, E2.id, E3.id]`.

### MIL-INH-41 — get_by_workspace returns the entries by id, lowest first
- **Rules:** `inherited` R6
- **Kind:** bug
- **Expect:** xfail BUG-100 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; usually [B, C, A] today, but the physical row order can match the intended order by accident)

**Given**
1. B = entry, `performed_at T1`.
2. C = entry, `performed_at T2`, but `id HIGH_ID`.
3. A = entry, `performed_at T3`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == sorted([B.id, C.id, A.id])`.
2. returns: `ids(result) == [B.id, A.id, C.id]`.

### MIL-INH-42 — the workspace list query asks the database for id, lowest first
- **Rules:** `inherited` R6
- **Kind:** bug
- **Expect:** xfail BUG-100
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. E1 = entry, `performed_at T1`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"machine_item_ledger.id" in order_part`.
4. statement: `"machine_item_ledger.id DESC" not in order_part`.

### MIL-INH-43 — update with a dict changes the column given and only that
- **Rules:** `inherited` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 5`, `notes "Keep"`.

**When**
- `result = dao.update(db, db_obj=E1, obj_in={"qty_after": 99})`.

**Then**
1. returns: `result is E1`.
2. re-read E1: `qty_after == 99`.
3. re-read E1: `notes == "Keep"`, `quantity == 1`, `qty_before == 4`.
4. re-read E1: `performed_at == T1`.

### MIL-INH-44 — update with MachineItemLedgerUpdate changes notes and only that
- **Rules:** `inherited` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 5`.

**When**
- `result = dao.update(db, db_obj=E1, obj_in=MachineItemLedgerUpdate(notes="Counted again"))`.

**Then**
1. returns: `result is E1`.
2. re-read E1: `notes == "Counted again"`.
3. re-read E1: `qty_after == 5`, `quantity == 1`.
4. re-read E1: `performed_at == T1`.

### MIL-INH-45 — update is flushed, not committed: a rollback restores the old value
- **Rules:** `inherited` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 5`.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.update(db, db_obj=E1, obj_in={"qty_after": 99})`.

**Then**
1. returns: `result is E1`.
2. returns: inside the savepoint, `db.scalar(select(MachineItemLedger.qty_after).where(MachineItemLedger.id == E1.id)) == 99`.
3. re-read E1 after the savepoint rollback: `qty_after == 5`.
4. mock called: the `db.commit` spy was never called.

### MIL-INH-46 — remove hard-deletes the entry and leaves the others
- **Rules:** `inherited` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.
3. `e1_id = E1.id`

**When**
- `result = dao.remove(db, id=e1_id)`.

**Then**
1. returns: `result.id == e1_id`.
2. count: `machine_item_ledger` rows with `id == e1_id`: exactly 0.
3. unchanged: unchanged(E2).

### MIL-INH-47 — remove is flushed, not committed: a rollback restores the entry
- **Rules:** `inherited` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. `e1_id = E1.id`
3. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.remove(db, id=e1_id)`.

**Then**
1. returns: `result.id == e1_id`.
2. count: inside the savepoint, `machine_item_ledger` rows with `id == e1_id`: exactly 0.
3. count: after the savepoint rollback, `machine_item_ledger` rows with `id == e1_id`: exactly 1.
4. mock called: the `db.commit` spy was never called.

### MIL-INH-48 — get returns an entry of any workspace
- **Rules:** `inherited` R8
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X9 = entry, `performed_at T5`, but `workspace_id W2.id`. (Same machine and item ids as a W1 entry, on purpose.)

**When**
- `result = dao.get(db, X9.id)`.

**Then**
1. returns: `result.id == X9.id`.
2. returns: `result.workspace_id == W2.id`.

### MIL-INH-49 — get_by_id_and_workspace returns an entry of that workspace
- **Rules:** `inherited` R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=E1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.

### MIL-INH-50 — get_by_id_and_workspace returns None for an entry of another workspace
- **Rules:** `inherited` R8
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X9 = entry, `performed_at T5`, but `workspace_id W2.id`. (Same machine and item ids as a W1 entry, on purpose.)

**When**
- `result = dao.get_by_id_and_workspace(db, id=X9.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### MIL-INH-51 — a unit_cost of 1.005 is stored as 1.01: a fresh read shows the rounded value
- **Rules:** `inherited` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `result = dao.create(db, obj_in={**FULL, "unit_cost": Decimal("1.005")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `unit_cost == Decimal("1.01")`.

### MIL-INH-52 — a unit_cost of 1.004 is stored as 1.00: a fresh read shows the rounded value
- **Rules:** `inherited` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `result = dao.create(db, obj_in={**FULL, "unit_cost": Decimal("1.004")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `unit_cost == Decimal("1.00")`.

### MIL-INH-53 — a unit_cost of 1.015 is stored as 1.02: a fresh read shows the rounded value
- **Rules:** `inherited` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `result = dao.create(db, obj_in={**FULL, "unit_cost": Decimal("1.015")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `unit_cost == Decimal("1.02")`.

### MIL-INH-54 — a unit_cost of 1.025 is stored as 1.03: a fresh read shows the rounded value
- **Rules:** `inherited` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `result = dao.create(db, obj_in={**FULL, "unit_cost": Decimal("1.025")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `unit_cost == Decimal("1.03")`.

### MIL-INH-55 — a unit_cost of 2.675 is stored as 2.68: a fresh read shows the rounded value
- **Rules:** `inherited` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `result = dao.create(db, obj_in={**FULL, "unit_cost": Decimal("2.675")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `unit_cost == Decimal("2.68")`.

### MIL-INH-56 — a unit_cost of 0.125 is stored as 0.13: a fresh read shows the rounded value
- **Rules:** `inherited` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `result = dao.create(db, obj_in={**FULL, "unit_cost": Decimal("0.125")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `unit_cost == Decimal("0.13")`.

### MIL-INH-57 — a unit_cost of 0.0049 is stored as 0.00: a fresh read shows the rounded value
- **Rules:** `inherited` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `result = dao.create(db, obj_in={**FULL, "unit_cost": Decimal("0.0049")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `unit_cost == Decimal("0.00")`.

### MIL-INH-58 — a unit_cost of -1.005 is stored as -1.01: a fresh read shows the rounded value
- **Rules:** `inherited` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `result = dao.create(db, obj_in={**FULL, "unit_cost": Decimal("-1.005")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `unit_cost == Decimal("-1.01")`.

### MIL-INH-59 — a Python float 1.005 is stored as 1.01
- **Rules:** `inherited` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `result = dao.create(db, obj_in={**FULL, "unit_cost": 1.005})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `unit_cost == Decimal("1.01")`.

### MIL-INH-60 — every money column stores 2 decimals
- **Rules:** `inherited` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `result = dao.create(db, obj_in={**FULL, "unit_cost": Decimal("1.005"), "total_cost": Decimal("1.005"), "value_before": Decimal("1.005"), "value_after": Decimal("1.005"), "avg_price_before": Decimal("1.005"), "avg_price_after": Decimal("1.005")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `unit_cost == Decimal("1.01")`, `total_cost == Decimal("1.01")`.
3. re-read the returned row: `value_before == Decimal("1.01")`, `value_after == Decimal("1.01")`.
4. re-read the returned row: `avg_price_before == Decimal("1.01")`, `avg_price_after == Decimal("1.01")`.

### MIL-INH-61 — the instance returned by create keeps the given value until it is refreshed
- **Rules:** `inherited` R1a
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `result = dao.create(db, obj_in={**FULL, "unit_cost": Decimal("1.005")})`.

**Then**
1. returns: `result.unit_cost == Decimal("1.005")` (read on the object, before any re-read).
2. re-read the returned row: `unit_cost == Decimal("1.01")`.

### MIL-INH-62 — 9999999999999.994 rounds down and is stored as 9999999999999.99
- **Rules:** `inherited` R1b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `result = dao.create(db, obj_in={**FULL, "unit_cost": Decimal("9999999999999.994")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `unit_cost == Decimal("9999999999999.99")`.

### MIL-INH-63 — a unit_cost of 9999999999999.995 rounds past the limit and nothing is saved
- **Rules:** `inherited` R1b, Errors row 5
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={**FULL, "unit_cost": Decimal("9999999999999.995")})`.

**Then**
1. raises: `DataError` on flush.
2. raises: `isinstance(exc.value.orig, NumericValueOutOfRange)`.
3. raises: `exc.value.orig.pgcode == "22003"`.
4. raises: `"numeric field overflow" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MIL-INH-64 — a total_cost of 9999999999999.995 rounds past the limit and nothing is saved
- **Rules:** `inherited` R1b, Errors row 5
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={**FULL, "total_cost": Decimal("9999999999999.995")})`.

**Then**
1. raises: `DataError` on flush.
2. raises: `isinstance(exc.value.orig, NumericValueOutOfRange)`.
3. raises: `exc.value.orig.pgcode == "22003"`.
4. raises: `"numeric field overflow" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MIL-INH-65 — a value_before of 9999999999999.995 rounds past the limit and nothing is saved
- **Rules:** `inherited` R1b, Errors row 5
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={**FULL, "value_before": Decimal("9999999999999.995")})`.

**Then**
1. raises: `DataError` on flush.
2. raises: `isinstance(exc.value.orig, NumericValueOutOfRange)`.
3. raises: `exc.value.orig.pgcode == "22003"`.
4. raises: `"numeric field overflow" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MIL-INH-66 — a value_after of 9999999999999.995 rounds past the limit and nothing is saved
- **Rules:** `inherited` R1b, Errors row 5
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={**FULL, "value_after": Decimal("9999999999999.995")})`.

**Then**
1. raises: `DataError` on flush.
2. raises: `isinstance(exc.value.orig, NumericValueOutOfRange)`.
3. raises: `exc.value.orig.pgcode == "22003"`.
4. raises: `"numeric field overflow" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MIL-INH-67 — an avg_price_before of 9999999999999.995 rounds past the limit and nothing is saved
- **Rules:** `inherited` R1b, Errors row 5
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={**FULL, "avg_price_before": Decimal("9999999999999.995")})`.

**Then**
1. raises: `DataError` on flush.
2. raises: `isinstance(exc.value.orig, NumericValueOutOfRange)`.
3. raises: `exc.value.orig.pgcode == "22003"`.
4. raises: `"numeric field overflow" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MIL-INH-68 — an avg_price_after of 9999999999999.995 rounds past the limit and nothing is saved
- **Rules:** `inherited` R1b, Errors row 5
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={**FULL, "avg_price_after": Decimal("9999999999999.995")})`.

**Then**
1. raises: `DataError` on flush.
2. raises: `isinstance(exc.value.orig, NumericValueOutOfRange)`.
3. raises: `exc.value.orig.pgcode == "22003"`.
4. raises: `"numeric field overflow" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MIL-INH-69 — the most negative amount a cost column holds is saved
- **Rules:** `inherited` R1b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `result = dao.create(db, obj_in={**FULL, "unit_cost": Decimal("-9999999999999.99")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `unit_cost == Decimal("-9999999999999.99")`.

### MIL-INH-70 — -10000000000000 is too big and nothing is saved
- **Rules:** `inherited` R1b, Errors row 5
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={**FULL, "unit_cost": Decimal("-10000000000000")})`.

**Then**
1. raises: `DataError` on flush.
2. raises: `isinstance(exc.value.orig, NumericValueOutOfRange)`.
3. raises: `exc.value.orig.pgcode == "22003"`.
4. raises: `"numeric field overflow" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MIL-INH-71 — the greatest integer is saved in quantity
- **Rules:** `inherited` R1b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `result = dao.create(db, obj_in={**FULL, "quantity": 2147483647})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `quantity == 2147483647`.

### MIL-INH-72 — the smallest integer is saved in quantity
- **Rules:** `inherited` R1b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `result = dao.create(db, obj_in={**FULL, "quantity": -2147483648})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `quantity == -2147483648`.

### MIL-INH-73 — a quantity of 2147483648 is out of range and nothing is saved
- **Rules:** `inherited` R1b, Errors row 6
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={**FULL, "quantity": 2147483648})`.

**Then**
1. raises: `DataError` on flush.
2. raises: `isinstance(exc.value.orig, NumericValueOutOfRange)`.
3. raises: `exc.value.orig.pgcode == "22003"`.
4. raises: `"integer out of range" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MIL-INH-74 — a quantity of -2147483649 is out of range and nothing is saved
- **Rules:** `inherited` R1b, Errors row 6
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={**FULL, "quantity": -2147483649})`.

**Then**
1. raises: `DataError` on flush.
2. raises: `isinstance(exc.value.orig, NumericValueOutOfRange)`.
3. raises: `exc.value.orig.pgcode == "22003"`.
4. raises: `"integer out of range" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MIL-INH-75 — a qty_before of 2147483648 is out of range and nothing is saved
- **Rules:** `inherited` R1b, Errors row 6
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={**FULL, "qty_before": 2147483648})`.

**Then**
1. raises: `DataError` on flush.
2. raises: `isinstance(exc.value.orig, NumericValueOutOfRange)`.
3. raises: `exc.value.orig.pgcode == "22003"`.
4. raises: `"integer out of range" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MIL-INH-76 — a qty_after of 2147483648 is out of range and nothing is saved
- **Rules:** `inherited` R1b, Errors row 6
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in={**FULL, "qty_after": 2147483648})`.

**Then**
1. raises: `DataError` on flush.
2. raises: `isinstance(exc.value.orig, NumericValueOutOfRange)`.
3. raises: `exc.value.orig.pgcode == "22003"`.
4. raises: `"integer out of range" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MIL-INH-77 — MachineItemLedgerCreate ignores workspace_id and performed_by: the flush still fails
- **Rules:** `inherited` R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `dao.create(db, obj_in=MachineItemLedgerCreate(machine_id=M1.id, item_id=I1.id, transaction_type="manual_add", quantity=3, unit_cost=Decimal("2.50"), total_cost=Decimal("7.50"), qty_before=4, qty_after=7, source_type="manual", workspace_id=W1.id, performed_by=U1.id))`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `'column "workspace_id"' in str(exc.value.orig)`.
4. nothing written: nothing written.

### MIL-INH-78 — MachineItemLedgerCreate rejects a negative quantity
- **Rules:** `inherited` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `MachineItemLedgerCreate(machine_id=M1.id, item_id=I1.id, transaction_type="manual_add", quantity=-1, unit_cost=Decimal("2.50"), total_cost=Decimal("7.50"), qty_before=4, qty_after=7, source_type="manual")` (target `schema`; the DAO is not called).

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.errors()[0]["type"] == "greater_than_equal"`.
3. raises: `exc.value.errors()[0]["loc"] == ("quantity",)`.
4. nothing written: nothing written.

### MIL-INH-79 — MachineItemLedgerCreate rejects a negative unit_cost
- **Rules:** `inherited` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `MachineItemLedgerCreate(machine_id=M1.id, item_id=I1.id, transaction_type="manual_add", quantity=3, unit_cost=Decimal("-1.00"), total_cost=Decimal("7.50"), qty_before=4, qty_after=7, source_type="manual")` (target `schema`; the DAO is not called).

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.errors()[0]["type"] == "greater_than_equal"`.
3. raises: `exc.value.errors()[0]["loc"] == ("unit_cost",)`.
4. nothing written: nothing written.

### MIL-INH-80 — MachineItemLedgerCreate rejects a negative total_cost
- **Rules:** `inherited` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `MachineItemLedgerCreate(machine_id=M1.id, item_id=I1.id, transaction_type="manual_add", quantity=3, unit_cost=Decimal("2.50"), total_cost=Decimal("-1.00"), qty_before=4, qty_after=7, source_type="manual")` (target `schema`; the DAO is not called).

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.errors()[0]["type"] == "greater_than_equal"`.
3. raises: `exc.value.errors()[0]["loc"] == ("total_cost",)`.
4. nothing written: nothing written.

### MIL-INH-81 — MachineItemLedgerCreate accepts zero quantity and costs: the limit is at least 0
- **Rules:** `inherited` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No entry exists in W1.

**When**
- `result = MachineItemLedgerCreate(machine_id=M1.id, item_id=I1.id, transaction_type="manual_add", quantity=0, unit_cost=Decimal("0.00"), total_cost=Decimal("0.00"), qty_before=4, qty_after=7, source_type="manual")` (target `schema`; the DAO is not called).

**Then**
1. returns: `result.quantity == 0`.
2. returns: `result.unit_cost == Decimal("0.00")`.
3. returns: `result.total_cost == Decimal("0.00")`.


## `GET /ledgers/machine/` response schema (`MachineItemLedgerResponse`)

### MIL-RS-01 — a stored row of type "purchase_order" passes and keeps its type
- **Rules:** `GET /ledgers/machine/` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "purchase_order"`.

**When**
- `result = MachineItemLedgerResponse.model_validate(E1)` (target `schema`; the DAO is not called).

**Then**
1. returns: `isinstance(result, MachineItemLedgerResponse)`.
2. returns: `result.transaction_type == "purchase_order"`.

### MIL-RS-02 — a stored row of type "manual_add" passes and keeps its type
- **Rules:** `GET /ledgers/machine/` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "manual_add"`.

**When**
- `result = MachineItemLedgerResponse.model_validate(E1)` (target `schema`; the DAO is not called).

**Then**
1. returns: `isinstance(result, MachineItemLedgerResponse)`.
2. returns: `result.transaction_type == "manual_add"`.

### MIL-RS-03 — a stored row of type "transfer_in" passes and keeps its type
- **Rules:** `GET /ledgers/machine/` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "transfer_in"`.

**When**
- `result = MachineItemLedgerResponse.model_validate(E1)` (target `schema`; the DAO is not called).

**Then**
1. returns: `isinstance(result, MachineItemLedgerResponse)`.
2. returns: `result.transaction_type == "transfer_in"`.

### MIL-RS-04 — a stored row of type "transfer_out" passes and keeps its type
- **Rules:** `GET /ledgers/machine/` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "transfer_out"`.

**When**
- `result = MachineItemLedgerResponse.model_validate(E1)` (target `schema`; the DAO is not called).

**Then**
1. returns: `isinstance(result, MachineItemLedgerResponse)`.
2. returns: `result.transaction_type == "transfer_out"`.

### MIL-RS-05 — a stored row of type "consumption" passes and keeps its type
- **Rules:** `GET /ledgers/machine/` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "consumption"`.

**When**
- `result = MachineItemLedgerResponse.model_validate(E1)` (target `schema`; the DAO is not called).

**Then**
1. returns: `isinstance(result, MachineItemLedgerResponse)`.
2. returns: `result.transaction_type == "consumption"`.

### MIL-RS-06 — a stored row of type "damaged" passes and keeps its type
- **Rules:** `GET /ledgers/machine/` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "damaged"`.

**When**
- `result = MachineItemLedgerResponse.model_validate(E1)` (target `schema`; the DAO is not called).

**Then**
1. returns: `isinstance(result, MachineItemLedgerResponse)`.
2. returns: `result.transaction_type == "damaged"`.

### MIL-RS-07 — a stored row of type "inventory_adjustment" passes and keeps its type
- **Rules:** `GET /ledgers/machine/` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "inventory_adjustment"`.

**When**
- `result = MachineItemLedgerResponse.model_validate(E1)` (target `schema`; the DAO is not called).

**Then**
1. returns: `isinstance(result, MachineItemLedgerResponse)`.
2. returns: `result.transaction_type == "inventory_adjustment"`.

### MIL-RS-08 — a stored row of type "cost_adjustment" passes and keeps its type
- **Rules:** `GET /ledgers/machine/` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "cost_adjustment"`.

**When**
- `result = MachineItemLedgerResponse.model_validate(E1)` (target `schema`; the DAO is not called).

**Then**
1. returns: `isinstance(result, MachineItemLedgerResponse)`.
2. returns: `result.transaction_type == "cost_adjustment"`.

### MIL-RS-09 — a stored row of type "purchase_return" passes and keeps its type
- **Rules:** `GET /ledgers/machine/` R1
- **Kind:** bug
- **Expect:** xfail BUG-990
- **Fails today on:** Then 1 (the call raises ValidationError: string_pattern_mismatch on transaction_type)

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "purchase_return"`.

**When**
- `result = MachineItemLedgerResponse.model_validate(E1)` (target `schema`; the DAO is not called).

**Then**
1. returns: `isinstance(result, MachineItemLedgerResponse)`.
2. returns: `result.transaction_type == "purchase_return"`.

### MIL-RS-10 — a stored row of type "consumption_reversal" passes and keeps its type
- **Rules:** `GET /ledgers/machine/` R1
- **Kind:** bug
- **Expect:** xfail BUG-990
- **Fails today on:** Then 1 (the call raises ValidationError: string_pattern_mismatch on transaction_type)

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "consumption_reversal"`.

**When**
- `result = MachineItemLedgerResponse.model_validate(E1)` (target `schema`; the DAO is not called).

**Then**
1. returns: `isinstance(result, MachineItemLedgerResponse)`.
2. returns: `result.transaction_type == "consumption_reversal"`.

### MIL-RS-11 — a stored row of type "work_order_install" passes and keeps its type
- **Rules:** `GET /ledgers/machine/` R1
- **Kind:** bug
- **Expect:** xfail BUG-990
- **Fails today on:** Then 1 (the call raises ValidationError: string_pattern_mismatch on transaction_type)

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "work_order_install"`.

**When**
- `result = MachineItemLedgerResponse.model_validate(E1)` (target `schema`; the DAO is not called).

**Then**
1. returns: `isinstance(result, MachineItemLedgerResponse)`.
2. returns: `result.transaction_type == "work_order_install"`.

### MIL-RS-12 — a stored row of type "work_order_replace_out" passes and keeps its type
- **Rules:** `GET /ledgers/machine/` R1
- **Kind:** bug
- **Expect:** xfail BUG-990
- **Fails today on:** Then 1 (the call raises ValidationError: string_pattern_mismatch on transaction_type)

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "work_order_replace_out"`.

**When**
- `result = MachineItemLedgerResponse.model_validate(E1)` (target `schema`; the DAO is not called).

**Then**
1. returns: `isinstance(result, MachineItemLedgerResponse)`.
2. returns: `result.transaction_type == "work_order_replace_out"`.

### MIL-RS-13 — a stored row of type "work_order_replace_in" passes and keeps its type
- **Rules:** `GET /ledgers/machine/` R1
- **Kind:** bug
- **Expect:** xfail BUG-990
- **Fails today on:** Then 1 (the call raises ValidationError: string_pattern_mismatch on transaction_type)

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "work_order_replace_in"`.

**When**
- `result = MachineItemLedgerResponse.model_validate(E1)` (target `schema`; the DAO is not called).

**Then**
1. returns: `isinstance(result, MachineItemLedgerResponse)`.
2. returns: `result.transaction_type == "work_order_replace_in"`.

### MIL-RS-14 — a stored row of type "work_order_borrow_returned" passes and keeps its type
- **Rules:** `GET /ledgers/machine/` R1
- **Kind:** bug
- **Expect:** xfail BUG-990
- **Fails today on:** Then 1 (the call raises ValidationError: string_pattern_mismatch on transaction_type)

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "work_order_borrow_returned"`.

**When**
- `result = MachineItemLedgerResponse.model_validate(E1)` (target `schema`; the DAO is not called).

**Then**
1. returns: `isinstance(result, MachineItemLedgerResponse)`.
2. returns: `result.transaction_type == "work_order_borrow_returned"`.

### MIL-RS-15 — a stored row of type "sale" passes and keeps its type
- **Rules:** `GET /ledgers/machine/` R1
- **Kind:** bug
- **Expect:** xfail BUG-990
- **Fails today on:** Then 1 (the call raises ValidationError: string_pattern_mismatch on transaction_type)

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "sale"`.

**When**
- `result = MachineItemLedgerResponse.model_validate(E1)` (target `schema`; the DAO is not called).

**Then**
1. returns: `isinstance(result, MachineItemLedgerResponse)`.
2. returns: `result.transaction_type == "sale"`.

### MIL-RS-16 — a stored negative quantity is rejected
- **Rules:** `GET /ledgers/machine/` R1a
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `quantity -1`.

**When**
- `result = MachineItemLedgerResponse.model_validate(E1)` (target `schema`; the DAO is not called).

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.errors()[0]["type"] == "greater_than_equal"`.
3. raises: `exc.value.errors()[0]["loc"] == ("quantity",)`.
4. nothing written: nothing written.
5. unchanged: unchanged(E1).

### MIL-RS-17 — a stored negative unit_cost is rejected
- **Rules:** `GET /ledgers/machine/` R1a
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `unit_cost Decimal("-2.00")`.

**When**
- `result = MachineItemLedgerResponse.model_validate(E1)` (target `schema`; the DAO is not called).

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.errors()[0]["type"] == "greater_than_equal"`.
3. raises: `exc.value.errors()[0]["loc"] == ("unit_cost",)`.
4. nothing written: nothing written.
5. unchanged: unchanged(E1).

### MIL-RS-18 — a stored negative total_cost is rejected
- **Rules:** `GET /ledgers/machine/` R1a
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `total_cost Decimal("-2.00")`.

**When**
- `result = MachineItemLedgerResponse.model_validate(E1)` (target `schema`; the DAO is not called).

**Then**
1. raises: `ValidationError`.
2. raises: `exc.value.errors()[0]["type"] == "greater_than_equal"`.
3. raises: `exc.value.errors()[0]["loc"] == ("total_cost",)`.
4. nothing written: nothing written.
5. unchanged: unchanged(E1).

### MIL-RS-19 — zero quantity and costs pass: the limit is at least 0
- **Rules:** `GET /ledgers/machine/` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `quantity 0`, `unit_cost Decimal("0.00")`, `total_cost Decimal("0.00")`.

**When**
- `result = MachineItemLedgerResponse.model_validate(E1)` (target `schema`; the DAO is not called).

**Then**
1. returns: `result.quantity == 0`.
2. returns: `result.unit_cost == Decimal("0.00")`.
3. returns: `result.total_cost == Decimal("0.00")`.

### MIL-RS-20 — a negative qty_after passes
- **Rules:** `GET /ledgers/machine/` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after -3`.

**When**
- `result = MachineItemLedgerResponse.model_validate(E1)` (target `schema`; the DAO is not called).

**Then**
1. returns: `result.qty_after == -3`.

### MIL-RS-21 — a negative qty_before passes
- **Rules:** `GET /ledgers/machine/` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_before -3`.

**When**
- `result = MachineItemLedgerResponse.model_validate(E1)` (target `schema`; the DAO is not called).

**Then**
1. returns: `result.qty_before == -3`.

### MIL-RS-22 — a negative value_after passes
- **Rules:** `GET /ledgers/machine/` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `value_after Decimal("-12.50")`.

**When**
- `result = MachineItemLedgerResponse.model_validate(E1)` (target `schema`; the DAO is not called).

**Then**
1. returns: `result.value_after == Decimal("-12.50")`.

### MIL-RS-23 — a negative avg_price_after passes
- **Rules:** `GET /ledgers/machine/` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `avg_price_after Decimal("-1.25")`.

**When**
- `result = MachineItemLedgerResponse.model_validate(E1)` (target `schema`; the DAO is not called).

**Then**
1. returns: `result.avg_price_after == Decimal("-1.25")`.

### MIL-RS-24 — any source_type passes
- **Rules:** `GET /ledgers/machine/` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `source_type "not a real source"`.

**When**
- `result = MachineItemLedgerResponse.model_validate(E1)` (target `schema`; the DAO is not called).

**Then**
1. returns: `result.source_type == "not a real source"`.

### MIL-RS-25 — the response carries the required fields read from the row and has no order_type
- **Rules:** `GET /ledgers/machine/` R1a
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = MachineItemLedgerResponse.model_validate(E1)` (target `schema`; the DAO is not called).

**Then**
1. returns: `result.id == E1.id`.
2. returns: `result.workspace_id == W1.id`.
3. returns: `result.performed_by == U1.id`.
4. returns: `result.performed_at == T1`.
5. returns: `result.machine_id == M1.id`, `result.item_id == I1.id`.
6. returns: `not hasattr(result, "order_type")`.

### MIL-RS-26 — the other ten fields are read from the row
- **Rules:** `GET /ledgers/machine/` R1a
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `value_before Decimal("7.00")`, `avg_price_before Decimal("1.75")`, `source_id 77`, `order_id 88`, `notes "Counted"`, `transfer_source_type "machine"`, `transfer_source_id 11`, `transfer_destination_type "storage"`, `transfer_destination_id 12`.
2. `E1.invoice_id = 99` (pending, not flushed: the column has a foreign key, and `model_validate` reads the attribute).

**When**
- `result = MachineItemLedgerResponse.model_validate(E1)` (target `schema`; the DAO is not called).

**Then**
1. returns: `result.value_before == Decimal("7.00")`.
2. returns: `result.avg_price_before == Decimal("1.75")`.
3. returns: `result.source_id == 77`.
4. returns: `result.order_id == 88`.
5. returns: `result.invoice_id == 99`.
6. returns: `result.notes == "Counted"`.
7. returns: `result.transfer_source_type == "machine"`.
8. returns: `result.transfer_source_id == 11`.
9. returns: `result.transfer_destination_type == "storage"`.
10. returns: `result.transfer_destination_id == 12`.

### MIL-RS-27 — a negative value_before passes
- **Rules:** `GET /ledgers/machine/` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `value_before Decimal("-12.50")`.

**When**
- `result = MachineItemLedgerResponse.model_validate(E1)` (target `schema`; the DAO is not called).

**Then**
1. returns: `result.value_before == Decimal("-12.50")`.

### MIL-RS-28 — a negative avg_price_before passes
- **Rules:** `GET /ledgers/machine/` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `avg_price_before Decimal("-1.25")`.

**When**
- `result = MachineItemLedgerResponse.model_validate(E1)` (target `schema`; the DAO is not called).

**Then**
1. returns: `result.avg_price_before == Decimal("-1.25")`.


## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `GET /ledgers/machine/` R2 [BUG-991] — an `end_date` with no time covers the whole day; one with a time stays exact (spec: integration-only) | HTTP / integration tests of `GET /ledgers/machine/`, `app/api/v1/endpoints/ledgers.py` | Entries at 29 Sep 10:00 and 30 Sep 10:00: `start_date=2026-09-30&end_date=2026-09-30` returns the 30 Sep entry, `2026-09-29`…`2026-09-30` returns both, `…T23:59:59` stays exact. Here only the DAO half is pinned (it compares what it is given): MIL-DR-07, DR-08. |
| `GET /ledgers/machine/` R1 [BUG-990], Errors note — a page holding such a row answers 200, not 500 (`ResponseValidationError`) | HTTP / integration tests of `GET /ledgers/machine/` | One request with a page holding a `work_order_install` row. Here the schema is tested directly (MIL-RS-*), as the spec says. |
| BUG-993 / FU-1 — a manual change keeps the average cost | machine item manager spec (`MachineItemManager._write_ledger_entry`) | **Money, owner's ruling.** No rule of this DAO. `unit_cost`, `avg_price_*` = latest average, `total_cost` = |change| × average, `value_*` = qty × average, first entry 0.00. Rounding and an empty `avg_price_after` are open there. |
| FU-6 — all code that rounds money follows half up (the stock movements' `quantize` does not yet); what the API answers for an over-limit amount | **Owner answered 2026-10-30: half up, BUG-1040.** Machine item manager and stock-movement specs | The database already rounds this way, so inherited R1a, R1b stand. |
| BUG-645 caller — `GET /ledgers/reports/user-transactions/{user_id}/` answers instead of 500 | ledger manager spec / endpoint | Here only the DAO method (MIL-PF-*). |
| BUG-341 — `get_by_date_range` with a transaction type and each bound alone; `item_id` passed by `get_item_movement_summary` | ledger manager spec | `get_by_date_range` R4 changes with that fix; MIL-DR-23, DR-24 pin today's `None` behavior (Spec gap 10). |
| BUG-642 — `limit >= 1` at `GET /ledgers/machine/`; `skip >= 0`, `limit <= 100` enforced by the endpoint | ledger endpoints (HR-7) | Here the DAO's own behavior: `limit=0` → `[]`, negative → `DataError`, `limit=101` uncapped. |
| BUG-680 — "already posted?" guards read this table directly | `to_inventory`, `po_return_inventory`, `po_receive_inventory` specs | **Orders / stock.** Not through this DAO; no unique index backs them. |
| BUG-661 — row lock on `machine_items` in the writers (HR-10) | stock-movement / machine item writers | **Stock.** Not in this file. |
| FU-2 — BUG-991 on the other ledger endpoints | ledger manager / endpoints | `/ledgers/inventory/`, `/ledgers/attachments/`, the two report endpoints. |
| FU-3 — same eight-type pattern on the project component ledger response | project component item ledger spec | Latent; no card here. |
| FU-4, Q5 — `order_id`, `order_type`, `invoice_id` never written; `get_by_order` to remove | model review / dead-code checklist | No card for `get_by_order` (Not specified). |
| FU-5 — hard delete of a profile or workspace | profile / workspace deletion, if ever added | The failure itself is pinned here (inherited R5 cards). |
| Inherited generic behavior of `get`, `get_multi`, `create`, `update`, `remove`, `get_by_workspace`, `get_by_id_and_workspace` | `tests/unit/dao/base.spec.md` / `base.cases.md` | Only what this model changes has cards. |

## Spec gaps
| # | Status | Where | What was missing, or is missing | Effect on the cards |
|---|---|---|---|---|
| 1 | Closed (G1) | inherited R2 | Fields of `MachineItemLedgerCreate`. | MIL-INH-07's assumed arguments are the required fields. No change. |
| 2 | Closed (G2) | `GET /ledgers/machine/` R1a | Other fields and limits of the response. | MIL-RS-16 … RS-25. |
| 3 | Closed (G3); money point answered as FU-6, half up | inherited R1a, R1b, Errors rows 5, 6 | Third decimal; limits and their errors. | MIL-INH-51 … INH-76, INH-34, INH-35. |
| 4 | Closed (G4), except gap 12 | `get_by_performer` R3 | Parent state; writes nothing. | MIL-PF-23 … PF-26. |
| 5 | Closed (G5) | `get_by_performer` R4 | `performed_by=None`. | MIL-PF-27. |
| 6 | Closed (G6) | Notes | The keyword-only note stays a note. | No card. |
| 7 | Closed (G7) | inherited Errors | Loose checks accepted. | No change. |
| 8 | Closed (G8) | inherited R1 | "Close to now" = within 5 minutes. | No change. |
| 9 | Closed (G9) | `get_by_date_range` R3a | An entry that wrongly appears; a naive bound next to an aware one. | MIL-DR-19 stands as it was. MIL-DR-57 … DR-61. |
| 10 | Closed (G10) | "Existing bugs" line BUG-341 | Stale rule numbers, now R4 and Errors row 1. | No change. |
| 11 | Closed (G11) | inherited R2 | The input schema's pattern is not specified. | No card, as designed. |
| 12 | Closed (verify report) | `get_by_performer` R3, last clause of the first sentence | "The performer's own profile state is not consulted": `Profile` has no state column, so there is nothing to test today. | No card. |
| 13 | Closed (decided under delegation, not the owner's answer) | `GET /ledgers/machine/` R1 and R1a | R1 says "one row never fails a page"; R1a says a stored negative `quantity`, `unit_cost` or `total_cost` raises `ValidationError`. Decided: R1a stands, since no writer stores a negative value. | MIL-RS-16 … RS-18 stand. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_item` | R1 | MIL-IT-01, MIL-IT-02, MIL-IT-03, MIL-IT-04, MIL-IT-05, MIL-IT-06 |
| `get_by_item` | R2 | MIL-IT-07 |
| `get_by_item` | R3 | MIL-IT-08, MIL-IT-09 |
| `get_by_item` | R9 | MIL-IT-10, MIL-IT-11 |
| `get_by_item` | R4 | MIL-IT-11, MIL-IT-25 |
| `get_by_item` | Returns | MIL-IT-11 |
| `get_by_item` | R5 | MIL-IT-12, MIL-IT-13, MIL-IT-14, MIL-IT-15, MIL-IT-19, MIL-IT-20, MIL-IT-21, MIL-IT-22 |
| `get_by_item` | R6 | MIL-IT-16, MIL-IT-17, MIL-IT-18 |
| `get_by_item` | R7 | MIL-IT-23, MIL-IT-24 |
| `get_by_item` | Errors row 1 | MIL-IT-23 |
| `get_by_item` | Errors row 2 | MIL-IT-24 |
| `get_by_item` | R4a | MIL-IT-26, MIL-IT-27 |
| `get_by_item` | R8 | MIL-IT-28, MIL-IT-29, MIL-IT-30 |
| `get_by_machine_and_item` | R1 | MIL-MI-01, MIL-MI-02, MIL-MI-03, MIL-MI-04, MIL-MI-05, MIL-MI-06, MIL-MI-07, MIL-MI-08 |
| `get_by_machine_and_item` | R2 | MIL-MI-09, MIL-MI-10 |
| `get_by_machine_and_item` | R3 | MIL-MI-11, MIL-MI-25 |
| `get_by_machine_and_item` | R6 | MIL-MI-11, MIL-MI-31 |
| `get_by_machine_and_item` | Returns | MIL-MI-11 |
| `get_by_machine_and_item` | R4 | MIL-MI-12, MIL-MI-13, MIL-MI-14, MIL-MI-15, MIL-MI-16, MIL-MI-17, MIL-MI-18, MIL-MI-19, MIL-MI-20, MIL-MI-21, MIL-MI-22, MIL-MI-23, MIL-MI-24 |
| `get_by_machine_and_item` | Errors (as get_by_item) | MIL-MI-23, MIL-MI-24 |
| `get_by_machine_and_item` | R3a | MIL-MI-26, MIL-MI-27 |
| `get_by_machine_and_item` | R5 | MIL-MI-28, MIL-MI-29, MIL-MI-30 |
| `get_by_transaction_type` | R1 | MIL-TT-01, MIL-TT-02, MIL-TT-03, MIL-TT-04, MIL-TT-05, MIL-TT-06, MIL-TT-07, MIL-TT-08, MIL-TT-09, MIL-TT-10, MIL-TT-11, MIL-TT-12, MIL-TT-13, MIL-TT-14, MIL-TT-15, MIL-TT-16, MIL-TT-17, MIL-TT-18, MIL-TT-19, MIL-TT-20, MIL-TT-21, MIL-TT-22, MIL-TT-25, MIL-TT-26, MIL-TT-27 |
| `get_by_transaction_type` | R2 | MIL-TT-23, MIL-TT-24 |
| `get_by_transaction_type` | R3 | MIL-TT-28 |
| `get_by_transaction_type` | R4 | MIL-TT-29, MIL-TT-30, MIL-TT-31, MIL-TT-32, MIL-TT-33 |
| `get_by_transaction_type` | R4a | MIL-TT-34, MIL-TT-35 |
| `get_by_transaction_type` | R5 | MIL-TT-36, MIL-TT-50 |
| `get_by_transaction_type` | R8 | MIL-TT-36, MIL-TT-58 |
| `get_by_transaction_type` | Returns | MIL-TT-36 |
| `get_by_transaction_type` | R6 | MIL-TT-37, MIL-TT-38, MIL-TT-39, MIL-TT-40, MIL-TT-41, MIL-TT-42, MIL-TT-43, MIL-TT-44, MIL-TT-45, MIL-TT-46, MIL-TT-47, MIL-TT-48, MIL-TT-49 |
| `get_by_transaction_type` | Errors (as get_by_item) | MIL-TT-48, MIL-TT-49 |
| `get_by_transaction_type` | R5a | MIL-TT-51, MIL-TT-52 |
| `get_by_transaction_type` | R7 | MIL-TT-53, MIL-TT-54, MIL-TT-55, MIL-TT-56, MIL-TT-57 |
| `get_by_date_range` | R1 | MIL-DR-01, MIL-DR-02, MIL-DR-03, MIL-DR-04, MIL-DR-05, MIL-DR-06, MIL-DR-07, MIL-DR-08, MIL-DR-25, MIL-DR-26, MIL-DR-27, MIL-DR-32 |
| `get_by_date_range` | R2 | MIL-DR-09, MIL-DR-10, MIL-DR-11 |
| `get_by_date_range` | R3 | MIL-DR-12, MIL-DR-13, MIL-DR-14, MIL-DR-15 |
| `get_by_date_range` | R3a | MIL-DR-16, MIL-DR-17, MIL-DR-18, MIL-DR-19, MIL-DR-20, MIL-DR-21, MIL-DR-22, MIL-DR-57, MIL-DR-58, MIL-DR-59, MIL-DR-60, MIL-DR-61 |
| `get_by_date_range` | R4 | MIL-DR-23, MIL-DR-24 |
| `get_by_date_range` | Errors row 1 | MIL-DR-23, MIL-DR-24 |
| `get_by_date_range` | R6 | MIL-DR-28, MIL-DR-29, MIL-DR-30, MIL-DR-31, MIL-DR-32, MIL-DR-33, MIL-DR-34 |
| `get_by_date_range` | R5 | MIL-DR-35, MIL-DR-49 |
| `get_by_date_range` | R8 | MIL-DR-35, MIL-DR-62 |
| `get_by_date_range` | Returns | MIL-DR-35 |
| `get_by_date_range` | R6a | MIL-DR-36, MIL-DR-37, MIL-DR-38, MIL-DR-39, MIL-DR-40, MIL-DR-41, MIL-DR-42, MIL-DR-43, MIL-DR-44, MIL-DR-45, MIL-DR-46, MIL-DR-47, MIL-DR-48 |
| `get_by_date_range` | Errors row 2 | MIL-DR-47, MIL-DR-48 |
| `get_by_date_range` | R5a | MIL-DR-50, MIL-DR-51 |
| `get_by_date_range` | R7 | MIL-DR-52, MIL-DR-53, MIL-DR-54, MIL-DR-55, MIL-DR-56 |
| `get_by_machine` | R1 | MIL-MA-01, MIL-MA-02, MIL-MA-03, MIL-MA-04, MIL-MA-05 |
| `get_by_machine` | R2 | MIL-MA-06, MIL-MA-07, MIL-MA-08 |
| `get_by_machine` | R3 | MIL-MA-09, MIL-MA-23 |
| `get_by_machine` | R6 | MIL-MA-09, MIL-MA-29 |
| `get_by_machine` | Returns | MIL-MA-09 |
| `get_by_machine` | R4 | MIL-MA-10, MIL-MA-11, MIL-MA-12, MIL-MA-13, MIL-MA-14, MIL-MA-15, MIL-MA-16, MIL-MA-17, MIL-MA-18, MIL-MA-19, MIL-MA-20, MIL-MA-21, MIL-MA-22 |
| `get_by_machine` | Errors (as get_by_item) | MIL-MA-21, MIL-MA-22 |
| `get_by_machine` | R3a | MIL-MA-24, MIL-MA-25 |
| `get_by_machine` | R5 | MIL-MA-26, MIL-MA-27, MIL-MA-28 |
| `calculate_balance` | R1 | MIL-BAL-01, MIL-BAL-14, MIL-BAL-16, MIL-BAL-18, MIL-BAL-20, MIL-BAL-21, MIL-BAL-22, MIL-BAL-23, MIL-BAL-24 |
| `calculate_balance` | Returns | MIL-BAL-01, MIL-BAL-02 |
| `calculate_balance` | R2 | MIL-BAL-02, MIL-BAL-03, MIL-BAL-04, MIL-BAL-05, MIL-BAL-06, MIL-BAL-09, MIL-BAL-10 |
| `calculate_balance` | R7 | MIL-BAL-02, MIL-BAL-28, MIL-BAL-29 |
| `calculate_balance` | R3 | MIL-BAL-07, MIL-BAL-08, MIL-BAL-09 |
| `calculate_balance` | R4 | MIL-BAL-11, MIL-BAL-12 |
| `calculate_balance` | R5 | MIL-BAL-13, MIL-BAL-14, MIL-BAL-15, MIL-BAL-16, MIL-BAL-17, MIL-BAL-18, MIL-BAL-19 |
| `calculate_balance` | R6 | MIL-BAL-25, MIL-BAL-26, MIL-BAL-27 |
| `get_latest_entry` | R1 | MIL-LE-01, MIL-LE-18, MIL-LE-19, MIL-LE-20 |
| `get_latest_entry` | R2 | MIL-LE-02, MIL-LE-03, MIL-LE-04, MIL-LE-05, MIL-LE-06, MIL-LE-08 |
| `get_latest_entry` | R6 | MIL-LE-02, MIL-LE-24, MIL-LE-25 |
| `get_latest_entry` | Returns | MIL-LE-02 |
| `get_latest_entry` | R3 | MIL-LE-07, MIL-LE-09, MIL-LE-10 |
| `get_latest_entry` | R4 | MIL-LE-11, MIL-LE-12, MIL-LE-13, MIL-LE-14, MIL-LE-15, MIL-LE-16, MIL-LE-17 |
| `get_latest_entry` | R5 | MIL-LE-21, MIL-LE-22, MIL-LE-23 |
| `get_by_performer` | R1 | MIL-PF-01, MIL-PF-02, MIL-PF-03, MIL-PF-04, MIL-PF-05, MIL-PF-06, MIL-PF-07 |
| `get_by_performer` | R2 | MIL-PF-07, MIL-PF-08, MIL-PF-09, MIL-PF-10, MIL-PF-11, MIL-PF-12, MIL-PF-13, MIL-PF-14, MIL-PF-15, MIL-PF-16, MIL-PF-17, MIL-PF-18, MIL-PF-19, MIL-PF-20, MIL-PF-21, MIL-PF-22 |
| `get_by_performer` | Errors (as get_by_item) | MIL-PF-19, MIL-PF-20 |
| `inherited` | R1 | MIL-INH-01, MIL-INH-02, MIL-INH-03, MIL-INH-04, MIL-INH-05, MIL-INH-06 |
| `inherited` | R2 | MIL-INH-07, MIL-INH-77, MIL-INH-78, MIL-INH-79, MIL-INH-80, MIL-INH-81 |
| `inherited` | Errors row 1 | MIL-INH-07, MIL-INH-13, MIL-INH-14, MIL-INH-15, MIL-INH-16, MIL-INH-17, MIL-INH-18, MIL-INH-19, MIL-INH-20, MIL-INH-21, MIL-INH-22, MIL-INH-23, MIL-INH-77 |
| `inherited` | R3 | MIL-INH-08, MIL-INH-09, MIL-INH-10, MIL-INH-11, MIL-INH-12, MIL-INH-13, MIL-INH-14, MIL-INH-15, MIL-INH-16, MIL-INH-17, MIL-INH-18, MIL-INH-19, MIL-INH-20, MIL-INH-21, MIL-INH-22, MIL-INH-23 |
| `inherited` | Errors row 2 | MIL-INH-08, MIL-INH-09, MIL-INH-10, MIL-INH-11, MIL-INH-12 |
| `inherited` | R4 | MIL-INH-24, MIL-INH-25, MIL-INH-26, MIL-INH-27, MIL-INH-28, MIL-INH-29, MIL-INH-30, MIL-INH-31, MIL-INH-32, MIL-INH-33 |
| `inherited` | R1b | MIL-INH-34, MIL-INH-35, MIL-INH-62, MIL-INH-63, MIL-INH-64, MIL-INH-65, MIL-INH-66, MIL-INH-67, MIL-INH-68, MIL-INH-69, MIL-INH-70, MIL-INH-71, MIL-INH-72, MIL-INH-73, MIL-INH-74, MIL-INH-75, MIL-INH-76 |
| `inherited` | Errors row 5 | MIL-INH-35, MIL-INH-63, MIL-INH-64, MIL-INH-65, MIL-INH-66, MIL-INH-67, MIL-INH-68, MIL-INH-70 |
| `inherited` | R5 | MIL-INH-36, MIL-INH-37, MIL-INH-38 |
| `inherited` | Errors row 3 | MIL-INH-36, MIL-INH-37 |
| `inherited` | Errors row 4 | MIL-INH-38 |
| `inherited` | R6 | MIL-INH-39, MIL-INH-40, MIL-INH-41, MIL-INH-42 |
| `inherited` | R8 | MIL-INH-39, MIL-INH-48, MIL-INH-49, MIL-INH-50 |
| `inherited` | R7 | MIL-INH-43, MIL-INH-44, MIL-INH-45, MIL-INH-46, MIL-INH-47 |
| `GET /ledgers/machine/` | R1 | MIL-RS-01, MIL-RS-02, MIL-RS-03, MIL-RS-04, MIL-RS-05, MIL-RS-06, MIL-RS-07, MIL-RS-08, MIL-RS-09, MIL-RS-10, MIL-RS-11, MIL-RS-12, MIL-RS-13, MIL-RS-14, MIL-RS-15 |
| `get_by_performer` | R3 | MIL-PF-23, MIL-PF-24, MIL-PF-25, MIL-PF-26, MIL-PF-28 |
| `get_by_performer` | R4 | MIL-PF-27 |
| `inherited` | R1a | MIL-INH-51, MIL-INH-52, MIL-INH-53, MIL-INH-54, MIL-INH-55, MIL-INH-56, MIL-INH-57, MIL-INH-58, MIL-INH-59, MIL-INH-60, MIL-INH-61 |
| `inherited` | Errors row 6 | MIL-INH-73, MIL-INH-74, MIL-INH-75, MIL-INH-76 |
| `GET /ledgers/machine/` | R1a | MIL-RS-16, MIL-RS-17, MIL-RS-18, MIL-RS-19, MIL-RS-20, MIL-RS-21, MIL-RS-22, MIL-RS-23, MIL-RS-24, MIL-RS-25, MIL-RS-26, MIL-RS-27, MIL-RS-28 |
| `GET /ledgers/machine/` | R2 [BUG-991] | Deferred (integration-only) |
| `GET /ledgers/machine/` | Errors (none intended; today 500) | Deferred (HTTP) |
| BUG-100 | all rules tagged | MIL-INH-41, MIL-INH-42 |
| BUG-640 | all rules tagged | MIL-IT-26, MIL-IT-27, MIL-MI-26, MIL-MI-27, MIL-TT-51, MIL-TT-52, MIL-DR-50, MIL-DR-51, MIL-MA-24, MIL-MA-25 |
| BUG-641 | all rules tagged | MIL-BAL-11, MIL-BAL-12 |
| BUG-645 | all rules tagged | MIL-PF-01, MIL-PF-02, MIL-PF-03, MIL-PF-04, MIL-PF-05, MIL-PF-06, MIL-PF-07, MIL-PF-08, MIL-PF-09, MIL-PF-10, MIL-PF-11, MIL-PF-12, MIL-PF-13, MIL-PF-14, MIL-PF-15, MIL-PF-16, MIL-PF-17, MIL-PF-18, MIL-PF-19, MIL-PF-20, MIL-PF-21, MIL-PF-22, MIL-PF-23, MIL-PF-24, MIL-PF-25, MIL-PF-26, MIL-PF-27, MIL-PF-28 |
| BUG-664 | all rules tagged | MIL-LE-09, MIL-LE-10 |
| BUG-990 | all rules tagged | MIL-RS-09, MIL-RS-10, MIL-RS-11, MIL-RS-12, MIL-RS-13, MIL-RS-14, MIL-RS-15 |
| BUG-992 | all rules tagged | MIL-DR-16, MIL-DR-17, MIL-DR-18, MIL-DR-19, MIL-DR-57, MIL-DR-58, MIL-DR-59 |
| BUG-991 | `GET /ledgers/machine/` R2 | Deferred |
| BUG-993 | none in this DAO (Q1, FU-1) | Deferred |
