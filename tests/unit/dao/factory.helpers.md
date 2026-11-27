# Helpers for `test_factory.py`

## Fixtures (add them as test arguments)
- `db` — the session.
- `w1`, `w2` — W1, W2. `u1`, `u2` — U1, U2. These rows already exist in every test: never build them, just request the ones the test names.
- `mk_factory`, `mk_machine`, `mk_section` — row builders.
- Every fixture a test uses — builders and actors too, also one used only in the When call or in an assert (`w1`, `u1`, `u2`) — must be in its argument list.
- ONLY the names above can be arguments. Rows the test builds itself (`f1`, `f9`, `fd`, `fd9`, `fi`, `fx`, `l1`, `ma1`, `sc1`) are local variables. `dao`, the constants and the reading helpers are used directly, never as arguments.
- The clock is already patched to NOW. Never patch or mock anything.

## Builders (keyword arguments only)
- `mk_factory(name=..., abbreviation=..., **columns)` — one "factory" with the Conventions defaults. Each thing the card lists after "but" is one more keyword, named like the card's column. The word "deleted" is the keyword `deleted=True` (it sets the three "deleted" columns itself). Two things after "but" -> both keywords: "but `is_active False`, deleted" -> `is_active=False, deleted=True`.
- `mk_machine(of=f1, name="Lathe")` — "machine of F1, `name "Lathe"`". `mk_section(of=f1, name="Assembly")` — "section of F1, `name "Assembly"`".
- Never add a keyword the card's row does not list — a value of the When call or of another row is not a value of this row.

## Card says -> write
| Card says | Write |
|---|---|
| `W1.id`, `W2.id`, `U1.id`, `U2.id`, `F1.id`, `F9.id`, `FD.id`, `FD9.id`, `FI.id`, `FX.id`, `L1.id`, MA1, SC2 | `w1.id`, `w2.id`, `u1.id`, `u2.id`, `f1.id`, `f9.id`, `fd.id`, `fd9.id`, `fi.id`, `fx.id`, `l1.id`, `ma1`, `sc2` |
| MISSING, NOW, T0 | the names `MISSING`, `NOW`, `T0` |
| F1 = factory, `name "Main Plant"`, `abbreviation "MP"`. | `f1 = mk_factory(name="Main Plant", abbreviation="MP")` |
| factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted | `mk_factory(name="Old Plant", abbreviation="OP", deleted=True)` |
| factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id` | `mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id)` |
| factory, `name "Idle Plant"`, `abbreviation "IP"`, but `is_active False` | `mk_factory(name="Idle Plant", abbreviation="IP", is_active=False)` |
| machine of F1, `name "Press"`, but `is_active False` | `mk_machine(of=f1, name="Press", is_active=False)` |
| "No factories exist." | no code |

Build the Given rows in the order written, one statement per row. Give a row a variable only if the test uses it later. Text in parentheses ( ) after a Given row and a sentence after the When call are explanations: no code for them. Copy every text in quotes character for character (`" mp"` keeps its space).

A Given line that contains code is run as written, at that place, with lower-case row names: "`F1.abbreviation = "ZX"`, then `db.flush()`" -> the two lines `f1.abbreviation = "ZX"` and `db.flush()`; "`db.refresh(FI)`" -> the line `db.refresh(fi)`. Snapshots (`before…`) come after these lines.

## Reading helpers (call them directly)
- `ids(result)`, `names(result)` — lists of the ids / names in the order returned.
- `by_id(result, f1)` — the element of `result` with F1's id.
- `reread(db, row)` — fresh copy of a factory, machine or section from the database. `snap(db, row)` — all columns of a row.
- `count_rows(db, "factories")` — rows of the table the card names.
- `written(db)` — the "nothing written" counts.

## Already imported (never import)
`pytest`, `dao`, `Factory`, `FactoryCreate`, `FactoryUpdate`, `Machine`, `FactorySection`, `DataError`, `IntegrityError`, `InvalidRowCountInLimitClause`, `InvalidRowCountInResultOffsetClause`, `ForeignKeyViolation`, `NotNullViolation`, `UniqueViolation`.

## How to write each kind of line
- When -> the call exactly as shown, with lower-case row names: `result = dao.get_by_id_and_workspace(db, id=f1.id, workspace_id=w1.id)`, `result = dao.get(db, f9.id)`, `result = dao.update(db, db_obj=f1, obj_in={"is_active": False})`. Keep every argument, also `None`, `0`, `-1`; add none.
- `returns:` -> `assert` + the expression as written, nothing changed but the lower-case names (keep `<=`, `>=`, `in`, `sorted(...)`, `set(...)` as the card has them): `assert result is None`, `assert result == []`, `assert names(result) == ["apple", "Zulu"]` (keep the card's order), `assert set(ids(result)) <= {fd1.id, fd2.id, f3.id}`.
- `raises: DataError` / `raises: IntegrityError` (also "`IntegrityError` on flush") -> as FCD-GA-22 below: `with pytest.raises(...) as exc:`, inside it `with db.begin_nested():`, inside that the call (without `result =`). The other `raises:` lines are asserts on `exc.value` after the `with` block, each under its own `# Then N`. Use `pytest.raises` only when a Then line starts with `raises:`, and then always, also if you think no error comes.
- `nothing written` -> `before = written(db)` before the call, `assert written(db) == before` after. Only when the card has that Then line.
- `unchanged(F1)` -> `before_f1 = snap(db, f1)` BEFORE the When call (after the Given lines), `assert snap(db, f1) == before_f1` after. Only when the card has that Then line.
- `re-read F1:` -> `row = reread(db, f1)`, then one `assert` per value; a line with two values gets an assert for each. Later `re-read F1:` lines reuse `row`; for another row (F2, MA1) call `reread` again. "re-read the returned row" -> `row = reread(db, result)`.
- `created_at == created_before` -> as FCD-RS-02 below.
- `count:` -> `assert count_rows(db, "machines") == 2` — the card's table name and number.

