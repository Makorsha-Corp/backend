"""Unit tests for app/dao/refresh_token.py.

Implements tests/unit/dao/refresh_token.cases.md, one test per case, in card
order. Real Postgres session (`db` fixture). The one external,
`app.dao.refresh_token.utcnow`, is patched to NOW around every When
(Conventions, Externals).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""
# ruff: noqa: SIM117, DTZ001  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`, and naive datetimes)
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import DataError, IntegrityError

from app.dao.refresh_token import refresh_token_dao
from app.models.refresh_token import RefreshToken
from tests.unit.factories import make_profile, make_workspace

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton refresh_token_dao"
dao = refresh_token_dao

# Convention "MISSING, NOW, EARLY, PAST, LATER, SLACK"
MISSING = 999999999
NOW = datetime(2026, 3, 5, 12, 0, 0)
EARLY = datetime(2026, 3, 1, 8, 0, 0)
PAST = datetime(2026, 3, 4, 12, 0, 0)
LATER = datetime(2026, 4, 5, 12, 0, 0)
SLACK = timedelta(seconds=5)

# Convention "Externals": the patch target every When runs under
UTCNOW = "app.dao.refresh_token.utcnow"


def clock():
    """Convention "clock window": the real UTC clock, naive."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --------------------------------------------------------------------------- #
# Conventions -> per-test values: TAG, H1 ... H9, FAM1, FAM2
# --------------------------------------------------------------------------- #

def _hashes():
    tag = uuid.uuid4().hex
    return [f"a{k}" + (tag + tag)[:62] for k in range(1, 10)]


@pytest.fixture
def hashes():
    return _hashes()


@pytest.fixture
def H1(hashes):
    return hashes[0]


@pytest.fixture
def H2(hashes):
    return hashes[1]


@pytest.fixture
def H3(hashes):
    return hashes[2]


@pytest.fixture
def H4(hashes):
    return hashes[3]


@pytest.fixture
def H5(hashes):
    return hashes[4]


@pytest.fixture
def FAM1():
    return str(uuid.uuid4())


@pytest.fixture
def FAM2():
    return str(uuid.uuid4())


# --------------------------------------------------------------------------- #
# Conventions -> the rows that exist in every test (W1, W2, U1, U2, in that order)
# --------------------------------------------------------------------------- #

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


# Convention "Standing rows, no Given line"
@pytest.fixture(autouse=True)
def standing_rows(w1, w2, u1, u2):
    return None


# --------------------------------------------------------------------------- #
# Conventions -> row builder (flushes before it returns)
# --------------------------------------------------------------------------- #

# Convention "token": RefreshToken(user_id=U1.id, token_hash=..., family_id=FAM1, expires_at=LATER)
@pytest.fixture
def mk_token(db, u1, FAM1):
    """mk_token(token_hash=..., **columns) -> RefreshToken. Keywords only."""
    def _mk(*, token_hash, **columns):
        fields = {"user_id": u1.id, "token_hash": token_hash, "family_id": FAM1, "expires_at": LATER}
        fields.update(columns)
        row = RefreshToken(**fields)
        db.add(row)
        db.flush()
        return row
    return _mk


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #

# Convention "re-read X": expire_all, then SELECT X by id
def reread(db, row_id):
    db.expire_all()
    return db.execute(select(RefreshToken).where(RefreshToken.id == row_id)).scalar_one_or_none()


# Convention "raw(X, col)": the database value, without touching the session
def raw(db, row, col):
    return db.execute(text(f"SELECT {col} FROM refresh_tokens WHERE id = :id"), {"id": row.id}).scalar()


# Convention "unchanged(X)": every column of X, straight from the table
def snap(db, row_id):
    table = RefreshToken.__table__
    found = db.execute(select(table).where(table.c.id == row_id)).mappings().one_or_none()
    return dict(found) if found is not None else None


def snap_except(db, row_id, column):
    """Convention "unchanged(X) except c"."""
    found = snap(db, row_id)
    found.pop(column)
    return found


# Convention "nothing written": the number of refresh_tokens rows stored
def stored_count(db):
    return db.scalar(select(func.count()).select_from(RefreshToken.__table__))


def count_where(db, column, value):
    """The number of refresh_tokens rows with `column == value`, by raw SQL."""
    return db.execute(text(f"SELECT count(*) FROM refresh_tokens WHERE {column} = :v"), {"v": value}).scalar()


# Convention "Statement recorder"
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


# Convention "rolled back": a spy that wraps db.commit (still callable, records calls)
def commit_spy(db):
    return patch.object(db, "commit", wraps=db.commit)


# --------------------------------------------------------------------------- #
# RefreshTokenDAO.get_by_hash
# --------------------------------------------------------------------------- #


