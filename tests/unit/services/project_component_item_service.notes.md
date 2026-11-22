# Execution notes — `app/services/project_component_item_service.py`

> Cases: `tests/unit/services/project_component_item_service.cases.md` (revision 3) · Tests: `tests/unit/services/test_project_component_item_service.py` · Source commit: e48a092
> Result: 68 of 68 cases implemented · 49 passed · 19 xfail as designed (18 strict, all xfailed; 1 non-strict, L-13, xfailed in every run) · 0 errors · 0 discrepancies — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_project_component_item_service.py -q -p no:cacheprovider`

## How the tests are built
Same scaffold as `project_component_note_service.notes.md`, plus the catalog items: fixture `S` adds I0 (W0 "Nut"), I1 (W1 "Bolt", `id=XID(8)`), I9 (W2 "Washer"), IDL (W1 "Old bolt", `is_active=False`), all `unit="pcs"`. One test per card, `# [claude] <ID>`, `# Then N`.
- Given rows: `line(db, S, C, q, **but)` (item I1), `line0` / `line9` (the cards' literal W0 / W2 rows L0 and L9), `pmem`, `commit_point`, `extra_x` (W2, C9, I9, qty 1) and `pending_p` (qty 2, not flushed).
- Checks: as the note file, with `counts` over `project_component_items` and `project_events`, `stock(db)` = row counts of `inventory`, `machine_items`, `project_component_item_ledger` by raw `SELECT count(*)` ("no stock", taken at the commit point), `committed_lines_of(db, component_id)`.
- C-12 uses `pytest.raises(Exception)` as the card says (any exception: `IntegrityError` today, `HTTPException` after BUG-1012); the line carries `# noqa: B017` with that reason. Today the foreign key fails at the DAO's flush and the service's rollback takes the extra row X with it.
- C-11 (xfail BUG-1012) fails today by the `IntegrityError` escaping `pytest.raises(HTTPException)` at Then 1, which is what its card names.
- L-17 / L-18 wrap the call in `db.begin_nested()` inside `pytest.raises(DataError)`.
- No external is patched.

## Fails-today check
`--runxfail` with the scratch `thenmap.py` plugin. Every xfail fails on its card's Then line with the value the card describes:
- L-02 (BUG-2309): Then 1, `DID NOT RAISE HTTPException`.
- L-05, G-08, C-08 (BUG-1278): Then 1, `DID NOT RAISE HTTPException`. L-11 (BUG-1278): Then 1, LD in the set.
- L-12 (BUG-2308): Then 1, `set()`. L-13 (non-strict): Then 1, VD and VE. L-14: Then 2, `5 <= 1`.
- C-09, C-10 (BUG-1012): Then 1, `DID NOT RAISE HTTPException`. C-11: Then 1, `IntegrityError` (`project_component_items_item_id_fkey`).
- C-13 (BUG-2306): Then 1, `DID NOT RAISE HTTPException`.
- C-14, C-15, C-16, U-08, U-09 (BUG-2307): Then 1, `DID NOT RAISE ValidationError`.
- U-04, U-05 (BUG-2310): Then 2, `1 == 0`.

## Reference run
`refplug_item.py` (scratch `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wpsvce\C\`, with `refcommon.py`) patches in memory: BUG-1278 (deleted project → 404 from the manager); `ProjectComponentItemCreate` / `Update` subclasses with `1 <= qty <= 2147483647` (BUG-2307); `get_items` sending `0` through the guard (BUG-2309) and the workspace-wide list as one joined, filtered statement (project not deleted, caller may open it), ordered by `id`, paged after the filter (BUG-1278 list side, BUG-2308); `create_component_item` answering 404 `Item with ID {id} not found` for an item of another workspace, an unknown id or an inactive item, after the component guard (BUG-1012, BUG-2306); `update_component_item` writing no event when `qty` did not change (BUG-2310).
- With `--runxfail`: **68 passed** (revision 3). Without it: the 18 strict cards XPASS (strict → failed), L-13 XPASSes.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (69 statements, 14 branches).

## Factories added
None.

## Notes for maintainers
- When a bug is fixed its cards XPASS: remove the marker. BUG-1278 lives in `app/managers/project_manager.py` (guard) and in the service's `_filter_accessible_items` (list); BUG-2307 in `app/schemas/project_component_item.py`; BUG-1012, BUG-2306, BUG-2308 … BUG-2310 in the service.
- After BUG-1012 C-12 keeps passing (it accepts any exception); C-11 then passes too.
- L-13 is non-strict: it rests on today's physical row order (no `ORDER BY` in base `get_by_workspace`).
- The "no stock" counts are all-workspace table counts; another test run committing stock rows at the same moment would break C-01 / U-01 / D-01. None of this module's writes can (the tests never commit past the fixture's outer transaction).
- Verified: 3 plain runs 49 passed / 19 xfailed each (revision 3); ruff check and format clean; LF.

## Revision history
- **Revision 3 (2026-11-06)** — cases revision 3 (from `project_component_item_service.verify.md` findings 1 and 2, plus G-09). Added `test_pcis_l_20__one_component_read_no_commit_no_rollback` (PCIS-L-20), `test_pcis_g_09__one_row_read_no_commit_no_rollback` (PCIS-G-09), `test_pcis_u_13__w0_line_not_found_in_w1` (PCIS-U-13: W0 line, qty 4, updated through W1 → `None`, spies, `not db.dirty`, unchanged, nothing written) and `test_pcis_d_05__w2_line_not_found_in_w1` (PCIS-D-05: W2 line, qty 4, deleted through W1 → `False`, `not db.deleted`); all four pass. `line0` / `line9` gained a `qty` argument (default 1, as before) for the cards' qty 4. No existing test changed; no card changed or retired. Re-verified: 49 passed / 19 xfailed in each of 3 plain runs; `--runxfail` gives the same 19 failures on the same Then lines as revision 2; the reference plugin needed no change and gives 68 passed under `--runxfail`; branch coverage of the service 100%; ruff check and format clean; LF.
