# Spec — `app/managers/purchase_order_return_manager.py`

> **Status:** APPROVED (2026-11-17; owner answered OQ-45 … OQ-48 and confirmed BUG-2750; case-designer gaps 1–4 closed)
> **Source commit:** e48a092

> **Review round 2026-11-14 (describe, under the reviewer's delegation of 2026-11-14).** Every item that is not money or stock policy was decided by Claude under the delegation and is marked so; none of them is the owner's own answer. The house-rule lines stand. Owner questions (what a return does to money; how a return and its credit note relate) are parked as OQ-45 … OQ-48. Twin of `tests/unit/managers/sales_order_return_manager.spec.md`: the two managers are the same code with PO/SO names, and every decision here is made the same way there.

> **Revision 2026-11-17 (apply-review + fill-gaps).** Owner answers of 2026-11-17 (`owner-questions.md` OQ-45 … OQ-48) applied: `validate_and_build_items` R6 → [BUG-2785], R7 → [BUG-2787], new R6a (check order); `sync_return_paid` R6 → [BUG-2788] (the check lives in `AccountInvoiceManager.void_invoice`, new R3c there, consistent with its O1 placement); OQ-48 → BUG-2789 (purchase order manager, no rule here). The owner also confirmed BUG-2750 (returnable counted once). Gaps of `purchase_order_return_manager.cases.md` closed (Gap log at the end): facts for gaps 1–2, and gaps 3–4 decided by Claude under the reviewer's delegation (2026-11-17), gap 3 logged as BUG-2792. Cards to revise: every `Q45-*`, `Q46-*`, `Q47-*` card (now bug cards, expected to fail), V-41 / V-42 (zero text fixed to `0`), new cards for R4 other-workspace reservations, R5 running total, R6a order.

> **Revision 2026-11-17 (owner refined OQ-48).** While a return is open a completed order shows "return in progress" (invoice frozen, nothing editable) and goes back to "completed" when the return is completed or cancelled; never reopened. Applied to OQ-48 and FU-2: the state is derived from this manager's `has_open_return`, never stored (Claude, under the reviewer's delegation, 2026-11-17); rules in `sales_manager.spec.md` *Return-in-progress state* RP1–RP7. No rule of this manager changes. Still APPROVED. Cards to revise (`purchase_order_return_manager.cases.md`): the Deferred row `OQ-48 / FU-2 [BUG-2789]` (text → stage stays `Complete`, order shows "return in progress" while `has_open_return`, back to "completed" when the last pending return closes, invoice frozen throughout). `PORM-HO-*` unchanged (they already pin the flag).

> **Revision 2026-11-19 (quote fix).** The OQ-47 suggested-answer quote now reads "have already moved", matching `account_invoice_manager` `void_invoice` R3c. Still APPROVED; no card change.

> **Revision 2026-11-19 (owner in chat, BUG-2810).** Replacement goods for a `replace` return on a completed PO come in through the return's own "receive replacements" step; the PO stays completed and its invoice frozen. Split decided by Claude under the reviewer's delegation (2026-11-19): this manager owns the **check** (new callable `validate_replacement_receipt`, rules RR1–RR8, *requires new method*), as it owns the check of a new return (`validate_and_build_items`); the **write** (stock in, ledger rows, line quantities, event) is the purchase order service's, with a posting module like `po_receive_inventory` (FU-2). Still APPROVED. Cards to revise (`purchase_order_return_manager.cases.md`): the Deferred row `OQ-48 / FU-2 [BUG-2789]` (replacement receipt now decided: point it to BUG-2810 / FU-2); new cards `PORM-RR-*` for RR1–RR8 (all strict xfail BUG-2810: the method does not exist).

> **Owner decisions applied, not asked again:** (1) invoice freeze, owner 2026-11-14 (`owner-questions.md`, "Invoice lock after completion"; BUG-2730 … BUG-2736): a completed order's invoice is frozen and corrections go through returns; a return credit note is never editable but can be voided, and the way to correct one is to void it and start a new return. (2) OQ-38 (owner 2026-11-11, BUG-2641): received and refunded are separate counts; a line is done when received + refunded = ordered. (3) HR-15: money rounds half up.

> **Verified PASS collaborators, referenced not restated:** `tests/unit/dao/purchase_order_return.spec.md` (returns and their lines: numbering, lists, `get_by_invoice_id`), `tests/unit/dao/purchase_order.spec.md` (`PurchaseOrderItemDAO.get_by_order`), `tests/unit/dao/base.spec.md` (`get_by_id_and_workspace`). The stock-out on completion is `tests/unit/managers/po_return_inventory.spec.md` (approved).

