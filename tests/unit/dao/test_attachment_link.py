"""Unit tests for app/dao/attachment_link.py.

Implements tests/unit/dao/attachment_link.cases.md, one test per case, in card
order. Real Postgres session (`db` fixture). Nothing is mocked and no clock
is patched (Conventions, Externals: None).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
from datetime import timedelta
from unittest import mock

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import DataError, IntegrityError

from app.dao.attachment_link import AttachmentLinkCreateSchema, attachment_link_dao
from app.models.attachment import Attachment
from app.models.attachment_link import AttachmentLink
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton attachment_link_dao; Schema = AttachmentLinkCreateSchema"
dao = attachment_link_dao
Schema = AttachmentLinkCreateSchema

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999


# --------------------------------------------------------------------------- #
# Conventions -> the rows that exist in every test
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


# Convention "W1, W2 = two workspaces rows; U1 = a profiles row", built in that order
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


@pytest.fixture
def u1(db, w2):
    return make_profile(db)


# Convention "they exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders (each flushes before it returns)
# --------------------------------------------------------------------------- #

def _attachment_fields(workspace, profile, columns):
    fields = {"workspace_id": workspace.id, "file_name": "file.png", "mime_type": "image/png", "file_size": 100,
              "uploaded_by": profile.id, "upload_status": "ready"}
    fields.update(columns)
    return fields


# Convention "attachment"; after "but" the card's columns override the defaults
@pytest.fixture
def mk_attachment(db, w1, u1):
    """mk_attachment(**columns) -> Attachment."""
    def _mk(**columns):
        return _add(db, Attachment(**_attachment_fields(w1, u1, columns)))
    return _mk


# Convention "deleted" adds is_deleted True, deleted_by U1.id
@pytest.fixture
def mk_deleted_attachment(mk_attachment, u1):
    """mk_deleted_attachment(**columns) -> Attachment."""
    def _mk(**columns):
        return mk_attachment(**{"is_deleted": True, "deleted_by": u1.id, **columns})
    return _mk


def _link_fields(workspace, profile, attachment, columns):
    fields = {"workspace_id": workspace.id, "attachment_id": attachment.id, "entity_type": "purchase_order",
              "entity_id": 501, "linked_by": profile.id}
    fields.update(columns)
    return fields


# Convention "link on X"; after "but" the card's columns override the defaults
@pytest.fixture
def mk_link(db, w1, u1):
    """mk_link(attachment, **columns) -> AttachmentLink."""
    def _mk(attachment, **columns):
        return _add(db, AttachmentLink(**_link_fields(w1, u1, attachment, columns)))
    return _mk


# The "101 attachments E1 … E101 ... 101 links, built with add_all" Givens of GA-18, GA-19, CN-03
@pytest.fixture
def mk_many_linked(db, w1, u1):
    """mk_many_linked(count) -> `all_ids`, the set of the ids of E1 … Ecount (Ek named f"f{k}.png", each linked)."""
    def _mk(count):
        rows = [Attachment(**_attachment_fields(w1, u1, {"file_name": f"f{k}.png"})) for k in range(1, count + 1)]
        db.add_all(rows)
        db.flush()
        db.add_all([AttachmentLink(**_link_fields(w1, u1, row, {})) for row in rows])
        db.flush()
        return {row.id for row in rows}
    return _mk


# Convention "age(X, n)"
def age(db, row, n):
    db.execute(text("UPDATE attachments SET uploaded_at = now() - make_interval(days => :n) WHERE id = :i"),
               {"n": n, "i": row.id})
    db.expire_all()


# Convention "bump(X)"
def bump(db, row):
    db.execute(text("UPDATE attachments SET note = 'bumped' WHERE id = :i"), {"i": row.id})
    db.expire_all()


# Convention "bumpL(L)"
def bump_l(db, row):
    db.execute(text("UPDATE attachment_links SET linked_by = linked_by WHERE id = :i"), {"i": row.id})
    db.expire_all()


# Convention "seqscan"
def seqscan(db):
    db.execute(text("SET LOCAL enable_indexscan = off"))
    db.execute(text("SET LOCAL enable_bitmapscan = off"))
    db.execute(text("SET LOCAL enable_indexonlyscan = off"))


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

# Convention "ids(result)": in the order returned
def ids(result):
    return [row.id for row in result]


# Convention "re-read X": expire, then SELECT X by id
def reread(db, row):
    db.expire_all()
    model = type(row)
    return db.execute(select(model).where(model.id == sa_inspect(row).identity[0])).scalar_one_or_none()


# Convention "links_of(X)"
def links_of(db, row):
    return db.scalar(text("SELECT count(*) FROM attachment_links WHERE attachment_id = :i"), {"i": row.id})


# Convention "nothing written": the numbers of attachments and of attachment_links rows stored (all workspaces)
def stored_count(db):
    return (db.scalar(select(func.count()).select_from(Attachment.__table__)),
            db.scalar(select(func.count()).select_from(AttachmentLink.__table__)))


# Convention "rolled back": a spy that wraps db.commit (still callable, records calls)
def commit_spy(db):
    return mock.patch.object(db, "commit", wraps=db.commit)


# Convention "Statement recorder": the SQL text of every statement the session's
# connection sends while the block runs.
class StatementRecorder:
    def __init__(self, db):
        self.bind = db.get_bind()
        self.statements = []

    def _record(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append(statement)

    def __enter__(self):
        event.listen(self.bind, "before_cursor_execute", self._record)
        return self

    def __exit__(self, *exc_info):
        event.remove(self.bind, "before_cursor_execute", self._record)
        return False

    def written(self):
        return [s for s in self.statements if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]

    def sql(self):
        """The one SELECT sent; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.statements if s.lstrip().upper().startswith("SELECT")]
        return statement


# Convention "order_part": the text of `sql` after its first ORDER BY and before any LIMIT ("" when there is no ORDER BY)
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1].split("LIMIT", 1)[0] if "ORDER BY" in sql else ""


# --------------------------------------------------------------------------- #
# AttachmentLinkCreateSchema
# --------------------------------------------------------------------------- #


# [claude] ALK-SC-01
def test_alk_sc_01__keywords_are_stored_and_model_dump_gives_exactly_the_five_keys():
    """ALK-SC-01 — keywords are stored and model_dump gives exactly the five keys.
    Rules: `AttachmentLinkCreateSchema` R1, R2, Returns"""
    s = Schema(workspace_id=11, attachment_id=22, entity_type="project", entity_id=33, linked_by=44)

    result = s.model_dump()

    # Then 1
    assert result == {"workspace_id": 11, "attachment_id": 22, "entity_type": "project", "entity_id": 33, "linked_by": 44}
    # Then 2
    assert s.entity_type == "project"


