# Helpers for `test_machine_section_assignment.py`

## Fixtures (add them as test arguments)
- `db` — the session. `w1`, `w2` — W1, W2. `u1`, `u2` — U1, U2. `f1`, `f2`, `f9` — F1, F2, F9. `s1`, `s2`, `s3`, `sx`, `s9` — S1, S2, S3, SX, S9. `m1`, `m2`, `m3`, `md`, `m9` — M1, M2, M3, MD, M9. These rows already exist in every test: never build them, just request the ones the test names.
- Every fixture a test uses, also one used only in the When call or in an assert (`w1`, `u2`, `m1`, `s1`) — must be in its argument list (also `mk_assignment`).
- ONLY the names above can be arguments. Assignment rows the test builds (`a1`, `a2`, `a3`, `ad`, `a9`, `o1`) are local variables, never arguments. `dao`, `MISSING` and the reading helpers are used directly, never as arguments.
- Never patch or mock anything.

## Builder (keyword arguments only)
- `mk_assignment(of=m1, to=s1)` — "assignment of M1 to S1" (workspace of the machine, created by U1). Each column the card lists after "but" is one more keyword, named like the card's column. Never add a keyword the card's row does not list.

## Card says -> write
| Card says | Write |
|---|---|
| `W1.id`, `U2.id`, `F1.id`, `S3.id`, `SX.id`, `M1.id`, `MD.id`, `M9.id`, A1, AD | `w1.id`, `u2.id`, `f1.id`, `s3.id`, `sx.id`, `m1.id`, `md.id`, `m9.id`, `a1`, `ad` |
| MISSING | the name `MISSING` |
| A1 = assignment of M1 to S1. | `a1 = mk_assignment(of=m1, to=s1)` |
| A1 = assignment of M1 to S1, but `workspace_id W2.id`. | `a1 = mk_assignment(of=m1, to=s1, workspace_id=w2.id)` |
| "No assignment exists." | no code |

Build the Given rows in the order written, one statement per row. Give a row a variable only if the test uses it later. Text in parentheses ( ) is an explanation: no code for it. Copy every text in quotes character for character.

