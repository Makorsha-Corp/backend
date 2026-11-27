# Execution notes — `app/managers/account_invoice_manager.py`

> Cases: `tests/unit/managers/account_invoice_manager.cases.md` (revision 11, 2026-11-19) · Tests: `tests/unit/managers/test_account_invoice_manager.py` · Source commit: e48a092
> Result: 250 passed · 128 xfailed · 0 discrepancies · 0 errors — branch coverage **100%** (198 stmts / 60 branches, 0 missed)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_account_invoice_manager.py -q -p no:cacheprovider --cov=app.managers.account_invoice_manager --cov-branch --cov-report=term-missing` (with a private `COVERAGE_FILE`, here `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\smaim\.coverage`)

All 378 cases in the cases file are implemented, one test per case. RPS-01..07,
RV-23/24, RV-25..27, DEL-25..27 and VD-30..32 are `pytest.param(id="AIM-...")` groups, so `pytest`
collects 378 items. A traceability script (`invlocke/trace.py`, scratch) maps
every case ID to exactly one test or param id: 377 of 377, none missing, none
twice (revision 9; revision 10 adds VD-48 as one new test, 378 of 378).

## Revision history

- **Revision 11 (2026-11-19): verify round 4, finding 17. VD-48's Given is now built
  in id order.** 250 passed, 128 xfailed, 100% branch coverage, 0 discrepancies.
  - **VD-48:** builds R0 (W0, completed), then R (W1, pending, `paid=False`),
    then RY (W2, pending). `mk_por` flushes after each row. Before the call the
    test asserts `r0.id < r.id < ry.id`. Thens are unchanged.
  - **`--runxfail`:** 128 failed, 250 passed. VD-48 still fails on the R
    re-read `status == "voided"` ('pending').
  - **Reference plugin** `invlocke/ref_aim.py` (unchanged, R3c filters by
    workspace): VD-48 passes. A full plain run with it gives 292 passed, 86
    xfailed.
  - **First-match mutant:** a scratch variant, `smaim/firstmatch/ref_aim_fm.py`,
    has an R3c that takes the first return row by id with no workspace filter.
    It fails VD-48: it picks R0 (completed) and raises the RETTXT 400, so the
    new Given order catches that fix.
  - **Runs:** 3 runs (plain ×2, coverage ×1), each 250 passed / 128 xfailed.
    ruff is clean, including F841/F811. LF.

- **Revision 10 (2026-11-19): verify finding 16, R3c finds the return within the
  workspace only (BUG-2788).** 250 passed, 128 xfailed, 100% branch coverage,
  0 discrepancies. No existing test changed.
  - **New test:** `test_vd_48__only_own_workspace_return_voided`, strict xfail
    `X2788`. Given: OI, P1 = PO(W1, "PO-1") at `Draft` linked to OI, CN for P1.
    R is a pending W1 POR (`paid=False`) on CN. R0 is a completed POR of W0 on
    CN. RY is a pending POR of W2 on CN. It guards `w0.id < w1.id < w2.id`.
    Thens in card order: no exception, `result.id == CN.id`, CN `voided`, R0
    `completed`, RY `pending` / `paid False`, and R `voided` / `paid False`.
  - **`--runxfail`:** 128 failed, 250 passed. VD-48 fails on the R re-read
    `assert ret.status == "voided"` ('pending' == 'voided'), which is the card's
    "fails today on".
  - **Reference plugin:** no change needed. In `ref_aim.py`, `_locked_returns`
    (R3c) already filters by `model.workspace_id == invoice.workspace_id`.
    VD-48 passes under it. Plain run with the plugin: 292 passed, 86 xfailed.
    With `--runxfail`: 292 passed, 86 failed (the other bugs). As a check, a
    scratch copy without the workspace filter
    (`smaim/nofilter/ref_aim_nf.py`) fails VD-48, because R0 being completed
    makes it refuse with RETTXT. So the card catches the fix it was written for.
  - **Runs:** 3 runs (plain ×2, coverage ×1), each 250 passed / 128 xfailed.
    ruff clean, including `--select F841,F811`. LF.
  - **New bugs:** none.

- **Revision 9 (2026-11-17) — `void_invoice` R3c (BUG-2788, owner OQ-47).**
  250 passed, 127 xfailed, 100% branch coverage, 0 discrepancies.
  - **Conventions:** `mk_por` / `mk_sor` now default to `status="pending"`,
    `paid=False`. New constant `RETTXT`, xfail reason `X2788`, and
    `SQLCapture.locks_table(T)` ("locks the return T" = a captured SELECT
    from T containing `FOR UPDATE`).
  - **Changed cards:** VD-26/27/28 build their return with
    `status="pending"` and cite R3c; they still assert only the invoice side.
    VD-12 now cites Errors row 6.
  - **New tests (15):** VD-33..36, VD-39, VD-40, VD-43, VD-46, VD-47 are strict
    xfails; VD-37, VD-38, VD-41, VD-42, VD-44, VD-45 pass.
  - **`--runxfail`:** 127 failed, 250 passed. Each new xfail fails on its named
    Then line: VD-33/34/43 on the return re-read `status == "voided"`
    ('pending'); VD-35/36/39/40 on `pytest.raises(HTTPException)` ("DID NOT
    RAISE"); VD-46/47 on `cap.locks_table(...)`.
  - **Reference plugin:** `ref_aim.py` gains R3c. After R2 / R3, it reads the
    invoice's return rows (same workspace) with `FOR UPDATE`. If one is
    `completed`, it raises RETTXT. Otherwise the void goes ahead and a
    `pending` return becomes `voided` / `paid=False`, while a `voided` return
    is left as it is. A credit note skips the freeze (R3b). BUG-2788 is added
    to the list of bugs whose markers the plugin removes. Plain run with it:
    291 passed, 86 xfailed. With `--runxfail`: 291 passed, 86 failed (the
    other bugs).
  - **Runs:** 3 plain runs, each 250 passed / 127 xfailed. ruff clean, LF.
  - **New bugs:** none.

- **Revision 8 (2026-11-14) — verify findings 14 and 15.** 244 passed,
  118 xfailed, 100% branch coverage, 0 discrepancies. No existing test changed.
  - **New tests (10):** RV-47 (SO + EO → `LOCK("sales order")`), RV-48 (PO +
    EO → `LOCK("purchase order")`), VD-29 (W0 / W2 return rows don't make a
    frozen invoice a credit note; payment stays unvoided), DEL-28 (voided PO
    at `Complete` still freezes the draft): strict xfails. DEL-25..27 and
    VD-30..32 (near-miss stage names `complete`, `" Complete"`, `Completed`)
    pass; each trio is a param group.
  - **`--runxfail`:** 118 failed, 244 passed; the four new xfails fail on
    `with pytest.raises(HTTPException)` ("DID NOT RAISE"), their named Then 1.
  - **Reference plugin:** no code change was needed. `ref_aim.py` already
    checks kinds in the spec F5 order (purchase, sales, expense, work), so
    RV-47 gets sales and RV-48 gets purchase. Its credit-note check is already
    scoped to the invoice's workspace (VD-29), and it ignores `voided` /
    `is_deleted` (F3, DEL-28). The coordinator asked for "sales before
    purchase". That contradicts spec F5 and RV-31 (SO + PO → purchase order),
    so the plugin keeps the spec order. Plain run with the plugin: 276
    passed, 86 xfailed. With `--runxfail`: 276 passed, 86 failed (the non-O1
    xfails).
  - **Runs:** 3 plain runs, each 244 passed / 118 xfailed. ruff clean, LF.

- **Revision 7 (2026-11-14) — completed-order freeze (spec O1, F1–F7; BUG-2730,
  BUG-2731, BUG-2733, BUG-2736).** 238 passed, 114 xfailed, 100% branch
  coverage, 0 discrepancies.
  - **New tests (62):** DEL-14..24, RV-13..46, VD-14..28, U-61, U-62
    (28 strict xfails: DEL-14..17, DEL-23, RV-13..18, RV-28..31, RV-33, RV-35,
    RV-37..40, RV-42, VD-14..17, VD-24, VD-25; 34 pass). RV-23/24 and
    RV-25..27 are param groups (same setup, one input).
  - **Changed cards:** RV-05 now asserts only the 400, a detail that starts
    with "Cannot revert to draft — " and contains "receiv", session clean, a
    full `snap_inv` and 0 events (holds for today's text and RCVTXT; the exact
    text moved to RV-13). RV-06 asserts "receiv" in and "active payments" not
    in the detail, session clean, and its Given now also sets
    `payment_status="partial"` as the card says. DEL-01 builds P1 with
    `stage="Draft"`; DEL-11 builds E1 `completed_at=None`, S1
    `order_completed=False`, Wo1 `status="DRAFT"`.
  - **Citations:** docstrings now cite the new Errors rows: DEL-06/DEL-09
    Errors 4, RV-04 Errors 6, RV-05/RV-06 Errors 5, VD-12 Errors 5.
  - **New conventions:** see "Revision 7 conventions" under How the tests are
    built. Builders changed only by adding defaults the Conventions now
    prescribe (PO stage "Draft", SO `order_completed=False`, EO
    `completed_at=None`, WO `status="DRAFT"`) and optional parameters
    (`mk_po(stage=)`, `mk_por(order=)`, `mk_sor(order=)`); every earlier test
    keeps its outcome.
  - **`--runxfail`:** 114 failed, 238 passed. Each of the 28 new strict xfails
    fails on its named Then line: DEL-14..17, RV-15..18, RV-28..31, RV-37..39,
    VD-14..17, VD-24, VD-25 on `with pytest.raises(HTTPException)` ("DID NOT
    RAISE" — the action goes ahead); DEL-23 inside that same `pytest.raises`
    with the `IntegrityError` (not-null `invoice_payments.invoice_id`) at flush;
    RV-13/RV-14 on `detail == RCVTXT` (today's "… Zero out received quantities
    first."); RV-33 on `detail == LOCK("purchase order")` (today: receiving
    text); RV-35 on `detail == LOCK("sales order")` (today: active-payments
    text); RV-40 on `detail == CNTXT` (receiving text); RV-42 on `detail ==
    CNTXT` (active-payments text). The 86 older xfails are unchanged (only
    docstrings touched).
  - **Reference plugin** `invlocke/ref_aim.py` (new; scratch, never in app/):
    see "Reference plugin" below. Plain run with it: 266 passed, 86 xfailed;
    with `--runxfail`: 266 passed, 86 failed (exactly the non-O1 xfails).
  - **Gap G16 (executor's):** read from the models — `statuses` has
    `workspace_id` (NOT NULL, FK workspaces), `name` and `comment` (both NOT
    NULL, no entity-type column), so ST = `Status(workspace_id=W, name=…,
    comment="")`. The order reference of a return row is
    `purchase_order_returns.purchase_order_id` /
    `sales_order_returns.sales_order_id` (NOT NULL, FK, `ON DELETE CASCADE`).
  - **ruff:** the file was not clean under the project's ruff rules before
    this pass (54 findings). Now clean: `dict(...)` calls in builders became
    literals (C408, ruff's own fix), IT-05's unused `items` list became a plain
    loop (F841; the card checks only the returned rows), and a file-level
    `# ruff: noqa: SIM117, DTZ001, FURB157, B017` covers what the cards
    prescribe (nested `pytest.raises` + savepoint, naive datetimes,
    `Decimal("0")` literals, `pytest.raises(Exception)` for "any Exception").
    `--select F841,F811`: clean. Line endings: LF.
  - **Runs:** 3 plain runs, each 238 passed / 114 xfailed (no flake).
  - **New bugs:** none found (BUG-2737..2749 unused).

