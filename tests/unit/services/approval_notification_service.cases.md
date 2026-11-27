# Test cases — `app/services/approval_notification_service.py`

> **Spec:** `tests/unit/services/approval_notification_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 4 (2026-11-10) — `approval_notification_service.verify.md` F1 (survivors #149, #178, #191, #179, #192, #197, #193, #198, #200): new IA-19, IA-20, IA-21 — transfer, expense and work order with `required_approvals 2` and an approved W1 approver, who is notified (R3); an approved suspended approver and an approved approver row stored under W2 are not. F2 (survivor #199) after spec `detect_section_unconfirmed` R2a: new DS-09 (an order lacking `invoice_confirmed` counts it as off → false). No card changed or retired.
> **Revision:** 3 (2026-11-10) — executor notes (`approval_notification_service.notes.md` DISCREPANCY-1 … 4). AN-05 retired: `profiles.name` is NOT NULL, so no stored profile has a NULL name (the empty-name arm stays in AN-04). RD-12, RD-15, GP-12 insert the order with every NOT NULL column set and blank the field in memory before the call (as RD-05 does). Parallel runs: `so` / `to` store their number with the per-process suffix **GN** (Conventions); no Then line reads a stored number.
> **Revision:** 2 (2026-11-10) — spec round 2: the sales "ready" rule is no longer *proposed* (owner did not object; still decided under the reviewer's delegation) — section relabelled "Sales readiness (delegation, final)", the `Pending:` header lines dropped from SR-01 … SR-05 (cards unchanged). Gap log G1: SU-21 now asserts the detail `"Sales order with ID <id> not found"`; new SU-22 (a W2 sales order is 404 with the same text, xfail BUG-1205). G2: GP-08 stays a pass card, tagged "retire when BUG-758 is fixed". Spec gaps closed. No card retired.
> **Counts:** 192 cases · 176 expected-to-pass · 16 expected-to-fail (bugs) · 5 deferred

## Reviewer summary
- **Per callable:** `format_order_ref` 7 (1 bug) · `_active_member_ids` 3 · `_notify_user` 12 · `_actor_name` 5 · `_approval_summary` 22 (7 bug) · `build_approval_preview` 7 (1 bug) · `_is_approval_ready` 22 · `_section_gap_preview` 15 · `_pending_approver_ids` 9 (1 bug) · `_has_approvers` 6 (1 bug) · `notify_approval_assigned` 9 · `notify_approval_pending_for_order` 11 · `notify_section_confirm_needed` 11 · `notify_invoice_action` 21 (1 bug) · `handle_add_approver` 5 · `handle_order_update_notifications` 13 · `detect_section_unconfirmed` 9 · sales readiness (delegation) 5 (4 bug).
- **Depth:** full on who is notified and when (as asked); lighter on the pure formatters (one card per branch). Every recipient rule has refused-recipient cards: suspended / invited / inactive members, members active only in W0 or only in W2 (built before and after W1, profile ids below and above the W1 people), approver rows stored under W0 / W2 on the W1 order id, and the actor: excluded where the spec says so (`handle_add_approver` R2), notified where it says not (`notify_approval_assigned` R5, pending R3, section R4, invoice R5, update R3). Every writer has a commit-spy card.
- **Expected-to-fail:** BUG-1205 11 (FR-07, SU-19, SU-20, SU-21, SU-22, PA-09, IA-17, SR-01, SR-03, SR-04, SR-05), BUG-1202 3 (SU-07, BP-04, HA-05), BUG-1203 1 (SU-08), BUG-755 1 (SU-09). All strict. Regression part of BUG-1205 that holds today: IA-16 (a sales order's creator still gets the invoice notice).
- **Isolated:** the sales "ready" rule and gap text (decided under the reviewer's delegation; owner did not object, 2026-11-10) stay only in section "Sales readiness (delegation, final)" (SR-01 … SR-05). No other card reads sales readiness, so a later change touches only those five. No rule here is pending an owner question.
- **Notable design choices:**
  - The whole test runs with `session_replication_role = replica` (spec Notes); orders name no real status, factory, location or item. NU-10 switches back to `origin` so the unknown-actor foreign key fires.
  - Cards that would change when BUG-1202 / 1203 / 755 are fixed are avoided: every "has approvers" / readiness-change card gives approver rows or an explicit `required_approvals`; the no-approver case of a work order (unaffected) carries the pass side.
  - PO and WO gap texts, sales readiness and `detect_section_unconfirmed` use `SimpleNamespace` orders (spec Facts); readiness of every type uses real rows.
  - Recipients are compared as sorted lists, never row order (spec: no defined order).
  - GP-08 is a pass card on today's fallback text for a quantity-0 expense line; it is tagged "retire when BUG-758 is fixed" (spec G2): after that fix the manager's own reason arrives instead.
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `APN` = `app/services/approval_notification_service.py`. `FR` format_order_ref · `AM` _active_member_ids · `NU` _notify_user · `AN` _actor_name · `SU` _approval_summary · `BP` build_approval_preview · `RD` _is_approval_ready · `GP` _section_gap_preview · `PA` _pending_approver_ids · `HA` _has_approvers · `AS` notify_approval_assigned · `PE` notify_approval_pending_for_order · `SC` notify_section_confirm_needed · `IA` notify_invoice_action · `AD` handle_add_approver · `OU` handle_order_update_notifications · `DS` detect_section_unconfirmed · `SR` = the sales-readiness cards (own section, see below).

**Imports.** `from app.services import approval_notification_service as ans`; every function is called as `ans.<name>(db, …)` (`db` first and positional, the rest by keyword; `format_order_ref` and `detect_section_unconfirmed` take no `db`, arguments positional). Models from `app.models.<module>`: `notification.Notification`, `workspace_member.WorkspaceMember`, `purchase_order.PurchaseOrder`, `transfer_order.TransferOrder`, `transfer_order_item.TransferOrderItem`, `expense_order.ExpenseOrder`, `expense_order_item.ExpenseOrderItem`, `work_order.WorkOrder`, `sales_order.SalesOrder`, and `<x>_order_approver.<X>OrderApprover` for x = purchase, transfer, expense, work, sales. `HTTPException` (`fastapi`); `IntegrityError` (`sqlalchemy.exc`); `text` (`sqlalchemy`); `patch` (`unittest.mock`); `SimpleNamespace`; `Decimal`; `date`, `datetime`; `os`.

**Fixed values.** MISSING = `999999999`. T(k) = `datetime(2026, 3, 4, k, 0, 0)`. `result` = what the When returns. Expected previews with an id are f-strings (`f"PO-{P.id}"`).

**Externals.** None mocked (spec: none). `pg_notify` runs in the database.

**Standing rows** (every test, no Given line), in this order:
1. `db.execute(text("SET LOCAL session_replication_role = replica"))` — kept for the whole test (spec Notes: orders name no real status, factory, location or item). Only APN-NU-10 switches back to `origin`.
2. W0, W1, W2 = `make_workspace(db)`, in that order (`W0.id < W1.id < W2.id`).
3. Profiles `make_profile(db, name=…)`, in this order (ids rise): UZ0 `"Zia"`, UA `"Ann"`, UB `"Bob"`, UC `"Cara"`, UD `"Dina"`, US `"Sue"`, UI `"Ivy"`, UV `"Val"`, UN `"Nora"`, UZ2 `"Zed"`.
4. Memberships `WorkspaceMember(workspace_id=…, user_id=…, role="member", status=…)`: UA, UB, UC, UD `"active"` in W1; US `"suspended"` in W1; UI `"invited"` in W1; UV `"inactive"` in W1; UZ0 `"active"` in W0 only; UZ2 `"active"` in W2 only. UN has none.
No order, approver or notification exists unless a Given line builds it.

**Given rows.** Built directly, flushed one at a time in the order written. After "but" a line lists every column that differs. Every order column is given at insert.
- **po(n)** = `PurchaseOrder(workspace_id=W1.id, po_number=n, destination_type="storage", destination_id=MISSING, subtotal=Decimal("0.00"), total_amount=Decimal("0.00"), current_status_id=MISSING, created_by=UC.id, supplier_confirmed=False, details_confirmed=False, items_confirmed=False, invoice_confirmed=False, required_approvals=None)`. **ready po(n)** = po(n) but `supplier_confirmed True`, `details_confirmed True`, `items_confirmed True`.
- **to(n)** = `TransferOrder(workspace_id=W1.id, transfer_number=GN(n), source_location_type="storage", source_location_id=MISSING, destination_location_type="storage", destination_location_id=999999998, current_status_id=MISSING, created_by=UC.id, required_approvals=None)`. **to line(T)** = `TransferOrderItem(workspace_id=W1.id, transfer_order_id=T.id, line_number=1, item_id=MISSING, quantity=Decimal("1"))`.
- **eo(n)** = `ExpenseOrder(workspace_id=W1.id, expense_number=n, expense_category="other", expense_date=date(2026, 3, 1), subtotal=Decimal("0.00"), total_amount=Decimal("0.00"), created_by=UC.id, description="Order One", required_approvals=None)`. **eo line(E)** = `ExpenseOrderItem(workspace_id=W1.id, expense_order_id=E.id, line_number=1, description="Paper", quantity=Decimal("1"), unit_price=Decimal("1"), line_subtotal=Decimal("1"))`.
- **wo(n)** = `WorkOrder(workspace_id=W1.id, work_order_number=n, title="Order One", factory_id=MISSING, work_order_type_id=MISSING, created_by=UC.id, required_approvals=None)`.
- **so(n)** = `SalesOrder(workspace_id=W1.id, sales_order_number=GN(n), account_id=MISSING, factory_id=MISSING, order_date=date(2026, 3, 1), total_amount=Decimal("0.00"), current_status_id=MISSING, created_by=UC.id)` (`required_approvals` not passed).
- "W2 x" / "W0 x" = builder x with `workspace_id W2.id` / `W0.id`.
- **poa(O, U, k)** = `PurchaseOrderApprover(workspace_id=W1.id, purchase_order_id=O.id, user_id=U.id, assigned_at=T(k))`; **toa**, **eoa**, **woa**, **soa** the same with `TransferOrderApprover` / `transfer_order_id`, `ExpenseOrderApprover` / `expense_order_id`, `WorkOrderApprover` / `work_order_id`, `SalesOrderApprover` / `sales_order_id`. "approved" after "but" = `approved True`, `approved_at T(12)`.
- **commit point** = `db.commit()` after the last Given line (a savepoint release under the `db` fixture).

**Named checks.**
- **notes()** = `db.expire_all()`, then `db.query(Notification).order_by(Notification.id).all()` (every workspace). **to(U)** = `[n for n in notes() if n.recipient_user_id == U.id]`. **recips()** = `sorted(n.recipient_user_id for n in notes())` (a list: a duplicate shows).
- `note <field list>` on a line = checks on `to(U)[0]` for the U the line names.
- **nothing written** = `len(notes()) == 0`.
- `session:` lines check `db` directly, before anything expires it.
- `raises: <Type>` = `with pytest.raises(<Type>) as exc:` around the call; following `raises:` lines check `exc.value`. For `IntegrityError`: `with pytest.raises(IntegrityError) as exc:` then `with db.begin_nested():` then the call.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. `committed:` lines: before the first one the test runs `db.rollback()` once, then counts afresh.

**xfail cards.** `pytest.mark.xfail(strict=True, reason="BUG-NNN")`. Write the call and checks as shown.

**Isolated cards.** The sales readiness / gap-text rule (BUG-1205, decided under the reviewer's delegation, final since 2026-11-10) is tested only in section "Sales readiness (delegation, final)", IDs `APN-SR-nn`; no other card depends on it.

**Parallel runs.** `transfer_number` and `sales_order_number` are unique across all workspaces today (BUG-726 and siblings). **GN(n)** = `f"{n}-{os.getpid()}"`: the `to` and `so` builders store `GN(n)` for the card's number n, so two processes never insert the same number. PO, expense and work order numbers are unique per workspace and are stored as written.

**Race simulations.** None.

## `format_order_ref`

### APN-FR-01 — purchase order reference uses the id given
- **Rules:** `format_order_ref` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = ans.format_order_ref("purchase_order", 12)`.

**Then**
1. returns: `result == "PO-12"`.

### APN-FR-02 — transfer order reference
- **Rules:** `format_order_ref` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = ans.format_order_ref("transfer_order", 7)`.

**Then**
1. returns: `result == "TO-7"`.

### APN-FR-03 — expense order reference
- **Rules:** `format_order_ref` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = ans.format_order_ref("expense_order", 485393)`.

**Then**
1. returns: `result == "EXP-485393"`.

### APN-FR-04 — work order reference
- **Rules:** `format_order_ref` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = ans.format_order_ref("work_order", 3)`.

**Then**
1. returns: `result == "WO-3"`.

### APN-FR-05 — an unknown type becomes words and a number
- **Rules:** `format_order_ref` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = ans.format_order_ref("project_component", 3)`.

