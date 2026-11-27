# Tester pre-check: dao-machine_maintenance_log

Date: 2026-11-27. Source `app/dao/machine_maintenance_log.py`. Specs and cases:
`tests/unit/dao/machine_maintenance_log.*`, `tests/unit/managers/machine_maintenance_log_manager.*`,
`tests/unit/services/machine_maintenance_log_service.*`.

Search: I grepped the bare numbers `1100`, `1101` and `1102` in `tests/**/*.py`. All the markers
are inline `pytest.mark.xfail(..., reason="BUG-110x: ...")`, with no helper constants. Callers: only
`MachineMaintenanceLogManager` imports `machine_maintenance_log_dao`, and the service wraps the
manager. `test_machine_manager.py` and `test_calendar_service.py` only use the model for fixtures,
and neither names these bugs. (`test_calendar_service.py:889` says "BUG-1101 shape", but its marker
is BUG-1805.) So there are 48 target tests in 3 files.

Run today with `--runxfail`, DB `bf_dao_machine_maintenance_log_test`: 45 failed, 3 passed
(MMLM-L-125, L-126, L-127, all non-strict physical-order ties, which is expected). Every strict
test fails on the Then its card names, apart from the two wrong ones below.

## BUG-1100: same-date order (`maintenance_date DESC, id DESC`)

| File | Tests | Strict |
|---|---|---|
| DAO | MML-GW-09, GW-11, GM-10, GT-12, GP-15 | no |
| DAO | MML-GW-10, GM-11, GT-13, GP-16 (SQL text) | yes |
| manager | MMLM-L-120 to L-127 | no |
| manager | MMLM-L-128 to L-131 (SQL text) | yes |
| service | MLS-L-08 | no (its `ids` helper sorts, so Then 1 is a set check) |

Verdict: **right**, all 22. Each tie test makes three or five logs on one date, edits the lowest
id so that it moves to the back physically, and expects highest id first. GW-11 and L-124 to L-127
page with `limit=1` (R4a: no repeats or gaps; today GW-11 shows one log twice). The SQL-text cards
want `maintenance_date DESC` before `machine_maintenance_logs.id DESC`. A plain ORM
`desc(MachineMaintenanceLog.id)` passes them. A raw `text()` sort, or an aliased entity, would not
(risk for the systems engineer). The different-date order (R4) is guarded by GW-08 and GM-09,
which pass today. This bug depends on no other open bug.

## BUG-1101: log on another workspace's machine is not found

| File | Tests | Today fails on |
|---|---|---|
| DAO | MML-GW-24, GW-25, GI-09, GM-20, GT-22, GT-25, GP-25 | Then 3 / Then 2 (row returned) |
| manager | MMLM-U-09, U-10, U-11, G-20, L-46 to L-51, D-08, D-09 | no 404, or 400 instead of 404 |
| manager | **MMLM-G-21, G-22** | `TypeError: get_log() got an unexpected keyword argument 'include_deleted'` |
| service | MLS-G-05 | no 404 |

Verdict: **right** for 20 tests. GW-25, GT-25, L-50 and L-51 check that the filter comes before
paging (HR-5). The tests on non-target rows (R3: deleted or inactive machine and factory still
listed; GM-21 and the other "machine's own workspace" tests) pass today and guard against a filter
on machine state. A correct fix (compare `Machine.workspace_id` to the log's own, in the query,
through a join or EXISTS) makes all 20 pass.

**Wrong: MMLM-G-21 and MMLM-G-22.** They call `get_log(..., include_deleted=True)`, and that
parameter is BUG-1150's intended change (manager, out of scope). A correct DAO fix can't make them
pass, but their strict marker names only BUG-1101. I entered them in `docs/bugfix/wrong-tests.md`
with a diff that changes the reason to "BUG-1101, BUG-1150: needs both fixes".
**Decision (decided by Claude under the reviewer's delegation, 2026-11-27):** BUG-1101 stays in
the unit, because the defect is the label, not the check, and 20 right tests cover the bug. The
condition is that the marker diff is on `origin/main` before the baseline is recorded. Then the
flip check reports G-21 and G-22 as "also needs [BUG-1150]; still xfailed", and stage C keeps
their markers. If the diff is not on main in time, skip BUG-1101 for this round.

## BUG-1102: `deleted_at` from the application clock

| File | Tests | Strict |
|---|---|---|
| DAO | MML-SD-02, SD-05 | yes |
| manager | MMLM-D-19 | yes |
| service | MLS-D-04 | yes |

Verdict: **right**, all 4. Each one patches `app.dao.machine_maintenance_log.utcnow` (with
`create=True`) to a fixed naive `NOW = 2031-05-06 07:08:09` and expects `deleted_at == NOW`. Today
they get the database's `now()` (2026-...), on Then 3 as the cards say.

**Time zone and OS independence:** the tests never read the real clock, the OS time zone or the
session's `TimeZone`. The expected value is a constant, and the column is `timestamp without time
zone`, so psycopg2 stores a naive value as it is. The tests give the same result on Windows and on
Linux CI, and under any server `TimeZone`. They also prove the value comes from Python, not the
database, which is a stronger check than R1a's "whatever the database's `TimeZone`". The
non-target soft-delete tests (SD-01, SD-04 `!= T0`, manager line 6395 `is not None`) pass with the
real clock too. No non-target test compares `deleted_at` with the database clock.

Risks for the systems engineer:
- The patch replaces a **module-level name**. If `utcnow` is imported inside `soft_delete` (the way
  `func` is imported there today), or called as `app.utils.time.utcnow()`, the patch misses it and
  all four tests fail, even though the clock is right.
- `func.timezone('UTC', func.now())` gives UTC but fails the tests. The brief rules it out
  (it must be `utcnow()`).
- This bug depends on no other open bug.

## Outside this unit

- BUG-1150 (manager `get_log` `include_deleted`): when it is fixed, MMLM-G-21 and G-22 need both
  fixes on main before their markers go (see wrong-tests.md).
- BUG-1805 (calendar maintenance collector): its intended rule hides logs that BUG-1101 covers.
  The calendar doesn't use this DAO today, so the fix here doesn't change it.

## Note for stage C

Remove the markers on 46 tests: every BUG-1100, BUG-1101 and BUG-1102 test except MMLM-G-21 and
G-22, which keep theirs (after the marker diff they name BUG-1150 too). The flip check should
show 43 strict and non-strict xfails becoming passed, L-125 to L-127 going from xpassed to passed,
and G-21 and G-22 still xfailed with a note.
