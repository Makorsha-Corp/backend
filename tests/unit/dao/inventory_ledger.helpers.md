# Helpers for `test_inventory_ledger.py`

## Fixtures (add them as test arguments)
- `db` — the session.
- `w1`, `w2` — W1, W2. `u1`, `u2` — U1, U2. `f1`, `f2`, `f9`, `fd` — F1, F2, F9, FD. `i1`, `i2`, `i9`, `ir` — I1, I2, I9, IR. These rows already exist in every test: never build them, just request the ones the test names.
- `mk_entry`, `mk_x9` — row builders.
- Every fixture a test uses — builders and actors too — must be in its argument list.
- The ONLY possible arguments are: `db, w1, w2, u1, u2, f1, f2, f9, fd, i1, i2, i9, ir, mk_entry, mk_x9`. Entries the test builds itself (`e1`, `eb`, `x9`) are local variables, never arguments. `dao`, the constants and the reading helpers are used directly, never as arguments.

## Builders
- `mk_entry(performed_at=..., **columns)` — inserts one "entry" with the Conventions defaults and flushes. Keyword arguments only; the keywords are the column names of the card.
- `mk_x9()` — inserts the row X9. It takes no arguments. Never build X9 with `mk_entry`.
- A default with values replaced = one keyword for each value the card lists after "but", each keyword once: `mk_entry(performed_at=T2, factory_id=f2.id, qty_after=92)`. Never add a keyword the card does not list.

## Card says -> write
| Card says | Write |
|---|---|
| `W1.id`, `U2.id`, `F2.id`, `FD.id`, `I9.id`, `IR.id`, `E1.id`, `EC.id`, `X9.id` | `w1.id`, `u2.id`, `f2.id`, `fd.id`, `i9.id`, `ir.id`, `e1.id`, `ec.id`, `x9.id` |
| STORAGE, DAMAGED, WASTE, SCRAP, MISSING, T1 … T5, HIGH_ID | constants with these names |
| E1 = entry, `performed_at T1`. | `e1 = mk_entry(performed_at=T1)` |
| X9. | `x9 = mk_x9()` |
| entry, `performed_at T2`, but `factory_id F2.id` | `mk_entry(performed_at=T2, factory_id=f2.id)` |
| entry, `performed_at T3`, but `inventory_type SCRAP` | `mk_entry(performed_at=T3, inventory_type=SCRAP)` |
| entry, `performed_at T2`, but `performed_by None` | `mk_entry(performed_at=T2, performed_by=None)` |
| entry, `performed_at T1`, but `avg_price_after Decimal("7.00")` | `mk_entry(performed_at=T1, avg_price_after=Decimal("7.00"))` |
| entry, `performed_at T1`, but `source_type "to"` | `mk_entry(performed_at=T1, source_type="to")` |
| EC = entry, `performed_at T1`, but `id HIGH_ID` | `ec = mk_entry(performed_at=T1, id=HIGH_ID)` |
| "No ledger entries exist." | no code |
| `datetime(2026, 1, 1, 10, 30, 0)` | the same text (`datetime` is imported) |

Each "but" row above shows ONE change; a card with several "but" values gets one keyword for each. Build the Given rows in the order written, one statement per row. Give a row a variable only if the test uses it later. Text in parentheses ( ) after a Given row is an explanation: no code for it. Take "before" values after the last Given row, just before the call.

## Reading helpers (plain functions, call them directly)
- `ids(result)` — list of the ids in the order returned.
- `reread(db, row)` — fresh copy of a row from the database.
- `snap(db, row)` — dict of all columns of a row.
- `count_rows(db, InventoryLedger)` — rows of `inventory_ledger` in all workspaces.
- `written(db)` — the "nothing written" counts.

## Already imported (never import)
`pytest`, `datetime`, `Decimal`, `dao`, `InventoryLedger`, `DataError`, `ArgumentError`, `InvalidRowCountInLimitClause`, `InvalidRowCountInResultOffsetClause`.

