# Spec — `app/managers/purchase_order_manager.py`

> **Status:** APPROVED (2026-11-21; owner answers OQ-53, OQ-54 applied; everything else decided under the reviewer's delegation; fill-gaps 2026-11-21, 13 gaps closed, see Gap log)
> **Source commit:** e48a092

> **Review round 2026-11-19 (describe, under the reviewer's delegation of 2026-11-19).** House-rule lines and precedent matches are pre-filled. Every new question that is not money, stock quantities, order workflow or security was decided by Claude under the delegation and is marked so; none of them is the owner's own answer. Two questions touch stock and money and wait for the owner (OQ-PO-1, OQ-PO-2; provisional numbers, to be renumbered when parked in `docs/testing/owner-questions.md`). Bug IDs BUG-2872 … BUG-2888 (block BUG-2872 … 2891) are logged in `docs/testing/bugs.md`. Owner rulings applied as already decided: the invoice freeze (BUG-2730 … 2736, `account_invoice_manager.spec.md` O1, F1–F7), OQ-48 refined (BUG-2789; `sales_manager.spec.md` RP1–RP7, which this manager follows with PO names), the 2026-11-19 chat answer on replacement goods (BUG-2810), OQ-13 (BUG-1881), OQ-38 (received + refunded = done).
>
> **Apply-review 2026-11-21.** The owner answered OQ-PO-1 as **OQ-53** (BUG-2887: receiving only through "Receive goods"; the line edit refuses `quantity_received`) and OQ-PO-2 as **OQ-54** (BUG-2888: a finalized invoice blocks delete; a draft invoice goes with the order), in chat 2026-11-21 (`docs/testing/owner-questions.md`). House-rule lines, precedent matches P1–P7 and Q1–Q8 confirmed as answered under the reviewer's delegation. Q5's dead code moved to *Not specified* and the removal checklist. BUG-2884 is superseded by BUG-2887 (the only path that logged the event goes).
>
> **Production:** not touched by this module (production deferred). **Projects:** a PO may name a project component as its destination; today's behaviour is described and tagged *revisit after launch*, no bugs.
>
> **Verified by running** (my own script `v_po.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\ordersdesc\purchase_order\`, one transaction on `marker_test` with foreign-key triggers off (`SET LOCAL session_replication_role = replica`), rolled back, nothing committed): three lines of 1.25 × 0.10 → in-session subtotal `0.3750`, stored total `0.38`, stored lines `0.13` each (sum `0.39`); a new order is `Draft` with one approver (the creator), one event, `order_date` today; an empty update stamps `updated_by`; `description: null` leaves the old text; another workspace's machine id is stored as destination; with a confirmed invoice `PUT` item `quantity_received = -5` is stored, then `1`, `1.25`, and `invoice_receiving_started` is logged twice; a PO with a confirmed invoice and nothing received is deleted and the invoice stays `confirmed`; a voided PO can unconfirm its items, take a new line, and record an approval withdrawal; a line of −3 × −2 is stored with subtotal `6.00`; an order with no lines cannot be completed; with no approvers the summary is `(0, 0, True)`; a completed PO accepts a new expected delivery date and approval threshold; `reopen_for_return` on a completed PO returns `True`, stage `Receiving`, `actual_delivery_date` cleared. **Not run:** concurrency (HR-10), the workflow-setup 422s.

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### House-rule violations — applied automatically
> Overwrite an answer only if the house rule should NOT apply here.

- **HR-10** `mark_order_complete` R2–R6, `reopen_for_return` R1, `update_purchase_order` R3–R7, `add_item` R2 (lock rule R7), `update_item` R2–R4 (R18), `remove_item` R2 (R4), `sync_items` R2 (R9), `set_approval` R2–R5 (R7), `add_approver` R2a/R6 (R7), `remove_approver` R1a/R4 (R5), `delete_purchase_order` R2–R3a (R6) — each reads the order (or line / approver) with a plain read, checks its state (stage, financial lock, section confirms, received quantity, approval) and then changes it. A race causes real harm: two completions, a line edit landing after the invoice amount was fixed by finalization (money), a receipt racing a delete or a completion (stock), an approval racing a withdrawal. Intended: the purchase order row is read `FOR UPDATE` before the check (the line and approver rows follow the order's lock); the loser sees the new state and gets the normal wrong-state error. One root cause (DAO spec `purchase_order.spec.md` FU-1, approver DAO FU-1 (c)). 🐞 BUG-2872
**Answer:** bug — per HR-10 (house rule)
- **HR-9** `update_purchase_order` R11 — `updated_by` is set on every call, also when nothing changes (an empty body, or the same values). Intended: written only when at least one field changes value. 🐞 BUG-2873
**Answer:** bug — per HR-9 (house rule)
- **HR-16** `create_purchase_order` R3, `update_purchase_order` R12 — `destination_id` is stored as sent: another workspace's factory or machine id is accepted (verified), and so is a soft-deleted one. BUG-1017 covers supplier, invoice and line items, not the destination. Intended: for `storage` the id must be a live factory of the workspace, for `machine` a live machine of the workspace; otherwise 404 `Factory with ID {id} not found` / `Machine with ID {id} not found`, nothing written ("live" as BUG-728 precedent). `project` destinations: today's behaviour, *revisit after launch*, not part of this bug. 🐞 BUG-2874
**Answer:** bug — per HR-16 (house rule)
- **HR-16** `_format_field_value` R5 — the "from" stage name in a `status_updated` event is read with an unscoped `status_dao.get`, so a stored row pointing at another workspace's status puts that workspace's status name in this order's log (status DAO spec FU-2). Intended: the status is read within the order's workspace; a status of another workspace shows `Status #<id>`. 🐞 BUG-2875
**Answer:** bug — per HR-16 (house rule)
- **HR-15** `_line_subtotal` R2, `create_purchase_order` R7 (narrowed in G15: `_recalc_totals` R1 and `sync_items` hold) — a line subtotal is `quantity × price` unrounded (up to 4 decimals), and the order subtotal is summed from the unrounded values while they are still in the session. The database then rounds each column on its own: lines 0.13 + 0.13 + 0.13 but total 0.38 (verified). The invoice is finalized at `total_amount`. Intended: each line subtotal is rounded half up to 2 places when computed, and the order subtotal / total is the sum of the rounded line subtotals (0.39). 🐞 BUG-2876
**Answer:** bug — per HR-15 (house rule)
- **HR-6** `list_approvers` R2 — order `assigned_at` only; ties unordered. Already logged: BUG-1200 (DAO). No new ID.
**Answer:** bug — per HR-6 (house rule), logged as BUG-1200

Checked and **not** a new line here: **HR-1/2/3** — no names; `description` and line `notes` are free text, stored as typed. **HR-4** — purchase orders, lines, approvers and events have no soft-delete column; voided is a visible state (see P6). **HR-5, HR-7, HR-8** — paging and filters live in `purchase_order.spec.md` (hub methods are pass-throughs). **HR-11 … HR-14** — no external system, no batch. **HR-16** elsewhere — every read is scoped by the caller's workspace (`get_by_id_and_workspace`, `get_by_order`); a foreign PO / line / approver is 404; supplier / invoice / line-item ids are BUG-1017; `log_event` is BUG-1192.

### Precedent matches — confirmed (reviewer delegation, 2026-11-21)

### P1. Lines accept zero or negative quantities and negative prices; the approval threshold accepts negatives — 🐞 BUG-2877 (precedent BUG-362)
**Background:** `PurchaseOrderItemCreate`, `PurchaseOrderItemUpdate`, `PurchaseOrderItemSyncUpdate` have plain `Decimal` quantity and price; `required_approvals` on create / update is a plain `int | None`. The order total is the sum of the line subtotals.
**What happens today:** `quantity_ordered: -3` with `unit_price: -2` is stored with subtotal 6.00 (verified); `0` quantity is accepted; `required_approvals: -1` makes approval "met" with nobody approving. Only confirming the items section checks that every price is > 0.
**Example:** A user adds "Bearing 6204" with quantity −3 at −2.00 on a draft PO; the order total rises by 6.00 and the draft invoice copies a line of −3.
**Rules affected:** `create_purchase_order` R5, `add_item` R4, `update_item` R7, `sync_items` R6, `approval_summary` R2
**Answer:** bug — per BUG-362 precedent: the PO schemas reject `quantity_ordered <= 0`, `unit_price < 0` and `required_approvals < 0` with 422 before anything is stored (fix in `app/schemas/purchase_order.py`; `required_approvals = 0` stays allowed, it is the explicit waiver of BUG-1202) (precedent — confirmed under reviewer delegation, 2026-11-21)

### P2. Quantities and prices with more than 2 decimals are silently rounded — 🐞 BUG-2878 (precedent BUG-021)
**Background:** quantity, price and subtotal columns hold 2 decimals; Postgres rounds anything longer when storing, after the subtotal was computed from the unrounded values.
**What happens today:** `quantity_ordered: 1.005`, `unit_price: 10` → stored quantity 1.01 and subtotal 10.05; ≥ 10^13 fails at flush (500).
**Example:** 1.005 kg at 10.00 shows as 1.01 kg with a line total of 10.05, so quantity × price disagrees with the line.
**Rules affected:** `create_purchase_order` R5, `add_item` R4, `update_item` R7, `sync_items` R6
**Answer:** bug — per BUG-021 precedent: the PO item schemas reject quantity / price with more than 2 decimal places or more than 13 integer digits (422) (precedent — confirmed under reviewer delegation, 2026-11-21)

### P3. An edit cannot clear a field — 🐞 BUG-2879 (precedent BUG-732)
**Background:** `update_purchase_order` and `update_item` drop every field sent as `null` before saving.
**What happens today:** once set, `account_id` (while the supplier is not confirmed), `order_date`, `expected_delivery_date`, `description`, `required_approvals` (null = "all assigned approvers") and a line's `unit_price` / `notes` can only be replaced, never removed (verified for `description`). `sync_items` can clear a line's price, `PUT` item cannot.
**Example:** A PO's threshold was set to 2; the buyer wants "all assigned approvers" again and sends `required_approvals: null`: nothing changes.
**Rules affected:** `update_purchase_order` R2, `update_item` R1
**Answer:** bug — per BUG-732 precedent: an explicit `null` clears `account_id`, `order_date`, `expected_delivery_date`, `description`, `required_approvals` (order) and `unit_price`, `notes` (line), subject to the existing confirm / lock guards; `destination_type`, `destination_id`, `quantity_ordered` are required columns and `null` for them is 422; omitted fields stay unchanged (precedent — confirmed under reviewer delegation, 2026-11-21)

### P4. Approving twice, or withdrawing when not approved, is recorded again — 🐞 BUG-2880 (precedent BUG-757)
**Background:** each approver row has `approved` and `approved_at`; every call writes both and logs an event.
**What happens today:** a second "Approve" moves `approved_at` to now and logs a second `approved` event; withdrawing when not approved logs `approval_withdrawn`.
**Example:** Alice approved PO-2026-014 on 1 March and clicks Approve again on 5 March: the panel shows "approved 5 March" and the log has two "Approved order" entries.
**Rules affected:** `set_approval` R6
**Answer:** bug — per BUG-757 precedent: setting the state the approver already has writes nothing and logs nothing; the row is returned unchanged (precedent — confirmed under reviewer delegation, 2026-11-21)

### P5. Approvers can be changed after the invoice is finalized or the order is complete — 🐞 BUG-2881 (precedent BUG-737 / BUG-756)
**Background:** approval gates invoice finalization. Withdrawing an approval is refused only when the order is complete, or its invoice is `locked` (a status nothing sets, BUG-2735). The sales twin refuses withdrawing once the invoice is confirmed.
**What happens today:** `add_approver` and `remove_approver` check nothing about the order's state; a withdrawal after the invoice was confirmed is accepted.
**Example:** After PO-2026-020's invoice is finalized on the strength of Bob's approval, someone removes Bob; the approvers panel now shows 0 approvals for a finalized order.
**Rules affected:** `add_approver` R6, `remove_approver` R4, `set_approval` R4
**Answer:** bug — per BUG-737 / BUG-756 precedent: `add_approver`, `remove_approver` and a withdrawal are refused with 400 when the order is complete (`Cannot change approvers — order is complete` / existing `Cannot withdraw approval — order is complete`) or its invoice is confirmed (`Cannot change approvers — invoice is finalized` / `Cannot withdraw approval — invoice is finalized`); nothing written (precedent — confirmed under reviewer delegation, 2026-11-21)

### P6. A voided purchase order can still be edited, approved, completed and given new lines — 🐞 BUG-2882 (precedent BUG-754)
**Background:** voiding (`PurchaseOrderService.void_purchase_order`) sets `voided = True`, voids / deletes the invoice and unlinks it, but leaves the section confirms and quantities. Once the invoice is unlinked the order is no longer "financially locked". No method of this manager reads `voided`.
**What happens today:** on a voided PO a user can unconfirm sections, add / change / remove lines, add / remove approvers, approve, and mark the order complete (verified: unconfirm, add line, withdraw). Re-confirming the three sections makes the service create a fresh draft invoice for the voided order.
**Example:** PO-2026-031 is voided as a duplicate. A week later someone reconfirms its sections; a new draft payable invoice appears for the supplier.
**Rules affected:** `update_purchase_order` R1a, `add_item` R1a, `update_item` R1a, `remove_item` R1a, `sync_items` R1a, `add_approver` R2a, `remove_approver` R1a, `set_approval` R1a, `mark_order_complete` R1a
**Answer:** bug — per BUG-754 precedent: a voided purchase order is read-only for these paths: each returns 400 `Purchase order is voided`, nothing written. Reads, `delete_purchase_order` and the invoice-sync helpers are unchanged (precedent — confirmed under reviewer delegation, 2026-11-21)

### P7. The activity log and the approvers list read one profile per row — 🐞 BUG-2883 (precedent BUG-1141)
**Background:** `list_events` reads the performer's profile for each entry; `list_approvers` reads a profile and a membership per approver. Neither list is paged.
**What happens today:** 500 log entries by one person take about 502 reads.
**Example:** A long-running PO with 300 entries opens its activity tab slowly; the result is right.
**Rules affected:** `list_events` R2, `list_approvers` R3
**Answer:** bug — per BUG-1141 precedent: profiles (and memberships) read together, a fixed number of reads per call, the result unchanged (precedent — confirmed under reviewer delegation, 2026-11-21)

### Already logged — rules carry the existing tag, no new ID
- **BUG-1017** — supplier `account_id`, line `item_id` (create, add item, sync) must be in the workspace; `invoice_id` is system-only and not accepted from the client. Rules: `create_purchase_order` R3, `update_purchase_order` R13, `add_item` R3, `sync_items` R7.
- **BUG-1192** — `log_event` refuses an order not in the workspace. Rule: `log_event` R2.
- **BUG-1195** — a delete leaves a `workspace_audit_logs` row. Rule: `delete_purchase_order` R5.
- **BUG-1202** — no approvers and no threshold is not "met". Rule: `approval_summary` R3.
- **BUG-1881** — stage statuses found ignoring capitals and outer spaces. Rules: `_ensure_po_stage_statuses` R1, `_resolve_po_stage_status_id` R1, `_current_stage_name` R1.
- **BUG-2631** — PO numbering is not race-free. Rule: `create_purchase_order` R1.
- **BUG-2637** — the PO found for an invoice is the lowest id. Rule: `get_po_by_invoice_id` R1.
- **BUG-2735** — invoice status `locked` is never set. Rules: `is_po_financially_locked` R2, `set_approval` R4 (the `update_item` receiving check goes with BUG-2887).
- **BUG-2789** — a return never reopens a completed PO. Rule: `reopen_for_return` R2 and *Return-in-progress state*.
- **BUG-1200** — approver ties (HR-6 line above).

### New questions

### Q1. "Invoice receiving started" is logged again on every receiving change — 🐞 BUG-2884 (superseded by BUG-2887)
**Background:** the first receipt on a PO whose invoice is confirmed sets the invoice's `receiving_started` flag (the invoice logs it once). The PO also logs `invoice_receiving_started`.
**What happens today:** the PO event is written on **every** change of a received quantity through `PUT /purchase-orders/items/{id}/` while the invoice is confirmed and anything is received, although the flag was set the first time (verified: two changes → two events).
**Example:** Three partial receipts on PO-2026-008 leave three "Invoice #41 receiving_started set after first receipt" entries.
**Rules affected:** `update_item` R16 (retired into R3)
**Answer:** bug — the PO event is written only when the invoice's flag actually changes from false to true in this call (decided by Claude under reviewer delegation, 2026-11-19)
**Resolution:** superseded by BUG-2887 (OQ-53): the line edit no longer records receiving, so the only path that logs `invoice_receiving_started` goes (receive events set the invoice flag through the service, which logs no such PO event). No rule of its own; `update_item` R16 retired into R3.

### Q2. A completed purchase order still accepts edits to its expected delivery date and approval threshold — 🐞 BUG-2885
**Background:** the owner ruled (OQ-48 refined, 2026-11-17) that while a return is open a completed order shows "return in progress" and **nothing on it is editable**, and the sales spec's RP5 relies on the existing completed-order guards for that. A completed PO's invoice is always confirmed, so supplier, destination, order date, description and lines are locked by the financial lock. `expected_delivery_date` and `required_approvals` are not covered by any guard, and `update_purchase_order` never reads the stage.
**What happens today:** `PUT /purchase-orders/{id}/` on a completed PO changes `expected_delivery_date` and `required_approvals` (verified) and logs the change.
**Example:** PO-2026-002 is completed; a return is in progress. A user changes its expected delivery date to 2030-01-01 and its threshold to 5: both are saved, so RP5 does not hold for purchase orders.
**Rules affected:** `update_purchase_order` R1b
**Answer:** bug — a completed PO (stage `Complete`, with or without an open return) refuses `update_purchase_order` with 400 `Cannot edit — purchase order is complete`, nothing written. Decided by Claude under reviewer delegation, 2026-11-19, as a direct consequence of the owner's OQ-48 refined answer ("nothing on the order is editable"); not a new owner decision.

### Q3. `GET /purchase-orders/{id}/items/` answers an empty list for a missing order — 🐞 BUG-2886
**Background:** `list_events` and `list_approvers` first check that the order exists in the workspace (404). `get_items` does not.
**What happens today:** a missing id, or another workspace's PO id, returns `[]` with 200.
**Example:** A link to PO id 9999 (deleted) opens an order page whose lines tab says "no items" instead of "not found".
**Rules affected:** `get_items` R1
**Answer:** bug — 404 `Purchase order with ID {po_id} not found`, as its siblings (decided by Claude under reviewer delegation, 2026-11-19)

### Q4. Missing stage statuses are backfilled only when `Draft` is missing — decided, no bug
**Background:** the four stage rows (`Draft`, `Planning`, `Receiving`, `Complete`) are created with each workspace. Before resolving a stage, the manager backfills them only if `Draft` is absent.
**What happens today:** in a workspace that has `Draft` but lost another stage row, moving to that stage answers 422 `Purchase order stage status '<name>' not found for this workspace` — unless the same call first passed through the workflow step, which creates any missing row.
**Example:** Someone deleted the `Planning` status; confirming a section of a draft PO answers 422.
**Rules affected:** `_ensure_po_stage_statuses` R1, `_resolve_po_stage_status_id` R2
**Answer:** intended — BUG-1220 (owner, 2026-11-02) stops stage statuses being renamed or deleted, so the case needs data made before that fix; the rule is tested as it is (decided by Claude under reviewer delegation, 2026-11-19)

### Q5. Three unreachable pieces of code — decided, remove
**Background:** (a) `approvals_met` has no caller (the invoice service calls `approval_summary`). (b) `_log_admin_field_updates` logs a `status_updated` "Changed status" event when `current_status_id` changes, but `update_purchase_order` always removes `current_status_id` from the update first. (c) `_format_scalar_value` answers `All assigned` for an empty `required_approvals`, but the threshold is always formatted by `_format_field_value`, which answers it first.
**What happens today:** none of the three can run from the API.
**Example:** —
**Rules affected:** `_log_admin_field_updates` R1, `_format_scalar_value` R1
**Answer:** remove (decided by Claude under reviewer delegation, 2026-11-19) — `purchase_order_manager.py:1507-1508` (`approvals_met`), `:798-805` (status branch), `:632-633` (`required_approvals` branch); to be added to `docs/testing/dead-code-removal-checklist.md` at apply-review. Not bugs.
**Resolution:** `approvals_met` under *Not specified*; the two branches removed from `_format_scalar_value` R1, `_log_admin_field_updates` R1 and the Branch map; all three on the removal checklist (2026-11-21).

### Q6. Creating a PO ignores the `current_status_id` and `order_workflow_id` sent — decided, intended
**Background:** `PurchaseOrderCreate` carries both fields; the stage and workflow are the system's (BUG-1223 made the purchase workflow system-managed).
**What happens today:** both are replaced by the workspace's `Draft` status and purchase workflow, without an error.
**Example:** A client sends `current_status_id: 4` (Complete); the order is created as Draft.
**Rules affected:** `create_purchase_order` R2
**Answer:** intended — the system owns the stage; dropping the two fields from the create schema is a clean-up for the schema spec, not a bug (decided by Claude under reviewer delegation, 2026-11-19)

### Q7. A duplicate line on create is refused after the order was already written — decided, no bug here
**Background:** `create_purchase_order` writes the order, the creator's approver row and the `created` event, then checks for the same catalog item twice.
**What happens today:** the 409 leaves those rows flushed in the session; the caller must roll back. `PurchaseOrderService.create_purchase_order` re-raises an `HTTPException` without calling its rollback (its `except HTTPException: raise`), so only the request's session close discards them.
**Example:** A create with "Bolt M10" twice answers 409; nothing is saved in practice.
**Rules affected:** `create_purchase_order` R4
**Answer:** intended for the manager (the caller rolls back, TC3); the missing rollback is the service's, noted as FU-3 (decided by Claude under reviewer delegation, 2026-11-19)

### Q8. `remove_item` does not refuse a line that has been received, unlike `sync_items` — decided, no bug
**Background:** `sync_items` refuses to remove a received line; `remove_item` relies on the items lock (items confirmed, or invoice finalized), and receiving needs a finalized invoice.
**What happens today:** a received line can be removed only once the lock is gone, which today needs a voided order (P6).
**Example:** On a voided PO with unconfirmed items, a line that received 5 can be removed.
**Rules affected:** `remove_item` R2
**Answer:** intended — unreachable once BUG-2882 makes voided orders read-only; no separate bug (decided by Claude under reviewer delegation, 2026-11-19)

### OQ-PO-1 (OQ-53). `PUT /purchase-orders/items/{id}/` can change a received quantity without moving any stock — 🐞 BUG-2887 (OQ-53)
**Background:** goods are received through receive events (`POST /purchase-orders/{id}/receive-events/`): each one is recorded, adds the stock at the order's factory or machine, refuses a completed or voided order, refuses going below zero or above ordered − refunded, and logs one entry. The line-edit endpoint `PUT /purchase-orders/items/{id}/` also accepts `quantity_received`. The web app's live screens never send it (only an unused mock-up screen did); it is reachable through the API.
**What happens today:** through `PUT`, once the invoice is finalized, a received quantity can be set to anything up to the ordered quantity — negative included — on completed orders too. No stock moves, no receive record is made, refunded quantity is not counted. Verified: −5 stored.
**Example:** PO-2026-040 ordered 100 cement bags; 60 were received properly, so storage shows 60. Someone sets the line to 100 through `PUT`. The order now says 100 received and can be marked complete; storage still shows 60; nothing explains the 40.
**Rules affected:** `update_item` R2–R3, R5, R9, R12–R17
**Recommended answer:** bug — remove `quantity_received` from the line edit: a `PUT` that sends it is refused with 422; received quantities change only through receive events. The receiving rules of `update_item` (R12–R17) then go.
**Options to ask the owner:**
- **Recommended — receiving only through "Receive goods".** The line edit can change only what was ordered and its price. Receiving goods always goes through the receive step, which updates stock and keeps a record of who received what. *Example:* someone tries to set the cement line to 100 received through the edit screen or the API; it is refused, and they must record the 40 bags through "Receive goods", which adds them to storage.
- **(a) Keep the edit, but make it do the same as "Receive goods".** Changing the received number through the edit moves stock and leaves a receive record, with the same checks. *Example:* setting the cement line from 60 to 100 adds 40 bags to storage and records a receipt of 40; setting it to −5 is refused.
- **(b) Leave it as it is.** The edit stays a manual correction that changes the number only. *Example:* the cement line says 100 received while storage says 60; someone must fix storage by hand, and the order can be closed with 40 bags missing.
**Answer:** owner, 2026-11-21 (OQ-53): recommended answer — receiving happens only through "Receive goods"; the line edit can change only the quantity ordered, the price and the notes; `quantity_received` is refused there.
**Resolution:** BUG-2887. A line edit that sends `quantity_received` (any value, also the stored one) is refused with 422, nothing written (fix in `PurchaseOrderItemUpdate`: the field goes and is refused, not ignored). The receiving rules of the line edit go. Rules: `update_item` R2, R3, R4, R9 (R10–R17 retired into R3); RP5 (PO).

### OQ-PO-2 (OQ-54). Deleting a purchase order whose invoice is finalized leaves the invoice behind — 🐞 BUG-2888 (OQ-54)
**Background:** a purchase order can be deleted while nothing has been received. Its invoice is a separate record; the order points to the invoice, not the other way round. A finalized invoice can carry payments.
**What happens today:** deleting a PO with a confirmed (or draft) invoice deletes the order, its lines, approvers and log; the invoice stays as it was, still `confirmed`, still owed, still naming the deleted order (verified). Payments recorded on it stay.
**Example:** PO-2026-044 for 50,000.00 is finalized and 10,000.00 is paid in advance; the supplier then cancels before delivery and the buyer deletes the PO. The 50,000.00 payable invoice stays in the supplier's account with 40,000.00 "outstanding" and no order behind it.
**Rules affected:** `delete_purchase_order` R4
**Recommended answer:** bug — a PO whose invoice is confirmed (anything but draft or voided) cannot be deleted: 400 `Cannot delete a purchase order with a finalized invoice — void the order instead`, nothing written. A **draft** invoice is deleted together with the order.
**Options to ask the owner:**
- **Recommended — finalized invoice blocks delete; a draft goes with the order.** Once an invoice is finalized the order can only be voided, which also voids the invoice and cancels its payments in one step and keeps the record. A draft invoice (never sent, no money) is simply removed with the order. *Example:* PO-2026-044 can't be deleted; the buyer voids it, so the 50,000.00 invoice is voided too and the 10,000.00 advance is shown as cancelled and needs a refund. A draft PO with a draft invoice is deleted and the draft invoice disappears with it.
- **(a) Any linked invoice blocks delete, draft included.** The user must delete the draft invoice first, then the order. *Example:* deleting a draft PO with a draft invoice answers "delete or void the invoice first".
- **(b) Leave it as it is.** The invoice stays after the order is gone. *Example:* the supplier's account keeps a 50,000.00 bill with no order, and someone in accounts must notice and void it by hand.
**Answer:** owner, 2026-11-21 (OQ-54): recommended answer — a finalized invoice blocks delete (the order can only be voided); a draft invoice is removed together with the order.
**Resolution:** BUG-2888. Rules: `delete_purchase_order` R3a, R4, R4a.

## Overview
`PurchaseOrderManager` owns the purchase-order aggregate: the order, its lines, approvers and activity log. It creates orders (numbered per workspace and year), edits them through four confirmable sections (supplier, details, items, draft invoice), works out the order's stage (`Draft` → `Planning` → `Receiving` → `Complete`) from its state, marks it complete, keeps the denormalised `paid` flag in step with the linked invoice, unlinks an invoice that was deleted or voided, runs approvals, and deletes orders that never received anything. Callers: `PurchaseOrderService` (all `/purchase-orders/…` endpoints), `AccountInvoiceService` (confirm, void, delete, resync), `InvoicePaymentManager` (`sync_po_for_linked_invoice`), `AttachmentManager` (`log_event`). It never commits; every write is flushed.

Invariants it is meant to protect: once the invoice is finalized the supplier, details and line structure are locked (receiving stays allowed); approval needs the three base sections confirmed; completion needs every line received + refunded ≥ ordered and no open return; `Complete` is never derived away; a PO with receiving history is never deleted.

**Callables:** 62 specified (some grouped under one heading) · 3 not specified
**Externals to mock:** none of the listed externals. Time: `date.today()` in this module (`order_date` default, `actual_delivery_date`) — patch `app.managers.purchase_order_manager.date`; `utcnow` imported into this module (`approved_at`) — patch `app.managers.purchase_order_manager.utcnow`; model defaults (`created_at`, `assigned_at`) use `app.utils.time.utcnow`. `allocate_po_number` reads the year inside `app/dao/purchase_order.py` (its spec).
**Integration-only behavior:** the race half of BUG-2872 (HR-10) and BUG-2631 — two sessions are needed; at unit level only the single-session state checks are tested, the lock rules are strict xfail.

**Notes for the test designer:**
- Stage rows: `statuses` named exactly `Draft`, `Planning`, `Receiving`, `Complete` in the workspace (`ensure_po_stage_statuses` creates missing ones; the first create in a new workspace does so). The purchase workflow is `order_workflows` with `type = 'purchase'`.
- `PurchaseOrder.order_completed` and `current_status_name` read the `current_status` **relationship**, which is not refreshed when `current_status_id` changes in the same session. After a stage change in a test, `session.expire(po)` (or use `_current_stage_name`) before reading them. `set_approval`'s withdraw check reads `order_completed` from the order it re-reads (same identity-map object).
- Invoices: `account_invoices` (`invoice_status` `draft` / `confirmed` / `voided`; `locked` never written, BUG-2735; `payment_status` `unpaid` / `partial` / `paid` / `overdue`). Returns: `purchase_order_returns.status` `pending` / `completed` / `voided`; "open return" = `pending` (`PurchaseOrderReturnManager.has_open_return`).
- Receive events: `po_receive_events` (`purchase_order_id`, `workspace_id`); any row blocks delete.
- `purchase_order_items.quantity_received`, `quantity_refunded` are NOT NULL (default 0), so the "None counts as 0" clauses are reachable only on in-memory objects (`_quantity_received_decimal` R1, `_all_items_fully_received` R2).
- Approver / member profiles cannot be missing (FK cascade): the `User #<id>` fallbacks of `add_approver` R5 / `remove_approver` R3 are not set up through the database.
- Line names in events: `item_name` comes from the joined `items` row; a line whose item is gone cannot exist (FK RESTRICT).
- Decimal rendering in event texts: `_format_scalar_value` R4 (integral → `"5"`, else normalized `"1.5"`); `update_item`'s own `_qty` is the same rule.
- **Return values (fact, G7):** these return `None`: `delete_purchase_order`, `remove_approver`, `unlink_invoice_from_po`, `unconfirm_sections_after_invoice_void`, `reset_approvals`, `apply_post_invoice_confirms`, `_recalc_totals`, `sync_po_for_linked_invoice`, `_ensure_po_stage_statuses`, `_log_field_change_event`.
- **`_resolve_po_workflow_id` R2 (test mechanics, G5):** no database state reaches it with today's schema: `order_workflows` has a unique `(workspace_id, type)` and no soft delete, so the seed returns none only when its insert raises `IntegrityError` and the re-read then finds no row. Test it by patching `app.managers.purchase_order_manager.ensure_po_workflow_record` to return `None`; the call then raises per `_raise_po_workflow_setup_error` R1 (both messages, with and without another workspace's `purchase` workflow).
- **Check order after the fixes (decided under the reviewer's delegation, 2026-11-21, G4):** in every write the checks run in this order, and the first failure wins: (1) the order / line exists in the workspace (404); (2) voided (400, BUG-2882); (3) completed (400, `update_purchase_order` R1b); (4) the financial-lock / section-confirm guards (400); (5) the new reference checks — supplier, destination, each catalog item, in the order the fields appear in the request (404, BUG-1017 / BUG-2874); (6) the duplicate-item check (409); (7) the confirm checks of `_validate_section_confirm` (400). All of (1)–(5) run before anything is written. So a foreign `item_id` that is also a duplicate answers 404, and a foreign `account_id` on a supplier-confirmed order answers 400 `Supplier is confirmed`. After BUG-1017 every line's item resolves in the workspace, so the `Item #<id>` name fallback of `create_purchase_order` R4 and `_ensure_catalog_item_not_on_po` R1 is reachable only through a line stored before the fix with another workspace's item (old data); test it on `_ensure_catalog_item_not_on_po` only.
- **`delete_purchase_order` takes a required `user_id` (G13, BUG-1195 / BUG-1193 precedent):** signature `delete_purchase_order(session, po_id, workspace_id, user_id)`; every delete case passes it.

## Not specified
- `PurchaseOrderManager.__init__` — wires the DAOs, no logic.
- `PurchaseOrderManager.list_purchase_orders` — dead code, already on the removal checklist (`purchase_order.spec.md` Q1).
- `PurchaseOrderManager.approvals_met` — dead code, to be removed (reviewer delegation, Q5; on the removal checklist).
- `_format_scalar_value` `required_approvals` → `All assigned` branch (`:632-633`) and `_log_admin_field_updates` status branch (`:798-805`) — dead code, to be removed (Q5; on the removal checklist).

---

## `_parse_unit_price(value)`
**Shape:** helper · **Persistence:** pure · **Visibility:** internal (used by: create, add, update, sync of lines)
**Purpose:** turn an optional price into a `Decimal`.
**Rules:**
- **R1.** `None` → `None`. Anything else → `Decimal(str(value))` (a `Decimal('5.00')` stays `5.00`; `0` → `Decimal('0')`, not `None`).

## `_line_subtotal(qty, price)`
**Shape:** compute · **Persistence:** pure · **Visibility:** internal
**Rules:**
- **R1.** `price is None` → `None` (an unpriced line has no subtotal and adds 0 to the order).
- **R2.** [BUG-2876] Otherwise `qty × price` rounded half up to 2 places (`1.25 × 0.10` → `0.13`; `0.5 × 0.25` → `0.13`). *(Today: unrounded, `0.1250`; the database rounds it half up when stored, but the order total is summed from the unrounded value.)*

## `_all_items_have_positive_unit_price(items)`
**Shape:** validator · **Persistence:** pure · **Visibility:** internal (used by: `_validate_section_confirm`)
**Rules:**
- **R1.** Empty list → `False`.
- **R2.** `True` only when every line has a price and the price is `> 0`; one unpriced or `0.00` line → `False`.

---

## `PurchaseOrderManager.get_po_by_invoice_id(session, invoice_id, workspace_id)`
**Shape:** get · **Persistence:** reads · **Visibility:** public (used by: `AccountInvoiceService` delete / confirm / void, `sync_po_for_linked_invoice`)
**Rules:**
- **R1.** Returns the workspace's purchase order whose `invoice_id` is the given id, or `None`. [BUG-2637] When two orders share the invoice, the lowest `id` is returned. *(Today: arbitrary.)* Another workspace's order is never returned.

## `PurchaseOrderManager.is_po_financially_locked(session, po)`
**Shape:** compute · **Persistence:** reads · **Visibility:** public (used by: update / item guards here, `PurchaseOrderService._sync_draft_invoice_for_po`)
**Purpose:** "the invoice is finalized, so the order's money fields are locked".
**Rules:**
- **R1.** No `invoice_id` → `False`. An invoice id that does not exist in the order's workspace (missing, or another workspace's) → `False`.
- **R2.** `True` when the invoice's status is `confirmed` or `locked` [BUG-2735: `locked` is never written; decided with the BUG-2730 fix]; `draft` or `voided` → `False`.

## `PurchaseOrderManager.unlink_invoice_from_po(session, po, user_id, reason, event_type='invoice_unlinked', extra_metadata=None)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: invoice delete / void in `AccountInvoiceService`, `PurchaseOrderService` void and draft-invoice removal)
**Rules:**
- **R1.** Sets `invoice_id = None`, `invoice_confirmed = False`, `paid = False`, flushed. `invoice_ever_linked`, the other three section confirms and the stage are unchanged. Called on an order with no invoice it still writes and logs (old id `None`).
- **R2.** Logs one event of `event_type` with description `reason`, `performed_by = user_id`, metadata `{"invoice_id": <old id>}` plus every key of `extra_metadata` (which wins on a clash); `extra_metadata` `None` or `{}` adds nothing.

## `PurchaseOrderManager.unconfirm_sections_after_invoice_void(session, po, workspace_id, user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (used by: `AccountInvoiceService.void_invoice`)
**Rules:**
- **R1.** For `supplier_confirmed` then `items_confirmed`: each that is `True` becomes `False` and logs `supplier_unconfirmed` / `Supplier unconfirmed` or `items_unconfirmed` / `Order items unconfirmed` (performer `user_id`). `details_confirmed` and `invoice_confirmed` are not touched. Approvals are not reset here.
- **R2.** If at least one changed: flush, then the stage is re-derived (`sync_po_stage`). If neither was set: nothing written, no event, no stage sync.

## `PurchaseOrderManager.reset_approvals(session, po_id, workspace_id, user_id, reason='Cleared approvals after invoice voided')`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `update_purchase_order`, invoice void, PO void, draft-invoice resync)
**Rules:**
- **R1.** Every approver of the order in the workspace with `approved = True` gets `approved = False`, `approved_at = None`; rows not approved are untouched; approver rows are never deleted.
- **R2.** If n ≥ 1 rows were reset: flush and one event `approvals_reset`, description `<reason> (<n> approval(s) cleared)`. If none: nothing written, no event. The order itself is not checked (an id of no order resets nothing).

## `PurchaseOrderManager._ensure_po_stage_statuses(session, workspace_id)`
**Shape:** helper · **Persistence:** writes · **Visibility:** internal (used by: `_resolve_po_stage_status_id`, `_resolve_po_workflow_id`)
**Rules:**
- **R1.** If the workspace has no status named exactly `Draft`, the four stage statuses are created (any missing one, with its fixed comment), flushed. If `Draft` exists nothing is done, even when another stage is missing (Q4, decided). [BUG-1881] Stage names are matched ignoring capitals and outer spaces, and an existing differently spelled row is reused instead of inserted. *(Today: exact spelling.)*

## `PurchaseOrderManager._raise_po_workflow_setup_error(session, workspace_id)`
**Shape:** helper · **Persistence:** reads · **Visibility:** internal (used by: `_resolve_po_workflow_id`)
**Rules:**
- **R1.** Always raises 422. If any **other** workspace has a `purchase` workflow: detail `Purchase order workflow requires database migration 022_po_stage_workflow. Run: alembic upgrade head`. Otherwise: `Purchase order workflow is not configured for this workspace`.

## `PurchaseOrderManager._resolve_po_stage_status_id(session, workspace_id, stage_name)`
**Shape:** get · **Persistence:** writes (backfill) · **Visibility:** internal (used by: `sync_po_stage`, `mark_order_complete`, `reopen_for_return`, `create_purchase_order`)
**Rules:**
- **R1.** Backfills per `_ensure_po_stage_statuses`, then returns the id of the workspace's status named `stage_name` (first match; [BUG-1881] name matched ignoring capitals and outer spaces).
- **R2.** None found → 422 `Purchase order stage status '<stage_name>' not found for this workspace`.

## `PurchaseOrderManager._resolve_po_workflow_id(session, workspace_id)`
**Shape:** get · **Persistence:** writes · **Visibility:** internal (used by: `sync_po_stage`, `create_purchase_order`)
**Rules:**
- **R1.** Ensures the stage statuses exist (all four are created if missing, through the workflow seed) and the workspace's `purchase` workflow exists with `status_sequence` = the four stage ids in order (an existing row's sequence is overwritten; a missing row is created, named `Purchase Order`); returns its id.
- **R2.** If the workflow still cannot be had (the seed returns none) → `_raise_po_workflow_setup_error` R1.

## `PurchaseOrderManager._all_items_fully_received(items)`
**Shape:** compute · **Persistence:** pure · **Visibility:** internal (used by: `mark_order_complete`)
**Rules:**
- **R1.** Empty list → `False`.
- **R2.** `True` when every line has received + refunded ≥ ordered (`None` received or refunded counts 0). Over-receipt counts as done.

## `PurchaseOrderManager._current_stage_name(session, workspace_id, status_id)`
**Shape:** get · **Persistence:** reads · **Visibility:** internal
**Rules:**
- **R1.** The name of the status with that id **in the workspace**, exactly as stored (no trimming or case change); a status of another workspace, a missing id or `None` → `None`. BUG-1881 does not change this rule: the stored name is compared by `_is_po_complete_stage` R1a.

## `PurchaseOrderManager._invoice_payment_status(session, po)`
**Shape:** get · **Persistence:** reads · **Visibility:** internal (used by: `sync_po_paid`)
**Rules:**
- **R1.** No `invoice_id`, or an invoice not in the order's workspace → `None`; else the invoice's `payment_status`.

## `PurchaseOrderManager.sync_po_for_linked_invoice(session, invoice_id, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `InvoicePaymentManager` after a payment change)
**Rules:**
- **R1.** Finds the order per `get_po_by_invoice_id` R1 and applies `sync_po_paid`; no such order → nothing written.

## `PurchaseOrderManager.sync_po_paid(session, po, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `sync_po_for_linked_invoice`, `mark_order_complete`)
**Rules:**
- **R1.** Target `paid` = `True` only when the order has an invoice in its workspace whose `payment_status` is exactly `paid`; no invoice, a foreign invoice, `partial`, `overdue`, `unpaid` → `False`.
- **R2.** Target equals the current `paid` → returns `False`, nothing written, no event.
- **R3.** Otherwise sets `paid`, flushes, logs `payment_status_synced` / `Order marked paid from linked invoice` (or `… unpaid …`), metadata `{"paid": <bool>}`, performer `user_id` (may be `None`); returns `True`.

## `PurchaseOrderManager._is_po_complete_stage(stage_name)`
**Shape:** compute · **Persistence:** pure · **Visibility:** internal
**Rules:**
- **R1.** `True` for `Complete`; `None`, `Receiving`, `Completed`, `""` → `False`.
- **R1a.** [BUG-1881] (owner, OQ-13) The name is compared ignoring capitals and outer spaces: `complete`, ` COMPLETE `, `Complete ` → `True`. So an order whose stage row is spelled `complete` counts as completed everywhere this helper is read (`sync_po_stage` R1 keeps it, `mark_order_complete` R2 returns it unchanged, `reopen_for_return` R1/R2, `set_approval` R3). *(Today: only exactly `Complete`; `complete` → `False`.)*

## `PurchaseOrderManager._derive_po_stage_name(session, po, items)`
**Shape:** compute · **Persistence:** reads · **Visibility:** internal (used by: `sync_po_stage`)
**Rules** (first match wins):
- **R1.** Any line with received > 0 → `Receiving` (a negative received does not count).
- **R2.** Else the order is financially locked (`is_po_financially_locked`) → `Receiving`.
- **R3.** Else any of supplier / details / items confirmed → `Planning` (`invoice_confirmed` alone does not count).
- **R4.** Else `Draft`. Never `Complete`.

## `PurchaseOrderManager.sync_po_stage(session, po, workspace_id, user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (used by: every write here; `PurchaseOrderService.get_purchase_order` and list pages with `user_id = None`; `AccountInvoiceService.confirm_invoice`)
**Purpose:** put the stored stage in line with the order's state.
**Rules:**
- **R1.** If the current stage (read per `_current_stage_name`) is `Complete`, the target is `Complete` whatever the lines say — also after a return lowers a received quantity or replacement goods are received through the return (BUG-2810: the PO stays `Complete`). Otherwise the target is `_derive_po_stage_name`.
- **R2.** The workflow is resolved per `_resolve_po_workflow_id` (sequence rewritten); if the order's `order_workflow_id` differs it is set.
- **R3.** If `current_status_id` differs from the target's id: it is set and one event `status_updated` / `Stage updated to <target>` is logged, metadata `changes = [{"field": "current_status_id", "label": "Status", "from_value": <old name per _format_field_value R5>, "to_value": <target>}]`, performer `user_id` (may be `None`).
- **R4.** Returns `True` (flushed) if the workflow id or the stage changed, else `False` with no event. A failed stage lookup raises per `_resolve_po_stage_status_id` R2 before anything is set.
- **R4a.** (fact, G12) The target's stage row is looked up **before** the workflow is resolved (R2). The lookup backfills only when `Draft` is missing (`_ensure_po_stage_statuses` R1, Q4). So with `Draft` present and `Planning` missing: a target of `Planning` raises 422 and the workflow is not touched; a target of `Draft` succeeds and the workflow step (R2) then creates every missing stage row, `Planning` included.

## `PurchaseOrderManager.mark_order_complete(session, po_id, workspace_id, user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST /purchase-orders/{id}/complete/`)
**Rules:**
- **R1.** Order not in the workspace → 404 `Purchase order with ID {po_id} not found`.
- **R1a.** [BUG-2882] A voided order → 400 `Purchase order is voided`, nothing written. *(Today: not checked.)*
- **R2.** Already `Complete` → returns the order unchanged: nothing written, no event (no paid sync).
- **R3.** Not every line done per `_all_items_fully_received` (an order with no lines included) → 400 `All line items must be fully received before marking the order complete`.
- **R4.** An open (`pending`) return on the order → 400 `Complete all open returns before marking the order complete`. R3 is checked before R4.
- **R5.** Otherwise: stage `Complete`, `updated_by = user_id`, `actual_delivery_date` = today if empty (an existing date is kept); flushed. Then `sync_po_paid` (R1–R3 there), the stage sync (stays `Complete`, no `status_updated` event), and one event `order_completed` / `Order marked complete`. Returns the order. The invoice need not be paid; approvals are not read.
- **R6.** [BUG-2872] The order row is read `FOR UPDATE` before R2–R4 (HR-10). *(Today: plain read.)*

## `PurchaseOrderManager.reopen_for_return(session, po, workspace_id, user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (used by: `PurchaseOrderService.start_return`)
**Rules:**
- **R1.** Order not `Complete` → returns `False`, nothing written.
- **R2.** [BUG-2789] (owner, OQ-48, refined 2026-11-17) A completed order stays completed: stage `Complete`, `actual_delivery_date` and `updated_by` unchanged, no event; returns `False`. Its invoice stays frozen (F2 reads only the stage) and while the return is open the order shows "return in progress", per the shared section below. *(Today: stage → `Receiving`, `actual_delivery_date = None`, `updated_by = user_id`, event `order_reopened` / `Order reopened — a new return was started`; returns `True`. Verified.)* The fix may instead drop the call from `start_return`; the outcome is the same.

## Shared: Return-in-progress state — purchase orders (owner OQ-48 refined, 2026-11-17)
This manager follows `sales_manager.spec.md` **RP1–RP7** with purchase-order names; they are not restated. PO specifics:
- **RP1 (PO).** "Stored completion" = stage `Complete` and `actual_delivery_date`. Starting, completing or cancelling a return never changes them (`reopen_for_return` R2).
- **RP2 (PO).** `has_open_return` = `PurchaseOrderReturnManager.has_open_return(po id, workspace)`. *(Requires new: `PurchaseOrderResponse.has_open_return: bool`, filled by the service; not this manager.)*
- **RP5 (PO) — the guards that keep a completed PO uneditable:** supplier, details and line structure by the financial lock (a completed PO's invoice is confirmed and, after BUG-2730, cannot be reverted or voided); approval withdrawal (`set_approval` R4); adding / removing approvers (`add_approver` R6, `remove_approver` R4 [BUG-2881]); receive events ("Cannot receive against a completed purchase order", service); `update_purchase_order` R1b [BUG-2885] for the fields no lock covers. The line-edit receiving path is closed by [BUG-2887] (OQ-53): `update_item` R3 refuses `quantity_received` on every order.
- **BUG-2810 (owner, 2026-11-19).** Replacement goods for a `replace` return come in through the return's own step (`PurchaseOrderReturnManager.validate_replacement_receipt`, service `receive_replacements`): the PO stays `Complete` (`sync_po_stage` R1), its invoice frozen; the service logs one PO event `return_replacement_received` through `log_event`. No rule of this manager changes.

## `PurchaseOrderManager.create_purchase_order(session, data, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /purchase-orders/`)
**Inputs:** `PurchaseOrderCreate` — `account_id?`, `destination_type` (str, required), `destination_id` (int, required), `order_date?`, `expected_delivery_date?`, `description?`, `current_status_id?`, `order_workflow_id?`, `required_approvals?`, `items?` (each `item_id`, `quantity_ordered`, `unit_price?`, `notes?`). No length, range or format checks; `destination_type` is free text (BUG-681).
**Returns:** the order, flushed, with lines.
**Rules:**
- **R1.** `po_number` per `allocate_po_number` (`PO-<year>-<nnn>`, per workspace; `purchase_order.spec.md`). [BUG-2631] Two creates at once both succeed with distinct numbers. *(Today: the second fails on `uq_po_workspace_number`; the service retries up to 5 times.)*
- **R2.** Stage `Draft` and the workspace's purchase workflow, whatever `current_status_id` / `order_workflow_id` were sent (Q6, intended). `created_by = user_id`; `order_date` = today when not sent (or falsy). Other fields as sent; `subtotal`, `total_amount` per R7.
- **R3.** [BUG-1017] `account_id` and each line `item_id` must exist in the workspace, else 404 `<Thing> with ID {id} not found`, nothing written. [BUG-2874] `destination_id` must be a live factory (`storage`) / live machine (`machine`) of the workspace, else 404 `Factory with ID {id} not found` / `Machine with ID {id} not found`. *(Today: all stored as sent; verified for a foreign machine.)* A `project` destination: the id is stored as sent today — *revisit after launch*.
- **R4.** The same catalog item twice in `items` → 409 `<name> appears more than once on this order` (name from the workspace's item, else `Item #<id>`). It is raised **after** the order, the approver row and the `created` event were flushed (Q7; the caller rolls back).
- **R5.** Lines are numbered 1, 2, … in the order sent, `quantity_received = 0`, price per `_parse_unit_price`, subtotal per `_line_subtotal`. [BUG-2877] / [BUG-2878] range and decimals refused by the schema (P1, P2). *(Today: accepted.)*
- **R6.** The creator is added as an approver (`assigned_by` = creator, not approved) and one event `created` / `Order created` is logged.
- **R7.** `subtotal = total_amount` = sum of the line subtotals (unpriced lines 0; no lines → 0). [BUG-2876] Sum of the rounded line subtotals. *(Today: sum of unrounded; three lines 1.25 × 0.10 store a total of 0.38 next to lines of 0.13.)*
- **R8.** Ends with `sync_po_stage` (a new order stays `Draft`; no stage event).

## `PurchaseOrderManager.update_purchase_order(session, po_id, data, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (`PUT /purchase-orders/{id}/`, `PATCH /purchase-orders/{id}/section-confirm/`)
**Inputs:** `PurchaseOrderUpdate` — every field optional: `account_id`, `destination_type`, `destination_id`, `order_date`, `expected_delivery_date`, `current_status_id`, `invoice_id`, `required_approvals`, `description`, `supplier_confirmed`, `details_confirmed`, `items_confirmed`, `invoice_confirmed`.
**Rules:**
- **R1.** Order not in the workspace → 404 `Purchase order with ID {po_id} not found`.
- **R1a.** [BUG-2882] Voided → 400 `Purchase order is voided`, nothing written. *(Today: accepted, verified.)*
- **R1b.** [BUG-2885] Stage `Complete` → 400 `Cannot edit — purchase order is complete`, nothing written. *(Today: `expected_delivery_date`, `required_approvals` (and `invoice_id`) are saved; verified.)*
- **R2.** Only fields sent and not `null` are applied. [BUG-2879] An explicit `null` clears the clearable fields (P3). *(Today: dropped.)* `current_status_id` is always ignored (stage is derived).
- **R3.** Financially locked: sending `supplier_confirmed: false` → 400 `Cannot unconfirm supplier after invoice is confirmed`; `details_confirmed: false` → `Cannot unconfirm order details after invoice is confirmed`; `items_confirmed: false` → `Cannot unconfirm order items after invoice is confirmed`; `invoice_confirmed: false` → `Cannot unconfirm draft invoice after invoice is finalized`. Checked in that order; `true` values pass here.
- **R4.** `account_id` sent (even unchanged) while locked → 400 `Confirmed after invoice creation`; while not locked but `supplier_confirmed` is stored `True` → 400 `Supplier is confirmed` (sending `supplier_confirmed: false` in the same request does not help).
- **R5.** Any of `destination_type`, `destination_id`, `order_date`, `description` sent while locked → 400 `Confirmed after invoice creation`; while not locked but `details_confirmed` stored → 400 `Order details are confirmed`. `expected_delivery_date` and `required_approvals` are never blocked by this (see R1b).
- **R6.** Confirming checks, per `_validate_section_confirm` R1–R4.
- **R7.** For each of supplier, details, items, invoice confirm sent with a value different from the stored one: event `<section>_confirmed` / `<Label> confirmed` or `<section>_unconfirmed` / `<Label> unconfirmed` (sections `supplier`, `details`, `items`, `invoice`; labels `Supplier`, `Order details`, `Order items`, `Draft invoice`). Sending the stored value logs nothing. If any section became unconfirmed: `reset_approvals` with reason `Section unconfirmed`.
- **R8.** Field-change events: `supplier_updated` / `Changed supplier` for an `account_id` change; `details_updated` / `Changed order details` listing each changed field of destination type, destination, order date, expected delivery, description; `approvals_threshold_updated` / `Changed approval threshold` for `required_approvals`. Each carries `changes` per `_collect_field_changes`. Unchanged values log nothing.
- **R9.** All accepted fields are written (confirm flags included) and flushed; then `sync_po_stage`. Returns the order.
- **R10.** Refusals in R1–R6 write nothing and log nothing.
- **R11.** [BUG-2873] `updated_by = user_id` only when at least one field changes value. *(Today: always, an empty body included; verified.)*
- **R12.** [BUG-2874] A changed `destination_id` (storage / machine) must be a live row of the workspace of the (new or kept) type, as `create_purchase_order` R3. *(Today: stored as sent.)*
- **R13.** [BUG-1017] `account_id` must be in the workspace (404); `invoice_id` is not accepted from the client (R13a). *(Today: both stored as sent; a sent `invoice_id` that is confirmed makes the order financially locked at once.)*
- **R13a.** [BUG-1017] A body that sends `invoice_id` (any value, `null` included) is refused with 422 by `PurchaseOrderUpdate`, before the manager runs; nothing written (decided under the reviewer's delegation, 2026-11-21, G3: refused, not silently dropped, as OQ-26 and BUG-2887). *(Today: stored as sent.)*
- **R14.** [BUG-2872] Read `FOR UPDATE` before R3–R7.

## `PurchaseOrderManager._format_scalar_value(field, value)`
**Shape:** mapper · **Persistence:** pure · **Visibility:** internal
**Rules:**
- **R1.** `None` → `—` (every field).
- **R2.** A `date` → ISO `YYYY-MM-DD`.
- **R3.** A `Decimal` with no fraction → integer text (`5.00` → `5`); otherwise normalized (`1.50` → `1.5`).
- **R4.** Anything else → `str(value)` trimmed; empty after trimming → `—`.

## `PurchaseOrderManager._format_destination_id(session, workspace_id, destination_type, destination_id)`
**Shape:** mapper · **Persistence:** reads · **Visibility:** internal
**Rules:**
- **R1.** `destination_id` `None` → `—`.
- **R2.** Type (case-insensitive) `storage` → the workspace's factory name, else `Factory #<id>`; `machine` → machine name, else `Machine #<id>`; `project` → project component name, else `Project component #<id>` (*revisit after launch*); any other type or `None` → `#<id>`. Another workspace's row gives the fallback text. A soft-deleted factory / machine still shows its name.

## `PurchaseOrderManager._format_field_value(session, workspace_id, field, value, *, destination_type=None)`
**Shape:** mapper · **Persistence:** reads · **Visibility:** internal
**Rules:**
- **R1.** `account_id`: `None` → `—`; the workspace's account name, else `Account #<id>`.
- **R2.** `destination_type`: empty / `None` → `—`; `storage` / `machine` / `project` (any case) → `Storage` / `Machine` / `Project`; other text as given.
- **R3.** `destination_id` → `_format_destination_id` with the given `destination_type`.
- **R4.** `required_approvals`: `None` → `All assigned`; else the number as text.
- **R5.** `current_status_id`: `None` → `—`; the status's name, else `Status #<id>`. [BUG-2875] Read within the workspace; a status of another workspace → `Status #<id>`. *(Today: unscoped read, shows the other workspace's name.)*
- **R6.** Any other field → `_format_scalar_value`.

## `PurchaseOrderManager._collect_field_changes(session, workspace_id, record, update_dict, fields)`
**Shape:** mapper · **Persistence:** reads · **Visibility:** internal
**Rules:**
- **R1.** For each field of `fields` (in the dict's order) present in `update_dict` whose new value differs from the stored one: `{"field", "label", "from_value", "to_value"}` with both values per `_format_field_value`. A destination id is formatted with the stored type for "from" and the new (or kept) type for "to". Absent or equal fields give nothing; `[]` when nothing changed. Labels (fact, G2): `account_id` → `Supplier`; `destination_type` → `Destination type`; `destination_id` → `Destination`; `order_date` → `Order date`; `expected_delivery_date` → `Expected delivery`; `description` → `Description`; `required_approvals` → `Approval threshold`; `current_status_id` → `Status`.

## `PurchaseOrderManager._collect_item_field_changes(record, update_dict)`
**Shape:** mapper · **Persistence:** pure · **Visibility:** internal
**Rules:**
- **R1.** Same as `_collect_field_changes` R1 for `quantity_ordered` (`Quantity ordered`), `unit_price` (`Unit price`), `notes` (`Notes`), values per `_format_scalar_value`. Equality is numeric (`5` equals `5.00`). `quantity_received` is never listed.

## `PurchaseOrderManager._log_field_change_event(session, po_id, workspace_id, user_id, event_type, description, changes, extra_metadata=None)`
**Shape:** event-log · **Persistence:** writes · **Visibility:** internal
**Rules:**
- **R1.** One event per `log_event` with metadata `{"changes": changes}` plus `extra_metadata` keys.

## `PurchaseOrderManager._log_section_field_updates(...)` / `_log_admin_field_updates(...)`
**Shape:** event-log · **Persistence:** writes · **Visibility:** internal (used by: `update_purchase_order`)
**Rules:**
- **R1.** As `update_purchase_order` R8: supplier, then details; then threshold.

## `PurchaseOrderManager._confirmed_supplier_update_fields(session, record)` / `_confirmed_detail_update_fields(session, record)`
**Shape:** compute · **Persistence:** reads · **Visibility:** internal
**Rules:**
- **R1.** Locked or supplier confirmed → `{account_id}`, else empty. Locked or details confirmed → `{destination_type, destination_id, order_date, description}`, else empty.

## `PurchaseOrderManager._items_structure_confirmed(session, po)`
**Rules:**
- **R1.** `True` when `items_confirmed` or financially locked.

## `PurchaseOrderManager._base_sections_confirmed(po)`
**Shape:** compute · **Persistence:** pure · **Visibility:** public in use (`AccountInvoiceService.confirm_invoice`, `PurchaseOrderService`)
**Rules:**
- **R1.** `True` only when supplier, details and items are all confirmed (`invoice_confirmed` not read).

## `PurchaseOrderManager._validate_section_confirm(record, update_dict, session, workspace_id)`
**Shape:** validator · **Persistence:** reads · **Visibility:** internal
**Rules** (each only when the flag is sent `true` and is stored `false`; checked in this order):
- **R1.** Supplier: no supplier after the update (sent or stored) → 400 `Select a supplier before confirming`.
- **R2.** Details: destination type empty, destination id `None`, or order date `None` after the update → 400 `Complete destination, location, and order date before confirming`.
- **R3.** Items: no lines → 400 `Add at least one line item before confirming`; any line unpriced or priced 0.00 → 400 `Enter unit prices to confirm`.
- **R4.** Invoice: → 400 `Draft invoice is confirmed when you finalize the invoice — use Finalize Invoice instead` (always, unless already confirmed).

## `PurchaseOrderManager.apply_post_invoice_confirms(session, po, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `AccountInvoiceService.confirm_invoice`)
**Rules:**
- **R1.** Always logs `invoice_created` / `Invoice created`.
- **R2.** For supplier, details, items, invoice in that order, each not yet confirmed becomes `True` and logs `supplier_confirmed` / `Supplier confirmed after invoice created`, `details_confirmed` / `Order details confirmed after invoice created`, `items_confirmed` / `Order items confirmed after invoice created`, `invoice_confirmed` / `Draft invoice confirmed after invoice finalized`; confirmed ones log nothing. Flushed. Approvals and stage untouched (the caller syncs the stage).

## `PurchaseOrderManager.get_purchase_order(session, po_id, workspace_id)`
**Shape:** get-or-404 · **Persistence:** reads · **Visibility:** public
**Rules:**
- **R1.** The workspace's order; missing or another workspace's → 404 `Purchase order with ID {po_id} not found`. Voided orders are returned.

## Hub pass-throughs: `list_purchase_orders_for_hub(session, workspace_id, *, skip=0, limit=50, **filters)`, `count_purchase_orders_for_hub`, `purchase_order_hub_stats`, `list_purchase_orders_recent_for_hub(…, limit=10, …)`, `purchase_order_pending_highlights_for_hub`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /purchase-orders/`, `GET /purchase-orders/stats/`)
**Rules:**
- **R1.** Each returns exactly what the same-named DAO method returns for the arguments given (defaults: list `skip 0`, `limit 50`; recent `limit 10`). Filtering, order and the voided / money rules are `purchase_order.spec.md` (`list_for_hub`, `count_for_hub`, `aggregate_hub_stats`, `list_recent_for_hub`, `get_pending_highlights_for_hub`; BUG-2639, 2640, 2641).

## `PurchaseOrderManager.delete_purchase_order(session, po_id, workspace_id)`
**Shape:** delete · **Persistence:** writes · **Visibility:** public (`DELETE /purchase-orders/{id}/`)
**Rules:**
- **R1.** Order not in the workspace → 404 `Purchase order with ID {po_id} not found`.
- **R2.** Any receive event of the order in the workspace → 400 `Cannot delete a purchase order with receiving history — void the order instead`.
- **R3.** Else any line with received > 0 → 400 `Cannot delete a purchase order with recorded receiving — void the order instead`.
- **R3a.** [BUG-2888] (owner, OQ-54, 2026-11-21) The order's linked invoice exists in the workspace with status `confirmed` or `locked` → 400 `Cannot delete a purchase order with a finalized invoice — void the order instead`, nothing written (the invoice and its payments stay). Checked after R2–R3. *(Today: the order is deleted and the invoice stays `confirmed`, owed and naming the deleted order; verified.)*
- **R4.** Otherwise the lines and the order are hard-deleted (flushed); approvers and events go with it (cascade). A voided order with nothing received can be deleted (its invoice was unlinked when it was voided). No linked invoice → only the order goes.
- **R4a.** [BUG-2888] A linked invoice with status `draft` is deleted together with the order (the invoice row and its lines, flushed); a re-select finds neither. Lines are `invoice_items` (`app.models.invoice_item.InvoiceItem`, `invoice_id` FK `ON DELETE CASCADE`); the invoice's `invoice_events` and `invoice_status_tracker` rows go the same way (fact, G9). *(Today: the draft invoice stays; verified.)*
- **R5.** [BUG-1195] A delete writes one `workspace_audit_logs` row: `user_id` = the deleter (*requires new parameter* `user_id`, passed by the endpoint), `action = purchase_order_deleted`, `resource_type = purchase_order`, `resource_id` = order id, `metadata = {"number", "total_amount" (2-decimal text), "created_by", "created_at" (ISO)}`; a refused delete writes none. *(Today: nothing.)* Written through `workspace_audit_log_dao.log_action`; the metadata is the model attribute `WorkspaceAuditLog.metadata_json` (column `metadata`) (fact, G10).
- **R5a.** [BUG-1195] `user_id` is a required parameter: a call without it raises `TypeError` and deletes nothing (G13, as `expense_order_manager.spec.md` `delete_expense_order` R5c). *(Today: no such parameter.)*
- **R6.** [BUG-2872] The order row is read `FOR UPDATE` before R2–R3a (HR-10). *(Today: plain read.)*

## `PurchaseOrderManager._quantity_received_decimal(record)`
**Rules:**
- **R1.** `None` → `Decimal(0)`; else `Decimal(str(value))`.

## `PurchaseOrderManager._validate_ordered_vs_received(quantity_ordered, quantity_received)`
**Rules:**
- **R1.** Ordered < received → 400 `Ordered quantity cannot be less than received (<received>)`, received shown as integer text when whole (`7`), else normalized (`7.5`). Equal passes. Refunded quantity is not read.

## `PurchaseOrderManager._ensure_catalog_item_not_on_po(session, po_id, item_id, workspace_id, *, exclude_item_id=None)`
**Rules:**
- **R1.** If a line of the order (other than `exclude_item_id`) already has `item_id` → 409 `<name> is already on this purchase order` (workspace item name, else `Item #<id>`). Lines flushed earlier in the same call count.

## `PurchaseOrderManager.add_item(session, po_id, data, workspace_id, user_id=None)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /purchase-orders/{id}/items/`)
**Rules:**
- **R1.** Order not in the workspace → 404 `Purchase order not found`.
- **R1a.** [BUG-2882] Voided → 400 `Purchase order is voided`. *(Today: accepted once items are unconfirmed; verified.)*
- **R2.** Items locked (`_items_structure_confirmed`) → 400 `Confirmed after invoice creation` when financially locked, else `Order items are confirmed`.
- **R3.** Duplicate catalog item → `_ensure_catalog_item_not_on_po` R1. [BUG-1017] `item_id` must be in the workspace (404).
- **R4.** Line number = highest existing + 1 (1 on an empty order); `quantity_received = 0`; price and subtotal per the helpers. [BUG-2877] / [BUG-2878] per P1, P2.
- **R5.** Totals recomputed per `_recalc_totals`. Event `item_added` / `Added <item name> (line <n>)`, metadata `item_id`, `item_name`, `line_number`, `quantity_ordered`, `unit_price` (texts per `_format_scalar_value`, `—` for no price), performer `user_id`.
- **R6.** With `user_id` given, the stage is synced; with `None` it is not. Returns the line, re-read from the database.
- **R7.** [BUG-2872] The order row is read `FOR UPDATE` before R1a–R3 (HR-10). *(Today: plain read.)*

## `PurchaseOrderManager.update_item(session, item_id, data, workspace_id, user_id=None)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (`PUT /purchase-orders/items/{item_id}/`)
**Inputs:** `PurchaseOrderItemUpdate` — `quantity_ordered?`, `unit_price?`, `notes?`. [BUG-2887] `quantity_received` is no longer accepted (R3). *(Today: also `quantity_received?`.)*
**Rules:**
- **R1.** Line not in the workspace → 404 `Purchase order item not found`. Only non-null sent fields apply; [BUG-2879] explicit `null` clears `unit_price`, `notes` (P3).
- **R1a.** [BUG-2882] The line's order voided → 400 `Purchase order is voided`.
- **R2.** Items locked (`_items_structure_confirmed`) and any field sent → 400 `Confirmed after invoice creation (receiving still allowed)` when financially locked, else `Order items are confirmed (receiving still allowed)` (texts unchanged; "receiving" now means "Receive goods"). An empty body passes and changes nothing.
- **R3.** [BUG-2887] (owner, OQ-53, 2026-11-21) A body that sends `quantity_received` — any value, the stored one and `null` included — is refused with 422 before anything is written; the line, the order, the invoice, stock and events stay as they were. Received quantities change only through receive events ("Receive goods", `PurchaseOrderService`). *(Today: a `quantity_received` that differs from the stored one is accepted once the order's invoice is `confirmed` / `locked` (else 400 `Finalize the invoice before recording receiving`); it may be negative (−5 verified) or up to the full ordered quantity ignoring refunds, on completed orders too; it moves no stock and makes no receive event; it logs `received` (`Received <delta> more …` / `Receiving adjusted to …`), may log `all_received` once, sets the invoice's `receiving_started`, logs `invoice_receiving_started` on every such change (BUG-2884, superseded), and syncs the stage (first receipt → `Receiving`). An unchanged value is a no-op.)*
- **R4.** A changed `quantity_ordered` must stay ≥ the stored received quantity per `_validate_ordered_vs_received`.
- **R5.** `quantity_ordered` or `unit_price` sent → `line_subtotal` recomputed from the effective quantity and price (`_line_subtotal`).
- **R6.** Written and flushed; order totals recomputed (`_recalc_totals`).
- **R7.** [BUG-2877] / [BUG-2878] range and decimals per P1, P2.
- **R8.** Changed `quantity_ordered` / `unit_price` / `notes` → one event `item_updated` / `Updated item: <item name>` with `changes` (per `_collect_item_field_changes`) and `item_id`, `item_name`, `line_number`; performer `user_id` (may be `None`). Nothing changed → no event.
- **R9.** With `user_id` given the stage is synced; with `None` it is not. Returns the line. (R10–R17 retired into R3 by BUG-2887.)
- **R18.** [BUG-2872] Read `FOR UPDATE` (order) before R2 and R4.

## `PurchaseOrderManager.remove_item(session, item_id, workspace_id, user_id=None)`
**Shape:** delete · **Persistence:** writes · **Visibility:** public (`DELETE /purchase-orders/items/{item_id}/`)
**Rules:**
- **R1.** Line not in the workspace → 404 `Purchase order item not found`.
- **R1a.** [BUG-2882] Order voided → 400 `Purchase order is voided`.
- **R2.** Items locked → 400 as `add_item` R2. Received quantity is not checked (Q8).
- **R3.** The line is hard-deleted (flushed); other lines keep their numbers (gaps stay); totals recomputed; event `item_removed` / `Removed <item name> (line <n>)`, metadata `item_id`, `item_name`, `line_number`. With `user_id` the stage is synced. Returns the deleted line object.
- **R4.** [BUG-2872] The line's order row is read `FOR UPDATE` before R1a–R2 (HR-10). *(Today: plain read.)*

## `PurchaseOrderManager.sync_items(session, po_id, data, workspace_id, user_id=None)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (`POST /purchase-orders/{id}/items/sync/`)
**Inputs:** `PurchaseOrderItemSyncRequest` (`app.schemas.purchase_order`) — `remove_ids: list[int]`, `updates: list[PurchaseOrderItemSyncUpdate]` (`{id, quantity_ordered, unit_price?}`), `additions: list[PurchaseOrderItemCreate]` (all default `[]`).
**Rules:**
- **R1.** Order not in the workspace → 404 `Purchase order not found`.
- **R1a.** [BUG-2882] Voided → 400 `Purchase order is voided`.
- **R2.** Items locked → 400 as `add_item` R2.
- **R3.** Removals first, in the order sent: an id that is not a line of **this** order (another order's, another workspace's, missing, or listed twice) → 404 `Purchase order item <id> not found`; a line with received > 0 → 400 `Cannot remove <item name> — receiving has already been recorded`; else deleted with event `item_removed` as `remove_item` R3.
- **R4.** Then updates: an id not a remaining line of this order (removed above included) → 404 `Purchase order item <id> not found`. Each sets `quantity_ordered`, `unit_price` (sent `null` → unpriced) and `line_subtotal`; ordered vs received per `_validate_ordered_vs_received`.
- **R5.** An update logs `item_updated` (as `update_item` R8) only when something changed **and** `user_id` is given.
- **R6.** Then additions: numbered from (highest remaining line number + 1), in the order sent; each per `add_item` R3–R5 (duplicate check sees earlier additions and kept lines, not removed ones), event `item_added`. [BUG-2877] / [BUG-2878] per P1, P2.
- **R7.** [BUG-1017] addition `item_id` in the workspace.
- **R8.** Totals recomputed once at the end; with `user_id` the stage is synced. Returns the order, re-read. A refusal at any step raises; rows changed by earlier steps are flushed and must be rolled back by the caller (the service does).
- **R9.** [BUG-2872] The order row is read `FOR UPDATE` before R1a–R2 (HR-10). *(Today: plain read.)*

## `PurchaseOrderManager.get_items(session, po_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /purchase-orders/{id}/items/`)
**Rules:**
- **R1.** The order's lines in the workspace by `line_number` ascending. [BUG-2886] A missing or foreign order → 404 `Purchase order with ID {po_id} not found`. *(Today: `[]`.)*

## `PurchaseOrderManager._recalc_totals(session, po)`
**Rules:**
- **R1.** `subtotal = total_amount` = sum of the lines' `line_subtotal` (unpriced 0; no lines 0.00), flushed. The sum is of the rounded subtotals.
- **R1a.** (G15, fact, verified by the executor: SY-22 passes) This holds today on every API path: `_recalc_totals` re-reads the order's lines, and lines loaded from the database carry the stored, rounded `line_subtotal`. At most one line in the session can still hold an unrounded value (the line `add_item` / `update_item` just wrote), and one half-up value added to a 2-decimal sum rounds to the same total. `sync_items` refreshes each line before summing. Not part of BUG-2876. *(The total can only drift when two or more unrounded lines sit in one session, which only `create_purchase_order` does — R7, BUG-2876.)*

## `PurchaseOrderManager.list_approvers(session, po_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /purchase-orders/{id}/approvers/`)
**Rules:**
- **R1.** Order not in the workspace → 404 `Purchase order with ID {po_id} not found`.
- **R2.** One `(approver, profile, position)` per approver of the order, by `assigned_at` [BUG-1200 tie → `id`]. Position = the person's membership position in the workspace, `None` when no membership or none set.
- **R3.** [BUG-2883] At most 4 SELECTs per call, whatever the number of approvers: the order guard, the approvers, their profiles together, their memberships together (decided under the reviewer's delegation, 2026-11-21, G11, as BUG-1141). *(Today: two per approver.)*

## `PurchaseOrderManager.approval_summary(session, po)`
**Shape:** compute · **Persistence:** reads · **Visibility:** public (`AccountInvoiceService.confirm_invoice`, `GET` approvers)
**Rules:**
- **R1.** Returns `(approved_count, required, met)`; `met = approved_count ≥ required`.
- **R2.** `required_approvals` set (0 included) → `required` = it. [BUG-2877] Negative refused by the schema.
- **R3.** Not set and n ≥ 1 approvers → `required = n`. Not set and no approvers: [BUG-1202] `required = 1`, not met. *(Today: 0, met; verified.)*

## `PurchaseOrderManager.add_approver(session, po_id, user_id, workspace_id, assigned_by)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /purchase-orders/{id}/approvers/`)
**Rules:**
- **R1.** Order not in the workspace → 404 `Purchase order with ID {po_id} not found`.
- **R2.** Person not a member of the workspace, or membership not `active` → 400 `User is not an active member of this workspace`.
- **R2a.** [BUG-2882] Voided → 400 `Purchase order is voided`.
- **R3.** Already an approver of the order → 409 `User is already an approver for this order`.
- **R4.** Creates the approver (`assigned_by`, not approved), flushed; returns it.
- **R5.** Event `approver_added` / `Added <name> as approver`, performer `assigned_by`, metadata `user_id`, `user_name`.
- **R6.** [BUG-2881] Complete → 400 `Cannot change approvers — order is complete`; invoice confirmed → 400 `Cannot change approvers — invoice is finalized`. *(Today: not checked.)*
- **R7.** [BUG-2872] (HR-10) (G14, decided by Claude under the reviewer's delegation, 2026-11-21, matching `work_order_manager.spec.md` `add_approver` R8 / `remove_approver` R5) The purchase order row is read `FOR UPDATE` before the R2a / R6 state checks: adding an approver changes whether approvals are met and races completion / finalization. The loser sees the new state and gets the normal error. *(Today: no lock.)*

## `PurchaseOrderManager.remove_approver(session, po_id, user_id, workspace_id, performed_by=None)`
**Shape:** delete · **Persistence:** writes · **Visibility:** public (`DELETE /purchase-orders/{id}/approvers/{user_id}/`)
**Rules:**
- **R1.** No such approver of the order in the workspace → 404 `Approver not found` (also for a missing order).
- **R1a.** [BUG-2882] Voided → 400 `Purchase order is voided`.
- **R2.** Hard-deleted, flushed; an approved approver and the creator can be removed.
- **R3.** Event `approver_removed` / `Removed <name> as approver`, performer `performed_by` (may be `None`), metadata `user_id`, `user_name`.
- **R4.** [BUG-2881] as `add_approver` R6.
- **R5.** [BUG-2872] (HR-10) (G14, decided by Claude under the reviewer's delegation, 2026-11-21, matching `work_order_manager.spec.md` `add_approver` R8 / `remove_approver` R5) The purchase order row is read `FOR UPDATE` before the R1a / R4 state checks; removing an approver can make approvals met. *(Today: no lock.)*

## `PurchaseOrderManager.set_approval(session, po_id, user_id, workspace_id, approved)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST` / `DELETE /purchase-orders/{id}/approvers/me/approve/`)
**Rules:**
- **R1.** The caller not an approver of the order in the workspace → 403 `You are not an assigned approver for this order`.
- **R1a.** [BUG-2882] Voided → 400 `Purchase order is voided`. *(Today: accepted, verified.)*
- **R2.** Approve: supplier, details and items not all confirmed → 400 `Confirm supplier, order details, and items before approving`.
- **R3.** Withdraw: order `Complete` → 400 `Cannot withdraw approval — order is complete`.
- **R4.** Withdraw: invoice status `locked` → 400 `Cannot withdraw approval — invoice is locked` (dead, BUG-2735). [BUG-2881] Invoice `confirmed` → 400 `Cannot withdraw approval — invoice is finalized`. *(Today: allowed.)*
- **R5.** Sets `approved`, `approved_at` = now (approve) / `None` (withdraw), flushed; event `approved` / `Approved order` or `approval_withdrawn` / `Withdrew approval`, performer the caller. Returns the row.
- **R6.** [BUG-2880] Same state as stored → nothing written, no event, row returned. *(Today: re-stamped and logged.)*
- **R7.** [BUG-2872] Order read `FOR UPDATE` before R2–R4.

## `PurchaseOrderManager.log_event(session, po_id, workspace_id, event_type, description, performed_by=None, metadata=None)`
**Shape:** event-log · **Persistence:** writes · **Visibility:** public (every writer here; services; `AttachmentManager`)
**Rules:**
- **R1.** Adds one `purchase_order_events` row with the given values (`metadata` in column `metadata`, `None` allowed), flushed; returns it.
- **R2.** [BUG-1192] An order not in the workspace → 404 `Purchase order with ID {po_id} not found`, nothing written. *(Today: stored under the caller's workspace.)*

## `PurchaseOrderManager.list_events(session, po_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /purchase-orders/{id}/events/`)
**Rules:**
- **R1.** Order not in the workspace → 404 `Purchase order with ID {po_id} not found`.
- **R2.** `(event, profile)` per event, newest first, ties by `id` descending; profile `None` when no performer. [BUG-2883] At most 3 SELECTs per call, whatever the number of events: the order guard, the events, the performers' profiles together (decided under the reviewer's delegation, 2026-11-21, G11, as BUG-1141).

---

## Follow-ups (other modules)
| # | Where | What | Source |
|---|---|---|---|
| FU-1 | `PurchaseOrderService.void_purchase_order` | BUG-2734 (owner): a completed PO, or one with goods received, cannot be voided. Void also leaves the section confirms, which P6 / BUG-2882 relies on being harmless once voided orders are read-only. | owner 2026-11-14 |
| FU-2 | `PurchaseOrderService` (`receive_replacements`, new) | BUG-2810 write side as `purchase_order_return_manager.spec.md` FU-2; this manager adds no rule (`sync_po_stage` R1 keeps `Complete`). Open, noted there: whether a replacement settles the return's credit note (money) — ask at the service describe. | owner 2026-11-19 |
| FU-3 | `PurchaseOrderService.create_purchase_order` | `except HTTPException: raise` skips `_rollback_transaction` (TC3 departure; Q7). | Q7 |
| FU-4 | `PurchaseOrderResponse` / service | `has_open_return` field (RP2). | OQ-48 refined |
| FU-5 | `app/schemas/purchase_order.py` | Drop `current_status_id`, `order_workflow_id` from `PurchaseOrderCreate` (Q6, clean-up); fixes of P1–P3, BUG-681. | Q6 |

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 86 | price None | `_parse_unit_price` R1 |
| 92 | price None | `_line_subtotal` R1, R2 |
| 96–97 | empty / unpriced / ≤ 0 | `_all_items_have_positive_unit_price` R1, R2 |
| 120 | no invoice id | `is_po_financially_locked` R1 |
| 125 | invoice not found | R1 |
| 127 | confirmed / locked | R2 |
| 144 | extra metadata | `unlink_invoice_from_po` R2 |
| 161–162 | flag already false | `unconfirm_sections_after_invoice_void` R1 |
| 173 | changed | R2 |
| 189 | approved | `reset_approvals` R1 |
| 194 | count > 0 | R2 |
| 209 | no Draft | `_ensure_po_stage_statuses` R1 |
| 221 | foreign workflow exists | `_raise_po_workflow_setup_error` R1 |
| 243 | stage row missing | `_resolve_po_stage_status_id` R2 |
| 253 | workflow None | `_resolve_po_workflow_id` R2 |
| 258 | no items | `_all_items_fully_received` R1 |
| 260–263 | received + refunded ≥ ordered | R2 |
| 274 | status found | `_current_stage_name` R1 |
| 277, 282 | no invoice / not found | `_invoice_payment_status` R1 |
| 292 | PO found | `sync_po_for_linked_invoice` R1 |
| 304 | has invoice | `sync_po_paid` R1 |
| 307 | unchanged | R2, R3 |
| 321 | Complete | `_is_po_complete_stage` R1 |
| 329, 331, 333 | received / locked / confirmed | `_derive_po_stage_name` R1–R4 |
| 352 | current Complete | `sync_po_stage` R1 |
| 363 | workflow differs | R2, R4 |
| 367 | status differs | R3 |
| 390 | changed | R4 |
| 403 | not found | `mark_order_complete` R1 |
| 408 | already Complete | R2 |
| 416 | not all received | R3 |
| 426 | open return | R4 |
| 436 | delivery date empty | R5 |
| 457 | not Complete | `reopen_for_return` R1, R2 |
| 478 | items None | `create_purchase_order` R5, R7 |
| 487 | no order date | R2 |
| 506–511 (util) | duplicate item id | R4 |
| 515 | loop over lines | R5 |
| 528 | unpriced line | R7 |
| 545 | not found | `update_purchase_order` R1 |
| 552 | locked | R3 |
| 553, 558, 563, 568 | unconfirm while locked | R3 |
| 575, 578 | supplier field blocked; locked? | R4 |
| 584, 587 | detail field blocked; locked? | R5 |
| 596 | confirm field sent | R7 |
| 600, 601 | changed; unconfirmed | R7 |
| 611 | any unconfirm | R7 |
| 629–631, 634 | None | `_format_scalar_value` R1 |
| 635 | date | R2 |
| 637–638 | Decimal integral | R3 |
| 640 | empty text | R4 |
| 645 | id None | `_format_destination_id` R1 |
| 648–663 | type; row found | R2 |
| 674–678 | account; None; found | `_format_field_value` R1 |
| 679–682 | destination type | R2 |
| 683 | destination id | R3 |
| 685–689 | status; None; found | R5 |
| 690–693 | threshold None | R4 |
| 694 | other | R6 |
| 707, 711 | absent / equal | `_collect_field_changes` R1 |
| 732, 736 | absent / equal | `_collect_item_field_changes` R1 |
| 758 | extra metadata | `_log_field_change_event` R1 |
| 774, 783 | changes found | `_log_section_field_updates` R1 |
| 810 | threshold changes | R1 |
| 817, 819 | locked / supplier confirmed | `_confirmed_supplier_update_fields` R1 |
| 824, 826 | locked / details confirmed | R1 |
| 831 | items confirmed or locked | `_items_structure_confirmed` R1 |
| 835–837 | all three | `_base_sections_confirmed` R1 |
| 848–851 | supplier confirm, no account | `_validate_section_confirm` R1 |
| 861–864 | details not ready | R2 |
| 870, 874, 879 | items confirm; no lines; price | R3 |
| 884 | invoice confirm | R4 |
| 898, 904, 910, 916 | not yet confirmed | `apply_post_invoice_confirms` R2 |
| 926 | not found | `get_purchase_order` R1 |
| 952–982 | pass-through | hub R1 |
| 986 | not found | `delete_purchase_order` R1 |
| 999 | receive events | R2 |
| 1008 | line received | R3 |
| 1016 | loop lines | R4 |
| — (new) | finalized / draft invoice | R3a, R4a [BUG-2888] |
| 1026 | None | `_quantity_received_decimal` R1 |
| 1033, 1036 | ordered < received; whole | `_validate_ordered_vs_received` R1 |
| 1056, 1060 | same item, not excluded; name found | `_ensure_catalog_item_not_on_po` R1 |
| 1072 | not found | `add_item` R1 |
| 1074, 1077 | locked; financially | R2 |
| 1083 | no lines → 1 | R4 |
| 1102 | name found | R5 |
| 1115, 1117 | user given; PO found | R6 |
| 1127 | not found | `update_item` R1 |
| 1134, 1136, 1139 | locked; structural; financially | R2 |
| 1145–1149 | received changed | R3 (today; refused by BUG-2887) |
| 1151, 1152, 1160 | PO; no invoice; not confirmed | R3 (today) |
| 1169–1172 | received sent / ordered vs received | R3 (today), R4 |
| 1176, 1178 | qty / price sent | R5 |
| 1187 | PO found | R6 |
| 1190 | item changes | R8 |
| 1204 | received changed | R3 (today; removed by BUG-2887) |
| 1215, 1216 | delta > 0; full | R3 (today; removed by BUG-2887) |
| 1242, 1246, 1251, 1258 | full; all done; not logged | R3 (today; removed by BUG-2887) |
| 1264, 1268, 1275 | invoice; confirmed; total > 0 | R3 (today; removed by BUG-2887) |
| 1293 | user given | R9 |
| 1302 | not found | `remove_item` R1 |
| 1307, 1310 | locked; financially | R2 |
| 1319, 1331 | PO found; user given | R3 |
| 1345 | not found | `sync_items` R1 |
| 1347, 1350 | locked | R2 |
| 1360–1373 | remove loop; unknown; received | R3 |
| 1391–1397 | update loop; unknown | R4 |
| 1408 | legacy None received | R4 |
| 1412 | changes and user | R5 |
| 1430 | additions loop | R6 |
| 1462 | user given | R8 |
| 1467 | — | `get_items` R1 |
| 1472 | unpriced | `_recalc_totals` R1 |
| 1485, 1490 | loop; member found | `list_approvers` R2 |
| 1499, 1501 | threshold set; approvers | `approval_summary` R2, R3 |
| 1517 | not active member | `add_approver` R2 |
| 1525 | existing | R3 |
| 1540 | profile found | R5 |
| 1556 | not found | `remove_approver` R1 |
| 1559 | profile found | R3 |
| 1575 | not an approver | `set_approval` R1 |
| 1580, 1582 | approve; sections | R2 |
| 1589 | complete | R3 |
| 1594, 1598 | invoice; locked | R4 |
| 1604 | approve → stamp | R5 |
| 1639 | performer set | `list_events` R2 |

## Gap log
G1 (purchase_order_manager.cases.md gap 1) — fact — `sync_items` Inputs name `PurchaseOrderItemSyncRequest` / `PurchaseOrderItemSyncUpdate`.
G2 (gap 2) — fact — `_collect_field_changes` R1 lists every label.
G3 (gap 3) — decided under delegation (2026-11-21) — `update_purchase_order` R13a: a sent `invoice_id` is refused with 422 by the schema.
G4 (gap 4) — decided under delegation (2026-11-21) — Overview "Check order after the fixes"; the `Item #<id>` fallback is old-data only.
G5 (gap 5) — test mechanics — Overview note: patch `ensure_po_workflow_record` to return `None`.
G6 (gap 6) — contradiction — `_is_po_complete_stage` R1 narrowed, new R1a [BUG-1881] (ignore capitals and outer spaces, per OQ-13); `_current_stage_name` R1 returns the stored name unchanged.
G7 (gap 7) — fact — Overview "Return values": all ten return `None`.
G8 (gap 8) — contradiction — lock rules added: `add_item` R7, `remove_item` R4, `sync_items` R9, `delete_purchase_order` R6 [BUG-2872]; HR-10 line points at them.
G9 (gap 9) — fact — `delete_purchase_order` R4a names `invoice_items` (`InvoiceItem`) and the cascading invoice rows.
G10 (gap 10) — fact — `delete_purchase_order` R5: `WorkspaceAuditLog.metadata_json` via `log_action`.
G11 (gap 11) — decided under delegation (2026-11-21) — `list_events` R2 at most 3 SELECTs, `list_approvers` R3 at most 4 (BUG-1141 precedent).
G12 (gap 12) — fact — `sync_po_stage` R4a: stage lookup before workflow resolution.
G13 (gap 13) — decided under delegation (2026-11-21), BUG-1193 precedent — `delete_purchase_order` R5a: `user_id` required; every delete case passes it.
G14 (coordinator follow-up after work order G15) — house rule not applied — decided under delegation (2026-11-21) — `add_approver` R7, `remove_approver` R5: row lock under BUG-2872 (HR-10), as the work order spec.
G15 (executor discrepancy, SY-22 / CR-06) — fact, decided under delegation (2026-11-21) — BUG-2876 narrowed to `_line_subtotal` R2 and `create_purchase_order` R7; `_recalc_totals` R1 untagged plus R1a (holds today, explains why), so `sync_items` R8 holds. Cards: SY-22 and RT-01…03 become pass cards (drop xfail BUG-2876); LS-02…05 and CR-06 stay strict xfail.
