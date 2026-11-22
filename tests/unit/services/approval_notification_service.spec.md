# Spec — `app/services/approval_notification_service.py`

> **Status:** APPROVED (2026-11-10; no new questions — notification "who / when / what text" points routed to `docs/future/notifications.md`, one precedent bug (BUG-1205) applied)
> **Source commit:** e48a092

> **Review round 2026-11-10 (low supervision).** No owner answer in this round. Following the sweep's routing: questions about *who* is notified, *when* and *with what text* are not asked here; today's behaviour is described exactly and each point is listed in `docs/future/notifications.md` under "Added during the sweep". No visibility, money, stock, security or project-cost question came up. **Precedent:** sales orders are not handled (BUG-1205, owner 2026-11-01) — applied to the rules, no new ID. No new bug.
>
> **Review round 2026-11-10 (3), verifier gap.** `detect_section_unconfirmed` R2a added: a missing confirm attribute counts as unconfirmed (decided by Claude under the reviewer's delegation (2026-11-10); today's behaviour, no bug). Status stays APPROVED.
>
> **Review round 2026-11-10 (2), owner and gaps.** Owner did not object to the sales "ready" choice (ready = `order_info_confirmed` and `items_confirmed`; gap text "Confirm Order info, Order items …"): no longer *proposed*, still decided under the reviewer's delegation. Case designer gaps G1–G2 closed (see Gap log). Status stays APPROVED.
>
> **Base behaviour referenced, not restated:** `NotificationDAO.create` (`tests/unit/dao/notification.spec.md` R1–R4: one flushed row + `pg_notify`); `WorkspaceMemberDAO.get_workspace_members` (`tests/unit/dao/workspace_member.spec.md`); the four approver DAOs' `get_by_order` (`tests/unit/dao/{purchase,transfer,expense,work}_order_approver.spec.md` R1–R9: rows of that order and workspace, `assigned_at` ascending, ties by lowest `id` after BUG-1200, no cap); `ExpenseOrderManager.is_approvable` / `approvability_gap_reason` / `approval_summary` (`tests/unit/managers/expense_order_manager.spec.md`). Purchase, transfer and work order managers have no spec yet; the parts used here are stated as outcomes below.
>
> **Verified by running** (my own `test_v1_an.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\lowsup\an\`, run with the unit `db` fixture on `marker_test`, rolled back, private `COVERAGE_FILE`; output `v1.out`): `format_order_ref` for PO / sales / unknown; `_actor_name` for `None`, empty name, unknown id, named profile; summary and preview of a PO with no approvers (`(0, 0, True)`, "Ready for review") and with 1 approved of 3 ("1 of 3 approval(s) collected", pending in assignment order); a `sales_order` everywhere (0/0/met, not ready, gap `None`, pending `[]`); another workspace's PO (`HTTPException` 404 "Purchase order with ID … not found"); PO gap text; a transfer order with source = destination and no items ("Add at least one item…"); an expense order whose only line has a blank description (not ready, generic fallback text); `handle_add_approver` on a not-ready PO (inactive new approver skipped, creator told even though they are the actor) and on a ready PO with self-assignment (self notified); `notify_invoice_action` with an unknown action (confirmed text; creator, pending and approved approvers; inactive skipped) and with `required_approvals = 0` (approved approver left out); `required_approvals = -1` ("Ready for review", `_has_approvers` False); "became ready" (actor who is a pending approver notified); empty `reason` (falls back to gap text); `detect_section_unconfirmed` cases. **Read, not run:** the five calling services. **Not run:** anything over HTTP, the live stream.

## Review
> No new questions. Applied 2026-11-10.

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | Sales orders: nobody is notified (no `sales_order` branch anywhere in this module) | bug — BUG-1205 (existing) | precedent (owner 2026-11-01) |
| N1–N12 | Who / when / what text (self-notification, previews, wrong gap texts, repeated "pending" notices, notices on closed orders, notices inside the order's transaction) | described as today; routed to `docs/future/notifications.md` | sweep routing (no OQ) |

### House-rule violations — applied automatically
None.

Checked and **not** violated: **HR-1/2/3** — no names stored or compared. **HR-4** — no soft-delete column is read (orders have none except work orders' `is_deleted`, which the order managers' `get_*` do not filter; a deleted work order is still found — inherited raw `get_by_id_and_workspace`, HR-4 scope; flagged on the work order manager, not here). **HR-5/6/7/8** — no list is returned; the order in which recipients get rows is not observable to anyone (one row each). **HR-9** — no audit stamp. **HR-10** — this module checks nothing and then changes nothing; a race between two order updates that both see "became ready" would notify twice, and that check-then-act lives in the order services (Follow-up FU-1). **HR-11–14** — no external system or batch. **HR-15** — no money. **HR-16** — every read is scoped by the caller's `workspace_id` (order: 404 for another workspace's id, verified; approvers: their own `workspace_id`); recipients must be active members of that workspace; the actor's name is read from the global `profiles` table, and the actor is always the caller.

**Permission checks:** none. Callers are order services that already checked the caller.

### Precedent matches — confirm all with ok

### P1. Sales orders get no approval notification — 🐞 BUG-1205 (existing, owner 2026-11-01)
**Background:** This module has a branch for purchase, transfer, expense and work orders only. BUG-1205 (owner) decided sales orders are notified like the other four (`tests/unit/dao/sales_order_approver.spec.md` Q2, FU-3).
**What happens today:** for `entity_type = "sales_order"` the reference is `sales order #5`, the summary is 0 of 0 met ("Ready for review"), the order is never ready, the gap text is empty (`None`), and the pending list is `[]` (verified). `SalesService` calls none of these functions.
**Example:** Rahim is added as approver on sales order 5. Nothing reaches his bell.
**Rules affected:** `format_order_ref` R2a, `_approval_summary` R6a, `_is_approval_ready` R6a, `_section_gap_preview` R6a, `_pending_approver_ids` R3a, `notify_invoice_action` R7a.
**Answer:** bug — per BUG-1205 precedent: `sales_order` handled like the other four (precedent — confirm)
**Resolution:** existing BUG-1205; no new ID. Readiness and gap text for sales orders are not named by FU-3; chosen here by analogy with purchase orders, decided by Claude under the reviewer's delegation (2026-11-10); owner did not object, 2026-11-10: ready = `order_info_confirmed` and `items_confirmed` both true (invoice confirmation ignored, as for purchase orders); gap text "Confirm Order info, Order items before approvals can proceed" listing only the missing ones. The `SalesService` call sites belong to the sales service spec.

### Routed to `docs/future/notifications.md` (no question here; rules describe today)
- **N1** Self-assignment notifies the approver who assigned themself (`notify_approval_assigned` R5). Already an open question there; restated with the verified example.
- **N2** The actor is never left out: the creator is told to confirm sections even when they made the change (`notify_section_confirm_needed` R4); a pending approver who made the edit gets "approval pending" (`handle_order_update_notifications` R4); the actor gets their own invoice notice (`notify_invoice_action` R5).
- **N3** References use the database id (`PO-296011`), not the business number (`format_order_ref` R1). Already open there.
- **N4** Transfer order with source = destination: the text says "Add at least one item…" even when it has items (`_section_gap_preview` R5).
- **N5** Expense order not ready because a line has a blank description or quantity ≤ 0: the text is the generic "Complete remaining details before approvals can proceed" (`_section_gap_preview` R3).
- **N6** Every time an approver is added to a ready order, all other pending approvers get another "approval pending" (`handle_add_approver` R2).
- **N7** Every approver added to a not-ready order sends the creator another "confirm sections" (`handle_add_approver` R3).
- **N8** "Invoice confirmed on PO-… — order locked" is the text for expense and work orders too, and for any action other than `"draft"` (`notify_invoice_action` R1).
- **N9** With `required_approvals = 0` (or negative) the approvers who already approved are not told about the invoice; with a positive requirement they are (`notify_invoice_action` R3).
- **N10** Orders already completed or voided are not looked at: adding an approver to one still sends "ready for your approval" (`_is_approval_ready` R7).
- **N11** Notifications are written inside the order's transaction: any failure here (e.g. 404 from the summary) undoes the order change (Overview, TC3 of the caller).
- **N12** After BUG-755 / BUG-1202 / BUG-1203 an order with no approvers and no explicit requirement shows "0 of 1 approval(s) collected" and counts as "has approvers" here, though no one can receive the notice (`build_approval_preview` R1, `_has_approvers` R1).

## Follow-ups for other reviews
> Nothing below is a rule of this module and no bug is logged for it here.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Purchase / transfer order services** (`update_purchase_order`, `update_transfer_order`, `add_item`; not yet specified) | `was_ready` is read before the update without a row lock; two concurrent edits that both make the order ready each send "approval pending" (HR-10, duplicate side effects). Decide with the services. | `handle_order_update_notifications` |
| FU-2 | **Order schemas** (`required_approvals: int | None` in purchase, transfer, expense, work, sales schemas) | No lower bound: `-1` is accepted and makes the order "Ready for review" with no approver notified (verified here at summary level). Order workflow — the owner's area; ask with the order schema specs. | `build_approval_preview` R1 |
| FU-3 | **Order managers `add_approver`** (purchase seen at `purchase_order_manager.py:1510-1538`) | Approvers can be added to a completed / voided order (only membership and duplicates are checked); this module then notifies "ready for your approval". | N10 |
| FU-4 | **`AccountInvoiceService.confirm_invoice`** (lines 472-487) | The expense order linked to an invoice is found with `get_by_workspace(..., invoice_id=…, limit=1)`; which order is notified when two share an invoice follows that DAO's order. | reading the callers |

## Overview
A module of plain functions (no class, no `BaseService`) that writes approval-related notifications for purchase (`PO`), transfer (`TO`), expense (`EXP`) and work (`WO`) orders: "you were assigned as approver" (`approval_assigned`), "an order is waiting for your approval" (`approval_pending`), "confirm the order's sections" (`section_confirm`, to the order's creator) and "the invoice was drafted / confirmed" (`invoice_action`). Callers: `PurchaseOrderService`, `TransferOrderService`, `ExpenseOrderService`, `WorkOrderService`, `AccountInvoiceService` (each inside its own `try` before `_commit_transaction`). Every notification goes only to an **active** member of the given workspace; each is one `notifications` row written by `NotificationDAO.create` (flushed, `pg_notify` sent, not committed). Nothing here commits, rolls back or changes any order.

**Transaction:** not a `BaseService`; TC1–TC6 (`tests/unit/services/base_service.spec.md`) do not apply to these functions. They apply to the calling services: an exception raised here (the 404 of `_approval_summary` R5, an `IntegrityError` from `NotificationDAO.create` R4) reaches the caller, which rolls back the whole order change (caller's TC3).

**Callables:** 17 specified · 1 not specified (plus the `ORDER_PREFIX` constant)
**Externals to mock:** none (no clock is read here; `pg_notify` runs in the database).
**Integration-only behavior:** delivery of the `pg_notify` message to a live stream after commit (`notification_stream.spec.md`).

**Facts for the test designer**
- Import: `from app.services import approval_notification_service as ans`; functions are module attributes (`ans.handle_add_approver`, `ans._section_gap_preview`, …). The private helpers are tested directly.
- Constants (`app/core/notification_types.py`): `approval_assigned`, `approval_pending`, `section_confirm`, `invoice_action`; sources `approver`, `order`, `section`, `invoice`.
- `SECTION_CONFIRM_FIELDS` (`app/managers/purchase_order_manager.py`), in this order: `supplier_confirmed` → label "Supplier", `details_confirmed` → "Order details", `items_confirmed` → "Order items", `invoice_confirmed` → "Draft invoice".
- `created_by` is NOT NULL on purchase, transfer and expense orders; nullable on work orders. `order` may be any object: functions read attributes with `getattr(..., default)`; a `SimpleNamespace` works where no DB lookup on the order object is made (gap texts for PO / WO, `detect_section_unconfirmed`).
- Readable notification fields: `recipient_user_id`, `actor_user_id`, `notification_type`, `entity_type`, `entity_id`, `source_type`, `source_id`, `preview`.

**Notes for the test designer**
- Orders with dangling FKs (`current_status_id`, `destination_id`, `factory_id`, …) need `SET LOCAL session_replication_role = replica` for the **whole test** (any later flush of the order re-checks FKs), as in `tests/unit/dao/test_purchase_order_approver.py`.
- Recipient sets are unordered (R of `notify_invoice_action`): compare as sets / sorted.
- A member row needs `role` (any string) and `status` (`"active"` to receive).

## Not specified
- `approval_notification_service` (module-level dict, lines 466-474) — a name → function map; no code imports it (callers import the functions). No logic.
- `ORDER_PREFIX` constant — covered by `format_order_ref`.

---

## `format_order_ref(entity_type, entity_id)`
**Shape:** mapper · **Persistence:** pure · **Visibility:** public (used by: `notify_approval_assigned`, `notify_invoice_action`)

**Purpose:** Short reference to an order for notification text.

**Returns:** `str`.

**Rules:**
- **R1.** `purchase_order` → `"PO-<id>"`, `transfer_order` → `"TO-<id>"`, `expense_order` → `"EXP-<id>"`, `work_order` → `"WO-<id>"`; `<id>` is the database id given, not the order's number (`format_order_ref("purchase_order", 12)` → `"PO-12"`).
- **R2.** Any other type → the type with underscores replaced by spaces, then ` #<id>`: `("x", 1)` → `"x #1"`, `("project_component", 3)` → `"project component #3"`.
- **R2a.** [BUG-1205] `sales_order` → `"SO-<id>"`. *(Today: `"sales order #5"`, by R2.)*

**Errors:** none. **Side effects:** none.

---

## `_active_member_ids(db, workspace_id)`
**Shape:** helper · **Persistence:** reads · **Visibility:** internal (used by: `_notify_user`)

**Purpose:** Who may receive a notification in this workspace.

**Returns:** `set[int]` of `user_id`s.

**Rules:**
- **R1.** The user ids of every member row of that workspace with `status = "active"`, all of them (no cap). Members with any other status (`inactive`, `suspended`, `invited`) and members of other workspaces are not in the set. An unknown workspace gives an empty set.

**Errors:** none. **Side effects:** none.

---

## `_notify_user(db, *, workspace_id, recipient_user_id, actor_user_id, notification_type, entity_type, entity_id, source_type, source_id, preview=None)`
**Shape:** create · **Persistence:** writes · **Visibility:** internal (used by: all four `notify_*` functions)

**Purpose:** Write one notification, only to an active member.

**Returns:** `None`.

**Rules:**
- **R1.** When `recipient_user_id` is an active member of `workspace_id` (`_active_member_ids` R1), one notification row is written with exactly the given values (as `NotificationDAO.create` R1–R2: flushed, `is_read = False`, `pg_notify` sent).
- **R2.** Otherwise nothing is written and no error is raised: not a member, an inactive member, a member of another workspace only, or an unknown id.
- **R3.** The recipient may be the actor; that is not checked.

**Errors:** those of `NotificationDAO.create` R4 (unknown `actor_user_id` → `IntegrityError`). **Side effects:** R1.

---

## `_actor_name(db, user_id)`
**Shape:** helper · **Persistence:** reads · **Visibility:** internal (used by: `notify_approval_assigned`)

**Rules:**
- **R1.** `None` → `"Someone"`.
- **R2.** A profile with a non-empty `name` → that name as stored (not trimmed; any workspace).
- **R3.** A profile whose `name` is `""` or `NULL`, or no profile with that id → `"User <id>"` (verified: empty name and unknown id).

**Errors:** none. **Side effects:** none.

---

## `_approval_summary(db, entity_type, entity_id, workspace_id)`
**Shape:** compute · **Persistence:** reads · **Visibility:** internal (used by: `build_approval_preview`, `_has_approvers`, `notify_invoice_action`)

**Purpose:** `(approved_count, required, met)` for an order.

**Returns:** a 3-tuple `(int, int, bool)`.

**Rules:**
- **R1.** For the four order types the order is looked up by id **in that workspace**, and the result is the order manager's `approval_summary`: `approved_count` = approver rows of the order with `approved = True`; `required` = the order's `required_approvals` when not `NULL` (any integer, `0` and negatives included); otherwise the number of approver rows; `met` = `approved_count >= required`. Example: 3 approvers, one approved, `required_approvals` NULL → `(1, 3, False)` (verified).
- **R2.** With `required_approvals` NULL and no approver rows: [BUG-755 (expense), BUG-1202 (purchase), BUG-1203 (transfer)] `required = 1`, `met = False` → `(0, 1, False)`. *(Today: `(0, 0, True)`, verified for a purchase order.)* A **work order** that never had an approver stays `(0, 0, True)` (BUG-1204 covers only a work order that lost its last approver; its rule lives in the work order manager).
- **R3.** Approver rows of another workspace on the same order id are not counted (approver DAOs `get_by_order` R2).
- **R4.** `approved_count` may exceed `required` (e.g. `required_approvals = 1`, two approved → `(2, 1, True)`).
- **R5.** An order id that does not exist, or exists in another workspace, raises `HTTPException` 404 with detail `"Purchase order with ID <id> not found"` / `"Transfer order with ID <id> not found"` / `"Expense order with ID <id> not found"` / `"Work order with ID <id> not found"` (verified for purchase).
- **R6.** Any other `entity_type` → `(0, 0, True)` with no lookup and no error.
- **R6a.** [BUG-1205] `sales_order` → the sales manager's `approval_summary` for that order of the workspace (BUG-736: no approvers and no requirement → required 1). An unknown id, or an id of another workspace, raises `HTTPException` 404 with detail `"Sales order with ID <id> not found"` — the same text as the other four types (R5) and as `SalesManager`'s own lookups (`get`/`update`/`add_approver`); decided by Claude under the reviewer's delegation (2026-11-10) (gap G1). *(Today: `(0, 0, True)`, by R6.)*

**Errors:** R5. **Side effects:** none.

---

## `build_approval_preview(db, entity_type, entity_id, workspace_id)`
**Shape:** mapper · **Persistence:** reads · **Visibility:** public (used by: `notify_approval_assigned`, `notify_approval_pending_for_order`)

**Returns:** `str`.

**Rules:**
- **R1.** When the summary's `required` is `0` or less → `"Ready for review"` (no approvers and no requirement *today*, `required_approvals = 0`, `required_approvals = -1`, unknown types; verified for 0, -1 and none). After the R2 bugs of `_approval_summary` are fixed, an order with no approvers shows `"0 of 1 approval(s) collected"`.
- **R2.** Otherwise `"<approved_count> of <required> approval(s) collected"`, e.g. `"1 of 3 approval(s) collected"`, `"2 of 1 approval(s) collected"`.
- **R3.** Errors of `_approval_summary` R5 pass through unchanged.

**Side effects:** none.

---

## `_is_approval_ready(db, entity_type, order, workspace_id)`
**Shape:** compute · **Persistence:** reads · **Visibility:** internal (used by: `handle_add_approver`, `handle_order_update_notifications`)

**Purpose:** Whether the order is complete enough for approvers to act.

**Returns:** `bool`.

**Rules:**
- **R1.** Purchase order: true exactly when `supplier_confirmed`, `details_confirmed` and `items_confirmed` are all true; `invoice_confirmed` is ignored.
- **R2.** Expense order: `ExpenseOrderManager.is_approvable` (expense manager spec): category and expense date set; a cost center unless category is `other`; a non-blank description; at least one line of the order in its own workspace; every line with a non-blank description and quantity > 0.
- **R3.** Work order: true exactly when the title is not blank after trimming and `factory_id` is set.
- **R4.** Transfer order: true exactly when all four route fields (`source_location_type`, `source_location_id`, `destination_location_type`, `destination_location_id`) are truthy, source ≠ destination (same type **and** same id counts as the same), and the order has at least one item row in `workspace_id`. A location id of `0` counts as unset.
- **R5.** Any other type → `False`.
- **R6.** The `order` object is read as given (its in-memory values), no lookup by id; for expense and transfer orders the lines/items are read from the database by the order's id.
- **R6a.** [BUG-1205] `sales_order`: true exactly when `order_info_confirmed` and `items_confirmed` are both true; `invoice_confirmed` ignored *(decided by Claude under the reviewer's delegation (2026-11-10); owner did not object, 2026-11-10)*. *(Today: `False`, by R5.)*
- **R7.** Order state is not looked at: a completed, voided or (work order) deleted order is judged by R1–R4 alone.

**Errors:** none. **Side effects:** none.

---

## `_section_gap_preview(db, entity_type, order)`
**Shape:** mapper · **Persistence:** reads · **Visibility:** internal (used by: `notify_section_confirm_needed`)

**Purpose:** Text telling the creator what is missing before approvals can proceed.

**Returns:** `str`, or `None` for unknown types.

**Rules:**
- **R1.** Purchase order: the labels of `supplier_confirmed`, `details_confirmed`, `items_confirmed` that are falsy (a missing attribute counts as falsy), in that order, joined by `", "`: `"Confirm <labels> before approvals can proceed"` — e.g. only supplier confirmed → `"Confirm Order details, Order items before approvals can proceed"` (verified). `invoice_confirmed` is never listed.
- **R2.** Purchase order with all three confirmed → `"Complete remaining sections before approvals can proceed"` (verified).
- **R3.** Expense order: `ExpenseOrderManager.approvability_gap_reason` text when it gives one (category/date, cost center, description, no lines — see expense manager spec); when it gives none → `"Complete remaining details before approvals can proceed"`. That fallback is also what an order gets that is not ready only because a line has a blank description or quantity ≤ 0 (verified). This line-problem fallback is **today's** text: once BUG-758 (expense order manager `approvability_gap_reason` R6) is fixed the manager returns `"Every expense line needs a description and a quantity above 0 before approvals can proceed"` and this module passes it on by the first half of this rule. The pass card for the fallback (APN-GP-08) is kept and tagged **"retire when BUG-758 is fixed"** (decided by Claude under the reviewer's delegation (2026-11-10), gap G2); the first half of R3 already covers the fixed text.
- **R4.** Work order: blank title → `"Work order setup is incomplete"`; else no factory → `"Set a factory before approvals can proceed"`; else `"Complete remaining details before approvals can proceed"`.
- **R5.** Transfer order: when any of the four route fields is falsy → `"Set source and destination before approvals can proceed"`; otherwise always `"Add at least one item before approvals can proceed"` — also when the order has items and the real gap is source = destination, or when it is in fact ready (verified for source = destination).
- **R6.** Any other type → `None`.
- **R6a.** [BUG-1205] `sales_order`: as R1/R2 with the fields `order_info_confirmed` → "Order info", `items_confirmed` → "Order items" *(decided by Claude under the reviewer's delegation (2026-11-10); owner did not object, 2026-11-10)*. *(Today: `None`, by R6.)*

**Errors:** none. **Side effects:** none.

---

## `_pending_approver_ids(db, entity_type, entity_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** internal (used by: `notify_approval_pending_for_order`, `notify_invoice_action`)

**Returns:** `list[int]`.

**Rules:**
- **R1.** For the four order types: the `user_id` of every approver row of that order and workspace with `approved = False`, in the DAO's order (`assigned_at` ascending; ties by lowest `id` after BUG-1200). Membership is not looked at here (filtered later by `_notify_user`). Verified: 3 approvers, middle one approved → the other two, in assignment order.
- **R2.** The order itself is not looked up: an unknown order id or another workspace gives `[]`, no error.
- **R3.** Any other type → `[]`.
- **R3a.** [BUG-1205] `sales_order` → the unapproved approvers of the sales order, as R1. *(Today: `[]`, by R3.)*

**Errors:** none. **Side effects:** none.

---

## `_has_approvers(db, entity_type, entity_id, workspace_id)`
**Shape:** compute · **Persistence:** reads · **Visibility:** internal (used by: `handle_order_update_notifications`)

**Rules:**
- **R1.** True exactly when the summary's `required` is greater than 0 (`_approval_summary`), whatever the number of approver rows: `required_approvals = 2` with no approvers → `True`; `required_approvals = 0` or `-1` with approvers → `False` (verified for -1).
- **R2.** Errors of `_approval_summary` R5 pass through.

---

## `notify_approval_assigned(db, *, workspace_id, entity_type, entity_id, actor_user_id, approver_user_id, approver_record_id, order, ready_for_approval=False)`
**Shape:** event-log · **Persistence:** writes · **Visibility:** public (used by: `handle_add_approver`)

**Purpose:** Tell a new approver they were assigned.

**Rules:**
- **R1.** One notification to `approver_user_id` (if an active member, `_notify_user` R1–R2): type `approval_assigned`, `entity_type` / `entity_id` as given, source `approver` / `approver_record_id`, actor `actor_user_id`.
- **R2.** `ready_for_approval` false (default) → preview `"Assigned by <actor name> on <ref>"`, e.g. `"Assigned by Karim on EXP-485393"` (verified); actor name per `_actor_name`, ref per `format_order_ref`.
- **R3.** `ready_for_approval` true → preview `"Assigned by <actor name> · ready for your approval · <build_approval_preview>"`, e.g. `"Assigned by Rahim · ready for your approval · 1 of 3 approval(s) collected"` (verified). The progress counts the new approver if their row is already flushed.
- **R4.** `order` is not read.
- **R5.** The approver is notified even when they assigned themself (`actor_user_id == approver_user_id`, verified).
- **R6.** With R3, errors of `_approval_summary` R5 pass through and nothing is written.

---

## `notify_approval_pending_for_order(db, *, workspace_id, entity_type, entity_id, actor_user_id, exclude_user_ids=None)`
**Shape:** event-log · **Persistence:** writes · **Visibility:** public (used by: `handle_add_approver`, `handle_order_update_notifications`)

**Purpose:** Tell every approver who has not yet approved that the order waits for them.

**Rules:**
- **R1.** The preview is `build_approval_preview` (computed first: a 404 there is raised even if nobody would be notified).
- **R2.** For each pending approver (`_pending_approver_ids` R1) not in `exclude_user_ids`, one notification (if an active member): type `approval_pending`, source `order` / `entity_id`, actor `actor_user_id` (may be `None`, stored NULL), that preview.
- **R3.** `exclude_user_ids` `None` or empty → nobody excluded; the actor is notified if they are a pending approver (verified).
- **R4.** Approvers who already approved get nothing; no pending approver → nothing written.

---

## `notify_section_confirm_needed(db, *, workspace_id, entity_type, entity_id, actor_user_id, order, reason=None)`
**Shape:** event-log · **Persistence:** writes · **Visibility:** public (used by: `handle_add_approver`, `handle_order_update_notifications`, purchase / expense / work order services)

**Purpose:** Tell the order's creator to complete or re-confirm sections.

**Rules:**
- **R1.** `order.created_by` missing or `None` → nothing written (only possible for work orders, and for objects without the attribute).
- **R2.** Otherwise one notification to `created_by` (if an active member): type `section_confirm`, source `section` / `entity_id`, actor `actor_user_id`.
- **R3.** Preview = `reason` when truthy; when `reason` is `None` or `""` → `_section_gap_preview` (verified for `""`). An unknown type with no reason gives preview `NULL`.
- **R4.** The creator is notified even when they are the actor (verified).

---

## `notify_invoice_action(db, *, workspace_id, entity_type, entity_id, actor_user_id, invoice_id, action, order)`
**Shape:** event-log · **Persistence:** writes · **Visibility:** public (used by: account invoice, purchase, expense and work order services; callers pass `"draft"` or `"confirmed"`)

**Purpose:** Tell the people on an order that its invoice was drafted or confirmed.

**Rules:**
- **R1.** `action == "draft"` → preview `"draft|Linked payable invoice is in draft — confirm when details look correct"`. Any other value (`"confirmed"`, `""`, `"voided"`, …) → `"confirmed|Invoice confirmed on <ref> — order locked"`, with `format_order_ref` (verified with an unknown action). The part before `|` is a title hint the web app splits off.
- **R2.** Recipients are a set (each person at most once): the pending approvers (`_pending_approver_ids` R1) …
- **R3.** … plus, only when the summary's `required` > 0, **every** approver row of the order in that workspace (approved ones too); with `required` ≤ 0 approved approvers are not included (verified with `required_approvals = 0`) …
- **R4.** … plus `order.created_by` when not `None`.
- **R5.** Each recipient who is an active member gets one notification: type `invoice_action`, source `invoice` / `invoice_id`, actor `actor_user_id`, that preview. The actor is not left out (verified: creator = actor notified). Rows are written in no defined order.
- **R6.** Errors of `_approval_summary` R5 pass through; nothing is written then.
- **R7.** Unknown type: no approver recipients; only the creator.
- **R7a.** [BUG-1205] `sales_order` → approvers of the sales order as R2–R3, plus the creator. *(Today: only the creator, by R7; no caller passes `sales_order`.)*

---

## `handle_add_approver(db, *, workspace_id, entity_type, entity_id, actor_user_id, approver_user_id, approver_record_id, order)`
**Shape:** event-log · **Persistence:** writes · **Visibility:** public (used by: `add_approver` of the purchase, transfer, expense and work order services, after the approver row is flushed)

**Rules:**
- **R1.** Readiness is `_is_approval_ready(order)`. The new approver always gets `notify_approval_assigned` with `ready_for_approval` = that readiness (R2 / R3 of it).
- **R2.** Ready → also `notify_approval_pending_for_order` with `exclude_user_ids = {actor, new approver}`: every **other** pending approver gets a fresh `approval_pending`, each time an approver is added. No `section_confirm`.
- **R3.** Not ready → also `notify_section_confirm_needed` with no reason: the creator gets the gap text (verified: creator = actor told; new inactive approver gets nothing). No `approval_pending`.

---

## `handle_order_update_notifications(db, *, workspace_id, entity_type, entity_id, actor_user_id, order, was_ready, section_was_unconfirmed=False)`
**Shape:** event-log · **Persistence:** writes · **Visibility:** public (used by: `update_purchase_order`; `update_transfer_order`, transfer `add_item` — never with `section_was_unconfirmed`)

**Purpose:** After an order edit, notify on readiness changes.

**Rules:** with `now_ready = _is_approval_ready(order)` and `has = _has_approvers`; the first matching rule applies, the rest are skipped:
- **R1.** `section_was_unconfirmed` and `has` → `notify_section_confirm_needed` with reason `"Approvals were reset — re-confirm sections before approving"`.
- **R2.** `was_ready` and not `now_ready` and `has` → `notify_section_confirm_needed` with no reason (gap text).
- **R3.** not `was_ready` and `now_ready` and `has` → `notify_approval_pending_for_order` with nobody excluded.
- **R4.** Otherwise nothing: no approvers required (`has` false — including `section_was_unconfirmed` true), or readiness unchanged (ready → ready, not → not). The actor is not excluded in R3 (verified).
- **R5.** Errors of `_approval_summary` R5 pass through (also when nothing would be sent).

---

## `detect_section_unconfirmed(entity_type, order, update_dict)`
**Shape:** compute · **Persistence:** pure · **Visibility:** public (used by: `update_purchase_order`, with the update's `exclude_unset`, `exclude_none` dump)

**Purpose:** Whether an update turns off a section confirmation that was on.

**Rules:**
- **R1.** Purchase order: true when at least one of `supplier_confirmed`, `details_confirmed`, `items_confirmed`, `invoice_confirmed` is a key of `update_dict` with a falsy value (`False`, `0`, `None`, `""`) while the order's current value is truthy. `invoice_confirmed` counts here, though readiness ignores it.
- **R2.** False when the key is absent, the new value is truthy, or the order's value is already falsy (verified: `invoice_confirmed: False` on an order with it off → false; `items_confirmed: 0` on → true).
- **R2a.** An order object that lacks a confirm attribute is treated as having that section unconfirmed (falsy): sending `False` for it returns false, never raises. Intended (decided by Claude under the reviewer's delegation (2026-11-10)): a section the order type does not track can never be confirmed, so it can never be "un-confirmed". (Verify with a `SimpleNamespace` order missing e.g. `invoice_confirmed`.)
- **R3.** Any other type → false, nothing read.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 31-34 | prefix known / not | `format_order_ref` R1, R2, R2a |
| 38-41 | active status filter | `_active_member_ids` R1 |
| 58-59 | recipient not active member → return | `_notify_user` R1, R2 |
| 75-76 | user_id None | `_actor_name` R1 |
| 78 | profile missing / empty name | `_actor_name` R2, R3 |
| 84-103 | four type branches; manager 404 | `_approval_summary` R1, R5, R6a |
| managers `approval_summary` | `required_approvals` not None / approvers > 0 / else 0 (WO: else len) | `_approval_summary` R1, R2, R4 |
| 104 | unknown type | `_approval_summary` R6 |
| 111-113 | required ≤ 0 | `build_approval_preview` R1, R2 |
| 117-132 | four type branches | `_is_approval_ready` R1–R4, R6, R6a |
| `transfer_order_manager.py` 67-95 | route defined / valid / items | `_is_approval_ready` R4 |
| `expense_order_manager.py` 66-80 | readiness checks | `_is_approval_ready` R2 |
| `work_order_manager.py` 104-105 | title / factory | `_is_approval_ready` R3 |
| 133 | unknown type | `_is_approval_ready` R5 |
| 137-148 | PO loop, skip invoice, gaps empty / not | `_section_gap_preview` R1, R2 |
| 149-152 | EO reason or fallback | `_section_gap_preview` R3 |
| 153-156 | WO reason or fallback (`work_order_manager.py` 107-112) | `_section_gap_preview` R4 |
| 157-162 | TO route defined / not | `_section_gap_preview` R5 |
| (fall-through) | unknown → None | `_section_gap_preview` R6, R6a |
| 166-191 | four type branches / else [] | `_pending_approver_ids` R1–R3a |
| 192 | filter not approved | `_pending_approver_ids` R1 |
| 197 | required > 0 | `_has_approvers` R1 |
| 214-218 | ready_for_approval | `notify_approval_assigned` R2, R3 |
| 242 | exclude None / empty | `notify_approval_pending_for_order` R3 |
| 244-246 | loop; uid excluded → continue | `notify_approval_pending_for_order` R2, R4 |
| 272-273 | created_by None → return | `notify_section_confirm_needed` R1 |
| 274 | reason truthy / falsy | `notify_section_confirm_needed` R3 |
| 301-306 | action == "draft" / else | `notify_invoice_action` R1 |
| 310 | required > 0 | `notify_invoice_action` R3 |
| 311-338 | type branches (none for unknown) | `notify_invoice_action` R3, R7, R7a |
| 341-342 | created_by not None | `notify_invoice_action` R4 |
| 345 | loop over recipients | `notify_invoice_action` R5 |
| 383-400 | ready / not | `handle_add_approver` R2, R3 |
| 417-427 | unconfirmed and has → return | `handle_order_update_notifications` R1 |
| 429-438 | was and not now and has → return | `handle_order_update_notifications` R2 |
| 440-447 | not was and now and has | `handle_order_update_notifications` R3, R4 |
| 451-456 | PO / other type | `detect_section_unconfirmed` R1, R3 |
| 458-462 | key absent → continue; falsy new and truthy old | `detect_section_unconfirmed` R1, R2 |

## Gap log
- G1 (`approval_notification_service.cases.md` gap 1) — fact + delegation — `_approval_summary` R6a: the 404 detail for an unknown or foreign sales order is `"Sales order with ID <id> not found"` (as R5 and `SalesManager`'s lookups).
- G2 (`approval_notification_service.cases.md` gap 2) — contradiction resolved under delegation (2026-11-10) — `_section_gap_preview` R3: the quantity-0 / blank-description fallback is today's text; APN-GP-08 stays a pass card, tagged "retire when BUG-758 is fixed"; after the fix the manager's text arrives through R3's first half.
- G-V1 (verifier gap, round 3) — Intent, decided by Claude under the reviewer's delegation (2026-11-10) — `detect_section_unconfirmed` R2a: a missing confirm attribute on the order counts as unconfirmed, so un-confirming it returns false (today's behaviour).
