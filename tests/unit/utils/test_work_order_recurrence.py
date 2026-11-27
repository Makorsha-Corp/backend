"""Unit tests for app/utils/work_order_recurrence.py — implements
tests/unit/utils/work_order_recurrence.cases.md (revision 5).

The module is pure: no database, no mocks (Conventions "No database, no mocks").
"""
from datetime import date
from types import SimpleNamespace

import pydantic
import pytest

from app.schemas.work_order_template import (
    WorkOrderTemplateCreate,
    WorkOrderTemplateUpdate,
)
from app.utils.work_order_recurrence import (
    _apply_recurrence_range,
    advance_next_generation_date,
    is_recurrence_program_active,
    reseed_recurrence_program,
    seed_recurrence_from_planned_date,
    should_advance_template,
    validate_recurrence_span,
)

# Convention "Error messages": exact texts.
E_BACK = "Recurrence end date must be on or after the start date"
E_SPAN = "Recurrence range cannot exceed 183 days (~6 months)"

BUG_360 = "BUG-360: Any text accepted as work order template recurrence_type"
BUG_361 = (
    "BUG-361: Recurring template allowed without a recurrence type; "
    "backend runs it daily, UI previews weekly"
)
BUG_362 = "BUG-362: Out-of-range recurrence_day silently wrapped (weekly) or clamped (monthly)"

# Convention "prior state P": defaults for any attribute a case does not list.
_PRIOR = dict(
    is_recurring=True,
    recurrence_day=4,
    recurrence_start_date=date(2025, 1, 1),
    recurrence_end_date=date(2025, 2, 1),
    next_generation_date=date(2025, 1, 15),
)


def T(recurrence_type, **overrides):
    """Convention "Template stand-in T(...)": SimpleNamespace with the six attributes, prior state P."""
    attrs = dict(_PRIOR, recurrence_type=recurrence_type)
    attrs.update(overrides)
    return SimpleNamespace(**attrs)


def snap(t):
    """Convention "Unchanged": snapshot of all six attributes."""
    return vars(t).copy()


def create(**fields):
    """Convention "Schema cases": WorkOrderTemplateCreate with the minimal valid payload."""
    return WorkOrderTemplateCreate(template_name="T", work_order_type_id=1, **fields)


def assert_rejected(exc_info, field=None):
    """Convention "Rejected": ValidationError whose loc names recurrence_type/recurrence_day/model root.
    With `field`, the case requires that specific field in the loc."""
    locs = [tuple(e["loc"]) for e in exc_info.value.errors()]
    if field is not None:
        assert any(field in loc for loc in locs), locs
    else:
        assert any(
            loc == () or "recurrence_type" in loc or "recurrence_day" in loc for loc in locs
        ), locs


def adv(from_date, recurrence_type, recurrence_day):
    return advance_next_generation_date(
        from_date=from_date, recurrence_type=recurrence_type, recurrence_day=recurrence_day
    )


# --- validate_recurrence_span ------------------------------------------------


def test_wor_vs_01__same_day_is_valid():
    """WOR-VS-01 — start == end returns None, no error.
    Rules: VS R2."""
    assert validate_recurrence_span(date(2026, 3, 2), date(2026, 3, 2)) is None


def test_wor_vs_02__end_one_day_before_start():
    """WOR-VS-02 — end one day before start raises E_BACK.
    Rules: VS R1."""
    with pytest.raises(ValueError) as exc:
        validate_recurrence_span(date(2026, 3, 2), date(2026, 3, 1))
    assert str(exc.value) == E_BACK


def test_wor_vs_03__backwards_beats_span():
    """WOR-VS-03 — end far before start raises E_BACK, not E_SPAN.
    Rules: VS R1, R5."""
    with pytest.raises(ValueError) as exc:
        validate_recurrence_span(date(2026, 12, 31), date(2026, 1, 1))
    assert str(exc.value) == E_BACK


def test_wor_vs_04__exactly_183_days_valid():
    """WOR-VS-04 — exactly 183 days returns None.
    Rules: VS R3."""
    assert validate_recurrence_span(date(2026, 1, 1), date(2026, 7, 3)) is None


def test_wor_vs_05__184_days_rejected():
    """WOR-VS-05 — 184 days raises E_SPAN.
    Rules: VS R4."""
    with pytest.raises(ValueError) as exc:
        validate_recurrence_span(date(2026, 1, 1), date(2026, 7, 4))
    assert str(exc.value) == E_SPAN


def test_wor_vs_06__365_days_rejected():
    """WOR-VS-06 — 365 days raises E_SPAN.
    Rules: VS R4."""
    with pytest.raises(ValueError) as exc:
        validate_recurrence_span(date(2026, 1, 1), date(2027, 1, 1))
    assert str(exc.value) == E_SPAN


# --- advance_next_generation_date: helper --------------------------------------


def test_wor_adv_01__daily_plus_one():
    """WOR-ADV-01 — daily advances one day.
    Rules: ADV R1."""
    assert adv(date(2026, 3, 2), "daily", None) == date(2026, 3, 3)


@pytest.mark.parametrize(
    "from_date, expected",
    [
        pytest.param(date(2026, 2, 28), date(2026, 3, 1), id="WOR-ADV-02-feb28"),
        pytest.param(date(2026, 12, 31), date(2027, 1, 1), id="WOR-ADV-02-dec31"),
    ],
)
def test_wor_adv_02__daily_month_and_year_rollover(from_date, expected):
    """WOR-ADV-02 — daily rolls over month end and year end.
    Rules: ADV R1."""
    assert adv(from_date, "daily", None) == expected