# [claude] ALK-SC-02
def test_alk_sc_02__nothing_is_validated_any_value_none_included_is_stored():
    """ALK-SC-02 — nothing is validated: any value, None included, is stored.
    Rules: `AttachmentLinkCreateSchema` R1, R2"""
    s = Schema(workspace_id=None, attachment_id="abc", entity_type="", entity_id=-5, linked_by=None)

    result = s.model_dump()

    # Then 1
    assert result == {"workspace_id": None, "attachment_id": "abc", "entity_type": "", "entity_id": -5, "linked_by": None}


# [claude] ALK-SC-03
def test_alk_sc_03__a_positional_call_raises_typeerror():
    """ALK-SC-03 — a positional call raises TypeError.
    Rules: `AttachmentLinkCreateSchema` R1, Errors"""
    # Then 1
    with pytest.raises(TypeError):
        Schema(11, 22, "project", 33, 44)


# [claude] ALK-SC-04
def test_alk_sc_04__a_missing_argument_raises_typeerror():
    """ALK-SC-04 — a missing argument raises TypeError.
    Rules: `AttachmentLinkCreateSchema` R1, Errors"""
    # Then 1
    with pytest.raises(TypeError):
        Schema(workspace_id=11, attachment_id=22, entity_type="project", entity_id=33)


# [claude] ALK-SC-05
def test_alk_sc_05__the_object_itself_passed_to_create_raises_typeerror_and_adds_nothing(db, w1, u1, mk_attachment):
    """ALK-SC-05 — the object itself passed to create raises TypeError and adds nothing.
    Rules: `AttachmentLinkCreateSchema` R3, Errors"""
    a = mk_attachment()
    s = Schema(workspace_id=w1.id, attachment_id=a.id, entity_type="purchase_order", entity_id=501, linked_by=u1.id)

    with pytest.raises(TypeError) as exc:
        dao.create(db, obj_in=s)

    # Then 1
    assert "by_alias" in str(exc.value)
    # Then 2
    assert links_of(db, a) == 0
    # Then 3
    assert len(db.new) == 0


# --------------------------------------------------------------------------- #
# AttachmentLinkDAO.get_attachments_for_entity
# --------------------------------------------------------------------------- #


# [claude] ALK-GA-01
def test_alk_ga_01__returns_a_list_of_the_record_s_ready_attachments(db, w1, mk_attachment, mk_link):
    """ALK-GA-01 — returns a list of the record's ready attachments.
    Rules: `get_attachments_for_entity` R1, Returns"""
    a = mk_attachment()
    mk_link(a)

    result = dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [a.id]
    # Then 3
    assert isinstance(result[0], Attachment)


# [claude] ALK-GA-02
def test_alk_ga_02__an_attachment_of_another_entity_id_is_not_returned(db, w1, mk_attachment, mk_link):
    """ALK-GA-02 — an attachment of another entity id is not returned.
    Rules: `get_attachments_for_entity` R1"""
    a = mk_attachment()
    mk_link(a)
    b = mk_attachment(file_name="b.png")
    mk_link(b, entity_id=502)

    result = dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501)

    # Then 1
    assert set(ids(result)) == {a.id}


# [claude] ALK-GA-03
def test_alk_ga_03__an_attachment_of_another_entity_type_is_not_returned(db, w1, mk_attachment, mk_link):
    """ALK-GA-03 — an attachment of another entity type is not returned.
    Rules: `get_attachments_for_entity` R1"""
    a = mk_attachment()
    mk_link(a)
    b = mk_attachment(file_name="b.png")
    mk_link(b, entity_type="project")

    result = dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501)

    # Then 1
    assert set(ids(result)) == {a.id}


# [claude] ALK-GA-04
def test_alk_ga_04__the_entity_type_in_capitals_matches_nothing(db, w1, mk_attachment, mk_link):
    """ALK-GA-04 — the entity type in capitals matches nothing.
    Rules: `get_attachments_for_entity` R1"""
    a = mk_attachment()
    mk_link(a)

    result = dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type="PURCHASE_ORDER", entity_id=501)

    # Then 1
    assert result == []


# [claude] ALK-GA-05
def test_alk_ga_05__a_part_of_the_entity_type_matches_nothing(db, w1, mk_attachment, mk_link):
    """ALK-GA-05 — a part of the entity type matches nothing.
    Rules: `get_attachments_for_entity` R1"""
    a = mk_attachment()
    mk_link(a)

    result = dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase", entity_id=501)

    # Then 1
    assert result == []


# [claude] ALK-GA-06
def test_alk_ga_06__a_leading_space_in_the_argument_matches_nothing(db, w1, mk_attachment, mk_link):
    """ALK-GA-06 — a leading space in the argument matches nothing.
    Rules: `get_attachments_for_entity` R1"""
    a = mk_attachment()
    mk_link(a)

    result = dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type=" purchase_order", entity_id=501)

    # Then 1
    assert result == []


# [claude] ALK-GA-07
def test_alk_ga_07__in_the_argument_is_no_wildcard_a_stored_purchase_order_is_not_found(db, w1, mk_attachment, mk_link):
    """ALK-GA-07 — _ in the argument is no wildcard: a stored "purchase-order" is not found.
    Rules: `get_attachments_for_entity` R1"""
    a = mk_attachment()
    mk_link(a)
    b = mk_attachment(file_name="b.png")
    mk_link(b, entity_type="purchase-order")

    result = dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501)

    # Then 1
    assert set(ids(result)) == {a.id}


# [claude] ALK-GA-08
def test_alk_ga_08__a_stored_type_with_a_leading_space_is_not_found(db, w1, mk_attachment, mk_link):
    """ALK-GA-08 — a stored type with a leading space is not found.
    Rules: `get_attachments_for_entity` R1"""
    a = mk_attachment()
    mk_link(a)
    b = mk_attachment(file_name="b.png")
    mk_link(b, entity_type=" purchase_order")

    result = dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501)

    # Then 1
    assert set(ids(result)) == {a.id}