# [claude] RT-GH-01
def test_rt_gh_01__the_row_with_that_hash_is_returned_whatever_its_state_and_user(db, w2, u2, mk_token, H1, H2):
    """RT-GH-01 — the row with that hash is returned, whatever its state and user.
    Rules: `get_by_hash` R1, R2, Returns"""
    b = mk_token(token_hash=H2)
    a = mk_token(token_hash=H1, user_id=u2.id, workspace_id=w2.id, expires_at=PAST, revoked_at=EARLY, replaced_by_id=b.id)

    with patch(UTCNOW, return_value=NOW):
        result = dao.get_by_hash(db, token_hash=H1)

    # Then 1
    assert isinstance(result, RefreshToken)
    # Then 2
    assert result.id == a.id
    # Then 3
    assert result.user_id == u2.id
    assert result.revoked_at == EARLY
    assert result.replaced_by_id == b.id


# [claude] RT-GH-02
def test_rt_gh_02__the_hash_in_capitals_gives_none(db, mk_token, H1):
    """RT-GH-02 — the hash in capitals gives None.
    Rules: `get_by_hash` R2"""
    mk_token(token_hash=H1)

    with patch(UTCNOW, return_value=NOW):
        result = dao.get_by_hash(db, token_hash=H1.upper())

    # Then 1
    assert result is None


# [claude] RT-GH-03
def test_rt_gh_03__an_empty_hash_gives_none(db, mk_token, H1):
    """RT-GH-03 — an empty hash gives None.
    Rules: `get_by_hash` R2"""
    mk_token(token_hash=H1)

    with patch(UTCNOW, return_value=NOW):
        result = dao.get_by_hash(db, token_hash="")

    # Then 1
    assert result is None


# [claude] RT-GH-04
def test_rt_gh_04__the_first_63_characters_of_a_hash_give_none(db, mk_token, H1):
    """RT-GH-04 — the first 63 characters of a hash give None.
    Rules: `get_by_hash` R2"""
    mk_token(token_hash=H1)

    with patch(UTCNOW, return_value=NOW):
        result = dao.get_by_hash(db, token_hash=H1[:63])

    # Then 1
    assert result is None


# [claude] RT-GH-05
def test_rt_gh_05__the_hash_with_a_leading_space_gives_none(db, mk_token, H1):
    """RT-GH-05 — the hash with a leading space gives None.
    Rules: `get_by_hash` R2"""
    mk_token(token_hash=H1)

    with patch(UTCNOW, return_value=NOW):
        result = dao.get_by_hash(db, token_hash=" " + H1)

    # Then 1
    assert result is None


# [claude] RT-GH-06
def test_rt_gh_06__is_no_wildcard_in_a_hash(db, mk_token, H1):
    """RT-GH-06 — _ is no wildcard in a hash.
    Rules: `get_by_hash` R2"""
    mk_token(token_hash=H1)

    with patch(UTCNOW, return_value=NOW):
        result = dao.get_by_hash(db, token_hash=H1[:5] + "_" + H1[6:])

    # Then 1
    assert result is None


# [claude] RT-GH-07
def test_rt_gh_07__a_stored_hash_with_a_leading_space_is_not_found_without_it(db, mk_token, H1):
    """RT-GH-07 — a stored hash with a leading space is not found without it.
    Rules: `get_by_hash` R2"""
    mk_token(token_hash=" " + H1[:63])

    with patch(UTCNOW, return_value=NOW):
        result = dao.get_by_hash(db, token_hash=H1[:63])

    # Then 1
    assert result is None


# [claude] RT-GH-08
def test_rt_gh_08__writes_nothing_a_pending_row_stays_pending_an_unflushed_edit_stays_unf(db, u1, mk_token, H1, H2, H3, FAM1):
    """RT-GH-08 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: `get_by_hash` Side effects"""
    a = mk_token(token_hash=H1)
    b = mk_token(token_hash=H2)
    p = RefreshToken(user_id=u1.id, token_hash=H3, family_id=FAM1, expires_at=LATER)
    db.add(p)
    b.user_agent = "edited"

    with StatementRecorder(db) as recorder:
        with patch(UTCNOW, return_value=NOW):
            result = dao.get_by_hash(db, token_hash=H1)
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
# RefreshTokenDAO.create
# --------------------------------------------------------------------------- #


# [claude] RT-CR-01
def test_rt_cr_01__one_row_with_the_given_values_issued_at_now_revoked_successor_and_last(db, w1, u1, H1, FAM1):
    """RT-CR-01 — one row with the given values; issued_at now; revoked, successor and last use empty.
    Rules: `create` R1, Returns"""
    before = clock()
    with patch(UTCNOW, return_value=NOW):
        result = dao.create(db, user_id=u1.id, token_hash=H1, family_id=FAM1, expires_at=LATER, workspace_id=w1.id, user_agent="Mozilla/5.0", ip_address="10.0.0.1")
    after = clock()

    # Then 1
    assert isinstance(result, RefreshToken)
    # Then 2
    assert result.id is not None
    # Then 3
    row = reread(db, result.id)
    assert row.user_id == u1.id
    assert row.token_hash == H1
    assert row.family_id == FAM1
    assert row.expires_at == LATER
    # Then 4
    assert row.workspace_id == w1.id
    assert row.user_agent == "Mozilla/5.0"
    assert row.ip_address == "10.0.0.1"
    # Then 5
    assert row.revoked_at is None
    assert row.replaced_by_id is None
    assert row.last_used_at is None
    # Then 6
    assert before - SLACK <= row.issued_at <= after + SLACK