@pytest.mark.parametrize("day", [0, 45, -1, 3], ids=lambda d: f"WOR-ADV-03-day{d}")
def test_wor_adv_03__daily_ignores_day(day):
    """WOR-ADV-03 — daily ignores recurrence_day.
    Rules: ADV R10."""
    assert adv(date(2026, 3, 2), "daily", day) == date(2026, 3, 3)


def test_wor_adv_04__weekly_no_day_plus_seven():
    """WOR-ADV-04 — weekly without day advances 7 days.
    Rules: ADV R2, R9."""
    assert adv(date(2026, 3, 4), "weekly", None) == date(2026, 3, 11)


def test_wor_adv_05__weekly_day_zero_is_monday():
    """WOR-ADV-05 — weekly day 0 goes to next Monday (0 is not treated as missing).
    Rules: ADV R3, R9."""
    assert adv(date(2026, 3, 4), "weekly", 0) == date(2026, 3, 9)


def test_wor_adv_06__weekly_same_weekday_plus_seven():
    """WOR-ADV-06 — weekly on the same weekday advances 7 days, never from_date.
    Rules: ADV R3."""
    assert adv(date(2026, 3, 4), "weekly", 2) == date(2026, 3, 11)


def test_wor_adv_07__weekly_one_day_ahead():
    """WOR-ADV-07 — weekly target the next day.
    Rules: ADV R3."""
    assert adv(date(2026, 3, 4), "weekly", 3) == date(2026, 3, 5)


def test_wor_adv_08__weekly_six_days_ahead():
    """WOR-ADV-08 — weekly target the previous weekday → 6 days ahead.
    Rules: ADV R3."""
    assert adv(date(2026, 3, 4), "weekly", 1) == date(2026, 3, 10)


@pytest.mark.parametrize(
    "from_date, day, expected",
    [
        pytest.param(date(2026, 3, 30), 2, date(2026, 4, 1), id="WOR-ADV-09-month"),
        pytest.param(date(2026, 12, 31), 0, date(2027, 1, 4), id="WOR-ADV-09-year"),
    ],
)
def test_wor_adv_09__weekly_month_and_year_rollover(from_date, day, expected):
    """WOR-ADV-09 — weekly crosses month end and year end.
    Rules: ADV R3."""
    assert adv(from_date, "weekly", day) == expected


@pytest.mark.parametrize(
    "day, expected",
    [
        pytest.param(7, date(2026, 3, 9), id="WOR-ADV-10-day7"),
        pytest.param(-1, date(2026, 3, 8), id="WOR-ADV-10-day-1"),
        pytest.param(10, date(2026, 3, 5), id="WOR-ADV-10-day10"),
        pytest.param(9, date(2026, 3, 11), id="WOR-ADV-10-day9"),
    ],
)
def test_wor_adv_10__weekly_out_of_range_day_wraps(day, expected):
    """WOR-ADV-10 — weekly out-of-range day is wrapped modulo 7, no error.
    Rules: ADV R4."""
    assert adv(date(2026, 3, 4), "weekly", day) == expected


@pytest.mark.parametrize(
    "from_date",
    [
        pytest.param(date(2026, 1, 10), id="WOR-ADV-11-before"),
        pytest.param(date(2026, 1, 15), id="WOR-ADV-11-on"),
        pytest.param(date(2026, 1, 20), id="WOR-ADV-11-after"),
    ],
)
def test_wor_adv_11__monthly_always_next_month(from_date):
    """WOR-ADV-11 — monthly day 15 always returns next month's 15th.
    Rules: ADV R5."""
    assert adv(from_date, "monthly", 15) == date(2026, 2, 15)


def test_wor_adv_12__monthly_year_rollover():
    """WOR-ADV-12 — monthly from December rolls into January of next year.
    Rules: ADV R5."""
    assert adv(date(2026, 12, 10), "monthly", 5) == date(2027, 1, 5)


@pytest.mark.parametrize(
    "from_date, expected",
    [
        pytest.param(date(2026, 1, 15), date(2026, 2, 28), id="WOR-ADV-13-feb"),
        pytest.param(date(2028, 1, 15), date(2028, 2, 29), id="WOR-ADV-13-leap"),
        pytest.param(date(2026, 3, 15), date(2026, 4, 30), id="WOR-ADV-13-apr"),
        pytest.param(date(2026, 12, 15), date(2027, 1, 31), id="WOR-ADV-13-jan"),
    ],
)
def test_wor_adv_13__monthly_day31_capped_to_month_end(from_date, expected):
    """WOR-ADV-13 — monthly day 31 is capped to the target month's last day.
    Rules: ADV R6."""
    assert adv(from_date, "monthly", 31) == expected