> **Verified by running** (my own script `v_ret.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\retprod\`, one transaction on `marker_test` with foreign-key triggers off (`SET LOCAL session_replication_role = replica`), rolled back, nothing committed): two request lines of 6 on one line of 10 received both accepted; exactly 10 accepted; `10.001` and `11` refused with the detail text; a bad line after a good one refused; a line of another order and a line of another workspace refused as "does not belong"; an unpriced line with no price sent → `unit_price None`; prices `-5`, `99999`, `0` kept as sent; quantity `0.004` passes the schema and is stored `0.00`, price `1.005` stored `1.01` (in-session value stays unrounded); a pending return of 4 leaves 6 available, 7 refused; after a completion done as `complete_return` does it (received 10 → 6, returned 0 → 4, refunded 0 → 4) only `2.00` is available and a return of the remaining 6 is refused; `get_return` with the right order, another order, another workspace, an unknown id; `list_returns`; `has_open_return` with only completed and voided returns; `sync_return_paid` with no invoice and `paid` already `False` / `True`. **Read, not run:** `PurchaseOrderService.start_return`, `_attach_return_invoice_for_po`, `complete_return`, `void_return`, `list_returns`, `get_return`; `PurchaseOrderManager.reopen_for_return`, `mark_order_complete`; `AccountInvoiceService.void_invoice`; `InvoicePaymentManager._sync_linked_order`; the models `PurchaseOrderItem`, `PurchaseOrderReturn`, `PurchaseOrderReturnItem`; the schema `app/schemas/purchase_order_return.py`. **Not run:** anything over HTTP; two concurrent transactions; the intended behaviour of the bugs.

## Review
> All items decided (delegation) or parked as owner questions; nothing blocks the test designer.

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| OQ-45 | A return's price per unit can be anything the user types: negative, zero, or above what was paid | bug — between 0 and the order line's price (BUG-2785) | owner, 2026-11-17 |
| OQ-46 | Returning a line that was ordered without a price makes a 0.00 credit note line | bug — a return price is required (BUG-2787) | owner, 2026-11-17 |
| OQ-47 | Voiding a return's credit note from the invoice page leaves the return as it was | bug — pending return cancelled with it; completed → void refused (BUG-2788) | owner, 2026-11-17 |
| OQ-48 | Starting a return reopens a completed order, which lifts its invoice freeze | bug — a return never reopens the order; while a return is open the completed order shows "return in progress" (derived `has_open_return`), invoice frozen, nothing editable; back to "completed" when the return closes (BUG-2789, not a rule here) | owner, 2026-11-17; refined by the owner 2026-11-17 |
| Q1 | After a return is completed, its quantity is taken off twice from what can still be returned | bug — counted once (BUG-2750) | Claude, delegated; confirmed by owner 2026-11-17 |
| Q2 | The same order line sent twice in one return is checked line by line, so more than was received can be returned | bug — the repeats are added up (BUG-2751) | Claude, delegated |
| P1 | Return quantities and prices with more than 2 decimals are accepted; `0.004` becomes a return line of `0.00` | bug — refused, 422 (BUG-2752) | Claude, delegated (BUG-604 precedent) |
| G3 | Another workspace's pending return lines reserve quantity on this workspace's line | bug — ignored, HR-16 (BUG-2792) | Claude, delegated (2026-11-17) |
| D1 | The "does not belong" and "only N available" messages differ in shape from the sales twin (line number here, item name there) | intended | Claude, delegated |

Decided by house rules: no lock while checking quantities (BUG-2753), no lock on the return read before complete / void (BUG-2754), a return's `items` in no fixed order (BUG-2755).

### House-rule violations — applied automatically

- **HR-10** `validate_and_build_items` R9 — the order's lines and their pending reservations are read with no row lock, then the caller creates the return. Two returns started at the same moment on one line both see the same quantity available and both are accepted (stock quantities and credit notes = real harm). Intended: the order's lines are read `FOR UPDATE` (or the order row is locked first), so the second start waits, then sees the first return's reservation and gets the normal "only N available" error.
**Answer:** bug — per HR-10 (house rule)
**Resolution:** 🐞 BUG-2753 (pattern `hr-10-unlocked-state-transition`). Rules: `validate_and_build_items` R9.
- **HR-10** `get_return` R4 — `complete_return` and `void_return` read the return through `get_return`, check `status == 'pending'`, then move stock out (complete) or void the credit note (void), with no row lock. Two completes at once both post stock out; a complete and a void at once leave a completed return with a voided credit note. The double completion is already BUG-800 (fix "lock the return row in `complete_return`"); this line covers the read itself and the void paths, one fix. Intended: `get_return` gains `for_update: bool = False`; with `True` the return row is read `SELECT … FOR UPDATE`; `complete_return` and `void_return` pass `True`, so the loser waits, then sees the new status and gets the normal "Only a pending return can be completed" / "… cancelled" error.
**Answer:** bug — per HR-10 (house rule)
**Resolution:** 🐞 BUG-2754 (pattern `hr-10-unlocked-state-transition`; same fix as BUG-800). Rules: `get_return` R4.
- **HR-6** `get_return` R5, `list_returns` R2 — a return's lines come back through the relationship `PurchaseOrderReturn.items`, which has no `order_by`; the response (`PurchaseOrderReturnResponse.items`) lists them in whatever order the database returns. The DAO's `get_by_return` got `id` ascending for the same reason (BUG-2431); the DAO spec's FU-1 (a) named this. Intended: `items` in `id` ascending (the order the lines were entered), by `order_by=PurchaseOrderReturnItem.id` on the relationship.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-2755 (pattern `unordered-pagination`). Rules: `get_return` R5, `list_returns` R2.

Checked and **not** a new line here: **HR-4** — no soft delete on returns, return lines, order lines or purchase orders; a voided return is a visible state. **HR-5, HR-7, HR-8** — nothing pages or searches. **HR-9** — `sync_return_paid` writes only `paid` (and the column's `updated_at` through `onupdate`) and only when it changes; it writes no `updated_by`, which is the service's (DAO spec note). **HR-15** — this manager does no arithmetic on money; the price it passes on is rounded half up by the `Numeric(15,2)` column when stored (verified `1.005` → `1.01`); the credit note's line subtotal is computed by the service (FU-1 (b)). **HR-16** — every read is scoped by the workspace: a line of another workspace, or of another order, is "does not belong" (R2) and the message echoes only the id the caller sent; a return of another workspace or another order is 404 (`get_return` R2); an invoice id pointing into another workspace counts as "no credit note" (`sync_return_paid` R3). **HR-1 / HR-2** — `notes` on a line is free text, passed on as sent.

### Owner questions — answered by the owner (2026-11-17), recorded in `docs/testing/owner-questions.md`

### OQ-45. A return's price per unit can be anything the user types — 🐞 BUG-2785
**Background:** Starting a return immediately creates and confirms a credit-note invoice of type `receivable` (the supplier owes us). Each credit-note line is quantity × the return line's unit price. The request may send a `unit_price` per line; if it sends none, the order line's price is used. Nothing checks the value sent: not its sign, not against the order line's price. Under the owner's 2026-11-14 freeze, returns are the way to correct a completed order, and the credit note cannot be edited afterwards (only voided).
**What happens today:** The price sent is used as is. Verified: `-5`, `0` and `99999` were all accepted.
**Example:** PO-0031 bought 10 bearings at 10.00. A user returns 1 bearing and types 99,999.00: the supplier now owes us 99,999.00 on a confirmed credit note. Typing −5.00 makes a credit note line of −5.00, i.e. we owe the supplier for goods we sent back.
**Rules affected:** `validate_and_build_items` R6 (tagged), R6a
**Suggested answer:** bug — a return price must be ≥ 0 and ≤ the order line's price (default: the order line's price); otherwise 400 `Return price for line {n} must be between 0 and {line price}`, nothing created. A price of 0 stays allowed (goods sent back with no credit).
**Alternatives:** (a) intended — the user may agree any credit with the supplier (restocking fee, goodwill credit). (b) only refuse negative prices; any price ≥ 0 allowed.
**Answer:** owner, 2026-11-17: suggested answer → BUG-2785
**Resolution:** 🐞 BUG-2785 (pattern `unbounded-credit-amount`). A sent price below 0, or above the order line's stored price, is refused with 400 `Return price for line {line_number} must be between 0 and {line price}`, nothing created; 0 and exactly the line price are accepted. An unpriced line has no upper bound (OQ-46 covers it). Detail text and check order (R6a) decided by Claude under the reviewer's delegation (2026-11-17). Rules: `validate_and_build_items` R6 (tagged), R6a.

### OQ-46. Returning a line that was ordered without a price makes a 0.00 credit note line — 🐞 BUG-2787
**Background:** A purchase order line may have no price (`unit_price` is nullable). When the return request sends no price for such a line, the return line keeps no price, and the service writes the credit-note line at 0.00 (`unit_price or 0`).
**What happens today:** The return is accepted and its credit note line is 0.00. Verified: an unpriced line with no price sent gives a return line with `unit_price None`.
**Example:** PO-0040 ordered 5 sample rolls with no price yet, all received, and the supplier later invoiced them separately. A user returns 2 rolls and leaves the price empty: the credit note says the supplier owes us 0.00 for them, and it cannot be edited afterwards (only voided).
**Rules affected:** `validate_and_build_items` R7a (tagged), R6a
**Suggested answer:** bug — when the order line has no price, the request must send one for that line; otherwise 400 `Enter a return price for line {n} — the order line has no price`, nothing created.
**Alternatives:** (a) intended — a 0.00 credit line is fine; credit is agreed separately. (b) take the price from the order's confirmed invoice line instead.
**Answer:** owner, 2026-11-17: suggested answer → BUG-2787
**Resolution:** 🐞 BUG-2787 (pattern `missing-required-money-input`). Rules: `validate_and_build_items` R7 (tagged), R6a.

### OQ-47. Voiding a return's credit note from the invoice page leaves the return as it was — 🐞 BUG-2788
**Background:** The owner decided (2026-11-14) that a return credit note can be voided, and that to correct one you void it and start a new return. The return page has its own "Cancel return" (`void_return`): it voids the credit note **and** marks the return `voided`, which frees the reserved quantity. The invoice page's "Void" (`AccountInvoiceService.void_invoice`) voids only the invoice; nothing tells the return. The only link back is `sync_return_paid`, which runs after a payment change and only resets the `paid` flag.
**What happens today:** A pending return whose credit note was voided from the invoice page stays `pending`: its quantity stays reserved (no new return can take it) and it can still be completed, sending the goods out with no credit. A completed return whose credit note is voided stays `completed`: the goods are gone and nothing is owed. `paid` keeps its old value until a payment changes.
**Example:** Return PR-2026-004 sends 3 motors (credit 3,000.00) back. The accountant voids its credit note on the invoice page to fix a typo, as the owner's rule says. The storekeeper then clicks "Complete return": 3 motors leave stock and the supplier owes nothing. A new return for the corrected amount is refused ("only 0 available to return"), because the voided-credit return still reserves the motors.
**Rules affected:** `sync_return_paid` R6 (tagged); `account_invoice_manager` `void_invoice` R3c
**Suggested answer:** bug — voiding a credit note from the invoice page is the same as cancelling its return while the return is pending (return → `voided`, quantity freed). For a **completed** return, voiding its credit note is refused (400 `This return is completed — its goods have already moved. Start a new return or issue a separate credit note.`), because "void and start a new return" cannot work once the goods are gone.
**Alternatives:** (a) intended — the invoice and the return are kept apart. (b) refuse voiding any return credit note from the invoice page; only "Cancel return" may do it (pending returns only).
**Answer:** owner, 2026-11-17: suggested answer → BUG-2788
**Resolution:** 🐞 BUG-2788 (pattern `linked-record-not-updated`). **Where the check belongs** (decided by Claude under the reviewer's delegation, 2026-11-17): in `AccountInvoiceManager.void_invoice` (new R3c there), next to the freeze check, for the same reason as its O1 placement — every path that voids an invoice (the `/void` endpoint, `void_return`, internal callers) goes through it, so none can skip the rule. The return managers keep only reads and the `paid` sync; they gain no new rule except the outcome in `sync_return_paid` R6. `void_return` keeps working: it calls `void_invoice` on a pending return, which now also sets the return `voided`; `void_return`'s own `status = 'voided'` is then a no-op. Rules: `sync_return_paid` R6 (tagged); `account_invoice_manager.spec.md` `void_invoice` R3c.

### OQ-48. Starting a return reopens a completed order, which lifts its invoice freeze — 🐞 BUG-2789
**Background:** Under the owner's freeze (2026-11-14) a completed order's invoice cannot be reverted, voided or deleted, and corrections go through returns. But starting a return on a completed purchase order moves it back to `Receiving` (`PurchaseOrderManager.reopen_for_return`; the sales twin clears `order_completed`). While the return is pending (and, for a `replace` return, until the goods are re-received) the order is no longer "completed", so the freeze no longer protects its invoice.
**What happens today:** Starting any return on a completed order reopens it; the order's own invoice is no longer frozen. For a purchase order the invoice stays protected anyway (revert and void are refused once anything was received, and a return needs received goods), so in practice the sales order is the open door.
**Example:** SO-2026-018 is completed and its invoice (12,000.00) is frozen. A customer sends one chair back; the user starts a return. The order is reopened, and its 12,000.00 invoice can now be voided from the invoice page, cancelling its payments, which the freeze was meant to stop.
**Rules affected:** none in this manager — the reopen is `PurchaseOrderManager.reopen_for_return` / `SalesManager.reopen_for_return`; the freeze is `AccountInvoiceManager` F2 (FU-2).
**Suggested answer:** bug — once an order has been completed, its invoice stays frozen for good, even while a return reopens the order (the freeze reads "was ever completed", e.g. a first-completed timestamp, not the current stage).
**Alternatives:** (a) a return does not reopen the order at all; returns are tracked on their own. (b) intended — a reopened order is open again, invoice included.
**Answer:** owner, 2026-11-17: a return never reopens a completed order or lifts its invoice freeze → BUG-2789. **Refined by the owner 2026-11-17:** while a return is open a completed order shows "return in progress"; the invoice stays frozen and nothing on the order is editable; when the return is completed or cancelled the order goes back to "completed". Never reopened to open/editable.
**Resolution:** 🐞 BUG-2789 (pattern `completed-order-invoice-not-frozen`, with BUG-2730). Starting a return leaves a completed purchase order completed (stage `Complete`, `actual_delivery_date` kept, no `order_reopened` event); its invoice stays frozen. The rule belongs to `PurchaseOrderManager.reopen_for_return` (no spec yet; FU-2). **Refinement (2026-11-17):** the "return in progress" state is derived from this manager's `has_open_return` (R1–R2), never stored: the stage stays `Complete`, so freeze F2 (which reads only the stage) keeps the invoice frozen, and the completed-order guards (approval withdrawal, "Cannot receive against a completed purchase order") keep the order uneditable. Shape chosen by Claude under the reviewer's delegation (2026-11-17); full rules, including two returns at once, one closing while another stays open, and a return cancelled through its credit note (BUG-2788), in `sales_manager.spec.md` *Return-in-progress state* RP1–RP7 (same rules with PO names). No rule of this manager changes: `has_open_return` R1–R2 already give the flag (one or several pending → `True`; all completed / voided → `False`).

### Decided under the reviewer's delegation (2026-11-14)

### Q1. A completed return's quantity is taken off twice from what can still be returned — 🐞 BUG-2750
**Background:** Each order line keeps `quantity_received` and `quantity_returned`. Completing a return lowers `quantity_received` by the returned amount ("the goods physically left") **and** raises `quantity_returned` by it. What can still be returned is worked out as received − returned − quantity in pending returns.
**What happens today:** A completed return counts twice. Verified: 10 received, a return of 4 completed → received 6, returned 4, available **2.00**; a return of the remaining 6 is refused "only 2.00 available to return". After a `replace` return of 4 and a re-receipt of 4, 10 are on hand but only 6 can be returned.
**Example:** PO-0012 line 1: 10 pumps received. 4 are sent back as faulty (return completed). Two more turn out faulty the next week: the user can return only 2 of the 6 pumps still held, and the other 4 cannot be returned at all.
**Rules affected:** `validate_and_build_items` R4
**Answer:** bug — what can be returned is what is held now: received (already net of completed returns) minus the quantity in pending returns, never below 0 (decided by Claude under the reviewer's delegation, 2026-11-14: arithmetic, not policy — the model's own docstring says received is lowered because the goods left; consistent with OQ-38, refunded quantity is not on hand and is not returnable)
**Confirmed:** owner, 2026-11-17 (with the OQ-45 answer): returnable counted once.
**Resolution:** 🐞 BUG-2750 (pattern `returned-quantity-counted-twice`). The fix is in the model property `PurchaseOrderItem.quantity_available_to_return` (also shown to the web app as `quantity_available_to_return` in the order line response). Rules: `validate_and_build_items` R4 (tagged).

### Q2. The same order line sent twice in one return is checked line by line — 🐞 BUG-2751
**Background:** A return request is a list of lines, each naming an order line. Nothing stops the list naming one order line twice.
**What happens today:** Each request line is compared with the order line's available quantity on its own. Verified: two request lines of 6 on a line with 10 available were both accepted (12 reserved out of 10).
**Example:** A user adds "line 1 × 6" twice by mistake. The return reserves 12 of 10 pumps; completing it lowers received to −2 and sends 12 pumps out of a stock that got 10.
**Rules affected:** `validate_and_build_items` R5
**Answer:** bug — request lines naming the same order line are added up and the total is checked against what is available; over → 400 with the total in the message (`Cannot return 12 of line 1 — only 10.00 available to return`); the lines are kept as sent (each with its own price and note) when the total fits (decided by Claude under the reviewer's delegation, 2026-11-14: the limit "never more than held" is plain; whether to merge or refuse repeats is cosmetic, and adding up keeps every typed price)
**Resolution:** 🐞 BUG-2751 (pattern `repeated-line-bypasses-limit`). Rules: `validate_and_build_items` R5 (tagged).

### P1. Return quantities and prices with more than 2 decimals are accepted — 🐞 BUG-2752
**Background:** `quantity_returned` and `unit_price` are stored in `Numeric(15,2)` columns, which round to 2 decimals (half up) and hold at most 13 digits before the point. The schema only checks the quantity is > 0. The same was ruled a bug for payment amounts (BUG-604) and stock prices (BUG-708).
**What happens today:** `0.004` passes (> 0), is checked against the available quantity as `0.004`, and is stored as a return line of `0.00`; `1.005` is stored `1.01` while the caller keeps `1.005` in memory for the credit note; a value of 10^13 or more fails at the flush (500). Verified for `0.004` and `1.005`.
**Example:** A typo `0.004` makes a return with a line of 0.00 units and its own confirmed credit note.
**Rules affected:** `validate_and_build_items` R10 (schema)
**Answer:** bug — per BUG-604 precedent: `PurchaseOrderReturnItemCreate` refuses a `quantity_returned` or `unit_price` with more than 2 decimal places or more than 13 integer digits (422), nothing reaches the manager (decided by Claude under the reviewer's delegation, 2026-11-14)
**Resolution:** 🐞 BUG-2752 (pattern `unbounded-decimal-input`). Fix in `app/schemas/purchase_order_return.py`. Rules: `validate_and_build_items` R10 (tagged).

### D1. Message shapes differ from the sales twin — ✅ intended
**Background:** Here the "too many" message names the order line by its line number (`line 2`), the sales twin by its item name in quotes (`"Install fee"`), because sales lines have no line number.
**What happens today:** `Cannot return 5 of line 2 — only 3.00 available to return`.
**Example:** The user sees the line number shown on the purchase order page.
**Rules affected:** `validate_and_build_items` R3
**Answer:** intended (decided by Claude under the reviewer's delegation, 2026-11-14: each names the line as its own page shows it)
**Resolution:** no bug. Rules: `validate_and_build_items` R3 ✅.

## Follow-ups for other reviews
> Nothing below is a rule of this manager and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Purchase order service** (`start_return`, `_attach_return_invoice_for_po`, `complete_return`, `void_return`; no spec yet) | (a) `start_return` refuses a voided order and an order with nothing received, then calls `validate_and_build_items`; a completed order is allowed (owner freeze: corrections go through returns). BUG-801 (fractional quantity on a storage / machine PO) is to be refused at start: the destination is known only in the service, so the check belongs there, not here. (b) The credit-note lines are built from the in-session return lines: `unit_price or 0` and `line_subtotal = unit_price × quantity` use the unrounded values sent (`1.005`), not the stored ones; after BUG-2752 this cannot happen, but the subtotal must still be rounded half up (HR-15). (c) `void_return` sets no `updated_by`. (d) `complete_return` and `void_return` must pass `for_update=True` to `get_return` (BUG-2754). | `validate_and_build_items`, `get_return` |
| FU-2 | **Purchase order manager** (`reopen_for_return`) | OQ-48 answered (owner 2026-11-17): a return never reopens a completed order → BUG-2789; write the rule when that manager is described. A `replace` return on a completed order then leaves a receiving gap on a completed order: re-receiving onto a completed order must stay possible, or be decided there. **2026-11-17 (OQ-48 refined):** the order is never editable while completed, and receiving onto a completed PO is refused today ("Cannot receive against a completed purchase order"); how replacement goods are received is still open (order workflow, owner). The return-in-progress state itself is decided: `sales_manager.spec.md` *Return-in-progress state* RP1–RP7. **2026-11-19 (owner, BUG-2810):** replacements are received through the return, never through the PO's receive path, and the PO stays `Complete` with its invoice frozen. The check is this manager's `validate_replacement_receipt` RR1–RR8. **For the purchase order service** (new `receive_replacements(db, po_id, return_id, workspace_id, user_id, data)`, e.g. `POST /purchase-orders/{po_id}/returns/{return_id}/receive-replacements/`), decided by Claude under the reviewer's delegation (2026-11-19): (a) read the return with `get_return(..., for_update=True)` (HR-10), then RR1–RR8; (b) per received line: `return_item.quantity_replaced += q` (*requires new column* `purchase_order_return_items.quantity_replaced` Numeric(15,2) NOT NULL default 0) and `po_line.quantity_received += q`, so the line closes again (received + refunded = ordered, OQ-38) — `quantity_returned` is not touched (the goods did go back once); (c) stock in at the PO's destination (factory storage or machine) with **one ledger row per return line received**: transaction type as a PO receipt, `source_type 'purchase_return_replacement'`, `source_id` = return line id, `quantity` = q, `unit_cost` = the original PO line's `unit_price` (for an unpriced line, the return line's `unit_price`, which BUG-2787 makes required), `total_cost` = cost × q rounded half up (HR-15), notes `Replacement for return {return_number} — PO {po_number} line {line_number}`; (d) no change to the PO's stage, `actual_delivery_date`, approvals or invoice; no new invoice or credit note; one PO event `return_replacement_received` (`Replacements received for return {return_number} — {q} unit(s)`); the return's `status` stays `completed`. **Why:** the limit (RR5) keeps `replace` meaning "the same goods again" — never more than went back, so stock cannot grow past what was bought; the cost is the original line cost because no new money changes hands (the invoice is frozen and the replacement settles the return), so stock is valued as if the goods had never left and the average is unchanged by a like-for-like swap; one ledger row per return line mirrors the stock-out rows of `po_return_inventory` (one per return line), so every unit out has a matching unit in, traceable to the same return line. Open for the owner, not asked now (money, not stock): a `replace` return also gets a confirmed credit note at start, so the supplier owes us for goods they then replace — whether a replacement should settle that credit note is left with OQ-45's area and noted in `docs/testing/owner-questions.md` is **not** added; flag it at the purchase order service describe. | reading `start_return`; owner 2026-11-19 |
| FU-3 | **Account invoice manager** (`void_invoice`) | OQ-47 answered → BUG-2788; rule `void_invoice` R3c written there (2026-11-17). | `sync_return_paid` |

## Overview
`PurchaseOrderReturnManager` holds the checks and reads for **purchase order returns** (received goods sent back to the supplier, lifecycle `pending` → `completed` | `voided`). It checks a new return's lines against what can still be returned and builds the rows to store, looks returns up for one order, tells the order whether a return is still open, and keeps the return's `paid` flag in step with its credit-note invoice. It writes nothing except `paid`. Callers: `PurchaseOrderService` (`start_return`, `complete_return`, `void_return`, `list_returns`, `get_return`), `PurchaseOrderManager.mark_order_complete` (`has_open_return`), `InvoicePaymentManager._sync_linked_order` (`sync_return_paid`, after every payment recorded or voided on a credit note). It never commits and, today, takes no lock.

**Callables:** 5 specified + 1 to be added (`validate_replacement_receipt`, BUG-2810) · 2 not specified
**Externals to mock:** none.
**Integration-only behavior:** none.

**Notes for the test designer:**
- Rows needed: a `purchase_orders` row, its `purchase_order_items` (need `items` rows), returns and their lines (parents per `tests/unit/dao/purchase_order_return.spec.md` Notes), and for `sync_return_paid` an `account_invoices` row (needs an `accounts` row). Rows of another workspace on one order are invalid data (HR-16) and can only be made by inserting directly.
- "Available to return" reads the line's return lines through the relationship `PurchaseOrderItem.return_items` and each one's return status. After inserting returns directly, `session.expire_all()` (or a fresh read) so the relationship is reloaded.
- To set up "a completed return" do what `complete_return` does: return `status = 'completed'`; on the order line `quantity_received -= q`, `quantity_returned += q`, and for `refund` also `quantity_refunded += q`.
- The concurrency rules (R9 of `validate_and_build_items`, R4 of `get_return`) need two transactions; no unit case. A card may check that `get_return(..., for_update=True)` returns the same row once the parameter exists.
- `HTTPException` is FastAPI's; assert `status_code` and `detail`.

## Not specified
- `PurchaseOrderReturnManager.__init__` — wires the return, return-line and order-line DAOs; no logic.
- `purchase_order_return_manager` — module singleton.
- Inherited `BaseManager` methods — `tests/unit/managers/base_manager.spec.md`; no caller uses them on this manager.

---

## `PurchaseOrderReturnManager.has_open_return(session, purchase_order_id, workspace_id)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `PurchaseOrderManager.mark_order_complete`)

