# Spec — `app/services/account_invoice_service.py`

> **Status:** APPROVED (2026-11-21, apply-review; OQ-AIS-1 answered by the owner as OQ-60 → BUG-2969; proposed fixes BUG-2966 and BUG-2968 confirmed by Claude under the reviewer's delegation of 2026-11-21)
> **Source commit:** e48a092

> **Fill-gaps 2026-11-21:** 8 gaps from `account_invoice_service.cases.md` closed (see `## Gap log`); all from the code or decided by Claude under the reviewer's delegation (2026-11-21); no new question. Still APPROVED.
>
> **Apply-review 2026-11-21:** OQ-60 applied (BUG-2969, K8, K10); BUG-2962…2968 tagged; BUG-2966 and BUG-2968 no longer `(proposed)`; Q7 and Q8 go to the dead-code checklist. Bug IDs are final; the coordinator logs them in `docs/testing/bugs.md`.
>
> **Review round 2026-11-21 (describe, under the reviewer's delegation of 2026-11-21).** House-rule lines and precedent matches are pre-filled. Every new question that is not a genuinely new money, stock, order-workflow or security question was decided by Claude under the delegation and is marked so; none of them is the owner's own answer. One question is money and order workflow and is not covered by any existing answer: **OQ-AIS-1** (provisional number, to be renumbered when parked in `docs/testing/owner-questions.md`). Bug IDs are provisional, from block BUG-2962 … 2981; nothing is logged in `docs/testing/bugs.md` yet.
>
> **Already decided elsewhere, cited, not asked again:** the completed-order freeze and its placement in the manager (`account_invoice_manager.spec.md` O1, F1–F7; BUG-2730, 2731, 2733, 2735, 2736) and the O1 follow-ups (a)–(e) for this service; credit-note void and its return (BUG-2788, manager `void_invoice` R3c); BUG-2732 (delete unlinks every order type); BUG-2734 (completed / received PO can't be voided — `purchase_order_service`, not here); invoice amount = sum of its items (BUG-627); the manager's row locks (BUG-621); sales orders get approval notifications (BUG-1205); an invoice's expense order found newest-first (expense order DAO R6, BUG-2711; approval notification FU-4); "no approvers" means 1 approval required (BUG-1202); the work order follow-ups (`work_order_manager.spec.md` FU-1: a voided / completed order can get an invoice, voiding an order leaves a hand-confirmed invoice payable) belong to the work order service.
>
> **Production:** not touched by this module. **Projects:** not touched (no project costs are read or written here).
>
> **Verified by running** (my own throwaway pytest file `test_v_ais.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc1desc\account_invoice_service\`, using the unit `db` fixture on `marker_test`, everything rolled back, nothing committed): `sales_manager` has no `get_sales_order` (resync of a sales-order invoice raises `AttributeError: 'SalesManager' object has no attribute 'get_sales_order'`); resync of a work-order draft invoice with one 5,000.00 line leaves 0 lines, `invoice_amount` 0.00, `payment_status` `paid`; confirming a sales order's draft invoice here leaves the sales order's `invoice_confirmed`, `order_info_confirmed`, `items_confirmed` all `False`, and the order's own "Finalize invoice" then answers 400 `Invoice is already confirmed` (sections confirmed) or `Confirm order info and items before finalizing`; deleting a PO's draft invoice logs `invoice_draft_deleted` / `Draft invoice #<id> deleted` with metadata `{"invoice_id": null}`; deleting a sales order's draft invoice leaves the order `is_invoiced = True` (its `invoice_id` is NULL by the database's `ON DELETE SET NULL`); confirming a PO's draft invoice whose PO `total_amount` is 999.00 and whose one invoice line is 400.00 confirms at 400.00, PO events `invoice_created`, `invoice_confirmed` (section flip), `status_updated`, `invoice_confirmed` (`Invoice #<id> confirmed — order locked`); a missing PO stage row makes the whole confirm fail with 422 and nothing saved; voiding a PO's confirmed invoice with no received lines: invoice `voided`, PO `invoice_id` NULL, `supplier_confirmed` / `items_confirmed` False, `details_confirmed` kept, events `invoice_voided` (metadata `invoice_id`, `changes` with the void reason), `supplier_unconfirmed`, `items_unconfirmed`, `status_updated` → `Planning`.

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| H1 | Confirm, void and resync check the order / invoice without locking it | bug — BUG-2962 | house rule HR-10 |
| P1 | Deleting a draft invoice unlinks only purchase orders | bug — BUG-2732 (existing) | owner 2026-11-14 |
| Q1 | "Resync items" on a sales order's invoice always crashes (500) | bug — BUG-2963 | delegation (crash) |
| Q2 | "Resync items" on a work order's invoice deletes its only line: the invoice becomes 0.00 and "paid" | bug — BUG-2964 | delegation (money lost, clear fix) |
| Q3 | Finalizing a sales order's invoice from the invoice page skips the order's checks and leaves the order stuck | bug — BUG-2965 | delegation (sibling path exists) |
| Q4 | Voiding a sales / expense / work order's invoice from the invoice page leaves the order tied to the voided invoice | bug — BUG-2966 | delegation (PO branch is the precedent) |
| Q5 | Voiding a sales order's invoice after goods were delivered is allowed (a PO's is refused) | bug — BUG-2967 | precedent (owner 2026-11-14, BUG-2734 rule) |
| Q6 | The PO's "draft invoice deleted" log entry records no invoice id | bug — BUG-2968 | delegation (audit) |
| Q7 | Confirm sets a PO invoice's amount to the PO total, then the manager replaces it with the item sum | intended (no effect; dead write) | delegation (BUG-627 answer) |
| Q8 | `list_accounts_hub_page` of this service has no caller | remove | delegation (dead code) |
| OQ-AIS-1 | **OWNER** — an expense or work order's invoice can be finalized on the invoice page before the order is approved or completed | bug — BUG-2969 | owner (OQ-60, 2026-11-21) |

### House-rule violations — applied automatically
> Overwrite an answer only if the house rule should NOT apply here.

- **HR-10** `confirm_invoice` K2–K3 (K3a), `void_invoice` X1, `resync_items` S1 — the service itself checks state and then acts, on rows it reads without a lock: confirm reads the PO's section confirms and approvals (an approval can be withdrawn, or a section unconfirmed, between the check and the commit, and the invoice is finalized without them); void reads the PO lines' received quantities (a receipt can land between the check and the commit, leaving goods received on a PO whose invoice is voided — money and stock); resync reads the invoice's status with a plain read (a concurrent confirm can finalize it and then have its lines replaced). The manager's own invoice lock (BUG-621) is taken later, inside the manager call, after these checks. Intended: the purchase order row is read `SELECT … FOR UPDATE` before the confirm / void checks, and resync reads the invoice `FOR UPDATE` before its status check; the loser sees the new state and gets the normal error. 🐞 BUG-2962
**Answer:** bug — per HR-10 (house rule)

Checked and **not** violated: **HR-1/2/3** — no names stored. **HR-4** — no soft-delete column is read here (orders have none except work orders; resync of a soft-deleted work order's invoice is part of BUG-2964's intended rule). **HR-5/6/7/8** — lists are the manager's (`account_invoice_manager.spec.md` shared filters; BUG-622, 623, 637, 638 there). **HR-9** — audit stamps are the manager's (BUG-620, 633). **HR-11–14** — no external system. **HR-15** — `Decimal(str(total))` does no rounding; no money is computed here. **HR-16** — every read is scoped by the caller's workspace: the PO by invoice (another workspace's PO pointing at the invoice is never found), the expense order by invoice, the linked order in resync (another workspace's order → 404).

**Permission checks:** none. Every endpoint only requires a member of the workspace; any member can finalize, void, revert or delete any invoice (noted for `docs/future/permissions.md`, not a question here).

### Precedent matches — confirm all with ok

### P1. Deleting a draft invoice unlinks only purchase orders — 🐞 BUG-2732 (existing, owner 2026-11-14)
**Background:** an order (purchase, sales, expense, work) points at its own invoice through its `invoice_id`, and keeps flags about it (a sales order: `is_invoiced`, `invoice_confirmed`, `paid`; a PO: `invoice_confirmed`, `paid`). When the invoice row is deleted, the database clears the `invoice_id` columns on its own (`ON DELETE SET NULL`), but not the flags.
**What happens today:** only a PO is unlinked properly (flags cleared, an event on the PO). A sales order keeps `is_invoiced = True` with no invoice (verified); expense and work orders get no log entry.
**Example:** a sales order's draft invoice is deleted from the invoice page; the sales order still shows "invoiced" and its activity log says nothing.
**Rules affected:** `delete_invoice` D5
**Answer:** bug — per BUG-2732 (owner 2026-11-14): every order type is unlinked on delete (precedent — confirm)
**Resolution:** existing BUG-2732, no new ID. What "unlinked" means per order type is chosen by Claude under the reviewer's delegation (2026-11-21): the same fields each order's own unlink clears, and one `invoice_draft_deleted` event on the order. Rules: `delete_invoice` D5.

### New questions

### Q1. "Resync items" on a sales order's invoice always crashes — 🐞 BUG-2963
**Background:** "Resync items" (`POST /invoices/{id}/resync-items`) rebuilds a draft invoice's lines from its linked order. It has a branch per order type.
**What happens today:** the sales branch calls a method the sales manager does not have. Every resync of a sales-order invoice fails with an internal error (500); nothing is changed (verified).
**Example:** SO-2026-012's draft invoice is out of step after a line price changed. The user clicks "Resync items" and gets "Something went wrong" every time.
**Rules affected:** `resync_items` S6a
**Answer:** bug — the sales order is read in the workspace (missing → 404 `Sales order with ID {id} not found`) and the lines are rebuilt exactly as the sales service builds them for its own draft invoice (decided by Claude under the reviewer's delegation, 2026-11-21: a crash with one obvious fix)
**Resolution:** rules `resync_items` S6a.

### Q2. "Resync items" on a work order's invoice deletes its only line — 🐞 BUG-2964
**Background:** a work order's invoice has one line: the work order's title at its cost (quantity 1). "Resync items" has branches for purchase, expense and sales orders only. Any other order type falls through to "no lines". An invoice with no lines is worth 0.00, and 0.00 paid of 0.00 counts as `paid`.
**What happens today:** resync on a work order's draft invoice deletes the line. The invoice becomes 0.00 and `paid` (verified). If it is then finalized it is a 0.00 invoice, and the customer is never billed.
**Example:** WO-2026-031 for "Rahman Traders" costs 5,000.00 and has a 5,000.00 draft invoice. A user clicks "Resync items". The invoice now shows 0.00, status "paid".
**Rules affected:** `resync_items` S7, S8
**Answer:** bug — a work order's invoice is rebuilt as its one line (title, quantity 1, unit price and subtotal = the order's cost, 0.00 when unset), as the work order service makes it; a soft-deleted work order is not found (404). An `order_type` this method does not know is refused with 400 and the lines are kept, never wiped (decided by Claude under the reviewer's delegation, 2026-11-21: money silently lost, and the work order service shows the intended line)
**Resolution:** rules `resync_items` S7, S8.

### Q3. Finalizing a sales order's invoice from the invoice page skips the order's checks and leaves the order stuck — 🐞 BUG-2965
**Background:** a sales order's own "Finalize invoice" requires its two sections (order info, items) confirmed and its approvals met, then marks the order's sections and `invoice_confirmed` as done. Deliveries can only be planned once the order's `invoice_confirmed` is set. The invoice page's "Finalize" (this service) does the same checks for a **purchase** order's invoice, but has no sales branch.
**What happens today:** for a sales order's invoice the invoice page finalizes without any of the order's checks and leaves the order's flags unset. The order's own "Finalize invoice" then fails with "Invoice is already confirmed", so the order can never plan a delivery (verified).
**Example:** SO-2026-018 for 12,000.00 needs two approvals and has none. An accountant finalizes its invoice from the invoice page; it is now a confirmed 12,000.00 receivable. The sales team then cannot deliver: "Finalize invoice" says it is already confirmed, and delivery planning says "Finalize the invoice before planning a delivery".
**Rules affected:** `confirm_invoice` K9
**Answer:** bug — the invoice page applies the sales order's own finalize rules: sections confirmed (400 `Confirm order info and items before finalizing`), approvals met (400 `Requires {required} approval(s); {approved} so far`), then the order's sections and `invoice_confirmed` are set and it logs `invoice_confirmed` / `Invoice #<id> confirmed — order locked`; approvers notified per BUG-1205 (decided by Claude under the reviewer's delegation, 2026-11-21: the sales order's own approval gate already exists, this only closes a path around it, and the purchase branch is the model)
**Resolution:** rules `confirm_invoice` K9.

### Q4. Voiding an order's invoice from the invoice page leaves sales, expense and work orders tied to the voided invoice — 🐞 BUG-2966
**Background:** voiding a purchase order's invoice here also unlinks it from the PO, clears the PO's approvals and unconfirms its supplier and items, so the PO can be fixed and invoiced again. Sales, expense and work orders get none of this.
**What happens today:** after the void, a sales order still says "invoice finalized", so deliveries can still be planned and fulfilled against an invoice that no longer asks for money. An expense or work order still points at the voided invoice; completing it is refused ("Linked invoice was voided — cannot complete this order"), and no new invoice is made because the order still has one.
**Example:** EXP-2026-007 (rent, 30,000.00) has a confirmed invoice. The accountant voids it from the invoice page to fix the amount. The order can now never be completed, and no new draft invoice appears.
**Rules affected:** `void_invoice` X8
**Answer:** bug — every order of the workspace whose own invoice is this one is unlinked as the PO is: sales order → approvals reset, `invoice_id` / `invoice_confirmed` / `is_invoiced` / `paid` cleared, `order_info_confirmed` / `items_confirmed` unconfirmed, event `invoice_voided`; expense and work order → `invoice_id` cleared and event `invoice_voided`, approvals unchanged (decided by Claude under the reviewer's delegation, 2026-11-21: the PO branch is the precedent; the frozen completed orders cannot reach this at all)
**Resolution:** rules `void_invoice` X8. Proposed fix confirmed under the delegation at apply-review (2026-11-21).

### Q5. Voiding a sales order's invoice after goods were delivered is allowed — 🐞 BUG-2967
**Background:** a PO's invoice can't be voided here once any goods were received on the PO (400). The owner ruled on 2026-11-14 that a PO with goods received can't be voided; a return is used instead (BUG-2734).
**What happens today:** a sales order's invoice is voided even after some of its goods were delivered. All its payments are cancelled and the customer owes nothing for goods that have left.
**Example:** SO-2026-020: 10 chairs, 20,000.00, 4 delivered, 8,000.00 paid. The invoice is voided from the invoice page; the 8,000.00 payment is cancelled and nothing is owed for the 4 chairs.
**Rules affected:** `void_invoice` X1a
**Answer:** bug — per the owner's 2026-11-14 rule (goods moved → no void, use a return), applied to sales orders: any line with delivered / fulfilled quantity > 0 → 400 `Cannot void invoice after delivery has been recorded on the linked order`, nothing written (precedent — confirm; decided by Claude under the reviewer's delegation, 2026-11-21)
**Resolution:** rules `void_invoice` X1a.

### Q6. The PO's "draft invoice deleted" log entry records no invoice id — 🐞 BUG-2968
**Background:** deleting a draft invoice writes `invoice_draft_deleted` on its PO with metadata `{"invoice_id": <old id>}`. The invoice row is deleted first; the database then clears the PO's `invoice_id`.
**What happens today:** the PO's link is already cleared when the event is written, so the metadata says `{"invoice_id": null}` (verified). Only the description still names the invoice.
**Example:** the PO log reads "Draft invoice #812 deleted", but a report built on the metadata cannot tell which invoice it was.
**Rules affected:** `delete_invoice` D4a
**Answer:** bug — the event's metadata carries the deleted invoice's id (decided by Claude under the reviewer's delegation, 2026-11-21)
**Resolution:** rules `delete_invoice` D4a.

### Q7. Confirm sets a PO invoice's amount to the PO total, then the item sum replaces it — ✅ intended (dead write)
**Background:** the owner's BUG-627 answer: an invoice's amount is always the sum of its lines, and confirming recomputes it.
**What happens today:** for a PO's draft invoice, the service first writes the PO's `total_amount` into the invoice, then the manager overwrites it with the line sum. The first write has no visible effect (verified: PO total 999.00, one 400.00 line → confirmed at 400.00).
**Example:** nothing a user can see.
**Rules affected:** `confirm_invoice` K4
**Answer:** intended — the confirmed amount is the line sum (BUG-627); the PO-total write is dead and can go with the next clean-up (decided by Claude under the reviewer's delegation, 2026-11-21; for the dead-code checklist at apply-review)
**Resolution:** rule `confirm_invoice` K4 states the outcome.

### Q8. `list_accounts_hub_page` has no caller — remove
**Background:** the accounts hub endpoint goes through `AccountService`, which calls the manager directly.
**What happens today:** this service's `list_accounts_hub_page` is called from nowhere in `app/` or `tests/`.
**Example:** unreachable from any endpoint.
**Rules affected:** none (not specified)
**Answer:** remove (decided by Claude under the reviewer's delegation, 2026-11-21)

### OQ-AIS-1. An expense or work order's invoice can be finalized on the invoice page before the order is approved or completed — 🐞 BUG-2969 (owner, OQ-60)
**Module / kind:** `confirm_invoice` (money, order workflow). Reached through `POST /invoices/{id}/confirm`.
**Background:** an expense order's or work order's draft invoice is normally finalized only when the order is completed, and completing it requires its approvals. A finalized payable invoice can be paid. The invoice page's "Finalize" checks sections and approvals for purchase orders (and, after Q3, for sales orders), but not for expense or work orders.
**What happens today:** anyone can finalize an expense or work order's invoice from the invoice page at any time: before approval, while the order is still a draft. The invoice can then be paid. Completing the order later skips the finalize step because it is already done.
**Example:** EXP-2026-009 is a 45,000.00 machine repair waiting for the manager's approval. An accountant opens its invoice and clicks "Finalize". The bill is now payable, and 45,000.00 can be paid out before anyone approved the expense.
**Rules affected:** `confirm_invoice` K8, K10
**Recommended answer:** (a) refuse.
**Options, in plain words:**
- **(a) Refuse it on the invoice page (recommended).** An expense or work order's invoice is finalized only by completing the order, which already checks approvals. On the invoice page "Finalize" says: "This invoice is finalized when expense order EXP-2026-009 is completed." In the example nothing can be paid on the 45,000.00 repair until the manager approves and the order is completed. Simple and safe; the one place that finalizes is the one that checks.
- **(b) Allow it once approvals are met.** The invoice page checks the order's approvals, as it does for purchase orders: with approvals missing it says "Requires 1 approval(s); 0 so far". In the example the accountant can finalize the 45,000.00 bill as soon as the manager approves, even before the repair is marked complete, so a deposit can be paid early. More flexible, but a bill can be paid for work not yet done.
- **(c) Keep today's behaviour.** Anyone can finalize at any time. In the example 45,000.00 can be paid before anyone approved the expense.
**Answer:** bug — option (a) (owner, [OQ-60](../../../docs/testing/owner-questions.md), 2026-11-21): refused on the invoice page; the message names the order, e.g. "This invoice is finalized when expense order EXP-2026-009 is completed."
**Resolution:** rules `confirm_invoice` K10 (refusal), K8 (the expense-order notification here becomes unreachable). Status code 400, as every other "wrong state" refusal of this method (K2, K3, K9), and the scope (voided / soft-deleted orders included) chosen by Claude under the reviewer's delegation (2026-11-21).

## Overview
`AccountInvoiceService` is the transaction boundary for the invoice endpoints (`app/api/v1/endpoints/account_invoices.py`, and the account pages' invoice lists and summary in `accounts.py`). Each write calls `AccountInvoiceManager`, commits and re-reads; on an invoice that is a purchase order's own invoice it also keeps the PO in step (confirm: section and approval checks, section flips, stage, event, notification; void: received-goods guard, approvals reset, unlink, sections unconfirmed; delete: unlink). Confirm also notifies the people on an expense order whose invoice it is. Resync rebuilds a draft's lines from its linked order. Reads are plain pass-throughs to the manager. Invariants it adds on top of the manager: a PO's invoice is finalized only with the PO's sections and approvals in place, and a PO with goods received keeps its invoice.

**Transaction contract:** every write follows TC1–TC6 of `tests/unit/services/base_service.spec.md`, tested here on `create_invoice`, `update_invoice`, `delete_invoice`, `revert_to_draft`, `resync_items`, `confirm_invoice`, `void_invoice`. Departure: `delete_invoice` returns the deleted object without re-reading it (TC2 does not apply; TC5 cannot happen). The manager's freeze refusals (F5), the credit-note refusals (BUG-2733, BUG-2788) and every other manager error pass through unchanged and roll back (O1 follow-up (c)). Reads: TC6.

**"The PO's invoice"** below is the workspace's purchase order whose `invoice_id` is this invoice (`purchase_order_manager.spec.md` `get_po_by_invoice_id` R1: lowest `id` when two share it, BUG-2637; another workspace's PO never). It is the same F1 slot the freeze uses. An invoice's `order_type` / `order_id` do not make a PO "the PO's invoice"; they are read only by `resync_items`.

**Callables:** 16 specified · 2 not specified
**Externals to mock:** none. Notifications are rows written by `notify_invoice_action` (`pg_notify` runs in the database); `utcnow` only through the manager (`app.managers.account_invoice_manager.utcnow`).
**Integration-only behavior:** none.

**Facts for the test designer**
- Import: `from app.services.account_invoice_service import AccountInvoiceService, account_invoice_service`. `AccountInvoiceService()` takes no arguments; it calls the module-level singletons `account_invoice_manager`, `purchase_order_manager`, `expense_order_dao`, `notify_invoice_action`.
- Builders already exist in `tests/unit/managers/test_account_invoice_manager.py` (`mk_account`, `mk_inv`, `mk_item`, `mk_pay`, `mk_po`, `mk_eo`, `mk_so`, `mk_wo`, `mk_st`, `mk_por`, `mk_sor`, `mk_cn`); copy them, do not import a test module.
- PO stage rows: confirm and void re-derive the PO stage (`sync_po_stage`), which needs `statuses` rows `Draft`, `Planning`, `Receiving`, `Complete` in the workspace, or the call fails with 422 and nothing is saved (verified). Build all four.
- Notifications reach only active members: a recipient needs a `workspace_members` row with `status = "active"`.
- The freeze, credit-note and manager rules are tested in the manager's own file; here one card per path is enough to prove the error passes through and the PO / order is left unchanged.

**Notes for the test designer**
- Session and commits: as `department_service.spec.md`. Assert "committed" with a test-level `db.rollback()` and a re-select.
- Locks (BUG-2962): record SQL with an `after_cursor_execute` listener (as the manager tests' lock recorder). Expected clauses: `purchase_orders`, `sales_orders`, `account_invoices` one-table reads end in `FOR UPDATE` (accept `FOR UPDATE OF <that table>`); the line reads end in exactly `FOR UPDATE OF purchase_order_items` / `FOR UPDATE OF sales_order_items`. None has `SKIP LOCKED` or `NOWAIT`. Each lock statement comes before the guard's first read of the state it checks (S1a, K3b, K9b, X1c).

## Not specified
- `AccountInvoiceService.__init__` — wires the manager, no logic.
- `AccountInvoiceService.list_accounts_hub_page` — dead code, to be removed (reviewer delegation, Q8): no caller in `app/` or `tests/`.

---

## `AccountInvoiceService.create_invoice(db, invoice_in, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /invoices`)

**Purpose:** create a draft invoice for an account.

**Returns:** the new invoice, committed and re-read.

**Rules:**
- **C1.** The invoice is created exactly as `account_invoice_manager.spec.md` `create_invoice` R1–R9d (including BUG-624, 625, 627) and committed (TC1); the returned row has `created_at` loaded (TC2).
- **C2.** A manager refusal (404 account, 400 deleted / inactive, 403 invoices not allowed, 404 order) reaches the caller unchanged and nothing is saved: no invoice, no event (TC3).

**Errors:** the manager's, unchanged. **Side effects:** one invoice + one event, committed.

---

## `AccountInvoiceService.get_invoice(db, invoice_id, workspace_id)`
**Shape:** get-or-404 · **Persistence:** reads · **Visibility:** public (`GET /invoices/{id}`)

**Rules:**
- **G1.** Returns the manager's `get_invoice` result (another workspace's or missing id → 404 `Invoice with ID {id} not found`); TC6.

---

## Read pass-throughs: `list_invoices`, `list_open_invoices_page`, `list_account_invoices_page`, `get_invoices_hub_summary`, `summarize_invoices`, `get_events`, `get_items`
**Shape:** list / compute · **Persistence:** reads · **Visibility:** public (`GET /invoices`, `GET /accounts/{id}/open-invoices`, `GET /accounts/{id}/invoices`, `GET /invoices/hub-summary`, `GET /accounts/{id}/invoice-summary`, `GET /invoices/{id}/events`, `GET /invoices/{id}/items`)

**Rules:**
- **L1.** `list_invoices` returns exactly the manager's `list_invoices` for the same filters, `skip`, `limit` (service defaults `skip 0`, `limit 100`); `list_open_invoices_page` returns the manager's `(items, total)` (defaults `0` / `10`); `get_invoices_hub_summary` and `summarize_invoices` return the manager's tuples; `get_events` / `get_items` the manager's lists (404 for a missing or another workspace's invoice). Filtering, ordering and money rules are the manager's (`account_invoice_manager.spec.md` shared filters R1–R14 and the per-method rules; BUG-622, 623, 634, 635, 636, 637, 638; OQ-41 / BUG-2692 in the DAO spec).
- **L2.** `list_account_invoices_page` returns the manager's `list_invoices_page` result for the given `account_id`, type, statuses, number search and date bounds, `skip` (default 0) and `limit` (**default 50**, not the manager's 100). It never passes `account_name_search`, `amount_min`, `amount_max`, `open_balance_only` or `prioritize_purchase_order_id`, so those keep the manager's defaults (no filter, not open-only, no prioritising).
- **L1a.** Signatures (all after `db`, positional or keyword; the endpoints pass keywords). Every argument is forwarded to the manager under the same name, with `session=db`:
  | Method | Parameters (default) |
  |---|---|
  | `list_invoices` | `workspace_id`, `account_id=None`, `invoice_type=None`, `payment_status=None`, `invoice_status=None`, `invoice_number_search=None`, `account_name_search=None`, `invoice_date_from=None`, `invoice_date_to=None`, `due_date_from=None`, `due_date_to=None`, `amount_min=None`, `amount_max=None`, `skip=0`, `limit=100` |
  | `list_open_invoices_page` | `workspace_id`, `account_id` (required), `prioritize_purchase_order_id=None`, `skip=0`, `limit=10` — `prioritize_purchase_order_id` is forwarded (manager rule) |
  | `list_account_invoices_page` | `workspace_id`, `account_id` (required), `invoice_type=None`, `payment_status=None`, `invoice_status=None`, `invoice_number_search=None`, `invoice_date_from=None`, `invoice_date_to=None`, `due_date_from=None`, `due_date_to=None`, `skip=0`, `limit=50` — calls the manager's `list_invoices_page` (L2) |
  | `get_invoices_hub_summary` | `workspace_id` |
  | `summarize_invoices` | the 13 filter parameters of `list_invoices` (no `skip` / `limit`) |
  | `get_events`, `get_items` | `invoice_id`, `workspace_id` |
- **L3.** Every read is TC6: nothing is committed or rolled back; pending changes in the session stay pending; a manager error reaches the caller unchanged.

---

## `AccountInvoiceService.update_invoice(db, invoice_id, invoice_in, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (`PUT /invoices/{id}`)

**Rules:**
- **U1.** The invoice is updated exactly as the manager's `update_invoice` R1–R15 (confirmed invoices: only `due_date`, `allow_payments`, `payment_locked_reason`, also on a completed order, R3b) and committed (TC1, TC2). Errors pass through and nothing is saved (TC3).
- **U2.** The linked order is not touched: no PO, sales, expense or work order row or event changes.

---

## `AccountInvoiceService.delete_invoice(db, invoice_id, workspace_id, user_id)`
**Shape:** delete · **Persistence:** writes · **Visibility:** public (`DELETE /invoices/{id}`)

**Purpose:** delete a draft invoice and unlink it from its order.

**Returns:** the deleted invoice object (not re-read; its row no longer exists).

**Rules:**
- **D1.** The PO's invoice is looked up first (Overview). Then the manager deletes the invoice per `delete_invoice` R1–R4 (non-draft → 400, frozen draft → 400 per F5 [BUG-2730], payment history → 400 [BUG-639], not found → 404). On any refusal nothing is written: the invoice, the PO and its events are unchanged (TC3).
- **D2.** On success the deletion is committed: the invoice row, its items and events are gone after a rollback of the session (TC1).
- **D3.** The returned object is the deleted invoice, with the `id` that was asked for; it is not re-read.
- **D4.** If there is a PO's invoice: the PO gets `invoice_id = None`, `invoice_confirmed = False`, `paid = False` (`purchase_order_manager.spec.md` `unlink_invoice_from_po` R1) and one event `invoice_draft_deleted`, description `Draft invoice #<invoice_id> deleted`, performer `user_id`. Its other section confirms and its stage are unchanged.
- **D4a.** [BUG-2968] That event's metadata is `{"invoice_id": <the deleted invoice's id>}`. *(Today: `{"invoice_id": null}` — the PO's link is already cleared by the database when the event is written; verified.)*
- **D5.** [BUG-2732] (owner 2026-11-14; field list chosen under the reviewer's delegation, 2026-11-21) Every other order of the workspace whose `invoice_id` was this invoice is unlinked too, each with one event `invoice_draft_deleted` / `Draft invoice #<invoice_id> deleted`, performer `user_id`, metadata `{"invoice_id": <id>}`: a **sales order** gets `invoice_id = None`, `invoice_confirmed = False`, `is_invoiced = False`, `paid = False`; an **expense order** and a **work order** get `invoice_id = None`. Another workspace's order is never touched. *(Today: only the PO is handled; a sales order keeps `is_invoiced = True` (verified) and no sales, expense or work order event is logged; their `invoice_id` is cleared only by the database's `ON DELETE SET NULL`.)*
- **D6.** No PO and no other order points at the invoice → only the invoice is deleted; nothing else changes.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found / other workspace | 404 | `Invoice with ID {id} not found` |
| not draft | 400 | `Only draft invoices can be deleted. This invoice is '{status}'. Use void instead.` |
| frozen draft | 400 | F5 text — BUG-2730 |
| payment history | 400 | `Invoice has payment history — confirm and void it instead` — BUG-639 |

**Side effects:** invoice deleted; order unlinked with an event; committed.

---

## `AccountInvoiceService.revert_to_draft(db, invoice_id, workspace_id, user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST /invoices/{id}/revert-to-draft`)

**Rules:**
- **V1.** Reverts exactly as the manager's `revert_to_draft` R1–R6 (credit note → 400 [BUG-2733]; frozen → 400 [BUG-2730]; receiving started → 400 [BUG-2736 text]; paid > 0 → 400) and commits (TC1, TC2). Errors pass through, nothing saved (TC3).
- **V2.** The linked order is not touched: a PO's `invoice_confirmed`, section confirms, approvals and stage stay as they were; no order event.

---

## `AccountInvoiceService.resync_items(db, invoice_id, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (`POST /invoices/{id}/resync-items`)

**Purpose:** rebuild a draft invoice's lines from the order its `order_type` / `order_id` name.

**Returns:** the invoice, committed and re-read.

**Rules:**
- **S1.** The invoice is read per the manager's `get_invoice` (missing / another workspace → 404). [BUG-2962] It is read `FOR UPDATE` before the status check. *(Today: plain read.)*
- **S1a.** [BUG-2962] Exact lock: the read is a one-table `SELECT … FROM account_invoices WHERE account_invoices.id = :id AND account_invoices.workspace_id = :ws … FOR UPDATE` — plain `FOR UPDATE` (the `AccountInvoice` model has no eager-joined relationship, so nothing is joined); `FOR UPDATE OF account_invoices` is the same lock and also acceptable; never `SKIP LOCKED` or `NOWAIT`. Held until the commit or rollback. The manager's own lock on the same row later in the request (BUG-621) is harmless.
- **S2.** Status other than `draft` (confirmed, voided) → 400 `Can only resync items on draft invoices.`, nothing written.
- **S3.** `order_id` empty (`None` or `0`) or `order_type` empty (`None` or `""`) → 400 `This invoice is not linked to an order — resync is not applicable.`, nothing written. Checked after S2.
- **S4.** The lines are replaced per the manager's `sync_items_from_list` R2–R7: old lines deleted, the built lines inserted in order, `last_synced_at` set, amount and payment status recomputed, one `items_synced` event `Items synced from order (<N> lines)`; committed (TC1, TC2). The linked order itself is not changed.
- **S5.** `order_type = "purchase_order"`: the PO is read in the workspace (missing or another workspace's → 404 `Purchase order with ID {order_id} not found`; a voided PO is found). One line per PO line, by `line_number` ascending: `line_number` = the PO line's, `description` = the item's name (`Item <item_id>` when the line has no item row), `item_id`, `source_order_item_id` = the PO line's id, `source_order_item_type = "po_item"`, `quantity` = `quantity_ordered`, `unit` = the item's unit, `unit_price`, `line_subtotal` as stored. (The `Item <item_id>` fallback cannot happen: `purchase_order_items.item_id` is NOT NULL with a `RESTRICT` foreign key, and soft-deleted items keep their row and name — so the line always carries the item's name and unit, even for a soft-deleted item. No case for the fallback.) A PO line with no `unit_price` or `line_subtotal` fails at flush with `IntegrityError` (the invoice-line columns are NOT NULL), the old lines are kept and nothing is saved (TC3).
- **S6.** `order_type = "expense_order"`: the order's lines (missing / other workspace order → 404 `Expense order with ID {order_id} not found`) in `line_number` order, renumbered 1, 2, 3 …: `description` = the line's description, or `Expense item <line id>` when empty; `item_id = None`; `source_order_item_type = "eo_item"`; `quantity` = the line's, `1` when empty or 0; `unit`; `unit_price` and `line_subtotal` = the line's, `0` when empty.
- **S6b.** What "empty" means for an expense line (columns of `expense_order_items`): `description` is nullable text — `None` **and** `""` both give `Expense item <line id>` (a whitespace-only description is kept as typed); `quantity` is NOT NULL (default 1), so only `0` (also `0.00`) gives `1`; `unit_price` and `line_subtotal` are nullable — `None` gives `0`, and a stored `0.00` stays `0.00`; `unit` is copied as is (`None` stays `None`). `source_order_item_id` = the expense line's own `id`. Lines are taken in `line_number` order (the DAO's ordering) and renumbered 1, 2, 3 … whatever their stored `line_number`.
- **S6a.** [BUG-2963] `order_type = "sales_order"`: the sales order is read in the workspace (missing / other workspace → 404 `Sales order with ID {order_id} not found`); one line per sales order line in `id` ascending order, renumbered 1, 2, 3 …: `description` = the item's name, else the line's description, else `Item <item_id>`; `item_id`; `source_order_item_id` = the line's id; `source_order_item_type = "so_item"`; `quantity` = `quantity_ordered`; `unit` = the item's unit (`None` for a free-text line); `unit_price`; `line_subtotal` = `line_total` (the same lines `SalesService` builds for the order's draft invoice). *(Today: `AttributeError: 'SalesManager' object has no attribute 'get_sales_order'` → 500; rolled back, lines unchanged; verified.)*
- **S7.** [BUG-2964] `order_type = "work_order"`: the work order is read in the workspace; missing, another workspace's or soft-deleted (`is_deleted = True`) → 404 `Work order with ID {order_id} not found`. One line: `line_number 1`, `description` = the order's title, `item_id None`, `source_order_item_id None`, `source_order_item_type = "wo_labor"`, `quantity 1`, `unit None`, `unit_price` = `line_subtotal` = the order's `cost` (0.00 when unset) — as `WorkOrderService` builds it. *(Today: falls through to S8's "no lines": every line is deleted, the invoice becomes 0.00 and `paid`; verified.)*
- **S8.** [BUG-2964] Any other `order_type` → 400 `Resync is not supported for order type '<order_type>'.`, nothing written, lines kept. *(Today: every line is deleted and the invoice becomes 0.00 with `payment_status = "paid"`, one `items_synced` event "(0 lines)". With BUG-624 fixed only the four known types can be stored, so this guards old rows.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| invoice not found | 404 | `Invoice with ID {id} not found` |
| not draft | 400 | `Can only resync items on draft invoices.` |
| not linked | 400 | `This invoice is not linked to an order — resync is not applicable.` |
| PO / EO missing | 404 | `Purchase order with ID {id} not found` / `Expense order with ID {id} not found` |
| SO / WO missing | 404 | `Sales order with ID {id} not found` / `Work order with ID {id} not found` — BUG-2963 / 2964 |
| unknown order type | 400 | `Resync is not supported for order type '<type>'.` — BUG-2964 |
| PO line unpriced | `IntegrityError` | — |

**Side effects:** invoice lines replaced, invoice amount / status recomputed, one event; committed.

---

## `AccountInvoiceService.confirm_invoice(db, invoice_id, workspace_id, user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST /invoices/{id}/confirm`)

**Purpose:** finalize a draft invoice; for an order's own invoice, keep the order in step.

**Returns:** the confirmed invoice, committed and re-read.

**Rules:**
- **K1.** No PO's invoice and no other order (K9–K10) → confirmed exactly as the manager's `confirm_invoice` R1–R6 (not found 404, voided 400, already confirmed 400, no lines 400 [BUG-628]; amount = line sum; event `confirmed`) and committed (TC1, TC2).
- *PO's invoice:*
- **K2.** The PO's supplier, details and items are not all confirmed (`_base_sections_confirmed`) → 400 `Confirm supplier, order details, and items before finalizing`, nothing written. Checked before the invoice's own status (so a confirmed PO invoice with an unconfirmed section gets this text, not "already confirmed").
- **K3.** Approvals not met (`purchase_order_manager.spec.md` `approval_summary` R1–R3; no approvers and no requirement → 1 required, BUG-1202) → 400 `Requires {required} approval(s); {approved_count} so far`, nothing written. Checked after K2.
- **K3a.** [BUG-2962] The PO row is read `FOR UPDATE` before K2. *(Today: plain read.)*
- **K3b.** [BUG-2962] Exact lock (K3a, and X1's PO read): the PO lookup by invoice is a one-table read, `SELECT … FROM purchase_orders WHERE purchase_orders.invoice_id = :invoice_id AND purchase_orders.workspace_id = :ws ORDER BY purchase_orders.id LIMIT 1 FOR UPDATE` (lowest `id`, BUG-2637). Plain `FOR UPDATE` (the `PurchaseOrder` model has no eager-joined relationship); `FOR UPDATE OF purchase_orders` is the same lock and also acceptable; never `SKIP LOCKED` / `NOWAIT`. Lock order within one request: the order row first, then (X1 / X1a) its lines, then the invoice (the manager's lock, BUG-621). The loser of a race waits, then sees the new state (e.g. sections unconfirmed, approval withdrawn) and gets the normal K2 / K3 error.
- **K4.** The confirmed amount is the sum of the invoice's lines (manager R4, BUG-627), whatever the PO's `total_amount` (verified: total 999.00, one 400.00 line → 400.00). (Q7: today's intermediate write of the PO total has no visible effect.)
- **K5.** After the invoice is confirmed: every PO section not yet confirmed becomes confirmed and the PO logs `invoice_created` / `Invoice created` and, per section flipped, its event (`purchase_order_manager.spec.md` `apply_post_invoice_confirms` R1–R2, including `invoice_confirmed` / `Draft invoice confirmed after invoice finalized`); the PO stage is re-derived (`sync_po_stage` R1–R4; a missing stage row → 422, nothing saved); then one more PO event `invoice_confirmed`, description `Invoice #<invoice_id> confirmed — order locked`, performer `user_id`, metadata `{"invoice_id": <id>}`. All committed together with the invoice.
- **K5a.** The stage after the confirm is **`Receiving`**: with the invoice now confirmed the PO counts as financially locked, which derives `Receiving` whatever the sections (a PO already at `Complete` stays `Complete`). So a PO at `Planning` (the normal case — K2 requires its sections) moves `Planning` → `Receiving` with one `status_updated` event. Missing stage row: if the workspace has no `Draft` status row, all four PO stage rows are created first and nothing fails; if `Draft` exists but `Receiving` does not → 422 `Purchase order stage status 'Receiving' not found for this workspace`, nothing saved (TC3).
- **K6.** The people on the PO are notified per `approval_notification_service.spec.md` `notify_invoice_action` R1–R6 with `entity_type = "purchase_order"`, `action = "confirmed"`, `invoice_id`, actor `user_id` (text `Invoice confirmed on <ref> — order locked`). Notifications are written in the same transaction: an error there undoes the confirm (TC3).
- **K7.** A manager refusal (K1's errors) after K2–K3 passed → nothing written: the PO's sections, stage and events are unchanged.
- *Other orders (no PO's invoice):*
- **K8.** [BUG-2969] No expense-order notification is sent from this method: an expense order's own invoice is refused by K10 before anything is written, so nobody is notified. (Expense orders notify when they are completed, in `expense_order_service`.) *(Today: the workspace's newest expense order with `invoice_id` = this invoice — voided and completed included, ties → highest `id`, BUG-2711 — gets `notify_invoice_action` with `entity_type = "expense_order"`, `action = "confirmed"` after the confirm; the order row is not changed. With the fix that branch can no longer run and goes with the clean-up.)*
- **K9.** [BUG-2965] (delegated) The invoice is a **sales order's** own invoice (a sales order of the workspace with `invoice_id` = it): order info and items not both confirmed → 400 `Confirm order info and items before finalizing`; approvals not met (`sales_manager.approval_summary`) → 400 `Requires {required} approval(s); {approved_count} so far`; both checked before the invoice's status, nothing written. Otherwise, after the confirm, the order's `order_info_confirmed`, `items_confirmed`, `invoice_confirmed` become `True` (as `sales_manager.apply_post_invoice_confirms`, with its section events) and the order logs `invoice_confirmed` / `Invoice #<id> confirmed — order locked`, metadata `{"invoice_id": <id>}`; its approvers and creator are notified (`notify_invoice_action` R7a, BUG-1205; preview `Invoice confirmed on SO-<order id> — order locked`, the reference built from the order's `id`, not its `SO-2026-…` number, per `format_order_ref` R2a). The order's own "Finalize invoice" is then answered 409 `Invoice is already finalized`. *(Today: no check, no flag, no event, no notification; the order's own finalize then fails 400 `Invoice is already confirmed` and the order can never plan a delivery; verified.)*
- **K9a.** [BUG-2965] Section events of K9, as `sales_manager.apply_post_invoice_confirms`: `order_info_confirmed` not yet set → it becomes `True` with event `order_info_confirmed` / `Order info confirmed after invoice finalized`; `items_confirmed` not yet set → `True` with event `items_confirmed` / `Order items confirmed after invoice finalized`; `invoice_confirmed` → `True` with **no** event of its own (the single `invoice_confirmed` / `Invoice #<id> confirmed — order locked` event of K9 is the only one). Performer `user_id` on each. A flag already set gets no event. Sales events in order: the section events, then `invoice_confirmed`. (K9 requires both sections confirmed before the confirm, so in practice only `invoice_confirmed` flips; the section branches stay as a guard.)
- **K9b.** [BUG-2962] (HR-10, delegated) The sales order is read `FOR UPDATE` before the K9 checks — one-table `SELECT … FROM sales_orders WHERE … FOR UPDATE`, plain (no eager-joined relationship; `OF sales_orders` also acceptable).
- **K10.** [BUG-2969] (owner, OQ-60) The invoice is an **expense order's** or **work order's** own invoice (an order of the workspace with `invoice_id` = it; voided, completed and soft-deleted orders included) and is not a PO's or sales order's invoice → 400, nothing written (invoice still `draft`, no event, no notification), checked before the invoice's own status. Detail: `This invoice is finalized when expense order <expense_number> is completed.` or `This invoice is finalized when work order <work_order_number> is completed.` (e.g. `This invoice is finalized when expense order EXP-2026-009 is completed.`). When both an expense and a work order point at it, the expense order is named. Another workspace's order pointing at the invoice is never found (HR-16), so the invoice confirms per K1. *(Today: confirmed with no check of the order's approvals or state; the bill is payable at once; verified path.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| PO sections not confirmed | 400 | `Confirm supplier, order details, and items before finalizing` |
| PO approvals not met | 400 | `Requires {required} approval(s); {approved_count} so far` |
| SO sections / approvals | 400 | `Confirm order info and items before finalizing` / `Requires … so far` — BUG-2965 |
| expense / work order's invoice | 400 | `This invoice is finalized when expense order <expense_number> is completed.` / `… work order <work_order_number> …` — BUG-2969 |
| manager | as `confirm_invoice` | — |
| PO stage row missing | 422 | `Purchase order stage status '<name>' not found for this workspace` |

**Side effects:** invoice confirmed; PO sections, stage, events; notifications; committed together.

---

## `AccountInvoiceService.void_invoice(db, invoice_id, workspace_id, user_id, void_note)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST /invoices/{id}/void`; body `VoidInvoiceRequest`)

**Purpose:** void a confirmed invoice with its payments; for an order's own invoice, release the order.

**Returns:** the voided invoice, committed and re-read.

**Rules:**
- **X1.** PO's invoice and any PO line (of the workspace) with `quantity_received > 0` → 400 `Cannot void invoice after receiving has been recorded on the linked order`, nothing written. Runs before every manager check (O1 follow-up (b)), so a draft or already-voided PO invoice with goods received also gets this text. [BUG-2962] The PO row is read `FOR UPDATE` before the lines are read. *(Today: plain read.)*
- **X1a.** [BUG-2967] (precedent, delegated) A sales order's own invoice with any line whose `quantity_delivered > 0` → 400 `Cannot void invoice after delivery has been recorded on the linked order`, nothing written, checked at the same point as X1. *(Today: voided; all payments cancelled.)*
- **X1b.** "Delivered" in X1a covers both kinds of sales line: `quantity_delivered` is the one column a delivery completion **and** a direct fulfilment (a `requires_delivery = False` line fulfilled in one click) both raise, so a service line fulfilled without any delivery record also blocks the void. `quantity_returned` / `quantity_refunded` are not looked at: a line delivered and then fully returned still has `quantity_delivered > 0` and still blocks (use a return's credit note, owner's 2026-11-14 rule).
- **X1c.** [BUG-2962] (HR-10, delegated) Exact locks of the guards: X1 — the PO row as K3b, then the PO's lines read `FOR UPDATE OF purchase_order_items`; X1a — the sales order row as K9b, then its lines read `FOR UPDATE OF sales_order_items`. The `OF` clause is required on the line reads: both line models eager-join their `item` (`lazy="joined"`, a `LEFT OUTER JOIN items`), and Postgres refuses a plain `FOR UPDATE` on the nullable side of an outer join (the BUG-029 restriction). Locking the lines serializes the guard with any concurrent receipt or delivery, because those update the same line rows. The loser sees the received / delivered quantity and gets the normal X1 / X1a 400. *(Today: plain reads.)*
- **X2.** The invoice and its payments are voided exactly as the manager's `void_invoice` R1–R8 (frozen → 400 per F5 [BUG-2731]; credit note of a completed return → 400, of a pending return → the return is voided too [BUG-2788]); committed (TC1, TC2). Any refusal → nothing written (invoice, payments, PO, approvals, events unchanged; TC3).
- **X3.** PO's invoice, after the void: every approved approver of the PO is reset (`reset_approvals` R1–R2: `approved = False`, `approved_at = None`, event `approvals_reset` `Cleared approvals after invoice voided (<n> approval(s) cleared)`; none approved → no event).
- **X4.** Then the PO is unlinked (`unlink_invoice_from_po` R1–R2): `invoice_id = None`, `invoice_confirmed = False`, `paid = False`, event `invoice_voided`, description `Invoice #<invoice_id> voided`, metadata `{"invoice_id": <id>, "changes": [{"field": "void_note", "label": "Void reason", "from_value": null, "to_value": <void_note>}]}`.
- **X5.** Then `supplier_confirmed` and `items_confirmed` that are set become `False`, each with its event, and the stage is re-derived (`unconfirm_sections_after_invoice_void` R1–R2); `details_confirmed` is kept (verified: stage `Draft` → `Planning`).
- **X6.** All of X2–X5 are committed together; a failure in any step (e.g. a missing stage row → 422) saves none of them.
- **X7.** No order's own invoice (e.g. a manual invoice, a return credit note) → only X2.
- **X8.** [BUG-2966] Every other order of the workspace whose `invoice_id` is this invoice is released after the void: a **sales order** gets its approvals reset (as `sales_manager.reset_approvals`), `invoice_id = None`, `invoice_confirmed = False`, `is_invoiced = False`, `paid = False`, `order_info_confirmed` / `items_confirmed` `False`, and one event `invoice_voided` / `Invoice #<id> voided` with the same metadata as X4; an **expense order** or **work order** gets `invoice_id = None` and that event, approvals unchanged. *(Today: these orders are not touched — a sales order still says its invoice is finalized and can deliver; an expense or work order points at the voided invoice and can never be completed.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| PO goods received | 400 | `Cannot void invoice after receiving has been recorded on the linked order` |
| SO goods delivered | 400 | `Cannot void invoice after delivery has been recorded on the linked order` — BUG-2967 |
| `void_note` blank | 422 (schema) | — BUG-626 |
| manager | as `void_invoice` | — |

**Side effects:** invoice and payments voided; PO approvals, link, sections, stage, events; committed together.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 52–69 | create: manager ok / raises | C1, C2 |
| 91 | get | G1 |
| 113–240 | read pass-throughs | L1, L2, L3 |
| 189–205 | hub page (dead) | Not specified |
| 266–284 | update ok / raises | U1, U2 |
| 308 | PO's invoice? | D1, D4, D6 |
| 310 | manager delete raises | D1 |
| 317 | `if po` → unlink | D4, D4a |
| (fix) | other order types unlinked | D5 |
| 324–330 | commit / rollback, no refresh | D2, D3 |
| 345–353 | revert ok / raises | V1, V2 |
| 358 | invoice read (no lock) | S1, S1a |
| 359 | not draft | S2 |
| 366 | `order_id` / `order_type` falsy | S3 |
| 374 | purchase order | S5 |
| 378 | expense order (`or` defaults) | S6, S6b |
| 396 | sales order (crashes today) | S6a |
| 414 | else → `[]` | S7, S8 |
| 417–423 | sync, commit / rollback | S4 |
| 427 | PO's invoice? | K1, K8 |
| 428 | PO lookup by invoice (lock, fix) | K3a, K3b |
| 429 | sections confirmed? | K2 |
| 435 | approvals met? | K3 |
| 443 | invoice draft → amount write | K4 |
| 447 | manager confirm | K1, K7 |
| 451–471 | PO follow-ups + notification | K5, K5a, K6 |
| 473–476 | expense order found? (unreachable after BUG-2969) | K8 |
| (fix) | sales order's invoice | K9, K9a, K9b |
| (fix) | expense / work order's invoice refused | K10 |
| 489–494 | commit / rollback | TC1–TC5 |
| 498–500 | PO's invoice? | X1, X7 |
| 504 | any line received > 0 | X1 |
| (fix) | SO delivered guard | X1a, X1b |
| (fix) | guard locks (order row, then lines `OF <lines table>`) | X1c |
| 512 | manager void | X2 |
| 517–534 | PO reset / unlink / unconfirm | X3, X4, X5 |
| (fix) | other orders released | X8 |
| 536–541 | commit / rollback | X6 |

## Gap log
- G1 (account_invoice_service.cases.md gap 1) — fact — L1a added: every read pass-through's parameter names and defaults (`list_open_invoices_page` also forwards `prioritize_purchase_order_id`; `summarize_invoices` takes the 13 filters, no paging).
- G2 (gap 2) — fact — K5a added: after the confirm the PO moves to `Receiving` (financially locked), `Complete` stays; the 422 names `Receiving` (`Purchase order stage status 'Receiving' not found for this workspace`) and happens only when `Draft` exists but `Receiving` does not (a missing `Draft` back-fills all four).
- G3 (gap 3) — fact — S6b added: column nullability of expense lines; `None` and `""` description → fallback; quantity is NOT NULL so only `0` → 1; `None` price / subtotal → 0; `source_order_item_id` = the expense line's id; renumbered after `line_number` order.
- G4 (gap 4) — fact — X1b added: `quantity_delivered` is raised by both delivery and direct fulfilment, so X1a covers service lines fulfilled without delivery; returns / refunds are not subtracted.
- G5 (gap 5) — fact — K9: preview `Invoice confirmed on SO-<order id> — order locked` (per `format_order_ref` R2a, BUG-1205; today's ref would be `sales order #<id>`).
- G6 (gap 6) — fact + decided under the reviewer's delegation (2026-11-21) — S1a, K3b exact clauses (one-table reads → plain `FOR UPDATE`, `OF <table>` accepted); X1c adds the line locks `FOR UPDATE OF purchase_order_items` / `FOR UPDATE OF sales_order_items` (eager `LEFT OUTER JOIN items`, BUG-029 restriction); K9b adds the sales order row lock (HR-10 now applies to the BUG-2965 / 2967 fixes). Lock order: order row → lines → invoice. Test-designer note updated. All under BUG-2962.
- G7 (gap 7) — fact — S5: the `Item <item_id>` fallback is unreachable (`item_id` NOT NULL, `RESTRICT` FK, soft-deleted items keep their row); no case.
- G8 (gap 8) — fact — K9a added: the section events `order_info_confirmed` / `items_confirmed` with their texts, none for `invoice_confirmed`, flags already set get no event.

