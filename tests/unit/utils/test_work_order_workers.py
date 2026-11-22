"""Unit tests for app/utils/work_order_workers.py.

Implements tests/unit/utils/work_order_workers.cases.md (revision 2), one test
per case. Pure callables (parse / join / resolve / resolve-text) use no
database; `load_active_member_lookups` and `display_names_for_user_ids` use the
real Postgres session (`db` fixture). Externals mocked: none.
"""
import uuid

import pytest
from sqlalchemy import func, select

from app.models.profile import Profile
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.utils.work_order_workers import (
    MemberLookup,
    display_names_for_user_ids,
    join_worker_names,
    load_active_member_lookups,
    parse_worker_names,
    resolve_names_to_members,
    resolve_worker_text_to_members,
)
from tests.unit.factories import make_profile, make_workspace

BUG_380 = "BUG-380: Worker name matching several members is given to an arbitrary one"
BUG_381 = "BUG-381: Worker display text repeats members and unmatched names"
BUG_382 = "BUG-382: Member with whitespace-only name vanishes from worker display text"

# --------------------------------------------------------------------------- #
# Conventions -> fixtures / helpers
# --------------------------------------------------------------------------- #

# Convention "Pure callables": members built directly as MemberLookup
M7 = MemberLookup(7, "Rahim", "rahim@x.com")
M9 = MemberLookup(9, "Karim", "karim@x.com")
M12 = MemberLookup(12, "rahim", "rahim12@x.com")
M31 = MemberLookup(31, "   ", "w@x.com")


# Convention "Result notation": ids=[...], unmatched=[...], display="..."
def assert_res(res, ids, unmatched, display):
    assert res.matched_user_ids == ids
    assert res.unmatched_names == unmatched
    assert res.display_text == display


# Convention "W1, W2, W3 = three workspaces"
@pytest.fixture
def w1(db):
    return make_workspace(db)


@pytest.fixture
def w2(db):
    return make_workspace(db)


@pytest.fixture
def w3(db):
    return make_workspace(db)


def email(local, domain="x.com"):
    """Convention "Profile emails must be unique": unique suffix on the local
    part so parallel tests never clash; expectations use the stored value."""
    return f"{local}+{uuid.uuid4().hex[:10]}@{domain}"


def prof(db, name, mail):
    """A profile with exactly this name and email (mail used as given)."""
    return make_profile(db, name=name, email=mail)


# Convention "P7" / "P9"
@pytest.fixture
def p7(db):
    return prof(db, "Rahim", email("rahim"))


@pytest.fixture
def p9(db):
    return prof(db, "Karim", email("karim"))


# Convention "Active / suspended / invited member of W"
def member(db, ws, profile, status="active"):
    row = WorkspaceMember(
        workspace_id=ws.id, user_id=profile.id, role="ground-team", status=status
    )
    db.add(row)
    db.flush()
    return row


# Convention "MISSING" = highest existing profile id + 1000
def missing_profile_id(db):
    return (db.execute(select(func.max(Profile.id))).scalar() or 0) + 1000


def missing_workspace_id(db):
    return (db.execute(select(func.max(Workspace.id))).scalar() or 0) + 1000


# Convention "Session clean"
def assert_session_clean(db):
    assert not db.new
    assert not db.dirty
    assert not db.deleted


def as_set(lookups):
    return {(m.user_id, m.name, m.email) for m in lookups}


def member_count(db, ws):
    db.expire_all()
    return db.execute(
        select(func.count()).select_from(WorkspaceMember).where(WorkspaceMember.workspace_id == ws.id)
    ).scalar()


# =========================================================================== #
# parse_worker_names
# =========================================================================== #

@pytest.mark.parametrize(
    "text",
    [
        pytest.param(None, id="WOW-P-01"),
        pytest.param("", id="WOW-P-02"),
        pytest.param("  \t\n ", id="WOW-P-03"),
    ],
)
def test_wow_p_01_03__none_empty_blank_give_empty_list(text):
    """WOW-P-01..03 — None, "" and whitespace-only text return [].
    Rules: parse_worker_names R1."""
    assert parse_worker_names(text) == []


