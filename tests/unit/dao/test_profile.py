"""Unit tests for app/dao/profile.py.

Implements tests/unit/dao/profile.cases.md, one test per case, in card order.
Real Postgres session (`db` fixture). Nothing is mocked except the `wraps=` spy
of PRF-AU-04 (BUG-038); bcrypt runs for real and no clock is read
(Conventions, Externals: None).

Built in normal mode (no local model): every test sits below a `# [claude] <ID>`
comment.
"""

# ruff: noqa: SIM117  (Conventions prescribe `with pytest.raises(...)` around `with db.begin_nested()`)
import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError

from app.core.security import get_password_hash, verify_password
from app.dao.profile import profile_dao
from app.models.profile import Profile
from app.schemas.profile import ProfileCreate
from tests.unit.factories import make_profile

# --------------------------------------------------------------------------- #
# Conventions -> constants
# --------------------------------------------------------------------------- #

# Convention "dao = the singleton profile_dao"
dao = profile_dao

# Convention "PW", "TZ"
PW = "Correct-Horse-9"
TZ = "Asia/Dhaka"

BUG_038 = "BUG-038: Login timing reveals which emails are registered"
BUG_500 = "BUG-500: Over-long login password reveals whether the email is registered"
BUG_1406 = "BUG-1406: A person's name is stored untrimmed and may be blank"
BUG_1860 = "BUG-1860: An email identifies one account only with its exact capitals"
BUG_1861 = "BUG-1861: Account email stored with the capitals typed"
BUG_1862 = "BUG-1862: Two accounts can hold the same email in other capitals"


# Convention "TAG, MIXED, LOWER, UPPER, EA, EZ": TAG is made once per test.
@pytest.fixture
def e():
    tag = uuid.uuid4().hex[:8]
    return SimpleNamespace(
        TAG=tag,
        MIXED=f"Ann.Lee.{tag}@example.com",
        LOWER=f"ann.lee.{tag}@example.com",
        UPPER=f"ANN.LEE.{tag.upper()}@EXAMPLE.COM",
        EA=f"bob.{tag}@example.com",
        EZ=f"zed.{tag}@example.com",
    )


# --------------------------------------------------------------------------- #
# Conventions -> Given rows (make_profile flushes before it returns)
# --------------------------------------------------------------------------- #


# Convention "profile(e)" / "profile(e, h)"; keywords are the columns after "but".
def profile(db, email, hashed_password=None, **columns):
    if hashed_password is not None:
        columns["hashed_password"] = hashed_password
    return make_profile(db, email=email, **columns)


# --------------------------------------------------------------------------- #
# Named checks -> reading helpers (plain functions; no expected values inside)
# --------------------------------------------------------------------------- #


# Convention "re-read X"
def reread(db, profile_id):
    db.expire_all()
    return db.get(Profile, profile_id)


# Convention "the new row"
def new_row(db, result):
    db.expire_all()
    return db.scalar(select(Profile).where(Profile.id == result.id))


# Convention "count(e)"
def count(db, email):
    return db.scalar(
        select(func.count()).select_from(Profile).where(Profile.email == email)
    )


# Convention "count_ci(e)"
def count_ci(db, email):
    return db.scalar(
        select(func.count())
        .select_from(Profile)
        .where(func.lower(Profile.email) == email.lower())
    )


