# Execution notes — `app/managers/machine_item_manager.py`

> Cases: `tests/unit/managers/machine_item_manager.cases.md` (revision 5) · Tests: `tests/unit/managers/test_machine_item_manager.py` · Source commit: e48a092
> Result: 490 of 490 cases implemented · 280 passed · 210 xfail as designed (202 strict, all xfailed; 8 non-strict: 5 always xfail, L-24, L-36, L-58 xfail or xpass from run to run, see Stability) · 0 errors · 0 discrepancies open (2 closed by cases revision 3) — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_machine_item_manager.py -q -p no:cacheprovider`

## How the tests are built
Normal mode: no local model. Every test carries `# [claude] <ID>`, a `# Then N` comment per Then line, and the card's rules in its docstring. MIM-D-31 is retired and has no test.

The test bodies were produced in one pass by a throwaway script that translates each card's Given, When and Then lines. The script is not in the repo. It stops on any line it does not recognise, so no card line was skipped silently. A separate check compared every card with its test: Then numbers in order, marker and bug, every quoted string and every compared number. The file is plain pytest code, to be maintained by hand from now on.

- **Names:** a card's row names are the lower-case names here (`M1` → `m1`, `MI` → `mi`, `PO1` → `po1`). `M`, `MISSING`, `T9` … `T12` are module-level.
- **Standing rows:** chained fixtures in Conventions order (`w1` … `st9`, ending in the autouse `standing_rows`), so every test has them and ids rise in that order.
- **Given rows:** `mk_item`, `mk_stock(machine, item, qty, **but)`, `bulk(n)`, `mk_entry(machine, item, performed_at, avg_price_after, **but)`, `mk_activity`, `mk_order(machine, "O1", status, **but)`, `mk_source_line`, `mk_replace_line`, `mk_transfer("TO1", **but)`, `mk_to_line`, `mk_po("PO1", **but)`, `mk_po_line`, `mk_return(po, "RT1", **but)`, `mk_return_line(rt, pol, **but)`. Each inserts one row and flushes. `but` is the card's "but" list, column by column. A Given name no later line reads gets no variable.
- **Reading helpers:** `reread`; `snap_before` (after `db.refresh`) and `snap` (after `db.expire_all`), both reading the table directly; `count_rows`; `written`; `entries_of`; `events_of(db, machine, event_type=None)`, the optional argument being the card's "with" filter; `ids`; `names`. Helpers hold no assertion.
- **"the `X` row":** `[row] = events_of(db, m1, event_type="X")`, so anything but exactly one row fails there.
- **Ids after a delete:** in the delete cards `mi_id = mi.id` is read right after the Given, and Thens use `mi_id`.
- **Refusals before a write:** plain `pytest.raises`. **Database errors:** `with pytest.raises(...)` around `with db.begin_nested():`, `as exc` only if a later line reads it.
- **Rolled back:** `sp = db.begin_nested()`, `spy = commit_spy(db, monkeypatch)`, then `sp.rollback()` at the first "after the savepoint rollback" Then.
- **Race simulation:** MIM-C-25 only, `patch.object(M.machine_item_dao, "get_by_machine_and_item", return_value=None)` inside `pytest.raises`, around `db.begin_nested()`. Nothing else is patched in the file.
- **sql_log:** `with record_sql(db) as sql_log:` around the call; it is the last Given line in all three cards.
- **BUG-1040 cards:** `lg = mk_entry(... Decimal("0.125") ...)  # noqa: F841`. The variable is what keeps the unexpired object alive, so it stays although nothing reads it. None of these cards takes a snapshot of LG; the script stops if one does, because `db.refresh` would end the recipe.
- **`next_clock_tick()`:** Conventions and the Given lines of MIM-W-21 … W-25 (cases revision 3). It waits on the real clock and patches nothing.
- `result = _machine_out(...)` in MIM-W-25 is kept as the card writes it, though nothing reads it (`noqa: F841`).

## Fails-today check
Every xfail was run with `--runxfail`, and the failing line was mapped to its `# Then N` comment:
- 202 strict cards: 198 fail inside the Then their card names; 4 (G-07, G-09, G-11, G-12) fail in the When call just before `# Then 1`, with the `TypeError` their card names. Every failing value was read against the card's parenthesis, grouped by card wording. No mismatch. No failure in setup. `BUG-1040` cards fail on `0.00` (BUG-993 first), as their cards say.
- 8 non-strict cards: L-02, L-46, L-55, L-56, L-57 fail at Then 1 in every run. L-24, L-36, L-58 passed in the `--runxfail` runs and fail in some plain runs (physical order, see Stability), so the wrong-order plugin is their proof.

**Non-strict proof, explicit wrong `ORDER BY` in a scratch plugin on both DAO list paths:**

| Order forced | Fails at Then 1 |
|---|---|
| `qty ASC, id ASC` | L-02, L-24, L-36, L-46, L-55, L-56, L-57 |
| `id DESC` | L-02, L-55, L-56, L-58 |

So all 8 fail at the Then their card names, with the card's reason. L-24 and L-36 show `[A, A, B]`: a repeat and a miss, which is what the cards describe.

## Reference run
Lines after an xfail's failure point never run today, and 95 BUG-1081 cards stop at Then 1. So a scratch plugin (`refplug.py`, not in the repo, nothing under `app/` touched) replaced the two input schemas and six manager methods at run time with the spec's intended behaviour, written from the spec alone: both list paths, every refusal, BUG-993 with half-up rounding, all four blocker kinds, `FOR UPDATE OF machine_items`. The unique index of BUG-983 is stood in for by a raw lookup the race patch does not reach.

