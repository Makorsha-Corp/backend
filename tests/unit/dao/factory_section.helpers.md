# Helpers for `test_factory_section.py`

## Fixtures (add them as test arguments)
- `db` — the session.
- `w1`, `w2` — W1, W2. `u1`, `u2` — U1, U2. `f1`, `f2`, `f9`, `fd`, `fi` — the factories F1, F2, F9, FD, FI. These rows already exist in every test: never build them, just request the ones the test names.
- `mk_section`, `mk_machine`, `mk_assignment` — row builders.
- Every fixture a test uses — builders and standing rows too, also one used only in the When call or in an assert (`w1`, `u1`, `f1`, `fd`) — must be in its argument list.
- ONLY the names above can be arguments. Rows the test builds itself (`s1`, `s9`, `sx`, `sh`, `si`, `l1`, `m1`, `a1`) are local variables, never arguments. `dao`, the constants and the reading helpers are used directly, never as arguments.
- The clock is already patched to NOW. Never patch or mock anything.

## Builders (keyword arguments only)
- `mk_section(name=..., **columns)` — one "section" with the Conventions defaults (in F1, in W1, created by U1). Each thing the card lists after "but" is one more keyword, named like the card's column. The word "deleted" is the keyword `deleted=True` (it sets the three "deleted" columns itself). Several things after "but" -> one keyword each: "but `factory_id FD.id`, `is_active False`" -> `factory_id=fd.id, is_active=False`.
- `mk_machine(of=f1, name="Lathe")` — "machine of F1, `name "Lathe"`". `mk_assignment(of=m1, to=s1)` — "assignment of M1 to S1". Only these two keywords each.
- Never add a keyword the card's row does not list — a value of the When call or of another row is not a value of this row. A section without "but" is only `mk_section(name="...")`.

## Card says -> write
| Card says | Write |
|---|---|
| `W1.id`, `W2.id`, `U1.id`, `U2.id`, `F1.id`, `F2.id`, `F9.id`, `FD.id`, `FI.id`, `S1.id`, `SX.id`, `SH.id`, `SX9.id`, `L1.id`, M1, A1 | `w1.id`, `w2.id`, `u1.id`, `u2.id`, `f1.id`, `f2.id`, `f9.id`, `fd.id`, `fi.id`, `s1.id`, `sx.id`, `sh.id`, `sx9.id`, `l1.id`, `m1`, `a1` |
| MISSING, NOW, T0 | the names `MISSING`, `NOW`, `T0` |
| S1 = section, `name "Cutting"`. | `s1 = mk_section(name="Cutting")` |
| section, `name "Old Line"`, but deleted | `mk_section(name="Old Line", deleted=True)` |
| section, `name "Welding"`, but `factory_id F2.id` | `mk_section(name="Welding", factory_id=f2.id)` |
| section, `name "Idle Bay"`, but `is_active False` | `mk_section(name="Idle Bay", is_active=False)` |
| section, `name "Cutting"`, but `updated_by U1.id` | `mk_section(name="Cutting", updated_by=u1.id)` |
| "No sections exist." | no code |

Build the Given rows in the order written, one statement per row. Give a row a variable only if the test uses it later. Text in parentheses ( ) after a Given row or a Then line and a sentence after the When call are explanations: no code for them. Copy every text in quotes character for character.

A Given line that contains code is run as written, at that place, with the lower-case row name: "`db.refresh(S1)`" -> the line `db.refresh(s1)`. Snapshots (`before…`) come after it.

## Reading helpers (call them directly)
- `ids(result)`, `names(result)` — lists of the ids / names in the order returned.
- `by_id(result, si)` — the element of `result` with SI's id.
- `reread(db, row)` — fresh copy of a section, factory, machine or assignment from the database. `snap(db, row)` — all columns of such a row.
- `count_rows(db, "factory_sections")` — rows of the table the card names.
- `written(db)` — the "nothing written" counts.

## Already imported (never import)
`pytest`, `dao`, `FactorySection`, `FactorySectionCreate`, `FactorySectionUpdate`, `Machine`, `MachineSectionAssignment`, `DataError`, `IntegrityError`, `InvalidRowCountInLimitClause`, `InvalidRowCountInResultOffsetClause`, `ForeignKeyViolation`, `NotNullViolation`.

