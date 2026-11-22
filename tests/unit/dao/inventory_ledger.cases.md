# Test cases — `app/dao/inventory_ledger.py`

> **Spec:** `tests/unit/dao/inventory_ledger.spec.md` (source commit e48a092)
> **Status:** READY — designed against the **APPROVED** spec (reviewer accepted all answers 2026-10-10: P1, P2 and Q1–Q5 as suggested; no rule ID or rule meaning changed).
> **Counts:** 170 cases · 150 expected-to-pass · 20 expected-to-fail (bugs) · 9 deferred

## Reviewer summary
- **Per callable:** `get_by_workspace` 39 (3 bug) · `get_by_transaction_type` 31 (3 bug) · `get_by_date_range` 30 (3 bug) · `get_by_performer` 20 (1 bug) · `calculate_balance` 16 (9 bug) · `get_latest_entry` 18 (1 bug) · `exists_for_source` 16.
- **Review answers and the cards that rest on them:** P1 / BUG-655 (balance = `qty_after`, `qty_after × avg_price_after`; NULL price gives 0.00) — LED-BAL-08 … BAL-16. P2 / BUG-885 (`0` filters and matches nothing) — LED-W-15, W-18, TT-20, TT-21, DR-19, DR-20. Q3 / Q4 (entries of a soft-deleted factory or a removed item stay listed) — LED-W-35 … W-38, TT-31, DR-30, PF-20. Q5 (single-bucket lookups stay raw) — LED-BAL-07, BAL-14, BAL-15, LE-16, LE-17, EX-14, EX-15. Q1 / Q2 (`get_by_order` and the `get_by_id_and_workspace` override are dead code) — no cards.
- **Notable design choices:**
  - Ties use the spec's recipe exactly: EB (sequence id), then EC with `id HIGH_ID`, then EA (sequence id), all at T1. The failing assertion is the exact intended result (`[EC, EA, EB]`, or `result.id == EC.id`), which today's code never produces under any query plan, so the xfails are strict. What already holds is in pass cards: tied entries are each returned once and stay between the newer and the older entry (LED-W-22, TT-23, DR-22, PF-12); an older entry never wins (LED-LE-07, LE-08 — LE-08 deliberately accepts either tied entry).
  - `calculate_balance`: every card for a bucket that has an entry is an xfail whose call raises today (BUG-655); only the empty-bucket cards pass today (LED-BAL-01 … BAL-07). LED-BAL-13 (BUG-641) is marked `xfail BUG-641, BUG-655`: it fails today on BUG-655 and keeps failing on BUG-641 after that fix.
  - Rows are always inserted in an order different from their time order, so "newest first" cannot pass by accident; LED-LE-02, LE-04 and LE-05 put the newest entry at the middle, lowest and highest id.
  - BUG-885 has one xfail card per filter and per list method (6); `get_by_performer` has no such filter.
  - Cards marked `Author: claude` (5): LED-W-28, LED-W-29, LED-TT-26, LED-DR-25, LED-PF-15 — all are the 101-entry cases (bulk setup in a loop). No mock, patch or savepoint card is needed: nothing is mocked, and the `DataError` cards use the `begin_nested` wrapper defined in Conventions, as in the inventory DAO file.
  - FD (soft-deleted factory) and IR (removed catalog item) are standing rows of every test, so no card has to build them.
  - No cards for the inherited `BaseDAO` methods, the `get_by_id_and_workspace` override or `get_by_order` (Not specified).
- **Needs a decision:** None blocking. Three small points are listed under Spec gaps: the profile "state" in `get_by_performer` R6, missing "changes nothing" rules for three list methods, time-zone-aware datetimes.


## Conventions for this module

**IDs.** `LED` = `app/dao/inventory_ledger.py`. `W` get_by_workspace · `TT` get_by_transaction_type · `DR` get_by_date_range · `PF` get_by_performer · `BAL` calculate_balance · `LE` get_latest_entry · `EX` exists_for_source.

**Actors and fixed values.**
- `dao` = the singleton `inventory_ledger_dao` (`from app.dao.inventory_ledger import inventory_ledger_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- W1, W2 = two `workspaces` rows. U1, U2 = two `profiles` rows.
- STORAGE, DAMAGED, WASTE, SCRAP = the four members of `InventoryTypeEnum` (`app.models.enums`). `InventoryLedger` = `app.models.inventory_ledger.InventoryLedger`.
- MISSING = `999999999`: an id that no row of any table has.
- T1 = `datetime(2026, 1, 1, 9, 0, 0)`, T2 = `datetime(2026, 1, 1, 10, 0, 0)`, T3 = `datetime(2026, 1, 1, 11, 0, 0)`, T4 = `datetime(2026, 1, 1, 12, 0, 0)`, T5 = `datetime(2026, 1, 1, 13, 0, 0)` (all naive).
- HIGH_ID = the greater of (the greatest `inventory_ledger.id` at that moment, 0 if the table is empty) and (`last_value` of the sequence `inventory_ledger_id_seq`), plus `1000000`.

**Externals.** Nothing is mocked and no clock is patched.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so sequence ids rise in that order. A card names, by column name, every column that differs from these defaults.
- These eight rows exist in every test and need no Given line:
  - F1 = `factories` row: `name "Factory One"`, `abbreviation "F1"`, `workspace_id W1.id`, `is_active True`, `is_deleted False`.
  - F2 = the same as F1, but `name "Factory Two"`, `abbreviation "F2"`.
  - F9 = the same as F1, but `name "Factory Nine"`, `abbreviation "F9"`, `workspace_id W2.id`.
  - FD = the same as F1, but `name "Old Plant"`, `abbreviation "OP"`, `is_deleted True` (a soft-deleted factory of W1; `is_active` stays True).
  - I1 = `items` row: `name "Bolt"`, `name_normalized "bolt"`, `unit "pcs"`, `workspace_id W1.id`, `is_active True`.
  - I2 = the same as I1, but `name "Nut"`, `name_normalized "nut"`.
  - I9 = the same as I1, but `workspace_id W2.id`.
  - IR = the same as I1, but `name "Old Gasket"`, `name_normalized "old gasket"`, `is_active False` (a removed catalog item of W1).
- Ledger entries (`inventory_ledger`) exist only if the card's Given lists them.
- **entry** = `inventory_ledger` row: `workspace_id W1.id`, `factory_id F1.id`, `item_id I1.id`, `inventory_type STORAGE`, `transaction_type "manual_add"`, `quantity 1`, `qty_before 0`, `qty_after 5`, `avg_price_after Decimal("2.00")`, `performed_by U1.id`, `source_type None`, `source_id None`, every other nullable column None, sequence `id`. The card always gives `performed_at`; after the word "but" it lists every other column that differs.
- X9 = entry, `performed_at T5`, but `workspace_id W2.id`, `factory_id F9.id`, `item_id I9.id` (so: the other workspace's entry; STORAGE, `transaction_type "manual_add"`, `performed_by U1.id`, no source).

**Named checks.**
- **ids(result)** = `[row.id for row in result]` — a list in the order returned (the order is part of the check).
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken before the call).
- **nothing written** = the numbers of rows in `inventory_ledger`, `factories` and `items` (all workspaces) equal their values before the call.
- `count:` lines count the rows of the named table in all workspaces.
- Prices and values are compared as `Decimal` values (`Decimal("120.00") == Decimal("120")`), never as strings, unless the line itself uses `str(...)`.
- `raises: DataError` = `sqlalchemy.exc.DataError`. Wrap the call: `with pytest.raises(DataError) as exc:` then `with db.begin_nested():` then the call. `InvalidRowCountInLimitClause`, `InvalidRowCountInResultOffsetClause` = classes of `psycopg2.errors`.
- `raises: ArgumentError` = `sqlalchemy.exc.ArgumentError`. Plain `with pytest.raises(ArgumentError) as exc:` around the call — no `begin_nested`; keep using `db` for the remaining checks.
- Further `raises:` lines of the same card are assertions on `exc.value`, written after the `with` block.

**xfail cards.** Write the call and the checks exactly as shown; the harness adds the marker.


## `InventoryLedgerDAO.get_by_workspace`

### LED-W-01 — returns a list of ledger rows, newest first whatever the insertion order
- **Rules:** `get_by_workspace` R2, R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [E2.id, E3.id, E1.id]`.
3. returns: `isinstance(result[0], InventoryLedger)`.

### LED-W-02 — with no filter, entries of every type, factory, item, transaction type and performer are returned
- **Rules:** `get_by_workspace` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `inventory_type DAMAGED`, `factory_id F2.id`.
3. E3 = entry, `performed_at T3`, but `item_id I2.id`, `transaction_type "sale"`, `performed_by None`.
4. E4 = entry, `performed_at T4`, but `inventory_type SCRAP`, `performed_by U2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E4.id, E3.id, E2.id, E1.id]`.

### LED-W-03 — an entry of another workspace is not returned
- **Rules:** `get_by_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. X9.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### LED-W-04 — a call for the other workspace returns only that workspace's entry
- **Rules:** `get_by_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. X9.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [X9.id]`.

### LED-W-05 — another workspace's entry is not returned when its factory id is the filter
- **Rules:** `get_by_workspace` R1, R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. X9.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, factory_id=F9.id)`.

**Then**
1. returns: `result == []`.

### LED-W-06 — another workspace's entry is not returned when its item id is the filter
- **Rules:** `get_by_workspace` R1, R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. X9.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, item_id=I9.id)`.

**Then**
1. returns: `result == []`.

### LED-W-07 — an entry of the other workspace booked in this workspace's factory and item is not returned
- **Rules:** `get_by_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `workspace_id W2.id`. (Same factory F1 and item I1 as E1, other workspace.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, factory_id=F1.id, item_id=I1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### LED-W-08 — an unknown workspace id returns an empty list
- **Rules:** `get_by_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### LED-W-09 — inventory_type filter keeps only that type
- **Rules:** `get_by_workspace` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `inventory_type DAMAGED`.
3. E3 = entry, `performed_at T3`, but `inventory_type SCRAP`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, inventory_type=DAMAGED)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### LED-W-10 — a type with no entries returns an empty list
- **Rules:** `get_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `inventory_type DAMAGED`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, inventory_type=WASTE)`.

**Then**
1. returns: `result == []`.

### LED-W-11 — explicit None for every optional filter applies no filter
- **Rules:** `get_by_workspace` R3, R4, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `inventory_type DAMAGED`, `factory_id F2.id`, `item_id I2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, inventory_type=None, factory_id=None, item_id=None)`.

**Then**
1. returns: `ids(result) == [E2.id, E1.id]`.

### LED-W-12 — factory_id filter keeps only that factory
- **Rules:** `get_by_workspace` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T2`, but `factory_id F2.id`.
2. E2 = entry, `performed_at T1`.
3. E3 = entry, `performed_at T3`, but `factory_id F2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, factory_id=F2.id)`.