Result with `--runxfail`: 479 passed, 1 failed on the first run; that one was DISCREPANCY-2, a `NameError` in the test. After the fix, and again on the revision 3 file, 480 passed, 0 failed. On the revision 5 file, with the plugin unchanged, **490 passed, 0 failed**: every line of every card has run. A reference written from the same spec cannot prove the spec right; it proves the lines run and that the cards agree with each other and with the spec.

## Stability
Revision 5 file: 3 plain runs plus the two forced plans of revision 2. All 3 plain runs and the seqscan run gave 280 passed, 208 xfailed, 2 xpassed (L-24, L-36); indexscan off gave 280 passed, 209 xfailed, 1 xpassed (L-58). Only L-24, L-36, L-58 moved; the other 487 tests were the same in all 5 runs. Ruff passes, line endings are LF.

Revision 3 file: 3 plain runs, each 279 passed, 198 xfailed, 3 xpassed (L-24, L-36, L-58); `--runxfail` gives the same failures, with MIM-U-25 still at Then 2 (`assert 7 is None`). Ruff passes.

Revision 2 file: 8 plain runs plus one with `PGOPTIONS="-c enable_seqscan=off"` and one with `PGOPTIONS="-c enable_indexscan=off -c enable_bitmapscan=off"`. `SHOW` confirmed `PGOPTIONS` reaches the session.
- The 472 tests that are not L-24, L-36, L-58 had the same outcome in all 10 runs: 279 passed, 193 strict and 5 non-strict xfailed.
- L-24, L-36, L-58 are non-strict and moved, with no forcing: 199 to 200 xfailed and 1 to 2 xpassed in the 8 plain runs, 3 xpassed under seqscan off, 1 under indexscan off. An earlier full set on the same test bodies gave 3 xpassed in all 8 plain runs, 1 under indexscan off. The order of these rows really does change, so these three cards are right to be non-strict.
- Ruff: all checks pass. Line endings are LF.

## Discrepancies
None open. DISCREPANCY-1 and DISCREPANCY-2 were closed by cases revision 3; see Revision history.

No `Fails today on` line was wrong. No new bug: the ties are BUG-664 and BUG-641.

## Coverage gaps
None — 100% branch coverage (78 statements, 24 branches) of `app/managers/machine_item_manager.py`.

## Factories added
None.

## Revision history
- **Cases revision 3:** closes both discrepancies of revision 2.
  - **DISCREPANCY-1 (flaky), MIM-W-21 … W-25:** without a wait, W-22, W-24, W-25 sometimes XPASSed and W-23 sometimes failed: 5 of 6 runs of these cards had one or more flips, and the first full run failed on an XPASS of W-22. Two entries written with the real clock could share `performed_at`, because Python 3.12 on Windows gave about 56 distinct `datetime.now` values in 0.2 s, and `get_latest_entry` / `calculate_balance` could then read the older one (BUG-664, BUG-641). The cards now carry the `next_clock_tick()` Given line the tests already had; no test changed. With BUG-664 and BUG-641 fixed (ties by `id`), the helper can go.
  - **DISCREPANCY-2 (card gap), MIM-U-25:** "that row" had no row counted before it; the reference run found it as a `NameError`, hidden today by the Then 2 failure. New Then 4 counts one event and the old Then 4 is Then 5. The test now has `rows = events_of(db, m1)`, `assert len(rows) == 1` under `# Then 4` and `rows[0].metadata_json` under `# Then 5`, in place of `[row] = events_of(db, m1)`. No other test changed.

- **Cases revisions 4 and 5:** added MIM-L-67 … L-70, W-33, D-246 … D-250. A diff against the revision 3 file shows only added lines, and no fixture changed. L-67, L-68 (BUG-1070), L-69, L-70 (BUG-1086), D-247 … D-250 (BUG-1081) are strict xfail and fail at Then 1: the list cards return the two hidden rows instead of `[B.id]`, the delete cards do not raise. W-33 is strict xfail BUG-1040 and fails at Then 2 on `0.00` against `0.13`. D-246 passes. The reference plugin needed no change: it already applies R5 (a) whatever the `action_type`, filters before paging, and removes the duplicate entry of D-250.

## Notes for maintainers
- When a BUG-NNN is fixed, its strict xfails turn into failures (XPASS): remove the marker. The marker's reason names the bug.
- **BUG-1040 cards** (W-08, W-09, W-32, W-33, U-39) stop at BUG-993's `0.00` today. They need both bugs fixed; the marker's reason says so.
- **BUG-1081:** the 95 cards stop at Then 1 today. Their blocker lists have run only against the scratch reference, so expect to review them when the bug is fixed. Many non-blocking pass cards pass today only because `delete_machine_item` looks at nothing yet; their value starts with that fix.
- **BUG-983:** MIM-C-25 builds a row, then races past the check. A fix through the unique index must turn the violation into the 409 inside `db.begin_nested()`.
- **`MachineItemUpdate`:** `qty: null` must be refused only when sent explicitly; omitted stays valid (MIM-U-26 against the many `MachineItemUpdate(req_qty=...)` calls).
- **Counts:** "nothing written" and the `count:` lines read all workspaces, so `marker_test` must hold no committed rows in those three tables.
- `bulk(101)` adds 202 rows; the whole file takes about 15 s.