def test_wow_p_04__split_on_comma_and_semicolon():
    """WOW-P-04 — commas and semicolons separate names.
    Rules: parse_worker_names R2."""
    assert parse_worker_names("Rahim,Karim;Babu") == ["Rahim", "Karim", "Babu"]


def test_wow_p_05__separator_run_is_one_split():
    """WOW-P-05 — a run of separators counts as one split.
    Rules: parse_worker_names R2."""
    assert parse_worker_names("Rahim,;,Karim;;Babu") == ["Rahim", "Karim", "Babu"]


def test_wow_p_06__other_characters_do_not_split():
    """WOW-P-06 — newline, "and", "&", "/" stay inside a name.
    Rules: parse_worker_names R2."""
    assert parse_worker_names("Rahim\nKarim") == ["Rahim\nKarim"]
    assert parse_worker_names("Rahim and Karim") == ["Rahim and Karim"]
    assert parse_worker_names("Rahim & Karim") == ["Rahim & Karim"]
    assert parse_worker_names("Rahim/Karim") == ["Rahim/Karim"]


def test_wow_p_07__outer_trim_inner_space_and_case_kept():
    """WOW-P-07 — outer spaces removed, inner double space and case kept.
    Rules: parse_worker_names R3."""
    assert parse_worker_names("  Abdul  Karim ,  rAHIM ") == ["Abdul  Karim", "rAHIM"]


def test_wow_p_08__empty_pieces_dropped():
    """WOW-P-08 — empty / whitespace-only pieces are dropped.
    Rules: parse_worker_names R4."""
    assert parse_worker_names(",Rahim,, ;Karim,") == ["Rahim", "Karim"]


def test_wow_p_09__only_separators_and_blanks():
    """WOW-P-09 — only separators and blanks give [].
    Rules: parse_worker_names R4."""
    assert parse_worker_names(",;, ; ") == []


def test_wow_p_10__single_name_no_separator():
    """WOW-P-10 — no separator gives one name.
    Rules: parse_worker_names R2, R4."""
    assert parse_worker_names("Rahim") == ["Rahim"]


def test_wow_p_11__duplicates_kept_in_order():
    """WOW-P-11 — duplicates are kept and order preserved.
    Rules: parse_worker_names R5."""
    assert parse_worker_names("A, A") == ["A", "A"]
    assert parse_worker_names("B, A, B") == ["B", "A", "B"]


# =========================================================================== #
# join_worker_names
# =========================================================================== #

def test_wow_j_01__trim_and_join_with_comma_space():
    """WOW-J-01 — names trimmed and joined with ", ".
    Rules: join_worker_names R1."""
    assert join_worker_names(["Rahim", " Karim "]) == "Rahim, Karim"


def test_wow_j_02__single_name_no_separator():
    """WOW-J-02 — one name gives no separator; inner spaces kept.
    Rules: join_worker_names R1."""
    assert join_worker_names(["Rahim"]) == "Rahim"
    assert join_worker_names(["Abdul  Karim"]) == "Abdul  Karim"


def test_wow_j_03__none_and_blank_entries_skipped():
    """WOW-J-03 — None / "" / whitespace entries skipped, no doubled separator.
    Rules: join_worker_names R2."""
    assert join_worker_names([None, "Rahim", "", "  ", "Karim", None]) == "Rahim, Karim"


def test_wow_j_04__empty_sequence():
    """WOW-J-04 — empty sequence gives "".
    Rules: join_worker_names R3."""
    assert join_worker_names([]) == ""


def test_wow_j_05__only_skipped_entries():
    """WOW-J-05 — only skipped entries give "".
    Rules: join_worker_names R3."""
    assert join_worker_names([None, "", " \t"]) == ""


