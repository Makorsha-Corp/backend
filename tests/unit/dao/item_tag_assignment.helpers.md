# Helpers for `test_item_tag_assignment.py`

## Fixtures (add them as test arguments)
- `db` — the session. `w1`, `w2` — W1, W2. `u1`, `u2` — U1, U2. Items `i1`, `i2`, `ix`, `i9` — I1, I2, IX, I9. Tags `t1`, `t2`, `ts`, `td`, `t9` — T1, T2, TS, TD, T9. These rows already exist in every test: never build them, just request the ones the test names.
- Builders: `mk_link`, `mk_tag`, `mk_system_tag`, `mk_item`.
- Every fixture a test uses — builders and actors too, also one used only in the When call, inside a dict (`w1.id`) or in an assert — must be in its argument list.
- ONLY the names above can be arguments. Rows the test builds (`l1`, `k1`, `i3`, `p1`) are local variables. `dao`, `MISSING` and the reading helpers are used directly.
- Never patch or mock anything.

## Builders (keyword arguments only)
- `mk_link(of=i1, to=t1)` — "link of I1 to T1" (workspace of the item, assigned by U1).
- `mk_tag(name="...", tag_code="...")` — a "tag". `mk_system_tag(name="...", tag_code="...")` — a "system tag". Never pass `is_system_tag`.
- `mk_item(name="...", name_normalized="...")` — an "item" (I3).
- Each column the card lists after "but" is one more keyword, named like the card's column. Never add a keyword the card's row does not list.

## Card says -> write
| Card says | Write |
|---|---|
| `W1.id`, `IX.id`, `TS.id`, `TD.id`, L1, K1, P1 | `w1.id`, `ix.id`, `ts.id`, `td.id`, `l1`, `k1`, `p1` |
| MISSING | the name `MISSING` |
| Link of I1 to T1. | `mk_link(of=i1, to=t1)` |
| L1 = link of I1 to T1. | `l1 = mk_link(of=i1, to=t1)` |
| Link of I1 to T1, but `workspace_id W2.id`. | `mk_link(of=i1, to=t1, workspace_id=w2.id)` |
| L9 = link of I9 to T9. (A link of W2.) | `l9 = mk_link(of=i9, to=t9)` — a link already takes its item's workspace; write `workspace_id=` only after "but" |
| K1 = tag, `name "Bolt"`, `tag_code "bolt_a"`. | `k1 = mk_tag(name="Bolt", tag_code="bolt_a")` |
| I3 = item, `name "Spring Pin"`, `name_normalized "spring pin"`. | `i3 = mk_item(name="Spring Pin", name_normalized="spring pin")` |
| "No link exists." | no code |

Build the Given rows in the order written, one statement per row; give a row a variable only if the test uses it later. Text in parentheses ( ) is an explanation: no code. Copy quoted text character for character.

A Given line that is code is run as written, at that place, with lower-case row names (`P1 = ...` and `db.add(P1)`: see ITA-TFI-15; no flush): "`l1_id = L1.id`" -> `l1_id = l1.id`. One exception: "`loaded = len(I1.tag_assignments)`" -> `_loaded = len(i1.tag_assignments)` (with the underscore; the line must stay). Snapshots (`before…`) come after the last Given line.

## Reading helpers (call them directly)
- `ids(x)`, `names(x)` — lists of the ids / names in the order returned; x is a list or one dict value (`ids(result[i1.id])`).
- `reread(db, row)` — fresh copy of a link, item or tag from the database. `snap(db, row)` — all columns of such a row.
- `links_of(db, i1)` — links_of(I1): fresh list of the link rows of I1.
- `count_rows(db, "item_tag_assignments")` — rows of the table (also `"items"`, `"item_tags"`); a filter is a keyword: `count_rows(db, "item_tag_assignments", id=l1_id)`.
- `written(db)` — the "nothing written" counts.
- `close_to_now(value)` — True when the value is close to now.

## Already imported (never import)
`pytest`, `dao`, `ItemTagAssignment`, `ItemTagAssignmentCreate`, `ItemTag`, `Item`, `IntegrityError`, `UniqueViolation`, `ForeignKeyViolation`, `NotNullViolation`.