- **Revision 6, fix round 2 (verify findings 11, 12, 13 + file-wide sweep).**
  No case changed and no expected value changed; 204 passed, 86 xfailed, 100%
  branch coverage. Every touched xfail was re-run with `--runxfail`: each still
  fails on its designed "fails today on" assertion, never on an added return
  assertion (U-23/U-24/U-25/U-40/U-44 on `assert_no_events`; U-38 on
  `'purchase_order' is None`; U-41 on the metadata dict; U-43 on `updated_by is
  None`; U-45 on `'purchase_order' == 'expense_order'`; CF-09/RV-11/VD-07/RS-08
  on `updated_by == U2.id`).
  - **Finding 11:** U-59 now takes `before = snap_inv(...)` before the call and
    asserts `snap_inv(...) == before` after it (the four explicit checks stay).
  - **Finding 12:** `result = ...` and `assert result.id == <row>.id` added
    before the existing assertions in U-23, U-24, U-25, U-38, U-40, U-41, U-43,
    U-44, U-45, CF-09, RV-11, VD-07, RS-08.
  - **Finding 13:** counts above, the BUG-625 maintainer note below and the
    "G14" -> "G15" comments in the test file were brought up to date.
  - **File-wide sweep (a): "returns ..." Thens** found these additional tests
    that did not assert the return: C-02 and C-08 (now `assert created.id is
    not None`, like C-01/C-25/C-26/C-27) and SUM-03 (now
    `assert result == (0, 0, 0, 0)` before the per-total checks).
  - **File-wide sweep (b): "unchanged" / "nothing written" Thens** found these
    additional tests that did not compare a full snapshot: U-28, CF-06 and RV-07
    (now `snap_inv` before/after, in addition to their explicit checks), SY-06
    and SY-07 (now `snap_inv` before/after; SY-06's Given also now builds CI with
    `invoice_amount=400.00` as the case says, and asserts `400.00`, instead of
    using the default 1000.00), and C-05, C-06 and C-07 (nothing written now
    also checks W2: `count_invoices` and `count_events` for `w2`, as the
    Conventions' "nothing written" requires; they take the `w2` fixture).
    Reviewed and left as is: the other "still exists / still draft" Thens
    (DEL-03..13, CF-05, RV-10, VD-04, VD-06) name specific facts, not "unchanged".

- **Revision 6.** New cases U-56 (bad `order_type` -> 422 on the update
  schema), U-57 (trim + lower-case), U-58 (confirmed invoice, changed
  `order_type` -> 400; strict xfail names both BUG-625 and BUG-631), U-59 (same
  value resent on a confirmed invoice, passes), U-60 (`order_type=None` alone on
  a linked draft -> half-set 400). U-53 now builds all four allowed values plus
  `None`. Docstrings (and G14 -> G15 in the xfail reasons) updated for U-35,
  U-36, U-37, U-38, U-45, U-46, U-47, U-48, U-53, U-54 to the cases rows' R2b /
  Errors numbers (order 404 = Errors 12, half-set 400 = Errors 13). Verify
  finding 8: U-03 now uses the draft `di` fixture, not `ci`. Verify finding 9:
  U-49 now sends `order_type="purchase_order"` as the case's When says. Result:
  204 passed, 86 xfailed, 100% branch coverage. `--runxfail` on the new and
  changed xfails: U-56 fails on "DID NOT RAISE ValidationError", U-57 on
  `AttributeError` (`.order_type` missing), U-53 on `"order_type" in
  model_fields_set`, U-58 and U-60 on "DID NOT RAISE HTTPException", U-38 and
  U-45 on the re-read `order_type`; U-03 on `locks_invoice()`. All are the
  designed "fails today on" assertions.

- **Revision 5, fix round 2.** Verify finding 6 (test-weakness): the 13 tests
  whose case says "returns the invoice" but asserted only `result is not None`
  (U-03, U-19, U-22, U-33, U-34, U-39, U-49, U-50, U-55, CF-10, RV-12, VD-08,
  RS-09) now assert `result.id == <row>.id`. No expected value changed; still
  203 passed, 82 xfailed, 100% branch coverage. Finding 7 (spec gap on
  `order_type` in update) belongs to the describer.

- **Revision 5 (this pass).** Two kinds of change, both against the
  revision-4 execution reviewed in `account_invoice_manager.verify.md`
  (verdict NEEDS WORK, 199 passed/78 xfailed at that time):
  - **New R9d cases (spec's "live" order per order type, cases-file gap G14
    closed).** Added the eight new cases the revision-5 cases file designed:
    `create_invoice` AIM-C-22 (voided expense order, xfail BUG-625),
    AIM-C-23 (soft-deleted work order, xfail BUG-625), AIM-C-24 (work order
    `status="VOIDED"`, xfail BUG-625), AIM-C-25/C-26/C-27 (live expense
    order / live work order / sales order, all passing); and `update_invoice`
    AIM-U-54 (work order `status="VOIDED"`, xfail BUG-625) and AIM-U-55
    (changing between two live work orders, passing). No existing test was
    touched for this part — `mk_po`/`mk_eo`/`mk_wo` already existed and needed
    no changes; the new cases just call them with different override
    combinations (`voided=True`, `is_deleted=True`, `status="VOIDED"`).
  - **verify.md findings routed to the executor (findings 1-4; finding 5 is
    a describer-side spec gap, not an executor fix — see below).**
    1. `synccall` no longer passes `is_manual` at all (was always passing
       `is_manual=False` positionally), so the manager's own default value is
       what actually runs. Re-verified with mutation testing (below): the
       `is_manual: bool = False -> True` mutant, which survived in the
       revision-4 run, is now killed.
    2. Fourteen cases whose Then column starts with "returns the invoice" but
       whose test dropped the return value now capture it and assert
       `result.id == <row>.id`: AIM-U-13, U-14, U-15, U-16, U-21, U-27, U-42,
       CF-02, CF-03, RV-02, RV-03, VD-02, VD-09, RS-02, RS-03, RS-04.
    3. AIM-RV-08 now does a full `snap_inv(...) == before` comparison (the
       case says "VI unchanged", which the Conventions define as every INV
       column), instead of checking only `invoice_status`.
    4. AIM-DEL-06, AIM-DEL-07 and AIM-RV-03's voided setup payments now pass
       `created_by=u1.id` (added the `u1` fixture param where it was missing),
       so `voided_by` matches the Conventions' "A voided setup payment has
       `voided_at = V0`, `voided_by = U1`" instead of accidentally being U2.
       The outcome of all three tests is unaffected (as the finding noted);
       only the Given now matches what the case says.
    Finding 5 (the spec and cases file's `create_invoice`/`update_invoke`
    "live order" text historically said a non-live PO is `is_deleted=True`,
    but `purchase_orders` has no such column) was already worked around in
    this test file before this pass (`mk_po`'s `voided=True`, with a comment
    explaining why) and the revision-5 cases file now documents the same
    decision directly (Conventions: "Never set `is_deleted` on
    `purchase_orders`..."). No test change was needed for finding 5 — it is
    a describer-side spec-text fix, not a test-side one.

- **Revision 4.** The cases file's gap-log update closed the two
  issues this module's revision-3 execution had logged as discrepancies, so
  this pass is a targeted update, not a rewrite:
  - **G14 (AIM-U-38, AIM-U-45, new AIM-U-53).** Revision 3 found that
    `AccountInvoiceUpdate` has no `order_type` field, so `UPD(order_type=...)`
    is silently dropped by Pydantic (`extra="ignore"`) and never reaches
    `update_invoice` — logged as DISCREPANCY-1, with U-38/U-45 forced to
    `xfail(strict=True)` even though the cases file still *designed* them as
    `pass`. Revision 4 resolved this at the design level (best-practice
    default, delegated by reviewer): being able to send `order_type` on a
    draft update is now part of the BUG-625 fix, so U-38 and U-45 are
    redesigned as `xfail BUG-625`, and a new case U-53 pins the missing field
    directly on the schema. This pass updated the two tests' markers/reasons
    from `DISCREPANCY-1` to `BUG-625 (G14)` and added `test_u_53__...`. No
    assertion changed — the actual behavior and its root cause are identical
    to revision 3; only the designed label changed, so DISCREPANCY-1 is
    retired (closed by the spec, not by weakening a test).
  - **G10 setup fix (AIM-EV-05, AIM-IT-04).** Revision 3 logged these as
    flaky (DISCREPANCY-2/3): with no tie-breaker, Postgres's physical order
    for rows tied on `created_at` / `line_number` is undefined and
    occasionally coincided with the intended fixed order, producing an
    XPASS under `xfail(strict=False)`. Revision 4 redesigned the setup
    (spec Notes G10): reserve three ids `N1 < N2 < N3` with three `nextval()`
    calls on the table's own id sequence, then insert the tied rows with
    *explicit* ids in the order `N2, N1, N3` (each flushed separately). Physical
    order is then `N2, N1, N3`, and reversed is `N3, N1, N2` — neither equals
    the intended `id`-descending (EV-05) or `id`-ascending (IT-04) order, so
    the xfail now fails today regardless of scan direction (forward index
    scan, backward index scan, or seq scan). Re-verified by running the full
    suite once and the two tests alone three more times (4/4 xfailed, no
    XPASS) — see Discrepancies below. Markers moved back to
    `xfail(strict=True)`.

## How the tests are built

### Revision 7 conventions

- **W0** → fixture `w0`. `w1` depends on `w0` and `w2` on `w1`, so W0, W1, W2
  are always built in that order; every card that uses W0 also asserts
  `w0.id < w1.id < w2.id`.
- **ST(W, "name")** → `mk_st(db, ws, name)` (G16 above). **PO … stage `X`** →
  `mk_po(..., stage="X")`, default `"Draft"`. `mk_status` (name `"Open"`) is
  kept only for the sales order's NOT NULL `current_status_id`, which F2 does
  not read.
- **Not completed / Completed** → builder defaults (PO stage `Draft`, SO
  `order_completed=False`, EO `completed_at=None`, WO `status="DRAFT"`) and the
  overrides `stage="Complete"`, `order_completed=True`, `completed_at=V0`,
  `status="COMPLETED"`.
- **CN** → `mk_cn(db, ws, account, created_by, order_type, order, **k)`
  (confirmed, receivable, `order_type` / `order_id` of the order); each card
  builds its POR(W1) / SOR(W1) with `mk_por(..., order=P1, invoice_id=CN.id)` /
  `mk_sor(..., order=S1, invoice_id=CN.id)`. **OI** → `mk_oi` (INV with
  `invoice_number="ORD-1"`), built before the order so the order can carry
  `invoice_id=OI.id`. Where the card makes CN the order's invoice (RV-39,
  VD-28) the order's `invoice_id` is set after CN exists, then flushed.
- **Session clean** → `assert_session_clean(db)` (the three asserts
  `not db.new`, `not db.dirty`, `not db.deleted`), called right after the
  `pytest.raises` block, before any re-read. DEL-23 opens its savepoint by hand
  (`sp = db.begin_nested()`), checks the session, then `sp.rollback()`, then
  re-reads, as the card orders.
- **LOCK(kind) / CNTXT / RCVTXT** → function `LOCK` and constants `CNTXT`,
  `RCVTXT`, compared with `==`. xfail reasons: constants `X2730`, `X2731`,
  `X2733`, `X2736`.
- `reread_row(db, Model, id)` (expire, then `db.get`) re-reads orders, return
  rows and payments.
- No test sets `invoice_status = "locked"` (BUG-2735).

### Reference plugin

`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\invlocke\ref_aim.py`
(load with `-p ref_aim`, that folder on `PYTHONPATH`) wraps three manager
methods in-process with the intended O1 behaviour and leaves everything else
as today: `delete_invoice` R2 → R2a freeze → today's code; `revert_to_draft`
R2 → R2a credit note (CNTXT) → R2b freeze → R3 with the R3a text (RCVTXT) →
today's code; `void_invoice` R2 / R3 → R3a freeze unless R3b (credit note) →
today's code. Freeze = an order of the **same workspace** whose `invoice_id`
is the invoice and that is completed per F2 (PO `statuses.name ==
"Complete"`, SO `order_completed`, EO `completed_at IS NOT NULL`, WO
`status == "COMPLETED"`; `voided` / `is_deleted` ignored), kind in F5 order.
Credit note = a POR / SOR row of the same workspace with this `invoice_id`.
It also removes the xfail marker from tests whose reason names only
BUG-2730/2731/2733/2736. Result (revision 8): 276 passed (244 pass cards + 32 O1
cards), 86 xfailed (the other bugs, untouched; none XPASS). So no pass card pins
today's pre-freeze behaviour, and every O1 card passes once the freeze, the
credit-note rule and the new texts are in. Earlier revisions had no reference
plugin for this module; it covers only O1, not BUG-620..639.

### Earlier conventions

Conventions → fixtures/helpers (all local to this file; batch mode — nothing
was added to `tests/unit/factories.py`):

- **W1/W2, U1/U2/U3** → fixtures `w1`, `w2`, `u1`, `u2`, `u3` (via
  `tests/unit/factories.py::make_workspace` / `make_profile`). U1's name is
  pinned to `"Rahim Uddin"` for the `get_events` `performed_by_name` join.
- **A1/A2/AX** → `mk_account` + fixtures `a1`, `a2`, `ax`.
- **INV(k=v, …)** → `mk_inv` (all documented defaults); `inv()` is the plain
  INV shorthand. **CI/DI/VI** → `CI_DEFAULTS` + `mk_ci` / `mk_di` / `mk_vi`,
  with fixtures `ci`, `di`, `vi`.
- **ITEM** → `mk_item`; **PAY** → `mk_pay`; **HIST** → `mk_hist`;
  **EVT** → `mk_evt`.
- **PO/EO/SO/WO/POR/SOR/MLED** → `mk_po`, `mk_eo`, `mk_so`, `mk_wo`, `mk_por`,
  `mk_sor`, `mk_mled`, each filling the referenced tables' other required
  columns with neutral values (own `Status`/`Factory`/`Machine`/`Item` rows as
  needed). `mk_po` notes that `PurchaseOrder` has no `is_deleted` — its
  soft-delete-equivalent flag is `voided`.
- **CRT(k=v, …)** → fixture `CRT` (closes over `a1`); applies the
  `invoice_amount=0.00` default only while that field still exists on
  `AccountInvoiceCreate` (BUG-627 escape hatch, per spec G1).
  **UPD(k=v, …)** → plain `AccountInvoiceUpdate(**k)`.
- **Time** → autouse fixture `_utcnow` patches
  `app.managers.account_invoice_manager.utcnow` to `NOW =
  datetime(2026, 9, 27, 12, 0, 0)` for every test; `V0`/`L0` are module
  constants used only as explicit column values on setup rows (column
  defaults such as `invoice_items.created_at` are intentionally not patched).
- **Re-read** → `reread_inv` / `reread_inv_or_none` (`db.expire_all()` then a
  fresh `select`), `snap_inv` for "unchanged" comparisons, `events_of` /
  `items_of` for child rows.
- **SQL capture** (HR-10 row-lock rules, BUG-621) → class `SQLCapture`
  (a `before_cursor_execute` listener on the `engine` fixture's connection,
  scoped to the `with` block around the call under test);
  `cap.locks_invoice()` greps the captured statements for a SELECT on
  `account_invoices` containing `FOR UPDATE`. Used by U-03, DEL-08, CF-10,
  RV-12, VD-08, RS-09 — all xfail (BUG-621: no caller locks the row today).
- **Error cases run inside `db.begin_nested()`** exactly where the cases file
  says "inside a savepoint" (U-51/52, DEL-06/07/09/10, SY-10/11), so the outer
  `db` fixture's transaction stays usable for the post-rollback re-read.
- **Race simulations:** none (per Conventions — the module has no simulated
  races; the two-session row-lock race is Deferred to integration tests).

- **R9d "live" order (revision 5)** — `mk_eo`'s `voided` column default
  (`False`) and `mk_wo`'s `status`/`is_deleted` column defaults (`"DRAFT"`,
  `False`) already give a "live" row with no overrides, so C-25/C-26/C-27/U-55
  just call the existing builders plain; the non-live variants (C-22/C-23/
  C-24/U-54) pass `voided=True`, `is_deleted=True`, or `status="VOIDED"`
  through each builder's `**overrides`.