**Then**
1. returns: `ids(result) == [E3.id, E1.id]`.

### LED-W-13 — a factory id that does not exist returns an empty list
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, factory_id=MISSING)`.

**Then**
1. returns: `result == []`.

### LED-W-14 — a negative factory id returns an empty list
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, factory_id=-1)`.

**Then**
1. returns: `result == []`.

### LED-W-15 — factory_id 0 filters and returns an empty list
- **Rules:** `get_by_workspace` R4a [BUG-885]
- **Kind:** bug
- **Expect:** xfail BUG-885
- **Fails today on:** Then 1 (factory_id 0 is treated as no filter, so both entries come back)

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `factory_id F2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, factory_id=0)`.

**Then**
1. returns: `result == []`.

### LED-W-16 — item_id filter keeps only that item
- **Rules:** `get_by_workspace` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T2`, but `item_id I2.id`.
2. E2 = entry, `performed_at T1`.
3. E3 = entry, `performed_at T3`, but `item_id I2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, item_id=I2.id)`.

**Then**
1. returns: `ids(result) == [E3.id, E1.id]`.

### LED-W-17 — an item id that does not exist returns an empty list
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, item_id=MISSING)`.

**Then**
1. returns: `result == []`.

### LED-W-18 — item_id 0 filters and returns an empty list
- **Rules:** `get_by_workspace` R5a [BUG-885]
- **Kind:** bug
- **Expect:** xfail BUG-885
- **Fails today on:** Then 1 (item_id 0 is treated as no filter, so both entries come back)

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `item_id I2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, item_id=0)`.

**Then**
1. returns: `result == []`.

### LED-W-19 — type, factory and item filters combine with AND
- **Rules:** `get_by_workspace` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `factory_id F2.id`.
3. E3 = entry, `performed_at T3`, but `inventory_type DAMAGED`.
4. E4 = entry, `performed_at T4`, but `item_id I2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, inventory_type=STORAGE, factory_id=F1.id, item_id=I1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### LED-W-20 — two filters combine with AND and the result stays newest first
- **Rules:** `get_by_workspace` R6, R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`, but `inventory_type DAMAGED`.
4. E4 = entry, `performed_at T4`, but `factory_id F2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, inventory_type=STORAGE, factory_id=F1.id)`.

**Then**
1. returns: `ids(result) == [E2.id, E1.id]`.

### LED-W-21 — entries sharing a performed_at come back greatest id first
- **Rules:** `get_by_workspace` R7a [BUG-640]
- **Kind:** bug
- **Expect:** xfail BUG-640
- **Fails today on:** Then 2 (entries are ordered by performed_at only, so the tied rows come back as [EB, EC, EA] or [EA, EC, EB])

**Given**
1. EB = entry, `performed_at T1`. (Normal sequence id, inserted first.)
2. EC = entry, `performed_at T1`, but `id HIGH_ID`. (Explicit high id, inserted second.)
3. EA = entry, `performed_at T1`. (Normal sequence id, inserted last.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [EC.id, EA.id, EB.id]`.

### LED-W-22 — entries sharing a performed_at are each returned once, between the newer and the older entry
- **Rules:** `get_by_workspace` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.
3. E3 = entry, `performed_at T2`.
4. E4 = entry, `performed_at T3`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `result[0].id == E4.id`.
3. returns: `result[3].id == E1.id`.
4. returns: `sorted(ids(result)) == [E1.id, E2.id, E3.id, E4.id]`.

### LED-W-23 — skip 1 and limit 1 return exactly the second newest entry
- **Rules:** `get_by_workspace` R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E3.id]`.

### LED-W-24 — first window of two
- **Rules:** `get_by_workspace` R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T3`.
2. E2 = entry, `performed_at T1`.
3. E3 = entry, `performed_at T5`.
4. E4 = entry, `performed_at T2`.
5. E5 = entry, `performed_at T4`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=0, limit=2)`.

**Then**
1. returns: `ids(result) == [E3.id, E5.id]`.

### LED-W-25 — second window of two continues without repeat or gap
- **Rules:** `get_by_workspace` R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T3`.
2. E2 = entry, `performed_at T1`.
3. E3 = entry, `performed_at T5`.
4. E4 = entry, `performed_at T2`.
5. E5 = entry, `performed_at T4`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=2, limit=2)`.

**Then**
1. returns: `ids(result) == [E1.id, E4.id]`.

### LED-W-26 — last window is short
- **Rules:** `get_by_workspace` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T3`.
2. E2 = entry, `performed_at T1`.
3. E3 = entry, `performed_at T5`.
4. E4 = entry, `performed_at T2`.
5. E5 = entry, `performed_at T4`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=4, limit=2)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### LED-W-27 — skip and limit are applied after filtering
- **Rules:** `get_by_workspace` R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `factory_id F2.id`.
3. E3 = entry, `performed_at T3`.
4. E4 = entry, `performed_at T4`, but `factory_id F2.id`.
5. E5 = entry, `performed_at T5`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, factory_id=F1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E3.id]`.

### LED-W-28 — default limit returns the 100 newest of 101 entries
- **Rules:** `get_by_workspace` R8
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — bulk setup (a loop over 101 entries) outside the Conventions vocabulary

**Given**
1. 101 entries N1 … N101, inserted in that order; entry Nk (k = 1 … 101) has `performed_at` = `datetime(2026, 1, 1, 0, 0) + timedelta(minutes=k)` and is otherwise the default entry (so N101 is the newest and N1 the oldest).

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `result[0].id == N101.id`.
3. returns: `result[99].id == N2.id`.
4. returns: `N1.id not in ids(result)`.

### LED-W-29 — an explicit limit of 101 returns all 101 entries
- **Rules:** `get_by_workspace` R8
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — bulk setup (a loop over 101 entries) outside the Conventions vocabulary

**Given**
1. 101 entries N1 … N101, inserted in that order; entry Nk (k = 1 … 101) has `performed_at` = `datetime(2026, 1, 1, 0, 0) + timedelta(minutes=k)` and is otherwise the default entry (so N101 is the newest and N1 the oldest).

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=101)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `result[0].id == N101.id`.
3. returns: `result[100].id == N1.id`.

