# Execution notes — `app/managers/machine_maintenance_log_manager.py`

> Cases: `tests/unit/managers/machine_maintenance_log_manager.cases.md` (revision 1; 397 cases) · Tests: `tests/unit/managers/test_machine_maintenance_log_manager.py` · Source commit: e48a092
> Result: 397 of 397 cases implemented · 283 passed · 114 xfail as designed (106 strict, all xfailed; 8 non-strict: L-120 … L-123 always xfail, L-124 … L-127 xfail or xpass by query plan, see Stability) · 0 errors · 0 discrepancies — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_machine_maintenance_log_manager.py -q -p no:cacheprovider`

## How the tests are built
Normal mode: no local model. Every test carries `# [claude] <ID>`, a `# Then N` comment per Then line, and the card's rules in its docstring.

The test bodies were produced in one pass by a throwaway script that translates each card's Given, When and Then lines. The script is not in the repo. It stops on any line it does not recognise, so no card line was skipped silently. A separate check read the test file back and compared it with every card: test order, marker and bug, Then numbers, a check in every Then block, every quoted string, the When call, unused fixtures and variables. The file is plain pytest code, to be maintained by hand from now on.

- **Names:** a card's row names are the lower-case names here (`M1` → `m1`, `A` → `a`, `M9D` → `m9d`). `M`, `LC`, `LU`, `LR`, `REPAIR`, `MISSING`, `D1` … `D3`, `T0`, `NOW` are module-level.
- **Standing rows:** chained fixtures in Conventions order (`w1` … `m9`, ending in the autouse `standing_rows`), so every test has them and ids rise in that order.
- **Given rows:** `mk_log(gone=False, **but)` inserts, flushes and refreshes one log; `gone=True` is the card word "gone". `mk_pending()` is the pending log Q, added last, after the snapshots. `bulk101()` returns the 101 rows. `same_machine(db, m1, name, **but)`, `same_factory(db, f1, name, abbreviation, **but)` are "the same as …". E1 is a direct `MachineActivityEvent`. A Given name no later line reads gets no variable.
- **Reading helpers:** `reread`; `snap_before` and `snap` read the table directly and take the card's "except" columns, so a snapshot leaves the instance as it is; `count_rows`; `written`; `events_of`; `ids` (in the order returned, as Conventions say). Helpers hold no assertion.
- **"that row":** `evs = events_of(db, m1)`, `assert len(evs) == 1`, then `evs[0]`.
- **Refusals:** plain `pytest.raises(HTTPException)`. **Database errors:** `with pytest.raises(...)` around `with db.begin_nested():`, `as exc` only if a later line reads it. **Schema refusals:** the schema is built inside `pytest.raises(ValidationError)`; the manager is not called.
- **Rolled back:** `sp = db.begin_nested()`, `spy = commit_spy(db, monkeypatch)`, `sp.rollback()` at the first "after the savepoint rollback" Then.
- **sql_log:** `with record_sql(db) as sql_log:` around the call, then `sql = last_sql(sql_log)`, `order_part = order_part_of(sql)`.
- **Clock patch:** MMLM-D-19 only, `patch("app.dao.machine_maintenance_log.utcnow", create=True, return_value=NOW)` around the When. Nothing else is patched.
- **`noqa`:** `FURB157` on the When lines with `Decimal("-5")` and the like, which keep the card's text; `F841` on MMLM-U-103, whose card writes `result =` and reads nothing from it.

## Fails-today check
Every xfail was run with `--runxfail`, and the failing line was mapped to its `# Then N` comment:
- 110 cards failed in the plain plan: 103 inside the Then their card names, 7 (C-38, U-54, U-55, U-113, G-11, G-12, D-32) in the When call just before `# Then 1`, with the `DataError`, `IntegrityError` or `TypeError` their card names. Every failing value was read against the card's parenthesis, grouped by card wording. No mismatch. No failure in setup.
- Sample of the values read: U-70 `'-0' == '0.00'`, U-67 `'1E+3' == '1000.00'`, D-19 today's clock against `NOW`, U-11 and D-09 `400 == 404`, L-128 … L-131 the `ORDER BY` with no `id` key.
- L-124 … L-127 (non-strict) passed in that run: physical order matched. They fail at Then 2 with index scans off (`assert [c.id] == [b.id]`) and in the proof below.