**Purpose:** Does this order still have a return in progress?

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `purchase_order_id` | int | Not checked to exist. |
| `workspace_id` | int | Only returns of this workspace count. |

**Returns:** `bool`.

**Rules:**
- **R1.** `True` when the order has at least one return of this workspace with status `pending` (one or several); `False` when its returns are all `completed` / `voided` (verified), when it has none, or for an unknown order. Which statuses count follows `get_open_by_purchase_order` R1 (exact `'pending'`).
- **R2.** A pending return of the same order id under another workspace does not count (`False`).
- **R3.** Nothing is written.

**Errors:** none. **Side effects:** none.

---

## `PurchaseOrderReturnManager.validate_and_build_items(session, *, purchase_order_id, workspace_id, data)`
**Shape:** validator
**Persistence:** reads
**Visibility:** public (used by: `PurchaseOrderService.start_return`)

**Purpose:** Check each requested return line against the order and against what can still be returned, and build the return-line rows to store.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `purchase_order_id` | int | The order the lines must belong to; not checked to exist (the service reads it first). |
| `workspace_id` | int | Only order lines of this workspace are considered. |
| `data` | `PurchaseOrderReturnCreate` | Fields (G2, from the schema): `return_type` **required**, `Literal['replace', 'refund']`; `items` **required**, a list of `PurchaseOrderReturnItemCreate`; `reason` and `notes` optional, `str \| None`, default `None`. Line fields: `po_item_id` **required** int, `quantity_returned` **required** Decimal, `unit_price` and `notes` optional (default `None`). Unknown extra fields are ignored (Pydantic default). Schema checks before the manager: `return_type` is `replace` or `refund` (else 422); `items` not empty (`At least one item must be selected for return`); every `quantity_returned` > 0 (`All return quantities must be positive`). Per line: `po_item_id` int, `quantity_returned` Decimal, `unit_price` Decimal or `None` (default), `notes` str or `None`. `return_type`, `reason`, `notes` of the return are not used here. |