@pytest.mark.parametrize(
    "from_date, day, expected",
    [
        pytest.param(date(2026, 1, 15), 28, date(2026, 2, 28), id="WOR-ADV-14-d28"),
        pytest.param(date(2026, 1, 15), 29, date(2026, 2, 28), id="WOR-ADV-14-d29"),
        pytest.param(date(2026, 3, 15), 30, date(2026, 4, 30), id="WOR-ADV-14-d30"),
        pytest.param(date(2026, 3, 15), 31, date(2026, 4, 30), id="WOR-ADV-14-d31"),
    ],
)
def test_wor_adv_14__monthly_cap_boundary(from_date, day, expected):
    """WOR-ADV-14 — month-end cap boundary on both sides.
    Rules: ADV R6."""
    assert adv(from_date, "monthly", day) == expected


@pytest.mark.parametrize("day", [0, -5, 1], ids=lambda d: f"WOR-ADV-15-day{d}")
def test_wor_adv_15__monthly_low_clamp(day):
    """WOR-ADV-15 — monthly day ≤ 1 clamps to the 1st, no error.
    Rules: ADV R7, R9."""
    assert adv(date(2026, 1, 10), "monthly", day) == date(2026, 2, 1)


@pytest.mark.parametrize(
    "from_date, day, expected",
    [
        pytest.param(date(2026, 1, 10), 45, date(2026, 2, 28), id="WOR-ADV-16-jan45"),
        pytest.param(date(2026, 2, 10), 45, date(2026, 3, 31), id="WOR-ADV-16-feb45"),
        pytest.param(date(2026, 2, 10), 32, date(2026, 3, 31), id="WOR-ADV-16-feb32"),
        pytest.param(date(2026, 2, 10), 31, date(2026, 3, 31), id="WOR-ADV-16-feb31"),
    ],
)
def test_wor_adv_16__monthly_high_clamp(from_date, day, expected):
    """WOR-ADV-16 — monthly day > 31 behaves like 31, no error.
    Rules: ADV R7."""
    assert adv(from_date, "monthly", day) == expected


@pytest.mark.parametrize(
    "from_date, expected",
    [
        pytest.param(date(2026, 1, 10), date(2026, 2, 10), id="WOR-ADV-17-jan10"),
        pytest.param(date(2026, 1, 31), date(2026, 2, 28), id="WOR-ADV-17-jan31"),
        pytest.param(date(2026, 2, 28), date(2026, 3, 28), id="WOR-ADV-17-feb28"),
        pytest.param(date(2026, 12, 31), date(2027, 1, 31), id="WOR-ADV-17-dec31"),
    ],
)
def test_wor_adv_17__monthly_no_day_uses_from_date_day(from_date, expected):
    """WOR-ADV-17 — monthly without day uses from_date's day (drifts after a short month).
    Rules: ADV R8."""
    assert adv(from_date, "monthly", None) == expected


def test_wor_adv_18__monthly_stored_day_never_drifts():
    """WOR-ADV-18 — chained monthly day 31 returns to 31 after February.
    Rules: ADV R6, R8a."""
    results = []
    current = date(2026, 1, 31)
    for _ in range(3):
        current = adv(current, "monthly", 31)
        results.append(current)
    assert results == [date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)]


@pytest.mark.xfail(strict=True, reason=BUG_360)
@pytest.mark.parametrize(
    "rtype, day",
    [
        pytest.param("Daily", None, id="WOR-ADV-19-Daily"),
        pytest.param("WEEKLY", None, id="WOR-ADV-19-WEEKLY"),
        pytest.param(" daily", None, id="WOR-ADV-19-space-daily"),
        pytest.param("Weekly", None, id="WOR-ADV-19-Weekly"),
        pytest.param("biweekly", None, id="WOR-ADV-19-biweekly"),
        pytest.param("quarterly", None, id="WOR-ADV-19-quarterly"),
        pytest.param("", None, id="WOR-ADV-19-empty"),
        pytest.param("Monthly", 15, id="WOR-ADV-19-Monthly15"),
    ],
)
def test_wor_adv_19__unsupported_type_raises(rtype, day):
    """WOR-ADV-19 — unsupported recurrence type raises ValueError with repr of the value.
    Rules: ADV R11 [BUG-360]."""
    with pytest.raises(ValueError) as exc:
        adv(date(2026, 3, 2), rtype, day)
    assert str(exc.value) == "Unsupported recurrence type: " + repr(rtype)


@pytest.mark.xfail(strict=True, reason=BUG_361)
@pytest.mark.parametrize("day", [None, 0], ids=lambda d: f"WOR-ADV-20-day{d}")
def test_wor_adv_20__none_type_raises(day):
    """WOR-ADV-20 — recurrence_type None raises ValueError.
    Rules: ADV R11b [BUG-361]."""
    with pytest.raises(ValueError) as exc:
        adv(date(2026, 3, 2), None, day)
    assert str(exc.value) == "Unsupported recurrence type: None"


# --- advance_next_generation_date: schema rules ---------------------------------


@pytest.mark.parametrize("v", ["daily", "weekly", "monthly"], ids=lambda v: f"WOR-ADV-21-{v}")
def test_wor_adv_21__create_accepts_supported_types(v):
    """WOR-ADV-21 — create schema accepts the three supported types as typed.
    Rules: ADV R11a."""
    m = create(is_recurring=True, recurrence_type=v, recurrence_day=None)
    assert m.recurrence_type == v


