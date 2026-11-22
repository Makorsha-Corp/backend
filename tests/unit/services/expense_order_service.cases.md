# Test cases — `app/services/expense_order_service.py`

> **Spec:** `tests/unit/services/expense_order_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 (2026-11-22) — spec Gap log G1–G10 closed. G10: the voided check now runs right after the locked read (C1, C3, C2, C4–C7; I1, I3, I2, I4): I-08 becomes a strict xfail BUG-3065 (400 `Expense order is voided`), new C-22 (voided and completed → 400, xfail BUG-3065) with pass companion C-23. G1: C-21, V-24, I-15 also pin the lock clause (`FOR UPDATE`, optionally `OF expense_orders`, one-table read). G2: new U-13, AA-08 (failing section / approver notification). G3: AA-03 checks the gap preview. G4: new H-07 (recent-summary fields, response class); H-04 checks `account_name`. G5/G8: D-01, AP-02, T-01 check `created_by`; new D-14 (keyword call); D-12 reads `invoice_data` by keyword. G6: RI-03 checks the detail; new RI-05 (W2 line). G7: R-10 checks the detail. G9: R-04 cites R2a (stays pass).
> **Revision:** 3 (2026-11-22) — spec Gap log G11–G12 (executor notes). G12: U-07, R-08, R-09 become strict xfail BUG-629 (fail on Then 1) and cite `_resync_draft_invoice` R4b; new U-14 (pass companion: a deleted new account is refused with 400 `Cannot assign invoice to deleted account`, edit rolled back). The 14 read cards (G-01, G-06, L-06, P-08, H-06, C-04, GI-01, GI-02, LA-01, LA-02, AS-01, AS-05, N-01, N-02) now check `X in db` (setup rows are flushed, so `db.new` is empty). G11: V-03 is xfail BUG-3070 (card fixed in 3a).
> **Revision:** 3a (2026-11-22) — V-03 becomes strict xfail BUG-3070 (fails today on Then 4), per spec G11.
> **Revision:** 4 (2026-11-22) — verifier findings 1–4 (`expense_order_service.verify.md`, NEEDS WORK). (1) TC3: every write-method card with X (42 cards) checks `X not in db` right after the raise, before any test rollback; one passing error card per write method (E-02, U-08, X-03, C-07, V-06, AI-05, UI-05, RI-03, I-02, AA-05, RA-04, AP-04, UA-02, T-04) also runs inside spies and checks `rb.call_count >= 1`. (2) V-10 asserts the void's event texts (reset reason, `invoice_voided` and `eo_voided` descriptions, `void_note` metadata, performer) in a passing card. (3) New P-09 (no filter: completed and voided orders listed) and H-08 (no filter: a voided order counted); the defaults are `_hub_filter_kwargs`'s (`exclude_complete=False`, `exclude_voided=False`), which P-1 / H-1 apply. (4) V-13's invoice carries `paid_amount 10.00`, `payment_status "partial"` to match its payment.
> **Counts:** 228 cases · 199 expected-to-pass · 29 expected-to-fail (bugs) · 9 deferred

## Reviewer summary
- **Per callable:** `create_expense_order` 4 · `update_expense_order` 14 (3 bug) · `get_expense_order` 6 · `list_expense_orders` 6 · `_hub_filter_kwargs` 7 · `list_expense_orders_page` 9 · `get_expense_order_hub_stats` 8 · `delete_expense_order` 7 (2 bug) · `complete_expense_order` 23 (6 bug) · `void_expense_order` 24 (8 bug) · `add_item` 7 · `update_item` 6 · `remove_item` 5 · `get_items` 2 · `_invoice_item_dicts` 11 · `_create_draft_invoice` 14 (2 bug) · `_resync_draft_invoice` 13 (2 bug) · `_sync_or_create_invoice` 11 · `create_invoice_for_expense_order` 15 (4 bug) · `list_approvers` 2 · `approval_summary_for` 5 (1 bug) · `add_approver` 8 · `remove_approver` 5 (1 bug) · `approve_as_me` 5 · `unapprove_as_me` 3 · `list_events` 2 · `create_expense_order_from_template` 6.
- **Depth:** full (skill step 1a): the service finalizes and deletes payable invoices, completes and voids orders. Manager rules are not re-tested; each manager or invoice-manager bug the service reaches gets a pass-through card (BUG-742, 755 ×2, 627, 628, 639); BUG-1193's service half is X-02.
- **Transaction contract:** every write has a commit card (`committed:` after a test-level rollback), at least one rollback card with an **uncommitted** extra workspace X that must be gone, and a failing-commit card; every refreshing write checks `loaded(result)`; TC5 once (E-04). The three flush-only helpers each get a spy card (D-13, R-13, Y-11). Every read checks no commit, no rollback and X still in the session (`X in db`), on success and on its 404. C-04 checks C2's "neither commit nor rollback".
- **Bugs (all strict):** BUG-3062 locks 3 (statement recorder, C-21, V-24, I-15) · BUG-3063 1 · BUG-3064 3 (schema) · BUG-3065 6 · BUG-3066 1 · BUG-3067 1 · BUG-3068 2 · BUG-3069 1 · BUG-1193 1 · BUG-629 3 (U-07, R-08, R-09) · pass-throughs 6 (BUG-627, 628, 639, 742, 755 ×2). Passing companions for what holds today and after the fix: C-07, I-07 (a voided order is still refused, loose on the text), I-08, V-09 (a draft with payment history is never deleted), V-14 (a confirmed invoice is never changed by the void), V-16 (void without invoice), V-20 (plain void note), RA-03 (summary met after removal), C-23 (a voided and completed order is never changed), U-14 (a deleted new account is refused and the edit undone).
- **Notable design choices:**
  - Concurrency is not simulated: the three lock cards check the emitted SQL (first read of `expense_orders` carries `FOR UPDATE`, optionally `OF expense_orders`, on a one-table read, sent before the first read of invoices / approvers). The race outcome is deferred to integration tests.
  - `Author: claude`: C-19 (forced notification failure: the only way to make the step after the confirm fail), D-12 (spy on `create_invoice` arguments for BUG-627: the outcome 0.00 is the same today), H-03, H-04 (compare with manager output). Patch targets are now stated by the spec (G2, G4).
  - Invoices of W0 / W2 linked to a W1 order are invalid data built on purpose (HR-16, legacy BUG-751).
  - BUG-3068 is tested through `update_expense_order` (where the spec places the check). Its other side (a voided invoice linked, or none: clearing allowed) depends on BUG-753 and is the manager's.
  - Check order (G10): the voided check runs right after the locked read, before C2 and before I2. C-22 / I-08 cover the overlap; C-23 is the pass companion that holds either way.
- **Needs a decision:** none (all spec gaps closed in Revisions 2 and 3; Revision 4 opens none).

## Conventions for this module

**IDs.** `EOS` = `app/services/expense_order_service.py`. `E` create · `U` update · `G` get · `L` list_expense_orders · `K` _hub_filter_kwargs · `P` list_expense_orders_page · `H` hub stats · `X` delete · `C` complete · `V` void (incl. `ExpenseOrderVoidRequest` schema) · `AI` add_item · `UI` update_item · `RI` remove_item · `GI` get_items · `S` _invoice_item_dicts · `D` _create_draft_invoice · `R` _resync_draft_invoice · `Y` _sync_or_create_invoice · `I` create_invoice_for_expense_order · `LA` list_approvers · `AS` approval_summary_for · `AA` add_approver · `RA` remove_approver · `AP` approve_as_me · `UA` unapprove_as_me · `N` list_events · `T` from template.

**Imports.** `svc` = `expense_order_service` (`from app.services.expense_order_service import ExpenseOrderService, expense_order_service`). `mgr` = `svc.manager`. Models from `app.models.<snake_case>`: `ExpenseOrder`, `ExpenseOrderItem`, `ExpenseOrderApprover`, `ExpenseOrderEvent`, `AccountInvoice`, `InvoiceItem`, `InvoiceEvent`, `InvoicePayment`, `Account`, `Department`, `Notification`, `OrderTemplate`, `OrderTemplateItem`, `WorkspaceMember`, `WorkspaceAuditLog`, `Workspace`. Schemas from `app.schemas.expense_order`: `ExpenseOrderCreate`, `ExpenseOrderUpdate`, `ExpenseOrderItemCreate`, `ExpenseOrderItemUpdate`, `ExpenseOrderVoidRequest`, `ExpenseOrderFromTemplateCreate`, `ExpenseOrderListResponse`. `HTTPException` (fastapi), `pydantic.ValidationError`, `inspect`, `select`, `func`, `text` (sqlalchemy), `patch` (unittest.mock), `Decimal`, `date`, `datetime`, `uuid`. Every call: `db` first, the rest by keyword. `result` = what the When returns.

**Fixed values.** MISSING = `999999999`. TAG = `uuid.uuid4().hex[:8]`, once per test. T0 = `datetime(2026, 9, 1, 8, 0)`, T1 = `datetime(2026, 9, 2, 9, 0)`, T2 = `datetime(2026, 9, 3, 10, 0)`. Long dashes are U+2014; copy them. NOTMET = `"Required approvals are not met"`. NOINV = `"No invoice linked — set an account so a draft invoice can be created, then try again"`. VOIDINV = `"Linked invoice was voided — cannot complete this order"`. RESETMSG = `"Approvals were reset — order details changed; re-approve when ready"`. RESETVOID = `"Cleared approvals — expense order voided (1 approval(s) cleared)"`. SKIPMSG = `"Approvals met but no account set — set an account to generate the invoice"`. DRAFTP = `"draft|Linked payable invoice is in draft — confirm when details look correct"`. CLEARACC = `"An invoice is linked to this order — choose another account instead of clearing it"`. PAYHIST = `"Invoice has payment history — confirm and void it instead"`. FINAL = `"This order's invoice is already finalized. Void the invoice on the invoice page first, then void the order."`.

**Time.** In every test `app.services.expense_order_service.utcnow` and `app.managers.expense_order_manager.utcnow` are patched to return **NOW = `datetime(2026, 9, 27, 12, 0, 0)`**, with the tz-awareness of the real `app.utils.time.utcnow`. Nothing else is mocked unless a card says so.

**Standing rows** (every test, this order, each flushed, no Given line):
1. W0, W1, W2 = `make_workspace(db)` ×3 (`W0.id < W1.id < W2.id`). U1 … U5 = `make_profile(db, name=…)`: `"Abid Hasan"`, `"Karim Ali"`, `"Rahim Uddin"`, `"Nadia Khan"`, `"Esha Roy"`.
2. `WorkspaceMember(workspace_id=W1.id, user_id=…, role="member", status=…)`: U1, U2, U3, U4 `"active"`; U5 `"inactive"`. U1 creates every Given row; **U2 is the acting user**.
3. A0, A1, A2, A9 = `Account(workspace_id=…, name=…, is_active=True, is_deleted=False, allow_invoices=True)`: A0 of W0 `"Zeta West"`, A1 of W1 `"Acme Supplies"`, A2 of W1 `"Beta Traders"`, A9 of W2 `"Xeno Foreign"`. DEP1 = `Department(workspace_id=W1.id, name="Admin", created_by=U1.id)`.

**Given rows.** Inserted directly (never through `svc`), flushed one at a time in the order written. After "but" a line lists every column that differs. A line written as code is a step to run exactly.
- **acct "n"** = `Account(workspace_id=W1.id, name="n", is_active=True, is_deleted=False, allow_invoices=True)`.
- **eo "n"** = `ExpenseOrder(workspace_id=W1.id, expense_number=f"EXP-{TAG}-n", expense_category="other", expense_date=date(2026, 9, 1), description="Office rent", account_id=A1.id, subtotal=Decimal("0.00"), total_amount=Decimal("0.00"), voided=False, created_by=U1.id)`; `cost_center_id`, `due_date`, `required_approvals`, `invoice_id`, `completed_at`, `completed_by`, `updated_by`, `voided_at`, `voided_by`, `void_note`, `items_updated_at` NULL. **of W0** / **of W2** = `workspace_id` W0 / W2, `account_id` A0 / A9. **waived** = `required_approvals 0`. **completed** = `completed_at T0`, `completed_by U1.id`, `updated_by U1.id`. **voided** = `voided True`, `void_note "Duplicate"`, `voided_at T0`, `voided_by U1.id`.
- **line(E, k, s)** = `ExpenseOrderItem(workspace_id=E.workspace_id, expense_order_id=E.id, line_number=k, description=f"Line {k}", quantity=Decimal("1"), unit=None, unit_price=Decimal(s), line_subtotal=Decimal(s))`.
- **appr(E, U)** = `ExpenseOrderApprover(workspace_id=E.workspace_id, expense_order_id=E.id, user_id=U.id, assigned_by=U1.id, approved=False, approved_at=None, assigned_at=T0)`. **approved** = `approved True`, `approved_at T0`.
- **inv(E)** = `AccountInvoice(workspace_id=W1.id, account_id=A1.id, invoice_type="payable", invoice_status="draft", payment_status="unpaid", invoice_amount=Decimal("0.00"), paid_amount=Decimal("0.00"), invoice_date=date(2026, 9, 1), allow_payments=True, receiving_started=False, created_by=U1.id, order_type="expense_order", order_id=E.id)`; `description`, `notes`, `due_date`, `invoice_number`, `vendor_invoice_number`, `payment_locked_reason`, `void_note` NULL. **inv(None)** = the same with `order_type`, `order_id` NULL. **confirmed** = `invoice_status "confirmed"`, `invoice_amount Decimal("100.00")`. **voided-inv** = `invoice_status "voided"`, `void_note "dup"`. **of W0** / **of W2** = `workspace_id` W0 / W2, `account_id` A0 / A9. **linked** = after its flush, `E.invoice_id = V.id`, then `db.flush()`.
- **invl(V, k, s)** = `InvoiceItem(workspace_id=V.workspace_id, invoice_id=V.id, line_number=k, description="Old line", quantity=Decimal("1"), unit_price=Decimal(s), line_subtotal=Decimal(s), created_by=U1.id)`.
- **pay(V, a)** = `InvoicePayment(workspace_id=V.workspace_id, invoice_id=V.id, payment_amount=Decimal(a), payment_date=date(2026, 9, 1), is_voided=False, created_by=U1.id)`; **voided pay** = `is_voided True`, `voided_at T0`, `voided_by U1.id`, `void_note "manual void"`.
- **ev(E, t)** = `ExpenseOrderEvent(workspace_id=E.workspace_id, expense_order_id=E.id, event_type="note", description="n", performed_by=U1.id, created_at=t)`.
- **tpl** = `OrderTemplate(workspace_id=W1.id, template_name="Monthly rent", description="Rent for the plant", expense_category="other", cost_center_id=None, account_id=A1.id, is_active=True, requires_approval=True, auto_approve=False, default_approver_id=None)`; **waiving** = `auto_approve True`. **tplline(T, k, s)** = `OrderTemplateItem(workspace_id=T.workspace_id, order_template_id=T.id, line_number=k, description="Rent", quantity=Decimal("1"), unit=None, unit_price=Decimal(s), notes=None)`.
- **commit point** = after the last Given line, `db.commit()` (a savepoint release under the `db` fixture); snapshots for `unchanged` / `nothing written` are taken here. Lines marked "(after the commit point)" run after it. **X** (only where listed) = `X = make_workspace(db)`, flushed, not committed; `X_ID = X.id`.

**Named checks.**
- **re-read R** = `db.expire_all()`, then `db.get(type(R), R.id)`. **X not in db** (TC3, Revision 4) = the `session:` line every refusal card with X carries right after the raise, before any re-read and before the test's own rollback; `x_gone` alone runs after that rollback and cannot show the service rolled back. One error card per write method (not its failing-commit card) also runs inside **spies** and checks `rb.call_count >= 1`. **unchanged(R)** = after re-read, every column of R equals its commit-point snapshot. **gone(R)** = after `db.expire_all()`, `db.get(type(R), R.id) is None`. **x_gone** = `db.get(Workspace, X_ID) is None`.
- **EV(E)** = after `db.expire_all()`, E's `expense_order_events` by `id`; **types(E)** = their `event_type` list (`metadata_json` holds metadata). **itypes(V)** = `event_type` list of the `invoice_events` of V by id; **LINES(V)** = V's `invoice_items` by `line_number`, after `db.expire_all()`. V may be an invoice or its id.
- **notes()** = after `db.expire_all()`, all `Notification` rows by id; **recips()** = `sorted(n.recipient_user_id for n in notes())`.
- **nothing written** = the row counts (all workspaces) of `expense_orders`, `expense_order_items`, `expense_order_approvers`, `expense_order_events`, `account_invoices`, `invoice_items`, `invoice_events`, `invoice_payments`, `notifications`, `workspace_audit_logs` equal their commit-point values.
- **session clean** = right after the call, before any re-read: `not db.new`, `not db.dirty`, `not db.deleted` (three asserts).
- **loaded(r)** = `inspect(r).expired_attributes.isdisjoint({c.key for c in inspect(type(r)).column_attrs})`; runs before any attribute of `r` is read.
- `committed:` lines: before the first one the test runs `db.rollback()` once; each line then re-reads with a fresh query.
- `raises: <Type>` = plain `with pytest.raises(<Type>) as exc:` around the call, **no** savepoint (the service rolls back itself), unless the When names `db.begin_nested()` (helpers that never roll back). A `schema` card wraps only building the schema.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = the same with `patch.object(db, "refresh", side_effect=RuntimeError("boom"))`. **failing notify** = the same with `patch("app.services.expense_order_service.notify_invoice_action", side_effect=RuntimeError("boom"))`. **failing section notify** / **failing approver notify** = the same with `patch("app.services.expense_order_service.notify_section_confirm_needed", side_effect=RuntimeError("boom"))` / `patch("app.services.expense_order_service.handle_add_approver", side_effect=RuntimeError("boom"))` (patch targets per spec Notes, G2).
- **Statement recorder** = an `after_cursor_execute` listener records every SQL statement sent during the When only. **first-read lock(T)** = the first recorded SELECT whose `FROM` names table T contains `FOR UPDATE` and neither `SKIP LOCKED` nor `NOWAIT`. **locks T before U** = some recorded SELECT on T with `FOR UPDATE` is sent before the first recorded SELECT whose `FROM` names U. **lock clause(T)** = that same first SELECT names no table but T in its `FROM` (no `JOIN`), and its text matches the regex `FOR UPDATE( OF T)?\s*$` (plain `FOR UPDATE` or `FOR UPDATE OF T`; spec C1a, V1a, I1a). A recorder card ends its Given with `db.expunge_all()` after the commit point; ids come from values taken before.

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`. Write the call and checks as shown, also when a parameter or behaviour does not exist yet.

**Race simulations.** None. Concurrency itself is integration-only; the lock cards check the emitted SQL.

## `ExpenseOrderService.create_expense_order`

### EOS-E-01 — a new order is committed and returned re-read; no invoice, no notification
- **Rules:** `create_expense_order` E1, E2, E3; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no expense orders.

