# Helpers for `test_item_manager.py`

## Fixtures (add them as test arguments)
- `db` — the session. `w1`, `w2` — W1, W2. `u1`, `u2` — U1, U2. Only these four rows exist in every test.
- Builders: `mk_item`, `mk_tag`, `mk_link`, `mk_f1`, `mk_mc1`, `mk_ac1`, `mk_wt1`, `mk_stage`, `mk_stock`, `mk_machine_stock`, `mk_po`, `mk_so`, `mk_wo`, `mk_to`, `mk_line`.
- Every fixture a test uses — builders and actors too, also one used only in the When call or in an assert — must be in its argument list.
- ONLY these names can be arguments. Every other row (`i1`, `t1`, `l1`, `f1`, `st`, `po`) is a local variable built from its Given line. `M`, `MISSING`, `T0` and the reading helpers are used directly. Never patch anything.

## Card says -> write
| Card says | Write |
|---|---|
| `W1.id`, `U2.id`, `IX.id`, `TD.id`, L1, SK, POL | `w1.id`, `u2.id`, `ix.id`, `td.id`, `l1`, `sk`, `pol` (lower case) |
| I1 (also I2, IX, I9) | `i1 = mk_item("I1")` — the recipe name in quotes |
| T1 (also T2, K3, TD, T9) | `t1 = mk_tag("T1")` |
| T1, but `usage_count 3` | `t1 = mk_tag("T1", usage_count=3)` |
| I1, but `sku "B-M8"` | `i1 = mk_item("I1", sku="B-M8")` |
| S1 = item, `name "Pa"`, `name_normalized "pq"` | `s1 = mk_item(name="Pa", name_normalized="pq")` — a plain "item" has no recipe: both keywords, nothing positional |
| L1 = link of I1 to T1 | `l1 = mk_link(of=i1, to=t1)` |
| F1 (also AC1, WT1) | `f1 = mk_f1()` — `ac1 = mk_ac1()`, `wt1 = mk_wt1()` |
| MC1 | `mc1 = mk_mc1(factory=f1)` |
| ST = stage "Draft" | `st = mk_stage("Draft")` |
| SK = stock of I1 in F1, `qty 400` | `sk = mk_stock(of=i1, factory=f1, qty=400)` |
| MS = machine stock of I1 on MC1, `qty 5` | `ms = mk_machine_stock(of=i1, machine=mc1, qty=5)` |
| PO = purchase order of F1, `current_status_id ST.id` | `po = mk_po(factory=f1, current_status_id=st.id)` |
| SO = sales order of F1 and AC1, `current_status_id ST.id` | `so = mk_so(factory=f1, account=ac1, current_status_id=st.id)` |
| WO = work order of F1 and WT1, `status "DRAFT"` | `wo = mk_wo(factory=f1, wo_type=wt1, status="DRAFT")` |
| TO = transfer order of F1, `current_status_id ST.id` | `to = mk_to(factory=f1, current_status_id=st.id)` |
| POL = PO line of I1 (also SO / WO / TO line) | `pol = mk_line(of=i1, order=po)` — `order=so`, `order=wo`, `order=to` |
| "No items exist." | no code |

Each column after "but" is one more keyword named like the card's column: "but `is_deleted True`" -> `is_deleted=True`, "but `inventory_type InventoryTypeEnum.DAMAGED`" -> `inventory_type=InventoryTypeEnum.DAMAGED`. Never add a keyword the card's row does not list.

Build the Given rows in the order written, one statement per row. Text in parentheses ( ) is an explanation: no code. Copy every quoted text exactly, as a plain string: `"   "` is three spaces, `"\t"` one tab. A Given line that is code runs as written, lower-case: "`l1_id = L1.id`" -> `l1_id = l1.id`, "`created_before = I1.created_at`" -> `created_before = i1.created_at`. Snapshots (`before…`) come after the last Given line.

