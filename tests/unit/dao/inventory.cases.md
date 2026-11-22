# Test cases — `app/dao/inventory.py`

> **Spec:** `tests/unit/dao/inventory.spec.md` (source commit e48a092)
> **Status:** READY — designed against the **APPROVED** spec (re-read from disk after review rounds 2026-10-10 (1) and (2): BUG-882, BUG-883 and BUG-884 rules included; no pilot default remains).
> **Counts:** 191 cases · 158 expected-to-pass · 33 expected-to-fail (bugs) · 8 deferred

## Reviewer summary
- **Per callable:** `_filtered_query` 40 (11 bug) · `list_filtered` 22 (3 bug) · `count_filtered` 15 (6 bug) · `stats_filtered` 25 (9 bug) · `get_by_id_and_workspace` 8 · `get_by_factory_item_type` 11 · `_get_any_by_factory_item_type` 7 · `sync_snapshot_from_ledger` 17 (1 bug) · `ensure_for_factory_item_type` 28 (1 bug) · `get_by_item` 13 (2 bug) · `restore` 5.
- **Notable design choices:**
  - `_filtered_query` is internal: its 40 cards run it through `list_filtered` and compare sorted ids (so the BUG-701 order change cannot break them and a duplicated row would show). `count_filtered` and `stats_filtered` then get a smaller set proving each filter reaches them too. BUG-880 has one xfail card per public caller (FQ-10, CNT-07, ST-16).
  - BUG-882 (soft-deleted factory) and BUG-883 (removed catalog item) follow the spec's designer notes so each xfail fails for exactly one bug: BUG-882 cards use only active items and a factory built `is_active True`, `is_deleted True`; BUG-883 cards use only live factories and clearly different item names; each keeps one row that must still match, and every hidden stock row is itself live with qty above 0. The rule examples (with today's values in the Fails-today line) are used as written. BUG-884 (`get_by_item`) likewise. What already holds is in pass cards: inactive-but-live factory (FQ-39, CNT-15, ST-25, GI-11), rows left untouched (FQ-35, FQ-40, GI-12), the `limit=1` mirror cases (L-20, L-22), and the raw lookups that must keep seeing such rows (GIW-07, GIW-08, GF-10, GF-11, EN-28, GI-13).
  - FQ-35, FQ-40 and GI-12 assert only `S1.id in ids(result)` on the return value — deliberately loose, so they pass both today and after the fixes; the exact result is in the xfail cards.
  - Every bug rule is split: what works today is in pass cards (e.g. FQ-27 / FQ-28 search text that merely *contains* `%` or `_`; EN-06 the restore itself), only the buggy assertion is in the xfail card.
  - BUG-701 (L-04) uses the spec's case-only tie; L-05 is the mirror-image pass card. BUG-664 (SY-17) uses the spec's insertion recipe with an explicit high id. BUG-719 (ST-03) is a **non-strict** xfail because today's order may already match.
  - Cards marked `Author: claude` (9): INV-ST-03, INV-SY-16, INV-EN-22, INV-EN-23, INV-EN-24, INV-EN-25, INV-EN-26, INV-GI-05, INV-R-05 — race simulations (the only patches in the file, declared in Conventions), the non-strict xfail, the four "flushed, not committed" rollback cards, and one bulk-setup card. All other cards are plain data-in, data-out.
  - "Flushed" is proved in every write card by the re-read (it expires the session first, and autoflush is off). "Not committed" has one rollback card per writing callable (SY-16, EN-25, EN-26, R-05).
  - Removed callables (`get_by_workspace` override, `soft_delete`, `get_by_item`'s `inventory_type` parameter — Q3–Q5) and the inherited `BaseDAO` methods have no cards. `get_by_id_and_workspace` is an override and is specified, so it has its own cards.
  - EN-15 makes a setup call to the method under test in Given (the rule is "calling twice returns the same row").
  - Field-length limits and types of the Inputs tables are not rules and got no cases.
- **Needs a decision:** None blocking. Three small facts are missing from the spec (see Spec gaps): item-name uniqueness, item description / SKU column names, enum string values.


## Conventions for this module

**IDs.** `INV` = `app/dao/inventory.py`. `FQ` _filtered_query · `L` list_filtered · `CNT` count_filtered · `ST` stats_filtered · `GIW` get_by_id_and_workspace · `GF` get_by_factory_item_type · `GA` _get_any_by_factory_item_type · `SY` sync_snapshot_from_ledger · `EN` ensure_for_factory_item_type · `GI` get_by_item · `R` restore.

**Actors and fixed values.**
- `dao` = the singleton `inventory_dao` (`from app.dao.inventory import inventory_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- W1, W2 = two `workspaces` rows. U1, U2 = two `profiles` rows: U1 is `created_by` of every Given stock row, U2 is the acting user of the calls.
- STORAGE, DAMAGED, WASTE, SCRAP = the four members of `InventoryTypeEnum` (`app.models.enums`). `Inventory` = `app.models.inventory.Inventory`. `Row` = `sqlalchemy.engine.Row`.
- MISSING = `999999999`: an id that no row of any table has.
- T0 = `datetime(2025, 12, 1, 8, 0, 0)`. T1 = `datetime(2026, 1, 1, 9, 0, 0)`, T2 = `datetime(2026, 1, 1, 10, 0, 0)`, T3 = `datetime(2026, 1, 1, 11, 0, 0)`, T4 = `datetime(2026, 1, 1, 12, 0, 0)`, T5 = `datetime(2026, 1, 1, 13, 0, 0)` (all naive).
- HIGH_ID = the greatest `inventory_ledger.id` at that moment (0 if the table is empty) + `1000000`.
- `"a\\b"` is the Python literal for the three characters a\b (one backslash).

**Externals.** Nothing is mocked and no clock is patched. Database `now()` is the same instant for the whole test.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. A card names, by column name, every column that differs from these defaults.
- These six rows exist in every test and need no Given line: F1 = `factories` row `name "Factory One"`, `abbreviation "F1"`, `workspace_id W1.id`, `is_active True`, `is_deleted False`. F2 = the same, but `name "Factory Two"`, `abbreviation "F2"`. F9 = the same, but `name "Factory Nine"`, `abbreviation "F9"`, `workspace_id W2.id`. I1 = default item, `name "Bolt"`. I2 = default item, `name "Nut"`. I9 = default item, `name "Bolt"`, but `workspace_id W2.id`.
- **default item** = `items` row: `workspace_id W1.id`, `unit "pcs"`, `is_active True`, `description None`, `sku None`; `name` is always given; `name_normalized` = the name in lower case unless the card gives it.
- Stock rows (`inventory`) and ledger entries (`inventory_ledger`) exist only if the card's Given lists them.
- **default stock of <item> in <factory>** = `inventory` row: `item_id` and `factory_id` of those two rows, `workspace_id W1.id`, `inventory_type STORAGE`, `qty 5`, `avg_price Decimal("2.00")`, `note None`, `created_by U1.id`, `updated_by None`, `updated_at None`, `is_active True`, `is_deleted False`, `deleted_at None`, `deleted_by None`.
- **deleted** (said of a stock row) = `is_deleted True`, `is_active False`, `deleted_at T0`, `deleted_by U1.id`.
- S9 = default stock of I9 in F9, but `workspace_id W2.id`.
- **entry of <item> in <factory>** = `inventory_ledger` row: `item_id` and `factory_id` of those two rows, `workspace_id W1.id`, `inventory_type STORAGE`, `transaction_type "manual_add"`, `quantity 1`, `qty_before 0`, sequence `id`; the card always gives `qty_after`, `avg_price_after` and `performed_at`.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values. (Expiring discards unflushed changes, so a re-read that shows a new value also proves the change was flushed.) "the returned row" = re-read by `result.id`.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken before the call).
- **nothing written** = the number of rows in `inventory` and the number of rows in `inventory_ledger` (all workspaces) equal their values before the call.
- **ids(result)** = `sorted(row.id for row in result)` — a list, so a row returned twice would show.
- **names(result)** = `[row.item_name for row in result]` — in the order returned.
- **by_type(result)** = `{(r[0], r[1], r[2]) for r in result[3]}` — the per-type rows of a `stats_filtered` result as a set of 3-tuples.
- `count:` lines count the rows of the named table in all workspaces.
- Prices and values are compared as `Decimal` values (`Decimal("6.00") == Decimal("6")`), never as strings. Assert `updated_at` only as `is None` / `is not None`.
- `raises: DataError` = `sqlalchemy.exc.DataError`. Wrap the call: `with pytest.raises(DataError) as exc:` then `with db.begin_nested():` then the call. `InvalidRowCountInLimitClause`, `InvalidRowCountInResultOffsetClause`, `ForeignKeyViolation`, `UniqueViolation` = classes of `psycopg2.errors`.
- `raises: IntegrityError` = `sqlalchemy.exc.IntegrityError`. Plain `with pytest.raises(IntegrityError) as exc:` around the call — no `begin_nested`; keep using `db` for the remaining checks.
- Further `raises:` lines of the same card are assertions on `exc.value`, written after the `with` block.

**xfail cards.** Write the call and the checks exactly as shown; the harness adds the marker.

**Race simulations** (cards marked Author: claude only; rules `ensure_for_factory_item_type` R9, R10). The insert can only hit the bucket's unique constraint if both pre-insert lookups miss an existing row, so with the row present:
- **race R9** = `patch.object(inventory_dao, "get_by_factory_item_type", return_value=None)` plus `patch.object(inventory_dao, "_get_any_by_factory_item_type", side_effect=…)` whose side effect returns `None` on the first call and delegates to the real method afterwards.
- **race R10** = the same two patches, both with `return_value=None` on every call.

**Rolled back** (cards marked Author: claude only). `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); the first checks run inside the savepoint; then `sp.rollback()` and the "after the savepoint rollback" checks.


## `InventoryDAO._filtered_query` (internal — exercised through `list_filtered`)

### INV-FQ-01 — default call returns the workspace's live in-stock rows, each once
- **Rules:** `_filtered_query` R1, R3, R12
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I2 in F1.
3. S9.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [S1.id, S2.id]`.

### INV-FQ-02 — a call for the other workspace returns only that workspace's rows
- **Rules:** `_filtered_query` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I2 in F1.
3. S9.

**When**
- `result = dao.list_filtered(db, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [S9.id]`.

### INV-FQ-03 — a W1 stock row pointing at a W2 item is matched and searchable
- **Rules:** `_filtered_query` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = default stock of I9 in F1. (The stock row is in W1; its item I9 is in W2.)
2. S2 = default stock of I2 in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, search="bolt")`.

**Then**
1. returns: `ids(result) == [S1.id]`.
2. returns: `result[0].item_name == "Bolt"`.

### INV-FQ-04 — soft-deleted stock rows are not matched
- **Rules:** `_filtered_query` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I2 in F1, but deleted.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [S1.id]`.

### INV-FQ-05 — a live stock row with is_active False (item active) is matched
- **Rules:** `_filtered_query` R2, R11c
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `is_active False`.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [S1.id]`.

### INV-FQ-06 — inventory_type filter keeps only that type
- **Rules:** `_filtered_query` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I1 in F1, but `inventory_type DAMAGED`.
3. S3 = default stock of I1 in F1, but `inventory_type SCRAP`.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, inventory_type=DAMAGED)`.

**Then**
1. returns: `ids(result) == [S2.id]`.

### INV-FQ-07 — explicit None for every optional filter applies no filter
- **Rules:** `_filtered_query` R3, R4, R5, R6, R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I2 in F2, but `inventory_type DAMAGED`.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, inventory_type=None, factory_id=None, item_id=None, search=None)`.

**Then**
1. returns: `ids(result) == [S1.id, S2.id]`.

### INV-FQ-08 — a type with no stock rows returns nothing
- **Rules:** `_filtered_query` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, inventory_type=WASTE)`.

**Then**
1. returns: `result == []`.

### INV-FQ-09 — factory_id filter keeps only that factory
- **Rules:** `_filtered_query` R5, R12
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I1 in F2.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, factory_id=F2.id)`.

**Then**
1. returns: `ids(result) == [S2.id]`.

### INV-FQ-10 — factory_id 0 matches no rows
- **Rules:** `_filtered_query` R5 [BUG-880]
- **Kind:** bug
- **Expect:** xfail BUG-880
- **Fails today on:** Then 1 (factory_id 0 is treated as no filter, so both rows come back)

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I1 in F2.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, factory_id=0)`.

**Then**
1. returns: `result == []`.

### INV-FQ-11 — a factory id that does not exist matches nothing
- **Rules:** `_filtered_query` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, factory_id=MISSING)`.

**Then**
1. returns: `result == []`.

### INV-FQ-12 — a factory whose stock is all in another workspace matches nothing
- **Rules:** `_filtered_query` R5, R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S9.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, factory_id=F9.id)`.

**Then**
1. returns: `result == []`.

### INV-FQ-13 — item_id filter keeps only that item
- **Rules:** `_filtered_query` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I2 in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, item_id=I2.id)`.

**Then**
1. returns: `ids(result) == [S2.id]`.

### INV-FQ-14 — item_id 0 filters and matches nothing
- **Rules:** `_filtered_query` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I2 in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, item_id=0)`.

**Then**
1. returns: `result == []`.

### INV-FQ-15 — by default only rows with qty above zero are matched
- **Rules:** `_filtered_query` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `qty 1`.
2. S2 = default stock of I2 in F1, but `qty 0`.
3. S3 = default stock of I1 in F2, but `qty -2`.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [S1.id]`.

### INV-FQ-16 — include_zero_qty True matches zero and negative quantities too
- **Rules:** `_filtered_query` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `qty 1`.
2. S2 = default stock of I2 in F1, but `qty 0`.
3. S3 = default stock of I1 in F2, but `qty -2`.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, include_zero_qty=True)`.

**Then**
1. returns: `ids(result) == [S1.id, S2.id, S3.id]`.

### INV-FQ-17 — empty search text applies no search
- **Rules:** `_filtered_query` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I2 in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, search="")`.

**Then**
1. returns: `ids(result) == [S1.id, S2.id]`.

### INV-FQ-18 — whitespace-only search text applies no search
- **Rules:** `_filtered_query` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I2 in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, search="   ")` — the search text is three spaces.

**Then**
1. returns: `ids(result) == [S1.id, S2.id]`.

### INV-FQ-19 — search is trimmed and matches the item name case-insensitively anywhere in it
- **Rules:** `_filtered_query` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. IA = default item, `name "Big Bolts M8"`.
2. S1 = default stock of IA in F1.
3. S2 = default stock of I1 in F1.
4. S3 = default stock of I2 in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, search=" BOLT ")` — one space before and one after.