**When**
- `result = svc.create_expense_order(db, eo_in=ExpenseOrderCreate(expense_category="other", account_id=A1.id, description="March rent"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `isinstance(result, ExpenseOrder)`, `result.id is not None`.
3. committed: the `expense_orders` row with `id == result.id` has `workspace_id == W1.id`, `account_id == A1.id`, `description == "March rent"`, `created_by == U2.id`, `invoice_id is None`.
4. committed: its approver rows are exactly one: `user_id == U2.id`, `approved is False`.
5. committed: `account_invoices` rows with `order_type == "expense_order"` and `order_id == result.id`: exactly 0.
6. committed: `notes() == []`.

### EOS-E-02 — the manager's 400 passes unchanged and the uncommitted extra row is gone
- **Rules:** `create_expense_order` E1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no expense orders.
2. X (after the commit point).

**When**
- `svc.create_expense_order(db, eo_in=ExpenseOrderCreate(expense_category="other", account_id=A1.id, description="   "), workspace_id=W1.id, user_id=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Description is required"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. session: session clean.
7. nothing written: nothing written.
8. committed: x_gone.

### EOS-E-03 — a failing commit is rolled back and re-raised; no order saved
- **Rules:** `create_expense_order` E1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no expense orders.

**When**
- `svc.create_expense_order(db, eo_in=ExpenseOrderCreate(expense_category="other", account_id=A1.id, description="March rent"), workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: W1 has exactly 0 `expense_orders` rows.
4. nothing written: nothing written.

### EOS-E-04 — a failing re-read after the commit leaves the order saved
- **Rules:** `create_expense_order` E1; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no expense orders.

**When**
- `svc.create_expense_order(db, eo_in=ExpenseOrderCreate(expense_category="other", account_id=A1.id, description="March rent"), workspace_id=W1.id, user_id=U2.id)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: W1 has exactly 1 `expense_orders` row.
3. committed: that row has `description == "March rent"`, `created_by == U2.id`.

## `ExpenseOrderService.update_expense_order`

### EOS-U-01 — an edit without recorded approvals is committed; no notification
- **Rules:** `update_expense_order` U1, U2 (no wipe → no notice); TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3).

**When**
- `result = svc.update_expense_order(db, eo_id=E.id, eo_in=ExpenseOrderUpdate(description="New rent"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == E.id`.
3. committed: re-read E: `description == "New rent"`.
4. committed: `notes() == []`.
5. committed: `account_invoices` rows with `order_id == E.id`: exactly 0.

### EOS-U-02 — an edit that wipes approvals tells the creator once, not the approvers
- **Rules:** `update_expense_order` U2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3), but approved.
4. appr(E, U4), but approved.

**When**
- `result = svc.update_expense_order(db, eo_id=E.id, eo_in=ExpenseOrderUpdate(description="New rent"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == E.id`.
2. committed: `len(notes()) == 1`.
3. committed: `notes()[0].recipient_user_id == U1.id`, `notes()[0].notification_type == "section_confirm"`.
4. committed: `notes()[0].entity_type == "expense_order"`, `notes()[0].entity_id == E.id`.
5. committed: `notes()[0].preview == RESETMSG`.
6. committed: re-read the approver row of U3: `approved is False`.

### EOS-U-03 — the creator is told also when the creator made the edit
- **Rules:** `update_expense_order` U2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3), but approved.

**When**
- `result = svc.update_expense_order(db, eo_id=E.id, eo_in=ExpenseOrderUpdate(description="New rent"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == E.id`.
2. committed: `recips() == [U1.id]`.
3. committed: `notes()[0].notification_type == "section_confirm"`, `notes()[0].preview == RESETMSG`.

### EOS-U-04 — an inactive creator gets no notice when approvals are wiped
- **Rules:** `update_expense_order` U2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1", but `created_by U5.id`.
2. line(E, 1, "100.00").
3. appr(E, U3), but approved.

**When**
- `result = svc.update_expense_order(db, eo_id=E.id, eo_in=ExpenseOrderUpdate(description="New rent"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == E.id`.
2. committed: re-read the approver row of U3: `approved is False`.
3. committed: `notes() == []`.

### EOS-U-05 — a linked draft is brought in step and stays linked
- **Rules:** `update_expense_order` U3; `_sync_or_create_invoice` Y2; Q4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. line(E, 2, "50.00").
4. appr(E, U3).
5. V = inv(E), linked.
6. invl(V, 1, "999.00").

**When**
- `result = svc.update_expense_order(db, eo_id=E.id, eo_in=ExpenseOrderUpdate(description="New rent"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == E.id`.
2. committed: re-read E: `invoice_id == V.id`.
3. committed: `[l.line_subtotal for l in LINES(V)] == [Decimal("100.00"), Decimal("50.00")]`.
4. committed: re-read V: `invoice_status == "draft"`, `invoice_amount == Decimal("150.00")`, `notes == "New rent"`.
5. committed: `"items_synced" in itypes(V)`.

### EOS-U-06 — lowering required approvals to 0 drafts the invoice and sends the draft notice
- **Rules:** `update_expense_order` U3; `_sync_or_create_invoice` Y7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3).

**When**
- `result = svc.update_expense_order(db, eo_id=E.id, eo_in=ExpenseOrderUpdate(required_approvals=0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == E.id`.
2. committed: re-read E: `invoice_id is not None`.
3. committed: the `account_invoices` row with `id == E.invoice_id` has `invoice_status == "draft"`, `invoice_type == "payable"`, `account_id == A1.id`, `order_id == E.id`, `invoice_amount == Decimal("100.00")`.
4. committed: `recips() == [U1.id, U3.id]`.
5. committed: every row of `notes()` has `notification_type == "invoice_action"`, `preview == DRAFTP`, `source_id == E.invoice_id`.

### EOS-U-07 — the invoice manager refusing the new account undoes the whole edit
- **Rules:** `update_expense_order` U4; `_resync_draft_invoice` R4b [BUG-629]; TC3
- **Kind:** bug
- **Expect:** xfail BUG-629 (`xfail(strict=True, reason="BUG-629")`)
- **Fails today on:** Then 1 (no error: the draft moves to the non-invoicing account and the edit is saved)

**Given**
1. A3 = acct "No Bills", but `allow_invoices False`.
2. E = eo "1".
3. line(E, 1, "100.00").
4. appr(E, U3).
5. V = inv(E), linked.
6. invl(V, 1, "100.00").
7. X (after the commit point).