### LED-W-30 — limit 0 returns an empty list
- **Rules:** `get_by_workspace` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### LED-W-31 — skip equal to the number of matching entries returns an empty list
- **Rules:** `get_by_workspace` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### LED-W-32 — skip one below the number of matching entries returns the oldest entry
- **Rules:** `get_by_workspace` R9, R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### LED-W-33 — negative limit is rejected by the database and nothing changes
- **Rules:** `get_by_workspace` R10, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `dao.get_by_workspace(db, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `exc.value.orig.pgcode == "2201W"`.
4. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.
6. unchanged: unchanged(E1).

### LED-W-34 — negative skip is rejected by the database and nothing changes
- **Rules:** `get_by_workspace` R10, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `dao.get_by_workspace(db, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `exc.value.orig.pgcode == "2201X"`.
4. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.
6. unchanged: unchanged(E1).

### LED-W-35 — an entry booked in a soft-deleted factory is listed like any other
- **Rules:** `get_by_workspace` R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `factory_id FD.id`. (FD is the soft-deleted factory.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E2.id, E1.id]`.

### LED-W-36 — the id of a soft-deleted factory works as the factory filter
- **Rules:** `get_by_workspace` R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `factory_id FD.id`. (FD is the soft-deleted factory.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, factory_id=FD.id)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### LED-W-37 — an entry of a removed catalog item is listed like any other
- **Rules:** `get_by_workspace` R12
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `item_id IR.id`. (IR is the removed catalog item.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E2.id, E1.id]`.

### LED-W-38 — the id of a removed catalog item works as the item filter
- **Rules:** `get_by_workspace` R12
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `item_id IR.id`. (IR is the removed catalog item.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, item_id=IR.id)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### LED-W-39 — listing changes nothing in the database
- **Rules:** `get_by_workspace` R13
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 20`, `avg_price_after Decimal("6.00")`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. nothing written: nothing written.
3. unchanged: unchanged(E1).
4. re-read E1: `qty_after == 20`, `performed_at == T1`.
5. re-read E1: `avg_price_after == Decimal("6.00")`.
6. count: `inventory_ledger` has exactly 1 row.


## `InventoryLedgerDAO.get_by_transaction_type`

### LED-TT-01 — returns only the entries of that transaction type, newest first
- **Rules:** `get_by_transaction_type` R1, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.
4. E4 = entry, `performed_at T4`, but `transaction_type "sale"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [E2.id, E3.id, E1.id]`.
3. returns: `isinstance(result[0], InventoryLedger)`.

### LED-TT-02 — the other transaction type returns only its own entry
- **Rules:** `get_by_transaction_type` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `transaction_type "sale"`.
3. E3 = entry, `performed_at T3`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="sale", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### LED-TT-03 — the transaction type is compared case-sensitively
- **Rules:** `get_by_transaction_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `transaction_type "sale"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="MANUAL_ADD", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### LED-TT-04 — a trailing space in the transaction type is not trimmed
- **Rules:** `get_by_transaction_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `transaction_type "sale"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add ", workspace_id=W1.id)`. The text ends with one space.

**Then**
1. returns: `result == []`.

### LED-TT-05 — a percent sign in the transaction type is an ordinary character
- **Rules:** `get_by_transaction_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `transaction_type "manual%"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual%", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### LED-TT-06 — an underscore in the transaction type is an ordinary character
- **Rules:** `get_by_transaction_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `transaction_type "manual_ad_"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_ad_", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### LED-TT-07 — an unknown transaction type returns an empty list
- **Rules:** `get_by_transaction_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `transaction_type "sale"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_out", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### LED-TT-08 — an empty transaction type returns an empty list
- **Rules:** `get_by_transaction_type` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `transaction_type "sale"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### LED-TT-09 — transaction type None returns an empty list
- **Rules:** `get_by_transaction_type` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `transaction_type "sale"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type=None, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### LED-TT-10 — an entry of that type in another workspace is not returned
- **Rules:** `get_by_transaction_type` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. X9.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### LED-TT-11 — a call for the other workspace returns only that workspace's entry
- **Rules:** `get_by_transaction_type` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. X9.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [X9.id]`.

### LED-TT-12 — an unknown workspace id returns an empty list
- **Rules:** `get_by_transaction_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### LED-TT-13 — inventory_type filter narrows the entries of that transaction type
- **Rules:** `get_by_transaction_type` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `inventory_type DAMAGED`.
3. E3 = entry, `performed_at T3`, but `inventory_type DAMAGED`, `transaction_type "sale"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, inventory_type=DAMAGED)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### LED-TT-14 — factory_id filter narrows the entries of that transaction type
- **Rules:** `get_by_transaction_type` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `factory_id F2.id`.
3. E3 = entry, `performed_at T3`, but `factory_id F2.id`, `transaction_type "sale"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, factory_id=F2.id)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### LED-TT-15 — item_id filter narrows the entries of that transaction type
- **Rules:** `get_by_transaction_type` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `item_id I2.id`.
3. E3 = entry, `performed_at T3`, but `item_id I2.id`, `transaction_type "sale"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, item_id=I2.id)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### LED-TT-16 — type, factory and item filters combine with the transaction type with AND
- **Rules:** `get_by_transaction_type` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `factory_id F2.id`.
3. E3 = entry, `performed_at T3`, but `inventory_type DAMAGED`.
4. E4 = entry, `performed_at T4`, but `item_id I2.id`.
5. E5 = entry, `performed_at T5`, but `transaction_type "sale"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, inventory_type=STORAGE, factory_id=F1.id, item_id=I1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### LED-TT-17 — explicit None for every optional filter applies no filter
- **Rules:** `get_by_transaction_type` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `inventory_type DAMAGED`, `factory_id F2.id`, `item_id I2.id`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, inventory_type=None, factory_id=None, item_id=None)`.

**Then**
1. returns: `ids(result) == [E2.id, E1.id]`.

### LED-TT-18 — a factory id that does not exist returns an empty list
- **Rules:** `get_by_transaction_type` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, factory_id=MISSING)`.

**Then**
1. returns: `result == []`.

### LED-TT-19 — an item id that does not exist returns an empty list
- **Rules:** `get_by_transaction_type` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, item_id=MISSING)`.

**Then**
1. returns: `result == []`.

### LED-TT-20 — factory_id 0 filters and returns an empty list
- **Rules:** `get_by_transaction_type` R3a [BUG-885]
- **Kind:** bug
- **Expect:** xfail BUG-885
- **Fails today on:** Then 1 (factory_id 0 is treated as no filter, so both entries come back)

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `factory_id F2.id`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, factory_id=0)`.

**Then**
1. returns: `result == []`.

### LED-TT-21 — item_id 0 filters and returns an empty list
- **Rules:** `get_by_transaction_type` R3a [BUG-885]
- **Kind:** bug
- **Expect:** xfail BUG-885
- **Fails today on:** Then 1 (item_id 0 is treated as no filter, so both entries come back)

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `item_id I2.id`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, item_id=0)`.

**Then**
1. returns: `result == []`.

### LED-TT-22 — entries sharing a performed_at come back greatest id first
- **Rules:** `get_by_transaction_type` R4a [BUG-640]
- **Kind:** bug
- **Expect:** xfail BUG-640
- **Fails today on:** Then 2 (entries are ordered by performed_at only, so the tied rows come back as [EB, EC, EA] or [EA, EC, EB])

**Given**
1. EB = entry, `performed_at T1`. (Normal sequence id, inserted first.)
2. EC = entry, `performed_at T1`, but `id HIGH_ID`. (Explicit high id, inserted second.)
3. EA = entry, `performed_at T1`. (Normal sequence id, inserted last.)

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [EC.id, EA.id, EB.id]`.

### LED-TT-23 — entries sharing a performed_at are each returned once, between the newer and the older entry
- **Rules:** `get_by_transaction_type` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.
3. E3 = entry, `performed_at T2`.
4. E4 = entry, `performed_at T3`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `result[0].id == E4.id`.
3. returns: `result[3].id == E1.id`.
4. returns: `sorted(ids(result)) == [E1.id, E2.id, E3.id, E4.id]`.

### LED-TT-24 — skip 1 and limit 1 return exactly the second newest entry
- **Rules:** `get_by_transaction_type` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E3.id]`.

### LED-TT-25 — skip and limit are applied after the transaction type filter
- **Rules:** `get_by_transaction_type` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `transaction_type "sale"`.
3. E3 = entry, `performed_at T3`.
4. E4 = entry, `performed_at T4`, but `transaction_type "sale"`.
5. E5 = entry, `performed_at T5`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E3.id]`.

### LED-TT-26 — default limit returns the 100 newest of 101 entries of that type
- **Rules:** `get_by_transaction_type` R5
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — bulk setup (a loop over 101 entries) outside the Conventions vocabulary

**Given**
1. 101 entries N1 … N101, inserted in that order; entry Nk (k = 1 … 101) has `performed_at` = `datetime(2026, 1, 1, 0, 0) + timedelta(minutes=k)` and is otherwise the default entry (so N101 is the newest and N1 the oldest).

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `result[0].id == N101.id`.
3. returns: `result[99].id == N2.id`.
4. returns: `N1.id not in ids(result)`.

### LED-TT-27 — limit 0 returns an empty list
- **Rules:** `get_by_transaction_type` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### LED-TT-28 — skip equal to the number of matching entries returns an empty list
- **Rules:** `get_by_transaction_type` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### LED-TT-29 — negative limit is rejected by the database and nothing changes
- **Rules:** `get_by_transaction_type` R5, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `exc.value.orig.pgcode == "2201W"`.
4. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.
6. unchanged: unchanged(E1).

### LED-TT-30 — negative skip is rejected by the database and nothing changes
- **Rules:** `get_by_transaction_type` R5, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `exc.value.orig.pgcode == "2201X"`.
4. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.
6. unchanged: unchanged(E1).

### LED-TT-31 — entries of a soft-deleted factory and of a removed item are listed like any other
- **Rules:** `get_by_transaction_type` R6
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `factory_id FD.id`. (FD is the soft-deleted factory.)
3. E3 = entry, `performed_at T3`, but `item_id IR.id`. (IR is the removed catalog item.)

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="manual_add", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E3.id, E2.id, E1.id]`.


## `InventoryLedgerDAO.get_by_date_range`

### LED-DR-01 — both bounds are inclusive and the result is newest first
- **Rules:** `get_by_date_range` R1, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T3)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [E2.id, E3.id, E1.id]`.
3. returns: `isinstance(result[0], InventoryLedger)`.

### LED-DR-02 — bounds one microsecond inside the outer entries keep only the middle entry
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

### LED-DR-03 — entries before the start and after the end are left out
- **Rules:** `get_by_date_range` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T3`.
2. E2 = entry, `performed_at T1`.
3. E3 = entry, `performed_at T5`.
4. E4 = entry, `performed_at T2`.
5. E5 = entry, `performed_at T4`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T2, end_date=T4)`.