## Example tests (copy this style)
```python
def test_fcd_gw_05__a_soft_deleted_factory_is_returned_along_with_a_live_one(db, w1, mk_factory):
    """FCD-GW-05 — a soft-deleted factory is returned along with a live one.
    Rules: `get_by_workspace` R4 (P1)"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [f1.id, fd.id]
    # Then 2
    assert by_id(result, fd).is_deleted is True
    # Then 3
    assert by_id(result, f1).is_deleted is False


def test_fcd_gw_22__factories_come_back_in_id_order_not_in_name_order_and_not_in_the(db, w1, mk_factory):
    """FCD-GW-22 — factories come back in id order, not in name order and not in the table's physical order.
    Rules: `get_by_workspace` R3 [BUG-100]"""
    f1 = mk_factory(name="Zulu", abbreviation="ZU")
    f2 = mk_factory(name="apple", abbreviation="AP")
    f1.abbreviation = "ZX"
    db.flush()

    result = dao.get_by_workspace(db, workspace_id=w1.id)

    # Then 1
    assert sorted(ids(result)) == [f1.id, f2.id]
    # Then 2
    assert ids(result) == [f1.id, f2.id]


def test_fcd_ga_22__negative_limit_is_rejected_by_the_database_and_nothing_changes(db, w1, mk_factory):
    """FCD-GA-22 — negative limit is rejected by the database and nothing changes.
    Rules: `get_active_factories` R5, Errors (negative `limit`, as `get_by_workspace`)"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    before = written(db)
    before_f1 = snap(db, f1)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_active_factories(db, workspace_id=w1.id, limit=-1)

    # Then 2
    assert isinstance(exc.value.orig, InvalidRowCountInLimitClause)
    # Then 3
    assert exc.value.orig.pgcode == "2201W"
    # Then 4
    assert "LIMIT must not be negative" in str(exc.value.orig)
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, f1) == before_f1


def test_fcd_sd_10__a_factory_of_another_workspace_is_deleted_all_the_same(db, w2, u2, mk_factory):
    """FCD-SD-10 — a factory of another workspace is deleted all the same.
    Rules: `soft_delete` R6"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f9 = mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id)
    before_f1 = snap(db, f1)

    result = dao.soft_delete(db, db_obj=f9, deleted_by=u2.id)

    # Then 1
    assert result is f9
    # Then 2
    row = reread(db, f9)
    assert row.is_deleted is True
    # Then 3
    assert row.deleted_at == NOW
    assert row.deleted_by == u2.id
    # Then 4
    assert row.workspace_id == w2.id
    # Then 5
    assert snap(db, f1) == before_f1


def test_fcd_rs_02__no_other_column_of_the_factory_is_changed_by_the_restore(db, w1, u1, mk_factory):
    """FCD-RS-02 — no other column of the factory is changed by the restore.
    Rules: `restore` R2"""
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)
    created_before = fd.created_at

    result = dao.restore(db, db_obj=fd)

    # Then 1
    assert result is fd
    # Then 2
    row = reread(db, fd)
    assert row.name == "Old Plant"
    assert row.abbreviation == "OP"
    # Then 3
    assert row.workspace_id == w1.id
    assert row.created_by == u1.id
    # Then 4
    assert row.created_at == created_before
    # Then 5
    assert row.updated_at is not None
    # Then 6
    assert row.is_deleted is False


def test_fcd_rs_08__a_factory_that_is_already_live_loaded_from_the_database_is_left(db, mk_factory):
    """FCD-RS-08 — a factory that is already live, loaded from the database, is left exactly as it is with no UPDATE.
    Rules: `restore` R4"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    db.refresh(f1)
    before_f1 = snap(db, f1)

    result = dao.restore(db, db_obj=f1)

    # Then 1
    assert result is f1
    # Then 2
    assert snap(db, f1) == before_f1
    # Then 3
    row = reread(db, f1)
    assert row.updated_at is None
    # Then 4
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 5
    assert row.deleted_at is None
    assert row.deleted_by is None
    # Then 6
    assert count_rows(db, "factories") == 1
```