## How to write each kind of line
- When -> the call exactly as shown, with lower-case names: `result = dao.get_tags_for_items(db, item_ids=[i1.id, MISSING], workspace_id=w1.id)`, `result = dao.remove(db, id=l1_id)`. Keep every argument, also `None`, `[]`, `MISSING`; add none.
- `returns:` -> `assert` + the expression as written, nothing changed but the lower-case names (keep `is`, `in`, `not in`, `sorted(...)`, `len(...)`, `list(...)`, `isinstance(...)` as the card has them): `assert sorted(ids(result[i1.id])) == [t1.id, ts.id]`, `assert list(result.keys()) == [i1.id, i2.id]`, `assert result == {i1.id: []}`, `assert t2.id not in result`, `assert l1 not in db`.
- `raises: IntegrityError` (also "`IntegrityError` on flush") -> as ITA-INH-04 below: `with pytest.raises(IntegrityError) as exc:`, inside it `with db.begin_nested():`, inside that the call (without `result =`). `# Then 1` goes directly above the `with pytest.raises(...)` line; the first `exc.value` assert is `# Then 2`. The other `raises:` lines are asserts on `exc.value` after the `with` block, each under its own `# Then N`. Use `pytest.raises` only for a `raises:` line.
- `nothing written` -> `before = written(db)` before the call, `assert written(db) == before` after (never `== 0`). Only when the card has that Then line.
- `unchanged(L2)` -> `before_l2 = snap(db, l2)` BEFORE the When call (after all Given lines), `assert snap(db, l2) == before_l2` after; `unchanged(TD)` -> `before_td = snap(db, td)` / `assert snap(db, td) == before_td`. Only when the card has that Then line.
- `re-read L2:` -> `row = reread(db, l2)`, then one `assert` per value: two values need TWO asserts (ITA-RM-05). Later re-read lines of the same row reuse `row`. "re-read the returned row" -> `row = reread(db, result)`. "`assigned_at` is close to now" -> `assert close_to_now(row.assigned_at)`.
- `re-read links_of(I1)[0]:` -> `row = links_of(db, i1)[0]`, then one `assert` per value.
- `count: links_of(I1) has exactly 1 row` -> `assert len(links_of(db, i1)) == 1`.
- `count: item_tag_assignments has exactly 0 rows` -> `assert count_rows(db, "item_tag_assignments") == 0`. "rows with `tag_id == K1.id`: exactly 0" -> `assert count_rows(db, "item_tag_assignments", tag_id=k1.id) == 0`.