**Then**
1. returns: `ids(result) == [E5.id, E1.id, E4.id]`.

### LED-DR-04 — equal start and end return the entry performed at that instant
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

### LED-DR-05 — equal start and end at an instant with no entry return an empty list
- **Rules:** `get_by_date_range` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=datetime(2026, 1, 1, 10, 30, 0), end_date=datetime(2026, 1, 1, 10, 30, 0))`.

**Then**
1. returns: `result == []`.

### LED-DR-06 — a start later than the end returns an empty list
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

### LED-DR-07 — start_date None is refused before any query and nothing changes
- **Rules:** `get_by_date_range` R3, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `dao.get_by_date_range(db, workspace_id=W1.id, start_date=None, end_date=T3)`.

**Then**
1. raises: `ArgumentError`.
2. raises: `str(exc.value).startswith("Only '=', '!=', 'is_()', 'is_not()', 'is_distinct_from()', 'is_not_distinct_from()' operators can be used with None/True/False")`.
3. nothing written: nothing written.
4. unchanged: unchanged(E1).

### LED-DR-08 — end_date None is refused before any query and nothing changes
- **Rules:** `get_by_date_range` R3, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=None)`.

**Then**
1. raises: `ArgumentError`.
2. raises: `str(exc.value).startswith("Only '=', '!=', 'is_()', 'is_not()', 'is_distinct_from()', 'is_not_distinct_from()' operators can be used with None/True/False")`.
3. nothing written: nothing written.
4. unchanged: unchanged(E1).

### LED-DR-09 — an entry of another workspace inside the window is not returned
- **Rules:** `get_by_date_range` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. X9.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### LED-DR-10 — a call for the other workspace returns only that workspace's entry
- **Rules:** `get_by_date_range` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. X9.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W2.id, start_date=T1, end_date=T5)`.

**Then**
1. returns: `ids(result) == [X9.id]`.

### LED-DR-11 — an unknown workspace id returns an empty list
- **Rules:** `get_by_date_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=MISSING, start_date=T1, end_date=T3)`.

**Then**
1. returns: `result == []`.

### LED-DR-12 — inventory_type filter narrows the entries of the window
- **Rules:** `get_by_date_range` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `inventory_type DAMAGED`.
3. E3 = entry, `performed_at T3`, but `inventory_type SCRAP`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T3, inventory_type=DAMAGED)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### LED-DR-13 — factory_id filter narrows the entries of the window
- **Rules:** `get_by_date_range` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `factory_id F2.id`.
3. E3 = entry, `performed_at T3`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T3, factory_id=F2.id)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### LED-DR-14 — item_id filter narrows the entries of the window
- **Rules:** `get_by_date_range` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `item_id I2.id`.
3. E3 = entry, `performed_at T3`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T3, item_id=I2.id)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### LED-DR-15 — type, factory and item filters combine with the window with AND
- **Rules:** `get_by_date_range` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `factory_id F2.id`.
3. E3 = entry, `performed_at T2`, but `inventory_type DAMAGED`.
4. E4 = entry, `performed_at T3`, but `item_id I2.id`.
5. E5 = entry, `performed_at T4`. (Matches the three filters but lies after the window.)

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T3, inventory_type=STORAGE, factory_id=F1.id, item_id=I1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### LED-DR-16 — explicit None for every optional filter applies no filter
- **Rules:** `get_by_date_range` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `inventory_type DAMAGED`, `factory_id F2.id`, `item_id I2.id`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T3, inventory_type=None, factory_id=None, item_id=None)`.

**Then**
1. returns: `ids(result) == [E2.id, E1.id]`.

### LED-DR-17 — a factory id that does not exist returns an empty list
- **Rules:** `get_by_date_range` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T3, factory_id=MISSING)`.

**Then**
1. returns: `result == []`.

### LED-DR-18 — an item id that does not exist returns an empty list
- **Rules:** `get_by_date_range` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T3, item_id=MISSING)`.

**Then**
1. returns: `result == []`.

### LED-DR-19 — factory_id 0 filters and returns an empty list
- **Rules:** `get_by_date_range` R4a [BUG-885]
- **Kind:** bug
- **Expect:** xfail BUG-885
- **Fails today on:** Then 1 (factory_id 0 is treated as no filter, so both entries come back)

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `factory_id F2.id`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T3, factory_id=0)`.

**Then**
1. returns: `result == []`.

### LED-DR-20 — item_id 0 filters and returns an empty list
- **Rules:** `get_by_date_range` R4a [BUG-885]
- **Kind:** bug
- **Expect:** xfail BUG-885
- **Fails today on:** Then 1 (item_id 0 is treated as no filter, so both entries come back)

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `item_id I2.id`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T3, item_id=0)`.

**Then**
1. returns: `result == []`.

### LED-DR-21 — entries sharing a performed_at come back greatest id first
- **Rules:** `get_by_date_range` R5a [BUG-640]
- **Kind:** bug
- **Expect:** xfail BUG-640
- **Fails today on:** Then 2 (entries are ordered by performed_at only, so the tied rows come back as [EB, EC, EA] or [EA, EC, EB])

**Given**
1. EB = entry, `performed_at T1`. (Normal sequence id, inserted first.)
2. EC = entry, `performed_at T1`, but `id HIGH_ID`. (Explicit high id, inserted second.)
3. EA = entry, `performed_at T1`. (Normal sequence id, inserted last.)

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T3)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [EC.id, EA.id, EB.id]`.

### LED-DR-22 — entries sharing a performed_at are each returned once, between the newer and the older entry
- **Rules:** `get_by_date_range` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.
3. E3 = entry, `performed_at T2`.
4. E4 = entry, `performed_at T3`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T3)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `result[0].id == E4.id`.
3. returns: `result[3].id == E1.id`.
4. returns: `sorted(ids(result)) == [E1.id, E2.id, E3.id, E4.id]`.

### LED-DR-23 — skip 1 and limit 1 return exactly the second newest entry
- **Rules:** `get_by_date_range` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T3, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E3.id]`.

### LED-DR-24 — skip and limit are applied after the window filter
- **Rules:** `get_by_date_range` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T4`.
2. E2 = entry, `performed_at T1`.
3. E3 = entry, `performed_at T5`.
4. E4 = entry, `performed_at T3`.
5. E5 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T3, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E5.id]`.

### LED-DR-25 — default limit returns the 100 newest of 101 entries inside the window
- **Rules:** `get_by_date_range` R6
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — bulk setup (a loop over 101 entries) outside the Conventions vocabulary

**Given**
1. 101 entries N1 … N101, inserted in that order; entry Nk (k = 1 … 101) has `performed_at` = `datetime(2026, 1, 1, 0, 0) + timedelta(minutes=k)` and is otherwise the default entry (so N101 is the newest and N1 the oldest).

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=datetime(2026, 1, 1, 0, 0, 0), end_date=datetime(2026, 1, 1, 2, 0, 0))`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `result[0].id == N101.id`.
3. returns: `result[99].id == N2.id`.
4. returns: `N1.id not in ids(result)`.

### LED-DR-26 — limit 0 returns an empty list
- **Rules:** `get_by_date_range` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T3, limit=0)`.

**Then**
1. returns: `result == []`.

### LED-DR-27 — skip equal to the number of matching entries returns an empty list
- **Rules:** `get_by_date_range` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T3, skip=2)`.

**Then**
1. returns: `result == []`.

### LED-DR-28 — negative limit is rejected by the database and nothing changes
- **Rules:** `get_by_date_range` R6, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T3, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `exc.value.orig.pgcode == "2201W"`.
4. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.
6. unchanged: unchanged(E1).

### LED-DR-29 — negative skip is rejected by the database and nothing changes
- **Rules:** `get_by_date_range` R6, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T3, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `exc.value.orig.pgcode == "2201X"`.
4. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.
6. unchanged: unchanged(E1).

### LED-DR-30 — entries of a soft-deleted factory and of a removed item are listed like any other
- **Rules:** `get_by_date_range` R7
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `factory_id FD.id`. (FD is the soft-deleted factory.)
3. E3 = entry, `performed_at T3`, but `item_id IR.id`. (IR is the removed catalog item.)

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T3)`.

**Then**
1. returns: `ids(result) == [E3.id, E2.id, E1.id]`.


## `InventoryLedgerDAO.get_by_performer`

### LED-PF-01 — returns that user's entries of every type, factory, item and transaction type
- **Rules:** `get_by_performer` R1, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`, but `performed_by U2.id`.
3. E3 = entry, `performed_at T2`, but `performed_by None`.
4. E4 = entry, `performed_at T4`, but `inventory_type DAMAGED`, `factory_id F2.id`, `item_id I2.id`, `transaction_type "sale"`.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [E4.id, E1.id]`.
3. returns: `isinstance(result[0], InventoryLedger)`.

