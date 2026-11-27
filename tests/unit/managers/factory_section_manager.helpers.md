# Helpers for `test_factory_section_manager.py`

## Fixtures (add them as test arguments)
- `db` — the session. `w1`, `w2` — W1, W2. `u1`, `u2` — U1, U2. `f1`, `f2`, `f9`, `fd`, `fi` — factories F1, F2, F9, FD, FI. These rows exist in every test: never build them, just request the ones the test names.
- `mk_section`, `mk_machine`, `mk_assignment` — row builders.
- Every fixture a test uses — builders and standing rows too, also one used only in the When call or in an assert (`w1`, `u1`, `u2`, `f1`, `fd`) — must be in its argument list.
- ONLY these names can be arguments. Rows the test builds (`s1`, `s9`, `sx`, `sh`, `ma1`, `a1`) are local variables. `M`, the constants and the reading helpers are used directly.
- The clock is already patched to NOW. Never patch or mock anything.

## Builders (keyword arguments only)
- `mk_section(name=..., **columns)` — one "section" with the Conventions defaults. Each thing the card lists after "but" is one more keyword, named like the card's column; "deleted" is `deleted=True` (it sets the three "deleted" columns itself). "but `factory_id F9.id`, `workspace_id W2.id`" -> `factory_id=f9.id, workspace_id=w2.id`.
- `mk_machine(of=f1, name="Lathe")` — "machine of F1, `name "Lathe"`" ("but `is_deleted True`" -> add `is_deleted=True`). `mk_assignment(of=ma1, to=s1)` — "assignment of MA1 to S1".
- Never add a keyword the card's row does not list. A section without "but" is only `mk_section(name="...")`.

## Card says -> write
| Card says | Write |
|---|---|
| `W2.id`, `U1.id`, `F9.id`, `FD.id`, `SX9.id`, MA1, A1 | `w2.id`, `u1.id`, `f9.id`, `fd.id`, `sx9.id`, `ma1`, `a1` (lower case) |
| M, MISSING, NOW, T0 | the names `M`, `MISSING`, `NOW`, `T0` |
| S1 = section, `name "Paint"`. | `s1 = mk_section(name="Paint")` |
| section, `name "Old Line"`, but deleted | `mk_section(name="Old Line", deleted=True)` |
| section, `name "Paint"`, but `factory_id FD.id` | `mk_section(name="Paint", factory_id=fd.id)` |
| "No sections exist." | no code |

Build the Given rows in the order written, one statement per row. Give a row a variable only if the test uses it later. Text in parentheses ( ) and a sentence after the When call are explanations: no code. Copy every quoted text character for character, as a plain string: `"   "` is three spaces, `" Spray "` keeps both spaces, `"\t"`, `"Paint\n"` as written.

A Given line that is code is run as written, at that place, with lower-case names: "`db.refresh(S1)`" -> `db.refresh(s1)`; "`created_before = S1.created_at`" -> `created_before = s1.created_at`. Snapshots (`before…`) come after it.

## Reading helpers (call them directly)
- `ids(result)`, `names(result)` — ids / names in the order returned.
- `reread(db, row)` — fresh copy of a section, factory, machine or assignment. `snap(db, row)` — all its columns.
- `count_rows(db, "factory_sections")` — rows of the named table. `rows_of_section(db, s1)` — list of S1's assignment rows.
- `written(db)` — the "nothing written" counts.
- Statement recorder (`Author: claude` cards only): `with recorded_sql(db) as statements:` around the When call; `section_selects(statements)` — the recorded SELECTs on `factory_sections` (lower-case, one space); `where_clause(s)` — the text of its WHERE clause.

## Already imported (never import)
`pytest`, `HTTPException`, `ValidationError`, `IntegrityError`, `DataError`, `ForeignKeyViolation`, `InvalidRowCountInLimitClause`, `InvalidRowCountInResultOffsetClause`, `FactorySection`, `FactorySectionCreate`, `FactorySectionUpdate`.

## How to write each kind of line
- When -> the call exactly as shown, lower-case names; keep every argument (also `None`, `0`, `-1`, `""`), add none; positional stays positional: `result = M.get_factory_section(db, s1.id, w1.id)`.
- `include_deleted=True` on `M.get_factory_section(...)`: write the call exactly as shown; never wrap it in `pytest.raises`. Use `pytest.raises` only when a Then line starts with `raises:`.
- target `schema` -> the When is only `result = FactorySectionUpdate(name="a")`; `M` is not called.
- `returns:` -> `assert` + the expression as written, only the names lower-cased (keep `sorted`, `set`, `<=`, `len`): `assert result is s1`, `assert result is True`, `assert result == []`. "read on the object: `MA1.factory_section_id == S1.id`" -> `assert ma1.factory_section_id == s1.id`, no reread.
- `raises: HTTPException` -> as FSM-D-06; `raises: ValidationError` -> as FSM-C-18. Further `raises:` lines are asserts on `exc.value` after the `with` block, each under its own `# Then N`; an f-string stays one: `assert exc.value.detail == f"Factory with ID {f9.id} not found"`.
- `raises: IntegrityError` / `DataError` -> the call inside `db.begin_nested()`, without `result =`:
  ```python
  # Then 1
  with pytest.raises(IntegrityError) as exc:
      with db.begin_nested():
          M.delete_factory_section(db, section_id=s1.id, workspace_id=w1.id, user_id=MISSING)
  # Then 2
  assert isinstance(exc.value.orig, ForeignKeyViolation)
  ```