**Then**
1. returns: `ids(result) == [S1.id, S2.id]`.

### INV-FQ-20 — search matches the item unit case-insensitively anywhere in it
- **Rules:** `_filtered_query` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. IA = default item, `name "Wire"`, `unit "kg"`.
2. S1 = default stock of I2 in F1. (I2 has `unit "pcs"`.)
3. S2 = default stock of IA in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, search="C")`.

**Then**
1. returns: `ids(result) == [S1.id]`.

### INV-FQ-21 — a row matches when either the name or the unit contains the text
- **Rules:** `_filtered_query` R9, R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. IA = default item, `name "Kg Scale"`.
2. IB = default item, `name "Wire"`, `unit "kg"`.
3. S1 = default stock of IA in F1.
4. S2 = default stock of IB in F1.
5. S3 = default stock of I2 in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, search="kg")`.

**Then**
1. returns: `ids(result) == [S1.id, S2.id]`.

### INV-FQ-22 — inner whitespace of the search text is kept
- **Rules:** `_filtered_query` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. IA = default item, `name "Hex Bolt"`.
2. IB = default item, `name "HexBolt"`.
3. S1 = default stock of IA in F1.
4. S2 = default stock of IB in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, search="x b")`.

**Then**
1. returns: `ids(result) == [S1.id]`.

### INV-FQ-23 — note, item description, item SKU and factory name are not searched
- **Rules:** `_filtered_query` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. IA = default item, `name "Washer"`, `description "gasket kit"`, `sku "GASKET-1"`.
2. FA = `factories` row: `name "Gasket Plant"`, `abbreviation "GP"`, `workspace_id W1.id`.
3. S1 = default stock of IA in FA, but `note "gasket spare"`.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, search="gasket")`.

**Then**
1. returns: `result == []`.

### INV-FQ-24 — a percent sign in the search text is matched literally
- **Rules:** `_filtered_query` R9 [BUG-702]
- **Kind:** bug
- **Expect:** xfail BUG-702
- **Fails today on:** Then 1 (the percent sign acts as a wildcard, so both rows come back)

**Given**
1. IA = default item, `name "50% Mix"`.
2. S1 = default stock of IA in F1.
3. S2 = default stock of I2 in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, search="%")`.

**Then**
1. returns: `ids(result) == [S1.id]`.

### INV-FQ-25 — an underscore in the search text is matched literally
- **Rules:** `_filtered_query` R9 [BUG-702]
- **Kind:** bug
- **Expect:** xfail BUG-702
- **Fails today on:** Then 1 (the underscore acts as a one-character wildcard, so both rows come back)

**Given**
1. IA = default item, `name "_x Rod"`.
2. S1 = default stock of IA in F1.
3. S2 = default stock of I2 in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, search="_")`.

**Then**
1. returns: `ids(result) == [S1.id]`.

### INV-FQ-26 — a backslash in the search text is matched literally
- **Rules:** `_filtered_query` R9 [BUG-702]
- **Kind:** bug
- **Expect:** xfail BUG-702
- **Fails today on:** Then 1 (the backslash acts as an escape character, so only S2 comes back)

**Given**
1. IA = default item, `name "a\\b"` (Python literal: the three characters a\b).
2. IB = default item, `name "ab"`.
3. S1 = default stock of IA in F1.
4. S2 = default stock of IB in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, search="a\\b")` — the search text is the three characters a\b.

**Then**
1. returns: `ids(result) == [S1.id]`.

### INV-FQ-27 — text containing a percent sign finds the item whose name contains it
- **Rules:** `_filtered_query` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. IA = default item, `name "50% Mix"`.
2. S1 = default stock of IA in F1.
3. S2 = default stock of I2 in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, search="50%")`.

**Then**
1. returns: `ids(result) == [S1.id]`.

### INV-FQ-28 — text containing an underscore finds the item whose name contains it
- **Rules:** `_filtered_query` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. IA = default item, `name "_x Rod"`.
2. S1 = default stock of IA in F1.
3. S2 = default stock of I2 in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, search="_x")`.

**Then**
1. returns: `ids(result) == [S1.id]`.

### INV-FQ-29 — type, factory and item filters combine with AND
- **Rules:** `_filtered_query` R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I1 in F2.
3. S3 = default stock of I1 in F1, but `inventory_type DAMAGED`.
4. S4 = default stock of I2 in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, inventory_type=STORAGE, factory_id=F1.id, item_id=I1.id)`.

**Then**
1. returns: `ids(result) == [S1.id]`.

### INV-FQ-30 — search combines with AND with the type, factory and quantity filters
- **Rules:** `_filtered_query` R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. IA = default item, `name "Bolt Long"`.
2. S1 = default stock of I1 in F1.
3. S2 = default stock of I1 in F2.
4. S3 = default stock of I2 in F1.
5. S4 = default stock of I1 in F1, but `inventory_type DAMAGED`.
6. S5 = default stock of IA in F1, but `qty 0`.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, search="bolt", factory_id=F1.id, inventory_type=STORAGE)`.

**Then**
1. returns: `ids(result) == [S1.id]`.

### INV-FQ-31 — stock of a removed catalog item is not matched
- **Rules:** `_filtered_query` R11 [BUG-883]; `list_filtered` R1b [BUG-883]
- **Kind:** bug
- **Expect:** xfail BUG-883
- **Fails today on:** Then 1 (the item's is_active is never looked at, so S2 comes back too)

**Given**
1. IA = default item, `name "Old Gasket"`, `is_active False` (a removed catalog item).
2. S1 = default stock of I1 in F1.
3. S2 = default stock of IA in F1, but `qty 12`.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [S1.id]`.

### INV-FQ-32 — stock of a removed item is not matched by that item's own id
- **Rules:** `_filtered_query` R11 [BUG-883]; `list_filtered` R1b [BUG-883]
- **Kind:** bug
- **Expect:** xfail BUG-883
- **Fails today on:** Then 1 (the item's is_active is never looked at, so S2 is returned)

**Given**
1. IA = default item, `name "Old Gasket"`, `is_active False` (a removed catalog item).
2. S1 = default stock of I1 in F1.
3. S2 = default stock of IA in F1, but `qty 12`.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, item_id=IA.id)`.

**Then**
1. returns: `result == []`.

### INV-FQ-33 — stock of a removed item is not found by a search for its name
- **Rules:** `_filtered_query` R11 [BUG-883]; `list_filtered` R1b [BUG-883]
- **Kind:** bug
- **Expect:** xfail BUG-883
- **Fails today on:** Then 1 (the item's is_active is never looked at, so S2 is returned)

**Given**
1. IA = default item, `name "Old Gasket"`, `is_active False` (a removed catalog item).
2. S1 = default stock of I1 in F1.
3. S2 = default stock of IA in F1, but `qty 12`.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, search="gasket")`.

**Then**
1. returns: `result == []`.

### INV-FQ-34 — stock of a removed item stays hidden whatever the other filters
- **Rules:** `_filtered_query` R11 [BUG-883]
- **Kind:** bug
- **Expect:** xfail BUG-883
- **Fails today on:** Then 1 (the item's is_active is never looked at, so S2 comes back too)

**Given**
1. IA = default item, `name "Old Gasket"`, `is_active False` (a removed catalog item).
2. S1 = default stock of I1 in F1.
3. S2 = default stock of IA in F1, but `qty 12`.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, inventory_type=STORAGE, factory_id=F1.id, include_zero_qty=True)`.

**Then**
1. returns: `ids(result) == [S1.id]`.

### INV-FQ-35 — listing leaves the stock row of a removed item and the item itself untouched
- **Rules:** `_filtered_query` R11c
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. IA = default item, `name "Old Gasket"`, `is_active False` (a removed catalog item).
2. S1 = default stock of I1 in F1.
3. S2 = default stock of IA in F1, but `qty 12`.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `S1.id in ids(result)` (looser check intended: only this membership is asserted).
2. unchanged: unchanged(S2).
3. re-read S2: `is_deleted is False`, `qty == 12`, `item_id == IA.id`.
4. re-read S2: `avg_price == Decimal("2.00")`.
5. unchanged: unchanged(IA).
6. re-read IA: `is_active is False`.
7. count: `inventory` has exactly 2 rows.

### INV-FQ-36 — stock in a soft-deleted factory is not matched
- **Rules:** `_filtered_query` R11a [BUG-882]; `list_filtered` R1a [BUG-882]
- **Kind:** bug
- **Expect:** xfail BUG-882
- **Fails today on:** Then 1 (the factory row is never looked at, so S2 comes back too)

**Given**
1. FA = `factories` row: `name "Old Plant"`, `abbreviation "OP"`, `workspace_id W1.id`, `is_active True`, `is_deleted True` (a soft-deleted factory).
2. S1 = default stock of I1 in F1.
3. S2 = default stock of I1 in FA, but `qty 30`.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [S1.id]`.

### INV-FQ-37 — stock in a soft-deleted factory is not matched by that factory's own id
- **Rules:** `_filtered_query` R11a [BUG-882]; `list_filtered` R1a [BUG-882]
- **Kind:** bug
- **Expect:** xfail BUG-882
- **Fails today on:** Then 1 (the factory row is never looked at, so S2 is returned)

**Given**
1. FA = `factories` row: `name "Old Plant"`, `abbreviation "OP"`, `workspace_id W1.id`, `is_active True`, `is_deleted True` (a soft-deleted factory).
2. S1 = default stock of I1 in F1.
3. S2 = default stock of I1 in FA, but `qty 30`.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, factory_id=FA.id)`.

**Then**
1. returns: `result == []`.

### INV-FQ-38 — stock in a soft-deleted factory stays hidden whatever the other filters
- **Rules:** `_filtered_query` R11a [BUG-882]
- **Kind:** bug
- **Expect:** xfail BUG-882
- **Fails today on:** Then 1 (the factory row is never looked at, so S2 comes back too)

**Given**
1. FA = `factories` row: `name "Old Plant"`, `abbreviation "OP"`, `workspace_id W1.id`, `is_active True`, `is_deleted True` (a soft-deleted factory).
2. S1 = default stock of I1 in F1.
3. S2 = default stock of I1 in FA, but `qty 30`.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, inventory_type=STORAGE, item_id=I1.id, search="bolt", include_zero_qty=True)`.

**Then**
1. returns: `ids(result) == [S1.id]`.

### INV-FQ-39 — stock in an inactive but live factory is matched
- **Rules:** `_filtered_query` R11b
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FB = `factories` row: `name "Idle Plant"`, `abbreviation "IP"`, `workspace_id W1.id`, `is_active False`, `is_deleted False` (inactive but live).
2. S1 = default stock of I1 in FB.
3. S2 = default stock of I1 in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [S1.id, S2.id]`.

### INV-FQ-40 — listing leaves the stock row of a soft-deleted factory untouched
- **Rules:** `_filtered_query` R11b
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. FA = `factories` row: `name "Old Plant"`, `abbreviation "OP"`, `workspace_id W1.id`, `is_active True`, `is_deleted True` (a soft-deleted factory).
2. S1 = default stock of I1 in F1.
3. S2 = default stock of I1 in FA, but `qty 30`.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `S1.id in ids(result)` (looser check intended: only this membership is asserted).
2. unchanged: unchanged(S2).
3. re-read S2: `is_deleted is False`, `qty == 30`, `factory_id == FA.id`.
4. re-read S2: `avg_price == Decimal("2.00")`.
5. count: `inventory` has exactly 2 rows.


## `InventoryDAO.list_filtered`

### INV-L-01 — returns a list of Inventory rows with the item loaded
- **Rules:** `list_filtered` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `len(result) == 1`.
3. returns: `isinstance(result[0], Inventory)`.
4. returns: `result[0].id == S1.id`.
5. returns: `result[0].item_name == "Bolt"`.
6. returns: `result[0].item_unit == "pcs"`.

### INV-L-02 — rows are ordered by item name ignoring case
- **Rules:** `list_filtered` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. IA = default item, `name "Zulu"`.
2. IB = default item, `name "apple"`.
3. IC = default item, `name "Banana"`.
4. S1 = default stock of IA in F1.
5. S2 = default stock of IB in F1.
6. S3 = default stock of IC in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `names(result) == ["apple", "Banana", "Zulu"]`.

### INV-L-03 — rows of the same item come back lower id first, after earlier names
- **Rules:** `list_filtered` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. IA = default item, `name "Apple"`.
2. S1 = default stock of I1 in F2.
3. S2 = default stock of I1 in F1.
4. S3 = default stock of IA in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `[row.id for row in result] == [S3.id, S1.id, S2.id]`.

### INV-L-04 — item names differing only in case come back in stock-row id order (upper case first)
- **Rules:** `list_filtered` R2 [BUG-701]
- **Kind:** bug
- **Expect:** xfail BUG-701
- **Fails today on:** Then 2 (the database collation puts "bolt" before "Bolt" whatever the ids)

**Given**
1. IB = default item, `name "bolt"`, `name_normalized "bolt lower"`. (I1 is the item named "Bolt".)
2. S1 = default stock of I1 in F1.
3. S2 = default stock of IB in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `names(result) == ["Bolt", "bolt"]`.

### INV-L-05 — item names differing only in case come back in stock-row id order (lower case first)
- **Rules:** `list_filtered` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. IB = default item, `name "bolt"`, `name_normalized "bolt lower"`. (I1 is the item named "Bolt".)
2. S1 = default stock of IB in F1.
3. S2 = default stock of I1 in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `names(result) == ["bolt", "Bolt"]`.

### INV-L-06 — first window of two
- **Rules:** `list_filtered` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. IA = default item, `name "Echo"`.
2. IB = default item, `name "Delta"`.
3. IC = default item, `name "Charlie"`.
4. ID = default item, `name "Bravo"`.
5. IE = default item, `name "Alpha"`.
6. S1 = default stock of IA in F1.
7. S2 = default stock of IB in F1.
8. S3 = default stock of IC in F1.
9. S4 = default stock of ID in F1.
10. S5 = default stock of IE in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, skip=0, limit=2)`.

**Then**
1. returns: `names(result) == ["Alpha", "Bravo"]`.