## Example tests (copy this style)
```python
def test_ita_tfs_16__lower_case_names_come_back_alphabetically_within_each_item_the_system(db, w1, i1, i2, mk_tag, mk_system_tag, mk_link):
    """ITA-TFS-16 — lower-case names come back alphabetically within each item, the system tag not first.
    Rules: `get_tags_for_items` R6 (the part that holds today: names with one case only; system tags not grouped first), R2"""
    k1 = mk_tag(name="delta", tag_code="delta")
    k2 = mk_tag(name="alpha", tag_code="alpha")
    k3 = mk_tag(name="charlie", tag_code="charlie")
    k4 = mk_system_tag(name="zulu", tag_code="zulu")
    mk_link(of=i1, to=k1)
    mk_link(of=i1, to=k4)
    mk_link(of=i1, to=k2)
    mk_link(of=i2, to=k3)
    mk_link(of=i2, to=k2)

    result = dao.get_tags_for_items(db, item_ids=[i1.id, i2.id], workspace_id=w1.id)

    # Then 1
    assert names(result[i1.id]) == ["alpha", "delta", "zulu"]
    # Then 2
    assert names(result[i2.id]) == ["alpha", "charlie"]


def test_ita_tfi_15__a_link_added_but_not_flushed_is_not_seen(db, w1, u1, i1, t1, t2, mk_link):
    """ITA-TFI-15 — a link added but not flushed is not seen.
    Rules: `get_tags_for_item` R5"""
    mk_link(of=i1, to=t1)
    p1 = ItemTagAssignment(workspace_id=w1.id, item_id=i1.id, tag_id=t2.id, assigned_by=u1.id)
    db.add(p1)

    result = dao.get_tags_for_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [t1.id]


def test_ita_ex_01__an_existing_link_gives_true_and_nothing_is_written(db, w1, i1, t1, mk_link):
    """ITA-EX-01 — an existing link gives True and nothing is written.
    Rules: `assignment_exists` R1, R5"""
    l1 = mk_link(of=i1, to=t1)
    before = written(db)
    before_l1 = snap(db, l1)

    result = dao.assignment_exists(db, item_id=i1.id, tag_id=t1.id, workspace_id=w1.id)

    # Then 1
    assert result is True
    # Then 2
    assert written(db) == before
    # Then 3
    assert snap(db, l1) == before_l1


def test_ita_cnt_01__counts_the_live_items_of_each_tag_system_and_user_tags_alike_and(db, w1, i1, i2, t1, t2, ts, mk_item, mk_link):
    """ITA-CNT-01 — counts the live items of each tag, system and user tags alike, and writes nothing.
    Rules: `count_active_items_per_tag` R1, R5 (system tags), R6, Returns"""
    i3 = mk_item(name="Spring Pin", name_normalized="spring pin")
    mk_link(of=i1, to=t1)
    mk_link(of=i2, to=t1)
    mk_link(of=i3, to=t1)
    mk_link(of=i1, to=t2)
    mk_link(of=i2, to=ts)
    before = written(db)

    result = dao.count_active_items_per_tag(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, dict)
    # Then 2
    assert result == {t1.id: 3, t2.id: 1, ts.id: 1}
    # Then 3
    assert written(db) == before


def test_ita_rm_05__a_link_of_the_same_item_recorded_under_another_workspace_stays(db, w1, w2, i1, t1, t2, mk_link):
    """ITA-RM-05 — a link of the same item recorded under another workspace stays.
    Rules: `remove_all_tags_from_item` R3"""
    mk_link(of=i1, to=t1)
    l2 = mk_link(of=i1, to=t2, workspace_id=w2.id)
    before_l2 = snap(db, l2)

    result = dao.remove_all_tags_from_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result == 1
    # Then 2
    assert len(links_of(db, i1)) == 1
    # Then 3
    assert snap(db, l2) == before_l2
    # Then 4
    row = reread(db, l2)
    assert row.workspace_id == w2.id
    assert row.tag_id == t2.id


def test_ita_inh_04__a_second_link_for_the_same_item_and_tag_fails_on_flush_and_the_first(db, w1, i1, t1, mk_link):
    """ITA-INH-04 — a second link for the same item and tag fails on flush and the first stays.
    Rules: inherited R2, Errors row 2"""
    l1 = mk_link(of=i1, to=t1)
    before_l1 = snap(db, l1)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "item_id": i1.id, "tag_id": t1.id})

    # Then 2
    assert isinstance(exc.value.orig, UniqueViolation)
    # Then 3
    assert "uq_item_tag" in str(exc.value.orig)
    # Then 4
    assert snap(db, l1) == before_l1
    # Then 5
    assert len(links_of(db, i1)) == 1


def test_ita_inh_17__update_with_a_dict_sets_the_given_column_and_nothing_else(db, w1, u2, i1, t1, mk_link):
    """ITA-INH-17 — update with a dict sets the given column and nothing else.
    Rules: inherited R5"""
    l1 = mk_link(of=i1, to=t1)
    at_before = l1.assigned_at

    result = dao.update(db, db_obj=l1, obj_in={"assigned_by": u2.id})

    # Then 1
    assert result.id == l1.id
    # Then 2
    row = reread(db, l1)
    assert row.assigned_by == u2.id
    # Then 3
    assert row.assigned_at == at_before
    # Then 4
    assert row.item_id == i1.id
    assert row.tag_id == t1.id
    assert row.workspace_id == w1.id
```