**Then**
1. returns: `result == "project component #3"`.

### APN-FR-06 — a one-word unknown type
- **Rules:** `format_order_ref` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = ans.format_order_ref("x", 1)`.

**Then**
1. returns: `result == "x #1"`.

### APN-FR-07 — a sales order is "SO-<id>"
- **Rules:** `format_order_ref` R2a [BUG-1205]
- **Kind:** bug
- **Expect:** xfail BUG-1205
- **Fails today on:** Then 1 (today `"sales order #5"`)

**Given**
1. Standing rows only.

**When**
- `result = ans.format_order_ref("sales_order", 5)`.

**Then**
1. returns: `result == "SO-5"`.

## `_active_member_ids`

### APN-AM-01 — only active members of that workspace
- **Rules:** `_active_member_ids` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Standing rows only (W1 active: UA, UB, UC, UD; W1 suspended US, invited UI, inactive UV; UZ0 active in W0; UZ2 active in W2).

**When**
- `result = ans._active_member_ids(db, W1.id)`.

**Then**
1. returns: `result == {UA.id, UB.id, UC.id, UD.id}`.
2. returns: `isinstance(result, set)`.

### APN-AM-02 — the other workspaces give their own members
- **Rules:** `_active_member_ids` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = ans._active_member_ids(db, W2.id)`.

**Then**
1. returns: `result == {UZ2.id}`.

### APN-AM-03 — an unknown workspace gives an empty set
- **Rules:** `_active_member_ids` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = ans._active_member_ids(db, MISSING)`.

**Then**
1. returns: `result == set()`.

## `_notify_user`

### APN-NU-01 — an active member gets one row with exactly the given values
- **Rules:** `_notify_user` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = ans._notify_user(db, workspace_id=W1.id, recipient_user_id=UB.id, actor_user_id=UA.id, notification_type="approval_pending", entity_type="purchase_order", entity_id=41, source_type="order", source_id=42, preview="Hello")`.

**Then**
1. returns: `result is None`.
2. session: `not db.new` (the row is flushed).
3. count: `len(notes()) == 1`.
4. count: `len(to(UB)) == 1`.
5. re-read note of UB: `workspace_id == W1.id`, `actor_user_id == UA.id`, `notification_type == "approval_pending"`, `entity_type == "purchase_order"`, `entity_id == 41`, `source_type == "order"`, `source_id == 42`, `preview == "Hello"`, `is_read is False`.

### APN-NU-02 — preview left out is stored NULL
- **Rules:** `_notify_user` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = ans._notify_user(db, workspace_id=W1.id, recipient_user_id=UB.id, actor_user_id=UA.id, notification_type="section_confirm", entity_type="work_order", entity_id=5, source_type="section", source_id=5)`.

**Then**
1. returns: `result is None`.
2. count: `len(to(UB)) == 1`.
3. re-read note of UB: `preview is None`, `notification_type == "section_confirm"`.

### APN-NU-03 — a suspended member gets nothing
- **Rules:** `_notify_user` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Standing rows only (US is `"suspended"` in W1).

**When**
- `result = ans._notify_user(db, workspace_id=W1.id, recipient_user_id=US.id, actor_user_id=UA.id, notification_type="approval_pending", entity_type="purchase_order", entity_id=41, source_type="order", source_id=41, preview="Hello")`.

**Then**
1. returns: `result is None`.
2. session: `not db.new`.
3. nothing written.

### APN-NU-04 — an invited member gets nothing
- **Rules:** `_notify_user` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Standing rows only (UI is `"invited"` in W1).

**When**
- `result = ans._notify_user(db, workspace_id=W1.id, recipient_user_id=UI.id, actor_user_id=UA.id, notification_type="approval_pending", entity_type="purchase_order", entity_id=41, source_type="order", source_id=41, preview="Hello")`.

**Then**
1. returns: `result is None`.
2. nothing written.

### APN-NU-05 — an inactive member gets nothing
- **Rules:** `_notify_user` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Standing rows only (UV is `"inactive"` in W1).

**When**
- `result = ans._notify_user(db, workspace_id=W1.id, recipient_user_id=UV.id, actor_user_id=UA.id, notification_type="approval_pending", entity_type="purchase_order", entity_id=41, source_type="order", source_id=41, preview="Hello")`.

**Then**
1. returns: `result is None`.
2. nothing written.

### APN-NU-06 — an active member of W0 only gets nothing in W1
- **Rules:** `_notify_user` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Standing rows only (UZ0 is active in W0 only; W0 is built before W1).

**When**
- `result = ans._notify_user(db, workspace_id=W1.id, recipient_user_id=UZ0.id, actor_user_id=UA.id, notification_type="approval_pending", entity_type="purchase_order", entity_id=41, source_type="order", source_id=41, preview="Hello")`.

**Then**
1. returns: `result is None`.
2. nothing written.

### APN-NU-07 — an active member of W2 only gets nothing in W1
- **Rules:** `_notify_user` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Standing rows only (UZ2 is active in W2 only; W2 is built after W1).

**When**
- `result = ans._notify_user(db, workspace_id=W1.id, recipient_user_id=UZ2.id, actor_user_id=UA.id, notification_type="approval_pending", entity_type="purchase_order", entity_id=41, source_type="order", source_id=41, preview="Hello")`.

**Then**
1. returns: `result is None`.
2. nothing written.

### APN-NU-08 — a W1 member gets nothing when the workspace given is W2
- **Rules:** `_notify_user` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Standing rows only (UB is active in W1 only).

**When**
- `result = ans._notify_user(db, workspace_id=W2.id, recipient_user_id=UB.id, actor_user_id=UA.id, notification_type="approval_pending", entity_type="purchase_order", entity_id=41, source_type="order", source_id=41, preview="Hello")`.

**Then**
1. returns: `result is None`.
2. nothing written.

### APN-NU-09 — no membership, or an unknown id, gets nothing
- **Rules:** `_notify_user` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Standing rows only (UN has no membership).

**When**
- `result = ans._notify_user(db, workspace_id=W1.id, recipient_user_id=UN.id, actor_user_id=UA.id, notification_type="approval_pending", entity_type="purchase_order", entity_id=41, source_type="order", source_id=41, preview="Hello")`.

**Then**
1. returns: `result is None`.
2. nothing written.

### APN-NU-10 — an unknown actor makes the write fail
- **Rules:** `_notify_user` Errors (NotificationDAO.create R4)
- **Kind:** error
- **Expect:** pass

**Given**
1. `db.execute(text("SET LOCAL session_replication_role = origin"))` (foreign keys checked again).

**When**
- `ans._notify_user(db, workspace_id=W1.id, recipient_user_id=UB.id, actor_user_id=MISSING, notification_type="approval_pending", entity_type="purchase_order", entity_id=41, source_type="order", source_id=41, preview="Hello")`, wrapped as `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError` on flush.
2. nothing written.

### APN-NU-11 — the recipient may be the actor
- **Rules:** `_notify_user` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = ans._notify_user(db, workspace_id=W1.id, recipient_user_id=UA.id, actor_user_id=UA.id, notification_type="invoice_action", entity_type="purchase_order", entity_id=41, source_type="invoice", source_id=9, preview="Hi")`.

**Then**
1. returns: `result is None`.
2. count: `len(to(UA)) == 1`.
3. re-read note of UA: `actor_user_id == UA.id`, `source_id == 9`.

### APN-NU-12 — writes but never commits or rolls back
- **Rules:** `_notify_user` R1 (no commit; spec Overview)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Standing rows, then the commit point.

**When**
- under **spies**: `ans._notify_user(db, workspace_id=W1.id, recipient_user_id=UB.id, actor_user_id=UA.id, notification_type="approval_pending", entity_type="purchase_order", entity_id=41, source_type="order", source_id=41, preview="Hello")`.

**Then**
1. mock called: `cm.call_count == 0`.
2. mock called: `rb.call_count == 0`.
3. committed: `len(notes()) == 0`.

## `_actor_name`

### APN-AN-01 — no user id gives "Someone"
- **Rules:** `_actor_name` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = ans._actor_name(db, None)`.

**Then**
1. returns: `result == "Someone"`.

### APN-AN-02 — a named profile gives its name
- **Rules:** `_actor_name` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = ans._actor_name(db, UA.id)`.

**Then**
1. returns: `result == "Ann"`.

### APN-AN-03 — the name is not trimmed, and any workspace's profile is named
- **Rules:** `_actor_name` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Profile PR = `make_profile(db, name=" Rahim ")`, with no membership anywhere.

**When**
- `result = ans._actor_name(db, PR.id)`.

**Then**
1. returns: `result == " Rahim "`.

### APN-AN-04 — an empty name gives "User <id>"
- **Rules:** `_actor_name` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Profile PE = `make_profile(db, name="")`.

**When**
- `result = ans._actor_name(db, PE.id)`.

**Then**
1. returns: `result == f"User {PE.id}"`.

### APN-AN-06 — an unknown id gives "User <id>"
- **Rules:** `_actor_name` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = ans._actor_name(db, MISSING)`.

**Then**
1. returns: `result == "User 999999999"`.

## `_approval_summary`

### APN-SU-01 — purchase order: three approvers, one approved, no requirement
- **Rules:** `_approval_summary` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order P = po("PO-1").
2. Approver = poa(P, UB, 9).
3. Approver = poa(P, UD, 10), but approved.
4. Approver = poa(P, US, 11).

**When**
- `result = ans._approval_summary(db, "purchase_order", P.id, W1.id)`.

**Then**
1. returns: `result == (1, 3, False)`.

### APN-SU-02 — transfer order: two approvers, one approved
- **Rules:** `_approval_summary` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order T = to("TO-1").
2. Approver = toa(T, UB, 9), but approved.
3. Approver = toa(T, UD, 10).

**When**
- `result = ans._approval_summary(db, "transfer_order", T.id, W1.id)`.

**Then**
1. returns: `result == (1, 2, False)`.

### APN-SU-03 — expense order: the requirement is met
- **Rules:** `_approval_summary` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order E = eo("EXP-1"), but `required_approvals 1`.
2. Approver = eoa(E, UB, 9), but approved.
3. Approver = eoa(E, UD, 10).

**When**
- `result = ans._approval_summary(db, "expense_order", E.id, W1.id)`.

**Then**
1. returns: `result == (1, 1, True)`.

### APN-SU-04 — work order: an explicit requirement wins over the row count
- **Rules:** `_approval_summary` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order O = wo("WO-1"), but `required_approvals 3`.
2. Approver = woa(O, UB, 9), but approved.

**When**
- `result = ans._approval_summary(db, "work_order", O.id, W1.id)`.

**Then**
1. returns: `result == (1, 3, False)`.

### APN-SU-05 — requirement 0 is met with approvers pending
- **Rules:** `_approval_summary` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order P = po("PO-1"), but `required_approvals 0`.
2. Approver = poa(P, UB, 9).

**When**
- `result = ans._approval_summary(db, "purchase_order", P.id, W1.id)`.

**Then**
1. returns: `result == (0, 0, True)`.

### APN-SU-06 — a negative requirement is used as given
- **Rules:** `_approval_summary` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order P = po("PO-1"), but `required_approvals -1`.
2. Approver = poa(P, UB, 9).

**When**
- `result = ans._approval_summary(db, "purchase_order", P.id, W1.id)`.

**Then**
1. returns: `result == (0, -1, True)`.

### APN-SU-07 — purchase order with no approvers and no requirement needs one approval
- **Rules:** `_approval_summary` R2 [BUG-1202]
- **Kind:** bug
- **Expect:** xfail BUG-1202
- **Fails today on:** Then 1 (today `(0, 0, True)`)

**Given**
1. Order P = po("PO-1").

**When**
- `result = ans._approval_summary(db, "purchase_order", P.id, W1.id)`.

**Then**
1. returns: `result == (0, 1, False)`.

### APN-SU-08 — transfer order with no approvers and no requirement needs one approval
- **Rules:** `_approval_summary` R2 [BUG-1203]
- **Kind:** bug
- **Expect:** xfail BUG-1203
- **Fails today on:** Then 1 (today `(0, 0, True)`)

**Given**
1. Order T = to("TO-1").

**When**
- `result = ans._approval_summary(db, "transfer_order", T.id, W1.id)`.

**Then**
1. returns: `result == (0, 1, False)`.

### APN-SU-09 — expense order with no approvers and no requirement needs one approval
- **Rules:** `_approval_summary` R2 [BUG-755]
- **Kind:** bug
- **Expect:** xfail BUG-755
- **Fails today on:** Then 1 (today `(0, 0, True)`)

**Given**
1. Order E = eo("EXP-1").

**When**
- `result = ans._approval_summary(db, "expense_order", E.id, W1.id)`.

**Then**
1. returns: `result == (0, 1, False)`.

### APN-SU-10 — work order that never had an approver stays 0 of 0, met
- **Rules:** `_approval_summary` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order O = wo("WO-1").

**When**
- `result = ans._approval_summary(db, "work_order", O.id, W1.id)`.

**Then**
1. returns: `result == (0, 0, True)`.

### APN-SU-11 — approver rows of W0 and W2 on the same order id are not counted
- **Rules:** `_approval_summary` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Order P = po("PO-1").
2. Approver = poa(P, UA, 8), but `workspace_id W0.id`, approved.
3. Approver = poa(P, UB, 9), but approved.
4. Approver = poa(P, UD, 10).
5. Approver = poa(P, UC, 11), but `workspace_id W2.id`, approved.

**When**
- `result = ans._approval_summary(db, "purchase_order", P.id, W1.id)`.

**Then**
1. returns: `result == (1, 2, False)`.

### APN-SU-12 — more approved than required
- **Rules:** `_approval_summary` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order P = po("PO-1"), but `required_approvals 1`.
2. Approver = poa(P, UB, 9), but approved.
3. Approver = poa(P, UD, 10), but approved.

**When**
- `result = ans._approval_summary(db, "purchase_order", P.id, W1.id)`.

**Then**
1. returns: `result == (2, 1, True)`.

### APN-SU-13 — unknown purchase order id is 404
- **Rules:** `_approval_summary` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `ans._approval_summary(db, "purchase_order", MISSING, W1.id)` under `raises: HTTPException`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Purchase order with ID 999999999 not found"`.

