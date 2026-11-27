"""Unit tests for app/dao/attachment_markup.py.

Implements tests/unit/dao/attachment_markup.cases.md, one test per case, in
card order. Real Postgres session (`db` fixture). Nothing is mocked
(Conventions, Externals: None); `updated_at` comes from the database.

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
from unittest.mock import patch

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError

from app.dao.attachment_markup import attachment_markup_dao
from app.models.attachment import Attachment
from app.models.attachment_markup import AttachmentMarkup
from app.models.attachment_markup_event import AttachmentMarkupEvent
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton attachment_markup_dao"
dao = attachment_markup_dao

# Convention "MISSING": an id that no row of any table has
MISSING = 999999999


# --------------------------------------------------------------------------- #
# Conventions -> the rows that exist in every test
# (W1, W2, U1, U2, U3, AT1, AT2, ATD, AT9; each depends on the one before, so
# ids rise in the order the Conventions list them)
# --------------------------------------------------------------------------- #

def _add(db, row):
    db.add(row)
    db.flush()
    return row


@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


@pytest.fixture
def u1(db, w2):
    return make_profile(db)


@pytest.fixture
def u2(db, u1):
    return make_profile(db)


@pytest.fixture
def u3(db, u2):
    return make_profile(db)


def _attachment_fields(w1, u1, **changes):
    fields = {"workspace_id": w1.id, "file_name": "a1.png", "mime_type": "image/png", "file_size": 100,
              "uploaded_by": u1.id, "upload_status": "ready"}
    fields.update(changes)
    return fields


# Convention "AT1"
@pytest.fixture
def at1(db, w1, u1, u3):
    return _add(db, Attachment(**_attachment_fields(w1, u1)))


# Convention "AT2 = the same, but file_name 'a2.png'"
@pytest.fixture
def at2(db, w1, u1, at1):
    return _add(db, Attachment(**_attachment_fields(w1, u1, file_name="a2.png")))


# Convention "ATD = the same as AT1, but file_name 'gone.png', is_deleted True, deleted_by U1.id"
@pytest.fixture
def atd(db, w1, u1, at2):
    return _add(db, Attachment(**_attachment_fields(w1, u1, file_name="gone.png", is_deleted=True, deleted_by=u1.id)))


# Convention "AT9 = the same as AT1, but file_name 'far.png', workspace_id W2.id"
@pytest.fixture
def at9(db, w1, w2, u1, atd):
    return _add(db, Attachment(**_attachment_fields(w1, u1, file_name="far.png", workspace_id=w2.id)))


# Convention "they exist in every test and need no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, u2, u3, at1, at2, atd, at9):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builders and Given steps
# --------------------------------------------------------------------------- #

# Convention "layer"
@pytest.fixture
def mk_layer(db, w1, u1, at1):
    """mk_layer(**columns) -> AttachmentMarkup, flushed. Keywords only: the columns after "but"."""
    def _mk(**columns):
        fields = {"workspace_id": w1.id, "attachment_id": at1.id, "user_id": u1.id, "payload": {"shapes": [1]}}
        fields.update(columns)
        return _add(db, AttachmentMarkup(**fields))
    return _mk


# Convention "hour_older(X)"
def hour_older(db, x):
    db.execute(text("UPDATE attachment_markups SET updated_at = now() - interval '1 hour' WHERE id = :i"), {"i": x.id})
    db.expire_all()


# Convention "bump(X)"
def bump(db, x):
    db.execute(text("UPDATE attachment_markups SET payload = CAST(:p AS json) WHERE id = :i"),
               {"p": '{"shapes": [9]}', "i": x.id})
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
    return [r.id for r in result]


# Convention "re-read X": expire, then SELECT by id
def reread(db, row):
    db.expire_all()
    model = type(row)
    return db.execute(select(model).where(model.id == sa_inspect(row).identity[0])).scalar_one_or_none()


# Convention "NOW_DB"
def now_db(db):
    return db.scalar(text("SELECT now()"))


# Convention "unchanged(X)": every column of X, straight from the table
def snap(db, row):
    table = type(row).__table__
    found = db.execute(select(table).where(table.c.id == sa_inspect(row).identity[0])).mappings().one_or_none()
    return dict(found) if found is not None else None


# Convention "stored_json(X)"
def stored_json(db, x):
    return db.scalar(text("SELECT payload::text FROM attachment_markups WHERE id = :i"), {"i": x.id})


# Convention "layers(a, u)"
def layers(db, a, u):
    return db.scalar(text("SELECT count(*) FROM attachment_markups WHERE attachment_id = :a AND user_id = :u"),
                     {"a": a, "u": u})


# Convention "nothing written": the numbers of attachment_markups and attachment_markup_events rows (all workspaces)
def stored_count(db):
    return (db.scalar(select(func.count()).select_from(AttachmentMarkup.__table__)),
            db.scalar(select(func.count()).select_from(AttachmentMarkupEvent.__table__)))


# "count: attachment_markup_events has N rows with attachment_id == X"
def events_of(db, attachment_id):
    return db.scalar(text("SELECT count(*) FROM attachment_markup_events WHERE attachment_id = :a"),
                     {"a": attachment_id})


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
        """The one SELECT from attachment_markups; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.statements
                       if s.lstrip().upper().startswith("SELECT") and "FROM attachment_markups" in s]
        return statement


