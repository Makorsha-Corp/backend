# Helpers for `test_inventory.py`

## Fixtures (add them as test arguments)
- `db` — the session.
- `w1`, `w2` — W1, W2. `u1`, `u2` — U1, U2. `f1`, `f2`, `f9` — F1, F2, F9. `i1`, `i2`, `i9` — I1, I2, I9. Request every one the test uses.
- `mk_item`, `mk_factory`, `mk_stock`, `mk_entry` — row builders.
- Every fixture a test uses — builders and actors too — must be in its argument list.
- The ONLY possible arguments are: `db, w1, w2, u1, u2, f1, f2, f9, i1, i2, i9, mk_item, mk_factory, mk_stock, mk_entry`. Rows the test builds itself (`s1`, `ia`, `ib`, `fa`, `e1`) are local variables, never arguments. `dao`, the constants and the reading helpers are used directly.

## Builders
- `mk_stock(item, factory, deleted=False, **columns)` — "default stock of <item> in <factory>".
- `mk_item(name, **columns)` — "default item".
- `mk_factory(name, abbreviation, **columns)` — a card's own "`factories` row".
- `mk_entry(item, factory, qty_after=..., avg_price_after=..., performed_at=..., **columns)` — "entry of <item> in <factory>".
- A default with values replaced = keyword arguments, each keyword once: `mk_stock(i1, f1, qty=7, avg_price=None)`.

## Card says -> write
| Card says | Write |
|---|---|
| `W1.id`, `U2.id`, `F2.id`, `I9.id`, `S1.id`, `IA.id`, `FA.id` | `w1.id`, `u2.id`, `f2.id`, `i9.id`, `s1.id`, `ia.id`, `fa.id` |
| STORAGE, DAMAGED, WASTE, SCRAP, MISSING, T0 … T5 | constants with these names |
| S1 = default stock of I1 in F1 | `s1 = mk_stock(i1, f1)` |
| S9 | `s9 = mk_stock(i9, f9, workspace_id=w2.id)` |
| default stock of I2 in F2, but `qty 0` | `mk_stock(i2, f2, qty=0)` |
| default stock of I1 in F1, but deleted | `mk_stock(i1, f1, deleted=True)` |
| default stock of I1 in F1, but `inventory_type DAMAGED` | `mk_stock(i1, f1, inventory_type=DAMAGED)` |
| IA = default item, `name "Wire"` | `ia = mk_item("Wire")` |
| IB = default item, `name "Wire"`, `unit "kg"` | `ib = mk_item("Wire", unit="kg")` |
| items IA, IB, IC, ID, IE | variables `ia`, `ib`, `ic`, `id_`, `ie` |
| FA = `factories` row: `name "Old Plant"`, `abbreviation "OP"`, …, `is_active True`, `is_deleted True` | `fa = mk_factory("Old Plant", "OP", is_active=True, is_deleted=True)` |
| E1 = entry of I1 in F1: `qty_after 20`, `avg_price_after Decimal("6.00")`, `performed_at T1` | `e1 = mk_entry(i1, f1, qty_after=20, avg_price_after=Decimal("6.00"), performed_at=T1)` |
| entry …, but the card also lists `inventory_type DAMAGED` (or `workspace_id W2.id`) | add `inventory_type=DAMAGED` (or `workspace_id=w2.id`) to that `mk_entry` call |
| entry …, but the card also lists `id HIGH_ID` | add `id=high_id(db)` to that `mk_entry` call |
| 101 default items "Item 001" … "Item 101", one stock each | `for n in range(1, 102):` + `item = mk_item(f"Item {n:03d}")` + `mk_stock(item, f1)` |
| "No stock rows exist", "No ledger entries exist" | no code |
| "Setup call (not the call under test): `first = dao…`" | that line as written, before the When call |

Each row shows ONE change. Several "but" values -> one keyword each. Build Given rows in the order written; give a row a variable only if the test uses it later. Take "before" values after the last Given row, just before the call.

## Reading helpers (plain functions, call them directly)
- `reread(db, row)` — fresh copy of any row from the database.
- `snap(db, row)` — dict of all columns of any row.
- `count_rows(db, Model)` — rows of `Inventory` or `InventoryLedger` in all workspaces.
- `written(db)` — the "nothing written" counts.
- `ids(result)`, `names(result)`, `by_type(result)` — as in Conventions. `high_id(db)` — HIGH_ID.

## Already imported (never import)
`pytest`, `Decimal`, `dao`, `Inventory`, `InventoryLedger`, `InventoryTypeEnum`, `Row`, `DataError`, `IntegrityError`, `InvalidRowCountInLimitClause`, `InvalidRowCountInResultOffsetClause`, `ForeignKeyViolation`, `UniqueViolation`.