### APN-SU-14 — a purchase order of W2 is 404 in W1
- **Rules:** `_approval_summary` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Order P9 = W2 po("PO-9").
2. Approver = poa(P9, UZ2, 9), but `workspace_id W2.id`.

**When**
- `ans._approval_summary(db, "purchase_order", P9.id, W1.id)` under `raises: HTTPException`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Purchase order with ID {P9.id} not found"`.

### APN-SU-15 — unknown transfer order id is 404
- **Rules:** `_approval_summary` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `ans._approval_summary(db, "transfer_order", MISSING, W1.id)` under `raises: HTTPException`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Transfer order with ID 999999999 not found"`.

### APN-SU-16 — unknown expense order id is 404
- **Rules:** `_approval_summary` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `ans._approval_summary(db, "expense_order", MISSING, W1.id)` under `raises: HTTPException`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Expense order with ID 999999999 not found"`.

### APN-SU-17 — a work order of W0 is 404 in W1
- **Rules:** `_approval_summary` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Order O0 = W0 wo("WO-0").

**When**
- `ans._approval_summary(db, "work_order", O0.id, W1.id)` under `raises: HTTPException`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Work order with ID {O0.id} not found"`.

### APN-SU-18 — an unknown type gives 0 of 0, met, with no lookup
- **Rules:** `_approval_summary` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = ans._approval_summary(db, "project_component", MISSING, W1.id)`.

**Then**
1. returns: `result == (0, 0, True)`.

### APN-SU-19 — sales order: approvers are counted
- **Rules:** `_approval_summary` R6a [BUG-1205]
- **Kind:** bug
- **Expect:** xfail BUG-1205
- **Fails today on:** Then 1 (today `(0, 0, True)`)

**Given**
1. Order S = so("SO-1").
2. Approver = soa(S, UB, 9), but approved.
3. Approver = soa(S, UD, 10).

**When**
- `result = ans._approval_summary(db, "sales_order", S.id, W1.id)`.

**Then**
1. returns: `result == (1, 2, False)`.

### APN-SU-20 — sales order with no approvers and no requirement needs one approval
- **Rules:** `_approval_summary` R6a [BUG-1205, BUG-736]
- **Kind:** bug
- **Expect:** xfail BUG-1205
- **Fails today on:** Then 1 (today `(0, 0, True)`)

**Given**
1. Order S = so("SO-1").

**When**
- `result = ans._approval_summary(db, "sales_order", S.id, W1.id)`.

**Then**
1. returns: `result == (0, 1, False)`.

### APN-SU-21 — an unknown sales order id is 404
- **Rules:** `_approval_summary` R6a [BUG-1205]
- **Kind:** bug
- **Expect:** xfail BUG-1205
- **Fails today on:** Then 1 (the call raises nothing today: it returns `(0, 0, True)`)

**Given**
1. Standing rows only.

**When**
- `ans._approval_summary(db, "sales_order", MISSING, W1.id)` under `raises: HTTPException`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Sales order with ID {MISSING} not found"`.

### APN-SU-22 — another workspace's sales order id is 404
- **Rules:** `_approval_summary` R6a [BUG-1205]
- **Kind:** bug
- **Expect:** xfail BUG-1205
- **Fails today on:** Then 1 (the call raises nothing today: it returns `(0, 0, True)`)

**Given**
1. Order S9 = so("SO-9"), but `workspace_id W2.id`.

**When**
- `ans._approval_summary(db, "sales_order", S9.id, W1.id)` under `raises: HTTPException`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Sales order with ID {S9.id} not found"`.

## `build_approval_preview`

### APN-BP-01 — requirement 0 reads "Ready for review"
- **Rules:** `build_approval_preview` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order P = po("PO-1"), but `required_approvals 0`.
2. Approver = poa(P, UB, 9).

**When**
- `result = ans.build_approval_preview(db, "purchase_order", P.id, W1.id)`.

**Then**
1. returns: `result == "Ready for review"`.

### APN-BP-02 — a negative requirement reads "Ready for review"
- **Rules:** `build_approval_preview` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order P = po("PO-1"), but `required_approvals -1`.

**When**
- `result = ans.build_approval_preview(db, "purchase_order", P.id, W1.id)`.

**Then**
1. returns: `result == "Ready for review"`.

### APN-BP-03 — work order without approvers reads "Ready for review"
- **Rules:** `build_approval_preview` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order O = wo("WO-1").

**When**
- `result = ans.build_approval_preview(db, "work_order", O.id, W1.id)`.

**Then**
1. returns: `result == "Ready for review"`.

### APN-BP-04 — purchase order without approvers reads "0 of 1"
- **Rules:** `build_approval_preview` R1 (via `_approval_summary` R2) [BUG-1202]
- **Kind:** bug
- **Expect:** xfail BUG-1202
- **Fails today on:** Then 1 (today `"Ready for review"`)

**Given**
1. Order P = po("PO-1").

**When**
- `result = ans.build_approval_preview(db, "purchase_order", P.id, W1.id)`.

**Then**
1. returns: `result == "0 of 1 approval(s) collected"`.

### APN-BP-05 — progress text with a positive requirement
- **Rules:** `build_approval_preview` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order P = po("PO-1").
2. Approver = poa(P, UB, 9).
3. Approver = poa(P, UD, 10), but approved.
4. Approver = poa(P, UC, 11).

**When**
- `result = ans.build_approval_preview(db, "purchase_order", P.id, W1.id)`.

**Then**
1. returns: `result == "1 of 3 approval(s) collected"`.

### APN-BP-06 — requirement 1 reads as progress, also when exceeded
- **Rules:** `build_approval_preview` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order E = eo("EXP-1"), but `required_approvals 1`.
2. Approver = eoa(E, UB, 9), but approved.
3. Approver = eoa(E, UD, 10), but approved.

**When**
- `result = ans.build_approval_preview(db, "expense_order", E.id, W1.id)`.

**Then**
1. returns: `result == "2 of 1 approval(s) collected"`.

### APN-BP-07 — the 404 of the summary passes through
- **Rules:** `build_approval_preview` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `ans.build_approval_preview(db, "transfer_order", MISSING, W1.id)` under `raises: HTTPException`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Transfer order with ID 999999999 not found"`.

## `_is_approval_ready`

### APN-RD-01 — purchase order with the three sections confirmed is ready; invoice ignored
- **Rules:** `_is_approval_ready` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order P = ready po("PO-1") (`invoice_confirmed False`).

**When**
- `result = ans._is_approval_ready(db, "purchase_order", P, W1.id)`.

**Then**
1. returns: `result is True`.

### APN-RD-02 — purchase order without supplier confirmed is not ready
- **Rules:** `_is_approval_ready` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order P = ready po("PO-1"), but `supplier_confirmed False`, `invoice_confirmed True`.

**When**
- `result = ans._is_approval_ready(db, "purchase_order", P, W1.id)`.

**Then**
1. returns: `result is False`.

### APN-RD-03 — purchase order without details confirmed is not ready
- **Rules:** `_is_approval_ready` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order P = ready po("PO-1"), but `details_confirmed False`.

**When**
- `result = ans._is_approval_ready(db, "purchase_order", P, W1.id)`.

**Then**
1. returns: `result is False`.

### APN-RD-04 — purchase order without items confirmed is not ready
- **Rules:** `_is_approval_ready` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order P = ready po("PO-1"), but `items_confirmed False`.

**When**
- `result = ans._is_approval_ready(db, "purchase_order", P, W1.id)`.

**Then**
1. returns: `result is False`.

### APN-RD-05 — the in-memory values are read, not the stored row
- **Rules:** `_is_approval_ready` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Order P = ready po("PO-1"), but `items_confirmed False` (flushed).
2. `P.items_confirmed = True` (not flushed).

**When**
- `result = ans._is_approval_ready(db, "purchase_order", P, W1.id)`.

**Then**
1. returns: `result is True`.

### APN-RD-06 — expense order that meets every check is ready
- **Rules:** `_is_approval_ready` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order E = eo("EXP-1").
2. Line = eo line(E).

**When**
- `result = ans._is_approval_ready(db, "expense_order", E, W1.id)`.

**Then**
1. returns: `result is True`.

### APN-RD-07 — expense order with no lines is not ready
- **Rules:** `_is_approval_ready` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order E = eo("EXP-1").

**When**
- `result = ans._is_approval_ready(db, "expense_order", E, W1.id)`.

**Then**
1. returns: `result is False`.

### APN-RD-08 — expense order whose only line is in W2 is not ready
- **Rules:** `_is_approval_ready` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Order E = eo("EXP-1").
2. Line = eo line(E), but `workspace_id W2.id`.

**When**
- `result = ans._is_approval_ready(db, "expense_order", E, W1.id)`.

**Then**
1. returns: `result is False`.

### APN-RD-09 — expense order with a quantity-0 line is not ready
- **Rules:** `_is_approval_ready` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order E = eo("EXP-1").
2. Line = eo line(E), but `quantity Decimal("0")`.

**When**
- `result = ans._is_approval_ready(db, "expense_order", E, W1.id)`.

**Then**
1. returns: `result is False`.

### APN-RD-10 — work order with a title and a factory is ready
- **Rules:** `_is_approval_ready` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order O = wo("WO-1"), but `title " x "`.

**When**
- `result = ans._is_approval_ready(db, "work_order", O, W1.id)`.

**Then**
1. returns: `result is True`.

### APN-RD-11 — work order with a blank title is not ready
- **Rules:** `_is_approval_ready` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order O = wo("WO-1"), but `title "   "`.

**When**
- `result = ans._is_approval_ready(db, "work_order", O, W1.id)`.

**Then**
1. returns: `result is False`.

### APN-RD-12 — work order without a factory is not ready
- **Rules:** `_is_approval_ready` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order O = wo("WO-1") (flushed, with its default factory).
2. `O.factory_id = None` (not flushed).

**When**
- `result = ans._is_approval_ready(db, "work_order", O, W1.id)`.

**Then**
1. returns: `result is False`.

### APN-RD-13 — transfer order with a full route and one item is ready
- **Rules:** `_is_approval_ready` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order T = to("TO-1").
2. Line = to line(T).

**When**
- `result = ans._is_approval_ready(db, "transfer_order", T, W1.id)`.

**Then**
1. returns: `result is True`.

### APN-RD-14 — a location id of 0 counts as unset
- **Rules:** `_is_approval_ready` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order T = to("TO-1"), but `source_location_id 0`.
2. Line = to line(T).

**When**
- `result = ans._is_approval_ready(db, "transfer_order", T, W1.id)`.

**Then**
1. returns: `result is False`.

### APN-RD-15 — no destination type is not ready
- **Rules:** `_is_approval_ready` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order T = to("TO-1") (flushed, with its default route).
2. Line = to line(T).
3. `T.destination_location_type = None` (not flushed).

**When**
- `result = ans._is_approval_ready(db, "transfer_order", T, W1.id)`.

**Then**
1. returns: `result is False`.

### APN-RD-16 — same type and same id on both ends is not ready
- **Rules:** `_is_approval_ready` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order T = to("TO-1"), but `destination_location_id MISSING`.
2. Line = to line(T).

**When**
- `result = ans._is_approval_ready(db, "transfer_order", T, W1.id)`.

**Then**
1. returns: `result is False`.

### APN-RD-17 — same id but a different type is a different place
- **Rules:** `_is_approval_ready` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order T = to("TO-1"), but `destination_location_type "factory"`, `destination_location_id MISSING`.
2. Line = to line(T).