def test_wow_j_06__duplicates_kept():
    """WOW-J-06 — duplicates are kept.
    Rules: join_worker_names R4."""
    assert join_worker_names(["A", "A"]) == "A, A"


def test_wow_j_07__no_escaping_of_commas():
    """WOW-J-07 — a name containing a comma is joined as-is.
    Rules: join_worker_names R5."""
    assert join_worker_names(["Rahim, Karim", "Babu"]) == "Rahim, Karim, Babu"


# =========================================================================== #
# resolve_names_to_members
# =========================================================================== #

def test_wow_r_01__name_match_case_insensitive():
    """WOW-R-01 — "rahim" matches member "Rahim", stored name shown.
    Rules: resolve_names_to_members R4, R6, R8."""
    assert_res(resolve_names_to_members(["rahim"], [M7, M9]), [7], [], "Rahim")


def test_wow_r_02__email_match_shows_member_name():
    """WOW-R-02 — email match (case/space-insensitive) shows the member's name.
    Rules: resolve_names_to_members R4, R8."""
    assert_res(resolve_names_to_members(["RAHIM@X.COM "], [M7, M9]), [7], [], "Rahim")


def test_wow_r_03__blank_names_skipped_completely():
    """WOW-R-03 — blank names are skipped; unknown kept as unmatched.
    Rules: resolve_names_to_members R1, R7, R9."""
    res = resolve_names_to_members(["Rahim", "", "   ", "Unknown"], [M7])
    assert_res(res, [7], ["Unknown"], "Rahim, Unknown")


def test_wow_r_04__empty_names():
    """WOW-R-04 — empty names give an empty resolution.
    Rules: resolve_names_to_members R2."""
    assert_res(resolve_names_to_members([], [M7]), [], [], "")


def test_wow_r_05__only_blank_names():
    """WOW-R-05 — only blank names give an empty resolution.
    Rules: resolve_names_to_members R1, R2."""
    assert_res(resolve_names_to_members(["", "  "], [M7]), [], [], "")


def test_wow_r_06__empty_members_all_unmatched():
    """WOW-R-06 — no members: every non-blank name is unmatched.
    Rules: resolve_names_to_members R3."""
    res = resolve_names_to_members(["Rahim", "Karim"], [])
    assert_res(res, [], ["Rahim", "Karim"], "Rahim, Karim")


def test_wow_r_07__unicode_casefold_match():
    """WOW-R-07 — "STRASSE" matches "straße" via casefold; "STRASSEX" does not.
    Rules: resolve_names_to_members R4, R8."""
    members = [MemberLookup(21, "straße", "s@x.com")]
    assert_res(resolve_names_to_members(["STRASSE"], members), [21], [], "straße")
    assert_res(resolve_names_to_members(["STRASSEX"], members), [], ["STRASSEX"], "STRASSEX")


def test_wow_r_08__member_side_trimmed():
    """WOW-R-08 — member name/email trimmed for matching and display.
    Rules: resolve_names_to_members R4, R8."""
    members = [MemberLookup(22, " Rahim ", "  rahim@x.com ")]
    assert_res(resolve_names_to_members(["rahim"], members), [22], [], "Rahim")
    assert_res(resolve_names_to_members(["rahim@x.com"], members), [22], [], "Rahim")


def test_wow_r_09__inner_whitespace_must_match_exactly():
    """WOW-R-09 — inner whitespace must match exactly.
    Rules: resolve_names_to_members R4."""
    members = [MemberLookup(23, "Abdul Karim", "ak@x.com")]
    assert_res(
        resolve_names_to_members(["Abdul  Karim"], members), [], ["Abdul  Karim"], "Abdul  Karim"
    )
    assert_res(resolve_names_to_members(["abdul karim"], members), [23], [], "Abdul Karim")