### This batch's additions (sync_items_from_list / get_events / get_items)

- `synccall(db, M, inv_row, items, user_id)` wraps `sync_items_from_list`,
  never passing `is_manual` (cases file: "never `is_manual`"), so every SY
  case exercises the manager's own default (`is_manual=False`), which is the
  value every production caller relies on. (Revision 4 had this wrapper
  defaulting `is_manual=False` itself and always passing it explicitly through
  positionally — verify.md finding 1 — which meant the *default* was never
  actually exercised, only an explicitly-passed `False`; mutating the default
  to `True` survived. Revision 5 drops the parameter so the real default
  runs.) The `is_manual=True` branch itself stays uncalled by design (dead
  code, see `account_invoice_manager.deadcode-staging.md`).
- `D(desc, q, p, s, **extra)` builds the item-dict shorthand from the
  Conventions section, as a plain `dict`, so it round-trips through
  `invoice_item_dao.create`'s `isinstance(obj_in, dict)` branch the same way
  the real PO/EO/SO/WO sync callers do.
- SY-10/SY-11 (a dict missing `line_subtotal`, and one with `quantity=None`)
  both raise a SQLAlchemy `IntegrityError` (not-null violation) inside
  `db.begin_nested()`; after the savepoint rolls back, `items_of` shows only
  the pre-existing item and the invoice's `invoice_amount` is untouched,
  confirming R7a: the DAO flushes each new item row immediately as it is
  created (R3), so the failure happens mid-replace, after the old items are
  already gone in the (rolled-back) transaction but before any new metadata
  is logged.
