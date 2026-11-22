"""Unit tests for app/services/item_service.py.

Implements tests/unit/services/item_service.cases.md (revision 2), one test per
case, in card order. Real Postgres session (`db` fixture): a `commit()` only
releases a savepoint, so the service's commits are safe and the fixture's outer
rollback discards everything. Nothing is patched except what Conventions name:
the failing commit / failing refresh wraps, the manager patches of the
translation cards and the spy of ITS-D-02.

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. Row names of the cards are the lower-case names here (I1 -> i1, TD ->
td, `W1.id` -> `w1.id`); `# Then N` marks the checks of the card's Then line N.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with patch.object(...)`)
from datetime import datetime
from unittest.mock import patch

import pytest
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflictError, NotFoundError
from app.core.exceptions import ValidationError as AppValidationError
from app.models.enums import InventoryTypeEnum
from app.models.factory import Factory
from app.models.inventory import Inventory
from app.models.item import Item
from app.models.item_tag import ItemTag
from app.models.item_tag_assignment import ItemTagAssignment
from app.schemas.item import ItemCreate, ItemUpdate
from app.services.item_service import item_service
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "svc = the singleton item_service"
svc = item_service

# Convention "MISSING": an id no row of any table has
MISSING = 999999999


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# Conventions -> actors: W1, W2, U1, U2 exist in every test
# --------------------------------------------------------------------------- #

@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# U1 created every Given row
@pytest.fixture
def u1(db, w2):
    return make_profile(db)


# U2 = the acting user
@pytest.fixture
def u2(db, u1):
    return make_profile(db)


@pytest.fixture(autouse=True)
def standing_rows(u2):
    pass


# --------------------------------------------------------------------------- #
# Conventions -> Given rows (built directly, flushed one at a time)
# --------------------------------------------------------------------------- #

# Convention "item"; the card gives name and name_normalized, "but" the rest
@pytest.fixture
def mk_item(db, w1, u1):
    def _mk(name, name_normalized, **but):
        fields = {
            "workspace_id": w1.id, "unit": "pcs", "description": None, "sku": None, "item_type": "physical",
            "is_active": True, "created_by": u1.id, "updated_by": None,
            "name": name, "name_normalized": name_normalized,
        }
        fields.update(but)
        return _add(db, Item(**fields))
    return _mk


# Convention "I1"
@pytest.fixture
def mk_i1(mk_item):
    return lambda **but: mk_item("Bolt M8", "bolt m8", **but)


# Convention "I2"
@pytest.fixture
def mk_i2(mk_item):
    return lambda **but: mk_item("Washer Ten", "washer ten", **but)


# Convention "IX" (a deleted item)
@pytest.fixture
def mk_ix(mk_item):
    return lambda **but: mk_item("Old Rivet", "old rivet", **{"is_active": False, **but})


# Convention "I9" (W2's item)
@pytest.fixture
def mk_i9(mk_item, w2):
    return lambda **but: mk_item("Far Spring", "far spring", **{"workspace_id": w2.id, **but})


# Convention "tag"
@pytest.fixture
def mk_tag(db, w1):
    def _mk(name, tag_code, **but):
        fields = {
            "workspace_id": w1.id, "is_system_tag": False, "is_active": True, "usage_count": 0, "created_by": None,
            "name": name, "tag_code": tag_code,
        }
        fields.update(but)
        return _add(db, ItemTag(**fields))
    return _mk


# Convention "T1"
@pytest.fixture
def mk_t1(mk_tag):
    return lambda **but: mk_tag("Spare Part", "spare_part", **but)


# Convention "TD" (a deleted tag)
@pytest.fixture
def mk_td(mk_tag):
    return lambda **but: mk_tag("Obsolete", "obsolete", **{"is_active": False, **but})


# Convention "link of I to T"
@pytest.fixture
def mk_link(db, w1, u1):
    def _mk(item, tag):
        return _add(db, ItemTagAssignment(workspace_id=w1.id, item_id=item.id, tag_id=tag.id, assigned_by=u1.id))
    return _mk


# Convention "F1"
@pytest.fixture
def mk_f1(db, w1, u1):
    return lambda: _add(db, Factory(workspace_id=w1.id, name="Main Plant", abbreviation="MP", created_by=u1.id))


# Convention "stock of I": an `inventory` row (model class `Inventory`)
@pytest.fixture
def mk_stock(db, w1, u1):
    def _mk(item, factory, qty):
        return _add(db, Inventory(
            workspace_id=w1.id, item_id=item.id, factory_id=factory.id, inventory_type=InventoryTypeEnum.STORAGE,
            is_deleted=False, created_by=u1.id, qty=qty,
        ))
    return _mk


# Convention "commit point"
def commit_point(db):
    db.commit()


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #

def _id_of(row):
    return inspect(row).identity[0]


def _columns(db, model, row_id):
    table = model.__table__
    found = db.execute(select(table).where(table.c.id == row_id)).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "re-read X"
def reread(db, row):
    row_id = _id_of(row)
    db.expire_all()
    return db.execute(select(type(row)).where(type(row).id == row_id)).scalar_one_or_none()


def reread_item_id(db, item_id):
    db.expire_all()
    return db.execute(select(Item).where(Item.id == item_id)).scalar_one_or_none()


# Convention "unchanged(X)": every column at the commit point ...
def snap_before(db, row):
    return _columns(db, type(row), _id_of(row))


# ... and after a re-read
def snap(db, row):
    row_id = _id_of(row)
    db.expire_all()
    return _columns(db, type(row), row_id)


_TABLES = {
    "items": Item,
    "item_tags": ItemTag,
    "item_tag_assignments": ItemTagAssignment,
}


# Convention "count:" lines: rows of the named table (all workspaces), with the filter stated
def count_rows(db, table_name, **filters):
    model = _TABLES[table_name]
    query = select(func.count()).select_from(model)
    for column, value in filters.items():
        query = query.where(getattr(model, column) == value)
    return db.execute(query).scalar_one()


# Convention "nothing written"
def written(db):
    return {name: count_rows(db, name) for name in _TABLES}


# Convention "stored_count(T)"
def stored_count(db, tag):
    return db.scalar(text("select usage_count from item_tags where id = :i"), {"i": _id_of(tag)})


# Convention "tag_ids_of(I)"
def tag_ids_of(db, item_id):
    query = select(ItemTagAssignment.tag_id).where(ItemTagAssignment.item_id == item_id)
    return sorted(db.execute(query).scalars())


# Convention "ids(x)"
def ids(rows):
    return sorted(r.id for r in rows)


# Convention "loaded:"
def unloaded(result):
    return inspect(result).unloaded


# Convention "session: usable"
def usable(db):
    return db.execute(text("SELECT 1")).scalar() == 1


# --------------------------------------------------------------------------- #
# ItemService.create_item
# --------------------------------------------------------------------------- #

# [claude] ITS-C-01
def test_its_c_01__a_new_item_with_a_tag_is_committed_and_returned_re_read(db, w1, u2, mk_t1):
    """ITS-C-01 — a new item with a tag is committed and returned re-read.
    Rules: `create_item` R1, Returns; TC1, TC2"""
    t1 = mk_t1(usage_count=3)
    commit_point(db)
    result = svc.create_item(
        db, item_in=ItemCreate(name="Bolt M8", unit="pcs", sku="B-M8", tag_ids=[t1.id]),
        workspace_id=w1.id, user_id=u2.id,
    )

    # Then 1
    for column in ("created_at", "name", "name_normalized", "workspace_id", "created_by"):
        assert column not in unloaded(result)
    # Then 2
    assert isinstance(result, Item)
    # Then 3
    assert result.id is not None
    assert result.name == "Bolt M8"
    assert result.sku == "B-M8"
    new_id = result.id
    db.rollback()
    # Then 4
    row = reread_item_id(db, new_id)
    assert row is not None
    assert row.name == "Bolt M8"
    assert row.name_normalized == "bolt m8"
    assert row.workspace_id == w1.id
    assert row.created_by == u2.id
    assert row.is_active is True
    # Then 5
    assert tag_ids_of(db, new_id) == [t1.id]
    # Then 6
    assert stored_count(db, t1) == 4


# [claude] ITS-C-02
def test_its_c_02__an_unknown_user_the_integrityerror_passes_unchanged(db, w1, mk_i2, mk_item):
    """ITS-C-02 — an unknown user: the IntegrityError passes unchanged, the session is rolled back and usable.
    Rules: `create_item` R3, Errors row 4; TC3"""
    i2 = mk_i2()
    commit_point(db)
    before_i2 = snap_before(db, i2)
    before = written(db)
    mk_item("Extra", "extra")
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        svc.create_item(db, item_in=ItemCreate(name="Bolt M8", unit="pcs"), workspace_id=w1.id, user_id=MISSING)
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    assert count_rows(db, "items", name="Bolt M8") == 0
    # Then 4
    assert count_rows(db, "items", name="Extra") == 0
    # Then 5
    assert written(db) == before
    # Then 6
    assert snap(db, i2) == before_i2
    # Then 7
    assert usable(db)


# [claude] ITS-C-03
def test_its_c_03__a_failing_commit_is_rolled_back_and_re_raised(db, w1, u2):
    """ITS-C-03 — a failing commit is rolled back and re-raised.
    Rules: `create_item` R3; TC4"""
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.create_item(db, item_in=ItemCreate(name="Bolt M8", unit="pcs"), workspace_id=w1.id, user_id=u2.id)
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert count_rows(db, "items", name="Bolt M8") == 0
    # Then 4
    assert written(db) == before


# [claude] ITS-C-04
def test_its_c_04__a_failing_re_read_after_the_commit_leaves_the_item_saved(db, w1, u2):
    """ITS-C-04 — a failing re-read after the commit leaves the item saved.
    Rules: `create_item` R3; TC5"""
    commit_point(db)
    # Then 1
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
            svc.create_item(db, item_in=ItemCreate(name="Bolt M8", unit="pcs"), workspace_id=w1.id, user_id=u2.id)
    assert str(exc.value) == "boom"
    db.rollback()
    # Then 2
    assert count_rows(db, "items", workspace_id=w1.id, name="Bolt M8") == 1


# [claude] ITS-C-05
@pytest.mark.xfail(strict=True, reason="BUG-944: Unknown item tag ids silently dropped on item create / update")
def test_its_c_05__the_managers_unknown_tag_valueerror_becomes_notfounderror_404(db, w1, u2, mk_i2, mk_item):
    """ITS-C-05 — the manager's unknown-tag ValueError becomes NotFoundError 404 after a rollback.
    Rules: `create_item` R2 [BUG-944], Errors row 1; TC3"""
    i2 = mk_i2()
    commit_point(db)
    before_i2 = snap_before(db, i2)
    mk_item("Extra", "extra")
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with patch.object(svc.item_manager, "create_item", side_effect=ValueError("Item tag 999999999 not found")):
            svc.create_item(db, item_in=ItemCreate(name="Bolt M8", unit="pcs"), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Item tag 999999999 not found"
    # Then 4
    assert count_rows(db, "items", name="Extra") == 0
    # Then 5
    assert snap(db, i2) == before_i2


# [claude] ITS-C-06
@pytest.mark.xfail(strict=True, reason="BUG-943: Deleted item tags can be put on items")
def test_its_c_06__the_managers_deleted_tag_valueerror_becomes_validationerror_400(db, w1, u2):
    """ITS-C-06 — the manager's deleted-tag ValueError becomes ValidationError 400.
    Rules: `create_item` R2 [BUG-943], Errors row 2"""
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(AppValidationError) as exc:
        with patch.object(svc.item_manager, "create_item", side_effect=ValueError("Item tag 77 is not active")):
            svc.create_item(db, item_in=ItemCreate(name="Bolt M8", unit="pcs"), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Item tag 77 is not active"
    # Then 4
    assert written(db) == before


# [claude] ITS-C-07
@pytest.mark.xfail(strict=True, reason="BUG-946: Item SKU is not unique per workspace")
def test_its_c_07__the_managers_sku_valueerror_becomes_conflicterror_409(db, w1, u2):
    """ITS-C-07 — the manager's SKU ValueError becomes ConflictError 409.
    Rules: `create_item` R2 [BUG-946], Errors row 3"""
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(ConflictError) as exc:
        with patch.object(
            svc.item_manager, "create_item", side_effect=ValueError("Item with SKU 'B-M8' already exists"),
        ):
            svc.create_item(db, item_in=ItemCreate(name="Bolt M8", unit="pcs"), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Item with SKU 'B-M8' already exists"
    # Then 4
    assert written(db) == before


# [claude] ITS-C-08
@pytest.mark.xfail(strict=True, reason="BUG-944: Unknown item tag ids silently dropped on item create / update")
def test_its_c_08__end_to_end_an_unknown_tag_id_gets_the_404_and_nothing_is_saved(db, w1, u2, mk_t1):
    """ITS-C-08 — end to end: an unknown tag id gets the 404 and nothing is saved.
    Rules: `create_item` R2 [BUG-944], Errors row 1"""
    t1 = mk_t1(usage_count=3)
    commit_point(db)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.create_item(
            db, item_in=ItemCreate(name="Bolt M8", unit="pcs", tag_ids=[t1.id, MISSING]),
            workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Item tag 999999999 not found"
    # Then 4
    assert count_rows(db, "items", name="Bolt M8") == 0
    # Then 5
    db.expire_all()
    assert stored_count(db, t1) == 3


# [claude] ITS-C-09
@pytest.mark.xfail(strict=True, reason="BUG-943: Deleted item tags can be put on items")
def test_its_c_09__end_to_end_a_deleted_tag_gets_the_400_and_nothing_is_saved(db, w1, u2, mk_td):
    """ITS-C-09 — end to end: a deleted tag gets the 400 and nothing is saved.
    Rules: `create_item` R2 [BUG-943], Errors row 2"""
    td = mk_td(usage_count=5)
    commit_point(db)
    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.create_item(
            db, item_in=ItemCreate(name="Bolt M8", unit="pcs", tag_ids=[td.id]), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == f"Item tag {td.id} is not active"
    # Then 4
    assert count_rows(db, "items", name="Bolt M8") == 0
    # Then 5
    db.expire_all()
    assert stored_count(db, td) == 5


# [claude] ITS-C-10
@pytest.mark.xfail(strict=True, reason="BUG-946: Item SKU is not unique per workspace")
def test_its_c_10__end_to_end_a_sku_in_use_gets_the_409_and_nothing_is_saved(db, w1, u2, mk_i1):
    """ITS-C-10 — end to end: a SKU in use gets the 409 and nothing is saved.
    Rules: `create_item` R2 [BUG-946], Errors row 3"""
    i1 = mk_i1(sku="B-M8")
    commit_point(db)
    before_i1 = snap_before(db, i1)
    # Then 1
    with pytest.raises(ConflictError) as exc:
        svc.create_item(
            db, item_in=ItemCreate(name="Hex Screw", unit="pcs", sku="B-M8"), workspace_id=w1.id, user_id=u2.id,
        )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Item with SKU 'B-M8' already exists"
    # Then 4
    assert count_rows(db, "items", sku="B-M8") == 1
    # Then 5
    assert snap(db, i1) == before_i1


# [claude] ITS-C-11
def test_its_c_11__a_valueerror_with_another_text_is_not_translated(db, w1, u2, mk_i2, mk_item):
    """ITS-C-11 — a ValueError with another text is not translated and the session is rolled back.
    Rules: `create_item` R3"""
    i2 = mk_i2()
    commit_point(db)
    before_i2 = snap_before(db, i2)
    mk_item("Extra", "extra")
    with pytest.raises(ValueError) as exc:
        with patch.object(svc.item_manager, "create_item", side_effect=ValueError("something else")):
            svc.create_item(db, item_in=ItemCreate(name="Bolt M8", unit="pcs"), workspace_id=w1.id, user_id=u2.id)
    # Then 1
    assert type(exc.value) is ValueError
    # Then 2
    assert exc.value.args == ("something else",)
    # Then 3
    assert count_rows(db, "items", name="Extra") == 0
    # Then 4
    assert snap(db, i2) == before_i2


# [claude] ITS-C-12
@pytest.mark.xfail(
    strict=True, reason="BUG-936: Blank / whitespace-only item names and units accepted; names stored untrimmed",
)
def test_its_c_12__pass_through_bug_936_a_padded_name_is_committed_trimmed(db, w1, u2):
    """ITS-C-12 — pass-through BUG-936: a padded name is committed trimmed.
    Rules: `create_item` R1 [BUG-936]"""
    commit_point(db)
    result = svc.create_item(
        db, item_in=ItemCreate(name="  Steel  Rod 22 m ", unit="pcs"), workspace_id=w1.id, user_id=u2.id,
    )

    # Then 1
    assert result.id is not None
    new_id = result.id
    db.rollback()
    # Then 2
    assert reread_item_id(db, new_id).name == "Steel  Rod 22 m"


# --------------------------------------------------------------------------- #
# ItemService.get_item
# --------------------------------------------------------------------------- #

# [claude] ITS-G-01
def test_its_g_01__a_live_item_of_the_workspace_is_returned(db, w1, mk_i9, mk_i1):
    """ITS-G-01 — a live item of the workspace is returned.
    Rules: `get_item` R1"""
    mk_i9()
    i1 = mk_i1()
    commit_point(db)
    result = svc.get_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, Item)
    # Then 2
    assert result.id == i1.id
    assert result.name == "Bolt M8"


# [claude] ITS-G-02
def test_its_g_02__another_workspaces_item_gets_notfounderror_404(db, w1, mk_i1, mk_i9):
    """ITS-G-02 — another workspace's item gets NotFoundError 404.
    Rules: `get_item` R1, Errors row 1"""
    mk_i1()
    i9 = mk_i9()
    commit_point(db)
    before_i9 = snap_before(db, i9)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.get_item(db, item_id=i9.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Item with ID {i9.id} not found"
    # Then 4
    assert snap(db, i9) == before_i9


# [claude] ITS-G-03
def test_its_g_03__id_0_gets_the_404(db, w1, mk_i1):
    """ITS-G-03 — id 0 gets the 404.
    Rules: `get_item` R1, Errors row 1"""
    mk_i1()
    commit_point(db)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.get_item(db, item_id=0, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Item with ID 0 not found"


# [claude] ITS-G-04
@pytest.mark.xfail(strict=True, reason="BUG-937: `get_item` returns deleted items")
def test_its_g_04__a_deleted_item_is_hidden_by_default(db, w1, mk_ix):
    """ITS-G-04 — a deleted item is hidden by default.
    Rules: `get_item` R2 [BUG-937], Errors row 1"""
    ix = mk_ix()
    commit_point(db)
    before_ix = snap_before(db, ix)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.get_item(db, item_id=ix.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Item with ID {ix.id} not found"
    # Then 4
    assert snap(db, ix) == before_ix


# [claude] ITS-G-05
@pytest.mark.xfail(strict=True, reason="BUG-937: `get_item` returns deleted items")
def test_its_g_05__include_deleted_true_returns_a_deleted_item(db, w1, mk_ix):
    """ITS-G-05 — include_deleted=True returns a deleted item.
    Rules: `get_item` R3 [BUG-937]"""
    ix = mk_ix()
    commit_point(db)
    result = svc.get_item(db, item_id=ix.id, workspace_id=w1.id, include_deleted=True)

    # Then 1
    assert result.id == ix.id
    # Then 2
    assert result.is_active is False


# [claude] ITS-G-06
@pytest.mark.xfail(strict=True, reason="BUG-937: `get_item` returns deleted items")
def test_its_g_06__include_deleted_true_does_not_reach_another_workspace(db, w1, mk_i9):
    """ITS-G-06 — include_deleted=True does not reach another workspace.
    Rules: `get_item` R3 [BUG-937], Errors row 1"""
    i9 = mk_i9(is_active=False)
    commit_point(db)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.get_item(db, item_id=i9.id, workspace_id=w1.id, include_deleted=True)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Item with ID {i9.id} not found"


# [claude] ITS-G-07
def test_its_g_07__the_read_neither_commits_nor_rolls_back(db, w1, mk_i1, mk_i2, mk_item):
    """ITS-G-07 — the read neither commits nor rolls back.
    Rules: `get_item` R4; TC6"""
    i1 = mk_i1()
    i2 = mk_i2()
    commit_point(db)
    mk_item("Pending", "pending")
    i2.name = "Edited"
    result = svc.get_item(db, item_id=i1.id, workspace_id=w1.id)

    # Then 1
    assert result.id == i1.id
    # Then 2
    assert i2 in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    # Then 4
    assert count_rows(db, "items", name="Pending") == 1
    db.rollback()
    # Then 5
    assert count_rows(db, "items", name="Pending") == 0
    # Then 6
    assert reread(db, i2).name == "Washer Ten"


# --------------------------------------------------------------------------- #
# ItemService.get_items_page
# --------------------------------------------------------------------------- #

# [claude] ITS-P-01
def test_its_p_01__the_page_holds_the_workspaces_live_items_with_total_and_paging(db, w1, mk_i1, mk_i2, mk_ix, mk_i9):
    """ITS-P-01 — the page holds the workspace's live items with total and paging values.
    Rules: `get_items_page` R1, R4"""
    i1 = mk_i1()
    i2 = mk_i2()
    mk_ix()
    mk_i9()
    commit_point(db)
    result = svc.get_items_page(db, workspace_id=w1.id)

    # Then 1
    assert ids(result.items) == [i1.id, i2.id]
    # Then 2
    assert result.total == 2
    # Then 3
    assert result.skip == 0
    assert result.limit == 100
    # Then 4
    assert result.has_more is False


# [claude] ITS-P-02
def test_its_p_02__search_reaches_the_list_and_the_count_limit_reaches_the_list(db, w1, mk_i1, mk_i2, mk_item):
    """ITS-P-02 — search reaches the list and the count; limit reaches the list.
    Rules: `get_items_page` R1, R4"""
    i1 = mk_i1()
    mk_i2()
    i3 = mk_item("Bolt M10", "bolt m10")
    commit_point(db)
    result = svc.get_items_page(db, workspace_id=w1.id, search="bolt", skip=0, limit=1)

    # Then 1
    assert len(result.items) == 1
    # Then 2
    assert result.items[0].id in (i1.id, i3.id)
    # Then 3
    assert result.total == 2
    # Then 4
    assert result.has_more is True


# [claude] ITS-P-03
def test_its_p_03__unit_reaches_the_list_and_the_count(db, w1, mk_i1, mk_i2):
    """ITS-P-03 — unit reaches the list and the count.
    Rules: `get_items_page` R1"""
    mk_i1()
    i2 = mk_i2(unit="kg")
    commit_point(db)
    result = svc.get_items_page(db, workspace_id=w1.id, unit="kg")

    # Then 1
    assert ids(result.items) == [i2.id]
    # Then 2
    assert result.total == 1


# [claude] ITS-P-04
def test_its_p_04__tag_ids_reach_the_list_and_the_count(db, w1, mk_i1, mk_i2, mk_t1, mk_link):
    """ITS-P-04 — tag_ids reach the list and the count.
    Rules: `get_items_page` R1"""
    mk_i1()
    i2 = mk_i2()
    t1 = mk_t1()
    mk_link(i2, t1)
    commit_point(db)
    result = svc.get_items_page(db, workspace_id=w1.id, tag_ids=[t1.id])

    # Then 1
    assert ids(result.items) == [i2.id]
    # Then 2
    assert result.total == 1


# [claude] ITS-P-05
def test_its_p_05__the_last_page_exactly_reaching_the_total_has_no_more(db, w1, mk_i1, mk_i2):
    """ITS-P-05 — the last page exactly reaching the total has no more.
    Rules: `get_items_page` R4"""
    mk_i1()
    mk_i2()
    commit_point(db)
    result = svc.get_items_page(db, workspace_id=w1.id, skip=1, limit=1)

    # Then 1
    assert len(result.items) == 1
    # Then 2
    assert result.total == 2
    # Then 3
    assert result.skip == 1
    assert result.limit == 1
    # Then 4
    assert result.has_more is False


# [claude] ITS-P-06
def test_its_p_06__skip_past_the_end_gives_an_empty_page_with_no_more(db, w1, mk_i1, mk_i2):
    """ITS-P-06 — skip past the end gives an empty page with no more.
    Rules: `get_items_page` R4"""
    mk_i1()
    mk_i2()
    commit_point(db)
    result = svc.get_items_page(db, workspace_id=w1.id, skip=5, limit=1000)

    # Then 1
    assert result.items == []
    # Then 2
    assert result.total == 2
    # Then 3
    assert result.skip == 5
    assert result.limit == 1000
    # Then 4
    assert result.has_more is False


# [claude] ITS-P-07
def test_its_p_07__limit_0_gives_an_empty_page_that_has_more(db, w1, mk_i1, mk_i2):
    """ITS-P-07 — limit=0 gives an empty page that has more.
    Rules: `get_items_page` R4"""
    mk_i1()
    mk_i2()
    commit_point(db)
    result = svc.get_items_page(db, workspace_id=w1.id, limit=0)

    # Then 1
    assert result.items == []
    # Then 2
    assert result.total == 2
    # Then 3
    assert result.has_more is True


# [claude] ITS-P-08
def test_its_p_08__limit_0_on_an_empty_workspace_has_no_more(db, w1):
    """ITS-P-08 — limit=0 on an empty workspace has no more.
    Rules: `get_items_page` R4"""
    commit_point(db)
    result = svc.get_items_page(db, workspace_id=w1.id, limit=0)

    # Then 1
    assert result.items == []
    # Then 2
    assert result.total == 0
    # Then 3
    assert result.has_more is False


# [claude] ITS-P-09
def test_its_p_09__each_tag_is_a_dict_with_exactly_six_keys(db, w1, mk_i1, mk_i2, mk_t1, mk_link):
    """ITS-P-09 — each tag is a dict with exactly six keys; an item without tags has [].
    Rules: `get_items_page` R2"""
    i1 = mk_i1()
    i2 = mk_i2()
    t1 = mk_t1(color="#3366FF", icon="wrench")
    mk_link(i1, t1)
    commit_point(db)
    result = svc.get_items_page(db, workspace_id=w1.id)

    # Then 1
    assert [r for r in result.items if r.id == i1.id][0].tags == [{  # noqa: RUF015  (the card's expression)
        "id": t1.id, "name": "Spare Part", "tag_code": "spare_part", "color": "#3366FF", "icon": "wrench",
        "is_system_tag": False,
    }]
    # Then 2
    assert [r for r in result.items if r.id == i2.id][0].tags == []  # noqa: RUF015  (the card's expression)


# [claude] ITS-P-10
def test_its_p_10__each_listed_item_carries_its_rows_values(db, w1, u1, u2, mk_i1):
    """ITS-P-10 — each listed item carries its row's values.
    Rules: `get_items_page` R3"""
    i1 = mk_i1(
        description="Zinc plated", sku="B-M8", unit="box", updated_by=u2.id,
        updated_at=datetime(2026, 2, 3, 4, 5, 6),  # noqa: DTZ001  (the card's naive stamp)
    )
    commit_point(db)
    result = svc.get_items_page(db, workspace_id=w1.id)

    # Then 1
    assert len(result.items) == 1
    # Then 2
    assert result.items[0].id == i1.id
    assert result.items[0].workspace_id == w1.id
    assert result.items[0].name == "Bolt M8"
    # Then 3
    assert result.items[0].description == "Zinc plated"
    assert result.items[0].sku == "B-M8"
    assert result.items[0].unit == "box"
    # Then 4
    assert result.items[0].is_active is True
    assert result.items[0].created_by == u1.id
    # Then 5
    assert result.items[0].updated_by == u2.id
    # Then 6
    assert result.items[0].created_at is not None
    # Then 7
    assert result.items[0].updated_at.replace(tzinfo=None) == datetime(2026, 2, 3, 4, 5, 6)  # noqa: DTZ001
    # Then 8
    assert result.items[0].item_type == "physical"


# [claude] ITS-P-11
@pytest.mark.xfail(strict=True, reason='BUG-1573: The catalog list shows every item as "physical"')
def test_its_p_11__a_service_item_is_listed_with_item_type_service(db, w1, mk_item):
    """ITS-P-11 — a service item is listed with item_type "service".
    Rules: `get_items_page` R3 [BUG-1573]"""
    r = mk_item("Repair", "repair", item_type="service")
    commit_point(db)
    result = svc.get_items_page(db, workspace_id=w1.id)

    # Then 1
    assert [x.id for x in result.items] == [r.id]
    # Then 2
    assert result.items[0].item_type == "service"


# [claude] ITS-P-12
@pytest.mark.xfail(strict=True, reason="BUG-012: Catalog search with non-ASCII digits (e.g. `²`) crashes")
def test_its_p_12__pass_through_bug_012_a_search_with_a_non_ascii_digit_does_not_raise(db, w1, mk_item, mk_i2):
    """ITS-P-12 — pass-through BUG-012: a search with a non-ASCII digit does not raise.
    Rules: `get_items_page` R1 [BUG-012]"""
    a = mk_item("Sheet 2 m²", "sheet 2m")
    mk_i2()
    commit_point(db)
    result = svc.get_items_page(db, workspace_id=w1.id, search="²")

    # Then 1
    assert ids(result.items) == [a.id]
    # Then 2
    assert result.total == 1


# [claude] ITS-P-13
@pytest.mark.xfail(strict=True, reason="BUG-013: `%` and `_` in catalog search act as wildcards")
def test_its_p_13__pass_through_bug_013_underscore_in_a_search_matches_literally(db, w1, mk_item):
    """ITS-P-13 — pass-through BUG-013: "_" in a search matches literally.
    Rules: `get_items_page` R1 [BUG-013]"""
    a = mk_item("snake_case bolt", "snake_case bolt")
    mk_item("Plain Bar", "plain bar")
    commit_point(db)
    result = svc.get_items_page(db, workspace_id=w1.id, search="_")

    # Then 1
    assert ids(result.items) == [a.id]
    # Then 2
    assert result.total == 1


# [claude] ITS-P-14
@pytest.mark.xfail(strict=True, reason="BUG-014: Filtering by a deleted tag still returns items")
def test_its_p_14__pass_through_bug_014_a_deleted_tag_does_not_filter(db, w1, mk_td, mk_i1, mk_link, mk_i2):
    """ITS-P-14 — pass-through BUG-014: a deleted tag does not filter.
    Rules: `get_items_page` R1 [BUG-014]"""
    td = mk_td()
    a = mk_i1()
    mk_link(a, td)
    mk_i2()
    commit_point(db)
    result = svc.get_items_page(db, workspace_id=w1.id, tag_ids=[td.id])

    # Then 1
    assert result.items == []
    # Then 2
    assert result.total == 0


# [claude] ITS-P-15
@pytest.mark.xfail(strict=True, reason="BUG-015: Catalog search matches names of deleted tags")
def test_its_p_15__pass_through_bug_015_a_deleted_tags_name_does_not_match_a_search(db, w1, mk_td, mk_i1, mk_link):
    """ITS-P-15 — pass-through BUG-015: a deleted tag's name does not match a search.
    Rules: `get_items_page` R1 [BUG-015]"""
    td = mk_td()
    a = mk_i1()
    mk_link(a, td)
    commit_point(db)
    result = svc.get_items_page(db, workspace_id=w1.id, search="obsol")

    # Then 1
    assert result.items == []
    # Then 2
    assert result.total == 0


# [claude] ITS-P-16
@pytest.mark.xfail(strict=True, reason="BUG-033: Catalog item list ordered by `id` instead of name")
def test_its_p_16__pass_through_bug_033_items_come_by_name_case_insensitively(db, w1, mk_item):
    """ITS-P-16 — pass-through BUG-033: items come by name case-insensitively.
    Rules: `get_items_page` R1 [BUG-033]"""
    mk_item("Zulu", "zulu")
    mk_item("Mike", "mike")
    mk_item("alpha", "alpha")
    commit_point(db)
    result = svc.get_items_page(db, workspace_id=w1.id)

    # Then 1
    assert len(result.items) == 3
    # Then 2
    assert [r.name for r in result.items] == ["alpha", "Mike", "Zulu"]


# [claude] ITS-P-17
@pytest.mark.xfail(strict=False, reason="BUG-933: Item list tag chips sorted by collation name with no tie-break")
def test_its_p_17__pass_through_bug_933_an_items_tags_come_by_name_then_id(db, w1, mk_i1, mk_tag, mk_link):
    """ITS-P-17 — pass-through BUG-933: an item's tags come by name case-insensitively, then id.
    Rules: `get_items_page` R2 [BUG-933]"""
    i1 = mk_i1()
    k1 = mk_tag("bravo", "bravo")
    k2 = mk_tag("Alpha", "alpha_upper")
    k3 = mk_tag("alpha", "alpha_lower")
    mk_link(i1, k1)
    mk_link(i1, k2)
    mk_link(i1, k3)
    commit_point(db)
    result = svc.get_items_page(db, workspace_id=w1.id)

    # Then 1
    assert sorted(t["id"] for t in result.items[0].tags) == [k1.id, k2.id, k3.id]
    # Then 2
    assert [t["id"] for t in result.items[0].tags] == [k2.id, k3.id, k1.id]


# [claude] ITS-P-18
def test_its_p_18__the_page_read_neither_commits_nor_rolls_back(db, w1, mk_i1, mk_i9, mk_item):
    """ITS-P-18 — the page read neither commits nor rolls back.
    Rules: `get_items_page` R5; TC6"""
    i1 = mk_i1()
    i9 = mk_i9()
    commit_point(db)
    p = mk_item("Pending", "pending")
    i9.name = "Edited"
    result = svc.get_items_page(db, workspace_id=w1.id)

    # Then 1
    assert ids(result.items) == sorted([i1.id, p.id])
    # Then 2
    assert i9 in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    db.rollback()
    # Then 4
    assert count_rows(db, "items", name="Pending") == 0
    # Then 5
    assert reread(db, i9).name == "Far Spring"


# --------------------------------------------------------------------------- #
# ItemService.get_distinct_units
# --------------------------------------------------------------------------- #

# [claude] ITS-N-01
def test_its_n_01__the_workspaces_units_come_back_as_the_manager_gives_them(db, w1, mk_i1, mk_i2, mk_i9):
    """ITS-N-01 — the workspace's units come back as the manager gives them.
    Rules: `get_distinct_units` R1"""
    mk_i1()
    mk_i2(unit="kg")
    mk_i9(unit="ltr")
    commit_point(db)
    result = svc.get_distinct_units(db, workspace_id=w1.id)

    # Then 1
    assert sorted(result) == ["kg", "pcs"]


# [claude] ITS-N-02
@pytest.mark.xfail(strict=True, reason="BUG-017: Unit list and unit filter treat each spelling separately")
def test_its_n_02__pass_through_bug_017_one_unit_in_three_spellings_is_listed_once(db, w1, mk_i1, mk_i2, mk_item):
    """ITS-N-02 — pass-through BUG-017: one unit in three spellings is listed once, lower case.
    Rules: `get_distinct_units` R1 [BUG-017]"""
    mk_i1(unit="kg")
    mk_i2(unit="Kg")
    mk_item("Pin", "pin", unit="KG")
    commit_point(db)
    result = svc.get_distinct_units(db, workspace_id=w1.id)

    # Then 1
    assert result == ["kg"]


# [claude] ITS-N-03
def test_its_n_03__the_unit_read_neither_commits_nor_rolls_back(db, w1, mk_i1, mk_i9, mk_item):
    """ITS-N-03 — the unit read neither commits nor rolls back.
    Rules: `get_distinct_units` R1; TC6"""
    mk_i1()
    i9 = mk_i9()
    commit_point(db)
    mk_item("Pending", "pending", unit="box")
    i9.name = "Edited"
    result = svc.get_distinct_units(db, workspace_id=w1.id)

    # Then 1
    assert sorted(result) == ["box", "pcs"]
    # Then 2
    assert i9 in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    db.rollback()
    # Then 4
    assert count_rows(db, "items", name="Pending") == 0
    # Then 5
    assert reread(db, i9).name == "Far Spring"


# --------------------------------------------------------------------------- #
# ItemService.get_similar_items
# --------------------------------------------------------------------------- #

# [claude] ITS-S-01
def test_its_s_01__the_query_is_echoed_untrimmed_normalized_and_the_match_comes_back(db, w1, mk_item):
    """ITS-S-01 — the query is echoed untrimmed, normalized, and the manager's match comes back.
    Rules: `get_similar_items` R1, R2"""
    b = mk_item("Bolt", "bolt")
    commit_point(db)
    result = svc.get_similar_items(db, workspace_id=w1.id, name="  BOLT ")

    # Then 1
    assert result.query == "  BOLT "
    # Then 2
    assert result.normalized_query == "bolt"
    # Then 3
    assert len(result.matches) == 1
    # Then 4
    assert result.matches[0].id == b.id
    assert result.matches[0].name == "Bolt"
    # Then 5
    assert result.matches[0].match_type == "exact_normalized"
    assert result.matches[0].similarity_score == 1.0


# [claude] ITS-S-02
def test_its_s_02__a_name_of_punctuation_normalizes_to_empty_and_finds_nothing(db, w1, mk_item):
    """ITS-S-02 — a name of punctuation normalizes to "" and finds nothing.
    Rules: `get_similar_items` R2"""
    mk_item("Bolt", "bolt")
    commit_point(db)
    result = svc.get_similar_items(db, workspace_id=w1.id, name="!!")

    # Then 1
    assert result.query == "!!"
    # Then 2
    assert result.normalized_query == ""
    # Then 3
    assert result.matches == []


# [claude] ITS-S-03
def test_its_s_03__exclude_item_id_reaches_the_manager(db, w1, mk_item):
    """ITS-S-03 — exclude_item_id reaches the manager.
    Rules: `get_similar_items` R1"""
    b1 = mk_item("Bolt", "bolt")
    b2 = mk_item("Bolt ", "bolt")
    commit_point(db)
    result = svc.get_similar_items(db, workspace_id=w1.id, name="bolt", exclude_item_id=b1.id)

    # Then 1
    assert [m.id for m in result.matches] == [b2.id]


# [claude] ITS-S-04
def test_its_s_04__limit_reaches_the_manager(db, w1, mk_item):
    """ITS-S-04 — limit reaches the manager.
    Rules: `get_similar_items` R1"""
    mk_item("Bolt", "bolt")
    mk_item("Bolt ", "bolt")
    mk_item("BOLT", "bolt")
    commit_point(db)
    result = svc.get_similar_items(db, workspace_id=w1.id, name="bolt", limit=2)

    # Then 1
    assert len(result.matches) == 2


# [claude] ITS-S-05
@pytest.mark.xfail(strict=True, reason="BUG-034: Similarity score of exactly 0.35 excluded")
def test_its_s_05__pass_through_bug_034_a_score_of_exactly_0_35_is_included(db, w1, mk_item):
    """ITS-S-05 — pass-through BUG-034: a score of exactly 0.35 is included.
    Rules: `get_similar_items` R1 [BUG-034]"""
    q = mk_item("Qa", "abcdefghijklmnopqr")
    commit_point(db)
    result = svc.get_similar_items(db, workspace_id=w1.id, name="abcdefg")

    # Then 1
    assert len(result.matches) == 1
    # Then 2
    assert result.matches[0].id == q.id
    assert result.matches[0].similarity_score == 0.35


# [claude] ITS-S-06
@pytest.mark.xfail(strict=False, reason="BUG-018: Similar-name suggestions with tied scores in no fixed order")
def test_its_s_06__pass_through_bug_018_equal_scores_come_by_name_then_id(db, w1, mk_item):
    """ITS-S-06 — pass-through BUG-018: equal scores come by name case-insensitively, then id.
    Rules: `get_similar_items` R1 [BUG-018]"""
    mk_item("delta", "steel rod 22m")
    mk_item("Bravo", "steel rod 22m")
    mk_item("alpha", "steel rod 22m")
    commit_point(db)
    result = svc.get_similar_items(db, workspace_id=w1.id, name="Steel Rod 22m")

    # Then 1
    assert len(result.matches) == 3
    # Then 2
    assert [m.name for m in result.matches] == ["alpha", "Bravo", "delta"]


# [claude] ITS-S-07
def test_its_s_07__the_similar_name_read_neither_commits_nor_rolls_back(db, w1, mk_item, mk_i9):
    """ITS-S-07 — the similar-name read neither commits nor rolls back.
    Rules: `get_similar_items` R3; TC6"""
    b = mk_item("Bolt", "bolt")
    i9 = mk_i9()
    commit_point(db)
    mk_item("Pending", "pending")
    i9.name = "Edited"
    result = svc.get_similar_items(db, workspace_id=w1.id, name="bolt")

    # Then 1
    assert [m.id for m in result.matches] == [b.id]
    # Then 2
    assert i9 in db.dirty
    # Then 3
    assert len(db.dirty) == 1
    db.rollback()
    # Then 4
    assert count_rows(db, "items", name="Pending") == 0
    # Then 5
    assert reread(db, i9).name == "Far Spring"


# [claude] ITS-S-08
def test_its_s_08__without_limit_6_matching_items_give_exactly_5_of_them(db, w1, mk_item):
    """ITS-S-08 — without limit, 6 matching items give exactly 5 of them.
    Rules: `get_similar_items` R1a"""
    b1 = mk_item("Bolt A", "bolt")
    b2 = mk_item("Bolt B", "bolt")
    b3 = mk_item("Bolt C", "bolt")
    b4 = mk_item("Bolt D", "bolt")
    b5 = mk_item("Bolt E", "bolt")
    b6 = mk_item("Bolt F", "bolt")
    commit_point(db)
    result = svc.get_similar_items(db, workspace_id=w1.id, name="bolt")

    # Then 1
    assert len(result.matches) == 5
    # Then 2
    assert len({m.id for m in result.matches}) == 5
    # Then 3
    assert {m.id for m in result.matches} <= {b1.id, b2.id, b3.id, b4.id, b5.id, b6.id}


# --------------------------------------------------------------------------- #
# ItemService.update_item
# --------------------------------------------------------------------------- #

# [claude] ITS-U-01
def test_its_u_01__a_rename_is_committed_and_returned_re_read(db, w1, u1, u2, mk_i1):
    """ITS-U-01 — a rename is committed and returned re-read.
    Rules: `update_item` R1, Returns; TC1, TC2"""
    i1 = mk_i1()
    commit_point(db)
    result = svc.update_item(db, item_id=i1.id, item_in=ItemUpdate(name="Lock Nut"), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    for column in ("updated_at", "updated_by", "name"):
        assert column not in unloaded(result)
    # Then 2
    assert result.id == i1.id
    # Then 3
    assert result.name == "Lock Nut"
    assert result.updated_by == u2.id
    assert result.updated_at is not None
    db.rollback()
    # Then 4
    row = reread(db, i1)
    assert row.name == "Lock Nut"
    assert row.name_normalized == "lock nut"
    assert row.updated_by == u2.id
    assert row.updated_at is not None
    # Then 5
    row = reread(db, i1)
    assert row.created_by == u1.id
    assert row.is_active is True


# [claude] ITS-U-02
def test_its_u_02__an_unknown_user_the_integrityerror_passes_unchanged(db, w1, mk_i1, mk_item):
    """ITS-U-02 — an unknown user: the IntegrityError passes unchanged, the session is rolled back.
    Rules: `update_item` R3; TC3"""
    i1 = mk_i1()
    commit_point(db)
    before_i1 = snap_before(db, i1)
    before = written(db)
    mk_item("Extra", "extra")
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        svc.update_item(
            db, item_id=i1.id, item_in=ItemUpdate(name="Lock Nut"), workspace_id=w1.id, user_id=MISSING,
        )
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    assert count_rows(db, "items", name="Extra") == 0
    # Then 4
    assert snap(db, i1) == before_i1
    # Then 5
    assert written(db) == before
    # Then 6
    assert usable(db)


# [claude] ITS-U-03
@pytest.mark.xfail(strict=True, reason="BUG-940: Editing a missing item or deleting an item twice answers 500")
def test_its_u_03__the_managers_not_found_valueerror_becomes_notfounderror_404(db, w1, u2, mk_i1, mk_item):
    """ITS-U-03 — the manager's not-found ValueError becomes NotFoundError 404 with the service's text.
    Rules: `update_item` R2 [BUG-940]"""
    i1 = mk_i1()
    commit_point(db)
    before_i1 = snap_before(db, i1)
    mk_item("Extra", "extra")
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with patch.object(svc.item_manager, "update_item", side_effect=ValueError(f"Item {i1.id} not found")):
            svc.update_item(
                db, item_id=i1.id, item_in=ItemUpdate(name="Lock Nut"), workspace_id=w1.id, user_id=u2.id,
            )
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Item with ID {i1.id} not found"
    # Then 4
    assert count_rows(db, "items", name="Extra") == 0
    # Then 5
    assert snap(db, i1) == before_i1


# [claude] ITS-U-04
@pytest.mark.xfail(strict=True, reason="BUG-940: Editing a missing item or deleting an item twice answers 500")
def test_its_u_04__end_to_end_a_missing_item_gets_the_404(db, w1, u2, mk_i1):
    """ITS-U-04 — end to end: a missing item gets the 404.
    Rules: `update_item` R2 [BUG-940]"""
    i1 = mk_i1()
    commit_point(db)
    before_i1 = snap_before(db, i1)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.update_item(db, item_id=MISSING, item_in=ItemUpdate(name="Lock Nut"), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Item with ID 999999999 not found"
    # Then 4
    assert snap(db, i1) == before_i1


# [claude] ITS-U-05
@pytest.mark.xfail(strict=True, reason="BUG-941: Other-workspace item reported differently from a missing one")
def test_its_u_05__end_to_end_another_workspaces_item_gets_the_same_404(db, w1, u2, mk_i9):
    """ITS-U-05 — end to end: another workspace's item gets the same 404.
    Rules: `update_item` R2 [BUG-941]"""
    i9 = mk_i9()
    commit_point(db)
    before_i9 = snap_before(db, i9)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.update_item(db, item_id=i9.id, item_in=ItemUpdate(name="Lock Nut"), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Item with ID {i9.id} not found"
    # Then 4
    assert snap(db, i9) == before_i9


# [claude] ITS-U-06
@pytest.mark.xfail(strict=True, reason="BUG-938: Deleted items can still be edited and tagged")
def test_its_u_06__end_to_end_a_deleted_item_gets_the_404_and_is_not_changed(db, w1, u2, mk_ix):
    """ITS-U-06 — end to end: a deleted item gets the 404 and is not changed.
    Rules: `update_item` R2 [BUG-938]"""
    ix = mk_ix()
    commit_point(db)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.update_item(db, item_id=ix.id, item_in=ItemUpdate(name="Lock Nut"), workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Item with ID {ix.id} not found"
    db.rollback()
    # Then 4
    row = reread(db, ix)
    assert row.name == "Old Rivet"
    assert row.updated_by is None


# [claude] ITS-U-07
def test_its_u_07__a_valueerror_with_another_text_is_not_translated(db, w1, u2, mk_i1):
    """ITS-U-07 — a ValueError with another text is not translated.
    Rules: `update_item` R3"""
    i1 = mk_i1()
    commit_point(db)
    before_i1 = snap_before(db, i1)
    with pytest.raises(ValueError) as exc:
        with patch.object(svc.item_manager, "update_item", side_effect=ValueError("something else")):
            svc.update_item(
                db, item_id=i1.id, item_in=ItemUpdate(name="Lock Nut"), workspace_id=w1.id, user_id=u2.id,
            )
    # Then 1
    assert type(exc.value) is ValueError
    # Then 2
    assert exc.value.args == ("something else",)
    # Then 3
    assert snap(db, i1) == before_i1


# [claude] ITS-U-08
@pytest.mark.xfail(strict=True, reason="BUG-939: `updated_by` stamped on no-op item updates")
def test_its_u_08__pass_through_bug_939_an_empty_update_does_not_stamp_the_item(db, w1, u2, mk_i1):
    """ITS-U-08 — pass-through BUG-939: an empty update does not stamp the item.
    Rules: `update_item` R1 [BUG-939]"""
    i1 = mk_i1()
    commit_point(db)
    result = svc.update_item(db, item_id=i1.id, item_in=ItemUpdate(), workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == i1.id
    db.rollback()
    # Then 2
    assert reread(db, i1).updated_by is None


# [claude] ITS-U-09
@pytest.mark.xfail(strict=True, reason="BUG-934: Saving an item's tags deletes and re-creates unchanged tag links")
def test_its_u_09__pass_through_bug_934_a_tag_that_stays_keeps_its_link(db, w1, u1, u2, mk_i1, mk_t1, mk_tag, mk_link):
    """ITS-U-09 — pass-through BUG-934: a tag that stays keeps its link.
    Rules: `update_item` R1 [BUG-934]"""
    i1 = mk_i1()
    t1 = mk_t1(usage_count=4)
    t2 = mk_tag("Galvanized", "galvanized", usage_count=6)
    l1 = mk_link(i1, t1)
    mk_link(i1, t2)
    l1_id = l1.id
    commit_point(db)
    result = svc.update_item(
        db, item_id=i1.id, item_in=ItemUpdate(tag_ids=[t1.id]), workspace_id=w1.id, user_id=u2.id,
    )

    # Then 1
    assert result.id == i1.id
    db.rollback()
    # Then 2
    assert tag_ids_of(db, i1.id) == [t1.id]
    # Then 3
    link = db.execute(select(ItemTagAssignment).where(
        ItemTagAssignment.item_id == i1.id, ItemTagAssignment.tag_id == t1.id,
    )).scalar_one()
    assert link.id == l1_id
    assert link.assigned_by == u1.id


# [claude] ITS-U-10
@pytest.mark.xfail(strict=True, reason="BUG-935: Saving an item's tags erases its links to deleted tags")
def test_its_u_10__pass_through_bug_935_a_tag_save_keeps_the_link_to_a_deleted_tag(
    db, w1, u2, mk_i1, mk_t1, mk_td, mk_link,
):
    """ITS-U-10 — pass-through BUG-935: a tag save keeps the link to a deleted tag.
    Rules: `update_item` R1 [BUG-935]"""
    i1 = mk_i1()
    t1 = mk_t1(usage_count=4)
    td = mk_td(usage_count=7)
    mk_link(i1, t1)
    mk_link(i1, td)
    commit_point(db)
    result = svc.update_item(
        db, item_id=i1.id, item_in=ItemUpdate(tag_ids=[t1.id]), workspace_id=w1.id, user_id=u2.id,
    )

    # Then 1
    assert result.id == i1.id
    db.rollback()
    # Then 2
    assert tag_ids_of(db, i1.id) == sorted([t1.id, td.id])


# [claude] ITS-U-11
@pytest.mark.xfail(strict=True, reason="BUG-942: Item description and SKU cannot be cleared")
def test_its_u_11__pass_through_bug_942_an_explicit_null_clears_the_description(db, w1, u2, mk_i1):
    """ITS-U-11 — pass-through BUG-942: an explicit null clears the description.
    Rules: `update_item` R1 [BUG-942]"""
    i1 = mk_i1(description="Zinc plated")
    commit_point(db)
    result = svc.update_item(
        db, item_id=i1.id, item_in=ItemUpdate(description=None), workspace_id=w1.id, user_id=u2.id,
    )

    # Then 1
    assert result.id == i1.id
    db.rollback()
    # Then 2
    assert reread(db, i1).description is None


# [claude] ITS-U-12
@pytest.mark.xfail(
    strict=True, reason="BUG-947: Item edit request can delete / restore an item, bypassing tag counters",
)
def test_its_u_12__pass_through_bug_947_is_active_sent_with_an_edit_is_ignored(db, w1, u2, mk_i1):
    """ITS-U-12 — pass-through BUG-947: is_active sent with an edit is ignored.
    Rules: `update_item` R1 [BUG-947]"""
    i1 = mk_i1()
    commit_point(db)
    result = svc.update_item(
        db, item_id=i1.id, item_in=ItemUpdate(name="Lock Nut", is_active=False), workspace_id=w1.id, user_id=u2.id,
    )

    # Then 1
    assert result.id == i1.id
    db.rollback()
    # Then 2
    assert reread(db, i1).name == "Lock Nut"
    # Then 3
    assert reread(db, i1).is_active is True


# --------------------------------------------------------------------------- #
# ItemService.delete_item
# --------------------------------------------------------------------------- #

# [claude] ITS-D-01
def test_its_d_01__a_delete_is_committed_and_none_is_returned(db, w1, u2, mk_i1, mk_t1, mk_link):
    """ITS-D-01 — a delete is committed and None is returned.
    Rules: `delete_item` R5, Returns; TC1"""
    i1 = mk_i1()
    t1 = mk_t1(usage_count=4)
    mk_link(i1, t1)
    commit_point(db)
    result = svc.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    db.rollback()
    # Then 2
    row = reread(db, i1)
    assert row.is_active is False
    assert row.updated_by == u2.id
    assert row.updated_at is not None
    # Then 3
    assert reread(db, i1).name == "Bolt M8"
    # Then 4
    assert stored_count(db, t1) == 3
    # Then 5
    assert tag_ids_of(db, i1.id) == [t1.id]


# [claude] ITS-D-02
def test_its_d_02__a_missing_id_404_the_managers_delete_is_not_called(db, w1, u2, mk_i1, mk_item):
    """ITS-D-02 — a missing id: NotFoundError 404, the manager's delete is not called, the session is rolled back.
    Rules: `delete_item` R1, Errors row 1; TC3"""
    i1 = mk_i1()
    commit_point(db)
    before_i1 = snap_before(db, i1)
    mk_item("Extra", "extra")
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with patch.object(svc.item_manager, "delete_item", wraps=svc.item_manager.delete_item) as spy:
            svc.delete_item(db, item_id=MISSING, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Item with ID 999999999 not found"
    # Then 4
    assert spy.call_count == 0
    # Then 5
    assert count_rows(db, "items", name="Extra") == 0
    # Then 6
    assert snap(db, i1) == before_i1
    # Then 7
    assert usable(db)


# [claude] ITS-D-03
def test_its_d_03__another_workspaces_item_gets_the_404(db, w1, u2, mk_i1, mk_i9):
    """ITS-D-03 — another workspace's item gets the 404.
    Rules: `delete_item` R1, Errors row 1"""
    mk_i1()
    i9 = mk_i9()
    commit_point(db)
    before_i9 = snap_before(db, i9)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.delete_item(db, item_id=i9.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Item with ID {i9.id} not found"
    # Then 4
    assert snap(db, i9) == before_i9


# [claude] ITS-D-04
@pytest.mark.xfail(strict=True, reason="BUG-937: `get_item` returns deleted items")
def test_its_d_04__end_to_end_a_deleted_item_gets_the_404(db, w1, u2, mk_ix):
    """ITS-D-04 — end to end: a deleted item gets the 404.
    Rules: `delete_item` R2 [BUG-937], Errors row 1"""
    ix = mk_ix()
    commit_point(db)
    before_ix = snap_before(db, ix)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        svc.delete_item(db, item_id=ix.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Item with ID {ix.id} not found"
    # Then 4
    assert snap(db, ix) == before_ix


# [claude] ITS-D-05
@pytest.mark.xfail(strict=True, reason="BUG-940: Editing a missing item or deleting an item twice answers 500")
def test_its_d_05__the_managers_already_deleted_valueerror_becomes_validationerror_400(db, w1, u2, mk_i1):
    """ITS-D-05 — the manager's already-deleted ValueError becomes ValidationError 400.
    Rules: `delete_item` R3 [BUG-940], Errors row 2"""
    i1 = mk_i1()
    commit_point(db)
    before_i1 = snap_before(db, i1)
    # Then 1
    with pytest.raises(AppValidationError) as exc:
        with patch.object(svc.item_manager, "delete_item", side_effect=ValueError(f"Item {i1.id} is already deleted")):
            svc.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == f"Item {i1.id} is already deleted"
    # Then 4
    assert snap(db, i1) == before_i1


# [claude] ITS-D-06
@pytest.mark.xfail(strict=True, reason="BUG-940: Editing a missing item or deleting an item twice answers 500")
def test_its_d_06__the_managers_not_found_valueerror_becomes_the_404(db, w1, u2, mk_i1):
    """ITS-D-06 — the manager's not-found ValueError becomes the 404.
    Rules: `delete_item` R3 [BUG-940], Errors row 1"""
    i1 = mk_i1()
    commit_point(db)
    before_i1 = snap_before(db, i1)
    # Then 1
    with pytest.raises(NotFoundError) as exc:
        with patch.object(svc.item_manager, "delete_item", side_effect=ValueError(f"Item {i1.id} not found")):
            svc.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == f"Item with ID {i1.id} not found"
    # Then 4
    assert snap(db, i1) == before_i1


# [claude] ITS-D-07
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_its_d_07__the_managers_in_use_valueerror_becomes_the_400_with_the_blockers(db, w1, u2, mk_i1, mk_item):
    """ITS-D-07 — the manager's in-use ValueError becomes the 400 with the blockers as given, after a rollback.
    Rules: `delete_item` R4 [BUG-948], Errors row 3"""
    i1 = mk_i1()
    commit_point(db)
    before_i1 = snap_before(db, i1)
    mk_item("Extra", "extra")
    blockers = [{"type": "work_order", "id": 3}, {"type": "factory_stock", "id": 1}, {"type": "other_workspace"}]
    # Then 1
    with pytest.raises(AppValidationError) as exc:
        with patch.object(
            svc.item_manager, "delete_item", side_effect=ValueError("Item has stock or open orders", blockers),
        ):
            svc.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Item has stock or open orders"
    # Then 4
    assert exc.value.errors == [
        {"type": "work_order", "id": 3}, {"type": "factory_stock", "id": 1}, {"type": "other_workspace"},
    ]
    # Then 5
    assert count_rows(db, "items", name="Extra") == 0
    # Then 6
    assert snap(db, i1) == before_i1


# [claude] ITS-D-08
@pytest.mark.xfail(strict=True, reason="BUG-948: Item with stock or open orders can be deleted")
def test_its_d_08__end_to_end_stock_in_a_factory_blocks_the_delete(db, w1, u2, mk_i1, mk_f1, mk_stock):
    """ITS-D-08 — end to end: stock in a factory blocks the delete with a 400 that lists it.
    Rules: `delete_item` R4 [BUG-948], Errors row 3"""
    i1 = mk_i1()
    f1 = mk_f1()
    sk = mk_stock(i1, f1, qty=400)
    commit_point(db)
    # Then 1
    with pytest.raises(AppValidationError) as exc:
        svc.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 2
    assert exc.value.status_code == 400
    # Then 3
    assert exc.value.detail == "Item has stock or open orders"
    # Then 4
    assert exc.value.errors == [{"type": "factory_stock", "id": sk.id}]
    db.rollback()
    # Then 5
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None


# [claude] ITS-D-09
def test_its_d_09__a_valueerror_with_another_text_is_not_translated_and_the_session_is_rolled_back(
    db, w1, u2, mk_i1, mk_item,
):
    """ITS-D-09 — a ValueError with another text is not translated and the session is rolled back.
    Rules: `delete_item` R6; TC3"""
    i1 = mk_i1()
    commit_point(db)
    before_i1 = snap_before(db, i1)
    mk_item("Extra", "extra")
    with pytest.raises(ValueError) as exc:
        with patch.object(svc.item_manager, "delete_item", side_effect=ValueError("something else", [])):
            svc.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)
    # Then 1
    assert type(exc.value) is ValueError
    # Then 2
    assert exc.value.args == ("something else", [])
    # Then 3
    assert count_rows(db, "items", name="Extra") == 0
    # Then 4
    assert snap(db, i1) == before_i1
    # Then 5
    assert usable(db)


# [claude] ITS-D-10
def test_its_d_10__an_unknown_user_on_an_item_not_in_use_integrityerror_nothing_saved(db, w1, mk_i1, mk_t1, mk_link):
    """ITS-D-10 — an unknown user on an item not in use: the IntegrityError passes unchanged, nothing saved.
    Rules: `delete_item` R6"""
    i1 = mk_i1()
    t1 = mk_t1(usage_count=4)
    mk_link(i1, t1)
    commit_point(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        svc.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=MISSING)
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    db.rollback()
    # Then 3
    row = reread(db, i1)
    assert row.is_active is True
    assert row.updated_by is None
    # Then 4
    assert stored_count(db, t1) == 4
    # Then 5
    assert usable(db)


# [claude] ITS-D-11
@pytest.mark.xfail(strict=True, reason="BUG-945: Deleting an item leaves its deleted tags counting it")
def test_its_d_11__pass_through_bug_945_a_deleted_tag_on_the_item_also_counts_one_less(db, w1, u2, mk_i1, mk_td, mk_link):
    """ITS-D-11 — pass-through BUG-945: a deleted tag on the item also counts one item less.
    Rules: `delete_item` R5 [BUG-945]"""
    i1 = mk_i1()
    td = mk_td(usage_count=9)
    mk_link(i1, td)
    commit_point(db)
    result = svc.delete_item(db, item_id=i1.id, workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result is None
    db.rollback()
    # Then 2
    assert stored_count(db, td) == 8