**When**
- `result = ans._is_approval_ready(db, "transfer_order", T, W1.id)`.

**Then**
1. returns: `result is True`.

### APN-RD-18 — transfer order with no items is not ready
- **Rules:** `_is_approval_ready` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order T = to("TO-1").

**When**
- `result = ans._is_approval_ready(db, "transfer_order", T, W1.id)`.

**Then**
1. returns: `result is False`.

### APN-RD-19 — transfer order whose only item is in W0 is not ready
- **Rules:** `_is_approval_ready` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Order T = to("TO-1").
2. Line = to line(T), but `workspace_id W0.id`.

**When**
- `result = ans._is_approval_ready(db, "transfer_order", T, W1.id)`.

**Then**
1. returns: `result is False`.

### APN-RD-20 — an unknown type is never ready
- **Rules:** `_is_approval_ready` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = ans._is_approval_ready(db, "project_component", SimpleNamespace(id=1), W1.id)`.

**Then**
1. returns: `result is False`.

### APN-RD-21 — a voided purchase order is judged by its sections alone
- **Rules:** `_is_approval_ready` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order P = ready po("PO-1"), but `voided True`.

**When**
- `result = ans._is_approval_ready(db, "purchase_order", P, W1.id)`.

**Then**
1. returns: `result is True`.

### APN-RD-22 — a deleted work order is judged by title and factory alone
- **Rules:** `_is_approval_ready` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order O = wo("WO-1"), but `is_deleted True`, `is_active False`.

**When**
- `result = ans._is_approval_ready(db, "work_order", O, W1.id)`.

**Then**
1. returns: `result is True`.

## `_section_gap_preview`

### APN-GP-01 — purchase order lists the missing labels in order
- **Rules:** `_section_gap_preview` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. `order = SimpleNamespace(supplier_confirmed=True, details_confirmed=False, items_confirmed=False, invoice_confirmed=False)`.

**When**
- `result = ans._section_gap_preview(db, "purchase_order", order)`.

**Then**
1. returns: `result == "Confirm Order details, Order items before approvals can proceed"`.

### APN-GP-02 — missing attributes count as unconfirmed
- **Rules:** `_section_gap_preview` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `order = SimpleNamespace()`.

**When**
- `result = ans._section_gap_preview(db, "purchase_order", order)`.

**Then**
1. returns: `result == "Confirm Supplier, Order details, Order items before approvals can proceed"`.

### APN-GP-03 — only the last section missing
- **Rules:** `_section_gap_preview` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `order = SimpleNamespace(supplier_confirmed=True, details_confirmed=True, items_confirmed=False, invoice_confirmed=True)`.

**When**
- `result = ans._section_gap_preview(db, "purchase_order", order)`.

**Then**
1. returns: `result == "Confirm Order items before approvals can proceed"`.

### APN-GP-04 — all three confirmed: the invoice is never listed
- **Rules:** `_section_gap_preview` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `order = SimpleNamespace(supplier_confirmed=True, details_confirmed=True, items_confirmed=True, invoice_confirmed=False)`.

**When**
- `result = ans._section_gap_preview(db, "purchase_order", order)`.

**Then**
1. returns: `result == "Complete remaining sections before approvals can proceed"`.

### APN-GP-05 — expense order: the manager's reason (blank description)
- **Rules:** `_section_gap_preview` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order E = eo("EXP-1"), but `description "   "`.
2. Line = eo line(E).

**When**
- `result = ans._section_gap_preview(db, "expense_order", E)`.

**Then**
1. returns: `result == "Add a description before approvals can proceed"`.

### APN-GP-06 — expense order: the manager's reason (no lines)
- **Rules:** `_section_gap_preview` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order E = eo("EXP-1").

**When**
- `result = ans._section_gap_preview(db, "expense_order", E)`.

**Then**
1. returns: `result == "Add at least one expense line before approvals can proceed"`.

### APN-GP-07 — expense order with no reason gets the fallback
- **Rules:** `_section_gap_preview` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order E = eo("EXP-1").
2. Line = eo line(E).

**When**
- `result = ans._section_gap_preview(db, "expense_order", E)`.

**Then**
1. returns: `result == "Complete remaining details before approvals can proceed"`.

### APN-GP-08 — expense order with a quantity-0 line gets the fallback today
- **Rules:** `_section_gap_preview` R3 (spec G2: retire when BUG-758 is fixed)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order E = eo("EXP-1").
2. Line = eo line(E), but `quantity Decimal("0")`.

**When**
- `result = ans._section_gap_preview(db, "expense_order", E)`.

**Then**
1. returns: `result == "Complete remaining details before approvals can proceed"`.

### APN-GP-09 — work order with a blank title
- **Rules:** `_section_gap_preview` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `order = SimpleNamespace(title="  ", factory_id=None)`.

**When**
- `result = ans._section_gap_preview(db, "work_order", order)`.

**Then**
1. returns: `result == "Work order setup is incomplete"`.

### APN-GP-10 — work order with no factory
- **Rules:** `_section_gap_preview` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `order = SimpleNamespace(title="Fix", factory_id=None)`.

**When**
- `result = ans._section_gap_preview(db, "work_order", order)`.

**Then**
1. returns: `result == "Set a factory before approvals can proceed"`.

### APN-GP-11 — work order with title and factory gets the fallback
- **Rules:** `_section_gap_preview` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `order = SimpleNamespace(title="Fix", factory_id=5)`.

**When**
- `result = ans._section_gap_preview(db, "work_order", order)`.

**Then**
1. returns: `result == "Complete remaining details before approvals can proceed"`.

### APN-GP-12 — transfer order with a route field missing
- **Rules:** `_section_gap_preview` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order T = to("TO-1") (flushed, with its default route).
2. `T.source_location_type = None` (not flushed).

**When**
- `result = ans._section_gap_preview(db, "transfer_order", T)`.

**Then**
1. returns: `result == "Set source and destination before approvals can proceed"`.

### APN-GP-13 — transfer order with the same place at both ends says "add an item"
- **Rules:** `_section_gap_preview` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order T = to("TO-1"), but `destination_location_id MISSING`.
2. Line = to line(T).

**When**
- `result = ans._section_gap_preview(db, "transfer_order", T)`.

**Then**
1. returns: `result == "Add at least one item before approvals can proceed"`.

### APN-GP-14 — a ready transfer order still says "add an item"
- **Rules:** `_section_gap_preview` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order T = to("TO-1").
2. Line = to line(T).

**When**
- `result = ans._section_gap_preview(db, "transfer_order", T)`.

**Then**
1. returns: `result == "Add at least one item before approvals can proceed"`.

### APN-GP-15 — an unknown type gives None
- **Rules:** `_section_gap_preview` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = ans._section_gap_preview(db, "project_component", SimpleNamespace(title="x"))`.

**Then**
1. returns: `result is None`.

## `_pending_approver_ids`

### APN-PA-01 — purchase order: unapproved approvers in assignment order, membership not looked at
- **Rules:** `_pending_approver_ids` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order P = po("PO-1").
2. Approver = poa(P, UB, 11).
3. Approver = poa(P, UD, 10), but approved.
4. Approver = poa(P, US, 9) (US is suspended).

**When**
- `result = ans._pending_approver_ids(db, "purchase_order", P.id, W1.id)`.

**Then**
1. returns: `result == [US.id, UB.id]`.

### APN-PA-02 — approver rows of W0 and W2 on the order id are left out
- **Rules:** `_pending_approver_ids` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Order P = po("PO-1").
2. Approver = poa(P, UA, 8), but `workspace_id W0.id`.
3. Approver = poa(P, UB, 9).
4. Approver = poa(P, UD, 10), but `workspace_id W2.id`.

**When**
- `result = ans._pending_approver_ids(db, "purchase_order", P.id, W1.id)`.

**Then**
1. returns: `result == [UB.id]`.

### APN-PA-03 — transfer order pending approvers
- **Rules:** `_pending_approver_ids` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order T = to("TO-1").
2. Approver = toa(T, UB, 9), but approved.
3. Approver = toa(T, UD, 10).

**When**
- `result = ans._pending_approver_ids(db, "transfer_order", T.id, W1.id)`.

**Then**
1. returns: `result == [UD.id]`.

### APN-PA-04 — expense order pending approvers
- **Rules:** `_pending_approver_ids` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order E = eo("EXP-1").
2. Approver = eoa(E, UD, 10).
3. Approver = eoa(E, UB, 9).

**When**
- `result = ans._pending_approver_ids(db, "expense_order", E.id, W1.id)`.

**Then**
1. returns: `result == [UB.id, UD.id]`.

### APN-PA-05 — work order pending approvers
- **Rules:** `_pending_approver_ids` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order O = wo("WO-1").
2. Approver = woa(O, UB, 9).
3. Approver = woa(O, UD, 10), but approved.

**When**
- `result = ans._pending_approver_ids(db, "work_order", O.id, W1.id)`.

**Then**
1. returns: `result == [UB.id]`.

### APN-PA-06 — an unknown order id gives [] with no error
- **Rules:** `_pending_approver_ids` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = ans._pending_approver_ids(db, "purchase_order", MISSING, W1.id)`.

**Then**
1. returns: `result == []`.

### APN-PA-07 — an order of W2 asked for in W1 gives []
- **Rules:** `_pending_approver_ids` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Order P9 = W2 po("PO-9").
2. Approver = poa(P9, UZ2, 9), but `workspace_id W2.id`.

**When**
- `result = ans._pending_approver_ids(db, "purchase_order", P9.id, W1.id)`.

**Then**
1. returns: `result == []`.

### APN-PA-08 — an unknown type gives []
- **Rules:** `_pending_approver_ids` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = ans._pending_approver_ids(db, "project_component", 1, W1.id)`.

**Then**
1. returns: `result == []`.

### APN-PA-09 — sales order pending approvers
- **Rules:** `_pending_approver_ids` R3a [BUG-1205]
- **Kind:** bug
- **Expect:** xfail BUG-1205
- **Fails today on:** Then 1 (today `[]`)

**Given**
1. Order S = so("SO-1").
2. Approver = soa(S, UB, 9).
3. Approver = soa(S, UD, 10), but approved.

**When**
- `result = ans._pending_approver_ids(db, "sales_order", S.id, W1.id)`.

**Then**
1. returns: `result == [UB.id]`.

## `_has_approvers`

### APN-HA-01 — a requirement with no approver rows counts as having approvers
- **Rules:** `_has_approvers` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order P = po("PO-1"), but `required_approvals 2`.

**When**
- `result = ans._has_approvers(db, "purchase_order", P.id, W1.id)`.

**Then**
1. returns: `result is True`.

### APN-HA-02 — approver rows with requirement 0 count as none
- **Rules:** `_has_approvers` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order P = po("PO-1"), but `required_approvals 0`.
2. Approver = poa(P, UB, 9).

**When**
- `result = ans._has_approvers(db, "purchase_order", P.id, W1.id)`.

**Then**
1. returns: `result is False`.

### APN-HA-03 — requirement -1 counts as none
- **Rules:** `_has_approvers` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order T = to("TO-1"), but `required_approvals -1`.
2. Approver = toa(T, UB, 9).

**When**
- `result = ans._has_approvers(db, "transfer_order", T.id, W1.id)`.

**Then**
1. returns: `result is False`.

### APN-HA-04 — one approver row and no requirement
- **Rules:** `_has_approvers` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order P = po("PO-1").
2. Approver = poa(P, UB, 9).

**When**
- `result = ans._has_approvers(db, "purchase_order", P.id, W1.id)`.

**Then**
1. returns: `result is True`.

### APN-HA-05 — purchase order with no approvers and no requirement
- **Rules:** `_has_approvers` R1 (via `_approval_summary` R2) [BUG-1202]
- **Kind:** bug
- **Expect:** xfail BUG-1202
- **Fails today on:** Then 1 (today `False`: required is 0)

**Given**
1. Order P = po("PO-1").

**When**
- `result = ans._has_approvers(db, "purchase_order", P.id, W1.id)`.

**Then**
1. returns: `result is True`.

### APN-HA-06 — the 404 of the summary passes through
- **Rules:** `_has_approvers` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `ans._has_approvers(db, "work_order", MISSING, W1.id)` under `raises: HTTPException`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Work order with ID 999999999 not found"`.

## `notify_approval_assigned`

### APN-AS-01 — the new approver is told who assigned them, on which order
- **Rules:** `notify_approval_assigned` R1, R2, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order P = po("PO-1").
2. Approver R = poa(P, UB, 9).

**When**
- `result = ans.notify_approval_assigned(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id, approver_user_id=UB.id, approver_record_id=R.id, order=None)`.

**Then**
1. returns: `result is None`.
2. count: `len(notes()) == 1`.
3. count: `len(to(UB)) == 1`.
4. re-read note of UB: `notification_type == "approval_assigned"`, `entity_type == "purchase_order"`, `entity_id == P.id`, `source_type == "approver"`, `source_id == R.id`, `actor_user_id == UA.id`, `workspace_id == W1.id`.
5. re-read note of UB: `preview == f"Assigned by Ann on PO-{P.id}"`.

