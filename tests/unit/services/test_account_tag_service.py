"""Unit tests for app/services/account_tag_service.py.

Implements tests/unit/services/account_tag_service.cases.md (revision 3), one test
per case, in card order. Real Postgres session (`db` fixture): a `commit()` only
releases a savepoint, so the service's commits are safe and the fixture's outer
rollback discards everything. Nothing is patched except what Conventions name:
the failing commit / failing refresh wraps, the commit / rollback spies (both
still call the real method) and the race simulation of ATV-C-18.

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

from app.dao.account_tag import account_tag_dao
from app.models.account import Account
from app.models.account_tag import AccountTag
from app.models.account_tag_assignment import AccountTagAssignment
from app.schemas.account_tag import (
    AccountTagCreate,
    AccountTagResponse,
    AccountTagUpdate,
)
from app.services.account_tag_service import account_tag_service
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "svc = the singleton account_tag_service"
svc = account_tag_service

MISSING = 999999999

# Convention "BN" (Bengali, "raw material")
BN = "কাঁচামাল"

BUG_1482 = "BUG-1482: Account tag lists have no sort order"
BUG_1483 = "BUG-1483: System tag list includes deleted system tags"
BUG_1485 = "BUG-1485: Account tag picker silently stops at 100 tags"
BUG_1682 = "BUG-1682: Account tag names are stored untrimmed, and blank names are accepted"
BUG_1683 = "BUG-1683: A deleted account tag's code can never be used again"
BUG_1684 = "BUG-1684: Account tag code uniqueness is not enforced by the database"
BUG_1685 = "BUG-1685: A deleted account tag can still be edited, deleted again and restored by an edit"
BUG_1688 = "BUG-1688: An account tag's colour, icon and description cannot be cleared"
BUG_1689 = "BUG-1689: Two live account tags can have the same name"
BUG_1690 = "BUG-1690: Some account tag names break the create or the whole tag list"
BUG_1691 = "BUG-1691: An account tag name that derives an existing code is refused with a code the user never typed"
BUG_1692 = "BUG-1692: An account tag's code can be changed by an edit, onto another tag's code"
BUG_1693 = "BUG-1693: A client-sent account tag code has no format"


def _add(db, row):
    db.add(row)
    db.flush()
    return row


# --------------------------------------------------------------------------- #
# Conventions -> actors (exist in every test)
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


@pytest.fixture(autouse=True)
def actors(u1):
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
        return _add(db, AccountTag(**_tag_fields(w1, name, tag_code, but)))
    return _mk


# Convention "system tag"
@pytest.fixture
def mk_system_tag(mk_tag):
    def _mk(name, tag_code, **but):
        return mk_tag(name, tag_code, is_system_tag=True, **but)
    return _mk


# Convention "deleted" (of a tag)
DELETED = {"is_active": False}


# Convention "account A1"
@pytest.fixture
def mk_account(db, w1):
    def _mk():
        return _add(db, Account(workspace_id=w1.id, name="Acme"))
    return _mk


# Convention "link of A1 to T"
@pytest.fixture
def mk_link(db, w1):
    def _mk(account, tag):
        return _add(db, AccountTagAssignment(workspace_id=w1.id, account_id=account.id, tag_id=tag.id))
    return _mk


# Convention "X": the extra row, after the commit point
@pytest.fixture
def mk_extra(mk_tag):
    def _mk():
        return mk_tag("Extra", "extra")
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
    table = AccountTag.__table__
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


# Convention "count:" lines: account_tags rows (all workspaces), with the filter stated
def count_tags(db, **filters):
    query = select(func.count()).select_from(AccountTag)
    for column, value in filters.items():
        query = query.where(getattr(AccountTag, column) == value)
    return db.execute(query).scalar_one()


# Convention "nothing written"
def written(db):
    return count_tags(db)


# Convention "the new row": the one account_tags row of W1 whose id is not among the Given rows
def new_row(db, w1, given=()):
    given_ids = [_id_of(row) for row in given]
    db.expire_all()
    query = select(AccountTag).where(AccountTag.workspace_id == w1.id)
    if given_ids:
        query = query.where(AccountTag.id.notin_(given_ids))
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
# AccountTagService.get_tags
# --------------------------------------------------------------------------- #

# [claude] ATV-T-01
def test_atv_t_01__live_tags_of_the_workspace_only_system_and_user(db, w1, w2, mk_tag, mk_system_tag):
    """ATV-T-01 — live tags of the workspace only, system and user.
    Rules: `get_tags` R1"""
    mk_tag("Far One", "far_one", workspace_id=w2.id)
    k1 = mk_tag("Vendor X", "vendor_x")
    ks = mk_system_tag("Supplier", "supplier")
    mk_tag("Obsolete", "obsolete", **DELETED)
    mk_tag("Far Two", "far_two", workspace_id=w2.id)
    commit_point(db)
    result = svc.get_tags(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [k1.id, ks.id]


# [claude] ATV-T-02
def test_atv_t_02__usage_count_is_the_stored_counter_not_a_recount(db, w1, mk_tag, mk_account, mk_link):
    """ATV-T-02 — usage_count is the stored counter, not a recount.
    Rules: `get_tags` R2"""
    k1 = mk_tag("Vendor X", "vendor_x", usage_count=9)
    a1 = mk_account()
    mk_link(a1, k1)
    commit_point(db)
    result = svc.get_tags(db, workspace_id=w1.id)

    # Then 1
    assert [t.usage_count for t in result] == [9]


# [claude] ATV-T-03
def test_atv_t_03__a_stored_tag_with_an_empty_code_is_still_returned(db, w1, mk_tag):
    """ATV-T-03 — a stored tag with an empty code is still returned.
    Rules: `get_tags` R3"""
    k1 = mk_tag("!!!", "")
    commit_point(db)
    result = svc.get_tags(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [k1.id]
    # Then 2
    assert result[0].tag_code == ""


# [claude] ATV-T-04
@pytest.mark.xfail(strict=True, reason=BUG_1690)
def test_atv_t_04__a_stored_tag_with_an_empty_code_passes_the_response_schema(db, w1, mk_tag):
    """ATV-T-04 — a stored tag with an empty code passes the response schema.
    Rules: `get_tags` R3 [BUG-1690]"""
    mk_tag("!!!", "")
    commit_point(db)
    result = svc.get_tags(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 1
    # Then 2
    assert AccountTagResponse.model_validate(result[0]).tag_code == ""


# [claude] ATV-T-05
def test_atv_t_05__a_stored_tag_with_a_non_ascii_code_passes_the_response_schema(db, w1, mk_tag):
    """ATV-T-05 — a stored tag with a non-ASCII code passes the response schema.
    Rules: `get_tags` R3"""
    k1 = mk_tag("Café", "café")
    commit_point(db)
    result = svc.get_tags(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [k1.id]
    # Then 2
    assert AccountTagResponse.model_validate(result[0]).tag_code == "café"


# [claude] ATV-T-06
def test_atv_t_06__the_list_neither_commits_nor_rolls_back(db, w1, mk_tag):
    """ATV-T-06 — the list neither commits nor rolls back.
    Rules: `get_tags` R4; S4"""
    k1 = mk_tag("Vendor X", "vendor_x")
    k2 = mk_tag("Client B", "client_b")
    commit_point(db)
    p = mk_tag("Pending", "pending")
    k2.color = "#00FF00"
    with spies(db) as (cm, rb):
        result = svc.get_tags(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [k1.id, k2.id, p.id]
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert k2 in db.dirty
    # Then 5
    db.rollback()
    assert count_tags(db, tag_code="pending") == 0


# [claude] ATV-T-07
@pytest.mark.xfail(strict=False, reason=BUG_1482)
def test_atv_t_07__pass_through_bug_1482_system_tags_first_then_name_case_insensitive_then_id(
    db, w1, mk_tag, mk_system_tag,
):
    """ATV-T-07 — pass-through BUG-1482: system tags first, then name case-insensitive, then id.
    Rules: `get_tags` R1 [BUG-1482]"""
    k1 = mk_tag("bravo", "bravo")
    k2 = mk_tag("Alpha", "alpha")
    k3 = mk_tag("Charlie", "charlie")
    ks = mk_system_tag("Zeta", "zeta")
    commit_point(db)
    result = svc.get_tags(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [k1.id, k2.id, k3.id, ks.id]
    # Then 2
    assert [t.id for t in result] == [ks.id, k2.id, k1.id, k3.id]


# [claude] ATV-T-08
@pytest.mark.xfail(strict=True, reason=BUG_1485)
def test_atv_t_08__pass_through_bug_1485_every_live_tag_is_returned_101_of_101(db, w1):
    """ATV-T-08 — pass-through BUG-1485: every live tag is returned, 101 of 101.
    Rules: `get_tags` R1 [BUG-1485]"""
    db.add_all([AccountTag(**_tag_fields(w1, f"t{k:03d}", f"t{k:03d}", {})) for k in range(101)])
    db.flush()
    commit_point(db)
    result = svc.get_tags(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 101


# --------------------------------------------------------------------------- #
# AccountTagService.get_system_tags
# --------------------------------------------------------------------------- #

# [claude] ATV-Y-01
def test_atv_y_01__the_workspaces_system_tags_only_with_the_stored_counter(db, w1, w2, mk_tag, mk_system_tag):
    """ATV-Y-01 — the workspace's system tags only, with the stored counter.
    Rules: `get_system_tags` R1"""
    mk_system_tag("Far One", "far_one", workspace_id=w2.id)
    mk_tag("Vendor X", "vendor_x")
    ks = mk_system_tag("Supplier", "supplier", usage_count=9)
    mk_system_tag("Far Two", "far_two", workspace_id=w2.id)
    commit_point(db)
    result = svc.get_system_tags(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [ks.id]
    # Then 2
    assert result[0].usage_count == 9


# [claude] ATV-Y-02
def test_atv_y_02__a_live_system_tag_of_the_workspace_is_returned_when_there_is_a_deleted_one(
    db, w1, mk_system_tag,
):
    """ATV-Y-02 — a live system tag of the workspace is returned when there is a deleted one.
    Rules: `get_system_tags` R1"""
    ks = mk_system_tag("Supplier", "supplier")
    mk_system_tag("Utility", "utility", **DELETED)
    commit_point(db)
    result = svc.get_system_tags(db, workspace_id=w1.id)

    # Then 1
    assert ks.id in [t.id for t in result]


# [claude] ATV-Y-03
@pytest.mark.xfail(strict=True, reason=BUG_1483)
def test_atv_y_03__pass_through_bug_1483_a_deleted_system_tag_is_not_returned(db, w1, mk_system_tag):
    """ATV-Y-03 — pass-through BUG-1483: a deleted system tag is not returned.
    Rules: `get_system_tags` R1 [BUG-1483]"""
    ks = mk_system_tag("Supplier", "supplier")
    mk_system_tag("Utility", "utility", **DELETED)
    commit_point(db)
    result = svc.get_system_tags(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [ks.id]


# [claude] ATV-Y-04
@pytest.mark.xfail(strict=False, reason=BUG_1482)
def test_atv_y_04__pass_through_bug_1482_system_tags_come_by_name_case_insensitive_ascending(
    db, w1, mk_system_tag,
):
    """ATV-Y-04 — pass-through BUG-1482: system tags come by name, case-insensitive ascending.
    Rules: `get_system_tags` R1 [BUG-1482]"""
    s1 = mk_system_tag("Utility", "utility")
    s2 = mk_system_tag("client", "client")
    s3 = mk_system_tag("Bank", "bank")
    commit_point(db)
    result = svc.get_system_tags(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [s1.id, s2.id, s3.id]
    # Then 2
    assert [t.name for t in result] == ["Bank", "client", "Utility"]


# [claude] ATV-Y-05
def test_atv_y_05__the_list_neither_commits_nor_rolls_back(db, w1, mk_tag, mk_system_tag):
    """ATV-Y-05 — the list neither commits nor rolls back.
    Rules: `get_system_tags` R2; S4"""
    ks = mk_system_tag("Supplier", "supplier")
    k2 = mk_tag("Client B", "client_b")
    commit_point(db)
    mk_tag("Pending", "pending")
    k2.color = "#00FF00"
    with spies(db) as (cm, rb):
        result = svc.get_system_tags(db, workspace_id=w1.id)

    # Then 1
    assert ids(result) == [ks.id]
    # Then 2
    assert cm.call_count == 0
    # Then 3
    assert rb.call_count == 0
    # Then 4
    assert k2 in db.dirty
    # Then 5
    assert count_tags(db, tag_code="pending") == 1
    # Then 6
    db.rollback()
    assert count_tags(db, tag_code="pending") == 0


# --------------------------------------------------------------------------- #
# AccountTagService.create_tag
# --------------------------------------------------------------------------- #

# [claude] ATV-C-01
def test_atv_c_01__a_sent_tag_code_in_the_format_is_used_as_sent(db, w1, u1):
    """ATV-C-01 — a sent tag_code in the format is used as sent.
    Rules: `create_tag` R1"""
    commit_point(db)
    result = svc.create_tag(
        db, tag_in=AccountTagCreate(name="Big Supplier", tag_code="supplier_x"), workspace_id=w1.id, user_id=u1.id,
    )

    # Then 1
    assert result.tag_code == "supplier_x"
    # Then 2
    db.rollback()
    row = new_row(db, w1)
    assert row.tag_code == "supplier_x"
    assert row.name == "Big Supplier"


# [claude] ATV-C-02
@pytest.mark.xfail(strict=True, reason=BUG_1693)
def test_atv_c_02__a_sent_code_in_capitals_is_refused_by_the_schema(db):
    """ATV-C-02 — a sent code in capitals is refused by the schema.
    Rules: `create_tag` R1a [BUG-1693], Errors row 3"""
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(PydanticValidationError):
        AccountTagCreate(name="Big Supplier", tag_code="SUPPLIER")
    # Then 2
    assert written(db) == before


# [claude] ATV-C-03
@pytest.mark.xfail(strict=True, reason=BUG_1693)
def test_atv_c_03__a_sent_code_with_a_leading_space_is_refused_not_trimmed(db):
    """ATV-C-03 — a sent code with a leading space is refused, not trimmed.
    Rules: `create_tag` R1a [BUG-1693], Errors row 3"""
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(PydanticValidationError):
        AccountTagCreate(name="Big Supplier", tag_code=" supplier")
    # Then 2
    assert written(db) == before


# [claude] ATV-C-04
@pytest.mark.xfail(strict=True, reason=BUG_1693)
def test_atv_c_04__a_sent_code_with_a_hyphen_is_refused(db):
    """ATV-C-04 — a sent code with a hyphen is refused.
    Rules: `create_tag` R1a [BUG-1693], Errors row 3"""
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(PydanticValidationError):
        AccountTagCreate(name="Big Supplier", tag_code="supplier-x")
    # Then 2
    assert written(db) == before


# [claude] ATV-C-05
@pytest.mark.xfail(strict=True, reason=BUG_1693)
def test_atv_c_05__a_sent_code_with_an_accented_letter_is_refused(db):
    """ATV-C-05 — a sent code with an accented letter is refused.
    Rules: `create_tag` R1a [BUG-1693], Errors row 3"""
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(PydanticValidationError):
        AccountTagCreate(name="Café", tag_code="café")
    # Then 2
    assert written(db) == before


# [claude] ATV-C-06
def test_atv_c_06__an_empty_sent_code_stays_refused(db):
    """ATV-C-06 — an empty sent code stays refused.
    Rules: `create_tag` R1a"""
    commit_point(db)
    # Then 1
    with pytest.raises(PydanticValidationError):
        AccountTagCreate(name="Big Supplier", tag_code="")


# [claude] ATV-C-07
def test_atv_c_07__a_sent_code_of_51_characters_stays_refused_50_are_accepted(db):
    """ATV-C-07 — a sent code of 51 characters stays refused; 50 are accepted.
    Rules: `create_tag` R1a"""
    ok = AccountTagCreate(name="Long", tag_code="a" * 50)
    commit_point(db)
    # Then 1
    with pytest.raises(PydanticValidationError):
        AccountTagCreate(name="Long", tag_code="a" * 51)
    # Then 2
    assert ok.tag_code == "a" * 50


# [claude] ATV-C-08
def test_atv_c_08__with_no_code_sent_spaces_become_underscore_and_digits_stay(db, w1, u1):
    """ATV-C-08 — with no code sent, spaces become _ and digits stay.
    Rules: `create_tag` R2"""
    commit_point(db)
    result = svc.create_tag(db, tag_in=AccountTagCreate(name="Steel Bar 2"), workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.tag_code == "steel_bar_2"
    # Then 2
    db.rollback()
    assert new_row(db, w1).tag_code == "steel_bar_2"


# [claude] ATV-C-09
def test_atv_c_09__with_the_code_sent_as_null_other_symbols_are_dropped(db, w1, u1):
    """ATV-C-09 — with the code sent as null, other symbols are dropped.
    Rules: `create_tag` R2"""
    commit_point(db)
    result = svc.create_tag(
        db, tag_in=AccountTagCreate(name="Steel-Bar", tag_code=None), workspace_id=w1.id, user_id=u1.id,
    )

    # Then 1
    assert result.tag_code == "steelbar"


# [claude] ATV-C-10
@pytest.mark.xfail(strict=True, reason=BUG_1690)
def test_atv_c_10__a_derived_code_drops_accented_letters(db, w1, u1):
    """ATV-C-10 — a derived code drops accented letters.
    Rules: `create_tag` R3 [BUG-1690]"""
    commit_point(db)
    result = svc.create_tag(db, tag_in=AccountTagCreate(name="Café"), workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.tag_code == "caf"
    # Then 2
    db.rollback()
    assert new_row(db, w1).tag_code == "caf"


# [claude] ATV-C-11
@pytest.mark.xfail(strict=True, reason=BUG_1690)
def test_atv_c_11__a_derived_code_with_nothing_left_is_tag(db, w1, u1):
    """ATV-C-11 — a derived code with nothing left is "tag".
    Rules: `create_tag` R3 [BUG-1690]"""
    commit_point(db)
    result = svc.create_tag(db, tag_in=AccountTagCreate(name="!!!"), workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.tag_code == "tag"


# [claude] ATV-C-12
@pytest.mark.xfail(strict=True, reason=BUG_1690)
def test_atv_c_12__a_derived_code_of_a_60_letter_name_is_cut_to_50(db, w1, u1):
    """ATV-C-12 — a derived code of a 60-letter name is cut to 50.
    Rules: `create_tag` R3 [BUG-1690]"""
    commit_point(db)
    result = svc.create_tag(db, tag_in=AccountTagCreate(name="a" * 60), workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.tag_code == "a" * 50
    # Then 2
    db.rollback()
    assert new_row(db, w1).tag_code == "a" * 50


# [claude] ATV-C-13
def test_atv_c_13__a_derived_code_of_exactly_50_characters_is_kept_whole(db, w1, u1):
    """ATV-C-13 — a derived code of exactly 50 characters is kept whole.
    Rules: `create_tag` R3"""
    commit_point(db)
    result = svc.create_tag(db, tag_in=AccountTagCreate(name="a" * 50), workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.tag_code == "a" * 50


# [claude] ATV-C-14
@pytest.mark.xfail(strict=True, reason=BUG_1690)
def test_atv_c_14__a_padded_name_derives_its_code_from_the_trimmed_name(db, w1, u1):
    """ATV-C-14 — a padded name derives its code from the trimmed name.
    Rules: `create_tag` R3 [BUG-1690]"""
    commit_point(db)
    result = svc.create_tag(db, tag_in=AccountTagCreate(name=" Bolt "), workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.tag_code == "bolt"


# [claude] ATV-C-15
@pytest.mark.xfail(strict=True, reason=BUG_1690)
def test_atv_c_15__a_bengali_name_derives_tag(db, w1, u1):
    """ATV-C-15 — a Bengali name derives "tag".
    Rules: `create_tag` R3 [BUG-1690]"""
    commit_point(db)
    result = svc.create_tag(db, tag_in=AccountTagCreate(name=BN), workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.tag_code == "tag"


# [claude] ATV-C-16
@pytest.mark.xfail(strict=True, reason=BUG_1684)
def test_atv_c_16__the_database_refuses_a_second_live_tag_with_the_same_code(db, w1, mk_tag):
    """ATV-C-16 — the database refuses a second live tag with the same code.
    Rules: `create_tag` R6 [BUG-1684]"""
    mk_tag("Vendor X", "vendor_x")
    commit_point(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            db.add(AccountTag(**_tag_fields(w1, "Vendor Y", "vendor_x", {})))
            db.flush()
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert count_tags(db, tag_code="vendor_x") == 1


# [claude] ATV-C-17
def test_atv_c_17__the_code_index_leaves_deleted_tags_out(db, w1, mk_tag):
    """ATV-C-17 — the code index leaves deleted tags out.
    Rules: `create_tag` R6"""
    mk_tag("Old Vendor", "vendor_x", **DELETED)
    commit_point(db)
    db.add(AccountTag(**_tag_fields(w1, "Vendor X", "vendor_x", {})))
    db.flush()

    # Then 1
    assert count_tags(db, tag_code="vendor_x") == 2


# [claude] ATV-C-18
@pytest.mark.xfail(strict=True, reason=BUG_1684)
def test_atv_c_18__a_create_that_loses_the_code_race_gets_the_409_one_row_stays(db, w1, u1, mk_tag):
    """ATV-C-18 — a create that loses the code race gets the 409, one row stays.
    Rules: `create_tag` R6 [BUG-1684], Errors row 2"""
    k1 = mk_tag("Vendor X", "vendor_x")
    commit_point(db)
    before_k1 = snap_before(db, k1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        with patch.object(account_tag_dao, "get_by_tag_code_in_workspace", return_value=None):
            svc.create_tag(
                db, tag_in=AccountTagCreate(name="Vendor Two", tag_code="vendor_x"), workspace_id=w1.id,
                user_id=u1.id,
            )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Tag with code 'vendor_x' already exists"
    # Then 4
    assert count_tags(db, workspace_id=w1.id, tag_code="vendor_x") == 1
    # Then 5
    assert snap(db, k1) == before_k1
    # Then 6
    assert usable(db)


# [claude] ATV-C-19
def test_atv_c_19__a_sent_code_taken_409_nothing_written_other_uncommitted_changes_stay(
    db, w1, u1, mk_tag, mk_extra,
):
    """ATV-C-19 — a sent code taken: 409, nothing written, other uncommitted changes stay.
    Rules: `create_tag` R4, R11, Errors row 2; S3"""
    k1 = mk_tag("Vendor X", "vendor_x")
    commit_point(db)
    before_k1 = snap_before(db, k1)
    mk_extra()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_tag(
            db, tag_in=AccountTagCreate(name="Vendor Two", tag_code="vendor_x"), workspace_id=w1.id, user_id=u1.id,
        )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Tag with code 'vendor_x' already exists"
    # Then 4
    assert count_tags(db, name="Vendor Two") == 0
    # Then 5
    assert count_tags(db, tag_code="extra") == 1
    # Then 6
    assert snap(db, k1) == before_k1


# [claude] ATV-C-20
def test_atv_c_20__the_same_code_in_another_workspace_does_not_block(db, w1, w2, u1, mk_tag):
    """ATV-C-20 — the same code in another workspace does not block.
    Rules: `create_tag` R4"""
    mk_tag("Vendor X", "vendor_x", workspace_id=w2.id)
    commit_point(db)
    result = svc.create_tag(
        db, tag_in=AccountTagCreate(name="Vendor X", tag_code="vendor_x"), workspace_id=w1.id, user_id=u1.id,
    )

    # Then 1
    assert result.workspace_id == w1.id
    assert result.tag_code == "vendor_x"
    # Then 2
    db.rollback()
    assert count_tags(db, tag_code="vendor_x") == 2


# [claude] ATV-C-21
@pytest.mark.xfail(strict=True, reason=BUG_1683)
def test_atv_c_21__a_deleted_tags_code_can_be_used_again(db, w1, u1, mk_tag):
    """ATV-C-21 — a deleted tag's code can be used again.
    Rules: `create_tag` R5 [BUG-1683]"""
    kd = mk_tag("Old Vendor", "vendor_x", **DELETED)
    commit_point(db)
    result = svc.create_tag(
        db, tag_in=AccountTagCreate(name="Vendor X", tag_code="vendor_x"), workspace_id=w1.id, user_id=u1.id,
    )

    # Then 1
    assert result.id != kd.id
    assert result.tag_code == "vendor_x"
    # Then 2
    db.rollback()
    assert count_tags(db, workspace_id=w1.id, tag_code="vendor_x") == 2


# [claude] ATV-C-22
@pytest.mark.xfail(strict=True, reason=BUG_1691)
def test_atv_c_22__a_derived_code_taken_gets_the_first_free_suffix(db, w1, u1, mk_tag):
    """ATV-C-22 — a derived code taken gets the first free suffix.
    Rules: `create_tag` R7 [BUG-1691]"""
    k1 = mk_tag("Steel-Bar", "steelbar")
    commit_point(db)
    result = svc.create_tag(db, tag_in=AccountTagCreate(name="SteelBar"), workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.tag_code == "steelbar_2"
    # Then 2
    db.rollback()
    row = new_row(db, w1, given=(k1,))
    assert row.tag_code == "steelbar_2"
    assert row.name == "SteelBar"


# [claude] ATV-C-23
@pytest.mark.xfail(strict=True, reason=BUG_1691)
def test_atv_c_23__the_suffix_skips_taken_ones_2_taken_gives_3(db, w1, u1, mk_tag):
    """ATV-C-23 — the suffix skips taken ones: _2 taken gives _3.
    Rules: `create_tag` R7 [BUG-1691]"""
    mk_tag("Steel-Bar", "steelbar")
    mk_tag("Steel Bar Two", "steelbar_2")
    commit_point(db)
    result = svc.create_tag(db, tag_in=AccountTagCreate(name="SteelBar"), workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.tag_code == "steelbar_3"


# [claude] ATV-C-24
@pytest.mark.xfail(strict=True, reason=BUG_1691)
def test_atv_c_24__the_suffixed_code_stays_within_50_the_base_is_cut(db, w1, u1, mk_tag):
    """ATV-C-24 — the suffixed code stays within 50: the base is cut.
    Rules: `create_tag` R7 [BUG-1691]"""
    mk_tag("a" * 50, "a" * 50)
    commit_point(db)
    result = svc.create_tag(db, tag_in=AccountTagCreate(name="a" * 50 + "!"), workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.tag_code == "a" * 48 + "_2"


# [claude] ATV-C-25
@pytest.mark.xfail(strict=True, reason=BUG_1689)
def test_atv_c_25__a_live_name_in_another_case_is_refused_with_the_submitted_name(db, w1, u1, mk_tag):
    """ATV-C-25 — a live name in another case is refused, with the submitted name.
    Rules: `create_tag` R8 [BUG-1689], Errors row 1"""
    mk_tag("Vendor X", "vendor_1")
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_tag(
            db, tag_in=AccountTagCreate(name="VENDOR X", tag_code="vendor_2"), workspace_id=w1.id, user_id=u1.id,
        )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Tag with name 'VENDOR X' already exists"
    # Then 4
    assert written(db) == before


# [claude] ATV-C-26
@pytest.mark.xfail(strict=True, reason=BUG_1689)
def test_atv_c_26__a_system_tags_name_blocks_too(db, w1, u1, mk_system_tag):
    """ATV-C-26 — a system tag's name blocks too.
    Rules: `create_tag` R8 [BUG-1689], Errors row 1"""
    mk_system_tag("Supplier", "supplier")
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_tag(
            db, tag_in=AccountTagCreate(name="supplier", tag_code="supplier_2"), workspace_id=w1.id, user_id=u1.id,
        )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Tag with name 'supplier' already exists"
    # Then 4
    assert written(db) == before


# [claude] ATV-C-27
@pytest.mark.xfail(strict=True, reason=BUG_1689)
def test_atv_c_27__the_database_refuses_a_second_live_tag_with_the_same_name_ignoring_case(db, w1, mk_tag):
    """ATV-C-27 — the database refuses a second live tag with the same name ignoring case.
    Rules: `create_tag` R8 [BUG-1689]"""
    mk_tag("Vendor X", "vendor_1")
    commit_point(db)
    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            db.add(AccountTag(**_tag_fields(w1, "VENDOR X", "vendor_2", {})))
            db.flush()
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert count_tags(db, workspace_id=w1.id) == 1


# [claude] ATV-C-28
@pytest.mark.xfail(strict=True, reason=BUG_1689)
def test_atv_c_28__the_name_is_checked_before_the_code(db, w1, u1, mk_tag):
    """ATV-C-28 — the name is checked before the code.
    Rules: `create_tag` R8 [BUG-1689], Errors row 1"""
    mk_tag("Vendor X", "vendor_x")
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_tag(
            db, tag_in=AccountTagCreate(name="Vendor X", tag_code="vendor_x"), workspace_id=w1.id, user_id=u1.id,
        )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Tag with name 'Vendor X' already exists"
    # Then 4
    assert written(db) == before


# [claude] ATV-C-29
@pytest.mark.xfail(strict=True, reason=BUG_1689)
def test_atv_c_29__a_padded_names_409_names_the_trimmed_name(db, w1, u1, mk_tag):
    """ATV-C-29 — a padded name's 409 names the trimmed name.
    Rules: `create_tag` R8 [BUG-1689], Errors row 1"""
    mk_tag("Vendor X", "vendor_1")
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_tag(
            db, tag_in=AccountTagCreate(name=" VENDOR X ", tag_code="vendor_2"), workspace_id=w1.id, user_id=u1.id,
        )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Tag with name 'VENDOR X' already exists"
    # Then 4
    assert written(db) == before


# [claude] ATV-C-30
@pytest.mark.xfail(strict=True, reason=BUG_1689)
def test_atv_c_30__a_name_refusal_leaves_other_uncommitted_changes_alone(db, w1, u1, mk_tag, mk_extra):
    """ATV-C-30 — a name refusal leaves other uncommitted changes alone.
    Rules: `create_tag` R8, R11 [BUG-1689]; S3"""
    mk_tag("Vendor X", "vendor_1")
    commit_point(db)
    mk_extra()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.create_tag(
            db, tag_in=AccountTagCreate(name="VENDOR X", tag_code="vendor_2"), workspace_id=w1.id, user_id=u1.id,
        )
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert count_tags(db, tag_code="extra") == 1


# [claude] ATV-C-31
def test_atv_c_31__a_deleted_tags_name_does_not_block(db, w1, u1, mk_tag):
    """ATV-C-31 — a deleted tag's name does not block.
    Rules: `create_tag` R8"""
    kd = mk_tag("Vendor X", "old_vendor", **DELETED)
    commit_point(db)
    result = svc.create_tag(
        db, tag_in=AccountTagCreate(name="Vendor X", tag_code="vendor_x"), workspace_id=w1.id, user_id=u1.id,
    )

    # Then 1
    assert result.name == "Vendor X"
    assert result.id != kd.id


# [claude] ATV-C-32
def test_atv_c_32__another_workspaces_name_does_not_block(db, w1, w2, u1, mk_tag):
    """ATV-C-32 — another workspace's name does not block.
    Rules: `create_tag` R8"""
    mk_tag("Vendor X", "vendor_x", workspace_id=w2.id)
    commit_point(db)
    result = svc.create_tag(
        db, tag_in=AccountTagCreate(name="Vendor X", tag_code="vendor_w1"), workspace_id=w1.id, user_id=u1.id,
    )

    # Then 1
    assert result.name == "Vendor X"
    assert result.workspace_id == w1.id


# [claude] ATV-C-33
@pytest.mark.xfail(strict=True, reason=BUG_1682)
def test_atv_c_33__a_whitespace_only_name_is_refused_by_the_schema(db):
    """ATV-C-33 — a whitespace-only name is refused by the schema.
    Rules: `create_tag` R9 [BUG-1682], Errors row 3"""
    commit_point(db)
    before = written(db)
    # Then 1
    with pytest.raises(PydanticValidationError):
        AccountTagCreate(name="   ")
    # Then 2
    assert written(db) == before


# [claude] ATV-C-34
@pytest.mark.xfail(strict=True, reason=BUG_1682)
def test_atv_c_34__a_padded_name_is_stored_trimmed(db, w1, u1):
    """ATV-C-34 — a padded name is stored trimmed.
    Rules: `create_tag` R9 [BUG-1682]"""
    commit_point(db)
    result = svc.create_tag(
        db, tag_in=AccountTagCreate(name=" Bolt ", tag_code="bolt"), workspace_id=w1.id, user_id=u1.id,
    )

    # Then 1
    assert result.tag_code == "bolt"
    # Then 2
    db.rollback()
    assert new_row(db, w1).name == "Bolt"


# [claude] ATV-C-35
def test_atv_c_35__a_new_tag_carries_every_given_field_and_the_fixed_ones_committed_and_returned_re_read(
    db, w1, u1,
):
    """ATV-C-35 — a new tag carries every given field and the fixed ones; committed and returned re-read.
    Rules: `create_tag` R10, Returns; S1"""
    commit_point(db)
    result = svc.create_tag(
        db,
        tag_in=AccountTagCreate(name="Steel", tag_code="steel", color="#FF0000", icon="bolt", description="Metal stock"),
        workspace_id=w1.id, user_id=u1.id,
    )

    # Then 1
    assert "created_at" not in unloaded(result)
    assert "tag_code" not in unloaded(result)
    assert "name" not in unloaded(result)
    assert "usage_count" not in unloaded(result)
    # Then 2
    assert isinstance(result, AccountTag)
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


# [claude] ATV-C-36
def test_atv_c_36__a_client_cannot_make_a_system_tag(db, w1, u1):
    """ATV-C-36 — a client cannot make a system tag.
    Rules: `create_tag` R10"""
    data = AccountTagCreate.model_validate(
        {"name": "Steel", "is_system_tag": True, "usage_count": 5, "is_active": False},
    )
    commit_point(db)
    result = svc.create_tag(db, tag_in=data, workspace_id=w1.id, user_id=u1.id)

    # Then 1
    assert result.is_system_tag is False
    # Then 2
    db.rollback()
    row = new_row(db, w1)
    assert row.is_system_tag is False
    assert row.usage_count == 0
    assert row.is_active is True


# [claude] ATV-C-37
def test_atv_c_37__a_failing_commit_is_rolled_back_and_re_raised_other_uncommitted_changes_go_too(
    db, w1, u1, mk_tag, mk_extra,
):
    """ATV-C-37 — a failing commit is rolled back and re-raised; other uncommitted changes go too.
    Rules: `create_tag` R11; S2"""
    mk_tag("Vendor X", "vendor_x")
    commit_point(db)
    mk_extra()
    boom = RuntimeError("boom")
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=boom), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.create_tag(db, tag_in=AccountTagCreate(name="Steel"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert count_tags(db, name="Steel") == 0
    # Then 4
    assert count_tags(db, tag_code="extra") == 0
    # Then 5
    assert exc.value is boom


# [claude] ATV-C-38
def test_atv_c_38__a_failing_re_read_after_the_commit_leaves_the_tag_saved(db, w1, u1):
    """ATV-C-38 — a failing re-read after the commit leaves the tag saved.
    Rules: `create_tag` R11; S2"""
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
            svc.create_tag(db, tag_in=AccountTagCreate(name="Steel"), workspace_id=w1.id, user_id=u1.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    assert count_tags(db, workspace_id=w1.id, name="Steel") == 1


# [claude] ATV-C-39
def test_atv_c_39__a_database_error_inside_the_write_is_rolled_back_and_passed_on(db, w1, u1, mk_extra):
    """ATV-C-39 — a database error inside the write is rolled back and passed on.
    Rules: `create_tag` R11; S2"""
    commit_point(db)
    before = written(db)
    mk_extra()
    data = AccountTagCreate.model_construct(name=None, tag_code="nameless", color=None, icon=None, description=None)
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


# --------------------------------------------------------------------------- #
# AccountTagService.update_tag
# --------------------------------------------------------------------------- #

# [claude] ATV-U-01
def test_atv_u_01__another_workspaces_id_404_nothing_written_other_uncommitted_changes_stay(
    db, w1, w2, mk_tag, mk_extra,
):
    """ATV-U-01 — another workspace's id: 404, nothing written, other uncommitted changes stay.
    Rules: `update_tag` R1, R9, Errors row 1; S3"""
    mk_tag("Far One", "far_one", workspace_id=w2.id)
    mk_tag("Vendor X", "vendor_x")
    kz2 = mk_tag("Far Two", "far_two", workspace_id=w2.id)
    commit_point(db)
    before_kz2 = snap_before(db, kz2)
    mk_extra()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_tag(db, tag_id=kz2.id, tag_in=AccountTagUpdate(name="Hacked"), workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Tag not found"
    # Then 4
    assert count_tags(db, tag_code="extra") == 1
    # Then 5
    assert snap(db, kz2) == before_kz2


# [claude] ATV-U-02
def test_atv_u_02__id_0_gets_the_404(db, w1, mk_tag):
    """ATV-U-02 — id 0 gets the 404.
    Rules: `update_tag` R1, Errors row 1"""
    k1 = mk_tag("Vendor X", "vendor_x")
    commit_point(db)
    before_k1 = snap_before(db, k1)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_tag(db, tag_id=0, tag_in=AccountTagUpdate(name="Hacked"), workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Tag not found"
    # Then 4
    assert snap(db, k1) == before_k1


# [claude] ATV-U-03
@pytest.mark.xfail(strict=True, reason=BUG_1685)
def test_atv_u_03__a_deleted_tag_is_not_found(db, w1, mk_tag):
    """ATV-U-03 — a deleted tag is not found.
    Rules: `update_tag` R2 [BUG-1685], Errors row 1"""
    kd = mk_tag("Obsolete", "obsolete", **DELETED)
    commit_point(db)
    before_kd = snap_before(db, kd)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_tag(db, tag_id=kd.id, tag_in=AccountTagUpdate(name="Revived"), workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Tag not found"
    # Then 4
    assert snap(db, kd) == before_kd


# [claude] ATV-U-04
@pytest.mark.xfail(strict=True, reason=BUG_1685)
def test_atv_u_04__is_active_true_cannot_bring_a_deleted_tag_back(db, w1, mk_tag):
    """ATV-U-04 — is_active true cannot bring a deleted tag back.
    Rules: `update_tag` R2 [BUG-1685], Errors row 1"""
    kd = mk_tag("Obsolete", "obsolete", **DELETED)
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_tag(db, tag_id=kd.id, tag_in=AccountTagUpdate(is_active=True), workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    db.rollback()
    assert reread(db, kd).is_active is False


# [claude] ATV-U-05
def test_atv_u_05__a_system_tag_403_nothing_written_other_uncommitted_changes_stay(
    db, w1, mk_system_tag, mk_extra,
):
    """ATV-U-05 — a system tag: 403, nothing written, other uncommitted changes stay.
    Rules: `update_tag` R3, R9, Errors row 2; S3"""
    ks = mk_system_tag("Supplier", "supplier")
    commit_point(db)
    before_ks = snap_before(db, ks)
    mk_extra()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_tag(db, tag_id=ks.id, tag_in=AccountTagUpdate(color="#00FF00"), workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert exc.value.detail == "System tags cannot be modified"
    # Then 4
    assert count_tags(db, tag_code="extra") == 1
    # Then 5
    assert snap(db, ks) == before_ks


# [claude] ATV-U-06
def test_atv_u_06__another_workspaces_system_tag_gets_the_404_not_the_403(db, w1, w2, mk_system_tag):
    """ATV-U-06 — another workspace's system tag gets the 404, not the 403.
    Rules: `update_tag` R1, R3"""
    kz = mk_system_tag("Far Supplier", "far_supplier", workspace_id=w2.id)
    commit_point(db)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_tag(db, tag_id=kz.id, tag_in=AccountTagUpdate(color="#00FF00"), workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Tag not found"


# [claude] ATV-U-07
def test_atv_u_07__every_field_sent_is_written_committed_and_returned_re_read(db, w1, mk_tag):
    """ATV-U-07 — every field sent is written; committed and returned re-read.
    Rules: `update_tag` R4, R9, Returns; S1"""
    k1 = mk_tag("Vendor X", "vendor_x", color="#000000", icon="box", description="Old", usage_count=3)
    commit_point(db)
    result = svc.update_tag(
        db, tag_id=k1.id,
        tag_in=AccountTagUpdate(name="Vendor Prime", color="#FF0000", icon="star", description="New"),
        workspace_id=w1.id,
    )

    # Then 1
    assert "name" not in unloaded(result)
    assert "color" not in unloaded(result)
    assert "tag_code" not in unloaded(result)
    # Then 2
    assert result.id == k1.id
    assert result.name == "Vendor Prime"
    # Then 3
    db.rollback()
    row = reread(db, k1)
    assert row.name == "Vendor Prime"
    assert row.color == "#FF0000"
    assert row.icon == "star"
    assert row.description == "New"
    # Then 4
    row = reread(db, k1)
    assert row.tag_code == "vendor_x"
    assert row.usage_count == 3
    assert row.is_active is True


# [claude] ATV-U-08
def test_atv_u_08__omitted_fields_stay(db, w1, mk_tag):
    """ATV-U-08 — omitted fields stay.
    Rules: `update_tag` R4"""
    k1 = mk_tag("Vendor X", "vendor_x", color="#000000", icon="box", description="Old")
    commit_point(db)
    result = svc.update_tag(db, tag_id=k1.id, tag_in=AccountTagUpdate(color="#FF0000"), workspace_id=w1.id)

    # Then 1
    assert result.color == "#FF0000"
    # Then 2
    db.rollback()
    row = reread(db, k1)
    assert row.name == "Vendor X"
    assert row.icon == "box"
    assert row.description == "Old"
    assert row.tag_code == "vendor_x"


# [claude] ATV-U-09
@pytest.mark.xfail(strict=True, reason=BUG_1692)
def test_atv_u_09__a_tag_code_in_the_body_is_ignored_the_other_fields_apply(db, w1, mk_tag):
    """ATV-U-09 — a tag_code in the body is ignored; the other fields apply.
    Rules: `update_tag` R4a [BUG-1692]"""
    mk_tag("Vendor X", "vendor_x")
    k2 = mk_tag("Other", "other")
    data = AccountTagUpdate.model_validate({"name": "Other Two", "tag_code": "vendor_x"})
    commit_point(db)
    result = svc.update_tag(db, tag_id=k2.id, tag_in=data, workspace_id=w1.id)

    # Then 1
    assert result.id == k2.id
    assert result.name == "Other Two"
    # Then 2
    db.rollback()
    assert reread(db, k2).name == "Other Two"
    # Then 3
    assert reread(db, k2).tag_code == "other"


# [claude] ATV-U-10
def test_atv_u_10__a_tag_code_sent_as_null_changes_nothing(db, w1, mk_tag):
    """ATV-U-10 — a tag_code sent as null changes nothing.
    Rules: `update_tag` R4a"""
    k1 = mk_tag("Vendor X", "vendor_x")
    data = AccountTagUpdate.model_validate({"tag_code": None})
    commit_point(db)
    before_k1 = snap_before(db, k1)
    result = svc.update_tag(db, tag_id=k1.id, tag_in=data, workspace_id=w1.id)

    # Then 1
    assert result.id == k1.id
    assert result.tag_code == "vendor_x"
    # Then 2
    assert snap(db, k1) == before_k1


# [claude] ATV-U-11
@pytest.mark.xfail(strict=True, reason=BUG_1692)
def test_atv_u_11__a_body_with_only_a_tag_code_value_changes_nothing(db, w1, mk_tag):
    """ATV-U-11 — a body with only a tag_code value changes nothing.
    Rules: `update_tag` R4a [BUG-1692]"""
    k1 = mk_tag("Vendor X", "vendor_x")
    data = AccountTagUpdate.model_validate({"tag_code": "renamed"})
    commit_point(db)
    before_k1 = snap_before(db, k1)
    result = svc.update_tag(db, tag_id=k1.id, tag_in=data, workspace_id=w1.id)

    # Then 1
    assert result.id == k1.id
    # Then 2
    assert snap(db, k1) == before_k1


# [claude] ATV-U-12
@pytest.mark.xfail(strict=True, reason=BUG_1688)
def test_atv_u_12__explicit_null_clears_color_icon_and_description(db, w1, mk_tag):
    """ATV-U-12 — explicit null clears color, icon and description.
    Rules: `update_tag` R5 [BUG-1688]"""
    k1 = mk_tag("Vendor X", "vendor_x", color="#000000", icon="box", description="Old")
    commit_point(db)
    result = svc.update_tag(
        db, tag_id=k1.id, tag_in=AccountTagUpdate(color=None, icon=None, description=None), workspace_id=w1.id,
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
    assert reread(db, k1).name == "Vendor X"


# [claude] ATV-U-13
@pytest.mark.xfail(strict=True, reason=BUG_1688)
def test_atv_u_13__null_for_name_is_refused_by_the_schema(db, mk_tag):
    """ATV-U-13 — null for name is refused by the schema.
    Rules: `update_tag` R5 [BUG-1688], Errors row 4"""
    k1 = mk_tag("Vendor X", "vendor_x")
    commit_point(db)
    before_k1 = snap_before(db, k1)
    # Then 1
    with pytest.raises(PydanticValidationError):
        AccountTagUpdate(name=None)
    # Then 2
    assert snap(db, k1) == before_k1


# [claude] ATV-U-14
@pytest.mark.xfail(strict=True, reason=BUG_1688)
def test_atv_u_14__null_for_is_active_is_refused_by_the_schema(db, mk_tag):
    """ATV-U-14 — null for is_active is refused by the schema.
    Rules: `update_tag` R5 [BUG-1688], Errors row 4"""
    k1 = mk_tag("Vendor X", "vendor_x")
    commit_point(db)
    before_k1 = snap_before(db, k1)
    # Then 1
    with pytest.raises(PydanticValidationError):
        AccountTagUpdate(is_active=None)
    # Then 2
    assert snap(db, k1) == before_k1


# [claude] ATV-U-15
@pytest.mark.xfail(strict=True, reason=BUG_1689)
def test_atv_u_15__a_rename_to_another_live_tags_name_is_refused(db, w1, mk_tag):
    """ATV-U-15 — a rename to another live tag's name is refused.
    Rules: `update_tag` R6 [BUG-1689], Errors row 3"""
    mk_tag("Vendor X", "vendor_x")
    k2 = mk_tag("Other", "other")
    commit_point(db)
    before_k2 = snap_before(db, k2)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_tag(db, tag_id=k2.id, tag_in=AccountTagUpdate(name="vendor x"), workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Tag with name 'vendor x' already exists"
    # Then 4
    assert snap(db, k2) == before_k2


# [claude] ATV-U-16
@pytest.mark.xfail(strict=True, reason=BUG_1689)
def test_atv_u_16__a_padded_renames_409_names_the_trimmed_name(db, w1, mk_tag):
    """ATV-U-16 — a padded rename's 409 names the trimmed name.
    Rules: `update_tag` R6 [BUG-1689], Errors row 3"""
    mk_tag("Vendor X", "vendor_x")
    k2 = mk_tag("Other", "other")
    commit_point(db)
    before_k2 = snap_before(db, k2)
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_tag(db, tag_id=k2.id, tag_in=AccountTagUpdate(name=" vendor x "), workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert exc.value.detail == "Tag with name 'vendor x' already exists"
    # Then 4
    assert snap(db, k2) == before_k2


# [claude] ATV-U-17
@pytest.mark.xfail(strict=True, reason=BUG_1689)
def test_atv_u_17__a_name_refusal_on_rename_leaves_other_uncommitted_changes_alone(db, w1, mk_tag, mk_extra):
    """ATV-U-17 — a name refusal on rename leaves other uncommitted changes alone.
    Rules: `update_tag` R6, R9 [BUG-1689]; S3"""
    mk_tag("Vendor X", "vendor_x")
    k2 = mk_tag("Other", "other")
    commit_point(db)
    mk_extra()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.update_tag(db, tag_id=k2.id, tag_in=AccountTagUpdate(name="vendor x"), workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 409
    # Then 3
    assert count_tags(db, tag_code="extra") == 1


# [claude] ATV-U-18
def test_atv_u_18__the_tags_own_name_in_another_case_is_accepted(db, w1, mk_tag):
    """ATV-U-18 — the tag's own name in another case is accepted.
    Rules: `update_tag` R6"""
    k1 = mk_tag("Vendor X", "vendor_x")
    commit_point(db)
    result = svc.update_tag(db, tag_id=k1.id, tag_in=AccountTagUpdate(name="VENDOR X"), workspace_id=w1.id)

    # Then 1
    assert result.name == "VENDOR X"
    # Then 2
    db.rollback()
    assert reread(db, k1).name == "VENDOR X"


# [claude] ATV-U-19
def test_atv_u_19__is_active_false_hides_a_live_tag_exactly_as_a_delete(db, w1, mk_tag, mk_account, mk_link):
    """ATV-U-19 — is_active false hides a live tag exactly as a delete.
    Rules: `update_tag` R7"""
    k1 = mk_tag("Vendor X", "vendor_x", usage_count=3)
    a1 = mk_account()
    link = mk_link(a1, k1)
    commit_point(db)
    result = svc.update_tag(db, tag_id=k1.id, tag_in=AccountTagUpdate(is_active=False), workspace_id=w1.id)

    # Then 1
    assert result.is_active is False
    # Then 2
    db.rollback()
    row = reread(db, k1)
    assert row.is_active is False
    assert row.usage_count == 3
    assert row.name == "Vendor X"
    assert row.tag_code == "vendor_x"
    # Then 3
    link_row = reread(db, link)
    assert link_row.tag_id == k1.id
    assert link_row.account_id == a1.id
    # Then 4
    assert svc.get_tags(db, workspace_id=w1.id) == []


# [claude] ATV-U-20
@pytest.mark.xfail(strict=True, reason=BUG_1682)
def test_atv_u_20__a_blank_new_name_is_refused_by_the_schema(db, mk_tag):
    """ATV-U-20 — a blank new name is refused by the schema.
    Rules: `update_tag` R8 [BUG-1682]"""
    k1 = mk_tag("Vendor X", "vendor_x")
    commit_point(db)
    before_k1 = snap_before(db, k1)
    # Then 1
    with pytest.raises(PydanticValidationError):
        AccountTagUpdate(name="  ")
    # Then 2
    assert snap(db, k1) == before_k1


# [claude] ATV-U-21
@pytest.mark.xfail(strict=True, reason=BUG_1682)
def test_atv_u_21__a_padded_new_name_is_stored_trimmed(db, w1, mk_tag):
    """ATV-U-21 — a padded new name is stored trimmed.
    Rules: `update_tag` R8 [BUG-1682]"""
    k1 = mk_tag("Vendor X", "vendor_x")
    data = AccountTagUpdate(name="  Vendor Prime  ")
    commit_point(db)
    result = svc.update_tag(db, tag_id=k1.id, tag_in=data, workspace_id=w1.id)

    # Then 1
    assert result.id == k1.id
    # Then 2
    db.rollback()
    assert reread(db, k1).name == "Vendor Prime"


# [claude] ATV-U-22
def test_atv_u_22__a_failing_commit_is_rolled_back_and_re_raised_other_uncommitted_changes_go_too(
    db, w1, mk_tag, mk_extra,
):
    """ATV-U-22 — a failing commit is rolled back and re-raised; other uncommitted changes go too.
    Rules: `update_tag` R9; S2"""
    k1 = mk_tag("Vendor X", "vendor_x")
    commit_point(db)
    before_k1 = snap_before(db, k1)
    mk_extra()
    boom = RuntimeError("boom")
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=boom), \
                patch.object(db, "rollback", wraps=db.rollback) as rb:
            svc.update_tag(db, tag_id=k1.id, tag_in=AccountTagUpdate(name="Steel"), workspace_id=w1.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    assert rb.call_count >= 1
    # Then 3
    assert snap(db, k1) == before_k1
    # Then 4
    assert count_tags(db, tag_code="extra") == 0
    # Then 5
    assert exc.value is boom


# [claude] ATV-U-23
def test_atv_u_23__a_failing_re_read_after_the_commit_leaves_the_change_saved(db, w1, mk_tag):
    """ATV-U-23 — a failing re-read after the commit leaves the change saved.
    Rules: `update_tag` R9; S2"""
    k1 = mk_tag("Vendor X", "vendor_x")
    commit_point(db)
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "refresh", side_effect=RuntimeError("boom")):
            svc.update_tag(db, tag_id=k1.id, tag_in=AccountTagUpdate(name="Steel"), workspace_id=w1.id)
    # Then 1
    assert str(exc.value) == "boom"
    # Then 2
    db.rollback()
    row = reread(db, k1)
    assert row.name == "Steel"
    assert row.is_active is True


# --------------------------------------------------------------------------- #
# AccountTagService.delete_tag
# --------------------------------------------------------------------------- #

# [claude] ATV-D-01
def test_atv_d_01__a_live_user_tag_gets_is_active_false_and_nothing_else_committed(
    db, w1, mk_tag, mk_account, mk_link,
):
    """ATV-D-01 — a live user tag gets is_active False and nothing else; committed.
    Rules: `delete_tag` R4, Returns; S1"""
    k1 = mk_tag("Vendor X", "vendor_x", usage_count=3, color="#000000")
    a1 = mk_account()
    link = mk_link(a1, k1)
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
    assert row.name == "Vendor X"
    assert row.tag_code == "vendor_x"
    assert row.color == "#000000"
    assert row.is_system_tag is False
    # Then 4
    link_row = reread(db, link)
    assert link_row.tag_id == k1.id
    assert link_row.account_id == a1.id
    # Then 5
    assert svc.get_tags(db, workspace_id=w1.id) == []


# [claude] ATV-D-02
def test_atv_d_02__another_workspaces_id_404_nothing_written_other_uncommitted_changes_stay(
    db, w1, w2, mk_tag, mk_extra,
):
    """ATV-D-02 — another workspace's id: 404, nothing written, other uncommitted changes stay.
    Rules: `delete_tag` R1, R5, Errors row 1; S3"""
    kz1 = mk_tag("Far One", "far_one", workspace_id=w2.id)
    mk_tag("Vendor X", "vendor_x")
    mk_tag("Far Two", "far_two", workspace_id=w2.id)
    commit_point(db)
    before_kz1 = snap_before(db, kz1)
    mk_extra()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_tag(db, tag_id=kz1.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 404
    # Then 3
    assert exc.value.detail == "Tag not found"
    # Then 4
    assert count_tags(db, tag_code="extra") == 1
    # Then 5
    assert snap(db, kz1) == before_kz1


# [claude] ATV-D-03
def test_atv_d_03__id_0_gets_the_404(db, w1, mk_tag):
    """ATV-D-03 — id 0 gets the 404.
    Rules: `delete_tag` R1, Errors row 1"""
    k1 = mk_tag("Vendor X", "vendor_x")
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


# [claude] ATV-D-04
@pytest.mark.xfail(strict=True, reason=BUG_1685)
def test_atv_d_04__an_already_deleted_tag_is_not_found(db, w1, mk_tag):
    """ATV-D-04 — an already deleted tag is not found.
    Rules: `delete_tag` R2 [BUG-1685], Errors row 1"""
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


# [claude] ATV-D-05
def test_atv_d_05__a_system_tag_403_nothing_written(db, w1, mk_system_tag):
    """ATV-D-05 — a system tag: 403, nothing written.
    Rules: `delete_tag` R3, Errors row 2"""
    ks = mk_system_tag("Supplier", "supplier")
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


# [claude] ATV-D-06
def test_atv_d_06__a_system_tag_refusal_leaves_other_uncommitted_changes_alone(db, w1, mk_system_tag, mk_extra):
    """ATV-D-06 — a system-tag refusal leaves other uncommitted changes alone.
    Rules: `delete_tag` R3, R5; S3"""
    ks = mk_system_tag("Supplier", "supplier")
    commit_point(db)
    mk_extra()
    # Then 1
    with pytest.raises(HTTPException) as exc:
        svc.delete_tag(db, tag_id=ks.id, workspace_id=w1.id)
    # Then 2
    assert exc.value.status_code == 403
    # Then 3
    assert count_tags(db, tag_code="extra") == 1


# [claude] ATV-D-07
def test_atv_d_07__a_failing_commit_is_rolled_back_and_re_raised_the_tag_stays_live(db, w1, mk_tag, mk_extra):
    """ATV-D-07 — a failing commit is rolled back and re-raised: the tag stays live.
    Rules: `delete_tag` R5; S2"""
    k1 = mk_tag("Vendor X", "vendor_x")
    commit_point(db)
    before_k1 = snap_before(db, k1)
    mk_extra()
    boom = RuntimeError("boom")
    with pytest.raises(RuntimeError) as exc:
        with patch.object(db, "commit", side_effect=boom), \
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
    # Then 5
    assert exc.value is boom