**When**
- `svc.update_expense_order(db, eo_id=E.id, eo_in=ExpenseOrderUpdate(account_id=A3.id, description="New rent"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "Invoices are not allowed for this account"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. session: session clean.
6. unchanged: unchanged(E).
7. unchanged: unchanged(V).
8. nothing written: nothing written.
9. committed: x_gone.

### EOS-U-08 — a missing order: the manager's 404 passes unchanged and the extra row is gone
- **Rules:** `update_expense_order` U1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. X (after the commit point).

**When**
- `svc.update_expense_order(db, eo_id=MISSING, eo_in=ExpenseOrderUpdate(description="New rent"), workspace_id=W1.id, user_id=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Expense order with ID 999999999 not found"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. session: session clean.
7. unchanged: unchanged(E).
8. committed: x_gone.

### EOS-U-09 — another workspace's order (W2) gets the 404, nothing changed
- **Rules:** `update_expense_order` U1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E = eo "1".
2. Z = eo "9", but of W2.

**When**
- `svc.update_expense_order(db, eo_id=Z.id, eo_in=ExpenseOrderUpdate(description="New rent"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Expense order with ID {Z.id} not found"`.
4. unchanged: unchanged(Z).

### EOS-U-10 — a failing commit keeps the old description and the old invoice lines
- **Rules:** `update_expense_order` U1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. V = inv(E), linked.
4. OL = invl(V, 1, "999.00").

**When**
- `svc.update_expense_order(db, eo_id=E.id, eo_in=ExpenseOrderUpdate(description="New rent"), workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read E: `description == "Office rent"`.
4. unchanged: unchanged(OL).
5. nothing written: nothing written.

### EOS-U-11 — clearing the account while a draft invoice is linked is refused
- **Rules:** `_resync_draft_invoice` R5a [BUG-3068]
- **Kind:** bug
- **Expect:** xfail BUG-3068
- **Fails today on:** Then 1 (no error: the `null` is ignored and the edit succeeds)

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. V = inv(E), linked.
4. invl(V, 1, "100.00").
5. X (after the commit point).

**When**
- `svc.update_expense_order(db, eo_id=E.id, eo_in=ExpenseOrderUpdate(account_id=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == CLEARACC`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. unchanged: unchanged(E).
6. unchanged: unchanged(V).
7. nothing written: nothing written.
8. committed: x_gone.

### EOS-U-12 — clearing the account while a confirmed invoice is linked is refused too
- **Rules:** `_resync_draft_invoice` R5a [BUG-3068]
- **Kind:** bug
- **Expect:** xfail BUG-3068
- **Fails today on:** Then 1 (no error: the `null` is ignored and the edit succeeds)

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. V = inv(E), but confirmed, linked.

**When**
- `svc.update_expense_order(db, eo_id=E.id, eo_in=ExpenseOrderUpdate(account_id=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == CLEARACC`.
4. unchanged: unchanged(E).

### EOS-U-13 — a failing approvals-reset notice undoes the whole edit
- **Rules:** `update_expense_order` U2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. P3 = appr(E, U3), but approved.
4. X (after the commit point).

**When**
- `svc.update_expense_order(db, eo_id=E.id, eo_in=ExpenseOrderUpdate(description="New rent"), workspace_id=W1.id, user_id=U2.id)`, inside **failing section notify**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
3. mock called: `rb.call_count >= 1`.
4. unchanged: unchanged(E).
5. unchanged: unchanged(P3).
6. nothing written: nothing written.
7. committed: x_gone.

### EOS-U-14 — a deleted new account is refused and the whole edit is undone (today and after the fix)
- **Rules:** `update_expense_order` U4; `_resync_draft_invoice` R4, R4a; TC3
- **Kind:** error
- **Expect:** pass
- **Note:** passing companion to U-07: the deleted-account refusal holds today (R4) and after the BUG-629 fix.

**Given**
1. AD = acct "Old Vendor", but `is_deleted True`.
2. E = eo "1".
3. line(E, 1, "100.00").
4. appr(E, U3).
5. V = inv(E), linked.
6. invl(V, 1, "100.00").
7. X (after the commit point).

**When**
- `svc.update_expense_order(db, eo_id=E.id, eo_in=ExpenseOrderUpdate(account_id=AD.id, description="New rent"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot assign invoice to deleted account"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. session: session clean.
6. unchanged: unchanged(E).
7. unchanged: unchanged(V).
8. nothing written: nothing written.
9. committed: x_gone.

## `ExpenseOrderService.get_expense_order`

### EOS-G-01 — returns the order; neither commits nor rolls back; a pending row stays pending
- **Rules:** `get_expense_order` G1; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. E = eo "1".
2. X (after the commit point).

**When**
- spies: `result = svc.get_expense_order(db, eo_id=E.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, ExpenseOrder)`, `result.id == E.id`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.

### EOS-G-02 — a voided order is returned
- **Rules:** `get_expense_order` G1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E = eo "1", but voided.

**When**
- `result = svc.get_expense_order(db, eo_id=E.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E.id`, `result.voided is True`.

### EOS-G-03 — a completed order is returned
- **Rules:** `get_expense_order` G1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E = eo "1", but completed.
2. V = inv(E), but confirmed, linked.

**When**
- `result = svc.get_expense_order(db, eo_id=E.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E.id`, `result.completed_at == T0`.

### EOS-G-04 — a W0 order (lower workspace id) gets the 404
- **Rules:** `get_expense_order` G1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = eo "0", but of W0.
2. E = eo "1".

**When**
- `svc.get_expense_order(db, eo_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Expense order with ID {Z.id} not found"`.

### EOS-G-05 — a W2 order (higher workspace id) gets the 404
- **Rules:** `get_expense_order` G1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E = eo "1".
2. Z = eo "9", but of W2.

**When**
- `svc.get_expense_order(db, eo_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Expense order with ID {Z.id} not found"`.

### EOS-G-06 — a 404 neither rolls back nor drops a pending row
- **Rules:** `get_expense_order` G1; TC6
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. X (after the commit point).

**When**
- spies: `svc.get_expense_order(db, eo_id=MISSING, workspace_id=W1.id)`, wrapped in `raises: HTTPException`.

**Then**
1. raises: `exc.value.detail == "Expense order with ID 999999999 not found"`.
2. mock called: `rb.call_count == 0`.
3. mock called: `cm.call_count == 0`.
4. session: `X in db`.

## `ExpenseOrderService.list_expense_orders`

### EOS-L-01 — returns the page of the workspace's orders; W0 and W2 orders never appear
- **Rules:** `list_expense_orders` L-1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Z0 = eo "0", but of W0.
2. A = eo "1".
3. B = eo "2".
4. C = eo "3".
5. Z2 = eo "9", but of W2.

**When**
- `result = svc.list_expense_orders(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, ExpenseOrderListResponse)`.
2. returns: `result.total == 3`, `result.skip == 0`, `result.has_more is False`.
3. returns: `{o.id for o in result.items} == {A.id, B.id, C.id}`.

### EOS-L-02 — with no limit given, 101 orders give 100 and `has_more` true
- **Rules:** `list_expense_orders` L-1 (own default limit 100)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 orders, by `add_all` and one flush: k = 1 … 101, eo f"{k}".

**When**
- `result = svc.list_expense_orders(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result.items) == 100`.
2. returns: `result.limit == 100`, `result.total == 101`, `result.has_more is True`.

### EOS-L-03 — skip and limit=1000 are passed on
- **Rules:** `list_expense_orders` L-1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = eo "1".
2. B = eo "2".
3. C = eo "3".

**When**
- `result = svc.list_expense_orders(db, workspace_id=W1.id, skip=1, limit=1000)`.

**Then**
1. returns: `len(result.items) == 2`, `{o.id for o in result.items} <= {A.id, B.id, C.id}`.
2. returns: `result.skip == 1`, `result.limit == 1000`, `result.total == 3`.

### EOS-L-04 — a hub filter passed by keyword reaches the page
- **Rules:** `list_expense_orders` L-1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = eo "1".
2. B = eo "2", but voided.

**When**
- `result = svc.list_expense_orders(db, workspace_id=W1.id, exclude_voided=True)`.

**Then**
1. returns: `[o.id for o in result.items] == [A.id]`.
2. returns: `result.total == 1`.

### EOS-L-05 — an unknown keyword filter raises TypeError
- **Rules:** `list_expense_orders` L-2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = eo "1".

**When**
- `svc.list_expense_orders(db, workspace_id=W1.id, colour="red")`.

**Then**
1. raises: `TypeError`.

### EOS-L-06 — the list neither commits nor rolls back
- **Rules:** `list_expense_orders` L-1; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = eo "1".
2. X (after the commit point).

**When**
- spies: `result = svc.list_expense_orders(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.total == 1`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.

## `ExpenseOrderService._hub_filter_kwargs`

### EOS-K-01 — with no arguments, the ten keys with their defaults
- **Rules:** `_hub_filter_kwargs` Returns, K1, K2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = svc._hub_filter_kwargs()`.

**Then**
1. returns: `result == {"expense_category": None, "account_id": None, "invoice_id": None, "date_from": None, "date_to": None, "status_ids": None, "invoice_filter": None, "search": None, "exclude_complete": False, "exclude_voided": False}`.

### EOS-K-02 — every value is passed through unchanged; "linked" stays as given
- **Rules:** `_hub_filter_kwargs` K1, K2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = svc._hub_filter_kwargs(expense_category="factory", account_id=7, invoice_id=8, date_from=date(2026, 9, 1), date_to=date(2026, 9, 30), status_ids=[3, 4], invoice_filter="linked", search="rent", exclude_complete=True, exclude_voided=True)`.

**Then**
1. returns: `result == {"expense_category": "factory", "account_id": 7, "invoice_id": 8, "date_from": date(2026, 9, 1), "date_to": date(2026, 9, 30), "status_ids": [3, 4], "invoice_filter": "linked", "search": "rent", "exclude_complete": True, "exclude_voided": True}`.

### EOS-K-03 — `invoice_filter=""` becomes None
- **Rules:** `_hub_filter_kwargs` K2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = svc._hub_filter_kwargs(invoice_filter="")`.

**Then**
1. returns: `result["invoice_filter"] is None`.

### EOS-K-04 — `invoice_filter="all"` becomes None
- **Rules:** `_hub_filter_kwargs` K2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = svc._hub_filter_kwargs(invoice_filter="all")`.

**Then**
1. returns: `result["invoice_filter"] is None`.

### EOS-K-05 — `invoice_filter="All"` is passed as given
- **Rules:** `_hub_filter_kwargs` K2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = svc._hub_filter_kwargs(invoice_filter="All")`.

**Then**
1. returns: `result["invoice_filter"] == "All"`.

### EOS-K-06 — `invoice_filter=" all"` is passed as given
- **Rules:** `_hub_filter_kwargs` K2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = svc._hub_filter_kwargs(invoice_filter=" all")`.

**Then**
1. returns: `result["invoice_filter"] == " all"`.

### EOS-K-07 — `invoice_filter="invoiced"` is passed as given
- **Rules:** `_hub_filter_kwargs` K2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = svc._hub_filter_kwargs(invoice_filter="invoiced")`.

**Then**
1. returns: `result["invoice_filter"] == "invoiced"`.

## `ExpenseOrderService.list_expense_orders_page`

### EOS-P-01 — total and items come from the same filters; defaults skip 0 / limit 50 are echoed
- **Rules:** `list_expense_orders_page` P-1, P-2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Z0 = eo "0", but of W0.
2. A = eo "1".
3. B = eo "2".
4. C = eo "3", but voided.
5. Z2 = eo "9", but of W2.

**When**
- `result = svc.list_expense_orders_page(db, workspace_id=W1.id, exclude_voided=True)`.

**Then**
1. returns: `isinstance(result, ExpenseOrderListResponse)`.
2. returns: `result.total == 2`.
3. returns: `{o.id for o in result.items} == {A.id, B.id}`.
4. returns: `result.skip == 0`, `result.limit == 50`, `result.has_more is False`.

### EOS-P-02 — with no limit given, 51 orders give 50 and `has_more` true
- **Rules:** `list_expense_orders_page` P-1, P-3 (default limit 50)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 51 orders, by `add_all` and one flush: k = 1 … 51, eo f"{k}".

**When**
- `result = svc.list_expense_orders_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result.items) == 50`.
2. returns: `result.total == 51`, `result.has_more is True`.

### EOS-P-03 — skip + items short of total: `has_more` true
- **Rules:** `list_expense_orders_page` P-3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 5 orders, by `add_all` and one flush: k = 1 … 5, eo f"{k}".

**When**
- `result = svc.list_expense_orders_page(db, workspace_id=W1.id, skip=0, limit=4)`.

**Then**
1. returns: `len(result.items) == 4`.
2. returns: `result.total == 5`, `result.skip == 0`, `result.limit == 4`, `result.has_more is True`.

### EOS-P-04 — skip + items equal to total: `has_more` false
- **Rules:** `list_expense_orders_page` P-3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 5 orders, by `add_all` and one flush: k = 1 … 5, eo f"{k}".

**When**
- `result = svc.list_expense_orders_page(db, workspace_id=W1.id, skip=1, limit=4)`.

**Then**
1. returns: `len(result.items) == 4`.
2. returns: `result.total == 5`, `result.skip == 1`, `result.has_more is False`.

### EOS-P-05 — skip beyond the total: no items, `has_more` false
- **Rules:** `list_expense_orders_page` P-3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 5 orders, by `add_all` and one flush: k = 1 … 5, eo f"{k}".

**When**
- `result = svc.list_expense_orders_page(db, workspace_id=W1.id, skip=7, limit=1000)`.

**Then**
1. returns: `result.items == []`.
2. returns: `result.total == 5`, `result.skip == 7`, `result.limit == 1000`, `result.has_more is False`.

### EOS-P-06 — no match: total 0, no items, `has_more` false
- **Rules:** `list_expense_orders_page` P-3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Z2 = eo "9", but of W2.

**When**
- `result = svc.list_expense_orders_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.items == []`.
2. returns: `result.total == 0`, `result.has_more is False`.

### EOS-P-07 — `invoice_filter="all"` lists linked and unlinked orders alike
- **Rules:** `list_expense_orders_page` P-1; `_hub_filter_kwargs` K2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = eo "1".
2. B = eo "2".
3. V = inv(B), linked.

**When**
- `result = svc.list_expense_orders_page(db, workspace_id=W1.id, invoice_filter="all")`.

**Then**
1. returns: `result.total == 2`.
2. returns: `{o.id for o in result.items} == {A.id, B.id}`.

### EOS-P-08 — the page neither commits nor rolls back
- **Rules:** `list_expense_orders_page` P-4; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = eo "1".
2. X (after the commit point).

**When**
- spies: `result = svc.list_expense_orders_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.total == 1`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.

### EOS-P-09 — with no filter, completed and voided orders are listed
- **Rules:** `list_expense_orders_page` P-1; `_hub_filter_kwargs` defaults (`exclude_complete=False`, `exclude_voided=False`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = eo "1".
2. C = eo "2", but completed.
3. D = eo "3", but voided.

**When**
- `result = svc.list_expense_orders_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.total == 3`.
2. returns: `{o.id for o in result.items} == {A.id, C.id, D.id}`.
3. returns: `result.has_more is False`.

## `ExpenseOrderService.get_expense_order_hub_stats`

### EOS-H-01 — the five figures are the manager's tuple, in order
- **Rules:** `get_expense_order_hub_stats` H-1, H-2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = eo "1", but `subtotal Decimal("100.00")`, `total_amount Decimal("100.00")`.
2. B = eo "2", but `subtotal Decimal("200.00")`, `total_amount Decimal("200.00")`.
3. VB = inv(B), linked.
4. C = eo "3", but completed, `subtotal Decimal("400.00")`, `total_amount Decimal("400.00")`.
5. VC = inv(C), but confirmed, linked.
6. Z2 = eo "9", but of W2, `subtotal Decimal("800.00")`, `total_amount Decimal("800.00")`.

**When**
- `result = svc.get_expense_order_hub_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: `(result.total_count, result.total_value, result.open_count, result.open_value, result.not_invoiced_count) == mgr.expense_order_hub_stats(db, W1.id, **svc._hub_filter_kwargs())`.
2. returns: `(result.total_count, result.total_value, result.open_count, result.open_value, result.not_invoiced_count) == (3, Decimal("700.00"), 2, Decimal("300.00"), 1)`.

### EOS-H-02 — one filter feeds the figures and the recent list alike
- **Rules:** `get_expense_order_hub_stats` H-1, H-3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = eo "1", but `subtotal Decimal("100.00")`, `total_amount Decimal("100.00")`.
2. B = eo "2", but voided, `subtotal Decimal("900.00")`, `total_amount Decimal("900.00")`.

**When**
- `result = svc.get_expense_order_hub_stats(db, workspace_id=W1.id, exclude_voided=True)`.

**Then**
1. returns: `result.total_count == 1`, `result.total_value == Decimal("100.00")`.
2. returns: `[s.id for s in result.recent_orders] == [A.id]`.

### EOS-H-03 — `recent_orders` holds at most 10, in the manager's order
- **Rules:** `get_expense_order_hub_stats` H-3
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. 11 orders, flushed one at a time: k = 1 … 11, eo f"{k}".
2. `rec = mgr.list_expense_orders_recent_for_hub(db, W1.id, limit=10, **svc._hub_filter_kwargs())` (after the commit point).

**When**
- `result = svc.get_expense_order_hub_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result.recent_orders) == 10`.
2. returns: `[s.id for s in result.recent_orders] == [o.id for o in rec]`.
3. returns: each `result.recent_orders[i]` equals `expense_order_to_recent_summary` of `rec[i]`.

### EOS-H-04 — the financial snapshot copies the manager's buckets without changing a number
- **Rules:** `get_expense_order_hub_stats` H-4, H-4a
- **Kind:** happy
- **Expect:** pass
- **Author:** claude

**Given**
1. A = eo "1", but `subtotal Decimal("100.00")`, `total_amount Decimal("100.00")`, `due_date date(2026, 9, 20)`.
2. B = eo "2", but `expense_category "department"`, `cost_center_id DEP1.id`, `account_id A2.id`, `subtotal Decimal("250.00")`, `total_amount Decimal("250.00")`.
3. VB = inv(B), but confirmed, `account_id A2.id`, `invoice_amount Decimal("250.00")`, linked.
4. `snap = mgr.expense_order_financial_snapshot(db, W1.id, **svc._hub_filter_kwargs())` (after the commit point).

**When**
- `result = svc.get_expense_order_hub_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: for `category_breakdown` and `stage_pipeline`, the list of `(key, label, count, total_value)` of `result.financial_snapshot` equals that of `snap`, in order.
2. returns: for `open_by_account`, the list of `(account_id, account_name, count, total_value)` equals that of `snap`, in order (H-4a).
3. returns: for `due_timeline`, the list of `(key, label, count, total_value)` and each bucket's samples `(id, order_number, total_value, sublabel)` equal those of `snap`, in order.
4. returns: for `unpaid_pipeline`, the list of `(key, label, count, outstanding_value)` and each bucket's samples equal those of `snap`, in order.

### EOS-H-05 — an empty workspace: empty lists stay empty, zero figures
- **Rules:** `get_expense_order_hub_stats` H-2, H-3, H-4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Z2 = eo "9", but of W2.

**When**
- `result = svc.get_expense_order_hub_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.total_count == 0`, `result.open_count == 0`, `result.not_invoiced_count == 0`.
2. returns: `result.recent_orders == []`.
3. returns: `result.financial_snapshot.category_breakdown == []`, `result.financial_snapshot.open_by_account == []`.

### EOS-H-06 — the stats neither commit nor roll back
- **Rules:** `get_expense_order_hub_stats` H-5; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = eo "1".
2. X (after the commit point).

**When**
- spies: `result = svc.get_expense_order_hub_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.total_count == 1`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.

### EOS-H-07 — the response class and every recent-summary field
- **Rules:** `get_expense_order_hub_stats` Returns, H-3, H-3a
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = eo "1", but `due_date date(2026, 10, 15)`, `subtotal Decimal("100.00")`, `total_amount Decimal("100.00")`.
2. VA = inv(A), linked.

**When**
- `result = svc.get_expense_order_hub_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, ExpenseOrderHubStatsResponse)` (`from app.schemas.expense_order import ExpenseOrderHubStatsResponse`).
2. returns: `len(result.recent_orders) == 1`; `s = result.recent_orders[0]`; `isinstance(s, OrderHubRecentSummary)` (`from app.schemas.order_hub import OrderHubRecentSummary`).
3. returns: `s.id == A.id`, `s.order_number == A.expense_number`, `s.status_id == 0`, `s.status_name is None`.
4. returns: `s.account_id == A1.id`, `s.invoice_id == VA.id`, `s.total_amount == Decimal("100.00")`, `s.expense_category == "other"`.
5. returns: `s.expense_date == date(2026, 9, 1)`, `s.due_date == date(2026, 10, 15)`, `s.created_at == A.created_at`, `s.updated_at == A.updated_at`.
6. returns: `s.source_location_type is None`, `s.destination_location_type is None`.

### EOS-H-08 — with no filter, a voided order is counted
- **Rules:** `get_expense_order_hub_stats` H-1, H-2; `_hub_filter_kwargs` defaults (`exclude_complete=False`, `exclude_voided=False`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = eo "1", but `subtotal Decimal("100.00")`, `total_amount Decimal("100.00")`.
2. D = eo "2", but voided, `subtotal Decimal("200.00")`, `total_amount Decimal("200.00")`.

**When**
- `result = svc.get_expense_order_hub_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: `figs = (result.total_count, result.total_value, result.open_count, result.open_value, result.not_invoiced_count)`; `figs == mgr.expense_order_hub_stats(db, W1.id, **svc._hub_filter_kwargs())`.
2. returns: `figs != mgr.expense_order_hub_stats(db, W1.id, **svc._hub_filter_kwargs(exclude_voided=True))` (the voided order changes the figures, so a default of `exclude_voided=True` is seen).
3. returns: `result.total_count == 2`.
4. returns: `{r.id for r in result.recent_orders} == {A.id, D.id}`.

## `ExpenseOrderService.delete_expense_order`

### EOS-X-01 — an order without an invoice is deleted and committed; no notification
- **Rules:** `delete_expense_order` X1, X3; Returns; TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E = eo "1".
2. L1 = line(E, 1, "100.00").
3. appr(E, U3).

**When**
- `result = svc.delete_expense_order(db, eo_id=E.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. committed: gone(E).
3. committed: gone(L1).
4. committed: `account_invoices` rows of W1: exactly 0.
5. committed: `notes() == []`.

### EOS-X-02 — the deleter is passed on and named in the audit row
- **Rules:** `delete_expense_order` X2 [BUG-1193]
- **Kind:** bug
- **Expect:** xfail BUG-1193
- **Fails today on:** Then 1 (the call raises TypeError: the service has no `user_id` parameter)

**Given**
1. E = eo "1".
2. `eid = E.id`.

**When**
- `result = svc.delete_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. committed: gone(E).
3. committed: `workspace_audit_logs` rows with `resource_type == "expense_order"` and `resource_id == eid`: exactly 1.
4. committed: that row has `user_id == U2.id`, `action == "expense_order_deleted"`, `workspace_id == W1.id`.

### EOS-X-03 — a missing order: 404 passes unchanged, the extra row is gone
- **Rules:** `delete_expense_order` X1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. X (after the commit point).

**When**
- `svc.delete_expense_order(db, eo_id=MISSING, workspace_id=W1.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Expense order with ID 999999999 not found"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. session: session clean.
7. unchanged: unchanged(E).
8. committed: x_gone.

### EOS-X-04 — a completed order: 400 passes unchanged, nothing deleted
- **Rules:** `delete_expense_order` X1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1", but completed.
2. V = inv(E), but confirmed, linked.
3. X (after the commit point).

**When**
- `svc.delete_expense_order(db, eo_id=E.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot delete a completed expense order"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. unchanged: unchanged(E).
6. unchanged: unchanged(V).
7. committed: x_gone.

### EOS-X-05 — another workspace's order (W2): 404, nothing deleted
- **Rules:** `delete_expense_order` X1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E = eo "1".
2. Z = eo "9", but of W2.

**When**
- `svc.delete_expense_order(db, eo_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Expense order with ID {Z.id} not found"`.
4. unchanged: unchanged(Z).

### EOS-X-06 — an order with a linked draft is refused: void it instead
- **Rules:** `delete_expense_order` X1 [BUG-742] (manager pass-through)
- **Kind:** bug
- **Expect:** xfail BUG-742
- **Fails today on:** Then 1 (no error: the order is deleted)

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. V = inv(E), linked.
4. X (after the commit point).

**When**
- `svc.delete_expense_order(db, eo_id=E.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Void the expense order instead"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. unchanged: unchanged(E).
6. unchanged: unchanged(V).
7. committed: x_gone.

### EOS-X-07 — a failing commit keeps the order
- **Rules:** `delete_expense_order` X1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. L1 = line(E, 1, "100.00").

**When**
- `svc.delete_expense_order(db, eo_id=E.id, workspace_id=W1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(E).
4. unchanged: unchanged(L1).

## `ExpenseOrderService.complete_expense_order`

### EOS-C-01 — a met order with a draft: the order is stamped complete and committed
- **Rules:** `complete_expense_order` C8, C10; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3), but approved.
4. V = inv(E), linked.
5. invl(V, 1, "100.00").

**When**
- `result = svc.complete_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == E.id`.
3. committed: re-read E: `completed_at == NOW`, `completed_by == U2.id`, `updated_by == U2.id`, `voided is False`, `invoice_id == V.id`.
4. committed: `types(E) == ["order_completed"]`.
5. committed: `EV(E)[0].description == "Invoice confirmed and expense order marked complete"`, `EV(E)[0].performed_by == U2.id`, `EV(E)[0].metadata_json is None`.

### EOS-C-02 — a met order with a draft: the draft is confirmed at its line sum
- **Rules:** `complete_expense_order` C8
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. line(E, 2, "25.50").
4. appr(E, U3), but approved.
5. V = inv(E), linked.
6. invl(V, 1, "100.00").
7. invl(V, 2, "25.50").

**When**
- `result = svc.complete_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == E.id`.
2. committed: re-read V: `invoice_status == "confirmed"`, `invoice_amount == Decimal("125.50")`.
3. committed: `"confirmed" in itypes(V)`.

### EOS-C-03 — the confirmed notice goes to every approver and the creator, active members only
- **Rules:** `complete_expense_order` C8
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3), but approved.
4. appr(E, U5), but approved.
5. V = inv(E), linked.
6. invl(V, 1, "100.00").

**When**
- `result = svc.complete_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == E.id`.
2. committed: `recips() == [U1.id, U3.id]`.
3. committed: every row of `notes()` has `notification_type == "invoice_action"`, `entity_type == "expense_order"`, `entity_id == E.id`.
4. committed: every row of `notes()` has `source_type == "invoice"`, `source_id == V.id`.
5. committed: every row of `notes()` has `preview == f"confirmed|Invoice confirmed on EXP-{E.id} — order locked"`.

### EOS-C-04 — an already completed order is returned as it is: no check, no write, no commit, no rollback
- **Rules:** `complete_expense_order` C2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E = eo "1", but completed.
2. line(E, 1, "100.00").
3. appr(E, U3).
4. V = inv(E), but confirmed, linked.
5. X (after the commit point).

**When**
- spies: `result = svc.complete_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == E.id`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.
5. re-read E: `completed_at == T0`, `completed_by == U1.id`, `updated_by == U1.id`.
6. unchanged: unchanged(V).
7. count: `types(E) == []`.
8. count: `notes() == []`.

### EOS-C-05 — a voided order is refused before anything else
- **Rules:** `complete_expense_order` C3, Errors row 2 [BUG-3065]
- **Kind:** bug
- **Expect:** xfail BUG-3065
- **Fails today on:** Then 1 (no error: the voided order is completed and its draft confirmed)

**Given**
1. E = eo "1", but voided, waived.
2. line(E, 1, "50.00").
3. V = inv(E), linked.
4. invl(V, 1, "50.00").
5. X (after the commit point).

**When**
- `svc.complete_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Expense order is voided"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. session: session clean.
6. unchanged: unchanged(E).
7. unchanged: unchanged(V).
8. nothing written: nothing written.
9. committed: x_gone.

### EOS-C-06 — the voided check comes before the approvals check
- **Rules:** `complete_expense_order` C3, C4 [BUG-3065]
- **Kind:** bug
- **Expect:** xfail BUG-3065
- **Fails today on:** Then 2 (the detail is `Required approvals are not met`)

**Given**
1. E = eo "1", but voided.
2. line(E, 1, "50.00").
3. appr(E, U3).

**When**
- `svc.complete_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Expense order is voided"`.
3. unchanged: unchanged(E).

### EOS-C-07 — a voided order with unmet approvals is never completed (today and after the fix)
- **Rules:** `complete_expense_order` C3, C4
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1", but voided.
2. line(E, 1, "50.00").
3. appr(E, U3).
4. X (after the commit point).

**When**
- `svc.complete_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
4. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
5. unchanged: unchanged(E).
6. nothing written: nothing written.
7. committed: x_gone.

### EOS-C-08 — approvals not met: 400, the draft stays a draft
- **Rules:** `complete_expense_order` C4, Errors row 3; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3), but approved.
4. appr(E, U4).
5. V = inv(E), linked.
6. invl(V, 1, "100.00").
7. X (after the commit point).

**When**
- `svc.complete_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == NOTMET`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. session: session clean.
6. unchanged: unchanged(E).
7. unchanged: unchanged(V).
8. nothing written: nothing written.
9. committed: x_gone.

### EOS-C-09 — no approvers and no explicit requirement counts as not met
- **Rules:** `complete_expense_order` C4 [BUG-755] (manager pass-through)
- **Kind:** bug
- **Expect:** xfail BUG-755
- **Fails today on:** Then 1 (no error: with no approvers the approvals count as met and the order is completed)

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. V = inv(E), linked.
4. invl(V, 1, "100.00").

**When**
- `svc.complete_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == NOTMET`.
4. unchanged: unchanged(E).
5. unchanged: unchanged(V).

### EOS-C-10 — a waived order (required 0) with no approvers completes; only the creator is told
- **Rules:** `complete_expense_order` C4, C8, C10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E = eo "1", but waived.
2. line(E, 1, "40.00").
3. V = inv(E), linked.
4. invl(V, 1, "40.00").

**When**
- `result = svc.complete_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == E.id`.
2. committed: re-read E: `completed_at == NOW`.
3. committed: re-read V: `invoice_status == "confirmed"`, `invoice_amount == Decimal("40.00")`.
4. committed: `recips() == [U1.id]`.

### EOS-C-11 — no invoice linked: 400 with the "set an account" text
- **Rules:** `complete_expense_order` C5, Errors row 4; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3), but approved.
4. X (after the commit point).

**When**
- `svc.complete_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == NOINV`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. session: session clean.
6. unchanged: unchanged(E).
7. nothing written: nothing written.
8. committed: x_gone.

### EOS-C-12 — the linked invoice is a W2 invoice: "Linked invoice not found", no id shown
- **Rules:** `complete_expense_order` C6, Errors row 5; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3), but approved.
4. Z = inv(E), but of W2, linked.
5. invl(Z, 1, "100.00").

**When**
- `svc.complete_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Linked invoice not found"`.
4. unchanged: unchanged(E).
5. unchanged: unchanged(Z).
6. nothing written: nothing written.

### EOS-C-13 — the linked invoice is a W0 invoice: "Linked invoice not found"
- **Rules:** `complete_expense_order` C6; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = inv(None), but of W0.
2. E = eo "1".
3. line(E, 1, "100.00").
4. appr(E, U3), but approved.
5. `E.invoice_id = Z.id`, then `db.flush()`.

**When**
- `svc.complete_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Linked invoice not found"`.
4. unchanged: unchanged(E).
5. unchanged: unchanged(Z).

### EOS-C-14 — the linked invoice was voided: 400, nothing written
- **Rules:** `complete_expense_order` C7, Errors row 6
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3), but approved.
4. V = inv(E), but voided-inv, linked.
5. X (after the commit point).

**When**
- `svc.complete_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == VOIDINV`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. unchanged: unchanged(E).
6. unchanged: unchanged(V).
7. nothing written: nothing written.
8. committed: x_gone.

### EOS-C-15 — a draft with no lines cannot be confirmed: 400, the order is not completed
- **Rules:** `complete_expense_order` C8, Errors row 7 [BUG-628] (invoice manager pass-through)
- **Kind:** bug
- **Expect:** xfail BUG-628
- **Fails today on:** Then 1 (no error: the empty draft is confirmed at 0.00 and the order completed)

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3), but approved.
4. V = inv(E), linked.
5. X (after the commit point).

**When**
- `svc.complete_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Add at least one line item before confirming"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. unchanged: unchanged(E).
6. unchanged: unchanged(V).
7. nothing written: nothing written.
8. committed: x_gone.

### EOS-C-16 — an invoice already confirmed is left as it is; the order is still completed, nobody told
- **Rules:** `complete_expense_order` C9, C10
- **Kind:** happy
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3), but approved.
4. V = inv(E), but confirmed, linked.
5. invl(V, 1, "100.00").

**When**
- `result = svc.complete_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == E.id`.
2. committed: unchanged(V).
3. committed: `itypes(V) == []`.
4. committed: re-read E: `completed_at == NOW`, `completed_by == U2.id`, `updated_by == U2.id`.
5. committed: `types(E) == ["order_completed"]`, `EV(E)[0].description == "Invoice confirmed and expense order marked complete"`.
6. committed: `notes() == []`.

### EOS-C-17 — a missing order: 404, the extra row is gone
- **Rules:** `complete_expense_order` C1, Errors row 1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. X (after the commit point).

**When**
- `svc.complete_expense_order(db, eo_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Expense order with ID 999999999 not found"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. session: session clean.
6. committed: x_gone.

### EOS-C-18 — another workspace's order (W2): 404, not completed
- **Rules:** `complete_expense_order` C1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E = eo "1".
2. Z = eo "9", but of W2, waived.
3. line(Z, 1, "100.00").
4. VZ = inv(Z), but of W2, linked.
5. invl(VZ, 1, "100.00").

**When**
- `svc.complete_expense_order(db, eo_id=Z.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Expense order with ID {Z.id} not found"`.
4. unchanged: unchanged(Z).
5. unchanged: unchanged(VZ).

### EOS-C-19 — a failing notification undoes the confirm
- **Rules:** `complete_expense_order` C8; TC3
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3), but approved.
4. V = inv(E), linked.
5. invl(V, 1, "100.00").
6. X (after the commit point).

**When**
- `svc.complete_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`, inside **failing notify**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
3. re-read V: `invoice_status == "draft"`.
4. unchanged: unchanged(E).
5. nothing written: nothing written.
6. committed: x_gone.

### EOS-C-20 — a failing commit saves neither the confirm nor the completion
- **Rules:** `complete_expense_order` C10; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3), but approved.
4. V = inv(E), linked.
5. invl(V, 1, "100.00").

**When**
- `svc.complete_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read V: `invoice_status == "draft"`.
4. re-read E: `completed_at is None`.
5. nothing written: nothing written.

### EOS-C-21 — the order is read with a row lock before any check
- **Rules:** `complete_expense_order` C1, C1a [BUG-3062]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-3062
- **Fails today on:** Then 2 (the order is read without `FOR UPDATE`)

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3), but approved.
4. V = inv(E), linked.
5. invl(V, 1, "100.00").
6. `eid = E.id`.
7. Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `result = svc.complete_expense_order(db, eo_id=eid, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == eid`.
2. statement: first-read lock(`expense_orders`).
3. statement: lock clause(`expense_orders`).
4. statement: locks `expense_orders` before `account_invoices`.
5. statement: locks `expense_orders` before `expense_order_approvers`.

### EOS-C-22 — an order both voided and completed gets the "voided" 400, not the unchanged 200
- **Rules:** `complete_expense_order` C3, C2 (check order C1, C3, C2) [BUG-3065]
- **Kind:** bug
- **Expect:** xfail BUG-3065
- **Fails today on:** Then 1 (no error: C2 returns the order unchanged)

**Given**
1. E = eo "1", but voided, completed.
2. line(E, 1, "100.00").
3. appr(E, U3), but approved.
4. V = inv(E), but confirmed, linked.
5. X (after the commit point).

**When**
- `svc.complete_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Expense order is voided"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. session: session clean.
6. unchanged: unchanged(E).
7. unchanged: unchanged(V).
8. nothing written: nothing written.
9. committed: x_gone.

### EOS-C-23 — an order both voided and completed is never changed (today and after the fix)
- **Rules:** `complete_expense_order` C2, C3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E = eo "1", but voided, completed.
2. line(E, 1, "100.00").
3. appr(E, U3), but approved.
4. V = inv(E), but confirmed, linked.

**When**
- `err = None`; `try: svc.complete_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)` / `except HTTPException as e: err = e` (no other exception is caught).

**Then**
1. returns: `err is None or err.status_code == 400`.
2. unchanged: unchanged(E).
3. unchanged: unchanged(V).
4. count: `types(E) == []`.
5. nothing written: nothing written.

## `ExpenseOrderService.void_expense_order`

### EOS-V-01 — an order with a draft is voided and committed; `updated_by` untouched; nobody told
- **Rules:** `void_expense_order` V9, V11, V12; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. E = eo "1", but `updated_by U1.id`.
2. line(E, 1, "100.00").
3. appr(E, U3), but approved.
4. V = inv(E), linked.
5. invl(V, 1, "100.00").

**When**
- `result = svc.void_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id, void_note="Duplicate order")`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == E.id`.
3. committed: re-read E: `voided is True`, `void_note == "Duplicate order"`, `voided_at == NOW`, `voided_by == U2.id`.
4. committed: re-read E: `invoice_id is None`, `completed_at is None`.
5. committed: re-read E: `updated_by == U1.id`.
6. committed: `notes() == []`.

### EOS-V-02 — the draft is deleted with its lines and events
- **Rules:** `void_expense_order` V4, V5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3), but approved.
4. V = inv(E), linked.
5. VL = invl(V, 1, "100.00").
6. `vid = V.id`.

**When**
- `result = svc.void_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id, void_note="Duplicate order")`.

**Then**
1. returns: `result.id == E.id`.
2. committed: gone(V).
3. committed: gone(VL).
4. committed: `invoice_events` rows with `invoice_id == vid`: exactly 0.

### EOS-V-03 — the void's events: approvals cleared, invoice unlinked, then voided
- **Rules:** `void_expense_order` V7 [BUG-3070], V9
- **Kind:** bug
- **Expect:** xfail BUG-3070 (`xfail(strict=True, reason="BUG-3070")`)
- **Fails today on:** Then 4 (the `invoice_voided` metadata is `{"invoice_id": null}`: the id is read after the draft's delete has nulled it)

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3), but approved.
4. V = inv(E), linked.
5. invl(V, 1, "100.00").
6. `vid = V.id`.

**When**
- `result = svc.void_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id, void_note="Duplicate order")`.

**Then**
1. returns: `result.id == E.id`.
2. committed: `types(E) == ["approvals_reset", "invoice_voided", "eo_voided"]`.
3. committed: `EV(E)[0].description == RESETVOID`.
4. committed: `EV(E)[1].description == f"Invoice unlinked — expense order {E.expense_number} voided"`, `EV(E)[1].metadata_json == {"invoice_id": vid}`.
5. committed: `EV(E)[2].description == f"Expense order {E.expense_number} voided. Reason: Duplicate order"`, `EV(E)[2].metadata_json == {"void_note": "Duplicate order"}`.
6. committed: `[e.performed_by for e in EV(E)] == [U2.id, U2.id, U2.id]`.

### EOS-V-04 — with a linked invoice the approvals are cleared
- **Rules:** `void_expense_order` V7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. P3 = appr(E, U3), but approved.
4. P4 = appr(E, U4).
5. V = inv(E), linked.

**When**
- `result = svc.void_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id, void_note="Duplicate order")`.

**Then**
1. returns: `result.id == E.id`.
2. committed: re-read P3: `approved is False`, `approved_at is None`.
3. committed: unchanged(P4).

### EOS-V-05 — no recorded approval: no `approvals_reset` event
- **Rules:** `void_expense_order` V7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3).
4. V = inv(E), linked.

**When**
- `result = svc.void_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id, void_note="Duplicate order")`.

**Then**
1. returns: `result.id == E.id`.
2. committed: `types(E) == ["invoice_voided", "eo_voided"]`.

### EOS-V-06 — already voided: 400, the extra row is gone
- **Rules:** `void_expense_order` V2, Errors row 2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1", but voided.
2. X (after the commit point).

**When**
- `svc.void_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id, void_note="Again")`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Expense order is already voided"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. session: session clean.
7. unchanged: unchanged(E).
8. nothing written: nothing written.
9. committed: x_gone.

### EOS-V-07 — a completed order with its confirmed invoice: the "completed" 400, nothing written
- **Rules:** `void_expense_order` V3, V6a (V3 first), Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1", but completed.
2. line(E, 1, "100.00").
3. V = inv(E), but confirmed, linked.
4. X (after the commit point).

**When**
- `svc.void_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot void a completed expense order"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. unchanged: unchanged(E).
6. unchanged: unchanged(V).
7. nothing written: nothing written.
8. committed: x_gone.

