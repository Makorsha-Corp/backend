# Test cases — `app/services/work_order_service.py`

> **Spec:** `tests/unit/services/work_order_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 4 (2026-11-22) — verifier findings 1–3 (`work_order_service.verify.md`, NEEDS WORK). (1) TC3: every error card with X (43 cards) checks `X not in db` right after the raise, before any test rollback; one passing error card per write method (E-02, T-03, U-09, B-04, SE-03, X-02, S-02, C-16, P-14, V-11, I-18, AA-04, RA-02, AP-02, UA-02, AI-03, UI-03, RI-02) also runs inside **spies** and checks `rb.call_count >= 1`. (2) New SB-13 (no `exclude_completed`: a completed order is listed, default False) and SB-14 (`True` passed through). (3) New LE-14 (`_WorkOrderEnrichment` frozen, fields in order; Facts G4). S-02 Then 9 names the column `qty` (verify DISCREPANCY-8 wording).
> **Revision:** 3 (2026-11-22) — spec gap log G7–G10 and the executor round applied: V-03 → strict xfail BUG-3229 on Then 3 (V4a), pass companion V-19 added; X-06, X-08, X-09, X-11 check the invoice id (`{"invoice_id": V.id}`, X2/X3 read order); U-07 expects the title unchanged (U4a); R-03 rebuilt on W6 (a soft-deleted type still gives its name); AA-03 builds the not-ready order with `title="   "` (A4, Facts Constraints); SB-01…03 read `b.approvers.approvers[0]` / `b.approvers.summary` (SB2); `inventory` counted in **nothing written**; line order in SB-01, SB-04, GI-01 compared as sets (BUG-1272, the DAO's, no ORDER BY); read cards check `X in db` instead of `X in db.new` on the flushed X.
> **Revision 2** (2026-11-22) — spec gap log G1–G6 and Facts L1 applied: lock check widened to `FOR UPDATE( OF work_orders)?` (L1); notification and `utcnow` patch targets and `_WorkOrderEnrichment` fields now stated, `Author: claude` dropped on U-08, AA-09, I-36, I-30; B3 / SE3 another workspace's invoice left alone (B-11 extended; new B-13, SE-10); `-5.00` storable (I-22 note). Spec gaps closed.
> **Counts:** 267 cases · 228 expected-to-pass · 39 expected-to-fail (bugs) · 8 deferred

## Reviewer summary
- **Depth:** full (skill step 1a). The service makes, confirms and deletes payable invoices, completes and voids orders. Manager rules are not re-tested (they live in `work_order_manager.cases.md`); each path gets one pass-through card, and each manager / invoice-manager bug the service reaches through a tagged rule gets one pass-through xfail (BUG-1279, 2931 ×3, 2917, 628, 639).
- **Per callable:** `_load_work_order_enrichment` 14 · `_to_work_order_response` 14 · `_to_work_order_responses` 3 · `create_work_order` 4 · `create_work_order_from_template` 4 · `update_work_order` 11 · `get_work_order` 7 (1 bug) · `list_work_orders` 5 · `bulk_delete_future_recurrence_drafts` 13 (5 bug) · `sheet_entry` 10 (2 bug) · `list_sheet_bundles` 14 · `sheet_daily_counts` 3 · `delete_work_order` 14 (4 bug) · `start_work_order` 4 · `complete_work_order` 27 (2 bug) · `complete_work_order_as_planned` 21 (4 bug) · `void_work_order` 19 (6 bug) · `create_invoice_for_work_order` 37 (11 bug) · approvers / approvals 27 (4 bug) · events 2 · items 14.
- **Transaction contract:** every write has a commit card (`committed:` after a test-level rollback), a rollback card whose **uncommitted** extra workspace X must be gone (`X not in db` right after the raise, before the test's rollback; one spied error card per method checks `rb.call_count >= 1`), and a failing-commit card; refreshing writes check `loaded(result)`; TC5 once (E-04). Every read checks no commit, no rollback and X still in the session (`X in db`: a flushed X is persistent, and a rollback would expunge it), on success and on its 404. C-04 / P-03 check "returned as it is: neither commit nor rollback".
- **Bugs (all strict):** BUG-3222 locks ×3 (I-37, V-18, P-21) and BUG-2916 lock (C-27): statement recorder, clause `FOR UPDATE` or `FOR UPDATE OF work_orders` (Facts L1) · BUG-3223 ×3 · BUG-3224 ×3 · BUG-3225 ×4 · BUG-3226 ×1 · BUG-3227 ×7 · BUG-3228 ×3 (422) · BUG-2923 ×4 · BUG-3229 ×1 (V-03) · BUG-627 ×1 · pass-throughs ×8 (BUG-1279 ×2, 2931 ×3, 2917, 628, 639).
- **Pass companions** for what holds today and after each fix: B-07, B-09, B-11, B-13, SE-07, SE-09, SE-10, X-07, X-10, X-12, X-13, X-14, V-05, V-10, V-11, V-13, V-19, I-14, I-17, I-23, I-24, P-07, P-08, P-15.
- **Notable design choices:**
  - Concurrency is not simulated (Race simulations: none); the races of BUG-3222 / BUG-2916 are deferred to integration tests. The lock cards pin the clause of Facts L1: `FOR UPDATE`, optionally `OF work_orders`, never `NOWAIT` / `SKIP LOCKED`, on the first read of `work_orders`, before any read of `account_invoices` and before any write.
  - Error-precedence bugs whose outcome is the same 400 today (V2, the "draft invoice" side of P3) are caught by the statement recorder: no statement naming `account_invoices` (V-12, V-14) / no `UPDATE account_invoices` (P-06) before the refusal.
  - `Author: claude`: the manager-return patches (U-06, B-04, SB-02), the `invoice_amount` spy (I-31), the in-memory `account_id 0` (I-19). The failing-notification cards (U-08, AA-09, I-36) use the **failing notify(name)** convention and I-30 the `utcnow` patch, both with targets now stated by the spec (Facts, G2, G3), so they are no longer marked.
  - SE-06 … SE-09 drive the re-plan through `sheet_entry` with the manager's MSR-08 setup (a weekly template anchored 2–16 March re-placed with end 9 March drops the 16 March draft).
  - Invoices and accounts of W0 / W2 linked to a W1 order are invalid data built on purpose (HR-16, legacy).
  - Line order (SB-01, SB-04, GI-01) is compared as a set: `WorkOrderItemDAO.get_by_work_order` has no ORDER BY (BUG-1272, the manager's / DAO's, HR-7), so an order check would be flaky and a strict xfail would XPASS at random. The id order belongs to the manager's / DAO's cases.
- **Needs a decision:** None (gaps 1–6 of revision 1 and G7–G10 closed by the spec's gap log; Revision 4 opens none).

## Conventions for this module

**IDs.** `WOS` = `app/services/work_order_service.py`. `LE` _load_work_order_enrichment · `R` _to_work_order_response · `RS` _to_work_order_responses · `E` create_work_order · `T` create_work_order_from_template · `U` update_work_order · `G` get_work_order · `L` list_work_orders · `B` bulk_delete_future_recurrence_drafts · `SE` sheet_entry · `SB` list_sheet_bundles · `SD` sheet_daily_counts · `X` delete_work_order · `S` start_work_order · `C` complete_work_order · `P` complete_work_order_as_planned · `V` void_work_order · `I` create_invoice_for_work_order · `LA` list_approvers · `AS` approval_summary_for · `AA` add_approver · `RA` remove_approver · `AP` approve_as_me · `UA` unapprove_as_me · `N` list_events · `AI` add_item · `UI` update_item · `RI` remove_item · `GI` get_items.

**Imports.** `svc` = `work_order_service` (`from app.services.work_order_service import WorkOrderService, work_order_service, _WorkOrderEnrichment`); `dataclasses`. `WOM` = `svc.manager`. Models from `app.models.<snake_case>`: `WorkOrder`, `WorkOrderItem`, `WorkOrderApprover`, `WorkOrderAssignee`, `WorkOrderCompleter`, `WorkOrderEvent`, `WorkOrderTemplate`, `WorkOrderTemplateApprover`, `AccountInvoice`, `InvoiceItem`, `InvoiceEvent`, `InvoicePayment`, `Account`, `Notification`, `MachineActivityEvent`, `Inventory`, `InventoryLedger`, `WorkspaceMember`, `Workspace`. `WorkOrderPriorityEnum`, `MachineEventTypeEnum` from `app.models.enums`. Schemas: `WorkOrderCreate`, `WorkOrderUpdate`, `WorkOrderSheetEntryCreate` from `app.schemas.work_order`; `WorkOrderItemCreate`, `WorkOrderItemUpdate` from `app.schemas.work_order_item`; `WorkOrderFromTemplateCreate` from `app.schemas.work_order_template`. `HTTPException` (fastapi), `inspect`, `select`, `func` (sqlalchemy), `patch` (unittest.mock), `Decimal`, `date`, `datetime`, `uuid`. Every call: `db` first, the rest by keyword. `result` = what the When returns. Response classes are checked by name: `type(result).__name__ == "…"`.

**Fixed values.** MISSING = `999999999`. TAG = `uuid.uuid4().hex[:8]`, once per test. NOW = `datetime(2026, 3, 10, 9, 0, 0)`; T0 = `datetime(2026, 1, 5, 8, 0, 0)`; T1 = `datetime(2026, 3, 1, 8, 0, 0)`; D(n) = `date(2026, 3, n)`; NOON(n) = `datetime(2026, 3, n, 12, 0, 0)`. Long dashes are U+2014; copy them. NF(i) = `f"Work order with ID {i} not found"`. INPROG = `"Work order must be in progress before it can be completed"`. NOTDRAFT = `"Work order must be in draft to complete as planned"`. NOINV = `"No invoice linked — create an invoice for this external work before completing"`. INVNF = `"Linked invoice not found"`. VOIDINV = `"Linked invoice was voided — cannot complete this order"`. NOLINES = `"Add at least one line item before confirming"`. FINAL = `"This order's invoice is already finalized. Void the invoice on the invoice page first, then void the order."`. PAYHIST = `"Invoice has payment history — confirm and void it instead"`. EXISTS = `"Invoice already exists for this work order"`. NOACC = `"Set an account on the work order before creating an invoice"`. NOCOST = `"Set the work order's cost before creating an invoice"`. ACC404 = `"Cannot create invoice: selected account was not found in this workspace"`. CONFDEL = `"This work order has a confirmed invoice — void the invoice first"`. BULKCONF(O) = `f"Work order {O.work_order_number} has a confirmed invoice — void the invoice first"`. RESETMSG = `"Approvals were reset — order details changed; re-approve when ready"`. DRAFTP = `"draft|Linked payable invoice is in draft — confirm when details look correct"`. CONFP(O) = `f"confirmed|Invoice confirmed on WO-{O.id} — order locked"`. NOTMEMBER = `"User is not an active member of this workspace"`. STARTED = `"Work has started — approvals can no longer change"`.

**Time.** Every test patches `app.managers.work_order_manager.utcnow` to return NOW (tz-awareness of the real `app.utils.time.utcnow`). Nothing else is mocked unless a card says so.

**Standing rows** (every test, no Given line, built and flushed in this order, so in each table W0's rows have lower ids than W1's and W1's lower than W2's):
1. W0, W1, W2 = `make_workspace(db)` ×3. U1 `"Karim Ahmed"`, U2 `"Rahim Uddin"`, U3 `"Sara Khan"`, U4 `"Omar Faruk"`, U5 `"Nadia Islam"` = `make_profile(db, name=…)`.
2. `WorkspaceMember(workspace_id, user_id, role, status, position)`: (W1, U1, `"manager"`, `"active"`, `"Supervisor"`), (W1, U2, `"member"`, `"active"`, None), (W1, U3, `"member"`, `"active"`, None), (W1, U4, `"member"`, `"suspended"`, `"Fitter"`), (W0, U5, `"manager"`, `"active"`, None), (W2, U5, `"manager"`, `"active"`, None). U1 creates every Given row; **U2 is the acting user**.
3. `WorkOrderType(workspace_id, name)`: WT0 (W0, `"Service"`), WT1 (W1, `"Service"`), WT9 (W2, `"Service"`). `Factory(workspace_id, name, abbreviation)`: F0 (W0, `"Plant Zero"`, `"P0"`), F1 (W1, `"Plant One"`, `"P1"`), F9 (W2, `"Plant Nine"`, `"P9"`). `Machine(workspace_id, factory_id, name)`: M0 (W0, F0, `"Press"`), M1 (W1, F1, `"Lathe 3"`), M2 (W1, F1, `"Lathe 4"`), M9 (W2, F9, `"Press"`).
4. `Item(workspace_id, name, name_normalized, unit="pcs")`: I1 (W1, `"Bolt"`), I2 (W1, `"Bearing"`); `name_normalized` = name lower-cased.
5. `Account(workspace_id, name, is_active=True, is_deleted=False, allow_invoices=True)`: A0 (W0), A1 (W1), A9 (W2), all `"Karim Engineering"`.

**NOT NULL (Facts Constraints).** `work_orders.work_order_type_id`, `factory_id` and `title` are NOT NULL: no card builds an order without them. A "not ready for approval" order is built with `title "   "`.

**Given rows.** Inserted directly (never through `svc`), flushed one at a time in the order written. After "but", a line lists every column that differs.
- **order N** = `WorkOrder(workspace_id=W1.id, work_order_number=f"WO-{TAG}-N", work_order_type_id=WT1.id, title="Service — Lathe 3", factory_id=F1.id, machine_id=M1.id, status="DRAFT", priority=WorkOrderPriorityEnum.MEDIUM, uses_inventory=False, description="Old desc", cost=Decimal("100.00"), planned_date=D(12), created_by=U1.id, approved_by=U1.id, approved_at=T0)`; `account_id`, `invoice_id`, `end_date`, `started_*`, `completed_*`, `voided_*`, `work_order_template_id` NULL. NUM(O) = `O.work_order_number`. **outside** = `account_id A1.id`. **started** = `status "IN_PROGRESS"`, `started_by U1.id`, `started_at T1`, `planned_date D(1)`. **completed** = started, plus `status "COMPLETED"`, `completed_at T1`, `completed_by U1.id`. **voided** = `status "VOIDED"`, `voided_at T1`, `voided_by U1.id`, `void_note "Old"`. **gone** = `is_deleted True`, `is_active False`, `deleted_at T0`, `deleted_by U1.id`. **of W0** / **of W2** = `workspace_id`, `work_order_type_id`, `factory_id`, `machine_id` W0 / WT0 / F0 / M0 or W2 / WT9 / F9 / M9 (`account_id` A0 / A9 when outside).
- **inv(O)** = `AccountInvoice(workspace_id=W1.id, account_id=A1.id, invoice_type="payable", invoice_status="draft", payment_status="unpaid", invoice_amount=Decimal("100.00"), paid_amount=Decimal("0.00"), invoice_date=date(2026, 3, 1), allow_payments=True, receiving_started=False, created_by=U1.id, order_type="work_order", order_id=O.id)`. **confirmed** = `invoice_status "confirmed"`. **voided-inv** = `invoice_status "voided"`, `void_note "dup"`. **of W0** / **of W2** = `workspace_id` W0 / W2, `account_id` A0 / A9. **linked** = after its flush, `O.invoice_id = V.id`, then `db.flush()`.
- **invl(V, "s")** = `InvoiceItem(workspace_id=V.workspace_id, invoice_id=V.id, line_number=1, description="Old line", quantity=Decimal("1"), unit_price=Decimal(s), line_subtotal=Decimal(s), created_by=U1.id)`. **pay(V, "a")** = `InvoicePayment(workspace_id=V.workspace_id, invoice_id=V.id, payment_amount=Decimal(a), payment_date=date(2026, 3, 1), is_voided=True, voided_at=T0, voided_by=U1.id, void_note="manual void", created_by=U1.id)`.
- **approver(O, U)** = `WorkOrderApprover(workspace_id=W1.id, work_order_id=O.id, user_id=U.id, assigned_by=U1.id, assigned_at=T0, approved=False)`; **approved** = `approved True`, `approved_at T0`. **assignee(O, U)** = `WorkOrderAssignee(workspace_id=W1.id, work_order_id=O.id, user_id=U.id)`. **completer(O, U)** = `WorkOrderCompleter(workspace_id=W1.id, work_order_id=O.id, user_id=U.id)`. For both, **of W0** / **of W2** = `workspace_id` W0 / W2.
- **line(O, I, "q")** = `WorkOrderItem(workspace_id=W1.id, work_order_id=O.id, item_id=I.id, quantity=Decimal(q), uses_inventory=True, source_location_type="storage", source_location_id=F1.id, action_type="CONSUME", created_by=U1.id)`; **gone** = `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`. **S(I, q, p)** = a STORAGE bucket of F1 exactly as `inventory_movements.cases.md` S(): one `Inventory` row (W1, qty q, avg_price p) plus one opening `InventoryLedger` row (`qty_after q`, `avg_price_after p`, `performed_at T0`).
- **status row(M, "S", at)** = `MachineActivityEvent(workspace_id=W1.id, machine_id=M.id, event_type="status_updated", description="Setup", metadata_json={"status": "S"}, created_at=at)`. **event(O, "t", meta, at)** = `WorkOrderEvent(workspace_id=W1.id, work_order_id=O.id, event_type="t", description="Setup", metadata_json=meta, created_at=at)`. **ran** (a started order) = status row(M1, "RUNNING", T0), status row(M1, "MAINTENANCE", T1), event(O, "started", {"previous_machine_status": "RUNNING"}, T1).
- **template** = `WorkOrderTemplate(workspace_id=W1.id, template_name="Oil change", work_order_type_id=WT1.id, uses_inventory=False, requires_approval=False, is_active=True, created_by=U1.id)`; **weekly** = `is_recurring True`, `recurrence_type "weekly"`, `recurrence_day 0`. **tapprover(T, U)** = `WorkOrderTemplateApprover(workspace_id=W1.id, work_order_template_id=T.id, user_id=U.id)`.
- **commit point** = after the last Given line, `db.commit()` (a savepoint release under the `db` fixture); snapshots for `unchanged` / `nothing written` and **mark** are taken here. **X** (only where listed) = `X = make_workspace(db)` after the commit point, flushed, not committed; `X_ID = X.id`. A flushed X is persistent, never in `db.new`: read cards check `X in db` (a rollback would expunge it).

**Requests.** `CR(**k)` = `WorkOrderCreate(**{"work_order_type_id": WT1.id, "factory_id": F1.id, "machine_id": M1.id, **k})`. `SHEET(**k)` = `WorkOrderSheetEntryCreate(**{"machine_id": M1.id, "work_order_type_id": WT1.id, "planned_date": D(12), **k})`. `ITEM(O, **k)` = `WorkOrderItemCreate(**{"work_order_id": O.id, "item_id": I1.id, "quantity": Decimal("2"), "uses_inventory": True, "source_location_type": "storage", "source_location_id": F1.id, **k})`.

**Named checks.**
- **re-read R** = `db.expire_all()`, then `db.get(type(R), R.id)`. **unchanged(R)** = after re-read, every column equals its commit-point snapshot. **gone(R)** = after `db.expire_all()`, `db.get(type(R), R_ID) is None` (`R_ID` taken before the call). **x_gone** = `db.get(Workspace, X_ID) is None`. **X not in db** (TC3, Revision 4) = the `session:` line every error card with X carries right after the raise, before any re-read and before the test's own rollback; `x_gone` alone runs after that rollback (a savepoint rollback that drops X anyway) and cannot show the service rolled back. One passing error card per write method (never its failing-commit card, whose own rollback would satisfy the spy) also runs inside **spies** and checks `rb.call_count >= 1`.
- **mark** = the highest id of `work_order_events` and of `machine_activity_events` at the commit point (0 when empty). **ev(O)** = `[(e.event_type, e.description) …]` of `WorkOrderEvent` rows of O with `id > mark`, by id; **evrow(O, "t")** = the one such row with that type. **stat(M)** = `[a.metadata_json["status"] …]` of `MachineActivityEvent` rows of M, `event_type "status_updated"`, `id > mark`, by id. **itypes(V)** = `event_type` list of the `invoice_events` of invoice id V, by id. **LINES(V)** = the `invoice_items` of invoice id V by `line_number`.
- **notes()** = after `db.expire_all()`, all `Notification` rows by id; **recips()** = `sorted(n.recipient_user_id for n in notes())`.
- **nothing written** = the row counts (all workspaces) of `work_orders`, `work_order_items`, `work_order_approvers`, `work_order_completers`, `work_order_events`, `account_invoices`, `invoice_items`, `invoice_events`, `invoice_payments`, `notifications`, `machine_activity_events`, `inventory` (model `Inventory`; the table is `inventory`, Facts Constraints), `inventory_ledger` equal their commit-point values.
- **session clean** = right after the raise, before any re-read: `not db.new`, `not db.dirty`, `not db.deleted` (three asserts).
- **loaded(r)** = `inspect(r).expired_attributes.isdisjoint({c.key for c in inspect(type(r)).column_attrs})`; runs before any attribute of `r` is read.
- `committed:` lines: before the first one the test runs `db.rollback()` once; each line then re-reads with a fresh query.
- `raises: <Type>` = plain `with pytest.raises(<Type>) as exc:` around the call, no savepoint (the service rolls back itself).
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = the same with `patch.object(db, "refresh", side_effect=RuntimeError("boom"))`. **failing notify(name)** = the same with `patch(f"app.services.work_order_service.{name}", side_effect=RuntimeError("boom"))`.
- **Statement recorder** = a `before_cursor_execute` listener records every SQL statement sent during the When only; a recorder card ends its Given with `db.expunge_all()` after the commit point (ids taken before). **lock(work_orders)** = the first recorded `SELECT` whose `FROM` names `work_orders` ends (after trailing whitespace) with `FOR UPDATE` or `FOR UPDATE OF work_orders` — regex `FOR UPDATE( OF work_orders)?\s*$` (Facts L1) — so `NOWAIT`, `SKIP LOCKED`, `OF` another table, `FOR SHARE`, `FOR NO KEY UPDATE` do not count. **lock first** = that statement is sent before the first recorded statement naming `account_invoices` and before the first recorded `INSERT` / `UPDATE` / `DELETE`. **names(t)** = the recorded statements whose text contains table name t.

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`. Write the call and checks as shown, also when a behaviour does not exist yet. **Race simulations:** none.