# [claude] RT-CR-02
def test_rt_cr_02__optional_values_not_given_are_stored_null(db, u1, H1, FAM1):
    """RT-CR-02 — optional values not given are stored NULL.
    Rules: `create` R1"""
    with patch(UTCNOW, return_value=NOW):
        result = dao.create(db, user_id=u1.id, token_hash=H1, family_id=FAM1, expires_at=LATER)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.workspace_id is None
    assert row.user_agent is None
    assert row.ip_address is None


# [claude] RT-CR-03
def test_rt_cr_03__a_past_expiry_and_a_workspace_the_user_is_not_a_member_of_are_stored(db, w2, u1, H1, FAM1):
    """RT-CR-03 — a past expiry and a workspace the user is not a member of are stored.
    Rules: `create` R2"""
    with patch(UTCNOW, return_value=NOW):
        result = dao.create(db, user_id=u1.id, token_hash=H1, family_id=FAM1, expires_at=PAST, workspace_id=w2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.expires_at == PAST
    assert row.workspace_id == w2.id


# [claude] RT-CR-04
def test_rt_cr_04__a_taken_hash_raises_integrityerror_23505_and_writes_nothing(db, u2, mk_token, H1, FAM2):
    """RT-CR-04 — a taken hash raises IntegrityError 23505 and writes nothing.
    Rules: `create` R3, Errors"""
    mk_token(token_hash=H1)
    before = stored_count(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            with patch(UTCNOW, return_value=NOW):
                dao.create(db, user_id=u2.id, token_hash=H1, family_id=FAM2, expires_at=LATER)
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert stored_count(db) == before


# [claude] RT-CR-05
def test_rt_cr_05__a_65_character_hash_raises_dataerror_22001(db, u1, H1, FAM1):
    """RT-CR-05 — a 65-character hash raises DataError 22001.
    Rules: `create` R3, Errors"""
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            with patch(UTCNOW, return_value=NOW):
                dao.create(db, user_id=u1.id, token_hash=H1 + "b", family_id=FAM1, expires_at=LATER)
    # Then 2
    assert exc.value.orig.pgcode == "22001"
    # Then 3
    assert stored_count(db) == before


# [claude] RT-CR-06
def test_rt_cr_06__a_37_character_family_raises_dataerror_22001(db, u1, H1, FAM1):
    """RT-CR-06 — a 37-character family raises DataError 22001.
    Rules: `create` R3, Errors"""
    before = stored_count(db)

    # Then 1
    with pytest.raises(DataError) as exc:
        with db.begin_nested():
            with patch(UTCNOW, return_value=NOW):
                dao.create(db, user_id=u1.id, token_hash=H1, family_id=FAM1 + "x", expires_at=LATER)
    # Then 2
    assert exc.value.orig.pgcode == "22001"
    # Then 3
    assert stored_count(db) == before


# [claude] RT-CR-07
def test_rt_cr_07__an_unknown_user_raises_integrityerror_23503(db, H1, FAM1):
    """RT-CR-07 — an unknown user raises IntegrityError 23503.
    Rules: `create` R3, Errors"""
    before = stored_count(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            with patch(UTCNOW, return_value=NOW):
                dao.create(db, user_id=MISSING, token_hash=H1, family_id=FAM1, expires_at=LATER)
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    assert stored_count(db) == before


# [claude] RT-CR-08
def test_rt_cr_08__an_unknown_workspace_raises_integrityerror_23503(db, u1, H1, FAM1):
    """RT-CR-08 — an unknown workspace raises IntegrityError 23503.
    Rules: `create` R3, Errors"""
    before = stored_count(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            with patch(UTCNOW, return_value=NOW):
                dao.create(db, user_id=u1.id, token_hash=H1, family_id=FAM1, expires_at=LATER, workspace_id=MISSING)
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    assert stored_count(db) == before


# [claude] RT-CR-09
def test_rt_cr_09__expires_at_none_raises_integrityerror_23502(db, u1, H1, FAM1):
    """RT-CR-09 — expires_at=None raises IntegrityError 23502.
    Rules: `create` R3, Errors"""
    before = stored_count(db)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            with patch(UTCNOW, return_value=NOW):
                dao.create(db, user_id=u1.id, token_hash=H1, family_id=FAM1, expires_at=None)
    # Then 2
    assert exc.value.orig.pgcode == "23502"
    # Then 3
    assert stored_count(db) == before


# [claude] RT-CR-10
def test_rt_cr_10__positional_arguments_raise_typeerror(db, u1, H1, FAM1):
    """RT-CR-10 — positional arguments raise TypeError.
    Rules: `create` R5, Errors"""
    before = stored_count(db)

    # Then 1
    with pytest.raises(TypeError):
        with patch(UTCNOW, return_value=NOW):
            dao.create(db, u1.id, H1, FAM1, LATER)
    # Then 2
    assert stored_count(db) == before


# [claude] RT-CR-11
@pytest.mark.xfail(strict=True, reason="BUG-1407: Over-long user agent or client address makes login fail")
def test_rt_cr_11__a_user_agent_of_513_characters_is_cut_to_512_and_the_row_is_written(db, u1, H1, FAM1):
    """RT-CR-11 — a user agent of 513 characters is cut to 512 and the row is written.
    Rules: `create` R4 [BUG-1407]"""
    with db.begin_nested():
        with patch(UTCNOW, return_value=NOW):
            result = dao.create(db, user_id=u1.id, token_hash=H1, family_id=FAM1, expires_at=LATER, user_agent="u" * 513)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.user_agent == "u" * 512


# [claude] RT-CR-12
@pytest.mark.xfail(strict=True, reason="BUG-1407: Over-long user agent or client address makes login fail")
def test_rt_cr_12__an_ip_address_of_65_characters_is_cut_to_64_and_the_row_is_written(db, u1, H1, FAM1):
    """RT-CR-12 — an IP address of 65 characters is cut to 64 and the row is written.
    Rules: `create` R4 [BUG-1407]"""
    with db.begin_nested():
        with patch(UTCNOW, return_value=NOW):
            result = dao.create(db, user_id=u1.id, token_hash=H1, family_id=FAM1, expires_at=LATER, ip_address="1" * 65)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.ip_address == "1" * 64


# [claude] RT-CR-13
def test_rt_cr_13__a_user_agent_of_exactly_512_and_an_ip_of_exactly_64_characters_are_st(db, u1, H1, FAM1):
    """RT-CR-13 — a user agent of exactly 512 and an IP of exactly 64 characters are stored whole.
    Rules: `create` R4"""
    with patch(UTCNOW, return_value=NOW):
        result = dao.create(db, user_id=u1.id, token_hash=H1, family_id=FAM1, expires_at=LATER, user_agent="u" * 512, ip_address="1" * 64)

    # Then 1
    assert result.id is not None
    # Then 2
    row = reread(db, result.id)
    assert row.user_agent == "u" * 512
    assert row.ip_address == "1" * 64


# [claude] RT-CR-14
def test_rt_cr_14__two_creates_in_one_family_both_stand(db, u1, mk_token, H1, H2, FAM1):
    """RT-CR-14 — two creates in one family both stand.
    Rules: `create` R2"""
    a = mk_token(token_hash=H1)
    before_a = snap(db, a.id)

    with patch(UTCNOW, return_value=NOW):
        result = dao.create(db, user_id=u1.id, token_hash=H2, family_id=FAM1, expires_at=LATER)

    # Then 1
    assert result.id != a.id
    # Then 2
    assert count_where(db, "family_id", FAM1) == 2
    # Then 3
    db.expire_all()
    assert snap(db, a.id) == before_a


# [claude] RT-CR-15
def test_rt_cr_15__the_row_is_flushed_not_committed(db, u1, H1, FAM1):
    """RT-CR-15 — the row is flushed, not committed.
    Rules: `create` Side effects"""
    with commit_spy(db) as spy:
        sp = db.begin_nested()
        with patch(UTCNOW, return_value=NOW):
            result = dao.create(db, user_id=u1.id, token_hash=H1, family_id=FAM1, expires_at=LATER)

        # Then 1
        assert result.id is not None
        # Then 2
        assert count_where(db, "token_hash", H1) == 1
        sp.rollback()
        # Then 3
        assert count_where(db, "token_hash", H1) == 0
    # Then 4
    assert spy.call_count == 0


# --------------------------------------------------------------------------- #
# RefreshTokenDAO.revoke
# --------------------------------------------------------------------------- #


# [claude] RT-RV-01
def test_rt_rv_01__an_unrevoked_row_is_stamped_now_with_no_successor_given_replaced_by_id(db, mk_token, H1):
    """RT-RV-01 — an unrevoked row is stamped now; with no successor given, replaced_by_id stays empty.
    Rules: `revoke` R1, R2, Returns"""
    a = mk_token(token_hash=H1)

    with patch(UTCNOW, return_value=NOW):
        result = dao.revoke(db, row=a)

    # Then 1
    assert result is None
    # Then 2
    row = reread(db, a.id)
    assert row.revoked_at == NOW
    assert row.replaced_by_id is None


# [claude] RT-RV-02
def test_rt_rv_02__a_row_already_revoked_keeps_its_first_stamp(db, mk_token, H1):
    """RT-RV-02 — a row already revoked keeps its first stamp.
    Rules: `revoke` R1"""
    a = mk_token(token_hash=H1, revoked_at=EARLY)

    with patch(UTCNOW, return_value=NOW):
        result = dao.revoke(db, row=a)

    # Then 1
    assert result is None
    # Then 2
    row = reread(db, a.id)
    assert row.revoked_at == EARLY


# [claude] RT-RV-03
def test_rt_rv_03__a_successor_given_is_written(db, mk_token, H1, H2):
    """RT-RV-03 — a successor given is written.
    Rules: `revoke` R2"""
    a = mk_token(token_hash=H1)
    b = mk_token(token_hash=H2)
    before_b = snap(db, b.id)

    with patch(UTCNOW, return_value=NOW):
        result = dao.revoke(db, row=a, replaced_by_id=b.id)

    # Then 1
    assert result is None
    # Then 2
    row = reread(db, a.id)
    assert row.revoked_at == NOW
    assert row.replaced_by_id == b.id
    # Then 3
    assert snap(db, b.id) == before_b


# [claude] RT-RV-04
def test_rt_rv_04__on_a_row_already_revoked_a_new_successor_replaces_the_first_the_stamp(db, mk_token, H1, H2, H3):
    """RT-RV-04 — on a row already revoked, a new successor replaces the first; the stamp stays.
    Rules: `revoke` R1, R2"""
    b = mk_token(token_hash=H2)
    c = mk_token(token_hash=H3)
    a = mk_token(token_hash=H1, revoked_at=EARLY, replaced_by_id=b.id)

    with patch(UTCNOW, return_value=NOW):
        result = dao.revoke(db, row=a, replaced_by_id=c.id)

    # Then 1
    assert result is None
    # Then 2
    row = reread(db, a.id)
    assert row.replaced_by_id == c.id
    assert row.revoked_at == EARLY


# [claude] RT-RV-05
def test_rt_rv_05__replaced_by_id_none_leaves_an_existing_successor_in_place(db, mk_token, H1, H2):
    """RT-RV-05 — replaced_by_id=None leaves an existing successor in place.
    Rules: `revoke` R2"""
    b = mk_token(token_hash=H2)
    a = mk_token(token_hash=H1, replaced_by_id=b.id)

    with patch(UTCNOW, return_value=NOW):
        result = dao.revoke(db, row=a, replaced_by_id=None)

    # Then 1
    assert result is None
    # Then 2
    row = reread(db, a.id)
    assert row.replaced_by_id == b.id
    assert row.revoked_at == NOW


# [claude] RT-RV-06
def test_rt_rv_06__a_stale_session_copy_the_database_s_stamp_is_overwritten(db, mk_token, H1):
    """RT-RV-06 — a stale session copy: the database's stamp is overwritten.
    Rules: `revoke` R3"""
    a = mk_token(token_hash=H1)
    db.execute(text("UPDATE refresh_tokens SET revoked_at = :t WHERE id = :id"), {"t": EARLY, "id": a.id})

    with patch(UTCNOW, return_value=NOW):
        result = dao.revoke(db, row=a)

    # Then 1
    assert result is None
    # Then 2
    row = reread(db, a.id)
    assert row.revoked_at == NOW


# [claude] RT-RV-07
def test_rt_rv_07__an_unknown_successor_raises_integrityerror_23503_and_the_row_keeps_no(db, mk_token, H1):
    """RT-RV-07 — an unknown successor raises IntegrityError 23503 and the row keeps no stamp.
    Rules: `revoke` R4, Errors"""
    a = mk_token(token_hash=H1)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            with patch(UTCNOW, return_value=NOW):
                dao.revoke(db, row=a, replaced_by_id=MISSING)
    # Then 2
    assert exc.value.orig.pgcode == "23503"
    # Then 3
    row = reread(db, a.id)
    assert row.revoked_at is None
    assert row.replaced_by_id is None


# [claude] RT-RV-08
def test_rt_rv_08__deleting_the_successor_later_sets_replaced_by_id_to_null(db, mk_token, H1, H2):
    """RT-RV-08 — deleting the successor later sets replaced_by_id to NULL.
    Rules: `revoke` R4"""
    b = mk_token(token_hash=H2)
    a = mk_token(token_hash=H1, revoked_at=EARLY, replaced_by_id=b.id)

    with patch(UTCNOW, return_value=NOW):
        db.execute(text("DELETE FROM refresh_tokens WHERE id = :id"), {"id": b.id})

    # Then 1
    assert count_where(db, "id", b.id) == 0
    # Then 2
    row = reread(db, a.id)
    assert row.replaced_by_id is None
    assert row.revoked_at == EARLY


# [claude] RT-RV-09
def test_rt_rv_09__the_change_is_flushed_not_committed(db, mk_token, H1, H2):
    """RT-RV-09 — the change is flushed, not committed.
    Rules: `revoke` R4, Side effects"""
    a = mk_token(token_hash=H1)
    b = mk_token(token_hash=H2)

    with commit_spy(db) as spy:
        sp = db.begin_nested()
        with patch(UTCNOW, return_value=NOW):
            result = dao.revoke(db, row=a, replaced_by_id=b.id)

        # Then 1
        assert result is None
        # Then 2
        assert raw(db, a, "revoked_at") == NOW
        # Then 3
        assert raw(db, a, "replaced_by_id") == b.id
        sp.rollback()
        # Then 4
        assert raw(db, a, "revoked_at") is None
    # Then 5
    assert spy.call_count == 0


# --------------------------------------------------------------------------- #
# RefreshTokenDAO.revoke_family
# --------------------------------------------------------------------------- #


# [claude] RT-RF-01
def test_rt_rf_01__every_unrevoked_row_of_the_family_is_stamped_expired_ones_too_revoked(db, mk_token, H1, H2, H3, FAM1):
    """RT-RF-01 — every unrevoked row of the family is stamped, expired ones too; revoked ones keep theirs.
    Rules: `revoke_family` R1, Returns"""
    a = mk_token(token_hash=H1)
    b = mk_token(token_hash=H2, expires_at=PAST)
    c = mk_token(token_hash=H3, revoked_at=EARLY)

    with patch(UTCNOW, return_value=NOW):
        result = dao.revoke_family(db, family_id=FAM1)

    # Then 1
    assert result == 2
    # Then 2
    assert reread(db, a.id).revoked_at == NOW
    # Then 3
    assert reread(db, b.id).revoked_at == NOW
    # Then 4
    assert reread(db, c.id).revoked_at == EARLY


# [claude] RT-RF-02
def test_rt_rf_02__rows_of_every_user_in_the_family_are_stamped_other_families_are_untouc(db, u2, mk_token, H1, H4, H5, FAM1, FAM2):
    """RT-RF-02 — rows of every user in the family are stamped; other families are untouched.
    Rules: `revoke_family` R2"""
    e = mk_token(token_hash=H5, family_id=FAM2)
    a = mk_token(token_hash=H1)
    d = mk_token(token_hash=H4, user_id=u2.id)
    before_e = snap(db, e.id)

    with patch(UTCNOW, return_value=NOW):
        result = dao.revoke_family(db, family_id=FAM1)

    # Then 1
    assert result == 2
    # Then 2
    assert reread(db, a.id).revoked_at == NOW
    # Then 3
    assert reread(db, d.id).revoked_at == NOW
    # Then 4
    assert snap(db, e.id) == before_e


# [claude] RT-RF-03
def test_rt_rf_03__an_unknown_family_gives_0(db, mk_token, H1, FAM2):
    """RT-RF-03 — an unknown family gives 0.
    Rules: `revoke_family` R3"""
    a = mk_token(token_hash=H1)
    before_a = snap(db, a.id)

    with patch(UTCNOW, return_value=NOW):
        result = dao.revoke_family(db, family_id=FAM2)

    # Then 1
    assert result == 0
    # Then 2
    db.expire_all()
    assert snap(db, a.id) == before_a


# [claude] RT-RF-04
def test_rt_rf_04__an_empty_family_gives_0(db, mk_token, H1):
    """RT-RF-04 — an empty family gives 0.
    Rules: `revoke_family` R3"""
    a = mk_token(token_hash=H1)
    before_a = snap(db, a.id)

    with patch(UTCNOW, return_value=NOW):
        result = dao.revoke_family(db, family_id="")

    # Then 1
    assert result == 0
    # Then 2
    db.expire_all()
    assert snap(db, a.id) == before_a


# [claude] RT-RF-05
def test_rt_rf_05__a_family_with_nothing_left_to_revoke_gives_0_as_a_second_call_would(db, mk_token, H1, H2, FAM1):
    """RT-RF-05 — a family with nothing left to revoke gives 0, as a second call would.
    Rules: `revoke_family` R3"""
    a = mk_token(token_hash=H1, revoked_at=EARLY)
    b = mk_token(token_hash=H2, revoked_at=EARLY)

    with patch(UTCNOW, return_value=NOW):
        result = dao.revoke_family(db, family_id=FAM1)

    # Then 1
    assert result == 0
    # Then 2
    assert reread(db, a.id).revoked_at == EARLY
    # Then 3
    assert reread(db, b.id).revoked_at == EARLY


# [claude] RT-RF-06
def test_rt_rf_06__the_family_in_capitals_matches_nothing(db, mk_token, H1, FAM1):
    """RT-RF-06 — the family in capitals matches nothing.
    Rules: `revoke_family` R2"""
    a = mk_token(token_hash=H1)
    before_a = snap(db, a.id)

    with patch(UTCNOW, return_value=NOW):
        result = dao.revoke_family(db, family_id=FAM1.upper())

    # Then 1
    assert result == 0
    # Then 2
    db.expire_all()
    assert snap(db, a.id) == before_a


# [claude] RT-RF-07
def test_rt_rf_07__part_of_a_family_matches_nothing(db, mk_token, H1, FAM1):
    """RT-RF-07 — part of a family matches nothing.
    Rules: `revoke_family` R2"""
    a = mk_token(token_hash=H1)
    before_a = snap(db, a.id)

    with patch(UTCNOW, return_value=NOW):
        result = dao.revoke_family(db, family_id=FAM1[:8])

    # Then 1
    assert result == 0
    # Then 2
    db.expire_all()
    assert snap(db, a.id) == before_a


# [claude] RT-RF-08
def test_rt_rf_08__a_row_loaded_in_the_session_keeps_its_old_revoked_at_until_refreshed(db, mk_token, H1, FAM1):
    """RT-RF-08 — a row loaded in the session keeps its old revoked_at until refreshed.
    Rules: `revoke_family` R4"""
    a = mk_token(token_hash=H1)

    with patch(UTCNOW, return_value=NOW):
        result = dao.revoke_family(db, family_id=FAM1)

    # Then 1
    assert result == 1
    # Then 2
    assert a.revoked_at is None
    # Then 3
    assert reread(db, a.id).revoked_at == NOW


# [claude] RT-RF-09
def test_rt_rf_09__the_update_is_flushed_not_committed(db, mk_token, H1, FAM1):
    """RT-RF-09 — the update is flushed, not committed.
    Rules: `revoke_family` R4, Side effects"""
    a = mk_token(token_hash=H1)

    with commit_spy(db) as spy:
        sp = db.begin_nested()
        with patch(UTCNOW, return_value=NOW):
            result = dao.revoke_family(db, family_id=FAM1)

        # Then 1
        assert result == 1
        # Then 2
        assert raw(db, a, "revoked_at") == NOW
        sp.rollback()
        # Then 3
        assert raw(db, a, "revoked_at") is None
    # Then 4
    assert spy.call_count == 0


# --------------------------------------------------------------------------- #
# RefreshTokenDAO.revoke_all_for_user
# --------------------------------------------------------------------------- #


# [claude] RT-RA-01
def test_rt_ra_01__every_unrevoked_row_of_the_user_is_stamped_whatever_family_workspace(db, w2, u1, mk_token, H1, H2, H3, H4, FAM2):
    """RT-RA-01 — every unrevoked row of the user is stamped, whatever family, workspace or expiry.
    Rules: `revoke_all_for_user` R1, Returns"""
    a = mk_token(token_hash=H1)
    b = mk_token(token_hash=H2, family_id=FAM2, workspace_id=w2.id)
    c = mk_token(token_hash=H3, expires_at=PAST)
    d = mk_token(token_hash=H4, revoked_at=EARLY)

    with patch(UTCNOW, return_value=NOW):
        result = dao.revoke_all_for_user(db, user_id=u1.id)

    # Then 1
    assert result == 3
    # Then 2
    assert reread(db, a.id).revoked_at == NOW
    # Then 3
    assert reread(db, b.id).revoked_at == NOW
    # Then 4
    assert reread(db, c.id).revoked_at == NOW
    # Then 5
    assert reread(db, d.id).revoked_at == EARLY


# [claude] RT-RA-02
def test_rt_ra_02__rows_of_another_user_are_untouched(db, u1, u2, mk_token, H1, H5):
    """RT-RA-02 — rows of another user are untouched.
    Rules: `revoke_all_for_user` R2"""
    x = mk_token(token_hash=H5, user_id=u2.id)
    a = mk_token(token_hash=H1)
    before_x = snap(db, x.id)

    with patch(UTCNOW, return_value=NOW):
        result = dao.revoke_all_for_user(db, user_id=u1.id)

    # Then 1
    assert result == 1
    # Then 2
    assert reread(db, a.id).revoked_at == NOW
    # Then 3
    assert snap(db, x.id) == before_x


# [claude] RT-RA-03
def test_rt_ra_03__user_id_0_gives_0(db, mk_token, H1):
    """RT-RA-03 — user id 0 gives 0.
    Rules: `revoke_all_for_user` R2"""
    a = mk_token(token_hash=H1)
    before_a = snap(db, a.id)

    with patch(UTCNOW, return_value=NOW):
        result = dao.revoke_all_for_user(db, user_id=0)

    # Then 1
    assert result == 0
    # Then 2
    db.expire_all()
    assert snap(db, a.id) == before_a


# [claude] RT-RA-04
def test_rt_ra_04__nothing_left_to_revoke_gives_0(db, u1, mk_token, H1):
    """RT-RA-04 — nothing left to revoke gives 0.
    Rules: `revoke_all_for_user` R2"""
    a = mk_token(token_hash=H1, revoked_at=EARLY)

    with patch(UTCNOW, return_value=NOW):
        result = dao.revoke_all_for_user(db, user_id=u1.id)

    # Then 1
    assert result == 0
    # Then 2
    assert reread(db, a.id).revoked_at == EARLY


# [claude] RT-RA-05
def test_rt_ra_05__a_row_loaded_in_the_session_keeps_its_old_revoked_at_until_refreshed(db, u1, mk_token, H1):
    """RT-RA-05 — a row loaded in the session keeps its old revoked_at until refreshed.
    Rules: `revoke_all_for_user` R3"""
    a = mk_token(token_hash=H1)

    with patch(UTCNOW, return_value=NOW):
        result = dao.revoke_all_for_user(db, user_id=u1.id)

    # Then 1
    assert result == 1
    # Then 2
    assert a.revoked_at is None
    # Then 3
    assert reread(db, a.id).revoked_at == NOW


# [claude] RT-RA-06
def test_rt_ra_06__the_update_is_flushed_not_committed(db, u1, mk_token, H1):
    """RT-RA-06 — the update is flushed, not committed.
    Rules: `revoke_all_for_user` Side effects"""
    a = mk_token(token_hash=H1)

    with commit_spy(db) as spy:
        sp = db.begin_nested()
        with patch(UTCNOW, return_value=NOW):
            result = dao.revoke_all_for_user(db, user_id=u1.id)

        # Then 1
        assert result == 1
        # Then 2
        assert raw(db, a, "revoked_at") == NOW
        sp.rollback()
        # Then 3
        assert raw(db, a, "revoked_at") is None
    # Then 4
    assert spy.call_count == 0


# [claude] RT-RA-07
def test_rt_ra_07__rows_of_another_user_with_a_lower_id_are_untouched(db, u2, mk_token, H1, H5):
    """RT-RA-07 — rows of another user with a lower id are untouched.
    Rules: `revoke_all_for_user` R2"""
    x = mk_token(token_hash=H5)
    a = mk_token(token_hash=H1, user_id=u2.id)
    before_x = snap(db, x.id)

    with patch(UTCNOW, return_value=NOW):
        result = dao.revoke_all_for_user(db, user_id=u2.id)

    # Then 1
    assert result == 1
    # Then 2
    assert reread(db, a.id).revoked_at == NOW
    # Then 3
    assert snap(db, x.id) == before_x


# --------------------------------------------------------------------------- #
# RefreshTokenDAO.touch_last_used
# --------------------------------------------------------------------------- #


# [claude] RT-TL-01
def test_rt_tl_01__last_used_at_is_replaced_by_now_a_revoked_row_stays_revoked_nothing_e(db, mk_token, H1):
    """RT-TL-01 — last_used_at is replaced by now; a revoked row stays revoked; nothing else changes.
    Rules: `touch_last_used` R1, Returns"""
    a = mk_token(token_hash=H1, revoked_at=EARLY, last_used_at=EARLY, user_agent="Mozilla/5.0")
    before_a = snap_except(db, a.id, "last_used_at")

    with patch(UTCNOW, return_value=NOW):
        result = dao.touch_last_used(db, row=a)

    # Then 1
    assert result is None
    # Then 2
    row = reread(db, a.id)
    assert row.last_used_at == NOW
    # Then 3
    assert snap_except(db, a.id, "last_used_at") == before_a
    # Then 4
    assert row.revoked_at == EARLY


# [claude] RT-TL-02
def test_rt_tl_02__the_change_is_flushed_not_committed(db, mk_token, H1):
    """RT-TL-02 — the change is flushed, not committed.
    Rules: `touch_last_used` R1, Side effects"""
    a = mk_token(token_hash=H1)

    with commit_spy(db) as spy:
        sp = db.begin_nested()
        with patch(UTCNOW, return_value=NOW):
            result = dao.touch_last_used(db, row=a)

        # Then 1
        assert result is None
        # Then 2
        assert raw(db, a, "last_used_at") == NOW
        sp.rollback()
        # Then 3
        assert raw(db, a, "last_used_at") is None
    # Then 4
    assert spy.call_count == 0


# [claude] RT-TL-03
def test_rt_tl_03__an_unrevoked_row_stays_unrevoked_only_last_used_at_changes(db, mk_token, H1):
    """RT-TL-03 — an unrevoked row stays unrevoked; only last_used_at changes.
    Rules: `touch_last_used` R1"""
    a = mk_token(token_hash=H1, user_agent="Mozilla/5.0")
    before_a = snap_except(db, a.id, "last_used_at")

    with patch(UTCNOW, return_value=NOW):
        result = dao.touch_last_used(db, row=a)

    # Then 1
    assert result is None
    # Then 2
    row = reread(db, a.id)
    assert row.last_used_at == NOW
    # Then 3
    assert snap_except(db, a.id, "last_used_at") == before_a
    # Then 4
    assert row.revoked_at is None