def test_wow_r_10__no_partial_match():
    """WOW-R-10 — no partial / prefix / suffix matching.
    Rules: resolve_names_to_members R4."""
    names = ["Rah", "Rahim Uddin", "rahim@x", "x.com"]
    res = resolve_names_to_members(names, [M7])
    assert_res(res, [], names, "Rah, Rahim Uddin, rahim@x, x.com")


def test_wow_r_11__member_without_name_email_never_matches():
    """WOW-R-11 — members with None / blank name and email never match.
    Rules: resolve_names_to_members R4."""
    members = [MemberLookup(24, None, None), MemberLookup(25, "", "  ")]
    res = resolve_names_to_members(["None", "x"], members)
    assert_res(res, [], ["None", "x"], "None, x")


def test_wow_r_12__name_none_shows_trimmed_email():
    """WOW-R-12 — name None: trimmed email (stored case) shown.
    Rules: resolve_names_to_members R4, R8."""
    members = [MemberLookup(26, None, " N@x.com ")]
    assert_res(resolve_names_to_members(["n@x.com"], members), [26], [], "N@x.com")


def test_wow_r_13__name_empty_shows_email():
    """WOW-R-13 — name "": email shown.
    Rules: resolve_names_to_members R8."""
    members = [MemberLookup(27, "", "e@x.com")]
    assert_res(resolve_names_to_members(["E@X.COM"], members), [27], [], "e@x.com")


def test_wow_r_14__typed_order_not_member_order():
    """WOW-R-14 — ids and display follow typed order.
    Rules: resolve_names_to_members R6, R9."""
    res = resolve_names_to_members(["Karim", "Rahim"], [M7, M9])
    assert_res(res, [9, 7], [], "Karim, Rahim")


def test_wow_r_15__id_listed_once():
    """WOW-R-15 — a member reached 3 times (name and email) is listed once.
    Rules: resolve_names_to_members R6."""
    res = resolve_names_to_members(["Rahim", "rahim@x.com", "rahim"], [M7])
    assert res.matched_user_ids == [7]
    assert res.unmatched_names == []


def test_wow_r_16__unmatched_trimmed_input_order():
    """WOW-R-16 — unmatched names trimmed, inner spaces/case kept, input order.
    Rules: resolve_names_to_members R7, R9."""
    res = resolve_names_to_members(["  Zed  Khan ", "Rahim", "unknown"], [M7])
    assert_res(res, [7], ["Zed  Khan", "unknown"], "Zed  Khan, Rahim, unknown")


def test_wow_r_17__two_members_same_name_each_keep_entry():
    """WOW-R-17 — two different members with equal stored names each keep an entry.
    Rules: resolve_names_to_members R9a, R6."""
    members = [M7, MemberLookup(12, "Rahim", "rahim12@x.com")]
    res = resolve_names_to_members(["rahim@x.com", "rahim12@x.com"], members)
    assert_res(res, [7, 12], [], "Rahim, Rahim")


def test_wow_r_18__same_member_twice_not_ambiguous():
    """WOW-R-18 — the same user_id listed twice is not ambiguous.
    Rules: resolve_names_to_members R5."""
    assert_res(resolve_names_to_members(["rahim"], [M7, M7]), [7], [], "Rahim")


def test_wow_r_19__generator_input():
    """WOW-R-19 — names may be a one-shot generator.
    Rules: resolve_names_to_members R6, R7, R9 (Inputs: iterated once)."""
    gen = (n for n in ["Rahim", "Unknown"])
    assert_res(resolve_names_to_members(gen, [M7]), [7], ["Unknown"], "Rahim, Unknown")


def test_wow_r_20__none_element_raises_attribute_error():
    """WOW-R-20 — a None element raises AttributeError.
    Rules: resolve_names_to_members Errors row 1."""
    with pytest.raises(AttributeError):
        resolve_names_to_members(["Rahim", None], [M7])


