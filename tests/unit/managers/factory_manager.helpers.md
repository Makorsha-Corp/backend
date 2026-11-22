# Helpers for `test_factory_manager.py`

## Fixtures (add them as test arguments)
- `db` — the session.
- `w1`, `w2`, `w3` — W1, W2, W3. `u1`, `u2` — U1, U2. These rows already exist in every test: never build them, just request the ones the test names.
- `mk_factory`, `mk_machine`, `mk_section`, `mk_line`, `mk_batch` — row builders. `mk_line(of=f1, name="Line A")` is "line of F1"; `mk_batch(on=l1, batch_number="BATCH-2026-001", status="draft")` is "batch on L1".
- Every fixture a test uses — builders and actors too, also one used only in the When call or in an assert (`w1`, `u1`, `u2`) — must be in its argument list.
- ONLY the names above can be arguments. Rows the test builds itself (`f1`, `f9`, `fd`, `fd9`, `d1`, `ma1`, `sc1`) are local variables. `M`, the constants and the reading helpers are used directly, never as arguments.
- The clock is already patched to NOW. Never patch or mock anything.

## Builders (keyword arguments only)
- `mk_factory(name=..., abbreviation=..., **columns)` — one "factory" with the Conventions defaults. Each thing the card lists after "but" is one more keyword, named like the card's column. The word "deleted" is the keyword `deleted=True` (it sets the three "deleted" columns itself). Two things after "but" -> both keywords.
- `mk_machine(of=f1, name="Lathe")` — "machine of F1, `name "Lathe"`". `mk_section(of=f1, name="Assembly")` — "section of F1, `name "Assembly"`".
- Never add a keyword the card's row does not list — a value of the When call or of another row is not a value of this row.

## Card says -> write
| Card says | Write |
|---|---|
| `W1.id`, `W3.id`, `U1.id`, `U2.id`, `F1.id`, `F9.id`, `FD.id`, `FD9.id`, `D1.id`, MA1, SC2 | `w1.id`, `w3.id`, `u1.id`, `u2.id`, `f1.id`, `f9.id`, `fd.id`, `fd9.id`, `d1.id`, `ma1`, `sc2` |
| M, MISSING, NOW, T0 | the names `M`, `MISSING`, `NOW`, `T0` |
| F1 = factory, `name "Main Plant"`, `abbreviation "MP"`. | `f1 = mk_factory(name="Main Plant", abbreviation="MP")` |
| factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted | `mk_factory(name="Old Plant", abbreviation="OP", deleted=True)` |
| factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id` | `mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id)` |
| machine of F1, `name "Press"`, but `is_active False` | `mk_machine(of=f1, name="Press", is_active=False)` |
| "No factories exist." | no code |

Build the Given rows in the order written, one statement per row. Give a row a variable only if the test uses it later. Text in parentheses ( ) after a Given row and a sentence after the When call are explanations: no code for them. Copy every text in quotes character for character, as a plain string: `"   "` is three spaces, `" Ops "` keeps both spaces, `"\t"`, `" \n "`, `"A\\B Works"`, `"\\"` as written.

## Reading helpers (call them directly)
- `ids(result)`, `names(result)` — lists of the ids / names in the order returned.
- `reread(db, row)` — fresh copy of a row from the database. `snap(db, row)` — all columns of a row.
- `count_rows(db, "factories")` — rows of the table the card names.
- `written(db)` — the "nothing written" counts.

## Already imported (never import)
`pytest`, `HTTPException`, `ValidationError`, `IntegrityError`, `DataError`, `ForeignKeyViolation`, `InvalidRowCountInLimitClause`, `InvalidRowCountInResultOffsetClause`, `Factory`, `FactoryCreate`, `FactoryUpdate`.

## How to write each kind of line
- When -> the call exactly as shown, with lower-case row names: `result = M.get_factory(db, factory_id=f1.id, workspace_id=w1.id)`. Keep every argument, also `None`, `0`, `-1`, `""`; add none. `FactoryUpdate()` stays empty. The `_check…` methods are called the same way: `result = M._check_name_exists(db, workspace_id=w1.id, name="Main Plant", exclude_id=f2.id)`, `result = M._check_abbreviation_exists(db, workspace_id=w1.id, abbreviation="MP")`.
- `include_deleted=True` on `M.get_factory(...)`: write the call exactly as shown; never wrap it in `pytest.raises`. Use `pytest.raises` only when a Then line starts with `raises:`.
- target `schema` -> the When is only `result = FactoryUpdate(name="a", abbreviation="b")`; `M` is not called.
- `returns:` -> `assert` + the expression as written, nothing changed but the lower-case names: `assert result is f1`, `assert result is True`, `assert ids(result) == [f2.id]`, `assert sorted(ids(result)) == [f1.id, f2.id]`, `assert names(result) == ["alpha", "Bravo"]` (keep the card's order), `assert result == []`. "after the call, `X`" -> `assert X`.
- `raises: HTTPException` -> as FAC-D-08 below: no `begin_nested`. `raises: ValidationError` -> as FAC-C-18 below. The other `raises:` lines are asserts on `exc.value` after the `with` block, each under its own `# Then N`; an f-string stays one: `assert exc.value.detail == f"Factory with ID {f9.id} not found"`.
- `raises: IntegrityError` / `raises: DataError` -> the call inside `db.begin_nested()`:
  ```python
  # Then 1
  with pytest.raises(IntegrityError) as exc:
      with db.begin_nested():
          M.delete_factory(db, factory_id=f1.id, workspace_id=w1.id, user_id=MISSING)
  # Then 2
  assert isinstance(exc.value.orig, ForeignKeyViolation)
  ```