## `WorkOrderService._load_work_order_enrichment`

### WOS-LE-01 — an empty list gives three empty maps and reads nothing
- **Rules:** `_load_work_order_enrichment` W1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.
2. Statement recorder on (after the commit point).

**When**
- `result = svc._load_work_order_enrichment(db, orders=[])`.

**Then**
1. returns: `result.assignee_map == {}`, `result.completer_map == {}`, `result.profile_names == {}`.
2. statement: no statement was recorded.

### WOS-LE-02 — every order gets an assignee key, ids in row order, [] without assignees
- **Rules:** `_load_work_order_enrichment` W2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = order "1".
2. O2 = order "2".
3. assignee(O1, U3).
4. assignee(O1, U2).

**When**
- `result = svc._load_work_order_enrichment(db, orders=[O1, O2])`.

**Then**
1. returns: `result.assignee_map == {O1.id: [U3.id, U2.id], O2.id: []}`.

### WOS-LE-03 — an assignee row of W2 on a W1 order is not read
- **Rules:** `_load_work_order_enrichment` W2; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O1 = order "1".
2. assignee(O1, U2).
3. assignee(O1, U5), but of W2.

**When**
- `result = svc._load_work_order_enrichment(db, orders=[O1])`.

**Then**
1. returns: `result.assignee_map == {O1.id: [U2.id]}`.

### WOS-LE-04 — an assignee row of W0 on a W1 order is not read
- **Rules:** `_load_work_order_enrichment` W2; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O1 = order "1".
2. assignee(O1, U5), but of W0.
3. assignee(O1, U3).

**When**
- `result = svc._load_work_order_enrichment(db, orders=[O1])`.

**Then**
1. returns: `result.assignee_map == {O1.id: [U3.id]}`.

### WOS-LE-05 — orders of two workspaces are each read with their own workspace
- **Rules:** `_load_work_order_enrichment` W2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O1 = order "1".
2. O9 = order "9", but of W2.
3. assignee(O1, U2).
4. assignee(O9, U5), but of W2.

**When**
- `result = svc._load_work_order_enrichment(db, orders=[O1, O9])`.

**Then**
1. returns: `result.assignee_map == {O1.id: [U2.id], O9.id: [U5.id]}`.

### WOS-LE-06 — completers are mapped the same way
- **Rules:** `_load_work_order_enrichment` W3
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = order "1", but completed.
2. O2 = order "2".
3. completer(O1, U3).
4. completer(O1, U2).

**When**
- `result = svc._load_work_order_enrichment(db, orders=[O1, O2])`.

**Then**
1. returns: `result.completer_map == {O1.id: [U3.id, U2.id], O2.id: []}`.

### WOS-LE-07 — a completer row of W2 on a W1 order is not read
- **Rules:** `_load_work_order_enrichment` W3; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O1 = order "1", but completed.
2. completer(O1, U5), but of W2.
3. completer(O1, U3).

**When**
- `result = svc._load_work_order_enrichment(db, orders=[O1])`.

**Then**
1. returns: `result.completer_map == {O1.id: [U3.id]}`.

### WOS-LE-08 — names of the starter and of the completer when no names text is stored
- **Rules:** `_load_work_order_enrichment` W4
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = order "1", but completed, `started_by U2.id`, `completed_by U3.id`, `completed_by_names None`.

**When**
- `result = svc._load_work_order_enrichment(db, orders=[O1])`.

**Then**
1. returns: `result.profile_names == {U2.id: "Rahim Uddin", U3.id: "Sara Khan"}`.

### WOS-LE-09 — a stored names text skips the completer's profile
- **Rules:** `_load_work_order_enrichment` W4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = order "1", but completed, `started_by U2.id`, `completed_by U3.id`, `completed_by_names "Crew A"`.

**When**
- `result = svc._load_work_order_enrichment(db, orders=[O1])`.

**Then**
1. returns: `result.profile_names == {U2.id: "Rahim Uddin"}`.

### WOS-LE-10 — an empty names text reads the completer's profile
- **Rules:** `_load_work_order_enrichment` W4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = order "1", but completed, `started_by None`, `completed_by U3.id`, `completed_by_names ""`.

**When**
- `result = svc._load_work_order_enrichment(db, orders=[O1])`.

**Then**
1. returns: `result.profile_names == {U3.id: "Sara Khan"}`.

### WOS-LE-11 — an id without a profile row is absent from the names
- **Rules:** `_load_work_order_enrichment` W4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = order "1", but started, `started_by U2.id`.
2. After the commit point: `O1.started_by = MISSING` in memory only (not flushed).

**When**
- `result = svc._load_work_order_enrichment(db, orders=[O1])`.

**Then**
1. returns: `result.profile_names == {}`.

### WOS-LE-12 — no starter and no completer: no profile is read
- **Rules:** `_load_work_order_enrichment` W4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = order "1".
2. Statement recorder on (after the commit point).

**When**
- `result = svc._load_work_order_enrichment(db, orders=[O1])`.

**Then**
1. returns: `result.profile_names == {}`.
2. statement: `names("profiles") == []`.

### WOS-LE-13 — the enrichment neither commits nor rolls back
- **Rules:** `_load_work_order_enrichment` (reads); TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O1 = order "1".
2. assignee(O1, U2).
3. X.

**When**
- spies: `result = svc._load_work_order_enrichment(db, orders=[O1])`.

**Then**
1. returns: `result.assignee_map == {O1.id: [U2.id]}`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.

### WOS-LE-14 — the enrichment is a frozen dataclass with its three fields in order
- **Rules:** Facts G4 (`_WorkOrderEnrichment`)
- **Kind:** happy
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.

**When**
- `e = _WorkOrderEnrichment(assignee_map={}, completer_map={}, profile_names={})` (import: `from app.services.work_order_service import _WorkOrderEnrichment`; `import dataclasses`).

**Then**
1. returns: `[f.name for f in dataclasses.fields(_WorkOrderEnrichment)] == ["assignee_map", "completer_map", "profile_names"]`.
2. raises: `with pytest.raises(dataclasses.FrozenInstanceError): e.assignee_map = {1: [2]}`.
3. returns: `e.assignee_map == {}` (unchanged after the refused assignment).
4. returns: `_WorkOrderEnrichment({}, {}, {}) == e` (positional construction gives an equal value).

## `WorkOrderService._to_work_order_response`

### WOS-R-01 — without an enrichment the order's own lists are loaded
- **Rules:** `_to_work_order_response` W5, W7
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but completed.
2. assignee(O, U2).
3. completer(O, U3).

**When**
- `result = svc._to_work_order_response(db, O)`.

**Then**
1. returns: `type(result).__name__ == "WorkOrderResponse"`.
2. returns: `result.assignee_user_ids == [U2.id]`, `result.completer_user_ids == [U3.id]`.

### WOS-R-02 — columns are copied, with the type name and the planned date as calendar date
- **Rules:** `_to_work_order_response` W6
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but outside, `cost Decimal("750.50")`.

**When**
- `result = svc._to_work_order_response(db, O)`.

**Then**
1. returns: `result.id == O.id`, `result.work_order_number == NUM(O)`, `result.title == "Service — Lathe 3"`, `result.status == "DRAFT"`.
2. returns: `result.cost == Decimal("750.50")`, `result.account_id == A1.id`, `result.invoice_id is None`.
3. returns: `result.work_order_type_name == "Service"`.
4. returns: `result.calendar_date == D(12)`.

### WOS-R-03 — a soft-deleted type still gives its name
- **Rules:** `_to_work_order_response` W6
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. WTD = `WorkOrderType(workspace_id=W1.id, name="Retired service", is_deleted=True)`.
2. O = order "1", but `work_order_type_id WTD.id`.

**When**
- `result = svc._to_work_order_response(db, O)`.

**Then**
1. returns: `result.work_order_type_name == "Retired service"`.
2. returns: `result.work_order_type_id == WTD.id`.

### WOS-R-04 — without a planned date the calendar date is the day of creation
- **Rules:** `_to_work_order_response` W6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but `planned_date None`.
2. `CREATED = O.created_at` read after the commit point.

**When**
- `result = svc._to_work_order_response(db, O)`.

**Then**
1. returns: `result.calendar_date == CREATED.date()`.