- `get_events` returns plain `dict`s (via `InvoiceEventDAO.get_by_invoice`'s
  outer join to `Profile`); `get_items` returns `InvoiceItem` ORM rows (via
  `InvoiceItemDAO.get_by_invoice`) — EV tests assert dict keys/values, IT
  tests assert `.id` / `.line_number` attributes, matching each DAO's actual
  return shape.
- **AIM-EV-05 / AIM-IT-04 (revision 4 setup)** — three ids reserved up front
  with `SELECT nextval(pg_get_serial_sequence('invoice_events'|'invoice_items', 'id'))`,
  then the tied rows inserted with those ids passed as an explicit `id=`
  override to `mk_evt` / `mk_item` (both accept `**overrides`), each flushed
  separately so the physical insert order is `N2, N1, N3`. See Revision
  history above for why this makes the xfail deterministic.

## Discrepancies

None. (Revision 7: still none; all 62 new cards and the changed cards ended as designed, no card was found wrong.) (Revision 6: still none; the five new cases and the changes ended as designed.) Revision 5 added eight new cases (C-22..C-27, U-54, U-55) and applied
verify.md's four routed test-side findings; every test ended as designed
(203 passed, 82 xfailed — see the result line above), and `--runxfail` on the
eight new cases alone confirms the four new xfails fail on "DID NOT RAISE
HTTPException" exactly as the cases file's "fails today on" column specifies.
Revision 3's three earlier discrepancies were all closed by revision 4's
cases-file update rather than by a test-side workaround — see Revision
history above:
- DISCREPANCY-1 (AIM-U-38, AIM-U-45) is closed because the cases file now
  *designs* them as `xfail BUG-625` instead of `pass`; the tests' markers
  were relabeled from `DISCREPANCY-1` to `BUG-625 (G14)` with no assertion
  change, and a new case (AIM-U-53) was added to pin the gap on the schema.