## How to write each kind of Then line
- Before the assertions of Then line N write `# Then N` on its own line (each once, in order); for `raises:` before `with pytest.raises`.
- Expected values are the card's literals (`20`, `Decimal("6.00")`, `"po"`), never read from a row or a "before" variable.
- When -> the call exactly as shown, with lower-case names: `result = dao.get_latest_entry(db, factory_id=fd.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)`. Keep every argument, also `None`, `0` and `-1`.
- `dao.calculate_balance(...)`: write the call exactly as shown; never wrap it in `pytest.raises`. Use `pytest.raises` only when a Then line starts with `raises:`.
- `returns:` -> `assert` + the expression as written, nothing changed but the lower-case names: `assert ids(result) == [e2.id, e3.id, e1.id]` (keep the card's order), `assert result == []`, `assert len(result) == 3`, `assert result[3].id == e1.id`, `assert sorted(ids(result)) == [e1.id, e2.id, e3.id, e4.id]`, `assert result is None`, `assert result is True`, `assert type(result) is bool`, `assert type(result[0]) is int`, `assert str(result[1]) == "0.00"`, `assert result.qty_after == 20`, `assert result.avg_price_after is None`, `assert result.performed_at == T2`, `assert result.id in [e2.id, e3.id]` (a "looser check": just that).
- `raises: DataError` -> as LED-W-33 below (with `db.begin_nested()`). `raises: ArgumentError` -> `with pytest.raises(ArgumentError) as exc:` and the call directly inside, no `begin_nested`. The other `raises:` lines are asserts on `exc.value` after the `with` block, each under its own `# Then N`: `assert str(exc.value).startswith("…")` with the card's text copied character for character.
- `nothing written` -> `before = written(db)` before the call, `assert written(db) == before` after. Only when the card has that Then line.
- `unchanged(E1)` -> `before_e1 = snap(db, e1)` BEFORE the When call (after the Given rows), `assert snap(db, e1) == before_e1` after. Only when the card has that Then line.
- `re-read E1:` -> `row = reread(db, e1)`, then one `assert` per value; a line with two values gets an assert for each (`assert row.qty_after == 20`, `assert row.performed_at == T1`). Later `re-read E1:` lines reuse `row`.
- `count:` -> `assert count_rows(db, InventoryLedger) == 1` — the card's number itself.

## Example tests (copy this style)
```python
def test_led_pf_01__returns_that_user_s_entries_of_every_type_factory_item_and_transaction(db, w1, u1, u2, f2, i2, mk_entry):
    """LED-PF-01 — returns that user's entries of every type, factory, item and transaction type.
    Rules: `get_by_performer` R1, R4"""
    e1 = mk_entry(performed_at=T1)
    mk_entry(performed_at=T3, performed_by=u2.id)
    mk_entry(performed_at=T2, performed_by=None)
    e4 = mk_entry(performed_at=T4, inventory_type=DAMAGED, factory_id=f2.id, item_id=i2.id, transaction_type="sale")

    result = dao.get_by_performer(db, performed_by=u1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [e4.id, e1.id]
    # Then 3
    assert isinstance(result[0], InventoryLedger)


def test_led_w_04__a_call_for_the_other_workspace_returns_only_that_workspace_s_entry(db, w2, mk_entry, mk_x9):
    """LED-W-04 — a call for the other workspace returns only that workspace's entry.
    Rules: `get_by_workspace` R1"""
    mk_entry(performed_at=T1)
    x9 = mk_x9()

    result = dao.get_by_workspace(db, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [x9.id]


def test_led_w_33__negative_limit_is_rejected_by_the_database_and_nothing_changes(db, w1, mk_entry):
    """LED-W-33 — negative limit is rejected by the database and nothing changes.
    Rules: `get_by_workspace` R10, Errors row 1"""
    e1 = mk_entry(performed_at=T1)
    before = written(db)
    before_e1 = snap(db, e1)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_workspace(db, workspace_id=w1.id, limit=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201W"
    # Then 4
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, e1) == before_e1


def test_led_bal_12__newer_entries_of_other_buckets_do_not_change_the_balance(db, w1, w2, f1, f2, i1, i2, mk_entry):
    """LED-BAL-12 — newer entries of other buckets do not change the balance.
    Rules: `calculate_balance` R4 [BUG-655], R3"""
    mk_entry(performed_at=T1, qty_after=20, avg_price_after=Decimal("6.00"))
    mk_entry(performed_at=T2, inventory_type=DAMAGED, qty_after=91)
    mk_entry(performed_at=T3, factory_id=f2.id, qty_after=92)
    mk_entry(performed_at=T4, item_id=i2.id, qty_after=93)
    mk_entry(performed_at=T5, workspace_id=w2.id, qty_after=94)

    result = dao.calculate_balance(db, factory_id=f1.id, item_id=i1.id, inventory_type=STORAGE, workspace_id=w1.id)

    # Then 1
    assert result[0] == 20
    # Then 2
    assert result[1] == Decimal("120.00")
```