@pytest.mark.xfail(strict=True, reason=BUG_360)
@pytest.mark.parametrize(
    "v, expected",
    [
        pytest.param(" Weekly ", "weekly", id="WOR-ADV-22-Weekly"),
        pytest.param("MONTHLY", "monthly", id="WOR-ADV-22-MONTHLY"),
        pytest.param("Daily", "daily", id="WOR-ADV-22-Daily"),
    ],
)
def test_wor_adv_22__create_normalises_type(v, expected):
    """WOR-ADV-22 — create schema trims and lower-cases recurrence_type.
    Rules: ADV R11a [BUG-360]."""
    m = create(is_recurring=True, recurrence_type=v)
    assert m.recurrence_type == expected


@pytest.mark.xfail(strict=True, reason=BUG_360)
@pytest.mark.parametrize(
    "v", ["biweekly", "wekly", "quarterly", "", "   "], ids=lambda v: f"WOR-ADV-23-{v!r}"
)
def test_wor_adv_23__create_rejects_unsupported_type(v):
    """WOR-ADV-23 — create schema rejects unsupported recurrence_type.
    Rules: ADV R11a [BUG-360]."""
    with pytest.raises(pydantic.ValidationError) as exc:
        create(is_recurring=True, recurrence_type=v)
    assert_rejected(exc, "recurrence_type")


@pytest.mark.xfail(strict=True, reason=BUG_360)
def test_wor_adv_24__update_normalises_type():
    """WOR-ADV-24 — update schema trims and lower-cases recurrence_type.
    Rules: ADV R11a [BUG-360]."""
    m = WorkOrderTemplateUpdate(recurrence_type=" Weekly ")
    assert m.recurrence_type == "weekly"


@pytest.mark.xfail(strict=True, reason=BUG_360)
@pytest.mark.parametrize("v", ["biweekly", "quarterly"], ids=lambda v: f"WOR-ADV-25-{v}")
def test_wor_adv_25__update_rejects_unsupported_type(v):
    """WOR-ADV-25 — update schema rejects unsupported recurrence_type.
    Rules: ADV R11a [BUG-360]."""
    with pytest.raises(pydantic.ValidationError) as exc:
        WorkOrderTemplateUpdate(recurrence_type=v)
    assert_rejected(exc, "recurrence_type")


@pytest.mark.parametrize(
    "v", [pytest.param(None, id="WOR-ADV-26-None"), pytest.param("monthly", id="WOR-ADV-26-monthly")]
)
def test_wor_adv_26__update_accepts_none_and_supported(v):
    """WOR-ADV-26 — update schema accepts None and a supported type.
    Rules: ADV R11a."""
    m = WorkOrderTemplateUpdate(recurrence_type=v)
    assert m.recurrence_type == v


@pytest.mark.xfail(strict=True, reason=BUG_361)
@pytest.mark.parametrize(
    "fields",
    [
        pytest.param(dict(is_recurring=True, recurrence_type=None), id="WOR-ADV-27-None"),
        pytest.param(dict(is_recurring=True), id="WOR-ADV-27-omitted"),
        pytest.param(
            dict(is_recurring=True, recurrence_type=None, recurrence_day=9), id="WOR-ADV-27-day9"
        ),
    ],
)
def test_wor_adv_27__create_recurring_requires_type(fields):
    """WOR-ADV-27 — create schema rejects is_recurring without a type (a day does not rescue it).
    Rules: ADV R11b, R10a [BUG-361]."""
    with pytest.raises(pydantic.ValidationError) as exc:
        create(**fields)
    assert_rejected(exc)


def test_wor_adv_28__create_non_recurring_without_type():
    """WOR-ADV-28 — a non-recurring template may have no type.
    Rules: ADV R11b."""
    m = create(is_recurring=False, recurrence_type=None)
    assert m.is_recurring is False
    assert m.recurrence_type is None


@pytest.mark.xfail(strict=True, reason=BUG_362)
@pytest.mark.parametrize("d", [7, -1, 10], ids=lambda d: f"WOR-ADV-29-day{d}")
def test_wor_adv_29__create_weekly_rejects_out_of_range_day(d):
    """WOR-ADV-29 — create schema rejects weekly recurrence_day outside 0–6.
    Rules: ADV R4a [BUG-362]."""
    with pytest.raises(pydantic.ValidationError) as exc:
        create(is_recurring=True, recurrence_type="weekly", recurrence_day=d)
    assert_rejected(exc)


@pytest.mark.parametrize("d", [0, 6, None], ids=lambda d: f"WOR-ADV-30-day{d}")
def test_wor_adv_30__create_weekly_accepts_in_range_day(d):
    """WOR-ADV-30 — create schema accepts weekly recurrence_day 0, 6 and None.
    Rules: ADV R4a, R2."""
    m = create(is_recurring=True, recurrence_type="weekly", recurrence_day=d)
    assert m.recurrence_day == d


@pytest.mark.xfail(strict=True, reason=BUG_362)
@pytest.mark.parametrize("d", [0, -5, 32, 45], ids=lambda d: f"WOR-ADV-31-day{d}")
def test_wor_adv_31__create_monthly_rejects_out_of_range_day(d):
    """WOR-ADV-31 — create schema rejects monthly recurrence_day outside 1–31.
    Rules: ADV R7a [BUG-362]."""
    with pytest.raises(pydantic.ValidationError) as exc:
        create(is_recurring=True, recurrence_type="monthly", recurrence_day=d)
    assert_rejected(exc)