- DISCREPANCY-2 / DISCREPANCY-3 (AIM-EV-05, AIM-IT-04) are closed because the
  redesigned setup (reserved out-of-order ids, spec Notes G10) makes the
  BUG-638 xfail deterministic: the full suite run above plus three extra
  standalone runs of `-k "ev_05 or it_04"` all xfailed (4/4, no XPASS), so
  both markers are back to `xfail(strict=True)`.

## Coverage gaps

None — 100% branch coverage (198 statements, 60 branches, 0 missed; revision 7, private `COVERAGE_FILE`). The one
`is_manual=True` branch in `sync_items_from_list` (the `item_manually_updated`
event text) is dead code per the spec's "Not specified" note — logged in
`account_invoice_manager.deadcode-staging.md`, not exercised here by design,
and does not appear as a miss because it sits on the same line as the
`is_manual=False` path already covered by every SY case.

## Factories added

None. This batch is local-helpers-only (batch mode): `D()` (item-dict
shorthand) and `synccall()` are module-local to this test file. If another
module's tests later need an `invoice_items` or `invoice_events` builder, the
existing `mk_item` / `mk_evt` helpers here (and `items_of` / `events_of`
re-read helpers) are reasonable candidates to promote into
`tests/unit/factories.py`.

## Notes for maintainers