### APN-AS-02 — no actor reads "Someone"
- **Rules:** `notify_approval_assigned` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `ans.notify_approval_assigned(db, workspace_id=W1.id, entity_type="work_order", entity_id=41, actor_user_id=None, approver_user_id=UB.id, approver_record_id=7, order=None)`.

**Then**
1. count: `len(to(UB)) == 1`.
2. re-read note of UB: `preview == "Assigned by Someone on WO-41"`, `actor_user_id is None`, `source_id == 7`.

### APN-AS-03 — on a ready order the preview carries the progress, counting the new approver
- **Rules:** `notify_approval_assigned` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order P = ready po("PO-1").
2. Approver = poa(P, UD, 9), but approved.
3. Approver = poa(P, UC, 10).
4. Approver R = poa(P, UB, 11).

**When**
- `ans.notify_approval_assigned(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id, approver_user_id=UB.id, approver_record_id=R.id, order=P, ready_for_approval=True)`.

**Then**
1. count: `len(notes()) == 1`.
2. re-read note of UB: `preview == "Assigned by Ann · ready for your approval · 1 of 3 approval(s) collected"`.

### APN-AS-04 — an approver who assigned themself is still notified
- **Rules:** `notify_approval_assigned` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `ans.notify_approval_assigned(db, workspace_id=W1.id, entity_type="expense_order", entity_id=485393, actor_user_id=UB.id, approver_user_id=UB.id, approver_record_id=7, order=None)`.

**Then**
1. count: `len(to(UB)) == 1`.
2. re-read note of UB: `actor_user_id == UB.id`, `preview == "Assigned by Bob on EXP-485393"`.

### APN-AS-05 — a suspended approver is not notified
- **Rules:** `notify_approval_assigned` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Standing rows only (US suspended in W1).

**When**
- `result = ans.notify_approval_assigned(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=41, actor_user_id=UA.id, approver_user_id=US.id, approver_record_id=7, order=None)`.

**Then**
1. returns: `result is None`.
2. nothing written.

### APN-AS-06 — an approver active only in W0 is not notified
- **Rules:** `notify_approval_assigned` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Standing rows only (UZ0 active in W0 only).

**When**
- `ans.notify_approval_assigned(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=41, actor_user_id=UA.id, approver_user_id=UZ0.id, approver_record_id=7, order=None)`.

**Then**
1. nothing written.

### APN-AS-07 — an approver active only in W2 is not notified
- **Rules:** `notify_approval_assigned` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Standing rows only (UZ2 active in W2 only).

**When**
- `ans.notify_approval_assigned(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=41, actor_user_id=UA.id, approver_user_id=UZ2.id, approver_record_id=7, order=None)`.

**Then**
1. nothing written.

### APN-AS-08 — ready preview on an unknown order raises 404 and writes nothing
- **Rules:** `notify_approval_assigned` R6
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `ans.notify_approval_assigned(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=MISSING, actor_user_id=UA.id, approver_user_id=UB.id, approver_record_id=7, order=None, ready_for_approval=True)` under `raises: HTTPException`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Purchase order with ID 999999999 not found"`.
3. session: `not db.new`.
4. nothing written.

### APN-AS-09 — writes but never commits or rolls back
- **Rules:** `notify_approval_assigned` R1 (no commit; spec Overview)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Standing rows, then the commit point.

**When**
- under **spies**: `ans.notify_approval_assigned(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=41, actor_user_id=UA.id, approver_user_id=UB.id, approver_record_id=7, order=None)`.

**Then**
1. mock called: `cm.call_count == 0`.
2. mock called: `rb.call_count == 0`.
3. committed: `len(notes()) == 0`.

## `notify_approval_pending_for_order`

### APN-PE-01 — every pending approver gets "approval pending" with the progress
- **Rules:** `notify_approval_pending_for_order` R1, R2, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order P = po("PO-1").
2. Approver = poa(P, UB, 9).
3. Approver = poa(P, UD, 10), but approved.
4. Approver = poa(P, UC, 11).

**When**
- `result = ans.notify_approval_pending_for_order(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id)`.

**Then**
1. returns: `result is None`.
2. count: `recips() == sorted([UB.id, UC.id])`.
3. count: `len(to(UD)) == 0`.
4. re-read note of UB: `notification_type == "approval_pending"`, `entity_type == "purchase_order"`, `entity_id == P.id`, `source_type == "order"`, `source_id == P.id`, `actor_user_id == UA.id`, `preview == "1 of 3 approval(s) collected"`.
5. re-read note of UC: `notification_type == "approval_pending"`, `preview == "1 of 3 approval(s) collected"`.

### APN-PE-02 — with no exclusions the actor, a pending approver, is notified
- **Rules:** `notify_approval_pending_for_order` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Order P = po("PO-1").
2. Approver = poa(P, UA, 9).
3. Approver = poa(P, UB, 10).

**When**
- `ans.notify_approval_pending_for_order(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id, exclude_user_ids=None)`.

**Then**
1. count: `recips() == sorted([UA.id, UB.id])`.
2. re-read note of UA: `actor_user_id == UA.id`, `notification_type == "approval_pending"`.

### APN-PE-03 — an empty exclusion set excludes nobody
- **Rules:** `notify_approval_pending_for_order` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order P = po("PO-1").
2. Approver = poa(P, UA, 9).
3. Approver = poa(P, UB, 10).

**When**
- `ans.notify_approval_pending_for_order(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id, exclude_user_ids=set())`.

**Then**
1. count: `recips() == sorted([UA.id, UB.id])`.

### APN-PE-04 — an excluded pending approver gets nothing
- **Rules:** `notify_approval_pending_for_order` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order P = po("PO-1").
2. Approver = poa(P, UB, 9).
3. Approver = poa(P, UC, 10).

**When**
- `ans.notify_approval_pending_for_order(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id, exclude_user_ids={UB.id})`.

**Then**
1. count: `recips() == [UC.id]`.

### APN-PE-05 — suspended, invited and inactive pending approvers get nothing
- **Rules:** `notify_approval_pending_for_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Order P = po("PO-1").
2. Approver = poa(P, US, 8).
3. Approver = poa(P, UB, 9).
4. Approver = poa(P, UI, 10).
5. Approver = poa(P, UV, 11).

**When**
- `ans.notify_approval_pending_for_order(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id)`.

**Then**
1. count: `recips() == [UB.id]`.
2. re-read note of UB: `preview == "0 of 4 approval(s) collected"`.

### APN-PE-06 — pending approvers active only in W0 or W2 get nothing
- **Rules:** `notify_approval_pending_for_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Order P = po("PO-1").
2. Approver = poa(P, UZ0, 8).
3. Approver = poa(P, UB, 9).
4. Approver = poa(P, UZ2, 10).

**When**
- `ans.notify_approval_pending_for_order(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id)`.

**Then**
1. count: `recips() == [UB.id]`.

### APN-PE-07 — approver rows of W0 and W2 on the order id notify nobody
- **Rules:** `notify_approval_pending_for_order` R2 (via `_pending_approver_ids` R1)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Order P = po("PO-1").
2. Approver = poa(P, UC, 8), but `workspace_id W0.id`.
3. Approver = poa(P, UB, 9).
4. Approver = poa(P, UD, 10), but `workspace_id W2.id`.

**When**
- `ans.notify_approval_pending_for_order(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id)`.

**Then**
1. count: `recips() == [UB.id]`.
2. re-read note of UB: `preview == "0 of 1 approval(s) collected"`.

### APN-PE-08 — every approver already approved: nothing written
- **Rules:** `notify_approval_pending_for_order` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order P = po("PO-1").
2. Approver = poa(P, UB, 9), but approved.
3. Approver = poa(P, UD, 10), but approved.

**When**
- `result = ans.notify_approval_pending_for_order(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id)`.

**Then**
1. returns: `result is None`.
2. session: `not db.new`.
3. nothing written.

### APN-PE-09 — no actor is stored as NULL
- **Rules:** `notify_approval_pending_for_order` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order O = wo("WO-1").
2. Approver = woa(O, UB, 9).

**When**
- `ans.notify_approval_pending_for_order(db, workspace_id=W1.id, entity_type="work_order", entity_id=O.id, actor_user_id=None)`.

**Then**
1. count: `recips() == [UB.id]`.
2. re-read note of UB: `actor_user_id is None`, `entity_type == "work_order"`, `entity_id == O.id`, `preview == "0 of 1 approval(s) collected"`.

### APN-PE-10 — an unknown order raises 404 even though nobody would be notified
- **Rules:** `notify_approval_pending_for_order` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `ans.notify_approval_pending_for_order(db, workspace_id=W1.id, entity_type="expense_order", entity_id=MISSING, actor_user_id=UA.id)` under `raises: HTTPException`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Expense order with ID 999999999 not found"`.
3. nothing written.

### APN-PE-11 — writes but never commits or rolls back
- **Rules:** `notify_approval_pending_for_order` R2 (no commit; spec Overview)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Order P = po("PO-1").
2. Approver = poa(P, UB, 9).
3. The commit point.

**When**
- under **spies**: `ans.notify_approval_pending_for_order(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id)`.

**Then**
1. mock called: `cm.call_count == 0`.
2. mock called: `rb.call_count == 0`.
3. committed: `len(notes()) == 0`.

## `notify_section_confirm_needed`

### APN-SC-01 — the creator gets the given reason
- **Rules:** `notify_section_confirm_needed` R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order P = po("PO-1") (created by UC).

**When**
- `result = ans.notify_section_confirm_needed(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id, order=P, reason="Please check")`.

**Then**
1. returns: `result is None`.
2. count: `recips() == [UC.id]`.
3. re-read note of UC: `notification_type == "section_confirm"`, `entity_type == "purchase_order"`, `entity_id == P.id`, `source_type == "section"`, `source_id == P.id`, `actor_user_id == UA.id`, `preview == "Please check"`.

### APN-SC-02 — no reason: the gap text is used
- **Rules:** `notify_section_confirm_needed` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order P = po("PO-1") (created by UC; no section confirmed).

**When**
- `ans.notify_section_confirm_needed(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id, order=P, reason=None)`.

**Then**
1. count: `recips() == [UC.id]`.
2. re-read note of UC: `preview == "Confirm Supplier, Order details, Order items before approvals can proceed"`.

### APN-SC-03 — an empty reason also falls back to the gap text
- **Rules:** `notify_section_confirm_needed` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `order = SimpleNamespace(created_by=UC.id, supplier_confirmed=True, details_confirmed=True, items_confirmed=False)`.

**When**
- `ans.notify_section_confirm_needed(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=41, actor_user_id=UA.id, order=order, reason="")`.

**Then**
1. count: `recips() == [UC.id]`.
2. re-read note of UC: `preview == "Confirm Order items before approvals can proceed"`.

### APN-SC-04 — an unknown type with no reason stores a NULL preview
- **Rules:** `notify_section_confirm_needed` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `order = SimpleNamespace(created_by=UC.id)`.

**When**
- `ans.notify_section_confirm_needed(db, workspace_id=W1.id, entity_type="project_component", entity_id=3, actor_user_id=UA.id, order=order)`.

**Then**
1. count: `recips() == [UC.id]`.
2. re-read note of UC: `preview is None`, `entity_type == "project_component"`.

### APN-SC-05 — a work order with no creator: nothing written
- **Rules:** `notify_section_confirm_needed` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order O = wo("WO-1"), but `created_by None`.

**When**
- `result = ans.notify_section_confirm_needed(db, workspace_id=W1.id, entity_type="work_order", entity_id=O.id, actor_user_id=UA.id, order=O, reason="Please check")`.

**Then**
1. returns: `result is None`.
2. session: `not db.new`.
3. nothing written.

### APN-SC-06 — an order object without `created_by`: nothing written
- **Rules:** `notify_section_confirm_needed` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `order = SimpleNamespace()`.

**When**
- `ans.notify_section_confirm_needed(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=41, actor_user_id=UA.id, order=order, reason="Please check")`.

**Then**
1. nothing written.

### APN-SC-07 — the creator is notified when they are the actor
- **Rules:** `notify_section_confirm_needed` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Order P = po("PO-1") (created by UC).

**When**
- `ans.notify_section_confirm_needed(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UC.id, order=P, reason="Please check")`.

**Then**
1. count: `recips() == [UC.id]`.
2. re-read note of UC: `actor_user_id == UC.id`.

### APN-SC-08 — a suspended creator is not notified
- **Rules:** `notify_section_confirm_needed` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. `order = SimpleNamespace(created_by=US.id)`.

**When**
- `ans.notify_section_confirm_needed(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=41, actor_user_id=UA.id, order=order, reason="Please check")`.