- `nothing written` -> `before = written(db)` before the call, `assert written(db) == before` after. Only when the card has that line.
- `unchanged(S2)` -> `before_s2 = snap(db, s2)` BEFORE the When call, `assert snap(db, s2) == before_s2` after; also for a factory: `before_f1 = snap(db, f1)`. Only when the card has that line.
- `re-read S1:` -> `row = reread(db, s1)`, then one `assert` per value (two values, two asserts). Later `re-read S1:` lines reuse `row`; another row (S2, A1) needs its own `reread`. "the returned row" -> `reread(db, result)`.
- `count:` -> `assert count_rows(db, "factory_sections") == 2`, the card's table and number. "rows_of_section(S1) has exactly 1 row" -> `assert len(rows_of_section(db, s1)) == 1`.

## Example tests (copy this style)
```python
def test_fsm_c_01__create_stores_a_section_with_the_name_factory_workspace_and_creator(db, w1, u2, f1):
    """FSM-C-01 — create stores a section with the name, factory, workspace and creator given.
    Rules: `create_factory_section` R1, Returns, Side effects"""
    result = M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=f1.id), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert isinstance(result, FactorySection)
    # Then 2
    assert result.id is not None
    # Then 3
    row = reread(db, result)
    assert row.name == "Paint"
    assert row.factory_id == f1.id
    # Then 4
    assert row.workspace_id == w1.id
    # Then 5
    assert row.created_by == u2.id
    # Then 6
    assert count_rows(db, "factory_sections") == 1


def test_fsm_c_18__an_empty_name_is_rejected_by_factorysectioncreate(db, f1):
    """FSM-C-18 — an empty name is rejected by FactorySectionCreate.
    Rules: `create_factory_section` R8 [BUG-915], Errors row 4"""
    # Then 1
    with pytest.raises(ValidationError):
        FactorySectionCreate(name="", factory_id=f1.id)

    # Then 2
    assert count_rows(db, "factory_sections") == 0


def test_fsm_u_46__an_empty_request_keeps_the_previous_updated_by(db, w1, u1, u2, mk_section):
    """FSM-U-46 — an empty request keeps the previous updated_by.
    Rules: `update_factory_section` R13 [BUG-919]"""
    s1 = mk_section(name="Paint", updated_by=u1.id)
    db.refresh(s1)

    result = M.update_factory_section(db, section_id=s1.id, section_data=FactorySectionUpdate(), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.updated_by == u1.id
    # Then 3
    assert row.updated_at is None


def test_fsm_g_06__a_section_of_the_second_workspace_is_returned_to_its_own_workspace(db, w2, f9, mk_section):
    """FSM-G-06 — a section of the second workspace is returned to its own workspace.
    Rules: `get_factory_section` R1"""
    s9 = mk_section(name="Packing", factory_id=f9.id, workspace_id=w2.id)

    result = M.get_factory_section(db, section_id=s9.id, workspace_id=w2.id)

    # Then 1
    assert result.id == s9.id
    # Then 2
    assert result.workspace_id == w2.id


def test_fsm_s_45__limit_1_of_two_sections_returns_one_of_them(db, w1, f1, mk_section):
    """FSM-S-45 — limit 1 of two sections returns one of them.
    Rules: `search_factory_sections` R11"""
    s1 = mk_section(name="Paint")
    s2 = mk_section(name="Welding")

    result = M.search_factory_sections(db, workspace_id=w1.id, factory_id=f1.id, limit=1)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert set(ids(result)) <= {s1.id, s2.id}


def test_fsm_d_06__an_already_deleted_section_is_answered_with_400_and_keeps_its(db, w1, u1, u2, mk_section):
    """FSM-D-06 — an already deleted section is answered with 400 and keeps its deletion stamp.
    Rules: `delete_factory_section` R2, Errors row 2"""
    sx = mk_section(name="Old Line", deleted=True)
    before_sx = snap(db, sx)
    before = written(db)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        M.delete_factory_section(db, section_id=sx.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Factory section is already deleted"
    # Then 4
    assert snap(db, sx) == before_sx
    # Then 5
    row = reread(db, sx)
    assert row.deleted_at == T0
    # Then 6
    assert row.deleted_by == u1.id
    # Then 7
    assert written(db) == before


def test_fsm_d_08__a_section_with_assigned_machines_is_deleted_machines_factory_and_the(db, w1, u2, f1, mk_section, mk_machine, mk_assignment):
    """FSM-D-08 — a section with assigned machines is deleted; machines, factory and the other section are untouched.
    Rules: `delete_factory_section` R5 (the side that holds today), R6, Side effects"""
    s1 = mk_section(name="Paint")
    s2 = mk_section(name="Welding")
    ma1 = mk_machine(of=f1, name="Lathe")
    ma2 = mk_machine(of=f1, name="Press")
    mk_assignment(of=ma1, to=s1)
    a3 = mk_assignment(of=ma2, to=s2)
    before_ma1 = snap(db, ma1)
    before_ma2 = snap(db, ma2)
    before_f1 = snap(db, f1)
    before_s2 = snap(db, s2)
    before_a3 = snap(db, a3)

    result = M.delete_factory_section(db, section_id=s1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is s1
    # Then 2
    row = reread(db, s1)
    assert row.is_deleted is True
    assert row.deleted_by == u2.id
    # Then 3
    assert snap(db, ma1) == before_ma1
    # Then 4
    assert snap(db, ma2) == before_ma2
    # Then 5
    assert snap(db, f1) == before_f1
    # Then 6
    assert snap(db, s2) == before_s2
    # Then 7
    assert snap(db, a3) == before_a3
    # Then 8
    assert count_rows(db, "machines") == 2
```