### INV-L-07 — second window of two continues without repeat or gap
- **Rules:** `list_filtered` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. IA = default item, `name "Echo"`.
2. IB = default item, `name "Delta"`.
3. IC = default item, `name "Charlie"`.
4. ID = default item, `name "Bravo"`.
5. IE = default item, `name "Alpha"`.
6. S1 = default stock of IA in F1.
7. S2 = default stock of IB in F1.
8. S3 = default stock of IC in F1.
9. S4 = default stock of ID in F1.
10. S5 = default stock of IE in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, skip=2, limit=2)`.

**Then**
1. returns: `names(result) == ["Charlie", "Delta"]`.

### INV-L-08 — last window is short
- **Rules:** `list_filtered` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. IA = default item, `name "Echo"`.
2. IB = default item, `name "Delta"`.
3. IC = default item, `name "Charlie"`.
4. ID = default item, `name "Bravo"`.
5. IE = default item, `name "Alpha"`.
6. S1 = default stock of IA in F1.
7. S2 = default stock of IB in F1.
8. S3 = default stock of IC in F1.
9. S4 = default stock of ID in F1.
10. S5 = default stock of IE in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, skip=4, limit=2)`.

**Then**
1. returns: `names(result) == ["Echo"]`.

### INV-L-09 — skip and limit are applied after filtering
- **Rules:** `list_filtered` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. IA = default item, `name "Echo"`.
2. IB = default item, `name "Delta"`.
3. IC = default item, `name "Charlie"`.
4. ID = default item, `name "Bravo"`.
5. IE = default item, `name "Alpha"`.
6. S1 = default stock of IA in F1.
7. S2 = default stock of IB in F1.
8. S3 = default stock of IC in F1, but `qty 0`.
9. S4 = default stock of ID in F1.
10. S5 = default stock of IE in F1, but `qty 0`.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `names(result) == ["Delta"]`.

### INV-L-10 — default limit returns the first 100 of 101 rows
- **Rules:** `list_filtered` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 default items with `name "Item 001"`, `"Item 002"`, … `"Item 101"` (three digits each), created in that order.
2. For each of those 101 items, one default stock of that item in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `names(result)[0] == "Item 001"`.
3. returns: `names(result)[-1] == "Item 100"`.

### INV-L-11 — an explicit limit of 101 returns all 101 rows
- **Rules:** `list_filtered` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 default items with `name "Item 001"`, `"Item 002"`, … `"Item 101"` (three digits each), created in that order.
2. For each of those 101 items, one default stock of that item in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, limit=101)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `names(result)[-1] == "Item 101"`.