**Non-strict proof, explicit wrong `ORDER BY` in a scratch plugin on all four DAO list paths:**

| Tie-break forced | Fails at Then 2 |
|---|---|
| `id ASC` | L-120, L-121, L-122, L-123 |
| `summary ASC, id ASC` | L-120 … L-127 |

`id ASC` cannot catch L-124 … L-127: B is the middle row whichever way ids run. `summary ASC` puts the edited A last, `[B, C, A]`, which is the physical order the cards describe, and the window then shows C. So all 8 fail at the Then their card names, with the card's reason.

## Reference run
Lines after an xfail's failure point never run today. So a scratch plugin (`refplug.py`, not in the repo, nothing under `app/` touched) replaced at run time the two input schemas, six DAO methods and four manager methods with the spec's intended behaviour: every BUG of this module, including `get_log(include_deleted=...)`, the stored form of `cost` in `changes`, the no-op that writes nothing, and the read of the machine's workspace.

Result with `--runxfail`: **394 passed, 0 failed**, on the first run; on the revision 1 file, **397 passed, 0 failed**. Every line of every card has run, the two-bug cards with both fixes in place. The spec gaps 1, 2 and 4, accepted under delegation on 2026-10-31, are implemented as designed and pass there: `5.0010`, `10000000000000.00` refused, `9999999999999.990` accepted; `-0` on update gives `0.00`; a row both deleted and on another workspace's machine gets the 404. A reference written from the same spec cannot prove the spec right; it proves the lines run and that the cards agree with each other and with the spec.

## Stability
Revision 1 file: 3 plain runs and seqscan off, each 283 passed, 110 xfailed, 4 xpassed (L-124 … L-127); indexscan and bitmapscan off, 283 passed, 114 xfailed. Ruff passes.

Revision 0 file, 394 tests: 8 plain runs plus one with `PGOPTIONS="-c enable_seqscan=off"` and one with `PGOPTIONS="-c enable_indexscan=off -c enable_bitmapscan=off"`. `SHOW` confirmed `PGOPTIONS` reaches the session.
- The 390 tests that are not L-124 … L-127 had the same outcome in all 10 runs: 280 passed, 106 strict and 4 non-strict xfailed.
- L-124 … L-127 are non-strict and moved with no forcing: 4 xpassed in 7 plain runs and under seqscan off, 3 xpassed and L-127 xfailed in one plain run, all 4 xfailed under indexscan off. These four cards are right to be non-strict.
- Ruff: all checks pass. Line endings are LF.

## Discrepancies
None.

No `Fails today on` line was wrong. No new bug.

## Coverage gaps
None — 100% branch coverage, unchanged on revision 1 (63 statements, 22 branches) of `app/managers/machine_maintenance_log_manager.py`.

## Factories added
None.

## Notes for maintainers
- When a BUG is fixed, its strict xfails XPASS: remove the marker. The padded-no-change cards need BUG-1151 as well as BUG-1155 or BUG-1156, and the `include_deleted=True` cards of BUG-1101 need BUG-1150 as well; they stay xfail until both are fixed.
- A BUG-1157 fix that formats only `to_value` passes every card, by design (cases Spec gap 3).
- `cost` limits: C-48, C-52, C-56, U-82, U-86, U-90 assume `ge=0, max_digits=15, decimal_places=2`. If the fix uses other limits, look at these first (cases Spec gap 1).
- `count:` lines count all workspaces, so a row committed to `marker_test` by anything else would fail them. None exists today.
- The module has 7 `FURB157` / `F841` `noqa` comments; keep them while the cards keep those literals.

## Revision history
- **Revision 1 (2026-11-01):** cases revision 1, from `machine_maintenance_log_manager.verify.md` findings 1 and 2. Added MMLM-U-121, MMLM-L-136, MMLM-L-137, all designed `pass`, all passed, no marker. The diff against the earlier file is 45 inserted lines: no existing test changed, none retired. Finding 3 was not taken by the designer. The 280 and 106 counts under Stability are revision 0's.
