# Execution notes — `app/managers/machine_manager.py`

> Cases: `tests/unit/managers/machine_manager.cases.md` (revision 5) · Tests: `tests/unit/managers/test_machine_manager.py` · Source commit: e48a092
> Result: 478 of 478 cases implemented · 304 passed · 174 xfailed as designed · 0 discrepancies · 0 errors — branch coverage 99% (the one missed line is dead code)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_machine_manager.py -q -p no:cacheprovider`

## How the tests are built
Normal mode: no local model. Every test carries `# [claude] <ID>`, a `# Then N` comment per Then line, and the card's rules in its docstring.

The test bodies were produced in one pass by a throwaway script that translates each card's Given, When and Then lines. The script is not in the repo. It stops on any line it does not recognise, so no card line was skipped silently; all cards translated. The file is plain pytest code, to be maintained by hand from now on; no generator needs re-running.

- **Names:** a card's row names are the lower-case names here (`M1` → `m1`, `F1.id` → `f1.id`, `O1` → `o1`). `M`, `MISSING`, `T0`, `T1`, `T2`, `NOW`, `IDLE`, `RUNNING`, `OFF`, `MAINTENANCE` and `D(n)` are module-level, as in Conventions.
- **Standing rows:** chained fixtures in Conventions order (`w1` … `stc`, ending in the autouse `standing_rows`), so every test has them and ids rise in that order. `standing_rows` also patches `app.dao.machine.utcnow` to NOW.
- **Given rows:** `mk_machine("M1", **but)` or `mk_machine(name=..., **but)`, `bulk(n, p, **but)` (returns the names), `machine_named(db, name)`, `mk_link`, `mk_status_row`, `mk_order(machine, "O1", ...)`, `mk_line`, `mk_approver`, `mk_assignee`, `mk_stock`, `mk_po("PO1", ...)`, `mk_to("TO1", ...)`, `mk_stock_movement()`, `mk_i9()`, `mk_ix()`, `mk_st9()`, `mk_stc9()`. Rows the cards spell out column by column (maintenance log, ledger, template, line, formula, stage) are `_add(db, Class(...))` in the test. Each builder inserts one row and flushes.
- **Reading helpers:** `reread`; `snap_before` (the "unchanged" snapshot, after `db.refresh`) and `snap` (after `db.expire_all`), both reading the table directly; `count_rows(db, table, **filters)`; `written` (the five "nothing written" tables); `links_of`, `events_of`, `wo_events`, `names`, `ids` (sorted).
- **Patches:** `app.dao.machine.utcnow` in every test. `MachineManager._check_name_exists_in_factory` in C-41 and U-51 only (Race simulations). Nothing else; `date` is never patched.
- **Refused after flush and Rolled back cards:** `sp = db.begin_nested()` right before the call, snapshots before it, `commit_spy(db, monkeypatch)` for the rolled-back cards, `sp.rollback()` at the first "after the savepoint rollback" Then.
- **Database errors:** `with pytest.raises(...)` around `with db.begin_nested():`, with `as exc` only if a later line reads `exc.value`.
- **`session:` lines (D-41):** run on `db` before the re-read: `assert m1 not in db.dirty`, then a bare `db.flush()`.
- **sql_log:** `with record_sql(db) as sql_log:` around the call. In S-112 and E-38 it is the last Given line, so starting it there and starting it at the `with` are the same.
- **Spec gap 11:** `maintenance_type = list(MaintenanceTypeEnum)[0]`, which is `MaintenanceTypeEnum.PREVENTIVE`, imported from `app.models.enums` (members `PREVENTIVE`, `REPAIR`, `EMERGENCY`, `INSPECTION`). `maintenance_date = D(0)`, a `datetime.date`; the column is `Date`, NOT NULL. D-42 is the only card using them and it passes.

## Fails-today check
Every xfail was run with `--runxfail`, and the failing line was mapped to its `# Then N` comment:
- 168 of the 174 fail inside the Then their card names, and each failing value matches the card's parenthesis (read one by one).
- 6 fail in the When call, just before the `# Then 1` comment. Each of these cards says so itself ("the call raises ..."), so they are correct and not mismatches: U-75 (`HTTPException` 400), U-134 (`IntegrityError`), G-06, G-09 (`TypeError`, no `include_deleted` yet), S-12, S-39 (`AttributeError`).
- 0 xfail cards passed. No `Fails today on` line was wrong.

## Stability
Revision 5, final file: 5 full runs (3 plain, 1 with `PGOPTIONS="-c enable_seqscan=off"`, 1 with `PGOPTIONS="-c enable_indexscan=off -c enable_bitmapscan=off"`). Every run gave 304 passed, 174 xfailed, with the same outcome for every test.