- `nothing written` -> `before = written(db)` before the call, `assert written(db) == before` after. Only when the card has that Then line.
- `unchanged(F1)` -> `before_f1 = snap(db, f1)` BEFORE the When call (after the Given rows), `assert snap(db, f1) == before_f1` after. Only when the card has that Then line.
- `re-read F1:` -> `row = reread(db, f1)`, then one `assert` per value; a line with two values gets an assert for each. Later `re-read F1:` lines reuse `row`; for another row (F2, MA1) call `reread` again. "re-read the returned row" -> `row = reread(db, result)`.
- `created_at == created_before` -> `created_before = f1.created_at` after the Given rows, before the call; then `assert row.created_at == created_before`.
- `count:` -> `assert count_rows(db, "factories") == 2` — the card's table name and number.

## Example tests (copy this style)
```python
def test_fac_c_01__create_stores_a_factory_with_the_name_abbreviation_workspace_and(db, w1, u2):
    """FAC-C-01 — create stores a factory with the name, abbreviation, workspace and creator given.
    Rules: `create_factory` R1, Side effects"""
    result = M.create_factory(db, factory_data=FactoryCreate(name="Main Plant", abbreviation="MP"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert isinstance(result, Factory)
    # Then 2
    assert result.id is not None
    # Then 3
    row = reread(db, result)
    assert row.name == "Main Plant"
    assert row.abbreviation == "MP"
    # Then 4
    assert row.workspace_id == w1.id
    # Then 5
    assert row.created_by == u2.id
    # Then 6
    assert count_rows(db, "factories") == 1


def test_fac_c_18__an_empty_abbreviation_is_rejected_by_factorycreate(db):
    """FAC-C-18 — an empty abbreviation is rejected by FactoryCreate.
    Rules: `create_factory` R7a [BUG-896], Errors row 3"""
    # Then 1
    with pytest.raises(ValidationError):
        FactoryCreate(name="Main Plant", abbreviation="")

    # Then 2
    assert count_rows(db, "factories") == 0


def test_fac_u_34__an_empty_request_keeps_the_previous_updated_by(db, w1, u1, u2, mk_factory):
    """FAC-U-34 — an empty request keeps the previous updated_by.
    Rules: `update_factory` R11 [BUG-900]"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP", updated_by=u1.id)

    result = M.update_factory(db, factory_id=f1.id, factory_data=FactoryUpdate(), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is f1
    # Then 2
    row = reread(db, f1)
    assert row.updated_by == u1.id
    # Then 3
    assert row.updated_at is None


def test_fac_u_43__a_factory_of_the_second_workspace_is_renamed_from_its_own_workspace(db, w2, u2, mk_factory):
    """FAC-U-43 — a factory of the second workspace is renamed from its own workspace.
    Rules: `update_factory` R4, R13"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    f9 = mk_factory(name="Far Depot", abbreviation="FD", workspace_id=w2.id)
    before_f1 = snap(db, f1)

    result = M.update_factory(db, factory_id=f9.id, factory_data=FactoryUpdate(name="West Yard"), workspace_id=w2.id, user_id=u2.id)

    # Then 1
    assert result is f9
    # Then 2
    row = reread(db, f9)
    assert row.name == "West Yard"
    assert row.abbreviation == "FD"
    # Then 3
    assert row.workspace_id == w2.id
    assert row.updated_by == u2.id
    # Then 4
    assert snap(db, f1) == before_f1


def test_fac_s_38__a_matching_soft_deleted_factory_is_returned_by_a_search_with_include(db, w1, mk_factory):
    """FAC-S-38 — a matching soft-deleted factory is returned by a search with include_deleted=True.
    Rules: `search_factories` R8, R5 [BUG-901]"""
    f1 = mk_factory(name="Main Plant", abbreviation="MP")
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)
    mk_factory(name="North Yard", abbreviation="NY")

    result = M.search_factories(db, workspace_id=w1.id, search="plant", include_deleted=True)

    # Then 1
    assert sorted(ids(result)) == [f1.id, fd.id]


def test_fac_d_08__an_already_deleted_factory_is_answered_with_400_and_keeps_its(db, w1, u1, u2, mk_factory):
    """FAC-D-08 — an already deleted factory is answered with 400 and keeps its deletion stamp.
    Rules: `delete_factory` R2, Errors row 2"""
    fd = mk_factory(name="Old Plant", abbreviation="OP", deleted=True)
    before_fd = snap(db, fd)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_factory(db, factory_id=fd.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Factory is already deleted"
    # Then 4
    assert snap(db, fd) == before_fd
    # Then 5
    row = reread(db, fd)
    assert row.deleted_at == T0
    # Then 6
    assert row.deleted_by == u1.id
    # Then 7
    assert written(db) == before
```