### INV-L-12 — limit 0 returns an empty list
- **Rules:** `list_filtered` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### INV-L-13 — skip equal to the number of matching rows returns an empty list
- **Rules:** `list_filtered` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I2 in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### INV-L-14 — skip one below the number of matching rows returns the last row
- **Rules:** `list_filtered` R4, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I2 in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [S2.id]`.

### INV-L-15 — a workspace with no stock rows returns an empty list
- **Rules:** `list_filtered` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### INV-L-16 — an unknown workspace id returns an empty list
- **Rules:** `list_filtered` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### INV-L-17 — negative limit is rejected by the database and nothing changes
- **Rules:** `list_filtered` R5, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.

**When**
- `dao.list_filtered(db, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `exc.value.orig.pgcode == "2201W"`.
4. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.
6. unchanged: unchanged(S1).

### INV-L-18 — negative skip is rejected by the database and nothing changes
- **Rules:** `list_filtered` R5, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.

**When**
- `dao.list_filtered(db, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `exc.value.orig.pgcode == "2201X"`.
4. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.
6. unchanged: unchanged(S1).

### INV-L-19 — a row in a soft-deleted factory does not use up a place in the page
- **Rules:** `list_filtered` R1a [BUG-882]
- **Kind:** bug
- **Expect:** xfail BUG-882
- **Fails today on:** Then 2 (the row of the deleted factory sorts first and is the one returned)

**Given**
1. FA = `factories` row: `name "Old Plant"`, `abbreviation "OP"`, `workspace_id W1.id`, `is_active True`, `is_deleted True` (a soft-deleted factory).
2. S1 = default stock of I1 in FA, but `qty 30`. (Inserted first, so it has the lower id.)
3. S2 = default stock of I1 in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id == S2.id`.

### INV-L-20 — with limit 1 the live-factory row is returned when it has the lower id
- **Rules:** `list_filtered` R1, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. FA = `factories` row: `name "Old Plant"`, `abbreviation "OP"`, `workspace_id W1.id`, `is_active True`, `is_deleted True` (a soft-deleted factory).
2. S1 = default stock of I1 in F1.
3. S2 = default stock of I1 in FA, but `qty 30`.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id == S1.id`.

### INV-L-21 — a row of a removed item does not use up a place in the page
- **Rules:** `list_filtered` R1b [BUG-883]
- **Kind:** bug
- **Expect:** xfail BUG-883
- **Fails today on:** Then 2 (the row of the removed item Anvil sorts first and is the one returned)

**Given**
1. IA = default item, `name "Anvil"`, `is_active False` (a removed catalog item).
2. S1 = default stock of IA in F1, but `qty 12`.
3. S2 = default stock of I1 in F1.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id == S2.id`.

### INV-L-22 — with limit 1 the active item's row is returned when its name sorts first
- **Rules:** `list_filtered` R1, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. IA = default item, `name "Old Gasket"`, `is_active False` (a removed catalog item).
2. S1 = default stock of I1 in F1.
3. S2 = default stock of IA in F1, but `qty 12`.

**When**
- `result = dao.list_filtered(db, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id == S1.id`.


## `InventoryDAO.count_filtered`

### INV-CNT-01 — counts stock rows, not distinct items
- **Rules:** `count_filtered` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I1 in F2.
3. S3 = default stock of I2 in F1.

**When**
- `result = dao.count_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == 3`.
2. returns: `type(result) is int`.

### INV-CNT-02 — deleted, zero-quantity and other-workspace rows are not counted
- **Rules:** `count_filtered` R1; `_filtered_query` R1, R2, R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I2 in F1, but deleted.
3. S3 = default stock of I1 in F2, but `qty 0`.
4. S9.

**When**
- `result = dao.count_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == 1`.

### INV-CNT-03 — include_zero_qty True also counts the zero-quantity row
- **Rules:** `count_filtered` R1; `_filtered_query` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I2 in F1, but deleted.
3. S3 = default stock of I1 in F2, but `qty 0`.
4. S9.

**When**
- `result = dao.count_filtered(db, workspace_id=W1.id, include_zero_qty=True)`.

**Then**
1. returns: `result == 2`.

### INV-CNT-04 — type and factory filters apply to the count
- **Rules:** `count_filtered` R1; `_filtered_query` R4, R5, R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I1 in F1, but `inventory_type DAMAGED`.
3. S3 = default stock of I1 in F2, but `inventory_type DAMAGED`.

**When**
- `result = dao.count_filtered(db, workspace_id=W1.id, inventory_type=DAMAGED, factory_id=F1.id)`.

**Then**
1. returns: `result == 1`.

### INV-CNT-05 — item filter applies to the count
- **Rules:** `count_filtered` R1; `_filtered_query` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I2 in F1.
3. S3 = default stock of I2 in F2.

**When**
- `result = dao.count_filtered(db, workspace_id=W1.id, item_id=I2.id)`.

**Then**
1. returns: `result == 2`.

### INV-CNT-06 — search applies to the count
- **Rules:** `count_filtered` R1; `_filtered_query` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I2 in F1.
3. S3 = default stock of I2 in F2.

**When**
- `result = dao.count_filtered(db, workspace_id=W1.id, search=" NUT ")` — one space before and one after.

**Then**
1. returns: `result == 2`.

### INV-CNT-07 — factory_id 0 counts nothing
- **Rules:** `count_filtered` R1; `_filtered_query` R5 [BUG-880]
- **Kind:** bug
- **Expect:** xfail BUG-880
- **Fails today on:** Then 1 (factory_id 0 is treated as no filter, so the count is 2)

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I1 in F2.

**When**
- `result = dao.count_filtered(db, workspace_id=W1.id, factory_id=0)`.

**Then**
1. returns: `result == 0`.

### INV-CNT-08 — a workspace with no stock rows counts 0 as an int
- **Rules:** `count_filtered` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.

**When**
- `result = dao.count_filtered(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == 0`.
2. returns: `type(result) is int`.

### INV-CNT-09 — an unknown workspace id counts 0 as an int
- **Rules:** `count_filtered` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.

**When**
- `result = dao.count_filtered(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == 0`.
2. returns: `type(result) is int`.

### INV-CNT-10 — stock in a soft-deleted factory is not counted
- **Rules:** `count_filtered` R1a [BUG-882]; `_filtered_query` R11a [BUG-882]
- **Kind:** bug
- **Expect:** xfail BUG-882
- **Fails today on:** Then 1 (the factory row is never looked at, so the count is 2)

**Given**
1. FA = `factories` row: `name "Old Plant"`, `abbreviation "OP"`, `workspace_id W1.id`, `is_active True`, `is_deleted True` (a soft-deleted factory).
2. S1 = default stock of I1 in F1.
3. S2 = default stock of I1 in FA, but `qty 30`.

**When**
- `result = dao.count_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == 1`.

### INV-CNT-11 — filtering by a soft-deleted factory counts nothing
- **Rules:** `count_filtered` R1a [BUG-882]; `_filtered_query` R11a [BUG-882]
- **Kind:** bug
- **Expect:** xfail BUG-882
- **Fails today on:** Then 1 (the factory row is never looked at, so the count is 1)

**Given**
1. FA = `factories` row: `name "Old Plant"`, `abbreviation "OP"`, `workspace_id W1.id`, `is_active True`, `is_deleted True` (a soft-deleted factory).
2. S1 = default stock of I1 in F1.
3. S2 = default stock of I1 in FA, but `qty 30`.

**When**
- `result = dao.count_filtered(db, workspace_id=W1.id, factory_id=FA.id)`.

**Then**
1. returns: `result == 0`.

### INV-CNT-12 — stock of a removed catalog item is not counted
- **Rules:** `count_filtered` R1b [BUG-883]; `_filtered_query` R11 [BUG-883]
- **Kind:** bug
- **Expect:** xfail BUG-883
- **Fails today on:** Then 1 (the item's is_active is never looked at, so the count is 2)

**Given**
1. IA = default item, `name "Old Gasket"`, `is_active False` (a removed catalog item).
2. S1 = default stock of I1 in F1.
3. S2 = default stock of IA in F1, but `qty 12`.

**When**
- `result = dao.count_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == 1`.

### INV-CNT-13 — filtering by a removed item's id counts nothing
- **Rules:** `count_filtered` R1b [BUG-883]; `_filtered_query` R11 [BUG-883]
- **Kind:** bug
- **Expect:** xfail BUG-883
- **Fails today on:** Then 1 (the item's is_active is never looked at, so the count is 1)

**Given**
1. IA = default item, `name "Old Gasket"`, `is_active False` (a removed catalog item).
2. S1 = default stock of I1 in F1.
3. S2 = default stock of IA in F1, but `qty 12`.

**When**
- `result = dao.count_filtered(db, workspace_id=W1.id, item_id=IA.id)`.

**Then**
1. returns: `result == 0`.

### INV-CNT-14 — searching for a removed item's name counts nothing
- **Rules:** `count_filtered` R1b [BUG-883]; `_filtered_query` R11 [BUG-883]
- **Kind:** bug
- **Expect:** xfail BUG-883
- **Fails today on:** Then 1 (the item's is_active is never looked at, so the count is 1)

**Given**
1. IA = default item, `name "Old Gasket"`, `is_active False` (a removed catalog item).
2. S1 = default stock of I1 in F1.
3. S2 = default stock of IA in F1, but `qty 12`.

**When**
- `result = dao.count_filtered(db, workspace_id=W1.id, search="gasket")`.

**Then**
1. returns: `result == 0`.

### INV-CNT-15 — stock in an inactive but live factory is counted
- **Rules:** `count_filtered` R1; `_filtered_query` R11b
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FB = `factories` row: `name "Idle Plant"`, `abbreviation "IP"`, `workspace_id W1.id`, `is_active False`, `is_deleted False` (inactive but live).
2. S1 = default stock of I1 in FB.
3. S2 = default stock of I1 in F1.

**When**
- `result = dao.count_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == 2`.


## `InventoryDAO.stats_filtered`

### INV-ST-01 — records, total quantity and value; a NULL price adds no value
- **Rules:** `stats_filtered` R1, R2, R3, R4, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `qty 5`, `avg_price Decimal("2.50")`.
2. S2 = default stock of I2 in F1, but `qty 4`, `avg_price Decimal("3.33")`.
3. S3 = default stock of I1 in F2, but `qty 8`, `avg_price None`.

**When**
- `result = dao.stats_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `type(result) is tuple`.
2. returns: `len(result) == 4`.
3. returns: `result[0] == 3`.
4. returns: `type(result[0]) is int`.
5. returns: `result[1] == 17`.
6. returns: `type(result[1]) is int`.
7. returns: `result[2] == Decimal("25.82")`.
8. returns: `isinstance(result[2], Decimal)`.
9. returns: `by_type(result) == {(STORAGE, 2, 17)}`.
10. returns: `len(result[3]) == 1`.

### INV-ST-02 — per-type rows count distinct items and sum quantity
- **Rules:** `stats_filtered` R5, R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `qty 5`.
2. S2 = default stock of I1 in F2, but `qty 4`.
3. S3 = default stock of I2 in F1, but `qty 1`.
4. S4 = default stock of I1 in F1, but `inventory_type SCRAP`, `qty 3`.

**When**
- `result = dao.stats_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `result[0] == 4`.
2. returns: `result[1] == 13`.
3. returns: `result[2] == Decimal("26.00")`.
4. returns: `by_type(result) == {(STORAGE, 2, 10), (SCRAP, 1, 3)}`.
5. returns: `len(result[3]) == 2`.

### INV-ST-03 — per-type rows come back in enum order STORAGE, DAMAGED, WASTE, SCRAP
- **Rules:** `stats_filtered` R6 [BUG-719]
- **Kind:** bug
- **Expect:** xfail BUG-719 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; the database's grouping may happen to give this order, so the test may pass today — non-strict xfail, the assertion is never weakened)
- **Author:** claude — non-strict xfail (`pytest.mark.xfail(strict=False, reason="BUG-719")`)

**Given**
1. S1 = default stock of I1 in F1, but `inventory_type SCRAP`.
2. S2 = default stock of I1 in F1, but `inventory_type WASTE`.
3. S3 = default stock of I1 in F1, but `inventory_type DAMAGED`.
4. S4 = default stock of I1 in F1. (STORAGE, inserted last.)

**When**
- `result = dao.stats_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result[3]) == 4`.
2. returns: `[r[0] for r in result[3]] == [STORAGE, DAMAGED, WASTE, SCRAP]`.

### INV-ST-04 — include_zero_qty True: zero rows count and negative rows subtract
- **Rules:** `stats_filtered` R1, R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I2 in F1, but `qty 0`, `avg_price Decimal("3.00")`.
3. S3 = default stock of I1 in F2, but `qty -2`, `avg_price Decimal("1.00")`.

**When**
- `result = dao.stats_filtered(db, workspace_id=W1.id, include_zero_qty=True)`.

**Then**
1. returns: `result[0] == 3`.
2. returns: `result[1] == 3`.
3. returns: `result[2] == Decimal("8.00")`.
4. returns: `by_type(result) == {(STORAGE, 2, 3)}`.

### INV-ST-05 — default: zero and negative rows are left out of every part
- **Rules:** `stats_filtered` R1, R3, R4; `_filtered_query` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I2 in F1, but `qty 0`, `avg_price Decimal("3.00")`.
3. S3 = default stock of I1 in F2, but `qty -2`, `avg_price Decimal("1.00")`.

**When**
- `result = dao.stats_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `result[0] == 1`.
2. returns: `result[1] == 5`.
3. returns: `result[2] == Decimal("10.00")`.
4. returns: `by_type(result) == {(STORAGE, 1, 5)}`.

### INV-ST-06 — include_zero_qty True: a type whose only row has qty 0 appears with total 0
- **Rules:** `stats_filtered` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I1 in F1, but `inventory_type DAMAGED`, `qty 0`.

**When**
- `result = dao.stats_filtered(db, workspace_id=W1.id, include_zero_qty=True)`.

**Then**
1. returns: `result[0] == 2`.
2. returns: `by_type(result) == {(STORAGE, 1, 5), (DAMAGED, 1, 0)}`.
3. returns: `len(result[3]) == 2`.

### INV-ST-07 — a type with no matched row is absent from the per-type rows
- **Rules:** `stats_filtered` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I1 in F1, but `inventory_type DAMAGED`, `qty 0`.

**When**
- `result = dao.stats_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `result[0] == 1`.
2. returns: `by_type(result) == {(STORAGE, 1, 5)}`.
3. returns: `len(result[3]) == 1`.

### INV-ST-08 — a workspace with no stock rows gives zeros and an empty list
- **Rules:** `stats_filtered` R7
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.

**When**
- `result = dao.stats_filtered(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == (0, 0, Decimal("0"), [])`.
2. returns: `type(result[0]) is int`.
3. returns: `type(result[1]) is int`.
4. returns: `isinstance(result[2], Decimal)`.
5. returns: `isinstance(result[3], list)`.

### INV-ST-09 — an unknown workspace id gives zeros and an empty list
- **Rules:** `stats_filtered` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.

**When**
- `result = dao.stats_filtered(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == (0, 0, Decimal("0"), [])`.
2. returns: `type(result[0]) is int`.
3. returns: `type(result[1]) is int`.
4. returns: `isinstance(result[2], Decimal)`.
5. returns: `isinstance(result[3], list)`.

### INV-ST-10 — filters matching no row give zeros and an empty list
- **Rules:** `stats_filtered` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.

**When**
- `result = dao.stats_filtered(db, workspace_id=W1.id, inventory_type=WASTE)`.

**Then**
1. returns: `result == (0, 0, Decimal("0"), [])`.
2. returns: `type(result[0]) is int`.
3. returns: `type(result[1]) is int`.
4. returns: `isinstance(result[2], Decimal)`.
5. returns: `isinstance(result[3], list)`.

### INV-ST-11 — when every matched price is NULL the value is Decimal zero, not None
- **Rules:** `stats_filtered` R8, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `avg_price None`.
2. S2 = default stock of I2 in F1, but `qty 3`, `avg_price None`.

**When**
- `result = dao.stats_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `result[0] == 2`.
2. returns: `result[1] == 8`.
3. returns: `result[2] == Decimal("0")`.
4. returns: `isinstance(result[2], Decimal)`.

### INV-ST-12 — factory filter, soft-delete and workspace scope apply to every part
- **Rules:** `stats_filtered` R1; `_filtered_query` R1, R2, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I2 in F1, but deleted, `qty 7`.
3. S3 = default stock of I1 in F2, but `qty 4`.
4. S9.

**When**
- `result = dao.stats_filtered(db, workspace_id=W1.id, factory_id=F1.id)`.

**Then**
1. returns: `result[0] == 1`.
2. returns: `result[1] == 5`.
3. returns: `result[2] == Decimal("10.00")`.
4. returns: `by_type(result) == {(STORAGE, 1, 5)}`.

### INV-ST-13 — without filters the same rows give the workspace's live totals
- **Rules:** `stats_filtered` R1, R2, R5; `_filtered_query` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I2 in F1, but deleted, `qty 7`.
3. S3 = default stock of I1 in F2, but `qty 4`.
4. S9.

**When**
- `result = dao.stats_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `result[0] == 2`.
2. returns: `result[1] == 9`.
3. returns: `result[2] == Decimal("18.00")`.
4. returns: `by_type(result) == {(STORAGE, 1, 9)}`.

### INV-ST-14 — search applies to every part
- **Rules:** `stats_filtered` R1; `_filtered_query` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I2 in F1, but `qty 3`.
3. S3 = default stock of I1 in F1, but `inventory_type DAMAGED`, `qty 2`, `avg_price Decimal("4.00")`.

**When**
- `result = dao.stats_filtered(db, workspace_id=W1.id, search="bolt")`.

**Then**
1. returns: `result[0] == 2`.
2. returns: `result[1] == 7`.
3. returns: `result[2] == Decimal("18.00")`.
4. returns: `by_type(result) == {(STORAGE, 1, 5), (DAMAGED, 1, 2)}`.

### INV-ST-15 — type and item filters apply to every part
- **Rules:** `stats_filtered` R1; `_filtered_query` R4, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I2 in F1, but `qty 3`.
3. S3 = default stock of I1 in F1, but `inventory_type DAMAGED`, `qty 2`, `avg_price Decimal("4.00")`.

**When**
- `result = dao.stats_filtered(db, workspace_id=W1.id, inventory_type=DAMAGED, item_id=I1.id)`.

**Then**
1. returns: `result[0] == 1`.
2. returns: `result[1] == 2`.
3. returns: `result[2] == Decimal("8.00")`.
4. returns: `by_type(result) == {(DAMAGED, 1, 2)}`.

### INV-ST-16 — factory_id 0 gives zero statistics
- **Rules:** `stats_filtered` R1; `_filtered_query` R5 [BUG-880]
- **Kind:** bug
- **Expect:** xfail BUG-880
- **Fails today on:** Then 1 (factory_id 0 is treated as no filter, so records is 2)

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I1 in F2.

**When**
- `result = dao.stats_filtered(db, workspace_id=W1.id, factory_id=0)`.

**Then**
1. returns: `result[0] == 0`.
2. returns: `result[1] == 0`.
3. returns: `result[3] == []`.

### INV-ST-17 — each per-type row is a 3-item Row: type member, int, int
- **Rules:** `stats_filtered` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.

**When**
- `result = dao.stats_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result[3], list)`.
2. returns: `isinstance(result[3][0], Row)`.
3. returns: `len(result[3][0]) == 3`.
4. returns: `isinstance(result[3][0][0], InventoryTypeEnum)`.
5. returns: `type(result[3][0][1]) is int`.
6. returns: `type(result[3][0][2]) is int`.
7. returns: unpacking works — `t, n, q = result[3][0]`, then `(t, n, q) == (STORAGE, 1, 5)`.

### INV-ST-18 — stock in a soft-deleted factory adds nothing to the totals
- **Rules:** `stats_filtered` R1a [BUG-882]; `_filtered_query` R11a [BUG-882]
- **Kind:** bug
- **Expect:** xfail BUG-882
- **Fails today on:** Then 1 (the factory row is never looked at, so records is 2)

**Given**
1. FA = `factories` row: `name "Old Plant"`, `abbreviation "OP"`, `workspace_id W1.id`, `is_active True`, `is_deleted True` (a soft-deleted factory).
2. S1 = default stock of I1 in F1.
3. S2 = default stock of I1 in FA, but `qty 30`, `avg_price Decimal("1.00")`.

**When**
- `result = dao.stats_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `result[0] == 1`.
2. returns: `result[1] == 5`.
3. returns: `result[2] == Decimal("10.00")`.

### INV-ST-19 — filtering by a soft-deleted factory gives the empty result
- **Rules:** `stats_filtered` R1a [BUG-882]; `_filtered_query` R11a [BUG-882]
- **Kind:** bug
- **Expect:** xfail BUG-882
- **Fails today on:** Then 1 (the factory row is never looked at, so the result has records 1 and total_qty 30)

**Given**
1. FA = `factories` row: `name "Old Plant"`, `abbreviation "OP"`, `workspace_id W1.id`, `is_active True`, `is_deleted True` (a soft-deleted factory).
2. S1 = default stock of I1 in F1.
3. S2 = default stock of I1 in FA, but `qty 30`, `avg_price Decimal("1.00")`.

**When**
- `result = dao.stats_filtered(db, workspace_id=W1.id, factory_id=FA.id)`.

**Then**
1. returns: `result == (0, 0, Decimal("0"), [])`.

### INV-ST-20 — stock in a soft-deleted factory is absent from the per-type rows
- **Rules:** `stats_filtered` R5a [BUG-882]; `_filtered_query` R11a [BUG-882]
- **Kind:** bug
- **Expect:** xfail BUG-882
- **Fails today on:** Then 1 (the factory row is never looked at, so the rows are (STORAGE, 2, 37) and (SCRAP, 1, 3))

**Given**
1. FA = `factories` row: `name "Old Plant"`, `abbreviation "OP"`, `workspace_id W1.id`, `is_active True`, `is_deleted True` (a soft-deleted factory).
2. S1 = default stock of I1 in F1.
3. S2 = default stock of I1 in FA, but `qty 30`.
4. S3 = default stock of I2 in FA, but `qty 2`.
5. S4 = default stock of I1 in FA, but `inventory_type SCRAP`, `qty 3`.

**When**
- `result = dao.stats_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `by_type(result) == {(STORAGE, 1, 5)}`.
2. returns: `len(result[3]) == 1`.

### INV-ST-21 — stock of a removed catalog item adds nothing to the totals
- **Rules:** `stats_filtered` R1b [BUG-883]; `_filtered_query` R11 [BUG-883]
- **Kind:** bug
- **Expect:** xfail BUG-883
- **Fails today on:** Then 1 (the item's is_active is never looked at, so records is 2)

**Given**
1. IA = default item, `name "Old Gasket"`, `is_active False` (a removed catalog item).
2. S1 = default stock of I1 in F1.
3. S2 = default stock of IA in F1, but `qty 12`, `avg_price Decimal("5.00")`.

**When**
- `result = dao.stats_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `result[0] == 1`.
2. returns: `result[1] == 5`.
3. returns: `result[2] == Decimal("10.00")`.

### INV-ST-22 — filtering by a removed item's id gives the empty result
- **Rules:** `stats_filtered` R1b [BUG-883]; `_filtered_query` R11 [BUG-883]
- **Kind:** bug
- **Expect:** xfail BUG-883
- **Fails today on:** Then 1 (the item's is_active is never looked at, so the result has records 1 and total_qty 12)

**Given**
1. IA = default item, `name "Old Gasket"`, `is_active False` (a removed catalog item).
2. S1 = default stock of I1 in F1.
3. S2 = default stock of IA in F1, but `qty 12`, `avg_price Decimal("5.00")`.

**When**
- `result = dao.stats_filtered(db, workspace_id=W1.id, item_id=IA.id)`.

**Then**
1. returns: `result == (0, 0, Decimal("0"), [])`.

### INV-ST-23 — searching for a removed item's name gives the empty result
- **Rules:** `stats_filtered` R1b [BUG-883]; `_filtered_query` R11 [BUG-883]
- **Kind:** bug
- **Expect:** xfail BUG-883
- **Fails today on:** Then 1 (the item's is_active is never looked at, so the result has records 1 and total_qty 12)

**Given**
1. IA = default item, `name "Old Gasket"`, `is_active False` (a removed catalog item).
2. S1 = default stock of I1 in F1.
3. S2 = default stock of IA in F1, but `qty 12`, `avg_price Decimal("5.00")`.

**When**
- `result = dao.stats_filtered(db, workspace_id=W1.id, search="gasket")`.

**Then**
1. returns: `result == (0, 0, Decimal("0"), [])`.

### INV-ST-24 — stock of a removed item is absent from the per-type rows
- **Rules:** `stats_filtered` R5b [BUG-883]; `_filtered_query` R11 [BUG-883]
- **Kind:** bug
- **Expect:** xfail BUG-883
- **Fails today on:** Then 1 (the item's is_active is never looked at, so the rows are (STORAGE, 2, 17) and (SCRAP, 1, 3))

**Given**
1. IA = default item, `name "Old Gasket"`, `is_active False` (a removed catalog item).
2. S1 = default stock of I1 in F1.
3. S2 = default stock of IA in F1, but `qty 12`.
4. S3 = default stock of IA in F1, but `inventory_type SCRAP`, `qty 3`.

**When**
- `result = dao.stats_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `by_type(result) == {(STORAGE, 1, 5)}`.
2. returns: `len(result[3]) == 1`.

### INV-ST-25 — stock in an inactive but live factory is in the totals
- **Rules:** `stats_filtered` R1; `_filtered_query` R11b
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FB = `factories` row: `name "Idle Plant"`, `abbreviation "IP"`, `workspace_id W1.id`, `is_active False`, `is_deleted False` (inactive but live).
2. S1 = default stock of I1 in FB, but `qty 30`.
3. S2 = default stock of I1 in F1.

**When**
- `result = dao.stats_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `result[0] == 2`.
2. returns: `result[1] == 35`.
3. returns: `result[2] == Decimal("70.00")`.
4. returns: `by_type(result) == {(STORAGE, 1, 35)}`.


## `InventoryDAO.get_by_id_and_workspace`

### INV-GIW-01 — returns the row with that id in that workspace
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I2 in F1.

**When**
- `result = dao.get_by_id_and_workspace(db, id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == S1.id`.

### INV-GIW-02 — an id of another workspace returns None
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.

**When**
- `result = dao.get_by_id_and_workspace(db, id=S1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### INV-GIW-03 — an unknown id returns None
- **Rules:** `get_by_id_and_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.

**When**
- `result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### INV-GIW-04 — a soft-deleted row is still returned
- **Rules:** `get_by_id_and_workspace` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but deleted.

**When**
- `result = dao.get_by_id_and_workspace(db, id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == S1.id`.
2. returns: `result.is_deleted is True`.

### INV-GIW-05 — a row with qty 0 is returned
- **Rules:** `get_by_id_and_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `qty 0`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == S1.id`.
2. returns: `result.qty == 0`.

### INV-GIW-06 — a row with negative qty is returned
- **Rules:** `get_by_id_and_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `qty -3`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == S1.id`.
2. returns: `result.qty == -3`.

### INV-GIW-07 — a row whose factory is soft-deleted is still returned by id
- **Rules:** `get_by_id_and_workspace` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FA = `factories` row: `name "Old Plant"`, `abbreviation "OP"`, `workspace_id W1.id`, `is_active True`, `is_deleted True` (a soft-deleted factory).
2. S1 = default stock of I1 in FA.

**When**
- `result = dao.get_by_id_and_workspace(db, id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == S1.id`.
2. returns: `result.factory_id == FA.id`.

### INV-GIW-08 — a row whose item has been removed is still returned by id
- **Rules:** `get_by_id_and_workspace` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. IA = default item, `name "Old Gasket"`, `is_active False` (a removed catalog item).
2. S1 = default stock of IA in F1.

**When**
- `result = dao.get_by_id_and_workspace(db, id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == S1.id`.
2. returns: `result.item_id == IA.id`.


## `InventoryDAO.get_by_factory_item_type`

### INV-GF-01 — returns the live row of the exact bucket among neighbouring buckets
- **Rules:** `get_by_factory_item_type` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I1 in F2.
3. S3 = default stock of I2 in F1.
4. S4 = default stock of I1 in F1, but `inventory_type DAMAGED`.

**When**
- `result = dao.get_by_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == S1.id`.

### INV-GF-02 — a row that differs only by workspace is not returned
- **Rules:** `get_by_factory_item_type` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S9.

**When**
- `result = dao.get_by_factory_item_type(db, factory_id=F9.id, item_id=I9.id, inventory_type=STORAGE, workspace_id=W1.id)` — S9's factory, item and type, but workspace W1.

**Then**
1. returns: `result is None`.

### INV-GF-03 — a row that differs only by factory is not returned
- **Rules:** `get_by_factory_item_type` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.

**When**
- `result = dao.get_by_factory_item_type(db, factory_id=F2.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### INV-GF-04 — a row that differs only by item is not returned
- **Rules:** `get_by_factory_item_type` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.

**When**
- `result = dao.get_by_factory_item_type(db, factory_id=F1.id, item_id=I2.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### INV-GF-05 — a row that differs only by type is not returned
- **Rules:** `get_by_factory_item_type` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.

**When**
- `result = dao.get_by_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=DAMAGED, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### INV-GF-06 — a soft-deleted bucket row returns None
- **Rules:** `get_by_factory_item_type` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but deleted.

**When**
- `result = dao.get_by_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### INV-GF-07 — a live row with is_active False is returned
- **Rules:** `get_by_factory_item_type` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `is_active False`.

**When**
- `result = dao.get_by_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == S1.id`.

### INV-GF-08 — a live row with qty 0 is returned
- **Rules:** `get_by_factory_item_type` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `qty 0`.

**When**
- `result = dao.get_by_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == S1.id`.

### INV-GF-09 — a live row with negative qty is returned
- **Rules:** `get_by_factory_item_type` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `qty -4`.

**When**
- `result = dao.get_by_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == S1.id`.

### INV-GF-10 — the live row of a bucket in a soft-deleted factory is returned
- **Rules:** `get_by_factory_item_type` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FA = `factories` row: `name "Old Plant"`, `abbreviation "OP"`, `workspace_id W1.id`, `is_active True`, `is_deleted True` (a soft-deleted factory).
2. S1 = default stock of I1 in FA.

**When**
- `result = dao.get_by_factory_item_type(db, factory_id=FA.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == S1.id`.

### INV-GF-11 — the live row of a bucket of a removed item is returned
- **Rules:** `get_by_factory_item_type` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. IA = default item, `name "Old Gasket"`, `is_active False` (a removed catalog item).
2. S1 = default stock of IA in F1.

**When**
- `result = dao.get_by_factory_item_type(db, factory_id=F1.id, item_id=IA.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == S1.id`.


## `InventoryDAO._get_any_by_factory_item_type`

### INV-GA-01 — returns the live row of the exact bucket among neighbouring buckets
- **Rules:** `_get_any_by_factory_item_type` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I1 in F2.
3. S3 = default stock of I2 in F1.
4. S4 = default stock of I1 in F1, but `inventory_type DAMAGED`.

**When**
- `result = dao._get_any_by_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == S1.id`.

### INV-GA-02 — a row that differs only by workspace is not returned
- **Rules:** `_get_any_by_factory_item_type` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S9.

**When**
- `result = dao._get_any_by_factory_item_type(db, factory_id=F9.id, item_id=I9.id, inventory_type=STORAGE, workspace_id=W1.id)` — S9's factory, item and type, but workspace W1.

**Then**
1. returns: `result is None`.

### INV-GA-03 — a row that differs only by factory is not returned
- **Rules:** `_get_any_by_factory_item_type` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.

**When**
- `result = dao._get_any_by_factory_item_type(db, factory_id=F2.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### INV-GA-04 — a row that differs only by item is not returned
- **Rules:** `_get_any_by_factory_item_type` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.

**When**
- `result = dao._get_any_by_factory_item_type(db, factory_id=F1.id, item_id=I2.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### INV-GA-05 — a row that differs only by type is not returned
- **Rules:** `_get_any_by_factory_item_type` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.

**When**
- `result = dao._get_any_by_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=DAMAGED, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### INV-GA-06 — a soft-deleted bucket row is returned
- **Rules:** `_get_any_by_factory_item_type` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but deleted.

**When**
- `result = dao._get_any_by_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == S1.id`.
2. returns: `result.is_deleted is True`.

### INV-GA-07 — no row at all for the bucket returns None
- **Rules:** `_get_any_by_factory_item_type` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No stock rows and no ledger entries exist.

**When**
- `result = dao._get_any_by_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.


## `InventoryDAO.sync_snapshot_from_ledger`

### INV-SY-01 — row takes the values of the entry with the greatest performed_at and is stamped
- **Rules:** `sync_snapshot_from_ledger` R1, R5, R11
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `qty 7`, `avg_price Decimal("5.00")`.
2. E1 = entry of I1 in F1: `qty_after 20`, `avg_price_after Decimal("6.00")`, `performed_at T3`.
3. E2 = entry of I1 in F1: `qty_after 30`, `avg_price_after Decimal("7.00")`, `performed_at T1`.
4. E3 = entry of I1 in F1: `qty_after 10`, `avg_price_after Decimal("4.00")`, `performed_at T2`.

**When**
- `result = dao.sync_snapshot_from_ledger(db, inv=S1, workspace_id=W1.id, updated_by=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. re-read S1: `qty == 20`.
3. re-read S1: `avg_price == Decimal("6.00")`.
4. re-read S1: `updated_by == U2.id`.
5. re-read S1: `updated_at is not None`.
6. count: `inventory_ledger` has exactly 3 rows.
7. count: `inventory` has exactly 1 row.

### INV-SY-02 — a NULL average price on the newest entry is copied
- **Rules:** `sync_snapshot_from_ledger` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `qty 20`, `avg_price Decimal("6.00")`.
2. E1 = entry of I1 in F1: `qty_after 9`, `avg_price_after Decimal("3.00")`, `performed_at T1`.
3. E2 = entry of I1 in F1: `qty_after 5`, `avg_price_after None`, `performed_at T2`.

**When**
- `result = dao.sync_snapshot_from_ledger(db, inv=S1, workspace_id=W1.id, updated_by=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. re-read S1: `qty == 5`.
3. re-read S1: `avg_price is None`.

### INV-SY-03 — a bucket with no ledger entry is set to 0 and no price
- **Rules:** `sync_snapshot_from_ledger` R3, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `qty 7`, `avg_price Decimal("5.00")`.
2. No ledger entries exist.

**When**
- `result = dao.sync_snapshot_from_ledger(db, inv=S1, workspace_id=W1.id, updated_by=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. re-read S1: `qty == 0`.
3. re-read S1: `avg_price is None`.
4. re-read S1: `updated_by == U2.id`.
5. count: `inventory_ledger` has exactly 0 rows.

### INV-SY-04 — no ledger entry and a row already at 0 / no price: nothing is written
- **Rules:** `sync_snapshot_from_ledger` R3, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `qty 0`, `avg_price None`.
2. No ledger entries exist.

**When**
- `result = dao.sync_snapshot_from_ledger(db, inv=S1, workspace_id=W1.id, updated_by=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. unchanged: unchanged(S1).
3. re-read S1: `updated_by is None`.
4. re-read S1: `updated_at is None`.

### INV-SY-05 — a different price alone triggers the write
- **Rules:** `sync_snapshot_from_ledger` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `qty 20`, `avg_price Decimal("5.00")`.
2. E1 = entry of I1 in F1: `qty_after 20`, `avg_price_after Decimal("6.00")`, `performed_at T1`.

**When**
- `result = dao.sync_snapshot_from_ledger(db, inv=S1, workspace_id=W1.id, updated_by=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. re-read S1: `qty == 20`.
3. re-read S1: `avg_price == Decimal("6.00")`.
4. re-read S1: `updated_by == U2.id`.

### INV-SY-06 — a different quantity alone triggers the write
- **Rules:** `sync_snapshot_from_ledger` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `qty 7`, `avg_price Decimal("6.00")`.
2. E1 = entry of I1 in F1: `qty_after 20`, `avg_price_after Decimal("6.00")`, `performed_at T1`.

**When**
- `result = dao.sync_snapshot_from_ledger(db, inv=S1, workspace_id=W1.id, updated_by=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. re-read S1: `qty == 20`.
3. re-read S1: `avg_price == Decimal("6.00")`.
4. re-read S1: `updated_by == U2.id`.

### INV-SY-07 — without updated_by a changed row keeps its previous stamp
- **Rules:** `sync_snapshot_from_ledger` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `qty 7`, `avg_price Decimal("5.00")`, `updated_by U1.id`.
2. E1 = entry of I1 in F1: `qty_after 20`, `avg_price_after Decimal("6.00")`, `performed_at T1`.

**When**
- `result = dao.sync_snapshot_from_ledger(db, inv=S1, workspace_id=W1.id)` — `updated_by` is not sent.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. re-read S1: `qty == 20`.
3. re-read S1: `updated_by == U1.id`.
4. re-read S1: `updated_at is not None`.

### INV-SY-08 — values already equal to the ledger: nothing is written, no stamp
- **Rules:** `sync_snapshot_from_ledger` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `qty 20`, `avg_price Decimal("6.00")`, `updated_by U1.id`.
2. E1 = entry of I1 in F1: `qty_after 20`, `avg_price_after Decimal("6")`, `performed_at T1`.

**When**
- `result = dao.sync_snapshot_from_ledger(db, inv=S1, workspace_id=W1.id, updated_by=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. unchanged: unchanged(S1).
3. re-read S1: `updated_by == U1.id`.
4. re-read S1: `updated_at is None`.
5. re-read S1: `qty == 20`.

### INV-SY-09 — no price on both sides counts as equal
- **Rules:** `sync_snapshot_from_ledger` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `qty 4`, `avg_price None`.
2. E1 = entry of I1 in F1: `qty_after 4`, `avg_price_after None`, `performed_at T1`.

**When**
- `result = dao.sync_snapshot_from_ledger(db, inv=S1, workspace_id=W1.id, updated_by=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. unchanged: unchanged(S1).
3. re-read S1: `updated_by is None`.
4. re-read S1: `updated_at is None`.

### INV-SY-10 — newer entries of other buckets are ignored
- **Rules:** `sync_snapshot_from_ledger` R7
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `qty 7`, `avg_price Decimal("5.00")`.
2. E1 = entry of I1 in F1: `qty_after 20`, `avg_price_after Decimal("6.00")`, `performed_at T1`.
3. E2 = entry of I1 in F1: `inventory_type DAMAGED`, `qty_after 91`, `avg_price_after Decimal("9.10")`, `performed_at T2`.
4. E3 = entry of I1 in F2: `qty_after 92`, `avg_price_after Decimal("9.20")`, `performed_at T3`.
5. E4 = entry of I2 in F1: `qty_after 93`, `avg_price_after Decimal("9.30")`, `performed_at T4`.
6. E5 = entry of I1 in F1: `workspace_id W2.id`, `qty_after 94`, `avg_price_after Decimal("9.40")`, `performed_at T5`.

**When**
- `result = dao.sync_snapshot_from_ledger(db, inv=S1, workspace_id=W1.id, updated_by=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. re-read S1: `qty == 20`.
3. re-read S1: `avg_price == Decimal("6.00")`.

### INV-SY-11 — entries of other buckets only: the bucket counts as having no ledger
- **Rules:** `sync_snapshot_from_ledger` R7, R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `qty 7`, `avg_price Decimal("5.00")`.
2. E1 = entry of I1 in F1: `inventory_type DAMAGED`, `qty_after 91`, `avg_price_after Decimal("9.10")`, `performed_at T1`.
3. E2 = entry of I1 in F2: `qty_after 92`, `avg_price_after Decimal("9.20")`, `performed_at T2`.

**When**
- `result = dao.sync_snapshot_from_ledger(db, inv=S1, workspace_id=W1.id, updated_by=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. re-read S1: `qty == 0`.
3. re-read S1: `avg_price is None`.

### INV-SY-12 — no other column of the row is touched
- **Rules:** `sync_snapshot_from_ledger` R8
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `qty 7`, `avg_price Decimal("5.00")`, `note "keep me"`.
2. E1 = entry of I1 in F1: `qty_after 20`, `avg_price_after Decimal("6.00")`, `performed_at T1`.

**When**
- `result = dao.sync_snapshot_from_ledger(db, inv=S1, workspace_id=W1.id, updated_by=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. re-read S1: `qty == 20`.
3. re-read S1: `note == "keep me"`.
4. re-read S1: `created_by == U1.id`.
5. re-read S1: `is_active is True`, `is_deleted is False`.
6. re-read S1: `deleted_at is None`, `deleted_by is None`.
7. re-read S1: `created_at` equals the `created_at` read from S1 before the call.

### INV-SY-13 — a soft-deleted row is aligned and stays soft-deleted
- **Rules:** `sync_snapshot_from_ledger` R9, R8
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but deleted, `qty 7`, `avg_price Decimal("5.00")`.
2. E1 = entry of I1 in F1: `qty_after 20`, `avg_price_after Decimal("6.00")`, `performed_at T1`.

**When**
- `result = dao.sync_snapshot_from_ledger(db, inv=S1, workspace_id=W1.id, updated_by=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. re-read S1: `qty == 20`.
3. re-read S1: `avg_price == Decimal("6.00")`.
4. re-read S1: `is_deleted is True`, `is_active is False`.
5. re-read S1: `deleted_at == T0`.
6. re-read S1: `deleted_by == U1.id`.

### INV-SY-14 — the ledger is searched in the workspace_id argument, not the row's workspace
- **Rules:** `sync_snapshot_from_ledger` R10
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `qty 7`, `avg_price Decimal("5.00")`. (S1 is in W1.)
2. E1 = entry of I1 in F1: `qty_after 20`, `avg_price_after Decimal("6.00")`, `performed_at T2`.
3. E2 = entry of I1 in F1: `workspace_id W2.id`, `qty_after 33`, `avg_price_after Decimal("3.00")`, `performed_at T1`.

**When**
- `result = dao.sync_snapshot_from_ledger(db, inv=S1, workspace_id=W2.id, updated_by=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. re-read S1: `qty == 33`.
3. re-read S1: `avg_price == Decimal("3.00")`.

### INV-SY-15 — called with a workspace that has no entries, the row is set to 0 and no price
- **Rules:** `sync_snapshot_from_ledger` R10, R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `qty 7`, `avg_price Decimal("5.00")`. (S1 is in W1.)
2. E1 = entry of I1 in F1: `qty_after 20`, `avg_price_after Decimal("6.00")`, `performed_at T1`.

**When**
- `result = dao.sync_snapshot_from_ledger(db, inv=S1, workspace_id=W2.id, updated_by=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. re-read S1: `qty == 0`.
3. re-read S1: `avg_price is None`.

### INV-SY-16 — the change is flushed but not committed: a rollback restores the row
- **Rules:** `sync_snapshot_from_ledger` R11
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback and a commit spy

**Given**
1. S1 = default stock of I1 in F1, but `qty 7`, `avg_price Decimal("5.00")`.
2. E1 = entry of I1 in F1: `qty_after 20`, `avg_price_after Decimal("6.00")`, `performed_at T1`.
3. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.sync_snapshot_from_ledger(db, inv=S1, workspace_id=W1.id, updated_by=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. re-read S1: `qty == 20`.
3. re-read S1 after the savepoint rollback: `qty == 7`.
4. re-read S1 after the savepoint rollback: `avg_price == Decimal("5.00")`, `updated_by is None`.
5. mock called: the `db.commit` spy was never called.

### INV-SY-17 — among entries sharing the newest performed_at the greatest id wins
- **Rules:** `sync_snapshot_from_ledger` R12 [BUG-664]
- **Kind:** bug
- **Expect:** xfail BUG-664
- **Fails today on:** Then 2 (entries are ordered by performed_at only, so E1 or E3 is used: qty 15 or 30)

**Given**
1. S1 = default stock of I1 in F1, but `qty 7`, `avg_price Decimal("5.00")`.
2. E1 = entry of I1 in F1: `qty_after 15`, `avg_price_after Decimal("1.00")`, `performed_at T1`.
3. E2 = entry of I1 in F1: `id HIGH_ID`, `qty_after 10`, `avg_price_after Decimal("4.00")`, `performed_at T1`.
4. E3 = entry of I1 in F1: `qty_after 30`, `avg_price_after Decimal("7.00")`, `performed_at T1`. (Normal sequence id, inserted last.)

**When**
- `result = dao.sync_snapshot_from_ledger(db, inv=S1, workspace_id=W1.id, updated_by=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. re-read S1: `qty == 10`.
3. re-read S1: `avg_price == Decimal("4.00")`.


## `InventoryDAO.ensure_for_factory_item_type`

### INV-EN-01 — a live row is returned, aligned to the ledger and stamped
- **Rules:** `ensure_for_factory_item_type` R1; `sync_snapshot_from_ledger` R1, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `qty 7`, `avg_price Decimal("5.00")`.
2. E1 = entry of I1 in F1: `qty_after 20`, `avg_price_after Decimal("6.00")`, `performed_at T1`.

**When**
- `result = dao.ensure_for_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id, created_by=U2.id)`.

**Then**
1. returns: `result.id == S1.id`.
2. re-read S1: `qty == 20`.
3. re-read S1: `avg_price == Decimal("6.00")`.
4. re-read S1: `updated_by == U2.id`.
5. re-read S1: `created_by == U1.id`.
6. count: `inventory` has exactly 1 row.
7. count: `inventory_ledger` has exactly 1 row.

### INV-EN-02 — a live row already equal to the ledger is returned unchanged and unstamped
- **Rules:** `ensure_for_factory_item_type` R1; `sync_snapshot_from_ledger` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `qty 20`, `avg_price Decimal("6.00")`.
2. E1 = entry of I1 in F1: `qty_after 20`, `avg_price_after Decimal("6.00")`, `performed_at T1`.

**When**
- `result = dao.ensure_for_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id, created_by=U2.id)`.

**Then**
1. returns: `result.id == S1.id`.
2. unchanged: unchanged(S1).
3. re-read S1: `updated_by is None`.
4. re-read S1: `updated_at is None`.
5. count: `inventory` has exactly 1 row.

### INV-EN-03 — a live row whose bucket has no ledger entry is set to 0 and no price
- **Rules:** `ensure_for_factory_item_type` R1; `sync_snapshot_from_ledger` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `qty 7`, `avg_price Decimal("5.00")`.
2. No ledger entries exist.

**When**
- `result = dao.ensure_for_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id, created_by=U2.id)`.

**Then**
1. returns: `result.id == S1.id`.
2. re-read S1: `qty == 0`.
3. re-read S1: `avg_price is None`.
4. re-read S1: `updated_by == U2.id`.
5. count: `inventory` has exactly 1 row.

### INV-EN-04 — a live row with is_active False is reused and stays inactive
- **Rules:** `ensure_for_factory_item_type` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `is_active False`, `qty 20`, `avg_price Decimal("6.00")`.
2. E1 = entry of I1 in F1: `qty_after 20`, `avg_price_after Decimal("6.00")`, `performed_at T1`.

**When**
- `result = dao.ensure_for_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id, created_by=U2.id)`.

**Then**
1. returns: `result.id == S1.id`.
2. re-read S1: `is_active is False`.
3. re-read S1: `is_deleted is False`.
4. count: `inventory` has exactly 1 row.

### INV-EN-05 — a soft-deleted row is restored, aligned and returned
- **Rules:** `ensure_for_factory_item_type` R3; `restore` R1, R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but deleted, `qty 7`, `avg_price Decimal("5.00")`, `note "old note"`.
2. E1 = entry of I1 in F1: `qty_after 20`, `avg_price_after Decimal("6.00")`, `performed_at T1`.

**When**
- `result = dao.ensure_for_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id, created_by=U2.id)`.

**Then**
1. returns: `result.id == S1.id`.
2. re-read S1: `is_deleted is False`, `is_active is True`.
3. re-read S1: `deleted_at is None`, `deleted_by is None`.
4. re-read S1: `qty == 20`.
5. re-read S1: `avg_price == Decimal("6.00")`.
6. re-read S1: `updated_by == U2.id`.
7. re-read S1: `note == "old note"`.
8. re-read S1: `created_by == U1.id`.
9. count: `inventory` has exactly 1 row.

### INV-EN-06 — a soft-deleted row whose values equal the ledger is restored with values kept
- **Rules:** `ensure_for_factory_item_type` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but deleted, `qty 4`, `avg_price Decimal("2.00")`, `updated_by U1.id`.
2. E1 = entry of I1 in F1: `qty_after 4`, `avg_price_after Decimal("2.00")`, `performed_at T1`.

**When**
- `result = dao.ensure_for_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id, created_by=U2.id)`.

**Then**
1. returns: `result.id == S1.id`.
2. re-read S1: `is_deleted is False`, `is_active is True`.
3. re-read S1: `deleted_at is None`, `deleted_by is None`.
4. re-read S1: `qty == 4`.
5. re-read S1: `avg_price == Decimal("2.00")`.
6. re-read S1: `updated_at is not None`.
7. count: `inventory` has exactly 1 row.

### INV-EN-07 — a restored row is stamped with the acting user even when its values do not change
- **Rules:** `ensure_for_factory_item_type` R4 [BUG-881]
- **Kind:** bug
- **Expect:** xfail BUG-881
- **Fails today on:** Then 3 (the stamp is written only when qty or price change; updated_by is still U1)

**Given**
1. S1 = default stock of I1 in F1, but deleted, `qty 4`, `avg_price Decimal("2.00")`, `updated_by U1.id`.
2. E1 = entry of I1 in F1: `qty_after 4`, `avg_price_after Decimal("2.00")`, `performed_at T1`.

**When**
- `result = dao.ensure_for_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id, created_by=U2.id)`.

**Then**
1. returns: `result.id == S1.id`.
2. re-read S1: `is_deleted is False`.
3. re-read S1: `updated_by == U2.id`.

### INV-EN-08 — no row and no ledger: an empty row is created
- **Rules:** `ensure_for_factory_item_type` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. No stock rows and no ledger entries exist.

**When**
- `result = dao.ensure_for_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id, created_by=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `factory_id == F1.id`, `item_id == I1.id`.
3. re-read the returned row: `inventory_type == STORAGE`.
4. re-read the returned row: `qty == 0`, `avg_price is None`.
5. re-read the returned row: `created_by == U2.id`, `note is None`.
6. re-read the returned row: `is_active is True`, `is_deleted is False`, `created_at is not None`.
7. re-read the returned row: `updated_by is None`, `updated_at is None`.
8. count: `inventory` has exactly 1 row.

### INV-EN-09 — no row but ledger entries: the new row is aligned and stamped
- **Rules:** `ensure_for_factory_item_type` R6, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. No stock rows exist.
2. E1 = entry of I1 in F1: `qty_after 20`, `avg_price_after Decimal("6.00")`, `performed_at T2`.
3. E2 = entry of I1 in F1: `qty_after 9`, `avg_price_after Decimal("3.00")`, `performed_at T1`.

**When**
- `result = dao.ensure_for_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id, created_by=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `qty == 20`.
3. re-read the returned row: `avg_price == Decimal("6.00")`.
4. re-read the returned row: `created_by == U2.id`, `updated_by == U2.id`.
5. re-read the returned row: `updated_at is not None`.
6. count: `inventory` has exactly 1 row.
7. count: `inventory_ledger` has exactly 2 rows.

### INV-EN-10 — no row and a newest entry of 0 / no price: the new row is not stamped
- **Rules:** `ensure_for_factory_item_type` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No stock rows exist.
2. E1 = entry of I1 in F1: `qty_after 0`, `avg_price_after None`, `performed_at T2`.
3. E2 = entry of I1 in F1: `qty_after 9`, `avg_price_after Decimal("3.00")`, `performed_at T1`.

**When**
- `result = dao.ensure_for_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id, created_by=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `qty == 0`, `avg_price is None`.
3. re-read the returned row: `updated_by is None`, `updated_at is None`.
4. count: `inventory` has exactly 1 row.

### INV-EN-11 — a row differing only in workspace is not reused: a new row is created next to it
- **Rules:** `ensure_for_factory_item_type` R7
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `workspace_id W2.id`.
2. No ledger entries exist.

**When**
- `result = dao.ensure_for_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id, created_by=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. returns: `result.id != S1.id`.
3. re-read the returned row: `workspace_id == W1.id`, `factory_id == F1.id`, `item_id == I1.id`.
4. re-read the returned row: `inventory_type == STORAGE`.
5. unchanged: unchanged(S1).
6. count: `inventory` has exactly 2 rows.

### INV-EN-12 — a row differing only in factory is not reused: a new row is created next to it
- **Rules:** `ensure_for_factory_item_type` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F2.
2. No ledger entries exist.

**When**
- `result = dao.ensure_for_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id, created_by=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. returns: `result.id != S1.id`.
3. re-read the returned row: `workspace_id == W1.id`, `factory_id == F1.id`, `item_id == I1.id`.
4. re-read the returned row: `inventory_type == STORAGE`.
5. unchanged: unchanged(S1).
6. count: `inventory` has exactly 2 rows.

### INV-EN-13 — a row differing only in item is not reused: a new row is created next to it
- **Rules:** `ensure_for_factory_item_type` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I2 in F1.
2. No ledger entries exist.

**When**
- `result = dao.ensure_for_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id, created_by=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. returns: `result.id != S1.id`.
3. re-read the returned row: `workspace_id == W1.id`, `factory_id == F1.id`, `item_id == I1.id`.
4. re-read the returned row: `inventory_type == STORAGE`.
5. unchanged: unchanged(S1).
6. count: `inventory` has exactly 2 rows.

### INV-EN-14 — a row differing only in inventory type is not reused: a new row is created next to it
- **Rules:** `ensure_for_factory_item_type` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `inventory_type DAMAGED`.
2. No ledger entries exist.

**When**
- `result = dao.ensure_for_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id, created_by=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. returns: `result.id != S1.id`.
3. re-read the returned row: `workspace_id == W1.id`, `factory_id == F1.id`, `item_id == I1.id`.
4. re-read the returned row: `inventory_type == STORAGE`.
5. unchanged: unchanged(S1).
6. count: `inventory` has exactly 2 rows.

### INV-EN-15 — a second call with the same arguments returns the same row
- **Rules:** `ensure_for_factory_item_type` R7, R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No stock rows and no ledger entries exist.
2. Setup call (not the call under test): `first = dao.ensure_for_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id, created_by=U2.id)`.

**When**
- `result = dao.ensure_for_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id, created_by=U2.id)`.

**Then**
1. returns: `result.id == first.id`.
2. count: `inventory` has exactly 1 row.

### INV-EN-16 — an item of another workspace is accepted
- **Rules:** `ensure_for_factory_item_type` R8
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No stock rows and no ledger entries exist.

**When**
- `result = dao.ensure_for_factory_item_type(db, factory_id=F1.id, item_id=I9.id, inventory_type=STORAGE, workspace_id=W1.id, created_by=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `item_id == I9.id`.
3. count: `inventory` has exactly 1 row.

### INV-EN-17 — a factory of another workspace is accepted
- **Rules:** `ensure_for_factory_item_type` R8
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No stock rows and no ledger entries exist.

**When**
- `result = dao.ensure_for_factory_item_type(db, factory_id=F9.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id, created_by=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `factory_id == F9.id`.
3. count: `inventory` has exactly 1 row.

### INV-EN-18 — an unknown item_id fails on the foreign key; nothing is created, the session stays usable
- **Rules:** `ensure_for_factory_item_type` R8, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. S1 = default stock of I2 in F1. (Written earlier in the same transaction.)

**When**
- `dao.ensure_for_factory_item_type(db, factory_id=F1.id, item_id=MISSING, inventory_type=STORAGE, workspace_id=W1.id, created_by=U2.id)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `exc.value.orig.pgcode == "23503"`.
4. raises: `"inventory_item_id_fkey" in str(exc.value.orig)`.
5. count: `inventory` has exactly 1 row.
6. unchanged: unchanged(S1).

### INV-EN-19 — an unknown factory_id fails on the foreign key; nothing is created, the session stays usable
- **Rules:** `ensure_for_factory_item_type` R8, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. S1 = default stock of I2 in F1. (Written earlier in the same transaction.)

**When**
- `dao.ensure_for_factory_item_type(db, factory_id=MISSING, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id, created_by=U2.id)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `exc.value.orig.pgcode == "23503"`.
4. raises: `"inventory_factory_id_fkey" in str(exc.value.orig)`.
5. count: `inventory` has exactly 1 row.
6. unchanged: unchanged(S1).

### INV-EN-20 — an unknown created_by fails on the foreign key; nothing is created, the session stays usable
- **Rules:** `ensure_for_factory_item_type` R8, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. S1 = default stock of I2 in F1. (Written earlier in the same transaction.)

**When**
- `dao.ensure_for_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id, created_by=MISSING)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `exc.value.orig.pgcode == "23503"`.
4. raises: `"inventory_created_by_fkey" in str(exc.value.orig)`.
5. count: `inventory` has exactly 1 row.
6. unchanged: unchanged(S1).

### INV-EN-21 — an unknown workspace_id fails on the foreign key; nothing is created, the session stays usable
- **Rules:** `ensure_for_factory_item_type` R8, Errors row 4
- **Kind:** error
- **Expect:** pass

**Given**
1. S1 = default stock of I2 in F1. (Written earlier in the same transaction.)

**When**
- `dao.ensure_for_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=MISSING, created_by=U2.id)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `exc.value.orig.pgcode == "23503"`.
4. raises: `"inventory_workspace_id_fkey" in str(exc.value.orig)`.
5. count: `inventory` has exactly 1 row.
6. unchanged: unchanged(S1).

### INV-EN-22 — insert loses a race to a live row: that row is returned, aligned, no error
- **Rules:** `ensure_for_factory_item_type` R9
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — race simulation (patches the DAO's own lookups)

**Given**
1. S1 = default stock of I1 in F1, but `qty 7`, `avg_price Decimal("5.00")`.
2. E1 = entry of I1 in F1: `qty_after 20`, `avg_price_after Decimal("6.00")`, `performed_at T1`.
3. Patches per **race R9** (Conventions).

**When**
- `result = dao.ensure_for_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id, created_by=U2.id)`.

**Then**
1. returns: `result.id == S1.id`.
2. re-read S1: `qty == 20`.
3. re-read S1: `avg_price == Decimal("6.00")`.
4. re-read S1: `updated_by == U2.id`.
5. re-read S1: `is_deleted is False`.
6. count: `inventory` has exactly 1 row.

### INV-EN-23 — insert loses a race to a soft-deleted row: it is restored, aligned and returned
- **Rules:** `ensure_for_factory_item_type` R9
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — race simulation (patches the DAO's own lookups)

**Given**
1. S1 = default stock of I1 in F1, but deleted, `qty 7`, `avg_price Decimal("5.00")`.
2. E1 = entry of I1 in F1: `qty_after 20`, `avg_price_after Decimal("6.00")`, `performed_at T1`.
3. Patches per **race R9** (Conventions).

**When**
- `result = dao.ensure_for_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id, created_by=U2.id)`.

**Then**
1. returns: `result.id == S1.id`.
2. re-read S1: `is_deleted is False`, `is_active is True`.
3. re-read S1: `deleted_at is None`, `deleted_by is None`.
4. re-read S1: `qty == 20`.
5. count: `inventory` has exactly 1 row.

### INV-EN-24 — unique violation and the row still cannot be found: the IntegrityError is re-raised
- **Rules:** `ensure_for_factory_item_type` R10, Errors row 5
- **Kind:** error
- **Expect:** pass
- **Author:** claude — race simulation (patches the DAO's own lookups)

**Given**
1. S1 = default stock of I1 in F1, but `qty 7`, `avg_price Decimal("5.00")`.
2. E1 = entry of I1 in F1: `qty_after 20`, `avg_price_after Decimal("6.00")`, `performed_at T1`.
3. Patches per **race R10** (Conventions).

**When**
- `dao.ensure_for_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id, created_by=U2.id)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `isinstance(exc.value.orig, UniqueViolation)`.
3. raises: `exc.value.orig.pgcode == "23505"`.
4. raises: `"uq_inventory_workspace_item_type_factory" in str(exc.value.orig)`.
5. count: `inventory` has exactly 1 row.
6. unchanged: unchanged(S1).

### INV-EN-25 — a created row is flushed but not committed: a rollback removes it
- **Rules:** `ensure_for_factory_item_type` R11
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback and a commit spy

**Given**
1. No stock rows and no ledger entries exist.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.ensure_for_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id, created_by=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `inventory` has exactly 1 row.
3. count: after the savepoint rollback `inventory` has exactly 0 rows.
4. mock called: the `db.commit` spy was never called.

### INV-EN-26 — a restore and alignment are not committed: a rollback undoes them
- **Rules:** `ensure_for_factory_item_type` R11
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback and a commit spy

**Given**
1. S1 = default stock of I1 in F1, but deleted, `qty 7`, `avg_price Decimal("5.00")`.
2. E1 = entry of I1 in F1: `qty_after 20`, `avg_price_after Decimal("6.00")`, `performed_at T1`.
3. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.ensure_for_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id, created_by=U2.id)`.

**Then**
1. returns: `result.id == S1.id`.
2. re-read S1: `is_deleted is False`, `qty == 20`.
3. re-read S1 after the savepoint rollback: `is_deleted is True`, `is_active is False`.
4. re-read S1 after the savepoint rollback: `qty == 7`, `deleted_at == T0`, `deleted_by == U1.id`.
5. mock called: the `db.commit` spy was never called.

### INV-EN-27 — alignment uses only the ledger of the workspace_id argument
- **Rules:** `ensure_for_factory_item_type` R1; `sync_snapshot_from_ledger` R7
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `qty 7`, `avg_price Decimal("5.00")`.
2. E1 = entry of I1 in F1: `qty_after 20`, `avg_price_after Decimal("6.00")`, `performed_at T1`.
3. E2 = entry of I1 in F1: `workspace_id W2.id`, `qty_after 33`, `avg_price_after Decimal("3.00")`, `performed_at T2`.

**When**
- `result = dao.ensure_for_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id, created_by=U2.id)`.

**Then**
1. returns: `result.id == S1.id`.
2. re-read S1: `qty == 20`.
3. re-read S1: `avg_price == Decimal("6.00")`.

### INV-EN-28 — the live row of a bucket in a soft-deleted factory is reused
- **Rules:** `ensure_for_factory_item_type` R1; `get_by_factory_item_type` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FA = `factories` row: `name "Old Plant"`, `abbreviation "OP"`, `workspace_id W1.id`, `is_active True`, `is_deleted True` (a soft-deleted factory).
2. S1 = default stock of I1 in FA, but `qty 7`, `avg_price Decimal("5.00")`.
3. E1 = entry of I1 in FA: `qty_after 20`, `avg_price_after Decimal("6.00")`, `performed_at T1`.

**When**
- `result = dao.ensure_for_factory_item_type(db, factory_id=FA.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id, created_by=U2.id)`.

**Then**
1. returns: `result.id == S1.id`.
2. re-read S1: `qty == 20`.
3. re-read S1: `updated_by == U2.id`.
4. count: `inventory` has exactly 1 row.


## `InventoryDAO.get_by_item`

### INV-GI-01 — returns the item's live rows across factories and all four types, not other items
- **Rules:** `get_by_item` R1, R4, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I1 in F2.
3. S3 = default stock of I1 in F1, but `inventory_type DAMAGED`.
4. S4 = default stock of I1 in F1, but `inventory_type WASTE`.
5. S5 = default stock of I1 in F1, but `inventory_type SCRAP`.
6. S6 = default stock of I2 in F1.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [S1.id, S2.id, S3.id, S4.id, S5.id]`.

### INV-GI-02 — rows with zero and negative quantity are included
- **Rules:** `get_by_item` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `qty 0`.
2. S2 = default stock of I1 in F2, but `qty -3`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [S1.id, S2.id]`.

### INV-GI-03 — soft-deleted rows are excluded, inactive live rows are included
- **Rules:** `get_by_item` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but deleted.
2. S2 = default stock of I1 in F2, but `is_active False`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [S2.id]`.

### INV-GI-04 — rows of the same item id in another workspace are not mixed in
- **Rules:** `get_by_item` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.
2. S2 = default stock of I1 in F2, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [S2.id]`.

### INV-GI-05 — there is no row cap: 104 matching rows are all returned
- **Rules:** `get_by_item` R5
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — bulk setup (nested loops over factories and types) outside the Conventions vocabulary

**Given**
1. 26 `factories` rows in W1 with `name "Plant 01"` … `"Plant 26"` and `abbreviation "P01"` … `"P26"`.
2. For each of those 26 factories, four default stock rows of I1: one per inventory type (STORAGE, DAMAGED, WASTE, SCRAP) — 104 rows.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 104`.
2. returns: `len({row.id for row in result}) == 104`.

### INV-GI-06 — an unknown item id returns an empty list
- **Rules:** `get_by_item` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.

**When**
- `result = dao.get_by_item(db, item_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### INV-GI-07 — an unknown workspace id returns an empty list
- **Rules:** `get_by_item` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### INV-GI-08 — an item with only soft-deleted rows returns an empty list
- **Rules:** `get_by_item` R6, R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but deleted.
2. S2 = default stock of I2 in F1.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### INV-GI-09 — a row in a soft-deleted factory is not returned
- **Rules:** `get_by_item` R1a [BUG-884]
- **Kind:** bug
- **Expect:** xfail BUG-884
- **Fails today on:** Then 1 (the factory row is never looked at, so S2 is returned too)

**Given**
1. FA = `factories` row: `name "Old Plant"`, `abbreviation "OP"`, `workspace_id W1.id`, `is_active True`, `is_deleted True` (a soft-deleted factory).
2. S1 = default stock of I1 in F1.
3. S2 = default stock of I1 in FA, but `qty 30`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [S1.id]`.

### INV-GI-10 — an item whose only stock sits in a soft-deleted factory returns an empty list
- **Rules:** `get_by_item` R1a [BUG-884]
- **Kind:** bug
- **Expect:** xfail BUG-884
- **Fails today on:** Then 1 (the factory row is never looked at, so S1 is returned)

**Given**
1. FA = `factories` row: `name "Old Plant"`, `abbreviation "OP"`, `workspace_id W1.id`, `is_active True`, `is_deleted True` (a soft-deleted factory).
2. S1 = default stock of I1 in FA, but `qty 30`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### INV-GI-11 — a row in an inactive but live factory is returned
- **Rules:** `get_by_item` R1b, R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FB = `factories` row: `name "Idle Plant"`, `abbreviation "IP"`, `workspace_id W1.id`, `is_active False`, `is_deleted False` (inactive but live).
2. S1 = default stock of I1 in FB.
3. S2 = default stock of I1 in F1.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [S1.id, S2.id]`.

### INV-GI-12 — the call leaves the stock row of a soft-deleted factory untouched
- **Rules:** `get_by_item` R1b
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. FA = `factories` row: `name "Old Plant"`, `abbreviation "OP"`, `workspace_id W1.id`, `is_active True`, `is_deleted True` (a soft-deleted factory).
2. S1 = default stock of I1 in F1.
3. S2 = default stock of I1 in FA, but `qty 30`.

**When**
- `result = dao.get_by_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `S1.id in ids(result)` (looser check intended: only this membership is asserted).
2. unchanged: unchanged(S2).
3. re-read S2: `is_deleted is False`, `qty == 30`, `factory_id == FA.id`.
4. re-read S2: `avg_price == Decimal("2.00")`.

### INV-GI-13 — the live rows of a removed item are returned when asked for by its id
- **Rules:** `get_by_item` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. IA = default item, `name "Old Gasket"`, `is_active False` (a removed catalog item).
2. S1 = default stock of IA in F1.
3. S2 = default stock of I1 in F1.

**When**
- `result = dao.get_by_item(db, item_id=IA.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [S1.id]`.


## `InventoryDAO.restore`

### INV-R-01 — a soft-deleted row is brought back and nothing else changes
- **Rules:** `restore` R1, R2, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but deleted, `qty 7`, `avg_price Decimal("5.00")`, `note "n1"`, `updated_by U1.id`.

**When**
- `result = dao.restore(db, db_obj=S1)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. re-read S1: `is_active is True`, `is_deleted is False`.
3. re-read S1: `deleted_at is None`, `deleted_by is None`.
4. re-read S1: `qty == 7`.
5. re-read S1: `avg_price == Decimal("5.00")`.
6. re-read S1: `note == "n1"`.
7. re-read S1: `created_by == U1.id`, `updated_by == U1.id`.
8. re-read S1: `updated_at is not None`.
9. re-read S1: `created_at` equals the `created_at` read from S1 before the call.

### INV-R-02 — a restored row is found again by the live bucket lookup
- **Rules:** `restore` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but deleted.

**When**
- `result = dao.restore(db, db_obj=S1)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. returns: after the call, `dao.get_by_factory_item_type(db, factory_id=F1.id, item_id=I1.id, inventory_type=STORAGE, workspace_id=W1.id).id == S1.id`.

### INV-R-03 — a row that is already live and active is left untouched
- **Rules:** `restore` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1.

**When**
- `result = dao.restore(db, db_obj=S1)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. unchanged: unchanged(S1).
3. re-read S1: `updated_at is None`.

### INV-R-04 — a live row with is_active False becomes active
- **Rules:** `restore` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = default stock of I1 in F1, but `is_active False`.

**When**
- `result = dao.restore(db, db_obj=S1)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. re-read S1: `is_active is True`.
3. re-read S1: `is_deleted is False`.

### INV-R-05 — the restore is flushed but not committed: a rollback makes the row deleted again
- **Rules:** `restore` R4
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback and a commit spy

**Given**
1. S1 = default stock of I1 in F1, but deleted.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.restore(db, db_obj=S1)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. re-read S1: `is_deleted is False`.
3. re-read S1 after the savepoint rollback: `is_deleted is True`, `is_active is False`.
4. re-read S1 after the savepoint rollback: `deleted_at == T0`, `deleted_by == U1.id`.
5. mock called: the `db.commit` spy was never called.


## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `list_filtered` Visibility note (`skip >= 0`, `1 <= limit <= 1000`, default `limit=50`; HR-7) | `GET /inventory/` (endpoint) | 422 for `limit=0`, `limit=1001`, `skip=-1`; the DAO itself accepts `limit=0` (INV-L-12) and lets Postgres reject negatives (INV-L-17, L-18). |
| `sync_snapshot_from_ledger` R12 [BUG-664] — fix location | `InventoryLedgerDAO.get_latest_entry` (`app/dao/inventory_ledger.py` spec) | Newest entry = greatest `performed_at`, ties by greatest `id`, tested directly on the ledger DAO. INV-SY-17 covers it only through the sync. |
| `ensure_for_factory_item_type` R8 — item / factory not checked against the workspace | `inventory_movements`, `ProductionBatchManager` (BUG-666 / BUG-710) | A foreign-workspace item or factory is refused before this DAO is called. Here it is accepted by design (INV-EN-16, EN-17). |
| `ensure_for_factory_item_type` R9 / R10 — the real race | integration tests (two committed sessions) | Two concurrent calls for a bucket with no row: both return the same row id, exactly one row exists. INV-EN-22…24 only simulate the post-race state by patching the lookups. |
| `ensure_for_factory_item_type` branch map 260–261, `False` side (row became live between the two lookups) | integration tests (two committed sessions) | No rule; unreachable in one session. Listed so the uncovered branch is not mistaken for a missing case. |
| `get_by_id_and_workspace` R5 / `get_by_factory_item_type` R5 — raw lookups still return stock of a soft-deleted factory or removed item | inventory manager spec (`get_inventory`, `update_inventory`, `delete_inventory`), production-batch and reconciliation callers | Whether show / adjust / clear and the availability checks refuse such a row. Here it is returned by design (INV-GIW-07, GIW-08, GF-10, GF-11, EN-28). |
| `_filtered_query` R11 [BUG-883] vs. inventory manager `create_inventory` R3a (cross-spec conflict noted in the spec header) | inventory manager spec (`create_inventory`) | Whether stock may still be created for a removed item; the manager cases must follow that spec's own pass. |
| `get_by_item` R3 — a removed item's rows are still returned | `ItemSummaryService` spec | Whether the summary page of a removed item is shown at all (INV-GI-13 covers only the DAO lookup). |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `list_filtered` R2 / Notes "Ordering (BUG-701)"; Model facts (`Item`) | Whether `items` has a uniqueness constraint on `(workspace_id, name_normalized)` (or on `name`). The BUG-701 recipe needs two items in W1 named "Bolt" and "bolt". | Not blocking: INV-L-04 and L-05 give the second item an explicit, different `name_normalized` ("bolt lower"), which this DAO never reads. If a constraint on `name` itself exists, both cards need a new recipe. |
| 2 | `_filtered_query` R9; Model facts (`Item`, `Factory`) | The column names of the item's description and SKU (R9 only says "description / SKU"). Also whether `factories.abbreviation` or `factories.name` must be unique. | Not blocking: INV-FQ-23 uses `description` and `sku` (the names used by the approved item DAO cases) and every factory in this file has its own name and abbreviation. |
| 3 | `stats_filtered` Returns; Model facts (`InventoryTypeEnum`) | The enum members' string values (e.g. `"STORAGE"` vs `"storage"`). | Not blocking: every card compares enum members (`== STORAGE`), never `.value`. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_filtered_query` | R1 | INV-FQ-01, INV-FQ-02, INV-FQ-03, INV-FQ-12, INV-CNT-02, INV-ST-12, INV-ST-13 |
| `_filtered_query` | R2 | INV-FQ-04, INV-FQ-05, INV-CNT-02, INV-ST-12, INV-ST-13 |
| `_filtered_query` | R3 | INV-FQ-01, INV-FQ-07 |
| `_filtered_query` | R4 | INV-FQ-06, INV-FQ-07, INV-FQ-08, INV-CNT-04, INV-ST-15 |
| `_filtered_query` | R5 [BUG-880] | INV-FQ-07, INV-FQ-09, INV-FQ-10, INV-FQ-11, INV-FQ-12, INV-CNT-04, INV-CNT-07, INV-ST-12, INV-ST-16 |
| `_filtered_query` | R6 | INV-FQ-07, INV-FQ-13, INV-FQ-14, INV-CNT-05, INV-ST-15 |
| `_filtered_query` | R7 | INV-FQ-15, INV-FQ-16, INV-CNT-02, INV-CNT-03, INV-ST-05 |
| `_filtered_query` | R8 | INV-FQ-07, INV-FQ-17, INV-FQ-18 |
| `_filtered_query` | R9 [BUG-702] | INV-FQ-19, INV-FQ-20, INV-FQ-21, INV-FQ-22, INV-FQ-23, INV-FQ-24, INV-FQ-25, INV-FQ-26, INV-FQ-27, INV-FQ-28, INV-CNT-06, INV-ST-14 |
| `_filtered_query` | R10 | INV-FQ-21, INV-FQ-29, INV-FQ-30, INV-CNT-04 |
| `_filtered_query` | R11 [BUG-883] | INV-FQ-31, INV-FQ-32, INV-FQ-33, INV-FQ-34, INV-CNT-12, INV-CNT-13, INV-CNT-14, INV-ST-21, INV-ST-22, INV-ST-23, INV-ST-24 |
| `_filtered_query` | R11a [BUG-882] | INV-FQ-36, INV-FQ-37, INV-FQ-38, INV-CNT-10, INV-CNT-11, INV-ST-18, INV-ST-19, INV-ST-20 |
| `_filtered_query` | R11b | INV-FQ-39, INV-FQ-40, INV-CNT-15, INV-ST-25 |
| `_filtered_query` | R11c | INV-FQ-05, INV-FQ-35 |
| `_filtered_query` | R12 | INV-FQ-01, INV-FQ-09 |
| `list_filtered` | R1 | INV-L-01, INV-L-20, INV-L-22 |
| `list_filtered` | R1a [BUG-882] | INV-FQ-36, INV-FQ-37, INV-L-19 |
| `list_filtered` | R1b [BUG-883] | INV-FQ-31, INV-FQ-32, INV-FQ-33, INV-L-21 |
| `list_filtered` | R2 [BUG-701] | INV-L-02, INV-L-03, INV-L-04, INV-L-05 |
| `list_filtered` | R3 | INV-L-06, INV-L-07, INV-L-08, INV-L-09, INV-L-10, INV-L-11, INV-L-14, INV-L-20, INV-L-22 |
| `list_filtered` | R4 | INV-L-12, INV-L-13, INV-L-14, INV-L-15, INV-L-16 |
| `list_filtered` | R5 | INV-L-17, INV-L-18 |
| `list_filtered` | Errors row 1 | INV-L-17 |
| `list_filtered` | Errors row 2 | INV-L-18 |
| `count_filtered` | R1 | INV-CNT-01, INV-CNT-02, INV-CNT-03, INV-CNT-04, INV-CNT-05, INV-CNT-06, INV-CNT-07, INV-CNT-15 |
| `count_filtered` | R1a [BUG-882] | INV-CNT-10, INV-CNT-11 |
| `count_filtered` | R1b [BUG-883] | INV-CNT-12, INV-CNT-13, INV-CNT-14 |
| `count_filtered` | R2 | INV-CNT-08, INV-CNT-09 |
| `stats_filtered` | R1 | INV-ST-01, INV-ST-04, INV-ST-05, INV-ST-12, INV-ST-13, INV-ST-14, INV-ST-15, INV-ST-16, INV-ST-25 |
| `stats_filtered` | R1a [BUG-882] | INV-ST-18, INV-ST-19 |
| `stats_filtered` | R1b [BUG-883] | INV-ST-21, INV-ST-22, INV-ST-23 |
| `stats_filtered` | R2 | INV-ST-01, INV-ST-02, INV-ST-13 |
| `stats_filtered` | R3 | INV-ST-01, INV-ST-02, INV-ST-04, INV-ST-05 |
| `stats_filtered` | R4 | INV-ST-01, INV-ST-04, INV-ST-05, INV-ST-11 |
| `stats_filtered` | R5 | INV-ST-01, INV-ST-02, INV-ST-06, INV-ST-07, INV-ST-13, INV-ST-17 |
| `stats_filtered` | R5a [BUG-882] | INV-ST-20 |
| `stats_filtered` | R5b [BUG-883] | INV-ST-24 |
| `stats_filtered` | R6 [BUG-719] | INV-ST-03 |
| `stats_filtered` | R7 | INV-ST-08, INV-ST-09, INV-ST-10 |
| `stats_filtered` | R8 | INV-ST-11 |
| `get_by_id_and_workspace` | R1 | INV-GIW-01 |
| `get_by_id_and_workspace` | R2 | INV-GIW-02 |
| `get_by_id_and_workspace` | R3 | INV-GIW-03 |
| `get_by_id_and_workspace` | R4 | INV-GIW-04, INV-GIW-05, INV-GIW-06 |
| `get_by_id_and_workspace` | R5 | INV-GIW-07, INV-GIW-08 |
| `get_by_factory_item_type` | R1 | INV-GF-01 |
| `get_by_factory_item_type` | R2 | INV-GF-02, INV-GF-03, INV-GF-04, INV-GF-05 |
| `get_by_factory_item_type` | R3 | INV-GF-06 |
| `get_by_factory_item_type` | R4 | INV-GF-07, INV-GF-08, INV-GF-09 |
| `get_by_factory_item_type` | R5 | INV-GF-10, INV-GF-11, INV-EN-28 |
| `_get_any_by_factory_item_type` | R1 | INV-GA-01, INV-GA-06 |
| `_get_any_by_factory_item_type` | R2 | INV-GA-02, INV-GA-03, INV-GA-04, INV-GA-05, INV-GA-07 |
| `sync_snapshot_from_ledger` | R1 | INV-SY-01, INV-EN-01 |
| `sync_snapshot_from_ledger` | R2 | INV-SY-02 |
| `sync_snapshot_from_ledger` | R3 | INV-SY-03, INV-SY-04, INV-SY-11, INV-SY-15, INV-EN-03 |
| `sync_snapshot_from_ledger` | R4 | INV-SY-05, INV-SY-06 |
| `sync_snapshot_from_ledger` | R5 | INV-SY-01, INV-SY-03, INV-SY-07, INV-EN-01 |
| `sync_snapshot_from_ledger` | R6 | INV-SY-04, INV-SY-08, INV-SY-09, INV-EN-02 |
| `sync_snapshot_from_ledger` | R7 | INV-SY-10, INV-SY-11, INV-EN-27 |
| `sync_snapshot_from_ledger` | R8 | INV-SY-12, INV-SY-13 |
| `sync_snapshot_from_ledger` | R9 | INV-SY-13 |
| `sync_snapshot_from_ledger` | R10 | INV-SY-14, INV-SY-15 |
| `sync_snapshot_from_ledger` | R11 | INV-SY-01, INV-SY-16 |
| `sync_snapshot_from_ledger` | R12 [BUG-664] | INV-SY-17 |
| `ensure_for_factory_item_type` | R1 | INV-EN-01, INV-EN-02, INV-EN-03, INV-EN-15, INV-EN-27, INV-EN-28 |
| `ensure_for_factory_item_type` | R2 | INV-EN-04 |
| `ensure_for_factory_item_type` | R3 | INV-EN-05, INV-EN-06 |
| `ensure_for_factory_item_type` | R4 [BUG-881] | INV-EN-07 |
| `ensure_for_factory_item_type` | R5 | INV-EN-08, INV-EN-09 |
| `ensure_for_factory_item_type` | R6 | INV-EN-09, INV-EN-10 |
| `ensure_for_factory_item_type` | R7 | INV-EN-11, INV-EN-12, INV-EN-13, INV-EN-14, INV-EN-15 |
| `ensure_for_factory_item_type` | R8 | INV-EN-16, INV-EN-17, INV-EN-18, INV-EN-19, INV-EN-20, INV-EN-21 |
| `ensure_for_factory_item_type` | R9 | INV-EN-22, INV-EN-23 |
| `ensure_for_factory_item_type` | R10 | INV-EN-24 |
| `ensure_for_factory_item_type` | R11 | INV-EN-25, INV-EN-26 |
| `ensure_for_factory_item_type` | Errors row 1 | INV-EN-18 |
| `ensure_for_factory_item_type` | Errors row 2 | INV-EN-19 |
| `ensure_for_factory_item_type` | Errors row 3 | INV-EN-20 |
| `ensure_for_factory_item_type` | Errors row 4 | INV-EN-21 |
| `ensure_for_factory_item_type` | Errors row 5 | INV-EN-24 |
| `get_by_item` | R1 | INV-GI-01, INV-GI-11 |
| `get_by_item` | R1a [BUG-884] | INV-GI-09, INV-GI-10 |
| `get_by_item` | R1b | INV-GI-11, INV-GI-12 |
| `get_by_item` | R2 | INV-GI-02 |
| `get_by_item` | R3 | INV-GI-03, INV-GI-08, INV-GI-13 |
| `get_by_item` | R4 | INV-GI-01, INV-GI-04 |
| `get_by_item` | R5 | INV-GI-01, INV-GI-05 |
| `get_by_item` | R6 | INV-GI-06, INV-GI-07, INV-GI-08 |
| `restore` | R1 | INV-EN-05, INV-R-01, INV-R-02 |
| `restore` | R2 | INV-EN-05, INV-R-01 |
| `restore` | R3 | INV-R-03, INV-R-04 |
| `restore` | R4 | INV-R-01, INV-R-05 |