# [claude] ALK-GA-09
def test_alk_ga_09__a_w2_link_to_a_w1_attachment_is_not_followed_for_w1(db, w1, w2, mk_attachment, mk_link):
    """ALK-GA-09 — a W2 link to a W1 attachment is not followed for W1.
    Rules: `get_attachments_for_entity` R2"""
    a = mk_attachment()
    mk_link(a)
    b = mk_attachment(file_name="b.png")
    mk_link(b, workspace_id=w2.id)

    result = dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501)

    # Then 1
    assert set(ids(result)) == {a.id}


# [claude] ALK-GA-10
def test_alk_ga_10__a_w2_link_to_a_w1_attachment_returns_that_attachment_for_w2(db, w2, mk_attachment, mk_link):
    """ALK-GA-10 — a W2 link to a W1 attachment returns that attachment for W2.
    Rules: `get_attachments_for_entity` R2"""
    a = mk_attachment()
    mk_link(a)
    b = mk_attachment(file_name="b.png")
    mk_link(b, workspace_id=w2.id)

    result = dao.get_attachments_for_entity(db, workspace_id=w2.id, entity_type="purchase_order", entity_id=501)

    # Then 1
    assert ids(result) == [b.id]


# [claude] ALK-GA-11
def test_alk_ga_11__a_pending_attachment_is_left_out(db, w1, mk_attachment, mk_link):
    """ALK-GA-11 — a pending attachment is left out.
    Rules: `get_attachments_for_entity` R3"""
    a = mk_attachment()
    mk_link(a)
    b = mk_attachment(upload_status="pending")
    mk_link(b)

    result = dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501)

    # Then 1
    assert set(ids(result)) == {a.id}


# [claude] ALK-GA-12
def test_alk_ga_12__a_failed_attachment_is_left_out(db, w1, mk_attachment, mk_link):
    """ALK-GA-12 — a failed attachment is left out.
    Rules: `get_attachments_for_entity` R3"""
    a = mk_attachment()
    mk_link(a)
    b = mk_attachment(upload_status="failed")
    mk_link(b)

    result = dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501)

    # Then 1
    assert set(ids(result)) == {a.id}


# [claude] ALK-GA-13
def test_alk_ga_13__a_deleted_ready_attachment_is_left_out(db, w1, mk_attachment, mk_deleted_attachment, mk_link):
    """ALK-GA-13 — a deleted ready attachment is left out.
    Rules: `get_attachments_for_entity` R3"""
    a = mk_attachment()
    mk_link(a)
    d = mk_deleted_attachment()
    mk_link(d)

    result = dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501)

    # Then 1
    assert set(ids(result)) == {a.id}


# [claude] ALK-GA-14
def test_alk_ga_14__the_status_filter_comes_before_the_page_a_newer_pending_row_takes_no_place(db, w1, mk_attachment, mk_link):
    """ALK-GA-14 — the status filter comes before the page: a newer pending row takes no place.
    Rules: `get_attachments_for_entity` R3"""
    x = mk_attachment(upload_status="pending")
    mk_link(x)
    a = mk_attachment()
    mk_link(a)
    age(db, a, 1)
    b = mk_attachment()
    mk_link(b)
    age(db, b, 2)

    result = dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501,
                                            skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] ALK-GA-15
def test_alk_ga_15__the_deleted_filter_comes_before_the_page_a_newer_deleted_row_takes_no_place(db, w1, mk_attachment, mk_deleted_attachment, mk_link):
    """ALK-GA-15 — the deleted filter comes before the page: a newer deleted row takes no place.
    Rules: `get_attachments_for_entity` R3"""
    x = mk_deleted_attachment()
    mk_link(x)
    a = mk_attachment()
    mk_link(a)
    age(db, a, 1)
    b = mk_attachment()
    mk_link(b)
    age(db, b, 2)

    result = dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501,
                                            skip=1, limit=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] ALK-GA-16
def test_alk_ga_16__an_unknown_entity_id_returns_an_empty_list(db, w1, mk_attachment, mk_link):
    """ALK-GA-16 — an unknown entity id returns an empty list.
    Rules: `get_attachments_for_entity` R4"""
    a = mk_attachment()
    mk_link(a)

    result = dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=MISSING)

    # Then 1
    assert result == []


# [claude] ALK-GA-17
def test_alk_ga_17__entity_id_0_returns_an_empty_list(db, w1, mk_attachment, mk_link):
    """ALK-GA-17 — entity id 0 returns an empty list.
    Rules: `get_attachments_for_entity` R4"""
    a = mk_attachment()
    mk_link(a)

    result = dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=0)

    # Then 1
    assert result == []


# [claude] ALK-GA-18
def test_alk_ga_18__with_the_defaults_101_ready_attachments_give_100(db, w1, mk_many_linked):
    """ALK-GA-18 — with the defaults 101 ready attachments give 100.
    Rules: `get_attachments_for_entity` R5"""
    all_ids = mk_many_linked(101)

    result = dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501)

    # Then 1
    assert len(result) == 100
    # Then 2
    assert set(ids(result)) <= all_ids


# [claude] ALK-GA-19
def test_alk_ga_19__limit_1000_gives_all_101(db, w1, mk_many_linked):
    """ALK-GA-19 — limit=1000 gives all 101.
    Rules: `get_attachments_for_entity` R5"""
    all_ids = mk_many_linked(101)

    result = dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501,
                                            limit=1000)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert set(ids(result)) == all_ids


# [claude] ALK-GA-20
def test_alk_ga_20__limit_0_returns_an_empty_list(db, w1, mk_attachment, mk_link):
    """ALK-GA-20 — limit=0 returns an empty list.
    Rules: `get_attachments_for_entity` R5"""
    a = mk_attachment()
    mk_link(a)
    b = mk_attachment(file_name="b.png")
    mk_link(b)

    result = dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501,
                                            limit=0)

    # Then 1
    assert result == []


# [claude] ALK-GA-21
def test_alk_ga_21__limit_1_returns_one_row(db, w1, mk_attachment, mk_link):
    """ALK-GA-21 — limit=1 returns one row.
    Rules: `get_attachments_for_entity` R5"""
    a = mk_attachment()
    mk_link(a)
    b = mk_attachment(file_name="b.png")
    mk_link(b)

    result = dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501,
                                            limit=1)

    # Then 1
    assert len(result) == 1


