# Helpers for `test_machine.py`

## Fixtures (add them as test arguments)
- `db` — the session.
- `w1`, `w2` — W1, W2. `u1`, `u2` — U1, U2. `f1`, `f2`, `f9`, `fd`, `fi` — F1, F2, F9, FD, FI. `s1`, `s2`, `s3`, `sx`, `si`, `s9` — S1, S2, S3, SX, SI, S9. These rows already exist in every test: never build them, just request the ones the test names.
- `mk_machine`, `mk_assignment`, `mk_event` — row builders.
- Every fixture a test uses — builders and actors too, also one used only in the When call or in an assert (`f1`, `w1`, `u1`) — must be in its argument list.
- ONLY the names above can be arguments. Rows the test builds itself (`m1`, `md`, `m9`, `a1`, `ad`) are local variables, never arguments. `dao`, the constants and the reading helpers are used directly, never as arguments.
- The clock is already patched to NOW. Never patch or mock anything.

## Builders (keyword arguments only)
- `mk_machine(name=..., **columns)` — one "machine" with the Conventions defaults. The keywords are the card's column names. The word "deleted" is the keyword `deleted=True` (it sets the four "deleted" columns itself).
- `mk_assignment(of=m1, to=s1)` — "assignment of M1 to S1". Only these two keywords; it calls `db.expire_all()` itself.
- `mk_event(of=m1, created_at=T1, metadata_json={"status": "RUNNING"})` — "event of M1, `created_at T1`, `metadata_json {"status": "RUNNING"}`". `metadata_json None` -> `metadata_json=None`. Values after "but" are more keywords: `mk_event(of=m1, created_at=T2, metadata_json={"status": "OFF"}, event_type="updated")`.
- A default with values replaced = one keyword for each value the card lists after "but", each keyword once: `mk_machine(name="Bravo", factory_id=f2.id, is_running=True)`. Never add a keyword the card's row does not list — a value of the When call or of another row is not a value of this row.

## Card says -> write
| Card says | Write |
|---|---|
| `W1.id`, `U2.id`, `F2.id`, `FD.id`, `FI.id`, `S1.id`, `SX.id`, `SI.id`, `M1.id`, `MD.id`, `M9.id` | `w1.id`, `u2.id`, `f2.id`, `fd.id`, `fi.id`, `s1.id`, `sx.id`, `si.id`, `m1.id`, `md.id`, `m9.id` |
| MISSING, NOW, T0 … T3, IDLE, RUNNING, OFF, MAINTENANCE | constants with these names |
| M1 = machine, `name "Lathe"`. | `m1 = mk_machine(name="Lathe")` |
| machine, `name "Press"`, but deleted | `mk_machine(name="Press", deleted=True)` |
| machine, `name "Drill"`, but `factory_id FD.id` | `mk_machine(name="Drill", factory_id=fd.id)` |
| machine, `name "Press"`, but `created_at T2` | `mk_machine(name="Press", created_at=T2)` |
| "No machines exist." | no code |

Build the Given rows in the order written, one statement per row. Give a row a variable only if the test uses it later. Text in parentheses ( ) after a Given row and a sentence after the When call are explanations: no code for them. Copy every text in quotes character for character (`"   "` is three spaces, `"a\\b"` keeps both backslashes, `" \t\n"` as written).

## Reading helpers (call them directly)
- `ids(result)`, `names(result)` — lists of the ids / names in the order returned.
- `by_id(result, m1)` — the element of `result` with M1's id.
- `reread(db, row)` — fresh copy of a machine or assignment from the database.
- `snap(db, row)` — all columns of a row.
- `count_rows(db, "machines")` — rows of the table the card names.
- `written(db)` — the "nothing written" counts.

## Already imported (never import)
`pytest`, `datetime`, `dao`, `Machine`, `MachineCreate`, `MachineUpdate`, `DataError`, `IntegrityError`, `InvalidRowCountInLimitClause`, `InvalidRowCountInResultOffsetClause`, `ForeignKeyViolation`.