@pytest.mark.xfail(strict=True, reason=BUG_380)
def test_wow_r_21__ambiguous_name_unmatched():
    """WOW-R-21 — a name matching two distinct members is unmatched.
    Rules: resolve_names_to_members R5 [BUG-380]."""
    assert_res(resolve_names_to_members(["Rahim"], [M7, M12]), [], ["Rahim"], "Rahim")


@pytest.mark.xfail(strict=True, reason=BUG_380)
def test_wow_r_22__ambiguous_name_unmatched_reverse_order():
    """WOW-R-22 — same as R-21 with members reversed; result independent of order.
    Rules: resolve_names_to_members R5 [BUG-380]."""
    assert_res(resolve_names_to_members(["Rahim"], [M12, M7]), [], ["Rahim"], "Rahim")


@pytest.mark.xfail(strict=True, reason=BUG_380)
def test_wow_r_23__name_equals_other_members_email_ambiguous():
    """WOW-R-23 — one member's name equal to another's email is ambiguous.
    Rules: resolve_names_to_members R5 [BUG-380]."""
    members = [M7, MemberLookup(30, "rahim@x.com", "boss@x.com")]
    res = resolve_names_to_members(["rahim@x.com"], members)
    assert_res(res, [], ["rahim@x.com"], "rahim@x.com")


@pytest.mark.xfail(strict=True, reason=BUG_380)
def test_wow_r_24__ambiguous_does_not_block_others():
    """WOW-R-24 — an ambiguous name does not stop other names resolving.
    Rules: resolve_names_to_members R5 [BUG-380], R6."""
    res = resolve_names_to_members(["Rahim", "Karim"], [M7, M12, M9])
    assert_res(res, [9], ["Rahim"], "Rahim, Karim")


@pytest.mark.xfail(strict=True, reason=BUG_381)
def test_wow_r_25__repeated_unmatched_listed_once():
    """WOW-R-25 — repeated unmatched names (trim + casefold) listed once.
    Rules: resolve_names_to_members R7a [BUG-381]."""
    res = resolve_names_to_members(["Unknown", "unknown ", "UNKNOWN"], [M7])
    assert_res(res, [], ["Unknown"], "Unknown")


@pytest.mark.xfail(strict=True, reason=BUG_381)
def test_wow_r_26__unmatched_dedup_uses_casefold():
    """WOW-R-26 — unmatched dedup uses casefold ("STRASSE" == "straße").
    Rules: resolve_names_to_members R7a [BUG-381]."""
    res = resolve_names_to_members(["STRASSE", "straße"], [])
    assert_res(res, [], ["STRASSE"], "STRASSE")


@pytest.mark.xfail(strict=True, reason=BUG_381)
def test_wow_r_27__member_displayed_once():
    """WOW-R-27 — a member typed three ways is displayed once.
    Rules: resolve_names_to_members R9a [BUG-381]."""
    res = resolve_names_to_members(["Rahim", "rahim@x.com", "rahim"], [M7])
    assert_res(res, [7], [], "Rahim")


@pytest.mark.xfail(strict=True, reason=BUG_381)
def test_wow_r_28__member_displayed_once_at_first_position():
    """WOW-R-28 — repeated member displayed once at its first position.
    Rules: resolve_names_to_members R9a [BUG-381]."""
    res = resolve_names_to_members(["Rahim", "Unknown", "rahim"], [M7])
    assert_res(res, [7], ["Unknown"], "Rahim, Unknown")


def test_wow_r_29__ids_and_unmatched_with_repeated_member():
    """WOW-R-29 — ids and unmatched for R-28's setup (display not asserted).
    Rules: resolve_names_to_members R6, R7."""
    res = resolve_names_to_members(["Rahim", "Unknown", "rahim"], [M7])
    assert res.matched_user_ids == [7]
    assert res.unmatched_names == ["Unknown"]


