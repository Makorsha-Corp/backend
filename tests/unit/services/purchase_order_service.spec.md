# Spec — `app/services/purchase_order_service.py`

> **Status:** APPROVED (2026-11-22; owner answered OQ-POS-1 as OQ-63, option (a); every other item decided under the reviewer's delegation of 2026-11-21; fill-gaps 2026-11-22: 12 gaps closed, see Gap log, no new questions)
> **Source commit:** e48a092

> **Review round 2026-11-21 (describe, under the reviewer's delegation of 2026-11-21).** House-rule lines and precedent matches are pre-filled. Every new question that is not a genuinely new money, stock, order-workflow or security question was decided by Claude under the delegation and is marked so; none of them is the owner's own answer. One question is new money and goes to the owner: **OQ-POS-1** (provisional number, to be renumbered when parked in `docs/testing/owner-questions.md`). Bug IDs come from block BUG-3162 … 3191 (used: 3162–3183).
>
> **Apply-review 2026-11-22.** OQ-POS-1 answered by the owner as **OQ-63** (option (a), with a full trail) → BUG-3176, `receive_replacements` RX8a–RX8i. Every other answer applied as written; each question carries a Resolution line. Bugs logged in `docs/testing/bugs.md`; BUG-3183 (return numbers unique across workspaces, return DAO) logged from this spec's Overview note.
>
> **Already decided elsewhere, cited, not asked again:** every rule and bug of `tests/unit/managers/purchase_order_manager.spec.md` (row locks BUG-2872, voided orders read-only BUG-2882, completed order uneditable BUG-2885, receiving only through "Receive goods" OQ-53 → BUG-2887, finalized invoice blocks delete / draft goes with the order OQ-54 → BUG-2888, numbering race BUG-2631, cross-workspace links BUG-1017 / BUG-2874, delete audit row BUG-1195) and its follow-ups FU-1 … FU-5, which land here; `purchase_order_return_manager.spec.md` (checks of a new return BUG-2750 … 2753, 2785, 2787, 2792; return lock BUG-2754; FU-1 (a)–(d); FU-2 = BUG-2810 and its check `validate_replacement_receipt` RR1–RR8); the owner's OQ-48 refined (return in progress, `sales_manager.spec.md` RP1–RP7, PO names in the PO manager spec RP1/RP2/RP5); the invoice freeze (`account_invoice_manager.spec.md` O1, F1–F7; void R3a–R3c, incl. BUG-2788); the posting modules (`po_receive_inventory.spec.md`, `po_return_inventory.spec.md`: BUG-680, 682, 684, 800, 801, 802); notification texts and recipients (`approval_notification_service.spec.md`, N1–N12, routed to `docs/future/notifications.md`); hub figures (`tests/unit/dao/purchase_order.spec.md`, OQ-35 … OQ-38 → BUG-2639 … 2641). `account_invoice_service.spec.md` BUG-2965, 2966, 2967 and 2969 touch the sales, expense and work order paths only: **no rule of this module changes** (the PO branches there are the precedents they follow).
>
> **Production:** not touched by this module. **Projects:** a PO may deliver to a project component, and `list_active_orders_for_context` has a project-component scope; today's behaviour is described and tagged *revisit after launch*, no bugs.
>
> **Read, not run.** Every rule below comes from reading the source and its collaborators. One read-only query on `marker_test` (`q_constraints.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc3desc\po\`, one transaction, rolled back) listed the check and unique constraints of `purchase_order_items`, `account_invoices`, `po_receive_events`, `po_receive_event_items`, `purchase_order_returns`, `purchase_order_return_items`: none except the primary keys and `purchase_order_returns.return_number` (globally unique — numbers are counted per workspace (`PR-2026-001` …), so the second workspace to start its first return of the year collides with the first one's number and the flush fails; logged as BUG-3183 against the return DAO / model, not a rule of this module). So the check-constraint and duplicate-line branches of `_handle_item_integrity_error` cannot fire from the database today (Q9).

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| H1 | Receiving, voiding and "create invoice" check the order and then act without locking it | bug — BUG-3162 | house rule HR-10 |
| H2 | A return credit note's line totals are not rounded | withdrawn — BUG-3163 not observable (the database rounds half up on store; Gap log G13) | house rule HR-15 |
| H3 | The list's invoice payment status is read without the workspace | bug — BUG-3164 | house rule HR-16 |
| H4 | An items sync that changes nothing still stamps "items updated" | bug — BUG-3165 | house rule HR-9 |
| H5 | "Active orders" for a machine reads only its newest 1,000 work orders, then filters | bug — BUG-3166 | house rule HR-5 |
| P1 | Draft invoices and credit notes are dated with the server's local date | bug — BUG-3167 | precedent BUG-3063 / BUG-2716 |
| P2 | A blank void reason is accepted (order void, return cancel) | bug — BUG-3168 | precedent BUG-626 / BUG-3064 |
| P3 | A voided PO can get a new draft invoice through "Create invoice" | bug — BUG-3169 | precedent BUG-3065 / BUG-754 |
| P4 | Voiding clears approvals only when the order had an invoice | bug — BUG-3170 | precedent BUG-3067 |
| P5 | One receive batch can name the same line twice and over-receive it | bug — BUG-3171 | precedent BUG-2751 |
| P6 | Receive events: ties and their lines come back in no fixed order | bug — BUG-3172 | precedent BUG-2755 |
| P7 | "Active orders" lists voided POs | bug — BUG-3173 | precedent BUG-717 |
| P8 | Completing or cancelling a return does not set `updated_by` | bug — BUG-3174 | precedent BUG-633 |
| FU-1 | A completed PO, or one with goods received, can be voided | bug — BUG-2734 (existing) | owner 2026-11-14 |
| FU-2 | Replacement goods for a `replace` return have no way in | bug — BUG-2810 (existing) | owner 2026-11-19 |
| FU-3 | Create re-raises a refusal without rolling back | bug — BUG-3175 | delegation (manager Q7) |
| FU-4 | The PO response has no "return in progress" flag | bug — BUG-2789 (existing) | owner OQ-48 refined |
| FU-5 | The create body still carries `current_status_id` / `order_workflow_id` | clean-up, no bug | delegation (manager Q6) |
| E1 | Delete does not pass who deleted the order | bug — BUG-1195 (existing) | owner |
| E2 | A fractional return quantity is accepted at start and blocks completion | bug — BUG-801 (existing) | reviewer |
| Q1 | Receiving goods never marks the invoice "receiving started", so it can be reverted to draft afterwards | bug — BUG-3177 | delegation |
| Q2 | The list repairs the stage of only the first stale order per page | bug — BUG-3178 | delegation |
| Q3 | An items sync saves the lines and the draft invoice in two separate commits | bug — BUG-3179 | delegation |
| Q4 | Receive notes: blank stored as empty text, log repeats the untrimmed text | bug — BUG-3180 | delegation |
| Q5 | Cancelling a pending return whose credit note is already voided is impossible | bug — BUG-3182 | delegation |
| Q6 | The replacement step could fill a line already re-received the normal way | bug — BUG-3181 | delegation (stock invariant of FU-2) |
| Q7 | Two lines of `create_purchase_order` can never run | remove | delegation |
| Q8 | GET and list commit when they repair a stage | intended | delegation |
| Q9 | Integrity-error mapping has branches no database constraint can reach | intended | delegation |
| Q10 | Only the list fills item counts and totals; other responses show 0 | intended | delegation |
| OQ-POS-1 | **OWNER** — receiving a `replace` return's replacements leaves its credit note owed | bug — BUG-3176 | owner OQ-63 (2026-11-22) |

### House-rule violations — applied automatically
> Overwrite an answer only if the house rule should NOT apply here.

- **HR-10** `create_receive_event` RE1, `void_purchase_order` V1, `create_invoice_for_purchase_order` CI1 — each reads the order (and its lines / linked invoice) with a plain read, checks its state (voided, completed, invoice finalized, quantity still receivable, invoice linked) and then writes. The manager's lock (BUG-2872) is not on these paths. A race does real harm: two receive batches on the last 10 units both pass the "exceeds ordered" check and both add stock (20 received on 10 ordered); a receipt racing a void reverses only what it saw; two "Create invoice" clicks make two draft invoices, one orphaned (there is no unique index on drafts per order). Intended: each reads the purchase order row `SELECT … FOR UPDATE` before its first check (lines and invoice follow the order's lock); the loser sees the new state and gets the normal error. 🐞 BUG-3162
**Answer:** bug — per HR-10 (house rule)
**Resolution:** applied 2026-11-22 — rule(s) `create_receive_event` RE1, `void_purchase_order` V1, `create_invoice_for_purchase_order` CI1 state the intended behaviour, tagged [BUG-3162] with a *(Today: …)* note.
- **HR-15** `_attach_return_invoice_for_po` AR3 — each credit-note line's `line_subtotal` is `unit_price × quantity_returned` unrounded (up to 4 decimals for 2-decimal inputs; `1.25 × 0.10 = 0.1250`); the invoice amount is summed from those values in the session while each stored line rounds on its own (as BUG-2876). Return manager FU-1 (b) named it. Intended: each line subtotal is rounded half up to 2 places when built; the credit note's amount is the sum of the rounded lines. 🐞 BUG-3163
**Answer:** bug — per HR-15 (house rule)
**Resolution:** applied 2026-11-22 — rule(s) `_attach_return_invoice_for_po` AR3 state the intended behaviour, tagged [BUG-3163] with a *(Today: …)* note. **Withdrawn 2026-11-22 (Gap log G13):** the stored lines and the amount already round half up, so AR3 is an untagged regression rule and BUG-3163 is not a bug.
- **HR-16** `_attach_invoice_payment_status` AP2 — invoices are read by id only, without the workspace. A PO row pointing at another workspace's invoice (invalid data, BUG-1017) shows that invoice's `payment_status` in this workspace's list and detail. Intended: only invoices of the order's workspace are read; another workspace's invoice gives `invoice_payment_status = null`. 🐞 BUG-3164
**Answer:** bug — per HR-16 (house rule)
**Resolution:** applied 2026-11-22 — rule(s) `_attach_invoice_payment_status` AP2 state the intended behaviour, tagged [BUG-3164] with a *(Today: …)* note.
- **HR-9** `sync_items` SY4 — the second step sets `items_updated_at` = now whenever the order has a supplier, also when the request changed nothing (empty `remove_ids`, `updates`, `additions`, or updates equal to the stored values). Intended: `items_updated_at` is written only when at least one line was added, removed or changed. 🐞 BUG-3165
**Answer:** bug — per HR-9 (house rule)
**Resolution:** applied 2026-11-22 — rule(s) `sync_items` SY4 state the intended behaviour, tagged [BUG-3165] with a *(Today: …)* note.
- **HR-5** `list_active_orders_for_context` AO9 — for a machine, the work orders are the machine's newest 1,000 (any status), and only then are drafts and in-progress ones kept. A machine with 1,000 newer completed work orders hides an older in-progress one. Intended: the status filter is in the query, before any limit, and every in-flight work order of the machine is returned. (The project-component scope reads the workspace's newest 1,000 and filters in Python: today's behaviour, *revisit after launch*, not part of this bug.) 🐞 BUG-3166
**Answer:** bug — per HR-5 (house rule)
**Resolution:** applied 2026-11-22 — rule(s) `list_active_orders_for_context` AO9 state the intended behaviour, tagged [BUG-3166] with a *(Today: …)* note.

Checked and **not** violated: **HR-1/2/3** — no names stored (void reasons are P2; receive texts are Q4). **HR-4** — purchase orders, lines, returns, receive events have no soft delete; work orders are read with `is_deleted = false`; the machine / factory / component scope check reads the raw row by id (BaseDAO scope), so a soft-deleted machine's open orders are still listed (decided under the delegation: the orders are not hidden by deleting their location). **HR-6** — list paging and order are the DAO's (`list_for_hub`: `created_at` desc, `id` desc); `list_active_orders_for_context` is not paged (Python sort by `created_at` desc, stable: ties keep purchase, then transfer, then work order, each in its DAO order). **HR-7** — the endpoint enforces `limit`. **HR-8** — search is the DAO's. **HR-11–14** — no external system or batch. **HR-16** elsewhere — every other read takes the caller's `workspace_id`; foreign supplier / line / destination ids are BUG-1017 / BUG-2874 (manager); `_build_invoice_items_from_po` only copies the order's own lines.

**Permission checks:** none in the service. Every endpoint needs only an active member of the workspace: any member can void an order (reversing stock and voiding its invoice), delete it, receive goods, start / complete / cancel returns, create the invoice, add or remove approvers. Noted for `docs/future/permissions.md`, not a question here.

### Precedent matches — confirm all with ok

### P1. Draft invoices and return credit notes are dated with the server's local date — 🐞 BUG-3167 (precedent)
**Background:** the expense order service's draft invoice date was ruled to come from the UTC clock (BUG-3063, after BUG-2716 / BUG-1334).
**What happens today:** the PO's draft payable invoice and a return's credit note get `invoice_date = date.today()`, the local date of the machine running the API.
**Example:** a server on Dhaka time starts a return at 01:30 on 2 March local time; `utcnow()` is still 1 March, but the credit note is dated 2 March.
**Rules affected:** `_sync_draft_invoice_for_po` SD7, `_attach_return_invoice_for_po` AR1
**Answer:** bug — per BUG-3063 / BUG-2716 precedent: `invoice_date = utcnow().date()` (precedent — confirm; decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** applied 2026-11-22 — rule(s) `_sync_draft_invoice_for_po` SD7, `_attach_return_invoice_for_po` AR1 state the intended behaviour, tagged [BUG-3167] with a *(Today: …)* note.

### P2. A blank void reason is accepted — 🐞 BUG-3168 (precedent)
**Background:** `PurchaseOrderVoidRequest.void_note` is a plain `str` (no minimum, not trimmed); `PurchaseOrderReturnVoidRequest.void_note` requires length ≥ 1 but is not trimmed. The reason is stored on the order and written into the log.
**What happens today:** voiding a PO with `""` or `"   "`, or cancelling a return with `"   "`, is accepted and stored as typed.
**Example:** PO-2026-031 is voided with an empty reason; its log reads `Purchase order #PO-2026-031 voided. Reason: `.
**Rules affected:** `void_purchase_order` V12, `void_return` VR7
**Answer:** bug — per BUG-626 / BUG-3064 precedent: both `void_note` fields are trimmed and must not be blank (422 at the schema, `app/schemas/purchase_order.py`, `app/schemas/purchase_order_return.py`), nothing written (precedent — confirm; decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** applied 2026-11-22 — rule(s) `void_purchase_order` V12, `void_return` VR7 state the intended behaviour, tagged [BUG-3168] with a *(Today: …)* note.

### P3. A voided PO can get a new draft invoice — 🐞 BUG-3169 (precedent)
**Background:** voiding unlinks the invoice but leaves the three section confirms on. BUG-2882 makes every manager edit of a voided PO refuse with 400 `Purchase order is voided`; "Create invoice" does not go through those guards.
**What happens today:** `POST /purchase-orders/{id}/create-invoice` on a voided PO with its sections confirmed creates a fresh draft payable invoice for the supplier.
**Example:** PO-2026-031 (35,000 taka) is voided as a duplicate; a click on "Create invoice" puts a new 35,000 taka draft bill on the supplier's account.
**Rules affected:** `create_invoice_for_purchase_order` CI2
**Answer:** bug — per BUG-3065 / BUG-754 precedent: refused with 400 `Purchase order is voided`, checked right after the order is read, nothing written (precedent — confirm; decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** applied 2026-11-22 — rule(s) `create_invoice_for_purchase_order` CI2 state the intended behaviour, tagged [BUG-3169] with a *(Today: …)* note.

### P4. Voiding clears approvals only when the order had an invoice — 🐞 BUG-3170 (precedent)
**Background:** voiding an order with a linked invoice clears every approval (`Cleared approvals — PO voided`); one without leaves them. The expense service's twin was ruled a bug (BUG-3067).
**What happens today:** two voided POs look different: one "0 of 2 approved", the other "2 of 2".
**Example:** PO-2026-050 and PO-2026-051 were both approved by two people and voided; only 050 had a draft invoice. 050 shows no approvals, 051 still shows both.
**Rules affected:** `void_purchase_order` V8
**Answer:** bug — per BUG-3067 precedent: every void clears the approvals with reason `Cleared approvals — PO voided`, invoice or not (precedent — confirm; decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** applied 2026-11-22 — rule(s) `void_purchase_order` V8 state the intended behaviour, tagged [BUG-3170] with a *(Today: …)* note.

### P5. One receive batch can name the same line twice and over-receive it — 🐞 BUG-3171 (precedent)
**Background:** each line of a receive batch is checked against the line's stored received quantity: the result may not exceed ordered − refunded. The return manager's twin check was ruled a bug when lines repeat (BUG-2751).
**What happens today:** a batch `[line 1 +6, line 1 +6]` on a line of 10 ordered, 0 received passes both checks (6 ≤ 10 each); the line ends at 12 received, and 12 units go into stock.
**Example:** a storekeeper's scanner sends the cement line twice; storage shows 120 bags against 100 ordered.
**Rules affected:** `create_receive_event` RE5
**Answer:** bug — per BUG-2751 precedent: lines naming the same PO line are added up in request order and the running total is checked (`Resulting received quantity for item {po_item_id} exceeds ordered quantity` / `cannot be negative` at the repeat that goes over), nothing written (precedent — confirm; decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** applied 2026-11-22 — rule(s) `create_receive_event` RE5 state the intended behaviour, tagged [BUG-3171] with a *(Today: …)* note.

### P6. Receive events: ties and their lines come back in no fixed order — 🐞 BUG-3172 (precedent)
**Background:** `GET /purchase-orders/{id}/receive-events/` orders events by `created_at` descending only; each event's lines come from a relationship with no order. The return manager's twin (BUG-2755) was ruled a bug.
**What happens today:** two events with the same timestamp, and the lines inside an event, come back in database order.
**Example:** a batch of three lines shows them in a different order after a reload.
**Rules affected:** `list_receive_events` LR2, `_build_receive_event_response` BR1
**Answer:** bug — per BUG-2755 precedent: events newest first, ties by `id` descending; each event's lines by `id` ascending (precedent — confirm; decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** applied 2026-11-22 — rule(s) `list_receive_events` LR2, `_build_receive_event_response` BR1 state the intended behaviour, tagged [BUG-3172] with a *(Today: …)* note.

### P7. "Active orders" lists voided purchase orders — 🐞 BUG-3173 (precedent)
**Background:** `GET /purchase-orders/active/` lists the non-terminal orders for a machine, factory or project component. A PO is skipped only when its stage is the last step of its workflow (`Complete`). The inventory manager's "incoming" twin was ruled a bug (BUG-717).
**What happens today:** a voided PO (stage unchanged by the void) is listed as active.
**Example:** PO-2026-031 for Machine 4 is voided as a duplicate; the machine page still shows it under active orders.
**Rules affected:** `list_active_orders_for_context` AO6
**Answer:** bug — per BUG-717 precedent: voided POs are not listed (precedent — confirm; decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** applied 2026-11-22 — rule(s) `list_active_orders_for_context` AO6 state the intended behaviour, tagged [BUG-3173] with a *(Today: …)* note.

### P8. Completing or cancelling a return does not set `updated_by` — 🐞 BUG-3174 (precedent)
**Background:** `purchase_order_returns` has `updated_by`. Return manager FU-1 (c) noted that `void_return` writes none. The invoice manager's twin (confirm / void / revert without `updated_by`) was ruled a bug (BUG-633).
**What happens today:** after "Complete return" or "Cancel return", `updated_by` stays the starter's (or `NULL`).
**Example:** Nadia cancels return PR-2026-004; the return still says it was last changed by Rahim, who started it.
**Rules affected:** `complete_return` CR7, `void_return` VR5, `receive_replacements` RX7
**Answer:** bug — per BUG-633 precedent: completing, cancelling and receiving replacements set `updated_by = user_id` (precedent — confirm; decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** applied 2026-11-22 — rule(s) `complete_return` CR7, `void_return` VR5, `receive_replacements` RX7 state the intended behaviour, tagged [BUG-3174] with a *(Today: …)* note.

### Follow-ups and existing bugs that land here — no new question
- **FU-1 / BUG-2734 (owner 2026-11-14).** A completed PO, or one with goods received, cannot be voided; use a return. Rules: `void_purchase_order` V2a, V2b. Detail texts and "goods received" = any line with `quantity_received > 0` now (a line whose goods were all returned counts as not received) decided by Claude under the reviewer's delegation (2026-11-21).
- **FU-2 / BUG-2810 (owner 2026-11-19).** New method `receive_replacements`, the write half of `validate_replacement_receipt` RR1–RR8, as return manager FU-2 (a)–(d). Rules: `receive_replacements` RX1–RX10. The money half is OQ-63 (OQ-POS-1) → BUG-3176, RX8a–RX8i.
- **FU-3 / BUG-3175.** `create_purchase_order` re-raises an `HTTPException` without `_rollback_transaction` (`except HTTPException: raise`): a 409 duplicate line or a 404 leaves the order, its approver row and its `created` event flushed in the session (manager Q7). Intended: TC3 — rolled back, nothing pending. Rule: `create_purchase_order` C5. (Decided by Claude under the reviewer's delegation (2026-11-21); the manager spec left it to this spec.)
- **FU-4 / BUG-2789 (owner OQ-48 refined).** `has_open_return` on the PO response, derived, never stored. Rules: *Return-in-progress flag* RF1–RF3. No new ID: the field is part of BUG-2789's intended behaviour.
- **FU-5 (manager Q6, clean-up).** `current_status_id` and `order_workflow_id` leave `PurchaseOrderCreate`. Sending them has no effect before and after (Pydantic ignores unknown fields), so the observable rule is unchanged: `create_purchase_order` C3. No bug.
- **BUG-1195 (existing).** The delete must record who deleted: the service takes `user_id` and passes it to the manager; the endpoint passes the current user. Rule: `delete_purchase_order` X2.
- **BUG-801 (existing).** A fractional return quantity on a storage / machine PO is refused when the return starts. Rule: `start_return` SR4.
- **BUG-2754 / BUG-800 (existing).** `complete_return` and `void_return` read the return `FOR UPDATE`. Rules: `complete_return` CR1, `void_return` VR1.
- **BUG-2641 (existing).** The list rows also carry the refunded total. Rule: `_attach_item_summaries` IS2.
- **BUG-2887 (existing, OQ-53).** A line edit that sends `quantity_received` is refused with 422 by the schema before this service runs. Rule: `update_item` UI1.

### New questions

### Q1. Receiving goods never marks the invoice "receiving started" — 🐞 BUG-3177
**Background:** a finalized PO invoice has a flag `receiving_started`; while it is set, the invoice cannot be reverted to draft (`account_invoice_manager` `revert_to_draft` R3, "goods have been received on the linked order. Record a return instead.", BUG-2736). The only code that sets it is the line edit's receiving path, which OQ-53 removes (BUG-2887). "Receive goods" (`create_receive_event`) never sets it.
**What happens today:** after goods are received through "Receive goods", the invoice's flag is still false; an invoice with nothing paid can be reverted to draft. That lifts the PO's financial lock, so its supplier, details and line prices become editable after the stock came in at those prices.
**Example:** PO-2026-060, 100 bags at 500 taka, invoice finalized at 50,000 taka; all 100 bags are received into storage. An accountant reverts the invoice, the buyer changes the price to 400 taka, and the invoice is finalized again at 40,000 taka, while storage values the bags at 500.
**Rules affected:** `create_receive_event` RE10
**Answer:** bug — the first receive event that changes a received quantity sets the invoice's `receiving_started` (as `set_receiving_started`, with its event), so the revert guard holds (decided by Claude under the reviewer's delegation (2026-11-21): the rule "goods received → no revert, record a return" is already approved in the invoice manager and by the owner's 2026-11-14 answers; this only connects the real receiving path to it)
**Resolution:** applied 2026-11-22 — rule(s) `create_receive_event` RE10 state the intended behaviour, tagged [BUG-3177] with a *(Today: …)* note.

### Q2. The list repairs the stage of only the first stale order per page — 🐞 BUG-3178
**Background:** the stage (`Draft` / `Planning` / `Receiving` / `Complete`) is derived from the order's state; reading an order repairs a stale stage and saves it.
**What happens today:** the list runs the repair as "is any order stale?", which stops at the first stale order. Later orders on the page keep their stale stage, and the response shows it. Each reload repairs one more.
**Example:** three POs on a page all became `Receiving` through an invoice action that skipped the stage step; the list shows the first as Receiving and the other two still as Planning.
**Rules affected:** `_prepare_listed_orders` PL2
**Answer:** bug — every listed order is repaired before the response is built (decided by Claude under the reviewer's delegation (2026-11-21): the method's evident intent; no workflow change)
**Resolution:** applied 2026-11-22 — rule(s) `_prepare_listed_orders` PL2 state the intended behaviour, tagged [BUG-3178] with a *(Today: …)* note.

### Q3. An items sync saves the lines and the draft invoice in two separate commits — 🐞 BUG-3179
**Background:** `POST /purchase-orders/{id}/items/sync/` adds, changes and removes lines, then keeps the draft invoice in step. `add_item`, `update_item`, `remove_item` do both in one transaction.
**What happens today:** the lines are committed first; the invoice step runs after. If it fails (e.g. 422 `The selected supplier account was not found. Re-select the supplier.`), the user sees an error but the line changes are saved and the draft invoice is out of step.
**Example:** a buyer syncs three new lines; the invoice step fails; the screen shows an error, the user retries, and the lines are added a second time (the first sync was saved).
**Rules affected:** `sync_items` SY2, SY3
**Answer:** bug — one transaction: the lines and the invoice step are committed together or not at all, as the single-line methods (decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** applied 2026-11-22 — rule(s) `sync_items` SY2, SY3 state the intended behaviour, tagged [BUG-3179] with a *(Today: …)* note.

### Q4. Receive notes: a blank value is stored as empty text, and the log repeats the untrimmed text — 🐞 BUG-3180
**Background:** a receive event takes an optional RCC number, "received by" and correction note. They are trimmed before storing.
**What happens today:** `"   "` is stored as `""` (not `NULL`); the log description and metadata use the text as sent, untrimmed (`RCC:  77 .`), and a blank value still adds ` RCC:    .` to the log.
**Example:** "received by" typed as `" Karim "` is stored `Karim` on the event but shows ` Received by:  Karim .` in the activity log.
**Rules affected:** `create_receive_event` RE7, RE8
**Answer:** bug — each text is stored trimmed, blank → `NULL`; the log and metadata use the stored values and leave out a blank one (decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** applied 2026-11-22 — rule(s) `create_receive_event` RE7, RE9 state the intended behaviour, tagged [BUG-3180] with a *(Today: …)* note.

### Q5. Cancelling a pending return whose credit note is already voided is impossible — 🐞 BUG-3182
**Background:** "Cancel return" voids the credit note and marks the return voided. Before BUG-2788 is fixed, an accountant can void the credit note on the invoice page and leave the return pending (legacy data after the fix).
**What happens today:** "Cancel return" on such a return answers 400 `Invoice is already voided` (from the invoice manager) and nothing changes: the return stays pending forever, its quantity stays reserved, and it can still be completed.
**Example:** PR-2026-004's credit note was voided on the invoice page; the storekeeper's "Cancel return" fails, and the 3 motors it reserved can never be returned again.
**Rules affected:** `void_return` VR3
**Answer:** bug — a credit note that is already voided is skipped and the cancel goes ahead (return → `voided`, `paid` re-synced) (decided by Claude under the reviewer's delegation (2026-11-21): no money moves — the note is already void)
**Resolution:** applied 2026-11-22 — rule(s) `void_return` VR3 state the intended behaviour, tagged [BUG-3182] with a *(Today: …)* note.

### Q6. The replacement step could fill a line already re-received the normal way — 🐞 BUG-3181
**Background:** a `replace` return on a PO that is **not** completed lowers the line's received quantity; the gap can be re-received through "Receive goods" (allowed while the PO is not complete) **or** through the new "receive replacements" step (BUG-2810), whose limit is only "not more than went back" (RR5).
**What happens today:** the replacement step does not exist yet; as specified, after the gap was refilled through "Receive goods", it would accept the same quantity again.
**Example:** 10 ordered, 10 received; a replace return of 4 completes (received 6). The supplier's 4 come in through "Receive goods" (received 10). Then someone records them again as replacements: received 14 on 10 ordered, and stock has 4 phantom bearings.
**Rules affected:** `receive_replacements` RX4
**Answer:** bug — the replacement step also refuses when the PO line would go above ordered − refunded: 400 `Cannot receive {q} replacement(s) for line {line_number} — the line is already fully received`, nothing written (decided by Claude under the reviewer's delegation (2026-11-21): it is the stated invariant of FU-2, "stock cannot grow past what was bought"; the check may live in `validate_replacement_receipt` as RR5a)
**Resolution:** applied 2026-11-22 — rule(s) `receive_replacements` RX4 state the intended behaviour, tagged [BUG-3181] with a *(Today: …)* note.

### Q7. Two lines of `create_purchase_order` can never run — remove
**Background:** creation retries up to 5 times when the PO number clashes. After the loop the code raises 409 when the last error was a number clash, else re-raises it, else raises 500 `Failed to create purchase order`.
**What happens today:** the loop is left only after 5 number clashes (any other error leaves earlier), so only the 409 can run; the re-raise and the 500 cannot.
**Example:** —
**Rules affected:** none (Branch map rows 382, 383–386)
**Answer:** remove (decided by Claude under the reviewer's delegation (2026-11-21)) — `purchase_order_service.py:382-386`; for `docs/testing/dead-code-removal-checklist.md` at apply-review. Not a bug.
**Resolution:** lines 382–386 listed under Not specified as dead code and added to `docs/testing/dead-code-removal-checklist.md`; Branch-map row removed. No bug.

### Q8. GET and the list commit when they repair a stage — ✅ intended
**Background:** TC6 says a read neither commits nor rolls back.
**What happens today:** `get_purchase_order` and the list commit when the stage repair changed anything (stage or workflow id), and `GET` re-reads the order. A failing repair raises without a rollback.
**Example:** opening a stale PO saves its new stage and writes one `status_updated` event with no performer.
**Rules affected:** `get_purchase_order` G2, `_prepare_listed_orders` PL3
**Answer:** intended — the stage is derived state, and saving the repair on read is how the module keeps it current; request sessions hold nothing else (decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** ✅ intended — rules `get_purchase_order` G2, `_prepare_listed_orders` PL3 unchanged, marked ✅.

### Q9. Integrity-error mapping has branches no database constraint can reach — ✅ intended
**Background:** `_handle_item_integrity_error` turns database errors into 400 / 409 messages (ordered < received, total < paid, duplicate catalog item, duplicate draft invoice, missing values, bad references).
**What happens today:** the database has no check constraint on lines or invoices and no unique index on (order, item) or on drafts per order, so the check-constraint and duplicate branches cannot fire from the database; the not-null and foreign-key branches can.
**Example:** —
**Rules affected:** `_handle_item_integrity_error` IE1–IE9
**Answer:** intended — a generic mapper; every branch is tested directly with a constructed `IntegrityError`, and stays ready for constraints added later (e.g. HR-10 / HR-2 fixes) (decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** ✅ intended — rules `_handle_item_integrity_error` IE1–IE9 unchanged, marked ✅.

### Q10. Only the list fills item counts and totals — ✅ intended
**Background:** `PurchaseOrderResponse` has `item_count`, `quantity_ordered_total`, `quantity_received_total`, `item_names_preview` (defaults 0 / 0 / 0 / `[]`) and `invoice_payment_status`.
**What happens today:** the list fills all of them; `GET` fills only `invoice_payment_status`; create, update, complete, void, sync and "create invoice" fill none (payment status `null`).
**Example:** `GET /purchase-orders/7/` of an order with 3 lines says `item_count: 0`.
**Rules affected:** `get_purchase_order` G1, the write methods' "Returns"
**Answer:** intended — the summary fields serve the list rows; the order page reads its lines from `/items/` (decided by Claude under the reviewer's delegation (2026-11-21)). `has_open_return` is different and goes on every PO response (RF1).
**Resolution:** ✅ intended — rules `get_purchase_order` G1, the write methods' "Returns" unchanged, marked ✅.

### OQ-POS-1. Receiving a `replace` return's replacements leaves its credit note owed — 🐞 BUG-3176 ([OQ-63](../../../docs/testing/owner-questions.md))
**Background:** when any return starts, the system makes a credit note at once and finalizes it: for a purchase return it says "the supplier owes us" the returned quantity × the return price. For a `refund` return that is the point. For a `replace` return the supplier sends the same goods again instead of money; the owner decided (2026-11-19) that those replacements come in through the return's own "receive replacements" step, at the original cost, without touching the PO or its invoice. Nothing in that step touches the credit note. And the owner also decided (OQ-47) that the credit note of a **completed** return can no longer be voided.
**What happens today / as specified:** after the replacements arrive, the credit note still says the supplier owes us the full amount, and nobody can void it.
**Example:** PO-2026-050 bought 10 bearings at 500 taka (5,000 taka, paid). 4 are faulty; a `replace` return for 4 is started, so a 2,000 taka credit note "supplier owes us" is finalized; the 4 go back. The supplier sends 4 new bearings, received as replacements: storage is back to 10 bearings, and accounts still show the supplier owing us 2,000 taka.
**Rules affected:** `receive_replacements` RX8
**Recommended answer:** (a) receiving replacements settles the credit note by the replaced value.
**Options for the owner:**
- **(a) The replacements settle the credit note — recommended.** Each time replacements are received, the system records a settlement on the return's credit note for their value (quantity × the return price, rounded half up), marked as "settled by replacement", not as cash. When every replaced unit has arrived the credit note is fully settled and the return shows as paid. In the example: 4 bearings arrive, a 2,000 taka "settled by replacement" entry goes on the credit note, and the supplier owes nothing. If only 3 arrive, 1,500 taka is settled and 500 taka stays owed, which the accountant can collect in cash. Accounts and stock always agree, and the record shows how the debt was settled.
- **(b) A `replace` return gets no credit note at all.** Only refund returns make a credit note. In the example: no 2,000 taka note is made when the 4 bearings go back. Simple when the supplier always replaces, but while we wait (or if the supplier never sends them) nothing in accounts shows that they hold 2,000 taka of our goods; someone must remember to start a refund instead.
- **(c) Keep the credit note as it is.** The 2,000 taka stays owed after the bearings are replaced, and since the note can't be voided, an accountant must record a manual "payment" on it to clear it. Easy to forget, and until then the supplier appears to owe us money they don't — someone could even collect it twice.
**Answer:** (a) — owner, OQ-63 (2026-11-22): receiving replacements settles the credit note, fully recorded: a non-cash payment entry of method "settled by replacement" for qty × return price rounded half up, with its date, the person who received the goods and a link to the receipt; an event on the return and an activity entry on the PO; the stock-in ledger row linked to the return. A partial receipt settles only its own share; the rest stays owed. A settlement entry is never deleted, only voided with a reason, like any payment.
**Resolution:** `receive_replacements` RX8 split: RX8 (order and invoice untouched) stays; RX8a–RX8i [BUG-3176] state the settlement and its trail. Two details decided by Claude under the reviewer's delegation (2026-11-21), nearest owner answer OQ-64: the entry is capped at what the credit note still has outstanding (nothing is settled twice), and when nothing is outstanding no entry is written and the response says so.

## Overview
`PurchaseOrderService` is the transaction layer for purchase orders. Around `PurchaseOrderManager` it commits or rolls back, and it owns what spans modules: the order's **draft payable invoice** (made when supplier, details and items are all confirmed, kept in step with the order while it is a draft, removed when a section is unconfirmed), **receiving** (receive batches and corrections that move stock through `po_receive_inventory`), **returns** (start with a finalized credit note, complete with stock out through `po_return_inventory`, cancel), **voiding** (reverses received stock, voids or deletes the invoice), the cross-order **"active orders"** list for a machine / factory / project component, the hub list and stats, and **approval notifications** (`approval_notification_service`). Callers: `app/api/v1/endpoints/purchase_orders.py` only (and `AccountInvoiceService.resync_items`, which uses `_build_invoice_items_from_po`). Invariants it is meant to protect: received stock matches received quantities; a draft invoice mirrors the order's supplier, description and lines; a finalized invoice is never changed by order edits; a voided order holds no stock and no live invoice.

**Callables:** 42 specified (41 existing + new `receive_replacements`; plus the derived flag RF1–RF3) · 1 not specified (+ dead lines, Q7)
**Externals to mock:** `utcnow` — patch `app.services.purchase_order_service.utcnow` (`items_updated_at`, `voided_at`, return `completed_at`), plus the manager's / posting modules' own targets when a test depends on them. `date.today()` (invoice dates, SD7, AR1) reads the system clock (P1 moves it to `utcnow`). Notifications are **not** mocked: they are `notifications` rows written in the same transaction (`approval_notification_service.spec.md`).
**Integration-only behavior:** the race half of BUG-3162 (two sessions); at unit level the lock is checked by SQL capture.

### Transaction contract
Every write method follows **TC1–TC6** of `tests/unit/services/base_service.spec.md`: manager / posting / invoice / notification steps, `_commit_transaction`, `db.refresh` of the returned row, all in one `try`; any exception rolls the session back and is re-raised as the same object. Departures, stated in the callable:
- `create_purchase_order` — retries a PO-number clash (C2); re-raises an `HTTPException` **without** rollback today (C5, BUG-3175).
- `update_purchase_order`, `add_item`, `update_item`, `remove_item`, `sync_items`, `create_invoice_for_purchase_order` — an `IntegrityError` is rolled back and **translated** to an `HTTPException` per `_handle_item_integrity_error` (not the same object).
- `create_invoice_for_purchase_order` — an `IntegrityError` when the order already has an invoice after the rollback returns the order without error (CI6).
- `sync_items` — two commits today (SY2, BUG-3179).
- `create_receive_event` — the refusals RE1–RE5 run before the `try`: nothing is rolled back (nothing was written by the call).
- `get_purchase_order`, the list — a read that commits when the stage repair changed something (Q8, intended).
- `delete_purchase_order`, `remove_approver` return `None`; `remove_item` returns the deleted line without a refresh.

**Facts for the test designer**
- Import: `from app.services.purchase_order_service import PurchaseOrderService, purchase_order_service`. `PurchaseOrderService()` takes no arguments; `.manager` is `purchase_order_manager`, `.account_invoice_manager` is `account_invoice_manager`.
- The order's invoice: `purchase_orders.invoice_id` (FK `ON DELETE SET NULL`); the invoice carries `order_type = "purchase_order"`, `order_id`, `invoice_type = "payable"`. A return's credit note: `purchase_order_returns.invoice_id`, `invoice_type = "receivable"`, same `order_type` / `order_id`.
- Order events: `purchase_order_events` (`event_type`, `description`, `metadata`, `performed_by`); invoice events: `invoice_events`.
- Stage rows and workflow: as the PO manager spec Notes (`statuses` `Draft`, `Planning`, `Receiving`, `Complete`; `order_workflows.type = 'purchase'`). `po.order_completed` reads the `current_status` relationship — `db.expire(po)` after a stage change.
- **Constraints that limit Givens (executor DISCREPANCY-2, -9).** `order_workflows` has `uq_order_workflows_workspace_type` (`workspace_id`, `type`): **one** `type = 'purchase'` workflow per workspace, so a second purchase workflow in W1 cannot be built. Vary the existing one instead (update WF1's `sequence`), or use another workspace. The stock table is `inventory` (model `Inventory`), not `inventories`; count `inventory` in every "nothing written" snapshot.
- An account that can be invoiced: `Account(is_active=True, is_deleted=False, allow_invoices=True)` of the workspace.
- Receive events: `po_receive_events` / `po_receive_event_items`; stock rows and ledgers per `po_receive_inventory.spec.md` / `po_storage_inventory.spec.md` / `po_machine_inventory.spec.md`.
- Notification rows: `notifications` (`recipient_user_id`, `notification_type`, `entity_type = "purchase_order"`, `entity_id`, `preview`); recipients must be active `workspace_members`.
- **Input schemas (gap 1).** `app/schemas/purchase_order.py`: `PurchaseOrderCreate` (`account_id?`, `destination_type`, `destination_id`, `order_date?`, `expected_delivery_date?`, `description?`, `current_status_id?`, `order_workflow_id?` — the last two dropped by FU-5 —, `required_approvals?`, `items?: list[PurchaseOrderItemCreate]`); `PurchaseOrderUpdate` (`account_id`, `destination_type`, `destination_id`, `order_date`, `expected_delivery_date`, `current_status_id`, `invoice_id`, `required_approvals`, `description`, `supplier_confirmed`, `details_confirmed`, `items_confirmed`, `invoice_confirmed`, all optional); `PurchaseOrderItemCreate` (`item_id`, `quantity_ordered`, `unit_price?`, `notes?`); `PurchaseOrderItemUpdate` (`quantity_ordered?`, `quantity_received?`, `unit_price?`, `notes?`); the items-sync body `PurchaseOrderItemSyncRequest` (`remove_ids: list[int] = []`, `updates: list[PurchaseOrderItemSyncUpdate] = []` with `id`, `quantity_ordered`, `unit_price?`, `additions: list[PurchaseOrderItemCreate] = []`); `PurchaseOrderVoidRequest` (`void_note`). `app/schemas/po_receive_event.py`: `PoReceiveEventCreate` (`event_type`, `rcc?`, `received_by?`, `correction_note?`, `items: list[PoReceiveEventItemCreate]` with `po_item_id`, `quantity_delta`). `po_receive_event_items.receive_event_id` is the FK to `po_receive_events.id` (`ON DELETE CASCADE`); `po_item_id` FK to `purchase_order_items.id`.
- **Ledgers (gap 8).** Stock rows are `inventory_ledger` (storage) and `machine_item_ledger` (machine); both have `transaction_type` (String(50), NOT NULL), `source_type`, `source_id`. A PO receipt writes `transaction_type = 'purchase_order'`; void reversals and corrections write `'inventory_adjustment'`.
- **Other order kinds read by "active orders" (gap 11).** `transfer_orders`: `transfer_number`, `source_location_type` / `source_location_id`, `destination_location_type` / `destination_location_id` (types `storage`, `machine`, `project`, `damaged`), `current_status_id` (FK `statuses`, NOT NULL, the `current_status` relationship), `description`, `created_at`, `completed_at` (NULL = not completed); no void or soft-delete column. `work_orders`: `work_order_number`, `title`, `status` (String(20): `DRAFT`, `IN_PROGRESS`, `COMPLETED`, `VOIDED`), `machine_id?`, `project_component_id?`, `cost` (Numeric(15,2), nullable), `created_at` (server default), `is_deleted`. `machines` and `factories` have `is_deleted`; `project_components` is looked up by id and workspace only. The work-order read is `work_order_dao.get_by_workspace` (live rows, `created_at` descending, `limit=1000`, machine filter only when `machine_id` is truthy).
- **Row locks (gap 2; coordinator decision 2026-11-22).** Each locked read has one exact clause, never `NOWAIT` or `SKIP LOCKED`:
  | Read | Table locked | Exact clause | Why |
  |---|---|---|---|
  | the order in RE1, V1, CI1, RX1a | `purchase_orders` | `FOR UPDATE OF purchase_orders` | `get_purchase_order` eager-loads `current_status` with a LEFT OUTER JOIN to `statuses`; Postgres refuses a bare `FOR UPDATE` on the nullable side of an outer join (BUG-029 rule) |
  | the return in CR1, VR1, RX1 | `purchase_order_returns` | `FOR UPDATE` | single-table read (`get_by_id_and_workspace`; the return model has no joined eager load) |
  | the credit note in RX8a | `account_invoices` | `FOR UPDATE` | single-table read, as `InvoicePaymentManager.create_payment` already locks it today |
  The clause ends the statement. Lock order inside `receive_replacements`: order → return → credit note (CR / VR lock only the return, then the credit note through the invoice manager, so the order is the same and no deadlock arises).
- **Return event log (gap 3; new, BUG-3176).** Table `purchase_order_return_events`, model `PurchaseOrderReturnEvent` in `app/models/purchase_order_return.py`, mirroring `purchase_order_events`: `id`, `workspace_id` (FK `workspaces`, CASCADE, NOT NULL), `return_id` (FK `purchase_order_returns.id`, CASCADE, NOT NULL, indexed), `event_type` (String(50), NOT NULL), `description` (Text, NOT NULL), `metadata` (JSON, attribute `metadata_json`), `performed_by` (FK `profiles`, SET NULL), `created_at` (default `utcnow`). Only `receive_replacements` writes it for now.
- **Settlement link columns (gap 4; new, BUG-3176).** On `invoice_payments`: `source_type` (String(50), nullable) and `source_id` (Integer, nullable). A settlement entry has `source_type = 'purchase_order_event'`, `source_id` = the id of RX9's `purchase_order_events` row. Ordinary payments leave both NULL.
- **Numbers in texts (gap 7).** A quantity total printed in an event text is `str()` of the Python sum of the values it adds: values **as sent** in the request keep their own form (`4` → `4`, `1.50` + `2` → `3.50`); values read back from a stored `Numeric(15,2)` column print with 2 places (`4.00`). Each rule below says which one it uses.

**Notes for the test designer**
- **Seeing C5 / BUG-3175 (executor DISCREPANCY-6, C-09).** The missing rollback is visible only *inside the same session, before any test-level rollback*. Given: flush an unrelated marker row first (e.g. a `Department` of W1) and remember its id; make the manager refuse with 409 after it flushed the order (a duplicate line). Then, with **no** `db.rollback()` first: `db.query(PurchaseOrder).filter_by(workspace_id=W1.id, description=<the sent description>).count() == 0` and the marker row is gone (TC3: every pending change discarded). Today both are still found, so the card fails as designed. `committed:` checks cannot see this bug.
- Session and commits as in `base_service.spec.md` Notes: under the `db` fixture `commit()` releases a savepoint; assert "committed" with a test-level `db.rollback()` and a re-select.
- To reach "draft invoice exists": create a PO with a supplier, destination, order date and a priced line, then confirm supplier, details and items through `update_purchase_order` (three calls or one body).
- To reach "invoice finalized": `account_invoice_manager.confirm_invoice` on that draft, then `purchase_order_manager.apply_post_invoice_confirms`.
- `IntegrityError` for `_handle_item_integrity_error`: build one with `sqlalchemy.exc.IntegrityError("stmt", {}, orig)` where `orig` is an object with `pgcode` and `diag` (`table_name`, `column_name`) attributes, and a `str()` you choose.
- Row-lock cases (H1): capture SQL with a `before_cursor_execute` listener and look for the exact clause of the **Row locks** table on the named table, sent before the first state check.

## Not specified
- `PurchaseOrderService.__init__` — wires the two managers, no logic.
- `create_purchase_order` lines 382–386 (re-raise / 500 after the loop) — dead code, to be removed (reviewer delegation, Q7).

---

## Shared: Return-in-progress flag (FU-4, owner OQ-48 refined) — *requires new field*
- **RF1.** [BUG-2789] Every `PurchaseOrderResponse` this service returns (get, list items, create, update, complete, void, sync items, create invoice) carries `has_open_return: bool` = `PurchaseOrderReturnManager.has_open_return(po id, workspace)` at the time the response is built (`True` while a return of this order in this workspace is `pending`). Never stored. *(Today: no such field.)* Which responses carry it decided by Claude under the reviewer's delegation (2026-11-21).
- **RF2.** What the order shows follows `sales_manager.spec.md` RP3 (completed + flag → "return in progress"; completed, no flag → "completed"; not completed → its stage). Completing or cancelling the last pending return turns the flag off with nothing written on the order (RP6, RP7).
- **RF3.** Reading the flag writes nothing.

---

## `PurchaseOrderService._integrity_context(exc)`
**Shape:** helper · **Persistence:** pure · **Visibility:** internal (used by: `_handle_item_integrity_error`)
**Returns:** `(table, column)`.
**Rules:**
- **IC1.** `(exc.orig.diag.table_name, exc.orig.diag.column_name)`; each is `None` when `orig`, `diag` or the attribute is missing (an `orig` / `diag` that is falsy counts as missing).
- **IC1a.** [BUG-3184] An attribute that is present but empty (`""`) is also returned as `None`, for the table and the column alike (a `diag` with `table_name = "account_invoices"`, `column_name = ""` → `("account_invoices", None)`). *(Today: the empty string is returned as is → `("account_invoices", "")`; executor DISCREPANCY-3, IC-04.)* Decided by Claude under the reviewer's delegation (2026-11-22).

---

## `PurchaseOrderService._handle_item_integrity_error(exc, *, phase='items')`
**Shape:** mapper · **Persistence:** pure · **Visibility:** internal (used by: `update_purchase_order` (`phase='invoice'`), `add_item`, `update_item`, `remove_item` (`'items'`), `sync_items` (both), `create_invoice_for_purchase_order` (`'invoice'`))
**Purpose:** turn a database integrity error into a user message.
**Returns:** never; always raises `HTTPException` chained `from exc`.
**Rules** (`combined` = lower-cased `str(exc)` + space + lower-cased `str(exc.orig)`; `table`, `column` per `_integrity_context`; first group that matches wins, in this order):
- **IE1.** Check violation — `pgcode == '23514'`, or `combined` contains `check constraint` or `23514`: ✅
  - `combined` contains `quantity_ordered`, or `quantity_received`, or both `ordered` and `received` → 400 `Ordered quantity cannot be less than received quantity`;
  - else contains `invoice_amount` or `paid_amount` → 400 `Order total cannot be less than amount already paid on the linked invoice`;
  - else → 400 `Update violates a business rule. Check amounts and quantities.`
- **IE2.** Unique violation — `pgcode == '23505'`, or `combined` contains `unique constraint` or `duplicate`: `table == 'account_invoices'` or `phase == 'invoice'` → 409 `A draft invoice for this order already exists`; else → 409 `That catalog item is already on this purchase order`. ✅
- **IE3.** Not-null violation — `pgcode == '23502'`, or `not-null constraint` / `null value`: `table` in (`account_invoices`, `financial_audit_logs`, `invoice_status_tracker`) or `phase == 'invoice'` → 400 `Could not sync the draft invoice for this order{loc}. Save the supplier section again, then retry editing items.`; else → 400 `Order line data is incomplete{loc}. Refresh the page and try again.` `{loc}` = ` (<table>.<column>)` when both are known, else empty. ✅
- **IE4.** Foreign-key violation — `pgcode == '23503'`, or `foreign key constraint`: `table` in (`account_invoices`, `financial_audit_logs`) or `phase == 'invoice'` → 400 `The selected supplier or linked invoice is invalid. Refresh and try again.`; else → 400 `A linked catalog item or order reference is missing. Refresh the page and try again.` ✅
- **IE5.** Anything else: logged (`logger.exception`), then `phase == 'invoice'` → 400 `Could not sync the draft invoice after saving items. Refresh and try again.`; else → 400 `Could not save order items. Refresh the page and try again.` ✅
- **IE6.** The text tests run on `combined`, so a not-null error whose message mentions `duplicate` is IE2 (groups are tried in IE1 → IE5 order). ✅
- **IE7.** A `phase` other than `items` / `invoice` behaves as `items`. ✅
- **IE8.** Reachability today (Q9, intended): only IE3, IE4, IE5 can come from the database (no check constraints, no unique index on lines or drafts); IE1, IE2 are tested with constructed errors. ✅
- **IE9.** Nothing is written. ✅

---

## `PurchaseOrderService._build_invoice_items_from_po(po)`
**Shape:** mapper · **Persistence:** pure (reads `po.line_items`) · **Visibility:** internal (used by: `_sync_draft_invoice_for_po`; `AccountInvoiceService.resync_items`)
**Returns:** `list[dict]`.
**Rules:**
- **BI1.** One dict per line of `po.line_items`, in `line_number` ascending; no lines (or `line_items` missing / `None`) → `[]`.
- **BI2.** Each dict: `line_number`, `description` = the line's `item_name` or, when empty, `Item {item_id}`, `item_id`, `source_order_item_id` = the line id, `source_order_item_type = "po_item"`, `quantity` = `quantity_ordered` (not received), `unit` = `item_unit`, `unit_price`, `line_subtotal` as stored on the line (rounding per the manager's BUG-2876).

---

## `PurchaseOrderService._delete_linked_draft_invoice_for_po(db, po, workspace_id, user_id)`
**Shape:** delete · **Persistence:** writes · **Visibility:** internal (used by: `_sync_draft_invoice_for_po`)
**Purpose:** drop the automatic draft when a base section is no longer confirmed.
**Rules:**
- **DD1.** No `invoice_id`, or the invoice is not found in the workspace, or its status is not `draft` → nothing written.
- **DD2.** A draft → deleted per `AccountInvoiceManager.delete_invoice` (its refusals pass through, e.g. 400 `Invoice has payment history — confirm and void it instead`, BUG-639), then the order is unlinked per `PurchaseOrderManager.unlink_invoice_from_po` with event `invoice_draft_deleted` / `Draft invoice #<id> deleted`, metadata per DD2a. Flushed, not committed.
- **DD2a.** [BUG-3185] The `invoice_draft_deleted` event's metadata is `{"invoice_id": <id of the deleted draft>}`. *(Today: `{"invoice_id": null}`: deleting the draft clears `po.invoice_id` before `unlink_invoice_from_po` reads it; executor DISCREPANCY-4, DD-04.)* Fix: hand the id read before the delete to the unlink (as BUG-3204 on the sales side). Decided by Claude under the reviewer's delegation (2026-11-22).

---

## `PurchaseOrderService._sync_draft_invoice_for_po(db, po, workspace_id, user_id, force_create=False)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** internal (used by: create, update, add / update / remove / sync items, `create_invoice_for_purchase_order` with `force_create=True`)
**Purpose:** make sure the order has a draft payable invoice that mirrors it, or none while its base sections are not all confirmed.
**Returns:** the new invoice id when a draft was created in this call, else `None`. Flushed, not committed.
**Rules** (in this order; "confirmed" = supplier, details and items all confirmed, `invoice_confirmed` not read):
- **SD1.** Order financially locked (its invoice is `confirmed` / `locked`, `is_po_financially_locked`) → `None`, nothing written.
- **SD2.** Not `force_create` and not confirmed → the linked draft is removed per `_delete_linked_draft_invoice_for_po`; `None`.
- **SD3.** `force_create` and not confirmed → 422 `Confirm supplier, order details, and items before creating a draft invoice`.
- **SD4.** No supplier (`account_id` `None`) → `None`, nothing written.
- **SD5.** No invoice linked → a draft is created per `AccountInvoiceManager.create_invoice` (all its rules, e.g. 403 `Invoices are not allowed for this account`, 400 inactive account pass through), with `account_id` = the supplier, `order_id`, `order_type = "purchase_order"`, `invoice_type = "payable"`, `invoice_number` and `vendor_invoice_number` `None`, `due_date` `None`, `description = "Purchase order <po_number>"`, `notes` = the order's `description`, `allow_payments = True`, `payment_locked_reason` `None`.
- **SD6.** Then `po.invoice_id` = the new id and `invoice_ever_linked = True` (flushed); the lines are copied per `_build_invoice_items_from_po` through `sync_items_from_list` (amount = sum of lines); one PO event `invoice_draft_created` / `Draft invoice #<id> linked to <po_number>`, metadata `{"invoice_id": <id>}`. Returns the id.
- **SD7.** [BUG-3167] `invoice_date` = `utcnow().date()`. *(Today: `date.today()`, the server's local date.)*
- **SD8.** The create answering 404 (the supplier account is not found in the workspace): the order is re-read; if it now has an invoice → `None` (no error); else 422 `The selected supplier account was not found. Re-select the supplier.` Any other `HTTPException` passes through unchanged.
- **SD9.** An invoice is linked but not found in the workspace, or not `draft` (e.g. `voided`) → `None`, nothing written.
- **SD10.** A linked draft: if the invoice's account differs from the order's supplier **and** the order's `invoice_confirmed` is true → `invoice_confirmed = False`, approvals reset per `reset_approvals` (reason `Draft invoice changed after order update`), one `section_confirm` notification to the creator with preview `Draft invoice changed — approvals reset; re-confirm sections` (per `notify_section_confirm_needed`), and PO event `invoice_unconfirmed` / `Draft invoice unconfirmed after order sync`. (Reachable when the draft's account was changed on the invoice page.)
- **SD11.** A linked draft: the invoice's `account_id`, `description` (`Purchase order <po_number>`) and `notes` (the order's description; `""` and `None` count as equal) are updated per `update_invoice` — only the ones that differ; none differ → no update call. Then the lines are always re-copied (`sync_items_from_list`, one `items_synced` invoice event every time). Returns `None`.

**Errors:** SD3, SD8; those of `create_invoice`, `update_invoice`, `delete_invoice`, `sync_items_from_list` (an `IntegrityError` for a line with no price reaches the caller's mapper).

---

## `PurchaseOrderService._emit_po_invoice_draft_notification(db, po, workspace_id, user_id, invoice_id)`
**Shape:** event-log · **Persistence:** writes · **Visibility:** internal (used by: create, update)
**Rules:**
- **EN1.** `invoice_id` `None` → nothing.
- **EN2.** Else `notify_invoice_action` with `action = "draft"`, `entity_type = "purchase_order"`: pending approvers, all approvers when `required` > 0, and the creator each get one `invoice_action` row (preview `draft|Linked payable invoice is in draft — confirm when details look correct`), per that spec R1–R6.

---

## `PurchaseOrderService.create_purchase_order(db, po_in, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /purchase-orders/`)
**Returns:** the new order, committed and refreshed.
**Rules:**
- **C1.** The order is created per `PurchaseOrderManager.create_purchase_order` (all its rules and errors) and committed (TC1, TC2). A new order has no section confirmed, so no invoice is drafted and no notification is written (`_sync_draft_invoice_for_po` SD2 with nothing linked).
- **C2.** A flush failing on the PO-number constraint (`IntegrityError` whose text contains `po_number` or `uq_po_workspace_number`) is rolled back and the whole create retried, up to 5 attempts; the 5th such failure → 409 `Could not assign a unique PO number. Please try again.` (chained from it), nothing saved. A first-try success makes one attempt only. [BUG-2631] after the DAO fix the retry is not needed; the rule still holds.
- **C3.** (FU-5) `current_status_id` / `order_workflow_id` sent in the body have no effect: the order is `Draft` in the purchase workflow (manager C-R2). After the schema clean-up they are unknown fields and are ignored the same way; no error either way.
- **C4.** Any other `IntegrityError` is rolled back and re-raised unchanged, no retry; any other non-HTTP exception is rolled back and re-raised (TC3).
- **C5.** [BUG-3175] An `HTTPException` from the manager (409 duplicate line, 404 supplier / item / destination after BUG-1017 / BUG-2874) is re-raised unchanged **and the session rolled back**: the order, approver row and `created` event the manager had flushed are not pending afterwards (TC3). *(Today: re-raised without rollback; those rows stay flushed in the session.)*

**Errors:** C2's 409; the manager's.

---

## `PurchaseOrderService.update_purchase_order(db, po_id, po_in, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (`PUT /purchase-orders/{id}/`, `PATCH /purchase-orders/{id}/section-confirm/`)
**Returns:** the order, committed and refreshed.
**Rules:**
- **U1.** The order is read first (404 `Purchase order with ID {po_id} not found` for a missing or other workspace's id, rolled back); then the edit follows `PurchaseOrderManager.update_purchase_order` (all its rules and errors: voided BUG-2882, completed BUG-2885, locks, confirm checks, `invoice_id` refused BUG-1017).
- **U2.** Notifications after the edit, per `handle_order_update_notifications` R1–R5 with `was_ready` = supplier, details and items all confirmed **before** the edit and `section_was_unconfirmed` = `detect_section_unconfirmed` on the body (fields sent and not `null`): an unconfirm → the creator gets `Approvals were reset — re-confirm sections before approving` (when the order has approvers); ready → not ready → the creator gets the gap text; not ready → ready → every pending approver gets `approval_pending`.
- **U3.** Then the invoice step per `_sync_draft_invoice_for_po` (not forced): the edit that confirms the last of the three sections drafts the invoice (SD5–SD7) and sends the draft notice (EN2); an unconfirm removes the draft (SD2); an edit of a confirmed, not locked order re-syncs the draft (SD10–SD11).
- **U4.** Everything is committed together (TC1, TC2); any error of U1–U3 rolls back the edit too (TC3). An `IntegrityError` is rolled back and translated per `_handle_item_integrity_error` with `phase='invoice'`.
- **U5.** Has no `has_open_return` today (RF1).

---

## `PurchaseOrderService.get_purchase_order(db, po_id, workspace_id)`
**Shape:** get-or-404 · **Persistence:** reads (writes the stage repair) · **Visibility:** public (`GET /purchase-orders/{id}/`)
**Rules:**
- **G1.** Returns the order per `PurchaseOrderManager.get_purchase_order` (voided and completed included; other workspace → 404), with `invoice_payment_status` per `_attach_invoice_payment_status`. Item summary fields keep their defaults (Q10). ✅ The ORM `PurchaseOrder` has **no** `item_count`, `quantity_ordered_total`, `quantity_received_total` or `item_names_preview` attribute: they exist only on the list rows (IS1) and as `PurchaseOrderResponse` defaults (0 / 0 / 0 / `[]`). "Keep their defaults" is observable only through the schema: `PurchaseOrderResponse.model_validate(result).item_count == 0`, and `not hasattr(result, "item_count")` on the returned object (executor DISCREPANCY-7).
- **G2.** The stage is repaired per `sync_po_stage` with no performer: if it changed the stage or workflow id, the change is committed (one `status_updated` event, `performed_by` `NULL`) and the order re-read; else nothing is committed (Q8, intended). A failing repair (e.g. 422 missing stage row) raises with no rollback. ✅

---

## `PurchaseOrderService.mark_order_complete(db, po_id, workspace_id, user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST /purchase-orders/{id}/complete/`)
**Rules:**
- **MC1.** Completes per `PurchaseOrderManager.mark_order_complete` (voided refused BUG-2882; not fully received → 400; open return → 400; already complete → unchanged) and commits (TC1–TC3). No invoice step, no notification.

---

## `PurchaseOrderService.list_purchase_orders(db, workspace_id, account_id=None, invoice_id=None, skip=0, limit=100, **hub_filters)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /purchase-orders/`)
**Rules:**
- **LP1.** Returns exactly `list_purchase_orders_page` for the same arguments. Its own default `limit` is 100 (the page's 50); the endpoint always passes `limit`. An unknown keyword filter raises `TypeError`.

---

## `PurchaseOrderService._hub_filter_kwargs(*, account_id=None, invoice_id=None, date_from=None, date_to=None, status_ids=None, factory_id=None, destination_type=None, invoice_filter=None, search=None, exclude_complete=False, exclude_voided=False)`
**Shape:** mapper · **Persistence:** pure · **Visibility:** internal
**Rules:**
- **HF1.** A dict of exactly these eleven keys, values unchanged, except `invoice_filter`: `None`, `""` or `"all"` → `None`; anything else (`"All"`, `" all"`) as given.

---

## `PurchaseOrderService._prepare_listed_orders(db, workspace_id, orders)`
**Shape:** helper · **Persistence:** reads (writes the stage repair) · **Visibility:** internal (used by: `list_purchase_orders_page`)
**Rules:**
- **PL1.** Attaches `invoice_payment_status` (AP) and item summaries (IS) to every order; returns the same list, same order.
- **PL2.** [BUG-3178] Every order's stage is repaired per `sync_po_stage` (no performer). *(Today: the repair stops at the first order whose repair changed something; later orders are not repaired and are returned with their stale stage.)*
- **PL3.** If any repair changed something, one commit (Q8); else no commit. An empty list writes nothing. ✅

---

## `PurchaseOrderService.list_purchase_orders_page(db, workspace_id, *, skip=0, limit=50, ...filters)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `list_purchase_orders`)
**Returns:** `PurchaseOrderListResponse(items, total, skip, limit, has_more)`.
**Rules:**
- **PG1.** Filters normalised per HF1; `total` = `count_purchase_orders_for_hub`, `items` = `list_purchase_orders_for_hub(skip, limit)` with the same filters (filtering, order, search escaping, workspace scope, voided handling: the DAO spec), each prepared per PL1–PL3.
- **PG2.** `skip`, `limit` echoed; `has_more = skip + len(items) < total` (120 matching, skip 0, limit 50 → true; skip 100 → false; skip past the end → false; none → `total 0`, `[]`, false).

---

## `PurchaseOrderService.get_purchase_order_hub_stats(db, workspace_id, *, ...filters)`
**Shape:** compute · **Persistence:** reads · **Visibility:** public (`GET /purchase-orders/stats/`)
**Rules:**
- **HS1.** Filters per HF1, the same for all three manager reads. `total_count`, `total_value`, `open_count`, `open_value`, `not_invoiced_count` are the five values of `purchase_order_hub_stats` in that order (BUG-2639 / OQ-36 / BUG-2640 are the DAO's).
- **HS2.** `recent_orders` = at most 10 of `list_purchase_orders_recent_for_hub(limit=10)`, in its order, each per `order_hub_stats_helpers.purchase_order_to_recent_summary`.
- **HS3.** `pending_planning_count`, `missing_invoice_count` copied; `pending_planning`, `missing_invoice`, `oldest_drafts` each mapped per `pending_highlight_from_dict`, order kept; empty stays empty. TC6.

---

## `PurchaseOrderService._attach_invoice_payment_status(db, orders)`
**Shape:** helper · **Persistence:** reads · **Visibility:** internal
**Rules:**
- **AP1.** Each order gets `invoice_payment_status` = its invoice's `payment_status` (`unpaid` / `partial` / `paid` / `overdue`, any invoice status, voided included); no invoice, or none of the orders has one → `None`. One query for all.
- **AP2.** [BUG-3164] Only invoices of the order's workspace are read; an `invoice_id` of another workspace → `None`. *(Today: read by id only; another workspace's status is shown.)*

---

## `PurchaseOrderService._attach_item_summaries(db, workspace_id, orders)`
**Shape:** helper · **Persistence:** reads · **Visibility:** internal
**Rules:**
- **IS1.** Each order gets `item_count`, `quantity_ordered_total`, `quantity_received_total` from `summarize_by_purchase_order_ids` (an order with no lines → 0, `Decimal(0)`, `Decimal(0)`) and `item_names_preview` from `preview_names_by_purchase_order_ids` (none → `[]`), within the workspace.
- **IS2.** [BUG-2641] Each order also gets `quantity_refunded_total` (*requires new response field*), so the row can show "7 received of 10 ordered · 3 refunded" (owner OQ-38). *(Today: not returned.)*

---

## `PurchaseOrderService.create_receive_event(db, po_id, workspace_id, user_id, data)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /purchase-orders/{id}/receive/`)
**Purpose:** "Receive goods": record a receive batch or a quantity correction and move the stock.
**Inputs:** `PoReceiveEventCreate` — `event_type` `receive` | `correction` (else 422); `rcc`, `received_by`, `correction_note` optional text; `items` list of `{po_item_id, quantity_delta}`. Schema: empty `items` → 422 `At least one item must have a quantity delta`; `correction` with a blank note → 422 `correction_note is required for correction events`; `receive` with any delta ≤ 0 → 422 `All quantity deltas must be positive for a receive event`. A correction may carry 0 or negative deltas.
**Returns:** `PoReceiveEventResponse` (RE-response per `_build_receive_event_response`).
**Rules** (RE1–RE5 checked in order, before anything is written; the first failure raises):
- **RE1.** Order not in the workspace → 404 `Purchase order with ID {po_id} not found`. [BUG-3162] The order row is read with `FOR UPDATE OF purchase_orders` (Row locks table) before RE2. *(Today: plain read.)*
- **RE2.** Voided → 400 `Cannot receive against a voided purchase order`; completed (stage `Complete`) → 400 `Cannot receive against a completed purchase order` (RP5; replacements go through `receive_replacements`).
- **RE3.** No invoice linked, or the linked invoice is not found in the workspace, or not `confirmed` / `locked` → 400 `Finalize the invoice before recording receiving`.
- **RE4.** Lines in request order: a `po_item_id` that is not a line of this order in this workspace → 400 `Item {po_item_id} does not belong to this PO`.
- **RE5.** For each line, new received = stored received + delta: below 0 → 400 `Resulting received quantity for item {po_item_id} cannot be negative`; above `quantity_ordered − quantity_refunded` → 400 `Resulting received quantity for item {po_item_id} exceeds ordered quantity`. Exactly 0 and exactly ordered − refunded pass. [BUG-3171] Lines naming the same PO line are added up in request order and the running total is checked (P5). *(Today: each line is checked alone against the stored value.)*
- **RE6.** One `po_receive_events` row: `event_type`, `performed_by = user_id`, the order and workspace; one `po_receive_event_items` row per request line (`quantity_delta` as sent); each line's `quantity_received` += its delta (flushed).
- **RE7.** [BUG-3180] `rcc`, `received_by`, `correction_note` are stored trimmed, blank → `NULL`. *(Today: trimmed, but a blank value is stored as `""`.)*
- **RE8.** Stock moves per `post_receive_event_inventory` (one ledger row per line with a non-zero whole delta at a storage / machine destination; fractional delta → 400 `Line {line_number} has a fractional quantity delta; inventory requires whole units`; insufficient stock for a negative delta → 400; destination not found / soft-deleted per that spec, BUG-684). A project destination moves no stock (*revisit after launch*). When at least one ledger row was written: PO event `inventory_posted` / `<n> receive line(s) posted to <dest>` (`factory storage` for `storage`, `machine inventory` for `machine`, else `inventory`), metadata `receive_event_id`, `lines_posted`, `destination_type`, `destination_id`.
- **RE9.** One PO event: `receive` → `received` / `Received <total delta> unit(s) across <n> item(s).<RCC part><by part>`; `correction` → `quantity_correction` / `Quantity correction: <total delta, signed: +2.5, -2, +0> unit(s) across <n> item(s).<note part>`, where RCC part = ` RCC: <rcc>.`, by part = ` Received by: <received_by>.`, note part = ` Note: <note>`, each only when the value is non-empty; metadata `receive_event_id` plus `rcc`, `received_by`, `correction_note` when non-empty. `<total delta>` is the sum as sent (`5`, `7.50`). [BUG-3180] The texts use the stored (trimmed) values. *(Today: the values as sent, untrimmed; a whitespace-only value is included.)*
- **RE10.** [BUG-3177] The first receive event whose stock change makes any line's received quantity > 0 sets the invoice's `receiving_started` per `AccountInvoiceManager.set_receiving_started` (invoice event `receiving_started_set`); already set → nothing more. *(Today: never set by this path.)*
- **RE11.** After the event, if every line of the order has received + refunded ≥ ordered (an order with lines) and no `all_received` event was ever logged for the order, one event `all_received` / `All items received`. It is logged once per order for its whole life, also when a later correction lowers and re-raises a quantity.
- **RE12.** The stage is not repaired here (the next read repairs it). Committed (TC1); the event re-read and returned. Any error from RE6 onward rolls everything back (TC3): no event row, quantities and stock unchanged.

**Errors:** RE1–RE5; those of the posting module.

---

## `PurchaseOrderService.list_receive_events(db, po_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /purchase-orders/{id}/receive-events/`)
**Rules:**
- **LR1.** Order not in the workspace → 404 `Purchase order with ID {po_id} not found`.
- **LR2.** Every receive event of the order in the workspace (an event of the same order id under another workspace is not listed), newest `created_at` first, each per `_build_receive_event_response`; none → `[]`. [BUG-3172] Ties by `id` descending. *(Today: no tie-break.)* Not paged. TC6.

---

## `PurchaseOrderService._build_receive_event_response(event)`
**Shape:** mapper · **Persistence:** reads (relationships) · **Visibility:** internal
**Rules:**
- **BR1.** Copies the event's columns; `performer_name` = the performer's profile name, `None` when no performer. `items`: one per event line with `po_item_name` / `po_item_unit` from the PO line (`None` when the line is gone) and `quantity_delta`. [BUG-3172] Lines in `id` ascending. *(Today: relationship order.)*

---

## `PurchaseOrderService._attach_return_invoice_for_po(db, po, ret, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** internal (used by: `start_return`)
**Purpose:** make the return's credit note and finalize it at once.
**Rules:**
- **AR1.** One invoice per `AccountInvoiceManager.create_invoice`: `account_id` = the order's supplier, `order_id` = the order, `order_type = "purchase_order"`, `invoice_type = "receivable"` (the supplier owes us), `description = "Return credit note for <po_number> (<return_number>)"`, `notes` = the return's reason, `allow_payments = True`. [BUG-3167] `invoice_date = utcnow().date()`. *(Today: `date.today()`.)* The return's `invoice_id` = it (flushed). The order's own `invoice_id` is not touched.
- **AR2.** Lines: one per return line (`get_by_return`, `id` ascending), numbered 1, 2, …: `description` = the return line's `item_name` or `Item <item_id>`, `item_id`, `source_order_item_id` = the PO line id, `source_order_item_type = "po_item"`, `quantity` = `quantity_returned`, `unit` = `item_unit`, `unit_price` = the return line's price, `0` when none (unreachable after BUG-2787).
- **AR3.** Each stored `line_subtotal` = price × quantity rounded half up to 2 places (the column is `Numeric(15, 2)` and Postgres rounds half away from zero on store), and the credit note's amount = sum of the stored, rounded lines (`invoice_item_dao.create` refreshes each line before `_recalculate_invoice_amount` / `confirm_invoice` sum them): `1.25 × 0.10` → line `0.13`; two such lines → amount `0.26`. HR-15 holds today. *(BUG-3163 withdrawn 2026-11-22, executor DISCREPANCY-8: the Python value is unrounded but never observable, because the refresh replaces it with the stored, rounded value before anything sums it. Kept as a regression rule. Decided by Claude under the reviewer's delegation (2026-11-22).)*
- **AR4.** Then confirmed per `confirm_invoice` (status `confirmed`, amount = sum of lines, one `confirmed` event). Errors of the three invoice calls pass through. Nothing committed.

---

## `PurchaseOrderService.start_return(db, po_id, workspace_id, user_id, data)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /purchase-orders/{id}/returns/`)
**Returns:** the return, committed and refreshed (status `pending`, `invoice_id` set).
**Rules:**
- **SR1.** Order not in the workspace → 404; voided → 400 `Cannot return items on a voided purchase order`. A completed order is accepted (owner freeze: corrections go through returns).
- **SR2.** No line with received > 0 → 400 `No items have been received yet — nothing to return`.
- **SR3.** The lines are checked and built per `PurchaseOrderReturnManager.validate_and_build_items` (all its rules: belongs, available quantity BUG-2750 / 2751 / 2792, price range BUG-2785, price required BUG-2787, lock BUG-2753, schema BUG-2752).
- **SR4.** [BUG-801] For a `storage` or `machine` order, a `quantity_returned` with a fractional part → 400 `Return line for PO line {line_number} has a fractional quantity; inventory requires whole units`, checked after SR3, nothing created. *(Today: accepted; completing the return then fails every time.)* A project order: any quantity (*revisit after launch*).
- **SR5.** [BUG-2789] A completed order stays completed (`reopen_for_return` R2: stage, `actual_delivery_date`, no `order_reopened` event); while the return is pending the order shows "return in progress" (RF1–RF2). *(Today: reopened to `Receiving`.)*
- **SR6.** One return (`return_type`, `reason`, `notes` as sent; numbered and `created_by` per the return DAO) and one return line per built item; the credit note per `_attach_return_invoice_for_po`; one PO event `return_started` / `Return <return_number> started — <return_type> (<total qty> unit(s) across <n> item(s))` (`<total qty>` = the sum of the quantities **as sent**, e.g. `4`), metadata `return_id`, `invoice_id`, `return_type`. No stock moves, no line quantity changes, no notification.
- **SR7.** Committed together (TC1); any error rolls back the return, its lines, the credit note and its events (TC3).

---

## `PurchaseOrderService.complete_return(db, po_id, return_id, workspace_id, user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST /purchase-orders/{id}/returns/{return_id}/complete/`)
**Rules:**
- **CR1.** Order not in the workspace → 404; return not of this order / workspace → 404 `Return with ID {return_id} not found`. [BUG-2754 / BUG-800] The return is read with a plain `FOR UPDATE` on `purchase_order_returns` (`get_return(..., for_update=True)`; single-table read, Row locks table). *(Today: plain read.)*
- **CR2.** Return not `pending` → 400 `Only a pending return can be completed`.
- **CR3.** For each return line whose PO line is on the order (a missing PO line is skipped): `quantity_returned` += q and `quantity_received` −= q; for a `refund` return also `quantity_refunded` += q (so the line counts as done, OQ-38); for `replace` the gap stays to be filled (`receive_replacements`, or "Receive goods" while the order is not complete).
- **CR3a.** [BUG-3186] (decided by Claude under the reviewer's delegation (2026-11-22); Gap log G20) Before anything is written, every return line whose PO line is on the order is checked: if stored `quantity_received` − q would be below 0, the call is refused with 400 `Cannot complete return {return_number} — line {line_number} has only {quantity_received} received; correct the receipt or cancel the return`, nothing written (no quantity, stock, status or event change; TC3). Exactly 0 is allowed. *(Today: no floor — a line received 4, put on a pending return of 4 and then corrected to 0 through "Receive goods" (RE5 checks only ≥ 0 and ignores pending returns) stores `quantity_received = −4.00` on completion; the column has no check constraint.)* Returnable quantity stays received minus returned, counted once (owner OQ-45 / BUG-2750); this rule only stops completion from storing a negative.
- **CR4.** Stock out per `post_purchase_return_inventory` (one ledger row per return line at a storage / machine destination; insufficient stock → 400; project → nothing, *revisit after launch*).
- **CR5.** The return: `status = 'completed'`, `completed_at` = `utcnow()`, `completed_by = user_id`. The credit note is not touched (it was finalized at start).
- **CR6.** One PO event `return_completed` / `Return <return_number> completed — <type> (<total qty> unit(s), <posted> inventory line(s) posted)` (`<total qty>` = the sum of the **stored** return quantities, 2 places, e.g. `4.00`; in a test that built the return in the same session, expire it first so the stored value is read) plus ` — re-receive to close the gap` for `replace`; metadata `return_id`, `return_type`. The order's stage and completion are not changed (RF2).
- **CR7.** [BUG-3174] `updated_by = user_id` on the return. *(Today: unchanged.)*
- **CR8.** Committed (TC1); any error (e.g. insufficient stock) rolls back the quantities, stock and status (TC3).

---

## `PurchaseOrderService.void_return(db, po_id, return_id, workspace_id, user_id, void_note)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST /purchase-orders/{id}/returns/{return_id}/void/`)
**Rules:**
- **VR1.** Order and return as CR1 (404s; the return read with a plain `FOR UPDATE` per BUG-2754).
- **VR2.** Return not `pending` → 400 `Only a pending return can be cancelled`.
- **VR3.** The credit note (if any) is voided per `AccountInvoiceManager.void_invoice` with `void_note` (its payments voided; with BUG-2788 the manager also marks the pending return `voided`). [BUG-3182] A credit note that is already `voided` is skipped and the cancel goes ahead. *(Today: 400 `Invoice is already voided`, nothing changes.)*
- **VR4.** The return: `status = 'voided'`, `paid` re-synced per `sync_return_paid` (→ `False`). No line quantities or stock change. One PO event `return_voided` / `Return <return_number> cancelled — <void_note>`, metadata `return_id`, `void_note`.
- **VR5.** [BUG-3174] `updated_by = user_id`. *(Today: unchanged.)*
- **VR6.** Committed (TC1); errors roll back (TC3).
- **VR7.** [BUG-3168] `void_note` is trimmed and not blank (422 at `PurchaseOrderReturnVoidRequest`). *(Today: `"   "` accepted and stored.)*

---

## `PurchaseOrderService.list_returns(db, po_id, workspace_id)` / `get_return(db, po_id, return_id, workspace_id)`
**Shape:** list / get-or-404 · **Persistence:** reads · **Visibility:** public (`GET /purchase-orders/{id}/returns/`, `GET …/returns/{return_id}/`)
**Rules:**
- **LRT1.** Order not in the workspace → 404 `Purchase order with ID {po_id} not found`, checked first.
- **LRT2.** Then `PurchaseOrderReturnManager.list_returns` R1–R2 / `get_return` R1–R5 (default, no lock). TC6.

---

## `PurchaseOrderService.list_active_orders_for_context(db, *, workspace_id, machine_id=None, factory_id=None, project_component_id=None)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /purchase-orders/active/`)
**Returns:** `list[ActiveOrderRow]`.
**Rules:**
- **AO1.** Not exactly one of the three ids given (none, or two or three) → 400 `Provide exactly one of machine_id, factory_id, project_component_id`. An id of `0` counts as given.
- **AO2.** The scope row must exist in the workspace (soft-deleted ones count): else 404 `Machine not found` / `Factory not found` / `Project component not found`.
- **AO3.** Purchase orders: every PO of the workspace whose destination is the scope (`machine` → `machine`/id, factory → `storage`/id, component → `project`/id; project *revisit after launch*), except those whose stage is the last status of their workflow's `status_sequence` (`Complete`). A PO with no workflow, or a workflow whose sequence is empty, not a list, or ends in a non-integer, is never skipped.
- **AO4.** Each PO row: `order_kind "purchase"`, `id`, `number` = `po_number`, `summary` = description, `current_status_id`, `status_name` = the stage's name (`None` if no status), `created_at`, `total_amount`.
- **AO5.** Transfer orders: every transfer of the workspace not completed (`completed_at` NULL) whose source or destination is the scope (`machine`/id, `storage`/id, `project`/id): `order_kind "transfer"`, `number` = `transfer_number`, `summary` = description, its status, `total_amount = None`.
- **AO6.** [BUG-3173] Voided purchase orders are not listed. *(Today: listed as active.)*
- **AO7.** Work orders, machine scope only (and component, AO8): drafts and in-progress work orders of the machine (not soft-deleted): `order_kind "work"`, `number` = `work_order_number`, `summary` = title, `current_status_id = None`, `status_name` = status title-cased with `_` → space (`DRAFT` → `Draft`, `IN_PROGRESS` → `In Progress`), `total_amount` = `cost`. Completed and voided work orders are not listed. A factory scope lists no work orders.
- **AO8.** Component scope (*revisit after launch*, today's behaviour, no bug): the workspace's newest 1,000 live work orders are read and those of the component in draft / in progress are kept.
- **AO9.** [BUG-3166] (HR-5) Machine scope: every in-flight work order of the machine is returned, whatever the number of the machine's other work orders. *(Today: only among the machine's newest 1,000 work orders, any status.)*
- **AO10.** All rows sorted by `created_at` descending; equal times keep purchase, then transfer, then work order rows, each in its DAO order. Nothing written.

---

## `PurchaseOrderService.delete_purchase_order(db, po_id, workspace_id)`
**Shape:** delete · **Persistence:** writes · **Visibility:** public (`DELETE /purchase-orders/{id}/`)
**Returns:** `None`.
**Rules:**
- **X1.** Deletes per `PurchaseOrderManager.delete_purchase_order` (receiving history → 400; [BUG-2888] finalized invoice → 400 `Cannot delete a purchase order with a finalized invoice — void the order instead`; a draft invoice goes with the order; lock BUG-2872) and commits; any error rolls back (TC1, TC3).
- **X2.** [BUG-1195] Takes `user_id` and passes it to the manager, which writes the `workspace_audit_logs` row; the endpoint passes the current user. *(Today: no `user_id`; the endpoint has no current user.)*

---

## `PurchaseOrderService.add_item(db, po_id, item_in, workspace_id, user_id=None)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /purchase-orders/{id}/items/`)
**Returns:** the new line, committed and refreshed.
**Rules:**
- **AI1.** The line is added per `PurchaseOrderManager.add_item` (all its rules and errors).
- **AI2.** The order's `items_updated_at` = `utcnow()`; with a `user_id` (the endpoint always passes one) the invoice step runs per `_sync_draft_invoice_for_po` (not forced; in practice SD1 or SD2: the items lock keeps a confirmed order from taking lines). Without `user_id`, no invoice step.
- **AI3.** Committed together (TC1); errors roll back; an `IntegrityError` → rolled back and translated per `_handle_item_integrity_error` (`phase='items'`), e.g. a missing catalog item id → 400 `A linked catalog item or order reference is missing. Refresh the page and try again.` (until BUG-1017's 404).

---

## `PurchaseOrderService.update_item(db, item_id, item_in, workspace_id, user_id=None)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (`PUT /purchase-orders/items/{item_id}/`)
**Rules:**
- **UI1.** Updates per `PurchaseOrderManager.update_item` (its rules and errors). [BUG-2887] A body with `quantity_received` is refused with 422 by `PurchaseOrderItemUpdate` before this method runs.
- **UI2.** With a `user_id`: the line's order gets `items_updated_at` = `utcnow()` and the invoice step as AI2. Without: neither.
- **UI3.** Commit, rollback and integrity translation as AI3; returns the line refreshed.

---

## `PurchaseOrderService.remove_item(db, item_id, workspace_id, user_id=None)`
**Shape:** delete · **Persistence:** writes · **Visibility:** public (`DELETE /purchase-orders/items/{item_id}/`)
**Rules:**
- **RI1.** Removes per `PurchaseOrderManager.remove_item`; with a `user_id`, `items_updated_at` and the invoice step as UI2; committed; returns the removed line **without** a refresh (its loaded attributes stay readable); errors as AI3.

---

## `PurchaseOrderService.sync_items(db, po_id, sync_in, workspace_id, user_id=None)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (`POST /purchase-orders/{id}/items/sync/`)
**Returns:** the order, refreshed.
**Rules:**
- **SY1.** The lines change per `PurchaseOrderManager.sync_items` (removals, updates, additions; its rules and errors). An `IntegrityError` → rolled back and translated (`phase='items'`).
- **SY2.** [BUG-3179] The line changes and the invoice step (SY3) are committed together, once; an error in either rolls back both. *(Today: the lines are committed first; the invoice step is a second transaction, so its failure leaves the line changes saved.)*
- **SY3.** With a `user_id` and a supplier on the order: `items_updated_at` and the invoice step per `_sync_draft_invoice_for_po` (not forced); its `IntegrityError` is translated with `phase='invoice'`. No `user_id` or no supplier → no invoice step, `items_updated_at` unchanged.
- **SY4.** [BUG-3165] (HR-9) `items_updated_at` is written only when at least one line was added, removed or changed. *(Today: on every call that reaches SY3, an empty request included.)*

---

## `PurchaseOrderService.get_items(db, po_id, workspace_id)` · `list_events(db, po_id, workspace_id)` · `list_approvers(db, po_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET …/items/`, `…/events/`, `…/approvers/`)
**Rules:**
- **PT1.** Exactly the manager's `get_items` (BUG-2886: 404 for a missing order), `list_events` (newest first; BUG-2883), `list_approvers` (BUG-1200, BUG-2883). TC6.
- **PT2.** Return shapes (fact, executor DISCREPANCY-11): `get_items` → `list[PurchaseOrderItem]`; `list_events` → `list[tuple[PurchaseOrderEvent, Profile | None]]` (the event, then its performer's profile or `None`); `list_approvers` → `list[tuple[PurchaseOrderApprover, Profile | None, str | None]]` (the approver row, its profile or `None`, its workspace position or `None`). An event id is `e[0].id`; an approver's user is `a[0].user_id`.

## `PurchaseOrderService.approval_summary_for(db, po_id, workspace_id)`
**Shape:** compute · **Persistence:** reads
**Rules:**
- **AS1.** Order not in the workspace → 404; else `(approved_count, required, met)` per `PurchaseOrderManager.approval_summary` (BUG-1202). TC6.

---

## `PurchaseOrderService.add_approver(db, po_id, user_id, workspace_id, assigned_by)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /purchase-orders/{id}/approvers/`)
**Rules:**
- **AA1.** Adds per `PurchaseOrderManager.add_approver` (its rules: BUG-2881 completed / finalized refused, BUG-2882, lock).
- **AA2.** Notifications per `handle_add_approver` R1–R3 with actor `assigned_by`: the new approver always; ready order → every other pending approver gets `approval_pending` again; not ready → the creator gets the gap text.
- **AA3.** Committed together; any error rolls back the approver row and the notifications (TC1–TC3). Returns the approver row refreshed.

## `PurchaseOrderService.remove_approver(db, po_id, user_id, workspace_id, performed_by=None)`
**Rules:**
- **RA1.** Removes per `PurchaseOrderManager.remove_approver` and commits; errors roll back; returns `None`. No notification, no invoice step.

## `PurchaseOrderService.set_approval(db, po_id, user_id, workspace_id, approved)`
**Rules:**
- **SA1.** Approves / withdraws per `PurchaseOrderManager.set_approval` (403 not an approver; BUG-2880 no-op; BUG-2881) and commits; errors roll back; returns the row refreshed. No notification (approvals met notifies nobody) and no invoice step.

---

## `PurchaseOrderService.void_purchase_order(db, po_id, workspace_id, user_id, void_note)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST /purchase-orders/{id}/void/`)
**Returns:** the order, committed and refreshed.
**Rules** (checks V1–V2b in order, before anything is written):
- **V1.** Order not in the workspace → 404. [BUG-3162] Read with `FOR UPDATE OF purchase_orders` before V2. *(Today: plain read.)*
- **V2.** Already voided → 400 `Purchase order is already voided`.
- **V2a.** [BUG-2734] (owner, 2026-11-14) Stage `Complete` → 400 `Cannot void a completed purchase order — record a return instead`, nothing written. *(Today: voided; its frozen invoice is voided and payments cancelled — only the invoice manager's freeze R3a, once fixed, would stop the invoice part.)*
- **V2b.** [BUG-2734] Any line with `quantity_received > 0` → 400 `Cannot void a purchase order with goods received — record a return instead`, nothing written. *(Today: the stock is reversed and the invoice voided.)* Texts decided by Claude under the reviewer's delegation (2026-11-21).
- **V3.** Received stock is reversed per `reverse_po_receive_inventory` (BUG-682 netting of completed returns); when it wrote rows, PO event `inventory_reversed` / `<n> inventory posting(s) reversed for void`, metadata `reversed_count`. After V2b this reverses only corrections that net to zero. Example (storage or machine order): line received +3 (posted, stock +3), then a correction −3 (posted, stock −3), so `quantity_received` = 0 and V2b passes; the void writes two `inventory_adjustment` rows (out 3 for the receive line, in 3 for the correction line), stock ends where it was, and `inventory_reversed` is logged with `reversed_count` 2. A line brought to 0 by a completed refund return instead nets to nothing under BUG-682 (`po_receive_inventory.spec.md` R6a/R7). A project order writes nothing (*revisit after launch*).
- **V4.** A linked invoice found in the workspace: `confirmed` → voided per `void_invoice` with note `Purchase order voided: <void_note>` (all its payments voided; owner OQ-54: voiding the order is how a finalized invoice goes); `draft` → deleted per `delete_invoice` (BUG-639 refusal passes through); `voided` or `locked` → left as is.
- **V5.** With an invoice linked (found or not): approvals reset (reason `Cleared approvals — PO voided`), then the order is unlinked per `unlink_invoice_from_po` with event `invoice_voided` / `Invoice unlinked — PO #<po_number> voided`, metadata `invoice_id` (per V5a) and `changes = [{"field": "void_note", "label": "Void reason", "from_value": null, "to_value": <void_note>}]`.
- **V5a.** [BUG-3185] The `invoice_voided` event's `invoice_id` is the id the order was linked to before the void, whatever happened to the invoice (confirmed → voided, draft → deleted, voided / locked / not found → left). *(Today: right in every case except a **draft**, where `delete_invoice` has already cleared `po.invoice_id`, so the event records `invoice_id: null`; executor DISCREPANCY-4, V-02.)* Decided by Claude under the reviewer's delegation (2026-11-22).
- **V6.** The order: `voided = True`, `void_note`, `voided_at` = `utcnow()`, `voided_by = user_id`; stage, section confirms and quantities unchanged. One PO event `po_voided` / `Purchase order #<po_number> voided. Reason: <void_note>`, metadata `void_note`.
- **V7.** No notification.
- **V8.** [BUG-3170] Approvals are reset on every void (V5's reset also without an invoice). *(Today: only with an invoice linked.)*
- **V9.** Committed together (TC1); any error rolls back the stock reversal, invoice changes and flags (TC3).
- **V10.** A pending return on the order is not touched (after V2b a pending return implies goods received, so V2b refuses first).
- **V11.** The order is not `updated_by`-stamped (`voided_by` records the actor).
- **V12.** [BUG-3168] `void_note` is trimmed and not blank (422 at `PurchaseOrderVoidRequest`). *(Today: any string, `""` included.)*

---

## `PurchaseOrderService.create_invoice_for_purchase_order(db, po_id, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /purchase-orders/{id}/create-invoice`)
**Returns:** the order, committed and refreshed.
**Rules:**
- **CI1.** Order not in the workspace → 404. [BUG-3162] Read with `FOR UPDATE OF purchase_orders` before CI2. *(Today: plain read.)*
- **CI2.** [BUG-3169] Voided → 400 `Purchase order is voided`, nothing written. *(Today: a fresh draft is made for a voided order with its sections confirmed.)*
- **CI3.** The invoice step runs per `_sync_draft_invoice_for_po` with `force_create=True`: locked → nothing; sections not all confirmed → 422 (SD3); no invoice → a draft is made (SD5–SD7); a linked draft is re-synced (SD10–SD11). No notification, also when a draft was made.
- **CI4.** Afterwards: no supplier → 422 `Assign a supplier before a draft invoice can be created`; still no invoice → 422 `Could not create draft invoice for this purchase order` (both reachable only with stored data the API cannot make, e.g. three sections confirmed and no supplier). Otherwise committed and returned.
- **CI5.** Errors roll back (TC3).
- **CI6.** An `IntegrityError`: rolled back; the order re-read; if it has an invoice → returned without error (nothing committed by this call); else translated per `_handle_item_integrity_error` with `phase='invoice'`.

---

## `PurchaseOrderService.receive_replacements(db, po_id, return_id, workspace_id, user_id, data)` — *requires new method* (BUG-2810, FU-2)
**Shape:** create · **Persistence:** writes · **Visibility:** public (new `POST /purchase-orders/{po_id}/returns/{return_id}/receive-replacements/`)
**Purpose:** bring a `replace` return's replacement goods into stock without touching the order's stage or invoice.
**Inputs:** `data`: new `PurchaseOrderReturnReplacementCreate` per `validate_replacement_receipt` Inputs (`items` of `{return_item_id, quantity}`, `notes?`; schema 422s there).
**Returns:** the return, committed and refreshed.
**Rules** (all [BUG-2810], owner 2026-11-19; details per return manager FU-2, decided under the reviewer's delegation (2026-11-19)):
- **RX1.** Order not in the workspace → 404 `Purchase order with ID {po_id} not found`; the return read per `get_return(..., for_update=True)` with a plain `FOR UPDATE` on `purchase_order_returns` (404 `Return with ID {return_id} not found`).
- **RX1a.** The order row is read first with `FOR UPDATE OF purchase_orders`, before the return, so a replacement receipt and a "Receive goods" on the same order cannot both pass the PO-line ceiling (RX4 / RE5). Lock order: order → return → credit note (Row locks table). Decided by Claude under the reviewer's delegation (2026-11-22; gap 2).
- **RX2.** The request is checked per `validate_replacement_receipt` RR1–RR8 (only `replace`, only `completed`, lines of this return, at most returned − already replaced, cost = original line price).
- **RX3.** A storage / machine order: a quantity with a fractional part → 400 `Line {line_number} has a fractional quantity; inventory requires whole units`, nothing written.
- **RX4.** [BUG-3181] A quantity that would take the PO line above `quantity_ordered − quantity_refunded` (running total per PO line in the request) → 400 `Cannot receive {q} replacement(s) for line {line_number} — the line is already fully received`, nothing written (Q6). `{q}` is that request line's quantity **as sent** (`4`).
- **RX5.** Per received line: `return_item.quantity_replaced` += q (*requires new column*, Numeric(15,2) NOT NULL default 0) and `po_line.quantity_received` += q; `quantity_returned` unchanged.
- **RX6.** Stock in at the order's destination, one ledger row per return line received: `transaction_type = 'purchase_order'` (as a PO receipt), `source_type 'purchase_return_replacement'`, `source_id` = return line id, `quantity` = q, `unit_cost` = RR6's cost, `total_cost` = cost × q rounded half up, stock / average per `_post_event_item_delta` R6 (storage) / R7 (machine), notes `Replacement for return <return_number> — PO <po_number> line <line_number>`; destination not found / soft-deleted as R12 / R12a there. A project order moves no stock (*revisit after launch*).
- **RX7.** The return keeps `status = 'completed'`; [BUG-3174] `updated_by = user_id`.
- **RX8.** The order's stage, `actual_delivery_date`, approvals and invoice are not changed; no new invoice or credit note is created.
- **RX8a.** [BUG-3176] ([OQ-63](../../../docs/testing/owner-questions.md)) Each receipt of replacements settles the return's credit note by the value received: one `invoice_payments` row on the credit note (the credit note is read with a plain `FOR UPDATE` on `account_invoices` before its balance is read and before the entry is inserted, so two receipts cannot both settle the same outstanding amount; HR-10, coordinator decision 2026-11-22) with `payment_amount` = Σ over the request's lines of q × the return line's `unit_price`, each line rounded half up to 2 places before summing (HR-15); `payment_method = 'settled_by_replacement'`; `payment_date` = the UTC date of the receipt; `created_by` = `user_id` (who received the goods); `is_voided = false`. *(Today: the method does not exist; the credit note stays owed in full.)*
- **RX8b.** [BUG-3176] The entry links to the receipt it came from: `payment_reference` = the return's `return_number`, and the entry carries the id of RX9's PO event (*requires new nullable columns `invoice_payments.source_type` = `'purchase_order_event'` and `source_id` = that event's id*, Overview gap 4). `notes` = `Settled by replacement — <total q> unit(s) received for return <return_number>`, `<total q>` = the sum of the request's quantities **as sent** (`4`; `1.50` + `2` → `3.50`).
- **RX8c.** [BUG-3176] A partial receipt settles only its own share. Example: return of 4 at 500 → credit note 2,000.00; receiving 3 writes a 1,500.00 entry and the note shows 500.00 outstanding (`payment_status` partial); receiving the 4th later writes a 500.00 entry and the note is paid. The return's `paid` flag is re-synced from the note as any payment does.
- **RX8d.** [BUG-3176] The entry never exceeds the credit note's outstanding balance (decided under delegation): if part was already collected in cash, the entry is the outstanding amount; if nothing is outstanding, no entry is written, the receipt still goes ahead, and the response carries `warnings: ["The return's credit note has nothing outstanding — no settlement recorded"]`; a credit note that is `voided` (or any status other than `confirmed`) gives instead `warnings: ["The return's credit note is voided — no settlement recorded"]` (same handling as the sales twin, BUG-3217) (*requires new response field*). **Where (gap 5):** `warnings: list[str]` is a new field on `PurchaseOrderReturnResponse`, default `[]`; a normal settlement returns `warnings == []`, and every other return endpoint returns `[]` too. Decided by Claude under the reviewer's delegation (2026-11-22).
- **RX8e.** [BUG-3176] The return gets one `purchase_order_return_events` row (Overview gap 3): `event_type = 'replacement_received'`, `description` = `Replacements received — <total q> unit(s), <settled_amount> settled`, metadata `return_id`, `total_quantity` (text, as sent), `settled_amount` (text, 2 places; `"0.00"` when no entry was written under RX8d / RX8k), `payment_id` (null when no entry), `performed_by = user_id` (*requires new: returns have no event log of their own today*). Gap 6 decided by Claude under the reviewer's delegation (2026-11-22).
- **RX8f.** [BUG-3176] The PO activity entry is RX9's event, with `settled_amount` (text, 2 places; `"0.00"` when no entry) and `payment_id` (null when no entry) added to its metadata.
- **RX8g.** [BUG-3176] Each stock-in ledger row of RX6 is linked to the return: `source_type 'purchase_return_replacement'`, `source_id` = the return line id (which belongs to the return), notes naming `<return_number>` as in RX6.
- **RX8h.** [BUG-3176] A settlement entry cannot be deleted or edited: `InvoicePaymentManager.delete_payment` and `update_payment` refuse a payment with `payment_method = 'settled_by_replacement'` with 400 `A settlement by replacement cannot be deleted or edited — void it with a reason instead`, nothing written (fix lives in `app/managers/invoice_payment_manager.py`; listed here because this method creates the row). *(Today: any payment can be deleted or edited.)*
- **RX8i.** [BUG-3176] A settlement entry can be voided like any payment (`void_payment`, reason required per BUG-3168 precedent): `is_voided = true`, `voided_at`, `voided_by`, `void_note` set; the amount is owed again on the credit note. Voiding it does not take the replacement stock back out.
- **RX8j.** [BUG-3176] The entry is written through the normal payment path, `InvoicePaymentManager.create_payment` (coordinator decision 2026-11-22, same as the sales twin): its invoice lock, its `confirmed`-only and outstanding-balance checks, the balance update (`paid_amount`, `payment_status`), one `financial_audit_logs` row (`entity_type = 'payment'`, `action_type = 'created'`, related invoice) and one invoice event `payment_recorded` (metadata `payment_method = 'settled_by_replacement'`), then the return's `paid` re-sync. The one difference: the **`allow_payments` refusal (403 `Payments are locked for this invoice`) is skipped** for a settlement, because a settlement is not cash — a credit note with `allow_payments = False` is still settled (*requires a new internal flag on `create_payment`, not reachable from the payments API*). RX8d's pre-checks mean the `confirmed` and outstanding checks never refuse here.
- **RX8k.** [BUG-3176] (HR-16, coordinator decision 2026-11-22; gap 9) A return whose `invoice_id` points to an invoice of another workspace (invalid data), or to no invoice at all, is left alone: that invoice is not read for update, not paid and not changed; no entry is written; the receipt still goes ahead and the response carries `warnings: ["The return's credit note could not be found — no settlement recorded"]` (no id in the text). RX8e / RX8f record `settled_amount "0.00"`, `payment_id` null.
- **RX8l.** [BUG-3176] (gap 12, confirmed from code) Voiding a settlement entry re-syncs the return's `paid` flag: `void_payment` recomputes the credit note's `paid_amount` / `payment_status` and calls `_sync_linked_order`, which finds the return by `invoice_id` and runs `sync_return_paid` → `paid = (payment_status == 'paid')`. So a fully settled return (`paid = True`) goes back to `paid = False` when its entry is voided, with nothing else on the return changed.
- **RX8m.** [BUG-3176] The payments API cannot make or fake a settlement: `create_payment` called from `POST /invoice-payments/` (no internal flag) and `update_payment` refuse `payment_method = 'settled_by_replacement'` with 400 `"settled_by_replacement" is recorded by the system and cannot be entered by hand`, nothing written (fix in `app/managers/invoice_payment_manager.py`). Decided by Claude under the reviewer's delegation (2026-11-22): without it anyone could record an undeletable non-cash payment.
- **RX9.** One PO event `return_replacement_received` / `Replacements received for return <return_number> — <total q> unit(s)` (`<total q>` as sent), metadata `return_id`, `total_quantity` (text, as sent). No notification.
- **RX10.** Committed together (TC1); any error rolls back quantities, stock, the settlement entry, the return event and the PO event (TC3).

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 72–75 | `orig` / `diag` / attrs present | IC1, IC1a |
| 88 | check violation | IE1 |
| 89–93 | ordered / received in text | IE1 |
| 98 | invoice / paid amount | IE1 |
| 108 | unique violation | IE2 |
| 109 | invoices table or invoice phase | IE2 |
| 119 | not-null | IE3 |
| 120 | invoice tables or phase | IE3 |
| 121, 129 | table and column known | IE3 |
| 137 | foreign key | IE4 |
| 138 | invoice tables or phase | IE4 |
| 148–157 | fallback, phase | IE5, IE7 |
| 162 | lines empty / missing | BI1 |
| 165 | item name empty | BI2 |
| 184 | no invoice id | DD1 |
| 189 | not found / not draft | DD1 |
| 192–197 | delete + unlink | DD2, DD2a |
| 212 | financially locked | SD1 |
| 214 | not forced, not confirmed | SD2 |
| 217 | forced, not confirmed | SD3 |
| 222 | no supplier | SD4 |
| 228 | no invoice linked | SD5–SD7 |
| 251–260 | create raised: 404 / other | SD8 |
| 254 | invoice linked meanwhile | SD8 |
| 280 | linked not found / not draft | SD9 |
| 288 | account changed and invoice confirmed | SD10 |
| 309–319 | which fields differ / none | SD11 |
| 338 | no new invoice | EN1 |
| 357 | retry loop (1…5) | C2 |
| 369–374 | integrity: number clash / other | C2, C4 |
| 375–381 | after loop, number clash → 409 | C2 |
| 387–388 | HTTPException re-raised, no rollback | C5 |
| 389–391 | other → rollback | C4 |
| 400–403 | sent-and-not-null dump; unconfirm detection | U2 |
| 425–433 | integrity / HTTP / other | U4 |
| 438 | stage changed → commit | G2 |
| 500 | invoice_filter all / empty | HF1 |
| 509–513 | any stage changed (short-circuit) | PL2, PL3 |
| 560 | has_more | PG2 |
| 634 | no invoice ids | AP1 |
| 661 | no summary | IS1 |
| 677, 679 | voided / completed | RE2 |
| 681, 684 | no invoice / not finalized | RE3 |
| 689–699 | per line: not on PO / negative / over max | RE4, RE5 |
| 706–708 | text fields present | RE7 |
| 731 | lines posted > 0 | RE8 |
| 733–737 | destination label | RE8 |
| 754–756 | rcc / received_by parts | RE9 |
| 758 | receive / correction | RE9 |
| 762 | note part | RE9 |
| 767–772 | metadata keys | RE9 |
| 778 | all fully received (non-empty) | RE11 |
| 786 | already logged | RE11 |
| 793–798 | errors → rollback | RE12 |
| 816, 821 | PO line gone | BR1 |
| 834 | performer missing | BR1 |
| 881, 887 | item name / price missing | AR2, AR3 |
| 901 | voided | SR1 |
| 907 | nothing received | SR2 |
| 923 | loop over built items | SR6 |
| 959 | not pending | CR2 |
| 976 | PO line missing → skip | CR3 |
| (new, BUG-3186) | received − q below 0 → refuse before any write | CR3a |
| 985 | refund | CR3 |
| 998 | gap note for replace | CR6 |
| 1027 | not pending | VR2 |
| 1033 | credit note linked | VR3 |
| 1078 | scope count ≠ 1 | AO1 |
| 1084–1098 | which scope; not found | AO2 |
| 1115 | any workflow ids | AO3 |
| 1126–1129 | sequence valid, last is int | AO3 |
| 1134–1137 | terminal → skip | AO3 |
| 1146, 1160 | status missing | AO4, AO5 |
| 1169 | machine or component scope | AO7, AO8 |
| 1176 | other component → skip | AO8 |
| 1178 | not in flight → skip | AO7 |
| 1215 | user given | AI2 |
| 1220–1228 | integrity / HTTP / other | AI3 |
| 1238 | user given | UI2 |
| 1262 | user given | RI1 |
| 1292–1300 | phase 1 errors | SY1 |
| 1302 | user and supplier | SY3 |
| 1308–1316 | phase 2 errors | SY3 |
| 1389 | already voided | V2 |
| 1401 | reversed > 0 | V3 |
| 1412 | invoice linked | V5, V5a |
| 1416 | invoice found | V4 |
| 1417, 1422 | confirmed / draft / other | V4 |
| 1472 | no invoice after sync → re-read | CI4 |
| 1476 | no supplier | CI4 |
| 1481 | no invoice | CI4 |
| 1489–1496 | integrity: invoice now linked / not | CI6 |
| (new) | has_open_return | RF1–RF3 |
| (new) | receive_replacements | RX1–RX10 |
| (new) | settlement: outstanding ≥ value / < value / nothing outstanding or voided; partial receipt | RX8a–RX8d |
| (new) | settlement entry delete / edit / void | RX8h, RX8i |
| (new) | order lock first, then return, then credit note | RX1a |
| (new) | settlement written through `create_payment`; `allow_payments` refusal skipped | RX8j |
| (new) | credit note of another workspace / missing → left alone, warning | RX8k |
| (new) | settlement voided → return `paid` re-synced | RX8l |
| (new) | payments API sends `settled_by_replacement` → 400 | RX8m |

## Gap log
G1 (purchase_order_service.cases.md gap 1) — Fact — Overview: modules and field names of every input schema; `po_receive_event_items.receive_event_id` FK.
G2 (gap 2) — House rule not applied / coordinator decision — Overview **Row locks** table with the exact clause per read (`FOR UPDATE OF purchase_orders` for the joined order read; plain `FOR UPDATE` on `purchase_order_returns` and `account_invoices`; never NOWAIT / SKIP LOCKED); RE1, V1, CI1, CR1, VR1, RX1, RX8a reworded; new RX1a (order locked first in `receive_replacements`, lock order) — part of BUG-2810 / BUG-3176, no new ID.
G3 (gap 3) — Intent, decided under delegation (2026-11-22) — Overview: table `purchase_order_return_events` / model `PurchaseOrderReturnEvent` and its columns; RX8e gives the description text.
G4 (gap 4) — Intent, decided under delegation — Overview: `invoice_payments.source_type = 'purchase_order_event'`, `source_id` = RX9 event id; RX8b reworded.
G5 (gap 5) — Intent, decided under delegation — RX8d: `warnings: list[str]` on `PurchaseOrderReturnResponse`, `[]` on a normal settlement and every other return endpoint; voided credit note gets its own warning text (coordinator: same as the sales twin).
G6 (gap 6) — Intent, decided under delegation — RX8e / RX8f: `settled_amount "0.00"`, `payment_id` null when no entry.
G7 (gap 7) — Fact + intent — Overview **Numbers in texts**; SR6 as sent (fact), CR6 stored 2 places (fact), RX4 / RX8b / RX8e / RX9 as sent (decided, matches RE9 / SR6).
G8 (gap 8) — Fact — Overview **Ledgers**; RX6 names `transaction_type = 'purchase_order'`.
G9 (gap 9) — House rule (HR-16), coordinator decision — new RX8k: a foreign or missing credit note is left alone, no entry, receipt goes ahead, generic warning without id.
G10 (gap 10) — Fact — V3: worked example of the remaining case (receive +3, correction −3 → two adjustment rows, `inventory_reversed` with `reversed_count` 2); returns net to nothing (BUG-682).
G11 (gap 11) — Fact — Overview: transfer, work-order, machine, factory, project-component columns and status values used by AO5, AO7, AO8.
G12 (gap 12) — Fact (confirmed in `invoice_payment_manager.void_payment` → `_sync_linked_order` → `sync_return_paid`) — new RX8l. Also added under delegation: RX8j (settlement goes through `create_payment`: lock, audit row, `payment_recorded` event; `allow_payments` refusal skipped — coordinator decision) and RX8m (the payments API refuses the reserved method).
G13 (executor notes rev 2, DISCREPANCY-8 / AR-05) — Contradiction (bug tag wrong) — AR3 holds today: `line_subtotal` is `Numeric(15, 2)`, Postgres rounds half up on store, `invoice_item_dao.create` refreshes each line, and the amount is summed from the stored lines. BUG-3163 withdrawn; AR3 untagged and kept as a regression rule; H2 and the HR-15 resolution updated.
G14 (DISCREPANCY-6 / C-09) — Test mechanics — C5 / BUG-3175 rule and tag are right; the card cannot see the bug because its checks run after a test-level `db.rollback()`. The exposing setup is in Notes for the test designer.
G15 (DISCREPANCY-3 / IC-04) — Contradiction (code bug) — new IC1a [BUG-3184]: an empty `table_name` / `column_name` → `None`; IC1 no longer says "or falsy".
G16 (DISCREPANCY-4 / DD-04, V-02) — Contradiction (code bug) — new DD2a and V5a [BUG-3185]: the unlink event keeps the deleted draft's `invoice_id`; DD2 / V5 point to them.
G17 (DISCREPANCY-11 / PT-03, PT-04) — Fact — new PT2: `list_events` / `list_approvers` return tuples (shapes given).
G18 (DISCREPANCY-7 / G-01) — Fact — G1: the summary fields exist only on the list rows and the response schema, not on the ORM order; how to observe the defaults.
G19 (DISCREPANCY-2, -9 / AO-11, AO-12, every "nothing written") — Fact — Facts: one purchase workflow per workspace (`uq_order_workflows_workspace_type`); the table is `inventory`.
G20 (cases rev 4 gap, coordinator 2026-11-22) — Contradiction / Intent, decided — CR3 had no floor and the state is reachable today (receive 4, start a return of 4, correct the receipt to 0, complete → −4.00). New CR3a [BUG-3186]: completion refuses with 400 when any line would go below 0, nothing written. Status stays APPROVED.