# [claude] ALK-GA-22
def test_alk_ga_22__skip_past_the_end_returns_an_empty_list(db, w1, mk_attachment, mk_link):
    """ALK-GA-22 — skip past the end returns an empty list.
    Rules: `get_attachments_for_entity` R5"""
    a = mk_attachment()
    mk_link(a)
    b = mk_attachment(file_name="b.png")
    mk_link(b)

    result = dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501,
                                            skip=2)

    # Then 1
    assert result == []


# [claude] ALK-GA-23
def test_alk_ga_23__skip_at_the_last_row_returns_it(db, w1, mk_attachment, mk_link):
    """ALK-GA-23 — skip at the last row returns it.
    Rules: `get_attachments_for_entity` R5"""
    a = mk_attachment()
    mk_link(a)
    b = mk_attachment(file_name="b.png")
    mk_link(b)
    age(db, b, 1)

    result = dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501,
                                            skip=1)

    # Then 1
    assert ids(result) == [b.id]


# [claude] ALK-GA-24
def test_alk_ga_24__a_negative_limit_raises_dataerror(db, w1, mk_attachment, mk_link):
    """ALK-GA-24 — a negative limit raises DataError.
    Rules: `get_attachments_for_entity` R5, Errors"""
    a = mk_attachment()
    mk_link(a)
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501,
                                           limit=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201W"
    # Then 3
    assert stored_count(db) == before


# [claude] ALK-GA-25
def test_alk_ga_25__a_negative_skip_raises_dataerror(db, w1, mk_attachment, mk_link):
    """ALK-GA-25 — a negative skip raises DataError.
    Rules: `get_attachments_for_entity` R5, Errors"""
    a = mk_attachment()
    mk_link(a)
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501,
                                           skip=-1)
    # Then 2
    assert exc.value.orig.pgcode == "2201X"
    # Then 3
    assert stored_count(db) == before


# [claude] ALK-GA-26
def test_alk_ga_26__newest_first_whatever_the_ids(db, w1, mk_attachment, mk_link):
    """ALK-GA-26 — newest first, whatever the ids.
    Rules: `get_attachments_for_entity` R6"""
    a = mk_attachment()
    mk_link(a)
    b = mk_attachment(file_name="b.png")
    mk_link(b)
    age(db, b, 2)
    c = mk_attachment(file_name="c.png")
    mk_link(c)
    age(db, c, 1)

    result = dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501)

    # Then 1
    assert ids(result) == [a.id, c.id, b.id]


# [claude] ALK-GA-27
def test_alk_ga_27__three_sharing_one_time_come_first_the_day_older_one_last(db, w1, mk_attachment, mk_link):
    """ALK-GA-27 — three sharing one time come first, the day-older one last.
    Rules: `get_attachments_for_entity` R6"""
    d = mk_attachment(file_name="d.png")
    mk_link(d)
    age(db, d, 1)
    a = mk_attachment()
    mk_link(a)
    b = mk_attachment(file_name="b.png")
    mk_link(b)
    c = mk_attachment(file_name="c.png")
    mk_link(c)

    result = dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert set(ids(result)[:3]) == {a.id, b.id, c.id}
    # Then 3
    assert result[3].id == d.id


# [claude] ALK-GA-28
def test_alk_ga_28__on_a_tie_the_highest_id_comes_first_when_the_lowest_id_was_updated(db, w1, mk_attachment, mk_link):
    """ALK-GA-28 — on a tie the highest id comes first, when the lowest id was updated.
    Rules: `get_attachments_for_entity` R6 [BUG-1432]"""
    a = mk_attachment()
    mk_link(a)
    b = mk_attachment(file_name="b.png")
    mk_link(b)
    c = mk_attachment(file_name="c.png")
    mk_link(c)
    d = mk_attachment(file_name="d.png")
    mk_link(d)
    age(db, d, 1)
    seqscan(db)
    bump(db, a)

    result = dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert ids(result) == [c.id, b.id, a.id, d.id]


# [claude] ALK-GA-29
def test_alk_ga_29__tied_rows_paged_one_at_a_time_neither_repeat_nor_miss_a_row(db, w1, mk_attachment, mk_link):
    """ALK-GA-29 — tied rows paged one at a time neither repeat nor miss a row.
    Rules: `get_attachments_for_entity` R6 [BUG-1432]"""
    a = mk_attachment()
    mk_link(a)
    b = mk_attachment(file_name="b.png")
    mk_link(b)
    c = mk_attachment(file_name="c.png")
    mk_link(c)
    d = mk_attachment(file_name="d.png")
    mk_link(d)
    seqscan(db)
    bump(db, a)

    pages = [dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501,
                                            skip=k, limit=1) for k in range(4)]

    # Then 1
    assert [len(p) for p in pages] == [1, 1, 1, 1]
    # Then 2
    assert [p[0].id for p in pages] == [d.id, c.id, b.id, a.id]


# [claude] ALK-GA-30
def test_alk_ga_30__the_query_orders_by_uploaded_at_then_id_both_descending(db, w1, mk_attachment, mk_link):
    """ALK-GA-30 — the query orders by uploaded_at, then id, both descending.
    Rules: `get_attachments_for_entity` R6 [BUG-1432]"""
    a = mk_attachment()
    mk_link(a)

    with StatementRecorder(db) as recorder:
        result = dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501)
    order_part = order_part_of(recorder.sql())

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "uploaded_at" in order_part
    # Then 3
    assert ".id" in order_part
    # Then 4
    assert order_part.index("uploaded_at") < order_part.index(".id")
    # Then 5
    assert order_part.upper().count("DESC") == 2


# [claude] ALK-GA-31
def test_alk_ga_31__the_record_itself_is_not_looked_at_a_link_to_an_id_with_no_record_is_followed(db, w1, mk_attachment, mk_link):
    """ALK-GA-31 — the record itself is not looked at: a link to an id with no record is followed.
    Rules: `get_attachments_for_entity` R7"""
    a = mk_attachment()
    mk_link(a, entity_type="machine", entity_id=MISSING)

    result = dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type="machine", entity_id=MISSING)

    # Then 1
    assert ids(result) == [a.id]


# [claude] ALK-GA-32
def test_alk_ga_32__writes_nothing_a_pending_row_stays_pending_an_unflushed_edit_stays_unflushed(db, w1, u1, mk_attachment, mk_link):
    """ALK-GA-32 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: `get_attachments_for_entity` Side effects"""
    a = mk_attachment()
    mk_link(a)
    b = mk_attachment(file_name="b.png")
    b.note = "Edited"
    p = Attachment(workspace_id=w1.id, file_name="p.png", mime_type="image/png", file_size=1, uploaded_by=u1.id,
                   upload_status="ready")
    db.add(p)
    before = stored_count(db)

    with StatementRecorder(db) as recorder:
        result = dao.get_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert b in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert recorder.written() == []
    # Then 7
    assert "FOR UPDATE" not in recorder.sql().upper()
    # Then 8
    assert stored_count(db) == before