@pytest.mark.xfail(strict=True, reason=BUG_382)
def test_wow_r_30__whitespace_name_falls_back_to_email():
    """WOW-R-30 — whitespace-only member name displays the member's email.
    Rules: resolve_names_to_members R8a [BUG-382]."""
    res = resolve_names_to_members(["W@X.COM", "Rahim"], [M31, M7])
    assert_res(res, [31, 7], [], "w@x.com, Rahim")


def test_wow_r_31__whitespace_name_member_credited_via_email():
    """WOW-R-31 — the whitespace-name member is credited via email (display not asserted).
    Rules: resolve_names_to_members R4, R6, R8a."""
    res = resolve_names_to_members(["W@X.COM", "Rahim"], [M31, M7])
    assert res.matched_user_ids == [31, 7]
    assert res.unmatched_names == []


@pytest.mark.xfail(strict=True, reason=BUG_382)
def test_wow_r_32__tab_space_name_falls_back_to_trimmed_email():
    """WOW-R-32 — tab/space-only name: trimmed email in stored case displayed.
    Rules: resolve_names_to_members R8a [BUG-382]."""
    members = [MemberLookup(32, " \t ", " W2@x.com ")]
    assert_res(resolve_names_to_members(["w2@x.com"], members), [32], [], "W2@x.com")


@pytest.mark.xfail(strict=True, reason=BUG_381)
def test_wow_r_33__repeated_unmatched_kept_at_first_position():
    """WOW-R-33 — repeated unmatched name kept once, first typed form, at its first position.
    Rules: resolve_names_to_members R7a, R9a [BUG-381]."""
    res = resolve_names_to_members(["Zed", "Rahim", " zed "], [M7])
    assert_res(res, [7], ["Zed"], "Zed, Rahim")


# =========================================================================== #
# resolve_worker_text_to_members
# =========================================================================== #

def test_wow_t_01__parse_then_resolve():
    """WOW-T-01 — text is split then resolved.
    Rules: resolve_worker_text_to_members R1."""
    res = resolve_worker_text_to_members("rahim; Unknown,", [M7])
    assert_res(res, [7], ["Unknown"], "Rahim, Unknown")


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(None, id="WOW-T-02"),
        pytest.param("", id="WOW-T-03"),
        pytest.param("  ;, ,; ", id="WOW-T-04"),
    ],
)
def test_wow_t_02_04__blank_text_empty_resolution(text):
    """WOW-T-02..04 — None / "" / separators-and-blanks give an empty resolution.
    Rules: resolve_worker_text_to_members R2."""
    assert_res(resolve_worker_text_to_members(text, [M7]), [], [], "")


def test_wow_t_05__newline_does_not_split():
    """WOW-T-05 — a newline does not split; the whole text is one unmatched name.
    Rules: resolve_worker_text_to_members R1."""
    res = resolve_worker_text_to_members("Rahim\nKarim", [M7, M9])
    assert_res(res, [], ["Rahim\nKarim"], "Rahim\nKarim")


def test_wow_t_06__mixed_separators():
    """WOW-T-06 — mixed separators, matched and unmatched in typed order.
    Rules: resolve_worker_text_to_members R1."""
    res = resolve_worker_text_to_members("Karim;;Rahim , Zed", [M7, M9])
    assert_res(res, [9, 7], ["Zed"], "Karim, Rahim, Zed")


# =========================================================================== #
# load_active_member_lookups
# =========================================================================== #

def test_wow_l_01__active_members_with_profile_data(db, w1, p7, p9):
    """WOW-L-01 — active members returned with profile name/email; read-only.
    Rules: load_active_member_lookups R1, R3, R4."""
    member(db, w1, p7)
    member(db, w1, p9)
    before = member_count(db, w1)
    result = load_active_member_lookups(db, w1.id)
    assert isinstance(result, list)
    assert len(result) == 2
    assert all(isinstance(m, MemberLookup) for m in result)
    assert as_set(result) == {(p7.id, "Rahim", p7.email), (p9.id, "Karim", p9.email)}
    assert_session_clean(db)
    assert member_count(db, w1) == before