A Given line that is code is run as written, at that place, with lower-case row names: "`a1_id = A1.id`" -> `a1_id = a1.id`. One exception: "`loaded = M1.factory_section_id`" -> `_loaded = m1.factory_section_id` (with the underscore; the line must stay, it loads M1's section into the session). Snapshots (`before…`) come after the last Given line.

## Reading helpers (call them directly)
- `ids(result)` — list of the ids in the order returned.
- `reread(db, row)` — fresh copy of an assignment, machine, section or factory from the database. `snap(db, row)` — all columns of such a row.
- `rows_of(db, m1)` — rows_of(M1): fresh list of the assignment rows of M1.
- `count_rows(db, "machine_section_assignments")` — rows of the table; a filter is a keyword: `count_rows(db, "machine_section_assignments", factory_section_id=s1.id)`.
- `written(db)` — the "nothing written" counts.

## Already imported (never import)
`pytest`, `dao`, `MachineSectionAssignment`, `MachineSectionAssignmentCreate`, `Machine`, `DataError`, `IntegrityError`, `InvalidRowCountInLimitClause`, `InvalidRowCountInResultOffsetClause`, `ForeignKeyViolation`, `UniqueViolation`, `NotNullViolation`.

## How to write each kind of line
- When -> the call exactly as shown, with lower-case names: `result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w1.id, skip=2, limit=2)`, `result = dao.get(db, a9.id)`, `result = dao.create(db, obj_in={"workspace_id": w1.id, "machine_id": m1.id, "factory_section_id": s1.id})`. Keep every argument, also `None`, `0`, `-1`, `MISSING`; add none.
- `returns:` -> `assert` + the expression as written, nothing changed but the lower-case names (keep `sorted(...)`, `set(...)`, `len(...)`, `<=`, `in`, `!=` as the card has them): `assert sorted(ids(result)) == [a1.id, a2.id]`, `assert result == []`, `assert result[0].id in [a1.id, a2.id]`, `assert m1.factory_section_id == s1.id`.
- `raises: DataError` / `raises: IntegrityError` (also "`IntegrityError` on flush") -> as MSA-UP-17 below: `with pytest.raises(...) as exc:`, inside it `with db.begin_nested():`, inside that the call (without `result =`). The other `raises:` lines are asserts on `exc.value` after the `with` block, each under its own `# Then N`, the expression as written. Use `pytest.raises` only for a `raises:` line.
- `nothing written` -> `before = written(db)` before the call, `assert written(db) == before` after. Only when the card has that Then line.
- `unchanged(A2)` -> `before_a2 = snap(db, a2)` BEFORE the When call (after all Given lines), `assert snap(db, a2) == before_a2` after. The same for a standing row: `unchanged(MD)` -> `before_md = snap(db, md)` / `assert snap(db, md) == before_md`. Only when the card has that Then line.
- `re-read A1:` -> `row = reread(db, a1)`, then one `assert` per value. A line with two values needs TWO asserts: "`created_by is None`, `updated_by is None`" -> `assert row.created_by is None` and `assert row.updated_by is None`. Later re-read lines of the same row reuse `row`. "re-read the returned row" -> `row = reread(db, result)`. "re-read MD" -> `row = reread(db, md)`.
- `re-read rows_of(M1)[0]:` -> `row = rows_of(db, m1)[0]`, then one `assert` per value.
- `count: rows_of(M1) has exactly 1 row` -> `assert len(rows_of(db, m1)) == 1`.
- `count: machine_section_assignments has exactly 1 row` -> `assert count_rows(db, "machine_section_assignments") == 1`. "rows with `id == a1_id`: exactly 0" -> `assert count_rows(db, "machine_section_assignments", id=a1_id) == 0`.

## Example tests (copy this style)
```python
def test_msa_gm_06__the_row_s_own_workspace_id_decides_asked_in_the_row_s_workspace(db, w2, m1, s1, mk_assignment):
    """MSA-GM-06 — the row's own workspace_id decides: asked in the row's workspace returns it.
    Rules: `get_by_machine` R1"""
    a1 = mk_assignment(of=m1, to=s1, workspace_id=w2.id)

    result = dao.get_by_machine(db, machine_id=m1.id, workspace_id=w2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    assert result.workspace_id == w2.id


def test_msa_up_01__a_machine_without_an_assignment_gets_one_new_row(db, w1, u2, m1, s1):
    """MSA-UP-01 — a machine without an assignment gets one new row.
    Rules: `upsert_for_machine` R1, Returns"""
    result = dao.upsert_for_machine(db, machine_id=m1.id, factory_section_id=s1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert isinstance(result, MachineSectionAssignment)
    # Then 2
    assert result.id is not None
    # Then 3
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.machine_id == m1.id
    assert row.factory_section_id == s1.id
    # Then 4
    assert row.created_by == u2.id
    # Then 5
    assert row.created_at is not None
    # Then 6
    assert row.updated_at is None
    assert row.updated_by is None
    # Then 7
    assert len(rows_of(db, m1)) == 1
    # Then 8
    assert count_rows(db, "machine_section_assignments") == 1


def test_msa_up_03__re_saving_the_section_the_machine_already_has_leaves_its_row_untouched(db, w1, u1, u2, m1, s1, mk_assignment):
    """MSA-UP-03 — re-saving the section the machine already has leaves its row untouched.
    Rules: `upsert_for_machine` R3 [BUG-909]"""
    a1 = mk_assignment(of=m1, to=s1)
    a1_id = a1.id

    result = dao.upsert_for_machine(db, machine_id=m1.id, factory_section_id=s1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.factory_section_id == s1.id
    # Then 2
    assert len(rows_of(db, m1)) == 1
    # Then 3
    assert result.id == a1_id
    # Then 4
    row = rows_of(db, m1)[0]
    assert row.id == a1_id
    # Then 5
    assert row.created_by == u1.id


def test_msa_up_17__a_factory_section_id_that_is_no_section_fails_on_flush_and_the(db, w1, u1, u2, m1, s1, mk_assignment):
    """MSA-UP-17 — a factory_section_id that is no section fails on flush and the machine's previous row is back.
    Rules: `upsert_for_machine` R8, Errors row 3"""
    a1 = mk_assignment(of=m1, to=s1)
    before_a1 = snap(db, a1)
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.upsert_for_machine(db, machine_id=m1.id, factory_section_id=MISSING, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "machine_section_assignments_factory_section_id_fkey" in str(exc.value.orig)
    # Then 4
    assert snap(db, a1) == before_a1
    # Then 5
    row = reread(db, a1)
    assert row.factory_section_id == s1.id
    assert row.created_by == u1.id
    # Then 6
    assert len(rows_of(db, m1)) == 1
    # Then 7
    assert written(db) == before


def test_msa_cl_01__every_row_of_the_section_is_deleted_and_its_machine_ids_are_returned(db, w1, f1, m1, m2, m3, s1, s2, mk_assignment):
    """MSA-CL-01 — every row of the section is deleted and its machine ids are returned.
    Rules: `clear_for_section` R1, R2, R3, Returns"""
    mk_assignment(of=m1, to=s1)
    mk_assignment(of=m2, to=s1)
    a3 = mk_assignment(of=m3, to=s2)
    before_a3 = snap(db, a3)
    before_s1 = snap(db, s1)
    before_m1 = snap(db, m1)
    before_f1 = snap(db, f1)

    result = dao.clear_for_section(db, factory_section_id=s1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(result) == [m1.id, m2.id]
    # Then 3
    assert len(result) == 2
    # Then 4
    assert count_rows(db, "machine_section_assignments", factory_section_id=s1.id) == 0
    # Then 5
    assert count_rows(db, "machine_section_assignments") == 1
    # Then 6
    assert snap(db, a3) == before_a3
    # Then 7
    assert snap(db, s1) == before_s1
    # Then 8
    assert snap(db, m1) == before_m1
    # Then 9
    assert snap(db, f1) == before_f1


def test_msa_inh_04__update_with_a_dict_sets_the_given_columns_and_updated_at(db, u1, u2, m1, s1, s2, mk_assignment):
    """MSA-INH-04 — update with a dict sets the given columns and updated_at.
    Rules: inherited R2"""
    a1 = mk_assignment(of=m1, to=s1)

    result = dao.update(db, db_obj=a1, obj_in={"factory_section_id": s2.id, "updated_by": u2.id})

    # Then 1
    assert result.id == a1.id
    # Then 2
    row = reread(db, a1)
    assert row.factory_section_id == s2.id
    # Then 3
    assert row.updated_by == u2.id
    # Then 4
    assert row.updated_at is not None
    # Then 5
    assert row.created_by == u1.id
    assert row.machine_id == m1.id
    # Then 6
    assert count_rows(db, "machine_section_assignments") == 1
```