Earlier revisions: 12 full runs on revision 1 (8 plain, 2 of each forced plan) and 5 each on revisions 2, 3 and 4, every test the same across the runs of a revision. `SHOW` confirmed that `PGOPTIONS` reaches the session.

The 6 non-strict cards (S-88, S-107 … S-111) stayed xfailed in all 32 runs: none flipped. They stay non-strict as designed, for two different reasons. S-107 … S-111: `get_by_workspace` has no `ORDER BY` (BUG-100, not new), and these two forced plans still return the rows of a small table in physical order. S-88: the order comes from the collation, not from the plan. So the runs show no flip, not that a flip cannot happen.

Ruff: all checks pass. Three `noqa` lines keep card text as written: `loaded = ...` (F841, U-63, U-64), `re.S` (FURB167, S-112), `list(MaintenanceTypeEnum)[0]` (RUF015, D-42). Line endings are LF.

## Discrepancies
None. DISCREPANCY-1 (MCM-S-35, a card fault) and the two card notes of revision 1 were closed by cases revision 2.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 307 | dead | `if maintenance_window == "all": return True` inside `matches_window`. The function runs only when the window is not `"all"`. Spec P9, on the dead-code list (the spec cites the `if` on line 306). |

## Factories added
None.

## Revision history
- **Cases revision 2:** MCM-S-35: MK's manufacturer is now "Bosch" and the DISCREPANCY-1 marker is removed; the card passes. MCM-U-121: commit spy dropped. MCM-D-41: Then 5 and 6 added (`session:` lines), later lines renumbered. Added MCM-D-61 … D-68 and fixture `mk_stc9`; D-61, D-62, D-63, D-64, D-68 are strict xfail BUG-968 and fail at Then 1; D-65, D-66, D-67 pass. A diff against the revision 1 file shows no other test changed. Schema imports were already right.
- **Cases revision 3:** added MCM-D-69 … D-77 (spec gap 12). D-69 … D-74 and D-77 are strict xfail BUG-968 and fail at Then 1; D-75, D-76 pass. `mk_line` already defaulted to `uses_inventory=True`, as the Convention says; only D-76 overrides it. D-77 builds `mk_order(m1, "O1", ..., machine_id=None)`, as the card says. No fixture changed, and a diff against the revision 2 file shows only added tests.

- **Cases revision 4:** 17 cards changed: D-55 … D-63 (blocker list now uses the `{"type": "other_workspace"}` entry), E-10, E-17, E-27 (a real order instead of id `77`), E-11, E-28 (id `0` is now a 404, strict xfail BUG-1000), E-07, E-08, E-16, E-39 (Errors row number only). Added D-78 … D-90, E-41 … E-44, U-138, U-139, S-114, S-115 and fixture `mk_ix`. New xfails: D-78, D-79, D-80, D-82 … D-90 and E-41, E-42 fail at Then 1, E-43 at Then 2 (400 against 404), U-138 at Then 2 (the order keeps FI); E-11, E-28 at Then 1. New passes: D-81, E-44, U-139, S-114, S-115. A diff against the revision 3 file shows no other test changed.
- **Cases revision 5:** added MCM-D-91 … D-98 and E-45; no other card changed, and a diff against the revision 4 file shows only added lines. No fixture changed. D-95 … D-98 are strict xfail BUG-968 and E-45 is strict xfail BUG-1000; all five fail at Then 1. D-91 … D-94 pass.

## Notes for maintainers
- When a BUG-NNN is fixed, its strict xfails turn into failures (XPASS): remove the marker. The marker's reason names the bug.
- **BUG-953:** C-37, C-38, C-41, U-51 become passing with the unique index. The cards never build two live same-named machines of one factory, so setups stay valid.
- **BUG-950 + BUG-952:** C-33 passes only when both are fixed (gap 4): the detail must read `'Lathe'`.
- **BUG-968:** all 50 cards stop at Then 1 today, so their blocker lists, including the `other_workspace` entry, have not run yet. Expect to review those Thens when the bug is fixed.
- **D-91 … D-94** pass today only because `delete_machine` looks at nothing yet. Their value starts when BUG-968 is fixed: each then proves that a foreign row meeting no condition does not block.
- **BUG-955, BUG-966:** G-06, G-07, G-09 call `include_deleted`, which does not exist yet.
- **`names`** is a local variable in N-11, N-12, N-13 (the card's name) and hides the helper there; those tests do not use the helper.
- **S-40, S-41** insert 10 001 rows, N-11 to N-14 up to 150; the whole file takes about 12 s.
- `D(n)` reads `date.today()` in the test while the manager reads it separately, so a run across midnight could shift a boundary card (FU-9 in the spec).