def test_wow_l_02__suspended_and_invited_excluded(db, w1, p7):
    """WOW-L-02 — suspended and invited members are excluded.
    Rules: load_active_member_lookups R1."""
    p8 = prof(db, "Sami", email("sami"))
    p10 = prof(db, "Tania", email("tania"))
    member(db, w1, p7)
    member(db, w1, p8, status="suspended")
    member(db, w1, p10, status="invited")
    result = load_active_member_lookups(db, w1.id)
    assert len(result) == 1
    assert as_set(result) == {(p7.id, "Rahim", p7.email)}


def test_wow_l_03__workspace_isolation(db, w1, w2, p7):
    """WOW-L-03 — only memberships of the given workspace are returned.
    Rules: load_active_member_lookups R1."""
    p11 = prof(db, "Nabil", email("nabil"))
    member(db, w1, p7)
    member(db, w2, p7)
    member(db, w2, p11)
    r1 = load_active_member_lookups(db, w1.id)
    assert len(r1) == 1
    assert as_set(r1) == {(p7.id, "Rahim", p7.email)}
    r2 = load_active_member_lookups(db, w2.id)
    assert as_set(r2) == {(p7.id, "Rahim", p7.email), (p11.id, "Nabil", p11.email)}


def test_wow_l_04__no_cap_101_members(db, w1):
    """WOW-L-04 — all 101 active members returned, no pagination.
    Rules: load_active_member_lookups R2, R3."""
    profiles = [prof(db, f"Worker {i:03d}", email(f"worker{i:03d}")) for i in range(1, 102)]
    for p in profiles:
        member(db, w1, p)
    result = load_active_member_lookups(db, w1.id)
    assert len(result) == 101
    assert {m.user_id for m in result} == {p.id for p in profiles}


def test_wow_l_05__no_active_members(db, w3):
    """WOW-L-05 — a workspace with only suspended/invited members gives [].
    Rules: load_active_member_lookups R6."""
    p8 = prof(db, "Sami", email("sami"))
    p10 = prof(db, "Tania", email("tania"))
    member(db, w3, p8, status="suspended")
    member(db, w3, p10, status="invited")
    assert load_active_member_lookups(db, w3.id) == []


def test_wow_l_06__unknown_workspace_id(db, w1, p7):
    """WOW-L-06 — a workspace id with no row gives [], no error.
    Rules: load_active_member_lookups R6."""
    member(db, w1, p7)
    assert load_active_member_lookups(db, missing_workspace_id(db)) == []


def test_wow_l_07__raw_stored_values(db, w1):
    """WOW-L-07 — name and email returned raw (not trimmed, not lower-cased).
    Rules: load_active_member_lookups R4."""
    stored_email = email("BABU")
    p13 = prof(db, "  Babu ", stored_email)
    member(db, w1, p13)
    result = load_active_member_lookups(db, w1.id)
    assert len(result) == 1
    assert result[0].name == "  Babu "
    assert result[0].email == stored_email


# =========================================================================== #
# display_names_for_user_ids
# =========================================================================== #

def test_wow_d_01__profile_name(db, p7):
    """WOW-D-01 — label is the profile name; read-only.
    Rules: display_names_for_user_ids R1."""
    assert display_names_for_user_ids(db, [p7.id]) == "Rahim"
    assert_session_clean(db)


def test_wow_d_02__empty_name_uses_email(db):
    """WOW-D-02 — empty name: label is the email.
    Rules: display_names_for_user_ids R2."""
    p14 = prof(db, "", email("e"))
    assert display_names_for_user_ids(db, [p14.id]) == p14.email


def test_wow_d_03__missing_profile_id_label(db):
    """WOW-D-03 — no profile: label "User #<id>".
    Rules: display_names_for_user_ids R3."""
    missing = missing_profile_id(db)
    assert display_names_for_user_ids(db, [missing]) == f"User #{missing}"