### WOS-R-05 — a given enrichment is used and nothing is read for the lists
- **Rules:** `_to_work_order_response` W5, W7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1".
2. assignee(O, U2).
3. After the commit point: `ENR = _WorkOrderEnrichment(assignee_map={O.id: [U4.id]}, completer_map={O.id: [U3.id]}, profile_names={})` (`from app.services.work_order_service import _WorkOrderEnrichment`; fields per the spec's Facts).
4. Statement recorder on.

**When**
- `result = svc._to_work_order_response(db, O, enrichment=ENR)`.

**Then**
1. returns: `result.assignee_user_ids == [U4.id]`.
2. returns: `result.completer_user_ids == [U3.id]`.
3. statement: `names("work_order_assignees") == []`.

### WOS-R-06 — an order missing from the maps gets empty lists
- **Rules:** `_to_work_order_response` W7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1".
2. assignee(O, U2).
3. After the commit point: `ENR = _WorkOrderEnrichment(assignee_map={}, completer_map={}, profile_names={})`.

**When**
- `result = svc._to_work_order_response(db, O, enrichment=ENR)`.

**Then**
1. returns: `result.assignee_user_ids == []`, `result.completer_user_ids == []`.

### WOS-R-07 — a started order shows the starter's name
- **Rules:** `_to_work_order_response` W8
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but started, `started_by U2.id`.

**When**
- `result = svc._to_work_order_response(db, O)`.

**Then**
1. returns: `result.started_by_name == "Rahim Uddin"`.

### WOS-R-08 — an order not started has no starter name
- **Rules:** `_to_work_order_response` W8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1".

**When**
- `result = svc._to_work_order_response(db, O)`.

**Then**
1. returns: `result.started_by_name is None`.

### WOS-R-09 — a starter without a profile row gives None
- **Rules:** `_to_work_order_response` W8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started, `started_by U2.id`.
2. After the commit point: `O.started_by = MISSING` in memory only.

**When**
- `result = svc._to_work_order_response(db, O)`.

**Then**
1. returns: `result.started_by_name is None`.

### WOS-R-10 — a stored names text wins over the completer's profile
- **Rules:** `_to_work_order_response` W9
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but completed, `completed_by U3.id`, `completed_by_names "Crew A"`.

**When**
- `result = svc._to_work_order_response(db, O)`.

**Then**
1. returns: `result.completed_by_name == "Crew A"`.
2. returns: `result.completed_by_names == "Crew A"`.

### WOS-R-11 — an empty names text falls back to the completer's profile; the text is copied as stored
- **Rules:** `_to_work_order_response` W9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but completed, `completed_by U3.id`, `completed_by_names ""`.

**When**
- `result = svc._to_work_order_response(db, O)`.

**Then**
1. returns: `result.completed_by_name == "Sara Khan"`.
2. returns: `result.completed_by_names == ""`.

### WOS-R-12 — no names text and no completer: None
- **Rules:** `_to_work_order_response` W9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but completed, `completed_by None`, `completed_by_names None`.

**When**
- `result = svc._to_work_order_response(db, O)`.

**Then**
1. returns: `result.completed_by_name is None`.

### WOS-R-13 — a completer without a profile row gives None
- **Rules:** `_to_work_order_response` W9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but completed, `completed_by U3.id`, `completed_by_names None`.
2. After the commit point: `O.completed_by = MISSING` in memory only.

**When**
- `result = svc._to_work_order_response(db, O)`.

**Then**
1. returns: `result.completed_by_name is None`.

### WOS-R-14 — mapping writes nothing, commits nothing, rolls nothing back
- **Rules:** `_to_work_order_response` W10; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but started, `started_by U2.id`.
2. X.

**When**
- spies: `result = svc._to_work_order_response(db, O)`.

**Then**
1. returns: `result.id == O.id`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`, `not db.new`.
5. session: `not db.dirty`, `not db.deleted`.

## `WorkOrderService._to_work_order_responses`

### WOS-RS-01 — an empty list gives [] and reads nothing
- **Rules:** `_to_work_order_responses` W11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No rows beyond the standing rows.
2. Statement recorder on (after the commit point).

**When**
- `result = svc._to_work_order_responses(db, orders=[])`.

**Then**
1. returns: `result == []`.
2. statement: no statement was recorded.

### WOS-RS-02 — orders are mapped in the given order from one enrichment
- **Rules:** `_to_work_order_responses` W12
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = order "1".
2. O2 = order "2".
3. O3 = order "3".
4. assignee(O1, U2).
5. assignee(O3, U3).
6. Statement recorder on (after the commit point).

**When**
- `result = svc._to_work_order_responses(db, orders=[O3, O1, O2])`.

**Then**
1. returns: `[r.id for r in result] == [O3.id, O1.id, O2.id]`.
2. returns: `[r.assignee_user_ids for r in result] == [[U3.id], [U2.id], []]`.
3. statement: `len([s for s in names("work_order_assignees") if s.lstrip().upper().startswith("SELECT")]) == 1`.

### WOS-RS-03 — the batch mapping neither commits nor rolls back
- **Rules:** `_to_work_order_responses` W12; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O1 = order "1".
2. X.

**When**
- spies: `result = svc._to_work_order_responses(db, orders=[O1])`.

**Then**
1. returns: `[r.id for r in result] == [O1.id]`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.

## `WorkOrderService.create_work_order`

### WOS-E-01 — a new order is committed and returned re-read; no invoice and no notification even with account and cost
- **Rules:** `create_work_order` E1, E2; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no work orders.

**When**
- `result = svc.create_work_order(db, wo_in=CR(account_id=A1.id, cost=Decimal("500.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `isinstance(result, WorkOrder)`, `result.id is not None`.
3. committed: the `work_orders` row with `id == result.id` has `workspace_id == W1.id`, `account_id == A1.id`, `cost == Decimal("500.00")`, `created_by == U2.id`, `invoice_id is None`.
4. committed: `account_invoices` rows with `order_type == "work_order"` and `order_id == result.id`: exactly 0.
5. committed: `notes() == []`.

### WOS-E-02 — the manager's 404 passes unchanged and the uncommitted extra row is gone
- **Rules:** `create_work_order` E1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no work orders.
2. X.

**When**
- `svc.create_work_order(db, wo_in=CR(factory_id=F9.id, machine_id=None), workspace_id=W1.id, user_id=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {F9.id} not found"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. session: session clean.
7. nothing written: nothing written.
8. committed: x_gone.

### WOS-E-03 — a failing commit is rolled back and re-raised; no order saved
- **Rules:** `create_work_order` E1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no work orders.

**When**
- `svc.create_work_order(db, wo_in=CR(), workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: W1 has exactly 0 `work_orders` rows.
4. nothing written: nothing written.

### WOS-E-04 — a failing re-read after the commit leaves the order saved
- **Rules:** `create_work_order` E1; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no work orders.

**When**
- `svc.create_work_order(db, wo_in=CR(description="Belt check"), workspace_id=W1.id, user_id=U2.id)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: W1 has exactly 1 `work_orders` row.
3. committed: that row has `description == "Belt check"`, `created_by == U2.id`.

## `WorkOrderService.create_work_order_from_template`

### WOS-T-01 — the order is committed; no invoice even with the template's account and cost
- **Rules:** `create_work_order_from_template` T1, T2; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, but `account_id A1.id`, `cost Decimal("300.00")`.

**When**
- `result = svc.create_work_order_from_template(db, template_id=T.id, overrides=WorkOrderFromTemplateCreate(machine_id=M1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id is not None`.
3. committed: the `work_orders` row with `id == result.id` has `work_order_template_id == T.id`, `account_id == A1.id`, `cost == Decimal("300.00")`, `invoice_id is None`.
4. committed: `account_invoices` rows with `order_id == result.id`: exactly 0.

### WOS-T-02 — approvers copied from the template are not notified
- **Rules:** `create_work_order_from_template` T2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template, but `requires_approval True`.
2. tapprover(T, U3).

**When**
- `result = svc.create_work_order_from_template(db, template_id=T.id, overrides=WorkOrderFromTemplateCreate(machine_id=M1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. committed: `[a.user_id for a in WorkOrderApprover rows with work_order_id == result.id] == [U3.id]`.
3. committed: `notes() == []`.

### WOS-T-03 — an inactive template: the manager's 400, the extra row is gone
- **Rules:** `create_work_order_from_template` T1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template, but `is_active False`.
2. X.

**When**
- `svc.create_work_order_from_template(db, template_id=T.id, overrides=WorkOrderFromTemplateCreate(machine_id=M1.id), workspace_id=W1.id, user_id=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Template is inactive"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. nothing written: nothing written.
7. committed: x_gone.

### WOS-T-04 — a failing commit leaves no order
- **Rules:** `create_work_order_from_template` T1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template.

**When**
- `svc.create_work_order_from_template(db, template_id=T.id, overrides=WorkOrderFromTemplateCreate(machine_id=M1.id), workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `work_orders` with `work_order_template_id == T.id`: exactly 0.

## `WorkOrderService.update_work_order`

### WOS-U-01 — an edit without recorded approvals is committed; no notification
- **Rules:** `update_work_order` U1, U3; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1".
2. approver(O, U3).

**When**
- `result = svc.update_work_order(db, wo_id=O.id, wo_in=WorkOrderUpdate(description="New desc"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == O.id`.
3. committed: re-read O: `description == "New desc"`.
4. committed: `notes() == []`.

### WOS-U-02 — an edit that clears approvals tells the creator once, not the approvers
- **Rules:** `update_work_order` U2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1".
2. approver(O, U3), but approved.

**When**
- `result = svc.update_work_order(db, wo_id=O.id, wo_in=WorkOrderUpdate(description="New desc"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. committed: `len(notes()) == 1`.
3. committed: `notes()[0].recipient_user_id == U1.id`, `notes()[0].notification_type == "section_confirm"`.
4. committed: `notes()[0].entity_type == "work_order"`, `notes()[0].entity_id == O.id`.
5. committed: `notes()[0].source_type == "section"`, `notes()[0].source_id == O.id`.
6. committed: `notes()[0].preview == RESETMSG`.

### WOS-U-03 — the creator is told also when the creator made the edit
- **Rules:** `update_work_order` U2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1".
2. approver(O, U3), but approved.

**When**
- `result = svc.update_work_order(db, wo_id=O.id, wo_in=WorkOrderUpdate(description="New desc"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == O.id`.
2. committed: `recips() == [U1.id]`.
3. committed: `notes()[0].preview == RESETMSG`.

### WOS-U-04 — a creator who is not an active member gets no notice
- **Rules:** `update_work_order` U2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but `created_by U4.id`.
2. approver(O, U3), but approved.

**When**
- `result = svc.update_work_order(db, wo_id=O.id, wo_in=WorkOrderUpdate(description="New desc"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. committed: `notes() == []`.
3. committed: re-read the approver row of U3: `approved is False`.

### WOS-U-05 — no creator: no notice
- **Rules:** `update_work_order` U2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but `created_by None`.
2. approver(O, U3), but approved.

**When**
- `result = svc.update_work_order(db, wo_id=O.id, wo_in=WorkOrderUpdate(description="New desc"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. committed: `notes() == []`.

### WOS-U-06 — a manager result without `_approvals_reset` sends nothing
- **Rules:** `update_work_order` U3
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. O = order "1".
2. approver(O, U3), but approved.

**When**
- `result = svc.update_work_order(db, wo_id=O.id, wo_in=WorkOrderUpdate(description="New desc"), workspace_id=W1.id, user_id=U2.id)`, with `patch.object(svc.manager, "update_work_order", return_value=O)` around it (O carries no `_approvals_reset` attribute).

**Then**
1. returns: `result.id == O.id`.
2. committed: `notes() == []`.

### WOS-U-07 — a linked draft invoice is not touched by an edit; the title in the edit is dropped
- **Rules:** `update_work_order` U4, U4a
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but outside.
2. V = inv(O), linked.
3. invl(V, "100.00").

**When**
- `result = svc.update_work_order(db, wo_id=O.id, wo_in=WorkOrderUpdate(title="Overhaul — Lathe 3", description="New desc", end_date=D(20)), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. committed: re-read O: `title == "Service — Lathe 3"` (unchanged, U4a), `description == "New desc"`, `end_date == D(20)`, `invoice_id == V.id`.
3. unchanged: unchanged(V).
4. committed: `[(i.description, i.unit_price) for i in LINES(V.id)] == [("Old line", Decimal("100.00"))]`.

### WOS-U-08 — a failing approvals-reset notice undoes the whole edit
- **Rules:** `update_work_order` U5; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1".
2. P3 = approver(O, U3), but approved.
3. X.

**When**
- `svc.update_work_order(db, wo_id=O.id, wo_in=WorkOrderUpdate(description="New desc"), workspace_id=W1.id, user_id=U2.id)`, inside **failing notify("notify_section_confirm_needed")**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
3. unchanged: unchanged(O).
4. unchanged: unchanged(P3).
5. nothing written: nothing written.
6. committed: x_gone.

### WOS-U-09 — the manager's 400 for a voided order passes unchanged; the extra row is gone
- **Rules:** `update_work_order` U1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but voided.
2. X.

**When**
- `svc.update_work_order(db, wo_id=O.id, wo_in=WorkOrderUpdate(description="New desc"), workspace_id=W1.id, user_id=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work order is voided and cannot be edited"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. unchanged: unchanged(O).
7. committed: x_gone.

### WOS-U-10 — another workspace's order (W2): 404, nothing changed
- **Rules:** `update_work_order` U1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = order "9", but of W2.

**When**
- `svc.update_work_order(db, wo_id=Z.id, wo_in=WorkOrderUpdate(description="New desc"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(Z.id)`.
4. unchanged: unchanged(Z).

### WOS-U-11 — a failing commit keeps the old description and sends nothing
- **Rules:** `update_work_order` U1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1".
2. approver(O, U3), but approved.

**When**
- `svc.update_work_order(db, wo_id=O.id, wo_in=WorkOrderUpdate(description="New desc"), workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read O: `description == "Old desc"`.
4. count: `notes() == []`.

## `WorkOrderService.get_work_order`

### WOS-G-01 — returns the order; neither commits nor rolls back; a pending row stays pending
- **Rules:** `get_work_order` G1; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1".
2. X.

**When**
- spies: `result = svc.get_work_order(db, wo_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, WorkOrder)`, `result.id == O.id`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.

### WOS-G-02 — a voided order is returned
- **Rules:** `get_work_order` G1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but voided.

**When**
- `result = svc.get_work_order(db, wo_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == O.id`, `result.status == "VOIDED"`.

### WOS-G-03 — a completed order is returned
- **Rules:** `get_work_order` G1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but completed.

**When**
- `result = svc.get_work_order(db, wo_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == O.id`, `result.status == "COMPLETED"`.

### WOS-G-04 — a W0 order (lower workspace id) gets the 404
- **Rules:** `get_work_order` G1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = order "0", but of W0.
2. O = order "1".

**When**
- `svc.get_work_order(db, wo_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(Z.id)`.

### WOS-G-05 — a W2 order (higher workspace id) gets the 404
- **Rules:** `get_work_order` G1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order "1".
2. Z = order "9", but of W2.

**When**
- `svc.get_work_order(db, wo_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(Z.id)`.

### WOS-G-06 — a 404 neither rolls back nor drops a pending row
- **Rules:** `get_work_order` G1; TC6
- **Kind:** error
- **Expect:** pass

**Given**
1. X.

**When**
- spies: `svc.get_work_order(db, wo_id=MISSING, workspace_id=W1.id)`, inside `pytest.raises(HTTPException) as exc`.

**Then**
1. raises: `exc.value.status_code == 404`, `exc.value.detail == NF(MISSING)`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.

### WOS-G-07 — a soft-deleted order gets the 404
- **Rules:** `get_work_order` G1 [BUG-1279] (manager pass-through)
- **Kind:** bug
- **Expect:** xfail BUG-1279
- **Fails today on:** Then 1 (no error: the deleted order is returned)

**Given**
1. O = order "1", but gone.

**When**
- `svc.get_work_order(db, wo_id=O.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(O.id)`.

## `WorkOrderService.list_work_orders`

### WOS-L-01 — returns the manager's list of W1 orders; W0 and W2 orders never appear; no commit, no rollback
- **Rules:** `list_work_orders` L1; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. Z0 = order "0", but of W0.
2. O1 = order "1".
3. O2 = order "2".
4. Z9 = order "9", but of W2.
5. X.

**When**
- spies: `result = svc.list_work_orders(db, workspace_id=W1.id)`.

**Then**
1. returns: `[o.id for o in result] == [o.id for o in WOM.list_work_orders(db, workspace_id=W1.id)]`.
2. returns: `{o.id for o in result} == {O1.id, O2.id}`.
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 0`.
5. session: `X in db`.

### WOS-L-02 — with no limit given, 101 orders give 100
- **Rules:** `list_work_orders` L1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 orders: order "k" for k = 1 … 101.

**When**
- `result = svc.list_work_orders(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

### WOS-L-03 — skip and limit=1000 are passed on
- **Rules:** `list_work_orders` L1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 3 orders: order "k" for k = 1 … 3.

**When**
- `result = svc.list_work_orders(db, workspace_id=W1.id, skip=1, limit=1000)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `[o.id for o in result] == [o.id for o in WOM.list_work_orders(db, workspace_id=W1.id, skip=1, limit=1000)]`.

### WOS-L-04 — the status filter is passed on
- **Rules:** `list_work_orders` L1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = order "1".
2. O2 = order "2", but started.

**When**
- `result = svc.list_work_orders(db, workspace_id=W1.id, wo_status="IN_PROGRESS")`.

**Then**
1. returns: `[o.id for o in result] == [O2.id]`.

### WOS-L-05 — the machine filter is passed on
- **Rules:** `list_work_orders` L1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = order "1".
2. O2 = order "2", but `machine_id M2.id`.

**When**
- `result = svc.list_work_orders(db, workspace_id=W1.id, machine_id=M2.id)`.

**Then**
1. returns: `[o.id for o in result] == [O2.id]`.

## `WorkOrderService.bulk_delete_future_recurrence_drafts`

### WOS-B-01 — future drafts are deleted and committed; the response lists them; nobody told
- **Rules:** `bulk_delete_future_recurrence_drafts` B1, B2, B4
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, but weekly.
2. A = order "a", but `work_order_template_id T.id`, `planned_date D(12)`.
3. B = order "b", but `work_order_template_id T.id`, `planned_date D(11)`.

**When**
- `result = svc.bulk_delete_future_recurrence_drafts(db, workspace_id=W1.id, user_id=U2.id, work_order_template_id=T.id, machine_id=M1.id, after_date=D(10))`.

**Then**
1. returns: `type(result).__name__ == "BulkDeleteFutureRecurrenceDraftsResponse"`.
2. returns: `result.deleted_ids == [B.id, A.id]`, `result.deleted_count == 2`.
3. committed: re-read A: `is_deleted is True`, `deleted_by == U2.id`.
4. committed: re-read B: `is_deleted is True`, `deleted_by == U2.id`.
5. committed: `notes() == []`.

### WOS-B-02 — nothing to delete: 0 and [], and the empty commit still happens
- **Rules:** `bulk_delete_future_recurrence_drafts` B2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but weekly.
2. ON = order "c", but `work_order_template_id T.id`, `planned_date D(10)`.

**When**
- spies: `result = svc.bulk_delete_future_recurrence_drafts(db, workspace_id=W1.id, user_id=U2.id, work_order_template_id=T.id, machine_id=M1.id, after_date=D(10))`.

**Then**
1. returns: `result.deleted_count == 0`, `result.deleted_ids == []`.
2. mock called: `cm.call_count == 1`.
3. unchanged: unchanged(ON).

### WOS-B-03 — a failing commit deletes nothing
- **Rules:** `bulk_delete_future_recurrence_drafts` B1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template, but weekly.
2. A = order "a", but `work_order_template_id T.id`, `planned_date D(12)`.

**When**
- `svc.bulk_delete_future_recurrence_drafts(db, workspace_id=W1.id, user_id=U2.id, work_order_template_id=T.id, machine_id=M1.id, after_date=D(10))`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read A: `is_deleted is False`.

### WOS-B-04 — an error from the manager rolls back and passes as the same object; the extra row is gone
- **Rules:** `bulk_delete_future_recurrence_drafts` B1; TC3
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. T = template, but weekly.
2. A = order "a", but `work_order_template_id T.id`, `planned_date D(12)`.
3. X.
4. `ERR = HTTPException(status_code=400, detail="x")`.

**When**
- `svc.bulk_delete_future_recurrence_drafts(db, workspace_id=W1.id, user_id=U2.id, work_order_template_id=T.id, machine_id=M1.id, after_date=D(10))`, with `patch.object(svc.manager, "bulk_delete_future_recurrence_drafts", side_effect=ERR)` around it, inside `pytest.raises(HTTPException) as exc`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `exc.value is ERR`.
2. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
3. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
4. re-read A: `is_deleted is False`.
5. committed: x_gone.

### WOS-B-05 — a deleted draft's draft invoice is deleted and unlinked, with an event
- **Rules:** `bulk_delete_future_recurrence_drafts` B3 [BUG-3227]
- **Kind:** bug
- **Expect:** xfail BUG-3227
- **Fails today on:** Then 3 (the draft invoice is kept)

**Given**
1. T = template, but weekly.
2. A = order "a", but outside, `work_order_template_id T.id`, `planned_date D(12)`.
3. V = inv(A), but `invoice_amount Decimal("3000.00")`, linked.
4. invl(V, "3000.00").
5. `V_ID = V.id`.

**When**
- `result = svc.bulk_delete_future_recurrence_drafts(db, workspace_id=W1.id, user_id=U2.id, work_order_template_id=T.id, machine_id=M1.id, after_date=D(10))`.

**Then**
1. returns: `result.deleted_ids == [A.id]`.
2. committed: re-read A: `is_deleted is True`.
3. committed: gone(V).
4. committed: re-read A: `invoice_id is None`.
5. committed: `invoice_items` rows with `invoice_id == V_ID`: exactly 0.
6. event: `ev(A) == [("invoice_voided", f"Invoice unlinked — work order {NUM(A)} deleted")]`.
7. event: `evrow(A, "invoice_voided").metadata_json == {"invoice_id": V_ID}`, `evrow(A, "invoice_voided").performed_by == U2.id`.

### WOS-B-06 — a draft with a linked draft invoice is still deleted (today and after the fix)
- **Rules:** `bulk_delete_future_recurrence_drafts` B1, B3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template, but weekly.
2. A = order "a", but outside, `work_order_template_id T.id`, `planned_date D(12)`.
3. V = inv(A), linked.

**When**
- `result = svc.bulk_delete_future_recurrence_drafts(db, workspace_id=W1.id, user_id=U2.id, work_order_template_id=T.id, machine_id=M1.id, after_date=D(10))`.

**Then**
1. returns: `result.deleted_ids == [A.id]`.
2. committed: re-read A: `is_deleted is True`, `deleted_by == U2.id`.

### WOS-B-07 — a confirmed invoice on one draft refuses the whole call; nothing deleted
- **Rules:** `bulk_delete_future_recurrence_drafts` B3 [BUG-3227]
- **Kind:** bug
- **Expect:** xfail BUG-3227
- **Fails today on:** Then 1 (no error: both drafts are deleted)

**Given**
1. T = template, but weekly.
2. B = order "b", but `work_order_template_id T.id`, `planned_date D(11)`.
3. A = order "a", but outside, `work_order_template_id T.id`, `planned_date D(12)`.
4. V = inv(A), but confirmed, linked.
5. X.

**When**
- `svc.bulk_delete_future_recurrence_drafts(db, workspace_id=W1.id, user_id=U2.id, work_order_template_id=T.id, machine_id=M1.id, after_date=D(10))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == BULKCONF(A)`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. unchanged: unchanged(A).
6. unchanged: unchanged(B).
7. unchanged: unchanged(V).
8. nothing written: nothing written.
9. committed: x_gone.

### WOS-B-08 — a confirmed invoice is never deleted or changed by the bulk delete (today and after the fix)
- **Rules:** `bulk_delete_future_recurrence_drafts` B3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template, but weekly.
2. A = order "a", but outside, `work_order_template_id T.id`, `planned_date D(12)`.
3. V = inv(A), but confirmed, linked.
4. pay(V, "50.00").

**When**
- `svc.bulk_delete_future_recurrence_drafts(db, workspace_id=W1.id, user_id=U2.id, work_order_template_id=T.id, machine_id=M1.id, after_date=D(10))`, wrapped in `try: … except HTTPException: pass`.

**Then**
1. unchanged: unchanged(V).
2. count: `invoice_payments` rows with `invoice_id == V.id`: exactly 1.

### WOS-B-09 — a voided invoice still linked refuses the call too
- **Rules:** `bulk_delete_future_recurrence_drafts` B3 [BUG-3227]
- **Kind:** bug
- **Expect:** xfail BUG-3227
- **Fails today on:** Then 1 (no error: the draft is deleted)

**Given**
1. T = template, but weekly.
2. A = order "a", but outside, `work_order_template_id T.id`, `planned_date D(12)`.
3. V = inv(A), but voided-inv, linked.

**When**
- `svc.bulk_delete_future_recurrence_drafts(db, workspace_id=W1.id, user_id=U2.id, work_order_template_id=T.id, machine_id=M1.id, after_date=D(10))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == BULKCONF(A)`.
4. unchanged: unchanged(A).
5. nothing written: nothing written.

### WOS-B-10 — two refusing drafts: the message names the first in planned-date order
- **Rules:** `bulk_delete_future_recurrence_drafts` B2, B3 [BUG-3227]
- **Kind:** bug
- **Expect:** xfail BUG-3227
- **Fails today on:** Then 1 (no error: both drafts are deleted)

**Given**
1. T = template, but weekly.
2. A = order "a", but outside, `work_order_template_id T.id`, `planned_date D(12)`.
3. VA = inv(A), but confirmed, linked.
4. B = order "b", but outside, `work_order_template_id T.id`, `planned_date D(11)`.
5. VB = inv(B), but confirmed, linked.

**When**
- `svc.bulk_delete_future_recurrence_drafts(db, workspace_id=W1.id, user_id=U2.id, work_order_template_id=T.id, machine_id=M1.id, after_date=D(10))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == BULKCONF(B)`.
3. unchanged: unchanged(A).
4. unchanged: unchanged(B).

### WOS-B-11 — an invoice of W2 linked to a draft is left alone; the draft is deleted
- **Rules:** `bulk_delete_future_recurrence_drafts` B1, B3 (gap log G5); HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template, but weekly.
2. A = order "a", but outside, `work_order_template_id T.id`, `planned_date D(12)`.
3. V = inv(A), but of W2, confirmed, linked.

**When**
- `result = svc.bulk_delete_future_recurrence_drafts(db, workspace_id=W1.id, user_id=U2.id, work_order_template_id=T.id, machine_id=M1.id, after_date=D(10))`.

**Then**
1. returns: `result.deleted_ids == [A.id]`.
2. committed: re-read A: `is_deleted is True`.
3. unchanged: unchanged(V).
4. committed: re-read A: `invoice_id == V.id`.
5. event: `[e for e in ev(A) if e[0] == "invoice_voided"] == []`.

### WOS-B-12 — a refused bulk call keeps the plain draft too
- **Rules:** `bulk_delete_future_recurrence_drafts` B3 [BUG-3227]; TC3
- **Kind:** bug
- **Expect:** xfail BUG-3227
- **Fails today on:** Then 1 (no error: the plain draft B is deleted and committed)

**Given**
1. T = template, but weekly.
2. B = order "b", but `work_order_template_id T.id`, `planned_date D(11)`.
3. A = order "a", but outside, `work_order_template_id T.id`, `planned_date D(12)`.
4. VA = inv(A), but voided-inv, linked.
5. X.

**When**
- `svc.bulk_delete_future_recurrence_drafts(db, workspace_id=W1.id, user_id=U2.id, work_order_template_id=T.id, machine_id=M1.id, after_date=D(10))`.

**Then**
1. raises: `HTTPException`.
2. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
3. committed: re-read B: `is_deleted is False`.
4. committed: x_gone.

### WOS-B-13 — a draft invoice of W0 linked to a draft is not deleted; the draft is deleted
- **Rules:** `bulk_delete_future_recurrence_drafts` B1, B3 (gap log G5); HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template, but weekly.
2. A = order "a", but outside, `work_order_template_id T.id`, `planned_date D(12)`.
3. V = inv(A), but of W0, linked.
4. invl(V, "100.00").

**When**
- `result = svc.bulk_delete_future_recurrence_drafts(db, workspace_id=W1.id, user_id=U2.id, work_order_template_id=T.id, machine_id=M1.id, after_date=D(10))`.

**Then**
1. returns: `result.deleted_ids == [A.id]`.
2. committed: re-read A: `is_deleted is True`.
3. committed: re-read A: `invoice_id == V.id`.
4. unchanged: unchanged(V).
5. committed: `[(i.description, i.unit_price) for i in LINES(V.id)] == [("Old line", Decimal("100.00"))]`.
6. event: `[e for e in ev(A) if e[0] == "invoice_voided"] == []`.

## `WorkOrderService.sheet_entry`

### WOS-SE-01 — an entry is committed and returned re-read; no invoice even with a cost
- **Rules:** `sheet_entry` SE1, SE2; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no work orders.

**When**
- `result = svc.sheet_entry(db, data=SHEET(cost=Decimal("300.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id is not None`.
3. committed: the `work_orders` row with `id == result.id` has `machine_id == M1.id`, `planned_date == D(12)`, `cost == Decimal("300.00")`, `invoice_id is None`.
4. committed: `account_invoices` rows with `order_id == result.id`: exactly 0.
5. committed: `notes() == []`.

### WOS-SE-02 — approvers named in the entry are not notified
- **Rules:** `sheet_entry` SE2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W1 has no work orders.

**When**
- `result = svc.sheet_entry(db, data=SHEET(approvers=[{"user_id": U3.id}]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. committed: `[a.user_id for a in WorkOrderApprover rows with work_order_id == result.id] == [U3.id]`.
3. committed: `notes() == []`.

### WOS-SE-03 — a machine of W2: the manager's 404, the extra row is gone
- **Rules:** `sheet_entry` SE1; TC3; HR-16
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no work orders.
2. X.

**When**
- `svc.sheet_entry(db, data=SHEET(machine_id=M9.id), workspace_id=W1.id, user_id=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Machine with ID {M9.id} not found"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. nothing written: nothing written.
7. committed: x_gone.

### WOS-SE-04 — a refusal from the recurrence step saves no order
- **Rules:** `sheet_entry` SE1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template, but weekly.
2. X.

**When**
- `svc.sheet_entry(db, data=SHEET(planned_date=D(2), template_id=T.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "recurrence_end_date is required when placing an unanchored recurring template"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. count: `work_orders` rows of W1: exactly 0.
6. unchanged: unchanged(T).
7. committed: x_gone.

### WOS-SE-05 — a failing commit saves no order
- **Rules:** `sheet_entry` SE1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no work orders.

**When**
- `svc.sheet_entry(db, data=SHEET(), workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `work_orders` rows of W1: exactly 0.

### WOS-SE-06 — a re-plan that drops a draft deletes and unlinks its draft invoice
- **Rules:** `sheet_entry` SE3 [BUG-3227]
- **Kind:** bug
- **Expect:** xfail BUG-3227
- **Fails today on:** Then 3 (the dropped draft's invoice is kept)

**Given**
1. T = template, but weekly, `recurrence_start_date D(2)`, `recurrence_end_date D(16)`, `next_generation_date D(23)`.
2. O9 = order "9", but `work_order_template_id T.id`, `planned_date D(9)`.
3. O16 = order "16", but outside, `work_order_template_id T.id`, `planned_date D(16)`.
4. V = inv(O16), linked.
5. invl(V, "100.00").
6. `V_ID = V.id`.

**When**
- `result = svc.sheet_entry(db, data=SHEET(planned_date=D(2), template_id=T.id, recurrence_end_date=D(9)), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. committed: re-read O16: `is_deleted is True`.
3. committed: gone(V).
4. committed: re-read O16: `invoice_id is None`.
5. event: `ev(O16) == [("invoice_voided", f"Invoice unlinked — work order {NUM(O16)} deleted")]`.
6. event: `evrow(O16, "invoice_voided").metadata_json == {"invoice_id": V_ID}`, `evrow(O16, "invoice_voided").performed_by == U2.id`.

### WOS-SE-07 — a re-plan still drops the draft that has a draft invoice (today and after the fix)
- **Rules:** `sheet_entry` SE1, SE3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template, but weekly, `recurrence_start_date D(2)`, `recurrence_end_date D(16)`, `next_generation_date D(23)`.
2. O9 = order "9", but `work_order_template_id T.id`, `planned_date D(9)`.
3. O16 = order "16", but outside, `work_order_template_id T.id`, `planned_date D(16)`.
4. V = inv(O16), linked.

**When**
- `result = svc.sheet_entry(db, data=SHEET(planned_date=D(2), template_id=T.id, recurrence_end_date=D(9)), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. committed: re-read O16: `is_deleted is True`, `deleted_by == U2.id`.
3. committed: re-read O9: `is_deleted is False`.

### WOS-SE-08 — a dropped draft with a confirmed invoice refuses the whole entry
- **Rules:** `sheet_entry` SE3 [BUG-3227]
- **Kind:** bug
- **Expect:** xfail BUG-3227
- **Fails today on:** Then 1 (no error: the entry is saved and O16 deleted)

**Given**
1. T = template, but weekly, `recurrence_start_date D(2)`, `recurrence_end_date D(16)`, `next_generation_date D(23)`.
2. O9 = order "9", but `work_order_template_id T.id`, `planned_date D(9)`.
3. O16 = order "16", but outside, `work_order_template_id T.id`, `planned_date D(16)`.
4. V = inv(O16), but confirmed, linked.
5. X.

**When**
- `svc.sheet_entry(db, data=SHEET(planned_date=D(2), template_id=T.id, recurrence_end_date=D(9)), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == BULKCONF(O16)`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. unchanged: unchanged(O16).
6. unchanged: unchanged(T).
7. unchanged: unchanged(V).
8. nothing written: nothing written.
9. committed: x_gone.

### WOS-SE-09 — a confirmed invoice is never changed by a re-plan (today and after the fix)
- **Rules:** `sheet_entry` SE3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template, but weekly, `recurrence_start_date D(2)`, `recurrence_end_date D(16)`, `next_generation_date D(23)`.
2. O16 = order "16", but outside, `work_order_template_id T.id`, `planned_date D(16)`.
3. V = inv(O16), but confirmed, linked.

**When**
- `svc.sheet_entry(db, data=SHEET(planned_date=D(2), template_id=T.id, recurrence_end_date=D(9)), workspace_id=W1.id, user_id=U2.id)`, wrapped in `try: … except HTTPException: pass`.

**Then**
1. unchanged: unchanged(V).

### WOS-SE-10 — a re-plan drops a draft whose linked invoice is of W2; the invoice is left alone
- **Rules:** `sheet_entry` SE1, SE3 (gap log G5); HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template, but weekly, `recurrence_start_date D(2)`, `recurrence_end_date D(16)`, `next_generation_date D(23)`.
2. O9 = order "9", but `work_order_template_id T.id`, `planned_date D(9)`.
3. O16 = order "16", but outside, `work_order_template_id T.id`, `planned_date D(16)`.
4. V = inv(O16), but of W2, confirmed, linked.

**When**
- `result = svc.sheet_entry(db, data=SHEET(planned_date=D(2), template_id=T.id, recurrence_end_date=D(9)), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. committed: re-read O16: `is_deleted is True`.
3. committed: re-read O16: `invoice_id == V.id`.
4. unchanged: unchanged(V).
5. event: `[e for e in ev(O16) if e[0] == "invoice_voided"] == []`.

## `WorkOrderService.list_sheet_bundles`

### WOS-SB-01 — one bundle per order with its mapped order, lines, approvers and summary
- **Rules:** `list_sheet_bundles` SB1, SB2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but `uses_inventory True`.
2. L1 = line(O, I1, "2").
3. L2 = line(O, I2, "1").
4. approver(O, U1), but approved, `approver_slot "QA"`.
5. assignee(O, U3).

**When**
- `result = svc.list_sheet_bundles(db, workspace_id=W1.id)`; then `b = result.items[0]`, `a = b.approvers.approvers[0]`, `s = b.approvers.summary`.

**Then**
1. returns: `type(result).__name__ == "WorkOrderSheetListResponse"`, `type(b.approvers).__name__ == "WorkOrderApproversList"`.
2. returns: `result.total == 1`, `len(result.items) == 1`.
3. returns: `b.order.id == O.id`, `b.order.assignee_user_ids == [U3.id]`.
4. returns: `{i.id for i in b.items} == {L1.id, L2.id}`, `len(b.items) == 2` (as a set: BUG-1272), `type(b.items[0]).__name__ == "WorkOrderItemResponse"`.
5. returns: `a.user_name == "Karim Ahmed"`, `a.user_email == U1.email`, `a.user_position == "Supervisor"`, `a.approver_slot == "QA"`.
6. returns: `a.approved is True`, `a.approved_at == T0`, `a.assigned_by == U1.id`, `a.assigned_at == T0`.
7. returns: `s.approved_count == 1`, `s.required == 1`, `s.met is True`.

### WOS-SB-02 — an approver without a profile shows no name or e-mail
- **Rules:** `list_sheet_bundles` SB2
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. O = order "1".
2. AP = approver(O, U2).

**When**
- `result = svc.list_sheet_bundles(db, workspace_id=W1.id)`, with `patch.object(svc.manager, "list_approvers", return_value=[(AP, None, None)])` around it; then `a = result.items[0].approvers.approvers[0]`.

**Then**
1. returns: `a.user_name is None`, `a.user_email is None`, `a.user_position is None`.
2. returns: `a.approved is False`.

### WOS-SB-03 — a member without a position shows None as position
- **Rules:** `list_sheet_bundles` SB2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1".
2. approver(O, U2).

**When**
- `result = svc.list_sheet_bundles(db, workspace_id=W1.id)`; then `a = result.items[0].approvers.approvers[0]`.

**Then**
1. returns: `a.user_name == "Rahim Uddin"`, `a.user_position is None`.

### WOS-SB-04 — only live lines are bundled
- **Rules:** `list_sheet_bundles` SB2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. O = order "1", but `uses_inventory True`.
2. L1 = line(O, I1, "1").
3. line(O, I2, "1"), but gone.
4. L3 = line(O, I1, "3").

**When**
- `result = svc.list_sheet_bundles(db, workspace_id=W1.id)`.

**Then**
1. returns: `{i.id for i in result.items[0].items} == {L1.id, L3.id}`, `len(result.items[0].items) == 2` (as a set: BUG-1272).

### WOS-SB-05 — 60 matching, default skip and limit: 50 items, echoed, has_more true
- **Rules:** `list_sheet_bundles` SB1, SB3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 60 orders: order "k" for k = 1 … 60.

**When**
- `result = svc.list_sheet_bundles(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.total == 60`, `len(result.items) == 50`.
2. returns: `result.skip == 0`, `result.limit == 50`.
3. returns: `result.has_more is True`.
4. returns: `[b.order.id for b in result.items] == [o.id for o in WOM.list_sheet_orders(db, workspace_id=W1.id, skip=0, limit=50)]`.

### WOS-SB-06 — skip 50 of 60: 10 items, has_more false
- **Rules:** `list_sheet_bundles` SB3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 60 orders: order "k" for k = 1 … 60.

**When**
- `result = svc.list_sheet_bundles(db, workspace_id=W1.id, skip=50, limit=50)`.

**Then**
1. returns: `result.total == 60`, `len(result.items) == 10`, `result.skip == 50`.
2. returns: `result.has_more is False`.

### WOS-SB-07 — skip 49 of 60 with limit 10: has_more true
- **Rules:** `list_sheet_bundles` SB3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 60 orders: order "k" for k = 1 … 60.

**When**
- `result = svc.list_sheet_bundles(db, workspace_id=W1.id, skip=49, limit=10)`.

**Then**
1. returns: `len(result.items) == 10`, `result.limit == 10`.
2. returns: `result.has_more is True`.

### WOS-SB-08 — skip beyond the total: no items, has_more false
- **Rules:** `list_sheet_bundles` SB3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 3 orders: order "k" for k = 1 … 3.

**When**
- `result = svc.list_sheet_bundles(db, workspace_id=W1.id, skip=70, limit=50)`.

**Then**
1. returns: `result.total == 3`, `result.items == []`, `result.skip == 70`.
2. returns: `result.has_more is False`.

### WOS-SB-09 — no match: total 0, no items, has_more false
- **Rules:** `list_sheet_bundles` SB1, SB3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1".

**When**
- `result = svc.list_sheet_bundles(db, workspace_id=W1.id, machine_id=M2.id)`.

**Then**
1. returns: `result.total == 0`, `result.items == []`.
2. returns: `result.has_more is False`.

### WOS-SB-10 — orders of W0 and W2 are neither counted nor listed
- **Rules:** `list_sheet_bundles` SB1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z0 = order "0", but of W0.
2. O = order "1".
3. Z9 = order "9", but of W2.

**When**
- `result = svc.list_sheet_bundles(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.total == 1`.
2. returns: `[b.order.id for b in result.items] == [O.id]`.

### WOS-SB-11 — one enrichment serves the whole page
- **Rules:** `list_sheet_bundles` SB2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. 3 orders: order "k" for k = 1 … 3.
2. Statement recorder on (after the commit point).

**When**
- `result = svc.list_sheet_bundles(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result.items) == 3`.
2. statement: `len([s for s in names("work_order_assignees") if s.lstrip().upper().startswith("SELECT")]) == 1`.

### WOS-SB-12 — the sheet neither commits nor rolls back
- **Rules:** `list_sheet_bundles` SB4; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1".
2. X.

**When**
- spies: `result = svc.list_sheet_bundles(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.total == 1`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.

### WOS-SB-13 — no `exclude_completed` sent: a completed order is counted and listed (default False)
- **Rules:** `list_sheet_bundles` SB1 (signature default `exclude_completed=False`; DAO `list_for_sheet` R4)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1".
2. K = order "2", but completed.

**When**
- `result = svc.list_sheet_bundles(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.total == 2`.
2. returns: `{b.order.id for b in result.items} == {O.id, K.id}`.

### WOS-SB-14 — `exclude_completed=True` is passed through: the completed order is left out
- **Rules:** `list_sheet_bundles` SB1 (DAO `_apply_sheet_list_filters` R8)
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1".
2. K = order "2", but completed.

**When**
- `result = svc.list_sheet_bundles(db, workspace_id=W1.id, exclude_completed=True)`.

**Then**
1. returns: `result.total == 1`.
2. returns: `[b.order.id for b in result.items] == [O.id]`.

## `WorkOrderService.sheet_daily_counts`

### WOS-SD-01 — the manager's map by ISO date; neither commits nor rolls back
- **Rules:** `sheet_daily_counts` SD1; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. order "1".
2. order "2".
3. order "3", but `planned_date D(13)`.
4. order "9", but of W2.
5. X.

**When**
- spies: `result = svc.sheet_daily_counts(db, workspace_id=W1.id)`.

**Then**
1. returns: `type(result).__name__ == "WorkOrderSheetDailyCountsResponse"`.
2. returns: `result.counts == {"2026-03-12": 2, "2026-03-13": 1}`.
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 0`.
5. session: `X in db`.

### WOS-SD-02 — no orders: an empty map
- **Rules:** `sheet_daily_counts` SD1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no work orders.

**When**
- `result = svc.sheet_daily_counts(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.counts == {}`.

### WOS-SD-03 — a filter is passed on
- **Rules:** `sheet_daily_counts` SD1
- **Kind:** happy
- **Expect:** pass

**Given**
1. order "1".
2. order "2", but `machine_id M2.id`, `planned_date D(13)`.

**When**
- `result = svc.sheet_daily_counts(db, workspace_id=W1.id, machine_id=M2.id)`.

**Then**
1. returns: `result.counts == {"2026-03-13": 1}`.

## `WorkOrderService.delete_work_order`

### WOS-X-01 — an order without an invoice is soft-deleted and committed; nobody told
- **Rules:** `delete_work_order` X1, X4; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1".

**When**
- `result = svc.delete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == O.id`.
3. committed: re-read O: `is_deleted is True`, `deleted_by == U2.id`.
4. committed: `notes() == []`.

### WOS-X-02 — a missing order: 404, the extra row is gone
- **Rules:** `delete_work_order` X1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. X.

**When**
- `svc.delete_work_order(db, wo_id=MISSING, workspace_id=W1.id, user_id=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(MISSING)`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. committed: x_gone.

### WOS-X-03 — an already deleted order: 400, nothing written
- **Rules:** `delete_work_order` X1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but gone.

**When**
- `svc.delete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work order is already deleted"`.
4. unchanged: unchanged(O).

### WOS-X-04 — another workspace's order (W2): 404, not deleted
- **Rules:** `delete_work_order` X1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = order "9", but of W2.

**When**
- `svc.delete_work_order(db, wo_id=Z.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(Z.id)`.
4. unchanged: unchanged(Z).

### WOS-X-05 — a failing commit keeps the order
- **Rules:** `delete_work_order` X1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1".

**When**
- `svc.delete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read O: `is_deleted is False`.

### WOS-X-06 — a linked draft invoice is deleted with its lines and events and unlinked, with an event
- **Rules:** `delete_work_order` X2 [BUG-2923]
- **Kind:** bug
- **Expect:** xfail BUG-2923
- **Fails today on:** Then 3 (the draft invoice is kept and linked — verified)

**Given**
1. O = order "1", but outside, `cost Decimal("2000.00")`.
2. V = inv(O), but `invoice_amount Decimal("2000.00")`, linked.
3. invl(V, "2000.00").
4. `V_ID = V.id` (taken before the call).

**When**
- `result = svc.delete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. committed: re-read O: `is_deleted is True`.
3. committed: gone(V).
4. committed: re-read O: `invoice_id is None`.
5. committed: `invoice_items` rows with `invoice_id == V_ID`: exactly 0.
6. committed: `itypes(V_ID) == []`.
7. event: `ev(O) == [("invoice_voided", f"Invoice unlinked — work order {NUM(O)} deleted")]`.
8. event: `evrow(O, "invoice_voided").metadata_json == {"invoice_id": V_ID}` (the id of the deleted invoice, read before the delete — X2 / BUG-3229 read order; `{"invoice_id": None}` fails), `evrow(O, "invoice_voided").performed_by == U2.id`.

### WOS-X-07 — an order with a linked draft invoice is still deleted (today and after the fix)
- **Rules:** `delete_work_order` X1, X2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but outside.
2. V = inv(O), linked.

**When**
- `result = svc.delete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. committed: re-read O: `is_deleted is True`, `deleted_by == U2.id`.

### WOS-X-08 — a draft invoice with payment history refuses the delete; nothing saved
- **Rules:** `delete_work_order` X2 [BUG-2923]
- **Kind:** bug
- **Expect:** xfail BUG-2923
- **Fails today on:** Then 1 (no error: the order is deleted, the invoice kept)

**Given**
1. O = order "1", but outside.
2. V = inv(O), linked.
3. P = pay(V, "100.00").
4. X.

**When**
- `svc.delete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == PAYHIST`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. unchanged: unchanged(O).
6. unchanged: unchanged(V).
7. unchanged: unchanged(P).
8. committed: x_gone.
9. committed: re-read O: `invoice_id == V.id` (the link `{"invoice_id": V.id}` is kept).
10. event: no `invoice_voided` row: `[e for e in ev(O) if e[0] == "invoice_voided"] == []`.

### WOS-X-09 — a confirmed invoice refuses the delete; nothing written
- **Rules:** `delete_work_order` X3 [BUG-2923]
- **Kind:** bug
- **Expect:** xfail BUG-2923
- **Fails today on:** Then 1 (no error: the order is deleted, the invoice kept)

**Given**
1. O = order "1", but outside.
2. V = inv(O), but confirmed, linked.
3. X.

**When**
- `svc.delete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == CONFDEL`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. session: session clean.
6. unchanged: unchanged(O).
7. unchanged: unchanged(V).
8. nothing written: nothing written.
9. committed: x_gone.
10. committed: re-read O: `invoice_id == V.id` (the link `{"invoice_id": V.id}` is kept).
11. event: no `invoice_voided` row: `[e for e in ev(O) if e[0] == "invoice_voided"] == []`.

### WOS-X-10 — a confirmed invoice is never deleted or changed by the delete (today and after the fix)
- **Rules:** `delete_work_order` X3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but outside.
2. V = inv(O), but confirmed, linked.
3. pay(V, "50.00").

**When**
- `svc.delete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`, wrapped in `try: … except HTTPException: pass`.

**Then**
1. unchanged: unchanged(V).
2. count: `invoice_payments` rows with `invoice_id == V.id`: exactly 1.

### WOS-X-11 — a voided invoice still linked refuses the delete too
- **Rules:** `delete_work_order` X3 [BUG-2923]
- **Kind:** bug
- **Expect:** xfail BUG-2923
- **Fails today on:** Then 1 (no error: the order is deleted)

**Given**
1. O = order "1", but outside.
2. V = inv(O), but voided-inv, linked.

**When**
- `svc.delete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == CONFDEL`.
4. unchanged: unchanged(O).
5. unchanged: unchanged(V).
6. committed: re-read O: `invoice_id == V.id` (the link `{"invoice_id": V.id}` is kept).
7. event: no `invoice_voided` row: `[e for e in ev(O) if e[0] == "invoice_voided"] == []`.

### WOS-X-12 — a linked invoice of W2 is left alone and the delete goes ahead
- **Rules:** `delete_work_order` X3; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order "1", but outside.
2. V = inv(O), but of W2, confirmed, linked.

**When**
- `result = svc.delete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. committed: re-read O: `is_deleted is True`.
3. unchanged: unchanged(V).

### WOS-X-13 — a linked invoice of W0 is left alone and the delete goes ahead
- **Rules:** `delete_work_order` X3; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order "1", but outside.
2. V = inv(O), but of W0, linked.

**When**
- `result = svc.delete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. committed: re-read O: `is_deleted is True`.
3. unchanged: unchanged(V).

### WOS-X-14 — the manager's checks come first: an already deleted order keeps its draft invoice
- **Rules:** `delete_work_order` X1, X2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but outside, gone.
2. V = inv(O), linked.

**When**
- `svc.delete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work order is already deleted"`.
4. unchanged: unchanged(V).
5. nothing written: nothing written.

## `WorkOrderService.start_work_order`

### WOS-S-01 — a draft with an account and no invoice is started and committed; nobody told
- **Rules:** `start_work_order` S1, S2; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but outside.
2. status row(M1, "RUNNING", T0).

**When**
- `result = svc.start_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == O.id`.
3. committed: re-read O: `status == "IN_PROGRESS"`, `started_by == U2.id`, `started_at == NOW`, `invoice_id is None`.
4. committed: `account_invoices` rows with `order_id == O.id`: exactly 0.
5. committed: `notes() == []`.

### WOS-S-02 — a line that cannot be consumed saves nothing; the extra row is gone
- **Rules:** `start_work_order` S1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. S(I1, 10, Decimal("2.50")).
2. S(I2, 2, Decimal("5.00")).
3. O = order "1", but `uses_inventory True`.
4. status row(M1, "RUNNING", T0).
5. line(O, I1, "3").
6. line(O, I2, "5").
7. X.

**When**
- `svc.start_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Insufficient stock (2 available, 5 requested)"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. unchanged: unchanged(O).
7. nothing written: nothing written.
8. committed: x_gone.
9. committed: the `inventory` rows of I1 and I2 at F1 keep `qty` 10 and 2 (the model's column is `qty`).

### WOS-S-03 — a started order: the manager's 400 passes unchanged
- **Rules:** `start_work_order` S1
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but started.

**When**
- `svc.start_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work order must be in draft to be started"`.
4. unchanged: unchanged(O).

### WOS-S-04 — a failing commit keeps the order a draft
- **Rules:** `start_work_order` S1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1".

**When**
- `svc.start_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read O: `status == "DRAFT"`, `started_by is None`.

## `WorkOrderService.complete_work_order`

### WOS-C-01 — a started order with a draft invoice is completed and committed
- **Rules:** `complete_work_order` C7, C10; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but started, outside, `cost Decimal("750.50")`.
2. ran.
3. V = inv(O), but `invoice_amount Decimal("750.50")`, linked.
4. invl(V, "750.50").

**When**
- `result = svc.complete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == O.id`.
3. committed: re-read O: `status == "COMPLETED"`, `completed_by == U2.id`, `completed_at == NOW`, `invoice_id == V.id`.
4. event: `("completed", f"Work order {NUM(O)} marked complete") in ev(O)`.

### WOS-C-02 — the draft is confirmed at its line sum, with the `confirmed` event
- **Rules:** `complete_work_order` C7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but started, outside, `cost Decimal("750.50")`.
2. ran.
3. V = inv(O), but `invoice_amount Decimal("0.00")`, linked.
4. invl(V, "750.50").

**When**
- `result = svc.complete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. committed: re-read V: `invoice_status == "confirmed"`, `invoice_amount == Decimal("750.50")`.
3. committed: `itypes(V.id)[-1] == "confirmed"`.

### WOS-C-03 — the confirmed notice goes to the creator and every approver, active members only
- **Rules:** `complete_work_order` C7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but started, outside.
2. ran.
3. approver(O, U3), but approved.
4. approver(O, U4), but approved.
5. V = inv(O), linked.
6. invl(V, "100.00").

**When**
- `result = svc.complete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. committed: `recips() == [U1.id, U3.id]`.
3. committed: every row of `notes()` has `notification_type == "invoice_action"`, `entity_type == "work_order"`, `entity_id == O.id`.
4. committed: every row of `notes()` has `preview == CONFP(O)`.

### WOS-C-04 — an already completed order is returned as it is: no write, no commit, no rollback
- **Rules:** `complete_work_order` C2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but completed, outside.
2. V = inv(O), but confirmed, linked.
3. X.

**When**
- spies: `result = svc.complete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.
5. unchanged: unchanged(O).
6. unchanged: unchanged(V).
7. count: `ev(O) == []`.
8. count: `notes() == []`.

### WOS-C-05 — a completed order with an account and no invoice is returned without the invoice check
- **Rules:** `complete_work_order` C2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but completed, outside.

**When**
- `result = svc.complete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`, `result.status == "COMPLETED"`.
2. unchanged: unchanged(O).

### WOS-C-06 — a draft: 400, nothing written, the extra row is gone
- **Rules:** `complete_work_order` C3; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but outside.
2. V = inv(O), linked.
3. invl(V, "100.00").
4. X.

**When**
- `svc.complete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == INPROG`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. unchanged: unchanged(O).
6. unchanged: unchanged(V).
7. nothing written: nothing written.
8. committed: x_gone.

### WOS-C-07 — a voided order: 400, nothing written
- **Rules:** `complete_work_order` C3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but voided.

**When**
- `svc.complete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == INPROG`.
4. unchanged: unchanged(O).

### WOS-C-08 — an account and no invoice: 400 asking for an invoice
- **Rules:** `complete_work_order` C4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but started, outside.
2. X.

**When**
- `svc.complete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == NOINV`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. unchanged: unchanged(O).
6. nothing written: nothing written.
7. committed: x_gone.

### WOS-C-09 — the linked invoice is a W2 invoice: "Linked invoice not found", no id shown
- **Rules:** `complete_work_order` C5; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order "1", but started, outside.
2. V = inv(O), but of W2, linked.

**When**
- `svc.complete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == INVNF`.
4. unchanged: unchanged(O).
5. unchanged: unchanged(V).

### WOS-C-10 — the linked invoice is a W0 invoice: "Linked invoice not found"
- **Rules:** `complete_work_order` C5; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order "1", but started, outside.
2. V = inv(O), but of W0, linked.

**When**
- `svc.complete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == INVNF`.
4. unchanged: unchanged(V).

### WOS-C-11 — the linked invoice was voided: 400, nothing written
- **Rules:** `complete_work_order` C6
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but started, outside.
2. V = inv(O), but voided-inv, linked.

**When**
- `svc.complete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == VOIDINV`.
4. unchanged: unchanged(O).
5. unchanged: unchanged(V).
6. nothing written: nothing written.

### WOS-C-12 — a draft with no lines cannot be confirmed: 400, the order is not completed
- **Rules:** `complete_work_order` C7, Errors row C7 [BUG-628] (invoice manager pass-through)
- **Kind:** bug
- **Expect:** xfail BUG-628
- **Fails today on:** Then 1 (no error: the empty draft is confirmed and the order completed)

**Given**
1. O = order "1", but started, outside.
2. ran.
3. V = inv(O), but `invoice_amount Decimal("0.00")`, linked.
4. X.

**When**
- `svc.complete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == NOLINES`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. unchanged: unchanged(O).
6. unchanged: unchanged(V).
7. nothing written: nothing written.
8. committed: x_gone.

### WOS-C-13 — an invoice already confirmed is left as it is; the order is completed, nobody told
- **Rules:** `complete_work_order` C8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started, outside.
2. ran.
3. V = inv(O), but confirmed, linked.
4. invl(V, "100.00").

**When**
- `result = svc.complete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. committed: re-read O: `status == "COMPLETED"`.
3. unchanged: unchanged(V).
4. committed: `itypes(V.id).count("confirmed") == 0`.
5. committed: `notes() == []`.

### WOS-C-14 — without an account a linked draft invoice is not looked at
- **Rules:** `complete_work_order` C9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. ran.
3. V = inv(O), linked.
4. invl(V, "100.00").

**When**
- `result = svc.complete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. committed: re-read O: `status == "COMPLETED"`, `invoice_id == V.id`.
3. unchanged: unchanged(V).
4. committed: `notes() == []`.

### WOS-C-15 — without an account and without an invoice the order completes
- **Rules:** `complete_work_order` C9, C10
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. ran.

**When**
- `result = svc.complete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. committed: re-read O: `status == "COMPLETED"`, `invoice_id is None`.
3. committed: `account_invoices` rows with `order_id == O.id`: exactly 0.
4. committed: `notes() == []`.

### WOS-C-16 — a refusal in the completion undoes the invoice confirm and its notices
- **Rules:** `complete_work_order` C10; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but started, outside.
2. ran.
3. V = inv(O), linked.
4. invl(V, "100.00").
5. X.

**When**
- `svc.complete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id, completed_by_user_ids=[U4.id])`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == NOTMEMBER`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. unchanged: unchanged(V).
7. unchanged: unchanged(O).
8. nothing written: nothing written.
9. committed: x_gone.

### WOS-C-17 — notes, workers and the performer are passed to the completion
- **Rules:** `complete_work_order` C10
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. ran.

**When**
- `result = svc.complete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id, completion_notes="Pump rebuilt", completed_by_user_ids=[U3.id])`.

**Then**
1. returns: `result.id == O.id`.
2. committed: re-read O: `completion_notes == "Pump rebuilt"`, `completed_by_names == "Sara Khan"`.
3. committed: `[c.user_id for c in WorkOrderCompleter rows with work_order_id == O.id] == [U3.id]`.
4. event: `evrow(O, "completed").performed_by == U2.id`.

### WOS-C-18 — machine status "IDLE" is used
- **Rules:** `complete_work_order` C11
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. ran.

**When**
- `result = svc.complete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id, machine_status="IDLE")`.

**Then**
1. returns: `result.id == O.id`.
2. event: `stat(M1) == ["IDLE"]`.

### WOS-C-19 — machine status "OFF" is used
- **Rules:** `complete_work_order` C11
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. ran.

**When**
- `result = svc.complete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id, machine_status="OFF")`.

**Then**
1. returns: `result.id == O.id`.
2. event: `stat(M1) == ["OFF"]`.

### WOS-C-20 — an empty machine status means "not given": the status before start comes back
- **Rules:** `complete_work_order` C11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. ran.

**When**
- `result = svc.complete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id, machine_status="")`.

**Then**
1. returns: `result.id == O.id`.
2. event: `stat(M1) == ["RUNNING"]`.

### WOS-C-21 — no machine status: the status before start comes back
- **Rules:** `complete_work_order` C11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. ran.

**When**
- `result = svc.complete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id, machine_status=None)`.

**Then**
1. returns: `result.id == O.id`.
2. event: `stat(M1) == ["RUNNING"]`.

### WOS-C-22 — an unknown machine status raises ValueError; nothing saved
- **Rules:** `complete_work_order` C11, Errors row C11; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but started, outside.
2. ran.
3. V = inv(O), linked.
4. invl(V, "100.00").
5. X.

**When**
- `svc.complete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id, machine_status="BROKEN")`.

**Then**
1. raises: `ValueError`.
2. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
3. unchanged: unchanged(O).
4. unchanged: unchanged(V).
5. nothing written: nothing written.
6. committed: x_gone.

### WOS-C-23 — approvals are not checked: a pending approver does not stop the completion
- **Rules:** `complete_work_order` C12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. ran.
3. approver(O, U3).

**When**
- `result = svc.complete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. committed: re-read O: `status == "COMPLETED"`.

### WOS-C-24 — a missing order: 404, the extra row is gone
- **Rules:** `complete_work_order` C1, Errors row C1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. X.

**When**
- `svc.complete_work_order(db, wo_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(MISSING)`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. committed: x_gone.

### WOS-C-25 — another workspace's order (W2): 404, not completed
- **Rules:** `complete_work_order` C1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = order "9", but of W2, started.

**When**
- `svc.complete_work_order(db, wo_id=Z.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(Z.id)`.
4. unchanged: unchanged(Z).

### WOS-C-26 — a failing commit saves neither the confirm nor the completion
- **Rules:** `complete_work_order` C10; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but started, outside.
2. ran.
3. V = inv(O), linked.
4. invl(V, "100.00").

**When**
- `svc.complete_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read O: `status == "IN_PROGRESS"`.
4. re-read V: `invoice_status == "draft"`.
5. count: `notes() == []`.

### WOS-C-27 — the order is read with a row lock before any check
- **Rules:** `complete_work_order` C1 [BUG-2916]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-2916
- **Fails today on:** Then 2 (the order is read without `FOR UPDATE`)

**Given**
1. O = order "1", but started, outside.
2. ran.
3. V = inv(O), linked.
4. invl(V, "100.00").
5. `oid = O.id`.
6. Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `result = svc.complete_work_order(db, wo_id=oid, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == oid`.
2. statement: lock(work_orders).
3. statement: lock first.

## `WorkOrderService.complete_work_order_as_planned`

### WOS-P-01 — a past-due draft with a draft invoice is started, completed at noon of its day and committed
- **Rules:** `complete_work_order_as_planned` P4, P6; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but outside, `planned_date D(8)`, `cost Decimal("750.50")`.
2. status row(M1, "RUNNING", T0).
3. V = inv(O), but `invoice_amount Decimal("0.00")`, linked.
4. invl(V, "750.50").

**When**
- `result = svc.complete_work_order_as_planned(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == O.id`.
3. committed: re-read O: `status == "COMPLETED"`, `started_at == NOON(8)`, `completed_at == NOON(8)`, `started_by == U2.id`.
4. committed: re-read V: `invoice_status == "confirmed"`, `invoice_amount == Decimal("750.50")`.

### WOS-P-02 — the confirm sends the confirmed notice to the creator
- **Rules:** `complete_work_order_as_planned` P4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but outside, `planned_date D(8)`.
2. V = inv(O), linked.
3. invl(V, "100.00").

**When**
- `result = svc.complete_work_order_as_planned(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. committed: `recips() == [U1.id]`.
3. committed: `notes()[0].notification_type == "invoice_action"`, `notes()[0].preview == CONFP(O)`.

### WOS-P-03 — an already completed order is returned as it is: no write, no commit, no rollback
- **Rules:** `complete_work_order_as_planned` P2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but completed, outside.
2. X.

**When**
- spies: `result = svc.complete_work_order_as_planned(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.
5. unchanged: unchanged(O).
6. count: `ev(O) == []`.

### WOS-P-04 — a started order with an account and no invoice is told it must be a draft
- **Rules:** `complete_work_order_as_planned` P3 [BUG-3223]
- **Kind:** bug
- **Expect:** xfail BUG-3223
- **Fails today on:** Then 3 (the detail is NOINV — verified)

**Given**
1. O = order "1", but started, outside.
2. X.

**When**
- `svc.complete_work_order_as_planned(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == NOTDRAFT`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. unchanged: unchanged(O).
6. committed: x_gone.

### WOS-P-05 — a voided order with an account and no invoice is told it must be a draft
- **Rules:** `complete_work_order_as_planned` P3 [BUG-3223]
- **Kind:** bug
- **Expect:** xfail BUG-3223
- **Fails today on:** Then 2 (the detail is NOINV)

**Given**
1. O = order "1", but voided, outside.

**When**
- `svc.complete_work_order_as_planned(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == NOTDRAFT`.
3. unchanged: unchanged(O).

### WOS-P-06 — a started order with a draft invoice is refused before the invoice is touched
- **Rules:** `complete_work_order_as_planned` P3 [BUG-3223]
- **Kind:** bug
- **Expect:** xfail BUG-3223
- **Fails today on:** Then 3 (the draft is confirmed — an `UPDATE` of `account_invoices` — before the manager's refusal)

**Given**
1. O = order "1", but started, outside.
2. V = inv(O), linked.
3. invl(V, "100.00").
4. `oid = O.id`.
5. Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `svc.complete_work_order_as_planned(db, wo_id=oid, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == NOTDRAFT`.
3. statement: no statement in `names("account_invoices")` starts with `UPDATE`.

### WOS-P-07 — a started order without an account: "must be in draft", nothing written (today and after the fix)
- **Rules:** `complete_work_order_as_planned` P3, P5; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but started.
2. X.

**When**
- `svc.complete_work_order_as_planned(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == NOTDRAFT`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. unchanged: unchanged(O).
6. nothing written: nothing written.
7. committed: x_gone.

### WOS-P-08 — a started order's draft invoice stays a draft (today and after the fix)
- **Rules:** `complete_work_order_as_planned` P3, P6; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but started, outside.
2. V = inv(O), linked.
3. invl(V, "100.00").

**When**
- `svc.complete_work_order_as_planned(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`, inside `pytest.raises(HTTPException) as exc`.

**Then**
1. raises: `exc.value.status_code == 400`.
2. unchanged: unchanged(V).
3. unchanged: unchanged(O).
4. count: `notes() == []`.

### WOS-P-09 — a draft with an account and no invoice: 400 asking for an invoice
- **Rules:** `complete_work_order_as_planned` P4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but outside, `planned_date D(8)`.

**When**
- `svc.complete_work_order_as_planned(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == NOINV`.
4. unchanged: unchanged(O).
5. nothing written: nothing written.

### WOS-P-10 — the linked invoice is a W2 invoice: "Linked invoice not found"
- **Rules:** `complete_work_order_as_planned` P4; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order "1", but outside, `planned_date D(8)`.
2. V = inv(O), but of W2, linked.

**When**
- `svc.complete_work_order_as_planned(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == INVNF`.
4. unchanged: unchanged(O).
5. unchanged: unchanged(V).

### WOS-P-11 — the linked invoice was voided: 400
- **Rules:** `complete_work_order_as_planned` P4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but outside, `planned_date D(8)`.
2. V = inv(O), but voided-inv, linked.

**When**
- `svc.complete_work_order_as_planned(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == VOIDINV`.
4. unchanged: unchanged(O).

### WOS-P-12 — an invoice already confirmed is left; the order completes, nobody told
- **Rules:** `complete_work_order_as_planned` P4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but outside, `planned_date D(8)`.
2. V = inv(O), but confirmed, linked.
3. invl(V, "100.00").

**When**
- `result = svc.complete_work_order_as_planned(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. committed: re-read O: `status == "COMPLETED"`.
3. unchanged: unchanged(V).
4. committed: `notes() == []`.

### WOS-P-13 — without an account a linked draft invoice is not looked at
- **Rules:** `complete_work_order_as_planned` P5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but `planned_date D(8)`.
2. V = inv(O), linked.
3. invl(V, "100.00").

**When**
- `result = svc.complete_work_order_as_planned(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == O.id`.
2. committed: re-read O: `status == "COMPLETED"`.
3. unchanged: unchanged(V).
4. committed: `notes() == []`.

### WOS-P-14 — a future planned date is refused and the invoice confirm is undone
- **Rules:** `complete_work_order_as_planned` P6; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but outside, `planned_date D(11)`.
2. V = inv(O), linked.
3. invl(V, "100.00").
4. X.

**When**
- `svc.complete_work_order_as_planned(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Complete as planned is only allowed when the planned date is today or in the past"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. unchanged: unchanged(V).
7. unchanged: unchanged(O).
8. nothing written: nothing written.
9. committed: x_gone.

### WOS-P-15 — no planned date and no invoice: the invoice error wins (today and after the fix)
- **Rules:** `complete_work_order_as_planned` P4, P6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but outside, `planned_date None`.

**When**
- `svc.complete_work_order_as_planned(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == NOINV`.
4. unchanged: unchanged(O).

### WOS-P-16 — unmet approvals are refused and the invoice confirm is undone
- **Rules:** `complete_work_order_as_planned` P6; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but outside, `planned_date D(8)`, `approved_by None`, `approved_at None`.
2. approver(O, U3).
3. V = inv(O), linked.
4. invl(V, "100.00").

**When**
- `svc.complete_work_order_as_planned(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Assigned approvers must approve before work can be completed"`.
4. unchanged: unchanged(V).
5. count: `notes() == []`.

### WOS-P-17 — an unknown machine status raises ValueError; nothing saved
- **Rules:** `complete_work_order_as_planned` P7
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but outside, `planned_date D(8)`.
2. V = inv(O), linked.
3. invl(V, "100.00").
4. X.

**When**
- `svc.complete_work_order_as_planned(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id, machine_status="BROKEN")`.

**Then**
1. raises: `ValueError`.
2. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
3. unchanged: unchanged(O).
4. unchanged: unchanged(V).
5. nothing written: nothing written.
6. committed: x_gone.

### WOS-P-18 — notes and workers are passed to the manager
- **Rules:** `complete_work_order_as_planned` P6, P7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but `planned_date D(8)`.
2. status row(M1, "RUNNING", T0).

**When**
- `result = svc.complete_work_order_as_planned(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id, completion_notes="Belt replaced", machine_status="OFF", completed_by_user_ids=[U3.id])`.

**Then**
1. returns: `result.id == O.id`.
2. committed: re-read O: `completion_notes == "Belt replaced"`, `completed_by_names == "Sara Khan"`.
3. committed: `[c.user_id for c in WorkOrderCompleter rows with work_order_id == O.id] == [U3.id]`.
4. event: `stat(M1)[-1] == "OFF"`.

### WOS-P-19 — a missing order: 404, the extra row is gone
- **Rules:** `complete_work_order_as_planned` P1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. X.

**When**
- `svc.complete_work_order_as_planned(db, wo_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(MISSING)`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. committed: x_gone.

### WOS-P-20 — a failing commit saves neither the confirm nor the completion
- **Rules:** `complete_work_order_as_planned` P6; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but outside, `planned_date D(8)`.
2. V = inv(O), linked.
3. invl(V, "100.00").

**When**
- `svc.complete_work_order_as_planned(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read O: `status == "DRAFT"`.
4. re-read V: `invoice_status == "draft"`.

### WOS-P-21 — the order is read with a row lock before any check
- **Rules:** `complete_work_order_as_planned` P1 [BUG-3222]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-3222
- **Fails today on:** Then 2 (the service reads the order without `FOR UPDATE`)

**Given**
1. O = order "1", but outside, `planned_date D(8)`.
2. V = inv(O), linked.
3. invl(V, "100.00").
4. `oid = O.id`.
5. Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `result = svc.complete_work_order_as_planned(db, wo_id=oid, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == oid`.
2. statement: lock(work_orders).
3. statement: lock first.

## `WorkOrderService.void_work_order`

### WOS-V-01 — an order without an invoice is voided and committed; nobody told
- **Rules:** `void_work_order` V3, V6, V7; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1".

**When**
- `result = svc.void_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == O.id`.
3. committed: re-read O: `status == "VOIDED"`, `void_note == "Cancelled"`, `voided_by == U2.id`, `voided_at == NOW`.
4. event: `ev(O) == [("voided", f"Work order {NUM(O)} voided. Reason: Cancelled")]`.
5. committed: `notes() == []`.

### WOS-V-02 — a linked draft invoice is deleted with its lines and events; the order is unlinked
- **Rules:** `void_work_order` V4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but outside, `cost Decimal("500.00")`.
2. V = inv(O), but `invoice_amount Decimal("500.00")`, linked.
3. invl(V, "500.00").
4. `V_ID = V.id`.

**When**
- `result = svc.void_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`.

**Then**
1. returns: `result.id == O.id`.
2. committed: gone(V).
3. committed: re-read O: `invoice_id is None`, `status == "VOIDED"`.
4. committed: `invoice_items` rows with `invoice_id == V_ID`: exactly 0.
5. committed: `itypes(V_ID) == []`.
6. committed: `notes() == []`.

### WOS-V-03 — the unlink event comes before the voided event and keeps the deleted invoice's id
- **Rules:** `void_work_order` V4, V4a [BUG-3229], V6
- **Kind:** bug
- **Expect:** xfail BUG-3229
- **Fails today on:** Then 3 (`metadata_json == {"invoice_id": None}`: the id is read after `delete_invoice`, when the FK `ON DELETE SET NULL` has cleared it — verified)

**Given**
1. O = order "1", but outside.
2. V = inv(O), linked.
3. invl(V, "100.00").
4. `V_ID = V.id` (taken before the call).

**When**
- `result = svc.void_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`.

**Then**
1. returns: `result.id == O.id`.
2. event: `ev(O) == [("invoice_voided", f"Invoice unlinked — work order {NUM(O)} voided"), ("voided", f"Work order {NUM(O)} voided. Reason: Cancelled")]`.
3. event: `evrow(O, "invoice_voided").metadata_json == {"invoice_id": V_ID}`.
4. event: `evrow(O, "invoice_voided").performed_by == U2.id`.

### WOS-V-04 — a draft with payment history: the invoice manager's 400, the whole void undone
- **Rules:** `void_work_order` V4, Errors row V4 [BUG-639] (invoice manager pass-through)
- **Kind:** bug
- **Expect:** xfail BUG-639
- **Fails today on:** Then 1 (the call raises IntegrityError, not HTTPException)

**Given**
1. O = order "1", but outside.
2. V = inv(O), linked.
3. P = pay(V, "100.00").

**When**
- `svc.void_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == PAYHIST`.
4. unchanged: unchanged(O).
5. unchanged: unchanged(V).

### WOS-V-05 — a draft with payment history is never deleted and the order not voided (today and after the fix)
- **Rules:** `void_work_order` V4; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but outside.
2. V = inv(O), linked.
3. P = pay(V, "100.00").
4. X.

**When**
- `svc.void_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`, wrapped in `with pytest.raises(Exception):`.

**Then**
1. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
2. re-read V: `V is not None`, `invoice_status == "draft"`.
3. re-read P: `P is not None`, `is_voided is True`.
4. unchanged: unchanged(O).
5. count: `ev(O) == []`.
6. committed: x_gone.

### WOS-V-06 — a linked invoice already voided is not touched; the order keeps the link and is voided
- **Rules:** `void_work_order` V5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but outside.
2. V = inv(O), but voided-inv, linked.

**When**
- `result = svc.void_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`.

**Then**
1. returns: `result.id == O.id`.
2. committed: re-read O: `status == "VOIDED"`, `invoice_id == V.id`.
3. unchanged: unchanged(V).
4. event: `[t for t, _ in ev(O)] == ["voided"]`.

### WOS-V-07 — a linked W2 invoice is not touched; the order keeps the link and is voided
- **Rules:** `void_work_order` V5; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order "1", but outside.
2. V = inv(O), but of W2, linked.

**When**
- `result = svc.void_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`.

**Then**
1. returns: `result.id == O.id`.
2. committed: re-read O: `status == "VOIDED"`, `invoice_id == V.id`.
3. unchanged: unchanged(V).

### WOS-V-08 — a linked W0 invoice is not touched; the order keeps the link and is voided
- **Rules:** `void_work_order` V5; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order "1", but outside.
2. V = inv(O), but of W0, linked.

**When**
- `result = svc.void_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`.

**Then**
1. returns: `result.id == O.id`.
2. committed: re-read O: `status == "VOIDED"`, `invoice_id == V.id`.
3. unchanged: unchanged(V).

### WOS-V-09 — a confirmed invoice refuses the void; order, approvals, invoice and payments kept
- **Rules:** `void_work_order` V5a, Errors row V5a [BUG-3224]
- **Kind:** bug
- **Expect:** xfail BUG-3224
- **Fails today on:** Then 1 (no error: the order is voided and keeps the payable invoice — verified)

**Given**
1. O = order "1", but outside, `cost Decimal("40000.00")`.
2. P3 = approver(O, U3), but approved.
3. V = inv(O), but confirmed, `invoice_amount Decimal("40000.00")`, linked.
4. P = pay(V, "10000.00").
5. X.

**When**
- `svc.void_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == FINAL`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. session: session clean.
6. unchanged: unchanged(O).
7. unchanged: unchanged(P3).
8. unchanged: unchanged(V).
9. unchanged: unchanged(P).
10. nothing written: nothing written.
11. committed: x_gone.

### WOS-V-10 — a confirmed invoice is never deleted or changed by the void (today and after the fix)
- **Rules:** `void_work_order` V5, V5a
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but outside.
2. V = inv(O), but confirmed, `invoice_amount Decimal("40000.00")`, linked.
3. P = pay(V, "10000.00").

**When**
- `svc.void_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`, wrapped in `try: … except HTTPException: pass`.

**Then**
1. unchanged: unchanged(V).
2. unchanged: unchanged(P).
3. count: `invoice_payments` rows with `invoice_id == V.id`: exactly 1.

### WOS-V-11 — a completed order with its confirmed invoice: the "completed" 400, nothing written
- **Rules:** `void_work_order` V2, Errors row V2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but completed, outside.
2. V = inv(O), but confirmed, linked.
3. X.

**When**
- `svc.void_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot void a completed work order"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. unchanged: unchanged(O).
7. unchanged: unchanged(V).
8. nothing written: nothing written.
9. committed: x_gone.

### WOS-V-12 — a completed order with a leftover draft is refused before the invoice is touched
- **Rules:** `void_work_order` V2 [BUG-3224]
- **Kind:** bug
- **Expect:** xfail BUG-3224
- **Fails today on:** Then 4 (the draft invoice is read and deleted before the manager's refusal)

**Given**
1. O = order "1", but completed.
2. V = inv(O), linked.
3. invl(V, "100.00").
4. `oid = O.id`.
5. Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `svc.void_work_order(db, wo_id=oid, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot void a completed work order"`.
4. statement: `names("account_invoices") == []`.

### WOS-V-13 — a voided order with a leftover draft: the "already voided" 400, the draft kept (today and after the fix)
- **Rules:** `void_work_order` V2, Errors row V2
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but voided.
2. V = inv(O), linked.
3. invl(V, "100.00").

**When**
- `svc.void_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work order is already voided"`.
4. unchanged: unchanged(V).
5. unchanged: unchanged(O).
6. nothing written: nothing written.

### WOS-V-14 — a voided order with a leftover draft is refused before the invoice is touched
- **Rules:** `void_work_order` V2 [BUG-3224]
- **Kind:** bug
- **Expect:** xfail BUG-3224
- **Fails today on:** Then 3 (the draft invoice is read and deleted before the manager's refusal)

**Given**
1. O = order "1", but voided.
2. V = inv(O), linked.
3. `oid = O.id`.
4. Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `svc.void_work_order(db, wo_id=oid, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == "Work order is already voided"`.
3. statement: `names("account_invoices") == []`.

### WOS-V-15 — a missing order: 404, the extra row is gone
- **Rules:** `void_work_order` V1, Errors row V1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. X.

**When**
- `svc.void_work_order(db, wo_id=MISSING, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(MISSING)`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. committed: x_gone.

### WOS-V-16 — another workspace's order (W2): 404, not voided
- **Rules:** `void_work_order` V1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = order "9", but of W2.

**When**
- `svc.void_work_order(db, wo_id=Z.id, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(Z.id)`.
4. unchanged: unchanged(Z).

### WOS-V-17 — a failing commit keeps the order and its draft invoice
- **Rules:** `void_work_order` V6; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but outside.
2. V = inv(O), linked.
3. invl(V, "100.00").

**When**
- `svc.void_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read O: `status == "DRAFT"`, `invoice_id == V.id`.
4. re-read V: `V is not None`, `invoice_status == "draft"`.

### WOS-V-18 — the order is read with a row lock before any check
- **Rules:** `void_work_order` V1 [BUG-3222]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-3222
- **Fails today on:** Then 2 (the service reads the order without `FOR UPDATE`)

**Given**
1. O = order "1", but outside.
2. V = inv(O), linked.
3. invl(V, "100.00").
4. `oid = O.id`.
5. Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `result = svc.void_work_order(db, wo_id=oid, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`.

**Then**
1. returns: `result.id == oid`.
2. statement: lock(work_orders).
3. statement: lock first.

### WOS-V-19 — the unlink event is written before the voided event, by the actor (today and after the fix)
- **Rules:** `void_work_order` V4, V6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but outside.
2. V = inv(O), linked.
3. invl(V, "100.00").
4. `V_ID = V.id`.

**When**
- `result = svc.void_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`.

**Then**
1. returns: `result.id == O.id`.
2. event: `ev(O) == [("invoice_voided", f"Invoice unlinked — work order {NUM(O)} voided"), ("voided", f"Work order {NUM(O)} voided. Reason: Cancelled")]`.
3. event: `evrow(O, "invoice_voided").performed_by == U2.id`.
4. event: `set(evrow(O, "invoice_voided").metadata_json) == {"invoice_id"}` (the key is there; its value is V-03's check).
5. committed: gone(V); re-read O: `invoice_id is None`.

## `WorkOrderService.create_invoice_for_work_order`

### WOS-I-01 — a draft order with account and cost gets its draft invoice, committed and linked
- **Rules:** `create_invoice_for_work_order` I6, I8, I10; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but outside, `cost Decimal("750.50")`.

**When**
- `result = svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == O.id`, `result.invoice_id is not None`.
3. committed: re-read O: `invoice_id == result.invoice_id`.
4. committed: the `account_invoices` row with `id == result.invoice_id` has `invoice_status == "draft"`, `invoice_amount == Decimal("750.50")`.
5. committed: `account_invoices` rows with `order_type == "work_order"` and `order_id == O.id`: exactly 1.

### WOS-I-02 — the invoice header carries the order's account, link, due date, description and notes
- **Rules:** `create_invoice_for_work_order` I6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but outside, `cost Decimal("750.50")`, `end_date D(20)`.

**When**
- `result = svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`; then `INV = db.get(AccountInvoice, result.invoice_id)` after `db.expire_all()`.

**Then**
1. returns: `result.invoice_id is not None`.
2. re-read INV: `workspace_id == W1.id`, `account_id == A1.id`, `invoice_type == "payable"`, `invoice_status == "draft"`.
3. re-read INV: `order_type == "work_order"`, `order_id == O.id`.
4. re-read INV: `due_date == D(20)`, `description == f"Auto-created from work order {NUM(O)}"`, `notes == "Old desc"`.
5. re-read INV: `allow_payments is True`, `invoice_number is None`, `vendor_invoice_number is None`, `payment_locked_reason is None`.

### WOS-I-03 — exactly one invoice line: the title, 1 × the cost, `wo_labor`, no rounding
- **Rules:** `create_invoice_for_work_order` I8
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but outside, `cost Decimal("750.50")`.

**When**
- `result = svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`; then `LS = LINES(result.invoice_id)` after `db.expire_all()`.

**Then**
1. returns: `result.invoice_id is not None`.
2. count: `len(LS) == 1`.
3. re-read LS[0]: `line_number == 1`, `description == "Service — Lathe 3"`, `item_id is None`, `source_order_item_id is None`, `source_order_item_type == "wo_labor"`.
4. re-read LS[0]: `quantity == Decimal("1")`, `unit is None`, `unit_price == Decimal("750.50")`, `line_subtotal == Decimal("750.50")`.

### WOS-I-04 — one `invoice_created` order event; the invoice has its `created` and `items_synced` events
- **Rules:** `create_invoice_for_work_order` I9, I8
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but outside.

**When**
- `result = svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.invoice_id is not None`.
2. event: `ev(O) == [("invoice_created", f"Invoice #{result.invoice_id} created from work order")]`.
3. event: `evrow(O, "invoice_created").metadata_json == {"invoice_id": result.invoice_id}`, `evrow(O, "invoice_created").performed_by == U2.id`.
4. committed: `itypes(result.invoice_id) == ["created", "items_synced"]`.

### WOS-I-05 — the draft notice goes to the creator
- **Rules:** `create_invoice_for_work_order` I10
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but outside.

**When**
- `result = svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.invoice_id is not None`.
2. committed: `recips() == [U1.id]`.
3. committed: `notes()[0].notification_type == "invoice_action"`, `notes()[0].entity_type == "work_order"`, `notes()[0].entity_id == O.id`.
4. committed: `notes()[0].preview == DRAFTP`.

### WOS-I-06 — approvals are not required; a pending approver is told too
- **Rules:** `create_invoice_for_work_order` I5, I10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but outside, `approved_by None`, `approved_at None`.
2. approver(O, U3).

**When**
- `result = svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.invoice_id is not None`.
2. committed: `recips() == [U1.id, U3.id]`.

### WOS-I-07 — no end date: the invoice has no due date
- **Rules:** `create_invoice_for_work_order` I6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but outside.

**When**
- `result = svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.invoice_id is not None`.
2. committed: the `account_invoices` row with `id == result.invoice_id` has `due_date is None`.

### WOS-I-08 — a started order may get an invoice
- **Rules:** `create_invoice_for_work_order` I3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but started, outside.

**When**
- `result = svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.invoice_id is not None`.
2. committed: re-read O: `status == "IN_PROGRESS"`, `invoice_id == result.invoice_id`.

### WOS-I-09 — a draft already linked: 409, the extra row is gone
- **Rules:** `create_invoice_for_work_order` I2, Errors row I2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but outside.
2. V = inv(O), linked.
3. X.

**When**
- `svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == EXISTS`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. session: session clean.
6. unchanged: unchanged(O).
7. nothing written: nothing written.
8. committed: x_gone.

### WOS-I-10 — a voided invoice linked still counts: 409
- **Rules:** `create_invoice_for_work_order` I2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but outside.
2. V = inv(O), but voided-inv, linked.

**When**
- `svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == EXISTS`.
4. nothing written: nothing written.

### WOS-I-11 — a confirmed invoice linked: 409
- **Rules:** `create_invoice_for_work_order` I2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but outside.
2. V = inv(O), but confirmed, linked.

**When**
- `svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == EXISTS`.
4. unchanged: unchanged(V).

### WOS-I-12 — a voided order gets no invoice: 400
- **Rules:** `create_invoice_for_work_order` I3, Errors row I3 [BUG-3225]
- **Kind:** bug
- **Expect:** xfail BUG-3225
- **Fails today on:** Then 1 (no error: a 500.00 draft is made for the voided order — verified)

**Given**
1. O = order "1", but voided, outside, `cost Decimal("500.00")`.
2. X.

**When**
- `svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work order is voided"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. unchanged: unchanged(O).
6. nothing written: nothing written.
7. committed: x_gone.

### WOS-I-13 — a completed order without an invoice gets no invoice: 400
- **Rules:** `create_invoice_for_work_order` I3 [BUG-3225]
- **Kind:** bug
- **Expect:** xfail BUG-3225
- **Fails today on:** Then 1 (no error: a draft is made for the completed order)

**Given**
1. O = order "1", but completed, outside.

**When**
- `svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work order is completed"`.
4. unchanged: unchanged(O).
5. nothing written: nothing written.

### WOS-I-14 — a voided order with an invoice linked never gets a second one (today and after the fix)
- **Rules:** `create_invoice_for_work_order` I2, I3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but voided, outside.
2. V = inv(O), but voided-inv, linked.

**When**
- `svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`, inside `pytest.raises(HTTPException) as exc`.

**Then**
1. raises: `exc.value.status_code in (400, 409)`.
2. count: `account_invoices` rows with `order_id == O.id`: exactly 1.
3. unchanged: unchanged(O).

### WOS-I-15 — a voided order with an invoice linked gets the "voided" 400, not the 409
- **Rules:** `create_invoice_for_work_order` I3 (checked before I2) [BUG-3225]
- **Kind:** bug
- **Expect:** xfail BUG-3225
- **Fails today on:** Then 1 (the status is 409)

**Given**
1. O = order "1", but voided, outside.
2. V = inv(O), but voided-inv, linked.

**When**
- `svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`, inside `pytest.raises(HTTPException) as exc`.

**Then**
1. raises: `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Work order is voided"`.

### WOS-I-16 — a completed order with an invoice linked gets the "completed" 400, not the 409
- **Rules:** `create_invoice_for_work_order` I3 (checked before I2) [BUG-3225]
- **Kind:** bug
- **Expect:** xfail BUG-3225
- **Fails today on:** Then 1 (the status is 409)

**Given**
1. O = order "1", but completed, outside.
2. V = inv(O), but confirmed, linked.

**When**
- `svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`, inside `pytest.raises(HTTPException) as exc`.

**Then**
1. raises: `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Work order is completed"`.

### WOS-I-17 — a completed order with its confirmed invoice never gets a second one (today and after the fix)
- **Rules:** `create_invoice_for_work_order` I2, I3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but completed, outside.
2. V = inv(O), but confirmed, linked.

**When**
- `svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`, inside `pytest.raises(HTTPException) as exc`.

**Then**
1. raises: `exc.value.status_code in (400, 409)`.
2. count: `account_invoices` rows with `order_id == O.id`: exactly 1.
3. unchanged: unchanged(V).

### WOS-I-18 — no account: 422, nothing written, the extra row is gone
- **Rules:** `create_invoice_for_work_order` I4, Errors row I4; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1".
2. X.

**When**
- `svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail == NOACC`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. unchanged: unchanged(O).
7. nothing written: nothing written.
8. committed: x_gone.

### WOS-I-19 — account id 0 counts as no account: 422
- **Rules:** `create_invoice_for_work_order` I4
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. O = order "1".
2. After the commit point: `O.account_id = 0` in memory only (not flushed).

**When**
- `svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail == NOACC`.
4. count: `account_invoices` rows with `order_id == O.id`: exactly 0.

### WOS-I-20 — an account and no cost: 422, no invoice
- **Rules:** `create_invoice_for_work_order` I4a, Errors row I4a [BUG-3228]
- **Kind:** bug
- **Expect:** xfail BUG-3228
- **Fails today on:** Then 1 (no error: a 0.00 draft showing `paid` is made — verified)

**Given**
1. O = order "1", but outside, `cost None`.
2. X.

**When**
- `svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail == NOCOST`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. session: session clean.
6. unchanged: unchanged(O).
7. nothing written: nothing written.
8. committed: x_gone.

### WOS-I-21 — an account and a cost of 0.00: 422, no invoice
- **Rules:** `create_invoice_for_work_order` I4a [BUG-3228]
- **Kind:** bug
- **Expect:** xfail BUG-3228
- **Fails today on:** Then 1 (no error: a 0.00 draft is made)

**Given**
1. O = order "1", but outside, `cost Decimal("0.00")`.

**When**
- `svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail == NOCOST`.
4. unchanged: unchanged(O).
5. nothing written: nothing written.

### WOS-I-22 — an account and a negative cost: 422, no invoice
- **Rules:** `create_invoice_for_work_order` I4a [BUG-3228]
- **Kind:** bug
- **Expect:** xfail BUG-3228
- **Fails today on:** Then 1 (no error: a draft with a -5.00 line is made)

**Given**
1. O = order "1", but outside, `cost Decimal("-5.00")` (inserted directly; `work_orders.cost` has no check constraint, spec Facts G6).

**When**
- `svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail == NOCOST`.
4. unchanged: unchanged(O).
5. nothing written: nothing written.

### WOS-I-23 — a cost of 0.01 is enough (today and after the fix)
- **Rules:** `create_invoice_for_work_order` I4a, I8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but outside, `cost Decimal("0.01")`.

**When**
- `result = svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.invoice_id is not None`.
2. committed: `[(i.unit_price, i.line_subtotal) for i in LINES(result.invoice_id)] == [(Decimal("0.01"), Decimal("0.01"))]`.
3. committed: the `account_invoices` row with `id == result.invoice_id` has `invoice_amount == Decimal("0.01")`.

### WOS-I-24 — neither account nor cost: the account is asked for first (today and after the fix)
- **Rules:** `create_invoice_for_work_order` I4, I4a (order)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1", but `cost None`.

**When**
- `svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail == NOACC`.
4. nothing written: nothing written.

### WOS-I-25 — a deleted account: the invoice manager's 400 passes unchanged
- **Rules:** `create_invoice_for_work_order` I7
- **Kind:** error
- **Expect:** pass

**Given**
1. AD = `Account(workspace_id=W1.id, name="Gone Traders", is_active=True, is_deleted=True, allow_invoices=True)`.
2. O = order "1", but `account_id AD.id`.

**When**
- `svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot create invoice for deleted account"`.
4. unchanged: unchanged(O).
5. nothing written: nothing written.

### WOS-I-26 — an inactive account: the invoice manager's 400 passes unchanged
- **Rules:** `create_invoice_for_work_order` I7
- **Kind:** error
- **Expect:** pass

**Given**
1. AI = `Account(workspace_id=W1.id, name="Idle Traders", is_active=False, is_deleted=False, allow_invoices=True)`.
2. O = order "1", but `account_id AI.id`.

**When**
- `svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot create invoice for inactive account"`.
4. nothing written: nothing written.

### WOS-I-27 — an account that does not allow invoices: 403 passes unchanged
- **Rules:** `create_invoice_for_work_order` I7
- **Kind:** error
- **Expect:** pass

**Given**
1. AN = `Account(workspace_id=W1.id, name="Cash Only", is_active=True, is_deleted=False, allow_invoices=False)`.
2. O = order "1", but `account_id AN.id`.

**When**
- `svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "Invoices are not allowed for this account"`.
4. nothing written: nothing written.

### WOS-I-28 — a W2 account becomes the 422 "not found in this workspace", the 404 as its cause
- **Rules:** `create_invoice_for_work_order` I7, Errors row I7; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order "1", but `account_id A9.id`.

**When**
- `svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail == ACC404`.
4. raises: `isinstance(exc.value.__cause__, HTTPException)`, `exc.value.__cause__.status_code == 404`.
5. nothing written: nothing written.

### WOS-I-29 — a W0 account becomes the same 422
- **Rules:** `create_invoice_for_work_order` I7; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O = order "1", but `account_id A0.id`.

**When**
- `svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail == ACC404`.
4. nothing written: nothing written.

### WOS-I-30 — the invoice date is the UTC date
- **Rules:** `create_invoice_for_work_order` I6 [BUG-3226]
- **Kind:** bug
- **Expect:** xfail BUG-3226
- **Fails today on:** Then 2 (the date is `date.today()`, the machine's real local date, not NOW's date)

**Given**
1. O = order "1", but outside.

**When**
- `result = svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`, with `patch("app.services.work_order_service.utcnow", return_value=NOW, create=True)` around it.

**Then**
1. returns: `result.invoice_id is not None`.
2. committed: the `account_invoices` row with `id == result.invoice_id` has `invoice_date == date(2026, 3, 10)`.

### WOS-I-31 — no invoice amount is sent to the invoice manager
- **Rules:** `create_invoice_for_work_order` I6 [BUG-627]
- **Kind:** bug
- **Expect:** xfail BUG-627
- **Author:** claude
- **Fails today on:** Then 2 (`invoice_amount` is sent as 0.00)

**Given**
1. O = order "1", but outside.

**When**
- `result = svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`, with `patch.object(svc.account_invoice_manager, "create_invoice", wraps=svc.account_invoice_manager.create_invoice) as ci` around it; then `SENT` = the one argument of `ci.call_args` (positional or keyword) whose class is named `AccountInvoiceCreate`.

**Then**
1. returns: `result.invoice_id is not None`.
2. mock called: `"invoice_amount" not in SENT.model_fields_set`.

### WOS-I-32 — a missing order: 404, the extra row is gone
- **Rules:** `create_invoice_for_work_order` I1, Errors row I1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. X.

**When**
- `svc.create_invoice_for_work_order(db, wo_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(MISSING)`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. nothing written: nothing written.
6. committed: x_gone.

### WOS-I-33 — another workspace's order (W2): 404, no invoice
- **Rules:** `create_invoice_for_work_order` I1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = order "9", but of W2, outside.

**When**
- `svc.create_invoice_for_work_order(db, wo_id=Z.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(Z.id)`.
4. nothing written: nothing written.

### WOS-I-34 — a soft-deleted order: 404, no invoice
- **Rules:** `create_invoice_for_work_order` I1 [BUG-1279] (manager pass-through)
- **Kind:** bug
- **Expect:** xfail BUG-1279
- **Fails today on:** Then 1 (no error: a draft is made for the deleted order)

**Given**
1. O = order "1", but outside, gone.

**When**
- `svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(O.id)`.
4. nothing written: nothing written.

### WOS-I-35 — a failing commit leaves no invoice and no link
- **Rules:** `create_invoice_for_work_order` I10; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but outside.

**When**
- `svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read O: `invoice_id is None`.
4. nothing written: nothing written.

### WOS-I-36 — a failing draft notice undoes the invoice and the link
- **Rules:** `create_invoice_for_work_order` I10; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but outside.
2. X.

**When**
- `svc.create_invoice_for_work_order(db, wo_id=O.id, workspace_id=W1.id, user_id=U2.id)`, inside **failing notify("notify_invoice_action")**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
3. unchanged: unchanged(O).
4. nothing written: nothing written.
5. committed: x_gone.

### WOS-I-37 — the order is read with a row lock before any check
- **Rules:** `create_invoice_for_work_order` I1 [BUG-3222]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-3222
- **Fails today on:** Then 2 (the order is read without `FOR UPDATE`)

**Given**
1. O = order "1", but outside.
2. `oid = O.id`.
3. Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `result = svc.create_invoice_for_work_order(db, wo_id=oid, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.invoice_id is not None`.
2. statement: lock(work_orders).
3. statement: lock first.

## `WorkOrderService.list_approvers`

### WOS-LA-01 — returns the manager's approver tuples; neither commits nor rolls back
- **Rules:** `list_approvers` A1; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1".
2. R1 = approver(O, U1).
3. R2 = approver(O, U2).
4. X.

**When**
- spies: `result = svc.list_approvers(db, wo_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `{r.id: (p.id, pos) for r, p, pos in result} == {R1.id: (U1.id, "Supervisor"), R2.id: (U2.id, None)}`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.

### WOS-LA-02 — another workspace's order: 404, no rollback
- **Rules:** `list_approvers` A1; TC6; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = order "9", but of W2.
2. X.

**When**
- spies: `svc.list_approvers(db, wo_id=Z.id, workspace_id=W1.id)`, inside `pytest.raises(HTTPException) as exc`.

**Then**
1. raises: `exc.value.status_code == 404`, `exc.value.detail == NF(Z.id)`.
2. mock called: `rb.call_count == 0`.
3. session: `X in db`.

## `WorkOrderService.approval_summary_for`

### WOS-AS-01 — one of two approved: (1, 2, False); neither commits nor rolls back
- **Rules:** `approval_summary_for` A2; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1".
2. approver(O, U2), but approved.
3. approver(O, U3).
4. X.

**When**
- spies: `result = svc.approval_summary_for(db, wo_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (1, 2, False)`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.

### WOS-AS-02 — no approvers: 0 of 0, met
- **Rules:** `approval_summary_for` A2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order "1".

**When**
- `result = svc.approval_summary_for(db, wo_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (0, 0, True)`.

### WOS-AS-03 — a W0 order: 404
- **Rules:** `approval_summary_for` A2; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = order "0", but of W0.

**When**
- `svc.approval_summary_for(db, wo_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NF(Z.id)`.

### WOS-AS-04 — a W2 order: 404, no rollback
- **Rules:** `approval_summary_for` A2; TC6; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = order "9", but of W2.
2. X.

**When**
- spies: `svc.approval_summary_for(db, wo_id=Z.id, workspace_id=W1.id)`, inside `pytest.raises(HTTPException) as exc`.

**Then**
1. raises: `exc.value.status_code == 404`, `exc.value.detail == NF(Z.id)`.
2. mock called: `rb.call_count == 0`.
3. session: `X in db`.

## `WorkOrderService.add_approver`

### WOS-AA-01 — the approver is added and committed; the new approver is told
- **Rules:** `add_approver` A3, A4; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1".

**When**
- `result = svc.add_approver(db, wo_id=O.id, user_id=U3.id, workspace_id=W1.id, assigned_by=U2.id, approver_slot="QA")`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `isinstance(result, WorkOrderApprover)`, `result.user_id == U3.id`.
3. committed: the `work_order_approvers` row with `id == result.id` has `work_order_id == O.id`, `assigned_by == U2.id`, `approver_slot == "QA"`.
4. committed: `[(n.recipient_user_id, n.notification_type) for n in notes() if n.recipient_user_id == U3.id] == [(U3.id, "approval_assigned")]`.

### WOS-AA-02 — ready order: the new approver is assigned, the other pending approver is reminded
- **Rules:** `add_approver` A4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1".
2. approver(O, U2).

**When**
- `result = svc.add_approver(db, wo_id=O.id, user_id=U3.id, workspace_id=W1.id, assigned_by=U1.id)`.

**Then**
1. returns: `result.user_id == U3.id`.
2. committed: `sorted((n.recipient_user_id, n.notification_type) for n in notes()) == sorted([(U3.id, "approval_assigned"), (U2.id, "approval_pending")])`.

### WOS-AA-03 — order not ready: the new approver is assigned, the creator gets the gap notice
- **Rules:** `add_approver` A4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but `title "   "` (whitespace only; `factory_id` is NOT NULL, Facts Constraints).

**When**
- `result = svc.add_approver(db, wo_id=O.id, user_id=U3.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. returns: `result.user_id == U3.id`.
2. committed: `sorted((n.recipient_user_id, n.notification_type) for n in notes()) == sorted([(U3.id, "approval_assigned"), (U1.id, "section_confirm")])`.
3. committed: the creator's row: `"Work order setup is incomplete" in n.preview` (contains, the gap text).

### WOS-AA-04 — a duplicate approver: 409 passes unchanged, the extra row is gone
- **Rules:** `add_approver` A3; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1".
2. approver(O, U3).
3. X.

**When**
- `svc.add_approver(db, wo_id=O.id, user_id=U3.id, workspace_id=W1.id, assigned_by=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "User is already an approver for this order"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. nothing written: nothing written.
7. committed: x_gone.

### WOS-AA-05 — a suspended member: 400 passes unchanged, nobody told
- **Rules:** `add_approver` A3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1".

**When**
- `svc.add_approver(db, wo_id=O.id, user_id=U4.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == NOTMEMBER`.
4. nothing written: nothing written.

### WOS-AA-06 — a completed order: 400 passes unchanged
- **Rules:** `add_approver` A3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but completed.

**When**
- `svc.add_approver(db, wo_id=O.id, user_id=U3.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work order is completed"`.
4. nothing written: nothing written.

### WOS-AA-07 — a started order takes no new approver
- **Rules:** `add_approver` A3 [BUG-2931] (manager pass-through)
- **Kind:** bug
- **Expect:** xfail BUG-2931
- **Fails today on:** Then 1 (no error: the approver is added and told)

**Given**
1. O = order "1", but started.

**When**
- `svc.add_approver(db, wo_id=O.id, user_id=U3.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == STARTED`.
4. nothing written: nothing written.

### WOS-AA-08 — a failing commit leaves no approver and no notification
- **Rules:** `add_approver` A3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1".

**When**
- `svc.add_approver(db, wo_id=O.id, user_id=U3.id, workspace_id=W1.id, assigned_by=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `work_order_approvers` rows with `work_order_id == O.id`: exactly 0.
4. count: `notes() == []`.

### WOS-AA-09 — a failing approver notification undoes the add
- **Rules:** `add_approver` A4; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1".
2. X.

**When**
- `svc.add_approver(db, wo_id=O.id, user_id=U3.id, workspace_id=W1.id, assigned_by=U2.id)`, inside **failing notify("handle_add_approver")**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
3. count: `work_order_approvers` rows with `work_order_id == O.id`: exactly 0.
4. nothing written: nothing written.
5. committed: x_gone.

## `WorkOrderService.remove_approver`

### WOS-RA-01 — the approver is removed and committed; returns None; nobody told even when approvals become met
- **Rules:** `remove_approver` A5
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but `approved_by None`, `approved_at None`.
2. R3 = approver(O, U3).
3. approver(O, U2), but approved.

**When**
- `result = svc.remove_approver(db, wo_id=O.id, user_id=U3.id, workspace_id=W1.id, performed_by=U2.id)`.

**Then**
1. returns: `result is None`.
2. committed: `work_order_approvers` rows with `id == R3.id`: exactly 0.
3. committed: `notes() == []`.

### WOS-RA-02 — not an approver: 404 passes unchanged, the extra row is gone
- **Rules:** `remove_approver` A5; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1".
2. X.

**When**
- `svc.remove_approver(db, wo_id=O.id, user_id=U3.id, workspace_id=W1.id, performed_by=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Approver not found"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. committed: x_gone.

### WOS-RA-03 — a started order keeps its approvers
- **Rules:** `remove_approver` A5 [BUG-2931] (manager pass-through)
- **Kind:** bug
- **Expect:** xfail BUG-2931
- **Fails today on:** Then 1 (no error: the approver is removed)

**Given**
1. O = order "1", but started.
2. R3 = approver(O, U3).

**When**
- `svc.remove_approver(db, wo_id=O.id, user_id=U3.id, workspace_id=W1.id, performed_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == STARTED`.
4. unchanged: unchanged(R3).

### WOS-RA-04 — a failing commit keeps the approver
- **Rules:** `remove_approver` A5; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1".
2. R3 = approver(O, U3).

**When**
- `svc.remove_approver(db, wo_id=O.id, user_id=U3.id, workspace_id=W1.id, performed_by=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(R3).

## `WorkOrderService.approve_as_me`

### WOS-AP-01 — the approval is recorded and committed; no invoice, nobody told even when the order becomes ready
- **Rules:** `approve_as_me` A6, A7; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but outside, `approved_by None`, `approved_at None`.
2. R2 = approver(O, U2).

**When**
- `result = svc.approve_as_me(db, wo_id=O.id, user_id=U2.id, workspace_id=W1.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == R2.id`.
3. committed: re-read R2: `approved is True`, `approved_at == NOW`.
4. committed: `account_invoices` rows with `order_id == O.id`: exactly 0.
5. committed: `notes() == []`.

### WOS-AP-02 — not an approver: 403 passes unchanged, the extra row is gone
- **Rules:** `approve_as_me` A6; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1".
2. X.

**When**
- `svc.approve_as_me(db, wo_id=O.id, user_id=U2.id, workspace_id=W1.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "You are not an assigned approver for this order"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. committed: x_gone.

### WOS-AP-03 — a started order takes no approval
- **Rules:** `approve_as_me` A6 [BUG-2931] (manager pass-through)
- **Kind:** bug
- **Expect:** xfail BUG-2931
- **Fails today on:** Then 1 (no error: the approval is stored)

**Given**
1. O = order "1", but started.
2. R2 = approver(O, U2).

**When**
- `svc.approve_as_me(db, wo_id=O.id, user_id=U2.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == STARTED`.
4. unchanged: unchanged(R2).

### WOS-AP-04 — approving again changes nothing
- **Rules:** `approve_as_me` A6 [BUG-2917] (manager pass-through)
- **Kind:** bug
- **Expect:** xfail BUG-2917
- **Fails today on:** Then 2 (`approved_at` is re-stamped to NOW)

**Given**
1. O = order "1", but `approved_by U2.id`.
2. R2 = approver(O, U2), but approved.

**When**
- `result = svc.approve_as_me(db, wo_id=O.id, user_id=U2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == R2.id`, `result.approved is True`.
2. committed: re-read R2: `approved_at == T0`.
3. event: `ev(O) == []`.

### WOS-AP-05 — a failing commit leaves the approval unrecorded
- **Rules:** `approve_as_me` A6; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1".
2. R2 = approver(O, U2).

**When**
- `svc.approve_as_me(db, wo_id=O.id, user_id=U2.id, workspace_id=W1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read R2: `approved is False`, `approved_at is None`.

## `WorkOrderService.unapprove_as_me`

### WOS-UA-01 — the approval is withdrawn and committed; nobody told
- **Rules:** `unapprove_as_me` A6, A7; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but `approved_by U2.id`.
2. R2 = approver(O, U2), but approved.

**When**
- `result = svc.unapprove_as_me(db, wo_id=O.id, user_id=U2.id, workspace_id=W1.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == R2.id`.
3. committed: re-read R2: `approved is False`.
4. committed: `notes() == []`.

### WOS-UA-02 — a completed order: 400 passes unchanged, the extra row is gone
- **Rules:** `unapprove_as_me` A6; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but completed.
2. R2 = approver(O, U2), but approved.
3. X.

**When**
- `svc.unapprove_as_me(db, wo_id=O.id, user_id=U2.id, workspace_id=W1.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Work order is completed"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. unchanged: unchanged(R2).
7. committed: x_gone.

### WOS-UA-03 — a failing commit keeps the approval
- **Rules:** `unapprove_as_me` A6; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but `approved_by U2.id`.
2. R2 = approver(O, U2), but approved.

**When**
- `svc.unapprove_as_me(db, wo_id=O.id, user_id=U2.id, workspace_id=W1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read R2: `approved is True`, `approved_at == T0`.

## `WorkOrderService.list_events`

### WOS-N-01 — returns the order's events newest first with their performer; neither commits nor rolls back
- **Rules:** `list_events` N1; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1".
2. E1 = event(O, "note", None, T0), but `performed_by U2.id`.
3. E2 = event(O, "note", None, T1).
4. X.

**When**
- spies: `result = svc.list_events(db, wo_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `[(e.id, p.id if p else None) for e, p in result] == [(E2.id, None), (E1.id, U2.id)]`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.

### WOS-N-02 — another workspace's order: 404, no rollback
- **Rules:** `list_events` N1; TC6; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = order "9", but of W2.
2. X.

**When**
- spies: `svc.list_events(db, wo_id=Z.id, workspace_id=W1.id)`, inside `pytest.raises(HTTPException) as exc`.

**Then**
1. raises: `exc.value.status_code == 404`, `exc.value.detail == NF(Z.id)`.
2. mock called: `rb.call_count == 0`.
3. session: `X in db`.

## `WorkOrderService.add_item`

### WOS-AI-01 — a line is added and committed; a linked draft invoice is not touched; nobody told
- **Rules:** `add_item` M1, M2; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but outside, `uses_inventory True`.
2. V = inv(O), linked.
3. invl(V, "100.00").

**When**
- `result = svc.add_item(db, item_in=ITEM(O), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `isinstance(result, WorkOrderItem)`, `result.id is not None`.
3. committed: the `work_order_items` row with `id == result.id` has `work_order_id == O.id`, `item_id == I1.id`, `quantity == Decimal("2")`, `created_by == U2.id`.
4. unchanged: unchanged(V).
5. committed: `[(i.description, i.unit_price) for i in LINES(V.id)] == [("Old line", Decimal("100.00"))]`.
6. committed: `notes() == []`.

### WOS-AI-02 — a line that clears approvals writes no notification
- **Rules:** `add_item` M2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but `uses_inventory True`.
2. R3 = approver(O, U3), but approved.

**When**
- `result = svc.add_item(db, item_in=ITEM(O), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. committed: re-read R3: `approved is False`.
3. committed: `notes() == []`.

### WOS-AI-03 — the manager's 400 passes unchanged, the extra row is gone
- **Rules:** `add_item` M1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1".
2. X.

**When**
- `svc.add_item(db, item_in=ITEM(O), workspace_id=W1.id, user_id=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "This work order does not use stock items"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. nothing written: nothing written.
7. committed: x_gone.

### WOS-AI-04 — a stock refusal on a started order saves nothing
- **Rules:** `add_item` M1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. S(I2, 2, Decimal("5.00")).
2. O = order "1", but started, `uses_inventory True`.

**When**
- `svc.add_item(db, item_in=ITEM(O, item_id=I2.id, quantity=Decimal("5")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Insufficient stock (2 available, 5 requested)"`.
4. nothing written: nothing written.

### WOS-AI-05 — a failing commit leaves no line
- **Rules:** `add_item` M1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but `uses_inventory True`.

**When**
- `svc.add_item(db, item_in=ITEM(O), workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `work_order_items` rows with `work_order_id == O.id`: exactly 0.

## `WorkOrderService.update_item`

### WOS-UI-01 — a line edit is committed and returned re-read
- **Rules:** `update_item` M1; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but `uses_inventory True`.
2. L = line(O, I1, "2").

**When**
- `result = svc.update_item(db, item_id=L.id, item_in=WorkOrderItemUpdate(quantity=Decimal("3")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == L.id`.
3. committed: re-read L: `quantity == Decimal("3")`, `updated_by == U2.id`.

### WOS-UI-02 — a line edit that clears approvals writes no notification and touches no invoice
- **Rules:** `update_item` M2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order "1", but outside, `uses_inventory True`.
2. R3 = approver(O, U3), but approved.
3. L = line(O, I1, "2").
4. V = inv(O), linked.

**When**
- `result = svc.update_item(db, item_id=L.id, item_in=WorkOrderItemUpdate(quantity=Decimal("3")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == L.id`.
2. committed: re-read R3: `approved is False`.
3. committed: `notes() == []`.
4. unchanged: unchanged(V).

### WOS-UI-03 — a missing line: 404 passes unchanged, the extra row is gone
- **Rules:** `update_item` M1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. X.

**When**
- `svc.update_item(db, item_id=MISSING, item_in=WorkOrderItemUpdate(quantity=Decimal("3")), workspace_id=W1.id, user_id=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Work order item not found"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. committed: x_gone.

### WOS-UI-04 — a failing commit keeps the old quantity
- **Rules:** `update_item` M1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but `uses_inventory True`.
2. L = line(O, I1, "2").

**When**
- `svc.update_item(db, item_id=L.id, item_in=WorkOrderItemUpdate(quantity=Decimal("3")), workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read L: `quantity == Decimal("2")`.

## `WorkOrderService.remove_item`

### WOS-RI-01 — the line is removed and committed; the line is returned without a refresh; nobody told
- **Rules:** `remove_item` M3, M4
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but outside, `uses_inventory True`.
2. L = line(O, I1, "2").
3. V = inv(O), linked.

**When**
- `result = svc.remove_item(db, item_id=L.id, workspace_id=W1.id, user_id=U2.id)`, with `patch.object(db, "refresh", wraps=db.refresh) as rf` around it.

**Then**
1. returns: `result.id == L.id`, `result.is_deleted is True`, `result.deleted_by == U2.id`, `result.work_order_id == O.id`.
2. mock called: `rf.call_count == 0`.
3. committed: re-read L: `is_deleted is True`.
4. committed: `notes() == []`.
5. unchanged: unchanged(V).

### WOS-RI-02 — a missing line: 404, the extra row is gone
- **Rules:** `remove_item` M3; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. X.

**When**
- `svc.remove_item(db, item_id=MISSING, workspace_id=W1.id, user_id=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Work order item not found"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. committed: x_gone.

### WOS-RI-03 — a failing commit keeps the line
- **Rules:** `remove_item` M3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. O = order "1", but `uses_inventory True`.
2. L = line(O, I1, "2").

**When**
- `svc.remove_item(db, item_id=L.id, workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read L: `is_deleted is False`.

## `WorkOrderService.get_items`

### WOS-GI-01 — returns the order's live lines; neither commits nor rolls back
- **Rules:** `get_items` M5; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order "1", but `uses_inventory True`.
2. L1 = line(O, I1, "1").
3. line(O, I2, "1"), but gone.
4. L3 = line(O, I1, "3").
5. X.

**When**
- spies: `result = svc.get_items(db, wo_id=O.id, workspace_id=W1.id)`.

**Then**
1. returns: `{i.id for i in result} == {L1.id, L3.id}`, `len(result) == 2` (as a set: BUG-1272).
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.

### WOS-GI-02 — another workspace's order: 404, no rollback
- **Rules:** `get_items` M5; TC6; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = order "9", but of W2.
2. X.

**When**
- spies: `svc.get_items(db, wo_id=Z.id, workspace_id=W1.id)`, inside `pytest.raises(HTTPException) as exc`.

**Then**
1. raises: `exc.value.status_code == 404`, `exc.value.detail == NF(Z.id)`.
2. mock called: `rb.call_count == 0`.
3. session: `X in db`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| E1, T1, U1, G1, L1, B1, SE1, X1, S1, C10, P6, V6, A1–A3, A5, A6, N1, M1–M5 details (manager rules and errors, BUG-1206, 2912–2918, 2922, 2925, 2927–2931) | `work_order_manager.cases.md` | every manager rule; here only one pass-through per path |
| SE3 the fix location (`sync_recurrence_drafts_for_machine`) | `work_order_manager.cases.md` | the manager's own card for the invoice step once BUG-3227 lands there |
| C7, I6, I7, I8, V4, X2 invoice-manager details (`create_invoice`, `confirm_invoice`, `delete_invoice`, `sync_items_from_list`; BUG-625, 627, 628, 639, 2730) | `account_invoice_manager.cases.md` | amounts, events, account refusals, order-link checks |
| U2, A4, C7, I10 notification texts and recipient rules (`notify_invoice_action` R2–R5, `notify_section_confirm_needed`, `handle_add_approver`) | `approval_notification_service.cases.md` | previews, gap text, recipient sets |
| BUG-3222 / BUG-2916 concurrency (two sessions racing create-invoice / void / complete / complete-as-planned) | integration tests | the loser sees the new state and gets the normal error; unit cards check only the `FOR UPDATE` read |
| BUG-2918 blank void note | `WorkOrderVoidRequest` schema (`work_order_manager.cases.md` V-12 … V-14), `POST /work-orders/{id}/void/` | 422 for a blank note |
| L1 / SB endpoint limits (`1 ≤ limit ≤ 1000` list, `1 ≤ limit ≤ 100` sheet, `skip ≥ 0`); C11 endpoint admits only `IDLE` / `OFF` | `GET /work-orders/`, `GET /work-orders/sheet/`, `POST /work-orders/{id}/complete/` | 422 outside the range / other values |
| Permission checks (any member can complete, void, delete, create the invoice, add approvers) | `docs/future/permissions.md` | not a rule today |

## Spec gaps
None open. Revision 1's gaps were closed by the spec's gap log (2026-11-22):
- 1 → G1 / Facts L1: `FOR UPDATE`, `OF work_orders` also accepted, never `NOWAIT` / `SKIP LOCKED`; lock(work_orders) regex widened (C-27, P-21, V-18, I-37).
- 2 → G2: patch target `app.services.work_order_service.<name>`; U-08, AA-09, I-36 unmarked.
- 3 → G3: patch target `app.services.work_order_service.utcnow`, `create=True` until the fix; I-30 unmarked.
- 4 → G4: `_WorkOrderEnrichment` importable, fields `assignee_map`, `completer_map`, `profile_names`; R-05, R-06 as written.
- 5 → G5: another workspace's linked invoice left alone in B3 and SE3; B-11 extended, B-13 and SE-10 added.
- 6 → G6: no check constraint on `work_orders.cost`; I-22 inserts `-5.00` directly.

Revision 2's executor round (notes DISCREPANCY-1…7), closed by the spec's gap log G7–G10 and the coordinator (2026-11-22):
- DISCREPANCY-1 → `X in db` on read cards (Conventions "X"); R-14 `X in db`, `not db.new`.
- DISCREPANCY-2 / G9 → R-03 rebuilt on W6 (a soft-deleted type keeps its name); `work_order_type_id` NOT NULL.
- DISCREPANCY-3 / G8 → U-07 expects the title unchanged (U4a).
- DISCREPANCY-4 / G10 → SB-01…03 read `b.approvers.approvers[0]` / `b.approvers.summary`.
- DISCREPANCY-5 → SB-01, SB-04, GI-01 compare lines as sets (BUG-1272).
- DISCREPANCY-6 / G9 → AA-03 uses `title "   "`, gap text `Work order setup is incomplete`.
- DISCREPANCY-7 / G7 → V-03 strict xfail BUG-3229 (V4a); V-19 pass companion; X-06, X-08, X-09, X-11 check the invoice id.
- G9 → `inventory` counted in **nothing written**; S-02 checks the `inventory` rows.

Revision 3's verifier round (`work_order_service.verify.md` findings 1–3, DISCREPANCY-8): no new gap; every fact needed (one `try` per write, `exclude_completed=False`, `@dataclass(frozen=True)`) is in the spec.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_load_work_order_enrichment` | W1 | LE-01 |
| | W2 | LE-02, LE-03, LE-04, LE-05 |
| | W3 | LE-06, LE-07 |
| | W4 | LE-08, LE-09, LE-10, LE-11, LE-12 |
| | reads (TC6) | LE-13 |
| `_WorkOrderEnrichment` | Facts G4 (frozen, fields) | LE-14 |
| `_to_work_order_response` | W5 | R-01, R-05 |
| | W6 | R-02, R-03, R-04 |
| | W7 | R-01, R-05, R-06 |
| | W8 | R-07, R-08, R-09 |
| | W9 | R-10, R-11, R-12, R-13 |
| | W10 | R-14 |
| `_to_work_order_responses` | W11 | RS-01 |
| | W12 | RS-02, RS-03 |
| `create_work_order` | E1 | E-01, E-02, E-03, E-04 |
| | E2 | E-01 |
| `create_work_order_from_template` | T1 | T-01, T-03, T-04 |
| | T2 | T-01, T-02 |
| `update_work_order` | U1 | U-01, U-09, U-10, U-11 |
| | U2 | U-02, U-03, U-04, U-05 |
| | U3 | U-01, U-06 |
| | U4 | U-07 |
| | U4a | U-07 |
| | U5 | U-08 |
| `get_work_order` | G1 | G-01 … G-06 |
| | G1 [BUG-1279] | G-07 |
| `list_work_orders` | L1 | L-01 … L-05 |
| `bulk_delete_future_recurrence_drafts` | B1 | B-01, B-03, B-04, B-06, B-11 |
| | B2 | B-01, B-02, B-10 |
| | B3 [BUG-3227] | B-05, B-07, B-09, B-10, B-12 (xfail); B-06, B-08, B-11, B-13 (pass) |
| | B4 | B-01 |
| `sheet_entry` | SE1 | SE-01, SE-03, SE-04, SE-05, SE-07 |
| | SE2 | SE-01, SE-02 |
| | SE3 [BUG-3227] | SE-06, SE-08 (xfail); SE-07, SE-09, SE-10 (pass) |
| `list_sheet_bundles` | SB1 | SB-01, SB-05, SB-09, SB-10, SB-13, SB-14 |
| | SB2 | SB-01, SB-02, SB-03, SB-04, SB-11 |
| | SB3 | SB-05, SB-06, SB-07, SB-08, SB-09 |
| | SB4 | SB-12 |
| `sheet_daily_counts` | SD1 | SD-01, SD-02, SD-03 |
| `delete_work_order` | X1 | X-01 … X-05, X-07, X-14 |
| | X2 [BUG-2923] | X-06, X-08 (xfail); X-07, X-14 (pass) |
| | X3 [BUG-2923] | X-09, X-11 (xfail); X-10, X-12, X-13 (pass) |
| | X4 | X-01 |
| `start_work_order` | S1 | S-01, S-02, S-03, S-04 |
| | S2 | S-01 |
| `complete_work_order` | C1 [BUG-2916] / Errors C1 | C-27 (xfail); C-24, C-25 |
| | C2 | C-04, C-05 |
| | C3 / Errors C3 | C-06, C-07 |
| | C4 / Errors C4 | C-08 |
| | C5 / Errors C5 | C-09, C-10 |
| | C6 / Errors C6 | C-11 |
| | C7 / Errors C7 | C-01, C-02, C-03; C-12 (xfail BUG-628) |
| | C8 | C-13 |
| | C9 | C-14, C-15 |
| | C10 / Errors C10 | C-01, C-16, C-17, C-26 |
| | C11 / Errors C11 | C-18, C-19, C-20, C-21, C-22 |
| | C12 | C-23 |
| `complete_work_order_as_planned` | P1 [BUG-3222] | P-21 (xfail); P-19 |
| | P2 | P-03 |
| | P3 [BUG-3223] | P-04, P-05, P-06 (xfail); P-07, P-08 (pass) |
| | P4 | P-01, P-02, P-09, P-10, P-11, P-12, P-15 |
| | P5 | P-07, P-13 |
| | P6 | P-01, P-08, P-14, P-15, P-16, P-18, P-20 |
| | P7 | P-17, P-18 |
| `void_work_order` | V1 [BUG-3222] / Errors V1 | V-18 (xfail); V-15, V-16 |
| | V2 [BUG-3224] / Errors V2 | V-12, V-14 (xfail); V-11, V-13 (pass) |
| | V3 | V-01 |
| | V4 / Errors V4 | V-02, V-05, V-19; V-04 (xfail BUG-639) |
| | V4a [BUG-3229] | V-03 (xfail); V-19 (pass) |
| | V5 | V-06, V-07, V-08, V-10 |
| | V5a [BUG-3224] / Errors V5a | V-09 (xfail); V-10 (pass) |
| | V6 / Errors V6 | V-01, V-03, V-17, V-19 |
| | V7 | V-01, V-02 |
| `create_invoice_for_work_order` | I1 [BUG-3222] / Errors I1 | I-37 (xfail); I-32, I-33; I-34 (xfail BUG-1279) |
| | I2 / Errors I2 | I-09, I-10, I-11, I-14, I-17 |
| | I3 [BUG-3225] / Errors I3 | I-12, I-13, I-15, I-16 (xfail); I-08, I-14, I-17 (pass) |
| | I4 / Errors I4 | I-18, I-19, I-24 |
| | I4a [BUG-3228] / Errors I4a | I-20, I-21, I-22 (xfail); I-23, I-24 (pass) |
| | I5 | I-06 |
| | I6 [BUG-3226] [BUG-627] | I-01, I-02, I-07; I-30 (xfail BUG-3226); I-31 (xfail BUG-627) |
| | I7 / Errors I7 | I-25, I-26, I-27, I-28, I-29 |
| | I8 | I-01, I-03, I-04, I-23 |
| | I9 | I-04 |
| | I10 | I-01, I-05, I-06, I-35, I-36 |
| `list_approvers` | A1 | LA-01, LA-02 |
| `approval_summary_for` | A2 | AS-01 … AS-04 |
| `add_approver` | A3 [BUG-2931] | AA-01, AA-04, AA-05, AA-06, AA-08; AA-07 (xfail) |
| | A4 | AA-01, AA-02, AA-03, AA-09 |
| `remove_approver` | A5 [BUG-2931] | RA-01, RA-02, RA-04; RA-03 (xfail) |
| `approve_as_me` / `unapprove_as_me` | A6 [BUG-2931] [BUG-2917] | AP-01, AP-02, AP-05, UA-01, UA-02, UA-03; AP-03 (xfail BUG-2931); AP-04 (xfail BUG-2917) |
| | A7 | AP-01, UA-01 |
| `list_events` | N1 | N-01, N-02 |
| `add_item` / `update_item` | M1 | AI-01, AI-03, AI-04, AI-05, UI-01, UI-03, UI-04 |
| | M2 | AI-01, AI-02, UI-02 |
| `remove_item` | M3 | RI-01, RI-02, RI-03 |
| | M4 | RI-01 |
| `get_items` | M5 | GI-01, GI-02 |
| Transaction contract | TC1, TC2 | E-01, T-01, U-01, B-01, SE-01, X-01, S-01, C-01, P-01, V-01, I-01, AA-01, RA-01, AP-01, UA-01, AI-01, UI-01, RI-01 |
| | TC3 (`X not in db`) | E-02, T-03, U-08, U-09, B-04, B-07, B-12, SE-03, SE-04, SE-08, X-02, X-08, X-09, S-02, C-06, C-08, C-12, C-16, C-22, C-24, P-04, P-07, P-14, P-17, P-19, V-05, V-09, V-11, V-15, I-09, I-12, I-18, I-20, I-32, I-36, AA-04, AA-09, RA-02, AP-02, UA-02, AI-03, UI-03, RI-02 |
| | TC3 (rollback spy) | E-02, T-03, U-09, B-04, SE-03, X-02, S-02, C-16, P-14, V-11, I-18, AA-04, RA-02, AP-02, UA-02, AI-03, UI-03, RI-02 |
| | TC4 | E-03, T-04, U-11, B-03, SE-05, X-05, S-04, C-26, P-20, V-17, I-35, AA-08, RA-04, AP-05, UA-03, AI-05, UI-04, RI-03 |
| | TC5 | E-04 |
| | TC6 | LE-13, R-14, RS-03, G-01, G-06, L-01, SB-12, SD-01, LA-01, LA-02, AS-01, AS-04, N-01, N-02, GI-01, GI-02; C-04, P-03 (no commit / rollback on early return) |
