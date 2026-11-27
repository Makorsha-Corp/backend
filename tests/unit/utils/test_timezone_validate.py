"""Unit tests for app/utils/timezone_validate.py — implements tests/unit/utils/timezone_validate.cases.md."""
import sys
import zoneinfo

import pytest

from app.utils.timezone_validate import is_valid_iana_timezone

# Convention: no database, no fixtures, no mocks — pure function called directly.

# Convention "BUG-300 marker": strict expected-failure on Windows only; ordinary pass on Linux.
BUG_300 = pytest.mark.xfail(
    condition=sys.platform == "win32",
    strict=True,
    reason="BUG-300: Timezone validity depends on the host OS",
)

# Convention "Excluded names": never use posix/... or right/... prefixed names.
_EXCLUDED_PREFIXES = ("posix/", "right/")


def _canonical_names():
    """Host's available_timezones() minus posix/ and right/ prefixed names."""
    return {n for n in zoneinfo.available_timezones() if not n.startswith(_EXCLUDED_PREFIXES)}


def _assert_loadable_canonical(value):
    """Positive-case invariant: in the canonical set and loadable with ZoneInfo."""
    assert value in zoneinfo.available_timezones()
    zoneinfo.ZoneInfo(value)  # must load without error


def test_tzv_v_01__empty_string_is_false():
    """TZV-V-01 — "" returns False, no exception.
    Rules: is_valid_iana_timezone R1."""
    assert is_valid_iana_timezone("") is False


def test_tzv_v_02__none_is_false():
    """TZV-V-02 — None returns False, no TypeError.
    Rules: is_valid_iana_timezone R1."""
    assert is_valid_iana_timezone(None) is False


def test_tzv_v_03__65_chars_is_false():
    """TZV-V-03 — a 65-character string returns False, no exception.
    Rules: is_valid_iana_timezone R2."""
    assert is_valid_iana_timezone("A" * 65) is False


def test_tzv_v_04__64_chars_is_false_by_lookup():
    """TZV-V-04 — exactly 64 characters returns False (rejected by lookup), no exception.
    Rules: is_valid_iana_timezone R2."""
    assert is_valid_iana_timezone("A" * 64) is False


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("Asia/Dhaka", id="TZV-V-05-Asia/Dhaka"),
        pytest.param("UTC", id="TZV-V-05-UTC"),
        pytest.param("America/New_York", id="TZV-V-05-America/New_York"),
        pytest.param("Etc/GMT+6", id="TZV-V-05-Etc/GMT+6"),
        pytest.param("GMT", id="TZV-V-05-GMT"),
    ],
)
def test_tzv_v_05__canonical_names_are_true(value):
    """TZV-V-05 — canonical IANA names return True, are in available_timezones() and load.
    Rules: is_valid_iana_timezone R3."""
    assert is_valid_iana_timezone(value) is True
    _assert_loadable_canonical(value)


def test_tzv_v_06__every_available_name_is_true():
    """TZV-V-06 — every host canonical name (minus posix/, right/) returns True.
    Rules: is_valid_iana_timezone R3."""
    names = _canonical_names()
    rejected = sorted(n for n in names if is_valid_iana_timezone(n) is not True)
    assert rejected == []
    assert len(names) >= 400


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("Asia/Calcutta", id="TZV-V-07-Asia/Calcutta"),
        pytest.param("US/Eastern", id="TZV-V-07-US/Eastern"),
        pytest.param("EST", id="TZV-V-07-EST"),
        pytest.param("EST5EDT", id="TZV-V-07-EST5EDT"),
        pytest.param("Factory", id="TZV-V-07-Factory"),
    ],
)
def test_tzv_v_07__legacy_alias_names_are_true(value):
    """TZV-V-07 — legacy/alias names in the canonical set return True and load.
    Rules: is_valid_iana_timezone R4."""
    assert is_valid_iana_timezone(value) is True
    _assert_loadable_canonical(value)


def test_tzv_v_08__unknown_name_is_false():
    """TZV-V-08 — unknown name "Nowhere/City" returns False, no exception.
    Rules: is_valid_iana_timezone R5."""
    assert is_valid_iana_timezone("Nowhere/City") is False


