# Execution notes — `app/services/machine_work_service.py`

> Cases: `tests/unit/services/machine_work_service.cases.md` (revision 3a) · Tests: `tests/unit/services/test_machine_work_service.py` · Source commit: e48a092
> Result: 65 passed · 5 xfailed · 0 discrepancies · 0 errors — branch coverage 98%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_machine_work_service.py -q -p no:cacheprovider -o addopts=""`

## How the tests are built
- **Standing rows** (W0, W1, W2, U1, F0, F1, F2, F9, WT0, WT1, WT9) are chained fixtures (`w0` … `wt9`) built in the Conventions order and pulled in by the autouse fixture `standing`, so ids rise W0 < W1 < W2 in every test.
- **Given rows**: the `g` fixture (class `Given`) has one builder per Conventions recipe: `g.machine(name, **but)`, `g.m0()`, `g.m1()`, `g.m2()`, `g.m3()`, `g.m9()`, `g.mx()`, `g.order(label, m, **but)`, `g.zero_order`, `g.far_order`, `g.factory`, `g.section`, `g.wtype`, `g.link(m, s)` (flushes, then `db.expire_all()`). Each builder flushes one row, so ids within a table rise in card order. `g.gone_machine()` and `g.gone()` are the two forms of the **gone** convention.
- **Order numbers** are `"WO-" + label + "-" + SFX` with `SFX = str(os.getpid())`.
- **commit point** = `db.commit()`, which only releases the fixture's savepoint.
- **sql_log** = a context manager that adds a `before_cursor_execute` listener to `db.connection()` and removes it on exit. In CR-24, DM-01 and DM-02, `w1.id` is read into `ws_id` **before** the commit point: the commit expires W1, and reading `w1.id` inside the log would add a `SELECT workspaces` to the log. That is a harness effect, not part of the call.
- **spies** = a context manager doing `patch.object(db, "commit"/"rollback", wraps=...)`. These are the only patches. Nothing else is mocked, and nothing reads the clock.
- **committed:** lines run `db.rollback()` once (after Then 6), then count `machines` named `"Pending"` with a fresh `select(func.count())` and re-read B (`expire_all` + select).
- **CR-27**: ids are read into a dict before the commit point and `db.expire_all()`, so no attribute access loads a relationship before the call. `ma` and `mb` are found in the result by order id, and `inspect(mb).unloaded` is checked before any attribute of `mb` is read.
- **HH-08**: the real message today is "year 29405 is out of range". Only the "contains" check is made (spec G3).
- **Checks run**: (1) `--runxfail`: the 5 BUG xfails fail on Then 1, as their cards name (CR-15, CR-16, UW-13, UW-14, DM-09). (2) A reference plugin (`mws_reference.py`, kept in scratch, not in the repo) adds a machine-workspace filter (BUG-1571), hides deleted-factory machines in `upcoming_work` only (BUG-1572). With it loaded and `--runxfail`, all 70 tests pass. (3) Three plain runs gave identical results (65 passed, 5 xfailed). (4) `ruff check` is clean and the file has LF line endings.

## Discrepancies
| ID | Case | Designed | Actual | Evidence | Likely cause |
|---|---|---|---|---|---|
| DISCREPANCY-1 | MWS-CR-01 | — | — | **Resolved in Revision 3**: the card (spec G4) no longer checks the tuple type; it asserts unpacking, indexing, `len == 2`, equality with `(wo, machine)` and the model types. The rows are SQLAlchemy `Row`s and all eight Then lines pass; the xfail was removed. | — |

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 118 (`if machine is None: continue`, true branch) | unreachable | Every bucket is created inside the loop over query rows, and the inner join means `machine` is never `None`. So a bucket always has a machine, and this defensive skip cannot run. |

## Factories added
None. Local helpers only.

## New bugs
None. BUG-3075 and BUG-3076 are unused.

## Notes for maintainers
- When BUG-1571 is fixed, CR-15, CR-16, UW-14 and DM-09 will XPASS. Remove their markers.
- When BUG-1572 is fixed, UW-13 will XPASS. The fix must stay in `upcoming_work`: CR-18 and DM-08 pin that `collect_raw_items` and `dates_by_machine` keep machines of deleted factories.
- `collect_raw_items` has no defined order, so every check on it compares sets.
- UW-12 builds 101 machines and 101 orders one flush at a time. It is the slowest test (about 1 s).

## Revision history
- **Revision 3 (2026-11-22).** CR-01 rewritten to the new eight Then lines (unpack, index with `is`, `len == 2`, `== (wo, machine)`, model types, pairs); the DISCREPANCY-1 xfail was removed and it passes. Re-checked: `--runxfail` (the 5 BUG xfails fail on Then 1), reference plugin 70 passed (its tuple conversion is no longer needed but harmless), 3 plain runs `65 passed, 5 xfailed`, branch coverage 98% (line 118 unreachable, unchanged), ruff clean, LF.
- **Verifier fixes (2026-11-22).** `commit_point(db)` added after the last Given line of the 48 database tests that lacked it: CR-01–23, CR-26, UW-01–15, DM-03–11 (inserted before the When statement, above any leading comment; the cards' Conventions require it). The module docstring now names Revision 3. Re-checked: 3 plain runs `65 passed, 5 xfailed`; `--runxfail` 5 failed, each on Then 1; reference plugin 70 passed; branch coverage 98% (line 118 unreachable); ruff clean; LF.
- **Revision 3a (2026-11-22).** DM-03 rebuilt to the new card. It adds M3. M1 gets its orders in descending date order (END, MID, START, MID), M2 in ascending order (START IN_PROGRESS, END), and M3 out of order (MID, START, END, factory F2). It calls with `[M1, M2, M3]`, expects all three lists, and gains Then 3 (`all(v == sorted(v) ...)`). Re-checked: 3 plain runs gave `65 passed, 5 xfailed`; `--runxfail` gives 5 failed; the reference plugin gives 70 passed; branch coverage 98% (line 118 unreachable); ruff clean; LF.