@pytest.mark.parametrize("d", [1, 31, 15], ids=lambda d: f"WOR-ADV-32-day{d}")
def test_wor_adv_32__create_monthly_accepts_in_range_day(d):
    """WOR-ADV-32 — create schema accepts monthly recurrence_day 1, 31 and 15.
    Rules: ADV R7a."""
    m = create(is_recurring=True, recurrence_type="monthly", recurrence_day=d)
    assert m.recurrence_day == d


@pytest.mark.parametrize("d", [9, -1, 45], ids=lambda d: f"WOR-ADV-33-day{d}")
def test_wor_adv_33__create_daily_keeps_any_day(d):
    """WOR-ADV-33 — create schema keeps any recurrence_day on a daily template.
    Rules: ADV R10a."""
    m = create(is_recurring=True, recurrence_type="daily", recurrence_day=d)
    assert m.recurrence_type == "daily"
    assert m.recurrence_day == d


@pytest.mark.parametrize("d", [9, -1, 45], ids=lambda d: f"WOR-ADV-34-day{d}")
def test_wor_adv_34__create_non_recurring_untyped_keeps_any_day(d):
    """WOR-ADV-34 — create schema keeps any recurrence_day on a non-recurring untyped template.
    Rules: ADV R10a."""
    m = create(is_recurring=False, recurrence_type=None, recurrence_day=d)
    assert m.is_recurring is False
    assert m.recurrence_type is None
    assert m.recurrence_day == d


@pytest.mark.parametrize(
    "fields, exp_day, exp_type",
    [
        pytest.param(dict(recurrence_type="daily", recurrence_day=45), 45, "daily", id="WOR-ADV-35-daily45"),
        pytest.param(dict(recurrence_day=-1), -1, None, id="WOR-ADV-35-day-1"),
    ],
)
def test_wor_adv_35__update_keeps_day_without_range_type(fields, exp_day, exp_type):
    """WOR-ADV-35 — update schema keeps recurrence_day for daily / no type.
    Rules: ADV R10a."""
    m = WorkOrderTemplateUpdate(**fields)
    assert m.recurrence_day == exp_day
    assert m.recurrence_type == exp_type


@pytest.mark.parametrize(
    "rtype, d",
    [
        pytest.param("weekly", 9, id="WOR-ADV-36-weekly9"),
        pytest.param("monthly", 0, id="WOR-ADV-36-monthly0"),
    ],
)
def test_wor_adv_36__update_schema_does_no_day_range_check(rtype, d):
    """WOR-ADV-36 — update schema alone does no day-range check, even with type and day together.
    Rules: ADV R4b."""
    m = WorkOrderTemplateUpdate(recurrence_type=rtype, recurrence_day=d)
    assert m.recurrence_type == rtype
    assert m.recurrence_day == d


@pytest.mark.parametrize(
    "schema, v, expected",
    [
        pytest.param("create", " Weekly ", "weekly", id="WOR-ADV-37-create-Weekly"),
        pytest.param("create", "MONTHLY", "monthly", id="WOR-ADV-37-create-MONTHLY"),
        pytest.param("create", "Daily", "daily", id="WOR-ADV-37-create-Daily"),
        pytest.param("update", " Weekly ", "weekly", id="WOR-ADV-37-update-Weekly"),
    ],
)
def test_wor_adv_37__padded_mixed_case_supported_type_not_rejected(schema, v, expected):
    """WOR-ADV-37 — padded / mixed-case supported types build without error in both schemas
    and equal the supported value after trim + lower-case (holds today and after the BUG-360 fix).
    Rules: ADV R11a."""
    if schema == "create":
        m = create(is_recurring=True, recurrence_type=v)
    else:
        m = WorkOrderTemplateUpdate(recurrence_type=v)
    assert m.recurrence_type.strip().lower() == expected


# --- _apply_recurrence_range ---------------------------------------------------


def test_wor_apr_01__daily_writes_range_and_clears_day():
    """WOR-APR-01 — daily: range written, day cleared, next = planned + 1.
    Rules: APR R2, R4, R5."""
    t = T("daily")
    assert _apply_recurrence_range(t, date(2026, 3, 2), date(2026, 3, 31)) is None
    assert t.recurrence_start_date == date(2026, 3, 2)
    assert t.recurrence_end_date == date(2026, 3, 31)
    assert t.recurrence_day is None
    assert t.next_generation_date == date(2026, 3, 3)
    assert t.is_recurring is True
    assert t.recurrence_type == "daily"


def test_wor_apr_02__weekly_clears_day_and_adds_seven():
    """WOR-APR-02 — weekly: day cleared, next = placement + 7 (not prior Monday).
    Rules: APR R2, R4, R5."""
    t = T("weekly", recurrence_day=0)
    assert _apply_recurrence_range(t, date(2026, 3, 4), date(2026, 4, 30)) is None
    assert t.recurrence_start_date == date(2026, 3, 4)
    assert t.recurrence_end_date == date(2026, 4, 30)
    assert t.recurrence_day is None
    assert t.next_generation_date == date(2026, 3, 11)


def test_wor_apr_03__monthly_day_from_planned_date():
    """WOR-APR-03 — monthly: day overwritten by planned date's day; next capped to Feb 28.
    Rules: APR R2, R3, R5."""
    t = T("monthly", recurrence_day=15)
    assert _apply_recurrence_range(t, date(2026, 1, 31), date(2026, 6, 30)) is None
    assert t.recurrence_start_date == date(2026, 1, 31)
    assert t.recurrence_end_date == date(2026, 6, 30)
    assert t.recurrence_day == 31
    assert t.next_generation_date == date(2026, 2, 28)