### LED-PF-02 — the other user gets only the entry that user performed
- **Rules:** `get_by_performer` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`, but `performed_by U2.id`.
3. E3 = entry, `performed_at T2`, but `performed_by None`.

**When**
- `result = dao.get_by_performer(db, performed_by=U2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### LED-PF-03 — an entry the same user performed in another workspace is not returned
- **Rules:** `get_by_performer` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. X9.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### LED-PF-04 — a call for the other workspace returns only the entry performed there
- **Rules:** `get_by_performer` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. X9.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [X9.id]`.

### LED-PF-05 — a profile id that does not exist returns an empty list
- **Rules:** `get_by_performer` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_performer(db, performed_by=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### LED-PF-06 — performed_by 0 returns an empty list, not the entries without a performer
- **Rules:** `get_by_performer` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `performed_by None`.

**When**
- `result = dao.get_by_performer(db, performed_by=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### LED-PF-07 — an unknown workspace id returns an empty list
- **Rules:** `get_by_performer` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### LED-PF-08 — performed_by None returns only the entries without a performer
- **Rules:** `get_by_performer` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `performed_by None`.
3. E3 = entry, `performed_at T3`, but `performed_by None`.
4. E4 = entry, `performed_at T4`, but `performed_by U2.id`.

**When**
- `result = dao.get_by_performer(db, performed_by=None, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E3.id, E2.id]`.

### LED-PF-09 — performed_by None stays inside the workspace
- **Rules:** `get_by_performer` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `performed_by None`.
2. E2 = entry, `performed_at T2`, but `workspace_id W2.id`, `performed_by None`.

**When**
- `result = dao.get_by_performer(db, performed_by=None, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### LED-PF-10 — the user's entries come back newest first whatever the insertion order
- **Rules:** `get_by_performer` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E2.id, E3.id, E1.id]`.

### LED-PF-11 — entries sharing a performed_at come back greatest id first
- **Rules:** `get_by_performer` R4a [BUG-640]
- **Kind:** bug
- **Expect:** xfail BUG-640
- **Fails today on:** Then 2 (entries are ordered by performed_at only, so the tied rows come back as [EB, EC, EA] or [EA, EC, EB])

**Given**
1. EB = entry, `performed_at T1`. (Normal sequence id, inserted first.)
2. EC = entry, `performed_at T1`, but `id HIGH_ID`. (Explicit high id, inserted second.)
3. EA = entry, `performed_at T1`. (Normal sequence id, inserted last.)

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [EC.id, EA.id, EB.id]`.

### LED-PF-12 — entries sharing a performed_at are each returned once, between the newer and the older entry
- **Rules:** `get_by_performer` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.
3. E3 = entry, `performed_at T2`.
4. E4 = entry, `performed_at T3`.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `result[0].id == E4.id`.
3. returns: `result[3].id == E1.id`.
4. returns: `sorted(ids(result)) == [E1.id, E2.id, E3.id, E4.id]`.

### LED-PF-13 — skip 1 and limit 1 return exactly the second newest entry
- **Rules:** `get_by_performer` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E3.id]`.

### LED-PF-14 — skip and limit are applied after the performer filter
- **Rules:** `get_by_performer` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `performed_by U2.id`.
3. E3 = entry, `performed_at T3`.
4. E4 = entry, `performed_at T4`, but `performed_by U2.id`.
5. E5 = entry, `performed_at T5`.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E3.id]`.

### LED-PF-15 — default limit returns the user's 100 newest of 101 entries
- **Rules:** `get_by_performer` R5
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — bulk setup (a loop over 101 entries) outside the Conventions vocabulary

**Given**
1. 101 entries N1 … N101, inserted in that order; entry Nk (k = 1 … 101) has `performed_at` = `datetime(2026, 1, 1, 0, 0) + timedelta(minutes=k)` and is otherwise the default entry (so N101 is the newest and N1 the oldest).

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `result[0].id == N101.id`.
3. returns: `result[99].id == N2.id`.
4. returns: `N1.id not in ids(result)`.

### LED-PF-16 — limit 0 returns an empty list
- **Rules:** `get_by_performer` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### LED-PF-17 — skip equal to the number of matching entries returns an empty list
- **Rules:** `get_by_performer` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### LED-PF-18 — negative limit is rejected by the database and nothing changes
- **Rules:** `get_by_performer` R5, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `exc.value.orig.pgcode == "2201W"`.
4. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.
6. unchanged: unchanged(E1).

### LED-PF-19 — negative skip is rejected by the database and nothing changes
- **Rules:** `get_by_performer` R5, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `exc.value.orig.pgcode == "2201X"`.
4. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.
6. unchanged: unchanged(E1).

### LED-PF-20 — entries of a soft-deleted factory and of a removed item are listed like any other
- **Rules:** `get_by_performer` R6
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `factory_id FD.id`. (FD is the soft-deleted factory.)
3. E3 = entry, `performed_at T3`, but `item_id IR.id`. (IR is the removed catalog item.)

**When**
- `result = dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E3.id, E2.id, E1.id]`.


## `InventoryLedgerDAO.calculate_balance`

### LED-BAL-01 — a bucket with no ledger entry gives quantity 0 and value 0.00
- **Rules:** `calculate_balance` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No ledger entries exist.

**When**
- `result = dao.calculate_balance(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, tuple)`.
2. returns: `len(result) == 2`.
3. returns: `result[0] == 0`.
4. returns: `type(result[0]) is int`.
5. returns: `isinstance(result[1], Decimal)`.
6. returns: `str(result[1]) == "0.00"`.

### LED-BAL-02 — an entry of another workspace does not count for the bucket
- **Rules:** `calculate_balance` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 20`, `avg_price_after Decimal("6.00")`, `workspace_id W2.id`.

**When**
- `result = dao.calculate_balance(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result[0] == 0`.
2. returns: `result[1] == Decimal("0.00")`.

