"""Unit tests for app/dao/workspace_invitation.py.

Implements tests/unit/dao/workspace_invitation.cases.md, one test per case, in
card order. Real Postgres session (`db` fixture). The one external,
`app.dao.workspace_invitation.utcnow`, is patched to NOW around every When
(Conventions, Externals).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: DTZ001  (Conventions prescribe naive datetimes)
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import event

from app.dao.workspace_invitation import workspace_invitation_dao
from app.models.workspace_invitation import WorkspaceInvitation
from tests.unit.factories import make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton workspace_invitation_dao"
dao = workspace_invitation_dao

# Convention "MISSING, NOW, US, DAY, T1, T2, T3"
MISSING = 999999999
NOW = datetime(2026, 3, 5, 12, 0, 0)
US = timedelta(microseconds=1)
DAY = timedelta(days=1)
T1 = datetime(2026, 3, 1, 9, 0, 0)
T2 = datetime(2026, 3, 2, 9, 0, 0)
T3 = datetime(2026, 3, 3, 9, 0, 0)

# Convention "Externals": the patch target of every When
CLOCK = "app.dao.workspace_invitation.utcnow"


# --------------------------------------------------------------------------- #
# Conventions -> the rows that exist in every test
# --------------------------------------------------------------------------- #

# Convention "W1, W2 = two workspaces rows from make_workspace(db)". w2 depends
# on w1, so the ids rise in the order the Conventions list them.
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db, w1):
    return make_workspace(db)


# Convention "Standing rows, no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2):
    return None


# Convention "TAG = uuid.uuid4().hex[:12], computed once at the start of each test"
@pytest.fixture
def tag():
    return uuid.uuid4().hex[:12]


# --------------------------------------------------------------------------- #
# Conventions -> row builders (each flushes before it returns)
# --------------------------------------------------------------------------- #

def _inv_fields(workspace, token, columns):
    fields = {"workspace_id": workspace.id, "email": "a@x.com", "role": "member", "token": token,
              "status": "pending", "expires_at": NOW + DAY}
    fields.update(columns)
    return fields


# Convention "invitation X": token f"tok-X-{TAG}"; after "but" the listed columns differ
@pytest.fixture
def mk_inv(db, w1, tag):
    """mk_inv(name, **columns) -> WorkspaceInvitation, inserted and flushed."""
    def _mk(name, **columns):
        row = WorkspaceInvitation(**_inv_fields(w1, f"tok-{name}-{tag}", columns))
        db.add(row)
        db.flush()
        return row
    return _mk


# The "101 invitations E1 ... E101, built with add_all" Given of GP-04, UI-07, GA-04
@pytest.fixture
def mk_many_inv(db, w1, tag):
    """mk_many_inv(count, **columns) -> the rows E1 ... Ecount, token f"tok-{k}-{TAG}"."""
    def _mk(count, **columns):
        rows = [WorkspaceInvitation(**_inv_fields(w1, f"tok-{k}-{tag}", columns)) for k in range(1, count + 1)]
        db.add_all(rows)
        db.flush()
        return rows
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

# Convention "idset(result)"
def idset(result):
    return {r.id for r in result}


# Convention "ids(result)": order is part of the check
def ids(result):
    return [r.id for r in result]


# Convention "re-read X": db.expire_all(), then SELECT X by id
def reread(db, row_id):
    db.expire_all()
    return db.get(WorkspaceInvitation, row_id)


# Convention "Statement recorder": every statement the session's connection
# sends while the block runs.
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
        """Convention `written`: every recorded INSERT, UPDATE or DELETE."""
        return [s for s in self.statements if s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]

    def sql(self):
        """Convention `sql`: the one SELECT from workspace_invitations; fails loudly unless there is exactly one."""
        [statement] = [s for s in self.statements
                       if s.lstrip().upper().startswith("SELECT") and "workspace_invitations" in s]
        return statement


# Convention "order_part": the text of `sql` after its first ORDER BY ("" when there is none)
def order_part_of(sql):
    return sql.split("ORDER BY", 1)[1] if "ORDER BY" in sql else ""


# --------------------------------------------------------------------------- #
# WorkspaceInvitationDAO.get_by_token
# --------------------------------------------------------------------------- #


# [claude] WSI-GT-01
def test_wsi_gt_01__the_row_with_that_token_is_returned_whatever_its_state_and_workspace(db, w2, tag, mk_inv):
    """WSI-GT-01 — the row with that token is returned, whatever its state and workspace.
    Rules: `get_by_token` R1, R2, Returns"""
    mk_inv("B")
    a = mk_inv("A", workspace_id=w2.id, status="accepted", expires_at=NOW - DAY)

    with patch(CLOCK, return_value=NOW):
        result = dao.get_by_token(db, token=f"tok-A-{tag}")

    # Then 1
    assert isinstance(result, WorkspaceInvitation)
    # Then 2
    assert result.id == a.id
    # Then 3
    assert result.status == "accepted"
    assert result.workspace_id == w2.id


# [claude] WSI-GT-02
def test_wsi_gt_02__the_token_in_capitals_gives_none(db, tag, mk_inv):
    """WSI-GT-02 — the token in capitals gives None.
    Rules: `get_by_token` R2"""
    mk_inv("A")

    with patch(CLOCK, return_value=NOW):
        result = dao.get_by_token(db, token=f"tok-A-{tag}".upper())

    # Then 1
    assert result is None


# [claude] WSI-GT-03
def test_wsi_gt_03__the_token_with_a_leading_space_gives_none(db, tag, mk_inv):
    """WSI-GT-03 — the token with a leading space gives None.
    Rules: `get_by_token` R2"""
    mk_inv("A")

    with patch(CLOCK, return_value=NOW):
        result = dao.get_by_token(db, token=f" tok-A-{tag}")

    # Then 1
    assert result is None


# [claude] WSI-GT-04
def test_wsi_gt_04__the_start_of_a_token_gives_none(db, mk_inv):
    """WSI-GT-04 — the start of a token gives None.
    Rules: `get_by_token` R2"""
    mk_inv("A")

    with patch(CLOCK, return_value=NOW):
        result = dao.get_by_token(db, token="tok-A-")

    # Then 1
    assert result is None


# [claude] WSI-GT-05
def test_wsi_gt_05__is_no_wildcard_in_a_token(db, tag, mk_inv):
    """WSI-GT-05 — _ is no wildcard in a token.
    Rules: `get_by_token` R2"""
    mk_inv("A")

    with patch(CLOCK, return_value=NOW):
        result = dao.get_by_token(db, token=f"tok_A-{tag}")

    # Then 1
    assert result is None


# [claude] WSI-GT-06
def test_wsi_gt_06__a_stored_token_with_a_leading_space_is_not_found_without_it(db, tag, mk_inv):
    """WSI-GT-06 — a stored token with a leading space is not found without it.
    Rules: `get_by_token` R2"""
    mk_inv("A", token=f" tok-A-{tag}")

    with patch(CLOCK, return_value=NOW):
        result = dao.get_by_token(db, token=f"tok-A-{tag}")

    # Then 1
    assert result is None


# [claude] WSI-GT-07
def test_wsi_gt_07__writes_nothing_a_pending_row_stays_pending_an_unflushed_edit_stays_unf(db, w1, w2, tag, mk_inv):
    """WSI-GT-07 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: `get_by_token` Side effects"""
    a = mk_inv("A")
    b = mk_inv("B", workspace_id=w2.id)
    p = WorkspaceInvitation(workspace_id=w1.id, email="p@x.com", role="member", token=f"tok-P-{tag}",
                            status="pending", expires_at=NOW + DAY)
    db.add(p)
    b.role = "admin"

    with StatementRecorder(db) as recorder, patch(CLOCK, return_value=NOW):
        result = dao.get_by_token(db, token=f"tok-A-{tag}")
    written = recorder.written()

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
    assert not db.deleted
    # Then 7
    assert written == []


# --------------------------------------------------------------------------- #
# WorkspaceInvitationDAO.get_pending_invitations
# --------------------------------------------------------------------------- #


# [claude] WSI-GP-01
def test_wsi_gp_01__only_rows_with_status_exactly_pending_not_expired_of_that_workspace(db, w1, w2, mk_inv):
    """WSI-GP-01 — only rows with status exactly 'pending', not expired, of that workspace.
    Rules: `get_pending_invitations` R1, R3, Returns"""
    a = mk_inv("A")
    mk_inv("B", status="Pending")
    mk_inv("C", status=" pending")
    mk_inv("D", status="accepted")
    mk_inv("E", status="cancelled")
    mk_inv("Z", workspace_id=w2.id)

    with patch(CLOCK, return_value=NOW):
        result = dao.get_pending_invitations(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert idset(result) == {a.id}


# [claude] WSI-GP-02
def test_wsi_gp_02__expiry_equal_to_now_or_earlier_is_left_out_one_microsecond_later_is_k(db, w1, mk_inv):
    """WSI-GP-02 — expiry: equal to now or earlier is left out, one microsecond later is kept.
    Rules: `get_pending_invitations` R2"""
    mk_inv("E", expires_at=NOW)
    f = mk_inv("F", expires_at=NOW + US)
    g = mk_inv("G", expires_at=NOW - DAY)

    with patch(CLOCK, return_value=NOW):
        result = dao.get_pending_invitations(db, workspace_id=w1.id)

    # Then 1
    assert idset(result) == {f.id}
    # Then 2
    row = reread(db, g.id)
    assert row.status == "pending"


# [claude] WSI-GP-03
def test_wsi_gp_03__workspace_id_0_gives_an_empty_list(db, mk_inv):
    """WSI-GP-03 — workspace id 0 gives an empty list.
    Rules: `get_pending_invitations` R3"""
    mk_inv("A")

    with patch(CLOCK, return_value=NOW):
        result = dao.get_pending_invitations(db, workspace_id=0)

    # Then 1
    assert result == []


# [claude] WSI-GP-04
def test_wsi_gp_04__no_cap_101_pending_invitations_give_101_rows(db, w1, mk_many_inv):
    """WSI-GP-04 — no cap: 101 pending invitations give 101 rows.
    Rules: `get_pending_invitations` R3"""
    rows = mk_many_inv(101)

    with patch(CLOCK, return_value=NOW):
        result = dao.get_pending_invitations(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert idset(result) == {r.id for r in rows}


# [claude] WSI-GP-05
def test_wsi_gp_05__writes_nothing_a_pending_row_stays_pending_an_unflushed_edit_stays_unf(db, w1, w2, tag, mk_inv):
    """WSI-GP-05 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: `get_pending_invitations` Side effects"""
    a = mk_inv("A")
    b = mk_inv("B", workspace_id=w2.id)
    p = WorkspaceInvitation(workspace_id=w1.id, email="p@x.com", role="member", token=f"tok-P-{tag}",
                            status="pending", expires_at=NOW + DAY)
    db.add(p)
    b.role = "admin"

    with StatementRecorder(db) as recorder, patch(CLOCK, return_value=NOW):
        result = dao.get_pending_invitations(db, workspace_id=w1.id)
    written = recorder.written()

    # Then 1
    assert idset(result) == {a.id}
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert len(db.new) == 1
    # Then 5
    assert b in db.dirty
    # Then 6
    assert len(db.dirty) == 1
    # Then 7
    assert not db.deleted
    # Then 8
    assert written == []


# [claude] WSI-GP-06
def test_wsi_gp_06__newest_invitation_first_and_on_a_tie_the_higher_id_first(db, w1, mk_inv):
    """WSI-GP-06 — newest invitation first, and on a tie the higher id first.
    Rules: `get_pending_invitations` R4 [BUG-1401]"""
    a = mk_inv("A", invited_at=T2)
    b = mk_inv("B", invited_at=T3)
    c = mk_inv("C", invited_at=T1)
    d = mk_inv("D", invited_at=T3)
    db.expire_all()

    with patch(CLOCK, return_value=NOW):
        result = dao.get_pending_invitations(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert ids(result) == [d.id, b.id, a.id, c.id]


# [claude] WSI-GP-07
def test_wsi_gp_07__the_query_orders_by_invited_at_then_id_both_descending(db, w1, mk_inv):
    """WSI-GP-07 — the query orders by invited_at, then id, both descending.
    Rules: `get_pending_invitations` R4 [BUG-1401]"""
    a = mk_inv("A")

    with StatementRecorder(db) as recorder, patch(CLOCK, return_value=NOW):
        result = dao.get_pending_invitations(db, workspace_id=w1.id)
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "invited_at" in order_part
    # Then 4
    assert ".id" in order_part
    # Then 5
    assert order_part.index("invited_at") < order_part.index(".id")
    # Then 6
    assert order_part.upper().count("DESC") == 2
    # Then 7
    assert order_part.count(",") == 1


# [claude] WSI-GP-08
def test_wsi_gp_08__rows_past_now_are_not_kept_by_an_expiry_check_in_python_after_the_rea(db, w1, mk_inv):
    """WSI-GP-08 — rows past now are not kept by an expiry check in Python after the read.
    Rules: `get_pending_invitations` R1"""
    a = mk_inv("A", expires_at=NOW + US)
    mk_inv("B", expires_at=NOW - US)

    with patch(CLOCK, return_value=NOW) as clock:
        result = dao.get_pending_invitations(db, workspace_id=w1.id)

    # Then 1
    assert idset(result) == {a.id}
    # Then 2
    assert clock.called is True


# [claude] WSI-GP-09
def test_wsi_gp_09__a_row_of_a_workspace_with_a_lower_id_is_not_returned(db, w2, mk_inv):
    """WSI-GP-09 — a row of a workspace with a lower id is not returned.
    Rules: `get_pending_invitations` R3"""
    mk_inv("Z")
    a = mk_inv("A", workspace_id=w2.id)

    with patch(CLOCK, return_value=NOW):
        result = dao.get_pending_invitations(db, workspace_id=w2.id)

    # Then 1
    assert idset(result) == {a.id}


# --------------------------------------------------------------------------- #
# WorkspaceInvitationDAO.get_user_invitations
# --------------------------------------------------------------------------- #


# [claude] WSI-UI-01
def test_wsi_ui_01__pending_unexpired_rows_of_that_email_from_every_workspace(db, w2, mk_inv):
    """WSI-UI-01 — pending, unexpired rows of that email from every workspace.
    Rules: `get_user_invitations` R1, R2a, Returns"""
    a = mk_inv("A")
    b = mk_inv("B", workspace_id=w2.id)
    mk_inv("C", status="accepted")
    mk_inv("D", expires_at=NOW)
    mk_inv("E", email="a@y.com")
    f = mk_inv("F", expires_at=NOW + US)

    with patch(CLOCK, return_value=NOW):
        result = dao.get_user_invitations(db, email="a@x.com")

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert idset(result) == {a.id, b.id, f.id}


# [claude] WSI-UI-02
def test_wsi_ui_02__the_email_is_matched_ignoring_case_on_the_argument_side(db, mk_inv):
    """WSI-UI-02 — the email is matched ignoring case on the argument side.
    Rules: `get_user_invitations` R2 [BUG-1402]"""
    a = mk_inv("A", email="john.doe@example.com")

    with patch(CLOCK, return_value=NOW):
        result = dao.get_user_invitations(db, email="John.Doe@example.com")

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [a.id]


# [claude] WSI-UI-03
def test_wsi_ui_03__the_email_is_matched_ignoring_surrounding_spaces_on_the_argument_side(db, mk_inv):
    """WSI-UI-03 — the email is matched ignoring surrounding spaces on the argument side.
    Rules: `get_user_invitations` R2 [BUG-1402]"""
    a = mk_inv("A", email="john.doe@example.com")

    with patch(CLOCK, return_value=NOW):
        result = dao.get_user_invitations(db, email=" john.doe@example.com ")

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [a.id]


# [claude] WSI-UI-04
def test_wsi_ui_04__a_stored_email_with_capitals_is_found_by_the_lower_case_one(db, mk_inv):
    """WSI-UI-04 — a stored email with capitals is found by the lower-case one.
    Rules: `get_user_invitations` R2 [BUG-1402]"""
    a = mk_inv("A", email="John.Doe@Example.com")

    with patch(CLOCK, return_value=NOW):
        result = dao.get_user_invitations(db, email="john.doe@example.com")

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [a.id]


# [claude] WSI-UI-05
def test_wsi_ui_05__part_of_an_email_finds_nothing(db, mk_inv):
    """WSI-UI-05 — part of an email finds nothing.
    Rules: `get_user_invitations` R2a"""
    mk_inv("A", email="john.doe@example.com")

    with patch(CLOCK, return_value=NOW):
        result = dao.get_user_invitations(db, email="doe@example.com")

    # Then 1
    assert result == []


# [claude] WSI-UI-06
def test_wsi_ui_06__is_no_wildcard_in_an_email(db, mk_inv):
    """WSI-UI-06 — _ is no wildcard in an email.
    Rules: `get_user_invitations` R2a"""
    mk_inv("A", email="john.doe@example.com")

    with patch(CLOCK, return_value=NOW):
        result = dao.get_user_invitations(db, email="john_doe@example.com")

    # Then 1
    assert result == []


# [claude] WSI-UI-07
def test_wsi_ui_07__no_cap_101_invitations_to_one_email_give_101_rows(db, mk_many_inv):
    """WSI-UI-07 — no cap: 101 invitations to one email give 101 rows.
    Rules: `get_user_invitations` R3"""
    rows = mk_many_inv(101)

    with patch(CLOCK, return_value=NOW):
        result = dao.get_user_invitations(db, email="a@x.com")

    # Then 1
    assert len(result) == 101
    # Then 2
    assert idset(result) == {r.id for r in rows}


# [claude] WSI-UI-08
def test_wsi_ui_08__newest_invitation_first_and_on_a_tie_the_higher_id_first(db, w2, mk_inv):
    """WSI-UI-08 — newest invitation first, and on a tie the higher id first.
    Rules: `get_user_invitations` R4 [BUG-1401]"""
    a = mk_inv("A", invited_at=T2)
    b = mk_inv("B", workspace_id=w2.id, invited_at=T3)
    c = mk_inv("C", invited_at=T1)
    d = mk_inv("D", invited_at=T3)
    db.expire_all()

    with patch(CLOCK, return_value=NOW):
        result = dao.get_user_invitations(db, email="a@x.com")

    # Then 1
    assert len(result) == 4
    # Then 2
    assert ids(result) == [d.id, b.id, a.id, c.id]


# [claude] WSI-UI-09
def test_wsi_ui_09__the_query_orders_by_invited_at_then_id_both_descending(db, mk_inv):
    """WSI-UI-09 — the query orders by invited_at, then id, both descending.
    Rules: `get_user_invitations` R4 [BUG-1401]"""
    a = mk_inv("A")

    with StatementRecorder(db) as recorder, patch(CLOCK, return_value=NOW):
        result = dao.get_user_invitations(db, email="a@x.com")
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "invited_at" in order_part
    # Then 4
    assert ".id" in order_part
    # Then 5
    assert order_part.index("invited_at") < order_part.index(".id")
    # Then 6
    assert order_part.upper().count("DESC") == 2
    # Then 7
    assert order_part.count(",") == 1


# [claude] WSI-UI-10
def test_wsi_ui_10__an_email_of_no_invitation_gives_an_empty_list(db, mk_inv):
    """WSI-UI-10 — an email of no invitation gives an empty list.
    Rules: `get_user_invitations` R2a"""
    mk_inv("A")

    with patch(CLOCK, return_value=NOW):
        result = dao.get_user_invitations(db, email="nobody@x.com")

    # Then 1
    assert result == []


# [claude] WSI-UI-11
def test_wsi_ui_11__writes_nothing_a_pending_row_stays_pending_an_unflushed_edit_stays_unf(db, w1, tag, mk_inv):
    """WSI-UI-11 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: `get_user_invitations` Side effects"""
    a = mk_inv("A")
    b = mk_inv("B", email="b@x.com")
    p = WorkspaceInvitation(workspace_id=w1.id, email="a@x.com", role="member", token=f"tok-P-{tag}",
                            status="pending", expires_at=NOW + DAY)
    db.add(p)
    b.role = "admin"

    with StatementRecorder(db) as recorder, patch(CLOCK, return_value=NOW):
        result = dao.get_user_invitations(db, email="a@x.com")
    written = recorder.written()

    # Then 1
    assert idset(result) == {a.id}
    # Then 2
    assert p in db.new
    # Then 3
    assert p.id is None
    # Then 4
    assert len(db.new) == 1
    # Then 5
    assert b in db.dirty
    # Then 6
    assert len(db.dirty) == 1
    # Then 7
    assert not db.deleted
    # Then 8
    assert written == []


# [claude] WSI-UI-12
def test_wsi_ui_12__only_status_exactly_pending_pending_pending_and_cancelled_are_left_out(db, mk_inv):
    """WSI-UI-12 — only status exactly 'pending': 'Pending', ' pending' and 'cancelled' are left out.
    Rules: `get_user_invitations` R1"""
    a = mk_inv("A")
    mk_inv("B", status="Pending")
    mk_inv("C", status=" pending")
    mk_inv("D", status="cancelled")

    with patch(CLOCK, return_value=NOW):
        result = dao.get_user_invitations(db, email="a@x.com")

    # Then 1
    assert idset(result) == {a.id}


# [claude] WSI-UI-13
def test_wsi_ui_13__a_stored_email_with_a_leading_space_is_found_by_the_plain_one(db, mk_inv):
    """WSI-UI-13 — a stored email with a leading space is found by the plain one.
    Rules: `get_user_invitations` R2 [BUG-1402]"""
    a = mk_inv("A", email=" john.doe@example.com")

    with patch(CLOCK, return_value=NOW):
        result = dao.get_user_invitations(db, email="john.doe@example.com")

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert ids(result) == [a.id]


# --------------------------------------------------------------------------- #
# WorkspaceInvitationDAO.count_pending_invitations
# --------------------------------------------------------------------------- #


# [claude] WSI-CP-01
def test_wsi_cp_01__counts_the_pending_unexpired_rows_of_the_workspace_one_per_row(db, w1, w2, mk_inv):
    """WSI-CP-01 — counts the pending, unexpired rows of the workspace, one per row.
    Rules: `count_pending_invitations` R1, Returns"""
    mk_inv("A")
    mk_inv("B")
    mk_inv("C", status="Pending")
    mk_inv("D", status="accepted")
    mk_inv("E", expires_at=NOW)
    mk_inv("F", email="b@x.com", expires_at=NOW + US)
    mk_inv("Z", workspace_id=w2.id)

    with patch(CLOCK, return_value=NOW):
        result = dao.count_pending_invitations(db, workspace_id=w1.id)

    # Then 1
    assert type(result) is int
    # Then 2
    assert result == 3


# [claude] WSI-CP-02
def test_wsi_cp_02__none_pending_gives_0(db, w1, mk_inv):
    """WSI-CP-02 — none pending gives 0.
    Rules: `count_pending_invitations` R2"""
    mk_inv("D", status="accepted")
    mk_inv("E", expires_at=NOW - DAY)

    with patch(CLOCK, return_value=NOW):
        result = dao.count_pending_invitations(db, workspace_id=w1.id)

    # Then 1
    assert result == 0


# [claude] WSI-CP-03
def test_wsi_cp_03__workspace_id_0_gives_0(db, mk_inv):
    """WSI-CP-03 — workspace id 0 gives 0.
    Rules: `count_pending_invitations` R2"""
    mk_inv("A")

    with patch(CLOCK, return_value=NOW):
        result = dao.count_pending_invitations(db, workspace_id=0)

    # Then 1
    assert result == 0


# [claude] WSI-CP-04
def test_wsi_cp_04__writes_nothing_a_pending_row_stays_pending_and_is_not_counted(db, w1, w2, tag, mk_inv):
    """WSI-CP-04 — writes nothing: a pending row stays pending and is not counted.
    Rules: `count_pending_invitations` Side effects"""
    mk_inv("A")
    b = mk_inv("B", workspace_id=w2.id)
    p = WorkspaceInvitation(workspace_id=w1.id, email="p@x.com", role="member", token=f"tok-P-{tag}",
                            status="pending", expires_at=NOW + DAY)
    db.add(p)
    b.role = "admin"

    with StatementRecorder(db) as recorder, patch(CLOCK, return_value=NOW):
        result = dao.count_pending_invitations(db, workspace_id=w1.id)
    written = recorder.written()

    # Then 1
    assert result == 1
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert b in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert written == []


# [claude] WSI-CP-05
def test_wsi_cp_05__a_status_with_a_leading_space_is_not_counted(db, w1, mk_inv):
    """WSI-CP-05 — a status with a leading space is not counted.
    Rules: `count_pending_invitations` R1"""
    mk_inv("A")
    mk_inv("C", status=" pending")

    with patch(CLOCK, return_value=NOW):
        result = dao.count_pending_invitations(db, workspace_id=w1.id)

    # Then 1
    assert result == 1


# [claude] WSI-CP-06
def test_wsi_cp_06__a_row_of_a_workspace_with_a_lower_id_is_not_counted(db, w2, mk_inv):
    """WSI-CP-06 — a row of a workspace with a lower id is not counted.
    Rules: `count_pending_invitations` R1"""
    mk_inv("Z")
    mk_inv("A", workspace_id=w2.id)

    with patch(CLOCK, return_value=NOW):
        result = dao.count_pending_invitations(db, workspace_id=w2.id)

    # Then 1
    assert result == 1


# --------------------------------------------------------------------------- #
# WorkspaceInvitationDAO.get_all_invitations
# --------------------------------------------------------------------------- #


# [claude] WSI-GA-01
def test_wsi_ga_01__every_row_of_the_workspace_whatever_its_state_none_of_another(db, w1, w2, mk_inv):
    """WSI-GA-01 — every row of the workspace whatever its state, none of another.
    Rules: `get_all_invitations` R1, Returns"""
    a = mk_inv("A")
    b = mk_inv("B", expires_at=NOW - DAY)
    c = mk_inv("C", status="accepted")
    d = mk_inv("D", status="cancelled")
    e = mk_inv("E", status="whatever")
    mk_inv("Z", workspace_id=w2.id)

    with patch(CLOCK, return_value=NOW):
        result = dao.get_all_invitations(db, workspace_id=w1.id)

    # Then 1
    assert isinstance(result, list)
    # Then 2
    assert idset(result) == {a.id, b.id, c.id, d.id, e.id}


# [claude] WSI-GA-02
def test_wsi_ga_02__the_clock_is_not_read(db, w1, mk_inv):
    """WSI-GA-02 — the clock is not read.
    Rules: `get_all_invitations` R2"""
    a = mk_inv("A", expires_at=NOW - DAY)

    with patch(CLOCK, return_value=NOW) as clock:
        result = dao.get_all_invitations(db, workspace_id=w1.id)

    # Then 1
    assert idset(result) == {a.id}
    # Then 2
    assert clock.called is False


# [claude] WSI-GA-03
def test_wsi_ga_03__workspace_id_0_gives_an_empty_list(db, mk_inv):
    """WSI-GA-03 — workspace id 0 gives an empty list.
    Rules: `get_all_invitations` R1"""
    mk_inv("A")

    with patch(CLOCK, return_value=NOW):
        result = dao.get_all_invitations(db, workspace_id=0)

    # Then 1
    assert result == []


# [claude] WSI-GA-04
def test_wsi_ga_04__no_cap_101_invitations_give_101_rows(db, w1, mk_many_inv):
    """WSI-GA-04 — no cap: 101 invitations give 101 rows.
    Rules: `get_all_invitations` R2"""
    rows = mk_many_inv(101, status="accepted")

    with patch(CLOCK, return_value=NOW):
        result = dao.get_all_invitations(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 101
    # Then 2
    assert idset(result) == {r.id for r in rows}


# [claude] WSI-GA-05
def test_wsi_ga_05__newest_invitation_first_and_on_a_tie_the_higher_id_first(db, w1, mk_inv):
    """WSI-GA-05 — newest invitation first, and on a tie the higher id first.
    Rules: `get_all_invitations` R3 [BUG-1401]"""
    a = mk_inv("A", invited_at=T2, status="accepted")
    b = mk_inv("B", invited_at=T3)
    c = mk_inv("C", invited_at=T1, expires_at=NOW - DAY)
    d = mk_inv("D", invited_at=T3, status="cancelled")
    db.expire_all()

    with patch(CLOCK, return_value=NOW):
        result = dao.get_all_invitations(db, workspace_id=w1.id)

    # Then 1
    assert len(result) == 4
    # Then 2
    assert ids(result) == [d.id, b.id, a.id, c.id]


# [claude] WSI-GA-06
def test_wsi_ga_06__the_query_orders_by_invited_at_then_id_both_descending(db, w1, mk_inv):
    """WSI-GA-06 — the query orders by invited_at, then id, both descending.
    Rules: `get_all_invitations` R3 [BUG-1401]"""
    a = mk_inv("A")

    with StatementRecorder(db) as recorder, patch(CLOCK, return_value=NOW):
        result = dao.get_all_invitations(db, workspace_id=w1.id)
    sql = recorder.sql()
    order_part = order_part_of(sql)

    # Then 1
    assert ids(result) == [a.id]
    # Then 2
    assert "ORDER BY" in sql
    # Then 3
    assert "invited_at" in order_part
    # Then 4
    assert ".id" in order_part
    # Then 5
    assert order_part.index("invited_at") < order_part.index(".id")
    # Then 6
    assert order_part.upper().count("DESC") == 2
    # Then 7
    assert order_part.count(",") == 1


# [claude] WSI-GA-07
def test_wsi_ga_07__writes_nothing_a_pending_row_stays_pending_an_unflushed_edit_stays_unf(db, w1, w2, tag, mk_inv):
    """WSI-GA-07 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: `get_all_invitations` Side effects"""
    a = mk_inv("A")
    b = mk_inv("B", workspace_id=w2.id)
    p = WorkspaceInvitation(workspace_id=w1.id, email="p@x.com", role="member", token=f"tok-P-{tag}",
                            status="pending", expires_at=NOW + DAY)
    db.add(p)
    b.role = "admin"

    with StatementRecorder(db) as recorder, patch(CLOCK, return_value=NOW):
        result = dao.get_all_invitations(db, workspace_id=w1.id)
    written = recorder.written()

    # Then 1
    assert idset(result) == {a.id}
    # Then 2
    assert p in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert b in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert not db.deleted
    # Then 7
    assert written == []


# [claude] WSI-GA-08
def test_wsi_ga_08__a_row_of_a_workspace_with_a_lower_id_is_not_returned(db, w2, mk_inv):
    """WSI-GA-08 — a row of a workspace with a lower id is not returned.
    Rules: `get_all_invitations` R1"""
    mk_inv("Z")
    a = mk_inv("A", workspace_id=w2.id)

    with patch(CLOCK, return_value=NOW):
        result = dao.get_all_invitations(db, workspace_id=w2.id)

    # Then 1
    assert idset(result) == {a.id}