@pytest.mark.parametrize(
    "value",
    [pytest.param("Asia", id="TZV-V-09-Asia"), pytest.param("Asia/", id="TZV-V-09-Asia/")],
)
def test_tzv_v_09__region_folder_is_false(value):
    """TZV-V-09 — a region folder returns False, no exception.
    Rules: is_valid_iana_timezone R5."""
    assert is_valid_iana_timezone(value) is False


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("../etc", id="TZV-V-10-dotdot-etc"),
        pytest.param("/etc/UTC", id="TZV-V-10-abs-etc-UTC"),
        pytest.param("Asia/../UTC", id="TZV-V-10-Asia-dotdot-UTC"),
        pytest.param("Asia/./Dhaka", id="TZV-V-10-Asia-dot-Dhaka"),
    ],
)
def test_tzv_v_10__path_like_is_false(value):
    """TZV-V-10 — path-like input returns False, no exception.
    Rules: is_valid_iana_timezone R5."""
    assert is_valid_iana_timezone(value) is False


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("Asia/Dhaka\x00", id="TZV-V-11-trailing-NUL"),
        pytest.param("Asia/Dh\x00aka", id="TZV-V-11-inner-NUL"),
    ],
)
def test_tzv_v_11__nul_character_is_false(value):
    """TZV-V-11 — a name containing NUL returns False, no ValueError.
    Rules: is_valid_iana_timezone R5."""
    assert is_valid_iana_timezone(value) is False


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("zone.tab", id="TZV-V-12-zone.tab"),
        pytest.param("tzdata.zi", id="TZV-V-12-tzdata.zi"),
        pytest.param("leapseconds", id="TZV-V-12-leapseconds"),
    ],
)
def test_tzv_v_12__metadata_files_are_false(value):
    """TZV-V-12 — timezone database metadata files return False, no exception.
    Rules: is_valid_iana_timezone R5."""
    assert is_valid_iana_timezone(value) is False


def _system_tzdb_loads(name: str) -> bool:
    """True where the OS timezone files include `name` (Linux /usr/share/zoneinfo does;
    Windows has no system database and uses the `tzdata` package, which does not)."""
    try:
        zoneinfo.ZoneInfo(name)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError, OSError):
        return False
    return True


# BUG-3301: on Linux (production, CI) ZoneInfo loads these OS files, so they are accepted.
X3301 = "BUG-3301: 'localtime' and 'posixrules' are accepted as timezones on Linux"


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("localtime", id="TZV-V-13-localtime",
                     marks=pytest.mark.xfail(_system_tzdb_loads("localtime"), strict=True, reason=X3301)),
        pytest.param("posixrules", id="TZV-V-13-posixrules",
                     marks=pytest.mark.xfail(_system_tzdb_loads("posixrules"), strict=True, reason=X3301)),
    ],
)
def test_tzv_v_13__localtime_posixrules_are_false(value):
    """TZV-V-13 — "localtime" and "posixrules" return False, no exception.
    Rules: is_valid_iana_timezone R5."""
    assert is_valid_iana_timezone(value) is False


def test_tzv_v_14__offset_is_false():
    """TZV-V-14 — an offset "+06:00" returns False, no exception.
    Rules: is_valid_iana_timezone R5."""
    assert is_valid_iana_timezone("+06:00") is False


def test_tzv_v_15__leading_space_is_false():
    """TZV-V-15 — " Asia/Dhaka" (leading space) returns False, no exception.
    Rules: is_valid_iana_timezone R5."""
    assert is_valid_iana_timezone(" Asia/Dhaka") is False


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("asia/dhaka", id="TZV-V-16-lower"),
        pytest.param("ASIA/DHAKA", id="TZV-V-16-upper"),
    ],
)
def test_tzv_v_16__wrong_case_region_is_false(value):
    """TZV-V-16 — wrong-case region names return False on every platform, no exception.
    Rules: is_valid_iana_timezone R5, R6."""
    assert is_valid_iana_timezone(value) is False


@BUG_300
def test_tzv_v_17__lowercase_utc_is_false():
    """TZV-V-17 — "utc" (lowercase) returns False.
    Rules: is_valid_iana_timezone R6 [BUG-300]."""
    assert is_valid_iana_timezone("utc") is False


@BUG_300
def test_tzv_v_18__backslash_separator_is_false():
    """TZV-V-18 — "Asia\\Dhaka" (backslash separator) returns False.
    Rules: is_valid_iana_timezone R6 [BUG-300]."""
    assert is_valid_iana_timezone("Asia\\Dhaka") is False


@BUG_300
def test_tzv_v_19__trailing_space_is_false():
    """TZV-V-19 — "Asia/Dhaka " (trailing space) returns False.
    Rules: is_valid_iana_timezone R6 [BUG-300]."""
    assert is_valid_iana_timezone("Asia/Dhaka ") is False


def test_tzv_v_20__int_raises_type_error():
    """TZV-V-20 — the integer 123 raises TypeError from the length check.
    Rules: is_valid_iana_timezone R7; Errors row 1."""
    with pytest.raises(TypeError) as exc:
        is_valid_iana_timezone(123)
    assert str(exc.value) == "object of type 'int' has no len()"


def test_tzv_v_21__padded_real_name_65_chars_is_false():
    """TZV-V-21 — "UTC" padded with trailing spaces to 65 characters returns False, no exception.
    Rules: is_valid_iana_timezone R2."""
    value = "UTC" + " " * 62
    assert len(value) == 65
    assert is_valid_iana_timezone(value) is False


@BUG_300
def test_tzv_v_22__padded_real_name_64_chars_is_false():
    """TZV-V-22 — "UTC" padded with trailing spaces to exactly 64 characters returns False.
    Rules: is_valid_iana_timezone R2, R6 [BUG-300]."""
    value = "UTC" + " " * 61
    assert len(value) == 64
    assert is_valid_iana_timezone(value) is False
