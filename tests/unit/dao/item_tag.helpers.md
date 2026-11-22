# Helpers for `test_item_tag.py`

## Fixtures (add them as test arguments)
- `db` — the session. `w1`, `w2` — W1, W2. They already exist in every test: never build them, just request the ones the test names.
- `mk_tag`, `mk_system_tag` — row builders.
- Every fixture a test uses — builders too, also one used only in the When call or in an assert (`w1`, `w2`) — must be in its argument list. A `dao.create` dict with `"workspace_id": w1.id` needs `w1` (ITG-INH-05 has no `w1` only because it uses `MISSING`).
- ONLY these names can be arguments. Tag rows the test builds (`t1`, `t2`, `t9`, `td`, `s1`, `s2`, `s9`, `sd`) are local variables, never arguments. `dao`, `MISSING` and the reading helpers are used directly, never as arguments.
- Never patch or mock anything.

## Builders (keyword arguments only)
- `mk_tag(name="...", tag_code="...")` — a "tag" (W1, active, usage_count 0). `mk_system_tag(name="...", tag_code="...")` — a "system tag". Never pass `is_system_tag`.
- Each column the card lists after "but" is one more keyword, named like the card's column: "but `workspace_id W2.id`, `usage_count 5`" -> `workspace_id=w2.id, usage_count=5`. Never add a keyword the card's row does not list.

## Card says -> write
| Card says | Write |
|---|---|
| `W1.id`, `W2.id`, T1, T9, TD, S1, SD | `w1.id`, `w2.id`, `t1`, `t9`, `td`, `s1`, `sd` |
| MISSING | the name `MISSING` |
| T1 = tag, `name "Hex Bolt"`, `tag_code "hex_bolt"`. | `t1 = mk_tag(name="Hex Bolt", tag_code="hex_bolt")` |
| S1 = system tag, `name "Raw Material"`, `tag_code "raw_material"`. | `s1 = mk_system_tag(name="Raw Material", tag_code="raw_material")` |
| tag, ..., but `is_active False` | `mk_tag(name="...", tag_code="...", is_active=False)` |
| tag, ..., but `usage_count 2` | `mk_tag(name="...", tag_code="...", usage_count=2)` |
| "No tag exists." | no code |

Build the Given rows in the order written, one statement per row. Give a row a variable only if the test uses it later. Text in parentheses ( ) is an explanation: no code for it. Copy every text in quotes character for character.

A Given line that is code is run as written, at that place, with lower-case row names: "`T1.name = "Lock Nut"` (pending: not flushed)" -> `t1.name = "Lock Nut"` (no flush), "`t1_id = T1.id`" -> `t1_id = t1.id`. Snapshots (`before…`) come after the last Given line.

## Reading helpers (call them directly)
- `ids(result)`, `names(result)` — lists of the ids / names in the order returned.
- `reread(db, row)` — fresh copy of a tag from the database. `snap(db, row)` — all columns of a tag.
- `stored_count(db, t1)` — stored_count(T1).
- `count_rows(db, "item_tags")` — rows of the table; a filter is a keyword: `count_rows(db, "item_tags", tag_code="spare_part")`.
- `written(db)` — the "nothing written" count.
- `close_to_now(value)` — True when the value is close to now.

## Already imported (never import)
`pytest`, `dao`, `ItemTag`, `ItemTagCreate`, `ItemTagUpdate`, `DataError`, `IntegrityError`, `NotNullViolation`, `ForeignKeyViolation`, `StringDataRightTruncation`.

## How to write each kind of line
- When -> the call exactly as shown, with lower-case row names: `result = dao.get_by_code_in_workspace(db, workspace_id=w1.id, tag_code="raw_material")`, `result = dao.get(db, td.id)`, `result = dao.update(db, db_obj=t1, obj_in={"color": None})`. Keep every argument, also `None`, `""`, `MISSING`; add none.
- `returns:` -> `assert` + the expression as written, nothing changed but the lower-case names (keep `is`, `in`, `sorted(...)`, `len(...)`, `isinstance(...)` as the card has them): `assert result is t1`, `assert result is None`, `assert result == []`, `assert sorted(ids(result)) == [t1.id, s1.id]`, `assert stored_count(db, t9) == 5`.
- `raises: DataError` / `raises: IntegrityError` (also "`IntegrityError` on flush") -> as ITG-INH-05 below: `with pytest.raises(...) as exc:`, inside it `with db.begin_nested():`, inside that the call (without `result =`). The `raises: DataError` / `raises: IntegrityError` line is Then 1: write `# Then 1` on the line directly above `with pytest.raises(...)`. The other `raises:` lines are asserts on `exc.value` after the `with` block, each under its own `# Then N` (the first of them is `# Then 2`), the expression as written. Use `pytest.raises` only for a `raises:` line.
- `nothing written` -> `before = written(db)` before the call, `assert written(db) == before` after (never `== 0`). Only when the card has that Then line.
- `unchanged(T2)` -> `before_t2 = snap(db, t2)` BEFORE the When call (after all Given lines), `assert snap(db, t2) == before_t2` after. Only when the card has that Then line.
- `re-read T1:` -> `row = reread(db, t1)`, then one `assert` per value. A line with three values needs THREE asserts: "`name == "Hex Bolt"`, `tag_code == "hex_bolt"`, `workspace_id == W1.id`" -> `assert row.name == "Hex Bolt"`, `assert row.tag_code == "hex_bolt"`, `assert row.workspace_id == w1.id`. Later re-read lines of the same row reuse `row`. "re-read the returned row" -> `row = reread(db, result)`.
- `count: item_tags has exactly 1 row` -> `assert count_rows(db, "item_tags") == 1`. "rows with `id == t1_id`: exactly 0" -> `assert count_rows(db, "item_tags", id=t1_id) == 0`.