def test_wor_apr_04__monthly_day_overwritten():
    """WOR-APR-04 — monthly: prior day 25 replaced by 10; next = next month's 10th.
    Rules: APR R3, R5."""
    t = T("monthly", recurrence_day=25)
    assert _apply_recurrence_range(t, date(2026, 3, 10), date(2026, 5, 31)) is None
    assert t.recurrence_day == 10
    assert t.next_generation_date == date(2026, 4, 10)
    assert t.recurrence_start_date == date(2026, 3, 10)
    assert t.recurrence_end_date == date(2026, 5, 31)


def test_wor_apr_05__backwards_range_leaves_template_unchanged():
    """WOR-APR-05 — end before start raises E_BACK and mutates nothing.
    Rules: APR R1."""
    t = T("daily")
    before = snap(t)
    with pytest.raises(ValueError) as exc:
        _apply_recurrence_range(t, date(2026, 3, 2), date(2026, 3, 1))
    assert str(exc.value) == E_BACK
    assert vars(t) == before


def test_wor_apr_06__span_too_long_leaves_template_unchanged():
    """WOR-APR-06 — 184-day span raises E_SPAN and mutates nothing.
    Rules: APR R1."""
    t = T("monthly")
    before = snap(t)
    with pytest.raises(ValueError) as exc:
        _apply_recurrence_range(t, date(2026, 1, 1), date(2026, 7, 4))
    assert str(exc.value) == E_SPAN
    assert vars(t) == before


def test_wor_apr_07__exactly_183_days_applied():
    """WOR-APR-07 — 183-day span is applied.
    Rules: APR R1."""
    t = T("daily")
    assert _apply_recurrence_range(t, date(2026, 1, 1), date(2026, 7, 3)) is None
    assert t.recurrence_start_date == date(2026, 1, 1)
    assert t.recurrence_end_date == date(2026, 7, 3)
    assert t.recurrence_day is None
    assert t.next_generation_date == date(2026, 1, 2)


def test_wor_apr_08__single_day_range_next_after_end():
    """WOR-APR-08 — one-day range: next date lands after the end date and is still set.
    Rules: APR R6, R7."""
    t = T("daily")
    assert _apply_recurrence_range(t, date(2026, 3, 2), date(2026, 3, 2)) is None
    assert t.recurrence_start_date == date(2026, 3, 2)
    assert t.recurrence_end_date == date(2026, 3, 2)
    assert t.next_generation_date == date(2026, 3, 3)


@pytest.mark.xfail(strict=True, reason=f"{BUG_360}; {BUG_361} (for None)")
@pytest.mark.parametrize(
    "v", [None, "Weekly", "biweekly", ""], ids=lambda v: f"WOR-APR-09-{v!r}"
)
def test_wor_apr_09__unsupported_type_rejected_before_mutation(v):
    """WOR-APR-09 — unsupported / None type raises ValueError and mutates nothing.
    Rules: APR R4a [BUG-360, BUG-361]."""
    t = T(v)
    before = snap(t)
    with pytest.raises(ValueError) as exc:
        _apply_recurrence_range(t, date(2026, 3, 2), date(2026, 3, 31))
    assert str(exc.value) == "Unsupported recurrence type: " + repr(v)
    assert vars(t) == before


@pytest.mark.parametrize(
    "rtype, start, end, message",
    [
        pytest.param("biweekly", date(2026, 3, 2), date(2026, 3, 1), E_BACK, id="WOR-APR-10-a"),
        pytest.param(None, date(2026, 1, 1), date(2026, 7, 4), E_SPAN, id="WOR-APR-10-b"),
    ],
)
def test_wor_apr_10__range_error_wins_over_type_error(rtype, start, end, message):
    """WOR-APR-10 — with a bad type AND a bad range, the range error is raised; nothing mutated.
    Rules: APR R4a, R1."""
    t = T(rtype)
    before = snap(t)
    with pytest.raises(ValueError) as exc:
        _apply_recurrence_range(t, start, end)
    assert str(exc.value) == message
    assert vars(t) == before


def test_wor_apr_11__is_recurring_not_checked():
    """WOR-APR-11 — applies even to a non-recurring template; is_recurring stays False.
    Rules: APR R2, R5."""
    t = T("daily", is_recurring=False)
    assert _apply_recurrence_range(t, date(2026, 3, 2), date(2026, 3, 31)) is None
    assert t.recurrence_start_date == date(2026, 3, 2)
    assert t.recurrence_end_date == date(2026, 3, 31)
    assert t.recurrence_day is None
    assert t.next_generation_date == date(2026, 3, 3)
    assert t.is_recurring is False


# --- seed_recurrence_from_planned_date -------------------------------------------


def test_wor_seed_01__non_recurring_skips_even_invalid_range():
    """WOR-SEED-01 — non-recurring: invalid range is not validated, nothing changes.
    Rules: SEED R1."""
    t = T("daily", is_recurring=False, next_generation_date=None)
    before = snap(t)
    assert seed_recurrence_from_planned_date(t, date(2026, 3, 2), date(2026, 3, 1)) is None
    assert vars(t) == before