# --------------------------------------------------------------------------- #
# AttachmentLinkDAO.count_linked_attachments_for_entity
# --------------------------------------------------------------------------- #


# [claude] ALK-CN-01
def test_alk_cn_01__failed_attachments_do_not_count_ready_and_pending_do(db, w1, mk_attachment, mk_deleted_attachment, mk_link):
    """ALK-CN-01 — failed attachments do not count; ready and pending do.
    Rules: `count_linked_attachments_for_entity` R1 [BUG-1434], Returns"""
    r = mk_attachment()
    mk_link(r)
    p = mk_attachment(upload_status="pending")
    mk_link(p)
    f = mk_attachment(upload_status="failed")
    mk_link(f)
    d = mk_deleted_attachment()
    mk_link(d)

    result = dao.count_linked_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501)

    # Then 1
    assert isinstance(result, int)
    # Then 2
    assert result == 2


# [claude] ALK-CN-02
def test_alk_cn_02__a_pending_one_counts_a_deleted_one_never(db, w1, mk_attachment, mk_deleted_attachment, mk_link):
    """ALK-CN-02 — a pending one counts, a deleted one never.
    Rules: `count_linked_attachments_for_entity` R1a, Returns"""
    r = mk_attachment()
    mk_link(r)
    p = mk_attachment(upload_status="pending")
    mk_link(p)
    d = mk_deleted_attachment()
    mk_link(d)

    result = dao.count_linked_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501)

    # Then 1
    assert isinstance(result, int)
    # Then 2
    assert result == 2


# [claude] ALK-CN-03
def test_alk_cn_03__no_cap_101_ready_attachments_count_101(db, w1, mk_many_linked):
    """ALK-CN-03 — no cap: 101 ready attachments count 101.
    Rules: `count_linked_attachments_for_entity` R2"""
    mk_many_linked(101)

    result = dao.count_linked_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501)

    # Then 1
    assert result == 101


# [claude] ALK-CN-04
def test_alk_cn_04__another_entity_id_does_not_count(db, w1, mk_attachment, mk_link):
    """ALK-CN-04 — another entity id does not count.
    Rules: `count_linked_attachments_for_entity` R3"""
    a = mk_attachment()
    mk_link(a)
    b = mk_attachment(file_name="b.png")
    mk_link(b, entity_id=502)

    result = dao.count_linked_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501)

    # Then 1
    assert result == 1


# [claude] ALK-CN-05
def test_alk_cn_05__another_entity_type_does_not_count(db, w1, mk_attachment, mk_link):
    """ALK-CN-05 — another entity type does not count.
    Rules: `count_linked_attachments_for_entity` R3"""
    a = mk_attachment()
    mk_link(a)
    b = mk_attachment(file_name="b.png")
    mk_link(b, entity_type="project")

    result = dao.count_linked_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501)

    # Then 1
    assert result == 1


# [claude] ALK-CN-06
def test_alk_cn_06__the_entity_type_in_capitals_counts_nothing(db, w1, mk_attachment, mk_link):
    """ALK-CN-06 — the entity type in capitals counts nothing.
    Rules: `count_linked_attachments_for_entity` R3"""
    a = mk_attachment()
    mk_link(a)

    result = dao.count_linked_attachments_for_entity(db, workspace_id=w1.id, entity_type="PURCHASE_ORDER", entity_id=501)

    # Then 1
    assert result == 0


# [claude] ALK-CN-07
def test_alk_cn_07__a_w2_link_to_a_w1_attachment_does_not_count_for_w1(db, w1, w2, mk_attachment, mk_link):
    """ALK-CN-07 — a W2 link to a W1 attachment does not count for W1.
    Rules: `count_linked_attachments_for_entity` R3"""
    a = mk_attachment()
    mk_link(a)
    b = mk_attachment(file_name="b.png")
    mk_link(b, workspace_id=w2.id)

    result = dao.count_linked_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501)

    # Then 1
    assert result == 1


# [claude] ALK-CN-08
def test_alk_cn_08__an_unknown_entity_id_counts_0(db, w1, mk_attachment, mk_link):
    """ALK-CN-08 — an unknown entity id counts 0.
    Rules: `count_linked_attachments_for_entity` R3"""
    a = mk_attachment()
    mk_link(a)

    result = dao.count_linked_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order",
                                                     entity_id=MISSING)

    # Then 1
    assert result == 0


# [claude] ALK-CN-09
def test_alk_cn_09__entity_id_0_counts_0(db, w1, mk_attachment, mk_link):
    """ALK-CN-09 — entity id 0 counts 0.
    Rules: `count_linked_attachments_for_entity` R3"""
    a = mk_attachment()
    mk_link(a)

    result = dao.count_linked_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=0)

    # Then 1
    assert result == 0


# [claude] ALK-CN-10
def test_alk_cn_10__the_record_itself_is_not_looked_at_a_link_to_an_id_with_no_record_counts(db, w1, mk_attachment, mk_link):
    """ALK-CN-10 — the record itself is not looked at: a link to an id with no record counts.
    Rules: `count_linked_attachments_for_entity` R4"""
    a = mk_attachment()
    mk_link(a, entity_type="machine", entity_id=MISSING)

    result = dao.count_linked_attachments_for_entity(db, workspace_id=w1.id, entity_type="machine", entity_id=MISSING)

    # Then 1
    assert result == 1


# [claude] ALK-CN-11
def test_alk_cn_11__writes_nothing_a_pending_row_stays_pending_an_unflushed_edit_stays_unflushed(db, w1, u1, mk_attachment, mk_link):
    """ALK-CN-11 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: `count_linked_attachments_for_entity` Side effects"""
    a = mk_attachment()
    mk_link(a)
    a.note = "Edited"
    p = Attachment(workspace_id=w1.id, file_name="p.png", mime_type="image/png", file_size=1, uploaded_by=u1.id,
                   upload_status="ready")
    db.add(p)
    before = stored_count(db)

    with StatementRecorder(db) as recorder:
        result = dao.count_linked_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order",
                                                         entity_id=501)

    # Then 1
    assert result == 1
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert a in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert recorder.written() == []
    # Then 7
    assert stored_count(db) == before