# Convention "Statement recorder": statement texts sent on db.connection() during the When.
class StatementRecorder:
    def __init__(self, db):
        self.conn = db.connection()
        self.statements = []

    def _record(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append(statement)

    def __enter__(self):
        event.listen(self.conn, "before_cursor_execute", self._record)
        return self

    def __exit__(self, *exc_info):
        event.remove(self.conn, "before_cursor_execute", self._record)
        return False

    def written(self):
        return [
            s
            for s in self.statements
            if s.strip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
        ]


# =========================================================================== #
# DAOProfile.get_by_email
# =========================================================================== #


# [claude] PRF-GE-01
def test_prf_ge_01__exact_text_found_not_neighbour(db, e):
    """PRF-GE-01 — the profile stored with exactly that text is found, not a neighbour.
    Rules: get_by_email R1."""
    profile(db, e.EA)
    p = profile(db, e.MIXED)
    profile(db, e.EZ)

    result = dao.get_by_email(db, email=e.MIXED)

    # Then 1
    assert isinstance(result, Profile)
    # Then 2
    assert result.id == p.id
    # Then 3
    assert result.email == e.MIXED


# [claude] PRF-GE-02
def test_prf_ge_02__lower_case_stored_found_by_same_text(db, e):
    """PRF-GE-02 — a lower-case stored email is found by the same lower-case text.
    Rules: get_by_email R1."""
    profile(db, e.EA)
    p = profile(db, e.LOWER)
    profile(db, e.EZ)

    result = dao.get_by_email(db, email=e.LOWER)

    # Then 1
    assert result.id == p.id


# [claude] PRF-GE-03
@pytest.mark.xfail(strict=True, reason=BUG_1860)
def test_prf_ge_03__other_capitals_find_mixed_case(db, e):
    """PRF-GE-03 — other capitals in the argument find a mixed-case stored email.
    Rules: get_by_email R1a [BUG-1860]."""
    profile(db, e.EA)
    p = profile(db, e.MIXED)
    profile(db, e.EZ)

    result = dao.get_by_email(db, email=e.LOWER)

    # Then 1
    assert result is not None
    # Then 2
    assert result.id == p.id


# [claude] PRF-GE-04
@pytest.mark.xfail(strict=True, reason=BUG_1860)
def test_prf_ge_04__all_capitals_find_mixed_case(db, e):
    """PRF-GE-04 — an all-capitals argument finds a mixed-case stored email.
    Rules: get_by_email R1a [BUG-1860]."""
    profile(db, e.EA)
    p = profile(db, e.MIXED)
    profile(db, e.EZ)

    result = dao.get_by_email(db, email=e.UPPER)

    # Then 1
    assert result is not None
    # Then 2
    assert result.id == p.id


# [claude] PRF-GE-05
@pytest.mark.xfail(strict=True, reason=BUG_1860)
def test_prf_ge_05__outer_spaces_of_argument_ignored(db, e):
    """PRF-GE-05 — outer spaces around the argument are ignored.
    Rules: get_by_email R1a [BUG-1860]."""
    profile(db, e.EA)
    p = profile(db, e.MIXED)
    profile(db, e.EZ)

    result = dao.get_by_email(db, email=f" {e.MIXED} ")

    # Then 1
    assert result is not None
    # Then 2
    assert result.id == p.id


# [claude] PRF-GE-06
@pytest.mark.xfail(strict=True, reason=BUG_1860)
def test_prf_ge_06__mixed_case_argument_finds_lower_case(db, e):
    """PRF-GE-06 — a mixed-case argument finds a lower-case stored email.
    Rules: get_by_email R1a [BUG-1860]."""
    profile(db, e.EA)
    p = profile(db, e.LOWER)
    profile(db, e.EZ)

    result = dao.get_by_email(db, email=e.MIXED)

    # Then 1
    assert result is not None
    # Then 2
    assert result.id == p.id


# [claude] PRF-GE-07
def test_prf_ge_07__inner_text_must_match(db, e):
    """PRF-GE-07 — inner text must still match: one more character gives None.
    Rules: get_by_email R1a."""
    profile(db, e.EA)
    profile(db, e.MIXED)
    profile(db, e.EZ)

    result = dao.get_by_email(db, email=f"ann.lee2.{e.TAG}@example.com")

    # Then 1
    assert result is None


# [claude] PRF-GE-08
def test_prf_ge_08__part_of_email_gives_none(db, e):
    """PRF-GE-08 — a part of the stored email gives None.
    Rules: get_by_email R1, R2."""
    profile(db, e.EA)
    profile(db, e.MIXED)
    profile(db, e.EZ)

    result = dao.get_by_email(db, email=f"Ann.Lee.{e.TAG}@example")

    # Then 1
    assert result is None


# [claude] PRF-GE-09
def test_prf_ge_09__underscore_is_literal(db, e):
    """PRF-GE-09 — `_` in the argument is a literal character, not a wildcard.
    Rules: get_by_email R1, R2."""
    profile(db, e.EA)
    profile(db, e.MIXED)
    profile(db, e.EZ)

    result = dao.get_by_email(db, email=f"Ann_Lee.{e.TAG}@example.com")

    # Then 1
    assert result is None


# [claude] PRF-GE-10
def test_prf_ge_10__unknown_email_gives_none(db, e):
    """PRF-GE-10 — an unknown email gives None, no error.
    Rules: get_by_email R2."""
    profile(db, e.EA)
    profile(db, e.EZ)

    result = dao.get_by_email(db, email=f"nobody.{e.TAG}@example.com")

    # Then 1
    assert result is None


# [claude] PRF-GE-11
def test_prf_ge_11__empty_email_gives_none(db, e):
    """PRF-GE-11 — an empty email gives None, no error.
    Rules: get_by_email R2."""
    profile(db, e.EA)
    profile(db, e.EZ)

    result = dao.get_by_email(db, email="")

    # Then 1
    assert result is None


# [claude] PRF-GE-12
def test_prf_ge_12__writes_nothing(db, e):
    """PRF-GE-12 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: get_by_email Side effects."""
    p = profile(db, e.MIXED)
    b = profile(db, e.EZ)
    n = Profile(
        name="New",
        email=f"new.{e.TAG}@example.com",
        user_id=f"new-{e.TAG}",
        hashed_password="x",
    )
    db.add(n)
    b.name = "Changed"

    with StatementRecorder(db) as rec:
        result = dao.get_by_email(db, email=e.MIXED)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert n in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert b in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert not db.deleted
    # Then 7
    assert rec.written() == []


# [claude] PRF-GE-13
@pytest.mark.xfail(strict=True, reason=BUG_1860)
def test_prf_ge_13__outer_space_on_stored_side_ignored(db, e):
    """PRF-GE-13 — an outer space on the stored side is ignored too.
    Rules: get_by_email R1a [BUG-1860]."""
    profile(db, e.EA)
    p = profile(db, f" {e.LOWER}")
    profile(db, e.EZ)

    result = dao.get_by_email(db, email=e.LOWER)

    # Then 1
    assert result is not None
    # Then 2
    assert result.id == p.id


# [claude] PRF-GE-14
def test_prf_ge_14__percent_is_literal(db, e):
    """PRF-GE-14 — `%` in the local part is a literal character, not a wildcard.
    Rules: get_by_email R1, R1a."""
    profile(db, e.EA)
    profile(db, e.MIXED)
    profile(db, e.EZ)

    result = dao.get_by_email(db, email=f"%.{e.TAG}@example.com")

    # Then 1
    assert result is None


# [claude] PRF-GE-15
def test_prf_ge_15__percent_alone_finds_nothing(db, e):
    """PRF-GE-15 — `%` alone before the domain finds no account.
    Rules: get_by_email R1, R1a."""
    profile(db, e.EA)
    profile(db, e.MIXED)
    profile(db, e.EZ)

    result = dao.get_by_email(db, email="%@example.com")

    # Then 1
    assert result is None


# [claude] PRF-GE-16
def test_prf_ge_16__inner_space_in_argument_not_ignored(db, e):
    """PRF-GE-16 — an inner space in the argument is not ignored.
    Rules: get_by_email R1a."""
    profile(db, e.EA)
    profile(db, e.MIXED)
    profile(db, e.EZ)

    result = dao.get_by_email(db, email=f"Ann.Lee .{e.TAG}@example.com")

    # Then 1
    assert result is None


# [claude] PRF-GE-17
def test_prf_ge_17__inner_space_on_stored_side_not_ignored(db, e):
    """PRF-GE-17 — an inner space on the stored side is not ignored.
    Rules: get_by_email R1a."""
    profile(db, e.EA)
    profile(db, f"Ann. Lee.{e.TAG}@example.com")
    profile(db, e.EZ)

    result = dao.get_by_email(db, email=e.MIXED)

    # Then 1
    assert result is None


# =========================================================================== #
# DAOProfile.create
# =========================================================================== #


# [claude] PRF-CR-01
def test_prf_cr_01__inserts_every_field(db, e):
    """PRF-CR-01 — one profile is inserted with every field set as stated.
    Rules: create R1, Returns, Side effects."""
    result = dao.create(
        db,
        obj_in=ProfileCreate(name="Ann Lee", email=e.LOWER, password=PW, timezone=TZ),
    )

    # Then 1
    assert isinstance(result, Profile)
    # Then 2
    assert result.id is not None
    # Then 3
    row = new_row(db, result)
    assert row.name == "Ann Lee"
    assert row.email == e.LOWER
    assert row.user_id == e.LOWER
    assert row.timezone == "Asia/Dhaka"
    # Then 4
    assert row.is_platform_admin is False
    assert row.saved_stamp is None
    # Then 5
    assert row.hashed_password.startswith("$2")
    # Then 6
    assert verify_password(PW, row.hashed_password) is True
    # Then 7
    assert row.hashed_password != PW
    # Then 8
    assert count(db, e.LOWER) == 1


# [claude] PRF-CR-02
def test_prf_cr_02__same_password_two_hashes(db, e):
    """PRF-CR-02 — the same password hashed twice gives two different hashes.
    Rules: create R1."""
    first = dao.create(
        db, obj_in=ProfileCreate(name="Ann", email=e.EA, password=PW, timezone=TZ)
    )

    result = dao.create(
        db, obj_in=ProfileCreate(name="Zed", email=e.EZ, password=PW, timezone=TZ)
    )

    # Then 1
    assert result.id != first.id
    # Then 2
    r = reread(db, result.id)
    f = reread(db, first.id)
    assert r.hashed_password != f.hashed_password
    # Then 3
    assert verify_password(PW, r.hashed_password) is True
    # Then 4
    assert verify_password(PW, f.hashed_password) is True


# [claude] PRF-CR-03
def test_prf_cr_03__flushes_never_commits(db, e):
    """PRF-CR-03 — create flushes but never commits.
    Rules: create Returns, Side effects."""
    sp = db.begin_nested()
    with patch.object(db, "commit", wraps=db.commit) as cm:
        result = dao.create(
            db,
            obj_in=ProfileCreate(name="Ann", email=e.LOWER, password=PW, timezone=TZ),
        )

    # Then 1
    assert result.id is not None
    # Then 2
    assert count(db, e.LOWER) == 1
    # Then 3
    assert cm.call_count == 0
    sp.rollback()
    # Then 4
    assert count(db, e.LOWER) == 0


# [claude] PRF-CR-04
@pytest.mark.xfail(strict=True, reason=BUG_1406)
def test_prf_cr_04__name_outer_spaces_removed(db, e):
    """PRF-CR-04 — outer spaces of the name are removed before storing.
    Rules: create R2 [BUG-1406]."""
    result = dao.create(
        db, obj_in=ProfileCreate(name="  Ann ", email=e.LOWER, password=PW, timezone=TZ)
    )

    # Then 1
    assert result.id is not None
    # Then 2
    assert new_row(db, result).name == "Ann"


# [claude] PRF-CR-05
@pytest.mark.xfail(strict=True, reason=BUG_1406)
def test_prf_cr_05__whitespace_only_name_refused(db, e):
    """PRF-CR-05 — a whitespace-only name is refused by the schema.
    Rules: create R2 [BUG-1406]."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        ProfileCreate(name="   ", email=e.LOWER, password=PW, timezone=TZ)
    # Then 2
    assert count(db, e.LOWER) == 0


# [claude] PRF-CR-06
@pytest.mark.xfail(strict=True, reason=BUG_1406)
def test_prf_cr_06__empty_name_refused(db, e):
    """PRF-CR-06 — an empty name is refused by the schema.
    Rules: create R2 [BUG-1406]."""
    # Then 1
    with pytest.raises(PydanticValidationError):
        ProfileCreate(name="", email=e.LOWER, password=PW, timezone=TZ)
    # Then 2
    assert count(db, e.LOWER) == 0


# [claude] PRF-CR-07
def test_prf_cr_07__inner_spaces_and_capitals_kept(db, e):
    """PRF-CR-07 — inner spaces and capitals of the name are kept.
    Rules: create R2."""
    result = dao.create(
        db,
        obj_in=ProfileCreate(name="Ann  LEE", email=e.LOWER, password=PW, timezone=TZ),
    )

    # Then 1
    assert result.id is not None
    # Then 2
    assert new_row(db, result).name == "Ann  LEE"


# [claude] PRF-CR-08
def test_prf_cr_08__empty_password_hashed(db, e):
    """PRF-CR-08 — an empty password is hashed and stored.
    Rules: create R3."""
    result = dao.create(
        db, obj_in=ProfileCreate(name="Ann", email=e.LOWER, password="", timezone=TZ)
    )

    # Then 1
    assert result.id is not None
    # Then 2
    row = new_row(db, result)
    assert row.hashed_password.startswith("$2")
    # Then 3
    assert verify_password("", row.hashed_password) is True


# [claude] PRF-CR-09
def test_prf_cr_09__72_ascii_bytes_accepted(db, e):
    """PRF-CR-09 — a password of 72 ASCII bytes is accepted.
    Rules: create R3."""
    result = dao.create(
        db,
        obj_in=ProfileCreate(name="Ann", email=e.LOWER, password="a" * 72, timezone=TZ),
    )

    # Then 1
    assert result.id is not None
    # Then 2
    assert verify_password("a" * 72, new_row(db, result).hashed_password) is True


# [claude] PRF-CR-10
def test_prf_cr_10__36_two_byte_chars_accepted(db, e):
    """PRF-CR-10 — a password of 36 two-byte characters (72 bytes) is accepted.
    Rules: create R3."""
    result = dao.create(
        db,
        obj_in=ProfileCreate(name="Ann", email=e.LOWER, password="é" * 36, timezone=TZ),
    )

    # Then 1
    assert result.id is not None
    # Then 2
    assert verify_password("é" * 36, new_row(db, result).hashed_password) is True


# [claude] PRF-CR-11
def test_prf_cr_11__73_ascii_bytes_raise(db, e):
    """PRF-CR-11 — a password of 73 ASCII bytes raises before anything is added.
    Rules: create R3, Errors row 1."""
    # Then 1
    with pytest.raises(ValueError) as exc:
        dao.create(
            db,
            obj_in=ProfileCreate(
                name="Ann", email=e.LOWER, password="a" * 73, timezone=TZ
            ),
        )
    # Then 2
    assert str(exc.value) == "Password exceeds bcrypt's 72-byte limit"
    # Then 3
    assert len(db.new) == 0
    # Then 4
    assert count(db, e.LOWER) == 0


# [claude] PRF-CR-12
def test_prf_cr_12__bytes_counted_not_characters(db, e):
    """PRF-CR-12 — 37 characters that are 73 bytes raise: bytes are counted, not characters.
    Rules: create R3, Errors row 1."""
    # Then 1
    with pytest.raises(ValueError) as exc:
        dao.create(
            db,
            obj_in=ProfileCreate(
                name="Ann", email=e.LOWER, password="é" * 36 + "a", timezone=TZ
            ),
        )
    # Then 2
    assert str(exc.value) == "Password exceeds bcrypt's 72-byte limit"
    # Then 3
    assert len(db.new) == 0
    # Then 4
    assert count(db, e.LOWER) == 0


# [claude] PRF-CR-13
def test_prf_cr_13__taken_email_fails_at_flush(db, e):
    """PRF-CR-13 — an email already taken with the same text fails at the flush.
    Rules: create R4, Errors row 2."""
    profile(db, e.EA)
    p = profile(db, e.LOWER, name="Ann")
    profile(db, e.EZ)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(
                db,
                obj_in=ProfileCreate(
                    name="Ann Two", email=e.LOWER, password=PW, timezone=TZ
                ),
            )
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert count(db, e.LOWER) == 1
    # Then 4
    row = reread(db, p.id)
    assert row.name == "Ann"
    assert row.email == e.LOWER


# [claude] PRF-CR-14
def test_prf_cr_14__email_equal_to_other_user_id_fails(db, e):
    """PRF-CR-14 — an email equal to another profile's user_id fails on the user_id constraint.
    Rules: create R4, Errors row 2."""
    profile(db, e.EA, user_id=e.LOWER)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(
                db,
                obj_in=ProfileCreate(
                    name="Ann", email=e.LOWER, password=PW, timezone=TZ
                ),
            )
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert exc.value.orig.diag.constraint_name == "profiles_user_id_key"
    # Then 4
    assert count(db, e.LOWER) == 0


# [claude] PRF-CR-15
@pytest.mark.xfail(strict=True, reason=BUG_1861)
def test_prf_cr_15__email_stored_lower_cased(db, e):
    """PRF-CR-15 — the email is stored lower-cased, and user_id with it.
    Rules: create R4a [BUG-1861]."""
    result = dao.create(
        db,
        obj_in=ProfileCreate(
            name="Ann", email=f"Ann.Lee.{e.TAG}@Example.COM", password=PW, timezone=TZ
        ),
    )

    # Then 1
    assert result.id is not None
    # Then 2
    row = new_row(db, result)
    assert row.email == e.LOWER
    # Then 3
    assert row.user_id == e.LOWER


# [claude] PRF-CR-16
def test_prf_cr_16__user_id_equals_email_domain_lowered(db, e):
    """PRF-CR-16 — user_id equals the stored email and the domain is lower-case.
    Rules: create R1, R4a."""
    result = dao.create(
        db,
        obj_in=ProfileCreate(
            name="Ann", email=f"Ann.Lee.{e.TAG}@Example.COM", password=PW, timezone=TZ
        ),
    )

    # Then 1
    assert result.id is not None
    # Then 2
    row = new_row(db, result)
    assert row.user_id == row.email
    # Then 3
    assert row.email.endswith("@example.com")
    # Then 4
    assert row.email.lower() == e.LOWER


# [claude] PRF-CR-17
@pytest.mark.xfail(strict=True, reason=BUG_1862)
def test_prf_cr_17__case_variant_second_account_refused(db, e):
    """PRF-CR-17 — a second account for the same address in other capitals is refused by the database.
    Rules: create R4b [BUG-1862]."""
    profile(db, e.EA)
    profile(db, e.MIXED)
    profile(db, e.EZ)

    # Then 1
    with pytest.raises(IntegrityError) as exc:
        with db.begin_nested():
            dao.create(
                db,
                obj_in=ProfileCreate(
                    name="Ann Two", email=e.LOWER, password=PW, timezone=TZ
                ),
            )
    # Then 2
    assert exc.value.orig.pgcode == "23505"
    # Then 3
    assert count_ci(db, e.LOWER) == 1


# [claude] PRF-CR-18
def test_prf_cr_18__dict_raises_attribute_error(db, e):
    """PRF-CR-18 — a plain dict raises AttributeError before anything is added.
    Rules: create R5, Errors row 3."""
    # Then 1
    with pytest.raises(AttributeError) as exc:
        dao.create(
            db, obj_in={"name": "Ann", "email": e.LOWER, "password": PW, "timezone": TZ}
        )
    # Then 2
    assert str(exc.value) == "'dict' object has no attribute 'name'"
    # Then 3
    assert len(db.new) == 0
    # Then 4
    assert count(db, e.LOWER) == 0


# =========================================================================== #
# DAOProfile.authenticate
# =========================================================================== #


# [claude] PRF-AU-01
def test_prf_au_01__right_email_and_password(db, e):
    """PRF-AU-01 — the right email and password return that profile, not a neighbour with the same password.
    Rules: authenticate R1."""
    hpw = get_password_hash(PW)
    profile(db, e.EA, hpw)
    p = profile(db, e.MIXED, hpw)
    profile(db, e.EZ, hpw)

    result = dao.authenticate(db, email=e.MIXED, password=PW)

    # Then 1
    assert isinstance(result, Profile)
    # Then 2
    assert result.id == p.id


# [claude] PRF-AU-02
@pytest.mark.xfail(strict=True, reason=BUG_1860)
def test_prf_au_02__other_capitals_log_in(db, e):
    """PRF-AU-02 — logging in with other capitals finds the account.
    Rules: authenticate R1a [BUG-1860]."""
    hpw = get_password_hash(PW)
    profile(db, e.EA, hpw)
    p = profile(db, e.MIXED, hpw)
    profile(db, e.EZ, hpw)

    result = dao.authenticate(db, email=e.UPPER, password=PW)

    # Then 1
    assert result is not None
    # Then 2
    assert result.id == p.id


# [claude] PRF-AU-03
def test_prf_au_03__unknown_email_gives_none(db, e):
    """PRF-AU-03 — an unknown email gives None.
    Rules: authenticate R2."""
    hpw = get_password_hash(PW)
    profile(db, e.EA, hpw)
    profile(db, e.EZ, hpw)

    result = dao.authenticate(db, email=f"nobody.{e.TAG}@example.com", password=PW)

    # Then 1
    assert result is None


# [claude] PRF-AU-04
@pytest.mark.xfail(strict=True, reason=BUG_038)
def test_prf_au_04__unknown_email_still_checks_password(db, e):
    """PRF-AU-04 — for an unknown email a password check still runs once.
    Rules: authenticate R2a [BUG-038]."""
    hpw = get_password_hash(PW)
    profile(db, e.EA, hpw)

    with patch("app.core.security.verify_password", wraps=verify_password) as spy:
        result = dao.authenticate(db, email=f"nobody.{e.TAG}@example.com", password=PW)

    # Then 1
    assert result is None
    # Then 2
    assert spy.call_count == 1


# [claude] PRF-AU-05
def test_prf_au_05__wrong_password_gives_none(db, e):
    """PRF-AU-05 — a wrong password gives None.
    Rules: authenticate R3."""
    profile(db, e.MIXED, get_password_hash(PW))

    result = dao.authenticate(db, email=e.MIXED, password="correct-horse-9")

    # Then 1
    assert result is None


# [claude] PRF-AU-06
def test_prf_au_06__empty_stored_hash_gives_none(db, e):
    """PRF-AU-06 — an empty stored hash gives None, no error.
    Rules: authenticate R3."""
    profile(db, e.MIXED, "")

    result = dao.authenticate(db, email=e.MIXED, password=PW)

    # Then 1
    assert result is None


# [claude] PRF-AU-07
def test_prf_au_07__non_bcrypt_hash_gives_none(db, e):
    """PRF-AU-07 — a stored value that is not a bcrypt hash gives None, no error.
    Rules: authenticate R3."""
    profile(db, e.MIXED, "not-a-hash")

    result = dao.authenticate(db, email=e.MIXED, password=PW)

    # Then 1
    assert result is None


# [claude] PRF-AU-08
def test_prf_au_08__empty_password_gives_none(db, e):
    """PRF-AU-08 — an empty password against a real hash gives None.
    Rules: authenticate R3."""
    profile(db, e.MIXED, get_password_hash(PW))

    result = dao.authenticate(db, email=e.MIXED, password="")

    # Then 1
    assert result is None


# [claude] PRF-AU-09
@pytest.mark.xfail(strict=True, reason=BUG_500)
def test_prf_au_09__over_72_bytes_known_email_gives_none(db, e):
    """PRF-AU-09 — a password over 72 bytes for a known email gives None, not an error.
    Rules: authenticate R4 [BUG-500], Errors."""
    profile(db, e.MIXED, get_password_hash(PW))

    # Then 1 (today the call itself raises ValueError)
    result = dao.authenticate(db, email=e.MIXED, password="a" * 73)
    assert result is None


# [claude] PRF-AU-10
def test_prf_au_10__over_72_bytes_unknown_email_gives_none(db, e):
    """PRF-AU-10 — a password over 72 bytes for an unknown email gives None.
    Rules: authenticate R4."""
    profile(db, e.EA, get_password_hash(PW))

    result = dao.authenticate(
        db, email=f"nobody.{e.TAG}@example.com", password="a" * 73
    )

    # Then 1
    assert result is None


# [claude] PRF-AU-11
def test_prf_au_11__writes_nothing(db, e):
    """PRF-AU-11 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed.
    Rules: authenticate R5."""
    p = profile(db, e.MIXED, get_password_hash(PW))
    b = profile(db, e.EZ)
    n = Profile(
        name="New",
        email=f"new.{e.TAG}@example.com",
        user_id=f"new-{e.TAG}",
        hashed_password="x",
    )
    db.add(n)
    b.name = "Changed"

    with StatementRecorder(db) as rec:
        result = dao.authenticate(db, email=e.MIXED, password=PW)

    # Then 1
    assert result.id == p.id
    # Then 2
    assert n in db.new
    # Then 3
    assert len(db.new) == 1
    # Then 4
    assert b in db.dirty
    # Then 5
    assert len(db.dirty) == 1
    # Then 6
    assert not db.deleted
    # Then 7
    assert rec.written() == []
