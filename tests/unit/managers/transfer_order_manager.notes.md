# Execution notes — `app/managers/transfer_order_manager.py`

> Cases: `tests/unit/managers/transfer_order_manager.cases.md` (revision 2b) · Tests: `tests/unit/managers/test_transfer_order_manager.py` · Source commit: e48a092
> Result: 281 passed · 82 xfailed · 0 discrepancies (DISCREPANCY-1 resolved as BUG-2890) · 0 errors — branch coverage 98% (332 stmts / 122 branches, 5 missed stmts, 2 branch-partial)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_transfer_order_manager.py -q -p no:cacheprovider -o addopts="" --cov=app.managers.transfer_order_manager --cov-branch --cov-report=term-missing` (with a private `COVERAGE_FILE`)

## How the tests are built
- **One test per case.** 363 card IDs → 363 collected tests (plain functions, or `pytest.param(..., id="TOM-…")` where several cards share setup and assertions and differ in one input). Checked by a script: every card ID appears exactly once, none extra; 82 strict xfails = the 81 `xfail` Expect lines of revision 2a plus TOM-D-02, now BUG-2890. TOM-C-12 is retired and has no test.
- **Standing rows** → fixture `S` (a `SimpleNamespace`): W0 < W1 < W2 (`make_workspace` ×3), U1…U5 (`make_profile` with the card names) and their `WorkspaceMember` rows, S0/S1/S2, F0/F1/FB/FD/F2, M1/MD/M0/M2 (ids `XID(k)`), PJ1/C1/PJ2/C2, I1/I2/IN/I0/IX — inserted in the Conventions' order, each flushed. Tests read them as `S.W1`, `S.F1`, ….
- **Given rows** → `order(db, S, "O" | "O2" | "O0" | "O9", completed=…, **over)`, `line(db, S, T, k, **over)` (I1 / I0 / IX by the order's workspace), `apr(db, S, T, U, h, approved=…, **over)`, `ev(db, T, type, h, **over)`, `RT(**over)` (transient). Shorthand Givens: `ready(...)` (MC "Ready order"), `open_line` / `met_line` (UI), `ready_to_approve` (SA), `hubrow(k)` (HUB).
- **Requests** → `CREATE(S, **k)`, `ITEM(I, "q", notes=…)` (notes only when given), `UPD(**k)` / `IU(**k)` (only the listed fields, so `model_fields_set` is exactly the card's), `CH(...)`, `DEL(db, S, id)` (adds `user_id=U2.id` only when the parameter exists).
- **Named checks** → `reread` (flush, `expire_all`, SELECT by id), `snap` / `unchanged` (every column, snapshot taken from the database after the last Given line), `session_clean` (`not db.new / dirty / deleted`), `counts` (the six tables of "nothing written", all workspaces), `evs` / `ev_rows` (events of T by id), `SUMMARY`, `AUDIT` (the card's raw SQL), `count_where`.
- **Externals.** Autouse fixture `clock` patches `app.managers.transfer_order_manager.utcnow` → NOW. Autouse fixture `TNUM` is NUMP: it patches `get_next_number` on `transfer_order_manager.to_dao` with `patch.object`. The card's dotted target `app.managers.transfer_order_manager.to_dao.get_next_number` cannot be resolved by `patch` (the module has no `to_dao` name; `to_dao` is an attribute of the manager instance, the same object as `transfer_order_dao`), so the same DAO object is patched by reference. MC cards wrap the call in `with POST(n) as pm:` / `POST(err=ERR)`; `posted(pm)` binds the call arguments with the card's lambda signature.
- **Lock cards (BUG-2892, BUG-821)** → `Recorder`, a `before_cursor_execute` listener around the When only, after `db.expunge_all()` with ids read into locals first. `locks_before_first_write("transfer_orders")` = some SELECT whose FROM names `transfer_orders`, with `FOR UPDATE` and without `SKIP LOCKED` / `NOWAIT`, recorded before the first INSERT / UPDATE / DELETE. G-01 counts SELECTs before and after reading `current_status` (joined load).
- **Commit spy** → `with patch.object(db, "commit", wraps=db.commit) as cm:`, `sp = db.begin_nested()` directly before the call, "inside" lines, `sp.rollback()`, then the "after" lines.
- **DB-error card** (LE-05) → `with pytest.raises(HTTPException) as exc, db.begin_nested():`, so today's `IntegrityError` leaves the session usable.
- **`# Then N` comments** mark each Then block. Where one parametrized test covers cards whose Then lists differ by an optional "session clean" line, the following block is marked `# Then 3 / 4` (its number with and without that line).
- **Stamps** are compared after `naive()` (tzinfo removed), as the Conventions say.
- **D-07** (BUG-1194): the card's When is the call with `user_id`, which raises `TypeError` today; the call sits under `# Then 1`, as the card's "Fails today on: Then 1 (the call raises TypeError)" says.