# [claude] ALK-CN-12
def test_alk_cn_12__in_the_argument_is_no_wildcard_a_stored_purchase_order_does_not_count(db, w1, mk_attachment, mk_link):
    """ALK-CN-12 — _ in the argument is no wildcard: a stored "purchase-order" does not count.
    Rules: `count_linked_attachments_for_entity` R3"""
    a = mk_attachment()
    mk_link(a)
    b = mk_attachment(file_name="b.png")
    mk_link(b, entity_type="purchase-order")

    result = dao.count_linked_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501)

    # Then 1
    assert result == 1


# [claude] ALK-CN-13
def test_alk_cn_13__the_start_of_the_entity_type_counts_nothing(db, w1, mk_attachment, mk_link):
    """ALK-CN-13 — the start of the entity type counts nothing.
    Rules: `count_linked_attachments_for_entity` R3"""
    a = mk_attachment()
    mk_link(a)

    result = dao.count_linked_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase", entity_id=501)

    # Then 1
    assert result == 0


# [claude] ALK-CN-14
def test_alk_cn_14__the_end_of_the_entity_type_counts_nothing(db, w1, mk_attachment, mk_link):
    """ALK-CN-14 — the end of the entity type counts nothing.
    Rules: `count_linked_attachments_for_entity` R3"""
    a = mk_attachment()
    mk_link(a)

    result = dao.count_linked_attachments_for_entity(db, workspace_id=w1.id, entity_type="order", entity_id=501)

    # Then 1
    assert result == 0


# [claude] ALK-CN-15
def test_alk_cn_15__a_leading_space_in_the_argument_counts_nothing(db, w1, mk_attachment, mk_link):
    """ALK-CN-15 — a leading space in the argument counts nothing.
    Rules: `count_linked_attachments_for_entity` R3"""
    a = mk_attachment()
    mk_link(a)

    result = dao.count_linked_attachments_for_entity(db, workspace_id=w1.id, entity_type=" purchase_order", entity_id=501)

    # Then 1
    assert result == 0


# [claude] ALK-CN-16
def test_alk_cn_16__a_stored_type_with_a_leading_space_does_not_count(db, w1, mk_attachment, mk_link):
    """ALK-CN-16 — a stored type with a leading space does not count.
    Rules: `count_linked_attachments_for_entity` R3"""
    a = mk_attachment()
    mk_link(a)
    b = mk_attachment(file_name="b.png")
    mk_link(b, entity_type=" purchase_order")

    result = dao.count_linked_attachments_for_entity(db, workspace_id=w1.id, entity_type="purchase_order", entity_id=501)

    # Then 1
    assert result == 1


# [claude] ALK-CN-17
def test_alk_cn_17__asked_for_w2_only_the_w2_link_counts_though_the_w1_link_is_earlier(db, w2, mk_attachment, mk_link):
    """ALK-CN-17 — asked for W2, only the W2 link counts, though the W1 link is earlier.
    Rules: `count_linked_attachments_for_entity` R3"""
    a = mk_attachment()
    mk_link(a)
    b = mk_attachment(file_name="b.png")
    mk_link(b, workspace_id=w2.id)

    result = dao.count_linked_attachments_for_entity(db, workspace_id=w2.id, entity_type="purchase_order", entity_id=501)

    # Then 1
    assert result == 1


# --------------------------------------------------------------------------- #
# AttachmentLinkDAO.get_links_for_attachment
# --------------------------------------------------------------------------- #