### EOS-V-08 — a draft with payment history: the invoice manager's 400, the whole void undone
- **Rules:** `void_expense_order` V5, Errors row 4 [BUG-639] (invoice manager pass-through)
- **Kind:** bug
- **Expect:** xfail BUG-639
- **Fails today on:** Then 1 (the call raises IntegrityError, not HTTPException)

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. V = inv(E), linked.
4. P = pay(V, "100.00"), but voided pay.

**When**
- `svc.void_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == PAYHIST`.
4. unchanged: unchanged(E).
5. unchanged: unchanged(V).

### EOS-V-09 — a draft with payment history is never deleted and the order not voided (today and after the fix)
- **Rules:** `void_expense_order` V5; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. V = inv(E), linked.
4. P = pay(V, "100.00"), but voided pay.
5. X (after the commit point).

**When**
- `svc.void_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`, wrapped in `with pytest.raises(Exception):`.

**Then**
1. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
2. re-read V: `V is not None`, `invoice_status == "draft"`.
3. re-read P: `P is not None`, `is_voided is True`.
4. unchanged: unchanged(E).
5. count: `types(E) == []`.
6. committed: x_gone.

### EOS-V-10 — a linked invoice already voided is not touched; the order is voided and unlinked, with the intended event texts
- **Rules:** `void_expense_order` V6, V7, V9
- **Note:** the passing home of the void's event texts (verifier finding 2): the invoice is left alone, so its id is kept and every event is correct today (V-03 is xfail BUG-3070 on Then 4 only).
- **Kind:** happy
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. P3 = appr(E, U3), but approved.
4. V = inv(E), but voided-inv, linked.
5. `vid = V.id`.

**When**
- `result = svc.void_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`.

**Then**
1. returns: `result.id == E.id`.
2. committed: unchanged(V).
3. committed: re-read E: `voided is True`, `invoice_id is None`.
4. committed: re-read P3: `approved is False`.
5. committed: `types(E) == ["approvals_reset", "invoice_voided", "eo_voided"]`, `EV(E)[1].metadata_json == {"invoice_id": vid}`.
6. committed: `EV(E)[0].description == RESETVOID`.
7. committed: `EV(E)[1].description == f"Invoice unlinked — expense order {E.expense_number} voided"`.
8. committed: `EV(E)[2].description == f"Expense order {E.expense_number} voided. Reason: Cancelled"`.
9. committed: `EV(E)[2].metadata_json == {"void_note": "Cancelled"}`.
10. committed: `[e.performed_by for e in EV(E)] == [U2.id, U2.id, U2.id]`.

### EOS-V-11 — a linked W2 invoice is not touched; the order is voided and unlinked
- **Rules:** `void_expense_order` V4, V6, V7; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. Z = inv(E), but of W2, linked.
4. ZL = invl(Z, 1, "100.00").

**When**
- `result = svc.void_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`.

**Then**
1. returns: `result.id == E.id`.
2. committed: unchanged(Z).
3. committed: unchanged(ZL).
4. committed: re-read E: `voided is True`, `invoice_id is None`.
5. committed: `types(E) == ["invoice_voided", "eo_voided"]`.

### EOS-V-12 — a linked W0 invoice is not touched; the order is voided and unlinked
- **Rules:** `void_expense_order` V4, V6; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = inv(None), but of W0.
2. E = eo "1".
3. line(E, 1, "100.00").
4. `E.invoice_id = Z.id`, then `db.flush()`.

**When**
- `result = svc.void_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`.

**Then**
1. returns: `result.id == E.id`.
2. committed: unchanged(Z).
3. committed: re-read E: `voided is True`, `invoice_id is None`.

### EOS-V-13 — a confirmed invoice refuses the void; order, approvals, invoice and payments kept
- **Rules:** `void_expense_order` V6a, Errors row 5 [BUG-3069]
- **Kind:** bug
- **Expect:** xfail BUG-3069
- **Fails today on:** Then 1 (no error: the order is voided and unlinked)

**Given**
1. E = eo "1".
2. line(E, 1, "20.00").
3. P3 = appr(E, U3), but approved.
4. V = inv(E), but confirmed, `invoice_amount Decimal("20.00")`, `paid_amount Decimal("10.00")`, `payment_status "partial"`, linked (the payment state matches P, so a fix that refuses only unpaid bills fails).
5. P = pay(V, "10.00").
6. X (after the commit point).

**When**
- `svc.void_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == FINAL`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. session: session clean.
6. unchanged: unchanged(E).
7. unchanged: unchanged(P3).
8. unchanged: unchanged(V).
9. unchanged: unchanged(P).
10. nothing written: nothing written.
11. committed: x_gone.

### EOS-V-14 — a confirmed invoice is never deleted or changed by the void (today and after the fix)
- **Rules:** `void_expense_order` V5, V6a
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "20.00").
3. V = inv(E), but confirmed, `invoice_amount Decimal("20.00")`, linked.
4. P = pay(V, "10.00").

**When**
- `svc.void_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`, wrapped in `try: … except HTTPException: pass`.

**Then**
1. re-read V: `V is not None`, `invoice_status == "confirmed"`, `invoice_amount == Decimal("20.00")`.
2. unchanged: unchanged(P).
3. count: `invoice_payments` rows with `invoice_id == V.id`: exactly 1.

### EOS-V-15 — without an invoice, the approvals are cleared the same way
- **Rules:** `void_expense_order` V8 [BUG-3067]
- **Kind:** bug
- **Expect:** xfail BUG-3067
- **Fails today on:** Then 3 (the approval is kept: `approved` is still True)

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. P3 = appr(E, U3), but approved.

**When**
- `result = svc.void_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`.

**Then**
1. returns: `result.id == E.id`.
2. committed: re-read E: `voided is True`.
3. committed: re-read P3: `approved is False`, `approved_at is None`.
4. committed: `types(E) == ["approvals_reset", "eo_voided"]`.
5. committed: `EV(E)[0].description == RESETVOID`.

### EOS-V-16 — without an invoice: voided, no `invoice_voided` event (today and after the fix)
- **Rules:** `void_expense_order` V8, V9
- **Kind:** happy
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3), but approved.

**When**
- `result = svc.void_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`.

**Then**
1. returns: `result.id == E.id`.
2. committed: re-read E: `voided is True`, `void_note == "Cancelled"`, `voided_by == U2.id`, `voided_at == NOW`, `invoice_id is None`.
3. committed: `"invoice_voided" not in types(E)`.
4. committed: `types(E)[-1] == "eo_voided"`.

### EOS-V-17 — the schema rejects a spaces-only void note
- **Rules:** `void_expense_order` V10, Errors row 6 [BUG-3064]
- **Kind:** bug
- **Expect:** xfail BUG-3064
- **Fails today on:** Then 1 (no error: the blank note is accepted)

**Given**
1. Standing rows only.

**When**
- build `ExpenseOrderVoidRequest(void_note="   ")` (target `schema`; `svc` is not called).

**Then**
1. raises: `pydantic.ValidationError`.

### EOS-V-18 — the schema rejects an empty void note
- **Rules:** `void_expense_order` V10 [BUG-3064]
- **Kind:** bug
- **Expect:** xfail BUG-3064
- **Fails today on:** Then 1 (no error: `""` is accepted)

**Given**
1. Standing rows only.

**When**
- build `ExpenseOrderVoidRequest(void_note="")` (target `schema`; `svc` is not called).

**Then**
1. raises: `pydantic.ValidationError`.

### EOS-V-19 — the schema trims a padded void note
- **Rules:** `void_expense_order` V10 [BUG-3064]
- **Kind:** bug
- **Expect:** xfail BUG-3064
- **Fails today on:** Then 1 (the note keeps its spaces)

**Given**
1. Standing rows only.

**When**
- `result = ExpenseOrderVoidRequest(void_note="  Duplicate  ")` (target `schema`).

**Then**
1. returns: `result.void_note == "Duplicate"`.