def test_wor_seed_02__non_recurring_skips_valid_range():
    """WOR-SEED-02 — non-recurring: valid range, nothing changes.
    Rules: SEED R1."""
    t = T("daily", is_recurring=False, next_generation_date=None)
    before = snap(t)
    assert seed_recurrence_from_planned_date(t, date(2026, 3, 2), date(2026, 3, 31)) is None
    assert vars(t) == before


def test_wor_seed_03__already_seeded_skips_invalid_range():
    """WOR-SEED-03 — already seeded: invalid range not validated, nothing changes.
    Rules: SEED R2."""
    t = T("daily", next_generation_date=date(2026, 2, 10))
    before = snap(t)
    assert seed_recurrence_from_planned_date(t, date(2026, 3, 2), date(2026, 3, 1)) is None
    assert vars(t) == before


def test_wor_seed_04__already_seeded_skips_valid_range():
    """WOR-SEED-04 — already seeded: valid range, nothing changes.
    Rules: SEED R2."""
    t = T("monthly", recurrence_day=15, next_generation_date=date(2026, 2, 10))
    before = snap(t)
    assert seed_recurrence_from_planned_date(t, date(2026, 1, 31), date(2026, 4, 30)) is None
    assert vars(t) == before


def test_wor_seed_05__first_placement_seeds():
    """WOR-SEED-05 — recurring and unseeded: range applied.
    Rules: SEED R3."""
    t = T(
        "monthly",
        recurrence_day=None,
        recurrence_start_date=None,
        recurrence_end_date=None,
        next_generation_date=None,
    )
    assert seed_recurrence_from_planned_date(t, date(2026, 1, 31), date(2026, 4, 30)) is None
    assert t.recurrence_start_date == date(2026, 1, 31)
    assert t.recurrence_end_date == date(2026, 4, 30)
    assert t.recurrence_day == 31
    assert t.next_generation_date == date(2026, 2, 28)


def test_wor_seed_06__span_error_propagates():
    """WOR-SEED-06 — recurring and unseeded with 184-day span raises E_SPAN, nothing changes.
    Rules: SEED R3."""
    t = T("daily", next_generation_date=None)
    before = snap(t)
    with pytest.raises(ValueError) as exc:
        seed_recurrence_from_planned_date(t, date(2026, 1, 1), date(2026, 7, 4))
    assert str(exc.value) == E_SPAN
    assert vars(t) == before


@pytest.mark.xfail(strict=True, reason=BUG_361)
def test_wor_seed_07__none_type_rejected():
    """WOR-SEED-07 — recurring, unseeded, no type: raises ValueError, nothing changes.
    Rules: SEED R3 (via APR R4a) [BUG-361]."""
    t = T(None, next_generation_date=None)
    before = snap(t)
    with pytest.raises(ValueError) as exc:
        seed_recurrence_from_planned_date(t, date(2026, 3, 2), date(2026, 3, 31))
    assert str(exc.value) == "Unsupported recurrence type: None"
    assert vars(t) == before


# --- reseed_recurrence_program --------------------------------------------------


def test_wor_reseed_01__non_recurring_skips_invalid_range():
    """WOR-RESEED-01 — non-recurring: invalid range not validated, nothing changes.
    Rules: RESEED R1."""
    t = T("daily", is_recurring=False)
    before = snap(t)
    assert reseed_recurrence_program(t, date(2026, 3, 2), date(2026, 3, 1)) is None
    assert vars(t) == before


def test_wor_reseed_02__non_recurring_skips_valid_range():
    """WOR-RESEED-02 — non-recurring: valid range, nothing changes.
    Rules: RESEED R1."""
    t = T("daily", is_recurring=False)
    before = snap(t)
    assert reseed_recurrence_program(t, date(2026, 3, 2), date(2026, 3, 31)) is None
    assert vars(t) == before


def test_wor_reseed_03__overwrites_seeded_program():
    """WOR-RESEED-03 — recurring and seeded: everything overwritten.
    Rules: RESEED R2."""
    t = T(
        "weekly",
        recurrence_day=3,
        recurrence_start_date=date(2026, 1, 1),
        recurrence_end_date=date(2026, 3, 31),
        next_generation_date=date(2026, 2, 10),
    )
    assert reseed_recurrence_program(t, date(2026, 3, 4), date(2026, 5, 31)) is None
    assert t.recurrence_start_date == date(2026, 3, 4)
    assert t.recurrence_end_date == date(2026, 5, 31)
    assert t.recurrence_day is None
    assert t.next_generation_date == date(2026, 3, 11)


def test_wor_reseed_04__seeds_unseeded_program():
    """WOR-RESEED-04 — recurring and unseeded: range applied.
    Rules: RESEED R2."""
    t = T("daily", next_generation_date=None)
    assert reseed_recurrence_program(t, date(2026, 3, 2), date(2026, 3, 31)) is None
    assert t.recurrence_start_date == date(2026, 3, 2)
    assert t.recurrence_end_date == date(2026, 3, 31)
    assert t.recurrence_day is None
    assert t.next_generation_date == date(2026, 3, 3)


def test_wor_reseed_05__backwards_range_raises():
    """WOR-RESEED-05 — recurring with backwards range raises E_BACK, nothing changes.
    Rules: RESEED R2."""
    t = T("monthly", recurrence_day=15, next_generation_date=date(2026, 2, 10))
    before = snap(t)
    with pytest.raises(ValueError) as exc:
        reseed_recurrence_program(t, date(2026, 3, 2), date(2026, 3, 1))
    assert str(exc.value) == E_BACK
    assert vars(t) == before