# [claude] ALK-GL-01
def test_alk_gl_01__returns_every_link_of_the_attachment_whatever_the_entity_type(db, w1, mk_attachment, mk_link):
    """ALK-GL-01 — returns every link of the attachment, whatever the entity type.
    Rules: `get_links_for_attachment` R1, Returns"""
    a = mk_attachment()
    l1 = mk_link(a)
    l2 = mk_link(a, entity_type="project", entity_id=7)
    l3 = mk_link(a, entity_type="machine", entity_id=9)

    result = dao.get_links_for_attachment(db, workspace_id=w1.id, attachment_id=a.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert set(ids(result)) == {l1.id, l2.id, l3.id}
    # Then 3
    assert isinstance(result[0], AttachmentLink)


# [claude] ALK-GL-02
def test_alk_gl_02__no_cap_101_links_give_101(db, w1, u1, mk_attachment):
    """ALK-GL-02 — no cap: 101 links give 101.
    Rules: `get_links_for_attachment` R1"""
    a = mk_attachment()
    db.add_all([AttachmentLink(**_link_fields(w1, u1, a, {"entity_id": k})) for k in range(1, 102)])
    db.flush()

    result = dao.get_links_for_attachment(db, workspace_id=w1.id, attachment_id=a.id)

    # Then 1
    assert len(result) == 101


# [claude] ALK-GL-03
def test_alk_gl_03__an_earlier_link_of_another_attachment_is_not_returned(db, w1, mk_attachment, mk_link):
    """ALK-GL-03 — an earlier link of another attachment is not returned.
    Rules: `get_links_for_attachment` R1"""
    b = mk_attachment(file_name="b.png")
    mk_link(b)
    a = mk_attachment()
    la = mk_link(a)

    result = dao.get_links_for_attachment(db, workspace_id=w1.id, attachment_id=a.id)

    # Then 1
    assert ids(result) == [la.id]


# [claude] ALK-GL-04
def test_alk_gl_04__a_link_of_the_attachment_under_w2_is_not_returned(db, w1, w2, mk_attachment, mk_link):
    """ALK-GL-04 — a link of the attachment under W2 is not returned.
    Rules: `get_links_for_attachment` R2"""
    a = mk_attachment()
    la = mk_link(a)
    mk_link(a, workspace_id=w2.id, entity_id=502)

    result = dao.get_links_for_attachment(db, workspace_id=w1.id, attachment_id=a.id)

    # Then 1
    assert ids(result) == [la.id]


# [claude] ALK-GL-05
def test_alk_gl_05__an_unknown_attachment_id_returns_an_empty_list(db, w1, mk_attachment, mk_link):
    """ALK-GL-05 — an unknown attachment id returns an empty list.
    Rules: `get_links_for_attachment` R3"""
    a = mk_attachment()
    mk_link(a)

    result = dao.get_links_for_attachment(db, workspace_id=w1.id, attachment_id=MISSING)

    # Then 1
    assert result == []


# [claude] ALK-GL-06
def test_alk_gl_06__attachment_id_0_returns_an_empty_list(db, w1, mk_attachment, mk_link):
    """ALK-GL-06 — attachment id 0 returns an empty list.
    Rules: `get_links_for_attachment` R3"""
    a = mk_attachment()
    mk_link(a)

    result = dao.get_links_for_attachment(db, workspace_id=w1.id, attachment_id=0)

    # Then 1
    assert result == []


# [claude] ALK-GL-07
def test_alk_gl_07__links_come_in_the_order_they_were_made_also_after_the_first_was_updated(db, w1, mk_attachment, mk_link):
    """ALK-GL-07 — links come in the order they were made, also after the first was updated.
    Rules: `get_links_for_attachment` R4 [BUG-1433]"""
    a = mk_attachment()
    l1 = mk_link(a, entity_id=1)
    l2 = mk_link(a, entity_id=2)
    l3 = mk_link(a, entity_id=3)
    seqscan(db)
    bump_l(db, l1)

    result = dao.get_links_for_attachment(db, workspace_id=w1.id, attachment_id=a.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [l1.id, l2.id, l3.id]


# [claude] ALK-GL-08
def test_alk_gl_08__the_query_orders_by_id_ascending(db, w1, mk_attachment, mk_link):
    """ALK-GL-08 — the query orders by id ascending.
    Rules: `get_links_for_attachment` R4 [BUG-1433]"""
    a = mk_attachment()
    l1 = mk_link(a)

    with StatementRecorder(db) as recorder:
        result = dao.get_links_for_attachment(db, workspace_id=w1.id, attachment_id=a.id)
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [l1.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert ".id" in order_part
    # Then 4
    assert "DESC" not in order_part.upper()


# [claude] ALK-GL-09
def test_alk_gl_09__the_links_of_a_soft_deleted_attachment_are_returned(db, w1, mk_deleted_attachment, mk_link):
    """ALK-GL-09 — the links of a soft-deleted attachment are returned.
    Rules: `get_links_for_attachment` R5"""
    d = mk_deleted_attachment()
    l1 = mk_link(d)

    result = dao.get_links_for_attachment(db, workspace_id=w1.id, attachment_id=d.id)

    # Then 1
    assert ids(result) == [l1.id]


# [claude] ALK-GL-10
def test_alk_gl_10__writes_nothing_a_pending_link_stays_pending_an_unflushed_edit_stays_unflushed(db, w1, u1, mk_attachment, mk_link):
    """ALK-GL-10 — writes nothing: a pending link stays pending, an unflushed edit stays unflushed.
    Rules: `get_links_for_attachment` Side effects"""
    a = mk_attachment()
    l1 = mk_link(a)
    b = mk_attachment(file_name="b.png")
    lb = mk_link(b)
    lb.entity_id = 777
    p = AttachmentLink(workspace_id=w1.id, attachment_id=a.id, entity_type="project", entity_id=8, linked_by=u1.id)
    db.add(p)
    before = stored_count(db)

    with StatementRecorder(db) as recorder:
        result = dao.get_links_for_attachment(db, workspace_id=w1.id, attachment_id=a.id)

    # Then 1
    assert ids(result) == [l1.id]
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert lb in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert recorder.written() == []
    # Then 7
    assert "FOR UPDATE" not in recorder.sql().upper()
    # Then 8
    assert stored_count(db) == before


# [claude] ALK-GL-11
def test_alk_gl_11__asked_for_w2_only_the_w2_link_is_returned_though_the_w1_link_is_earlier(db, w2, mk_attachment, mk_link):
    """ALK-GL-11 — asked for W2, only the W2 link is returned, though the W1 link is earlier.
    Rules: `get_links_for_attachment` R2"""
    a = mk_attachment()
    mk_link(a)
    lz = mk_link(a, workspace_id=w2.id, entity_id=502)

    result = dao.get_links_for_attachment(db, workspace_id=w2.id, attachment_id=a.id)

    # Then 1
    assert ids(result) == [lz.id]


# [claude] ALK-GL-12
def test_alk_gl_12__links_come_in_id_order_not_entity_order(db, w1, mk_attachment, mk_link):
    """ALK-GL-12 — links come in id order, not entity order.
    Rules: `get_links_for_attachment` R4 [BUG-1433]"""
    a = mk_attachment()
    l1 = mk_link(a, entity_id=9)
    l2 = mk_link(a, entity_id=5)
    l3 = mk_link(a, entity_id=7)

    result = dao.get_links_for_attachment(db, workspace_id=w1.id, attachment_id=a.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [l1.id, l2.id, l3.id]


# --------------------------------------------------------------------------- #
# Inherited BaseDAO.create on AttachmentLink
# --------------------------------------------------------------------------- #


# [claude] ALK-CR-01
def test_alk_cr_01__the_dict_of_model_dump_creates_and_flushes_the_link(db, w1, u1, mk_attachment):
    """ALK-CR-01 — the dict of model_dump creates and flushes the link.
    Rules: `create` R1, Returns; `AttachmentLinkCreateSchema` R3"""
    a = mk_attachment()

    result = dao.create(db, obj_in=Schema(workspace_id=w1.id, attachment_id=a.id, entity_type="purchase_order",
                                          entity_id=501, linked_by=u1.id).model_dump())

    # Then 1
    assert isinstance(result, AttachmentLink)
    # Then 2
    assert result.id is not None
    # Then 3
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.attachment_id == a.id
    assert row.entity_type == "purchase_order"
    assert row.entity_id == 501
    assert row.linked_by == u1.id
    # Then 4
    assert links_of(db, a) == 1


# [claude] ALK-CR-02
@pytest.mark.xfail(strict=True, reason="BUG-1431: An attachment link's time depends on the database's time zone")
def test_alk_cr_02__under_asia_dhaka_linked_at_is_the_utc_moment_of_the_insert(db, w1, u1, mk_attachment):
    """ALK-CR-02 — under Asia/Dhaka linked_at is the UTC moment of the insert.
    Rules: `create` R2 [BUG-1431]"""
    db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))
    a = mk_attachment()

    result = dao.create(db, obj_in={"workspace_id": w1.id, "attachment_id": a.id, "entity_type": "purchase_order",
                                    "entity_id": 501, "linked_by": u1.id})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.linked_at.tzinfo is None
    # Then 3
    assert abs(row.linked_at - db.scalar(text("SELECT now() AT TIME ZONE 'UTC'"))) < timedelta(minutes=5)


# [claude] ALK-CR-03
def test_alk_cr_03__under_utc_linked_at_is_the_utc_moment_of_the_insert(db, w1, u1, mk_attachment):
    """ALK-CR-03 — under UTC linked_at is the UTC moment of the insert.
    Rules: `create` R2 [BUG-1431]"""
    db.execute(text("SET LOCAL TIME ZONE 'UTC'"))
    a = mk_attachment()

    result = dao.create(db, obj_in={"workspace_id": w1.id, "attachment_id": a.id, "entity_type": "purchase_order",
                                    "entity_id": 501, "linked_by": u1.id})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert abs(row.linked_at - db.scalar(text("SELECT now() AT TIME ZONE 'UTC'"))) < timedelta(minutes=5)


# [claude] ALK-CR-04
def test_alk_cr_04__a_second_link_for_the_same_attachment_and_record_is_refused(db, w1, u1, mk_attachment, mk_link):
    """ALK-CR-04 — a second link for the same attachment and record is refused.
    Rules: `create` R3, Errors"""
    a = mk_attachment()
    mk_link(a)

    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "attachment_id": a.id, "entity_type": "purchase_order",
                                   "entity_id": 501, "linked_by": u1.id})

    # Then 1
    assert exc.value.orig.pgcode == "23505"
    # Then 2
    assert "uq_attachment_link_entity" in str(exc.value.orig)
    # Then 3
    assert links_of(db, a) == 1