### LED-BAL-03 — an entry of another factory does not count for the bucket
- **Rules:** `calculate_balance` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 20`, `avg_price_after Decimal("6.00")`, `factory_id F2.id`.

**When**
- `result = dao.calculate_balance(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result[0] == 0`.
2. returns: `result[1] == Decimal("0.00")`.

### LED-BAL-04 — an entry of another item does not count for the bucket
- **Rules:** `calculate_balance` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 20`, `avg_price_after Decimal("6.00")`, `item_id I2.id`.

**When**
- `result = dao.calculate_balance(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result[0] == 0`.
2. returns: `result[1] == Decimal("0.00")`.

### LED-BAL-05 — an entry of another inventory type does not count for the bucket
- **Rules:** `calculate_balance` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 20`, `avg_price_after Decimal("6.00")`, `inventory_type DAMAGED`.

**When**
- `result = dao.calculate_balance(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result[0] == 0`.
2. returns: `result[1] == Decimal("0.00")`.

### LED-BAL-06 — with only other-bucket entries the result is empty and nothing changes
- **Rules:** `calculate_balance` R3, R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `factory_id F2.id`.
2. E2 = entry, `performed_at T2`, but `item_id I2.id`.
3. E3 = entry, `performed_at T3`, but `inventory_type DAMAGED`.
4. E4 = entry, `performed_at T4`, but `workspace_id W2.id`.

**When**
- `result = dao.calculate_balance(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result[0] == 0`.
2. returns: `result[1] == Decimal("0.00")`.
3. nothing written: nothing written.
4. unchanged: unchanged(E1).
5. count: `inventory_ledger` has exactly 4 rows.

### LED-BAL-07 — a bucket without entries in a soft-deleted factory gives quantity 0 and value 0.00
- **Rules:** `calculate_balance` R1, R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`. (In the live factory F1, so not in the bucket asked for.)

**When**
- `result = dao.calculate_balance(db, factory_id=FD.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result[0] == 0`.
2. returns: `result[1] == Decimal("0.00")`.

### LED-BAL-08 — a single entry gives its quantity and quantity times average price
- **Rules:** `calculate_balance` R2 [BUG-655]
- **Kind:** bug
- **Expect:** xfail BUG-655
- **Fails today on:** Then 1 (the call raises AttributeError: the balance reads value_after, a column the inventory ledger does not have)

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 20`, `avg_price_after Decimal("6.00")`.

**When**
- `result = dao.calculate_balance(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result[0] == 20`.
2. returns: `result[1] == Decimal("120.00")`.
3. returns: `isinstance(result, tuple)`.
4. returns: `type(result[0]) is int`.
5. returns: `isinstance(result[1], Decimal)`.

### LED-BAL-09 — an entry with no average price gives its quantity and value 0.00
- **Rules:** `calculate_balance` R2 [BUG-655]
- **Kind:** bug
- **Expect:** xfail BUG-655
- **Fails today on:** Then 1 (the call raises AttributeError: the balance reads value_after, a column the inventory ledger does not have)

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 5`, `avg_price_after None`.

**When**
- `result = dao.calculate_balance(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result[0] == 5`.
2. returns: `result[1] == Decimal("0.00")`.
3. returns: `isinstance(result[1], Decimal)`.

### LED-BAL-10 — an entry with quantity 0 gives quantity 0 and value 0
- **Rules:** `calculate_balance` R2 [BUG-655]
- **Kind:** bug
- **Expect:** xfail BUG-655
- **Fails today on:** Then 1 (the call raises AttributeError: the balance reads value_after, a column the inventory ledger does not have)

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 0`, `avg_price_after Decimal("6.00")`.

**When**
- `result = dao.calculate_balance(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result[0] == 0`.
2. returns: `result[1] == Decimal("0")`.

### LED-BAL-11 — the balance comes from the entry with the greatest performed_at
- **Rules:** `calculate_balance` R4 [BUG-655]
- **Kind:** bug
- **Expect:** xfail BUG-655
- **Fails today on:** Then 1 (the call raises AttributeError: the balance reads value_after, a column the inventory ledger does not have)

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 30`, `avg_price_after Decimal("7.00")`.
2. E2 = entry, `performed_at T3`, but `qty_after 20`, `avg_price_after Decimal("6.00")`.
3. E3 = entry, `performed_at T2`, but `qty_after 10`, `avg_price_after Decimal("4.00")`.

**When**
- `result = dao.calculate_balance(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result[0] == 20`.
2. returns: `result[1] == Decimal("120.00")`.

### LED-BAL-12 — newer entries of other buckets do not change the balance
- **Rules:** `calculate_balance` R4 [BUG-655], R3
- **Kind:** bug
- **Expect:** xfail BUG-655
- **Fails today on:** Then 1 (the call raises AttributeError: the balance reads value_after, a column the inventory ledger does not have)

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 20`, `avg_price_after Decimal("6.00")`.
2. E2 = entry, `performed_at T2`, but `inventory_type DAMAGED`, `qty_after 91`.
3. E3 = entry, `performed_at T3`, but `factory_id F2.id`, `qty_after 92`.
4. E4 = entry, `performed_at T4`, but `item_id I2.id`, `qty_after 93`.
5. E5 = entry, `performed_at T5`, but `workspace_id W2.id`, `qty_after 94`.

**When**
- `result = dao.calculate_balance(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result[0] == 20`.
2. returns: `result[1] == Decimal("120.00")`.

### LED-BAL-13 — among entries sharing the newest performed_at the greatest id gives the balance
- **Rules:** `calculate_balance` R4a [BUG-641, BUG-655]
- **Kind:** bug
- **Expect:** xfail BUG-641, BUG-655
- **Fails today on:** Then 1 (the call raises AttributeError, BUG-655; once that is fixed the tie is still decided by performed_at only, so the quantity is 15 or 99, never 10)

**Given**
1. EB = entry, `performed_at T1`, but `qty_after 15`. (Normal sequence id, inserted first.)
2. EC = entry, `performed_at T1`, but `id HIGH_ID`, `qty_after 10`. (Explicit high id, inserted second.)
3. EA = entry, `performed_at T1`, but `qty_after 99`. (Normal sequence id, inserted last.)

**When**
- `result = dao.calculate_balance(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result[0] == 10`.
2. returns: `result[1] == Decimal("20.00")`.

### LED-BAL-14 — the balance of a bucket in a soft-deleted factory is returned
- **Rules:** `calculate_balance` R5 [BUG-655]
- **Kind:** bug
- **Expect:** xfail BUG-655
- **Fails today on:** Then 1 (the call raises AttributeError: the balance reads value_after, a column the inventory ledger does not have)

**Given**
1. E1 = entry, `performed_at T1`, but `factory_id FD.id`, `qty_after 20`, `avg_price_after Decimal("6.00")`. (FD is the soft-deleted factory.)

**When**
- `result = dao.calculate_balance(db, factory_id=FD.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result[0] == 20`.
2. returns: `result[1] == Decimal("120.00")`.

### LED-BAL-15 — the balance of a bucket of a removed catalog item is returned
- **Rules:** `calculate_balance` R5 [BUG-655]
- **Kind:** bug
- **Expect:** xfail BUG-655
- **Fails today on:** Then 1 (the call raises AttributeError: the balance reads value_after, a column the inventory ledger does not have)

**Given**
1. E1 = entry, `performed_at T1`, but `item_id IR.id`, `qty_after 20`, `avg_price_after Decimal("6.00")`. (IR is the removed catalog item.)

**When**
- `result = dao.calculate_balance(db, factory_id=F1.id, item_id=IR.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result[0] == 20`.
2. returns: `result[1] == Decimal("120.00")`.

### LED-BAL-16 — reading the balance of a bucket with history changes nothing
- **Rules:** `calculate_balance` R6, R2 [BUG-655]
- **Kind:** bug
- **Expect:** xfail BUG-655
- **Fails today on:** Then 1 (the call raises AttributeError: the balance reads value_after, a column the inventory ledger does not have)

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 20`, `avg_price_after Decimal("6.00")`.

**When**
- `result = dao.calculate_balance(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result[0] == 20`.
2. nothing written: nothing written.
3. unchanged: unchanged(E1).
4. re-read E1: `qty_after == 20`.
5. count: `inventory_ledger` has exactly 1 row.


## `InventoryLedgerDAO.get_latest_entry`

### LED-LE-01 — a bucket with no ledger entry returns None
- **Rules:** `get_latest_entry` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No ledger entries exist.

**When**
- `result = dao.get_latest_entry(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### LED-LE-02 — returns the entry with the greatest performed_at when it was inserted second
- **Rules:** `get_latest_entry` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 30`.
2. E2 = entry, `performed_at T3`, but `qty_after 20`.
3. E3 = entry, `performed_at T2`, but `qty_after 10`.

**When**
- `result = dao.get_latest_entry(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, InventoryLedger)`.
2. returns: `result.id == E2.id`.
3. returns: `result.qty_after == 20`.

### LED-LE-03 — a single entry is returned as it is
- **Rules:** `get_latest_entry` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 30`.

**When**
- `result = dao.get_latest_entry(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.
2. returns: `result.qty_after == 30`.

### LED-LE-04 — the newest entry is returned when it has the lowest id
- **Rules:** `get_latest_entry` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T3`, but `qty_after 20`.
2. E2 = entry, `performed_at T1`, but `qty_after 30`.
3. E3 = entry, `performed_at T2`, but `qty_after 10`.

**When**
- `result = dao.get_latest_entry(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.
2. returns: `result.qty_after == 20`.

### LED-LE-05 — the newest entry is returned when it has the highest id
- **Rules:** `get_latest_entry` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 30`.
2. E2 = entry, `performed_at T2`, but `qty_after 10`.
3. E3 = entry, `performed_at T3`, but `qty_after 20`.

**When**
- `result = dao.get_latest_entry(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E3.id`.
2. returns: `result.qty_after == 20`.

### LED-LE-06 — among entries sharing the newest performed_at the greatest id wins
- **Rules:** `get_latest_entry` R3 [BUG-664]
- **Kind:** bug
- **Expect:** xfail BUG-664
- **Fails today on:** Then 1 (entries are ordered by performed_at only, so EB or EA is returned, never EC)

**Given**
1. EB = entry, `performed_at T1`, but `qty_after 15`. (Normal sequence id, inserted first.)
2. EC = entry, `performed_at T1`, but `id HIGH_ID`, `qty_after 10`. (Explicit high id, inserted second.)
3. EA = entry, `performed_at T1`, but `qty_after 99`. (Normal sequence id, inserted last.)

**When**
- `result = dao.get_latest_entry(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == EC.id`.
2. returns: `result.qty_after == 10`.

### LED-LE-07 — an older entry never wins, even with a much greater id
- **Rules:** `get_latest_entry` R3, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T2`, but `qty_after 20`.
2. E2 = entry, `performed_at T1`, but `id HIGH_ID`, `qty_after 30`. (Older, with the explicit high id.)

**When**
- `result = dao.get_latest_entry(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.
2. returns: `result.qty_after == 20`.

### LED-LE-08 — with a tie for newest, one of the tied entries is returned and never the older one
- **Rules:** `get_latest_entry` R3, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 30`.
2. E2 = entry, `performed_at T2`, but `qty_after 15`.
3. E3 = entry, `performed_at T2`, but `qty_after 10`.

**When**
- `result = dao.get_latest_entry(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result.id in [E2.id, E3.id]` (looser check intended: either tied entry is accepted here).
2. returns: `result.performed_at == T2`.

### LED-LE-09 — a newer entry of another workspace is not returned
- **Rules:** `get_latest_entry` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 20`.
2. E2 = entry, `performed_at T2`, but `qty_after 91`, `workspace_id W2.id`.

**When**
- `result = dao.get_latest_entry(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.
2. returns: `result.qty_after == 20`.

### LED-LE-10 — a newer entry of another factory is not returned
- **Rules:** `get_latest_entry` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 20`.
2. E2 = entry, `performed_at T2`, but `qty_after 91`, `factory_id F2.id`.

**When**
- `result = dao.get_latest_entry(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.
2. returns: `result.qty_after == 20`.

### LED-LE-11 — a newer entry of another item is not returned
- **Rules:** `get_latest_entry` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 20`.
2. E2 = entry, `performed_at T2`, but `qty_after 91`, `item_id I2.id`.

**When**
- `result = dao.get_latest_entry(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.
2. returns: `result.qty_after == 20`.

### LED-LE-12 — a newer entry of another inventory type is not returned
- **Rules:** `get_latest_entry` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 20`.
2. E2 = entry, `performed_at T2`, but `qty_after 91`, `inventory_type DAMAGED`.

**When**
- `result = dao.get_latest_entry(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.
2. returns: `result.qty_after == 20`.

### LED-LE-13 — when only entries of other buckets exist the result is None
- **Rules:** `get_latest_entry` R4, R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `factory_id F2.id`.
2. E2 = entry, `performed_at T2`, but `item_id I2.id`.
3. E3 = entry, `performed_at T3`, but `inventory_type DAMAGED`.
4. E4 = entry, `performed_at T4`, but `workspace_id W2.id`.

**When**
- `result = dao.get_latest_entry(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### LED-LE-14 — the returned row carries id, quantity and average price as stored
- **Rules:** `get_latest_entry` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 20`, `avg_price_after Decimal("6.00")`.

**When**
- `result = dao.get_latest_entry(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.
2. returns: `result.qty_after == 20`.
3. returns: `type(result.qty_after) is int`.
4. returns: `result.avg_price_after == Decimal("6.00")`.
5. returns: `isinstance(result.avg_price_after, Decimal)`.

### LED-LE-15 — a NULL average price is readable as None
- **Rules:** `get_latest_entry` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 5`, `avg_price_after None`.

**When**
- `result = dao.get_latest_entry(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.
2. returns: `result.qty_after == 5`.
3. returns: `result.avg_price_after is None`.

### LED-LE-16 — the latest entry of a bucket in a soft-deleted factory is returned
- **Rules:** `get_latest_entry` R6
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `factory_id FD.id`, `qty_after 30`. (FD is the soft-deleted factory.)
2. E2 = entry, `performed_at T2`, but `qty_after 20`. (In the live factory F1.)

**When**
- `result = dao.get_latest_entry(db, factory_id=FD.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.
2. returns: `result.qty_after == 30`.

### LED-LE-17 — the latest entry of a bucket of a removed catalog item is returned
- **Rules:** `get_latest_entry` R6
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `item_id IR.id`, `qty_after 30`. (IR is the removed catalog item.)
2. E2 = entry, `performed_at T2`, but `qty_after 20`. (Of the active item I1.)

**When**
- `result = dao.get_latest_entry(db, factory_id=F1.id, item_id=IR.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.
2. returns: `result.qty_after == 30`.

### LED-LE-18 — the lookup changes nothing in the database
- **Rules:** `get_latest_entry` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 20`, `avg_price_after Decimal("6.00")`.

**When**
- `result = dao.get_latest_entry(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.
2. nothing written: nothing written.
3. unchanged: unchanged(E1).
4. re-read E1: `qty_after == 20`, `performed_at == T1`.
5. re-read E1: `avg_price_after == Decimal("6.00")`.
6. count: `inventory_ledger` has exactly 1 row.


## `InventoryLedgerDAO.exists_for_source`

### LED-EX-01 — one entry with that source type and id gives True
- **Rules:** `exists_for_source` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `source_type "po"`, `source_id 5`.

**When**
- `result = dao.exists_for_source(db, workspace_id=W1.id, source_type="po", source_id=5)`.

**Then**
1. returns: `result is True`.
2. returns: `type(result) is bool`.

### LED-EX-02 — several entries with that source still give True
- **Rules:** `exists_for_source` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `source_type "po"`, `source_id 5`.
2. E2 = entry, `performed_at T2`, but `source_type "po"`, `source_id 5`.
3. E3 = entry, `performed_at T3`, but `source_type "po"`, `source_id 5`.

**When**
- `result = dao.exists_for_source(db, workspace_id=W1.id, source_type="po", source_id=5)`.

**Then**
1. returns: `result is True`.

### LED-EX-03 — the match does not depend on type, factory, item, transaction type, quantity or performer
- **Rules:** `exists_for_source` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `inventory_type DAMAGED`, `factory_id F2.id`, `item_id I2.id`, `transaction_type "sale"`, `quantity 7`, `performed_by None`, `source_type "po"`, `source_id 5`.

**When**
- `result = dao.exists_for_source(db, workspace_id=W1.id, source_type="po", source_id=5)`.

**Then**
1. returns: `result is True`.

### LED-EX-04 — an empty ledger gives False
- **Rules:** `exists_for_source` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No ledger entries exist.

**When**
- `result = dao.exists_for_source(db, workspace_id=W1.id, source_type="po", source_id=5)`.

**Then**
1. returns: `result is False`.
2. returns: `type(result) is bool`.

### LED-EX-05 — the same source in another workspace gives False
- **Rules:** `exists_for_source` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `workspace_id W2.id`, `source_type "po"`, `source_id 5`.

**When**
- `result = dao.exists_for_source(db, workspace_id=W1.id, source_type="po", source_id=5)`.

**Then**
1. returns: `result is False`.

### LED-EX-06 — the same source id with another source type gives False
- **Rules:** `exists_for_source` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `source_type "to"`, `source_id 5`.

**When**
- `result = dao.exists_for_source(db, workspace_id=W1.id, source_type="po", source_id=5)`.

**Then**
1. returns: `result is False`.

### LED-EX-07 — the same source type with another source id gives False
- **Rules:** `exists_for_source` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `source_type "po"`, `source_id 6`.

**When**
- `result = dao.exists_for_source(db, workspace_id=W1.id, source_type="po", source_id=5)`.

**Then**
1. returns: `result is False`.

### LED-EX-08 — an entry with no source gives False for a named source
- **Rules:** `exists_for_source` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`. (`source_type` and `source_id` stay None.)

**When**
- `result = dao.exists_for_source(db, workspace_id=W1.id, source_type="po", source_id=5)`.

**Then**
1. returns: `result is False`.

### LED-EX-09 — the source type is compared case-sensitively
- **Rules:** `exists_for_source` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `source_type "po"`, `source_id 5`.

**When**
- `result = dao.exists_for_source(db, workspace_id=W1.id, source_type="PO", source_id=5)`.

**Then**
1. returns: `result is False`.

### LED-EX-10 — source_id None matches an entry whose source id is NULL
- **Rules:** `exists_for_source` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `source_type "po"`. (`source_id` stays None.)

**When**
- `result = dao.exists_for_source(db, workspace_id=W1.id, source_type="po", source_id=None)`.

**Then**
1. returns: `result is True`.

### LED-EX-11 — source_id None does not match an entry that has a source id
- **Rules:** `exists_for_source` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `source_type "po"`, `source_id 5`.

**When**
- `result = dao.exists_for_source(db, workspace_id=W1.id, source_type="po", source_id=None)`.

**Then**
1. returns: `result is False`.

### LED-EX-12 — source type None and source id None match an entry that has neither
- **Rules:** `exists_for_source` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `source_type "po"`, `source_id 5`.
2. E2 = entry, `performed_at T2`. (`source_type` and `source_id` stay None.)

**When**
- `result = dao.exists_for_source(db, workspace_id=W1.id, source_type=None, source_id=None)`.

**Then**
1. returns: `result is True`.

### LED-EX-13 — source type None and source id None do not match an entry that has a source
- **Rules:** `exists_for_source` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `source_type "po"`, `source_id 5`.

**When**
- `result = dao.exists_for_source(db, workspace_id=W1.id, source_type=None, source_id=None)`.

**Then**
1. returns: `result is False`.

### LED-EX-14 — an entry booked in a soft-deleted factory counts
- **Rules:** `exists_for_source` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `factory_id FD.id`, `source_type "po"`, `source_id 5`. (FD is the soft-deleted factory.)

**When**
- `result = dao.exists_for_source(db, workspace_id=W1.id, source_type="po", source_id=5)`.

**Then**
1. returns: `result is True`.

### LED-EX-15 — an entry of a removed catalog item counts
- **Rules:** `exists_for_source` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `item_id IR.id`, `source_type "po"`, `source_id 5`. (IR is the removed catalog item.)

**When**
- `result = dao.exists_for_source(db, workspace_id=W1.id, source_type="po", source_id=5)`.

**Then**
1. returns: `result is True`.

### LED-EX-16 — the check changes nothing in the database
- **Rules:** `exists_for_source` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `source_type "po"`, `source_id 5`.

**When**
- `result = dao.exists_for_source(db, workspace_id=W1.id, source_type="po", source_id=5)`.

**Then**
1. returns: `result is True`.
2. nothing written: nothing written.
3. unchanged: unchanged(E1).
4. re-read E1: `source_type == "po"`, `source_id == 5`.
5. count: `inventory_ledger` has exactly 1 row.


## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Overview "Integration-only behavior": `skip >= 0`, `limit <= 100` | `GET /ledgers/inventory/` (endpoint) | 422 for `skip=-1` and `limit=101`. The DAO itself lets Postgres reject negatives (LED-W-33, W-34) and accepts any positive limit (LED-W-29). |
| `limit >= 1` (HR-7, BUG-642) | `GET /ledgers/inventory/` and `GET /ledgers/reports/user-transactions/{user_id}/` (endpoints; bug logged against `ledger_manager`) | 422 for `limit=0`. Here `limit=0` returns `[]` by rule (LED-W-30, TT-27, DR-26, PF-16). |
| Which list method a request reaches (BUG-341 / BUG-646 / BUG-648) | `LedgerManager.get_inventory_ledger` spec | The choice between the date, type and plain list; a fix may merge the three list methods and these cards must then be re-mapped. |
| `get_by_performer` Visibility note (BUG-645) | `LedgerManager.get_transactions_by_user` spec | The report reaches this method at all (today it crashes earlier). |
| `exists_for_source` — no unique index behind the guard (BUG-680) | `po_receive_inventory` spec / migration | Two concurrent postings of one source line: the database rejects the second. Here only the read is tested. |
| `get_by_workspace` R11, R12 (and the same rules of the other lists) — labelling entries of a deleted factory / removed item | ledger page / `ItemSummaryService` spec | Whether such entries are labelled, and whether the summary page of a removed item is shown at all. Here they are returned by design. |
| `calculate_balance` R5, `get_latest_entry` R6, `exists_for_source` R5 — refusing to work on a deleted factory / removed item | stock-posting callers (`inventory_movements`, `po_receive_inventory`; BUG-662, BUG-715) | The caller refuses before the lookup. Here the lookups stay raw by design (LED-BAL-07, BAL-14, BAL-15, LE-16, LE-17, EX-14, EX-15). |
| Inherited `get`, `get_multi`, `create`, `update`, `remove`, `get_by_id_and_workspace` | `tests/unit/dao/base.spec.md` / `base.cases.md` | Generic behaviour, including `create` with a schema failing on NOT NULL `workspace_id`. Not repeated here. |
| `get_by_workspace` R7a and the other tie rules — second proof by emitted SQL (`ORDER BY … performed_at DESC, id DESC`) | `LedgerManager` tests (statement recorder already used there) | Optional extra proof named in the spec's designer notes; not used here because the tie recipe already gives a strict xfail without a recorder. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `get_by_performer` R6, last sentence | "The performer's own profile state is not consulted" — the spec does not say which `profiles` column(s) make up that state (inactive? deleted?) or their names. | No card for that sentence (the rest of R6 is covered by LED-PF-20). Needs the column name and the value that means "inactive / deleted". |
| 2 | `get_by_transaction_type`, `get_by_date_range`, `get_by_performer` | These three have "Side effects: none" but no numbered "changes nothing in the database" rule (`get_by_workspace` has R13). | Not blocking: no dedicated card; their error cards assert nothing written and unchanged(E1) (LED-TT-29, TT-30, DR-07, DR-08, DR-28, DR-29, PF-18, PF-19). |
| 3 | `get_by_date_range` Inputs note | Time-zone-aware `start_date` / `end_date` are declared "not specified". | Not blocking: no card uses them. If the endpoint can pass aware datetimes, a rule is needed. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_workspace` | R1 | LED-W-03, LED-W-04, LED-W-05, LED-W-06, LED-W-07, LED-W-08 |
| `get_by_workspace` | R2 | LED-W-01, LED-W-02 |
| `get_by_workspace` | R3 | LED-W-09, LED-W-10, LED-W-11 |
| `get_by_workspace` | R4 | LED-W-05, LED-W-11, LED-W-12, LED-W-13, LED-W-14 |
| `get_by_workspace` | R4a [BUG-885] | LED-W-15 |
| `get_by_workspace` | R5 | LED-W-06, LED-W-11, LED-W-16, LED-W-17 |
| `get_by_workspace` | R5a [BUG-885] | LED-W-18 |
| `get_by_workspace` | R6 | LED-W-19, LED-W-20 |
| `get_by_workspace` | R7 | LED-W-01, LED-W-20, LED-W-22 |
| `get_by_workspace` | R7a [BUG-640] | LED-W-21 |
| `get_by_workspace` | R8 | LED-W-23, LED-W-24, LED-W-25, LED-W-26, LED-W-27, LED-W-28, LED-W-29, LED-W-32 |
| `get_by_workspace` | R9 | LED-W-30, LED-W-31, LED-W-32 |
| `get_by_workspace` | R10 | LED-W-33, LED-W-34 |
| `get_by_workspace` | R11 | LED-W-35, LED-W-36 |
| `get_by_workspace` | R12 | LED-W-37, LED-W-38 |
| `get_by_workspace` | R13 | LED-W-39 |
| `get_by_workspace` | Errors row 1 (negative `limit`) | LED-W-33 |
| `get_by_workspace` | Errors row 2 (negative `skip`) | LED-W-34 |
| `get_by_transaction_type` | R1 | LED-TT-01, LED-TT-02, LED-TT-03, LED-TT-04, LED-TT-05, LED-TT-06, LED-TT-07, LED-TT-10, LED-TT-11, LED-TT-12 |
| `get_by_transaction_type` | R2 | LED-TT-08, LED-TT-09 |
| `get_by_transaction_type` | R3 | LED-TT-13, LED-TT-14, LED-TT-15, LED-TT-16, LED-TT-17, LED-TT-18, LED-TT-19 |
| `get_by_transaction_type` | R3a [BUG-885] | LED-TT-20, LED-TT-21 |
| `get_by_transaction_type` | R4 | LED-TT-01, LED-TT-23 |
| `get_by_transaction_type` | R4a [BUG-640] | LED-TT-22 |
| `get_by_transaction_type` | R5 | LED-TT-24, LED-TT-25, LED-TT-26, LED-TT-27, LED-TT-28, LED-TT-29, LED-TT-30 |
| `get_by_transaction_type` | R6 | LED-TT-31 |
| `get_by_transaction_type` | Errors (negative `limit`, as `get_by_workspace`) | LED-TT-29 |
| `get_by_transaction_type` | Errors (negative `skip`, as `get_by_workspace`) | LED-TT-30 |
| `get_by_date_range` | R1 | LED-DR-01, LED-DR-02, LED-DR-03, LED-DR-09, LED-DR-10, LED-DR-11 |
| `get_by_date_range` | R2 | LED-DR-04, LED-DR-05, LED-DR-06 |
| `get_by_date_range` | R3 | LED-DR-07, LED-DR-08 |
| `get_by_date_range` | R4 | LED-DR-12, LED-DR-13, LED-DR-14, LED-DR-15, LED-DR-16, LED-DR-17, LED-DR-18 |
| `get_by_date_range` | R4a [BUG-885] | LED-DR-19, LED-DR-20 |
| `get_by_date_range` | R5 | LED-DR-01, LED-DR-22 |
| `get_by_date_range` | R5a [BUG-640] | LED-DR-21 |
| `get_by_date_range` | R6 | LED-DR-23, LED-DR-24, LED-DR-25, LED-DR-26, LED-DR-27, LED-DR-28, LED-DR-29 |
| `get_by_date_range` | R7 | LED-DR-30 |
| `get_by_date_range` | Errors row 1 (`None` date) | LED-DR-07, LED-DR-08 |
| `get_by_date_range` | Errors row 2 (negative `limit` / `skip`) | LED-DR-28, LED-DR-29 |
| `get_by_performer` | R1 | LED-PF-01, LED-PF-02 |
| `get_by_performer` | R2 | LED-PF-03, LED-PF-04, LED-PF-05, LED-PF-06, LED-PF-07 |
| `get_by_performer` | R3 | LED-PF-08, LED-PF-09 |
| `get_by_performer` | R4 | LED-PF-01, LED-PF-10, LED-PF-12 |
| `get_by_performer` | R4a [BUG-640] | LED-PF-11 |
| `get_by_performer` | R5 | LED-PF-13, LED-PF-14, LED-PF-15, LED-PF-16, LED-PF-17, LED-PF-18, LED-PF-19 |
| `get_by_performer` | R6 | LED-PF-20 |
| `get_by_performer` | Errors (negative `limit`, as `get_by_workspace`) | LED-PF-18 |
| `get_by_performer` | Errors (negative `skip`, as `get_by_workspace`) | LED-PF-19 |
| `calculate_balance` | R1 | LED-BAL-01, LED-BAL-07 |
| `calculate_balance` | R2 [BUG-655] | LED-BAL-08, LED-BAL-09, LED-BAL-10, LED-BAL-16 |
| `calculate_balance` | R3 | LED-BAL-02, LED-BAL-03, LED-BAL-04, LED-BAL-05, LED-BAL-06, LED-BAL-12 |
| `calculate_balance` | R4 [BUG-655] | LED-BAL-11, LED-BAL-12 |
| `calculate_balance` | R4a [BUG-641] | LED-BAL-13 |
| `calculate_balance` | R5 [BUG-655] | LED-BAL-07, LED-BAL-14, LED-BAL-15 |
| `calculate_balance` | R6 | LED-BAL-06, LED-BAL-16 |
| `get_latest_entry` | R1 | LED-LE-01, LED-LE-13 |
| `get_latest_entry` | R2 | LED-LE-02, LED-LE-03, LED-LE-04, LED-LE-05, LED-LE-07, LED-LE-08 |
| `get_latest_entry` | R3 [BUG-664] | LED-LE-06, LED-LE-07, LED-LE-08 |
| `get_latest_entry` | R4 | LED-LE-09, LED-LE-10, LED-LE-11, LED-LE-12, LED-LE-13 |
| `get_latest_entry` | R5 | LED-LE-14, LED-LE-15 |
| `get_latest_entry` | R6 | LED-LE-16, LED-LE-17 |
| `get_latest_entry` | R7 | LED-LE-18 |
| `exists_for_source` | R1 | LED-EX-01, LED-EX-02, LED-EX-03 |
| `exists_for_source` | R2 | LED-EX-04, LED-EX-05, LED-EX-06, LED-EX-07, LED-EX-08 |
| `exists_for_source` | R3 | LED-EX-09 |
| `exists_for_source` | R4 | LED-EX-10, LED-EX-11, LED-EX-12, LED-EX-13 |
| `exists_for_source` | R5 | LED-EX-14, LED-EX-15 |
| `exists_for_source` | R6 | LED-EX-16 |
