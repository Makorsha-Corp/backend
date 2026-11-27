"""Unit tests for app/services/item_tag_service.py.

Implements tests/unit/services/item_tag_service.cases.md (revision 1), one test
per case, in card order. Real Postgres session (`db` fixture): a `commit()` only
releases a savepoint, so the service's commits are safe and the fixture's outer
rollback discards everything. Nothing is patched except what Conventions name:
the failing commit / failing refresh wraps, the commit / rollback spies (both
still call the real method) and the race simulation of ITS-C-29.

Normal mode: every test is written from its card and carries a `# [claude] <ID>`
comment. Row names of the cards are the lower-case names here (K1 -> k1, `W1.id`
-> `w1.id`); `# Then N` marks the checks of the card's Then line N.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with patch.object(...)`)
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.dao.item_tag import item_tag_dao
from app.models.item import Item
from app.models.item_tag import ItemTag
from app.models.item_tag_assignment import ItemTagAssignment
from app.schemas.item_tag import ItemTagCreate, ItemTagResponse, ItemTagUpdate
from app.services.item_tag_service import item_tag_service
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "svc = the singleton item_tag_service"
svc = item_tag_service

MISSING = 999999999

# Convention "BN" (Bengali, "raw material")
BN = "কাঁচামাল"


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# Conventions -> actors and standing rows
# --------------------------------------------------------------------------- #

@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# U1 = the acting user
@pytest.fixture
def u1(db, w2):
    return make_profile(db)


@pytest.fixture
def i1(db, w1, u1):
    return _add(db, Item(workspace_id=w1.id, name="Bolt M8", name_normalized="bolt m8", unit="pcs", is_active=True))


@pytest.fixture
def ix(db, w1, i1):
    return _add(db, Item(
        workspace_id=w1.id, name="Old Rivet", name_normalized="old rivet", unit="pcs", is_active=False,
    ))


# Conventions "Standing rows": in every test, no Given line needed
@pytest.fixture(autouse=True)
def standing_rows(ix):
    pass


# --------------------------------------------------------------------------- #
# Conventions -> Given rows
# --------------------------------------------------------------------------- #

def _tag_fields(w1, name, tag_code, but):
    fields = {
        "workspace_id": w1.id, "name": name, "tag_code": tag_code, "is_system_tag": False, "is_active": True,
        "usage_count": 0, "color": None, "icon": None, "description": None, "created_by": None,
    }
    fields.update(but)
    return fields


# Convention "tag": the card gives name and tag_code; "but" changes other columns
@pytest.fixture
def mk_tag(db, w1):
    def _mk(name, tag_code, **but):
        return _add(db, ItemTag(**_tag_fields(w1, name, tag_code, but)))
    return _mk


# Convention "system tag"
@pytest.fixture
def mk_system_tag(mk_tag):
    def _mk(name, tag_code, **but):
        return mk_tag(name, tag_code, is_system_tag=True, **but)
    return _mk


# Convention "deleted" (of a tag)
DELETED = {"is_active": False}


# Convention "link of I to T"
@pytest.fixture
def mk_link(db, w1, u1):
    def _mk(item, tag):
        return _add(db, ItemTagAssignment(workspace_id=w1.id, item_id=item.id, tag_id=tag.id, assigned_by=u1.id))
    return _mk


# Convention "commit point"
def commit_point(db):
    db.commit()


# --------------------------------------------------------------------------- #
# Conventions -> named checks
# --------------------------------------------------------------------------- #

def _id_of(row):
    return inspect(row).identity[0]


# Convention "re-read X" (any model)
def reread(db, row):
    model, row_id = type(row), _id_of(row)
    db.expire_all()
    return db.execute(select(model).where(model.id == row_id)).scalar_one_or_none()


def _columns(db, row_id):
    table = ItemTag.__table__
    found = db.execute(select(table).where(table.c.id == row_id)).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "unchanged(X)": every column at the commit point ...
def snap_before(db, row):
    return _columns(db, _id_of(row))


# ... and after a re-read
def snap(db, row):
    row_id = _id_of(row)
    db.expire_all()
    return _columns(db, row_id)


# Convention "stored_count(T)": without expiring or refreshing T
def stored_count(db, tag):
    return db.scalar(select(ItemTag.usage_count).where(ItemTag.id == _id_of(tag)))


# Convention "count:" lines: item_tags rows (all workspaces), with the filter stated
def count_tags(db, **filters):
    query = select(func.count()).select_from(ItemTag)
    for column, value in filters.items():
        query = query.where(getattr(ItemTag, column) == value)
    return db.execute(query).scalar_one()


# Convention "nothing written"
def written(db):
    return count_tags(db)


# Convention "the new row": the one item_tags row of W1 whose id is not among the Given rows
def new_row(db, w1, given=()):
    given_ids = [_id_of(row) for row in given]
    db.expire_all()
    query = select(ItemTag).where(ItemTag.workspace_id == w1.id)
    if given_ids:
        query = query.where(ItemTag.id.notin_(given_ids))
    return db.execute(query).scalar_one()


# Convention "ids(x)"
def ids(rows):
    return sorted(t.id for t in rows)


# Convention "loaded:"
def unloaded(result):
    return inspect(result).unloaded


# Convention "session: usable"
def usable(db):
    return db.execute(text("SELECT 1")).scalar() == 1


# Convention "spies": both wrap the real method
@contextmanager
def spies(db):
    with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:
        yield cm, rb


# --------------------------------------------------------------------------- #
# ItemTagService.get_tags
# --------------------------------------------------------------------------- #

# [claude] ITS-T-01
def test_its_t_01__live_tags_of_the_workspace_only_system_tags_first(db, w1, w2, mk_tag, mk_system_tag):
    """ITS-T-01 — live tags of the workspace only, system tags first.
    Rules: `get_tags` R1, R5"""
    k1 = mk_tag("Bolt", "bolt")
    ks = mk_system_tag("Raw Material", "raw_material")
    mk_tag("Obsolete", "obsolete", **DELETED)
    mk_tag("Far Crate", "far_crate", workspace_id=w2.id)
    commit_point(db)
    result = svc.get_tags(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [k1.id, ks.id]
    # Then 2
    assert result[0].id == ks.id


# [claude] ITS-T-02
def test_its_t_02__each_tag_shows_the_number_of_active_items_linked_to_it_no_link_shows_0(
    db, w1, i1, ix, mk_tag, mk_link,
):
    """ITS-T-02 — each tag shows the number of active items linked to it; no link shows 0.
    Rules: `get_tags` R2"""
    k1 = mk_tag("Bolt", "bolt", usage_count=9)
    k2 = mk_tag("Nut", "nut", usage_count=4)
    mk_link(i1, k1)
    mk_link(ix, k1)
    commit_point(db)
    result = svc.get_tags(db, workspace_id=w1.id)

    # Then 1
    assert {t.id: t.usage_count for t in result} == {k1.id: 1, k2.id: 0}


# [claude] ITS-T-03
def test_its_t_03__the_live_count_is_not_saved_or_committed_but_the_objects_stay_changed(
    db, w1, i1, mk_tag, mk_link,
):
    """ITS-T-03 — the live count is not saved or committed, but the objects stay changed.
    Rules: `get_tags` R3"""
    k1 = mk_tag("Bolt", "bolt", usage_count=9)
    mk_link(i1, k1)
    commit_point(db)
    result = svc.get_tags(db, workspace_id=w1.id)

    # Then 1
    assert result[0].usage_count == 1
    # Then 2
    assert k1 in db.dirty
    # Then 3
    assert stored_count(db, k1) == 9
    # Then 4
    db.rollback()
    assert stored_count(db, k1) == 9


# [claude] ITS-T-04
def test_its_t_04__the_list_neither_commits_nor_rolls_back(db, w1, mk_tag):
    """ITS-T-04 — the list neither commits nor rolls back.
    Rules: `get_tags` R5; S4"""
    k1 = mk_tag("Bolt", "bolt")
    commit_point(db)
    p = mk_tag("Pending", "pending")
    with spies(db) as (cm, rb):
        result = svc.get_tags(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [k1.id, p.id]
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    db.rollback()
    assert count_tags(db, tag_code="pending") == 0


# [claude] ITS-T-05
def test_its_t_05__a_stored_tag_with_an_invalid_code_is_still_returned(db, w1, mk_tag):
    """ITS-T-05 — a stored tag with an invalid code is still returned.
    Rules: `get_tags` R4"""
    k1 = mk_tag("Café", "café")
    commit_point(db)
    result = svc.get_tags(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [k1.id]
    # Then 2
    assert result[0].tag_code == "café"


# [claude] ITS-T-06
@pytest.mark.xfail(strict=True, reason="BUG-1532: Some tag names break the whole tag list")
def test_its_t_06__a_stored_tag_with_an_invalid_code_passes_the_response_schema(db, w1, mk_tag):
    """ITS-T-06 — a stored tag with an invalid code passes the response schema.
    Rules: `get_tags` R4 [BUG-1532]"""
    mk_tag("Café", "café")
    commit_point(db)
    result = svc.get_tags(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert ItemTagResponse.model_validate(result[0]).tag_code == "café"


# [claude] ITS-T-07
@pytest.mark.xfail(strict=True, reason="BUG-1532: Some tag names break the whole tag list")
def test_its_t_07__a_stored_tag_with_an_empty_code_passes_the_response_schema(db, w1, mk_tag):
    """ITS-T-07 — a stored tag with an empty code passes the response schema.
    Rules: `get_tags` R4 [BUG-1532]"""
    mk_tag("!!!", "")
    commit_point(db)
    result = svc.get_tags(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert ItemTagResponse.model_validate(result[0]).tag_code == ""


# [claude] ITS-T-08
def test_its_t_08__pass_through_bug_930_names_come_case_insensitive_ascending(db, w1, mk_tag):
    """ITS-T-08 — pass-through BUG-930: names come case-insensitive ascending.
    Rules: `get_tags` R1 [BUG-930]"""
    k1 = mk_tag("bravo", "bravo")
    k2 = mk_tag("Alpha", "alpha")
    k3 = mk_tag("Charlie", "charlie")
    commit_point(db)
    result = svc.get_tags(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [k1.id, k2.id, k3.id]
    # Then 2
    assert [t.name for t in result] == ["Alpha", "bravo", "Charlie"]


# --------------------------------------------------------------------------- #
# ItemTagService.get_system_tags
# --------------------------------------------------------------------------- #

# [claude] ITS-Y-01
def test_its_y_01__the_workspaces_system_tags_only(db, w1, w2, mk_tag, mk_system_tag):
    """ITS-Y-01 — the workspace's system tags only.
    Rules: `get_system_tags` R1"""
    mk_tag("Bolt", "bolt")
    ks = mk_system_tag("Raw Material", "raw_material")
    mk_system_tag("Far Raw", "far_raw", workspace_id=w2.id)
    commit_point(db)
    result = svc.get_system_tags(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [ks.id]


# [claude] ITS-Y-02
def test_its_y_02__usage_count_is_the_stored_counter(db, w1, i1, ix, mk_system_tag, mk_link):
    """ITS-Y-02 — usage_count is the stored counter.
    Rules: `get_system_tags` R2"""
    ks = mk_system_tag("Raw Material", "raw_material", usage_count=9)
    mk_link(i1, ks)
    mk_link(ix, ks)
    commit_point(db)
    result = svc.get_system_tags(db, workspace_id=w1.id)

    # Then 1
    assert result[0].usage_count == 9


# [claude] ITS-Y-03
def test_its_y_03__the_list_neither_commits_nor_rolls_back(db, w1, mk_tag, mk_system_tag):
    """ITS-Y-03 — the list neither commits nor rolls back.
    Rules: `get_system_tags` R3; S4"""
    ks = mk_system_tag("Raw Material", "raw_material")
    commit_point(db)
    mk_tag("Pending", "pending")
    with spies(db) as (cm, rb):
        result = svc.get_system_tags(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [ks.id]
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert count_tags(db, tag_code="pending") == 1
    # Then 5
    db.rollback()
    assert count_tags(db, tag_code="pending") == 0


# [claude] ITS-Y-04
def test_its_y_04__pass_through_bug_929_system_tags_come_by_name_case_insensitive_ascending(
    db, w1, mk_system_tag,
):
    """ITS-Y-04 — pass-through BUG-929: system tags come by name, case-insensitive ascending.
    Rules: `get_system_tags` R1 [BUG-929]"""
    s1 = mk_system_tag("Tool", "tool")
    s2 = mk_system_tag("consumable", "consumable")
    s3 = mk_system_tag("Bolt", "bolt")
    commit_point(db)
    result = svc.get_system_tags(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [s1.id, s2.id, s3.id]
    # Then 2
    assert [t.name for t in result] == ["Bolt", "consumable", "Tool"]


# --------------------------------------------------------------------------- #
# ItemTagService.create_tag
# --------------------------------------------------------------------------- #

# [claude] ITS-C-01
def test_its_c_01__a_sent_tag_code_is_used_as_sent(db, w1, u1):
    """ITS-C-01 — a sent tag_code is used as sent.
    Rules: `create_tag` R1"""
    commit_point(db)
    result = svc.create_tag(db, tag_in=ItemTagCreate(name="Steel", tag_code="metal_1"), workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.tag_code == "metal_1"
    # Then 2
    db.rollback()
    row = new_row(db, w1)
    assert row.tag_code == "metal_1"
    assert row.name == "Steel"


# [claude] ITS-C-02
def test_its_c_02__with_no_code_spaces_become_underscore_and_digits_stay(db, w1, u1):
    """ITS-C-02 — with no code, spaces become _ and digits stay.
    Rules: `create_tag` R2"""
    commit_point(db)
    result = svc.create_tag(db, tag_in=ItemTagCreate(name="Raw Material 2"), workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.tag_code == "raw_material_2"
    # Then 2
    db.rollback()
    assert new_row(db, w1).tag_code == "raw_material_2"


# [claude] ITS-C-03
def test_its_c_03__with_no_code_other_symbols_are_dropped(db, w1, u1):
    """ITS-C-03 — with no code, other symbols are dropped.
    Rules: `create_tag` R2"""
    commit_point(db)
    result = svc.create_tag(db, tag_in=ItemTagCreate(name="Steel-Bar"), workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.tag_code == "steelbar"


# [claude] ITS-C-04
@pytest.mark.xfail(strict=True, reason="BUG-1532: Some tag names break the whole tag list")
def test_its_c_04__a_derived_code_drops_accented_letters(db, w1, u1):
    """ITS-C-04 — a derived code drops accented letters.
    Rules: `create_tag` R3 [BUG-1532]"""
    commit_point(db)
    result = svc.create_tag(db, tag_in=ItemTagCreate(name="Café"), workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.tag_code == "caf"
    # Then 2
    db.rollback()
    assert new_row(db, w1).tag_code == "caf"


# [claude] ITS-C-05
@pytest.mark.xfail(strict=True, reason="BUG-1532: Some tag names break the whole tag list")
def test_its_c_05__a_derived_code_with_nothing_left_is_tag(db, w1, u1):
    """ITS-C-05 — a derived code with nothing left is "tag".
    Rules: `create_tag` R3 [BUG-1532]"""
    commit_point(db)
    result = svc.create_tag(db, tag_in=ItemTagCreate(name="!!!"), workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.tag_code == "tag"


# [claude] ITS-C-06
@pytest.mark.xfail(strict=True, reason="BUG-1532: Some tag names break the whole tag list")
def test_its_c_06__a_derived_code_is_cut_to_50_characters(db, w1, u1):
    """ITS-C-06 — a derived code is cut to 50 characters.
    Rules: `create_tag` R3 [BUG-1532]"""
    commit_point(db)
    result = svc.create_tag(db, tag_in=ItemTagCreate(name="a" * 60), workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.tag_code == "a" * 50


# [claude] ITS-C-07
def test_its_c_07__a_derived_code_of_exactly_50_characters_is_kept_whole(db, w1, u1):
    """ITS-C-07 — a derived code of exactly 50 characters is kept whole.
    Rules: `create_tag` R3"""
    commit_point(db)
    result = svc.create_tag(db, tag_in=ItemTagCreate(name="a" * 50), workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.tag_code == "a" * 50


# [claude] ITS-C-08
@pytest.mark.xfail(strict=True, reason="BUG-1526: Item tag names are stored untrimmed, and blank names are accepted")
def test_its_c_08__a_padded_name_is_stored_trimmed_and_its_code_derived_from_the_trimmed_name(db, w1, u1):
    """ITS-C-08 — a padded name is stored trimmed and its code derived from the trimmed name.
    Rules: `create_tag` R3, R9 [BUG-1526]"""
    data = ItemTagCreate(name=" Bolt ")
    commit_point(db)
    result = svc.create_tag(db, tag_in=data, workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.tag_code == "bolt"
    # Then 2
    db.rollback()
    row = new_row(db, w1)
    assert row.name == "Bolt"
    assert row.tag_code == "bolt"


# [claude] ITS-C-09
@pytest.mark.xfail(strict=True, reason="BUG-1532: Some tag names break the whole tag list")
def test_its_c_09__a_bengali_name_derives_tag(db, w1, u1):
    """ITS-C-09 — a Bengali name derives "tag".
    Rules: `create_tag` R3 [BUG-1532]"""
    commit_point(db)
    result = svc.create_tag(db, tag_in=ItemTagCreate(name=BN), workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.tag_code == "tag"


# [claude] ITS-C-10
@pytest.mark.xfail(strict=True, reason="BUG-1526: Item tag names are stored untrimmed, and blank names are accepted")
def test_its_c_10__a_whitespace_only_name_is_refused_by_the_schema(db, w1):
    """ITS-C-10 — a whitespace-only name is refused by the schema.
    Rules: `create_tag` R9 [BUG-1526], Errors row 3"""
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(PydanticValidationError):
        ItemTagCreate(name="   ")
    # Then 2
    assert written(db) == before


# [claude] ITS-C-11
def test_its_c_11__an_explicit_code_taken_409_nothing_written_and_no_rollback_of_other_changes(
    db, w1, u1, mk_tag,
):
    """ITS-C-11 — an explicit code taken: 409, nothing written, and no rollback of other changes.
    Rules: `create_tag` R4, R7, R11, Errors row 2; S3"""
    k1 = mk_tag("Bolt", "bolt")
    commit_point(db)
    before_k1 = snap_before(db, k1)
    mk_tag("Extra", "extra")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_tag(db, tag_in=ItemTagCreate(name="Screw", tag_code="bolt"), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Tag with code 'bolt' already exists"
    # Then 4
    assert count_tags(db, name="Screw") == 0
    # Then 5
    assert count_tags(db, tag_code="extra") == 1
    # Then 6
    assert snap(db, k1) == before_k1


# [claude] ITS-C-12
def test_its_c_12__the_same_code_in_another_workspace_does_not_block(db, w1, w2, u1, mk_tag):
    """ITS-C-12 — the same code in another workspace does not block.
    Rules: `create_tag` R4"""
    mk_tag("Bolt", "bolt", workspace_id=w2.id)
    commit_point(db)
    result = svc.create_tag(db, tag_in=ItemTagCreate(name="Bolt", tag_code="bolt"), workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.workspace_id == w1.id
    assert result.tag_code == "bolt"
    # Then 2
    db.rollback()
    assert count_tags(db, tag_code="bolt") == 2


# [claude] ITS-C-13
@pytest.mark.xfail(strict=True, reason="BUG-1527: A deleted item tag's code can never be used again")
def test_its_c_13__a_deleted_tags_code_can_be_used_again(db, w1, u1, mk_tag):
    """ITS-C-13 — a deleted tag's code can be used again.
    Rules: `create_tag` R5 [BUG-1527]"""
    kd = mk_tag("Old Bolt", "bolt", **DELETED)
    commit_point(db)
    result = svc.create_tag(db, tag_in=ItemTagCreate(name="Bolt", tag_code="bolt"), workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.id != kd.id
    assert result.tag_code == "bolt"
    # Then 2
    db.rollback()
    assert count_tags(db, workspace_id=w1.id, tag_code="bolt") == 2


# [claude] ITS-C-14
@pytest.mark.xfail(strict=True, reason="BUG-1528: Item tag code uniqueness is not enforced by the database")
def test_its_c_14__the_database_refuses_a_second_live_tag_with_the_same_code(db, w1, mk_tag):
    """ITS-C-14 — the database refuses a second live tag with the same code.
    Rules: `create_tag` R6 [BUG-1528]"""
    mk_tag("Bolt", "bolt")
    commit_point(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            db.add(ItemTag(**_tag_fields(w1, "Screw", "bolt", {})))
            db.flush()
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert count_tags(db, tag_code="bolt") == 1


# [claude] ITS-C-15
def test_its_c_15__the_code_index_leaves_deleted_tags_out(db, w1, mk_tag):
    """ITS-C-15 — the code index leaves deleted tags out.
    Rules: `create_tag` R6"""
    mk_tag("Old Bolt", "bolt", **DELETED)
    commit_point(db)
    db.add(ItemTag(**_tag_fields(w1, "Bolt", "bolt", {})))
    db.flush()

    # Then 1
    assert count_tags(db, tag_code="bolt") == 2


# [claude] ITS-C-16
@pytest.mark.xfail(
    strict=True, reason="BUG-1533: A tag name that derives an existing code is refused with a code the user never typed",
)
def test_its_c_16__a_derived_code_taken_gets_the_first_free_suffix(db, w1, u1, mk_tag):
    """ITS-C-16 — a derived code taken gets the first free suffix.
    Rules: `create_tag` R7 [BUG-1533]"""
    k1 = mk_tag("Steel-Bar", "steelbar")
    commit_point(db)
    result = svc.create_tag(db, tag_in=ItemTagCreate(name="SteelBar"), workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.tag_code == "steelbar_2"
    # Then 2
    db.rollback()
    row = new_row(db, w1, given=(k1,))
    assert row.tag_code == "steelbar_2"
    assert row.name == "SteelBar"


# [claude] ITS-C-17
@pytest.mark.xfail(
    strict=True, reason="BUG-1533: A tag name that derives an existing code is refused with a code the user never typed",
)
def test_its_c_17__the_suffix_skips_taken_ones_2_taken_gives_3(db, w1, u1, mk_tag):
    """ITS-C-17 — the suffix skips taken ones: _2 taken gives _3.
    Rules: `create_tag` R7 [BUG-1533]"""
    mk_tag("Steel-Bar", "steelbar")
    mk_tag("Steel Bar Two", "steelbar_2")
    commit_point(db)
    result = svc.create_tag(db, tag_in=ItemTagCreate(name="SteelBar"), workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.tag_code == "steelbar_3"


# [claude] ITS-C-18
@pytest.mark.xfail(strict=True, reason="BUG-1531: Two live item tags can have the same name")
def test_its_c_18__a_live_name_in_another_case_is_refused_with_the_submitted_name(db, w1, u1, mk_tag):
    """ITS-C-18 — a live name in another case is refused, with the submitted name.
    Rules: `create_tag` R8 [BUG-1531], Errors row 1"""
    mk_tag("Paint", "paint1")
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_tag(db, tag_in=ItemTagCreate(name="PAINT", tag_code="paint2"), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Tag with name 'PAINT' already exists"
    # Then 4
    assert written(db) == before


# [claude] ITS-C-19
@pytest.mark.xfail(strict=True, reason="BUG-1531: Two live item tags can have the same name")
def test_its_c_19__a_system_tags_name_blocks_too(db, w1, u1, mk_system_tag):
    """ITS-C-19 — a system tag's name blocks too.
    Rules: `create_tag` R8 [BUG-1531], Errors row 1"""
    mk_system_tag("Raw Material", "raw_material")
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_tag(
            db, tag_in=ItemTagCreate(name="raw material", tag_code="rm2"), workspace_id=w1.id, user_id=u1.id,
        )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Tag with name 'raw material' already exists"
    # Then 4
    assert written(db) == before


# [claude] ITS-C-20
@pytest.mark.xfail(strict=True, reason="BUG-1531: Two live item tags can have the same name")
def test_its_c_20__the_name_is_checked_before_the_code(db, w1, u1, mk_tag):
    """ITS-C-20 — the name is checked before the code.
    Rules: `create_tag` R8 [BUG-1531], Errors row 1"""
    mk_tag("Paint", "paint")
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_tag(db, tag_in=ItemTagCreate(name="Paint", tag_code="paint"), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Tag with name 'Paint' already exists"
    # Then 4
    assert written(db) == before


# [claude] ITS-C-21
def test_its_c_21__a_deleted_tags_name_does_not_block(db, w1, u1, mk_tag):
    """ITS-C-21 — a deleted tag's name does not block.
    Rules: `create_tag` R8"""
    kd = mk_tag("Paint", "old_paint", **DELETED)
    commit_point(db)
    result = svc.create_tag(db, tag_in=ItemTagCreate(name="Paint", tag_code="paint"), workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.name == "Paint"
    assert result.id != kd.id


# [claude] ITS-C-22
def test_its_c_22__another_workspaces_name_does_not_block(db, w1, w2, u1, mk_tag):
    """ITS-C-22 — another workspace's name does not block.
    Rules: `create_tag` R8"""
    mk_tag("Paint", "paint", workspace_id=w2.id)
    commit_point(db)
    result = svc.create_tag(
        db, tag_in=ItemTagCreate(name="Paint", tag_code="paint_w1"), workspace_id=w1.id, user_id=u1.id,
    )

    # Then 1
    assert result.name == "Paint"
    assert result.workspace_id == w1.id


# [claude] ITS-C-23
@pytest.mark.xfail(strict=True, reason="BUG-1531: Two live item tags can have the same name")
def test_its_c_23__the_database_refuses_a_second_live_tag_with_the_same_name_ignoring_case(db, w1, mk_tag):
    """ITS-C-23 — the database refuses a second live tag with the same name ignoring case.
    Rules: `create_tag` R8 [BUG-1531]"""
    mk_tag("Paint", "paint1")
    commit_point(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            db.add(ItemTag(**_tag_fields(w1, "PAINT", "paint2", {})))
            db.flush()
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert count_tags(db, workspace_id=w1.id) == 1


# [claude] ITS-C-24
def test_its_c_24__a_new_tag_carries_every_given_field_and_the_fixed_ones_committed_and_returned_re_read(
    db, w1, u1,
):
    """ITS-C-24 — a new tag carries every given field and the fixed ones; committed and returned re-read.
    Rules: `create_tag` R10, Returns; S1"""
    commit_point(db)
    result = svc.create_tag(
        db,
        tag_in=ItemTagCreate(name="Steel", tag_code="steel", color="#FF0000", icon="bolt", description="Metal stock"),
        workspace_id=w1.id, user_id=u1.id,
    )

    # Then 1
    assert "created_at" not in unloaded(result)
    assert "tag_code" not in unloaded(result)
    assert "name" not in unloaded(result)
    assert "usage_count" not in unloaded(result)
    # Then 2
    assert isinstance(result, ItemTag)
    # Then 3
    assert result.created_at is not None
    assert result.created_by == u1.id
    # Then 4
    db.rollback()
    row = new_row(db, w1)
    assert row.workspace_id == w1.id
    assert row.name == "Steel"
    assert row.tag_code == "steel"
    # Then 5
    row = new_row(db, w1)
    assert row.color == "#FF0000"
    assert row.icon == "bolt"
    assert row.description == "Metal stock"
    # Then 6
    row = new_row(db, w1)
    assert row.created_by == u1.id
    assert row.is_system_tag is False
    assert row.usage_count == 0
    assert row.is_active is True


# [claude] ITS-C-25
def test_its_c_25__a_client_cannot_make_a_system_tag(db, w1, u1):
    """ITS-C-25 — a client cannot make a system tag.
    Rules: `create_tag` R10"""
    data = ItemTagCreate.model_validate({"name": "Steel", "is_system_tag": True, "usage_count": 5})
    commit_point(db)
    result = svc.create_tag(db, tag_in=data, workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.is_system_tag is False
    # Then 2
    db.rollback()
    row = new_row(db, w1)
    assert row.is_system_tag is False
    assert row.usage_count == 0


# [claude] ITS-C-26
def test_its_c_26__a_failing_commit_is_rolled_back_and_re_raised_other_uncommitted_changes_go_too(
    db, w1, u1, mk_tag,
):
    """ITS-C-26 — a failing commit is rolled back and re-raised; other uncommitted changes go too.
    Rules: `create_tag` R11; S2"""
    mk_tag("Bolt", "bolt")
    commit_point(db)
    mk_tag("Extra", "extra")
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.create_tag(db, tag_in=ItemTagCreate(name="Steel"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert count_tags(db, name="Steel") == 0
    # Then 4
    assert count_tags(db, tag_code="extra") == 0


# [claude] ITS-C-27
def test_its_c_27__a_failing_re_read_after_the_commit_leaves_the_tag_saved(db, w1, u1):
    """ITS-C-27 — a failing re-read after the commit leaves the tag saved.
    Rules: `create_tag` R11; S2"""
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
            svc.create_tag(db, tag_in=ItemTagCreate(name="Steel"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    assert count_tags(db, workspace_id=w1.id, name="Steel") == 1


# [claude] ITS-C-28
def test_its_c_28__a_database_error_inside_the_write_is_rolled_back_and_passed_on(db, w1, u1, mk_tag):
    """ITS-C-28 — a database error inside the write is rolled back and passed on.
    Rules: `create_tag` R11; S2"""
    commit_point(db)
    before = written(db)
    mk_tag("Extra", "extra")
    data = ItemTagCreate.model_construct(name=None, tag_code="nameless", color=None, icon=None, description=None)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        svc.create_tag(db, tag_in=data, workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.orig.pgcode == "23502"
    # Then 3
    assert count_tags(db, tag_code="extra") == 0
    # Then 4
    assert written(db) == before
    # Then 5
    assert usable(db)


# [claude] ITS-C-29
@pytest.mark.xfail(strict=True, reason="BUG-1528: Item tag code uniqueness is not enforced by the database")
def test_its_c_29__a_create_that_loses_the_code_race_gets_the_409_one_row_stays(db, w1, u1, mk_tag):
    """ITS-C-29 — a create that loses the code race gets the 409, one row stays.
    Rules: `create_tag` R6 [BUG-1528], Errors row 2"""
    k1 = mk_tag("Steel", "steel")
    commit_point(db)
    before_k1 = snap_before(db, k1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with patch.object(item_tag_dao, "get_by_code_in_workspace", return_value=None):
            svc.create_tag(
                db, tag_in=ItemTagCreate(name="Steel Two", tag_code="steel"), workspace_id=w1.id, user_id=u1.id,
            )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Tag with code 'steel' already exists"
    # Then 4
    assert count_tags(db, workspace_id=w1.id, tag_code="steel") == 1
    # Then 5
    assert snap(db, k1) == before_k1
    # Then 6
    assert usable(db)


# [claude] ITS-C-30
@pytest.mark.xfail(strict=True, reason="BUG-1531: Two live item tags can have the same name")
def test_its_c_30__a_name_refusal_leaves_other_uncommitted_changes_alone(db, w1, u1, mk_tag):
    """ITS-C-30 — a name refusal leaves other uncommitted changes alone.
    Rules: `create_tag` R8, R11 [BUG-1531]; S3"""
    mk_tag("Paint", "paint1")
    commit_point(db)
    mk_tag("Extra", "extra")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_tag(db, tag_in=ItemTagCreate(name="PAINT", tag_code="paint2"), workspace_id=w1.id, user_id=u1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert count_tags(db, tag_code="extra") == 1


# [claude] ITS-C-31
@pytest.mark.xfail(strict=True, reason="BUG-1531: Two live item tags can have the same name")
def test_its_c_31__a_padded_names_409_names_the_trimmed_name(db, w1, u1, mk_tag):
    """ITS-C-31 — a padded name's 409 names the trimmed name.
    Rules: `create_tag` R8 [BUG-1531], Errors row 1"""
    mk_tag("Paint", "paint1")
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_tag(
            db, tag_in=ItemTagCreate(name=" PAINT ", tag_code="paint2"), workspace_id=w1.id, user_id=u1.id,
        )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Tag with name 'PAINT' already exists"
    # Then 4
    assert written(db) == before


# --------------------------------------------------------------------------- #
# ItemTagService.update_tag
# --------------------------------------------------------------------------- #

# [claude] ITS-U-01
def test_its_u_01__another_workspaces_id_404_nothing_written_no_rollback_of_other_changes(
    db, w1, w2, mk_tag,
):
    """ITS-U-01 — another workspace's id: 404, nothing written, no rollback of other changes.
    Rules: `update_tag` R1, R9, Errors row 1; S3"""
    mk_tag("Bolt", "bolt")
    kz = mk_tag("Far", "far", workspace_id=w2.id)
    commit_point(db)
    before_kz = snap_before(db, kz)
    mk_tag("Extra", "extra")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_tag(db, tag_id=kz.id, tag_in=ItemTagUpdate(name="Hacked"), workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Tag not found"
    # Then 4
    assert count_tags(db, tag_code="extra") == 1
    # Then 5
    assert snap(db, kz) == before_kz


# [claude] ITS-U-02
def test_its_u_02__id_0_gets_the_404(db, w1, mk_tag):
    """ITS-U-02 — id 0 gets the 404.
    Rules: `update_tag` R1, Errors row 1"""
    k1 = mk_tag("Bolt", "bolt")
    commit_point(db)
    before_k1 = snap_before(db, k1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_tag(db, tag_id=0, tag_in=ItemTagUpdate(name="Hacked"), workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Tag not found"
    # Then 4
    assert snap(db, k1) == before_k1


# [claude] ITS-U-03
@pytest.mark.xfail(
    strict=True, reason="BUG-1529: A deleted item tag can still be edited, deleted again and restored by an edit",
)
def test_its_u_03__a_deleted_tag_is_not_found(db, w1, mk_tag):
    """ITS-U-03 — a deleted tag is not found.
    Rules: `update_tag` R2 [BUG-1529], Errors row 1"""
    kd = mk_tag("Obsolete", "obsolete", **DELETED)
    commit_point(db)
    before_kd = snap_before(db, kd)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_tag(db, tag_id=kd.id, tag_in=ItemTagUpdate(name="Revived"), workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Tag not found"
    # Then 4
    assert snap(db, kd) == before_kd


# [claude] ITS-U-04
@pytest.mark.xfail(
    strict=True, reason="BUG-1529: A deleted item tag can still be edited, deleted again and restored by an edit",
)
def test_its_u_04__is_active_true_cannot_bring_a_deleted_tag_back(db, w1, mk_tag):
    """ITS-U-04 — is_active true cannot bring a deleted tag back.
    Rules: `update_tag` R2 [BUG-1529], Errors row 1"""
    kd = mk_tag("Obsolete", "obsolete", **DELETED)
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_tag(db, tag_id=kd.id, tag_in=ItemTagUpdate(is_active=True), workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    db.rollback()
    assert reread(db, kd).is_active is False


# [claude] ITS-U-05
def test_its_u_05__a_system_tag_403_nothing_written_no_rollback_of_other_changes(
    db, w1, mk_tag, mk_system_tag,
):
    """ITS-U-05 — a system tag: 403, nothing written, no rollback of other changes.
    Rules: `update_tag` R3, R9, Errors row 2; S3"""
    ks = mk_system_tag("Raw Material", "raw_material")
    commit_point(db)
    before_ks = snap_before(db, ks)
    mk_tag("Extra", "extra")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_tag(db, tag_id=ks.id, tag_in=ItemTagUpdate(color="#00FF00"), workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "System tags cannot be modified"
    # Then 4
    assert count_tags(db, tag_code="extra") == 1
    # Then 5
    assert snap(db, ks) == before_ks


# [claude] ITS-U-06
def test_its_u_06__another_workspaces_system_tag_gets_the_404_not_the_403(db, w1, w2, mk_system_tag):
    """ITS-U-06 — another workspace's system tag gets the 404, not the 403.
    Rules: `update_tag` R3"""
    kz = mk_system_tag("Far Raw", "far_raw", workspace_id=w2.id)
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_tag(db, tag_id=kz.id, tag_in=ItemTagUpdate(color="#00FF00"), workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Tag not found"


# [claude] ITS-U-07
def test_its_u_07__every_field_sent_is_written_the_code_stays_on_a_rename_committed_and_returned_re_read(
    db, w1, mk_tag,
):
    """ITS-U-07 — every field sent is written; the code stays on a rename; committed and returned re-read.
    Rules: `update_tag` R4, R9, Returns; S1"""
    k1 = mk_tag("Bolt", "bolt", color="#000000", icon="nut", description="Old", usage_count=3)
    commit_point(db)
    result = svc.update_tag(
        db, tag_id=k1.id,
        tag_in=ItemTagUpdate(name="Steel Bolt", color="#FF0000", icon="bolt", description="New"),
        workspace_id=w1.id,
    )

    # Then 1
    assert "name" not in unloaded(result)
    assert "color" not in unloaded(result)
    assert "tag_code" not in unloaded(result)
    # Then 2
    assert result.id == k1.id
    assert result.name == "Steel Bolt"
    # Then 3
    db.rollback()
    row = reread(db, k1)
    assert row.name == "Steel Bolt"
    assert row.color == "#FF0000"
    assert row.icon == "bolt"
    assert row.description == "New"
    # Then 4
    row = reread(db, k1)
    assert row.tag_code == "bolt"
    assert row.usage_count == 3
    assert row.is_active is True


# [claude] ITS-U-08
def test_its_u_08__omitted_fields_stay(db, w1, mk_tag):
    """ITS-U-08 — omitted fields stay.
    Rules: `update_tag` R4"""
    k1 = mk_tag("Bolt", "bolt", color="#000000", icon="nut", description="Old")
    commit_point(db)
    result = svc.update_tag(db, tag_id=k1.id, tag_in=ItemTagUpdate(color="#FF0000"), workspace_id=w1.id)

    # Then 1
    assert result.color == "#FF0000"
    # Then 2
    db.rollback()
    row = reread(db, k1)
    assert row.name == "Bolt"
    assert row.icon == "nut"
    assert row.description == "Old"


# [claude] ITS-U-09
@pytest.mark.xfail(strict=True, reason="BUG-1530: An item tag's colour, icon and description cannot be cleared")
def test_its_u_09__explicit_null_clears_color_icon_and_description(db, w1, mk_tag):
    """ITS-U-09 — explicit null clears color, icon and description.
    Rules: `update_tag` R5 [BUG-1530]"""
    k1 = mk_tag("Bolt", "bolt", color="#000000", icon="nut", description="Old")
    commit_point(db)
    result = svc.update_tag(
        db, tag_id=k1.id, tag_in=ItemTagUpdate(color=None, icon=None, description=None), workspace_id=w1.id,
    )

    # Then 1
    assert result.id == k1.id
    # Then 2
    db.rollback()
    row = reread(db, k1)
    assert row.color is None
    assert row.icon is None
    assert row.description is None
    # Then 3
    assert reread(db, k1).name == "Bolt"


# [claude] ITS-U-10
@pytest.mark.xfail(strict=True, reason="BUG-1530: An item tag's colour, icon and description cannot be cleared")
def test_its_u_10__null_for_name_is_refused_by_the_schema(db, mk_tag):
    """ITS-U-10 — null for name is refused by the schema.
    Rules: `update_tag` R5 [BUG-1530]"""
    k1 = mk_tag("Bolt", "bolt")
    commit_point(db)
    before_k1 = snap_before(db, k1)
    # Then 1
    with pytest.raises(PydanticValidationError):
        ItemTagUpdate(name=None)
    # Then 2
    assert snap(db, k1) == before_k1


# [claude] ITS-U-11
@pytest.mark.xfail(strict=True, reason="BUG-1531: Two live item tags can have the same name")
def test_its_u_11__a_rename_to_another_live_tags_name_is_refused(db, w1, mk_tag):
    """ITS-U-11 — a rename to another live tag's name is refused.
    Rules: `update_tag` R6 [BUG-1531], Errors row 3"""
    mk_tag("Paint", "paint")
    k2 = mk_tag("Bolt", "bolt")
    commit_point(db)
    before_k2 = snap_before(db, k2)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_tag(db, tag_id=k2.id, tag_in=ItemTagUpdate(name="paint"), workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Tag with name 'paint' already exists"
    # Then 4
    assert snap(db, k2) == before_k2


# [claude] ITS-U-12
def test_its_u_12__the_tags_own_name_in_another_case_is_accepted(db, w1, mk_tag):
    """ITS-U-12 — the tag's own name in another case is accepted.
    Rules: `update_tag` R6"""
    k1 = mk_tag("Paint", "paint")
    commit_point(db)
    result = svc.update_tag(db, tag_id=k1.id, tag_in=ItemTagUpdate(name="PAINT"), workspace_id=w1.id)

    # Then 1
    assert result.name == "PAINT"
    # Then 2
    db.rollback()
    assert reread(db, k1).name == "PAINT"


# [claude] ITS-U-13
@pytest.mark.xfail(strict=True, reason="BUG-1526: Item tag names are stored untrimmed, and blank names are accepted")
def test_its_u_13__a_blank_new_name_is_refused_by_the_schema(db, mk_tag):
    """ITS-U-13 — a blank new name is refused by the schema.
    Rules: `update_tag` R7 [BUG-1526]"""
    k1 = mk_tag("Bolt", "bolt")
    commit_point(db)
    before_k1 = snap_before(db, k1)
    # Then 1
    with pytest.raises(PydanticValidationError):
        ItemTagUpdate(name="  ")
    # Then 2
    assert snap(db, k1) == before_k1


# [claude] ITS-U-14
@pytest.mark.xfail(strict=True, reason="BUG-1526: Item tag names are stored untrimmed, and blank names are accepted")
def test_its_u_14__a_padded_new_name_is_stored_trimmed(db, w1, mk_tag):
    """ITS-U-14 — a padded new name is stored trimmed.
    Rules: `update_tag` R7 [BUG-1526]"""
    k1 = mk_tag("Bolt", "bolt")
    data = ItemTagUpdate(name="  Steel  ")
    commit_point(db)
    result = svc.update_tag(db, tag_id=k1.id, tag_in=data, workspace_id=w1.id)

    # Then 1
    assert result.id == k1.id
    # Then 2
    db.rollback()
    assert reread(db, k1).name == "Steel"


# [claude] ITS-U-15
def test_its_u_15__is_active_false_hides_a_live_tag_exactly_as_a_delete(db, w1, i1, mk_tag, mk_link):
    """ITS-U-15 — is_active false hides a live tag exactly as a delete.
    Rules: `update_tag` R8"""
    k1 = mk_tag("Bolt", "bolt", usage_count=3)
    link = mk_link(i1, k1)
    commit_point(db)
    result = svc.update_tag(db, tag_id=k1.id, tag_in=ItemTagUpdate(is_active=False), workspace_id=w1.id)

    # Then 1
    assert result.is_active is False
    # Then 2
    db.rollback()
    row = reread(db, k1)
    assert row.is_active is False
    assert row.usage_count == 3
    assert row.name == "Bolt"
    # Then 3
    assert reread(db, link).tag_id == k1.id
    # Then 4
    assert svc.get_tags(db, workspace_id=w1.id) == []


# [claude] ITS-U-16
def test_its_u_16__is_active_true_on_a_live_tag_changes_nothing(db, w1, mk_tag):
    """ITS-U-16 — is_active true on a live tag changes nothing.
    Rules: `update_tag` R8"""
    k1 = mk_tag("Bolt", "bolt")
    commit_point(db)
    before_k1 = snap_before(db, k1)
    result = svc.update_tag(db, tag_id=k1.id, tag_in=ItemTagUpdate(is_active=True), workspace_id=w1.id)

    # Then 1
    assert result.is_active is True
    # Then 2
    assert snap(db, k1) == before_k1


# [claude] ITS-U-17
def test_its_u_17__a_failing_commit_is_rolled_back_and_re_raised_other_uncommitted_changes_go_too(
    db, w1, mk_tag,
):
    """ITS-U-17 — a failing commit is rolled back and re-raised; other uncommitted changes go too.
    Rules: `update_tag` R9; S2"""
    k1 = mk_tag("Bolt", "bolt")
    commit_point(db)
    before_k1 = snap_before(db, k1)
    mk_tag("Extra", "extra")
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.update_tag(db, tag_id=k1.id, tag_in=ItemTagUpdate(name="Steel"), workspace_id=w1.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert snap(db, k1) == before_k1
    # Then 4
    assert count_tags(db, tag_code="extra") == 0


# [claude] ITS-U-18
@pytest.mark.xfail(strict=True, reason="BUG-1531: Two live item tags can have the same name")
def test_its_u_18__a_name_refusal_on_rename_leaves_other_uncommitted_changes_alone(db, w1, mk_tag):
    """ITS-U-18 — a name refusal on rename leaves other uncommitted changes alone.
    Rules: `update_tag` R6, R9 [BUG-1531]; S3"""
    mk_tag("Paint", "paint")
    k2 = mk_tag("Bolt", "bolt")
    commit_point(db)
    mk_tag("Extra", "extra")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_tag(db, tag_id=k2.id, tag_in=ItemTagUpdate(name="paint"), workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert count_tags(db, tag_code="extra") == 1


# --------------------------------------------------------------------------- #
# ItemTagService.delete_tag
# --------------------------------------------------------------------------- #

# [claude] ITS-D-01
def test_its_d_01__a_live_user_tag_gets_is_active_false_and_nothing_else_committed(db, w1, i1, mk_tag, mk_link):
    """ITS-D-01 — a live user tag gets is_active False and nothing else; committed.
    Rules: `delete_tag` R4, Returns; S1"""
    k1 = mk_tag("Bolt", "bolt", usage_count=3, color="#000000")
    link = mk_link(i1, k1)
    commit_point(db)
    result = svc.delete_tag(db, tag_id=k1.id, workspace_id=w1.id)

    # Then 1
    assert result is None
    # Then 2
    db.rollback()
    assert reread(db, k1).is_active is False
    # Then 3
    row = reread(db, k1)
    assert row.usage_count == 3
    assert row.name == "Bolt"
    assert row.tag_code == "bolt"
    assert row.color == "#000000"
    assert row.is_system_tag is False
    # Then 4
    link_row = reread(db, link)
    assert link_row.tag_id == k1.id
    assert link_row.item_id == i1.id
    # Then 5
    assert svc.get_tags(db, workspace_id=w1.id) == []


# [claude] ITS-D-02
def test_its_d_02__another_workspaces_id_404_nothing_written_no_rollback_of_other_changes(db, w1, w2, mk_tag):
    """ITS-D-02 — another workspace's id: 404, nothing written, no rollback of other changes.
    Rules: `delete_tag` R1, R5, Errors row 1; S3"""
    kz = mk_tag("Far", "far", workspace_id=w2.id)
    commit_point(db)
    before_kz = snap_before(db, kz)
    mk_tag("Extra", "extra")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_tag(db, tag_id=kz.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Tag not found"
    # Then 4
    assert count_tags(db, tag_code="extra") == 1
    # Then 5
    assert snap(db, kz) == before_kz


# [claude] ITS-D-03
def test_its_d_03__id_0_gets_the_404(db, w1, mk_tag):
    """ITS-D-03 — id 0 gets the 404.
    Rules: `delete_tag` R1, Errors row 1"""
    k1 = mk_tag("Bolt", "bolt")
    commit_point(db)
    before_k1 = snap_before(db, k1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_tag(db, tag_id=0, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Tag not found"
    # Then 4
    assert snap(db, k1) == before_k1


# [claude] ITS-D-04
@pytest.mark.xfail(
    strict=True, reason="BUG-1529: A deleted item tag can still be edited, deleted again and restored by an edit",
)
def test_its_d_04__an_already_deleted_tag_is_not_found(db, w1, mk_tag):
    """ITS-D-04 — an already deleted tag is not found.
    Rules: `delete_tag` R2 [BUG-1529], Errors row 1"""
    kd = mk_tag("Obsolete", "obsolete", **DELETED)
    commit_point(db)
    before_kd = snap_before(db, kd)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_tag(db, tag_id=kd.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Tag not found"
    # Then 4
    assert snap(db, kd) == before_kd


# [claude] ITS-D-05
def test_its_d_05__a_system_tag_403_nothing_written(db, w1, mk_system_tag):
    """ITS-D-05 — a system tag: 403, nothing written.
    Rules: `delete_tag` R3, Errors row 2"""
    ks = mk_system_tag("Raw Material", "raw_material")
    commit_point(db)
    before_ks = snap_before(db, ks)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_tag(db, tag_id=ks.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "System tags cannot be deleted"
    # Then 4
    assert snap(db, ks) == before_ks


# [claude] ITS-D-06
def test_its_d_06__a_failing_commit_is_rolled_back_and_re_raised_the_tag_stays_live(db, w1, mk_tag):
    """ITS-D-06 — a failing commit is rolled back and re-raised: the tag stays live.
    Rules: `delete_tag` R5; S2"""
    k1 = mk_tag("Bolt", "bolt")
    commit_point(db)
    before_k1 = snap_before(db, k1)
    mk_tag("Extra", "extra")
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=RuntimeError("boom")), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.delete_tag(db, tag_id=k1.id, workspace_id=w1.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert snap(db, k1) == before_k1
    # Then 4
    assert count_tags(db, tag_code="extra") == 0


# [claude] ITS-D-07
def test_its_d_07__a_system_tag_refusal_leaves_other_uncommitted_changes_alone(db, w1, mk_tag, mk_system_tag):
    """ITS-D-07 — a system-tag refusal leaves other uncommitted changes alone.
    Rules: `delete_tag` R3, R5; S3"""
    ks = mk_system_tag("Raw Material", "raw_material")
    commit_point(db)
    mk_tag("Extra", "extra")
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_tag(db, tag_id=ks.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert count_tags(db, tag_code="extra") == 1