# [claude] ALK-CR-05
def test_alk_cr_05__the_duplicate_is_refused_also_under_another_workspace(db, w2, u1, mk_attachment, mk_link):
    """ALK-CR-05 — the duplicate is refused also under another workspace.
    Rules: `create` R3, Errors"""
    a = mk_attachment()
    mk_link(a)

    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w2.id, "attachment_id": a.id, "entity_type": "purchase_order",
                                   "entity_id": 501, "linked_by": u1.id})

    # Then 1
    assert exc.value.orig.pgcode == "23505"
    # Then 2
    assert links_of(db, a) == 1


# [claude] ALK-CR-06
def test_alk_cr_06__the_same_attachment_may_be_linked_to_another_record(db, w1, u1, mk_attachment, mk_link):
    """ALK-CR-06 — the same attachment may be linked to another record.
    Rules: `create` R3"""
    a = mk_attachment()
    mk_link(a)

    result = dao.create(db, obj_in={"workspace_id": w1.id, "attachment_id": a.id, "entity_type": "purchase_order",
                                    "entity_id": 502, "linked_by": u1.id})

    # Then 1
    assert result.id is not None
    # Then 2
    assert links_of(db, a) == 2


# [claude] ALK-CR-07
def test_alk_cr_07__an_entity_type_of_65_characters_raises_dataerror(db, w1, u1, mk_attachment):
    """ALK-CR-07 — an entity type of 65 characters raises DataError.
    Rules: `create` R4, Errors"""
    a = mk_attachment()

    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "attachment_id": a.id, "entity_type": "x" * 65,
                                   "entity_id": 501, "linked_by": u1.id})

    # Then 1
    assert exc.value.orig.pgcode == "22001"
    # Then 2
    assert links_of(db, a) == 0


# [claude] ALK-CR-08
def test_alk_cr_08__an_entity_type_of_64_characters_is_stored(db, w1, u1, mk_attachment):
    """ALK-CR-08 — an entity type of 64 characters is stored.
    Rules: `create` R4"""
    a = mk_attachment()

    result = dao.create(db, obj_in={"workspace_id": w1.id, "attachment_id": a.id, "entity_type": "x" * 64,
                                    "entity_id": 501, "linked_by": u1.id})

    # Then 1
    assert result.id is not None
    # Then 2
    assert reread(db, result).entity_type == "x" * 64


# [claude] ALK-CR-09
def test_alk_cr_09__an_unknown_attachment_id_raises_integrityerror_23503(db, w1, u1, mk_attachment):
    """ALK-CR-09 — an unknown attachment id raises IntegrityError 23503.
    Rules: `create` R4, Errors"""
    mk_attachment()
    before = stored_count(db)

    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "attachment_id": MISSING, "entity_type": "purchase_order",
                                   "entity_id": 501, "linked_by": u1.id})

    # Then 1
    assert exc.value.orig.pgcode == "23503"
    # Then 2
    assert stored_count(db) == before


# [claude] ALK-CR-10
def test_alk_cr_10__an_unknown_linked_by_raises_integrityerror_23503(db, w1, mk_attachment):
    """ALK-CR-10 — an unknown linked_by raises IntegrityError 23503.
    Rules: `create` R4, Errors"""
    a = mk_attachment()

    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(db, obj_in={"workspace_id": w1.id, "attachment_id": a.id, "entity_type": "purchase_order",
                                   "entity_id": 501, "linked_by": MISSING})

    # Then 1
    assert exc.value.orig.pgcode == "23503"
    # Then 2
    assert links_of(db, a) == 0


# [claude] ALK-CR-11
def test_alk_cr_11__hard_deleting_the_attachment_deletes_its_links(db, mk_attachment, mk_link):
    """ALK-CR-11 — hard-deleting the attachment deletes its links.
    Rules: `create` R5"""
    a = mk_attachment()
    mk_link(a)
    b = mk_attachment(file_name="b.png")
    mk_link(b)

    db.execute(text("DELETE FROM attachments WHERE id = :i"), {"i": a.id})

    # Then 1
    assert links_of(db, a) == 0
    # Then 2
    assert links_of(db, b) == 1


# [claude] ALK-CR-12
def test_alk_cr_12__create_is_flushed_not_committed_a_rollback_removes_the_link(db, w1, u1, mk_attachment):
    """ALK-CR-12 — create is flushed, not committed: a rollback removes the link.
    Rules: `create` R1, Side effects"""
    a = mk_attachment()

    with commit_spy(db) as spy:
        sp = db.begin_nested()
        result = dao.create(db, obj_in={"workspace_id": w1.id, "attachment_id": a.id, "entity_type": "purchase_order",
                                        "entity_id": 501, "linked_by": u1.id})

        # Then 1
        assert result.id is not None
        # Then 2
        assert links_of(db, a) == 1
        sp.rollback()
        # Then 3
        assert links_of(db, a) == 0
        # Then 4
        assert spy.call_count == 0