**Then**
1. nothing written.

### APN-SC-09 — a creator active only in W0 is not notified
- **Rules:** `notify_section_confirm_needed` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. `order = SimpleNamespace(created_by=UZ0.id)`.

**When**
- `ans.notify_section_confirm_needed(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=41, actor_user_id=UA.id, order=order, reason="Please check")`.

**Then**
1. nothing written.

### APN-SC-10 — a creator active only in W2 is not notified
- **Rules:** `notify_section_confirm_needed` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. `order = SimpleNamespace(created_by=UZ2.id)`.

**When**
- `ans.notify_section_confirm_needed(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=41, actor_user_id=UA.id, order=order, reason="Please check")`.

**Then**
1. nothing written.

### APN-SC-11 — writes but never commits or rolls back
- **Rules:** `notify_section_confirm_needed` R2 (no commit; spec Overview)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. `order = SimpleNamespace(created_by=UC.id)`.
2. The commit point.

**When**
- under **spies**: `ans.notify_section_confirm_needed(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=41, actor_user_id=UA.id, order=order, reason="Please check")`.

**Then**
1. mock called: `cm.call_count == 0`.
2. mock called: `rb.call_count == 0`.
3. committed: `len(notes()) == 0`.

## `notify_invoice_action`

### APN-IA-01 — draft: every approver and the creator, once each
- **Rules:** `notify_invoice_action` R1, R2, R3, R4, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order P = po("PO-1") (created by UC; `required_approvals` NULL).
2. Approver = poa(P, UB, 9).
3. Approver = poa(P, UD, 10), but approved.

**When**
- `result = ans.notify_invoice_action(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id, invoice_id=77, action="draft", order=P)`.

**Then**
1. returns: `result is None`.
2. count: `recips() == sorted([UB.id, UC.id, UD.id])`.
3. re-read note of UB: `notification_type == "invoice_action"`, `entity_type == "purchase_order"`, `entity_id == P.id`, `source_type == "invoice"`, `source_id == 77`, `actor_user_id == UA.id`.
4. re-read note of UB: `preview == "draft|Linked payable invoice is in draft — confirm when details look correct"`.
5. re-read note of UD: `preview == "draft|Linked payable invoice is in draft — confirm when details look correct"`.
6. re-read note of UC: `notification_type == "invoice_action"`, `source_id == 77`.

### APN-IA-02 — confirmed on an expense order names the EXP reference
- **Rules:** `notify_invoice_action` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order E = eo("EXP-1") (created by UC).
2. Approver = eoa(E, UB, 9).

**When**
- `ans.notify_invoice_action(db, workspace_id=W1.id, entity_type="expense_order", entity_id=E.id, actor_user_id=UA.id, invoice_id=77, action="confirmed", order=E)`.

**Then**
1. count: `recips() == sorted([UB.id, UC.id])`.
2. re-read note of UB: `preview == f"confirmed|Invoice confirmed on EXP-{E.id} — order locked"`.

### APN-IA-03 — any action other than "draft" reads as confirmed
- **Rules:** `notify_invoice_action` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order O = wo("WO-1") (created by UC; no approvers).

**When**
- `ans.notify_invoice_action(db, workspace_id=W1.id, entity_type="work_order", entity_id=O.id, actor_user_id=UA.id, invoice_id=77, action="voided", order=O)`.

**Then**
1. count: `recips() == [UC.id]`.
2. re-read note of UC: `preview == f"confirmed|Invoice confirmed on WO-{O.id} — order locked"`.

### APN-IA-04 — an empty action reads as confirmed
- **Rules:** `notify_invoice_action` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order T = to("TO-1") (created by UC).
2. Approver = toa(T, UB, 9).

**When**
- `ans.notify_invoice_action(db, workspace_id=W1.id, entity_type="transfer_order", entity_id=T.id, actor_user_id=UA.id, invoice_id=77, action="", order=T)`.

**Then**
1. count: `recips() == sorted([UB.id, UC.id])`.
2. re-read note of UB: `preview == f"confirmed|Invoice confirmed on TO-{T.id} — order locked"`.

### APN-IA-05 — with requirement 0, approvers who approved are left out
- **Rules:** `notify_invoice_action` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order P = po("PO-1"), but `required_approvals 0` (created by UC).
2. Approver = poa(P, UB, 9).
3. Approver = poa(P, UD, 10), but approved.

**When**
- `ans.notify_invoice_action(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id, invoice_id=77, action="confirmed", order=P)`.

**Then**
1. count: `recips() == sorted([UB.id, UC.id])`.
2. count: `len(to(UD)) == 0`.

### APN-IA-06 — with requirement 1, approvers who approved are included
- **Rules:** `notify_invoice_action` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order P = po("PO-1"), but `required_approvals 1` (created by UC).
2. Approver = poa(P, UB, 9), but approved.
3. Approver = poa(P, UD, 10), but approved.

**When**
- `ans.notify_invoice_action(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id, invoice_id=77, action="confirmed", order=P)`.

**Then**
1. count: `recips() == sorted([UB.id, UC.id, UD.id])`.

### APN-IA-07 — a creator who is also an approver gets one notification
- **Rules:** `notify_invoice_action` R2, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order P = po("PO-1") (created by UC).
2. Approver = poa(P, UC, 9).
3. Approver = poa(P, UB, 10), but approved.

**When**
- `ans.notify_invoice_action(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id, invoice_id=77, action="draft", order=P)`.

**Then**
1. count: `recips() == sorted([UB.id, UC.id])`.
2. count: `len(to(UC)) == 1`.

### APN-IA-08 — the actor is not left out
- **Rules:** `notify_invoice_action` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Order P = po("PO-1") (created by UC).
2. Approver = poa(P, UB, 9).

**When**
- `ans.notify_invoice_action(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UC.id, invoice_id=77, action="draft", order=P)`.

**Then**
1. count: `recips() == sorted([UB.id, UC.id])`.
2. re-read note of UC: `actor_user_id == UC.id`.

### APN-IA-09 — suspended, invited and inactive approvers get nothing
- **Rules:** `notify_invoice_action` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Order P = po("PO-1") (created by UC).
2. Approver = poa(P, US, 8).
3. Approver = poa(P, UB, 9).
4. Approver = poa(P, UI, 10).
5. Approver = poa(P, UV, 11), but approved.

**When**
- `ans.notify_invoice_action(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id, invoice_id=77, action="draft", order=P)`.

**Then**
1. count: `recips() == sorted([UB.id, UC.id])`.

### APN-IA-10 — approvers active only in W0 or W2 get nothing
- **Rules:** `notify_invoice_action` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Order P = po("PO-1") (created by UC).
2. Approver = poa(P, UZ0, 8), but approved.
3. Approver = poa(P, UB, 9).
4. Approver = poa(P, UZ2, 10).

**When**
- `ans.notify_invoice_action(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id, invoice_id=77, action="draft", order=P)`.

**Then**
1. count: `recips() == sorted([UB.id, UC.id])`.

### APN-IA-11 — approver rows of W0 and W2 on the order id are no recipients
- **Rules:** `notify_invoice_action` R2, R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Order P = po("PO-1") (created by UC).
2. Approver = poa(P, UA, 8), but `workspace_id W0.id`, approved.
3. Approver = poa(P, UB, 9).
4. Approver = poa(P, UD, 10), but `workspace_id W2.id`.

**When**
- `ans.notify_invoice_action(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UC.id, invoice_id=77, action="draft", order=P)`.

**Then**
1. count: `recips() == sorted([UB.id, UC.id])`.

### APN-IA-12 — no creator: only the approvers
- **Rules:** `notify_invoice_action` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order O = wo("WO-1"), but `created_by None`.
2. Approver = woa(O, UB, 9).

**When**
- `ans.notify_invoice_action(db, workspace_id=W1.id, entity_type="work_order", entity_id=O.id, actor_user_id=UA.id, invoice_id=77, action="draft", order=O)`.

**Then**
1. count: `recips() == [UB.id]`.

### APN-IA-13 — a suspended creator gets nothing
- **Rules:** `notify_invoice_action` R4, R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Order P = po("PO-1"), but `created_by US.id`.
2. Approver = poa(P, UB, 9).

**When**
- `ans.notify_invoice_action(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id, invoice_id=77, action="draft", order=P)`.

**Then**
1. count: `recips() == [UB.id]`.

### APN-IA-14 — an unknown order raises 404 and writes nothing
- **Rules:** `notify_invoice_action` R6
- **Kind:** error
- **Expect:** pass

**Given**
1. `order = SimpleNamespace(created_by=UC.id)`.

**When**
- `ans.notify_invoice_action(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=MISSING, actor_user_id=UA.id, invoice_id=77, action="draft", order=order)` under `raises: HTTPException`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Purchase order with ID 999999999 not found"`.
3. session: `not db.new`.
4. nothing written.

### APN-IA-15 — an unknown type: only the creator
- **Rules:** `notify_invoice_action` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `order = SimpleNamespace(created_by=UC.id)`.

**When**
- `ans.notify_invoice_action(db, workspace_id=W1.id, entity_type="project_component", entity_id=3, actor_user_id=UA.id, invoice_id=77, action="confirmed", order=order)`.

**Then**
1. count: `recips() == [UC.id]`.
2. re-read note of UC: `preview == "confirmed|Invoice confirmed on project component #3 — order locked"`.

### APN-IA-16 — a sales order's creator is notified
- **Rules:** `notify_invoice_action` R4, R7a (the part that holds today and after BUG-1205)
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order S = so("SO-1") (created by UC).
2. Approver = soa(S, UB, 9).

**When**
- `ans.notify_invoice_action(db, workspace_id=W1.id, entity_type="sales_order", entity_id=S.id, actor_user_id=UA.id, invoice_id=77, action="draft", order=S)`.

**Then**
1. count: `len(to(UC)) == 1`.
2. re-read note of UC: `notification_type == "invoice_action"`, `source_type == "invoice"`, `source_id == 77`, `entity_type == "sales_order"`.

### APN-IA-17 — a sales order's approvers are notified too
- **Rules:** `notify_invoice_action` R7a [BUG-1205]
- **Kind:** bug
- **Expect:** xfail BUG-1205
- **Fails today on:** Then 1 (today only UC is notified)

**Given**
1. Order S = so("SO-1") (created by UC).
2. Approver = soa(S, UB, 9).
3. Approver = soa(S, UD, 10), but approved.

**When**
- `ans.notify_invoice_action(db, workspace_id=W1.id, entity_type="sales_order", entity_id=S.id, actor_user_id=UA.id, invoice_id=77, action="draft", order=S)`.

**Then**
1. count: `recips() == sorted([UB.id, UC.id, UD.id])`.

### APN-IA-18 — writes but never commits or rolls back
- **Rules:** `notify_invoice_action` R5 (no commit; spec Overview)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. `order = SimpleNamespace(created_by=UC.id)`.
2. The commit point.

**When**
- under **spies**: `ans.notify_invoice_action(db, workspace_id=W1.id, entity_type="project_component", entity_id=3, actor_user_id=UA.id, invoice_id=77, action="draft", order=order)`.

**Then**
1. mock called: `cm.call_count == 0`.
2. mock called: `rb.call_count == 0`.
3. committed: `len(notes()) == 0`.

### APN-IA-19 — transfer order: with requirement 2, an approver who approved is included
- **Rules:** `notify_invoice_action` R3, R2, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order O = to("TO-1"), but `required_approvals 2` (created by UC).
2. Approver = toa(O, UB, 9), but approved.
3. Approver = toa(O, US, 10), but approved.
4. Approver = W2 toa(O, UD, 11), but approved.

**When**
- `ans.notify_invoice_action(db, workspace_id=W1.id, entity_type="transfer_order", entity_id=O.id, actor_user_id=UA.id, invoice_id=77, action="confirmed", order=O)`.

**Then**
1. count: `recips() == sorted([UB.id, UC.id])`.
2. re-read note of UB: `notification_type == "invoice_action"`, `entity_type == "transfer_order"`, `entity_id == O.id`, `source_id == 77`.
3. re-read note of UB: `preview == f"confirmed|Invoice confirmed on TO-{O.id} — order locked"`.
4. count: `len(to(US)) == 0`.
5. count: `len(to(UD)) == 0`.

### APN-IA-20 — expense order: with requirement 2, an approver who approved is included
- **Rules:** `notify_invoice_action` R3, R2, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order O = eo("EXP-1"), but `required_approvals 2` (created by UC).
2. Approver = eoa(O, UB, 9), but approved.
3. Approver = eoa(O, US, 10), but approved.
4. Approver = W2 eoa(O, UD, 11), but approved.

**When**
- `ans.notify_invoice_action(db, workspace_id=W1.id, entity_type="expense_order", entity_id=O.id, actor_user_id=UA.id, invoice_id=77, action="confirmed", order=O)`.

