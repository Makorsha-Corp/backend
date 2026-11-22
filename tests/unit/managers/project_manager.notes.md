# Execution notes — `app/managers/project_manager.py`

> Cases: `tests/unit/managers/project_manager.cases.md` (revision 2, 2026-11-04) · Tests: `tests/unit/managers/test_project_manager.py` · Source commit: e48a092
> Result: 280 of 280 cases implemented · 234 passed · 46 xfailed as designed (43 strict, 3 non-strict) · 0 discrepancies · 0 errors — branch coverage 100% (207 statements, 64 branches)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_project_manager.py -q -p no:cacheprovider`

## How the tests are built
Normal mode: no local model. Every card is one test, or one `pytest.param(id="PRJM-…")` where cards share setup and checks and differ in one input (PV-05 … PV-14, CA-26 … CA-28, FF-02 … FF-07, AM-06 … AM-11, C-13/14, C-16/17, C-20/21, C-22/23, C-24/25, U-17 … U-20, U-21 … U-24, U-30/31). 279 tests are collected, one per case ID. Each has the card's rules in its docstring and a `# Then N` comment before the checks of Then line N (before the `with pytest.raises` for a `raises:` line). The three cards marked `Author: claude` (LM-03, L-09, L-10) carry `# [claude] <ID>`.

