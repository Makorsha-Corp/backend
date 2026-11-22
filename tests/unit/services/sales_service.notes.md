# Execution notes — `app/services/sales_service.py`

> Cases: `tests/unit/services/sales_service.cases.md` (revision 4a, 2026-11-22) · Tests: `tests/unit/services/test_sales_service.py` · Source commit: e48a092
> Result: 352 of 352 cases implemented · 219 passed · 133 xfailed (132 strict, SS-A-07b non-strict) · 0 xpassed · 1 open minor discrepancy (DISCREPANCY-5, wording) · 0 errors — branch coverage 99% (406 statements, 78 branches; 1 line and 1 branch missed, dead code)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_sales_service.py -q -p no:cacheprovider -o addopts=""`

## How the tests are built
Normal mode, no local model. One test per card, in card order. Parametrized only where the cards have the same setup and checks and differ in one input, with the case ID as the param id: U-18…U-21 (one schema field each), SR-15/16 (W0 / W2 credit note), SR-17/18 (W0 / W2 return row), SR-38/39 (W0 / W2 credit note, SQL check). SR-42 and SR-43 differ in Then 3, so they are two tests. Each test has a `# Then N` comment before the checks of its card's Then line N (before the `with pytest.raises` line for a `raises:` line) and the card's rules in its docstring. `# [claude]` marks the `Author: claude` cards (A-07b, A-08, A-15, A-16, RS-05, SR-31).

- **Standing rows:** fixture `s` (namespace): `W0 < W1 < W2`, `U1…U5` with the cards' names, memberships (U4 inactive in W1, U5 in W2 only), `CU = U2`, the `statuses` row with id 10 (inserted inside the test's transaction when missing, so it is rolled back), `A0 / A1 / A9` each tagged `client` in its workspace, `F0 / F1 / F9`, `I1`, `IS`, `P1` (qty 100), `DM1`, `TAG`.
- **Time:** autouse fixture `clock` patches `app.services.sales_service.utcnow` to NOW (naive, like the real helper). `date.today()` is not mocked (spec), which is why A-06 / RS-04 fail on the real date today.
- **Given rows:** `so(ws=, ready=, finalized=, completed=, **but)`, `ln(free=, service=, **but)`, `inv(ws=, confirmed=, voided_inv=, linked=, **but)`, `cn(amount, ws=, voided_inv=, draft=, **but)`, `invl`, `ret(refund=, done=, voided=, of=, ws=, **but)`, `rl`, `dlv(delivered=)`, `dl`, `pay(voided=, settle=)`, `appr(approved=)`, `ev`. Each flushes. `scene(L1=, CN=, cn_amount=, cn_lines=, R1=, D1=, rl_q=, dl_q=)` builds SCENE with the card's "but … also" overrides; `scene_call` is SCENE-CALL.
- **Commit point:** `commit_point(db)` commits (savepoint release) and returns the 15-table row counts ("nothing written") and MAXLED. `unchanged(R)` snapshots (`snap`) are taken right after it with a Core select (no `expire_all`), so in-memory objects the When uses are not touched. `X` = `mk_x(db)` after the commit point. Every `committed:` block starts with one `db.rollback()`.
- **Statement recorder:** `Recorder` listens to `after_cursor_execute` on the session's connection only around the When, keeping statement and parameters; `first(T)`, `row_lock(T)` (single-table FROM, no JOIN, ends in a plain `FOR UPDATE`, no `SKIP LOCKED` / `NOWAIT`), `cnlock(id)`, `payread(id)` and `count_from(T)` follow the Conventions. The `db.expunge_all()` Given steps use `expunge_all(db, s)`, which first loads the standing rows the When reads (`s.W1.id`, `s.CU.id`), because a detached, expired row cannot load its id.
- **Messages:** `mt(m)` / `mtd(m)` turn an `ActionMessage` into `(type, message)` / `(type, message, details)`; `MSG` / `MSGD` build the expected tuples. `MessageType` is a `str` enum, so tuple equality compares it with the plain text.
- **ipm cards (SR-53…SR-58):** `sp = db.begin_nested()` before the call, `sp.rollback()` after the `raises:` block when still active. SR-54 / SR-55 / SR-58 fail today with `TypeError` (`update_payment` has no `user_id` parameter yet), inside Then 1, as the cards allow ("write the call as shown").
- **Stock (BUG-664 rule):** sales stock is `products.qty`, read by `ProductManager` from the product row, never from a "latest ledger row", so the BUG-664 tie-break cannot arise here. P1 is seeded as the card says (qty 100, no ledger row) and no Given posts stock.