@pytest.mark.xfail(strict=True, reason=BUG_360)
def test_wor_reseed_06__unsupported_type_rejected():
    """WOR-RESEED-06 — unsupported type raises ValueError, nothing changes.
    Rules: RESEED R2 (via APR R4a) [BUG-360]."""
    t = T("quarterly", next_generation_date=date(2026, 2, 10))
    before = snap(t)
    with pytest.raises(ValueError) as exc:
        reseed_recurrence_program(t, date(2026, 3, 2), date(2026, 3, 31))
    assert str(exc.value) == "Unsupported recurrence type: 'quarterly'"
    assert vars(t) == before


# --- is_recurrence_program_active ------------------------------------------------

TARGET = date(2026, 3, 15)


def test_wor_act_01__non_recurring_inactive():
    """WOR-ACT-01 — non-recurring is inactive.
    Rules: ACT R1."""
    t = T("daily", is_recurring=False, next_generation_date=date(2026, 3, 1), recurrence_end_date=None)
    assert is_recurrence_program_active(t, TARGET) is False


def test_wor_act_02__unseeded_inactive():
    """WOR-ACT-02 — no next date is inactive.
    Rules: ACT R2."""
    t = T("daily", next_generation_date=None, recurrence_end_date=None)
    assert is_recurrence_program_active(t, TARGET) is False


@pytest.mark.parametrize(
    "end, expected",
    [
        pytest.param(date(2026, 3, 14), False, id="WOR-ACT-03"),
        pytest.param(date(2026, 3, 15), True, id="WOR-ACT-04"),
        pytest.param(date(2026, 3, 16), True, id="WOR-ACT-05"),
    ],
)
def test_wor_act_03_04_05__end_date_boundary(end, expected):
    """WOR-ACT-03 / WOR-ACT-04 / WOR-ACT-05 — end before target inactive; on or after target active.
    Rules: ACT R3, R4."""
    t = T("daily", next_generation_date=date(2026, 3, 1), recurrence_end_date=end)
    assert is_recurrence_program_active(t, TARGET) is expected


def test_wor_act_06__open_ended_active():
    """WOR-ACT-06 — no end date is active for any target.
    Rules: ACT R5."""
    t = T("daily", next_generation_date=date(2026, 3, 1), recurrence_end_date=None)
    assert is_recurrence_program_active(t, date(2099, 12, 31)) is True


def test_wor_act_07__start_and_next_ignored():
    """WOR-ACT-07 — start and next dates after the target do not make it inactive.
    Rules: ACT R6."""
    t = T(
        "daily",
        recurrence_start_date=date(2026, 4, 1),
        next_generation_date=date(2026, 4, 10),
        recurrence_end_date=date(2026, 5, 31),
    )
    assert is_recurrence_program_active(t, TARGET) is True


# --- should_advance_template ------------------------------------------------------


@pytest.mark.parametrize(
    "next_date, expected",
    [
        pytest.param(date(2026, 3, 15), True, id="WOR-SHA-01"),
        pytest.param(date(2026, 3, 16), False, id="WOR-SHA-02"),
        pytest.param(date(2026, 3, 1), True, id="WOR-SHA-03"),
    ],
)
def test_wor_sha_01_02_03__next_date_vs_target(next_date, expected):
    """WOR-SHA-01 / WOR-SHA-02 / WOR-SHA-03 — due when next date is on or before the target.
    Rules: SHA R1, R2, R3, R4."""
    t = T("daily", next_generation_date=next_date, recurrence_end_date=None)
    assert should_advance_template(t, TARGET) is expected


@pytest.mark.parametrize(
    "end, expected",
    [
        pytest.param(date(2026, 3, 14), False, id="WOR-SHA-04"),
        pytest.param(date(2026, 3, 15), True, id="WOR-SHA-05"),
    ],
)
def test_wor_sha_04_05__end_date_boundary(end, expected):
    """WOR-SHA-04 / WOR-SHA-05 — ended program not advanced; end on target still advanced.
    Rules: SHA R5."""
    t = T("daily", next_generation_date=date(2026, 3, 10), recurrence_end_date=end)
    assert should_advance_template(t, TARGET) is expected


def test_wor_sha_06__non_recurring_false():
    """WOR-SHA-06 — non-recurring is never advanced.
    Rules: SHA R6."""
    t = T("daily", is_recurring=False, next_generation_date=date(2026, 3, 10), recurrence_end_date=None)
    assert should_advance_template(t, TARGET) is False


def test_wor_sha_07__unseeded_false_not_none():
    """WOR-SHA-07 — no next date returns False (not None).
    Rules: SHA R6."""
    t = T("daily", next_generation_date=None, recurrence_end_date=None)
    assert should_advance_template(t, TARGET) is False


def test_wor_sha_08__start_after_target_does_not_block():
    """WOR-SHA-08 — a start date after the target does not block advancing.
    Rules: SHA R1 (per ACT R6)."""
    t = T(
        "daily",
        recurrence_start_date=date(2026, 4, 1),
        next_generation_date=date(2026, 3, 10),
        recurrence_end_date=date(2026, 5, 31),
    )
    assert should_advance_template(t, TARGET) is True