## Reading helpers (call them directly)
- `reread(db, row)` — fresh copy of a row. `snap(db, row)` — its columns.
- `count_rows(db, "items")` — rows of `items`, `item_tags` or `item_tag_assignments`; filters are keywords: `count_rows(db, "items", workspace_id=w1.id, name="Bolt M8")`, "`sku` NULL" -> `sku=None`.
- `written(db)` — the "nothing written" counts.
- `stored_count(db, t1)`, `links_of(db, i1)`, `tag_ids_of(db, i1)`, `ids(x)` — the named checks. `link_of(db, i1, t1)` — "the link of I1 to T1".

## Already imported (never import)
`pytest`, `ValidationError`, `IntegrityError`, `DataError`, `ForeignKeyViolation`, `Item`, `ItemTag`, `ItemTagAssignment`, `ItemCreate`, `ItemUpdate`, `InventoryTypeEnum`.

## How to write each kind of line
- When -> the call exactly as shown, lower-case names; keep every argument, add none; positional stays positional: `result = M.get_item(db, i1.id, w1.id)`. `include_deleted=True`: write the call as shown; never wrap it in `pytest.raises`.
- target `schema` -> only the schema call, `M` is not called: `result = ItemUpdate(is_active=False)`, or inside `pytest.raises(ValidationError)` as ITM-C-11.
- `returns:` -> `assert` + the expression as written, names lower-cased: `assert result is i1`, `assert result == []`, `assert result[0]["match_type"] == "fuzzy"`.
- `raises: ValueError` -> as ITM-D-06. In-use refusal (`args[0]`, `args[1]`) -> as ITM-D-39. Further `raises:` lines are asserts on `exc.value` after the `with` block, each under its own `# Then N`.
- `raises: IntegrityError` / `DataError` -> the call inside `db.begin_nested()`, without `result =`:
  ```python
  # Then 1
  with pytest.raises(IntegrityError) as exc:
      with db.begin_nested():
          M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=MISSING)
  # Then 2
  assert isinstance(exc.value.orig, ForeignKeyViolation)
  ```
  `raises: TypeError (plain …)` -> `with pytest.raises(TypeError):` around the call.
- `nothing written` -> `before = written(db)` before the call, `assert written(db) == before` after; `unchanged(X)` -> `before_x = snap(db, x)` BEFORE the call, `assert snap(db, x) == before_x` after. Only when the card has that line.
- `re-read I1:` -> `row = reread(db, i1)`, then one `assert` per value (two values, two asserts). "the returned row" -> `reread(db, result)`. Another row needs its own variable (`row_i2 = reread(db, i2)`).
- `re-read: stored_count(T1) == 4` -> `assert stored_count(db, t1) == 4`; `links_of(IX) == []` -> `assert links_of(db, ix) == []` (every reading helper takes `db` first). "every row of links_of(I1) has …" -> as ITM-C-33.
- `count:` -> `assert count_rows(db, "items") == 1`, the card's table and number.