**Then**
1. count: `recips() == sorted([UB.id, UC.id])`.
2. re-read note of UB: `notification_type == "invoice_action"`, `entity_type == "expense_order"`, `entity_id == O.id`, `source_id == 77`.
3. re-read note of UB: `preview == f"confirmed|Invoice confirmed on EXP-{O.id} — order locked"`.
4. count: `len(to(US)) == 0`.
5. count: `len(to(UD)) == 0`.

### APN-IA-21 — work order: with requirement 2, an approver who approved is included
- **Rules:** `notify_invoice_action` R3, R2, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order O = wo("WO-1"), but `required_approvals 2` (created by UC).
2. Approver = woa(O, UB, 9), but approved.
3. Approver = woa(O, US, 10), but approved.
4. Approver = W2 woa(O, UD, 11), but approved.

**When**
- `ans.notify_invoice_action(db, workspace_id=W1.id, entity_type="work_order", entity_id=O.id, actor_user_id=UA.id, invoice_id=77, action="confirmed", order=O)`.

**Then**
1. count: `recips() == sorted([UB.id, UC.id])`.
2. re-read note of UB: `notification_type == "invoice_action"`, `entity_type == "work_order"`, `entity_id == O.id`, `source_id == 77`.
3. re-read note of UB: `preview == f"confirmed|Invoice confirmed on WO-{O.id} — order locked"`.
4. count: `len(to(US)) == 0`.
5. count: `len(to(UD)) == 0`.

## `handle_add_approver`

### APN-AD-01 — ready order: new approver assigned, other pending approvers reminded, actor left out
- **Rules:** `handle_add_approver` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order P = ready po("PO-1") (created by UC).
2. Approver = poa(P, UD, 9).
3. Approver = poa(P, UB, 10), but approved.
4. Approver = poa(P, UA, 11).
5. Approver R = poa(P, UC, 12).

**When**
- `result = ans.handle_add_approver(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id, approver_user_id=UC.id, approver_record_id=R.id, order=P)`.

**Then**
1. returns: `result is None`.
2. count: `recips() == sorted([UC.id, UD.id])`.
3. count: `len(to(UA)) == 0`.
4. count: `[n.notification_type for n in to(UC)] == ["approval_assigned"]`.
5. re-read note of UC: `preview == "Assigned by Ann · ready for your approval · 1 of 4 approval(s) collected"`, `source_type == "approver"`, `source_id == R.id`.
6. re-read note of UD: `notification_type == "approval_pending"`, `source_type == "order"`, `source_id == P.id`, `preview == "1 of 4 approval(s) collected"`, `actor_user_id == UA.id`.

### APN-AD-02 — ready expense order: same split
- **Rules:** `handle_add_approver` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order E = eo("EXP-1") (created by UC).
2. Line = eo line(E).
3. Approver = eoa(E, UB, 9).
4. Approver R = eoa(E, UD, 10).

**When**
- `ans.handle_add_approver(db, workspace_id=W1.id, entity_type="expense_order", entity_id=E.id, actor_user_id=UA.id, approver_user_id=UD.id, approver_record_id=R.id, order=E)`.

**Then**
1. count: `recips() == sorted([UB.id, UD.id])`.
2. count: `len(to(UC)) == 0`.
3. re-read note of UD: `notification_type == "approval_assigned"`, `preview == "Assigned by Ann · ready for your approval · 0 of 2 approval(s) collected"`.
4. re-read note of UB: `notification_type == "approval_pending"`, `preview == "0 of 2 approval(s) collected"`.

### APN-AD-03 — not ready: new approver assigned, creator asked to confirm, nobody reminded
- **Rules:** `handle_add_approver` R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order P = po("PO-1") (created by UC; no section confirmed).
2. Approver = poa(P, UD, 9).
3. Approver R = poa(P, UB, 10).

**When**
- `ans.handle_add_approver(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id, approver_user_id=UB.id, approver_record_id=R.id, order=P)`.

**Then**
1. count: `recips() == sorted([UB.id, UC.id])`.
2. count: `len(to(UD)) == 0`.
3. re-read note of UB: `notification_type == "approval_assigned"`, `preview == f"Assigned by Ann on PO-{P.id}"`.
4. re-read note of UC: `notification_type == "section_confirm"`, `source_type == "section"`, `source_id == P.id`, `actor_user_id == UA.id`.
5. re-read note of UC: `preview == "Confirm Supplier, Order details, Order items before approvals can proceed"`.

### APN-AD-04 — not ready, creator is the actor, new approver suspended
- **Rules:** `handle_add_approver` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Order P = po("PO-1"), but `supplier_confirmed True` (created by UC).
2. Approver R = poa(P, US, 9).

**When**
- `ans.handle_add_approver(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UC.id, approver_user_id=US.id, approver_record_id=R.id, order=P)`.

**Then**
1. count: `recips() == [UC.id]`.
2. re-read note of UC: `notification_type == "section_confirm"`, `actor_user_id == UC.id`, `preview == "Confirm Order details, Order items before approvals can proceed"`.

### APN-AD-05 — writes but never commits or rolls back
- **Rules:** `handle_add_approver` R1 (no commit; spec Overview)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Order P = po("PO-1") (created by UC).
2. Approver R = poa(P, UB, 9).
3. The commit point.

**When**
- under **spies**: `ans.handle_add_approver(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id, approver_user_id=UB.id, approver_record_id=R.id, order=P)`.

**Then**
1. mock called: `cm.call_count == 0`.
2. mock called: `rb.call_count == 0`.
3. committed: `len(notes()) == 0`.

## `handle_order_update_notifications`

### APN-OU-01 — unconfirmed sections with approvers: the creator gets the reset text, nothing else
- **Rules:** `handle_order_update_notifications` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order P = ready po("PO-1") (created by UC).
2. Approver = poa(P, UB, 9).
3. Approver = poa(P, UD, 10).

**When**
- `result = ans.handle_order_update_notifications(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id, order=P, was_ready=False, section_was_unconfirmed=True)`.

**Then**
1. returns: `result is None`.
2. count: `recips() == [UC.id]`.
3. re-read note of UC: `notification_type == "section_confirm"`, `source_type == "section"`, `source_id == P.id`, `actor_user_id == UA.id`.
4. re-read note of UC: `preview == "Approvals were reset — re-confirm sections before approving"`.

### APN-OU-02 — unconfirmed sections with no approvers required: nothing
- **Rules:** `handle_order_update_notifications` R1, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order P = po("PO-1"), but `required_approvals 0` (created by UC).
2. Approver = poa(P, UB, 9).

**When**
- `result = ans.handle_order_update_notifications(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id, order=P, was_ready=False, section_was_unconfirmed=True)`.

**Then**
1. returns: `result is None`.
2. nothing written.

### APN-OU-03 — ready to not ready: the creator gets the gap text
- **Rules:** `handle_order_update_notifications` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order P = po("PO-1"), but `supplier_confirmed True` (created by UC).
2. Approver = poa(P, UB, 9).
3. Approver = poa(P, UD, 10).

**When**
- `ans.handle_order_update_notifications(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id, order=P, was_ready=True)`.

**Then**
1. count: `recips() == [UC.id]`.
2. re-read note of UC: `notification_type == "section_confirm"`, `actor_user_id == UA.id`, `preview == "Confirm Order details, Order items before approvals can proceed"`.

### APN-OU-04 — ready to not ready with no approvers required: nothing
- **Rules:** `handle_order_update_notifications` R2, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order P = po("PO-1"), but `required_approvals 0` (created by UC).
2. Approver = poa(P, UB, 9).

**When**
- `ans.handle_order_update_notifications(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id, order=P, was_ready=True)`.

**Then**
1. nothing written.

### APN-OU-05 — ready to not ready: a suspended creator gets nothing
- **Rules:** `handle_order_update_notifications` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Order P = po("PO-1"), but `created_by US.id`.
2. Approver = poa(P, UB, 9).

**When**
- `ans.handle_order_update_notifications(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id, order=P, was_ready=True)`.

**Then**
1. nothing written.

### APN-OU-06 — not ready to ready: every pending approver, the actor included
- **Rules:** `handle_order_update_notifications` R3, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order P = ready po("PO-1") (created by UC).
2. Approver = poa(P, UB, 9).
3. Approver = poa(P, UD, 10).

**When**
- `ans.handle_order_update_notifications(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UB.id, order=P, was_ready=False)`.

**Then**
1. count: `recips() == sorted([UB.id, UD.id])`.
2. count: `len(to(UC)) == 0`.
3. re-read note of UB: `notification_type == "approval_pending"`, `actor_user_id == UB.id`, `preview == "0 of 2 approval(s) collected"`.
4. re-read note of UD: `notification_type == "approval_pending"`, `source_type == "order"`, `source_id == P.id`.

### APN-OU-07 — not ready to ready: inactive and other-workspace approvers get nothing
- **Rules:** `handle_order_update_notifications` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Order P = ready po("PO-1") (created by UC).
2. Approver = poa(P, UZ0, 8).
3. Approver = poa(P, US, 9).
4. Approver = poa(P, UB, 10).
5. Approver = poa(P, UZ2, 11).

**When**
- `ans.handle_order_update_notifications(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id, order=P, was_ready=False)`.

**Then**
1. count: `recips() == [UB.id]`.

### APN-OU-08 — not ready to ready on a transfer order
- **Rules:** `handle_order_update_notifications` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. Order T = to("TO-1") (created by UC).
2. Line = to line(T).
3. Approver = toa(T, UB, 9).

**When**
- `ans.handle_order_update_notifications(db, workspace_id=W1.id, entity_type="transfer_order", entity_id=T.id, actor_user_id=UA.id, order=T, was_ready=False)`.

**Then**
1. count: `recips() == [UB.id]`.
2. re-read note of UB: `notification_type == "approval_pending"`, `entity_type == "transfer_order"`, `preview == "0 of 1 approval(s) collected"`.

### APN-OU-09 — not ready to ready with no approvers required: nothing
- **Rules:** `handle_order_update_notifications` R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order P = ready po("PO-1"), but `required_approvals 0`.
2. Approver = poa(P, UB, 9).

**When**
- `ans.handle_order_update_notifications(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id, order=P, was_ready=False)`.

**Then**
1. nothing written.

### APN-OU-10 — ready stays ready: nothing
- **Rules:** `handle_order_update_notifications` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order P = ready po("PO-1") (created by UC).
2. Approver = poa(P, UB, 9).

**When**
- `ans.handle_order_update_notifications(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id, order=P, was_ready=True)`.

**Then**
1. nothing written.

### APN-OU-11 — not ready stays not ready: nothing
- **Rules:** `handle_order_update_notifications` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Order P = po("PO-1") (created by UC).
2. Approver = poa(P, UB, 9).

**When**
- `ans.handle_order_update_notifications(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id, order=P, was_ready=False)`.

**Then**
1. nothing written.

### APN-OU-12 — an unknown order id raises 404 even when nothing would be sent
- **Rules:** `handle_order_update_notifications` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. Order P = ready po("PO-1") (created by UC).

**When**
- `ans.handle_order_update_notifications(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=MISSING, actor_user_id=UA.id, order=P, was_ready=True)` under `raises: HTTPException`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Purchase order with ID 999999999 not found"`.
3. nothing written.

### APN-OU-13 — writes but never commits or rolls back
- **Rules:** `handle_order_update_notifications` R3 (no commit; spec Overview)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Order P = ready po("PO-1") (created by UC).
2. Approver = poa(P, UB, 9).
3. The commit point.

**When**
- under **spies**: `ans.handle_order_update_notifications(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=P.id, actor_user_id=UA.id, order=P, was_ready=False)`.

**Then**
1. mock called: `cm.call_count == 0`.
2. mock called: `rb.call_count == 0`.
3. committed: `len(notes()) == 0`.

## `detect_section_unconfirmed`

### APN-DS-01 — a confirmed section set to 0 counts
- **Rules:** `detect_section_unconfirmed` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. `order = SimpleNamespace(supplier_confirmed=False, details_confirmed=False, items_confirmed=True, invoice_confirmed=False)`.

**When**
- `result = ans.detect_section_unconfirmed("purchase_order", order, {"items_confirmed": 0})`.

**Then**
1. returns: `result is True`.

### APN-DS-02 — turning off the invoice confirmation counts
- **Rules:** `detect_section_unconfirmed` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. `order = SimpleNamespace(supplier_confirmed=False, details_confirmed=False, items_confirmed=False, invoice_confirmed=True)`.

**When**
- `result = ans.detect_section_unconfirmed("purchase_order", order, {"invoice_confirmed": False})`.

**Then**
1. returns: `result is True`.

### APN-DS-03 — None as the new value counts
- **Rules:** `detect_section_unconfirmed` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `order = SimpleNamespace(supplier_confirmed=True, details_confirmed=False, items_confirmed=False, invoice_confirmed=False)`.

**When**
- `result = ans.detect_section_unconfirmed("purchase_order", order, {"supplier_confirmed": None})`.