- **When BUG-621 is fixed** (row locking added to `_get_or_404` or the six
  mutating methods): U-03, DEL-08, CF-10, RV-12, VD-08, RS-09 will XPASS —
  remove their `xfail` markers.
- **When BUG-638 is fixed** (a real tie-breaker — `id` — is added to the
  `ORDER BY` in `get_events`/`get_items`): EV-05 and IT-04 should start
  XPASSing *reliably* (the reserved-id setup makes the order deterministic
  now, so a real fix should make them pass every time) — at that point,
  remove their `xfail` markers.
- **When the `order_type` field is added to `AccountInvoiceUpdate`**
  (BUG-625 / G15, spec R2b): re-run U-38, U-45, U-53, U-56 and U-57 — all five
  should XPASS (U-56 and U-57 only need the field, its trim + lower-case and
  its four-value restriction); U-46 and U-60 XPASS once R12a's pair check
  (`order_type` and `order_id` set together) is also in; U-58 XPASSes only when
  BUG-631 (confirmed invoice rejects a changed non-editable field) is fixed
  as well as BUG-625. U-59 passes before and after and must keep passing. Then
  drop the `xfail` markers, and double check BUG-625's order validation
  afterward actually fires for the now-live `order_type` field, per R12a.
- **When BUG-625's order-existence/liveness check is added**: besides the
  original C-12..C-15 / U-35..U-37 group, C-22, C-23, C-24 and U-54 (the
  revision-5 "live order" cases for EO/WO) should also start XPASSing —
  remove their `xfail` markers at the same time as the others.