## Checks run
- **Plain runs:** 3 × `281 passed, 82 xfailed` — identical, no flakiness.
- **`--runxfail`** with my scratch plugin `failson.py` (records, for every failed test, the test-file line it failed on and the `# Then N` block around it, then compares with the card's "Fails today on"): 82 failed, 281 passed; **all 81 strict xfails fail inside their named Then block, 0 mismatches**; the 82nd failure is TOM-D-02 (BUG-2890), which fails in the When (its card is being moved to a strict xfail for BUG-2890). Spot-checked that the failing assertion is the field the card names (e.g. U-23 Then 3 `A1.approved`, SA-11 Then 3 `approved_at`, C-11 Then 2 the order row count, LA-07 Then 2 the profile SELECT count).
- **Reference plugin** `ref_tom.py` (scratch, `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\toe\`, never in `app/`): replaces the four schemas of `app.schemas.transfer_order` and 14 manager methods in-process with the intended behaviour (all 21 bugs of the cases file, plus BUG-2890: the delete removes every line of the order explicitly, whatever its workspace), and removes every xfail marker. Plain run with it: **363 passed**; with `--runxfail` as well: 363 passed. So every xfail can pass once its bug is fixed, and no pass card depends on a bug.
- **ruff** clean (project config, plus `F841,F811,F401`); an AST pass found no unused test arguments. LF line endings.

## Discrepancies
None open. **DISCREPANCY-1 (TOM-D-02, `delete_transfer_order` R4) is resolved as BUG-2890.** The code raised `IntegrityError` (NotNullViolation: `UPDATE transfer_order_items SET transfer_order_id=NULL`) instead of letting a line stored under another workspace go with the database cascade. The cause is `TransferOrderItem.transfer_order = relationship("TransferOrder", backref="line_items")`, which has no `passive_deletes`, so the ORM nulls the leftover line's foreign key. The coordinator had the spec tag R4 as BUG-2890 and the cases move TOM-D-02 to a strict xfail. The test is now marked `xfail("BUG-2890")`.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 352 | dead | `list_transfer_orders` → `to_dao.get_by_workspace`. Spec Not specified / Q3: no caller, to be removed (`dead-code-removal-checklist.md`). |
| 557–559 (and branch 556→557) | dead | `update_item` stamps `approved_by` / `approved_at = func.now()` when `approved: true` reaches a line not yet approved. Spec R6 describes it, but BUG-2896 removes `approved` from the schema, and the cases deliberately give today's stamping no pass card (Reviewer summary); UI-19 pins the removal. |
| 572 (and branch 571→572) | unreachable | `update_item` writes `transfer_cleared` when `transferred_at` is cleared on a recorded line. Unreachable today because `exclude_none` drops the null (spec R8); reachable after BUG-2895, covered by the strict xfail UI-16. |

## Factories added
None (`tests/unit/factories.py` unchanged). Local builders worth promoting if another module needs them: `order` / `line` / `apr` / `ev` for transfer orders; the standing-row block for Factory / Machine / Project / ProjectComponent / Item / Status / WorkspaceMember.

## Notes for maintainers
- **When a bug is fixed**, its strict xfails will XPASS and fail the run: remove the marker from exactly those tests (`xfail("BUG-…")` decorator; U-25 carries BUG-2903 and BUG-2895 and needs both fixed).
- **BUG-2896** fix: the UI-19 card checks only that `approved` is gone from `TransferOrderItemUpdate.model_fields`; lines 557–559 then go away.
- **BUG-1194** fix: `DEL` starts passing `user_id=U2.id` automatically; D-07 / D-08 then call with it directly.
- **BUG-2892 / BUG-821**: the lock cards only check a `SELECT … FOR UPDATE` on `transfer_orders` before the first write; the two-session race is deferred to integration tests.
- **NUMP target**: if the manager ever gets a module-level `to_dao`, the card's dotted path would work as written; the `patch.object` on `M.to_dao` keeps working either way.
- The HUB cards compare with the DAO in the same session (identity-equal ORM rows); they also assert the filter changed the result, so a dropped keyword is caught. The DAO prints two `SAWarning`s (subquery coerced into `IN()`); they are DAO-side and harmless here.
- Another agent runs PO / WO manager tests on the same database in parallel; every test here rolls back and all names use `GN(...)` / `XID(k)` (pid-based), so there is no collision.

## Revision history
- 2026-11-21 — first implementation of cases revision 2a (363 cases).
- 2026-11-21 — cases revision 2b: TOM-D-02's test name, docstring and Rules updated to BUG-2890 (every line removed with the order).
- 2026-11-21 — DISCREPANCY-1 resolved as BUG-2890: TOM-D-02's reason changed to `BUG-2890`; `ref_tom.py` now deletes all of the order's lines explicitly. Plain run: 281 passed, 82 xfailed. With the plugin: 363 passed.
- 2026-11-22 — cases revision 2c (spec G13, exact lock clause). `Recorder.locks_before_first_write` now needs a SELECT from the table that ends with `FOR UPDATE OF <table>` once its whitespace is collapsed, and still rejects `SKIP LOCKED` / `NOWAIT`. This follows `locked_before_items` in `test_transfer_order_service.py`. The 9 lock cards (U-44, D-09, MC-19, AI-12, UI-23, RI-08, AA-11, RA-08, SA-16) use it and stay strict xfail. Plain run ×3: 281 passed, 82 xfailed, the same as before. With `--runxfail`, the 9 cards fail on their Then 2 line (2080, 2494, 2861, 3165, 3493, 3647, 4012, 4169, 4404), with 82 failed in total. In `ref_tom.py`, `_lock` now uses `with_for_update(of=TransferOrder)` (the old copy is kept as `ref_tom.py.bak-20261122`). With it: 363 passed, also with `--runxfail`.