## How to write each kind of Then line
- When -> the call exactly as shown, with lower-case names: `result = dao.search_advanced(db, workspace_id=w1.id, factory_id=fd.id, sort_dir="desc", limit=1)`. Keep every argument, also `None`, `0`, `-1` and `""`; add none. `restore` the same: `result = dao.restore(db, db_obj=md)`.
- `latest_event_type=...` calls: write the call exactly as shown; never wrap it in `pytest.raises`. Use `pytest.raises` only when a Then line starts with `raises:`.
- `returns:` -> `assert` + the expression as written, nothing changed but the lower-case names: `assert ids(result) == [m2.id, m3.id, m1.id]` (keep the card's order), `assert sorted(ids(result)) == [m1.id, m2.id]`, `assert names(result) == ["Lathe"]`, `assert result == []`, `assert result is m1`, `assert by_id(result, m2).factory_section_name is None`. "after the call, `X`" -> `assert X`.
- `raises: DataError` / `raises: IntegrityError` -> as MCH-GF-24 below (with `db.begin_nested()` and `as exc`). `raises: AttributeError` -> as MCH-INH-13 below (no `begin_nested`). The other `raises:` lines are asserts on `exc.value` after the `with` block, each under its own `# Then N`.
- `nothing written` -> `before = written(db)` before the call, `assert written(db) == before` after. Only when the card has that Then line.
- `unchanged(M1)` -> `before_m1 = snap(db, m1)` BEFORE the When call (after the Given rows), `assert snap(db, m1) == before_m1` after. Only when the card has that Then line.
- `re-read M1:` -> `row = reread(db, m1)`, then one `assert` per value; a line with two values gets an assert for each. Later `re-read M1:` lines reuse `row`; for another row (A1, MD) call `reread` again. "re-read the returned row" -> `row = reread(db, result)`. E.g. `assert row.created_by == u1.id`.
- `count:` -> `assert count_rows(db, "machine_section_assignments") == 2` — the card's table name and number.

## Example tests (copy this style)
```python
def test_mch_gs_05__the_workspace_filter_follows_the_machine_not_the_section(db, w2, f9, s1, mk_machine, mk_assignment):
    """MCH-GS-05 — the workspace filter follows the machine, not the section.
    Rules: `get_by_section` R2"""
    m1 = mk_machine(name="Lathe")
    mk_assignment(of=m1, to=s1)
    m9 = mk_machine(name="Other", workspace_id=w2.id, factory_id=f9.id)
    mk_assignment(of=m9, to=s1)

    result = dao.get_by_section(db, factory_section_id=s1.id, workspace_id=w2.id)

    # Then 1
    assert ids(result) == [m9.id]


def test_mch_sd_01__a_live_machine_is_marked_deleted_with_the_clock_value_and_the_acting(db, u2, mk_machine):
    """MCH-SD-01 — a live machine is marked deleted with the clock value and the acting user.
    Rules: `soft_delete` R1, R5"""
    m1 = mk_machine(name="Press 4")

    result = dao.soft_delete(db, db_obj=m1, deleted_by=u2.id)

    # Then 1
    assert result is m1
    # Then 2
    row = reread(db, m1)
    assert row.is_deleted is True
    assert row.is_active is False
    # Then 3
    assert row.deleted_at == NOW
    # Then 4
    assert row.deleted_by == u2.id
    # Then 5
    assert count_rows(db, "machines") == 1


def test_mch_gf_24__negative_limit_is_rejected_by_the_database_and_nothing_changes(db, w1, f1, mk_machine):
    """MCH-GF-24 — negative limit is rejected by the database and nothing changes.
    Rules: `get_by_factory` R5, Errors row 1"""
    m1 = mk_machine(name="Lathe")
    before = written(db)
    before_m1 = snap(db, m1)

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
    assert snap(db, m1) == before_m1


def test_mch_inh_13__a_refused_update_leaves_an_existing_assignment_pointing_at_its_old(db, s1, s2, mk_machine, mk_assignment):
    """MCH-INH-13 — a refused update leaves an existing assignment pointing at its old section.
    Rules: inherited R4"""
    m1 = mk_machine(name="Press")
    a1 = mk_assignment(of=m1, to=s1)
    before_a1 = snap(db, a1)
    before_m1 = snap(db, m1)

    # Then 1
    with pytest.raises(AttributeError):
        dao.update(db, db_obj=m1, obj_in={"factory_section_id": s2.id})

    # Then 2
    assert snap(db, a1) == before_a1
    # Then 3
    row = reread(db, a1)
    assert row.machine_id == m1.id
    assert row.factory_section_id == s1.id
    # Then 4
    assert snap(db, m1) == before_m1
    # Then 5
    assert count_rows(db, "machine_section_assignments") == 1


def test_mch_sa_72__the_newest_status_change_decides_the_machine_matches_its_newest_status(db, w1, mk_machine, mk_event):
    """MCH-SA-72 — the newest status change decides: the machine matches its newest status.
    Rules: `search_advanced` R12a [BUG-886]"""
    m1 = mk_machine(name="Alpha")
    mk_event(of=m1, created_at=T1, metadata_json={"status": "RUNNING"})
    mk_event(of=m1, created_at=T2, metadata_json={"status": "IDLE"})
    m2 = mk_machine(name="Bravo")
    mk_event(of=m2, created_at=T1, metadata_json={"status": "RUNNING"})

    result = dao.search_advanced(db, workspace_id=w1.id, latest_event_type=IDLE)

    # Then 1
    assert ids(result) == [m1.id]
```