## How to write each kind of line
- When -> the call exactly as shown, with lower-case row names: `result = dao.get_by_factory(db, factory_id=fd.id, workspace_id=w1.id, skip=1)`, `result = dao.get(db, s9.id)`, `result = dao.restore(db, db_obj=sx)`. Keep every argument, also `None`, `0`, `-1`; add none.
- `returns:` -> `assert` + the expression as written, nothing changed but the lower-case names (keep `<=`, `in`, `sorted(...)`, `set(...)`, `len(...)` as the card has them): `assert result is sx`, `assert result == []`, `assert set(ids(result)) <= {s1.id, sx.id}`, `assert by_id(result, si).is_active is False`.
- `raises: DataError` / `raises: IntegrityError` (also "`IntegrityError` on flush") -> as FSD-GF-30 below: `with pytest.raises(...) as exc:`, inside it `with db.begin_nested():`, inside that the call (without `result =`). The other `raises:` lines are asserts on `exc.value` after the `with` block, each under its own `# Then N`, the expression as written: `assert 'column "name"' in str(exc.value.orig)`. Use `pytest.raises` only when a Then line starts with `raises:`, and then always.
- `nothing written` -> `before = written(db)` before the call, `assert written(db) == before` after. Only when the card has that Then line.
- `unchanged(S2)` -> `before_s2 = snap(db, s2)` BEFORE the When call (after all Given lines), `assert snap(db, s2) == before_s2` after. The same for a factory, machine or assignment: `unchanged(FD)` -> `before_fd = snap(db, fd)` / `assert snap(db, fd) == before_fd`. Only when the card has that Then line.
- `re-read SX:` -> `row = reread(db, sx)`, then one `assert` per value. A line with two values needs TWO asserts, never one: "`deleted_at is None`, `deleted_by is None`" -> `assert row.deleted_at is None` and `assert row.deleted_by is None`. Later `re-read SX:` lines reuse `row`; for another row (S2, FD, A1) call `reread` again: `row = reread(db, fd)`. "re-read the returned row" -> `row = reread(db, result)`.
- `created_at == created_before` -> as FSD-RS-02 below.
- `count:` -> `assert count_rows(db, "machines") == 1` — the card's table name and number.

## Example tests (copy this style)
```python
def test_fsd_gf_04__the_other_workspace_gets_its_own_section(db, w2, f9, mk_section):
    """FSD-GF-04 — the other workspace gets its own section.
    Rules: `get_by_factory` R1"""
    mk_section(name="Cutting")
    s9 = mk_section(name="Packing", factory_id=f9.id, workspace_id=w2.id)

    result = dao.get_by_factory(db, factory_id=f9.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [s9.id]
    # Then 2
    assert result[0].workspace_id == w2.id


def test_fsd_gf_10__a_soft_deleted_section_is_not_returned(db, w1, f1, mk_section):
    """FSD-GF-10 — a soft-deleted section is not returned.
    Rules: `get_by_factory` R2 [BUG-905]"""
    s1 = mk_section(name="Cutting")
    mk_section(name="Old Line", deleted=True)

    result = dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id)

    # Then 1
    assert s1.id in ids(result)
    # Then 2
    assert ids(result) == [s1.id]


def test_fsd_gf_30__negative_limit_is_rejected_by_the_database_and_nothing_changes(db, w1, f1, mk_section):
    """FSD-GF-30 — negative limit is rejected by the database and nothing changes.
    Rules: `get_by_factory` R5, Errors row 1"""
    s1 = mk_section(name="Cutting")
    before = written(db)
    before_s1 = snap(db, s1)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_by_factory(db, factory_id=f1.id, workspace_id=w1.id, limit=-1)

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


def test_fsd_sd_06__the_machine_its_assignment_row_and_the_factory_of_the_deleted_section(db, u2, f1, mk_section, mk_machine, mk_assignment):
    """FSD-SD-06 — the machine, its assignment row and the factory of the deleted section are left exactly as they were.
    Rules: `soft_delete` R3"""
    s1 = mk_section(name="Cutting")
    m1 = mk_machine(of=f1, name="Lathe")
    a1 = mk_assignment(of=m1, to=s1)
    before_a1 = snap(db, a1)
    before_m1 = snap(db, m1)
    before_f1 = snap(db, f1)
    before = written(db)

    result = dao.soft_delete(db, db_obj=s1, deleted_by=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.is_deleted is True
    # Then 3
    assert snap(db, a1) == before_a1
    # Then 4
    row = reread(db, a1)
    assert row.machine_id == m1.id
    assert row.factory_section_id == s1.id
    # Then 5
    assert count_rows(db, "machine_section_assignments") == 1
    # Then 6
    assert snap(db, m1) == before_m1
    # Then 7
    assert count_rows(db, "machines") == 1
    # Then 8
    assert snap(db, f1) == before_f1
    # Then 9
    row = reread(db, f1)
    assert row.is_deleted is False
    assert row.is_active is True
    # Then 10
    assert written(db) == before


def test_fsd_rs_02__no_other_column_of_the_section_is_changed_by_the_restore(db, w1, u1, f1, mk_section):
    """FSD-RS-02 — no other column of the section is changed by the restore.
    Rules: `restore` R2"""
    sx = mk_section(name="Old Line", deleted=True)
    created_before = sx.created_at

    result = dao.restore(db, db_obj=sx)

    # Then 1
    assert result is sx
    # Then 2
    row = reread(db, sx)
    assert row.name == "Old Line"
    assert row.factory_id == f1.id
    # Then 3
    assert row.workspace_id == w1.id
    assert row.created_by == u1.id
    # Then 4
    assert row.created_at == created_before
    # Then 5
    assert row.updated_at is not None
    # Then 6
    assert row.is_deleted is False


def test_fsd_inh_09__update_with_an_explicit_null_name_changes_only_the_factory(db, w1, f2, mk_section):
    """FSD-INH-09 — update with an explicit null name changes only the factory.
    Rules: inherited R3"""
    s1 = mk_section(name="Cutting")

    result = dao.update(db, db_obj=s1, obj_in=FactorySectionUpdate(name=None, factory_id=f2.id))

    # Then 1
    assert result.id == s1.id
    # Then 2
    row = reread(db, s1)
    assert row.factory_id == f2.id
    # Then 3
    assert row.name == "Cutting"
    # Then 4
    assert row.workspace_id == w1.id
```