### Checks run (revision 3)
- `--runxfail` with my plugin `thencheck_ss.py` (scratch): each of the 129 strict xfails fails inside the block its card's "Fails today on" names (126 reported directly; SR-56 in `# Given 2`). RV-06, RV-07 and SC-06 fail in the call, which sits under `# Then 1` but inside a one-line call helper (`_void`, `_confirm`), so the plugin reports "When"; checked by hand (400 `Invoice is already voided`, 404 `Invoice with ID … not found`, `IntegrityError`, as the cards say).
- The ten list-order xfails (L-02, L-03, L-07, LD-05, LD-06, LD-09, GD-04, GI-03, GDI-03, RS-23) fail on Then 1, the new **id order on T** SQL check (`Recorder.id_order`). With that check forced to pass (scratch plugin `skipthen1.py`), all ten **pass** their Then 2 today: the unordered reads return insertion order on this database. So RS-23's row-order check passes by accident today; only its SQL check makes it fail.
- Reference plugin `ssref.py` (scratch, in-process, never in `app/`), `-p ssref --runxfail`: **347 passed**. New in revision 3: ORDER BY id in BaseDAO `get_by_workspace`, items / deliveries `get_by_sales_order`, deliveries `get_by_status`, `get_by_delivery`, `get_by_return` (BUG-100, 1270, 1271, 2425, 2442, 2443).
- 3 plain runs: `217 passed, 130 xfailed` each. Branch coverage 99% (same gap). `ruff check` clean, LF line endings.