- **When the O1 freeze is fixed** (BUG-2730 / 2731 / 2733 / 2736): the 28
  strict xfails listed in Revision 7 XPASS — remove their markers in the same
  change. BUG-2736 alone (the new receiving text) flips only RV-13 and RV-14;
  RV-05 / RV-06 pass with either text. RV-34, RV-36, RV-41, RV-43 and DEL-24
  pin only the refusal and must keep passing. If the fix stores a `locked`
  status (BUG-2735) instead of reading the order, the cards still build the
  freeze only from the order's state, so they keep testing the rule.
- **Fragile spots:** none outstanding. The two setup patterns worth noting for
  a future maintainer are: (a) EV-05/IT-04 depend on explicit `id=` overrides
  reserved via `nextval()` rather than natural insertion order — if a future
  change reorders the three inserts or reuses the reserved ids elsewhere in
  the same test, the "physical order differs from the intended order either
  way" guarantee could break; (b) the `is_manual=True` branch of
  `sync_items_from_list` is dead code (see Coverage gaps) and must stay
  uncalled by every SY case.
- Every write case re-reads via `db.expire_all()` + a fresh query (never
  asserts on the in-memory object alone); every case expected to fail at
  flush with a DB-level error runs inside `db.begin_nested()` so the outer
  `db` fixture stays usable afterward.