**Then**
1. returns: `result is True`.

### APN-DS-04 — an empty string as the new value counts
- **Rules:** `detect_section_unconfirmed` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `order = SimpleNamespace(supplier_confirmed=False, details_confirmed=True, items_confirmed=False, invoice_confirmed=False)`.

**When**
- `result = ans.detect_section_unconfirmed("purchase_order", order, {"details_confirmed": ""})`.

**Then**
1. returns: `result is True`.

### APN-DS-05 — a section already off does not count
- **Rules:** `detect_section_unconfirmed` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `order = SimpleNamespace(supplier_confirmed=True, details_confirmed=True, items_confirmed=True, invoice_confirmed=False)`.

**When**
- `result = ans.detect_section_unconfirmed("purchase_order", order, {"invoice_confirmed": False})`.

**Then**
1. returns: `result is False`.

### APN-DS-06 — a truthy new value does not count
- **Rules:** `detect_section_unconfirmed` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `order = SimpleNamespace(supplier_confirmed=True, details_confirmed=True, items_confirmed=True, invoice_confirmed=True)`.

**When**
- `result = ans.detect_section_unconfirmed("purchase_order", order, {"items_confirmed": True, "supplier_confirmed": 1})`.

**Then**
1. returns: `result is False`.

### APN-DS-07 — keys absent from the update do not count
- **Rules:** `detect_section_unconfirmed` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `order = SimpleNamespace(supplier_confirmed=True, details_confirmed=True, items_confirmed=True, invoice_confirmed=True)`.

**When**
- `result = ans.detect_section_unconfirmed("purchase_order", order, {"notes": ""})`.

**Then**
1. returns: `result is False`.

### APN-DS-08 — any other type is false and the order is not read
- **Rules:** `detect_section_unconfirmed` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = ans.detect_section_unconfirmed("transfer_order", None, {"supplier_confirmed": False})`.

**Then**
1. returns: `result is False`.

### APN-DS-09 — an order without the confirm attribute counts it as off
- **Rules:** `detect_section_unconfirmed` R2a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `order = SimpleNamespace(supplier_confirmed=True, details_confirmed=True, items_confirmed=True)` (no `invoice_confirmed` attribute).

**When**
- `result = ans.detect_section_unconfirmed("purchase_order", order, {"invoice_confirmed": False})`.

**Then**
1. returns: `result is False`.

## Sales readiness (delegation, final)

These cards test the readiness rule and gap text chosen for sales orders under the reviewer's delegation (`_is_approval_ready` R6a, `_section_gap_preview` R6a; owner did not object, 2026-11-10). If that choice is ever revisited, only these cards change. They use a `SimpleNamespace` order, so no sales column name outside the rule is assumed.

### APN-SR-01 — sales order with order info and items confirmed is ready
- **Rules:** `_is_approval_ready` R6a [BUG-1205]
- **Kind:** bug
- **Expect:** xfail BUG-1205
- **Fails today on:** Then 1 (today `False`, by R5)

**Given**
1. `order = SimpleNamespace(order_info_confirmed=True, items_confirmed=True, invoice_confirmed=False)`.

**When**
- `result = ans._is_approval_ready(db, "sales_order", order, W1.id)`.

**Then**
1. returns: `result is True`.

### APN-SR-02 — sales order without items confirmed is not ready
- **Rules:** `_is_approval_ready` R6a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `order = SimpleNamespace(order_info_confirmed=True, items_confirmed=False, invoice_confirmed=True)`.

**When**
- `result = ans._is_approval_ready(db, "sales_order", order, W1.id)`.

**Then**
1. returns: `result is False`.

### APN-SR-03 — sales gap text lists both missing sections
- **Rules:** `_section_gap_preview` R6a [BUG-1205]
- **Kind:** bug
- **Expect:** xfail BUG-1205
- **Fails today on:** Then 1 (today `None`, by R6)

**Given**
1. `order = SimpleNamespace(order_info_confirmed=False, items_confirmed=False, invoice_confirmed=False)`.

**When**
- `result = ans._section_gap_preview(db, "sales_order", order)`.

**Then**
1. returns: `result == "Confirm Order info, Order items before approvals can proceed"`.

### APN-SR-04 — sales gap text lists only the missing one
- **Rules:** `_section_gap_preview` R6a [BUG-1205]
- **Kind:** bug
- **Expect:** xfail BUG-1205
- **Fails today on:** Then 1 (today `None`, by R6)

**Given**
1. `order = SimpleNamespace(order_info_confirmed=True, items_confirmed=False, invoice_confirmed=False)`.

**When**
- `result = ans._section_gap_preview(db, "sales_order", order)`.

**Then**
1. returns: `result == "Confirm Order items before approvals can proceed"`.

### APN-SR-05 — sales order fully confirmed: the invoice is not listed
- **Rules:** `_section_gap_preview` R6a [BUG-1205]
- **Kind:** bug
- **Expect:** xfail BUG-1205
- **Fails today on:** Then 1 (today `None`, by R6)

**Given**
1. `order = SimpleNamespace(order_info_confirmed=True, items_confirmed=True, invoice_confirmed=False)`.

**When**
- `result = ans._section_gap_preview(db, "sales_order", order)`.

**Then**
1. returns: `result == "Complete remaining sections before approvals can proceed"`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Overview / N11 (an error here undoes the order change) | the calling services (`PurchaseOrderService`, `TransferOrderService`, `ExpenseOrderService`, `WorkOrderService`, `AccountInvoiceService`), their TC3 | an exception from these functions rolls back the order change |
| `_notify_user` R1 (`pg_notify` delivered after commit) | `notification_stream.spec.md` (integration) | the stream receives the message after commit |
| BUG-1205 call sites | `SalesService` spec | the sales service calls these functions |
| FU-1 … FU-4 | purchase / transfer services, order schemas, order managers' `add_approver`, `AccountInvoiceService.confirm_invoice` | as the spec's Follow-ups table says |
| `_pending_approver_ids` R1 tie order (lowest id after BUG-1200) | approver DAO specs (`get_by_order`) | ties of `assigned_at` |

## Spec gaps
None. Gaps 1–2 of revision 1 were closed in spec round 2 (Gap log G1, G2).

## Retired IDs
- APN-AN-05 — a NULL profile name cannot be stored (`profiles.name` is NOT NULL), so `_actor_name` R3's NULL arm is unreachable with a real row; the empty-name arm stays in AN-04 (revision 3).

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `format_order_ref` | R1 | APN-FR-01, FR-02, FR-03, FR-04 |
| `format_order_ref` | R2 | APN-FR-05, FR-06, IA-15 |
| `format_order_ref` | R2a [BUG-1205] | APN-FR-07 |
| `_active_member_ids` | R1 | APN-AM-01, AM-02, AM-03 |
| `_notify_user` | R1 | APN-NU-01, NU-02, NU-12 |
| `_notify_user` | R2 | APN-NU-03 … NU-09 |
| `_notify_user` | R3 | APN-NU-11 |
| `_notify_user` | Errors (IntegrityError) | APN-NU-10 |
| `_actor_name` | R1 | APN-AN-01, AS-02 |
| `_actor_name` | R2 | APN-AN-02, AN-03 |
| `_actor_name` | R3 | APN-AN-04, AN-06 (the NULL-name arm cannot be stored: `profiles.name` NOT NULL; AN-05 retired) |
| `_approval_summary` | R1 | APN-SU-01 … SU-06 |
| `_approval_summary` | R2 [BUG-755, BUG-1202, BUG-1203] | APN-SU-07, SU-08, SU-09 (xfail), SU-10 |
| `_approval_summary` | R3 | APN-SU-11 |
| `_approval_summary` | R4 | APN-SU-12 |
| `_approval_summary` | R5 / Errors | APN-SU-13 … SU-17 |
| `_approval_summary` | R6 | APN-SU-18 |
| `_approval_summary` | R6a [BUG-1205] | APN-SU-19, SU-20, SU-21, SU-22 |
| `build_approval_preview` | R1 | APN-BP-01, BP-02, BP-03, BP-04 (BUG-1202) |
| `build_approval_preview` | R2 | APN-BP-05, BP-06 |
| `build_approval_preview` | R3 | APN-BP-07 |
| `_is_approval_ready` | R1 | APN-RD-01 … RD-04 |
| `_is_approval_ready` | R2 | APN-RD-06 … RD-09 |
| `_is_approval_ready` | R3 | APN-RD-10, RD-11, RD-12 |
| `_is_approval_ready` | R4 | APN-RD-13 … RD-19 |
| `_is_approval_ready` | R5 | APN-RD-20 |
| `_is_approval_ready` | R6 | APN-RD-05 |
| `_is_approval_ready` | R6a [BUG-1205, delegation] | APN-SR-01, SR-02 |
| `_is_approval_ready` | R7 | APN-RD-21, RD-22 |
| `_section_gap_preview` | R1 | APN-GP-01, GP-02, GP-03 |
| `_section_gap_preview` | R2 | APN-GP-04 |
| `_section_gap_preview` | R3 | APN-GP-05 … GP-08 |
| `_section_gap_preview` | R4 | APN-GP-09, GP-10, GP-11 |
| `_section_gap_preview` | R5 | APN-GP-12, GP-13, GP-14 |
| `_section_gap_preview` | R6 | APN-GP-15 |
| `_section_gap_preview` | R6a [BUG-1205, delegation] | APN-SR-03, SR-04, SR-05 |
| `_pending_approver_ids` | R1 | APN-PA-01 … PA-05 |
| `_pending_approver_ids` | R2 | APN-PA-06, PA-07 |
| `_pending_approver_ids` | R3 | APN-PA-08 |
| `_pending_approver_ids` | R3a [BUG-1205] | APN-PA-09 |
| `_has_approvers` | R1 | APN-HA-01 … HA-04, HA-05 (BUG-1202) |
| `_has_approvers` | R2 | APN-HA-06 |
| `notify_approval_assigned` | R1 | APN-AS-01, AS-05, AS-06, AS-07, AS-09 |
| `notify_approval_assigned` | R2 | APN-AS-01, AS-02 |
| `notify_approval_assigned` | R3 | APN-AS-03 |
| `notify_approval_assigned` | R4 | APN-AS-01 |
| `notify_approval_assigned` | R5 | APN-AS-04 |
| `notify_approval_assigned` | R6 | APN-AS-08 |
| `notify_approval_pending_for_order` | R1 | APN-PE-01, PE-10 |
| `notify_approval_pending_for_order` | R2 | APN-PE-01, PE-04 … PE-07, PE-09, PE-11 |
| `notify_approval_pending_for_order` | R3 | APN-PE-02, PE-03 |
| `notify_approval_pending_for_order` | R4 | APN-PE-01, PE-08 |
| `notify_section_confirm_needed` | R1 | APN-SC-05, SC-06 |
| `notify_section_confirm_needed` | R2 | APN-SC-01, SC-08, SC-09, SC-10, SC-11 |
| `notify_section_confirm_needed` | R3 | APN-SC-01 … SC-04 |
| `notify_section_confirm_needed` | R4 | APN-SC-07 |
| `notify_invoice_action` | R1 | APN-IA-01 … IA-04 |
| `notify_invoice_action` | R2 | APN-IA-01, IA-07, IA-11 |
| `notify_invoice_action` | R3 | APN-IA-01, IA-05, IA-06, IA-11, IA-19, IA-20, IA-21 |
| `notify_invoice_action` | R4 | APN-IA-01, IA-07, IA-12, IA-13, IA-16 |
| `notify_invoice_action` | R5 | APN-IA-01, IA-08, IA-09, IA-10, IA-13, IA-18 |
| `notify_invoice_action` | R6 | APN-IA-14 |
| `notify_invoice_action` | R7 | APN-IA-03, IA-15 |
| `notify_invoice_action` | R7a [BUG-1205] | APN-IA-16 (pass part), IA-17 |
| `handle_add_approver` | R1 | APN-AD-01 … AD-05 |
| `handle_add_approver` | R2 | APN-AD-01, AD-02 |
| `handle_add_approver` | R3 | APN-AD-03, AD-04 |
| `handle_order_update_notifications` | R1 | APN-OU-01, OU-02 |
| `handle_order_update_notifications` | R2 | APN-OU-03, OU-04, OU-05 |
| `handle_order_update_notifications` | R3 | APN-OU-06, OU-07, OU-08, OU-09, OU-13 |
| `handle_order_update_notifications` | R4 | APN-OU-02, OU-04, OU-09, OU-10, OU-11 |
| `handle_order_update_notifications` | R5 | APN-OU-12 |
| `detect_section_unconfirmed` | R1 | APN-DS-01 … DS-04 |
| `detect_section_unconfirmed` | R2 | APN-DS-05, DS-06, DS-07 |
| `detect_section_unconfirmed` | R2a | APN-DS-09 |
| `detect_section_unconfirmed` | R3 | APN-DS-08 |
