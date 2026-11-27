# Helpers for `test_machine_section_assignment_manager.py`

## Fixtures (add them as test arguments)
- `db` — the session. `w1`, `w2` — W1, W2. `u1`, `u2` — U1, U2. Standing rows: `f1`, `f2`, `f9`, `fd` — F1, F2, F9, FD. `s1`, `s2`, `s3`, `sx`, `s9`, `sf` — S1, S2, S3, SX, S9, SF. `m1`, `m2`, `m3`, `md`, `m9`, `mf` — M1, M2, M3, MD, M9, MF. They exist in every test: never build them; request the ones the test names.
- Builders: `mk_assignment`, `mk_factory`, `mk_section`, `mk_machine`.
- Every fixture a test uses — builders and actors too, also one used only in the When call or in an assert (`w1`, `u2`, `f1`, `m1`, `mk_section`) — must be in its argument list.
- ONLY the names above can be arguments. Rows the test builds (`a1`, `a2`, `af`, `fq`, `sq`, `mq`, `si`, `mn`) are local variables, never arguments. `mgr`, `MISSING` and the reading helpers are used directly, never as arguments.
- Never patch or mock anything.

## Builders (keyword arguments only)
- `mk_assignment(of=m1, to=s1)` — "assignment of M1 to S1". Each column the card lists after "but" is one more keyword.
- `mk_factory(name="Quiet Works", abbreviation="QW")` — "extra factory". `mk_section(of=f1, name="Spare Bay")` — "section of F1". `mk_machine(of=f1, name="Belt Sander")` — "machine of F1".
- Never add a keyword the card's row does not list.

## Card says -> write
| Card says | Write |
|---|---|
| `W1.id`, `U2.id`, `F9.id`, `FD.id`, `SX.id`, `SF.id`, `MF.id`, A1, AF | `w1.id`, `u2.id`, `f9.id`, `fd.id`, `sx.id`, `sf.id`, `mf.id`, `a1`, `af` |
| mgr, MISSING | the names `mgr`, `MISSING` |
| A1 = assignment of M1 to S1. | `a1 = mk_assignment(of=m1, to=s1)` |
| A1 = assignment of M1 to S1, but `workspace_id W2.id`. | `a1 = mk_assignment(of=m1, to=s1, workspace_id=w2.id)` |
| FQ = extra factory, `name "Quiet Works"`, `abbreviation "QW"`, but `is_active False`. | `fq = mk_factory(name="Quiet Works", abbreviation="QW", is_active=False)` |
| SG = section of FD, `name "Dry Store"`. | `sg = mk_section(of=fd, name="Dry Store")` |
| SI = section of F1, `name "Spare Bay"`, but `is_active False`. | `si = mk_section(of=f1, name="Spare Bay", is_active=False)` |
| MQ = machine of FQ, `name "Planer"`. | `mq = mk_machine(of=fq, name="Planer")` |
| "No assignment exists." | no code |

Build the Given rows in the order written, one statement per row. Give a row a variable only if the test uses it later. Text in parentheses ( ) is an explanation: no code for it. Copy every text in quotes character for character.