def test_wow_d_04__empty_name_and_email_id_label(db):
    """WOW-D-04 — empty name and empty email: label "User #<id>".
    Rules: display_names_for_user_ids R3."""
    p15 = prof(db, "", "")
    assert display_names_for_user_ids(db, [p15.id]) == f"User #{p15.id}"


def test_wow_d_05__mixed_input_order(db, p7, p9):
    """WOW-D-05 — labels keep input order, missing ids get "User #<id>".
    Rules: display_names_for_user_ids R1, R3, R4."""
    missing = missing_profile_id(db)
    assert (
        display_names_for_user_ids(db, [p9.id, missing, p7.id])
        == f"Karim, User #{missing}, Rahim"
    )


def test_wow_d_06__empty_ids(db):
    """WOW-D-06 — empty ids give "".
    Rules: display_names_for_user_ids R4."""
    assert display_names_for_user_ids(db, []) == ""


def test_wow_d_07__no_workspace_scoping(db, w2):
    """WOW-D-07 — no workspace or status check.
    Rules: display_names_for_user_ids R6."""
    p20 = prof(db, "Nomad", email("nomad"))
    p21 = prof(db, "Sam", email("sam"))
    member(db, w2, p21, status="suspended")
    assert display_names_for_user_ids(db, [p20.id, p21.id]) == "Nomad, Sam"


@pytest.mark.xfail(strict=True, reason=BUG_382)
def test_wow_d_08__whitespace_name_falls_back_to_email(db, p7, p9):
    """WOW-D-08 — whitespace-only name: label is the email.
    Rules: display_names_for_user_ids R7 [BUG-382]."""
    p22 = prof(db, "   ", email("ws"))
    assert display_names_for_user_ids(db, [p22.id]) == p22.email
    assert display_names_for_user_ids(db, [p7.id, p22.id, p9.id]) == f"Rahim, {p22.email}, Karim"
    assert_session_clean(db)


def test_wow_d_09__label_trimmed_by_join(db):
    """WOW-D-09 — the label is trimmed by the join.
    Rules: display_names_for_user_ids R1, R4."""
    p23 = prof(db, " Babu ", email("babu"))
    assert display_names_for_user_ids(db, [p23.id]) == "Babu"


@pytest.mark.xfail(strict=True, reason=BUG_381)
def test_wow_d_10__repeated_id_one_label(db, p7, p9):
    """WOW-D-10 — a repeated id produces one label at its first position.
    Rules: display_names_for_user_ids R5 [BUG-381]."""
    assert display_names_for_user_ids(db, [p7.id, p9.id, p7.id]) == "Rahim, Karim"


@pytest.mark.xfail(strict=True, reason=BUG_381)
def test_wow_d_11__repeated_missing_id_one_label(db):
    """WOW-D-11 — a repeated missing id produces one label.
    Rules: display_names_for_user_ids R5 [BUG-381]."""
    missing = missing_profile_id(db)
    assert display_names_for_user_ids(db, [missing, missing]) == f"User #{missing}"


@pytest.mark.xfail(strict=True, reason=BUG_382)
def test_wow_d_12__empty_name_whitespace_email_id_label(db):
    """WOW-D-12 — empty name and whitespace-only email: label "User #<id>".
    Rules: display_names_for_user_ids R7 [BUG-382], R3."""
    p24 = prof(db, "", "   ")
    assert display_names_for_user_ids(db, [p24.id]) == f"User #{p24.id}"


@pytest.mark.xfail(strict=True, reason=BUG_382)
def test_wow_d_13__whitespace_name_and_email_id_label(db, p7):
    """WOW-D-13 — tab/space name and email: label "User #<id>".
    Rules: display_names_for_user_ids R7 [BUG-382], R3."""
    p25 = prof(db, " \t ", "\t ")
    assert display_names_for_user_ids(db, [p25.id, p7.id]) == f"User #{p25.id}, Rahim"
