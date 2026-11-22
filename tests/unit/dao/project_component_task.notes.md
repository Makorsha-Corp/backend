# Execution notes — `app/dao/project_component_task.py`

> Cases: `tests/unit/dao/project_component_task.cases.md` (Revision 1, READY, 41 cases) · Tests: `tests/unit/dao/test_project_component_task.py` · Source commit: e48a092
> Result: **41 tests for 41 cases — 34 passed · 7 xfailed · 0 discrepancies · 0 errors** — branch coverage 100% line and branch (13 statements, 2 branches). Non-strict cards may XPASS without turning the run red: forced plans 1 or 2 gave `34 passed, 6 xfailed, 1 xpassed` (PCT-GC-12).
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_project_component_task.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment, written by hand from the cards. An audit script of my own (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\E\check.py`) checked: one test per ID in card order, title in the docstring, `# Then 1..N` matching the card's Then count, marker and bug matching the Expect line, no unused argument. LF only.

## How the tests are built
- **Nothing is patched** (Externals: None).
- **Constants:** `dao`, `MISSING`.
- **Standing rows** (autouse `standing_rows`): `w1`, `w2`, `f1`, `pj1`, `pjd`, `pc1`, `pc2`, `pcd`, each fixture depending on the one before, so ids rise in the Conventions' order.
- **Builders:** `mk_task(name=, **columns)` = "task"; `mk_note(name=, **columns)` = "note" (task, but `is_note=True`); `mk_many(count)` = the 104 rows built with `add_all`.
- `bump(db, row)` = bumpK; `seqscan(db)` = the three `SET LOCAL` lines, in order.
- **Reading helpers (no expected values inside):** `ids(result)`; `stored_count(db)` = "nothing written" (row count, all workspaces), taken after the last Given line.
- **Statement recorder:** `StatementRecorder(db)`, a `before_cursor_execute` listener around the When only; `recorder.sql()` is the one SELECT from `project_component_tasks`, `order_part_of(sql)` the text after the first `ORDER BY` and before `LIMIT`, `recorder.written()` the INSERT/UPDATE/DELETE list.
- **DataError cards:** `with pytest.raises(DataError) as exc:` around `with db.begin_nested():`.
- Row letters are lower case in the code; a Given row no later line names is built without a variable.

## xfail location (`--runxfail`, reading the failing value)
| Card | Strict | Fails on | Actual |
|---|---|---|---|
| PCT-GC-11 | no | Then 2 | `assert [596, 597, 598] == [597, 598, 596]`: Zulu first, physical order |
| PCT-GC-12 | no | Then 2 (default and plans 1, 3, 4, 5; XPASS under plan 2) | `assert [600, 601, 602, 599] == [599, 600, 601, 602]`: bumped lowest id moved last |
| PCT-GC-13 | yes | Then 2, every run | `assert 'ORDER BY' in 'SELECT ... LIMIT %(param_1)s OFFSET %(param_2)s'` |
| PCT-GI-08 | no | Then 2 | `assert [604, 605, 606] == [605, 606, 604]` |
| PCT-GI-09 | yes | Then 2, every run | `assert 'ORDER BY' in '... is_note = false \n LIMIT ...'` |

**Proof plugin.** `e_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\E` (`PYTHONPATH` there, `-p e_plug`, `E_PCT=<mode>`) replaces both list methods in-process with an explicit `ORDER BY`; nothing in `app/` changes. Runs with `--runxfail`:

| `E_PCT` mode (ORDER BY) | Cards that fail | Pass cards that fail |
|---|---|---|
| `fix` — `lower(name), id` (the intended order) | none: all 38 pass, so Then 3 to 6 of GC-13 and GI-09 hold | none |
| `name_desc` — `lower(name) DESC, id` | GC-11, GC-12, GI-08 on Then 2; GC-13, GI-09 on Then 6 | none |
| `created` — `created_at DESC` | GC-11, GC-12, GI-08 on Then 2; GC-13, GI-09 on Then 3 | none |
| `id_only` — `id` | GC-11, GI-08 on Then 2; GC-13, GI-09 on Then 3 | none |
| `id_desc_tie` — `lower(name), id DESC` | GC-12 on Then 2; GC-13, GI-09 on Then 6 | none |
| `note_first` — `is_note, lower(name), id` | GC-11 on Then 2 | none |
| `case_sensitive` — `name, id` | **none** (see below) | none |

So every non-strict card can fail on its Then 2, and no pass card depends on row order. With the markers on and `E_PCT=fix`, GC-13 and GI-09 are `XPASS(strict)`.

## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

**Prose only, for the case designer (no test affected): the case-insensitive part of R4 is not tested on this database.** The test database's collation is `English_United States.1252` (libc), which already sorts `apple < Banana < roof < Roof < Zulu`. A case-sensitive `ORDER BY name, id` therefore passes every card (the `case_sensitive` row above), including GC-11 and GC-12, and GC-13 / GI-09 only look for `"name"` in the order text. Data cannot tell the two apart under this collation, so a card that does needs a check on the SQL (for example `"lower(" in order_part.lower()`).

## Spec gaps of the cases file, checked
None listed. Every column the Conventions name exists; `Project` takes `is_active=False` for PJD as written.

## Coverage gaps
None — 100% line and branch coverage. Run with a private `COVERAGE_FILE`. Inherited `BaseDAO` methods are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
5 default runs, each `33 passed, 5 xfailed`. 5 forced plans via `PGOPTIONS` (1 `enable_seqscan=off`; 2 that plus hash join and nested loop off; 3 `enable_hashjoin=off`; 4 index, bitmap and index-only scans off; 5 that plus hash and merge join off): `33 passed, 5 xfailed` each, except plan 2, which gives `33 passed, 4 xfailed, 1 xpassed` (PCT-GC-12) in each of 4 runs — a non-strict card, allowed by its marker. Database time zones `UTC` and `Asia/Dhaka` (`PGOPTIONS=-c timezone=...`): `33 passed, 5 xfailed`. No card compares a real-clock stamp. `ruff check`: all checks passed.

## Notes for maintainers
- When BUG-1447 is fixed, GC-13 and GI-09 turn the run red: remove the five markers.
- Never read a GC-11 / GC-12 / GI-08 XPASS as the bug being gone: GC-13 and GI-09 are the proof.
- The passing cards compare sets or counts on purpose (no order today).

## Revision history
- **Revision 1 of the cases (project_component_task.verify.md, case-missing findings):** added PCT-GC-23, GI-17 (xfail BUG-1447, non-strict) and GI-18 (pass). With `--runxfail` GC-23 fails on Then 1 (`[67422, 67423, 67424, 67425] == [67425, 67424, 67422, 67423]`), GI-17 likewise; neither XPASSed in any run or plan. Closes the case-insensitivity weak spot noted below. Patched in place, no other test changed. 3 default runs, 5 forced plans (as above) and the database time zones `UTC` and `Asia/Dhaka`, `ruff check` passed, coverage with a private `COVERAGE_FILE`, LF only. Card audit (my own `audit.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\R`): every ID once, in card order, `# Then 1..N` per card, markers as the Expect lines. Reference plugin `attxr_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\R` (`-p attxr_plug`, `ATTXR_MODE=ref`, in-process, nothing in `app/`; covers the seven revised modules): with `--runxfail` all 371 tests of the seven files pass, so the lines past every failure point hold. The verifier's named variants, rebuilt in the same plugin (`ATTXR_MODE=<variant>`, the reference with one change, `--runxfail`, default plan; each asserted applied): `gc_ord_case_sensitive` → GC-23; `gi_ord_case_sensitive` → GI-17; `gi_ws_le` → GI-18. No other test failed under any of them.