**Returns:** `list[dict]`, one per request line, in request order: `{'po_item_id', 'item_id', 'quantity_returned', 'unit_price', 'notes'}`. Nothing is stored.

**Rules:**
- **R1.** Every request line is checked in request order; the first failure raises and nothing is returned (a good line before a bad one does not help, verified). A request that passes returns one dict per request line, in request order.
- **R2.** A request line whose `po_item_id` is not a line of this order in this workspace → 400 `Item {po_item_id} does not belong to this purchase order`. Covers an unknown id, a line of another order (verified), and a line of this order id under another workspace (verified; HR-16). The order's lines are `PurchaseOrderItemDAO.get_by_order` R1–R2.
- **R3.** ✅ A request quantity greater than what can be returned (R4) → 400 `Cannot return {quantity as sent} of line {line_number} — only {available} available to return`. The quantity is shown as sent (`10.001`, `11`); `available` as computed from the stored values (`6.00`). When nothing is left — exactly zero, or arithmetic below zero — `available` prints `0` (G1: the result is `max(Decimal(0), …)`, and Python's `max` returns the first of equal values, so a computed `0.00` also comes out as `Decimal(0)`; verified `only 0 available to return` on a line fully reserved by a pending return). Exactly the available quantity is accepted (verified: 10 of 10).
- **R4.** [BUG-2750] What can be returned on a line = `quantity_received` − (sum of `quantity_returned` of this line's return lines whose return is `pending`), never below 0. `quantity_received` is already lowered by completed returns; voided returns reserve nothing; refunded quantity is not on hand and does not count (OQ-38). Example: 10 received, a pending return of 4 → 6 (verified); 10 received, a return of 4 completed (received now 6) → 6. Confirmed by the owner, 2026-11-17. *(Today: completed returns are taken off a second time through `quantity_returned`: received 6, returned 4 → 2.00 available, verified. With only pending and voided returns today's value equals the intended one.)*
- **R4a.** [BUG-2792] (HR-16, decided by Claude under the reviewer's delegation, 2026-11-17) Only return lines of this workspace whose return is of this workspace reserve quantity; a pending return line of another workspace pointing at this line (invalid data) is ignored. *(Today: it reserves: 3 received, a pending return line of 1 under another workspace → `2.00` available, verified.)*
- **R5.** [BUG-2751] Request lines naming the same order line are added up, and the total is checked as in R3, with the total in the message (`Cannot return 12 of line 1 — only 10.00 available to return`). When the total fits, every request line is kept as its own dict. The total is a **running total** in request order (G4, decided by Claude under the reviewer's delegation, 2026-11-17): each line is checked when it is reached, against the sum of its own and the earlier lines' quantities for that order line, so the error is raised at the repeat that goes over and names that running total; a different line that fails earlier in the request wins (R1). Example: lines `A×6, B×99 (unknown), A×6` → `Item … does not belong` (B is reached first); `A×6, A×6, B×99` with 10 available → `Cannot return 12 of line 1 …`. *(Today: each line is checked alone; two lines of 6 on 10 available are both accepted, verified.)*
- **R6.** [BUG-2785] (owner, OQ-45) A sent `unit_price` must be ≥ 0 and, when the order line has a price, ≤ that price; otherwise 400 `Return price for line {line_number} must be between 0 and {line price}` (`{line price}` as stored, e.g. `10.00`), nothing returned. Within the range it is used as sent; `0` is a price, not "not sent"; exactly the line price is accepted. When the order line has no price, any sent price ≥ 0 is accepted; a negative one → 400 `Return price for line {line_number} cannot be negative`. *(Today: any value kept as sent; verified `-5`, `0`, `99999`.)*
- **R6a.** Check order per request line (decided by Claude under the reviewer's delegation, 2026-11-17): lines in request order (R1); for each line R2 (belongs), then R3 / R5 (quantity, running total), then R6 (price range), then R7 (missing price). The first failure raises.
- **R7.** When the request line sends no `unit_price` (`None`), the order line's `unit_price` is used.
- **R7a.** [BUG-2787] (owner, OQ-46) When neither the request line nor the order line has a price → 400 `Enter a return price for line {line_number} — the order line has no price`, nothing returned. *(Today: `unit_price None` is returned and the request is accepted, verified; the credit note line becomes 0.00.)*
- **R8.** Each dict has `po_item_id` = the order line's id, `item_id` = the order line's catalog item, `quantity_returned` as sent, `notes` as sent (`None`, `""` kept).
- **R9.** [BUG-2753] (HR-10) The order's lines are read with a row lock (`FOR UPDATE`) before the check, so two returns started at the same moment on one line cannot together reserve more than is available; the second waits and then gets R3. *(Today: no lock; both are accepted.)* Not unit-testable (two transactions); no case.
- **R10.** [BUG-2752] (schema) A `quantity_returned` or `unit_price` with more than 2 decimal places or more than 13 digits before the point is refused by `PurchaseOrderReturnItemCreate` (422), so the manager never sees one. *(Today: accepted; `0.004` passes the check against what is available and is stored as `0.00`, `1.005` is stored `1.01`, verified; ≥ 10^13 fails at the flush.)*
- **R11.** Nothing is written; the order lines are not changed (the reservation exists only once the caller stores the return lines).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| line not on this order / workspace | `HTTPException` 400 | `Item {po_item_id} does not belong to this purchase order` |
| more than can be returned (per line, or running total per order line after BUG-2751) | `HTTPException` 400 | `Cannot return {qty} of line {line_number} — only {available} available to return` |
| price below 0 or above the line price (BUG-2785) | `HTTPException` 400 | `Return price for line {line_number} must be between 0 and {line price}` / unpriced line: `Return price for line {line_number} cannot be negative` |
| no price anywhere (BUG-2787) | `HTTPException` 400 | `Enter a return price for line {line_number} — the order line has no price` |
| schema: empty items, quantity ≤ 0, bad `return_type`, too many decimals / digits (BUG-2752) | `pydantic.ValidationError` (422 at the API) | `At least one item must be selected for return` / `All return quantities must be positive` / literal error / decimal error |

**Side effects:** none.

---

## `PurchaseOrderReturnManager.get_return(session, return_id, purchase_order_id, workspace_id)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** public (used by: `PurchaseOrderService.complete_return`, `void_return`, `get_return`)

**Purpose:** One return of one order, or 404.

**Inputs:** `return_id`, `purchase_order_id`, `workspace_id` — ints. (After BUG-2754: `for_update: bool = False`.)

**Returns:** the `PurchaseOrderReturn`, any status.

**Rules:**
- **R1.** A return of this workspace that belongs to this order is returned, whatever its status (`pending`, `completed`, `voided`).
- **R2.** An unknown id, a return of another order (verified), or a return of another workspace (verified) → 404 `Return with ID {return_id} not found`. The workspace lookup is `BaseDAO.get_by_id_and_workspace`.
- **R3.** Nothing is written.
- **R4.** [BUG-2754] (HR-10) With `for_update=True` the return row is read `SELECT … FOR UPDATE`; `complete_return` and `void_return` read it that way, so of two concurrent completes / voids the second sees the new status and gets the normal "only a pending return …" error. The default (`False`) reads without a lock, as today. *(Today: there is no such parameter and no lock.)* Concurrency not unit-testable; a card may check that `for_update=True` returns the same row.
- **R5.** [BUG-2755] (HR-6) The return's `items` come in `id` ascending. *(Today: the relationship has no `order_by`; database order.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found / other order / other workspace | `HTTPException` 404 | `Return with ID {return_id} not found` |

**Side effects:** none.

---

## `PurchaseOrderReturnManager.list_returns(session, purchase_order_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `PurchaseOrderService.list_returns` → `GET /purchase-orders/{po_id}/returns/`)

**Purpose:** Every return of one order.

**Inputs:** `purchase_order_id`, `workspace_id` — ints; the order is not checked to exist here (the service reads it first).

**Returns:** `list[PurchaseOrderReturn]`, possibly empty.

**Rules:**
- **R1.** The order's returns of this workspace, every status, newest first — exactly `DAOPurchaseOrderReturn.get_by_purchase_order` R1–R3 (ties broken by `id` descending after BUG-2429). Unknown order or another workspace → `[]`.
- **R2.** [BUG-2755] (HR-6) Each return's `items` come in `id` ascending, as `get_return` R5.

**Errors:** none. **Side effects:** none.

---

## `PurchaseOrderReturnManager.sync_return_paid(session, ret, workspace_id)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: `InvoicePaymentManager._sync_linked_order` after a payment is recorded or voided on a credit note; `PurchaseOrderService.void_return`)

**Purpose:** Keep the return's `paid` flag equal to "its credit note is fully paid".

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `ret` | `PurchaseOrderReturn` | A loaded return; any status. |
| `workspace_id` | int | The credit note is looked up in this workspace only. |

**Returns:** `bool` — `True` when `paid` changed, `False` when it already had the right value.

**Rules:**
- **R1.** The new value is `True` only when the return has a credit note (`invoice_id` set), that invoice is in this workspace, and its `payment_status` is exactly `'paid'`.
- **R2.** `payment_status` `'unpaid'`, `'partial'` or `'overdue'` → `False`. A voided credit note has `payment_status = 'unpaid'` (the void resets it) → `False`.
- **R3.** No credit note (`invoice_id` `NULL`, e.g. after the invoice was deleted — `ON DELETE SET NULL`), or an `invoice_id` that is not an invoice of this workspace (invalid data, HR-16) → `False`. Verified for `NULL`.
- **R4.** `paid` already equal to the new value → returns `False`; nothing is written and nothing is flushed (`updated_at` unchanged). Verified (`False` → `False`).
- **R5.** `paid` different → `paid` set to the new value, flushed, returns `True` (verified `True` → `False` with no credit note). `updated_at` is set by the column's `onupdate`; `updated_by`, `status`, `completed_*` are not touched. Not committed.
- **R6.** [BUG-2788] (owner, OQ-47) Voiding a return's credit note, from any path, keeps the return in step: a `pending` return becomes `voided` (its quantity is no longer reserved, `has_open_return` no longer counts it, and `paid` is re-synced to `False`); for a `completed` return the void is refused (400, credit note and return unchanged). Both are done by `AccountInvoiceManager.void_invoice` R3c, not by this method; this method still only writes `paid`. A test sets it up by voiding the credit note through `AccountInvoiceManager.void_invoice` and reading the return. *(Today: the return's status never follows its credit note; a pending return stays pending and completable, a completed one stays completed.)*

**Errors:** none.

**Side effects:** at most `purchase_order_returns.paid` (+ `updated_at`), flushed.

---

---

## `PurchaseOrderReturnManager.validate_replacement_receipt(session, *, ret, workspace_id, data)` — *requires new method* (BUG-2810)
**Shape:** validator
**Persistence:** reads
**Visibility:** public (to be used by: `PurchaseOrderService.receive_replacements`, FU-2)

**Purpose:** Check a receipt of replacement goods against a completed `replace` return, and build what the service posts.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `ret` | `PurchaseOrderReturn` | Read by the caller with `get_return(..., for_update=True)` (R4). |
| `workspace_id` | int | Only this workspace's return lines count. |
| `data` | new schema `PurchaseOrderReturnReplacementCreate` | `items`: non-empty list of `{return_item_id: int, quantity: Decimal}`; `quantity` > 0, at most 2 decimal places and 13 integer digits (as BUG-2752); `notes` optional. Schema failures → 422. |

**Returns:** `list[dict]` in request order: `{'return_item_id', 'po_item_id', 'item_id', 'quantity', 'unit_cost'}`. Nothing is stored.

**Rules** (all [BUG-2810], owner 2026-11-19; details decided by Claude under the reviewer's delegation, 2026-11-19):
- **RR1.** A return whose `return_type` is not `'replace'` → 400 `Only a replace return can receive replacements`.
- **RR2.** A `replace` return that is not `completed` → 400 `Complete the return before receiving replacements` (pending: the goods have not gone back yet; voided: nothing to replace).
- **RR3.** Lines are checked in request order; the first failure raises (as `validate_and_build_items` R1).
- **RR4.** A `return_item_id` that is not a line of this return in this workspace → 400 `Line {return_item_id} is not part of return {return_number}` (HR-16: another workspace's line is "not part").
- **RR5.** The quantity limit is the replaced quantity: for each return line, the running total in this request plus what was already received for it (`quantity_replaced`, *requires new column*) must not exceed its `quantity_returned`; over → 400 `Cannot receive {total} replacement(s) for line {line_number} — only {left} still to replace` (`{line_number}` of the PO line, `{left}` = returned − already replaced, printed like `validate_and_build_items` R3: `0` when nothing is left).
- **RR6.** `unit_cost` = the original PO line's stored `unit_price`; when that is `NULL`, the return line's `unit_price`. Never the request's: the request has no price field.
- **RR7.** The PO's state is not checked here beyond the return: a completed PO is accepted, which is the point (the PO's own receive path keeps refusing a completed PO). A voided PO cannot reach here (a return needs received goods, and a PO with goods received cannot be voided, BUG-2734).
- **RR8.** Nothing is written; the return, its lines and the PO lines are unchanged.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not a `replace` return | `HTTPException` 400 | `Only a replace return can receive replacements` |
| return not completed | `HTTPException` 400 | `Complete the return before receiving replacements` |
| line not on this return / workspace | `HTTPException` 400 | `Line {return_item_id} is not part of return {return_number}` |
| more than still to replace | `HTTPException` 400 | `Cannot receive {total} replacement(s) for line {line_number} — only {left} still to replace` |
| schema | `pydantic.ValidationError` (422) | — |

**Side effects:** none.

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 27 | any pending return / none | `has_open_return` R1, R2 |
| 41–45 | order lines of this order and workspace (map) | `validate_and_build_items` R2 |
| 47 | loop over request lines (one / many, first failure stops) | `validate_and_build_items` R1 |
| 49 | line not in the map | `validate_and_build_items` R2 |
| 54 | available = received − returned − pending (model property: `return_items` filtered on `status == 'pending'`, `max(0, …)`) | `validate_and_build_items` R4 |
| 55 | requested > available / equal | `validate_and_build_items` R3, R5 |
| 63 | `unit_price is not None` → sent / order line's (possibly `None`) | `validate_and_build_items` R6, R7 |
| 64–70 | dict built | `validate_and_build_items` R8 |
| 76–77 | not found, or another order | `get_return` R1, R2 |
| 93 | `invoice_id is None` | `sync_return_paid` R3 |
| 94–97 | invoice found in workspace and `payment_status == 'paid'` | `sync_return_paid` R1, R2, R3 |
| 98 | unchanged → `False` | `sync_return_paid` R4 |
| 100–102 | changed → set, flush, `True` | `sync_return_paid` R5 |
| schema `validate_return` | empty items / quantity ≤ 0 | `validate_and_build_items` Inputs, Errors |

## Gap log
- G1 (purchase_order_return_manager.cases.md gap 1) — Fact — `validate_and_build_items` R3: at exactly zero, and when the arithmetic goes below zero, `available` prints `0` (`max(Decimal(0), …)` returns its first argument on a tie); verified 2026-11-17. The OQ-47 example now reads `only 0 available to return`.
- G2 (gap 2) — Fact — Inputs: `PurchaseOrderReturnCreate` requires `return_type` and `items`; `reason`, `notes` optional `str | None` (default `None`); line `po_item_id`, `quantity_returned` required, `unit_price`, `notes` optional; extras ignored. Verified from the schema's `model_fields`.
- G3 (gap 3) — Intent, decided by Claude under the reviewer's delegation (2026-11-17), HR-16 — new R4a: another workspace's pending return lines do not reserve quantity. Today they do (verified) → BUG-2792.
- G4 (gap 4) — Intent, decided by Claude under the reviewer's delegation (2026-11-17) — R5: running total in request order, the first failing line in request order wins; R6a: per-line check order R2 → R3/R5 → R6 → R7a.
- G-RR (2026-11-19, owner in chat) — Intent — BUG-2810: new callable `validate_replacement_receipt` RR1–RR8 (check here, write in the purchase order service, FU-2); limit, cost and ledger rows decided by Claude under the reviewer's delegation (2026-11-19), reasons in FU-2.