## Example tests (copy this style)
```python
def test_itm_c_33__the_tags_sent_are_linked_to_the_new_item_and_counted_once_each(db, w1, u2, mk_tag):
    """ITM-C-33 — the tags sent are linked to the new item and counted once each.
    Rules: `create_item` R8; `_assign_tags_to_item` R1"""
    t1 = mk_tag("T1", usage_count=3)
    t2 = mk_tag("T2")

    result = M.create_item(db, item_data=ItemCreate(name="Bolt M8", unit="pcs", tag_ids=[t1.id, t2.id]), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    assert tag_ids_of(db, result) == [t1.id, t2.id]
    # Then 3
    links = links_of(db, result)
    assert all(link.workspace_id == w1.id for link in links)
    assert all(link.assigned_by == u2.id for link in links)
    # Then 4
    assert stored_count(db, t1) == 4
    # Then 5
    assert stored_count(db, t2) == 1


def test_itm_u_34__a_tag_that_stays_keeps_its_link_same_id_same_assigning_user_same_time(db, w1, u1, u2, mk_item, mk_tag, mk_link):
    """ITM-U-34 — a tag that stays keeps its link: same id, same assigning user, same time.
    Rules: `update_item` R12 [BUG-934]"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1", usage_count=4)
    t2 = mk_tag("T2", usage_count=6)
    k3 = mk_tag("K3")
    l1 = mk_link(of=i1, to=t1)
    mk_link(of=i1, to=t2)
    l1_id = l1.id
    l1_at = l1.assigned_at

    result = M.update_item(db, item_id=i1.id, item_data=ItemUpdate(tag_ids=[t1.id, k3.id]), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is i1
    # Then 2
    assert tag_ids_of(db, i1) == [t1.id, k3.id]
    # Then 3
    row = link_of(db, i1, t1)
    assert row.id == l1_id
    # Then 4
    assert row.assigned_by == u1.id
    # Then 5
    assert row.assigned_at == l1_at


def test_itm_d_06__an_already_deleted_item_is_refused_its_tag_count_and_stamp_stay(db, w1, u2, mk_item, mk_tag, mk_link):
    """ITM-D-06 — an already deleted item is refused; its tag count and stamp stay.
    Rules: `delete_item` R3, Errors row 3"""
    ix = mk_item("IX")
    t1 = mk_tag("T1", usage_count=3)
    mk_link(of=ix, to=t1)
    before_ix = snap(db, ix)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=ix.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert str(exc.value) == f"Item {ix.id} is already deleted"
    # Then 3
    assert stored_count(db, t1) == 3
    # Then 4
    assert snap(db, ix) == before_ix
    # Then 5
    row = reread(db, ix)
    assert row.updated_by is None


def test_itm_d_39__a_line_on_a_sales_order_that_is_not_completed_blocks_the_delete_and(db, w1, u2, mk_item, mk_tag, mk_link, mk_f1, mk_ac1, mk_stage, mk_so, mk_line):
    """ITM-D-39 — a line on a sales order that is not completed blocks the delete and names the order.
    Rules: `delete_item` R9 (d) [BUG-948], R9b [BUG-948], Errors row 4"""
    i1 = mk_item("I1")
    t1 = mk_tag("T1", usage_count=4)
    mk_link(of=i1, to=t1)
    f1 = mk_f1()
    ac1 = mk_ac1()
    st = mk_stage("Open")
    so = mk_so(factory=f1, account=ac1, current_status_id=st.id)
    sol = mk_line(of=i1, order=so)
    before_so = snap(db, so)
    before_sol = snap(db, sol)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 2
    assert exc.value.args[0] == "Item has stock or open orders"
    # Then 3
    assert exc.value.args[1] == [{"type": "sales_order", "id": so.id}]
    # Then 4
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 5
    assert row.updated_at is None
    # Then 6
    assert stored_count(db, t1) == 4
    # Then 7
    assert snap(db, so) == before_so
    # Then 8
    assert snap(db, sol) == before_sol
    # Then 9
    assert written(db) == before


def test_itm_c_11__an_empty_name_is_rejected_by_itemcreate(db):
    """ITM-C-11 — an empty name is rejected by ItemCreate.
    Rules: `create_item` R3 [BUG-936], Errors row 1"""
    # Then 1
    with pytest.raises(ValidationError):
        ItemCreate(name="", unit="pcs")

    # Then 2
    assert count_rows(db, "items") == 0


def test_itm_l_01__the_default_page_holds_the_workspace_s_live_items_only(db, w1, mk_item):
    """ITM-L-01 — the default page holds the workspace's live items only.
    Rules: `list_items_filtered` R1"""
    i1 = mk_item("I1")
    i2 = mk_item("I2")
    mk_item("IX")
    mk_item("I9")
    before = written(db)

    result = M.list_items_filtered(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [i1.id, i2.id]
    # Then 2
    assert written(db) == before
```