## Discrepancies
| ID | Case | Status |
|---|---|---|
| DISCREPANCY-1 | SS-OR-03 | resolved in revision 3 (G17: plain pass card). Marker removed; passes |
| DISCREPANCY-2 | SS-A-01 Then 4 | resolved in revision 3 (G15: Then 4 commits first). Test commits before the re-read; passes |
| DISCREPANCY-3 | SS-DD-08, SS-SC-06 | resolved in revision 3 (G18: xfail BUG-639, pass companions DD-09, SC-08). Markers now `xfail(639)` |
| DISCREPANCY-4 (flaky) | 14 list cards | resolved in revision 3 (G16: set compares, order cards xfail on the SQL check). Non-strict markers removed |
| DISCREPANCY-5 (wording, no marker) | SS-DD-08, SS-DD-09 (and the ipm-calls convention) | still open after revision 4, minor. Revision 4 reads "roll the savepoint back unless it is already closed (`if sp.is_active: sp.rollback()`; the IntegrityError may already have closed it)", but the failed flush does **not** close it: `sp.is_active` is False and the session refuses queries until `sp.rollback()`. Original note: The cards say `sp.rollback()` "if `sp.is_active`", but a failed flush inside the savepoint (today's `IntegrityError`) leaves it deactivated (`is_active` False) yet not closed, and the session then refuses every query (`PendingRollbackError`). The tests roll back when `sp.is_active or not db.is_active`, which is what the step is for. Suggest the Conventions say "unless it is already closed" |

The BUG-124 citation noted in revision 2 is fixed by G14 (C2 is now BUG-3219).

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 59-63 (and the branch into it) | dead | A1: `order.account_id is None` → 422 "sales order has no customer account". `account_id` is NOT NULL; spec "Not specified" lists it as dead, to be removed (Q9) |

## Factories added
None.

## Notes for maintainers
- When a bug is fixed, its xfail tests XPASS (strict → failed): remove the marker. BUG-3217 covers 36 SR cards; the fix also needs the `invoice_payments.source_type / source_id` columns (SR3c) and `update_payment(..., user_id)`.
- When BUG-639 lands, DD-08 / SC-06 XPASS: remove their `xfail(639)` markers. When a DAO sort lands (BUG-100, 1270, 1271, 2425, 2442, 2443), its order cards XPASS the same way.
- SR-15/16/17/18/38/39/41/43 count `invoice_payments` in **all** workspaces (the cards say so): they rely on the shared test database having no committed payment rows. A committed row left by any other run would fail them.
- SS-A-07b is non-strict by design: line order after an in-place row update depends on physical row order.
- `_attach_invoice_payment_status` is a staticmethod; tests call it through the instance.
- `Recorder.id_order(T)` is the Conventions' **id order on T**: any recorded SELECT from T whose ORDER BY starts with `T.id` (not DESC).
- Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc3e\sales_svc\` (part files p0…p5, `plug/thencheck_ss.py`, `plug/ssref.py`, `plug/skipthen1.py`, `thencheck.json`; revision 2 parts in `..\sales_svc_rev2_backup\`, `.coverage`).

## Revision history
- **Revision 2 (2026-11-22).** First implementation: 335 cases; 4 discrepancies (OR-03 passes today; A-01 Then 4 needs a flush; DD-08 / SC-06 depend on open BUG-639; 14 list cards flaky on unordered DAO reads), BUG-124 citation mismatch reported.
- **Revision 3 (2026-11-22).** Cases revision 3 (Gap log G14–G18). C-02 marker BUG-3219 (was 124), C-03 text. A-01 Then 4 commits before the re-read. OR-03 plain pass. DD-08 / SC-06 `xfail(639)`; new DD-09, SC-08 (any error, everything kept; DD-09 rolls the savepoint back also when a failed flush deactivated it, DISCREPANCY-5). L-01, L-06, LD-01…LD-03, GD-01, GI-01, GDI-01 compare sets (L-06 keys by id); RS-02 finds lines by order line; L-04 checks count and workspace. L-02, L-03, LD-05, LD-06 become strict xfail with the `id_order` SQL check as Then 1; new L-07, LD-09, GD-04, GI-03, GDI-03, RS-23 (xfail) and L-08, L-09, LD-10, LD-11 (pass). All DISCREPANCY markers removed (`disc()` and `_DISC` gone); `_BUGS` gained 100, 639, 1270, 1271, 2425, 2442, 2443, 3219 and lost 124. Re-checked: 3 runs `217 passed, 130 xfailed`; `--runxfail` 129/129 on the named line (3 checked by hand); reference plugin 347 passed; branch coverage 99%; ruff clean; LF.
- **Revisions 4 and 4a (2026-11-22).** Cases revision 4 (verifier findings 1–5) and 4a (Gap log G19, G20). Every write-method card with X now asserts `X not in db` right after the raise (31 cards; `mk_x` returns the workspace, `X_ID = X.id`); the 17 named error cards also run the call inside **spies** and assert `rb.call_count >= 1`; later Then numbers shifted to match. New RK-22, RS-24, RS-25; RK-23 added in 4 and deleted in 4a (retired). A-03 is now `xfail(3220)` expecting `Line 1`; new RS-26, RS-27 `xfail(3220)` (blank names stored directly in the DB). Reference plugin: RC3a / A7a line-name rule (`_line_name`). DD-08 / DD-09 keep the `sp.is_active or not db.is_active` rollback (DISCREPANCY-5 still open). Re-checked on 4a: 3 runs `219 passed, 133 xfailed`; `--runxfail` 132/132 strict on the named line (RV-06, RV-07, SC-06 checked by hand); reference plugin 352 passed; branch coverage 99%; ruff clean; LF.
- **TC3 rollback-strip check (4a).** My plugin `plug/strip_rb.py` (scratch, in-process; it copies the method of `tc3audit/tc3method.py`, which I read but did not run): `STRIP_METHOD=<name>` compiles a copy of `sales_service.py` with `self._rollback_transaction(db)` / `db.rollback()` removed inside that one method, rebinds the function to the real module globals and puts it on `SalesService`. Each of the 17 write methods fails at least one test when stripped (see the report for the list). A first run without the globals rebind also failed SS-RK-01, because the clock patch did not reach the copy; the fixed plugin does not.