### EOS-V-20 — the schema keeps a plain void note as typed
- **Rules:** `void_expense_order` V10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = ExpenseOrderVoidRequest(void_note="Duplicate order")` (target `schema`).

**Then**
1. returns: `result.void_note == "Duplicate order"`.

### EOS-V-21 — a missing order: 404, the extra row is gone
- **Rules:** `void_expense_order` V1, Errors row 1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. X (after the commit point).

**When**
- `svc.void_expense_order(db, eo_id=MISSING, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Expense order with ID 999999999 not found"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. session: session clean.
6. unchanged: unchanged(E).
7. committed: x_gone.

### EOS-V-22 — another workspace's order (W2): 404, not voided
- **Rules:** `void_expense_order` V1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E = eo "1".
2. Z = eo "9", but of W2.

**When**
- `svc.void_expense_order(db, eo_id=Z.id, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Expense order with ID {Z.id} not found"`.
4. unchanged: unchanged(Z).

### EOS-V-23 — a failing commit keeps the order, its draft and its approvals
- **Rules:** `void_expense_order` V9; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. P3 = appr(E, U3), but approved.
4. V = inv(E), linked.
5. VL = invl(V, 1, "100.00").

**When**
- `svc.void_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(E).
4. unchanged: unchanged(V).
5. unchanged: unchanged(VL).
6. unchanged: unchanged(P3).
7. nothing written: nothing written.

### EOS-V-24 — the order is read with a row lock before the checks
- **Rules:** `void_expense_order` V1, V1a [BUG-3062]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-3062
- **Fails today on:** Then 2 (the order is read without `FOR UPDATE`)

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. V = inv(E), linked.
4. `eid = E.id`.
5. Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `result = svc.void_expense_order(db, eo_id=eid, workspace_id=W1.id, user_id=U2.id, void_note="Cancelled")`.

**Then**
1. returns: `result.id == eid`.
2. statement: first-read lock(`expense_orders`).
3. statement: lock clause(`expense_orders`).
4. statement: locks `expense_orders` before `account_invoices`.

## `ExpenseOrderService.add_item`

### EOS-AI-01 — a line is added, stamped and committed; no invoice while approvals are not met
- **Rules:** `add_item` L1, L2; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. E = eo "1".
2. appr(E, U3).

**When**
- `result = svc.add_item(db, eo_id=E.id, item_in=ExpenseOrderItemCreate(description="Fee", quantity=Decimal("1"), unit_price=Decimal("50.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `isinstance(result, ExpenseOrderItem)`, `result.expense_order_id == E.id`.
3. committed: the `expense_order_items` row with `id == result.id` has `description == "Fee"`, `line_subtotal == Decimal("50.00")`.
4. committed: re-read E: `items_updated_at == NOW`, `invoice_id is None`.
5. committed: `account_invoices` rows with `order_id == E.id`: exactly 0.
6. committed: `notes() == []`.

### EOS-AI-02 — a linked draft gets the new line set
- **Rules:** `add_item` L2; `_sync_or_create_invoice` Y2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3).
4. V = inv(E), linked.
5. invl(V, 1, "100.00").

**When**
- `result = svc.add_item(db, eo_id=E.id, item_in=ExpenseOrderItemCreate(description="Fee", quantity=Decimal("1"), unit_price=Decimal("50.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.expense_order_id == E.id`.
2. committed: `[l.line_subtotal for l in LINES(V)] == [Decimal("100.00"), Decimal("50.00")]`.
3. committed: re-read V: `invoice_amount == Decimal("150.00")`, `invoice_status == "draft"`.
4. committed: `account_invoices` rows with `order_id == E.id`: exactly 1.

### EOS-AI-03 — a waived order with an account gets its draft on the first line, and the draft notice
- **Rules:** `add_item` L2; `_sync_or_create_invoice` Y7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1", but waived.

**When**
- `result = svc.add_item(db, eo_id=E.id, item_in=ExpenseOrderItemCreate(description="Fee", quantity=Decimal("1"), unit_price=Decimal("50.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.expense_order_id == E.id`.
2. committed: re-read E: `invoice_id is not None`.
3. committed: the `account_invoices` row with `id == E.invoice_id` has `invoice_status == "draft"`, `invoice_amount == Decimal("50.00")`.
4. committed: `recips() == [U1.id]`.
5. committed: `notes()[0].preview == DRAFTP`, `notes()[0].notification_type == "invoice_action"`.

### EOS-AI-04 — a line that wipes approvals writes no notification
- **Rules:** `add_item` L3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. P3 = appr(E, U3), but approved.

**When**
- `result = svc.add_item(db, eo_id=E.id, item_in=ExpenseOrderItemCreate(description="Fee", quantity=Decimal("1"), unit_price=Decimal("50.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.expense_order_id == E.id`.
2. committed: re-read P3: `approved is False`.
3. committed: `notes() == []`.

### EOS-AI-05 — a missing order: 404 passes unchanged, the extra row is gone
- **Rules:** `add_item` L1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. X (after the commit point).

**When**
- `svc.add_item(db, eo_id=MISSING, item_in=ExpenseOrderItemCreate(description="Fee", quantity=Decimal("1"), unit_price=Decimal("50.00")), workspace_id=W1.id, user_id=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Expense order with ID 999999999 not found"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. session: session clean.
7. nothing written: nothing written.
8. committed: x_gone.

### EOS-AI-06 — the draft step refusing the account undoes the new line
- **Rules:** `add_item` L2; `_create_draft_invoice` D4; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. A3 = acct "No Bills", but `allow_invoices False`.
2. E = eo "1", but waived, `account_id A3.id`.
3. X (after the commit point).

**When**
- `svc.add_item(db, eo_id=E.id, item_in=ExpenseOrderItemCreate(description="Fee", quantity=Decimal("1"), unit_price=Decimal("50.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "Invoices are not allowed for this account"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. session: session clean.
6. unchanged: unchanged(E).
7. count: `expense_order_items` rows with `expense_order_id == E.id`: exactly 0.
8. nothing written: nothing written.
9. committed: x_gone.

### EOS-AI-07 — a failing commit keeps the order without the line
- **Rules:** `add_item` L1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. appr(E, U3).

**When**
- `svc.add_item(db, eo_id=E.id, item_in=ExpenseOrderItemCreate(description="Fee", quantity=Decimal("1"), unit_price=Decimal("50.00")), workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(E).
4. nothing written: nothing written.

## `ExpenseOrderService.update_item`

### EOS-UI-01 — a price change is committed; the order is stamped and its draft follows
- **Rules:** `update_item` L4, L5; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. E = eo "1".
2. L1 = line(E, 1, "100.00").
3. appr(E, U3).
4. V = inv(E), linked.
5. invl(V, 1, "100.00").

**When**
- `result = svc.update_item(db, item_id=L1.id, item_in=ExpenseOrderItemUpdate(unit_price=Decimal("80.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == L1.id`.
3. committed: re-read L1: `unit_price == Decimal("80.00")`, `line_subtotal == Decimal("80.00")`.
4. committed: re-read E: `items_updated_at == NOW`.
5. committed: `[l.line_subtotal for l in LINES(V)] == [Decimal("80.00")]`.
6. committed: re-read V: `invoice_amount == Decimal("80.00")`.
7. committed: `notes() == []`.

### EOS-UI-02 — a call that changes nothing still stamps the order and resyncs the draft
- **Rules:** `update_item` L5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E = eo "1".
2. L1 = line(E, 1, "100.00").
3. V = inv(E), linked.
4. invl(V, 1, "100.00").

**When**
- `result = svc.update_item(db, item_id=L1.id, item_in=ExpenseOrderItemUpdate(unit_price=Decimal("100.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == L1.id`.
2. committed: re-read E: `items_updated_at == NOW`.
3. committed: `itypes(V).count("items_synced") == 1`.

### EOS-UI-03 — only the line's own order is stamped and resynced
- **Rules:** `update_item` L5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. VE = inv(E), linked.
4. invl(VE, 1, "100.00").
5. F = eo "2".
6. LF = line(F, 1, "30.00").

**When**
- `result = svc.update_item(db, item_id=LF.id, item_in=ExpenseOrderItemUpdate(unit_price=Decimal("35.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == LF.id`.
2. committed: re-read F: `items_updated_at == NOW`.
3. committed: re-read E: `items_updated_at is None`.
4. committed: `itypes(VE) == []`.

### EOS-UI-04 — a line edit that wipes approvals writes no notification
- **Rules:** `update_item` L5 (no notification, as L3)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1".
2. L1 = line(E, 1, "100.00").
3. P3 = appr(E, U3), but approved.

**When**
- `result = svc.update_item(db, item_id=L1.id, item_in=ExpenseOrderItemUpdate(unit_price=Decimal("80.00")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == L1.id`.
2. committed: re-read P3: `approved is False`.
3. committed: `notes() == []`.

### EOS-UI-05 — a missing line: 404 passes unchanged, the extra row is gone
- **Rules:** `update_item` L4; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. L1 = line(E, 1, "100.00").
3. X (after the commit point).

**When**
- `svc.update_item(db, item_id=MISSING, item_in=ExpenseOrderItemUpdate(unit_price=Decimal("80.00")), workspace_id=W1.id, user_id=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Expense order item not found"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. session: session clean.
7. unchanged: unchanged(L1).
8. committed: x_gone.

### EOS-UI-06 — a failing commit keeps the old price and the old draft
- **Rules:** `update_item` L4; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. L1 = line(E, 1, "100.00").
3. V = inv(E), linked.
4. VL = invl(V, 1, "100.00").

**When**
- `svc.update_item(db, item_id=L1.id, item_in=ExpenseOrderItemUpdate(unit_price=Decimal("80.00")), workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(L1).
4. unchanged: unchanged(VL).
5. re-read E: `items_updated_at is None`.

## `ExpenseOrderService.remove_item`

### EOS-RI-01 — the line is removed and committed; the deleted line is returned, its fields readable
- **Rules:** `remove_item` L6, L7; TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. L2 = line(E, 2, "50.00").
4. V = inv(E), linked.
5. invl(V, 1, "100.00").
6. invl(V, 2, "50.00").

**When**
- `result = svc.remove_item(db, item_id=L2.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.expense_order_id == E.id`, `result.line_number == 2`.
2. committed: gone(L2).
3. committed: re-read E: `items_updated_at == NOW`.
4. committed: `[l.line_subtotal for l in LINES(V)] == [Decimal("100.00")]`.
5. committed: `notes() == []`.

### EOS-RI-02 — removing the last line leaves a 0.00 draft with no lines
- **Rules:** `remove_item` L6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E = eo "1".
2. L1 = line(E, 1, "100.00").
3. V = inv(E), linked.
4. invl(V, 1, "100.00").

**When**
- `result = svc.remove_item(db, item_id=L1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.line_number == 1`.
2. committed: `LINES(V) == []`.
3. committed: re-read V: `invoice_status == "draft"`, `invoice_amount == Decimal("0.00")`.
4. committed: re-read E: `invoice_id == V.id`.

### EOS-RI-03 — a missing line: 404, the extra row is gone
- **Rules:** `remove_item` L6, L6a; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. L1 = line(E, 1, "100.00").
3. X (after the commit point).

**When**
- `svc.remove_item(db, item_id=MISSING, workspace_id=W1.id, user_id=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == "Expense order item not found"`.
3. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
4. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
5. session: session clean.
6. unchanged: unchanged(L1).
7. committed: x_gone.

### EOS-RI-04 — a failing commit keeps the line and the draft's lines
- **Rules:** `remove_item` L7; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. L1 = line(E, 1, "100.00").
3. V = inv(E), linked.
4. VL = invl(V, 1, "100.00").

**When**
- `svc.remove_item(db, item_id=L1.id, workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(L1).
4. unchanged: unchanged(VL).

### EOS-RI-05 — another workspace's line (W2): the same 404, the line kept
- **Rules:** `remove_item` L6a; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z2 = eo "9", but of W2.
2. L9 = line(Z2, 1, "100.00").
3. X (after the commit point).

**When**
- `svc.remove_item(db, item_id=L9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == "Expense order item not found"`.
3. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
4. unchanged: unchanged(L9).
5. unchanged: unchanged(Z2).
6. nothing written: nothing written.
7. committed: x_gone.

## `ExpenseOrderService.get_items`

### EOS-GI-01 — returns the order's lines by line number; neither commits nor rolls back
- **Rules:** `get_items` L8; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. E = eo "1".
2. L3 = line(E, 3, "30.00").
3. L1 = line(E, 1, "10.00").
4. F = eo "2".
5. line(F, 1, "99.00").
6. X (after the commit point).

**When**
- spies: `result = svc.get_items(db, eo_id=E.id, workspace_id=W1.id)`.

**Then**
1. returns: `[l.id for l in result] == [L1.id, L3.id]`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.

### EOS-GI-02 — another workspace's order: 404, no rollback
- **Rules:** `get_items` L8; TC6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = eo "9", but of W2.
2. line(Z, 1, "10.00").
3. X (after the commit point).

**When**
- spies: `svc.get_items(db, eo_id=Z.id, workspace_id=W1.id)`, wrapped in `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Expense order with ID {Z.id} not found"`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.

## `ExpenseOrderService._invoice_item_dicts`

Cards in this section build **transient** lines only (nothing added to the session): `ExpenseOrderItem(id=…, line_number=…, description=…, quantity=…, unit=…, unit_price=…, line_subtotal=…)`.

### EOS-S-01 — one dict per line, renumbered 1…N, every field mapped
- **Rules:** `_invoice_item_dicts` Returns, S1, S3, S4, S5
- **Kind:** happy
- **Expect:** pass

**Given**
1. `a = ExpenseOrderItem(id=501, line_number=1, description="Rent", quantity=Decimal("1"), unit=None, unit_price=Decimal("100.00"), line_subtotal=Decimal("100.00"))`.
2. `b = ExpenseOrderItem(id=502, line_number=3, description="Water", quantity=Decimal("2"), unit="month", unit_price=Decimal("12.50"), line_subtotal=Decimal("25.00"))`.
3. `c = ExpenseOrderItem(id=503, line_number=4, description="Gas", quantity=Decimal("0.5"), unit="kg", unit_price=Decimal("8.00"), line_subtotal=Decimal("4.00"))`.

**When**
- `result = svc._invoice_item_dicts([a, b, c])`.

**Then**
1. returns: `[d["line_number"] for d in result] == [1, 2, 3]`.
2. returns: `[d["description"] for d in result] == ["Rent", "Water", "Gas"]`.
3. returns: `[d["source_order_item_id"] for d in result] == [501, 502, 503]`.
4. returns: `[d["item_id"] for d in result] == [None, None, None]`, `[d["source_order_item_type"] for d in result] == ["eo_item", "eo_item", "eo_item"]`.
5. returns: `[d["unit"] for d in result] == [None, "month", "kg"]`.
6. returns: `[d["quantity"] for d in result] == [Decimal("1"), Decimal("2"), Decimal("0.5")]`.
7. returns: `[d["unit_price"] for d in result] == [Decimal("100.00"), Decimal("12.50"), Decimal("8.00")]`.
8. returns: `[d["line_subtotal"] for d in result] == [Decimal("100.00"), Decimal("25.00"), Decimal("4.00")]`.

### EOS-S-02 — the given order is kept, not the stored line numbers
- **Rules:** `_invoice_item_dicts` S1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `a = ExpenseOrderItem(id=601, line_number=7, description="Late", quantity=Decimal("1"), unit=None, unit_price=Decimal("1.00"), line_subtotal=Decimal("1.00"))`.
2. `b = ExpenseOrderItem(id=602, line_number=2, description="Early", quantity=Decimal("1"), unit=None, unit_price=Decimal("2.00"), line_subtotal=Decimal("2.00"))`.

**When**
- `result = svc._invoice_item_dicts([a, b])`.

**Then**
1. returns: `[(d["line_number"], d["source_order_item_id"]) for d in result] == [(1, 601), (2, 602)]`.

### EOS-S-03 — an empty description becomes "Expense item <line id>"
- **Rules:** `_invoice_item_dicts` S2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `a = ExpenseOrderItem(id=502, line_number=1, description="", quantity=Decimal("1"), unit=None, unit_price=Decimal("1.00"), line_subtotal=Decimal("1.00"))`.

**When**
- `result = svc._invoice_item_dicts([a])`.

**Then**
1. returns: `result[0]["description"] == "Expense item 502"`.

### EOS-S-04 — a None description becomes "Expense item <line id>"
- **Rules:** `_invoice_item_dicts` S2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `a = ExpenseOrderItem(id=503, line_number=1, description=None, quantity=Decimal("1"), unit=None, unit_price=Decimal("1.00"), line_subtotal=Decimal("1.00"))`.

**When**
- `result = svc._invoice_item_dicts([a])`.

**Then**
1. returns: `result[0]["description"] == "Expense item 503"`.

### EOS-S-05 — a one-space description is kept as it is
- **Rules:** `_invoice_item_dicts` S2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `a = ExpenseOrderItem(id=504, line_number=1, description=" ", quantity=Decimal("1"), unit=None, unit_price=Decimal("1.00"), line_subtotal=Decimal("1.00"))`.

**When**
- `result = svc._invoice_item_dicts([a])`.

**Then**
1. returns: `result[0]["description"] == " "`.

### EOS-S-06 — quantity 0 becomes 1; the subtotal stays as stored
- **Rules:** `_invoice_item_dicts` S4, S5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `a = ExpenseOrderItem(id=505, line_number=1, description="Old", quantity=Decimal("0"), unit=None, unit_price=Decimal("7.00"), line_subtotal=Decimal("0.00"))`.

**When**
- `result = svc._invoice_item_dicts([a])`.

**Then**
1. returns: `result[0]["quantity"] == Decimal(1)`.
2. returns: `result[0]["line_subtotal"] == Decimal("0.00")`, `result[0]["unit_price"] == Decimal("7.00")`.

### EOS-S-07 — quantity None becomes 1
- **Rules:** `_invoice_item_dicts` S4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `a = ExpenseOrderItem(id=506, line_number=1, description="Old", quantity=None, unit=None, unit_price=Decimal("7.00"), line_subtotal=Decimal("7.00"))`.

**When**
- `result = svc._invoice_item_dicts([a])`.

**Then**
1. returns: `result[0]["quantity"] == Decimal(1)`.

### EOS-S-08 — quantity 0.01 is kept
- **Rules:** `_invoice_item_dicts` S4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `a = ExpenseOrderItem(id=507, line_number=1, description="Tiny", quantity=Decimal("0.01"), unit=None, unit_price=Decimal("7.00"), line_subtotal=Decimal("0.07"))`.

**When**
- `result = svc._invoice_item_dicts([a])`.

**Then**
1. returns: `result[0]["quantity"] == Decimal("0.01")`.

### EOS-S-09 — price and subtotal None become 0
- **Rules:** `_invoice_item_dicts` S5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `a = ExpenseOrderItem(id=508, line_number=1, description="Free", quantity=Decimal("2"), unit=None, unit_price=None, line_subtotal=None)`.

**When**
- `result = svc._invoice_item_dicts([a])`.

**Then**
1. returns: `result[0]["unit_price"] == Decimal(0)`.
2. returns: `result[0]["line_subtotal"] == Decimal(0)`.
3. returns: `result[0]["quantity"] == Decimal("2")`.

### EOS-S-10 — no rounding and no recomputation of the subtotal
- **Rules:** `_invoice_item_dicts` S5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `a = ExpenseOrderItem(id=509, line_number=1, description="Odd", quantity=Decimal("2"), unit=None, unit_price=Decimal("3.333"), line_subtotal=Decimal("5.00"))`.

**When**
- `result = svc._invoice_item_dicts([a])`.

**Then**
1. returns: `result[0]["unit_price"] == Decimal("3.333")`.
2. returns: `result[0]["line_subtotal"] == Decimal("5.00")`.

### EOS-S-11 — an empty list gives an empty list
- **Rules:** `_invoice_item_dicts` S6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = svc._invoice_item_dicts([])`.

**Then**
1. returns: `result == []`.

## `ExpenseOrderService._create_draft_invoice`

### EOS-D-01 — the draft carries the order's account, due date, notes and link fields
- **Rules:** `_create_draft_invoice` D2, D2a, D6
- **Kind:** happy
- **Expect:** pass

**Given**
1. E = eo "1", but `due_date date(2026, 10, 15)`.
2. line(E, 1, "100.00").

**When**
- `result = svc._create_draft_invoice(db, eo=E, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == E.id`, `result.invoice_id is not None`.
2. re-read the `account_invoices` row with `id == result.invoice_id`: `workspace_id == W1.id`, `account_id == A1.id`, `invoice_type == "payable"`, `invoice_status == "draft"`.
3. re-read that row: `order_type == "expense_order"`, `order_id == E.id`, `due_date == date(2026, 10, 15)`.
4. re-read that row: `description == f"Auto-created from expense order {E.expense_number}"`, `notes == "Office rent"`, `allow_payments is True`.
5. re-read that row: `invoice_number is None`, `vendor_invoice_number is None`, `payment_locked_reason is None`.
6. re-read E: `invoice_id == result.invoice_id`.
7. re-read that row: `created_by == U2.id` (D2a).

### EOS-D-02 — the draft's lines mirror the order's lines; amount is their sum
- **Rules:** `_create_draft_invoice` D2 (amount follows the lines), D6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. line(E, 3, "25.50").

**When**
- `result = svc._create_draft_invoice(db, eo=E, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.invoice_id is not None`.
2. re-read: `[l.line_number for l in LINES(result.invoice_id)] == [1, 2]`.
3. re-read: `[l.line_subtotal for l in LINES(result.invoice_id)] == [Decimal("100.00"), Decimal("25.50")]`.
4. re-read the `account_invoices` row with `id == result.invoice_id`: `invoice_amount == Decimal("125.50")`.
5. re-read: `itypes(result.invoice_id) == ["created", "items_synced"]`.

### EOS-D-03 — one `invoice_created` order event; no notification
- **Rules:** `_create_draft_invoice` D7, D8
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").

**When**
- `result = svc._create_draft_invoice(db, eo=E, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.invoice_id is not None`.
2. count: `types(E) == ["invoice_created"]`.
3. re-read: `EV(E)[0].description == f"Invoice #{result.invoice_id} created from expense order"`, `EV(E)[0].metadata_json == {"invoice_id": result.invoice_id}`, `EV(E)[0].performed_by == U2.id`.
4. count: `notes() == []`.

### EOS-D-04 — an order with no lines gives a 0.00 draft with no lines
- **Rules:** `_create_draft_invoice` D6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E = eo "1".

**When**
- `result = svc._create_draft_invoice(db, eo=E, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.invoice_id is not None`.
2. re-read the `account_invoices` row with `id == result.invoice_id`: `invoice_amount == Decimal("0.00")`, `invoice_status == "draft"`.
3. count: `invoice_items` rows with `invoice_id == result.invoice_id`: exactly 0.

### EOS-D-05 — no account: 422, nothing written
- **Rules:** `_create_draft_invoice` D1
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1", but `account_id None`.
2. line(E, 1, "100.00").

**When**
- `svc._create_draft_invoice(db, eo=E, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail == "Set an account on the expense order before creating an invoice"`.
4. session: session clean.
5. nothing written: nothing written.
6. unchanged: unchanged(E).

### EOS-D-06 — a deleted account: 400 passes unchanged
- **Rules:** `_create_draft_invoice` D4, R4a (deleted = `is_deleted True`)
- **Kind:** error
- **Expect:** pass

**Given**
1. AD = acct "Old Vendor", but `is_deleted True`.
2. E = eo "1", but `account_id AD.id`.

**When**
- `svc._create_draft_invoice(db, eo=E, workspace_id=W1.id, user_id=U2.id)`, inside `db.begin_nested()`; the savepoint is rolled back after the raise.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot create invoice for deleted account"`.
4. count: `account_invoices` rows of W1: exactly 0.

### EOS-D-07 — an inactive account: 400 passes unchanged
- **Rules:** `_create_draft_invoice` D4
- **Kind:** error
- **Expect:** pass

**Given**
1. AQ = acct "Sleepy", but `is_active False`.
2. E = eo "1", but `account_id AQ.id`.

**When**
- `svc._create_draft_invoice(db, eo=E, workspace_id=W1.id, user_id=U2.id)`, inside `db.begin_nested()`; the savepoint is rolled back after the raise.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot create invoice for inactive account"`.
4. count: `account_invoices` rows of W1: exactly 0.

### EOS-D-08 — an account that does not allow invoices: 403 passes unchanged
- **Rules:** `_create_draft_invoice` D4
- **Kind:** error
- **Expect:** pass

**Given**
1. A3 = acct "No Bills", but `allow_invoices False`.
2. E = eo "1", but `account_id A3.id`.

**When**
- `svc._create_draft_invoice(db, eo=E, workspace_id=W1.id, user_id=U2.id)`, inside `db.begin_nested()`; the savepoint is rolled back after the raise.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "Invoices are not allowed for this account"`.
4. count: `account_invoices` rows of W1: exactly 0.

### EOS-D-09 — a W2 account becomes the 422 "not found in this workspace", the 404 as its cause
- **Rules:** `_create_draft_invoice` D5; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E = eo "1", but `account_id A9.id`.

**When**
- `svc._create_draft_invoice(db, eo=E, workspace_id=W1.id, user_id=U2.id)`, inside `db.begin_nested()`; the savepoint is rolled back after the raise.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail == "Cannot create invoice: selected account was not found in this workspace"`.
4. raises: `isinstance(exc.value.__cause__, HTTPException)`, `exc.value.__cause__.status_code == 404`.
5. count: `account_invoices` rows of W1 and W2: exactly 0.

### EOS-D-10 — a W0 account becomes the same 422
- **Rules:** `_create_draft_invoice` D5; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E = eo "1", but `account_id A0.id`.

**When**
- `svc._create_draft_invoice(db, eo=E, workspace_id=W1.id, user_id=U2.id)`, inside `db.begin_nested()`; the savepoint is rolled back after the raise.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail == "Cannot create invoice: selected account was not found in this workspace"`.

### EOS-D-11 — the order's invoice date is the UTC date
- **Rules:** `_create_draft_invoice` D3 [BUG-3063]
- **Kind:** bug
- **Expect:** xfail BUG-3063
- **Fails today on:** Then 2 (the date is `date.today()`, the machine's real local date, not NOW's date)

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").

**When**
- `result = svc._create_draft_invoice(db, eo=E, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.invoice_id is not None`.
2. re-read the `account_invoices` row with `id == result.invoice_id`: `invoice_date == date(2026, 9, 27)`.

### EOS-D-12 — no invoice amount is sent to the invoice manager
- **Rules:** `_create_draft_invoice` D2 [BUG-627]
- **Kind:** bug
- **Expect:** xfail BUG-627
- **Author:** claude
- **Fails today on:** Then 2 (`invoice_amount` is sent as 0.00)

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").

**When**
- `result = svc._create_draft_invoice(db, eo=E, workspace_id=W1.id, user_id=U2.id)`, with `patch.object(svc.account_invoice_manager, "create_invoice", wraps=svc.account_invoice_manager.create_invoice) as ci` around it.

**Then**
1. returns: `result.invoice_id is not None`.
2. mock called: `"invoice_amount" not in ci.call_args.kwargs["invoice_data"].model_fields_set` (D2a: called by keyword).

### EOS-D-13 — the draft is flushed, never committed
- **Rules:** `_create_draft_invoice` Persistence (flush only)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").

**When**
- spies: `result = svc._create_draft_invoice(db, eo=E, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.invoice_id is not None`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. committed: `account_invoices` rows of W1: exactly 0.

### EOS-D-14 — `create_invoice` is called once, by keyword
- **Rules:** `_create_draft_invoice` D2a
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").

**When**
- `result = svc._create_draft_invoice(db, eo=E, workspace_id=W1.id, user_id=U2.id)`, with `patch.object(svc.account_invoice_manager, "create_invoice", wraps=svc.account_invoice_manager.create_invoice) as ci` around it.

**Then**
1. returns: `result.invoice_id is not None`.
2. mock called: `ci.call_count == 1`, `ci.call_args.args == ()`.
3. mock called: `set(ci.call_args.kwargs) == {"session", "invoice_data", "workspace_id", "user_id"}`.
4. mock called: `ci.call_args.kwargs["session"] is db`, `ci.call_args.kwargs["workspace_id"] == W1.id`, `ci.call_args.kwargs["user_id"] == U2.id`.
5. mock called: `type(ci.call_args.kwargs["invoice_data"]).__name__ == "AccountInvoiceCreate"`.

## `ExpenseOrderService._resync_draft_invoice`

### EOS-R-01 — the draft's lines are replaced by the order's current lines
- **Rules:** `_resync_draft_invoice` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. line(E, 4, "50.00").
4. V = inv(E), but `notes "Office rent"`, linked.
5. invl(V, 1, "999.00").

**When**
- `svc._resync_draft_invoice(db, eo=E, invoice=V, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read V: `[(l.line_number, l.line_subtotal) for l in LINES(V)] == [(1, Decimal("100.00")), (2, Decimal("50.00"))]`.
2. re-read V: `invoice_amount == Decimal("150.00")`.
3. count: `itypes(V) == ["items_synced"]`.

### EOS-R-02 — nothing differs: still one `items_synced` event, no header update
- **Rules:** `_resync_draft_invoice` R1, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. V = inv(E), but `notes "Office rent"`, linked.
4. invl(V, 1, "100.00").

**When**
- `svc._resync_draft_invoice(db, eo=E, invoice=V, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. count: `itypes(V) == ["items_synced"]`.
2. re-read V: `account_id == A1.id`, `due_date is None`, `notes == "Office rent"`.

### EOS-R-03 — a different due date is copied in one header update
- **Rules:** `_resync_draft_invoice` R2, R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1", but `due_date date(2026, 10, 15)`.
2. V = inv(E), but `due_date date(2026, 10, 1)`, `notes "Office rent"`, linked.

**When**
- `svc._resync_draft_invoice(db, eo=E, invoice=V, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read V: `due_date == date(2026, 10, 15)`.
2. count: `itypes(V).count("item_manually_updated") == 1`.

### EOS-R-04 — the order's due date cleared: the invoice's due date is cleared too
- **Rules:** `_resync_draft_invoice` R2, R2a (the order's `due_date` is NULL on the row; works today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E = eo "1".
2. V = inv(E), but `due_date date(2026, 10, 1)`, `notes "Office rent"`, linked.

**When**
- `svc._resync_draft_invoice(db, eo=E, invoice=V, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read V: `due_date is None`.

### EOS-R-05 — a different non-empty description replaces the notes
- **Rules:** `_resync_draft_invoice` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1", but `description "Water bill"`.
2. V = inv(E), but `notes "Office rent"`, linked.

**When**
- `svc._resync_draft_invoice(db, eo=E, invoice=V, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read V: `notes == "Water bill"`.
2. count: `itypes(V).count("item_manually_updated") == 1`.

### EOS-R-06 — an empty order description never clears the notes
- **Rules:** `_resync_draft_invoice` R3, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E = eo "1".
2. V = inv(E), but `notes "Office rent"`, linked.
3. `E.description = ""` in memory (no flush) (after the commit point).

**When**
- `svc._resync_draft_invoice(db, eo=E, invoice=V, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read V: `notes == "Office rent"`.
2. count: `"item_manually_updated" not in itypes(V)`.

### EOS-R-07 — another account moves the draft to it
- **Rules:** `_resync_draft_invoice` R4, R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1", but `account_id A2.id`.
2. V = inv(E), but `notes "Office rent"`, linked.

**When**
- `svc._resync_draft_invoice(db, eo=E, invoice=V, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read V: `account_id == A2.id`.
2. count: `itypes(V).count("item_manually_updated") == 1`.

### EOS-R-08 — an inactive account is refused with the invoice manager's 400
- **Rules:** `_resync_draft_invoice` R4b [BUG-629]
- **Kind:** bug
- **Expect:** xfail BUG-629 (`xfail(strict=True, reason="BUG-629")`)
- **Fails today on:** Then 1 (no error: the draft branch checks only existence and `is_deleted`, so the draft moves to the inactive account)

**Given**
1. AQ = acct "Sleepy", but `is_active False`.
2. E = eo "1", but `account_id AQ.id`.
3. V = inv(E), but `notes "Office rent"`, linked.

**When**
- `svc._resync_draft_invoice(db, eo=E, invoice=V, workspace_id=W1.id, user_id=U2.id)`, inside `db.begin_nested()`; the savepoint is rolled back after the raise.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot assign invoice to inactive account"`.
4. re-read V: `account_id == A1.id`.

### EOS-R-09 — an account that does not allow invoices is refused with 403
- **Rules:** `_resync_draft_invoice` R4b [BUG-629]
- **Kind:** bug
- **Expect:** xfail BUG-629 (`xfail(strict=True, reason="BUG-629")`)
- **Fails today on:** Then 1 (no error: the draft branch checks only existence and `is_deleted`, so the draft moves to the non-invoicing account)

**Given**
1. A3 = acct "No Bills", but `allow_invoices False`.
2. E = eo "1", but `account_id A3.id`.
3. V = inv(E), but `notes "Office rent"`, linked.

**When**
- `svc._resync_draft_invoice(db, eo=E, invoice=V, workspace_id=W1.id, user_id=U2.id)`, inside `db.begin_nested()`; the savepoint is rolled back after the raise.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "Invoices are not allowed for this account"`.
4. re-read V: `account_id == A1.id`.

### EOS-R-10 — a deleted account is refused with 400
- **Rules:** `_resync_draft_invoice` R4, R4a
- **Kind:** error
- **Expect:** pass

**Given**
1. AD = acct "Old Vendor", but `is_deleted True`.
2. E = eo "1", but `account_id AD.id`.
3. V = inv(E), but `notes "Office rent"`, linked.

**When**
- `svc._resync_draft_invoice(db, eo=E, invoice=V, workspace_id=W1.id, user_id=U2.id)`, inside `db.begin_nested()`; the savepoint is rolled back after the raise.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`, `exc.value.detail == "Cannot assign invoice to deleted account"` (R4a).
3. re-read V: `account_id == A1.id`.

### EOS-R-11 — an order without an account leaves the invoice's account alone
- **Rules:** `_resync_draft_invoice` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E = eo "1", but `account_id None`.
2. V = inv(E), but `notes "Office rent"`, linked.

**When**
- `svc._resync_draft_invoice(db, eo=E, invoice=V, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read V: `account_id == A1.id`.
2. count: `"item_manually_updated" not in itypes(V)`.

### EOS-R-12 — due date, notes and account all differ: one header update
- **Rules:** `_resync_draft_invoice` R2, R3, R4, R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1", but `account_id A2.id`, `due_date date(2026, 10, 15)`, `description "Water bill"`.
2. V = inv(E), but `notes "Office rent"`, linked.

**When**
- `svc._resync_draft_invoice(db, eo=E, invoice=V, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read V: `account_id == A2.id`, `due_date == date(2026, 10, 15)`, `notes == "Water bill"`.
2. count: `itypes(V).count("item_manually_updated") == 1`.
3. count: `itypes(V).count("items_synced") == 1`.

### EOS-R-13 — the resync is flushed, never committed
- **Rules:** `_resync_draft_invoice` Persistence (flush only)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. V = inv(E), linked.

**When**
- spies: `svc._resync_draft_invoice(db, eo=E, invoice=V, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. mock called: `cm.call_count == 0`.
2. mock called: `rb.call_count == 0`.
3. committed: `invoice_items` rows with `invoice_id == V.id`: exactly 0.

## `ExpenseOrderService._sync_or_create_invoice`

### EOS-Y-01 — a missing order: 404
- **Rules:** `_sync_or_create_invoice` Y1
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".

**When**
- `svc._sync_or_create_invoice(db, eo_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Expense order with ID 999999999 not found"`.
4. nothing written: nothing written.

### EOS-Y-02 — a linked draft is resynced; no second invoice
- **Rules:** `_sync_or_create_invoice` Y2
- **Kind:** happy
- **Expect:** pass

**Given**
1. E = eo "1", but waived.
2. line(E, 1, "100.00").
3. V = inv(E), linked.
4. invl(V, 1, "999.00").

**When**
- `svc._sync_or_create_invoice(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read V: `[l.line_subtotal for l in LINES(V)] == [Decimal("100.00")]`.
2. count: `account_invoices` rows with `order_id == E.id`: exactly 1.
3. count: `types(E) == []`.
4. count: `notes() == []`.

### EOS-Y-03 — a linked confirmed invoice: nothing happens
- **Rules:** `_sync_or_create_invoice` Y3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E = eo "1", but waived.
2. line(E, 1, "100.00").
3. V = inv(E), but confirmed, linked.
4. VL = invl(V, 1, "999.00").

**When**
- `svc._sync_or_create_invoice(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. unchanged: unchanged(V).
2. unchanged: unchanged(VL).
3. unchanged: unchanged(E).
4. nothing written: nothing written.

### EOS-Y-04 — a linked voided invoice: nothing happens, no new draft
- **Rules:** `_sync_or_create_invoice` Y3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E = eo "1", but waived.
2. line(E, 1, "100.00").
3. V = inv(E), but voided-inv, linked.

**When**
- `svc._sync_or_create_invoice(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. unchanged: unchanged(V).
2. unchanged: unchanged(E).
3. nothing written: nothing written.

### EOS-Y-05 — a linked W2 invoice: nothing happens, no new draft
- **Rules:** `_sync_or_create_invoice` Y3; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E = eo "1", but waived.
2. line(E, 1, "100.00").
3. Z = inv(E), but of W2, linked.
4. ZL = invl(Z, 1, "999.00").

**When**
- `svc._sync_or_create_invoice(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. unchanged: unchanged(Z).
2. unchanged: unchanged(ZL).
3. unchanged: unchanged(E).
4. nothing written: nothing written.

### EOS-Y-06 — no invoice and approvals not met: nothing happens
- **Rules:** `_sync_or_create_invoice` Y4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3).

**When**
- `svc._sync_or_create_invoice(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. unchanged: unchanged(E).
2. nothing written: nothing written.

### EOS-Y-07 — met but no account: one `invoice_autocreate_skipped` event, no invoice
- **Rules:** `_sync_or_create_invoice` Y5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1", but `account_id None`.
2. line(E, 1, "100.00").
3. appr(E, U3), but approved.

**When**
- `svc._sync_or_create_invoice(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. count: `types(E) == ["invoice_autocreate_skipped"]`.
2. re-read: `EV(E)[0].description == SKIPMSG`, `EV(E)[0].performed_by == U2.id`.
3. count: `account_invoices` rows of W1: exactly 0.
4. count: `notes() == []`.

### EOS-Y-08 — the skip is logged again on every call in that state
- **Rules:** `_sync_or_create_invoice` Y5 (Q5)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1", but waived, `account_id None`.
2. line(E, 1, "100.00").
3. `svc._sync_or_create_invoice(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)` once (after the commit point).

**When**
- `svc._sync_or_create_invoice(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. count: `types(E) == ["invoice_autocreate_skipped", "invoice_autocreate_skipped"]`.
2. count: `account_invoices` rows of W1: exactly 0.

### EOS-Y-09 — met with an account but no lines: nothing happens
- **Rules:** `_sync_or_create_invoice` Y6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E = eo "1", but waived.

**When**
- `svc._sync_or_create_invoice(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. unchanged: unchanged(E).
2. nothing written: nothing written.

### EOS-Y-10 — met with an account and a line: a draft and the draft notice
- **Rules:** `_sync_or_create_invoice` Y7
- **Kind:** happy
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3), but approved.
4. appr(E, U5), but approved.

**When**
- `svc._sync_or_create_invoice(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read E: `invoice_id is not None`.
2. re-read the `account_invoices` row with `id == E.invoice_id`: `invoice_status == "draft"`, `invoice_amount == Decimal("100.00")`, `order_id == E.id`.
3. count: `types(E) == ["invoice_created"]`.
4. count: `recips() == [U1.id, U3.id]`.
5. re-read: every row of `notes()` has `preview == DRAFTP`, `source_type == "invoice"`, `source_id == E.invoice_id`, `entity_id == E.id`.

### EOS-Y-11 — the step is flushed, never committed
- **Rules:** `_sync_or_create_invoice` Persistence (flush only)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1", but waived.
2. line(E, 1, "100.00").

**When**
- spies: `svc._sync_or_create_invoice(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. mock called: `cm.call_count == 0`.
2. mock called: `rb.call_count == 0`.
3. committed: `account_invoices` rows of W1: exactly 0.

## `ExpenseOrderService.create_invoice_for_expense_order`

### EOS-I-01 — a met order gets its draft by hand, committed, with the draft notice
- **Rules:** `create_invoice_for_expense_order` I5; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3), but approved.

**When**
- `result = svc.create_invoice_for_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == E.id`, `result.invoice_id is not None`.
3. committed: the `account_invoices` row with `id == result.invoice_id` has `invoice_status == "draft"`, `invoice_type == "payable"`, `order_id == E.id`, `invoice_amount == Decimal("100.00")`.
4. committed: `types(E) == ["invoice_created"]`.
5. committed: `recips() == [U1.id, U3.id]`.
6. committed: every row of `notes()` has `preview == DRAFTP`, `notification_type == "invoice_action"`.

### EOS-I-02 — a draft already linked: 409, the extra row is gone
- **Rules:** `create_invoice_for_expense_order` I2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3), but approved.
4. V = inv(E), linked.
5. X (after the commit point).

**When**
- `svc.create_invoice_for_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Invoice already exists for this expense order"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. session: session clean.
7. unchanged: unchanged(E).
8. nothing written: nothing written.
9. committed: x_gone.

### EOS-I-03 — a voided invoice linked still counts: 409
- **Rules:** `create_invoice_for_expense_order` I2 (any status)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3), but approved.
4. V = inv(E), but voided-inv, linked.

**When**
- `svc.create_invoice_for_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Invoice already exists for this expense order"`.
4. nothing written: nothing written.

### EOS-I-04 — a completed order is refused by the "already exists" check
- **Rules:** `create_invoice_for_expense_order` I6, I2
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1", but completed.
2. line(E, 1, "100.00").
3. V = inv(E), but confirmed, linked.

**When**
- `svc.create_invoice_for_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Invoice already exists for this expense order"`.
4. unchanged: unchanged(V).

### EOS-I-05 — a voided waived order is refused; no draft is made
- **Rules:** `create_invoice_for_expense_order` I3, Errors row I3 [BUG-3065]
- **Kind:** bug
- **Expect:** xfail BUG-3065
- **Fails today on:** Then 1 (no error: a new draft is made for the voided order)

**Given**
1. E = eo "1", but voided, waived.
2. line(E, 1, "50.00").
3. X (after the commit point).

**When**
- `svc.create_invoice_for_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Expense order is voided"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. session: session clean.
6. unchanged: unchanged(E).
7. nothing written: nothing written.
8. committed: x_gone.

### EOS-I-06 — a voided order with unmet approvals gets the "voided" text, not the approvals one
- **Rules:** `create_invoice_for_expense_order` I3, I4 [BUG-3065]
- **Kind:** bug
- **Expect:** xfail BUG-3065
- **Fails today on:** Then 2 (the detail is `Required approvals are not met`)

**Given**
1. E = eo "1", but voided.
2. line(E, 1, "50.00").
3. appr(E, U3).

**When**
- `svc.create_invoice_for_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Expense order is voided"`.
3. nothing written: nothing written.

### EOS-I-07 — a voided order with unmet approvals never gets a draft (today and after the fix)
- **Rules:** `create_invoice_for_expense_order` I3, I4
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1", but voided.
2. line(E, 1, "50.00").
3. appr(E, U3).

**When**
- `svc.create_invoice_for_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. unchanged: unchanged(E).
4. nothing written: nothing written.

### EOS-I-08 — a voided order with an invoice still linked gets the "voided" 400, not the 409
- **Rules:** `create_invoice_for_expense_order` I3, I2 (check order I1, I3, I2, I4) [BUG-3065]
- **Kind:** bug
- **Expect:** xfail BUG-3065
- **Fails today on:** Then 2 (the status is 409, `Invoice already exists for this expense order`)

**Given**
1. Z = inv(None), but voided-inv.
2. E = eo "1", but voided, waived.
3. `E.invoice_id = Z.id`, then `db.flush()`.
4. X (after the commit point).

**When**
- `svc.create_invoice_for_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Expense order is voided"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. unchanged: unchanged(E).
6. unchanged: unchanged(Z).
7. nothing written: nothing written.
8. committed: x_gone.

### EOS-I-09 — approvals not met: 400, no draft
- **Rules:** `create_invoice_for_expense_order` I4; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3).
4. X (after the commit point).

**When**
- `svc.create_invoice_for_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == NOTMET`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. unchanged: unchanged(E).
6. nothing written: nothing written.
7. committed: x_gone.

### EOS-I-10 — no account: 422, no draft
- **Rules:** `create_invoice_for_expense_order` I5; `_create_draft_invoice` D1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1", but `account_id None`.
2. line(E, 1, "100.00").
3. appr(E, U3), but approved.
4. X (after the commit point).

**When**
- `svc.create_invoice_for_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail == "Set an account on the expense order before creating an invoice"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. unchanged: unchanged(E).
6. nothing written: nothing written.
7. committed: x_gone.

### EOS-I-11 — no lines: a 0.00 draft with no lines is committed
- **Rules:** `create_invoice_for_expense_order` I5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E = eo "1", but waived.

**When**
- `result = svc.create_invoice_for_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.invoice_id is not None`.
2. committed: the `account_invoices` row with `id == result.invoice_id` has `invoice_amount == Decimal("0.00")`, `invoice_status == "draft"`.
3. committed: `invoice_items` rows with `invoice_id == result.invoice_id`: exactly 0.

### EOS-I-12 — a missing order: 404, the extra row is gone
- **Rules:** `create_invoice_for_expense_order` I1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. X (after the commit point).

**When**
- `svc.create_invoice_for_expense_order(db, eo_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Expense order with ID 999999999 not found"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. session: session clean.
6. committed: x_gone.

### EOS-I-13 — another workspace's order (W2): 404, no draft
- **Rules:** `create_invoice_for_expense_order` I1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E = eo "1".
2. Z = eo "9", but of W2, waived, `account_id A9.id`.
3. line(Z, 1, "100.00").

**When**
- `svc.create_invoice_for_expense_order(db, eo_id=Z.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Expense order with ID {Z.id} not found"`.
4. unchanged: unchanged(Z).
5. nothing written: nothing written.

### EOS-I-14 — a failing commit leaves no draft and no link
- **Rules:** `create_invoice_for_expense_order` I5; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3), but approved.

**When**
- `svc.create_invoice_for_expense_order(db, eo_id=E.id, workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read E: `invoice_id is None`.
4. nothing written: nothing written.

### EOS-I-15 — the order is read with a row lock before the checks
- **Rules:** `create_invoice_for_expense_order` I1, I1a [BUG-3062]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-3062
- **Fails today on:** Then 2 (the order is read without `FOR UPDATE`)

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3), but approved.
4. `eid = E.id`.
5. Statement recorder on; `db.expunge_all()` (after the commit point).

**When**
- `result = svc.create_invoice_for_expense_order(db, eo_id=eid, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == eid`.
2. statement: first-read lock(`expense_orders`).
3. statement: lock clause(`expense_orders`).
4. statement: locks `expense_orders` before `expense_order_approvers`.

## `ExpenseOrderService.list_approvers`

### EOS-LA-01 — returns the order's approvers with profiles; neither commits nor rolls back
- **Rules:** `list_approvers` A1; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. E = eo "1".
2. appr(E, U3).
3. appr(E, U4), but approved.
4. F = eo "2".
5. appr(F, U2).
6. X (after the commit point).

**When**
- spies: `result = svc.list_approvers(db, eo_id=E.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `{(a.user_id, p.id) for a, p, pos in result} == {(U3.id, U3.id), (U4.id, U4.id)}`.
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 0`.
5. session: `X in db`.

### EOS-LA-02 — another workspace's order: 404, no rollback
- **Rules:** `list_approvers` A1; TC6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = eo "9", but of W2.
2. X (after the commit point).

**When**
- spies: `svc.list_approvers(db, eo_id=Z.id, workspace_id=W1.id)`, wrapped in `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Expense order with ID {Z.id} not found"`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.

## `ExpenseOrderService.approval_summary_for`

### EOS-AS-01 — one of two approved: (1, 2, False); neither commits nor rolls back
- **Rules:** `approval_summary_for` A2; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. E = eo "1".
2. appr(E, U3), but approved.
3. appr(E, U4).
4. X (after the commit point).

**When**
- spies: `result = svc.approval_summary_for(db, eo_id=E.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (1, 2, False)`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.

### EOS-AS-02 — both approved: (2, 2, True)
- **Rules:** `approval_summary_for` A2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E = eo "1".
2. appr(E, U3), but approved.
3. appr(E, U4), but approved.

**When**
- `result = svc.approval_summary_for(db, eo_id=E.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (2, 2, True)`.

### EOS-AS-03 — waived (required 0), no approvers: met
- **Rules:** `approval_summary_for` A2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E = eo "1", but waived.

**When**
- `result = svc.approval_summary_for(db, eo_id=E.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (0, 0, True)`.

### EOS-AS-04 — no approvers and no requirement: 1 required, not met
- **Rules:** `approval_summary_for` A2 [BUG-755] (manager pass-through)
- **Kind:** bug
- **Expect:** xfail BUG-755
- **Fails today on:** Then 1 (today `(0, 0, True)`)

**Given**
1. E = eo "1".

**When**
- `result = svc.approval_summary_for(db, eo_id=E.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (0, 1, False)`.

### EOS-AS-05 — another workspace's order: 404, no rollback
- **Rules:** `approval_summary_for` A2; TC6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = eo "9", but of W2.
2. X (after the commit point).

**When**
- spies: `svc.approval_summary_for(db, eo_id=Z.id, workspace_id=W1.id)`, wrapped in `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Expense order with ID {Z.id} not found"`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.

## `ExpenseOrderService.add_approver`

### EOS-AA-01 — the approver is added and committed
- **Rules:** `add_approver` A3; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").

**When**
- `result = svc.add_approver(db, eo_id=E.id, user_id=U4.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `isinstance(result, ExpenseOrderApprover)`, `result.user_id == U4.id`.
3. committed: the `expense_order_approvers` row with `id == result.id` has `expense_order_id == E.id`, `assigned_by == U2.id`, `approved is False`.

### EOS-AA-02 — ready order: the new approver is assigned, the other pending approver is reminded
- **Rules:** `add_approver` A4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3).

**When**
- `result = svc.add_approver(db, eo_id=E.id, user_id=U4.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. returns: `result.user_id == U4.id`.
2. committed: `sorted((n.recipient_user_id, n.notification_type) for n in notes()) == sorted([(U4.id, "approval_assigned"), (U3.id, "approval_pending")])`.

### EOS-AA-03 — order not ready: the new approver is assigned, the creator gets the gap notice
- **Rules:** `add_approver` A4, A4a
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1".
2. appr(E, U3).

**When**
- `result = svc.add_approver(db, eo_id=E.id, user_id=U4.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. returns: `result.user_id == U4.id`.
2. committed: `sorted((n.recipient_user_id, n.notification_type) for n in notes()) == sorted([(U4.id, "approval_assigned"), (U1.id, "section_confirm")])`.
3. committed: the `section_confirm` row of `notes()` has `preview == "Add at least one expense line before approvals can proceed"` (A4a: E has category, date, description and no lines).

### EOS-AA-04 — no invoice step: a waived order with an account and a line still has no draft
- **Rules:** `add_approver` A5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1", but waived.
2. line(E, 1, "100.00").

**When**
- `result = svc.add_approver(db, eo_id=E.id, user_id=U4.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. returns: `result.user_id == U4.id`.
2. committed: re-read E: `invoice_id is None`.
3. committed: `account_invoices` rows of W1: exactly 0.
4. committed: `"invoice_autocreate_skipped" not in types(E)`, `"invoice_created" not in types(E)`.

### EOS-AA-05 — a duplicate approver: 409 passes unchanged, the extra row is gone
- **Rules:** `add_approver` A3; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. P3 = appr(E, U3).
3. X (after the commit point).

**When**
- `svc.add_approver(db, eo_id=E.id, user_id=U3.id, workspace_id=W1.id, assigned_by=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "User is already an approver for this order"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. session: session clean.
7. unchanged: unchanged(P3).
8. nothing written: nothing written.
9. committed: x_gone.

### EOS-AA-06 — an inactive member: 400 passes unchanged, nothing written
- **Rules:** `add_approver` A3; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. X (after the commit point).

**When**
- `svc.add_approver(db, eo_id=E.id, user_id=U5.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "User is not an active member of this workspace"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. nothing written: nothing written.
6. committed: x_gone.

### EOS-AA-07 — a failing commit leaves no approver and no notification
- **Rules:** `add_approver` A3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").

**When**
- `svc.add_approver(db, eo_id=E.id, user_id=U4.id, workspace_id=W1.id, assigned_by=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `expense_order_approvers` rows with `expense_order_id == E.id`: exactly 0.
4. nothing written: nothing written.

### EOS-AA-08 — a failing approver notification undoes the add
- **Rules:** `add_approver` A3, A4; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. X (after the commit point).

**When**
- `svc.add_approver(db, eo_id=E.id, user_id=U4.id, workspace_id=W1.id, assigned_by=U2.id)`, inside **failing approver notify**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
3. mock called: `rb.call_count >= 1`.
4. count: `expense_order_approvers` rows with `expense_order_id == E.id`: exactly 0.
5. nothing written: nothing written.
6. committed: x_gone.

## `ExpenseOrderService.remove_approver`

### EOS-RA-01 — the approver is removed and committed; returns None; no notification
- **Rules:** `remove_approver` A6, A8; Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. E = eo "1".
2. P3 = appr(E, U3).
3. P4 = appr(E, U4).

**When**
- `result = svc.remove_approver(db, eo_id=E.id, user_id=U4.id, workspace_id=W1.id, performed_by=U2.id)`.

**Then**
1. returns: `result is None`.
2. committed: gone(P4).
3. committed: unchanged(P3).
4. committed: `notes() == []`.

### EOS-RA-02 — removing the last pending approver makes approvals met and drafts the invoice
- **Rules:** `remove_approver` A7 [BUG-3066]
- **Kind:** bug
- **Expect:** xfail BUG-3066
- **Fails today on:** Then 3 (no invoice step: `invoice_id` stays None)

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3), but approved.
4. P4 = appr(E, U4).

**When**
- `result = svc.remove_approver(db, eo_id=E.id, user_id=U4.id, workspace_id=W1.id, performed_by=U2.id)`.

**Then**
1. returns: `result is None`.
2. committed: gone(P4).
3. committed: re-read E: `invoice_id is not None`.
4. committed: the `account_invoices` row with `id == E.invoice_id` has `invoice_status == "draft"`, `invoice_amount == Decimal("100.00")`.
5. committed: `recips() == [U1.id, U3.id]`.
6. committed: every row of `notes()` has `preview == DRAFTP`.

### EOS-RA-03 — after removing the pending approver the summary reads met (today and after the fix)
- **Rules:** `remove_approver` A6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. appr(E, U3), but approved.
4. appr(E, U4).

**When**
- `result = svc.remove_approver(db, eo_id=E.id, user_id=U4.id, workspace_id=W1.id, performed_by=U2.id)`.

**Then**
1. returns: `result is None`.
2. committed: `svc.approval_summary_for(db, eo_id=E.id, workspace_id=W1.id) == (1, 1, True)`.

### EOS-RA-04 — not an approver: 404 passes unchanged, the extra row is gone
- **Rules:** `remove_approver` A6; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. P3 = appr(E, U3).
3. X (after the commit point).

**When**
- `svc.remove_approver(db, eo_id=E.id, user_id=U4.id, workspace_id=W1.id, performed_by=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Approver not found"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. session: session clean.
7. unchanged: unchanged(P3).
8. committed: x_gone.

### EOS-RA-05 — a failing commit keeps the approver
- **Rules:** `remove_approver` A6; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. P4 = appr(E, U4).

**When**
- `svc.remove_approver(db, eo_id=E.id, user_id=U4.id, workspace_id=W1.id, performed_by=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(P4).

## `ExpenseOrderService.approve_as_me`

### EOS-AP-01 — the approval is recorded and committed; one of two is not met, no draft
- **Rules:** `approve_as_me` A9a, A9b; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. P3 = appr(E, U3).
4. appr(E, U4).

**When**
- `result = svc.approve_as_me(db, eo_id=E.id, user_id=U3.id, workspace_id=W1.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == P3.id`.
3. committed: re-read P3: `approved is True`, `approved_at == NOW`.
4. committed: re-read E: `invoice_id is None`.
5. committed: `account_invoices` rows of W1: exactly 0.

### EOS-AP-02 — the approval that makes approvals met drafts the invoice and sends the notice
- **Rules:** `approve_as_me` A9b; `_sync_or_create_invoice` Y7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. P3 = appr(E, U3).

**When**
- `result = svc.approve_as_me(db, eo_id=E.id, user_id=U3.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == P3.id`.
2. committed: re-read E: `invoice_id is not None`.
3. committed: the `account_invoices` row with `id == E.invoice_id` has `invoice_status == "draft"`, `invoice_amount == Decimal("100.00")`, `created_by == U3.id` (D2a: the approver).
4. committed: `recips() == [U1.id, U3.id]`.
5. committed: every row of `notes()` has `preview == DRAFTP`.

### EOS-AP-03 — approving a completed order leaves its confirmed invoice alone
- **Rules:** `approve_as_me` A9b; `_sync_or_create_invoice` Y3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E = eo "1", but completed.
2. line(E, 1, "100.00").
3. P3 = appr(E, U3).
4. V = inv(E), but confirmed, linked.
5. invl(V, 1, "100.00").

**When**
- `result = svc.approve_as_me(db, eo_id=E.id, user_id=U3.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == P3.id`.
2. committed: re-read P3: `approved is True`.
3. committed: unchanged(V).
4. committed: `account_invoices` rows with `order_id == E.id`: exactly 1.
5. committed: `notes() == []`.

### EOS-AP-04 — not an approver: 403 passes unchanged, the extra row is gone
- **Rules:** `approve_as_me` A9a; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. P3 = appr(E, U3).
4. X (after the commit point).

**When**
- `svc.approve_as_me(db, eo_id=E.id, user_id=U4.id, workspace_id=W1.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "You are not an assigned approver for this order"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. session: session clean.
7. unchanged: unchanged(P3).
8. nothing written: nothing written.
9. committed: x_gone.

### EOS-AP-05 — a failing commit leaves the approval unrecorded and no draft
- **Rules:** `approve_as_me` A9a; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. P3 = appr(E, U3).

**When**
- `svc.approve_as_me(db, eo_id=E.id, user_id=U3.id, workspace_id=W1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(P3).
4. nothing written: nothing written.

## `ExpenseOrderService.unapprove_as_me`

### EOS-UA-01 — the approval is withdrawn and committed; the draft stays; nobody told
- **Rules:** `unapprove_as_me` A9 (Q4); TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. P3 = appr(E, U3), but approved.
4. V = inv(E), linked.
5. invl(V, 1, "100.00").

**When**
- `result = svc.unapprove_as_me(db, eo_id=E.id, user_id=U3.id, workspace_id=W1.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == P3.id`.
3. committed: re-read P3: `approved is False`, `approved_at is None`.
4. committed: re-read E: `invoice_id == V.id`.
5. committed: unchanged(V).
6. committed: `notes() == []`.

### EOS-UA-02 — a completed order: 400 passes unchanged, the extra row is gone
- **Rules:** `unapprove_as_me` A9; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1", but completed.
2. line(E, 1, "100.00").
3. P3 = appr(E, U3), but approved.
4. V = inv(E), but confirmed, linked.
5. X (after the commit point).

**When**
- `svc.unapprove_as_me(db, eo_id=E.id, user_id=U3.id, workspace_id=W1.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot withdraw approval — order is complete"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. session: session clean.
7. unchanged: unchanged(P3).
8. nothing written: nothing written.
9. committed: x_gone.

### EOS-UA-03 — a failing commit keeps the approval
- **Rules:** `unapprove_as_me` A9; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. E = eo "1".
2. line(E, 1, "100.00").
3. P3 = appr(E, U3), but approved.

**When**
- `svc.unapprove_as_me(db, eo_id=E.id, user_id=U3.id, workspace_id=W1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(P3).

## `ExpenseOrderService.list_events`

### EOS-N-01 — returns the order's events newest first; neither commits nor rolls back
- **Rules:** `list_events` N1; TC6
- **Kind:** happy
- **Expect:** pass

**Given**
1. E = eo "1".
2. EA = ev(E, T1).
3. EB = ev(E, T0).
4. EC = ev(E, T2).
5. F = eo "2".
6. ev(F, T2).
7. X (after the commit point).

**When**
- spies: `result = svc.list_events(db, eo_id=E.id, workspace_id=W1.id)`.

**Then**
1. returns: `[e.id for e, p in result] == [EC.id, EA.id, EB.id]`.
2. returns: `[p.id for e, p in result] == [U1.id, U1.id, U1.id]`.
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 0`.
5. session: `X in db`.

### EOS-N-02 — another workspace's order: 404, no rollback
- **Rules:** `list_events` N1; TC6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = eo "9", but of W2.
2. ev(Z, T0).
3. X (after the commit point).

**When**
- spies: `svc.list_events(db, eo_id=Z.id, workspace_id=W1.id)`, wrapped in `raises: HTTPException`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Expense order with ID {Z.id} not found"`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.

## `ExpenseOrderService.create_expense_order_from_template`

### EOS-T-01 — a waiving template with an account and a line: order and draft committed, draft notice
- **Rules:** `create_expense_order_from_template` T1, T2; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. TPL = tpl, but waiving.
2. tplline(TPL, 1, "5000.00").

**When**
- `result = svc.create_expense_order_from_template(db, template_id=TPL.id, overrides=ExpenseOrderFromTemplateCreate(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `isinstance(result, ExpenseOrder)`, `result.invoice_id is not None`.
3. committed: the `expense_orders` row with `id == result.id` has `required_approvals == 0`, `account_id == A1.id`, `created_by == U2.id`.
4. committed: the `account_invoices` row with `id == result.invoice_id` has `invoice_status == "draft"`, `invoice_amount == Decimal("5000.00")`, `order_id == result.id`, `created_by == U2.id` (D2a).
5. committed: `recips() == [U2.id]`.
6. committed: `notes()[0].preview == DRAFTP`.

### EOS-T-02 — a waiving template without an account: the skip event, no invoice
- **Rules:** `create_expense_order_from_template` T2; `_sync_or_create_invoice` Y5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. TPL = tpl, but waiving, `account_id None`.
2. tplline(TPL, 1, "5000.00").

**When**
- `result = svc.create_expense_order_from_template(db, template_id=TPL.id, overrides=ExpenseOrderFromTemplateCreate(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.invoice_id is None`.
2. committed: `types(result)[-1] == "invoice_autocreate_skipped"`.
3. committed: `account_invoices` rows of W1: exactly 0.
4. committed: `notes() == []`.

### EOS-T-03 — a template that needs approval, with a default approver: no invoice, no notification
- **Rules:** `create_expense_order_from_template` T1, T2, T3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. TPL = tpl, but `default_approver_id U3.id`.
2. tplline(TPL, 1, "5000.00").

**When**
- `result = svc.create_expense_order_from_template(db, template_id=TPL.id, overrides=ExpenseOrderFromTemplateCreate(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.invoice_id is None`.
2. committed: the approver rows of `result` have `{a.user_id for a in rows} == {U2.id, U3.id}`.
3. committed: `account_invoices` rows of W1: exactly 0.
4. committed: `notes() == []`.
5. committed: `"invoice_autocreate_skipped" not in types(result)`.

### EOS-T-04 — an inactive template: the manager's 400, the extra row is gone
- **Rules:** `create_expense_order_from_template` T1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. TPL = tpl, but waiving, `is_active False`.
2. tplline(TPL, 1, "5000.00").
3. X (after the commit point).

**When**
- `svc.create_expense_order_from_template(db, template_id=TPL.id, overrides=ExpenseOrderFromTemplateCreate(), workspace_id=W1.id, user_id=U2.id)`, inside **spies** (the spies sit inside the `pytest.raises`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Template is inactive"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. mock called: `rb.call_count >= 1` (the service rolled back itself; TC3).
6. session: session clean.
7. nothing written: nothing written.
8. committed: x_gone.

### EOS-T-05 — the draft step refusing the account undoes the whole new order
- **Rules:** `create_expense_order_from_template` T2; `_create_draft_invoice` D4; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. A3 = acct "No Bills", but `allow_invoices False`.
2. TPL = tpl, but waiving, `account_id A3.id`.
3. tplline(TPL, 1, "5000.00").
4. X (after the commit point).

**When**
- `svc.create_expense_order_from_template(db, template_id=TPL.id, overrides=ExpenseOrderFromTemplateCreate(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "Invoices are not allowed for this account"`.
4. session: `X not in db` (right after the call, before any re-read or test rollback; TC3).
5. session: session clean.
6. count: W1 has exactly 0 `expense_orders` rows.
7. nothing written: nothing written.
8. committed: x_gone.

### EOS-T-06 — a failing commit leaves no order and no invoice
- **Rules:** `create_expense_order_from_template` T1; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. TPL = tpl, but waiving.
2. tplline(TPL, 1, "5000.00").

**When**
- `svc.create_expense_order_from_template(db, template_id=TPL.id, overrides=ExpenseOrderFromTemplateCreate(), workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: W1 has exactly 0 `expense_orders` rows.
4. nothing written: nothing written.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| E1, U1, X1, L1, L4, L6, L8, A1–A3, A6, A9a, A9, N1, T1 details (manager rules and errors, BUG-740, 743, 744, 746–759) | `expense_order_manager.cases.md` | every manager rule; here only one pass-through per path |
| C8, D2, D4, R4, V5 invoice-manager details (`confirm_invoice`, `create_invoice`, `update_invoice` R10, `delete_invoice`, `sync_items_from_list`) | `account_invoice_manager.cases.md` | amounts, events, account refusals |
| U2, A4, C8, Y7 notification texts and recipient rules | `approval_notification_service.cases.md` | previews, gap text, recipient sets |
| H-2 … H-4 figures and bucket contents (BUG-2714 … 2719, 746 … 748) | expense order manager / DAO cases | what each figure counts |
| BUG-3062 concurrency (two sessions racing complete / void / create invoice) | integration tests | the loser sees the new state and gets the normal error; unit cards only check the `FOR UPDATE` read |
| V10 blank note → 422 at the endpoint (BUG-3064) | `POST /expense-orders/{id}/void/` | 422 body; nothing written |
| X2 the endpoint passes the current user (BUG-1193) | `DELETE /expense-orders/{id}/` | audit row names the caller |
| L-1 endpoint limit range `1 ≤ limit ≤ 100`, `skip ≥ 0` | `GET /expense-orders/` | 422 outside the range |
| Permission checks (any member can complete, void, delete, approve) | `docs/future/permissions.md` | not a rule today |

## Spec gaps
None open. All ten gaps of Revision 1 are closed by the spec's Gap log (2026-11-22):
| # | Closed by | Card change |
|---|---|---|
| 1 | G1 — rules C1a, V1a, I1a: plain `FOR UPDATE` on a one-table read, `OF expense_orders` also correct, no `NOWAIT` / `SKIP LOCKED` | C-21, V-24, I-15 add lock clause(`expense_orders`) |
| 2 | G2 — patch targets in spec Notes | C-19 target confirmed; new U-13, AA-08 |
| 3 | G3 — rule A4a | AA-03 checks the preview |
| 4 | G4 — rules H-3a, H-4a | new H-07; H-04 adds `account_name` |
| 5 | G5 — rule D2a | D-01, AP-02, T-01 check `created_by` |
| 6 | G6 — rule L6a | RI-03 checks the detail; new RI-05 |
| 7 | G7 — rule R4a | R-10 checks the detail; D-06, R-10 keep `is_deleted True` only |
| 8 | G8 — rule D2a | D-12 reads `invoice_data` by keyword; new D-14 |
| 9 | G9 — rule R2a | R-04 stays a pass card |
| 10 | G10 — check order C1, C3, C2, C4–C7 and I1, I3, I2, I4 | I-08 → xfail BUG-3065 (400); new C-22 (xfail), C-23 (pass) |

Revision 3 (executor discrepancies, closed by the spec's Gap log 2026-11-22):
| Item | Closed by | Card change |
|---|---|---|
| DISCREPANCY-1 (U-07, R-08, R-09) | G12 — rule `_resync_draft_invoice` R4b [BUG-629] | U-07, R-08, R-09 → strict xfail BUG-629; new U-14 (pass) |
| EOS-V-03 metadata | G11 — `void_expense_order` V7 [BUG-3070] | V-03 → strict xfail BUG-3070, fails on Then 4 (Revision 3a) |
| `X in db.new` on flushed rows | executor note | 14 read cards check `X in db` |

Revision 4 (verifier findings, 2026-11-22) opens no gap. Finding 3 needed no fill-gaps: P-1 and H-1 normalise filters per `_hub_filter_kwargs`, whose signature gives `exclude_complete=False`, `exclude_voided=False`, so the defaults are stated. If the describer reads P-1 / H-1 differently, P-09 and H-08 are the cards to revisit.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_expense_order` | E1 | E-01, E-02, E-03, E-04 |
| | E2, E3 | E-01 |
| `update_expense_order` | U1 | U-01, U-08, U-09, U-10 |
| | U2 | U-01, U-02, U-03, U-04, U-13 |
| | U3 | U-05, U-06 |
| | U4 | U-07, U-14 |
| `get_expense_order` | G1 | G-01 … G-06 |
| `list_expense_orders` | L-1 | L-01, L-02, L-03, L-04, L-06 |
| | L-2 | L-05 |
| `_hub_filter_kwargs` | Returns, K1 | K-01, K-02 |
| | K2 | K-01 … K-07 |
| `list_expense_orders_page` | P-1 | P-01, P-02, P-07, P-09 |
| | P-2 | P-01, P-03, P-04, P-05 |
| | P-3 | P-02 … P-06 |
| | P-4 | P-08 |
| `get_expense_order_hub_stats` | H-1 | H-01, H-02, H-08 |
| | H-2 | H-01, H-05, H-08 |
| | H-3 | H-02, H-03, H-05, H-07 |
| | H-3a, Returns | H-07 |
| | H-4 | H-04, H-05 |
| | H-4a | H-04 |
| | H-5 | H-06 |
| `delete_expense_order` | X1 (404, 400 completed, commit, rollback) | X-01, X-03, X-04, X-05, X-07 |
| | X1 [BUG-742] | X-06 |
| | X2 [BUG-1193] | X-02 |
| | X3 | X-01 |
| `complete_expense_order` | C1 / Errors row 1 | C-17, C-18 |
| | C1, C1a [BUG-3062] | C-21 |
| | C2 | C-04, C-23 |
| | C3 / Errors row 2 [BUG-3065] | C-05, C-06, C-07, C-22 |
| | check order C3 before C2 [BUG-3065] | C-22, C-23 |
| | C4 / Errors row 3 | C-08, C-10 |
| | C4 [BUG-755] | C-09 |
| | C5 / Errors row 4 | C-11 |
| | C6 / Errors row 5 | C-12, C-13 |
| | C7 / Errors row 6 | C-14 |
| | C8 | C-01, C-02, C-03, C-10, C-19 |
| | C8 / Errors row 7 [BUG-628] | C-15 |
| | C9 | C-16 |
| | C10 | C-01, C-16, C-20 |
| `void_expense_order` | V1 / Errors row 1 | V-21, V-22 |
| | V1, V1a [BUG-3062] | V-24 |
| | V2 / Errors row 2 | V-06 |
| | V3 / Errors row 3 | V-07 |
| | V4 | V-02, V-11, V-12 |
| | V5 | V-02, V-09 |
| | V5 / Errors row 4 [BUG-639] | V-08 |
| | V6 | V-10, V-11, V-12 |
| | V6a / Errors row 5 [BUG-3069] | V-13, V-14 |
| | V7 | V-03, V-04, V-05, V-10 |
| | V8 [BUG-3067] | V-15, V-16 |
| | V9 | V-01, V-03, V-10, V-16, V-23 |
| | V10 / Errors row 6 [BUG-3064] | V-17, V-18, V-19, V-20 |
| | V11, V12 | V-01 |
| `add_item` | L1 | AI-01, AI-05, AI-07 |
| | L2 | AI-01, AI-02, AI-03, AI-06 |
| | L3 | AI-04 |
| `update_item` | L4 | UI-01, UI-05, UI-06 |
| | L5 | UI-01, UI-02, UI-03, UI-04 |
| `remove_item` | L6 | RI-01, RI-02, RI-03 |
| | L6a | RI-03, RI-05 |
| | L7 | RI-01, RI-04 |
| `get_items` | L8 | GI-01, GI-02 |
| `_invoice_item_dicts` | S1 | S-01, S-02 |
| | S2 | S-03, S-04, S-05 |
| | S3 | S-01 |
| | S4 | S-01, S-06, S-07, S-08 |
| | S5 | S-01, S-06, S-09, S-10 |
| | S6 | S-11 |
| `_create_draft_invoice` | D1 | D-05, I-10 |
| | D2 | D-01, D-02 |
| | D2 [BUG-627] | D-12 |
| | D2a | D-01, D-14, AP-02, T-01 |
| | D3 [BUG-3063] | D-11 |
| | D4 | D-06, D-07, D-08, AI-06, T-05 |
| | R4a (D4 side) | D-06 |
| | D5 | D-09, D-10 |
| | D6 | D-01, D-02, D-04 |
| | D7, D8 | D-03 |
| | flush only | D-13 |
| `_resync_draft_invoice` | R1 | R-01, R-02 |
| | R2, R2a | R-03, R-04, R-12 |
| | R3 | R-05, R-06, R-12 |
| | R4 | R-07, R-10, R-11, U-14 |
| | R4a | R-10, U-14 |
| | R4b | R-08, R-09, U-07 |
| | R5 | R-02, R-03, R-05, R-06, R-12 |
| | R5a [BUG-3068] | U-11, U-12 |
| | flush only | R-13 |
| `_sync_or_create_invoice` | Y1 | Y-01 |
| | Y2 | Y-02, U-05, AI-02 |
| | Y3 | Y-03, Y-04, Y-05, AP-03 |
| | Y4 | Y-06 |
| | Y5 | Y-07, Y-08, T-02 |
| | Y6 | Y-09 |
| | Y7 | Y-10, U-06, AI-03, AP-02 |
| | flush only | Y-11 |
| `create_invoice_for_expense_order` | I1 | I-12, I-13 |
| | I1, I1a [BUG-3062] | I-15 |
| | I2 | I-02, I-03 |
| | I3 [BUG-3065] | I-05, I-06, I-07, I-08 |
| | check order I3 before I2 [BUG-3065] | I-08 |
| | I4 | I-09 |
| | I5 | I-01, I-10, I-11, I-14 |
| | I6 | I-04 |
| `list_approvers` | A1 | LA-01, LA-02 |
| `approval_summary_for` | A2 | AS-01, AS-02, AS-03, AS-05 |
| | A2 [BUG-755] | AS-04 |
| `add_approver` | A3 | AA-01, AA-05, AA-06, AA-07 |
| | A4 | AA-02, AA-03, AA-08 |
| | A4a | AA-03 |
| | A5 | AA-04 |
| `remove_approver` | A6 | RA-01, RA-03, RA-04, RA-05 |
| | A7 [BUG-3066] | RA-02 |
| | A8 | RA-01 |
| `approve_as_me` | A9a | AP-01, AP-04, AP-05 |
| | A9b | AP-01, AP-02, AP-03 |
| `unapprove_as_me` | A9 | UA-01, UA-02, UA-03 |
| `list_events` | N1 | N-01, N-02 |
| `create_expense_order_from_template` | T1 | T-01, T-03, T-04, T-06 |
| | T2 | T-01, T-02, T-03, T-05 |
| | T3 | T-03 |
| Transaction contract | TC1 | E-01, U-01, X-01, C-01, V-01, AI-01, UI-01, RI-01, I-01, AA-01, RA-01, AP-01, UA-01, T-01 |
| | TC2 | E-01, U-01, C-01, V-01, AI-01, UI-01, I-01, AA-01, AP-01, UA-01, T-01 |
| | TC3 | E-02, U-07, U-08, U-13, U-14, X-03, X-04, C-08, C-11, C-17, C-19, V-06, V-09, V-21, AI-05, AI-06, UI-05, RI-03, RI-05, I-02, I-08, I-09, I-10, I-12, AA-05, AA-06, AA-08, RA-04, AP-04, UA-02, T-04, T-05 |
| | TC4 | E-03, U-10, X-07, C-20, V-23, AI-07, UI-06, RI-04, I-14, AA-07, RA-05, AP-05, UA-03, T-06 |
| | TC5 | E-04 |
| | TC6 | G-01, G-06, L-06, P-08, H-06, GI-01, GI-02, LA-01, LA-02, AS-01, AS-05, N-01, N-02 |