## How to write each kind of Then line
- Before the assertions of Then line N write `# Then N` on its own line (each once, in order); for `raises:` before `with pytest.raises`.
- Expected values are the card's literals (`20`, `Decimal("6.00")`, `"Bolt"`), never read from a row or a "before" variable.
- When -> the call exactly as shown, lower-case names: `result = dao.list_filtered(db, workspace_id=w1.id, factory_id=f2.id)`. Never wrap it in `pytest.raises` unless a Then line starts with `raises:`.
- `returns:` -> `assert` + the expression as written: `assert ids(result) == [s1.id, s2.id]`, `assert result == []`, `assert result is None`, `assert result is s1`, `assert type(result) is int`, `assert isinstance(result[2], Decimal)`, `assert s1.id in ids(result)` (a "looser check": just that).
- `returns:` with "after the call, `dao.get_…(…).id == S1.id`" -> `assert dao.get_…(db, …).id == s1.id`. "Unpacking works" -> `t, n, q = result[3][0]`, then `assert (t, n, q) == (STORAGE, 1, 5)`.
- `re-read S1:` -> `row = reread(db, s1)`, then one `assert` per value; a line with two or three values -> an assert for each (`assert row.is_deleted is False`, `assert row.qty == 30`). Later `re-read S1:` lines may reuse `row`. A second row (IA) -> `row_ia = reread(db, ia)`.
- `re-read the returned row:` -> `row = reread(db, result)`, then the asserts.
- "`created_at` equals the `created_at` read from S1 before the call" -> `created_before = snap(db, s1)["created_at"]` before the call, `assert row.created_at == created_before` after.
- `unchanged(S2)` -> `before_s2 = snap(db, s2)` BEFORE the When call (after the Given rows), `assert snap(db, s2) == before_s2` after. One `before_…` per row; an item the same (`before_ia = snap(db, ia)`).
- `nothing written` -> `before = written(db)` before the call, `assert written(db) == before` after. Only when the card has that Then line.
- `count:` -> `assert count_rows(db, Inventory) == 2`; `inventory_ledger` -> `count_rows(db, InventoryLedger)`.
- `raises: DataError` -> as INV-L-17 below (with `db.begin_nested()`). `raises: IntegrityError` -> `with pytest.raises(IntegrityError) as exc:` and the call directly inside, no `begin_nested`. The other `raises:` lines are asserts on `exc.value` after the `with` block, each under its own `# Then N`.

## Example tests (copy this style)
```python
def test_inv_st_12__factory_filter_soft_delete_and_scope(db, w1, w2, f1, f2, f9, i1, i2, i9, mk_stock):
    """INV-ST-12 — factory filter, soft-delete and workspace scope apply to every part.
    Rules: stats_filtered R1; _filtered_query R1, R2, R5"""
    mk_stock(i1, f1)
    mk_stock(i2, f1, deleted=True, qty=7)
    mk_stock(i1, f2, qty=4)
    mk_stock(i9, f9, workspace_id=w2.id)

    result = dao.stats_filtered(db, workspace_id=w1.id, factory_id=f1.id)

    # Then 1
    assert result[0] == 1
    # Then 2
    assert result[1] == 5
    # Then 3
    assert result[2] == Decimal("10.00")
    # Then 4
    assert by_type(result) == {(STORAGE, 1, 5)}


def test_inv_en_05__soft_deleted_row_restored_and_aligned(db, w1, u1, u2, f1, i1, mk_stock, mk_entry):
    """INV-EN-05 — a soft-deleted row is restored, aligned and returned.
    Rules: ensure_for_factory_item_type R3; restore R1, R2"""
    s1 = mk_stock(i1, f1, deleted=True, qty=7, avg_price=Decimal("5.00"), note="old note")
    mk_entry(i1, f1, qty_after=20, avg_price_after=Decimal("6.00"), performed_at=T1)

    result = dao.ensure_for_factory_item_type(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE,
                                              workspace_id=w1.id, created_by=u2.id)

    # Then 1
    assert result.id == s1.id
    # Then 2
    row = reread(db, s1)
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 3
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 4
    assert row.qty == 20
    # Then 5
    assert row.avg_price == Decimal("6.00")
    # Then 6
    assert row.updated_by == u2.id
    # Then 7
    assert row.note == "old note"
    # Then 8
    assert row.created_by == u1.id
    # Then 9
    assert count_rows(db, Inventory) == 1


def test_inv_l_17__negative_limit_rejected(db, w1, f1, i1, mk_stock):
    """INV-L-17 — negative limit is rejected by the database and nothing changes.
    Rules: list_filtered R5, Errors row 1"""
    s1 = mk_stock(i1, f1)
    before = written(db)
    before_s1 = snap(db, s1)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.list_filtered(db, workspace_id=w1.id, limit=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201W"
    # Then 4
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, s1) == before_s1


def test_inv_fq_36__stock_in_soft_deleted_factory_not_matched(db, w1, f1, i1, mk_factory, mk_stock):
    """INV-FQ-36 — stock in a soft-deleted factory is not matched.
    Rules: _filtered_query R11a [BUG-882]; list_filtered R1a [BUG-882]"""
    fa = mk_factory("Old Plant", "OP", is_active=True, is_deleted=True)
    s1 = mk_stock(i1, f1)
    mk_stock(i1, fa, qty=30)

    result = dao.list_filtered(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [s1.id]
```