A Given line that is code is run exactly as written, at that place, with lower-case row names: "`a1_id = A1.id`" -> `a1_id = a1.id`; "`loaded = M1.factory_section_id`" -> `loaded = m1.factory_section_id` (keep it: it loads M1's section into the session); "`MN.name = "Edge Trimmer"`" -> `mn.name = "Edge Trimmer"`; "`db.expunge_all()`" -> `db.expunge_all()`. Snapshots (`before…`) come after the last Given line.

## Reading helpers (call them directly)
- `reread(db, row)` — fresh copy of a row. `snap(db, row)` — all columns of a row.
- `rows_of(db, m1)` — rows_of(M1): fresh list of the assignment rows of M1.
- `count_rows(db, "machine_section_assignments")` — rows of the table; a filter is a keyword: `count_rows(db, "machine_section_assignments", id=a1_id)`.
- `written(db)` — the "nothing written" counts.

## Already imported (never import)
`pytest`, `mgr`, `HTTPException`, `IntegrityError`, `ForeignKeyViolation`, `UniqueViolation`, `MachineSectionAssignment`, `Machine`.

## How to write each kind of line
- When -> the call exactly as shown, lower-case names: `result = mgr.set_assignment(db, machine_id=m1.id, factory_id=MISSING, factory_section_id=None, workspace_id=w1.id, user_id=MISSING)`, `result = mgr.clear_for_section(db, factory_section_id=s1.id, workspace_id=w1.id)`. Keep every argument, also `None`, `0`, `-1`, `MISSING`; add none. A When without `result =` stays without it.
- `returns:` -> `assert` + the expression as written, nothing changed but the lower-case names: `assert result is None`, `assert result == [m1.id]`, `assert sorted(result) == [m1.id, m2.id]`, `assert m1.factory_section_id == s1.id` (on the same object; no re-read before it).
- `raises: HTTPException` -> as MSM-SET-13 below: no `begin_nested`. `raises: IntegrityError` on flush -> as MSM-SET-29 below: the call inside `with db.begin_nested():`. The other `raises:` lines are asserts on `exc.value` after the `with` block, each under its own `# Then N`, the expression as written (`isinstance(exc.value.orig, ForeignKeyViolation)`). Use `pytest.raises` only for a `raises:` line.
- `nothing written` -> `before = written(db)` before the call, `assert written(db) == before` after. Only when the card has that Then line.
- `unchanged(A2)` -> `before_a2 = snap(db, a2)` BEFORE the When call, `assert snap(db, a2) == before_a2` after. The same for a standing row: `unchanged(S1)` -> `before_s1 = snap(db, s1)` / `assert snap(db, s1) == before_s1`. Only when the card has that Then line.
- `re-read A1:` -> `row = reread(db, a1)`, then one `assert` per value: a line with two values needs TWO asserts. Later re-read lines of the same row reuse `row`. "re-read the returned row" -> `row = reread(db, result)`.
- `re-read rows_of(M1)[0]:` -> `row = rows_of(db, m1)[0]`, then one `assert` per value.
- `count: rows_of(M1) has exactly 1 row` -> `assert len(rows_of(db, m1)) == 1`. `count: machine_section_assignments has exactly 1 row` -> `assert count_rows(db, "machine_section_assignments") == 1`.

## Example tests (copy this style)
```python
def test_msm_set_01__a_machine_without_a_section_is_put_into_a_live_section_of_its_factory(db, w1, u2, f1, m1, s1):
    """MSM-SET-01 — a machine without a section is put into a live section of its factory.
    Rules: `set_assignment` R1, Returns"""
    result = mgr.set_assignment(db, machine_id=m1.id, factory_id=f1.id, factory_section_id=s1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert isinstance(result, MachineSectionAssignment)
    # Then 2
    assert result.id is not None
    # Then 3
    row = reread(db, result)
    assert row.machine_id == m1.id
    assert row.factory_section_id == s1.id
    assert row.workspace_id == w1.id
    # Then 4
    assert row.created_by == u2.id
    # Then 5
    assert row.updated_at is None
    assert row.updated_by is None
    # Then 6
    assert len(rows_of(db, m1)) == 1
    # Then 7
    assert count_rows(db, "machine_section_assignments") == 1


def test_msm_set_08__re_saving_the_section_the_machine_already_has_leaves_its_link(db, w1, u1, u2, f1, m1, s1, mk_assignment):
    """MSM-SET-08 — re-saving the section the machine already has leaves its link untouched.
    Rules: `set_assignment` R4 [BUG-909]"""
    a1 = mk_assignment(of=m1, to=s1)
    a1_id = a1.id

    result = mgr.set_assignment(db, machine_id=m1.id, factory_id=f1.id, factory_section_id=s1.id, workspace_id=w1.id, user_id=u2.id)

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


def test_msm_set_13__a_section_of_another_workspace_is_answered_with_the_same_404(db, w1, u2, f9, m1, s1, s9, mk_assignment):
    """MSM-SET-13 — a section of another workspace is answered with the same 404.
    Rules: `set_assignment` R6, Errors row 1"""
    a1 = mk_assignment(of=m1, to=s1)
    before = written(db)
    before_a1 = snap(db, a1)
    before_s9 = snap(db, s9)

    # Then 1
    with pytest.raises(HTTPException) as exc:
        mgr.set_assignment(db, machine_id=m1.id, factory_id=f9.id, factory_section_id=s9.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Factory section with ID {s9.id} not found"
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, a1) == before_a1
    # Then 6
    assert snap(db, s9) == before_s9


def test_msm_set_29__a_machine_whose_link_has_another_workspace_id_hits_the_one_link_per(db, w1, w2, u2, f1, m1, s1, s2, mk_assignment):
    """MSM-SET-29 — a machine whose link has another workspace_id hits the one-link-per-machine constraint and nothing changes.
    Rules: `set_assignment` R11, Errors row 7"""
    a1 = mk_assignment(of=m1, to=s1, workspace_id=w2.id)
    before_a1 = snap(db, a1)
    before = written(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            mgr.set_assignment(db, machine_id=m1.id, factory_id=f1.id, factory_section_id=s2.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert isinstance(exc.value.orig, UniqueViolation)
    # Then 3
    assert "uq_machine_section_assignment_machine" in str(exc.value.orig)
    # Then 4
    assert snap(db, a1) == before_a1
    # Then 5
    row = reread(db, a1)
    assert row.workspace_id == w2.id
    assert row.factory_section_id == s1.id
    # Then 6
    assert len(rows_of(db, m1)) == 1
    # Then 7
    assert written(db) == before


def test_msm_clr_01__every_link_of_the_section_is_deleted_and_its_machine_ids_are_returned(db, w1, f1, m1, m2, m3, s1, s2, mk_assignment):
    """MSM-CLR-01 — every link of the section is deleted and its machine ids are returned; section, machines and factory are not written.
    Rules: `clear_for_section` R1, R4, Returns"""
    mk_assignment(of=m1, to=s1)
    mk_assignment(of=m2, to=s1)
    a3 = mk_assignment(of=m3, to=s2)
    before_a3 = snap(db, a3)
    before_s1 = snap(db, s1)
    before_m1 = snap(db, m1)
    before_m2 = snap(db, m2)
    before_f1 = snap(db, f1)

    result = mgr.clear_for_section(db, factory_section_id=s1.id, workspace_id=w1.id)

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
    assert snap(db, m2) == before_m2
    # Then 10
    assert snap(db, f1) == before_f1
```