## Example tests (copy this style)
```python
def test_itg_code_03__the_same_code_in_two_workspaces_each_workspace_gets_its_own_tag(db, w2, mk_tag):
    """ITG-CODE-03 — the same code in two workspaces: each workspace gets its own tag.
    Rules: `get_by_code_in_workspace` R1"""
    mk_tag(name="Raw Material", tag_code="raw_material")
    t9 = mk_tag(name="Raw Stock", tag_code="raw_material", workspace_id=w2.id)

    result = dao.get_by_code_in_workspace(db, workspace_id=w2.id, tag_code="raw_material")

    # Then 1
    assert result.id == t9.id
    # Then 2
    assert result.workspace_id == w2.id


def test_itg_act_01__returns_a_list_of_the_system_and_user_tags_of_the_workspace_and(db, w1, mk_tag, mk_system_tag):
    """ITG-ACT-01 — returns a list of the system and user tags of the workspace and writes nothing.
    Rules: `get_active_tags_in_workspace` R1, R5, Returns"""
    t1 = mk_tag(name="Custom Bin", tag_code="custom_bin")
    t2 = mk_tag(name="Spare Part", tag_code="spare_part")
    s1 = mk_system_tag(name="Raw Material", tag_code="raw_material")
    before = written(db)
    before_t1 = snap(db, t1)

    result = dao.get_active_tags_in_workspace(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert sorted(ids(result)) == [t1.id, t2.id, s1.id]
    # Then 3
    assert isinstance(result[0], ItemTag)
    # Then 4
    assert written(db) == before
    # Then 5
    assert snap(db, t1) == before_t1


def test_itg_inc_01__the_counter_goes_up_by_one_flushed_and_the_session_s_tag_object_is(db, w1, mk_tag):
    """ITG-INC-01 — the counter goes up by one, flushed, and the session's tag object is returned.
    Rules: `increment_usage_count` R1, R6, Returns"""
    t1 = mk_tag(name="Hex Bolt", tag_code="hex_bolt", usage_count=2)
    before = written(db)

    result = dao.increment_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is t1
    # Then 2
    assert result.usage_count == 3
    # Then 3
    assert stored_count(db, t1) == 3
    # Then 4
    assert written(db) == before


def test_itg_dec_04__at_0_nothing_is_flushed_another_pending_change_stays_unsaved(db, w1, mk_tag):
    """ITG-DEC-04 — at 0 nothing is flushed: another pending change stays unsaved.
    Rules: `decrement_usage_count` R2"""
    t1 = mk_tag(name="Hex Bolt", tag_code="hex_bolt")
    t1.name = "Lock Nut"

    result = dao.decrement_usage_count(db, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is t1
    # Then 2
    row = reread(db, t1)
    assert row.name == "Hex Bolt"
    # Then 3
    assert row.usage_count == 0


def test_itg_inh_05__create_with_an_unknown_workspace_id_fails_on_flush_and_saves_nothing(db):
    """ITG-INH-05 — create with an unknown workspace_id fails on flush and saves nothing.
    Rules: inherited R2, Errors row 2"""
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": MISSING, "name": "Spare Part", "tag_code": "spare_part"})

    # Then 2
    assert isinstance(exc.value.orig, ForeignKeyViolation)
    # Then 3
    assert "item_tags_workspace_id_fkey" in str(exc.value.orig)
    # Then 4
    assert count_rows(db, "item_tags") == 0


def test_itg_inh_01__create_with_a_dict_stores_a_tag_with_the_model_defaults(db, w1):
    """ITG-INH-01 — create with a dict stores a tag with the model defaults.
    Rules: inherited R1"""
    result = dao.create(db, obj_in={"workspace_id": w1.id, "name": "Spare Part", "tag_code": "spare_part"})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.name == "Spare Part"
    assert row.tag_code == "spare_part"
    # Then 3
    assert row.is_system_tag is False
    assert row.is_active is True
    assert row.usage_count == 0
    # Then 4
    assert row.created_by is None
    assert row.color is None
    assert row.icon is None
    assert row.description is None
    # Then 5
    assert row.created_at.tzinfo is None
    # Then 6
    assert close_to_now(row.created_at)
    # Then 7
    assert count_rows(db, "item_tags") == 1
```