# Convention "order_part": the text of `sql` after its first ORDER BY ("" when there is none)
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1] if "ORDER BY" in sql else ""


# --------------------------------------------------------------------------- #
# AttachmentMarkupDAO.get_for_attachment
# --------------------------------------------------------------------------- #


# [claude] AMK-GF-01
def test_amk_gf_01__returns_a_list_of_every_user_s_layer_on_the_attachment(db, w1, u2, at1, mk_layer):
    """AMK-GF-01 — returns a list of every user's layer on the attachment.
    Rules: `get_for_attachment` R1, Returns"""
    a = mk_layer()
    b = mk_layer(user_id=u2.id)

    result = dao.get_for_attachment(db, workspace_id=w1.id, attachment_id=at1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert set(ids(result)) == {a.id, b.id}
    # Then 3
    assert isinstance(result[0], AttachmentMarkup)


# [claude] AMK-GF-02
def test_amk_gf_02__a_layer_on_another_attachment_is_not_returned(db, w1, u2, at1, at2, mk_layer):
    """AMK-GF-02 — a layer on another attachment is not returned.
    Rules: `get_for_attachment` R1"""
    mk_layer(attachment_id=at2.id, user_id=u2.id)
    a = mk_layer()

    result = dao.get_for_attachment(db, workspace_id=w1.id, attachment_id=at1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] AMK-GF-03
def test_amk_gf_03__a_w2_layer_on_a_w1_attachment_is_not_returned_for_w1(db, w1, w2, u2, at1, mk_layer):
    """AMK-GF-03 — a W2 layer on a W1 attachment is not returned for W1.
    Rules: `get_for_attachment` R2"""
    a = mk_layer()
    mk_layer(workspace_id=w2.id, user_id=u2.id)

    result = dao.get_for_attachment(db, workspace_id=w1.id, attachment_id=at1.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] AMK-GF-04
def test_amk_gf_04__a_w2_layer_on_a_w1_attachment_is_returned_for_w2(db, w2, u2, at1, mk_layer):
    """AMK-GF-04 — a W2 layer on a W1 attachment is returned for W2.
    Rules: `get_for_attachment` R2"""
    mk_layer()
    b = mk_layer(workspace_id=w2.id, user_id=u2.id)

    result = dao.get_for_attachment(db, workspace_id=w2.id, attachment_id=at1.id)

    # Then 1
    assert ids(result) == [b.id]


# [claude] AMK-GF-05
def test_amk_gf_05__an_unknown_attachment_id_returns_an_empty_list(db, w1, mk_layer):
    """AMK-GF-05 — an unknown attachment id returns an empty list.
    Rules: `get_for_attachment` R3"""
    mk_layer()

    result = dao.get_for_attachment(db, workspace_id=w1.id, attachment_id=MISSING)

    # Then 1
    assert result == []


# [claude] AMK-GF-06
def test_amk_gf_06__attachment_id_0_returns_an_empty_list(db, w1, mk_layer):
    """AMK-GF-06 — attachment id 0 returns an empty list.
    Rules: `get_for_attachment` R3"""
    mk_layer()

    result = dao.get_for_attachment(db, workspace_id=w1.id, attachment_id=0)

    # Then 1
    assert result == []


# [claude] AMK-GF-07
def test_amk_gf_07__an_attachment_without_layers_returns_an_empty_list(db, w1, at2, mk_layer):
    """AMK-GF-07 — an attachment without layers returns an empty list.
    Rules: `get_for_attachment` R3"""
    mk_layer()

    result = dao.get_for_attachment(db, workspace_id=w1.id, attachment_id=at2.id)

    # Then 1
    assert result == []


# [claude] AMK-GF-08
def test_amk_gf_08__the_hour_older_layer_comes_first_though_its_id_is_higher(db, w1, u2, at1, mk_layer):
    """AMK-GF-08 — the hour-older layer comes first, though its id is higher.
    Rules: `get_for_attachment` R4"""
    a = mk_layer()
    b = mk_layer(user_id=u2.id)
    hour_older(db, b)

    result = dao.get_for_attachment(db, workspace_id=w1.id, attachment_id=at1.id)

    # Then 1
    assert ids(result) == [b.id, a.id]


# [claude] AMK-GF-09
def test_amk_gf_09__on_a_tie_both_layers_follow_the_older_one(db, w1, u2, u3, at1, mk_layer):
    """AMK-GF-09 — on a tie both layers follow the older one.
    Rules: `get_for_attachment` R4"""
    a = mk_layer()
    b = mk_layer(user_id=u2.id)
    d = mk_layer(user_id=u3.id)
    hour_older(db, d)

    result = dao.get_for_attachment(db, workspace_id=w1.id, attachment_id=at1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert result[0].id == d.id
    # Then 3
    assert set(ids(result)[1:]) == {a.id, b.id}


# [claude] AMK-GF-10
@pytest.mark.xfail(strict=False, reason="BUG-1435: Markup layers saved at one moment come back in no fixed order")
def test_amk_gf_10__on_a_tie_the_lowest_id_comes_first_when_it_was_updated_in_place(db, w1, u2, u3, at1, mk_layer):
    """AMK-GF-10 — on a tie the lowest id comes first, when it was updated in place.
    Rules: `get_for_attachment` R4 [BUG-1435]"""
    a = mk_layer()
    b = mk_layer(user_id=u2.id)
    c = mk_layer(user_id=u3.id)
    seqscan(db)
    bump(db, a)

    result = dao.get_for_attachment(db, workspace_id=w1.id, attachment_id=at1.id)

    # Then 1
    assert len(result) == 3
    # Then 2
    assert ids(result) == [a.id, b.id, c.id]


# [claude] AMK-GF-11
@pytest.mark.xfail(strict=True, reason="BUG-1435: Markup layers saved at one moment come back in no fixed order")
def test_amk_gf_11__the_query_orders_by_updated_at_then_id_ascending(db, w1, at1, mk_layer):
    """AMK-GF-11 — the query orders by updated_at, then id, ascending.
    Rules: `get_for_attachment` R4 [BUG-1435]"""
    a = mk_layer()

    with StatementRecorder(db) as recorder:
        result = dao.get_for_attachment(db, workspace_id=w1.id, attachment_id=at1.id)
    order_part = order_part_of(recorder.sql())

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "updated_at" in order_part
    # Then 3
    assert ".id" in order_part
    # Then 4
    assert order_part.index("updated_at") < order_part.index(".id")
    # Then 5
    assert "DESC" not in order_part.upper()


# [claude] AMK-GF-12
def test_amk_gf_12__the_layers_of_a_soft_deleted_attachment_are_returned(db, w1, atd, mk_layer):
    """AMK-GF-12 — the layers of a soft-deleted attachment are returned.
    Rules: `get_for_attachment` R5"""
    a = mk_layer(attachment_id=atd.id)

    result = dao.get_for_attachment(db, workspace_id=w1.id, attachment_id=atd.id)

    # Then 1
    assert ids(result) == [a.id]


# [claude] AMK-GF-13
def test_amk_gf_13__writes_nothing_a_pending_row_stays_pending_an_unflushed_edit_stays_unf(db, w1, u2, at1, at2,
                                                                                          mk_layer):
    """AMK-GF-13 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: `get_for_attachment` Side effects"""
    a = mk_layer()
    b = mk_layer(attachment_id=at2.id)
    b.payload = {"shapes": [5]}
    p = AttachmentMarkup(workspace_id=w1.id, attachment_id=at1.id, user_id=u2.id, payload={"shapes": [3]})
    db.add(p)
    before = stored_count(db)

    with StatementRecorder(db) as recorder:
        result = dao.get_for_attachment(db, workspace_id=w1.id, attachment_id=at1.id)

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
# AttachmentMarkupDAO.get_for_user
# --------------------------------------------------------------------------- #


# [claude] AMK-GU-01
def test_amk_gu_01__returns_the_user_s_layer_the_instance_the_session_holds(db, w1, u1, u2, at1, mk_layer):
    """AMK-GU-01 — returns the user's layer, the instance the session holds.
    Rules: `get_for_user` R1, Returns"""
    mk_layer(user_id=u2.id)
    a = mk_layer()

    result = dao.get_for_user(db, workspace_id=w1.id, attachment_id=at1.id, user_id=u1.id)

    # Then 1
    assert result is a


# [claude] AMK-GU-02
def test_amk_gu_02__another_user_returns_none(db, w1, u2, at1, mk_layer):
    """AMK-GU-02 — another user returns None.
    Rules: `get_for_user` R2"""
    mk_layer()

    result = dao.get_for_user(db, workspace_id=w1.id, attachment_id=at1.id, user_id=u2.id)

    # Then 1
    assert result is None


# [claude] AMK-GU-03
def test_amk_gu_03__another_attachment_returns_none(db, w1, u1, at2, mk_layer):
    """AMK-GU-03 — another attachment returns None.
    Rules: `get_for_user` R2"""
    mk_layer()

    result = dao.get_for_user(db, workspace_id=w1.id, attachment_id=at2.id, user_id=u1.id)

    # Then 1
    assert result is None


# [claude] AMK-GU-04
def test_amk_gu_04__another_workspace_s_earlier_layer_returns_none(db, w1, w2, u1, at9, mk_layer):
    """AMK-GU-04 — another workspace's earlier layer returns None.
    Rules: `get_for_user` R2"""
    mk_layer(workspace_id=w2.id, attachment_id=at9.id)
    mk_layer()

    result = dao.get_for_user(db, workspace_id=w1.id, attachment_id=at9.id, user_id=u1.id)

    # Then 1
    assert result is None


# [claude] AMK-GU-05
def test_amk_gu_05__the_layer_asked_for_under_another_workspace_returns_none(db, w2, u1, at1, mk_layer):
    """AMK-GU-05 — the layer asked for under another workspace returns None.
    Rules: `get_for_user` R2"""
    mk_layer()

    result = dao.get_for_user(db, workspace_id=w2.id, attachment_id=at1.id, user_id=u1.id)

    # Then 1
    assert result is None


# [claude] AMK-GU-06
def test_amk_gu_06__ids_of_0_return_none_with_no_error(db, w1, mk_layer):
    """AMK-GU-06 — ids of 0 return None, with no error.
    Rules: `get_for_user` R3"""
    mk_layer()

    result = dao.get_for_user(db, workspace_id=w1.id, attachment_id=0, user_id=0)

    # Then 1
    assert result is None


# [claude] AMK-GU-07
def test_amk_gu_07__the_layer_on_a_soft_deleted_attachment_is_returned(db, w1, u1, atd, mk_layer):
    """AMK-GU-07 — the layer on a soft-deleted attachment is returned.
    Rules: `get_for_user` R4"""
    a = mk_layer(attachment_id=atd.id)

    result = dao.get_for_user(db, workspace_id=w1.id, attachment_id=atd.id, user_id=u1.id)

    # Then 1
    assert result.id == a.id


# [claude] AMK-GU-08
def test_amk_gu_08__writes_nothing_a_pending_row_stays_pending_an_unflushed_edit_stays_unf(db, w1, u1, u2, at1, at2,
                                                                                          mk_layer):
    """AMK-GU-08 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: `get_for_user` Side effects"""
    a = mk_layer()
    b = mk_layer(user_id=u2.id)
    b.payload = {"shapes": [5]}
    p = AttachmentMarkup(workspace_id=w1.id, attachment_id=at2.id, user_id=u1.id, payload={"shapes": [3]})
    db.add(p)
    before = stored_count(db)

    with StatementRecorder(db) as recorder:
        result = dao.get_for_user(db, workspace_id=w1.id, attachment_id=at1.id, user_id=u1.id)

    # Then 1
    assert result.id == a.id
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
# AttachmentMarkupDAO.upsert_for_user
# --------------------------------------------------------------------------- #


# [claude] AMK-UP-01
def test_amk_up_01__the_first_save_creates_the_layer_with_the_four_values_stamped_now(db, w1, u1, at1):
    """AMK-UP-01 — the first save creates the layer with the four values, stamped now.
    Rules: `upsert_for_user` R1, Returns, Side effects"""
    result = dao.upsert_for_user(db, workspace_id=w1.id, attachment_id=at1.id, user_id=u1.id,
                                 payload={"shapes": [1]})

    # Then 1
    assert isinstance(result, AttachmentMarkup)
    # Then 2
    assert result.id is not None
    # Then 3
    row = reread(db, result)
    assert row.workspace_id == w1.id
    assert row.attachment_id == at1.id
    assert row.user_id == u1.id
    assert row.payload == {"shapes": [1]}
    # Then 4
    row = reread(db, result)
    assert row.updated_at == now_db(db)
    # Then 5
    assert layers(db, at1.id, u1.id) == 1
    # Then 6
    assert events_of(db, at1.id) == 0


# [claude] AMK-UP-02
def test_amk_up_02__a_later_save_replaces_the_payload_of_the_same_row(db, w1, u1, at1, mk_layer):
    """AMK-UP-02 — a later save replaces the payload of the same row.
    Rules: `upsert_for_user` R2"""
    a = mk_layer()

    result = dao.upsert_for_user(db, workspace_id=w1.id, attachment_id=at1.id, user_id=u1.id,
                                 payload={"shapes": [2]})

    # Then 1
    assert result is a
    # Then 2
    row = reread(db, a)
    assert row.payload == {"shapes": [2]}
    # Then 3
    assert layers(db, at1.id, u1.id) == 1


# [claude] AMK-UP-03
def test_amk_up_03__is_stored_as_on_insert(db, w1, u1, at1):
    """AMK-UP-03 — {} is stored as {} on insert.
    Rules: `upsert_for_user` R3"""
    result = dao.upsert_for_user(db, workspace_id=w1.id, attachment_id=at1.id, user_id=u1.id, payload={})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.payload == {}
    # Then 3
    assert stored_json(db, result) == "{}"


# [claude] AMK-UP-04
def test_amk_up_04__none_is_stored_as_json_null_on_insert(db, w1, u1, at1):
    """AMK-UP-04 — None is stored as JSON null on insert.
    Rules: `upsert_for_user` R3"""
    result = dao.upsert_for_user(db, workspace_id=w1.id, attachment_id=at1.id, user_id=u1.id, payload=None)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.payload is None
    # Then 3
    assert stored_json(db, result) == "null"


# [claude] AMK-UP-05
def test_amk_up_05__none_is_stored_as_json_null_on_update(db, w1, u1, at1, mk_layer):
    """AMK-UP-05 — None is stored as JSON null on update.
    Rules: `upsert_for_user` R3"""
    a = mk_layer()

    result = dao.upsert_for_user(db, workspace_id=w1.id, attachment_id=at1.id, user_id=u1.id, payload=None)

    # Then 1
    assert result.id == a.id
    # Then 2
    db.expire_all()
    assert stored_json(db, a) == "null"


# [claude] AMK-UP-06
def test_amk_up_06__an_equal_payload_sends_no_update_and_the_stamp_stays(db, w1, u1, at1, mk_layer):
    """AMK-UP-06 — an equal payload sends no UPDATE and the stamp stays.
    Rules: `upsert_for_user` R4"""
    a = mk_layer()
    hour_older(db, a)
    before = snap(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.upsert_for_user(db, workspace_id=w1.id, attachment_id=at1.id, user_id=u1.id,
                                     payload={"shapes": [1]})

    # Then 1
    assert result.id == a.id
    # Then 2
    assert recorder.written() == []
    # Then 3
    db.expire_all()
    assert snap(db, a) == before


# [claude] AMK-UP-07
def test_amk_up_07__a_different_payload_sends_one_update_and_the_stamp_becomes_now(db, w1, u1, at1, mk_layer):
    """AMK-UP-07 — a different payload sends one UPDATE and the stamp becomes now.
    Rules: `upsert_for_user` R4"""
    a = mk_layer()
    hour_older(db, a)

    with StatementRecorder(db) as recorder:
        result = dao.upsert_for_user(db, workspace_id=w1.id, attachment_id=at1.id, user_id=u1.id,
                                     payload={"shapes": [2]})

    # Then 1
    assert result.id == a.id
    # Then 2
    assert len(recorder.written()) == 1
    # Then 3
    assert recorder.written()[0].lstrip().upper().startswith("UPDATE")
    # Then 4
    row = reread(db, a)
    assert row.updated_at == now_db(db)


# [claude] AMK-UP-08
def test_amk_up_08__an_unknown_attachment_fails_at_the_flush_with_23503(db, w1, u1):
    """AMK-UP-08 — an unknown attachment fails at the flush with 23503.
    Rules: `upsert_for_user` R5, Errors row 1"""
    before = stored_count(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.upsert_for_user(db, workspace_id=w1.id, attachment_id=MISSING, user_id=u1.id,
                                payload={"shapes": [1]})
    assert exc.value.orig.pgcode == "23503"
    # Then 2
    assert stored_count(db) == before


# [claude] AMK-UP-09
def test_amk_up_09__an_unknown_user_fails_at_the_flush_with_23503(db, w1, at1):
    """AMK-UP-09 — an unknown user fails at the flush with 23503.
    Rules: `upsert_for_user` R5, Errors row 1"""
    before = stored_count(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.upsert_for_user(db, workspace_id=w1.id, attachment_id=at1.id, user_id=MISSING,
                                payload={"shapes": [1]})
    assert exc.value.orig.pgcode == "23503"
    # Then 2
    assert stored_count(db) == before


# [claude] AMK-UP-10
def test_amk_up_10__the_same_attachment_and_user_under_another_workspace_is_refused_with(db, w1, w2, u1, at1,
                                                                                        mk_layer):
    """AMK-UP-10 — the same attachment and user under another workspace is refused with 23505.
    Rules: `upsert_for_user` R6, Errors row 2"""
    z = mk_layer(workspace_id=w2.id)
    before = snap(db, z)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.upsert_for_user(db, workspace_id=w1.id, attachment_id=at1.id, user_id=u1.id,
                                payload={"shapes": [2]})
    assert exc.value.orig.pgcode == "23505"
    # Then 2
    assert "uq_attachment_markup_user" in str(exc.value.orig)
    # Then 3
    db.expire_all()
    assert snap(db, z) == before
    # Then 4
    assert layers(db, at1.id, u1.id) == 1


# [claude] AMK-UP-11
def test_amk_up_11__a_w2_layer_is_created_on_a_w1_attachment(db, w2, u2, at1):
    """AMK-UP-11 — a W2 layer is created on a W1 attachment.
    Rules: `upsert_for_user` R7"""
    result = dao.upsert_for_user(db, workspace_id=w2.id, attachment_id=at1.id, user_id=u2.id,
                                 payload={"shapes": [1]})

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result)
    assert row.workspace_id == w2.id
    assert row.attachment_id == at1.id
    assert row.user_id == u2.id


# [claude] AMK-UP-12
def test_amk_up_12__an_insert_is_flushed_not_committed_a_rollback_removes_it(db, w1, u1, at1):
    """AMK-UP-12 — an insert is flushed, not committed: a rollback removes it.
    Rules: `upsert_for_user` R8, Side effects"""
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        result = dao.upsert_for_user(db, workspace_id=w1.id, attachment_id=at1.id, user_id=u1.id,
                                     payload={"shapes": [1]})

    # Then 1
    assert result.id is not None
    # Then 2
    assert layers(db, at1.id, u1.id) == 1
    # Then 3
    sp.rollback()
    assert layers(db, at1.id, u1.id) == 0
    # Then 4
    assert commit_spy.call_count == 0


# [claude] AMK-UP-13
def test_amk_up_13__an_update_is_flushed_not_committed_a_rollback_restores_the_old_payloa(db, w1, u1, at1, mk_layer):
    """AMK-UP-13 — an update is flushed, not committed: a rollback restores the old payload.
    Rules: `upsert_for_user` R8, Side effects"""
    a = mk_layer()

    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        result = dao.upsert_for_user(db, workspace_id=w1.id, attachment_id=at1.id, user_id=u1.id,
                                     payload={"shapes": [2]})

    # Then 1
    assert result.id == a.id
    # Then 2
    row = reread(db, a)
    assert row.payload == {"shapes": [2]}
    # Then 3
    sp.rollback()
    row = reread(db, a)
    assert row.payload == {"shapes": [1]}
    # Then 4
    assert commit_spy.call_count == 0


# [claude] AMK-UP-14
def test_amk_up_14__the_user_s_layer_on_another_attachment_and_another_user_s_layer_here(db, w1, u1, u2, at1, at2,
                                                                                        mk_layer):
    """AMK-UP-14 — the user's layer on another attachment and another user's layer here are not taken.
    Rules: `upsert_for_user` R1"""
    b = mk_layer(attachment_id=at2.id)
    c = mk_layer(user_id=u2.id)
    before_b = snap(db, b)
    before_c = snap(db, c)

    result = dao.upsert_for_user(db, workspace_id=w1.id, attachment_id=at1.id, user_id=u1.id,
                                 payload={"shapes": [7]})

    # Then 1
    assert result.id not in {b.id, c.id}
    # Then 2
    assert layers(db, at1.id, u1.id) == 1
    # Then 3
    db.expire_all()
    assert snap(db, b) == before_b
    # Then 4
    assert snap(db, c) == before_c


# --------------------------------------------------------------------------- #
# AttachmentMarkupDAO.delete_for_user
# --------------------------------------------------------------------------- #


# [claude] AMK-DL-01
def test_amk_dl_01__the_user_s_layer_is_deleted_and_true_returned_the_others_stay(db, w1, u1, u2, at1, mk_layer):
    """AMK-DL-01 — the user's layer is deleted and True returned; the others stay.
    Rules: `delete_for_user` R1, Returns, Side effects"""
    mk_layer()
    b = mk_layer(user_id=u2.id)
    before_b = snap(db, b)

    result = dao.delete_for_user(db, workspace_id=w1.id, attachment_id=at1.id, user_id=u1.id)

    # Then 1
    assert result is True
    # Then 2
    assert layers(db, at1.id, u1.id) == 0
    # Then 3
    db.expire_all()
    assert snap(db, b) == before_b
    # Then 4
    assert events_of(db, at1.id) == 0


# [claude] AMK-DL-02
def test_amk_dl_02__another_user_s_call_returns_false_and_deletes_nothing(db, w1, u2, at1, mk_layer):
    """AMK-DL-02 — another user's call returns False and deletes nothing.
    Rules: `delete_for_user` R2"""
    a = mk_layer()
    before = snap(db, a)

    result = dao.delete_for_user(db, workspace_id=w1.id, attachment_id=at1.id, user_id=u2.id)

    # Then 1
    assert result is False
    # Then 2
    db.expire_all()
    assert snap(db, a) == before


# [claude] AMK-DL-03
def test_amk_dl_03__a_call_under_another_workspace_returns_false_and_deletes_nothing(db, w2, u1, at1, mk_layer):
    """AMK-DL-03 — a call under another workspace returns False and deletes nothing.
    Rules: `delete_for_user` R2"""
    a = mk_layer()
    before = snap(db, a)

    result = dao.delete_for_user(db, workspace_id=w2.id, attachment_id=at1.id, user_id=u1.id)

    # Then 1
    assert result is False
    # Then 2
    db.expire_all()
    assert snap(db, a) == before


# [claude] AMK-DL-04
def test_amk_dl_04__unknown_ids_return_false(db, w1, mk_layer):
    """AMK-DL-04 — unknown ids return False.
    Rules: `delete_for_user` R2"""
    mk_layer()
    before = stored_count(db)

    result = dao.delete_for_user(db, workspace_id=w1.id, attachment_id=MISSING, user_id=MISSING)

    # Then 1
    assert result is False
    # Then 2
    assert stored_count(db) == before


# [claude] AMK-DL-05
def test_amk_dl_05__a_second_call_after_a_delete_returns_false(db, w1, u1, at1, mk_layer):
    """AMK-DL-05 — a second call after a delete returns False.
    Rules: `delete_for_user` R2"""
    mk_layer()
    dao.delete_for_user(db, workspace_id=w1.id, attachment_id=at1.id, user_id=u1.id)

    result = dao.delete_for_user(db, workspace_id=w1.id, attachment_id=at1.id, user_id=u1.id)

    # Then 1
    assert result is False
    # Then 2
    assert layers(db, at1.id, u1.id) == 0


# [claude] AMK-DL-06
def test_amk_dl_06__flushed_not_committed_a_rollback_brings_the_row_back(db, w1, u1, at1, mk_layer):
    """AMK-DL-06 — flushed, not committed: a rollback brings the row back.
    Rules: `delete_for_user` R3, Side effects"""
    mk_layer()

    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as commit_spy:
        result = dao.delete_for_user(db, workspace_id=w1.id, attachment_id=at1.id, user_id=u1.id)

    # Then 1
    assert result is True
    # Then 2
    assert layers(db, at1.id, u1.id) == 0
    # Then 3
    sp.rollback()
    assert layers(db, at1.id, u1.id) == 1
    # Then 4
    assert commit_spy.call_count == 0
