# Test cases — `app/managers/account_invoice_manager.py`

> **Spec:** `tests/unit/managers/account_invoice_manager.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 1 — re-run on the unchanged spec; self-check fixes only: Kind `schema` replaced by allowed kinds (C-09, U-05, U-11, VD-10, VD-11 keep "target `schema`" in When); added L-44 (empty `payment_status`/`invoice_status` = no filter) and LO-09 (`prioritize_purchase_order_id=0` is "given").
> **Revision:** 2 — spec Gap log G1–G13 closed. G1: C-18 asserts `loc == ("invoice_amount",)`. G2: exact detail texts added to C-12..C-15, U-35..U-37; BUG-630 cases assert `loc == (<field>,)`. G3: day-boundary cases HS-10, AH-20 (NOW pinned via `utcnow`). G4: new `list_invoices` R5a → L-45, L-46; Deferred row removed. G5/G13: new `create_invoice` R9c → C-19..C-21; new `update_invoice` R12a → U-45..U-50; U-38 now clears both link fields (clearing only `order_id` is half-set after the fix). G6: new R10a → U-51, U-52. G7: DEL-09, DEL-10 (status-history variant). G8: DEL-11..DEL-13 (other SET NULL referrers). G9: new R7a → SY-11; SY-08 also checks `unit is None`. G10: no change (setups already follow the Notes). G11: AH-21, AH-22 (id tie-break). AH-15 rewritten with case-only name differences: the test DB collation (`English_United States.1252`) already orders "apex"/"Beta"/"Zeta" case-insensitively, so the old setup would XPASS. C-09..C-11 now also send `order_id` (R9c makes a lone `order_type` invalid). G12: recalc helpers assert `None` returns; SY-01 checks exact metadata-item keys. Errors-row numbers for `create_invoice` and `update_invoice` renumbered to the new Errors tables.
> **Revision:** 3 — re-run after the spec's Gap log update; the spec content matches what revision 2 already applied (G1–G13), so no case was added, removed or renumbered. Full self-check re-run: RV-06 and RV-07 now also re-read the invoice to prove nothing changed.
> **Revision:** 4 — re-run after the spec's Gap log update (spec text unchanged since revision 3: G1–G13 already applied). Two test-side findings from the execution notes were addressed. (a) The spec's `AccountInvoiceUpdate` input list never names `order_type` (Q4 lists the nullable fields without it), but R12a talks about "the value sent in this request". New gap G14 was decided by best-practice default: sending `order_type` on update is part of the BUG-625 fix. So U-38 and U-45 move from pass to xfail BUG-625, and new U-53 pins the field on the schema. (b) The BUG-638 tie cases EV-05 and IT-04 were flaky: the order depends on the plan (seq scan vs. forward/backward index scan, HOT updates). Their setups now reserve three ids from the table's sequence and insert them out of id order, so neither scan direction can produce the intended order today.
> **Revision:** 5 — re-run after verification and the spec's Gap log G14. The spec adds `create_invoice` R9d, which defines a "live" order per type: PO/EO `voided = False`; WO `is_deleted = False` and `status != "VOIDED"`; SO any existing row. `purchase_orders`, `expense_orders` and `sales_orders` have no `is_deleted` column. Verify finding 5 is addressed: the order-row convention and C-14, U-37 and U-50 now build the non-live PO with `voided=True` (IDs kept, same intent). New R9d cases: C-22..C-27 cover both sides for each order type, and U-54 and U-55 cover R12's reuse of R9d on update. The open case-designer gap about `order_type` on update is renumbered from G14 to G15, because the spec now uses G14 for a different gap. Verify findings 1–4 are executor-side: `synccall` must omit `is_manual`; return-value checks; the RV-08 snapshot; voided PAY with `voided_by = U1`. The cases already state these correctly, so no case changed for them.
> **Revision:** 6 — re-run after verification and the spec's Gap log G15. The spec adds `update_invoice` R2b (`order_type` is sendable on update: nullable, trimmed + lower-cased, restricted to the four known values, a sent field; non-editable on a confirmed invoice) and a new Errors row (bad `order_type` → 422, `loc = ("order_type",)`). Verify finding 10 is addressed: new U-56 (bad value → 422), U-57 (trim + lower-case), U-58 and U-59 (confirmed invoice: changed value rejected / same value no-op) and U-60 (`order_type=None` alone on a linked draft → half-set 400). U-38, U-45, U-46 and U-53 now cite R2b, and U-53 builds all four allowed values. The new Errors row shifts the `update_invoice` Errors numbers: order 404 is now Errors 12 (U-35, U-36, U-37, U-46, U-54) and the half-set pair 400 is Errors 13 (U-47, U-48). The cases gap G15 is closed by the spec, and the stale "the describer should still confirm it" text is removed. Verify findings 8 and 9 are executor-side (U-03 must use DI; U-49 must send `order_type`); those cases already say so and are unchanged.
> **Revision:** 7 (2026-11-14) — spec owner decision O1 (completed-order freeze, shared F1–F7; `delete_invoice` R2a [BUG-2730], `revert_to_draft` R2a [BUG-2733], R2b [BUG-2730], R3a [BUG-2736], `void_invoice` R3a [BUG-2731], R3b, `update_invoice` R3b), per spec Gap log R1. RV-05 and RV-06 split: they keep the 400 itself (detail starts with "Cannot revert to draft — " and contains "receiv", which holds for the old and the new text) and gain the session check; the exact new text moves to strict xfails RV-13 and RV-14 (BUG-2736). DEL-01 and DEL-11 now pin their linked orders as not completed; the PO/EO/SO/WO shorthand in Conventions means "not completed" (PO stage `Draft` through a new ST `statuses` row), with new names W0, ST, Completed, CN/OI, Session clean and the freeze texts LOCK/CNTXT/RCVTXT. New cards: DEL-14..DEL-24, RV-15..RV-46, VD-14..VD-28, U-61, U-62. Errors-row numbers renumbered to the spec's new Errors tables: `delete_invoice` payment history is Errors 4 (DEL-06, DEL-09); `revert_to_draft` receiving is Errors 5 (RV-05, RV-06) and payments Errors 6 (RV-04); `void_invoice` blank note is Errors 5 (VD-12). No case sets `invoice_status = "locked"` (BUG-2735). The verify report has no open finding.
> **Revision:** 8 (2026-11-14) — verify findings 14 and 15 (scoped round on revision 7). Finding 14: kind-priority pairs (SO, EO) and (PO, EO) added, RV-47 and RV-48 (strict xfail BUG-2730). Finding 15: VD-29 (strict xfail BUG-2731) shows that return rows of W0/W2 do not turn a frozen invoice into a voidable credit note, so its payment stays unvoided. The near-miss PO stage names now also cover delete (DEL-25..27, pass) and void (VD-30..32, pass). DEL-28 (strict xfail BUG-2730) covers F3 on delete: a voided PO at `Complete` still freezes. No existing card changed.
> **Revision:** 9 (2026-11-17) — spec `void_invoice` R3c [BUG-2788] (owner OQ-47): a credit note's return decides its void. A pending return is voided with it (`status "voided"`, `paid False`). A completed return refuses with 400 and nothing is written. An already voided return lets the void through unchanged. R3b is narrowed to "never frozen". Conventions: POR/SOR default `status "pending"`, `paid False`; new RETTXT; new "locks the return T". VD-26..28 (R3b) now pin their return as `pending`, so they keep passing before and after the fix. They still assert only the invoice side. New cards: VD-33..36 (strict xfail: pending/completed × purchase/sales), VD-37/38 (pass: return already voided), VD-39/40 (xfail: R3c wins over the completed order, not LOCK), VD-41/42 (pass: R2 and R3 come first), VD-43 (xfail: pending return on a credit note that is also a completed order's invoice), VD-44/45 (pass: returns of W0/W2 ignored), VD-46/47 (xfail: return row lock). Errors renumbered: `void_invoice` blank note is now Errors 6 (VD-12).
> **Revision:** 10 (2026-11-19) — verify finding 16: new VD-48 (strict xfail BUG-2788). The credit note has its own pending W1 return plus a completed POR(W0) and a pending POR(W2) pointing at it. The void goes ahead and only the W1 return is voided. This catches a fix that finds the return without the workspace filter.
> **Revision:** 11 (2026-11-19) — verify round 4 finding 17: VD-48's Given now builds the return rows in id order R0 (W0, completed) < R (W1) < RY (W2). Each is flushed and the order is asserted, so a fix that takes the first matching return without a workspace filter picks R0 and fails. No count change.
> **Counts:** 378 cases · 250 expected-to-pass · 128 expected-to-fail (bugs) · 2 deferred

## Reviewer summary
- **Per callable:** `_get_or_404` 5 · `_log_event` 5 · `_recalculate_payment_status` 7 · `_recalculate_invoice_amount` 4 · `create_invoice` 27 (15 bug; 8 build the schema directly) · `get_invoice` 3 · `list_invoices` 46 (7 bug) · `list_open_invoices_page` 9 (1 bug) · `list_invoices_page` 7 (1 bug) · `get_invoices_hub_summary` 10 (3 bug) · `list_accounts_hub_page` 22 (8 bug) · `summarize_invoices` 6 (1 bug) · `update_invoice` 62 (34 bug; 10 schema) · `delete_invoice` 28 (9 bug) · `confirm_invoice` 10 (3 bug) · `revert_to_draft` 48 (21 bug) · `void_invoice` 48 (21 bug; 4 schema) · `set_receiving_started` 9 (2 bug) · `sync_items_from_list` 11 · `get_events` 6 (1 bug) · `get_items` 5 (1 bug)
- **Notable design choices:**
  - The HR-10 row-lock rules (BUG-621, six methods) are unit-tested the same way as `payment_transaction_manager` RR-08: capture the SQL the call runs and look for `FOR UPDATE` on `account_invoices`. The real two-session race goes to Deferred (integration tests). Race simulations: none.
  - Payload building around BUG-627: `invoice_amount` is still a required field of `AccountInvoiceCreate` today and will be removed by the fix. Passing create cases therefore send `invoice_amount=Decimal("0.00")` only while the field exists, so they pass both before and after the fix (best-practice default, delegated by reviewer).
  - Schema rules (BUG-624, BUG-626, BUG-627, BUG-630, the `AccountInvoiceUpdate` field set) are tested by building the Pydantic model directly (target `schema`).
  - "Overdue" (BUG-635): "today" is the application clock `utcnow().date()`, pinned to NOW (2026-09-27). Most cases use far dates (2020-01-01 vs 2099-12-31); HS-10 and AH-20 test the day boundary (due 2026-09-26 overdue, due 2026-09-27 not). Because the real date is later than 2026-09-27, a fix that reads the DB clock instead of `utcnow` fails these two cases.
  - Linked order (BUG-625, R2b, R12a): `AccountInvoiceUpdate` has no `order_type` field today (Pydantic drops it silently). Spec R2b (Gap log G15) makes it part of the BUG-625 fix: a nullable field, trimmed and lower-cased, restricted to the four known values. So every update case that relies on a sent `order_type` taking effect is an xfail BUG-625: U-38, U-45, U-46, U-60 on a draft, and the schema checks U-53 (four values and `None` accepted), U-56 (bad value → 422) and U-57 (normalised). U-49 stays a passing case because it holds both today and after the fix. Changing `order_id` within the same type keeps its passing coverage (U-34). U-38 clears **both** link fields, because clearing only one of them is a half-set pair (400) after the fix (U-48 for `order_id`, U-60 for `order_type`).
  - `order_type` on a confirmed invoice (R2b → R4/R4a): U-58 (changed value → 400) is marked `xfail BUG-625, BUG-631` and starts passing only when **both** are fixed: BUG-625 makes `order_type` a sent field, BUG-631 rejects it. U-59 (same value resent → no-op) passes today and after both fixes (best-practice default, delegated by reviewer).
  - Name-order bug (BUG-623): the test DB collation (`English_United States.1252`) already sorts names almost case-insensitively, so a plain "apex before Zeta" setup would pass today. AH-15 and AH-22 therefore mix names that differ only in case, with ids chosen so that today's case-sensitive order differs from the intended order under both this collation and a byte-wise one.
  - Tie-order bugs (BUG-638): EV-05 and IT-04 reserve three consecutive ids N+1..N+3 from the table's own id sequence (`nextval` three times, so no other session can ever get them). They then insert the tied rows with explicit ids in the order N+2, N+1, N+3. Physical (TID) order is then N+2, N+1, N+3, and reversed it is N+3, N+1, N+2. Neither matches id-descending (events) or id-ascending (items), so the strict xfail fails today whether Postgres sorts after a seq scan or reads an index forward or backward. The earlier setups (insert order / update-to-move) were flaky per the execution notes.
  - BUG-639 (delete of a draft with voided payments or legacy status-history rows) and BUG-629 R10a (`account_id = 0`) each have a strict xfail for the intended clear error and a passing case that only pins "raises, nothing changed", which holds before and after the fix (DEL-06/07, DEL-09/10, U-51/52).
  - `delete_invoice` R3 SET NULL referrers: EO/SO/WO (DEL-11), both return tables (DEL-12) and `machine_item_ledger` (DEL-13). `project_component_item_ledger` is not set up, following the spec note that one ledger table is enough (best-practice default, delegated by reviewer).
  - "Live" order (R9d, spec G14): each order table has its own liveness flag, so every non-live variant gets its own xfail: voided PO (C-14), voided EO (C-22), soft-deleted WO (C-23) and WO with `status="VOIDED"` (C-24). Each order type also has a passing "live is accepted" case that holds before and after the fix: C-08, C-25, C-26 and C-27. Sales orders have no non-live state, so only their accepted side exists. On update, U-37 (voided PO) and U-54 (voided WO) are the xfail side, and U-34 and U-55 are the passing side.
  - Completed-order freeze (O1, 2026-11-14): full depth, because it guards money. Per order kind × delete / revert / void one strict xfail (DEL-14..17, RV-15..18, VD-14..17) asserting the exact LOCK text, the session check and that nothing is written (void cards carry an active payment that must stay unvoided). Pass edges hold today and after the fix: PO stage `Receiving` (DEL-18, RV-19, VD-18), orders of W0 and W2 pointing at the invoice (DEL-19/20, RV-20/21, VD-19/20; each card has one lower and one higher workspace id, and two cards so every order table gets both sides), a link by `order_type`/`order_id` only (DEL-21, RV-22, VD-21), WO `IN_PROGRESS` / `VOIDED` (RV-23/24) and near-miss stage names `complete`, `" Complete"`, `Completed` on every method (RV-25..27, DEL-25..27, VD-30..32). F3 (void/delete flags do not lift the freeze): VD-24, VD-25, DEL-28. F5 kind priority: RV-28..31, RV-47, RV-48 (every pair whose order is decided). Other-workspace return rows on a frozen invoice: VD-29. Credit-note void and its return (R3c, BUG-2788): VD-33..47. The return lock (VD-46/47) is checked the same way as the invoice lock, on the captured SQL. Check order: DEL-22/23, RV-32..36, RV-39..44, VD-22/23. Where today already refuses with a different text (RV-33, RV-35, RV-40, RV-42, DEL-23) a passing twin pins only the refusal (RV-34, RV-36, RV-41, RV-43, DEL-24). Credit notes: revert refused (RV-37..40, RV-42; both return tables), return rows of W0/W2 ignored (RV-45/46), void allowed on a completed order (VD-26..28, pass). `update_invoice` R3b: U-61 (SO), U-62 (PO) pass (best-practice default, delegated by reviewer).
  - Confirmed-path "no-op" cases (R4a, R5) send a non-editable field with the **same** value as stored, because a changed value becomes a 400 once BUG-631 is fixed.
- **Needs a decision:** None. The spec's Gap log G1–G15 are closed (G15: `order_type` is sendable on update → spec `update_invoice` R2b). G16 (columns of `statuses` and of the return rows' order link) is test mechanics only and does not block a case.

## Conventions for this module

**ID prefixes:** `AIM` = account_invoice_manager. Methods: `G4` = `_get_or_404`, `LOG` = `_log_event`, `RPS` = `_recalculate_payment_status`, `RIA` = `_recalculate_invoice_amount`, `C` = `create_invoice` (incl. `AccountInvoiceCreate` schema cases), `GI` = `get_invoice`, `L` = `list_invoices` (shared filters), `LO` = `list_open_invoices_page`, `LP` = `list_invoices_page`, `HS` = `get_invoices_hub_summary`, `AH` = `list_accounts_hub_page`, `SUM` = `summarize_invoices`, `U` = `update_invoice` (incl. `AccountInvoiceUpdate` schema cases), `DEL` = `delete_invoice`, `CF` = `confirm_invoice`, `RV` = `revert_to_draft`, `VD` = `void_invoice` (incl. `VoidInvoiceRequest` schema cases), `RS` = `set_receiving_started`, `SY` = `sync_items_from_list`, `EV` = `get_events`, `IT` = `get_items`. IDs below omit the `AIM-` prefix. The full ID is e.g. `AIM-U-12`.

**Actors and accounts:**
- W0, W1, W2 = three workspaces, built in that order so `W0.id < W1.id < W2.id` (the executor asserts it). W0 is used only by the freeze cards. U1, U2 = two profiles in W1. U1 created every setup row. U2 is the acting user unless the case says otherwise, so `updated_by = U2` can be told apart from setup values. U1's profile name is `"Rahim Uddin"`. U3 = a profile in W2.
- A1 = account `"Acme Traders"` in W1. A2 = account `"Beta Supplies"` in W1. Both have `is_active = True`, `is_deleted = False`, `allow_invoices = True`, unless the case overrides a flag. AX = an account `"Xeno Foreign"` in W2 with the same flags.
- `NOID` = `999999`, an id that exists in no table used here.

**Invoice shorthand:** **INV(k=v, …)** = one `account_invoices` row inserted directly, with these defaults unless overridden: workspace W1, account A1, `invoice_type "payable"`, `invoice_status "confirmed"`, `payment_status "unpaid"`, `invoice_amount 1000.00`, `paid_amount 0.00`, `invoice_date 2026-09-01`, `due_date None`, `allow_payments True`, `receiving_started False`, `created_by U1`, `updated_by None`, `updated_at None`, `last_synced_at None`, `void_note None`, and `description`, `notes`, `invoice_number`, `vendor_invoice_number`, `payment_locked_reason`, `order_type`, `order_id` all `None`. "INV in W2" means workspace W2, account AX, created_by U3.
- **CI** = INV(`description="Old desc"`, `notes="Old notes"`, `invoice_number="INV-1"`, `due_date=2026-10-01`), a confirmed invoice.
- **DI** = CI with `invoice_status="draft"`.
- **VI** = CI with `invoice_status="voided"`, `void_note="Old reason"`.

**Other rows:**
- **ITEM(inv, s, line_number=1)** = one `invoice_items` row: workspace = inv's workspace (unless the case says otherwise), `invoice_id = inv.id`, `description "Item"`, `quantity 1`, `unit_price s`, `line_subtotal s`, `line_number` as given, `created_by U1`.
- **PAY(inv, amt, voided=False)** = one `invoice_payments` row for inv (inv's workspace), amount amt, `is_voided` as given. The executor fills the other required columns with neutral values. A voided setup payment has `voided_at = V0`, `voided_by = U1`, `void_note = "manual void"`.
- **PO(W, "number")** / **EO** / **SO** / **WO** = one live, **not completed** `purchase_orders` / `expense_orders` / `sales_orders` / `work_orders` row in workspace W with `po_number` / `expense_number` / `sales_order_number` / `work_order_number` = number and `invoice_id` None, unless stated. Not completed (spec Notes O1) = PO `current_status_id` → ST(W, "Draft"); SO `order_completed=False`; EO `completed_at=None`; WO `status="DRAFT"`. The executor fills the other required columns neutrally. "Live" follows spec `create_invoice` R9d: a PO or EO has `voided = False`; a WO has `is_deleted = False` and a `status` other than `"VOIDED"`; an SO has no such flag. A **non-live** PO or EO is written "with `voided=True`". A non-live WO is written "with `is_deleted=True`" or "with `status="VOIDED"`". Never set `is_deleted` on `purchase_orders`, `expense_orders` or `sales_orders`, because that column does not exist there.
- **ST(W, "name")** = one `statuses` row with `name` exactly as given (other required columns neutral, workspace W if the table has a workspace column). `current_status_id` is NOT NULL, so every PO points at one. "PO … stage `X`" = `current_status_id` → ST(W, "X").
- **Completed** (spec F2): PO stage `Complete`; SO `order_completed=True`; EO `completed_at=V0`; WO `status="COMPLETED"`. Written e.g. "PO(W1, "PO-1") stage `Complete`", "SO(W1, "SO-1") completed".
- **CN** = credit note (spec F6): an INV (confirmed, `invoice_type "receivable"`) with `order_type`/`order_id` of the order the case names, plus a POR(W1) or SOR(W1) row with `invoice_id = CN.id` whose order reference points at that order. **OI** = INV(`invoice_number="ORD-1"`), the order's own confirmed invoice: in CN cards the order has `invoice_id = OI.id` unless stated.
- No case ever sets `invoice_status = "locked"` (spec Overview, BUG-2735): a frozen invoice is built only from its order's state.
- **HIST(inv)** = one `invoice_status_tracker` row: `workspace_id` = inv's workspace, `invoice_id = inv.id`, `from_status "draft"`, `to_status "confirmed"`, `changed_by U1`, `changed_at V0`.
- **POR(W)** / **SOR(W)** = one `purchase_order_returns` / `sales_order_returns` row in workspace W; **MLED(W)** = one `machine_item_ledger` row in W (with its own machine and item rows, `transaction_type`, `quantity 1`, `unit_cost 1.00`, `total_cost 1.00`, `qty_before 0`, `qty_after 1`, `source_type`, `performed_by U1`). The executor fills the other required columns neutrally. The `invoice_id` is set as the case says. A POR/SOR has `status "pending"`, `paid False` unless the case says otherwise (spec `void_invoice` R3c: `pending`, `completed`, `voided`).
- **EVT(inv, t, performed_by=None)** = one `invoice_events` row inserted directly for inv with explicit `created_at = t`, `event_type "note"`, `description "n"`, `metadata_json None`.

**Payload shorthand:**
- **CRT(k=v, …)** = `AccountInvoiceCreate(account_id=A1.id, invoice_type="payable", invoice_date=date(2026, 9, 1), **k)`, plus `invoice_amount=Decimal("0.00")` **only if** `"invoice_amount" in AccountInvoiceCreate.model_fields` (best-practice default, delegated by reviewer — see G1).
- **UPD(k=v, …)** = `AccountInvoiceUpdate(**k)`. Only the listed fields are sent, so `model_fields_set` is exactly those.

**Time:** `app.managers.account_invoice_manager.utcnow` is patched in every test to return **NOW = `datetime(2026, 9, 27, 12, 0, 0)`**, with the same tz-awareness as the real `app.utils.time.utcnow`. Column defaults (`created_at` of events and items) are not patched. **V0** = `datetime(2026, 9, 1, 8, 0, 0)` and **L0** = `datetime(2026, 9, 2, 9, 0, 0)` are earlier timestamps set on setup rows.

**Events:** "E(type, "desc", by, meta)" = one `invoice_events` row with that `event_type`, exact `description`, `performed_by = by`, `metadata_json == meta`, `invoice_id` = the invoice's id and `workspace_id` = its workspace. "0 events" = zero `invoice_events` rows for that invoice id, re-read. "Events: E1" = exactly that list for the invoice, in id order, counting only rows written by the action (setup EVT rows are listed separately when present).

**Re-read:** after the call, expire the session and query the rows again from the DB. Do not rely only on the returned object. "Unchanged" = every column listed in the INV defaults, plus the overrides, still has its setup value.

**Error cases:** "nothing written" = the invoice row is unchanged, 0 events, and no new `account_invoices` rows in W1 or W2. Actions expected to fail at flush with a DB error run inside `session.begin_nested()`. After the error, roll back the savepoint and then re-read.
**Session clean** = right after the raise, before any re-read, `expire_all()` or savepoint rollback: `not db.new`, `not db.dirty`, `not db.deleted` (three asserts).
**Freeze texts** (spec F5, `revert_to_draft` R2a/R3a, `void_invoice` R3c; compare with `==`): RETTXT = `"This return is completed — its goods have already moved. Start a new return or issue a separate credit note."`. LOCK(kind) = `"Invoice is locked — the linked " + kind + " is completed. Correct it with a credit note or return."` with kind one of `"purchase order"`, `"sales order"`, `"expense order"`, `"work order"`. CNTXT = `"Return credit notes cannot be reverted to draft. Void it and create a new return instead."`. RCVTXT = `"Cannot revert to draft — goods have been received on the linked order. Record a return instead."`.

**SQL capture:** a SQLAlchemy `before_cursor_execute` listener on the test connection records every statement run during the action only (not the setup). "Locks the invoice" = at least one captured statement is a SELECT from `account_invoices` containing `FOR UPDATE`. "Locks the return T" = at least one captured statement is a SELECT from table T (`purchase_order_returns` or `sales_order_returns`) containing `FOR UPDATE`.

**Lists:** `list_invoices` returns a list, and "→ [X, Y]" means exactly those invoices, in that order (compare ids). "→ {X, Y}" means exactly that set, in any order. Page methods return `(items, total)`, written "→ ([X, Y], 2)".

**Race simulations:** none.

---

## `AccountInvoiceManager._get_or_404`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| G4-01 | R1 | happy | CI in W1 | `_get_or_404(session, CI.id, W1)` | returns an `AccountInvoice` with `id == CI.id`, `invoice_status == "confirmed"`; CI unchanged | pass |
| G4-02 | R1 | soft-delete | VI in W1; A1 has `is_deleted=True`, `is_active=False` | `_get_or_404(session, VI.id, W1)` | returns the invoice with `id == VI.id`, `invoice_status == "voided"` | pass |
| G4-03 | R1 | boundary | DI in W1; A1 has `is_active=False` | `_get_or_404(session, DI.id, W1)` | returns the invoice with `id == DI.id`, `invoice_status == "draft"` | pass |
| G4-04 | R2; Errors 1 | error | no invoices | `_get_or_404(session, NOID, W1)` | raises `HTTPException` 404, detail `"Invoice with ID 999999 not found"`; no `account_invoices` rows in W1 | pass |
| G4-05 | R3; Errors 1 | isolation | INV in W2 (id X) | `_get_or_404(session, X, W1)` | raises `HTTPException` 404, detail `f"Invoice with ID {X} not found"`; the W2 row is unchanged | pass |

## `AccountInvoiceManager._log_event`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| LOG-01 | R1, R2 | happy | INV in W2 (id X) | `_log_event(session, inv, "note_added", "Note added", performed_by=U3.id, metadata={"k": "v", "n": 2})` | returns `None`; re-read: exactly 1 event for X, with `id` not None, `workspace_id=W2`, `invoice_id=X`, `event_type="note_added"`, `description="Note added"`, `performed_by=U3.id`, `metadata_json={"k": "v", "n": 2}`, `created_at` not None | pass |
| LOG-02 | R1 | side-effect | CI | `_log_event(session, CI, "x", "y")` (no `performed_by`, no `metadata`) | returns `None`; re-read: 1 event, `event_type="x"`, `description="y"`, `performed_by is None`, `metadata_json is None`, `workspace_id=W1` | pass |
| LOG-03 | R1 | boundary | CI | `_log_event(session, CI, "e"*50, "fifty")` | returns `None`; re-read: 1 event with `event_type == "e"*50` | pass |
| LOG-04 | R1 | boundary | CI | `_log_event(session, CI, "e"*51, "fifty-one")` inside a savepoint | raises SQLAlchemy `DataError`; after the savepoint rollback: 0 events for CI | pass |
| LOG-05 | Errors (non-JSON metadata) | error | CI | `_log_event(session, CI, "x", "y", metadata={"when": object()})` inside a savepoint | raises an exception (any `Exception` subclass) during the call/flush; after the savepoint rollback: 0 events for CI | pass |

## `AccountInvoiceManager._recalculate_payment_status`

Target: a transient `AccountInvoice(invoice_amount=a, paid_amount=p, payment_status=s)` (never added to the session). Every case also asserts that the call returns `None` (spec G12).

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| RPS-01 | R1 | boundary | a=100.00, p=100.00, s="unpaid" | call | returns `None`; `payment_status == "paid"` | pass |
| RPS-02 | R1 | boundary | a=0.00, p=0.00, s="unpaid" | call | returns `None`; `payment_status == "paid"` | pass |
| RPS-03 | R1 | happy | a=100.00, p=150.00, s="partial" | call | returns `None`; `payment_status == "paid"` | pass |
| RPS-04 | R1, R2 | boundary | a=100.00, p=99.99, s="paid" | call | returns `None`; `payment_status == "partial"` | pass |
| RPS-05 | R2 | boundary | a=100.00, p=0.01, s="unpaid" | call | returns `None`; `payment_status == "partial"` | pass |
| RPS-06 | R3 | happy | a=100.00, p=0.00, s="partial" | call | returns `None`; `payment_status == "unpaid"` | pass |
| RPS-07 | R3 | boundary | a=100.00, p=0.00, s="overdue" | call | returns `None`; `payment_status == "unpaid"` | pass |

## `AccountInvoiceManager._recalculate_invoice_amount`

Every case also asserts that the call returns `None` (spec G12).

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| RIA-01 | R1, R3 | happy | DI (amount 1000.00, paid 0.00, "unpaid"); ITEM(DI, 100.25), ITEM(DI, 50.50), ITEM(DI, 0.10) | `_recalculate_invoice_amount(session, DI)`, then `session.flush()` | returns `None`; in memory: `invoice_amount == Decimal("150.85")`, `payment_status == "unpaid"`; re-read after the flush: same values | pass |
| RIA-02 | R1 | isolation | DI; ITEM(DI, 200.00); one `invoice_items` row with `invoice_id = DI.id` but `workspace_id = W2`, subtotal 999.00; another draft J = INV(invoice_status="draft") with ITEM(J, 50.00) | call on DI | returns `None`; `DI.invoice_amount == Decimal("200.00")`; J's amount still 1000.00 | pass |
| RIA-03 | R2, R3 | boundary | DI (amount 500.00, paid 0.00, "unpaid"), no items | call | returns `None`; `invoice_amount == Decimal("0.00")`; `payment_status == "paid"` | pass |
| RIA-04 | R3 | side-effect | DI (paid 100.00, "unpaid"); ITEM(DI, 300.00) | call | returns `None`; `invoice_amount == Decimal("300.00")`; `payment_status == "partial"` | pass |

## `AccountInvoiceManager.create_invoice`

Acting user U1 in these cases (so `created_by` can be checked against U1), unless stated.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| C-01 | R5, R6, R7, R8 | happy | A1; no invoices | `create_invoice(session, CRT(), W1, U1.id)` | returns an invoice with `id` not None; re-read that row: `workspace_id=W1`, `account_id=A1.id`, `invoice_type="payable"`, `invoice_date=2026-09-01`, `invoice_status="draft"`, `payment_status="unpaid"`, `paid_amount == 0.00`, `invoice_amount == 0.00`, `receiving_started is False`, `allow_payments is True`, `created_by=U1.id`, `created_at` not None, and `updated_by`, `updated_at`, `last_synced_at`, `void_note`, `due_date`, `description`, `notes`, `invoice_number`, `vendor_invoice_number`, `order_type`, `order_id`, `payment_locked_reason` all None; Events: E("created", "Draft invoice created", U1.id, {"invoice_type": "payable", "account_id": A1.id}) | pass |
| C-02 | R5, R6, R8 | side-effect | A2 | `create_invoice(session, CRT(account_id=A2.id, invoice_type="receivable", due_date=date(2026, 10, 15), description="Desc", notes="Notes", invoice_number="INV-77", vendor_invoice_number="V-77", payment_locked_reason="Hold", allow_payments=False), W1, U2.id)` | returns the invoice; re-read: `account_id=A2.id`, `invoice_type="receivable"`, `due_date=2026-10-15`, `description="Desc"`, `notes="Notes"`, `invoice_number="INV-77"`, `vendor_invoice_number="V-77"`, `payment_locked_reason="Hold"`, `allow_payments is False`, `created_by=U2.id`, `invoice_status="draft"`; Events: E("created", "Draft invoice created", U2.id, {"invoice_type": "receivable", "account_id": A2.id}) | pass |
| C-03 | R1; Errors 1 | error | no accounts other than A1/A2 | `create_invoice(session, CRT(account_id=NOID), W1, U1.id)` | raises `HTTPException` 404, detail `"Account with ID 999999 not found"`; 0 `account_invoices` rows in W1; 0 `invoice_events` rows in W1 | pass |
| C-04 | R1; Errors 1 | isolation | AX in W2 | `create_invoice(session, CRT(account_id=AX.id), W1, U1.id)` | raises 404, detail `f"Account with ID {AX.id} not found"`; 0 invoices in W1 and W2; 0 events | pass |
| C-05 | R2; Errors 2 | error | A1 with `is_deleted=True`, `is_active=False`, `allow_invoices=False` | `create_invoice(session, CRT(), W1, U1.id)` | raises `HTTPException` 400, detail `"Cannot create invoice for deleted account"` (the deleted check comes before the active/allow checks); nothing written | pass |
| C-06 | R3; Errors 3 | error | A1 with `is_active=False`, `allow_invoices=False` | same call | raises 400, detail `"Cannot create invoice for inactive account"`; nothing written | pass |
| C-07 | R4; Errors 4 | error | A1 with `allow_invoices=False` | same call | raises `HTTPException` 403, detail `"Invoices are not allowed for this account"`; nothing written | pass |
| C-08 | R9a, R9b | happy | P1 = PO(W1, "PO-1001") | `create_invoice(session, CRT(order_type="purchase_order", order_id=P1.id), W1, U1.id)` | returns the invoice; re-read: `order_type="purchase_order"`, `order_id=P1.id`, `invoice_status="draft"` | pass |
| C-09 | R9a | happy | — | (target `schema`) build `CRT(order_type=t, order_id=1)` for each t in `"purchase_order"`, `"expense_order"`, `"sales_order"`, `"work_order"` | each builds without error, and `.order_type == t`, `.order_id == 1` (both link fields sent, so R9c is satisfied) | pass |
| C-10 | R9a [BUG-624] | bug | — | build `CRT(order_type="  Purchase_Order ", order_id=1)` | no error; `.order_type == "purchase_order"` | xfail BUG-624 — fails today on: `.order_type == "  Purchase_Order "` (stored as typed) |
| C-11 | R9a [BUG-624]; Errors 5 | bug | — | build `CRT(order_type="banana", order_id=1)` | raises `pydantic.ValidationError` | xfail BUG-624 — fails today on: no error raised |
| C-12 | R9b [BUG-625]; Errors 7 | bug | no orders | `create_invoice(session, CRT(order_type="purchase_order", order_id=NOID), W1, U1.id)` | raises `HTTPException` 404, detail `"Order with ID 999999 not found"`; 0 invoices in W1; 0 events | xfail BUG-625 — fails today on: no exception (invoice created) |
| C-13 | R9b [BUG-625]; Errors 7 | bug | PW = PO(W2, "PO-9001") | `create_invoice(session, CRT(order_type="purchase_order", order_id=PW.id), W1, U1.id)` | raises 404, detail `f"Order with ID {PW.id} not found"`; 0 invoices in W1; 0 events | xfail BUG-625 — fails today on: no exception |
| C-14 | R9b, R9d [BUG-625]; Errors 7 | bug | PD = PO(W1, "PO-1002") with `voided=True` | `create_invoice(session, CRT(order_type="purchase_order", order_id=PD.id), W1, U1.id)` | raises 404, detail `f"Order with ID {PD.id} not found"`; 0 invoices in W1; 0 events | xfail BUG-625 — fails today on: no exception |
| C-15 | R9b [BUG-625]; Errors 7 | bug | P1 = PO(W1, "PO-1001"); no `expense_orders` row with `id == P1.id` in any workspace (the executor asserts this precondition) | `create_invoice(session, CRT(order_type="expense_order", order_id=P1.id), W1, U1.id)` | raises 404, detail `f"Order with ID {P1.id} not found"`; 0 invoices in W1; 0 events | xfail BUG-625 — fails today on: no exception |
| C-16 | R9 [BUG-627] | bug | — | inspect `AccountInvoiceCreate.model_fields` | `"invoice_amount" not in AccountInvoiceCreate.model_fields` | xfail BUG-627 — fails today on: the field exists |
| C-17 | R9 [BUG-627] | bug | A1 | build `AccountInvoiceCreate(account_id=A1.id, invoice_type="payable", invoice_date=date(2026, 9, 1))` (no amount), then `create_invoice(session, <it>, W1, U1.id)` | no error; re-read: `invoice_amount == 0.00`, `payment_status == "unpaid"` | xfail BUG-627 — fails today on: `ValidationError` at build (`invoice_amount` required) |
| C-18 | R9 [BUG-627]; Errors 6 | bug | — | build `AccountInvoiceCreate(account_id=1, invoice_type="payable", invoice_date=date(2026, 9, 1), invoice_amount=Decimal("1000.00"))` | raises `pydantic.ValidationError`, and one error's `loc == ("invoice_amount",)` (a client amount is rejected, never silently ignored — spec R9, G1) | xfail BUG-627 — fails today on: no error raised |
| C-19 | R9c [BUG-625]; Errors 8 | bug | — | (target `schema`) build `CRT(order_id=5)` (no `order_type`) | raises `pydantic.ValidationError`, and one error's `loc == ("order_type",)` | xfail BUG-625 — fails today on: no error raised |
| C-20 | R9c [BUG-625]; Errors 8 | bug | — | (target `schema`) build `CRT(order_type="purchase_order")` (no `order_id`) | raises `pydantic.ValidationError`, and one error's `loc == ("order_id",)` | xfail BUG-625 — fails today on: no error raised |
| C-21 | R9c [BUG-625]; Errors 8 | bug | — | (target `schema`) build `CRT(order_type="purchase_order", order_id=None)` (explicit null) | raises `pydantic.ValidationError`, and one error's `loc == ("order_id",)` | xfail BUG-625 — fails today on: no error raised |
| C-22 | R9b, R9d [BUG-625]; Errors 7 | bug | ED = EO(W1, "EXP-1002") with `voided=True` | `create_invoice(session, CRT(order_type="expense_order", order_id=ED.id), W1, U1.id)` | raises `HTTPException` 404, detail `f"Order with ID {ED.id} not found"`; 0 invoices in W1; 0 events | xfail BUG-625 — fails today on: no exception (invoice created) |
| C-23 | R9b, R9d [BUG-625]; Errors 7 | bug | WD = WO(W1, "WO-1002") with `is_deleted=True` (status = the neutral default, not `"VOIDED"`) | `create_invoice(session, CRT(order_type="work_order", order_id=WD.id), W1, U1.id)` | raises `HTTPException` 404, detail `f"Order with ID {WD.id} not found"`; 0 invoices in W1; 0 events | xfail BUG-625 — fails today on: no exception |
| C-24 | R9b, R9d [BUG-625]; Errors 7 | bug | WV = WO(W1, "WO-1003") with `is_deleted=False`, `status="VOIDED"` | `create_invoice(session, CRT(order_type="work_order", order_id=WV.id), W1, U1.id)` | raises `HTTPException` 404, detail `f"Order with ID {WV.id} not found"`; 0 invoices in W1; 0 events | xfail BUG-625 — fails today on: no exception |
| C-25 | R9b, R9d | boundary | E1 = EO(W1, "EXP-1001") (live: `voided=False`) | `create_invoice(session, CRT(order_type="expense_order", order_id=E1.id), W1, U1.id)` | no exception; returns an invoice with `id` not None; re-read: `order_type="expense_order"`, `order_id=E1.id`, `invoice_status="draft"`; Events: E("created", "Draft invoice created", U1.id, {"invoice_type": "payable", "account_id": A1.id}) | pass |
| C-26 | R9b, R9d | boundary | Wo1 = WO(W1, "WO-1001") (live: `is_deleted=False`, status = the neutral default; the executor asserts `status != "VOIDED"` as a precondition) | `create_invoice(session, CRT(order_type="work_order", order_id=Wo1.id), W1, U1.id)` | no exception; returns an invoice with `id` not None; re-read: `order_type="work_order"`, `order_id=Wo1.id`, `invoice_status="draft"` | pass |
| C-27 | R9b, R9d | boundary | S1 = SO(W1, "SO-1001") | `create_invoice(session, CRT(order_type="sales_order", order_id=S1.id), W1, U1.id)` | no exception; returns an invoice with `id` not None; re-read: `order_type="sales_order"`, `order_id=S1.id`, `invoice_status="draft"` | pass |

## `AccountInvoiceManager.get_invoice`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| GI-01 | R1 | happy | DI in W1 | `get_invoice(session, DI.id, W1)` | returns the invoice with `id == DI.id` | pass |
| GI-02 | R1 | isolation | INV in W2 (id X) | `get_invoice(session, X, W1)` | raises 404, detail `f"Invoice with ID {X} not found"` | pass |
| GI-03 | R1 | error | none | `get_invoice(session, NOID, W1)` | raises 404, detail `"Invoice with ID 999999 not found"` | pass |

## `AccountInvoiceManager.list_invoices` (shared filters R1–R14)

Call: `list_invoices(session, W1, …)` with only the named filters. Invoices are INV rows (confirmed, amount 1000.00, date 2026-09-01) unless stated.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| L-01 | R1 | isolation | I1 = INV; I2 = INV in W2 | no filters | → [I1] | pass |
| L-02 | R2 | soft-delete | I1 on A1; I2 on A2 with A2 `is_active=False`; A3 = account "Gamma" in W1 with `is_deleted=True`, I3 on A3 | no filters | → {I1, I2} | pass |
| L-03 | R3 | happy | I1 draft, I2 confirmed, I3 voided | no filters | → {I1, I2, I3} | pass |
| L-04 | R4 | happy | I1 on A1, I2 on A2 | `account_id=A2.id` | → [I2] | pass |
| L-05 | R4 | boundary | I1 on A1, I2 on A2 | `account_id=0` | → [] | pass |
| L-06 | R5 | happy | I1 payable, I2 receivable | `invoice_type="payable"` | → [I1] | pass |
| L-07 | R5 | boundary | I1 payable, I2 receivable | `invoice_type="Payable"` | → [] (case-sensitive) | pass |
| L-08 | R5 | boundary | I1 payable, I2 receivable | `invoice_type=""` | → {I1, I2} | pass |
| L-09 | R5 | happy | I1 unpaid, I2 partial (paid 200.00), I3 paid (paid 1000.00) | `payment_status="partial"` | → [I2] | pass |
| L-10 | R5 | happy | I1 draft, I2 confirmed, I3 voided | `invoice_status="voided"` | → [I3] | pass |
| L-11 | R5 | boundary | I1 draft, I2 confirmed | `invoice_status="bogus"` | → [] | pass |
| L-12 | R6 | boundary | invoice_dates 2026-03-01 (I1), 03-02 (I2), 03-03 (I3), 03-04 (I4) | `invoice_date_from=date(2026,3,2)`, `invoice_date_to=date(2026,3,3)` | → [I3, I2] | pass |
| L-13 | R7 | boundary | due_dates 2026-03-01 (I1), 03-02 (I2), 03-03 (I3), None (I4) | `due_date_from=date(2026,3,2)` | → {I2, I3} (I4 without a due date excluded) | pass |
| L-14 | R7 | boundary | same as L-13 | `due_date_to=date(2026,3,2)` | → {I1, I2} | pass |
| L-15 | R8 | boundary | amounts 99.99 (I1), 100.00 (I2), 200.00 (I3), 200.01 (I4) | `amount_min=Decimal("100.00")`, `amount_max=Decimal("200.00")` | → {I2, I3} | pass |
| L-16 | R8 | boundary | amounts 0.00 (I1, paid 0), 50.00 (I2) | `amount_max=Decimal("0")` | → [I1] (0 is a real bound, not "no filter") | pass |
| L-17 | R9 | happy | I1 `invoice_number="INV-2026-0042"`, I2 `"INV-2026-0100"` | `invoice_number_search="v-2026-004"` | → [I1] (case-insensitive, middle of the value) | pass |
| L-18 | R9 | boundary | same as L-17 | `invoice_number_search="  v-2026-0042  "` | → [I1] (trimmed; not all digits, so no id match) | pass |
| L-19 | R9 | happy | I1 `vendor_invoice_number="VND-ABC-9"`, I2 `"VND-XYZ-1"`; both invoice_number None | `invoice_number_search="abc"` | → [I1] | pass |
| L-20 | R9 | happy | P = PO(W1, "PO-7788"); I1 `order_type="purchase_order"`, `order_id=P.id`, invoice_number "ALPHA"; I2 invoice_number "BRAVO" | `invoice_number_search="o-7788"` | → [I1] | pass |
| L-21 | R9 | happy | E = EO(W1, "EXP-5566"); I1 `order_type="expense_order"`, `order_id=E.id`; I2 unlinked | `invoice_number_search="xp-55"` | → [I1] | pass |
| L-22 | R9 | happy | I1, I2 unlinked; S = SO(W1, "SO-3344") with `invoice_id=I1.id` | `invoice_number_search="so-33"` | → [I1] | pass |
| L-23 | R9 | happy | I1, I2 unlinked; Wo = WO(W1, "WO-2211") with `invoice_id=I1.id` | `invoice_number_search="wo-22"` | → [I1] | pass |
| L-24 | R9 | isolation | PW = PO(W2, "PO-9911"); no W1 purchase order has `id == PW.id` (precondition asserted); I1 in W1 with `order_type="purchase_order"`, `order_id=PW.id`, invoice_number "ALPHA" | `invoice_number_search="o-9911"` | → [] | pass |
| L-25 | R9 | boundary | I1 invoice_number `"A%B"`, I2 `"AXB"` | `invoice_number_search="%"` | → [I1] (`%` literal) | pass |
| L-26 | R9 | boundary | I1 `"A_B"`, I2 `"AXB"` | `invoice_number_search="_"` | → [I1] (`_` literal) | pass |
| L-27 | R9 | boundary | I1 `"A\B"` (one backslash), I2 `"AB"` | `invoice_number_search="\\"` (one backslash) | → [I1] | pass |
| L-28 | R9 | boundary | I1 `"A-1"`, I2 `"B-2"`, I3 number None | `invoice_number_search=""` | → {I1, I2, I3} | pass |
| L-29 | R9a [BUG-637] | bug | same as L-28 | `invoice_number_search="   "` | → {I1, I2, I3} | xfail BUG-637 — fails today on: the result is not all three (whitespace becomes an empty pattern) |
| L-30 | R10 | happy | I1 invoice_number "ALPHA", I2 "BRAVO" (no digits anywhere) | `invoice_number_search=str(I2.id)` | → [I2] | pass |
| L-31 | R10 | boundary | same as L-30 | `invoice_number_search=f"  {I2.id}  "` | → [I2] (trimmed before the digit check) | pass |
| L-32 | R10 | boundary | same as L-30 | `invoice_number_search=f"{I2.id}x"` | → [] (not all digits → no id match) | pass |
| L-33 | R10 [BUG-622] | bug | same as L-30 | `invoice_number_search="²"` | no exception; → [] | xfail BUG-622 — fails today on: `ValueError` raised |
| L-34 | R10 [BUG-622] | bug | same as L-30 | `invoice_number_search` = `str(I2.id)` with each ASCII digit replaced by its Arabic-Indic digit (`"0123456789"` → `"٠١٢٣٤٥٦٧٨٩"`) | no exception; → [] | xfail BUG-622 — fails today on: returns [I2] |
| L-35 | R11 | happy | I1 on A1 "Acme Traders", I2 on A2 "Beta Supplies" | `account_name_search="ME TR"` | → [I1] | pass |
| L-36 | R11 [BUG-622] | bug | A1 renamed `"100% Cotton"`; I1 on A1; I2 on A2 "Beta Supplies" | `account_name_search="%"` | → [I1] | xfail BUG-622 — fails today on: I2 also returned |
| L-37 | R11 [BUG-622] | bug | A1 renamed `"Dhaka_Mills"`; I1 on A1; I2 on A2 "Beta Supplies" | `account_name_search="_"` | → [I1] | xfail BUG-622 — fails today on: I2 also returned |
| L-38 | R11 [BUG-622] | bug | A1 renamed `"Back\Slash"` (one backslash); I1 on A1; I2 on A2 | `account_name_search="\\"` (one backslash) | → [I1] | xfail BUG-622 — fails today on: I1 not returned (unescaped backslash) |
| L-39 | R12 | happy | I1 A1 payable; I2 A1 receivable; I3 A2 payable | `account_id=A1.id`, `invoice_type="payable"` | → [I1] | pass |
| L-40 | R13 | happy | I1 date 2026-03-01; I2 date 2026-03-05; I3 date 2026-03-05 inserted after I2 (higher id) | no filters | → [I3, I2, I1] | pass |
| L-41 | R14 | boundary | I1..I5 dated 2026-03-01..03-05 | `skip=1`, `limit=2` | → [I4, I3] | pass |
| L-42 | R14 | boundary | 101 invoices dated 2026-01-01 + n days (n = 0..100) | no skip/limit | returns 100 invoices; the oldest (2026-01-01) is not among them; the first is dated 2026-04-11 | pass |
| L-43 | R12, R14 | boundary | P1..P3 payable dated 03-01..03-03; R1..R3 receivable dated 03-04..03-06 | `invoice_type="payable"`, `limit=2` | → [P3, P2] (filter before paging) | pass |
| L-44 | R5 | boundary | I1 draft unpaid; I2 confirmed partial (paid 200.00); I3 voided unpaid | `payment_status=""`, `invoice_status=""` | → {I1, I2, I3} (empty string = no filter on either column) | pass |
| L-45 | R5a [BUG-635] | bug | I1 confirmed unpaid due 2026-09-26; I2 confirmed partial (paid 200.00) due 2020-01-01; I3 confirmed unpaid due 2026-09-27 (= today); I4 confirmed unpaid due None; I5 draft unpaid due 2020-01-01; I6 voided unpaid due 2020-01-01; I7 confirmed paid (paid 1000.00) due 2020-01-01 | `payment_status="overdue"` | → {I1, I2} | xfail BUG-635 — fails today on: returns [] |
| L-46 | R5, R5a | boundary | same rows as L-45 | `payment_status="unpaid"` | → {I1, I3, I4, I5, I6} (stored-column equality; I1, though overdue, still matches `unpaid`) | pass |

## `AccountInvoiceManager.list_open_invoices_page`

Call: `list_open_invoices_page(session, workspace_id=W1, account_id=A1.id, …)`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| LO-01 | R1, R2 | happy | on A1: I1 confirmed unpaid; I2 confirmed partial (paid 200.00); I3 confirmed paid (paid 1000.00); I4 voided unpaid; on A2: I5 confirmed unpaid | defaults | items = {I1, I2}; total == 2 | pass |
| LO-02 | R2 [BUG-634] | bug | on A1: I1 confirmed unpaid (date 09-02); I2 draft unpaid (date 09-01) | defaults | → ([I1], 1) | xfail BUG-634 — fails today on: I2 included, total 2 |
| LO-03 | R1 | isolation | INV in W2 on AX (confirmed unpaid) | `account_id=AX.id` | → ([], 0) | pass |
| LO-04 | R1 | soft-delete | A1 `is_deleted=True`; I1 on A1 confirmed unpaid | defaults | → ([], 0) | pass |
| LO-05 | R3 | happy | I1 date 03-01; I2 date 03-03; I3 date 03-03 inserted after I2 | defaults | → ([I3, I2, I1], 3) | pass |
| LO-06 | R3 | happy | X (`order_type="purchase_order"`, `order_id=55`, 03-01); Y (unlinked, 03-05); Z (`purchase_order`, 55, 03-03); V (`purchase_order`, 66, 03-04); E (`order_type="expense_order"`, `order_id=55`, 03-06) | `prioritize_purchase_order_id=55` | → ([Z, X, E, Y, V], 5) | pass |
| LO-07 | R4 | boundary | 12 open invoices on A1 dated 2026-09-01..09-12 | defaults | items = the 10 dated 09-12 down to 09-03, in that order; total == 12 | pass |
| LO-08 | R4 | boundary | I1..I5 dated 03-01..03-05 | `skip=2`, `limit=2` | → ([I3, I2], 5) | pass |
| LO-09 | R3 | boundary | X (`order_type="purchase_order"`, `order_id=0`, 03-01); Y (unlinked, 03-05) — both inserted directly, confirmed unpaid on A1 | `prioritize_purchase_order_id=0` | → ([X, Y], 2) (`0` is a real value, not "not given") | pass |

## `AccountInvoiceManager.list_invoices_page`

Call: `list_invoices_page(session, workspace_id=W1, …)`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| LP-01 | R1 | happy | I1 A1 payable `invoice_number="INV-0042"`; I2 A1 payable `"INV-0100"`; I3 A1 receivable `"INV-0042B"`; I4 A2 payable `"INV-0042C"`; INV in W2 payable `"INV-0042"` | `account_id=A1.id`, `invoice_type="payable"`, `invoice_number_search="v-0042"` | → ([I1], 1) | pass |
| LP-02 | R1 | soft-delete | I1 A1 voided; I2 A1 draft; A3 "Gamma" with `is_deleted=True`, I3 on A3 | no filters | items = {I1, I2}; total == 2 | pass |
| LP-03 | R2 | happy | I1 confirmed unpaid; I2 confirmed partial (paid 200.00); I3 confirmed paid; I4 voided unpaid | `open_balance_only=True` | items = {I1, I2}; total == 2 | pass |
| LP-04 | R2 [BUG-634] | bug | I1 confirmed unpaid (09-02); I2 draft unpaid (09-01) | `open_balance_only=True` | → ([I1], 1) | xfail BUG-634 — fails today on: I2 included |
| LP-05 | R3 | happy | same rows as LO-06 | `prioritize_purchase_order_id=55` | → ([Z, X, E, Y, V], 5) | pass |
| LP-06 | R3 | boundary | I1..I5 dated 03-01..03-05 | `skip=1`, `limit=2` | → ([I4, I3], 5) | pass |
| LP-07 | R3 | boundary | 101 invoices dated 2026-01-01 + n days | defaults | 100 items, the first dated 2026-04-11; total == 101 | pass |

## `AccountInvoiceManager.get_invoices_hub_summary`

Call: `get_invoices_hub_summary(session, workspace_id=W1)`. Result written `(payable, receivable, any, active)`, with each type tuple `(open_count, outstanding_total, overdue_count, accounts_with_open_count)`. Totals are compared as `Decimal`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| HS-01 | R2, R3, R4 | happy | A1: P1 payable confirmed unpaid 1000.00/0; P2 payable confirmed partial 500.00/200.00; P3 payable confirmed paid 300.00/300.00; P4 payable voided unpaid 700.00/0. A2: P5 payable confirmed unpaid 250.00/0; R1 receivable confirmed unpaid 400.00/0; R2 receivable confirmed partial 100.00/40.00. No due dates | call | returns `((3, Decimal("1550.00"), 0, 2), (2, Decimal("460.00"), 0, 1), 2, 2)` | pass |
| HS-02 | R1, R4 | soft-delete | W1 has only A3 "Gamma" (`is_deleted=True`, payable confirmed unpaid 900.00) and A4 "Delta" (`is_active=False`, payable confirmed unpaid 600.00) | call | returns `((1, Decimal("600.00"), 0, 1), (0, 0, 0, 0), 1, 0)`, with each total `== 0` as a Decimal | pass |
| HS-03 | R1 | isolation | A1: payable confirmed unpaid 100.00; W2: AX payable confirmed unpaid 5000.00 and receivable confirmed unpaid 7000.00 | call | returns `((1, Decimal("100.00"), 0, 1), (0, 0, 0, 0), 1, 2)` | pass |
| HS-04 | R2, R3, R4 | boundary | A1, A2, no invoices | call | returns `((0, 0, 0, 0), (0, 0, 0, 0), 0, 2)`; both outstanding totals `== Decimal("0")` (not None) | pass |
| HS-05 | R2, R3 [BUG-634] | bug | A1: payable confirmed unpaid 1000.00; A2: payable **draft** unpaid 5000.00 | call | payable == `(1, Decimal("1000.00"), 0, 1)`; any == 1 | xfail BUG-634 — fails today on: payable == (2, 6000.00, 0, 2) |
| HS-06 | R2 [BUG-635] | bug | A1 payable confirmed: unpaid 1000/0 due 2020-01-01; partial 500/100 due 2020-01-01; unpaid 200/0 due 2099-12-31; unpaid 300/0 due None; paid 400/400 due 2020-01-01. A2 receivable confirmed unpaid 150/0 due 2020-01-01 | call | payable `overdue_count == 2`; receivable `overdue_count == 1` | xfail BUG-635 — fails today on: both overdue counts are 0 |
| HS-07 | R2, R3 | happy | same as HS-06 | call | payable open_count 4, outstanding `Decimal("1900.00")`, accounts 1; receivable open_count 1, outstanding `Decimal("150.00")`, accounts 1; any == 2; active == 2 (overdue counts not asserted) | pass |
| HS-08 | R3 | happy | A1: payable confirmed unpaid 100 and receivable confirmed unpaid 100; A2: receivable confirmed partial 100/50; A3 "Gamma" (active): payable confirmed paid 100/100 only | call | any == 2 | pass |
| HS-09 | R4 | boundary | W1: A1, A2 active; A3 "Gamma" `is_active=False`; A4 "Delta" `is_active=True, is_deleted=True`; W2: AX active; no invoices | call | active == 2 | pass |
| HS-10 | R2 [BUG-635] | bug | A1 payable confirmed unpaid 100/0 due 2026-09-26; A1 payable confirmed unpaid 200/0 due 2026-09-27; A2 receivable confirmed unpaid 50/0 due 2026-09-27 (NOW = 2026-09-27) | call | payable `overdue_count == 1`; receivable `overdue_count == 0` | xfail BUG-635 — fails today on: payable `overdue_count == 0` |

## `AccountInvoiceManager.list_accounts_hub_page`

Call: `list_accounts_hub_page(session, workspace_id=W1, …)`. A row is `(account, payable_agg, receivable_agg)`. "agg (o, n, h)" means `outstanding_total == o`, `open_count == n`, `has_overdue is h`. Rows are compared by account id, in order.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| AH-01 | R1 | soft-delete | W1: A1 "Acme Traders", A2 "Beta Supplies" (no invoices), A3 "Delta" `is_deleted=True`, A4 "Gamma" `is_active=False` with no invoices; W2: AX | defaults | rows' accounts = [A1, A2]; total == 2 | pass |
| AH-02 | R2 | happy | A1 payable: confirmed unpaid 1000/0; confirmed partial 500/200; confirmed paid 300/300; voided unpaid 700/0. No receivables | defaults | A1 row: payable agg (1300.00, 2, False); receivable agg (0, 0, False) | pass |
| AH-03 | R1 [BUG-636] | bug | A1 (no invoices); A4 "Gamma" `is_active=False` with payable confirmed unpaid 2000/0 | defaults | rows' accounts = [A1, A4]; total == 2; A4 payable agg (2000.00, 1, False) | xfail BUG-636 — fails today on: A4 missing, total 1 |
| AH-04 | R1 | boundary | A1 (no invoices); A5 "Omega" `is_active=False` with only a payable confirmed paid 300/300 | defaults | rows' accounts = [A1]; total == 1 | pass |
| AH-05 | R2 [BUG-634] | bug | A1 payable: confirmed unpaid 1000/0; draft unpaid 5000/0 | defaults | A1 payable agg outstanding 1000.00, open_count 1 | xfail BUG-634 — fails today on: 6000.00 / 2 |
| AH-06 | R3 [BUG-635] | bug | A1 payable confirmed unpaid 1000/0 due 2020-01-01; A1 receivable confirmed unpaid 500/0 due 2099-12-31 | defaults | A1 payable `has_overdue is True`; receivable `has_overdue is False` | xfail BUG-635 — fails today on: payable `has_overdue` is False |
| AH-07 | R2, R3 | boundary | A1 payable: confirmed unpaid 1000/0 due None; confirmed paid 400/400 due 2020-01-01 | defaults | A1 payable agg (1000.00, 1, False) | pass |
| AH-08 | R4 | happy | A1 "Acme Traders", A2 "Beta Supplies" | `search="ME TR"` | rows' accounts = [A1]; total == 1 | pass |
| AH-09 | R4 [BUG-622] | bug | A1 renamed `"100% Cotton"`; A2 "Beta Supplies" | `search="%"` | rows' accounts = [A1]; total == 1 | xfail BUG-622 — fails today on: A2 also returned |
| AH-10 | R4 [BUG-622] | bug | A1 renamed `"Dhaka_Mills"`; A2 "Beta Supplies" | `search="_"` | rows' accounts = [A1]; total == 1 | xfail BUG-622 — fails today on: A2 also returned |
| AH-11 | R5 | happy | A1: payable confirmed unpaid 100/0; A2: receivable confirmed unpaid 200/0; A3 "Gamma" (active): no invoices; A4 "Delta" (active): payable confirmed paid 50/50 | `section="payable"` | rows' accounts = [A1]; total == 1 (A4 has outstanding 0 → excluded) | pass |
| AH-12 | R5 | happy | same as AH-11 | `section="receivable"` | rows' accounts = [A2]; total == 1 | pass |
| AH-13 | R5 | boundary | same as AH-11 | `section="overview"` | rows' accounts = [A1, A2, A4, A3] (name order: Acme, Beta, Delta, Gamma); total == 4 | pass |
| AH-14 | R5 | boundary | same as AH-11 | `section="bogus"` | same as AH-13 | pass |
| AH-15 | R6 [BUG-623] | bug | W1 accounts only, inserted in this order: N1 "APEX", N2 "Zeta", N3 "Beta", N4 "apex" (all active) | defaults | rows' accounts = [N1, N4, N3, N2] (lower-cased names ascending, then id) | xfail BUG-623 — fails today on: the order is not [N1, N4, N3, N2] — a case-sensitive name order gives [N4, N1, N3, N2] under the test DB's collation (lower case first) and [N1, N3, N2, N4] under a byte-wise collation |
| AH-16 | R6 | happy | W1 accounts only: "Charlie", "Alpha", "Bravo" (inserted in that order) | defaults | names in order == ["Alpha", "Bravo", "Charlie"] | pass |
| AH-17 | R7 | boundary | W1 accounts only: "Acc 1".."Acc 5" | `skip=1`, `limit=2` | names == ["Acc 2", "Acc 3"]; total == 5 | pass |
| AH-18 | R7 | boundary | W1 accounts only: "Acc 01".."Acc 51" | defaults | 50 rows, the last named "Acc 50"; total == 51 | pass |
| AH-19 | R5, R7 | boundary | W1 accounts only: "P1", "P2", "P3", each with payable confirmed unpaid 100/0; "Q1", "Q2" with no invoices | `section="payable"`, `limit=1` | names == ["P1"]; total == 3 | pass |
| AH-20 | R3 [BUG-635] | bug | A1 payable confirmed unpaid 100/0 due 2026-09-26; A2 payable confirmed unpaid 100/0 due 2026-09-27 (NOW = 2026-09-27) | defaults | A1 payable `has_overdue is True`; A2 payable `has_overdue is False` | xfail BUG-635 — fails today on: A1 `has_overdue` is False |
| AH-21 | R6 | boundary | W1 accounts only, inserted in this order: S1 "Same Name", S2 "Same Name", B "Alpha"; then raw SQL `UPDATE accounts SET is_active = TRUE WHERE id = S1.id` is executed (S1's row version moves to the end of the heap) | defaults | rows' accounts = [B, S1, S2] (equal names ordered by id ascending); total == 3 | pass |
| AH-22 | R6 [BUG-623] | bug | W1 accounts only, inserted in this order: K1 "acme", K2 "Acme", K3 "acme" | defaults | rows' accounts = [K1, K2, K3] (case-insensitively equal names → id ascending); total == 3 | xfail BUG-623 — fails today on: the order is not [K1, K2, K3] — case-sensitive order gives [K1, K3, K2] (lower case first) or [K2, K1, K3] (byte-wise) |

## `AccountInvoiceManager.summarize_invoices`

Call: `summarize_invoices(session, W1, …)`. The result is `(count, invoiced, paid, outstanding)`, and totals are compared as `Decimal`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SUM-01 | R1, R2 | happy | A1: confirmed partial 1000/400; confirmed paid 500/500; voided unpaid 700/0 | no filters | returns `(3, Decimal("1500.00"), Decimal("900.00"), Decimal("600.00"))` | pass |
| SUM-02 | R1 | happy | A1: confirmed 1000/0; A2: confirmed 200/0 | `account_id=A2.id` | returns `(1, Decimal("200.00"), Decimal("0"), Decimal("200.00"))` | pass |
| SUM-03 | R2 | boundary | no invoices | no filters | returns `(0, 0, 0, 0)`, with each total `== Decimal("0")` (not None) | pass |
| SUM-04 | R2 [BUG-634] | bug | A1: confirmed 1000/0; draft 5000/0 | no filters | invoiced == 1000.00; paid == 0; outstanding == 1000.00 | xfail BUG-634 — fails today on: invoiced 6000.00 |
| SUM-05 | R1 | happy | same as SUM-04 | no filters | count == 2 (drafts stay in the count) | pass |
| SUM-06 | R1 | isolation | A1: confirmed 1000/0; A3 "Gamma" `is_deleted=True`: confirmed 300/0; W2: AX confirmed 900/0 | no filters | returns `(1, Decimal("1000.00"), Decimal("0"), Decimal("1000.00"))` | pass |

## `AccountInvoiceManager.update_invoice`

Call: `update_invoice(session, inv.id, UPD(…), W1, U2.id)`. Rows are CI / DI / VI from Conventions.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| U-01 | R1; Errors 1 | error | no invoices | `update_invoice(session, NOID, UPD(description="x"), W1, U2.id)` | raises 404, detail `"Invoice with ID 999999 not found"`; 0 invoices, 0 events in W1 | pass |
| U-02 | R1; Errors 1 | isolation | CI inserted in W2 (account AX), id X | `update_invoice(session, X, UPD(due_date=date(2026,12,1)), W1, U2.id)` | raises 404, detail `f"Invoice with ID {X} not found"`; the W2 row is unchanged (`due_date` 2026-10-01, `updated_by` None); 0 events | pass |
| U-03 | R1 [BUG-621] | bug | DI; SQL capture on | `UPD(description="New")` | returns the invoice; captured SQL locks the invoice; re-read `description == "New"` | xfail BUG-621 — fails today on: no captured SELECT on `account_invoices` contains `FOR UPDATE` |
| U-04 | R2; Errors 2 | error | VI | `UPD(due_date=date(2026,12,1), description="x")` | raises `HTTPException` 400, detail `"Voided invoices cannot be edited"`; VI unchanged (`due_date` 2026-10-01, `description` "Old desc", `updated_by` None); 0 events | pass |
| U-05 | R2a | boundary | — | (target `schema`) build `AccountInvoiceUpdate(due_date=None, description=None, notes=None, invoice_number=None, vendor_invoice_number=None, payment_locked_reason=None, order_id=None)` | no error; `model_fields_set` == those 7 names; each value is None | pass |
| U-06 | R2a [BUG-630]; Errors 3 | bug | — | build `AccountInvoiceUpdate(account_id=None)` | raises `ValidationError`, and one error's `loc == ("account_id",)` | xfail BUG-630 — fails today on: no error raised |
| U-07 | R2a [BUG-630]; Errors 3 | bug | — | build `AccountInvoiceUpdate(invoice_type=None)` | raises `ValidationError`, and one error's `loc == ("invoice_type",)` | xfail BUG-630 — fails today on: no error raised |
| U-08 | R2a [BUG-630]; Errors 3 | bug | — | build `AccountInvoiceUpdate(invoice_date=None)` | raises `ValidationError`, and one error's `loc == ("invoice_date",)` | xfail BUG-630 — fails today on: no error raised |
| U-09 | R2a [BUG-630]; Errors 3 | bug | — | build `AccountInvoiceUpdate(allow_payments=None)` | raises `ValidationError`, and one error's `loc == ("allow_payments",)` | xfail BUG-630 — fails today on: no error raised |
| U-10 | R2a, R11 [BUG-630]; Errors 4 | bug | — | build `AccountInvoiceUpdate(invoice_amount=Decimal("750.00"))` | raises `ValidationError` | xfail BUG-630 — fails today on: no error raised |
| U-11 | R11 | boundary | — | (target `schema`) inspect `AccountInvoiceUpdate.model_fields` | none of `invoice_status`, `payment_status`, `paid_amount`, `void_note`, `receiving_started` is a field | pass |
| U-12 | R3, R6, R7, R8, R9 | happy | CI (`due_date` 2026-10-01, `allow_payments` True, `payment_locked_reason` None) | `UPD(due_date=date(2026,11,15), allow_payments=False, payment_locked_reason="Disputed")` | returns the invoice with `id == CI.id`; re-read: `due_date=2026-11-15`, `allow_payments is False`, `payment_locked_reason="Disputed"`, `updated_by=U2.id`, `invoice_status="confirmed"`, `description="Old desc"`; exactly 3 events: E("due_date_changed", "Due date updated", U2.id, {"old_due_date": "2026-10-01", "new_due_date": "2026-11-15"}), E("allow_payments_changed", "Payments disabled", U2.id, {"allow_payments": False}), E("payment_lock_changed", "Payment lock updated", U2.id, {"payment_locked_reason": "Disputed"}) (asserted as a set of (type, description, metadata)) | pass |
| U-13 | R3, R7 | boundary | CI (due 2026-10-01) | `UPD(due_date=None)` | returns the invoice; re-read `due_date is None`, `updated_by=U2.id`; Events: E("due_date_changed", "Due date updated", U2.id, {"old_due_date": "2026-10-01", "new_due_date": None}) | pass |
| U-14 | R7 | boundary | CI with `due_date=None` | `UPD(due_date=date(2026,11,15))` | returns the invoice; re-read `due_date=2026-11-15`; Events: E("due_date_changed", "Due date updated", U2.id, {"old_due_date": None, "new_due_date": "2026-11-15"}) | pass |
| U-15 | R8 | happy | CI with `allow_payments=False` | `UPD(allow_payments=True)` | returns the invoice; re-read `allow_payments is True`, `updated_by=U2.id`; Events: E("allow_payments_changed", "Payments enabled", U2.id, {"allow_payments": True}) | pass |
| U-16 | R9 | boundary | CI with `payment_locked_reason="Disputed"` | `UPD(payment_locked_reason=None)` | returns the invoice; re-read `payment_locked_reason is None`; Events: E("payment_lock_changed", "Payment lock updated", U2.id, {"payment_locked_reason": None}) | pass |
| U-17 | R4 [BUG-631]; Errors 5 | bug | CI | `UPD(notes="New notes", due_date=date(2026,11,15))` | raises `HTTPException` 400 and `"notes"` appears in the detail; re-read: `due_date=2026-10-01`, `notes="Old notes"`, `updated_by` None; 0 events | xfail BUG-631 — fails today on: no exception (due date applied) |
| U-18 | R4 [BUG-631]; Errors 5 | bug | CI on A1 | `UPD(account_id=A2.id)` | raises 400 and `"account_id"` appears in the detail; re-read `account_id=A1.id`; 0 events | xfail BUG-631 — fails today on: no exception (returns the invoice unchanged) |
| U-19 | R4a, R3, R7 | boundary | CI (`notes` "Old notes") | `UPD(notes="Old notes", due_date=date(2026,11,15))` | no exception; returns the invoice; re-read `due_date=2026-11-15`, `notes="Old notes"`; Events: E("due_date_changed", "Due date updated", U2.id, {"old_due_date": "2026-10-01", "new_due_date": "2026-11-15"}) | pass |
| U-20 | R5 | boundary | CI | `UPD()` (empty) | returns the invoice with `id == CI.id`; CI unchanged; `updated_by` None; 0 events | pass |
| U-21 | R5, R4a | boundary | CI | `UPD(description="Old desc")` (same value, non-editable) | returns the invoice; CI unchanged; `updated_by` None; 0 events | pass |
| U-22 | R6 [BUG-620] | bug | CI (`allow_payments` True) | `UPD(allow_payments=True)` | returns the invoice; re-read `updated_by is None` | xfail BUG-620 — fails today on: `updated_by == U2.id` |
| U-23 | R7 [BUG-632] | bug | CI (due 2026-10-01) | `UPD(due_date=date(2026,10,1))` | returns the invoice; 0 events | xfail BUG-632 — fails today on: 1 `due_date_changed` event |
| U-24 | R8 [BUG-632] | bug | CI (`allow_payments` True) | `UPD(allow_payments=True)` | returns the invoice; 0 events | xfail BUG-632 — fails today on: 1 `allow_payments_changed` event |
| U-25 | R9 [BUG-632] | bug | CI with `payment_locked_reason="Disputed"` | `UPD(payment_locked_reason="Disputed")` | returns the invoice; 0 events | xfail BUG-632 — fails today on: 1 `payment_lock_changed` event |
| U-26 | R11, R12, R13, R14, R15 | happy | DI (`updated_at` None) | `UPD(description="New desc", notes="N1", invoice_number=None, due_date=date(2026,12,1), invoice_date=date(2026,9,5), invoice_type="receivable")` | returns the invoice with `id == DI.id`; re-read: `description="New desc"`, `notes="N1"`, `invoice_number is None`, `due_date=2026-12-01`, `invoice_date=2026-09-05`, `invoice_type="receivable"`, `invoice_status="draft"`, `invoice_amount == 1000.00`, `updated_by=U2.id`, `updated_at` not None; Events: E("item_manually_updated", "Invoice details updated", U2.id, {"description": "New desc", "notes": "N1", "invoice_number": "None", "due_date": "2026-12-01", "invoice_date": "2026-09-05", "invoice_type": "receivable"}) | pass |
| U-27 | R10, R14 | happy | DI on A1 | `UPD(account_id=A2.id)` | returns the invoice; re-read `account_id=A2.id`, `updated_by=U2.id`; Events: E("item_manually_updated", "Invoice details updated", U2.id, {"account_id": str(A2.id)}) | pass |
| U-28 | R10; Errors 6 | isolation | DI on A1; AX in W2 | `UPD(account_id=AX.id)` | raises 404, detail `f"Account with ID {AX.id} not found"`; DI unchanged (`account_id=A1.id`, `updated_by` None); 0 events | pass |
| U-29 | R10; Errors 6 | error | DI | `UPD(account_id=NOID)` | raises 404, detail `"Account with ID 999999 not found"`; DI unchanged; 0 events | pass |
| U-30 | R10; Errors 7 | error | DI on A1; A2 with `is_deleted=True`, `is_active=False`, `allow_invoices=False` | `UPD(account_id=A2.id)` | raises 400, detail `"Cannot assign invoice to deleted account"`; DI unchanged; 0 events | pass |
| U-31 | R10 [BUG-629]; Errors 8 | bug | DI on A1; A2 with `is_active=False`, `allow_invoices=False` | `UPD(account_id=A2.id)` | raises 400, detail `"Cannot assign invoice to inactive account"`; re-read `account_id=A1.id`, `updated_by` None; 0 events | xfail BUG-629 — fails today on: no exception (account changed) |
| U-32 | R10 [BUG-629]; Errors 9 | bug | DI on A1; A2 with `allow_invoices=False` | `UPD(account_id=A2.id)` | raises `HTTPException` 403, detail `"Invoices are not allowed for this account"`; re-read `account_id=A1.id`; 0 events | xfail BUG-629 — fails today on: no exception |
| U-33 | R10 | boundary | DI on A1; A1 now `is_active=False`, `allow_invoices=False` | `UPD(account_id=A1.id, description="New desc")` | no exception; returns the invoice; re-read `account_id=A1.id`, `description="New desc"` | pass |
| U-34 | R12 | happy | P1 = PO(W1, "PO-1"), P2 = PO(W1, "PO-2"); DI with `order_type="purchase_order"`, `order_id=P1.id` | `UPD(order_id=P2.id)` | returns the invoice; re-read `order_id=P2.id`, `order_type="purchase_order"` | pass |
| U-35 | R12 [BUG-625]; Errors 12 | bug | P1 = PO(W1, "PO-1"); DI linked to P1 as in U-34 | `UPD(order_id=NOID)` | raises `HTTPException` 404, detail `"Order with ID 999999 not found"`; re-read `order_id=P1.id`, `updated_by` None; 0 events | xfail BUG-625 — fails today on: no exception (order_id stored) |
| U-36 | R12 [BUG-625]; Errors 12 | bug | as U-35, plus PW = PO(W2, "PO-9") | `UPD(order_id=PW.id)` | raises 404, detail `f"Order with ID {PW.id} not found"`; re-read `order_id=P1.id`; 0 events | xfail BUG-625 — fails today on: no exception |
| U-37 | R12, R9d [BUG-625]; Errors 12 | bug | as U-35, plus PD = PO(W1, "PO-D") with `voided=True` | `UPD(order_id=PD.id)` | raises 404, detail `f"Order with ID {PD.id} not found"`; re-read `order_id=P1.id`; 0 events | xfail BUG-625 — fails today on: no exception |
| U-38 | R2b, R12, R12a, R14 [BUG-625] | bug | DI linked to P1 as in U-34 | `UPD(order_type=None, order_id=None)` | returns the invoice; re-read `order_type is None`, `order_id is None`, `updated_by=U2.id`; Events: E("item_manually_updated", "Invoice details updated", U2.id, {"order_type": "None", "order_id": "None"}) (both null → no order check) | xfail BUG-625 (G15) — fails today on: re-read `order_type == "purchase_order"` (the schema has no `order_type` field and drops it) |
| U-39 | R13 [BUG-620] | bug | DI | `UPD()` | returns the invoice; re-read `updated_by is None` | xfail BUG-620 — fails today on: `updated_by == U2.id` |
| U-40 | R14 [BUG-632] | bug | DI | `UPD()` | returns the invoice; 0 events | xfail BUG-632 — fails today on: 1 `item_manually_updated` event with metadata `{}` |
| U-41 | R14 [BUG-632] | bug | DI | `UPD(description="Old desc", notes="New notes")` | returns the invoice; exactly 1 event, whose `metadata_json == {"notes": "New notes"}` | xfail BUG-632 — fails today on: metadata also contains `"description"` |
| U-42 | R12, R13, R14 | happy | DI | `UPD(description="Old desc", notes="New notes")` | returns the invoice; re-read `notes="New notes"`, `description="Old desc"`, `updated_by=U2.id`; exactly 1 event of type `item_manually_updated` with `metadata_json["notes"] == "New notes"` | pass |
| U-43 | R13 [BUG-620] | bug | DI | `UPD(description="Old desc")` | returns the invoice; re-read `updated_by is None` | xfail BUG-620 — fails today on: `updated_by == U2.id` |
| U-44 | R14 [BUG-632] | bug | DI | `UPD(description="Old desc")` | returns the invoice; 0 events | xfail BUG-632 — fails today on: 1 event |
| U-45 | R2b, R12, R12a, R14 [BUG-625] | bug | P1 = PO(W1, "PO-1"); E1 = EO(W1, "EXP-1"); DI linked to P1 as in U-34 | `UPD(order_type="expense_order", order_id=E1.id)` | returns the invoice; re-read `order_type="expense_order"`, `order_id=E1.id`, `updated_by=U2.id`; Events: E("item_manually_updated", "Invoice details updated", U2.id, {"order_type": "expense_order", "order_id": str(E1.id)}) | xfail BUG-625 (G15) — fails today on: re-read `order_type == "purchase_order"` (`order_type` dropped by the schema) |
| U-46 | R2b, R12a [BUG-625]; Errors 12 | bug | P1 = PO(W1, "PO-1"); DI linked to P1; no `expense_orders` row with `id == P1.id` in any workspace (precondition asserted) | `UPD(order_type="expense_order")` (only the type) | raises `HTTPException` 404, detail `f"Order with ID {P1.id} not found"` (the stored id is re-validated against the new type); re-read `order_type="purchase_order"`, `order_id=P1.id`, `updated_by` None; 0 events | xfail BUG-625 (G15) — fails today on: no exception (today the schema drops `order_type`, so nothing is checked) |
| U-47 | R12a [BUG-625]; Errors 13 | bug | P1 = PO(W1, "PO-1"); DI unlinked (`order_type`, `order_id` None) | `UPD(order_id=P1.id)` (only the id) | raises `HTTPException` 400, detail `"order_type and order_id must be set together"`; re-read `order_type is None`, `order_id is None`, `updated_by` None; 0 events | xfail BUG-625 — fails today on: no exception (`order_id` stored) |
| U-48 | R12a [BUG-625]; Errors 13 | bug | P1 = PO(W1, "PO-1"); DI linked to P1 | `UPD(order_id=None)` (only the id) | raises `HTTPException` 400, detail `"order_type and order_id must be set together"`; re-read `order_id=P1.id`, `order_type="purchase_order"`, `updated_by` None; 0 events | xfail BUG-625 — fails today on: no exception (`order_id` cleared) |
| U-49 | R12a | boundary | P1 = PO(W1, "PO-1"); DI linked to P1 | `UPD(order_type="purchase_order", order_id=P1.id, description="New desc")` (link resent unchanged) | no exception; returns the invoice; re-read `order_id=P1.id`, `order_type="purchase_order"`, `description="New desc"` | pass |
| U-50 | R12a | boundary | PD = PO(W1, "PO-D") with `voided=True`; DI with `order_type="purchase_order"`, `order_id=PD.id` (inserted directly) | `UPD(order_id=PD.id, notes="New notes")` (same id resent) | no exception (the effective pair equals the stored pair, so no order check runs); returns the invoice; re-read `order_id=PD.id`, `notes="New notes"` | pass |
| U-51 | R10a [BUG-629]; Errors 10 | bug | DI on A1 | inside a savepoint: `UPD(account_id=0)` | raises `HTTPException` 404, detail `"Account with ID 0 not found"`; after the savepoint rollback: `account_id=A1.id`, `updated_by` None; 0 events | xfail BUG-629 — fails today on: the exception is a DB integrity error (FK violation at flush), not an `HTTPException` 404 |
| U-52 | R10a | error | DI on A1 | inside a savepoint: `UPD(account_id=0)` | raises an exception (any `Exception` subclass); after the savepoint rollback: DI re-read has `account_id=A1.id`, `updated_by` None; 0 events | pass |
| U-53 | R2b [BUG-625] (G15) | bug | — | (target `schema`) build `AccountInvoiceUpdate(order_type=t)` for each t in `"purchase_order"`, `"expense_order"`, `"sales_order"`, `"work_order"`, and `AccountInvoiceUpdate(order_type=None)` | all five build without error; for each t: `"order_type" in model_fields_set` and `.order_type == t`; for `None`: `"order_type" in model_fields_set` and `.order_type is None` | xfail BUG-625 (G15) — fails today on: `"order_type" not in model_fields_set` (no such field; the kwarg is ignored) |
| U-54 | R12, R9d [BUG-625]; Errors 12 | bug | Wo1 = WO(W1, "WO-1") (live); WV = WO(W1, "WO-V") with `is_deleted=False`, `status="VOIDED"`; DI with `order_type="work_order"`, `order_id=Wo1.id` | `UPD(order_id=WV.id)` | raises `HTTPException` 404, detail `f"Order with ID {WV.id} not found"`; re-read `order_type="work_order"`, `order_id=Wo1.id`, `updated_by` None; 0 events | xfail BUG-625 — fails today on: no exception (`order_id` stored) |
| U-55 | R12, R9d | boundary | Wo1 = WO(W1, "WO-1"), Wo2 = WO(W1, "WO-2") (both live; the executor asserts neither has `status == "VOIDED"`); DI with `order_type="work_order"`, `order_id=Wo1.id` | `UPD(order_id=Wo2.id)` | no exception; returns the invoice; re-read `order_type="work_order"`, `order_id=Wo2.id`, `updated_by=U2.id` | pass |
| U-56 | R2b [BUG-625]; Errors 11 | bug | — | (target `schema`) build `AccountInvoiceUpdate(order_type="banana")` | raises `pydantic.ValidationError`, and one error's `loc == ("order_type",)` | xfail BUG-625 — fails today on: no error raised (no such field; the kwarg is ignored) |
| U-57 | R2b [BUG-625] | bug | — | (target `schema`) build `AccountInvoiceUpdate(order_type="  Purchase_Order ")` | no error; `.order_type == "purchase_order"` (trimmed and lower-cased); `"order_type" in model_fields_set` | xfail BUG-625 — fails today on: `.order_type == "purchase_order"` (no such field on the model: the attribute is missing, `AttributeError`) |
| U-58 | R2b, R4 [BUG-625, BUG-631]; Errors 5 | bug | CI (unlinked: `order_type` None, `order_id` None) | `UPD(order_type="purchase_order")` | raises `HTTPException` 400 and `"order_type"` appears in the detail; re-read: `order_type is None`, `order_id is None`, `due_date=2026-10-01`, `updated_by` None; 0 events | xfail BUG-625, BUG-631 — fails today on: no exception (the schema drops `order_type`, so the call returns the invoice unchanged). Needs both fixes: BUG-625 makes `order_type` a sent field, BUG-631 rejects a changed non-editable field |
| U-59 | R2b, R4a, R5 | boundary | P1 = PO(W1, "PO-1"); CI with `order_type="purchase_order"`, `order_id=P1.id` (inserted directly) | `UPD(order_type="purchase_order")` (same value as stored, non-editable on a confirmed invoice) | no exception; returns the invoice with `id == CI.id`; CI unchanged (`order_type="purchase_order"`, `order_id=P1.id`, `due_date=2026-10-01`, `updated_by` None); 0 events | pass |
| U-60 | R2b, R12a [BUG-625]; Errors 13 | bug | P1 = PO(W1, "PO-1"); DI linked to P1 as in U-34 | `UPD(order_type=None)` (only the type cleared) | raises `HTTPException` 400, detail `"order_type and order_id must be set together"`; re-read `order_type="purchase_order"`, `order_id=P1.id`, `updated_by` None; 0 events | xfail BUG-625 — fails today on: no exception (the schema drops `order_type`, so the call returns the invoice) |
| U-61 | R3b, R3, R7, R8, R9; F7 | happy | CI (id C; `due_date` 2026-10-01, `allow_payments` True, `payment_locked_reason` None); S1 = SO(W1, "SO-1") with `order_completed=True`, `invoice_id=C` | `UPD(due_date=date(2026,11,15), allow_payments=False, payment_locked_reason="Disputed")` | no exception (no freeze on update); returns the invoice with `id == C`; re-read: `due_date=2026-11-15`, `allow_payments is False`, `payment_locked_reason="Disputed"`, `invoice_status="confirmed"`; exactly 3 events: E("due_date_changed", "Due date updated", U2.id, {"old_due_date": "2026-10-01", "new_due_date": "2026-11-15"}), E("allow_payments_changed", "Payments disabled", U2.id, {"allow_payments": False}), E("payment_lock_changed", "Payment lock updated", U2.id, {"payment_locked_reason": "Disputed"}) (asserted as a set of (type, description, metadata)) | pass |
| U-62 | R3b, R3; F7 | happy | CI (id C; `due_date` 2026-10-01, `allow_payments` True); P1 = PO(W1, "PO-1") stage `Complete` with `invoice_id=C` | `UPD(due_date=date(2026,12,1), allow_payments=False, payment_locked_reason="On hold")` | no exception; returns the invoice with `id == C`; re-read: `due_date=2026-12-01`, `allow_payments is False`, `payment_locked_reason="On hold"`, `invoice_status="confirmed"`; exactly 3 events for C, with event types {"due_date_changed", "allow_payments_changed", "payment_lock_changed"} | pass |

## `AccountInvoiceManager.delete_invoice`

Call: `delete_invoice(session, inv.id, W1, U2.id)`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| DEL-01 | R3 | happy | DI (id D) with ITEM(DI, 100.00), ITEM(DI, 50.00), EVT(DI, V0); P1 = PO(W1, "PO-1") stage `Draft` (not completed) with `invoice_id=D` | call | returns an object whose `id == D`; re-read: no `account_invoices` row with id D; 0 `invoice_items` and 0 `invoice_events` with `invoice_id=D`; P1 re-read `invoice_id is None`; 0 `invoice_events` rows in W1 | pass |
| DEL-02 | R1; Errors 1 | error | none | `delete_invoice(session, NOID, W1, U2.id)` | raises 404, detail `"Invoice with ID 999999 not found"` | pass |
| DEL-03 | R1; Errors 1 | isolation | DI inserted in W2 (account AX), id X | `delete_invoice(session, X, W1, U2.id)` | raises 404, detail `f"Invoice with ID {X} not found"`; the W2 row still exists | pass |
| DEL-04 | R2; Errors 2 | error | CI with ITEM(CI, 100.00) | call | raises 400, detail `"Only draft invoices can be deleted. This invoice is 'confirmed'. Use void instead."`; CI and its item still exist; 0 events | pass |
| DEL-05 | R2; Errors 2 | error | VI | call | raises 400, detail `"Only draft invoices can be deleted. This invoice is 'voided'. Use void instead."`; VI still exists | pass |
| DEL-06 | R4 [BUG-639]; Errors 4 | bug | DI with PAY(DI, 100.00, voided=True) | call inside a savepoint | raises `HTTPException` 400, detail `"Invoice has payment history — confirm and void it instead"`; after the savepoint rollback, DI and the payment row still exist | xfail BUG-639 — fails today on: the exception is a DB integrity error, not an `HTTPException` 400 with that detail |
| DEL-07 | R4 | error | same as DEL-06 | call inside a savepoint | raises an exception (any `Exception`); after the savepoint rollback, DI and the payment row still exist | pass |
| DEL-08 | R1 [BUG-621] | bug | DI; SQL capture on | call | returns the deleted invoice object; captured SQL locks the invoice; DI deleted (no row with its id) | xfail BUG-621 — fails today on: no `FOR UPDATE` captured |
| DEL-09 | R4 [BUG-639]; Errors 4 | bug | DI with HIST(DI); no payments | call inside a savepoint | raises `HTTPException` 400, detail `"Invoice has payment history — confirm and void it instead"`; after the savepoint rollback, DI and the HIST row still exist | xfail BUG-639 — fails today on: the exception is a DB integrity error, not an `HTTPException` 400 with that detail |
| DEL-10 | R4 | error | same as DEL-09 | call inside a savepoint | raises an exception (any `Exception`); after the savepoint rollback, DI and the HIST row still exist | pass |
| DEL-11 | R3 | side-effect | DI (id D); E1 = EO(W1, "EXP-1") with `completed_at=None`, S1 = SO(W1, "SO-1") with `order_completed=False`, Wo1 = WO(W1, "WO-1") with `status="DRAFT"` (none completed), each with `invoice_id=D` | call | returns an object whose `id == D`; re-read: no `account_invoices` row with id D; E1, S1 and Wo1 still exist, each with `invoice_id is None` | pass |
| DEL-12 | R3 | side-effect | DI (id D); POR(W1) and SOR(W1), each with `invoice_id=D` | call | returns an object whose `id == D`; re-read: no invoice D; both return rows still exist with `invoice_id is None` | pass |
| DEL-13 | R3 | side-effect | DI (id D); MLED(W1) with `invoice_id=D` | call | returns an object whose `id == D`; re-read: no invoice D; the ledger row still exists with `invoice_id is None` | pass |
| DEL-14 | R2a [BUG-2730]; Errors 3; F1, F2, F4, F5 | bug | DI (id D) with ITEM(DI, 100.00); P1 = PO(W1, "PO-1") stage `Complete` with `invoice_id=D` | call | raises `HTTPException` 400, `detail == LOCK("purchase order")`; session clean; re-read: DI still exists and is unchanged; its item still exists; P1 `invoice_id == D`; 0 events for D | xfail BUG-2730 — fails today on: raises (no exception — the draft is deleted) |
| DEL-15 | R2a [BUG-2730]; Errors 3; F2, F5 | bug | DI (id D) with ITEM(DI, 100.00); S1 = SO(W1, "SO-1") with `order_completed=True`, `invoice_id=D` | call | raises `HTTPException` 400, `detail == LOCK("sales order")`; session clean; re-read: DI still exists and is unchanged; its item still exists; S1 `invoice_id == D`; 0 events for D | xfail BUG-2730 — fails today on: raises (no exception) |
| DEL-16 | R2a [BUG-2730]; Errors 3; F2, F5 | bug | DI (id D) with ITEM(DI, 100.00); E1 = EO(W1, "EXP-1") with `completed_at=V0`, `invoice_id=D` | call | raises `HTTPException` 400, `detail == LOCK("expense order")`; session clean; re-read: DI still exists and is unchanged; its item still exists; E1 `invoice_id == D`; 0 events for D | xfail BUG-2730 — fails today on: raises (no exception) |
| DEL-17 | R2a [BUG-2730]; Errors 3; F2, F5 | bug | DI (id D) with ITEM(DI, 100.00); Wo1 = WO(W1, "WO-1") with `status="COMPLETED"`, `invoice_id=D` | call | raises `HTTPException` 400, `detail == LOCK("work order")`; session clean; re-read: DI still exists and is unchanged; its item still exists; Wo1 `invoice_id == D`; 0 events for D | xfail BUG-2730 — fails today on: raises (no exception) |
| DEL-18 | R2a, R3; F2 | boundary | DI (id D); P1 = PO(W1, "PO-1") stage `Receiving` with `invoice_id=D` (`Receiving` is not completed) | call | no exception; returns an object whose `id == D`; re-read: no `account_invoices` row with id D; P1 `invoice_id is None` | pass |
| DEL-19 | R2a, R3; F1 | isolation | DI (id D); S0 = SO(W0, "SO-0") completed with `invoice_id=D`; Wo2 = WO(W2, "WO-2") completed with `invoice_id=D` (orders of other workspaces, one lower and one higher workspace id); no W1 order points at D | call | no exception; returns an object whose `id == D`; re-read: no `account_invoices` row with id D; S0 and Wo2 still exist, each with `invoice_id is None` | pass |
| DEL-20 | R2a, R3; F1 | isolation | DI (id D); P2 = PO(W2, "PO-2") stage `Complete` (ST in W2) with `invoice_id=D`; E0 = EO(W0, "EXP-0") completed with `invoice_id=D`; no W1 order points at D | call | no exception; returns an object whose `id == D`; re-read: no `account_invoices` row with id D; P2 and E0 still exist, each with `invoice_id is None` | pass |
| DEL-21 | R2a, R3; F1 | boundary | S1 = SO(W1, "SO-1") completed, `invoice_id` None; DI (id D) with `order_type="sales_order"`, `order_id=S1.id` (linked only by type/id) | call | no exception; returns an object whose `id == D`; re-read: no `account_invoices` row with id D; S1 still exists with `invoice_id is None`, `order_completed is True` | pass |
| DEL-22 | R2, R2a (check order); Errors 2 | error | CI (id C) with ITEM(CI, 100.00); S1 = SO(W1, "SO-1") completed with `invoice_id=C` | call | raises `HTTPException` 400, `detail == "Only draft invoices can be deleted. This invoice is 'confirmed'. Use void instead."` (R2 comes before the freeze); session clean; re-read: CI unchanged; its item still exists; S1 `invoice_id == C`; 0 events | pass |
| DEL-23 | R2a, R4 (check order) [BUG-2730]; Errors 3 | bug | DI (id D) with PAY(DI, 100.00, voided=True); S1 = SO(W1, "SO-1") completed with `invoice_id=D` | call inside a savepoint | raises `HTTPException` 400, `detail == LOCK("sales order")` (the freeze comes before the payment-history check); session clean (before the savepoint rollback); after the rollback, re-read: DI and the payment row still exist; S1 `invoice_id == D` | xfail BUG-2730 — fails today on: raises (no `HTTPException` — a DB integrity error at flush) |
| DEL-24 | R2a, R4 | error | same rows as DEL-23: DI (id D) with PAY(DI, 100.00, voided=True); S1 = SO(W1, "SO-1") completed with `invoice_id=D` | call inside a savepoint | raises an exception (any `Exception`); after the savepoint rollback, re-read: DI and the payment row still exist; S1 `invoice_id == D` | pass |
| DEL-25 | R2a, R3; F2 (exact name) | boundary | DI (id D); P1 = PO(W1, "PO-1") stage `complete` (lower-case c) with `invoice_id=D` | call | no exception; returns an object whose `id == D`; re-read: no `account_invoices` row with id D; P1 `invoice_id is None` | pass |
| DEL-26 | R2a, R3; F2 (exact name) | boundary | DI (id D); P1 = PO(W1, "PO-1") stage `" Complete"` (leading space) with `invoice_id=D` | call | no exception; returns an object whose `id == D`; re-read: no `account_invoices` row with id D; P1 `invoice_id is None` | pass |
| DEL-27 | R2a, R3; F2 (exact name) | boundary | DI (id D); P1 = PO(W1, "PO-1") stage `Completed` with `invoice_id=D` | call | no exception; returns an object whose `id == D`; re-read: no `account_invoices` row with id D; P1 `invoice_id is None` | pass |
| DEL-28 | R2a [BUG-2730]; Errors 3; F3 | bug | DI (id D) with ITEM(DI, 100.00); P1 = PO(W1, "PO-1") stage `Complete` with `voided=True`, `invoice_id=D` (the order's void flag does not lift the freeze) | call | raises `HTTPException` 400, `detail == LOCK("purchase order")`; session clean; re-read: DI still exists and is unchanged; its item still exists; P1 `invoice_id == D`; 0 events for D | xfail BUG-2730 — fails today on: raises (no exception — the draft is deleted) |

## `AccountInvoiceManager.confirm_invoice`

Call: `confirm_invoice(session, inv.id, W1, U2.id)`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| CF-01 | R4, R5, R6 | happy | DI (amount 1000.00, paid 0.00, `last_synced_at` None); ITEM(DI, 150.00), ITEM(DI, 250.00) | call | returns the invoice with `id == DI.id`; re-read: `invoice_status="confirmed"`, `invoice_amount == Decimal("400.00")`, `payment_status="unpaid"`, `last_synced_at == NOW`; Events: E("confirmed", "Invoice finalized", U2.id, {"invoice_amount": "400.00"}) | pass |
| CF-02 | R4 | side-effect | DI with `paid_amount=100.00`; ITEM(DI, 400.00) | call | returns the invoice; re-read `invoice_amount == 400.00`, `payment_status="partial"` | pass |
| CF-03 | R4 | isolation | DI; ITEM(DI, 0.10), ITEM(DI, 0.20); one `invoice_items` row with `invoice_id=DI.id`, workspace W2, subtotal 999.00 | call | returns the invoice; re-read `invoice_amount == Decimal("0.30")`; event metadata `{"invoice_amount": "0.30"}` | pass |
| CF-04 | R1; Errors 1 | error | none | `confirm_invoice(session, NOID, W1, U2.id)` | raises 404, detail `"Invoice with ID 999999 not found"` | pass |
| CF-05 | R1; Errors 1 | isolation | DI inserted in W2 with an item, id X | `confirm_invoice(session, X, W1, U2.id)` | raises 404; the W2 row is still `"draft"`; 0 events | pass |
| CF-06 | R2; Errors 2 | error | VI with ITEM(VI, 100.00) | call | raises 400, detail `"Voided invoices cannot be confirmed"`; VI unchanged (`invoice_amount` 1000.00, status voided); 0 events | pass |
| CF-07 | R3; Errors 3 | error | CI (amount 1000.00, `last_synced_at` L0) with ITEM(CI, 100.00) | call | raises 400, detail `"Invoice is already confirmed"`; re-read `invoice_amount == 1000.00`, `last_synced_at == L0`; 0 events | pass |
| CF-08 | R4 [BUG-628]; Errors 4 | bug | DI (amount 1000.00), no items | call | raises 400, detail `"Add at least one line item before confirming"`; re-read `invoice_status="draft"`, `invoice_amount == 1000.00`, `payment_status="unpaid"`, `last_synced_at is None`; 0 events | xfail BUG-628 — fails today on: no exception (confirmed at 0.00, `paid`) |
| CF-09 | R5 [BUG-633] | bug | DI with ITEM(DI, 100.00) | call | returns the invoice; re-read `updated_by == U2.id` | xfail BUG-633 — fails today on: `updated_by is None` |
| CF-10 | R1 [BUG-621] | bug | DI with ITEM(DI, 100.00); SQL capture on | call | returns the invoice; captured SQL locks the invoice; re-read `invoice_status="confirmed"` | xfail BUG-621 — fails today on: no `FOR UPDATE` captured |

## `AccountInvoiceManager.revert_to_draft`

Call: `revert_to_draft(session, inv.id, W1, U2.id)`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| RV-01 | R5, R6 | happy | CI with `invoice_amount=400.00`, `paid_amount=0.00`, `payment_status="unpaid"`, `last_synced_at=L0` | call | returns the invoice with `id == CI.id`; re-read: `invoice_status="draft"`, `invoice_amount == 400.00`, `payment_status="unpaid"`, `last_synced_at == L0`; Events: E("reverted_to_draft", "Reverted to draft", U2.id, None) | pass |
| RV-02 | R4 | boundary | CI with `paid_amount=None` | call | returns the invoice; re-read `invoice_status="draft"` | pass |
| RV-03 | R4 | boundary | CI with `paid_amount=0.00` and PAY(CI, 100.00, voided=True) | call | returns the invoice; re-read `invoice_status="draft"` | pass |
| RV-04 | R4; Errors 6 | boundary | CI with `paid_amount=0.01`, `payment_status="partial"` | call | raises 400, detail `"Cannot revert to draft — invoice has active payments. Void all payments first."`; re-read status confirmed; 0 events | pass |
| RV-05 | R3; Errors 5 | error | CI with `receiving_started=True`, `paid_amount=0.00` | call | raises `HTTPException` 400; the detail starts with `"Cannot revert to draft — "` and contains `"receiv"` (holds for today's text and for RCVTXT; the exact text is RV-13); session clean; re-read: CI unchanged (status confirmed, `updated_by` None); 0 events | pass |
| RV-06 | R3, R4 (check order); Errors 5 | boundary | CI with `receiving_started=True`, `paid_amount=100.00`, `payment_status="partial"` | call | raises `HTTPException` 400; the detail contains `"receiv"` and does not contain `"active payments"` (receiving is checked before payments; the exact text is RV-14); session clean; re-read: status confirmed, `paid_amount == 100.00`, `updated_by` None; 0 events | pass |
| RV-07 | R2; Errors 2 | error | DI | call | raises 400, detail `"Only confirmed invoices can be reverted to draft. Current status: 'draft'."`; DI unchanged (status draft, `updated_by` None); 0 events | pass |
| RV-08 | R2; Errors 2 | error | VI | call | raises 400, detail `"Only confirmed invoices can be reverted to draft. Current status: 'voided'."`; VI unchanged; 0 events | pass |
| RV-09 | R1; Errors 1 | error | none | `revert_to_draft(session, NOID, W1, U2.id)` | raises 404, detail `"Invoice with ID 999999 not found"` | pass |
| RV-10 | R1; Errors 1 | isolation | CI inserted in W2, id X | `revert_to_draft(session, X, W1, U2.id)` | raises 404; the W2 row is still confirmed; 0 events | pass |
| RV-11 | R5 [BUG-633] | bug | CI | call | returns the invoice; re-read `updated_by == U2.id` | xfail BUG-633 — fails today on: `updated_by is None` |
| RV-12 | R1 [BUG-621] | bug | CI; SQL capture on | call | returns the invoice; captured SQL locks the invoice; re-read status draft | xfail BUG-621 — fails today on: no `FOR UPDATE` captured |
| RV-13 | R3a [BUG-2736]; Errors 5 | bug | CI with `receiving_started=True`, `paid_amount=0.00` | call | raises `HTTPException` 400; `detail == RCVTXT`; session clean; re-read: CI unchanged; 0 events | xfail BUG-2736 — fails today on: `detail == RCVTXT` (today: "… receiving has been recorded on the linked order. Zero out received quantities first.") |
| RV-14 | R3, R3a, R4 [BUG-2736]; Errors 5 | bug | CI with `receiving_started=True`, `paid_amount=100.00`, `payment_status="partial"` | call | raises `HTTPException` 400; `detail == RCVTXT`; session clean; re-read: status confirmed, `paid_amount == 100.00`; 0 events | xfail BUG-2736 — fails today on: `detail == RCVTXT` (old receiving text) |
| RV-15 | R2b [BUG-2730]; Errors 4; F1, F2, F5 | bug | CI (id C) with `receiving_started=False`, `paid_amount=0.00`; P1 = PO(W1, "PO-1") stage `Complete` with `invoice_id=C` | call | raises `HTTPException` 400, `detail == LOCK("purchase order")`; session clean; re-read: CI unchanged (status confirmed, `updated_by` None); 0 events | xfail BUG-2730 — fails today on: raises (no exception — reverted to draft) |
| RV-16 | R2b [BUG-2730]; Errors 4; F2, F5 | bug | CI (id C); S1 = SO(W1, "SO-1") with `order_completed=True`, `invoice_id=C` | call | raises `HTTPException` 400, `detail == LOCK("sales order")`; session clean; re-read: CI unchanged; 0 events | xfail BUG-2730 — fails today on: raises (no exception) |
| RV-17 | R2b [BUG-2730]; Errors 4; F2, F5 | bug | CI (id C); E1 = EO(W1, "EXP-1") with `completed_at=V0`, `invoice_id=C` | call | raises `HTTPException` 400, `detail == LOCK("expense order")`; session clean; re-read: CI unchanged; 0 events | xfail BUG-2730 — fails today on: raises (no exception) |
| RV-18 | R2b [BUG-2730]; Errors 4; F2, F5 | bug | CI (id C); Wo1 = WO(W1, "WO-1") with `status="COMPLETED"`, `invoice_id=C` | call | raises `HTTPException` 400, `detail == LOCK("work order")`; session clean; re-read: CI unchanged; 0 events | xfail BUG-2730 — fails today on: raises (no exception) |
| RV-19 | R2b, R5; F2 | boundary | CI (id C); P1 = PO(W1, "PO-1") stage `Receiving` with `invoice_id=C` | call | no exception; returns the invoice with `id == C`; re-read `invoice_status == "draft"`; Events: E("reverted_to_draft", "Reverted to draft", U2.id, None) | pass |
| RV-20 | R2b, R5; F1 | isolation | CI (id C); S0 = SO(W0, "SO-0") completed with `invoice_id=C`; Wo2 = WO(W2, "WO-2") completed with `invoice_id=C`; no W1 order points at C | call | no exception; returns the invoice with `id == C`; re-read `invoice_status == "draft"` | pass |
| RV-21 | R2b, R5; F1 | isolation | CI (id C); P2 = PO(W2, "PO-2") stage `Complete` (ST in W2) with `invoice_id=C`; E0 = EO(W0, "EXP-0") completed with `invoice_id=C`; no W1 order points at C | call | no exception; returns the invoice with `id == C`; re-read `invoice_status == "draft"` | pass |
| RV-22 | R2b, R5; F1 | boundary | Wo1 = WO(W1, "WO-1") completed, `invoice_id` None; CI (id C) with `order_type="work_order"`, `order_id=Wo1.id` (linked only by type/id) | call | no exception; returns the invoice with `id == C`; re-read `invoice_status == "draft"` | pass |
| RV-23 | R2b, R5; F2 | boundary | CI (id C); Wo1 = WO(W1, "WO-1") with `status="IN_PROGRESS"`, `invoice_id=C` | call | no exception; returns the invoice with `id == C`; re-read `invoice_status == "draft"` | pass |
| RV-24 | R2b, R5; F2, F3 | boundary | CI (id C); Wo1 = WO(W1, "WO-1") with `status="VOIDED"`, `invoice_id=C` | call | no exception; returns the invoice with `id == C`; re-read `invoice_status == "draft"` | pass |
| RV-25 | R2b, R5; F2 (exact name) | boundary | CI (id C); P1 = PO(W1, "PO-1") stage `complete` (lower-case c) with `invoice_id=C` | call | no exception; returns the invoice with `id == C`; re-read `invoice_status == "draft"` | pass |
| RV-26 | R2b, R5; F2 (exact name) | boundary | CI (id C); P1 = PO(W1, "PO-1") stage `" Complete"` (leading space) with `invoice_id=C` | call | no exception; returns the invoice with `id == C`; re-read `invoice_status == "draft"` | pass |
| RV-27 | R2b, R5; F2 (exact name) | boundary | CI (id C); P1 = PO(W1, "PO-1") stage `Completed` with `invoice_id=C` | call | no exception; returns the invoice with `id == C`; re-read `invoice_status == "draft"` | pass |
| RV-28 | R2b [BUG-2730]; F5 (kind) | bug | CI (id C); P1 = PO(W1, "PO-1") stage `Draft` with `invoice_id=C`; Wo1 = WO(W1, "WO-1") completed with `invoice_id=C` | call | raises `HTTPException` 400, `detail == LOCK("work order")` (the kind of the completed order, not of the first linked one); session clean; re-read: CI unchanged; 0 events | xfail BUG-2730 — fails today on: raises (no exception) |
| RV-29 | R2b [BUG-2730]; F5 (kind) | bug | CI (id C); Wo1 = WO(W1, "WO-1") completed with `invoice_id=C`; S1 = SO(W1, "SO-1") completed with `invoice_id=C` | call | raises `HTTPException` 400, `detail == LOCK("sales order")`; session clean; re-read: CI unchanged; 0 events | xfail BUG-2730 — fails today on: raises (no exception) |
| RV-30 | R2b [BUG-2730]; F5 (kind) | bug | CI (id C); Wo1 = WO(W1, "WO-1") completed with `invoice_id=C`; E1 = EO(W1, "EXP-1") completed with `invoice_id=C` | call | raises `HTTPException` 400, `detail == LOCK("expense order")`; session clean; re-read: CI unchanged; 0 events | xfail BUG-2730 — fails today on: raises (no exception) |
| RV-31 | R2b [BUG-2730]; F5 (kind) | bug | CI (id C); S1 = SO(W1, "SO-1") completed with `invoice_id=C`; P1 = PO(W1, "PO-1") stage `Complete` with `invoice_id=C` | call | raises `HTTPException` 400, `detail == LOCK("purchase order")`; session clean; re-read: CI unchanged; 0 events | xfail BUG-2730 — fails today on: raises (no exception) |
| RV-32 | R2, R2b (check order); Errors 2 | error | DI (id D); S1 = SO(W1, "SO-1") completed with `invoice_id=D` | call | raises `HTTPException` 400, `detail == "Only confirmed invoices can be reverted to draft. Current status: 'draft'."`; session clean; re-read: DI unchanged; 0 events | pass |
| RV-33 | R2b, R3 (check order) [BUG-2730]; Errors 4 | bug | CI (id C) with `receiving_started=True`, `paid_amount=0.00`; P1 = PO(W1, "PO-1") stage `Complete` with `invoice_id=C` | call | raises `HTTPException` 400; `detail == LOCK("purchase order")` (the freeze comes before the receiving check); session clean; re-read: CI unchanged; 0 events | xfail BUG-2730 — fails today on: `detail == LOCK("purchase order")` (today: the receiving text) |
| RV-34 | R2b, R3 | error | CI (id C) with `receiving_started=True`, `paid_amount=0.00`; P1 = PO(W1, "PO-1") stage `Complete` with `invoice_id=C` | call | raises `HTTPException` 400; session clean; re-read: CI unchanged (status confirmed, `receiving_started is True`); 0 events | pass |
| RV-35 | R2b, R4 (check order) [BUG-2730]; Errors 4 | bug | CI (id C) with `paid_amount=100.00`, `payment_status="partial"`; PA = PAY(CI, 100.00); S1 = SO(W1, "SO-1") completed with `invoice_id=C` | call | raises `HTTPException` 400; `detail == LOCK("sales order")` (the freeze comes before the payments check); session clean; re-read: CI unchanged; PA `is_voided is False`; 0 events | xfail BUG-2730 — fails today on: `detail == LOCK("sales order")` (today: the active-payments text) |
| RV-36 | R2b, R4 | error | CI (id C) with `paid_amount=100.00`, `payment_status="partial"`; PA = PAY(CI, 100.00); S1 = SO(W1, "SO-1") completed with `invoice_id=C` | call | raises `HTTPException` 400; session clean; re-read: CI unchanged; PA `is_voided is False`; 0 events | pass |
| RV-37 | R2a [BUG-2733]; Errors 3; F6 | bug | P1 = PO(W1, "PO-1") stage `Draft` with `invoice_id=OI.id`; CN for P1 with POR(W1) `invoice_id=CN.id`; CN `receiving_started=False`, `paid_amount=0.00` | `revert_to_draft(session, CN.id, W1, U2.id)` | raises `HTTPException` 400, `detail == CNTXT`; session clean; re-read: CN unchanged (status confirmed, `updated_by` None); 0 events for CN | xfail BUG-2733 — fails today on: raises (no exception — the credit note reverts) |
| RV-38 | R2a [BUG-2733]; Errors 3; F1, F6 | bug | S1 = SO(W1, "SO-1") completed with `invoice_id=OI.id`; CN for S1 with SOR(W1) `invoice_id=CN.id` | `revert_to_draft(session, CN.id, W1, U2.id)` | raises `HTTPException` 400, `detail == CNTXT` (not LOCK: the credit note is not the order's invoice); session clean; re-read: CN unchanged; 0 events for CN | xfail BUG-2733 — fails today on: raises (no exception) |
| RV-39 | R2a, R2b (check order) [BUG-2733]; Errors 3 | bug | S1 = SO(W1, "SO-1") completed; CN for S1 with SOR(W1) `invoice_id=CN.id`; S1 `invoice_id=CN.id` (CN is both the return's and the order's invoice; no OI) | `revert_to_draft(session, CN.id, W1, U2.id)` | raises `HTTPException` 400, `detail == CNTXT` (credit note before freeze); session clean; re-read: CN unchanged; 0 events for CN | xfail BUG-2733 — fails today on: raises (no exception) |
| RV-40 | R2a, R3 (check order) [BUG-2733]; Errors 3 | bug | P1 = PO(W1, "PO-1") stage `Draft` with `invoice_id=OI.id`; CN for P1 with POR(W1) `invoice_id=CN.id`; CN `receiving_started=True` | `revert_to_draft(session, CN.id, W1, U2.id)` | raises `HTTPException` 400; `detail == CNTXT`; session clean; re-read: CN unchanged; 0 events for CN | xfail BUG-2733 — fails today on: `detail == CNTXT` (today: the receiving text) |
| RV-41 | R2a, R3 | error | P1 = PO(W1, "PO-1") stage `Draft` with `invoice_id=OI.id`; CN for P1 with POR(W1) `invoice_id=CN.id`; CN `receiving_started=True` | `revert_to_draft(session, CN.id, W1, U2.id)` | raises `HTTPException` 400; session clean; re-read: CN unchanged (status confirmed); 0 events for CN | pass |
| RV-42 | R2a, R4 (check order) [BUG-2733]; Errors 3 | bug | S1 = SO(W1, "SO-1") with `invoice_id=OI.id`; CN for S1 with SOR(W1) `invoice_id=CN.id`; CN `paid_amount=100.00`, `payment_status="partial"`; PA = PAY(CN, 100.00) | `revert_to_draft(session, CN.id, W1, U2.id)` | raises `HTTPException` 400; `detail == CNTXT`; session clean; re-read: CN unchanged; PA `is_voided is False`; 0 events for CN | xfail BUG-2733 — fails today on: `detail == CNTXT` (today: the active-payments text) |
| RV-43 | R2a, R4 | error | S1 = SO(W1, "SO-1") with `invoice_id=OI.id`; CN for S1 with SOR(W1) `invoice_id=CN.id`; CN `paid_amount=100.00`, `payment_status="partial"`; PA = PAY(CN, 100.00) | `revert_to_draft(session, CN.id, W1, U2.id)` | raises `HTTPException` 400; session clean; re-read: CN unchanged; PA `is_voided is False`; 0 events for CN | pass |
| RV-44 | R2, R2a (check order); Errors 2 | error | S1 = SO(W1, "SO-1") with `invoice_id=OI.id`; CN for S1 with SOR(W1) `invoice_id=CN.id`, but CN `invoice_status="draft"` | `revert_to_draft(session, CN.id, W1, U2.id)` | raises `HTTPException` 400, `detail == "Only confirmed invoices can be reverted to draft. Current status: 'draft'."`; session clean; re-read: CN unchanged; 0 events for CN | pass |
| RV-45 | R2a, R5; F6 | isolation | CI (id C), no W1 return row points at it; POR(W0) with `invoice_id=C`; SOR(W2) with `invoice_id=C` (return rows of other workspaces, lower and higher workspace id) | call | no exception; returns the invoice with `id == C`; re-read `invoice_status == "draft"` | pass |
| RV-46 | R2a, R5; F6 | isolation | CI (id C), no W1 return row points at it; POR(W2) with `invoice_id=C`; SOR(W0) with `invoice_id=C` | call | no exception; returns the invoice with `id == C`; re-read `invoice_status == "draft"` | pass |
| RV-47 | R2b [BUG-2730]; F5 (kind) | bug | CI (id C); S1 = SO(W1, "SO-1") completed with `invoice_id=C`; E1 = EO(W1, "EXP-1") completed with `invoice_id=C` | call | raises `HTTPException` 400, `detail == LOCK("sales order")` (sales before expense); session clean; re-read: CI unchanged; 0 events | xfail BUG-2730 — fails today on: raises (no exception) |
| RV-48 | R2b [BUG-2730]; F5 (kind) | bug | CI (id C); P1 = PO(W1, "PO-1") stage `Complete` with `invoice_id=C`; E1 = EO(W1, "EXP-1") completed with `invoice_id=C` | call | raises `HTTPException` 400, `detail == LOCK("purchase order")` (purchase before expense); session clean; re-read: CI unchanged; 0 events | xfail BUG-2730 — fails today on: raises (no exception) |

## `AccountInvoiceManager.void_invoice`

Call: `void_invoice(session, inv.id, W1, U2.id, note)`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| VD-01 | R4, R5, R7 | happy | CI (amount 1000.00, paid 600.00, "partial"); PA = PAY(CI, 400.00), PB = PAY(CI, 200.00), PC = PAY(CI, 150.00, voided=True); J = another CI-like confirmed invoice with PJ = PAY(J, 50.00) | note `"Damaged goods"` | returns the invoice with `id == CI.id`; re-read CI: `invoice_status="voided"`, `void_note="Damaged goods"`, `paid_amount == 0.00`, `payment_status="unpaid"`, `invoice_amount == 1000.00`; PA and PB each: `is_voided is True`, `voided_at == NOW`, `voided_by=U2.id`, `void_note == f"Automatically voided — invoice #{CI.id} was voided. Reason: Damaged goods"`; PC unchanged (`voided_at == V0`, `voided_by=U1.id`, `void_note="manual void"`); PJ `is_voided is False`; Events for CI: E("voided", "Invoice voided", U2.id, {"prior_status": "confirmed", "payments_voided": 2, "void_note": "Damaged goods"}); 0 events for J | pass |
| VD-02 | R4, R7 | boundary | CI with no payments | note `"Wrong vendor"` | returns the invoice; re-read status voided; event metadata `{"prior_status": "confirmed", "payments_voided": 0, "void_note": "Wrong vendor"}` | pass |
| VD-03 | R2; Errors 2 | error | VI (`void_note` "Old reason") | note `"Again"` | raises 400, detail `"Invoice is already voided"`; re-read `void_note="Old reason"`; 0 events | pass |
| VD-04 | R3; Errors 3 | error | DI with PAY(DI, 100.00) | note `"x"` | raises 400, detail `"Draft invoices cannot be voided — delete them instead"`; DI still draft; payment `is_voided is False`; 0 events | pass |
| VD-05 | R1; Errors 1 | error | none | `void_invoice(session, NOID, W1, U2.id, "x")` | raises 404, detail `"Invoice with ID 999999 not found"` | pass |
| VD-06 | R1; Errors 1 | isolation | CI inserted in W2 with an active payment, id X | `void_invoice(session, X, W1, U2.id, "x")` | raises 404; the W2 row is still confirmed; its payment `is_voided is False`; 0 events | pass |
| VD-07 | R6 [BUG-633] | bug | CI | note `"x"` | returns the invoice; re-read `updated_by == U2.id` | xfail BUG-633 — fails today on: `updated_by is None` |
| VD-08 | R1 [BUG-621] | bug | CI; SQL capture on | note `"x"` | returns the invoice; captured SQL locks the invoice; re-read status voided | xfail BUG-621 — fails today on: no `FOR UPDATE` captured |
| VD-09 | R8 | side-effect | CI | note `"  spaced note  "` | returns the invoice; re-read `void_note == "  spaced note  "` (the manager stores what it gets; trimming is the schema's job) | pass |
| VD-10 | R8 | error | — | (target `schema`) build `VoidInvoiceRequest(void_note="")` | raises `ValidationError` | pass |
| VD-11 | R8 | happy | — | (target `schema`) build `VoidInvoiceRequest(void_note="Damaged")` | no error; `.void_note == "Damaged"` | pass |
| VD-12 | R8 [BUG-626]; Errors 6 | bug | — | build `VoidInvoiceRequest(void_note="   ")` | raises `ValidationError` | xfail BUG-626 — fails today on: no error raised |
| VD-13 | R8 [BUG-626] | bug | — | build `VoidInvoiceRequest(void_note="  Damaged  ")` | `.void_note == "Damaged"` | xfail BUG-626 — fails today on: `.void_note == "  Damaged  "` |
| VD-14 | R3a [BUG-2731]; Errors 4; F1, F2, F5 | bug | CI (id C) with `paid_amount=200.00`, `payment_status="partial"`; PA = PAY(CI, 200.00); P1 = PO(W1, "PO-1") stage `Complete` with `invoice_id=C` | note `"Damaged"` | raises `HTTPException` 400, `detail == LOCK("purchase order")`; session clean; re-read: CI unchanged (status confirmed, `paid_amount == 200.00`, `payment_status == "partial"`, `void_note` None, `updated_by` None); PA `is_voided is False`, `voided_at is None`, `voided_by is None`, `void_note is None`; 0 events | xfail BUG-2731 — fails today on: raises (no exception — invoice and payment voided) |
| VD-15 | R3a [BUG-2731]; Errors 4; F2, F5 | bug | CI (id C) with `paid_amount=200.00`, `payment_status="partial"`; PA = PAY(CI, 200.00); S1 = SO(W1, "SO-1") with `order_completed=True`, `invoice_id=C` | note `"Damaged"` | raises `HTTPException` 400, `detail == LOCK("sales order")`; session clean; re-read: CI unchanged; PA `is_voided is False`, `voided_at is None`; 0 events | xfail BUG-2731 — fails today on: raises (no exception) |
| VD-16 | R3a [BUG-2731]; Errors 4; F2, F5 | bug | CI (id C) with `paid_amount=200.00`, `payment_status="partial"`; PA = PAY(CI, 200.00); E1 = EO(W1, "EXP-1") with `completed_at=V0`, `invoice_id=C` | note `"Damaged"` | raises `HTTPException` 400, `detail == LOCK("expense order")`; session clean; re-read: CI unchanged; PA `is_voided is False`, `voided_at is None`; 0 events | xfail BUG-2731 — fails today on: raises (no exception) |
| VD-17 | R3a [BUG-2731]; Errors 4; F2, F5 | bug | CI (id C) with `paid_amount=200.00`, `payment_status="partial"`; PA = PAY(CI, 200.00); Wo1 = WO(W1, "WO-1") with `status="COMPLETED"`, `invoice_id=C` | note `"Damaged"` | raises `HTTPException` 400, `detail == LOCK("work order")`; session clean; re-read: CI unchanged; PA `is_voided is False`, `voided_at is None`; 0 events | xfail BUG-2731 — fails today on: raises (no exception) |
| VD-18 | R3a, R4, R5; F2 | boundary | CI (id C); P1 = PO(W1, "PO-1") stage `Receiving` with `invoice_id=C` | note `"Damaged"` | no exception; returns the invoice with `id == C`; re-read `invoice_status == "voided"`, `void_note == "Damaged"`; Events: E("voided", "Invoice voided", U2.id, {"prior_status": "confirmed", "payments_voided": 0, "void_note": "Damaged"}) | pass |
| VD-19 | R3a, R5; F1 | isolation | CI (id C); S0 = SO(W0, "SO-0") completed with `invoice_id=C`; Wo2 = WO(W2, "WO-2") completed with `invoice_id=C`; no W1 order points at C | note `"Damaged"` | no exception; returns the invoice with `id == C`; re-read `invoice_status == "voided"` | pass |
| VD-20 | R3a, R5; F1 | isolation | CI (id C); P2 = PO(W2, "PO-2") stage `Complete` (ST in W2) with `invoice_id=C`; E0 = EO(W0, "EXP-0") completed with `invoice_id=C`; no W1 order points at C | note `"Damaged"` | no exception; returns the invoice with `id == C`; re-read `invoice_status == "voided"` | pass |
| VD-21 | R3a, R5; F1 | boundary | E1 = EO(W1, "EXP-1") completed, `invoice_id` None; CI (id C) with `order_type="expense_order"`, `order_id=E1.id` (linked only by type/id) | note `"Damaged"` | no exception; returns the invoice with `id == C`; re-read `invoice_status == "voided"` | pass |
| VD-22 | R2, R3a (check order); Errors 2 | error | VI (id V, `void_note` "Old reason"); S1 = SO(W1, "SO-1") completed with `invoice_id=V` | note `"Again"` | raises `HTTPException` 400, `detail == "Invoice is already voided"`; session clean; re-read: VI unchanged (`void_note == "Old reason"`); 0 events | pass |
| VD-23 | R3, R3a (check order); Errors 3 | error | DI (id D) with PA = PAY(DI, 100.00); S1 = SO(W1, "SO-1") completed with `invoice_id=D` | note `"x"` | raises `HTTPException` 400, `detail == "Draft invoices cannot be voided — delete them instead"`; session clean; re-read: DI unchanged; PA `is_voided is False`; 0 events | pass |
| VD-24 | R3a [BUG-2731]; F3 | bug | CI (id C); P1 = PO(W1, "PO-1") stage `Complete` with `voided=True`, `invoice_id=C` (the order's void flag does not lift the freeze) | note `"Damaged"` | raises `HTTPException` 400, `detail == LOCK("purchase order")`; session clean; re-read: CI unchanged; 0 events | xfail BUG-2731 — fails today on: raises (no exception) |
| VD-25 | R3a [BUG-2731]; F3 | bug | CI (id C); Wo1 = WO(W1, "WO-1") with `status="COMPLETED"`, `is_deleted=True`, `invoice_id=C` | note `"Damaged"` | raises `HTTPException` 400, `detail == LOCK("work order")`; session clean; re-read: CI unchanged; 0 events | xfail BUG-2731 — fails today on: raises (no exception) |
| VD-26 | R3b, R3c, R4, R5, R7; F6 | happy | P1 = PO(W1, "PO-1") stage `Complete` with `invoice_id=OI.id`; CN for P1 with POR(W1) `invoice_id=CN.id`, `status="pending"`; CN `paid_amount=50.00`, `payment_status="partial"`; PA = PAY(CN, 50.00) | `void_invoice(session, CN.id, W1, U2.id, "Wrong qty")` | no exception; returns the invoice with `id == CN.id`; re-read CN: `invoice_status == "voided"`, `void_note == "Wrong qty"`, `paid_amount == 0.00`; PA `is_voided is True`, `voided_by == U2.id`; Events for CN: E("voided", "Invoice voided", U2.id, {"prior_status": "confirmed", "payments_voided": 1, "void_note": "Wrong qty"}); OI re-read `invoice_status == "confirmed"` | pass |
| VD-27 | R3b, R3c, R5; F6 | happy | S1 = SO(W1, "SO-1") completed with `invoice_id=OI.id`; CN for S1 with SOR(W1) `invoice_id=CN.id`, `status="pending"` | `void_invoice(session, CN.id, W1, U2.id, "Wrong qty")` | no exception; returns the invoice with `id == CN.id`; re-read CN `invoice_status == "voided"`, `void_note == "Wrong qty"`; OI re-read `invoice_status == "confirmed"` | pass |
| VD-28 | R3b, R3a, R3c, R5; F6 | boundary | S1 = SO(W1, "SO-1") completed; CN for S1 with SOR(W1) `invoice_id=CN.id`, `status="pending"`; S1 `invoice_id=CN.id` (CN is both the return's and the order's invoice; no OI) | `void_invoice(session, CN.id, W1, U2.id, "Wrong qty")` | no exception (a credit note is never frozen); returns the invoice with `id == CN.id`; re-read CN `invoice_status == "voided"` | pass |
| VD-29 | R3a, R3b [BUG-2731]; Errors 4; F1, F6 | bug | CI (id C) with `paid_amount=200.00`, `payment_status="partial"`; PA = PAY(CI, 200.00); S1 = SO(W1, "SO-1") completed with `invoice_id=C`; POR(W0) with `invoice_id=C`; SOR(W2) with `invoice_id=C` (return rows of other workspaces do not make CI a credit note); no W1 return row points at C | note `"Damaged"` | raises `HTTPException` 400, `detail == LOCK("sales order")`; session clean; re-read: CI unchanged (status confirmed, `paid_amount == 200.00`, `void_note` None); PA `is_voided is False`, `voided_at is None`, `voided_by is None`; 0 events | xfail BUG-2731 — fails today on: raises (no exception — invoice and payment voided) |
| VD-30 | R3a, R5; F2 (exact name) | boundary | CI (id C); P1 = PO(W1, "PO-1") stage `complete` (lower-case c) with `invoice_id=C` | note `"Damaged"` | no exception; returns the invoice with `id == C`; re-read `invoice_status == "voided"` | pass |
| VD-31 | R3a, R5; F2 (exact name) | boundary | CI (id C); P1 = PO(W1, "PO-1") stage `" Complete"` (leading space) with `invoice_id=C` | note `"Damaged"` | no exception; returns the invoice with `id == C`; re-read `invoice_status == "voided"` | pass |
| VD-32 | R3a, R5; F2 (exact name) | boundary | CI (id C); P1 = PO(W1, "PO-1") stage `Completed` with `invoice_id=C` | note `"Damaged"` | no exception; returns the invoice with `id == C`; re-read `invoice_status == "voided"` | pass |
| VD-33 | R3c [BUG-2788]; F6 | bug | P1 = PO(W1, "PO-1") stage `Draft` with `invoice_id=OI.id`; CN for P1 with R = POR(W1) `invoice_id=CN.id`, `status="pending"`, `paid=True`; CN `invoice_amount=1000.00`, `paid_amount=1000.00`, `payment_status="paid"`; PA = PAY(CN, 1000.00) | `void_invoice(session, CN.id, W1, U2.id, "Wrong qty")` | returns the invoice with `id == CN.id`; re-read CN: `invoice_status == "voided"`, `paid_amount == 0.00`; PA `is_voided is True`; re-read R: `status == "voided"`, `paid is False` | xfail BUG-2788 — fails today on: re-read R `status == "voided"` (today the return stays `pending`) |
| VD-34 | R3c [BUG-2788]; F6 | bug | S1 = SO(W1, "SO-1") with `invoice_id=OI.id`; CN for S1 with R = SOR(W1) `invoice_id=CN.id`, `status="pending"`, `paid=True`; CN `invoice_amount=1000.00`, `paid_amount=1000.00`, `payment_status="paid"`; PA = PAY(CN, 1000.00) | `void_invoice(session, CN.id, W1, U2.id, "Wrong qty")` | returns the invoice with `id == CN.id`; re-read CN: `invoice_status == "voided"`, `paid_amount == 0.00`; PA `is_voided is True`; re-read R: `status == "voided"`, `paid is False` | xfail BUG-2788 — fails today on: re-read R `status == "voided"` (today `pending`) |
| VD-35 | R3c [BUG-2788]; Errors 5; F6 | bug | P1 = PO(W1, "PO-1") stage `Draft` with `invoice_id=OI.id`; CN for P1 with R = POR(W1) `invoice_id=CN.id`, `status="completed"`, `paid=True`; CN `invoice_amount=1000.00`, `paid_amount=1000.00`, `payment_status="paid"`; PA = PAY(CN, 1000.00) | `void_invoice(session, CN.id, W1, U2.id, "Wrong qty")` | raises `HTTPException` 400, `detail == RETTXT`; session clean; re-read: CN unchanged (status confirmed, `paid_amount == 1000.00`, `void_note` None); PA `is_voided is False`, `voided_at is None`; R `status == "completed"`, `paid is True`; 0 events for CN | xfail BUG-2788 — fails today on: raises (no exception — the credit note is voided) |
| VD-36 | R3c [BUG-2788]; Errors 5; F6 | bug | S1 = SO(W1, "SO-1") with `invoice_id=OI.id`; CN for S1 with R = SOR(W1) `invoice_id=CN.id`, `status="completed"`, `paid=True`; CN `invoice_amount=1000.00`, `paid_amount=1000.00`, `payment_status="paid"`; PA = PAY(CN, 1000.00) | `void_invoice(session, CN.id, W1, U2.id, "Wrong qty")` | raises `HTTPException` 400, `detail == RETTXT`; session clean; re-read: CN unchanged; PA `is_voided is False`, `voided_at is None`; R `status == "completed"`, `paid is True`; 0 events for CN | xfail BUG-2788 — fails today on: raises (no exception) |
| VD-37 | R3c; F6 | boundary | P1 = PO(W1, "PO-1") stage `Draft` with `invoice_id=OI.id`; CN for P1 with R = POR(W1) `invoice_id=CN.id`, `status="voided"`, `paid=False` | `void_invoice(session, CN.id, W1, U2.id, "Wrong qty")` | no exception; returns the invoice with `id == CN.id`; re-read CN `invoice_status == "voided"`; re-read R: `status == "voided"`, `paid is False` (unchanged); Events for CN: E("voided", "Invoice voided", U2.id, {"prior_status": "confirmed", "payments_voided": 0, "void_note": "Wrong qty"}) | pass |
| VD-38 | R3c; F6 | boundary | S1 = SO(W1, "SO-1") with `invoice_id=OI.id`; CN for S1 with R = SOR(W1) `invoice_id=CN.id`, `status="voided"`, `paid=False` | `void_invoice(session, CN.id, W1, U2.id, "Wrong qty")` | no exception; returns the invoice with `id == CN.id`; re-read CN `invoice_status == "voided"`; re-read R: `status == "voided"`, `paid is False` (unchanged) | pass |
| VD-39 | R3a, R3b, R3c (check order) [BUG-2788]; Errors 5 | bug | S1 = SO(W1, "SO-1") completed; CN for S1 with R = SOR(W1) `invoice_id=CN.id`, `status="completed"`; S1 `invoice_id=CN.id` (CN is also the completed order's invoice; no OI) | `void_invoice(session, CN.id, W1, U2.id, "Wrong qty")` | raises `HTTPException` 400, `detail == RETTXT` (not LOCK: a credit note is never frozen, its return decides); session clean; re-read: CN unchanged; R `status == "completed"`; 0 events for CN | xfail BUG-2788 — fails today on: raises (no exception) |
| VD-40 | R3b, R3c [BUG-2788]; Errors 5 | bug | P1 = PO(W1, "PO-1") stage `Complete` with `invoice_id=OI.id`; CN for P1 with R = POR(W1) `invoice_id=CN.id`, `status="completed"` | `void_invoice(session, CN.id, W1, U2.id, "Wrong qty")` | raises `HTTPException` 400, `detail == RETTXT`; session clean; re-read: CN unchanged; R `status == "completed"`; OI unchanged; 0 events for CN | xfail BUG-2788 — fails today on: raises (no exception) |
| VD-41 | R2, R3c (check order); Errors 2 | error | P1 = PO(W1, "PO-1") stage `Draft` with `invoice_id=OI.id`; CN for P1 with R = POR(W1) `invoice_id=CN.id`, `status="completed"`; CN `invoice_status="voided"`, `void_note="Old reason"` | `void_invoice(session, CN.id, W1, U2.id, "Again")` | raises `HTTPException` 400, `detail == "Invoice is already voided"`; session clean; re-read: CN unchanged (`void_note == "Old reason"`); R `status == "completed"`; 0 events for CN | pass |
| VD-42 | R3, R3c (check order); Errors 3 | error | S1 = SO(W1, "SO-1") with `invoice_id=OI.id`; CN for S1 with R = SOR(W1) `invoice_id=CN.id`, `status="completed"`; CN `invoice_status="draft"` | `void_invoice(session, CN.id, W1, U2.id, "x")` | raises `HTTPException` 400, `detail == "Draft invoices cannot be voided — delete them instead"`; session clean; re-read: CN unchanged; R `status == "completed"`; 0 events for CN | pass |
| VD-43 | R3a, R3b, R3c [BUG-2788] | bug | S1 = SO(W1, "SO-1") completed; CN for S1 with R = SOR(W1) `invoice_id=CN.id`, `status="pending"`, `paid=False`; S1 `invoice_id=CN.id` (no OI) | `void_invoice(session, CN.id, W1, U2.id, "Wrong qty")` | returns the invoice with `id == CN.id`; re-read CN `invoice_status == "voided"`; re-read R `status == "voided"` | xfail BUG-2788 — fails today on: re-read R `status == "voided"` (today `pending`) |
| VD-44 | R3c; F6 | isolation | CI (id C, `paid_amount=0.00`), no W1 return row points at it; POR(W0) `invoice_id=C`, `status="completed"`; RX = SOR(W2) `invoice_id=C`, `status="pending"` (returns of other workspaces, lower and higher workspace id) | note `"Damaged"` | no exception; returns the invoice with `id == C`; re-read CI `invoice_status == "voided"`; POR(W0) `status == "completed"`; RX `status == "pending"` (not cancelled) | pass |
| VD-45 | R3c; F6 | isolation | CI (id C, `paid_amount=0.00`), no W1 return row points at it; RX = POR(W2) `invoice_id=C`, `status="pending"`; SOR(W0) `invoice_id=C`, `status="completed"` | note `"Damaged"` | no exception; returns the invoice with `id == C`; re-read CI `invoice_status == "voided"`; RX `status == "pending"` (not cancelled); SOR(W0) `status == "completed"` | pass |
| VD-46 | R3c [BUG-2788, HR-10] | bug | P1 = PO(W1, "PO-1") stage `Draft` with `invoice_id=OI.id`; CN for P1 with R = POR(W1) `invoice_id=CN.id`, `status="pending"`; SQL capture on | `void_invoice(session, CN.id, W1, U2.id, "Wrong qty")` | returns the invoice with `id == CN.id`; captured SQL locks the return `purchase_order_returns` | xfail BUG-2788 — fails today on: no `FOR UPDATE` on `purchase_order_returns` captured (the return is never read) |
| VD-47 | R3c [BUG-2788, HR-10] | bug | S1 = SO(W1, "SO-1") with `invoice_id=OI.id`; CN for S1 with R = SOR(W1) `invoice_id=CN.id`, `status="pending"`; SQL capture on | `void_invoice(session, CN.id, W1, U2.id, "Wrong qty")` | returns the invoice with `id == CN.id`; captured SQL locks the return `sales_order_returns` | xfail BUG-2788 — fails today on: no `FOR UPDATE` on `sales_order_returns` captured |
| VD-48 | R3c [BUG-2788]; F6 | bug | P1 = PO(W1, "PO-1") stage `Draft` with `invoice_id=OI.id`; CN for P1 (the CN invoice row only; its return rows follow, built in this order and flushed after each one): (1) R0 = POR(W0) `invoice_id=CN.id`, `status="completed"`, flush; (2) R = POR(W1) `invoice_id=CN.id`, `status="pending"`, `paid=False` (CN's own return), flush; (3) RY = POR(W2) `invoice_id=CN.id`, `status="pending"`, flush. The executor asserts `R0.id < R.id < RY.id` as a precondition, so "first matching row" without a workspace filter picks R0 (foreign rows on both sides, by workspace id and by row id) | `void_invoice(session, CN.id, W1, U2.id, "Wrong qty")` | no exception (R0 being completed does not refuse); returns the invoice with `id == CN.id`; re-read CN `invoice_status == "voided"`; R0 `status == "completed"` (unchanged); RY `status == "pending"`, `paid is False` (unchanged); re-read R `status == "voided"`, `paid is False` | xfail BUG-2788 — fails today on: re-read R `status == "voided"` (today the W1 return stays `pending`) |

## `AccountInvoiceManager.set_receiving_started`

Call: `set_receiving_started(session, inv.id, W1, performed_by, reason)`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| RS-01 | R3, R4 | happy | CI (`receiving_started` False) | `performed_by=U2.id`, `reason="PO-1001 received"` | returns the invoice with `id == CI.id`; re-read `receiving_started is True`; Events: E("receiving_started_set", "PO-1001 received", U2.id, None) | pass |
| RS-02 | R3, R4 | boundary | CI | `performed_by=None`, `reason=""` | returns the invoice; re-read `receiving_started is True`, `updated_by is None`; Events: E("receiving_started_set", "Receiving started on linked order", None, None) | pass |
| RS-03 | R3 | boundary | DI | `performed_by=U2.id`, `reason="r"` | returns the invoice; re-read `receiving_started is True`, status still draft; 1 event | pass |
| RS-04 | R3 | boundary | VI | `performed_by=U2.id`, `reason="r"` | returns the invoice; re-read `receiving_started is True`, status still voided; 1 event | pass |
| RS-05 | R2 | boundary | CI with `receiving_started=True` | `performed_by=U2.id`, `reason="again"` | returns the invoice with `id == CI.id`; re-read `receiving_started is True`, `updated_by is None`; 0 events | pass |
| RS-06 | R1 | error | none | `set_receiving_started(session, NOID, W1, U2.id, "r")` | returns `None`; no exception; 0 `invoice_events` in W1 | pass |
| RS-07 | R1 | isolation | CI inserted in W2, id X | `set_receiving_started(session, X, W1, U2.id, "r")` | returns `None`; the W2 row has `receiving_started is False`; 0 events | pass |
| RS-08 | R3 [BUG-633] | bug | CI | `performed_by=U2.id`, `reason="r"` | returns the invoice; re-read `updated_by == U2.id` | xfail BUG-633 — fails today on: `updated_by is None` |
| RS-09 | R1 [BUG-621] | bug | CI; SQL capture on | `performed_by=U2.id`, `reason="r"` | returns the invoice; captured SQL locks the invoice; re-read `receiving_started is True` | xfail BUG-621 — fails today on: no `FOR UPDATE` captured |

## `AccountInvoiceManager.sync_items_from_list`

Call: `sync_items_from_list(session, inv, items, user_id)` (never `is_manual`). **D(desc, q, p, s, **extra)** = dict `{"description": desc, "quantity": Decimal(q), "unit_price": Decimal(p), "line_subtotal": Decimal(s), **extra}`. "Items of X" = all `invoice_items` rows with `invoice_id = X.id` in any workspace, ordered by id. Each metadata item has exactly the keys `description`, `quantity`, `unit_price`, `line_subtotal`, `unit` (spec R7, G12).

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SY-01 | R2, R3, R5, R6, R7 | happy | DI (amount 1000.00, paid 0.00); ITEM(DI, 10.00), ITEM(DI, 20.00); one item with `invoice_id=DI.id`, workspace W2, subtotal 5.00 | `items=[D("Steel rod","2","50.00","100.00", unit="pcs", line_number=1), D("Bolt","10","2.50","25.00", unit="box", line_number=2)]`, `user_id=U2.id` | returns `None`; items of DI: exactly 2 new rows (the 3 old rows are gone), in id order "Steel rod", "Bolt", each with `workspace_id=W1`, `invoice_id=DI.id`, `created_by=U2.id`, `last_synced_at == NOW`; re-read DI: `invoice_amount == Decimal("125.00")`, `payment_status="unpaid"`, `last_synced_at == NOW`, status draft; Events: 1 event `items_synced`, description `"Items synced from order (2 lines)"`, `performed_by=U2.id`, `metadata_json["item_count"] == 2`, `metadata_json["items"][0]` has description "Steel rod", quantity "2", unit_price "50.00", line_subtotal "100.00", unit "pcs"; `[1]` has "Bolt", "10", "2.50", "25.00", "box"; each metadata item's key set == {`description`, `quantity`, `unit_price`, `line_subtotal`, `unit`} (`line_number` not copied) | pass |
| SY-02 | R3 | boundary | DI, no items | `items=[D("A","1","10.00","10.00", created_by=U1.id), D("B","1","7.00","7.00", workspace_id=W2)]`, `user_id=U2.id` | returns `None`; item "A": `created_by=U1.id`, workspace W1; item "B": `workspace_id=W2`, `created_by=U2.id`; re-read DI `invoice_amount == Decimal("10.00")` (the W2 item is not summed) | pass |
| SY-03 | R3 | side-effect | DI | `items=[d]` with `d = D("A","1","10.00","10.00")`, `user_id=U2.id` | returns `None`; afterwards the caller's `d` has `d["workspace_id"] == W1`, `d["invoice_id"] == DI.id`, `d["created_by"] == U2.id`, `d["last_synced_at"] == NOW` | pass |
| SY-04 | R3 | boundary | DI | `items=[D("A","1","10.00","10.00", last_synced_at=V0)]`, `user_id=U2.id` | returns `None`; the new item has `last_synced_at == NOW` (always overwritten) | pass |
| SY-05 | R4, R5, R6 | boundary | DI (amount 1000.00, paid 0.00); ITEM(DI, 10.00), ITEM(DI, 20.00) | `items=[]`, `user_id=U2.id` | returns `None`; 0 items of DI; re-read `invoice_amount == Decimal("0.00")`, `payment_status="paid"`, `last_synced_at == NOW`; Events: E("items_synced", "Items synced from order (0 lines)", U2.id, {"item_count": 0, "items": []}) | pass |
| SY-06 | R1 | boundary | CI (amount 400.00, `last_synced_at` None) with ITEM(CI, 400.00) (id K) | `items=[D("New","1","5.00","5.00")]`, `user_id=U2.id` | returns `None`; items of CI == exactly [K] (unchanged); re-read `invoice_amount == 400.00`, `last_synced_at is None`; 0 events | pass |
| SY-07 | R1 | boundary | VI with ITEM(VI, 400.00) (id K) | same | returns `None`; items of VI == [K]; `invoice_amount == 1000.00`; 0 events | pass |
| SY-08 | R7 | boundary | DI | `items=[D("","1","1.00","1.00", line_number=5), D("","1","2.00","2.00")]`, `user_id=U2.id` | returns `None`; `metadata_json["items"][0]["description"] == "Line 5"`; `[1]["description"] == "Line 2"` (1-based position); both items have `unit is None` (no `unit` key given) | pass |
| SY-09 | R6 | side-effect | DI | `items=[D("A","1","10.00","10.00")]`, `user_id=None` | returns `None`; the new item has `created_by is None`; the event has `performed_by is None`, description `"Items synced from order (1 lines)"` | pass |
| SY-10 | R7a; Errors (missing column) | error | DI with ITEM(DI, 10.00) (id K) | inside a savepoint: `items=[{"description": "A", "quantity": Decimal("1"), "unit_price": Decimal("10.00")}]` (no `line_subtotal`) | raises a SQLAlchemy `IntegrityError` (or another DB error at flush); after the savepoint rollback, items of DI == [K]; DI `invoice_amount == 1000.00`; 0 events | pass |
| SY-11 | R7a; Errors (None column) | error | DI with ITEM(DI, 10.00) (id K) | inside a savepoint: `items=[D("A","1","10.00","10.00")]` with `quantity` replaced by `None` | raises a SQLAlchemy `IntegrityError` (or another DB error at flush); after the savepoint rollback, items of DI == [K]; DI `invoice_amount == 1000.00`; 0 events | pass |

## `AccountInvoiceManager.get_events`

Call: `get_events(session, inv.id, W1)`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EV-01 | R2 | happy | DI; E1 = EVT(DI, 2026-09-01 10:00, performed_by=U1.id); E2 = EVT(DI, 2026-09-02 10:00); E3 = EVT(DI, 2026-09-03 10:00, performed_by=U1.id) | call | returns a list of 3 dicts with ids [E3, E2, E1]; each dict's keys are exactly {`id`, `workspace_id`, `invoice_id`, `event_type`, `description`, `metadata_json`, `performed_by`, `performed_by_name`, `created_at`}; E1 dict: `performed_by == U1.id`, `performed_by_name == "Rahim Uddin"`, `workspace_id == W1`, `invoice_id == DI.id`, `event_type == "note"`, `description == "n"`, `metadata_json is None`, `created_at == 2026-09-01 10:00`; E2 dict: `performed_by is None`, `performed_by_name is None` | pass |
| EV-02 | R2 | isolation | DI with E1 = EVT(DI, 2026-09-01 10:00); J = another draft with EVT(J, 2026-09-02 10:00); one event row with `invoice_id=DI.id` and `workspace_id=W2` (created_at 2026-09-03) | call | returns exactly [E1] | pass |
| EV-03 | R1 | error | none | `get_events(session, NOID, W1)` | raises 404, detail `"Invoice with ID 999999 not found"` | pass |
| EV-04 | R1 | isolation | DI inserted in W2 with one event, id X | `get_events(session, X, W1)` | raises 404 | pass |
| EV-05 | R2 [BUG-638] | bug | DI; reserve N1 < N2 < N3 = three `nextval` calls on the `invoice_events` id sequence; insert EVT(DI, 2026-09-01 10:00) rows with explicit ids, each flushed, in this order: id N2, then N1, then N3 | call | ids in order == [N3, N2, N1] | xfail BUG-638 (strict) — fails today on: the order is not [N3, N2, N1] (with no tie-breaker the result follows physical order [N2, N1, N3] or its reverse [N3, N1, N2]) |
| EV-06 | R2 | boundary | DI with 101 events at 2026-09-01 00:00 + n minutes | call | 101 dicts returned (no paging); the first is the latest | pass |

## `AccountInvoiceManager.get_items`

Call: `get_items(session, inv.id, W1)`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| IT-01 | R2 | happy | DI; items inserted in this order: X3 = ITEM(DI, 3.00, line_number=3), X1 = ITEM(DI, 1.00, line_number=1), X2 = ITEM(DI, 2.00, line_number=2); one item with `invoice_id=DI.id`, workspace W2, line 0; J = another draft with ITEM(J, 9.00, line_number=1) | call | returns `InvoiceItem`s with ids [X1, X2, X3] exactly | pass |
| IT-02 | R1 | error | none | `get_items(session, NOID, W1)` | raises 404, detail `"Invoice with ID 999999 not found"` | pass |
| IT-03 | R1 | isolation | DI inserted in W2 with one item, id X | `get_items(session, X, W1)` | raises 404 | pass |
| IT-04 | R2 [BUG-638] | bug | DI; reserve N1 < N2 < N3 = three `nextval` calls on the `invoice_items` id sequence; insert ITEM(DI, 1.00, line_number=1) rows with explicit ids, each flushed, in this order: id N2, then N1, then N3 | call | ids in order == [N1, N2, N3] | xfail BUG-638 (strict) — fails today on: the order is not [N1, N2, N3] (with no tie-breaker the result follows physical order [N2, N1, N3] or its reverse [N3, N1, N2]) |
| IT-05 | R2 | boundary | DI with 101 items, `line_number` 1..101 | call | 101 items returned, `line_number` ascending | pass |

## Deferred to other specs

| Rule | Owner | What must be tested there |
|---|---|---|
| `update_invoice` R1, `delete_invoice` R1, `confirm_invoice` R1, `revert_to_draft` R1, `void_invoice` R1, `set_receiving_started` R1 [BUG-621] (concurrency) | integration tests (two committed sessions) | Two concurrent state changes on one committed invoice: the second waits on the row lock, then sees the new state and gets the normal wrong-state 400. For example: two confirms → one succeeds and one gets `"Invoice is already confirmed"`, with exactly one `confirmed` event. Two `set_receiving_started` → exactly one `receiving_started_set` event. Void racing a payment record → no active payment on the voided invoice. (The lock clause itself is unit-tested by U-03, DEL-08, CF-10, RV-12, VD-08, RS-09.) |
| `create_invoice` R9 [BUG-627], R9a [BUG-624], R9c [BUG-625], `void_invoice` R8 [BUG-626], `update_invoice` R2a [BUG-630], R2b [BUG-625] (HTTP status) | `POST /invoices`, `POST /invoices/{id}/void`, `PUT /invoices/{id}` | The schema rejections above surface as HTTP 422 through the endpoints. The schema itself is unit-tested here (C-10/11, C-18..C-21, VD-12/13, U-06..U-10, U-56). |

## Spec gaps

| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| G16 | spec Notes O1, F2, F6 | The `statuses` table's other required columns (is it per workspace? per entity type?) and the name of the order-reference column on `purchase_order_returns` / `sales_order_returns`. | Not blocking: ST and CN in Conventions say "other required columns neutral" and "order reference points at that order"; the executor reads the models. The describer may add the facts to the Notes. |

Closed by the spec's Gap log in revision 6: G15 `order_type` sendable on update (was G14 in revision 4) → `update_invoice` R2b, its Inputs row, R2a's clearable list and a new Errors row (verify findings 7 and 10). Known limit, not a gap: "change link type via update" has no passing coverage, because it does not work today (U-38, U-45, U-46 are xfail BUG-625). Closed by the spec's Gap log in revision 5: G14 (spec) "live" order per order type → `create_invoice` R9d (verify finding 5). Closed in revision 2 (earlier titles, for traceability): G1 client `invoice_amount` on create · G2 detail texts for BUG-625/630/631 · G3 source of "today" for overdue · G4 `payment_status=overdue` filter · G5 effective `order_type` on update · G6 `account_id = 0` on update · G7 legacy status-history table · G8 SET NULL referrer tables · G9 reachability of the `null` metadata branch · G10 tie setups for BUG-638 · G11 duplicate account names · G12 recalc return values and metadata keys · G13 half-given `order_type`/`order_id`.

## Coverage matrix

| Callable | Rule / Error row | Cases |
|---|---|---|
| `_get_or_404` | R1 | G4-01, G4-02, G4-03 |
| `_get_or_404` | R2 / Errors 1 | G4-04 |
| `_get_or_404` | R3 | G4-05 |
| `_log_event` | R1 | LOG-01, LOG-02, LOG-03, LOG-04 |
| `_log_event` | R2 | LOG-01 |
| `_log_event` | Errors (non-JSON metadata) | LOG-05 |
| `_recalculate_payment_status` | R1 | RPS-01, RPS-02, RPS-03, RPS-04 |
| `_recalculate_payment_status` | R2 | RPS-04, RPS-05 |
| `_recalculate_payment_status` | R3 | RPS-06, RPS-07 |
| `_recalculate_invoice_amount` | R1 | RIA-01, RIA-02 |
| `_recalculate_invoice_amount` | R2 | RIA-03 |
| `_recalculate_invoice_amount` | R3 | RIA-01, RIA-03, RIA-04 |
| `create_invoice` | R1 / Errors 1 | C-03, C-04 |
| `create_invoice` | R2 / Errors 2 | C-05 |
| `create_invoice` | R3 / Errors 3 | C-06 |
| `create_invoice` | R4 / Errors 4 | C-07 |
| `create_invoice` | R5 | C-01, C-02 |
| `create_invoice` | R6 | C-01, C-02 |
| `create_invoice` | R7 | C-01 |
| `create_invoice` | R8 | C-01, C-02 |
| `create_invoice` | R9 [BUG-627] / Errors 6 | C-16, C-17, C-18 (C-01 amount 0.00) |
| `create_invoice` | R9a [BUG-624] / Errors 5 | C-08, C-09, C-10, C-11 |
| `create_invoice` | R9b [BUG-625] / Errors 7 | C-08, C-12, C-13, C-14, C-15, C-22, C-23, C-24, C-25, C-26, C-27 |
| `create_invoice` | R9c [BUG-625] / Errors 8 | C-19, C-20, C-21 (both given: C-08, C-09; neither: C-01) |
| `create_invoice` | R9d [BUG-625] / Errors 7 | PO: C-08 (live), C-14 (voided) · EO: C-25 (live), C-22 (voided) · WO: C-26 (live), C-23 (soft-deleted), C-24 (`VOIDED`) · SO: C-27 (any row) · on update: U-37, U-50, U-54, U-55 |
| `get_invoice` | R1 | GI-01, GI-02, GI-03 |
| `list_invoices` | R1 | L-01 |
| `list_invoices` | R2 | L-02 |
| `list_invoices` | R3 | L-03 |
| `list_invoices` | R4 | L-04, L-05 |
| `list_invoices` | R5 | L-06, L-07, L-08, L-09, L-10, L-11, L-44, L-46 |
| `list_invoices` | R5a [BUG-635] | L-45, L-46 |
| `list_invoices` | R6 | L-12 |
| `list_invoices` | R7 | L-13, L-14 |
| `list_invoices` | R8 | L-15, L-16 |
| `list_invoices` | R9 | L-17 … L-28 |
| `list_invoices` | R9a [BUG-637] | L-29 |
| `list_invoices` | R10 [BUG-622] | L-30, L-31, L-32, L-33, L-34 |
| `list_invoices` | R11 [BUG-622] | L-35, L-36, L-37, L-38 |
| `list_invoices` | R12 | L-39, L-43 |
| `list_invoices` | R13 | L-40 |
| `list_invoices` | R14 | L-41, L-42, L-43 |
| `list_open_invoices_page` | R1 | LO-01, LO-03, LO-04 |
| `list_open_invoices_page` | R2 [BUG-634] | LO-01, LO-02 |
| `list_open_invoices_page` | R3 | LO-05, LO-06, LO-09 |
| `list_open_invoices_page` | R4 | LO-07, LO-08 |
| `list_invoices_page` | R1 | LP-01, LP-02 |
| `list_invoices_page` | R2 [BUG-634] | LP-03, LP-04 |
| `list_invoices_page` | R3 | LP-05, LP-06, LP-07 |
| `get_invoices_hub_summary` | R1 | HS-02, HS-03 |
| `get_invoices_hub_summary` | R2 [BUG-634, BUG-635] | HS-01, HS-04, HS-05, HS-06, HS-07, HS-10 |
| `get_invoices_hub_summary` | R3 | HS-01, HS-04, HS-05, HS-07, HS-08 |
| `get_invoices_hub_summary` | R4 | HS-01, HS-02, HS-04, HS-09 |
| `list_accounts_hub_page` | R1 [BUG-636] | AH-01, AH-03, AH-04 |
| `list_accounts_hub_page` | R2 [BUG-634] | AH-02, AH-05, AH-07 |
| `list_accounts_hub_page` | R3 [BUG-635] | AH-06, AH-07, AH-20 |
| `list_accounts_hub_page` | R4 [BUG-622] | AH-08, AH-09, AH-10 |
| `list_accounts_hub_page` | R5 | AH-11, AH-12, AH-13, AH-14, AH-19 |
| `list_accounts_hub_page` | R6 [BUG-623] | AH-15, AH-16, AH-21, AH-22 |
| `list_accounts_hub_page` | R7 | AH-17, AH-18, AH-19 |
| `summarize_invoices` | R1 | SUM-01, SUM-02, SUM-05, SUM-06 |
| `summarize_invoices` | R2 [BUG-634] | SUM-01, SUM-03, SUM-04 |
| `update_invoice` | R1 [BUG-621] / Errors 1 | U-01, U-02, U-03; concurrency Deferred |
| `update_invoice` | R2 / Errors 2 | U-04 |
| `update_invoice` | R2a [BUG-630] / Errors 3, 4 | U-05, U-06, U-07, U-08, U-09, U-10 |
| `update_invoice` | R2b [BUG-625] / Errors 11 | schema: U-53 (four values and `None` accepted, sent field), U-56 (bad value → 422), U-57 (trim + lower-case) · draft: U-38 (both cleared), U-45 (type changed, in event metadata), U-46 (type only → re-validation), U-60 (type cleared alone → 400) · confirmed: U-58 (changed → 400), U-59 (same value → no-op); HTTP 422 Deferred |
| `update_invoice` | R3 | U-12, U-13, U-61, U-62 |
| `update_invoice` | R3b (no freeze on the three admin edits) | U-61 (completed SO), U-62 (completed PO) |
| `update_invoice` | R4 [BUG-631] / Errors 5 | U-17, U-18, U-58 |
| `update_invoice` | R4a | U-19, U-21, U-59 |
| `update_invoice` | R5 | U-20, U-21, U-59 |
| `update_invoice` | R6 [BUG-620] | U-12, U-15, U-22 |
| `update_invoice` | R7 [BUG-632] | U-12, U-13, U-14, U-19, U-23 |
| `update_invoice` | R8 [BUG-632] | U-12, U-15, U-24 |
| `update_invoice` | R9 [BUG-632] | U-12, U-16, U-25 |
| `update_invoice` | R10 [BUG-629] / Errors 6–9 | U-27, U-28, U-29, U-30, U-31, U-32, U-33 |
| `update_invoice` | R10a [BUG-629] / Errors 10 | U-51, U-52 |
| `update_invoice` | R11 | U-10, U-11, U-26 |
| `update_invoice` | R12 [BUG-625] / Errors 12 | U-26, U-34, U-35, U-36, U-37, U-38, U-42, U-45, U-54, U-55 |
| `update_invoice` | R12a [BUG-625] / Errors 12, 13 | U-38, U-45, U-46, U-47, U-48, U-49, U-50, U-60 |
| `update_invoice` | R13 [BUG-620] | U-26, U-42, U-39, U-43 |
| `update_invoice` | R14 [BUG-632] | U-26, U-27, U-38, U-42, U-45, U-40, U-41, U-44 |
| `update_invoice` | R15 | U-26 |
| `delete_invoice` | R1 [BUG-621] / Errors 1 | DEL-02, DEL-03, DEL-08; concurrency Deferred |
| `delete_invoice` | R2 / Errors 2 | DEL-04, DEL-05, DEL-22 (before R2a) |
| `delete_invoice` | R2a [BUG-2730] / Errors 3 | per kind: DEL-14 (PO), DEL-15 (SO), DEL-16 (EO), DEL-17 (WO) · F3: DEL-28 (voided PO) · not frozen: DEL-01 (PO `Draft`), DEL-11 (EO/SO/WO not completed), DEL-18 (PO `Receiving`), DEL-19, DEL-20 (other workspaces), DEL-21 (type/id link only), DEL-25, DEL-26, DEL-27 (near-miss stage names) · order: DEL-22 (R2 first), DEL-23, DEL-24 (before R4) |
| `delete_invoice` | R3 | DEL-01, DEL-11, DEL-12, DEL-13, DEL-18, DEL-19, DEL-20, DEL-21, DEL-25, DEL-26, DEL-27 |
| `delete_invoice` | R4 [BUG-639] / Errors 4 | DEL-06, DEL-07, DEL-09, DEL-10, DEL-24 |
| `confirm_invoice` | R1 [BUG-621] / Errors 1 | CF-04, CF-05, CF-10; concurrency Deferred |
| `confirm_invoice` | R2 / Errors 2 | CF-06 |
| `confirm_invoice` | R3 / Errors 3 | CF-07 |
| `confirm_invoice` | R4 [BUG-628] / Errors 4 | CF-01, CF-02, CF-03, CF-08 |
| `confirm_invoice` | R5 [BUG-633] | CF-01, CF-09 |
| `confirm_invoice` | R6 | CF-01, CF-03 |
| `revert_to_draft` | R1 [BUG-621] / Errors 1 | RV-09, RV-10, RV-12; concurrency Deferred |
| `revert_to_draft` | R2 / Errors 2 | RV-07, RV-08, RV-32 (before R2b), RV-44 (before R2a) |
| `revert_to_draft` | R2a [BUG-2733] / Errors 3 | RV-37 (PO return), RV-38 (SO return, completed order), RV-39 (before R2b), RV-40, RV-41 (before R3), RV-42, RV-43 (before R4), RV-44 (after R2) · not a credit note: RV-45, RV-46 (return rows of other workspaces) |
| `revert_to_draft` | R2b [BUG-2730] / Errors 4 | per kind: RV-15 (PO), RV-16 (SO), RV-17 (EO), RV-18 (WO) · not frozen: RV-19 (PO `Receiving`), RV-20, RV-21 (other workspaces), RV-22 (type/id link only), RV-23 (WO `IN_PROGRESS`), RV-24 (WO `VOIDED`), RV-25, RV-26, RV-27 (near-miss stage names) · kind: RV-28..RV-31, RV-47, RV-48 · order: RV-32, RV-33, RV-34 (before R3), RV-35, RV-36 (before R4) |
| `revert_to_draft` | R3 / Errors 5 | RV-05, RV-06, RV-34, RV-41 |
| `revert_to_draft` | R3a [BUG-2736] / Errors 5 | RV-13, RV-14 |
| `revert_to_draft` | R4 / Errors 6 | RV-02, RV-03, RV-04, RV-06, RV-14, RV-36, RV-43 |
| `revert_to_draft` | R5 [BUG-633] | RV-01, RV-11, RV-19 … RV-27, RV-45, RV-46 |
| `revert_to_draft` | R6 | RV-01 |
| `void_invoice` | R1 [BUG-621] / Errors 1 | VD-05, VD-06, VD-08; concurrency Deferred |
| `void_invoice` | R2 / Errors 2 | VD-03, VD-22 (before R3a) |
| `void_invoice` | R3 / Errors 3 | VD-04, VD-23 (before R3a) |
| `void_invoice` | R3a [BUG-2731] / Errors 4 | per kind: VD-14 (PO), VD-15 (SO), VD-16 (EO), VD-17 (WO) · F3: VD-24 (voided PO), VD-25 (deleted WO) · other-workspace return rows: VD-29 · not frozen: VD-18 (PO `Receiving`), VD-19, VD-20 (other workspaces), VD-21 (type/id link only), VD-30, VD-31, VD-32 (near-miss stage names) · order: VD-22, VD-23 |
| `void_invoice` | R3b (credit note never frozen) | VD-26 (PO return), VD-27 (SO return), VD-28 (credit note is also the order's invoice), VD-39, VD-40, VD-43 · not a credit note: VD-29 (return rows of other workspaces) |
| `void_invoice` | R3c [BUG-2788] / Errors 5 | pending: VD-33 (PO), VD-34 (SO), VD-43 · completed: VD-35 (PO), VD-36 (SO) · already voided: VD-37 (PO), VD-38 (SO) · order: VD-39, VD-40 (before LOCK), VD-41 (after R2), VD-42 (after R3) · other workspaces: VD-44, VD-45, VD-48 · lock: VD-46, VD-47 · invoice side only: VD-26, VD-27, VD-28 |
| `void_invoice` | R4 | VD-01, VD-02, VD-18, VD-26, VD-33, VD-34 |
| `void_invoice` | R5 | VD-01, VD-18 … VD-21, VD-26, VD-27, VD-28, VD-30, VD-31, VD-32, VD-37, VD-38, VD-44, VD-45, VD-48 |
| `void_invoice` | R6 [BUG-633] | VD-07 |
| `void_invoice` | R7 | VD-01, VD-02, VD-18, VD-26, VD-37 |
| `void_invoice` | R8 [BUG-626] / Errors 6 | VD-09, VD-10, VD-11, VD-12, VD-13; HTTP 422 Deferred |
| Shared freeze | F1 (the order's own invoice slot, same workspace) | DEL-19..21, RV-20..22, VD-19..21, RV-38 |
| Shared freeze | F2 (completion per kind) | DEL-14..18, DEL-25..27, RV-15..19, RV-23..27, VD-14..18, VD-30..32 |
| Shared freeze | F3 (only completion counts) | VD-24, VD-25, DEL-28, RV-24 |
| Shared freeze | F4 (a draft can be frozen) | DEL-14..17, DEL-23 |
| Shared freeze | F5 (400, fixed text, kind, nothing written) | every freeze xfail above; kind priority RV-28..31, RV-47, RV-48 |
| Shared freeze | F6 (credit note) | RV-37..46, VD-26..29, VD-33..45, VD-48 |
| Shared freeze | F7 (update etc. unchanged) | U-61, U-62; payments: `InvoicePaymentManager`, not here |
| `set_receiving_started` | R1 [BUG-621] | RS-06, RS-07, RS-09; concurrency Deferred |
| `set_receiving_started` | R2 | RS-05 |
| `set_receiving_started` | R3 [BUG-633] | RS-01, RS-02, RS-03, RS-04, RS-08 |
| `set_receiving_started` | R4 | RS-01, RS-02 |
| `sync_items_from_list` | R1 | SY-06, SY-07 |
| `sync_items_from_list` | R2 | SY-01 |
| `sync_items_from_list` | R3 | SY-01, SY-02, SY-03, SY-04 |
| `sync_items_from_list` | R4 | SY-05 |
| `sync_items_from_list` | R5 | SY-01, SY-05 |
| `sync_items_from_list` | R6 | SY-01, SY-05, SY-09 |
| `sync_items_from_list` | R7 | SY-01, SY-08 |
| `sync_items_from_list` | R7a | SY-10, SY-11 (the unreachable `null` metadata branch is not tested, per spec) |
| `sync_items_from_list` | Errors (missing column / None value) | SY-10, SY-11 |
| `get_events` | R1 | EV-03, EV-04 |
| `get_events` | R2 [BUG-638] | EV-01, EV-02, EV-05, EV-06 |
| `get_items` | R1 | IT-02, IT-03 |
| `get_items` | R2 [BUG-638] | IT-01, IT-04, IT-05 |
| BUG tags | BUG-620 | U-22, U-39, U-43 |
| BUG tags | BUG-621 | U-03, DEL-08, CF-10, RV-12, VD-08, RS-09 |
| BUG tags | BUG-622 | L-33, L-34, L-36, L-37, L-38, AH-09, AH-10 |
| BUG tags | BUG-623 | AH-15, AH-22 |
| BUG tags | BUG-624 | C-10, C-11 |
| BUG tags | BUG-625 | C-12, C-13, C-14, C-15, C-19, C-20, C-21, C-22, C-23, C-24, U-35, U-36, U-37, U-38, U-45, U-46, U-47, U-48, U-53, U-54, U-56, U-57, U-58, U-60 |
| BUG tags | BUG-626 | VD-12, VD-13 |
| BUG tags | BUG-627 | C-16, C-17, C-18 |
| BUG tags | BUG-628 | CF-08 |
| BUG tags | BUG-629 | U-31, U-32, U-51 |
| BUG tags | BUG-630 | U-06, U-07, U-08, U-09, U-10 |
| BUG tags | BUG-631 | U-17, U-18, U-58 (with BUG-625) |
| BUG tags | BUG-632 | U-23, U-24, U-25, U-40, U-41, U-44 |
| BUG tags | BUG-633 | CF-09, RV-11, VD-07, RS-08 |
| BUG tags | BUG-634 | LO-02, LP-04, HS-05, AH-05, SUM-04 |
| BUG tags | BUG-635 | L-45, HS-06, HS-10, AH-06, AH-20 |
| BUG tags | BUG-636 | AH-03 |
| BUG tags | BUG-637 | L-29 |
| BUG tags | BUG-638 | EV-05, IT-04 |
| BUG tags | BUG-639 | DEL-06, DEL-09 |
| BUG tags | BUG-2730 | DEL-14, DEL-15, DEL-16, DEL-17, DEL-23, RV-15, RV-16, RV-17, RV-18, RV-28, RV-29, RV-30, RV-31, RV-33, RV-35, RV-47, RV-48, DEL-28 |
| BUG tags | BUG-2731 | VD-14, VD-15, VD-16, VD-17, VD-24, VD-25, VD-29 |
| BUG tags | BUG-2733 | RV-37, RV-38, RV-39, RV-40, RV-42 |
| BUG tags | BUG-2735 | no case (dead `locked` status; Conventions forbid setting it) |
| BUG tags | BUG-2736 | RV-13, RV-14 |
| BUG tags | BUG-2788 | VD-33, VD-34, VD-35, VD-36, VD-39, VD-40, VD-43, VD-46, VD-47, VD-48 |