- **Names:** card names are kept: the standing rows are attributes of the fixture `S` (`S.W1`, `S.UG`, `S.F1`, `S.FD` …); Given rows are local variables with the card's name (`P`, `P9`, `MX`, `H1` …). `PM`, `MISSING`, `T0` … `T3`, `NOW`, `XID(k)`, `val`, `idset`, `names` are module-level, as in Conventions.
- **Standing rows:** fixture `S`, built in Conventions order (W0, W1, W2, U1, U2, UG, the three memberships, F0, F1, F2, FI, FD, F9), each flushed. Tests of pure helpers whose card has no database step (`_visibility_value`, `_format_field_value`, most of `_collect_field_changes`, PV-18, U-12, U-21 … U-31 schema cards) do not request it.
- **Clock:** autouse fixture `clock` patches `app.managers.project_manager.utcnow` to NOW in every test (Externals). Nothing else is patched, except `db.commit` wrapped by `patch.object(..., wraps=db.commit)` in the eight "Rolled back" cards (LC-09, LE-10, AM-18, RM-13, SV-08, C-27, D-08, U-33).
- **Given builders:** `proj(db, S, name, where="W1"|"W0"|"W2", private=, deleted=, **but)` (W0 proj → F0, W2 proj → F9; "deleted" = `is_deleted True, deleted_at T0, deleted_by U1`), `member(db, S, U, role, status=, ws=)`, `pmem(db, S, P, U, **but)`, `comp(db, P, name, **but)`, `ev(db, P, type, at, by)`, `bulk(db, S, n, p)` (one `insert(Project)` then `expire_all`), `set_owner(db, W, U)`. Invalid-data rows the cards spell out (CA-18, EV-02, RC-08) are `_add(db, Model(...))` in the test.
- **Named checks:** `snap` (after `db.refresh`) / `unchanged` (after `expire_all`, every mapped column compared) for unchanged(X); `counts(db)` = row counts of projects, project_members, project_events, project_components for "nothing written", taken before the call; `events_of`, `members_of` (expire, then by `id`); `reread`; `n_rows(db, Model, W)` for "count: rows with workspace_id == W". `recorder(db)` returns the statement list and a stop function, stopped right after the When.
- **Database errors:** `with pytest.raises(DataError):` around `with db.begin_nested():` (LE-05, L-29); LE-08 / LE-09 wrap as their When says (`pytest.raises(HTTPException)` then `begin_nested`).
- **EV-08 (BUG-1964):** the call's argument values (`P.id`, `W1.id`, `UG.id`) are read into locals before step 4's `db.expire_all()`. Reading `S.W1.id` / `S.UG.id` after the expiry refreshes those rows and puts 2 extra statements in the recorder (8 instead of the card's 6), which would also make the fixed code fail the `<= 3`. With the ids read first, today's count is 6, exactly the card's "6 statements besides the project read", and the reference fix gives 2.

## Fails-today check
`--runxfail` with a recording plugin (scratch `then_check.py` / `then_report.py`), mapping each failing line to its `# Then N`:
- all 46 xfail cards fail, each in the Then line its card names (0 mismatches), and the failing values match the cards' parentheses (read one by one): e.g. L-24 `['Zulu', 'apple', 'Banana']`, U-32 `'1000.5'`, EV-08 `6 <= 3`, LE-08 / LE-09 `IntegrityError` (ForeignKeyViolation), G-07 `TypeError` (no `include_deleted`).
- 0 xfail cards pass today. No `Fails today on` line is wrong.

## Reference-fix run
Scratch plugin `ref_fix_project.py` (in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\mgr6e\project\`, loaded with `-p` and `PYTHONPATH`) monkeypatches, in-process only, the intended behaviour of every xfail bug: BUG-1278 / 1954 (`require_project_access(include_deleted=False)`, `get_project(include_deleted=)`; `list_events`, `update_project`, `set_visibility`, `delete_project` still receive a deleted project), BUG-1192 (`log_event` checks the project in the workspace), BUG-1964 (profiles in one `IN` read), BUG-1274 (member DAO order `assigned_at, id`), BUG-1951 / 1953 / 1962 / 1963 (fixed `ProjectCreate` / `ProjectUpdate`: stripped non-blank name, nulls refused for name/description/priority/status, `budget ge=0, max_digits=15, decimal_places=2`), BUG-1952 (stamp only when a field changes), BUG-1953 (`exclude_unset` only), BUG-1963 (budget quantized to 2 places before the change list), BUG-1955 … 1960 (one filtered query: live projects of live factories, factory `is not None`, factory AND status, access filter in SQL, `lower(name), id`, then paging).
Result with `--runxfail`: **279 passed** — every check after each failure point holds once the bug is fixed.

## Stability
5 full runs of the final file: 3 plain, 1 with `PGOPTIONS="-c enable_seqscan=off"` (confirmed with `SHOW enable_seqscan` → `off`), 1 with `-c enable_indexscan=off -c enable_bitmapscan=off`. Every run: 233 passed, 46 xfailed, same outcome per test. The 3 non-strict cards (LM-03, L-09, L-10) stayed xfailed in every run; they rest on physical row order (no tie-break / no `ORDER BY` in the filtered DAO reads), so the runs show no flip, not that one cannot happen.

Ruff: all checks pass. File-level `noqa: SIM117, FURB157` (Conventions' nested `with`; budgets written as the cards write them, `Decimal("0")`, `Decimal("1000")`); `DTZ001` on naive datetimes as in the other files. Line endings LF.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage.

## Factories added
None.

## Notes for maintainers
- When a bug is fixed its strict xfail tests XPASS (fail): remove the marker. BUG-1278 → RC-09, LM-06, AM-17, RM-12; BUG-1954 → G-06, G-07 (G-07 needs the `include_deleted` parameter); BUG-1192 → LE-06 … LE-09; BUG-1964 → EV-08; BUG-1951 → C-12, C-13, C-14, U-26, U-27; BUG-1952 → U-06, U-08; BUG-1953 → U-17 … U-24; BUG-1955 → L-19, L-20; BUG-1956 → L-22; BUG-1957 → L-24, L-25; BUG-1958 → L-07, L-08 (and non-strict L-09, L-10); BUG-1959 → L-13; BUG-1960 → L-14; BUG-1962 → C-22, C-23, U-29; BUG-1963 → C-24, C-25, U-30, U-31, U-32. BUG-1274 (DAO) → non-strict LM-03.
- The schema cards build `ProjectCreate` / `ProjectUpdate` directly; the fix for BUG-1951/1953/1962/1963 belongs in `app/schemas/project.py`.
- XID(k) ids (RC-01, RC-02, LC-01) are explicit and pid-based; they never collide with sequence ids.
- No new bugs found (BUG-2020 … 2029 unused).

## Revision history
- **2026-11-04 — Revision 2** (cases revision 2; `project_manager.verify.md` Findings 1–5, all `case-missing`).
  - **What changed:** a `session:` check now comes right after the `pytest.raises` block and before the `unchanged` re-read in seven cards. Later `# Then` comments were renumbered. No other test changed.
    - SV-04, SV-05, D-05: `P not in db.dirty and not db.new`.
    - AM-12, AM-13: `not db.new and not db.dirty`.
    - RM-05, RM-06: `not db.deleted and not db.new`.
  - **New test:** PRJM-CA-33. A private W2 project with UG's member row filed under W2, asked for with W1, returns `False`. It passes.
  - **Mutation check:** a scratch plugin (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\mgr6e\project\rev2_variant.py`) wraps `set_visibility`, `delete_project`, `add_member` and `remove_member`. Before the HTTPException leaves, it leaves one unflushed change. Every catch fails on the card's new Then 4 line. A card passes only when its own `session:` line does not cover that kind of change, as the cards intend.
    - Dirty project: fails SV-04, SV-05, D-05, AM-12, AM-13. RM-05 and RM-06 do not check `dirty`.
    - Pending add: fails all 7.
    - Pending delete: fails RM-05 and RM-06. The other five do not check `deleted`.
  - **Runs:** 3 plain runs gave 234 passed and 46 xfailed each time. Branch coverage is still 100%. Ruff is clean and the file is LF.
