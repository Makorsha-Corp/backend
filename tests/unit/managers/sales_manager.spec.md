# Spec — `app/managers/sales_manager.py`

> **Status:** APPROVED
> **Source commit:** e48a092
> **Revision 2026-11-17 (owner, OQ-48 from the sales return manager spec):** `reopen_for_return` R2 rewritten to the owner's answer (a return never reopens a completed order) → [BUG-2790]. Still APPROVED. Cards to revise: the `reopen_for_return` R2 card(s), now expected to fail.
> **Revision 2026-11-17 (owner refined OQ-48, `owner-questions.md` OQ-48 answer line).** While a return is open on a completed order the order shows **"return in progress"**: the invoice stays frozen and nothing on the order is editable. When the return is completed or cancelled the order shows "completed" again. The order is never reopened to open/editable. Shape chosen by Claude under the reviewer's delegation (2026-11-17): the state is **derived** (`has_open_return`), never stored; the stored completion is untouched, so freeze F2 keeps working unchanged. New shared section *Return-in-progress state* RP1–RP7 (after `reopen_for_return`); `reopen_for_return` R2 now points to it. [BUG-2790] row updated. Still APPROVED. Cards to revise (`sales_manager.cases.md`): SM-ROR-02 … SM-ROR-10 (rule text and citations; ROR-02 / 06 / 07 stay strict xfail; see the note under RP7), plus new cards for RP2–RP6 once the state's home (sales service / order response) is specified.

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### House-rule violations — applied automatically
> Overwrite an answer only if the house rule should NOT apply here.

- **HR-10** `complete_delivery` R2, R4, R5; `cancel_delivery` R2, R3; `create_delivery_with_items` R7; `fulfill_service_item` R4, R5; `mark_order_complete` R2–R8; `set_section_confirm` R3–R10; `set_approval` R2–R5 — every state-checked-then-changed transition in this module reads its row(s) without a lock: two concurrent "complete" requests can both deduct stock, a cancel can race a completion, two planned deliveries can together exceed a line's ordered quantity, two fulfil requests can both log the event, two completions/confirms/approvals can both proceed. Intended: the relevant row(s) read `FOR UPDATE` before the check; the loser sees the new state and gets the normal wrong-state error — one root cause recurring across the module. 🐞 BUG-720
**Answer:** bug — per HR-10 (house rule)
**Resolution:** logged as one bug (BUG-720, Pattern `hr-10-unlocked-state-transition`, same pattern as BUG-029) covering all seven methods; each method gets one new rule adding the `FOR UPDATE` lock. Rules: `complete_delivery` R2a (new), `cancel_delivery` R2a (new), `create_delivery_with_items` R7a (new), `fulfill_service_item` R3a (new), `mark_order_complete` R10 (new), `set_section_confirm` R11 (new), `set_approval` R7 (new).

### Precedent matches — confirmed

### P1. Creating an order with no line items returns a 500 error — 🐞 BUG-3219 (BUG-124 precedent)
**Background:** The manager rejects an empty item list with a plain Python `ValueError`. The sales service does not translate `ValueError` for order creation (it does for delivery planning, turning it into 400), and the app has no global `ValueError` handler, so it reaches the client as the generic 500.
**What happens today:** `POST /sales-orders/` with `items: []` answers 500 "internal server error" instead of a clear 4xx.
**Example:** A client posts a valid order header with `items: []`. Nothing is created (correct), but the user sees a generic server error rather than "Sales order must have at least one item".
**Rules affected:** `create_sales_order_with_items` R1
**Answer:** bug — per BUG-124 precedent: the rejection reaches the client as 400 with the message "Sales order must have at least one item" (raise an error the caller translates, e.g. the service maps this `ValueError` to 400 as `create_delivery` does), never 500 (precedent — confirmed: ok)
**Resolution:** the manager's rule is unchanged (it already raises `ValueError`); the fix is the caller translating it to 400, same shape as BUG-124. Logged as BUG-3219 (Pattern `wrong-error-type-uncaught`; re-cited 2026-11-22, BUG-124 is the attachment-allowlist bug and only the precedent). Rules: `create_sales_order_with_items` R1.

### P2. Order lines accept zero or negative quantities and negative prices — 🐞 BUG-362 (precedent)
**Background:** `SalesOrderItemInput.quantity_ordered` and `unit_price` are plain `Decimal`s with no range. The endpoint computes `line_total = quantity × price` and sums them into the order total. The only quantity check is the product's minimum order quantity, and only when the catalog product has one.
**What happens today:** A line with `quantity_ordered: 0`, `-5`, or `unit_price: -100` is stored as typed; the order total can be zero or negative.
**Example:** A user creates an order with one free-text line "Discount", quantity `-1`, price `500`. The order is stored with `total_amount = -500`, and the draft invoice later copies the negative line.
**Rules affected:** `create_sales_order_with_items` R13
**Answer:** bug — per BUG-362 precedent: `SalesOrderItemInput` rejects `quantity_ordered <= 0` and `unit_price < 0` with 422 before anything is stored (fix in `app/schemas/sales_order_item.py`) (precedent — confirmed: ok)
**Resolution:** logged against existing BUG-362 (Pattern `unvalidated-numeric-range`); fix belongs in `app/schemas/sales_order_item.py`, not this manager. Rules: `create_sales_order_with_items` R13.

### P3. Delivery lines accept zero or negative quantities — 🐞 BUG-362 (precedent)
**Background:** `SalesDeliveryItemInput.quantity_delivered` has no range. The planning check only rejects a quantity *larger* than what is still available. Completing a delivery adds each line's quantity to the order line's `quantity_delivered`; catalog lines also deduct stock, which rejects quantities ≤ 0 with a `ValueError` (500).
**What happens today:** A planned quantity of `0` or `-3` is accepted. On completion, a free-text line's delivered quantity goes *down* by 3; a catalog line fails with 500 "Sale deduction quantity must be positive", so that delivery can never be completed.
**Example:** A fully delivered free-text line (ordered 5, delivered 5). A user plans a delivery with `-3` for it and completes it: the line now shows delivered 2, and the order is no longer "fully delivered".
**Rules affected:** `create_delivery_with_items` R13
**Answer:** bug — per BUG-362 precedent: `SalesDeliveryItemInput` rejects `quantity_delivered <= 0` with 422 before anything is stored (fix in `app/schemas/sales_delivery_item.py`) (precedent — confirmed: ok)
**Resolution:** logged against existing BUG-362 (Pattern `unvalidated-numeric-range`); fix belongs in `app/schemas/sales_delivery_item.py`. Rules: `create_delivery_with_items` R13.

### P4. Quantities and prices with more than 2 decimals are silently rounded — 🐞 BUG-021 (precedent)
**Background:** Quantity, price and line-total columns hold exactly 2 decimals; Postgres rounds anything longer when storing. The endpoint computes `line_total` from the unrounded values before storage.
**What happens today:** `quantity_ordered: 1.005`, `unit_price: 10` → stored quantity `1.01`, stored line total `10.05` (from 10.05), so quantity × price no longer equals the line total. Values ≥ 10^13 fail at flush with a database error.
**Example:** A line of 1.005 kg at 10 BDT is shown as 1.01 kg with a line total of 10.05 BDT; the invoice copied from it disagrees with itself by 0.05.
**Rules affected:** `create_sales_order_with_items` R13, `create_delivery_with_items` R13
**Answer:** bug — per BUG-021 precedent: `SalesOrderItemInput` (quantity, price) and `SalesDeliveryItemInput` (quantity) reject values with more than 2 decimal places or more than 13 integer digits with 422 (precedent — confirmed: ok)
**Resolution:** logged against existing BUG-021 (Pattern `unbounded-decimal-input`). Rules: `create_sales_order_with_items` R13, `create_delivery_with_items` R13.

### P5. Approving twice (or withdrawing when not approved) re-stamps and logs again — 🐞 BUG-009 (precedent)
**Background:** Each approver row has `approved` and `approved_at`. Every call writes both and logs an event, whether or not anything changes.
**What happens today:** An approver who already approved and clicks "Approve" again gets a new `approved_at` and a second `approved` event; withdrawing when not approved logs an `approval_withdrawn` event although nothing changed.
**Example:** Alice approved on 1 March. On 5 March she re-sends the approve request: her approval now shows "approved 5 March" and the activity log shows two "Approved order" entries.
**Rules affected:** `set_approval` R6
**Answer:** bug — per BUG-009 precedent: when the requested state equals the current one, nothing is written — `approved_at` keeps its value and no event is logged; the approver row is returned unchanged (precedent — confirmed: ok)
**Resolution:** logged against existing BUG-009 (Pattern `audit-stamp-on-noop`). Rules: `set_approval` R6.

### P6. A negative required-approvals number makes approval automatically satisfied — 🐞 BUG-362 (precedent)
**Background:** `required_approvals` is set through `PUT /sales-orders/{id}` (`SalesOrderUpdate`, plain `int | None`, no range). `approval_summary` uses it as-is: approval is met when approved count ≥ required.
**What happens today:** `required_approvals: -1` (or `0`) is stored, and approval counts as met with nobody having approved, so the invoice can be finalized without any approval.
**Example:** An order has 3 approvers, none approved. Someone sets `required_approvals = -1`. The approvers panel shows "0 of -1 — met" and "Finalize invoice" succeeds.
**Rules affected:** `approval_summary` R3
**Answer:** bug — per BUG-362 precedent: `SalesOrderUpdate.required_approvals` must be null or ≥ 1; anything else is rejected with 422 (fix in `app/schemas/sales_order.py`) (precedent — confirmed: ok)
**Resolution:** logged against existing BUG-362 (Pattern `unvalidated-numeric-range`); fix belongs in `app/schemas/sales_order.py`. Rules: `approval_summary` R2 (unchanged, ✅), R3.

### New questions

### Q1. A delivery that is already delivered or cancelled can be completed again — 🐞 BUG-721
**Background:** Deliveries have a status: `planned`, `delivered` or `cancelled`. Cancel and edit both refuse anything not `planned`. Completing a delivery adds its quantities to the order lines and deducts sellable stock.
**What happens today:** Completion does not look at the status. A `delivered` delivery can be completed again, adding the quantities a second time and deducting stock twice; a `cancelled` delivery can be completed and deducts stock although its quantity was freed for re-planning.
**Example:** DEL-2026-004 ships 10 units of item "Bolt M10" and is completed. A double-click sends the complete request again: the order line now shows 20 delivered of 10 ordered and the warehouse stock drops by another 10.
**Rules affected:** `complete_delivery` R2
**Answer:** bug — only a 'planned' delivery can be completed; otherwise ValueError "Only planned deliveries can be completed (this delivery is '<status>')" (400), nothing changed (reviewer accepted suggestion)
**Resolution:** only a `planned` delivery can be completed; otherwise `ValueError("Only planned deliveries can be completed (this delivery is '<status>')")` (400 at the API), nothing changed. Pattern `unchecked-status-before-transition`. Rules: `complete_delivery` R2.

### Q2. A delivery can be created directly in any status — 🐞 BUG-722
**Background:** The create-delivery body (`SalesDeliveryCreate`) contains `delivery_status` with default `"planned"`, and the value is stored as sent. Only `planned` deliveries count against the "available to plan" capacity.
**What happens today:** A client can create a delivery as `delivered`, `cancelled` or any made-up text (e.g. `"shipped"`). Such a delivery does not reserve capacity, and (see Q1) can still be completed, moving stock.
**Example:** A client posts a delivery of 8 units with `delivery_status: "draft"`. It is created, the line still shows 8 units available to plan, and another delivery of 8 can be planned on top.
**Rules affected:** `create_delivery_with_items` R4
**Answer:** bug — a new delivery always starts as 'planned'; delivery_status removed from (or ignored in) the create schema (reviewer accepted suggestion)
**Resolution:** a new delivery always starts as `planned`; `delivery_status` is removed from the create schema (or ignored). Pattern `client-controlled-status-on-create`. Rules: `create_delivery_with_items` R4.

### Q3. A delivery can include lines from a different sales order — 🐞 BUG-723
**Background:** A delivery belongs to one sales order. Each requested line is looked up only by its id within the workspace.
**What happens today:** A line id belonging to another sales order of the same workspace is accepted. Completing the delivery increases that other order's delivered quantity and deducts stock at *this* order's factory, booked to *this* order's customer.
**Example:** Delivery for SO-2026-010 (Factory A, customer X) includes line 77, which is on SO-2026-012 (Factory B, customer Y). On completion, SO-2026-012 shows the goods delivered, while stock leaves Factory A with a ledger entry naming customer X.
**Rules affected:** `create_delivery_with_items` R5
**Answer:** bug — a line not belonging to the delivery's sales order is rejected with ValueError (400), nothing written (reviewer accepted suggestion)
**Resolution:** a line that does not belong to the delivery's sales order is rejected with `ValueError("Sales order item <id> does not belong to sales order <order id>")` (400), nothing written. Pattern `missing-cross-entity-ownership-check`. Rules: `create_delivery_with_items` R5.

### Q4. Listing the same order line twice in one delivery bypasses the capacity check — 🐞 BUG-724
**Background:** Each delivery line is checked against "available to plan" = ordered − delivered − refunded − already planned. The already-planned amount is read from the order line's list of delivery lines, which is loaded once and is not refreshed as new lines of the same request are created.
**What happens today:** Two entries for the same order line are each checked against the capacity as it was before the request, so together they can exceed it.
**Example:** Line "Bolt M10" ordered 10, nothing planned. One delivery request has two entries for that line, 6 and 6. Both pass; 12 units are planned and, once completed, 12 are deducted from stock for an order of 10.
**Rules affected:** `create_delivery_with_items` R8
**Answer:** bug — an order line may appear only once per delivery; a repeat is rejected with ValueError (400), nothing written (reviewer accepted suggestion)
**Resolution:** the same order line may appear only once per delivery; a repeat is rejected with `ValueError` (400), nothing written. Pattern `same-request-duplicates-bypass-check`. Rules: `create_delivery_with_items` R8.

### Q5. A fractional quantity can be planned for a stock item that can only ship whole units — 🐞 BUG-725
**Background:** Order and delivery quantities have 2 decimals, but sellable stock is kept in whole units; completing a delivery of a catalog line with a fractional quantity fails with 400 "Delivery line has a fractional quantity; stock requires whole units". Planned deliveries cannot have their quantities edited.
**What happens today:** Planning 2.5 units of a catalog line succeeds; the delivery can then never be completed and must be cancelled and re-planned.
**Example:** A user plans 2.5 boxes of "Paint 5L". On delivery day, "Mark delivered" always fails with the fractional-quantity error.
**Rules affected:** `create_delivery_with_items` R13
**Answer:** bug — planning rejects fractional quantities on catalog lines with the same 400 message; free-text lines may stay fractional (reviewer accepted suggestion)
**Resolution:** planning rejects a fractional quantity on a catalog (`item_id` set) line with the same 400 message, before anything is written; free-text lines may stay fractional. Pattern `late-validation-blocks-completion`. Rules: `create_delivery_with_items` R13.

### Q6. Order and delivery numbers collide across workspaces — 🐞 BUG-726
**Background:** Order numbers are `SO-<year>-<n>` and delivery numbers `DEL-<year>-<n>`, where `n` is one more than the number of this workspace's orders (deliveries) of that year. The database requires each number to be unique across **all** workspaces.
**What happens today:** Workspace B's first order of 2026 is numbered `SO-2026-001`; if workspace A already has `SO-2026-001`, the insert violates the unique index and the create fails (409 "may already exist"). The same happens for deliveries. In practice only the workspace that got there first can create orders/deliveries until the counts diverge.
**Example:** Workspace A has 3 orders in 2026. Workspace B (0 orders) creates its first order: it gets `SO-2026-001`, which A already uses → the user sees a conflict error. Every retry computes `SO-2026-001` again (B's count stays 0), so workspace B can never create an order this year.
**Rules affected:** `create_sales_order_with_items` R5, `create_delivery_with_items` R4
**Answer:** bug — numbers unique per workspace (unique on (workspace_id, number) instead of global); every workspace starts at -001 (reviewer accepted suggestion)
**Resolution:** numbers are unique per workspace (unique index on `(workspace_id, sales_order_number)` / `(workspace_id, delivery_number)` instead of the global one); every workspace starts at `-001`. Pattern `unscoped-uniqueness-constraint`. Rules: `create_sales_order_with_items` R5, `create_delivery_with_items` R4.

### Q7. Two orders (or deliveries) created at the same moment get the same number — 🐞 BUG-727
**Background:** The next number is computed by counting existing rows, with no lock or sequence.
**What happens today:** Two creates in the same workspace at the same time both count N rows and both use `N+1`; the second fails on the unique index (409) although the user did nothing wrong.
**Example:** Two sales reps save new orders at the same second; one of them gets "A database constraint was violated" and must retry.
**Rules affected:** `create_sales_order_with_items` R5, `create_delivery_with_items` R4
**Answer:** bug — race-free numbering (per-workspace/year counter row read FOR UPDATE, or retry on unique violation); both creates succeed with distinct numbers (reviewer accepted suggestion)
**Resolution:** number generation is race-free (e.g. a per-workspace, per-year counter row read `FOR UPDATE`, or a retry on unique violation); concurrent creates both succeed with distinct numbers. Pattern `count-then-insert-race`; not merged with BUG-720 (HR-10) because the harmed resource is a number sequence, not a checked-then-changed row. Rules: `create_sales_order_with_items` R5, `create_delivery_with_items` R4.

### Q8. An order can reference another workspace's customer, factory or catalog items — 🐞 BUG-728
**Background:** Every workspace has its own customers (accounts), factories and catalog items; accounts and factories can be soft-deleted. The order's customer and factory names and each line's item name/unit are shown back in order responses and copied into the invoice.
**What happens today:** `account_id`, `factory_id` and line `item_id`s are stored as sent; only "does the row exist at all" is enforced by the database. Ids from another workspace, and soft-deleted customers/factories, are accepted.
**Example:** A user in workspace B creates an order with `account_id` = a customer of workspace A and a line with an item of workspace A. The order (and its draft invoice) shows workspace A's customer name and item name to workspace B.
**Rules affected:** `create_sales_order_with_items` R12
**Answer:** bug — customer, factory and each catalog item must be live and in the caller's workspace; otherwise 404 before anything is written (reviewer accepted suggestion)
**Resolution:** customer, factory and every catalog item must be live and belong to the caller's workspace; otherwise the create is rejected (404 "… not found") before anything is written. Pattern `missing-workspace-scope` (same root cause as BUG-035, different module — new ID). Rules: `create_sales_order_with_items` R12.

### Q9. The customer does not have to be tagged as a client — 🐞 BUG-729
**Background:** The model documents the customer as "must have 'client' tag". Accounts are typed by tags (client, supplier, vendor…). Nothing in the backend checks the tag.
**What happens today:** Any account, e.g. a supplier-only account, can be the customer of a sales order.
**Example:** A user picks "Steel Supplier Ltd" (tag: supplier) as the customer; the order and its receivable invoice are created normally.
**Rules affected:** `create_sales_order_with_items` R12
**Answer:** bug — reject accounts without the 'client' tag with 400 "Selected account is not a client" (reviewer accepted suggestion)
**Resolution:** creating a sales order with an account that lacks the `client` tag is rejected with 400 "Selected account is not a client". Pattern `docstring-constraint-not-enforced`. Rules: `create_sales_order_with_items` R12.

### Q10. A delivery method from another workspace (or deleted) is accepted — 🐞 BUG-730
**Background:** Delivery methods belong to a workspace and can be soft-deleted. Creating a delivery requires a `delivery_method_id`; editing may change it.
**What happens today:** The id is stored as sent on create and edit, with no workspace or deleted check.
**Example:** A planned delivery is edited to `delivery_method_id` = a method of another workspace; the delivery now shows that workspace's method name.
**Rules affected:** `create_delivery_with_items` R13, `update_delivery` R7
**Answer:** bug — delivery method must be live and in the caller's workspace; otherwise ValueError "Delivery method <id> not found" (400) (reviewer accepted suggestion)
**Resolution:** the delivery method must be live and in the caller's workspace; otherwise `ValueError("Delivery method <id> not found")` (400), nothing written. Pattern `missing-workspace-scope` (same pattern as Q8/BUG-728; separate ID — different entity and methods). Rules: `create_delivery_with_items` R13, `update_delivery` R7.

### Q11. "Fully delivered" ignores refunded quantities, unlike order completion — 🐞 BUG-731
**Background:** A refund-type return reduces a line's delivered quantity and raises its refunded quantity; the module's completion checks count refunded quantity as satisfying the order. The order's `is_fully_delivered` flag (shown in the UI and in the "now fully delivered" message) is recomputed separately after each delivery/fulfilment.
**What happens today:** The flag requires delivered ≥ ordered on every line and ignores refunded quantity, so after a refund an order can be "complete-able" but never "fully delivered".
**Example:** Line ordered 10, delivered 10, then a refund return of 2 → delivered 8, refunded 2. Another line is then delivered; the recompute sets `is_fully_delivered = False` (8 < 10), while "Mark complete" succeeds.
**Rules affected:** `_recompute_is_fully_delivered` R1
**Answer:** bug — a line counts as done when delivered + refunded >= ordered, same as the completion helpers (reviewer accepted suggestion)
**Resolution:** a line counts as done when delivered + refunded ≥ ordered, the same rule as `all_deliverable_items_delivered` / `all_fulfilment_items_fulfilled`. Bundled with Q12 as one bug (BUG-731, Pattern `refunded-quantity-ignored`) — both are the same root cause (refunded quantity dropped from a "is this line done" check) recurring in two methods. Rules: `_recompute_is_fully_delivered` R1.

### Q12. Re-fulfilling a service line after a refund over-fulfils it — 🐞 BUG-731
**Background:** A line that does not need delivery is fulfilled in one click, setting delivered = ordered. After a refund return on that line, delivered goes down and refunded goes up.
**What happens today:** Fulfilling again sets delivered back to the full ordered quantity, ignoring the refunded part.
**Example:** "Installation" ordered 5, fulfilled 5, then refunded 2 (delivered 3, refunded 2). Clicking "Fulfil" sets delivered to 5; the line now counts 7 units (5 delivered + 2 refunded) against 5 ordered, and a new `item_fulfilled` event is logged.
**Rules affected:** `fulfill_service_item` R7
**Answer:** bug — fulfil sets delivered to ordered − refunded; no-op (no change, no event) when delivered + refunded >= ordered (reviewer accepted suggestion)
**Resolution:** fulfilling sets delivered to ordered − refunded; when delivered + refunded ≥ ordered it is a no-op (no change, no event). Bundled with Q11 under BUG-731 (Pattern `refunded-quantity-ignored`). Rules: `fulfill_service_item` R4, R6, R7.

### Q13. Editing a planned delivery cannot clear a field — 🐞 BUG-732
**Background:** The edit form sends scheduled date, delivery method, tracking number and notes. Fields sent as `null` are dropped before saving.
**What happens today:** A tracking number, notes or scheduled date, once set, can only be replaced, never removed.
**Example:** A user typed a wrong tracking number, then clears the field and saves. The response still shows the old tracking number and no `delivery_updated` event is logged.
**Rules affected:** `update_delivery` R3
**Answer:** bug — explicit null clears scheduled_date/tracking_number/notes; null delivery_method_id rejected with 422; omitted fields unchanged (reviewer accepted suggestion)
**Resolution:** a field explicitly sent as `null` clears it (`scheduled_date`, `tracking_number`, `notes`); `delivery_method_id` stays required and a `null` for it is rejected with 422 (fix in `SalesDeliveryEditRequest`); omitted fields stay unchanged. Pattern `exclude-none-blocks-clearing`. Rules: `update_delivery` R3, R6.

### Q14. Delivery changes never record who made them — 🐞 BUG-733
**Background:** Deliveries have `updated_by` ("last changed by"). HR-9 says it is written when a field actually changes.
**What happens today:** Editing, cancelling and completing a delivery never set `updated_by`; it stays empty (only `updated_at` moves).
**Example:** Bob cancels DEL-2026-007. The delivery shows "updated at 14:02" but "updated by —".
**Rules affected:** `complete_delivery` R3, `cancel_delivery` R3, `update_delivery` R3
**Answer:** bug — updated_by set to the acting user whenever edit/cancel/complete changes a field (HR-9) (reviewer accepted suggestion)
**Resolution:** `updated_by` is set to the acting user whenever edit/cancel/complete changes at least one field (HR-9); unchanged edits (a no-op `update_delivery`, per R5) leave it alone. Pattern `hr-9-stamp-never-written` (opposite direction of BUG-009, which over-stamps; no existing pattern covers "never stamped", so a new one is used). Intended column cites HR-9. Rules: `complete_delivery` R3, `cancel_delivery` R3, `update_delivery` R3.

### Q15. A blank completion code is handled differently by deliveries and fulfilment — 🐞 BUG-734
**Background:** Both "mark delivered" and "fulfil line" accept an optional completion code (e.g. a customer's confirmation code).
**What happens today:** Completing a delivery with `""` stores `""` on the delivery; fulfilling a line with `""` stores nothing. `"   "` is stored as typed by both and shown as "(code:    )" in the activity log.
**Example:** A user leaves the code box with a space: the delivery's activity entry reads "Delivery DEL-2026-003 marked delivered on 2026-09-29 (code:  )".
**Rules affected:** `complete_delivery` R3, R9; `fulfill_service_item` R4, R5
**Answer:** bug — code trimmed; empty after trim = no code (null, not shown) in both places (reviewer accepted suggestion)
**Resolution:** the code is trimmed; empty after trimming means "no code" (stored as null, not shown in the description) in both places. Pattern `untrimmed-optional-free-text`. Rules: `complete_delivery` R3, R9; `fulfill_service_item` R4, R5.

### Q16. Stock ledger notes show the order number as "SO-SO-2026-…" — 🐞 BUG-735
**Background:** Order numbers already start with `SO-`. The stock ledger entry written on delivery completion adds another `SO-` prefix.
**What happens today:** The note reads "Delivery DEL-2026-001 for SO-SO-2026-001".
**Example:** The product ledger for "Bolt M10" lists a sale with note "Delivery DEL-2026-004 for SO-SO-2026-010".
**Rules affected:** `complete_delivery` R5
**Answer:** bug — note reads "Delivery DEL-2026-004 for SO-2026-010" (reviewer accepted suggestion)
**Resolution:** note reads "Delivery DEL-2026-004 for SO-2026-010" (order number used as stored, no extra prefix). Pattern `duplicated-prefix-in-formatted-string`. Rules: `complete_delivery` R5.

### Q17. Two "confirm order info" checks can never fail — 🗑️ removed
**Background:** Customer (`account_id`) and order date are mandatory database columns, so a saved order always has both.
**What happens today:** Confirming order info checks "customer missing" (400 "Select a customer before confirming") and "order date missing" (400 "Set the order date before confirming"); neither can ever trigger. Only the contact-name check is live.
**Example:** No request can produce either message.
**Rules affected:** `set_section_confirm` R4
**Answer:** remove (reviewer accepted suggestion)
**Resolution:** the two unreachable checks (`app/managers/sales_manager.py:582-583` and `:584-585`) are dropped from `set_section_confirm` R4; logged to `tests/unit/managers/sales_manager.deadcode-staging.md`, not a bug (no BUG ID). `set_section_confirm` R4 keeps only the live contact-name check. The two dead error rows are removed from the Errors table.

### Q18. An order with no approvers counts as approved — 🐞 BUG-736
**Background:** The creator is added as the first approver, but any approver can be removed. With "required approvals" left empty, the order needs all assigned approvers; approval gates invoice finalization.
**What happens today:** With zero approvers and no required number, approval is "met" (0 of 0).
**Example:** A user removes the only approver (themselves) and immediately finalizes the invoice, with no approval by anyone.
**Rules affected:** `approval_summary` R3
**Answer:** bug — at least one approval is always required; with no approvers assigned approval is not met (reviewer accepted suggestion)
**Resolution:** at least one approval is always required: with no approvers assigned, approval is not met (`required = max(1, …)`). Pattern `vacuous-truth-on-empty-set`. Rules: `approval_summary` R3.

### Q19. Approvers can be added or removed after the invoice is finalized or the order is complete — 🐞 BUG-737
**Background:** Withdrawing an approval is blocked once the order is complete or its invoice is confirmed.
**What happens today:** Adding and removing approvers is never blocked, so the approval record of a finalized/completed order can still be changed (e.g. removing someone who approved).
**Example:** After finalization, a user removes Alice (who approved); the approvers panel now shows 0 approvals for an order whose invoice was confirmed on the basis of Alice's approval.
**Rules affected:** `add_approver` R6, `remove_approver` R4
**Answer:** bug — add/remove approver rejected with 400 when the order is complete or financially locked, same checks as withdrawing (reviewer accepted suggestion)
**Resolution:** add/remove approver is rejected with 400 when the order is complete ("Cannot change approvers — order is complete") or financially locked ("Cannot change approvers — invoice is locked"), same checks as withdrawing. Pattern `inconsistent-sibling-guard`. Rules: `add_approver` R6, `remove_approver` R4.

### Q20. `approvals_met` is never used — 🗑️ removed
**Background:** The sales flow calls `approval_summary` directly; nothing in the app calls `SalesManager.approvals_met`.
**What happens today:** The method exists but is unreachable.
**Example:** —
**Rules affected:** `approvals_met` R1
**Answer:** remove (reviewer accepted suggestion)
**Resolution:** moved to **Not specified** as dead code (`app/managers/sales_manager.py:769-770`); logged to `tests/unit/managers/sales_manager.deadcode-staging.md`, not a bug. No legacy test (in or outside `tests/unit/`) calls `SalesManager.approvals_met` — the `approvals_met` references in `tests/test_work_order_complete*.py` are for the unrelated `WorkOrderManager.approvals_met`.

## Overview
`SalesManager` owns the sales-order aggregate: the order, its lines, deliveries and delivery lines, approvers and the activity-event log. It creates orders and deliveries, completes deliveries (moving sellable stock through `ProductManager`) and fulfils non-delivery lines directly, runs the section-confirm / approval workflow, marks orders complete or reopens them for returns, and keeps the denormalised `paid` flag in step with the linked invoice. Callers are `SalesService` (all endpoints under `/sales-orders/` and `/sales-deliveries/`), `InvoicePaymentManager` (`sync_so_for_linked_invoice`) and `AttachmentManager` (`log_event`). It never commits; every write is flushed only.

Invariants it is meant to protect: an order has at least one line; delivery/fulfilment needs a finalized invoice; planned quantity never exceeds what is left to deliver; stock moves only when a delivery is completed; completion needs a finalized invoice, all lines done and no open return.

**Callables:** 27 specified · 2 not specified
**Externals to mock:** none of the listed externals. Time is read directly: `datetime.now()` (delivery date default, in this module) and `datetime.utcnow()` (`completed_at`, `approved_at`, in this module), plus `datetime.now().year` inside `app/dao/sales_order.py` / `app/dao/sales_delivery.py` for numbering, and `datetime.utcnow` model defaults (`assigned_at`, event `created_at`). Patch `app.managers.sales_manager.datetime` (and the DAO modules' `datetime`) or assert time ranges.
**Integration-only behavior:** the race-freedom half of BUG-727 (`create_sales_order_with_items` R5, `create_delivery_with_items` R4) — two concurrent creates in one workspace both getting distinct numbers can only be shown with two separate DB connections/transactions, which the per-test rolled-back session cannot provide; the generation mechanism (counter row read `FOR UPDATE`, transaction-scoped advisory lock, or retry on unique violation) is left to the implementer and is not asserted at unit level (best-practice default, delegated by reviewer). Single-session numbering (format, per-workspace count, per-workspace uniqueness / BUG-726) stays unit-tested.

**Notes for the test designer:**
- Numbers are unique across all workspaces in the DB today — that is itself BUG-726; until it is fixed, creating orders/deliveries in two workspaces in the same test hits the global unique index.
- `SalesOrderCreate.current_status_id` defaults to `10` and is a NOT NULL FK to `statuses`: a `statuses` row with id 10 must exist, or pass an existing id.
- Orders need real `accounts`, `factories`, `profiles` rows (FKs); catalog lines need `items`; stock deduction needs a live `products` row (factory, item, `is_available_for_sale=True`) with enough whole-unit `qty`.
- Errors come in two families: `ValueError` (delivery/fulfil methods and `create_sales_order_with_items` R1) and `fastapi.HTTPException` (section confirm, completion, approvers, events, order-catalog checks, stock checks). Pydantic `ValidationError` is a `ValueError` subclass.
- `create_delivery_with_items` R8 depends on the order line's `delivery_items` collection being loaded before and not refreshed after new lines are flushed (normal session behavior; do not expire the session between entries).
- BUG-720 (HR-10) rules (`complete_delivery` R2a, `cancel_delivery` R2a, `create_delivery_with_items` R7a, `fulfill_service_item` R3a, `mark_order_complete` R10, `set_section_confirm` R11, `set_approval` R7) describe locking that the code does not have yet; today's tests for the underlying state checks pass without a lock, so the lock itself is untestable at the unit level until implemented — these rules are `xfail(strict=True, reason="BUG-720")`, same as any other tagged rule.
- **Table / column map (G1):**
  - Invoices: table `account_invoices` (model `AccountInvoice`). Required columns: `workspace_id`, `account_id`, `invoice_type` (`'receivable'` for sales), `invoice_amount`, `invoice_date`. `invoice_status` defaults `'draft'`; the only values the application ever writes are `'draft'`, `'confirmed'`, `'voided'` (`AccountInvoiceManager` confirm/unconfirm/void; G18). `'locked'` is never written by any code path — `is_so_financially_locked` R3 still lists it, but it is a dead value: do not design a `'locked'` case (best-practice default, delegated by reviewer). The column is a plain `String(20)` with no check constraint; `payment_status` defaults `'unpaid'` (`'unpaid'`, `'partial'`, `'paid'`, `'overdue'`). Linked to an order via `sales_orders.invoice_id`.
  - Returns: table `sales_order_returns` (model `SalesOrderReturn`): `workspace_id`, `sales_order_id`, `return_number` (NOT NULL, globally unique), `status` (default `'pending'`; also `'completed'`, `'voided'`), `created_by` (NOT NULL). Return lines: `sales_order_return_items` (`return_id`, `so_item_id`, `quantity_returned`).
  - Product ledger: table `product_ledger` (model `ProductLedger`): `workspace_id`, `factory_id`, `item_id`, `transaction_type`, `quantity` (Integer), `unit_cost`, `total_cost`, `qty_before`, `qty_after`, `avg_cost_before`, `avg_cost_after`, `source_type`, `source_id`, `transfer_source_type`/`_id`, `transfer_destination_type`/`_id`, `notes`, `performed_by`, `performed_at` (server default now()).
  - Product stock: table `products` (model `Product`): `qty` (Integer, whole units), `avg_cost` (Numeric 15,2 — the "average cost"), `min_order_qty`, `is_available_for_sale`, `is_deleted`, `updated_by`.
  - Account tags: `account_tags` (`workspace_id`, `name`, `tag_code` — `'client'` / `'supplier'`, `is_active`) joined to accounts through `account_tag_assignments` (`workspace_id`, `account_id`, `tag_id`). "Has the `client` tag" (BUG-729) = an assignment to an active tag of the same workspace with `tag_code = 'client'` (best-practice default, delegated by reviewer).
  - Workspace membership: `workspace_members` (`workspace_id`, `user_id` → `profiles.id`, `role` NOT NULL, `position` nullable, `status` default `'active'`; also `'suspended'`, `'invited'`).
  - Delivery completion code: `sales_deliveries.completion_code` (String 100). Fulfilment code: `sales_order_items.fulfillment_completion_code` (String 100).
  - "Live" (BUG-728, BUG-730) means: accounts, factories, delivery methods `is_deleted = False`; items (no soft-delete column) `is_active = True` (best-practice default, delegated by reviewer).
- **Decimal rendering in messages (G6):** `quantity_available_to_plan` and `quantity_planned` are computed as `Decimal(str(<attribute>))`, so they render with the scale of the attribute value in memory: a line re-read from the DB renders `6.00`; a line created in the same session and not refreshed renders the value as it was assigned (e.g. `6` from `Decimal("10") - Decimal("4")`). The zero floor of available is `Decimal(0)` and renders `0`; `planned` with no planned lines renders `0`. The requested quantity renders exactly as passed in the request dict. In `complete_delivery` R7 the stock-error `requested`/`available` are whole integers (`requested 4, available 2`). Use 2-decimal setup values (or `session.expire_all()` before the call) to make rendering deterministic.
- **Profile fallbacks are unreachable (G8):** `sales_order_approvers.user_id` and `workspace_members.user_id` are NOT NULL FKs to `profiles.id` with `ON DELETE CASCADE`, so an approver or member row can never point to a missing profile; deleting the profile deletes the approver/member row too. The `User #<id>` name fallback (`add_approver` R5, `remove_approver` R3) and the `None` profile (`list_approvers` R4) cannot be set up through the database — do not design cases for them (the two fallback branches are logged as dead code in `sales_manager.deadcode-staging.md`).
- **`quantity_refunded` is never `None` on a persisted order line (G17):** `sales_order_items.quantity_refunded` is `NOT NULL` with default/server default `0`, so a line stored in the database cannot hold `None` (setting it raises `NotNullViolation` at flush). The "`quantity_refunded` of `None` counts as 0" clause is reachable only through the pure helpers `all_deliverable_items_delivered` R2 and `all_fulfilment_items_fulfilled` R1, which take in-memory objects; for the DB-backed `create_delivery_with_items` R7, `fulfill_service_item` R4 and `_recompute_is_fully_delivered` R1 the clause is unreachable — do not design `None`-refunded cases for them (same treatment as the G8 profile fallbacks).
- **Line processing order (G12):** `complete_delivery` reads the delivery's lines with no `ORDER BY` — processing order is unspecified (in practice insertion order, not guaranteed). Mid-way error cases should use one failing line, or assert only order-independent state.

## Not specified
- `SalesManager.__init__` — wires DAOs, no logic
- `SalesManager.approvals_met` — dead code, to be removed (reviewer; Q20, no bug ID — see `tests/unit/managers/sales_manager.deadcode-staging.md`)

---

## `all_deliverable_items_delivered(items)`
**Shape:** compute
**Persistence:** pure
**Visibility:** internal (used by: `mark_order_complete`)

**Purpose:** Says whether every line that needs physical delivery has been delivered (or refunded) in full.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| items | list[SalesOrderItem] | any lines; none required |

**Returns:** `bool`

**Rules:**
- **R1.** Only lines with `requires_delivery = True` are considered; other lines never affect the result.
- **R2.** Returns `True` when every considered line has `quantity_delivered + quantity_refunded >= quantity_ordered` (exactly equal counts; more than ordered also counts). A `quantity_refunded` of `None` counts as 0.
- **R3.** Returns `False` when any considered line is short (e.g. ordered 10, delivered 7, refunded 2 → 9 < 10).
- **R4.** Returns `True` for an empty list and for a list with no delivery lines.

**Errors:** none
**Side effects:** none

---

## `all_fulfilment_items_fulfilled(items)`
**Shape:** compute
**Persistence:** pure
**Visibility:** internal (used by: `mark_order_complete`)

**Purpose:** Says whether every line that does not need delivery has been fulfilled (or refunded) in full.

**Inputs:** as `all_deliverable_items_delivered`.

**Returns:** `bool`

**Rules:**
- **R1.** Only lines with `requires_delivery = False` are considered; the done-test is the same as `all_deliverable_items_delivered` R2–R3 (delivered + refunded ≥ ordered, refunded `None` = 0).
- **R2.** Returns `True` for an empty list and for a list with no non-delivery lines.

**Errors:** none
**Side effects:** none

---

## `SalesManager.create_sales_order_with_items(session, order_data, items_data, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `SalesService.create_sales_order_from_dict` ← `POST /sales-orders/`)

**Purpose:** Create a sales order with its lines, make the creator its first approver and log the creation.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| order_data | dict | Validated as `SalesOrderCreate`: `account_id`, `factory_id`, `order_date` required; `expected_delivery_date`, `contact_name`, `contact_phone`, `description`, `total_amount` optional (default `None`); `current_status_id` default `10`. Unknown keys ignored. `factory_id` key must be present: it is read (for R3) before `order_data` is validated, so a missing `factory_id` key raises `KeyError('factory_id')` after R1/R2 and before anything is written. Validation of `order_data` itself happens before any row is written: an invalid `order_data` (e.g. missing `account_id`, bad `order_date`) raises pydantic `ValidationError` and leaves no order, approver, event or line. |
| items_data | list[dict] | Each dict validated as `SalesOrderItemCreate`: `item_id` or non-blank `description` required; `quantity_ordered`, `unit_price`, `line_total` required; `requires_delivery` default `True`; `notes` optional. No range checks today. The API itself validates the request lines as `SalesOrderItemInput` (`item_id`/`description`, `quantity_ordered`, `unit_price` required; `requires_delivery` default `True`; `notes` optional; no `line_total`) before calling the manager. |
| workspace_id | int | workspace of the new order |
| user_id | int | creator |

**Returns:** the new `SalesOrder`, flushed, not committed.

**Rules:**
- **R1.** [BUG-3219] An empty `items_data` (`[]` or `None`) raises `ValueError("Sales order must have at least one item")`; nothing is written; the caller (`SalesService`) translates this to `HTTPException` 400 with the same message. *(Today: the service does not translate this `ValueError` for order creation, so it reaches the API as a generic 500 — P1.)*
- **R2.** Two lines with the same catalog `item_id` → `HTTPException` 409 `"<item name> appears more than once on this order"` (name fallback `Item #<id>`); free-text lines (`item_id` null) never conflict. Nothing is written. Detail follows the `order_catalog_items` spec (`assert_unique_catalog_item_ids`). ✅
- **R2a.** [BUG-728] Once BUG-728 is fixed, the `Item #<id>` name fallback cannot be reached through this method: R12 runs first and rejects (404) any catalog line whose item is not a live item of this workspace, so every duplicate that reaches R2 resolves to a real item name. Order of checks for a duplicated foreign/unknown item: the R12 404 is raised, not the R2 409. Test the fallback only in the `order_catalog_items` spec, not here (best-practice default, delegated by reviewer). *(Today [BUG-728]: two lines with the same item id from another workspace reach R2 and get the 409 with `Item #<id>`.)*
- **R3.** A catalog line whose `quantity_ordered` is below the `min_order_qty` of the live sellable product for (this workspace, `factory_id`, `item_id`) → `HTTPException` 422 `"Minimum order quantity for <name> is <min> (requested <qty>)"`. No product, or a product with no/zero minimum → no check. Free-text lines are not checked. Detail follows the `order_catalog_items` spec. Nothing is written. Checks run in the order R1, R2, R3. ✅
- **R4.** The order is stored with the values from `order_data`, `workspace_id`, `created_by = user_id` and a new number (R5). `total_amount` is stored as given — it is **not** computed from the lines; `None` becomes `0`. Defaults: `required_approvals` null; `order_info_confirmed`, `items_confirmed`, `invoice_confirmed`, `order_completed`, `is_fully_delivered`, `is_invoiced`, `paid` all `False`; `invoice_id`, `completed_at`, `completed_by` null. ✅
- **R5.** [BUG-726, BUG-727] The number is `SO-<year>-<n>` with `<year>` the server's current local year and `<n>` = (number of orders **of this workspace** whose number starts with `SO-<year>-`) + 1, zero-padded to 3 digits (`SO-2026-001`, …, `SO-2026-1000`). Other workspaces' orders are not counted. The number must be unique **per workspace** (unique index on `(workspace_id, sales_order_number)`); a collision within the same workspace is prevented by race-free numbering (a per-workspace, per-year counter read `FOR UPDATE`, or a retry on unique violation), so two concurrent creates in the same workspace both succeed with distinct numbers. *(Today [BUG-726]: the unique index is global across all workspaces, not per-workspace, so a number already used by another workspace collides and the create fails at flush with `IntegrityError` even though nothing is wrong for this workspace. Today [BUG-727]: the count-then-insert is not locked or sequenced, so two concurrent creates in the same workspace can compute the same `<n>` and one fails at flush with `IntegrityError`.)*
- **R6.** The creator is added as an approver: `user_id = assigned_by = user_id`, `approved = False`, `approved_at` null, `assigned_at` = now (UTC). ✅
- **R7.** One event is logged: `event_type 'created'`, description `'Order created'`, `performed_by = user_id`, no metadata. ✅
- **R8.** One `SalesOrderItem` is created per entry, with `sales_order_id` and `workspace_id` set; `quantity_delivered`, `quantity_returned`, `quantity_refunded` = 0; `line_total` stored as given (not recomputed); `fulfillment_completion_code` null. ✅
- **R9.** The caller's line dicts are modified in place: each gains `sales_order_id` and `workspace_id` keys. ✅
- **R10.** A line that fails `SalesOrderItemCreate` validation (e.g. missing `line_total`, neither `item_id` nor non-blank `description`) raises pydantic `ValidationError` after the order, approver, event and earlier lines have been flushed; nothing is committed (the caller rolls back). ✅
- **R11.** Entries must be dicts: a non-dict entry passes R2/R3 (read via attribute) but then fails with `TypeError` when the ids are added. Only reachable by direct calls; the API always passes dicts. ✅
- **R12.** [BUG-728, BUG-729] `account_id` and `factory_id` must reference a live account/factory of this workspace, and every catalog line's `item_id` a live item of this workspace; otherwise `HTTPException` 404 with detail `"Account with ID <id> not found"`, `"Factory with ID <id> not found"` or `"Item with ID <id> not found"` (same wording as the rest of the codebase), nothing written. The account must also carry the `client` tag, otherwise `HTTPException` 400 `"Selected account is not a client"`, nothing written. These checks run after R1 and before R2, in the order: account exists/live → account is a client → factory → each catalog line's item in line order; the first failure is raised (best-practice default, delegated by reviewer). *(Today [BUG-728]: `account_id`, `factory_id` and line `item_id`s are not checked for workspace or soft-deletion; only existence is enforced by the DB, so an id from another workspace or a soft-deleted row is accepted, and a non-existent id raises `IntegrityError` at flush instead of a clean 404. Today [BUG-729]: the account's tags are never checked, so a non-client account — e.g. a supplier-only one — is accepted as the customer.)*
- **R13.** [BUG-021, BUG-362] Catalog and free-text line `quantity_ordered` must be `> 0` and `unit_price >= 0`, both with at most 2 decimal places and at most 13 integer digits; a violation is rejected with 422 before anything is stored (fix in `app/schemas/sales_order_item.py`). The constraints go on both the API input schema `SalesOrderItemInput` and the shared base `SalesOrderItemBase` (so `SalesOrderItemCreate`, which the manager validates, enforces them too) (best-practice default, delegated by reviewer); when the manager is called directly, a violation raises pydantic `ValidationError` before any row is written (all lines validated before the order is created). *(Today [BUG-362, P2]: quantities and prices have no range check — `0`, negative quantities and negative prices are stored as typed, and the order total can be zero or negative. Today [BUG-021, P4]: values with more than 2 decimals are silently rounded by the DB on storage — `1.005` stores as `1.01` — and values ≥ 10^13 fail at flush with a database error instead of a clean validation error.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| no lines | `ValueError` | `Sales order must have at least one item` (translated to `HTTPException` 400 by the caller — BUG-3219) |
| duplicate catalog item | `HTTPException` 409 | `<name> appears more than once on this order` |
| below minimum order qty | `HTTPException` 422 | `Minimum order quantity for <name> is <min> (requested <qty>)` |
| account/factory/item not found or not live in workspace [BUG-728] | `HTTPException` 404 | `Account with ID <id> not found` / `Factory with ID <id> not found` / `Item with ID <id> not found` |
| account missing `client` tag [BUG-729] | `HTTPException` 400 | `Selected account is not a client` |
| out-of-range quantity/price [BUG-362, BUG-021] | pydantic `ValidationError` (422) | schema message |
| invalid order/line data | pydantic `ValidationError` | pydantic message |
| number collision within workspace / bad FK | `IntegrityError` (at flush) — not expected once BUG-726/BUG-727 are fixed | DB message |

**Side effects:** inserts 1 `sales_orders`, 1 `sales_order_approvers`, 1 `sales_order_events`, N `sales_order_items` rows; mutates `items_data` dicts; flush only.

---

## `SalesManager.create_delivery_with_items(session, delivery_data, delivery_items_data, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `SalesService.create_delivery` ← `POST /sales-deliveries/`, which turns `ValueError` into 400 with the message)

**Purpose:** Plan a delivery of some quantities of an order's delivery lines, within what is still available to plan.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| delivery_data | dict | Validated as `SalesDeliveryCreate`: `sales_order_id`, `delivery_method_id` required; `scheduled_date`, `tracking_number`, `notes` optional; `delivery_status` default `'planned'`, any string accepted (today; removed by BUG-722). `sales_order_id` key must be present. |
| delivery_items_data | list[dict] | Each: `sales_order_item_id`, `quantity_delivered` (Decimal, no range), `notes` optional |
| workspace_id | int | |
| user_id | int | creator |

**Returns:** `(delivery, sales_order)` — the new `SalesDelivery` and its parent order; flushed, not committed.

**Rules:**
- **R1.** An empty `delivery_items_data` raises `ValueError("Delivery must have at least one item")`; nothing written. ✅
- **R2.** A `sales_order_id` not found in this workspace (non-existent or another workspace's) raises `ValueError("Sales order <id> not found")`; nothing written. ✅
- **R3.** An order whose `invoice_confirmed` is `False` raises `ValueError("Finalize the invoice before planning a delivery")`; nothing written. ✅
- **R4.** [BUG-722, BUG-726, BUG-727] The delivery is stored with the values from `delivery_data`, `workspace_id`, `created_by = user_id`, a new number (below) and `delivery_status = 'planned'` always — `delivery_status` is removed from `SalesDeliveryCreate`; a `delivery_status` key still sent in `delivery_data` is silently ignored (pydantic's default `extra='ignore'`), not rejected, and the delivery is stored as `planned` (best-practice default, delegated by reviewer). The number is `DEL-<year>-<n>`, computed like the order number (`create_sales_order_with_items` R5, counting this workspace's deliveries with prefix `DEL-<year>-`), unique **per workspace** (unique index on `(workspace_id, delivery_number)`), generated race-free. *(Today [BUG-722]: `delivery_status` is a client-supplied field on `SalesDeliveryCreate`, defaulting to `'planned'` but accepting any string, and is stored as sent — a delivery created as `'delivered'`/`'cancelled'`/anything else reserves no capacity (R7) and, per `complete_delivery` BUG-721, can still be completed. Today [BUG-726]: the number is unique across all workspaces, not per workspace. Today [BUG-727]: numbering is not race-free.)*
- **R5.** [BUG-723] Each line's `sales_order_item_id` is looked up in this workspace and must belong to **this delivery's sales order**; not found, another workspace's, or a different order of the same workspace → `ValueError`: `"Sales order item <id> not found"` (not in workspace) or `"Sales order item <id> does not belong to sales order <order id>"` (different order, same workspace). *(Today: a line belonging to a different order of the same workspace is silently accepted — completing the delivery then credits that other order and deducts stock at this order's factory, booked to this order's customer.)*
- **R6.** A line whose order line has `requires_delivery = False` → `ValueError("Sales order item <id> does not require delivery — it should be fulfilled directly, not delivered")`. ✅
- **R7.** Capacity: available = max(0, ordered − delivered − refunded − planned) (`refunded` is always a number on a stored line — NOT NULL, default 0; see Notes, G17), where planned = sum of the line's delivery-line quantities whose delivery has status exactly `planned` (delivered, cancelled or other statuses do not count). A requested quantity greater than available → `ValueError("Cannot plan <requested> unit(s) for sales order item <id> — only <available> unit(s) are available to plan (<planned> already committed to other planned deliveries). Edit or delete an existing planned delivery to free up capacity.")`. Exactly equal is allowed. ✅
- **R7a.** [BUG-720, HR-10] The requested order lines (`sales_order_items` rows) are read `FOR UPDATE` before this capacity check — the order lines, not the parent order (best-practice default, delegated by reviewer); a delivery planned concurrently for the same line is visible to the loser, which is rejected by the normal R7 capacity error instead of both succeeding. *(Today: the "available to plan" check reads the order lines without a lock, so two deliveries planned at the same moment for the same line can together exceed the ordered quantity.)*
- **R8.** [BUG-724] The same order line may appear only once per delivery request; a second entry for an order line already used earlier in this request is rejected with `ValueError("Sales order item <id> appears more than once in this delivery")` (400), nothing written (best-practice default, delegated by reviewer). *(Today: when one request lists the same order line more than once, every entry is checked against the capacity as it was before the request — entries of the same request do not reduce each other's capacity, so together they can exceed it.)*
- **R9.** Each accepted line creates a delivery line with `delivery_id`, `workspace_id`, `sales_order_item_id`, `item_id` copied from the order line (null for free-text lines), `quantity_delivered` and `notes` as sent. ✅
- **R10.** Lines are processed in the given order; an error from today's checks — R5's "not found" (not in this workspace), R6 and R7 — is raised after the delivery and earlier lines were flushed (nothing committed; the caller rolls back); no `delivery_planned` event is logged. ✅
- **R10a.** [BUG-723, BUG-724, BUG-725, BUG-730, BUG-362, BUG-021] The new checks — line belongs to a different order (R5), repeated line (R8), fractional catalog quantity, out-of-range quantity and delivery method (R13) — are all made for the whole request **before** the delivery row is created: on rejection no delivery row, no delivery lines and no event exist (best-practice default, delegated by reviewer). *(Today: these checks do not exist; such requests are accepted.)* A fix may also move the R5-not-found/R6/R7 checks ahead of the insert; that is allowed, so R10 tests should assert only the raised error, no event, and (for a later failing line) that the earlier line was flushed when the delivery exists.
- **R11.** One event on the order: `event_type 'delivery_planned'`, description `"Delivery <number> planned (<total> unit<s> across <count> item<s>)"` where `<total>` is the sum of requested quantities as Decimal text (`5`, `2.50`) and `unit`/`item` are singular only when the value equals 1; metadata `{"delivery_id": <id>, "tracking_number": <value or null>}`; `performed_by = user_id`. ✅
- **R12.** Order lines' quantities are not changed by planning. ✅
- **R13.** [BUG-021, BUG-362, BUG-725, BUG-730] `quantity_delivered` must be `> 0`, at most 2 decimal places, at most 13 integer digits (schema fix, `app/schemas/sales_delivery_item.py`, on both `SalesDeliveryItemInput` and the shared `SalesDeliveryItemBase` (best-practice default, delegated by reviewer)); a violation is pydantic `ValidationError` (422 at the API). For a catalog order line (`item_id` set) the quantity must also be a whole number — the schema cannot know this (the item comes from the order line), so the manager rejects it with `ValueError("Delivery line has a fractional quantity; stock requires whole units")` (400 via the service; same wording as `complete_delivery` R7) (best-practice default, delegated by reviewer). Free-text lines may stay fractional. All of these are rejected before anything is written (R10a). `delivery_method_id` must reference a live delivery method of this workspace, else `ValueError("Delivery method <id> not found")` (400), nothing written. *(Today [BUG-362, P3]: `quantity_delivered` has no range check — `0` or a negative value is accepted, which on completion decreases a free-text line's delivered quantity or fails a catalog line's stock deduction with a 500. Today [BUG-021, P4]: more than 2 decimals is silently rounded by the DB. Today [BUG-725, Q5]: a fractional quantity on a catalog line is accepted at planning time, and the delivery can then never be completed — `complete_delivery` R7's whole-units check always fails it — so it must be cancelled and re-planned. Today [BUG-730, Q10]: `delivery_method_id` is not checked for workspace or soft-deletion.)* Order completion state is not otherwise checked here.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| no lines | `ValueError` | `Delivery must have at least one item` |
| order not in workspace | `ValueError` | `Sales order <id> not found` |
| invoice not finalized | `ValueError` | `Finalize the invoice before planning a delivery` |
| line not in workspace | `ValueError` | `Sales order item <id> not found` |
| line belongs to a different order [BUG-723] | `ValueError` | `Sales order item <id> does not belong to sales order <order id>` |
| line needs no delivery | `ValueError` | `Sales order item <id> does not require delivery — it should be fulfilled directly, not delivered` |
| over capacity | `ValueError` | see R7 |
| repeated line within one request [BUG-724] | `ValueError` | `Sales order item <id> appears more than once in this delivery` |
| out-of-range quantity [BUG-362, BUG-021] | pydantic `ValidationError` (422) | schema message |
| fractional quantity on a catalog line [BUG-725] | `ValueError` (400) | `Delivery line has a fractional quantity; stock requires whole units` |
| delivery method not found/live in workspace [BUG-730] | `ValueError` | `Delivery method <id> not found` |

**Side effects:** inserts 1 `sales_deliveries`, N `sales_delivery_items`, 1 `sales_order_events`; flush only.

---

## `SalesManager.complete_delivery(session, delivery_id, workspace_id, user_id, actual_delivery_date=None, completion_code=None)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: `SalesService.complete_delivery` ← `POST /sales-deliveries/{id}/complete/`; the service returns 404 itself for an unknown delivery)

**Purpose:** Mark a delivery delivered, add its quantities to the order lines and deduct sellable stock for catalog lines.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| delivery_id | int | |
| workspace_id | int | |
| user_id | int | performer; stamped on the stock ledger/product |
| actual_delivery_date | date \| None | `None` → today (server local date) |
| completion_code | str \| None | free text, no checks |

**Returns:** the parent `SalesOrder`, flushed.

**Rules:**
- **R1.** A delivery not found in this workspace raises `ValueError("Delivery not found")`; nothing written. ✅
- **R2.** [BUG-721] Only a delivery whose status is exactly `planned` is completed; a `delivered` or `cancelled` delivery (or any other status) raises `ValueError("Only planned deliveries can be completed (this delivery is '<status>')")`, nothing changed. *(Today: the status is not checked at all — `planned`, `delivered` and `cancelled` deliveries are all processed the same way, so a `delivered` delivery can be completed again (adding quantities and deducting stock a second time) and a `cancelled` one can still deduct stock.)*
- **R2a.** [BUG-720, HR-10] The delivery row is read `FOR UPDATE` before the R2 status check; a second, concurrent complete request sees the already-`delivered` status and gets the normal R2 error instead of both succeeding. This lock also covers R4 (order-line quantity increase) and R5 (stock deduction) for the same request. *(Today: the delivery is read without a row lock, so two concurrent "complete" requests for the same delivery can both deduct stock.)*
- **R3.** [BUG-733, BUG-734] The delivery gets `delivery_status = 'delivered'` and `actual_delivery_date` = the given date or today's server-local date. `completion_code` is trimmed; when the trimmed value is empty (including `None`, `""` or whitespace-only) the stored code becomes/stays `None` and nothing is shown in the activity log; otherwise the trimmed code is stored. `updated_by` is set to `user_id` (HR-9; this transition always changes at least the status/date, so it is always written here). *(Today [BUG-733]: `updated_by` is never written by completion. Today [BUG-734]: an empty string is written as `""` (not trimmed to `None`), and `None` leaves the stored code unchanged instead of clearing it — different from `fulfill_service_item`, which drops `""`/`None` entirely.)*
- **R4.** For each delivery line, the order line's `quantity_delivered` increases by the delivery line's quantity, without any cap against the ordered quantity. ✅ *(locked together with R2/R2a — BUG-720)*
- **R5.** [BUG-735] For each catalog delivery line (`item_id` set), sellable stock is deducted at the order's factory: the live product row (workspace, order factory, item, `is_available_for_sale = True`) has `qty` reduced by the quantity and `updated_by = user_id`; one product-ledger row is written with `transaction_type 'sale'`, `quantity`, `qty_before`/`qty_after`, `unit_cost` = product avg cost, `total_cost` = avg cost × quantity (null if no avg cost), `avg_cost_before = avg_cost_after`, `source_type 'sales_delivery'`, `source_id = delivery_id`, `transfer_destination_type 'customer'`, `transfer_destination_id = order.account_id`, `performed_by = user_id`, notes `"Delivery <delivery number> for <order number>"` — the order number is used as stored, with no extra prefix. *(Today: the note template adds its own `SO-` prefix in front of an order number that already starts with `SO-`, giving `"… for SO-SO-2026-010"`.)* *(locked together with R2/R2a — BUG-720)*
- **R6.** Free-text delivery lines (`item_id` null) move no stock. ✅
- **R7.** Stock errors, raised mid-way after earlier changes were flushed (caller rolls back): quantity ≤ 0 → `ValueError("Sale deduction quantity must be positive")`; fractional quantity → `HTTPException` 400 `"Delivery line has a fractional quantity; stock requires whole units"`; no live product row or `qty` < quantity → `HTTPException` 422 `"Insufficient sellable stock for item <item_id> at factory <factory_id>: requested <q>, available <a>"` (`available` 0 when no row). Exactly the available quantity is allowed (stock goes to 0). ✅
- **R8.** Afterwards the order's `is_fully_delivered` is recomputed per `_recompute_is_fully_delivered`. ✅
- **R9.** [BUG-734] One event on the order: `event_type 'delivery_completed'`, description `"Delivery <number> marked delivered on <YYYY-MM-DD>"` plus `" (code: <code>)"` when the trimmed code is non-empty; metadata `{"delivery_id", "actual_delivery_date": "<YYYY-MM-DD>", "completion_code": <trimmed value or null>}`; `performed_by = user_id`. *(Today: the raw, untrimmed code is used both in the description and the metadata, so a whitespace-only code shows as `" (code:  )"` instead of being treated as absent.)*
- **R10.** A delivery with no lines just changes status, recomputes the flag and logs the event. ✅
- **R11.** The invoice-finalized state is not re-checked here. ✅

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| delivery not in workspace | `ValueError` | `Delivery not found` |
| not planned [BUG-721] | `ValueError` | `Only planned deliveries can be completed (this delivery is '<status>')` |
| stock errors | see R7 | see R7 |

**Side effects:** updates the delivery, order lines, products, `is_fully_delivered`; inserts product-ledger rows and 1 event; flush only.

---

## `SalesManager.cancel_delivery(session, delivery_id, workspace_id, user_id=None)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: `SalesService.cancel_delivery` ← `POST /sales-deliveries/{id}/cancel/`; `ValueError` → 400)

**Purpose:** Cancel a planned delivery so its quantity can be planned again.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| delivery_id | int | |
| workspace_id | int | |
| user_id | int \| None | event performer (may be null) |

**Returns:** the updated `SalesDelivery`, flushed.

**Rules:**
- **R1.** A delivery not found in this workspace raises `ValueError("Delivery <id> not found")`. ✅
- **R2.** A delivery whose status is not exactly `planned` raises `ValueError("Only planned deliveries can be cancelled (this delivery is '<status>')")`; nothing changes. ✅
- **R2a.** [BUG-720, HR-10] The delivery row is read `FOR UPDATE` before the R2 check; a cancel racing a concurrent completion sees the already-updated status and gets the normal R2 error, instead of cancelling a delivery whose stock was already deducted. *(Today: the `planned` status is checked without a row lock.)*
- **R3.** [BUG-733] Otherwise `delivery_status` becomes `cancelled`; nothing else on the delivery, the order lines or stock changes; `updated_by` is set to `user_id` (HR-9). Its lines stop counting as planned (see `create_delivery_with_items` R7). *(Today: `updated_by` is never written by cancel.)*
- **R4.** One event on the delivery's order: `event_type 'delivery_cancelled'`, description `"Delivery <number> cancelled"`, metadata `{"delivery_id": <id>}`, `performed_by = user_id`. ✅

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not in workspace | `ValueError` | `Delivery <id> not found` |
| not planned | `ValueError` | `Only planned deliveries can be cancelled (this delivery is '<status>')` |

**Side effects:** delivery status update; 1 event; flush only.

---

## `SalesManager.update_delivery(session, delivery_id, workspace_id, data, user_id=None)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `SalesService.update_delivery` ← `PATCH /sales-deliveries/{id}/`; `ValueError` → 400)

**Purpose:** Edit schedule, delivery method, tracking number or notes of a planned delivery.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| data | pydantic model | API passes `SalesDeliveryEditRequest` (`scheduled_date`, `delivery_method_id`, `tracking_number`, `notes`, all optional) |
| user_id | int \| None | event performer |

**Returns:** the updated `SalesDelivery`, flushed.

**Rules:**
- **R1.** A delivery not found in this workspace raises `ValueError("Delivery <id> not found")`. ✅
- **R2.** A delivery whose status is not exactly `planned` raises `ValueError("Only planned deliveries can be edited (this delivery is '<status>')")`; nothing changes. ✅
- **R3.** [BUG-732, BUG-733] `scheduled_date`, `tracking_number` and `notes` sent with a non-null value are written as given; sent explicitly as `null`, they are cleared to `None`; omitted, they are left unchanged. `delivery_method_id` sent with a value is written (subject to R7/BUG-730); omitted, it is left unchanged; sent explicitly as `null`, the request is rejected before any field is touched (`SalesDeliveryEditRequest.delivery_method_id` requires a value when the key is present — new schema constraint, since the column itself is required). When at least one field actually changes, `updated_by` is set to `user_id` (HR-9); a no-op request (R5) leaves it alone. *(Today [BUG-732]: a field sent as `null` is dropped like an omitted one — `scheduled_date`, `tracking_number` and `notes`, once set, can only be replaced, never cleared. Today [BUG-733]: `updated_by` is never written by this method, whether or not a field changed.)*
- **R4.** An event is logged only if at least one sent value (including an explicit `null` that clears a field) differs from the stored one: `event_type 'delivery_updated'`, description `"Delivery <number> updated (<labels>)"`, labels of the changed fields joined by `", "` in the fixed order `scheduled date`, `delivery method`, `tracking number`, `notes`; metadata `{"delivery_id": <id>}`; `performed_by = user_id`. ✅
- **R5.** When every sent value equals the stored one, nothing is logged and the row is unchanged. ✅
- **R6.** Any field of `data` that also exists on the delivery is written (a wider schema could change e.g. `delivery_status`); the API only sends the four edit fields. ✅ A changed field outside the four edit fields gets no label: it still triggers the R4 event but contributes nothing to `<labels>` — when it is the only change, the description is `"Delivery <number> updated ()"`.
- **R7.** [BUG-730] `delivery_method_id`, when given a value, must reference a live delivery method of this workspace, else `ValueError("Delivery method <id> not found")` (400), nothing written. *(Today: not checked for workspace or soft-deletion — a method of another workspace, or a deleted one, is accepted and stored.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not in workspace | `ValueError` | `Delivery <id> not found` |
| not planned | `ValueError` | `Only planned deliveries can be edited (this delivery is '<status>')` |
| `delivery_method_id` explicitly `null` [BUG-732] | pydantic `ValidationError` (422) | schema message |
| delivery method not found/live in workspace [BUG-730] | `ValueError` | `Delivery method <id> not found` |

**Side effects:** delivery update; 0 or 1 event; flush only.

---

## `SalesManager.fulfill_service_item(session, order_item_id, workspace_id, user_id, completion_code=None)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: `SalesService.fulfill_service_item` ← `POST /sales-orders/{id}/items/{item_id}/fulfill/`; the service repeats R1–R3 itself with 404/422 and also checks the line belongs to the order in the URL)

**Purpose:** Mark a line that needs no delivery as fully fulfilled in one step, with no stock movement.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| order_item_id | int | order line id |
| completion_code | str \| None | free text |

**Returns:** the parent `SalesOrder`, flushed.

**Rules:**
- **R1.** A line not found in this workspace raises `ValueError("Sales order item <id> not found")`. ✅
- **R2.** A line with `requires_delivery = True` raises `ValueError("This line requires delivery — use the delivery workflow, not direct fulfillment")`. ✅
- **R3.** When the order's `invoice_confirmed` is `False`, raises `ValueError("Finalize the invoice before fulfilling this line")`. Checks run R1, R2, R3. ✅
- **R3a.** [BUG-720, HR-10] The order line is read `FOR UPDATE` before the R4/R6 "not yet fulfilled" check; a concurrent second fulfil request sees the already-fulfilled line and is the R6 no-op instead of both logging an `item_fulfilled` event. *(Today: the check is made without a row lock.)*
- **R4.** [BUG-731, BUG-734] When `quantity_delivered + quantity_refunded < quantity_ordered` (`quantity_refunded` is never `None` on a stored line — NOT NULL, default 0; Notes, G17): `quantity_delivered` becomes `quantity_ordered − quantity_refunded`; `completion_code` is trimmed, and a non-empty trimmed value is stored in `fulfillment_completion_code` (`None`, `""` or whitespace-only leaves it unchanged). *(Today [BUG-731]: the condition and the new value ignore `quantity_refunded` entirely — `quantity_delivered < quantity_ordered` and set to `quantity_ordered` — so re-fulfilling after a partial refund sets delivered back above what was actually still owed, over-counting the line (`delivered + refunded > ordered`). Today [BUG-734]: the code is not trimmed, so a whitespace-only code is treated as non-empty and stored/shown as typed.)*
- **R5.** [BUG-734] In that case one event is logged: `event_type 'item_fulfilled'`, description `"<label> fulfilled (<quantity_ordered> <unit>)"` plus `" (code: <code>)"` for a non-empty trimmed code, where `<label>` is the catalog item's name, else the line's description, else `Item #<item_id>`, and `<unit>` is the catalog item's unit or `unit(s)`; metadata `{"item_id": <order line id>, "completion_code": <trimmed value or null>}`; `performed_by = user_id`. *(Today: the untrimmed code is used in both the description and the metadata.)*
- **R6.** [BUG-731] When `quantity_delivered + quantity_refunded >= quantity_ordered` nothing is written and no event is logged (the code is ignored). *(Today: the no-op condition is `quantity_delivered >= quantity_ordered`, ignoring `quantity_refunded` — see R4.)*
- **R7.** *(superseded — `quantity_refunded` is now considered by R4/R6; see BUG-731.)*
- **R8.** In every successful case the order's `is_fully_delivered` is recomputed per `_recompute_is_fully_delivered`. ✅
- **R9.** No delivery rows and no stock movement are created. ✅

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| line not in workspace | `ValueError` | `Sales order item <id> not found` |
| line needs delivery | `ValueError` | `This line requires delivery — use the delivery workflow, not direct fulfillment` |
| invoice not finalized | `ValueError` | `Finalize the invoice before fulfilling this line` |

**Side effects:** order line update; 0 or 1 event; `is_fully_delivered` may change; flush only.

---

## `SalesManager._recompute_is_fully_delivered(session, sales_order, workspace_id)`
**Shape:** compute
**Persistence:** writes
**Visibility:** internal (used by: `complete_delivery`, `fulfill_service_item`)

**Purpose:** Store whether every line of the order has been delivered in full.

**Returns:** the computed `bool`.

**Rules:**
- **R1.** [BUG-731] The value is `True` when every line of the order (in this workspace; delivery and non-delivery lines alike) has `quantity_delivered + quantity_refunded >= quantity_ordered` (`quantity_refunded` is never `None` on a stored line — NOT NULL, default 0; Notes, G17) — the same done-test as `all_deliverable_items_delivered` / `all_fulfilment_items_fulfilled`. *(Today: `quantity_refunded` is ignored — the condition is `quantity_delivered >= quantity_ordered` — so after a refund the flag can never become `True` again even though the completion checks (which do count refunded quantity) consider the line done.)*
- **R2.** An order with no lines gives `True`. ✅
- **R3.** The order's `is_fully_delivered` is written only when it differs from the computed value (it can also go from `True` back to `False`). ✅

**Errors:** none
**Side effects:** may update `sales_orders.is_fully_delivered`; flush only.

---

## `SalesManager._base_sections_confirmed(order)`
**Shape:** compute
**Persistence:** pure
**Visibility:** internal (used by: `set_approval`, `SalesService._sync_draft_invoice_for_so`, `SalesService.finalize_sales_order_invoice`)

**Purpose:** Says whether both order info and items are confirmed.

**Returns:** `bool`

**Rules:**
- **R1.** `True` only when `order_info_confirmed` and `items_confirmed` are both true; `invoice_confirmed` plays no part.

**Errors:** none
**Side effects:** none

---

## `SalesManager.is_so_financially_locked(session, order)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `set_section_confirm`, `set_approval`, `SalesService._sync_draft_invoice_for_so`)

**Purpose:** Says whether the order's linked invoice has been confirmed, which locks the order.

**Returns:** `bool`

**Rules:**
- **R1.** No linked invoice (`invoice_id` null) → `False`.
- **R2.** A linked invoice not found in the order's workspace → `False`.
- **R3.** Invoice status `confirmed` → `True`; `draft` or `voided` → `False`. (The code also treats `locked` as locked, but no code path in the application ever writes `invoice_status = 'locked'` — only `draft`/`confirmed`/`voided` are written — so `locked` is a dead value and is not specified or tested (best-practice default, delegated by reviewer; G18).)

**Errors:** none
**Side effects:** none

---

## `SalesManager.unlink_invoice_from_so(session, order, user_id, reason, event_type='invoice_unlinked')`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `SalesService._delete_linked_draft_invoice_for_so`, with `event_type='invoice_draft_deleted'`)

**Purpose:** Detach the invoice from the order and reset the invoice-related flags.

**Returns:** `None`

**Rules:**
- **R1.** Sets `invoice_id = None`, `invoice_confirmed = False`, `is_invoiced = False`, `paid = False`, whatever their previous values.
- **R2.** Logs one event with the given `event_type`, description = `reason`, `performed_by = user_id`, metadata `{"invoice_id": <previous invoice_id, may be null>}`.
- **R3.** The invoice row, approvals and section flags are not touched.

**Errors:** none
**Side effects:** order update; 1 event; flush only.

---

## `SalesManager.set_section_confirm(session, order_id, workspace_id, user_id, section, confirmed)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: `SalesService.set_section_confirm` ← `PATCH /sales-orders/{id}/section-confirm/`; the request schema limits `section` to `order_info`/`items`)

**Purpose:** Confirm or unconfirm the order-info or items section of an order.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| section | str | `order_info` or `items`; anything else rejected (R1) |
| confirmed | bool | target state |

**Returns:** the `SalesOrder`, flushed.

**Rules:**
- **R1.** A section other than `order_info` / `items` (including `invoice`) → 400 `"Unknown section '<section>'"`, checked before the order is looked up. ✅
- **R2.** An order not found in this workspace → 404 `"Sales order with ID <id> not found"`. ✅
- **R3.** When `confirmed` equals the current flag, the order is returned unchanged: no checks, no event, no approval reset. ✅
- **R4.** Confirming `order_info`: a `contact_name` that is null, empty or whitespace-only → 400 `'Set the customer name before confirming'`. *(The "missing customer" / "missing order date" checks removed — dead code, see the spec's dead-code log.)*
- **R5.** Confirming `items` with no lines on the order → 400 `'Add at least one line item before confirming'`. ✅
- **R6.** Confirming is never blocked by the invoice lock or completion. ✅
- **R7.** Unconfirming when the order is financially locked (`is_so_financially_locked`) → 400 `'Cannot unconfirm order info after invoice is confirmed'` / `'Cannot unconfirm order items after invoice is confirmed'`. This is checked before R8. ✅
- **R8.** Unconfirming a completed order → 400 `'Cannot unconfirm — order is complete'`. ✅
- **R9.** On success the flag is set and one event is logged: `event_type` `order_info_confirmed` / `order_info_unconfirmed` / `items_confirmed` / `items_unconfirmed`, description `'Order info confirmed'` / `'Order info unconfirmed'` / `'Order items confirmed'` / `'Order items unconfirmed'`, `performed_by = user_id`, no metadata. ✅
- **R10.** A successful unconfirm then clears approvals per `reset_approvals` with reason `'Section unconfirmed'` (event after the unconfirm event). ✅
- **R11.** [BUG-720, HR-10] The order row is read `FOR UPDATE` before the R3 current-flag check; the loser of a race sees the already-applied flag (R3's unchanged-return) or the already-changed lock/completion state (R7/R8's error) instead of both proceeding. *(Today: the confirm/unconfirm decision is made on an unlocked read; concurrent requests can both log the same event, and an unconfirm can race invoice finalization.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| unknown section | `HTTPException` 400 | `Unknown section '<section>'` |
| order not in workspace | `HTTPException` 404 | `Sales order with ID <id> not found` |
| confirm checks | `HTTPException` 400 | see R4, R5 |
| unconfirm checks | `HTTPException` 400 | see R7, R8 |

**Side effects:** order flag update; 1 event (+ approval reset and its event on unconfirm); flush only.

---

## `SalesManager.reset_approvals(session, order_id, workspace_id, user_id, reason='Cleared approvals')`
**Shape:** update
**Persistence:** writes
**Visibility:** internal (used by: `set_section_confirm`)

**Purpose:** Clear every given approval on an order.

**Returns:** `None`

**Rules:**
- **R1.** Every approver of the order (in this workspace) with `approved = True` gets `approved = False`, `approved_at = None`. Approvers not yet approved are untouched.
- **R2.** When at least one approval was cleared, one event is logged: `event_type 'approvals_reset'`, description `"<n> approval(s) cleared — <reason>"`, `performed_by = user_id` (may be null), no metadata.
- **R3.** No approved approvers (or none at all) → nothing written, no event. The order's existence is not checked.

**Errors:** none
**Side effects:** approver updates; 0 or 1 event; flush only.

---

## `SalesManager.apply_post_invoice_confirms(session, order, workspace_id, user_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `SalesService.finalize_sales_order_invoice`, which logs its own `invoice_confirmed` event afterwards)

**Purpose:** Set all three section flags after the invoice is finalized.

**Returns:** `None`

**Rules:**
- **R1.** If `order_info_confirmed` is false it becomes true and an event `order_info_confirmed` / `'Order info confirmed after invoice finalized'` is logged.
- **R2.** If `items_confirmed` is false it becomes true and an event `items_confirmed` / `'Order items confirmed after invoice finalized'` is logged.
- **R3.** `invoice_confirmed` becomes true; no event is logged for it.
- **R4.** Flags already true produce no event. No checks of any kind are made.

**Errors:** none
**Side effects:** order flags; 0–2 events (`performed_by = user_id`); flush only.

---

## `SalesManager.mark_order_complete(session, order_id, workspace_id, user_id)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: `SalesService.mark_order_complete` ← `POST /sales-orders/{id}/complete/`)

**Purpose:** Close an order once its invoice is finalized, every line is done and no return is open.

**Returns:** the `SalesOrder`, flushed.

**Rules:**
- **R1.** An order not found in this workspace → 404 `"Sales order with ID <id> not found"`. ✅
- **R2.** An already completed order is returned unchanged (no checks, no event, no paid sync). ✅
- **R3.** `invoice_confirmed` false → 400 `'Finalize the invoice before marking the order complete'`. ✅
- **R4.** Any line not done per `all_deliverable_items_delivered` / `all_fulfilment_items_fulfilled` (delivered + refunded ≥ ordered) → 400 `'Finish delivering and fulfilling all items before completing the order'`. An order with no lines passes. ✅
- **R5.** A return of this order with status `pending` → 400 `'Complete all open returns before marking the order complete'`; completed/voided returns do not block. Checks run R3, R4, R5. ✅
- **R6.** On success: `order_completed = True`, `completed_at` = current UTC time (naive), `completed_by = user_id`. ✅
- **R7.** Then the `paid` flag is synced per `sync_so_paid` (may log `payment_status_synced` before the completion event). ✅
- **R8.** One event `order_completed` / `'Order marked complete'`, `performed_by = user_id`. ✅
- **R9.** Approvals, `paid` and `is_fully_delivered` do not gate completion. ✅
- **R10.** [BUG-720, HR-10] The order row is read `FOR UPDATE` before the R2 completion check; a second, concurrent complete request sees `order_completed = True` and is the normal R2 unchanged-return instead of both completing the order and both logging `order_completed`. *(Today: completion state is checked without a lock.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not in workspace | `HTTPException` 404 | `Sales order with ID <id> not found` |
| invoice not finalized | `HTTPException` 400 | `Finalize the invoice before marking the order complete` |
| lines not done | `HTTPException` 400 | `Finish delivering and fulfilling all items before completing the order` |
| open return | `HTTPException` 400 | `Complete all open returns before marking the order complete` |

**Side effects:** order update; 1–2 events; flush only.

---

## `SalesManager.reopen_for_return(session, order, workspace_id, user_id)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: `SalesService.start_return`)

**Purpose:** Reopen a completed order when a return is started.

**Returns:** `True` if the order was reopened, else `False`.

**Rules:**
- **R1.** An order that is not completed → returns `False`; nothing written.
- **R2.** [BUG-2790] (owner, OQ-48, 2026-11-17) A completed order stays completed: `order_completed`, `completed_at`, `completed_by` unchanged, no event, nothing written, returns `False` — so its invoice stays frozen (`account_invoice_manager` F2, see RP4), and while the return is open the order shows "return in progress" (RP3), never open/editable (RP5). *(Today: a completed order gets `order_completed = False`, `completed_at = None`, `completed_by = None`, and one event `order_reopened` / `'Order reopened — a new return was started'`; returns `True`.)* The fix may instead drop the call from `SalesService.start_return`; either way the outcome above holds.
- **R2a.** (owner, OQ-48 refined, 2026-11-17) The "return in progress" state the order shows while the return is open is **not written here** and is not stored on the order: it is derived, per *Return-in-progress state* RP1–RP7 below. So R2's "nothing written" holds for the refined rule too: no completion field changes, no new column, no event. The same holds when the order already has an open return (a second return started): `False`, nothing written.

**Errors:** none
**Side effects:** order update; 0 or 1 event; flush only. *(Intended: none.)*

---

## Shared: Return-in-progress state (owner OQ-48 refined, 2026-11-17)
Not a callable of this manager; stated once here and cited by `reopen_for_return` R2/R2a, `purchase_order_return_manager.spec.md` and `sales_order_return_manager.spec.md` (OQ-48 / FU-2), and BUG-2789 / BUG-2790. The purchase order manager has no spec yet; the same rules apply to it with the PO names given.

**What exists today (read from the code):** no field can carry "return in progress". A sales order stores completion as `order_completed` (bool, not null, default `False`) with `completed_at` / `completed_by`; a purchase order stores it as its workflow stage (`current_status_id` → `statuses.name`; `PurchaseOrder.order_completed` is a property, `True` exactly when the name is `"Complete"`; the stages are `Draft`, `Planning`, `Receiving`, `Complete`). Neither order model nor response schema has a return flag. What does exist is `SalesOrderReturnManager.has_open_return` / `PurchaseOrderReturnManager.has_open_return` (at least one return of this order and workspace with status `pending`), used today only by `mark_order_complete`.

**Shape chosen (Claude, under the reviewer's delegation, 2026-11-17):** a derived flag, not a stored state and not a new PO stage. A new stage (e.g. "Return in progress") or clearing `order_completed` would make the order "not completed", which F2 reads, and would also drop it out of every "completed / closed" filter (e.g. the PO "fully closed" filter `Complete` + paid). The derived flag leaves all of that alone.

- **RP1. Stored completion is never changed by a return.** Starting, completing or cancelling a return on a completed order leaves `order_completed`, `completed_at`, `completed_by` (sales) and the stage `Complete` and `actual_delivery_date` (purchase) exactly as they were. No `order_reopened` event. (`reopen_for_return` R2 [BUG-2790]; PO twin [BUG-2789].)
- **RP2. The flag.** `has_open_return` = the return manager's `has_open_return(order id, workspace)`: `True` while at least one of this order's returns in this workspace is `pending`. Read at call time; never stored. *(Requires new: the order's read responses (`SalesOrderResponse`, the PO response) carry `has_open_return: bool`, filled by the service when it builds the response; today they don't.)*
- **RP3. What the order shows.** Completed and `has_open_return` → **"return in progress"**. Completed and not `has_open_return` → **"completed"**. Not completed → its normal state, whatever `has_open_return` says (a return on an open order does not change what it shows; `mark_order_complete` R5 already refuses completion while one is open).
- **RP4. The freeze stays on.** `account_invoice_manager.spec.md` F2 reads only stored completion (stage `Complete` / `order_completed = True`) and, per F3, nothing else; it does **not** read `has_open_return`. Because of RP1, a completed order with an open return is still "completed" to F2, so its own invoice stays frozen (delete / revert / void refused per F5). F2 needs no change. The return's own credit note is not the order's invoice (F6) and keeps its own rules (`void_invoice` R3b/R3c).
- **RP5. Nothing on the order is editable.** The existing completed-order guards keep refusing because completion stays stored: sales `set_section_confirm` unconfirm ("Cannot unconfirm — order is complete"), approval withdrawal ("Cannot withdraw approval — order is complete"); purchase approval withdrawal and receiving ("Cannot receive against a completed purchase order"). No guard reads `has_open_return`, and none needs to.
- **RP6. Several returns.** (a) Two returns open at once: the flag is `True`; the second `start_return` writes nothing on the order (R2a). (b) One completed (or cancelled) while another stays `pending`: still "return in progress". (c) Only when the **last** pending return leaves `pending` does the order show "completed" again. Nothing is written on the order at any of these steps.
- **RP7. A return cancelled through its credit note** (BUG-2788, `void_invoice` R3c): the pending return becomes `voided`, so it no longer counts in RP2; if it was the last pending one the order shows "completed" again (RP6 c), with no write on the order. Same as cancelling through `void_return`. A completed return's credit-note void is refused (R3c), so the state does not change.

**Open, not decided here (order workflow, for the owner):** a `replace` return on a completed order leaves a gap (sales: delivered < ordered; purchase: received < ordered) that today must be redelivered / re-received. Under RP5 a completed order cannot take new receiving (purchase guard above) and, under the owner's rule, goes back to "completed" when the return completes. How the replacement goods move is the return managers' FU-2, still open.

**Note for the cases file (SM-ROR-02 … 10):** ROR-02, 06, 07 stay strict xfail BUG-2790 with the same Then (stored completion unchanged, `False`, no event); cite R2/R2a and RP1. ROR-02 additionally gets a pending return in its Given and, in its Then, the order still `order_completed True` with `has_open_return` (return manager) `True` — i.e. "return in progress". ROR-03 keeps its pass Thens and should cite RP4 (invoice confirmed and unchanged). ROR-08 / 09 / 10: citations only (R2a: nothing written). RP2/RP3 (the response field) are not this manager's: their cards belong to the service/response spec, deferred.

---

## `SalesManager._invoice_payment_status(session, order)`
**Shape:** helper
**Persistence:** reads
**Visibility:** internal (used by: `sync_so_paid`)

**Purpose:** Read the linked invoice's payment status.

**Returns:** `str | None`

**Rules:**
- **R1.** No linked invoice → `None`.
- **R2.** Linked invoice not found in the order's workspace → `None`.
- **R3.** Otherwise the invoice's `payment_status` (`unpaid`, `partial`, `paid`, `overdue`).

**Errors:** none
**Side effects:** none

---

## `SalesManager.sync_so_for_linked_invoice(session, invoice_id, workspace_id, user_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `InvoicePaymentManager` after payment changes)

**Purpose:** Re-sync the `paid` flag of the order linked to an invoice.

**Returns:** `None`

**Rules:**
- **R1.** No order of this workspace links to `invoice_id` → nothing happens.
- **R2.** Otherwise that order is synced per `sync_so_paid`. If several orders link the same invoice, only one of them (unspecified which) is synced.

**Errors:** none
**Side effects:** see `sync_so_paid`.

---

## `SalesManager.sync_so_paid(session, order, workspace_id, user_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `mark_order_complete`, `sync_so_for_linked_invoice`)

**Purpose:** Keep the order's denormalised `paid` flag equal to "linked invoice is paid".

**Returns:** `True` if the flag changed, else `False`.

**Rules:**
- **R1.** The target value is `True` only when a linked invoice exists in the order's workspace and its `payment_status` is exactly `paid`; `partial`, `unpaid`, `overdue`, no invoice or an invoice not found → `False`. The invoice's status (e.g. `voided`) is not considered.
- **R2.** Target equal to the current flag → returns `False`; nothing written.
- **R3.** Otherwise the flag is set and one event is logged: `event_type 'payment_status_synced'`, description `'Order marked paid from linked invoice'` / `'Order marked unpaid from linked invoice'`, metadata `{"paid": <bool>}`, `performed_by = user_id` (may be null); returns `True`.

**Errors:** none
**Side effects:** order update; 0 or 1 event; flush only.

---

## `SalesManager.list_approvers(session, order_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `SalesService.list_approvers` ← `GET /sales-orders/{id}/approvers/`)

**Purpose:** List an order's approvers with their profile and workspace position.

**Returns:** list of `(approver, profile or None, position or None)`.

**Rules:**
- **R1.** An order not found in this workspace → 404 `"Sales order with ID <id> not found"`.
- **R2.** All approvers of the order in this workspace are returned, ordered by `assigned_at` ascending (equal times in no guaranteed order); no approvers → `[]`.
- **R3.** `position` is the user's workspace-member position; `None` when the user is no longer a member of this workspace or has no position. Member status (active/suspended) is not considered.
- **R4.** `profile` is the approver's profile; it is always present (FK with cascade — Notes, G8), so `None` cannot occur.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not in workspace | `HTTPException` 404 | `Sales order with ID <id> not found` |

**Side effects:** none

---

## `SalesManager.approval_summary(session, order)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `SalesService.finalize_sales_order_invoice`, `GET /sales-orders/{id}/approvers/`)

**Purpose:** Count approvals against the number required.

**Returns:** `(approved_count, required, met)`

**Rules:**
- **R1.** `approved_count` = number of the order's approvers (in the order's workspace) with `approved = True`. ✅
- **R2.** [BUG-362] `required` = `required_approvals` when it is not null — guaranteed by the schema to be null or `>= 1` (`SalesOrderUpdate.required_approvals` rejects anything else with 422, fix in `app/schemas/sales_order.py`) — used as-is, including larger than the number of approvers; when null, `required` = `max(1, number of assigned approvers)` (BUG-736). *(Today: `required_approvals` has no range check and is used as-is even if `0` or negative; when null, `required` is the number of assigned approvers with no floor, i.e. `0` when there are none.)*
- **R3.** [BUG-736] `met` = `approved_count >= required`. With R2's fix, zero approvers with null `required_approvals` → `required = 1` → never met; an explicit `required_approvals` above the number of approvers still → never met. *(Today [BUG-736, Q18]: zero approvers with null `required_approvals` gives `required = 0`, so approval is "met" with nobody having approved. Today [BUG-362, P6]: an unvalidated `required_approvals <= 0` also makes approval automatically met.)*

**Errors:** none
**Side effects:** none

---

## `SalesManager.add_approver(session, order_id, user_id, workspace_id, assigned_by)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `SalesService.add_approver` ← `POST /sales-orders/{id}/approvers/`)

**Purpose:** Assign a workspace member as an approver of an order.

**Returns:** the new `SalesOrderApprover`, flushed.

**Rules:**
- **R1.** An order not found in this workspace → 404 `"Sales order with ID <id> not found"`. ✅
- **R2.** A user with no membership in this workspace, or a membership whose status is not `active` (`suspended`, `invited`), → 400 `"User is not an active member of this workspace"`. ✅
- **R3.** A user already an approver of this order → 409 `"User is already an approver for this order"`. (A DB unique constraint on `(sales_order_id, user_id)` backs this.) Checks run R1, R2, R3. ✅
- **R4.** Creates an approver with `approved = False`, `approved_at` null, `assigned_by`, `assigned_at` = now (UTC). ✅
- **R5.** One event `approver_added`, description `"Added <name> as approver"`, metadata `{"user_id", "user_name"}`, `performed_by = assigned_by`; `<name>` is the profile's name. ✅ (The `User #<id>` fallback for a missing profile is unreachable — see Notes, G8.)
- **R6.** [BUG-737] An order that is completed → 400 `"Cannot change approvers — order is complete"`; otherwise, an order that is financially locked (`is_so_financially_locked`) → 400 `"Cannot change approvers — invoice is locked"`; checked after R1–R3, before R4. *(Today: the order's state (completed, invoice confirmed) is not checked at all, so an approver can be added to — and per `remove_approver` R4, removed from — a finalized/completed order, changing the record the approval decision was based on. This is the same guard `set_approval` already applies to withdrawing, per `set_approval` R4.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| order not in workspace | `HTTPException` 404 | `Sales order with ID <id> not found` |
| not an active member | `HTTPException` 400 | `User is not an active member of this workspace` |
| already approver | `HTTPException` 409 | `User is already an approver for this order` |
| order complete [BUG-737] | `HTTPException` 400 | `Cannot change approvers — order is complete` |
| invoice locked [BUG-737] | `HTTPException` 400 | `Cannot change approvers — invoice is locked` |

**Side effects:** 1 approver row; 1 event; flush only.

---

## `SalesManager.remove_approver(session, order_id, user_id, workspace_id, performed_by=None)`
**Shape:** delete
**Persistence:** writes
**Visibility:** public (used by: `SalesService.remove_approver` ← `DELETE /sales-orders/{id}/approvers/{user_id}/`)

**Purpose:** Remove an approver from an order.

**Returns:** `None`

**Rules:**
- **R1.** No approver row for (order, user) in this workspace — including a missing or other-workspace order — → 404 `"Approver not found"`. ✅
- **R2.** The approver row is hard-deleted, whether or not it had approved; the last approver can be removed (subject to R4). ✅
- **R3.** One event `approver_removed`, description `"Removed <name> as approver"` (`<name>` = profile name; the `User #<id>` fallback is unreachable — Notes, G8), metadata `{"user_id", "user_name"}`, `performed_by = performed_by`. ✅
- **R4.** [BUG-737] An order that is completed → 400 `"Cannot change approvers — order is complete"`; otherwise, an order that is financially locked (`is_so_financially_locked`) → 400 `"Cannot change approvers — invoice is locked"`; checked after R1, before R2. *(Today: the order's state is not checked — an approver, including one who already approved, can be removed from a finalized/completed order. Same fix and messages as `add_approver` R6.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not an approver | `HTTPException` 404 | `Approver not found` |
| order complete [BUG-737] | `HTTPException` 400 | `Cannot change approvers — order is complete` |
| invoice locked [BUG-737] | `HTTPException` 400 | `Cannot change approvers — invoice is locked` |

**Side effects:** 1 approver row deleted; 1 event; flush only.

---

## `SalesManager.set_approval(session, order_id, user_id, workspace_id, approved)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: `SalesService.set_approval` ← `POST`/`DELETE /sales-orders/{id}/approvers/me/approve/`, always for the current user)

**Purpose:** Give or withdraw the user's approval of an order.

**Returns:** the approver row, flushed.

**Rules:**
- **R1.** A user who is not an approver of this order in this workspace → 403 `"You are not an assigned approver for this order"`. ✅
- **R2.** Approving when order info and items are not both confirmed → 400 `'Confirm customer, order details, and items before approving'`. ✅
- **R3.** Approving is allowed on completed or financially locked orders. ✅
- **R4.** Withdrawing on a completed order → 400 `'Cannot withdraw approval — order is complete'`; otherwise, on a financially locked order → 400 `'Cannot withdraw approval — invoice is locked'` (completion checked first). ✅
- **R5.** On success `approved` is set; `approved_at` = current UTC time when approving, `None` when withdrawing; one event `approved` / `'Approved order'` or `approval_withdrawn` / `'Withdrew approval'`, `performed_by = user_id`, no metadata. ✅
- **R6.** [BUG-009] When the requested state (`approved`) equals the current one, nothing is written: `approved_at` keeps its current value and no event is logged; the approver row is returned unchanged. *(Today: a request that does not change the state — approve when already approved, withdraw when not approved — is processed the same as a real change: `approved_at` is re-stamped/cleared and an event is logged, per BUG-009's pattern.)*
- **R7.** [BUG-720, HR-10] The approver row and the order row are read `FOR UPDATE` before the R2–R4 checks; the loser of a race against another approve/withdraw, an unconfirm (`set_section_confirm` R10's approval reset) or an invoice finalization sees the new state and gets the normal R2/R4 error instead of proceeding. *(Today: the approval decision is made on unlocked reads of the approver and the order.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not an approver | `HTTPException` 403 | `You are not an assigned approver for this order` |
| sections not confirmed (approve) | `HTTPException` 400 | `Confirm customer, order details, and items before approving` |
| completed (withdraw) | `HTTPException` 400 | `Cannot withdraw approval — order is complete` |
| locked (withdraw) | `HTTPException` 400 | `Cannot withdraw approval — invoice is locked` |

**Side effects:** approver update; 1 event; flush only.

---

## `SalesManager.log_event(session, order_id, workspace_id, event_type, description, performed_by=None, metadata=None)`
**Shape:** event-log
**Persistence:** writes
**Visibility:** public (used by: most methods here, `SalesService`, `AttachmentManager`)

**Purpose:** Append one entry to an order's activity log.

**Returns:** the new `SalesOrderEvent`, flushed.

**Rules:**
- **R1.** One row is stored with the given `workspace_id`, `sales_order_id`, `event_type`, `description`, `performed_by` and `metadata` (stored in the `metadata` JSON column; `None` reads back as `None`); `created_at` = now (UTC).
- **R2.** Nothing is validated: a non-existent order id fails at flush with `IntegrityError`; an `event_type` longer than 50 characters fails at flush with a DB error.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| unknown order / too-long type | DB error at flush | DB message |

**Side effects:** 1 event row; flush only.

---

## `SalesManager.list_events(session, order_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `SalesService.list_events` ← `GET /sales-orders/{id}/events/`)

**Purpose:** List an order's activity log with the performer's profile.

**Returns:** list of `(event, profile or None)`.

**Rules:**
- **R1.** An order not found in this workspace → 404 `"Sales order with ID <id> not found"`.
- **R2.** All events of the order in this workspace, newest `created_at` first, ties broken by higher `id` first; none → `[]`.
- **R3.** Each event is paired with the performer's profile; `None` when `performed_by` is null.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not in workspace | `HTTPException` 404 | `Sales order with ID <id> not found` |

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 46 | line `requires_delivery` true → considered | `all_deliverable_items_delivered` R1 |
| 47–50 | every line delivered+refunded ≥ ordered / any short / empty | `all_deliverable_items_delivered` R2, R3, R4 |
| 48 | `quantity_refunded or 0` | `all_deliverable_items_delivered` R2 |
| 59 | line `requires_delivery` false → considered | `all_fulfilment_items_fulfilled` R1 |
| 60–63 | all done / short / empty; `or 0` | `all_fulfilment_items_fulfilled` R1, R2 |
| 118 | `not items_data` | `create_sales_order_with_items` R1 |
| 130, 137, 138 | row is dict / object | `create_sales_order_with_items` R11 |
| order_catalog_items `assert_unique_catalog_item_ids` | item_id None → skip; seen → 409; name fallback | `create_sales_order_with_items` R2 |
| order_catalog_items `assert_meets_minimum_order_quantities` | item_id None → skip; product and min and qty < min → 422 | `create_sales_order_with_items` R3 |
| 143, 167 | pydantic validation of order / line | `create_sales_order_with_items` R4, R10 |
| dao/sales_order `generate_sales_order_number` | count per workspace+prefix, +1, pad 3 | `create_sales_order_with_items` R5 |
| 163 | loop over lines (one / many) | `create_sales_order_with_items` R8, R9 |
| 196 | `not delivery_items_data` | `create_delivery_with_items` R1 |
| 202 | parent order not found | `create_delivery_with_items` R2 |
| 204 | `not invoice_confirmed` | `create_delivery_with_items` R3 |
| dao/sales_delivery `generate_delivery_number` | count per workspace+prefix, +1, pad 3 | `create_delivery_with_items` R4 |
| 220 | loop over lines | `create_delivery_with_items` R9, R10 |
| 229 | order line not found | `create_delivery_with_items` R5 (extended: also checks the line's own `sales_order_id` matches — BUG-723) |
| (none) | repeated line within one request not checked | `create_delivery_with_items` R8 (BUG-724) |
| 231 | `not requires_delivery` | `create_delivery_with_items` R6 |
| model `quantity_planned` | delivery status == `planned` | `create_delivery_with_items` R7, R8 |
| model `quantity_available_to_plan` | `max(0, …)`; `or 0` | `create_delivery_with_items` R7 |
| 239 | requested > available | `create_delivery_with_items` R7 |
| (none) | no row lock before capacity check | `create_delivery_with_items` R7a (BUG-720) |
| 267 | `total_qty != 1`; `item_count != 1` | `create_delivery_with_items` R11 |
| (schema) | `delivery_status` field accepted on create | `create_delivery_with_items` R4 (BUG-722) |
| dao numbering (shared with `create_sales_order_with_items`) | global unique index; count-then-insert, no lock | `create_delivery_with_items` R4 (BUG-726, BUG-727) |
| (schema, `sales_delivery_item.py`) | quantity range/precision/whole-units not checked | `create_delivery_with_items` R13 (BUG-021, BUG-362, BUG-725) |
| (none) | `delivery_method_id` workspace/deletion not checked | `create_delivery_with_items` R13 (BUG-730) |
| 307 | delivery not found | `complete_delivery` R1 |
| (none) | no status check | `complete_delivery` R2 (BUG-721) |
| (none) | no row lock before status check | `complete_delivery` R2a (BUG-720) |
| 324 | `actual_delivery_date or today` | `complete_delivery` R3 |
| BaseDAO.update `exclude_none` | completion_code None → not written; not trimmed | `complete_delivery` R3 (BUG-734) |
| (none) | `updated_by` never set | `complete_delivery` R3 (BUG-733) |
| 330 | loop over delivery lines (zero / one / many) | `complete_delivery` R4, R10 |
| 338 | `item_id is not None` | `complete_delivery` R5, R6 |
| product_manager `apply_sale_deduction` | qty ≤ 0; fractional; no row / insufficient; avg cost None | `complete_delivery` R5, R7 |
| (ledger note template) | `f"... for SO-{order.sales_order_number}"` | `complete_delivery` R5 (BUG-735) |
| 353 | actual date set (always true after update) | `complete_delivery` R9 |
| 355 | `if actual_date_str` (always true) | `complete_delivery` R9 |
| 357 | `if completion_code` | `complete_delivery` R9 (BUG-734: untrimmed today) |
| 390 | delivery not found | `cancel_delivery` R1 |
| 392 | status != planned | `cancel_delivery` R2 |
| (none) | no row lock before status check | `cancel_delivery` R2a (BUG-720) |
| (none) | `updated_by` never set | `cancel_delivery` R3 (BUG-733) |
| 426 | delivery not found | `update_delivery` R1 |
| 428 | status != planned | `update_delivery` R2 |
| 435 / BaseDAO.update | `exclude_unset`, `exclude_none`; `hasattr` | `update_delivery` R3, R6 (BUG-732: `exclude_none` also drops an explicit `null`, so a field can never be cleared) |
| (none) | `updated_by` never set | `update_delivery` R3 (BUG-733) |
| 437 | sent value != stored | `update_delivery` R4, R5 |
| 441 | any changed field | `update_delivery` R4, R5 |
| 443 | label filter in fixed order | `update_delivery` R4 |
| (none) | `delivery_method_id` workspace/deletion not checked | `update_delivery` R7 (BUG-730) |
| 474 | line not found | `fulfill_service_item` R1 |
| 477 | `requires_delivery` | `fulfill_service_item` R2 |
| 485 | `not invoice_confirmed` | `fulfill_service_item` R3 |
| (none) | no row lock before the not-yet-fulfilled check | `fulfill_service_item` R3a (BUG-720) |
| 488 | delivered < ordered; `quantity_refunded` not read | `fulfill_service_item` R4, R6 (BUG-731: intended condition/target add `quantity_refunded`) |
| 490 | `if completion_code` (untrimmed) | `fulfill_service_item` R4 (BUG-734) |
| 494, model `item_name` | item name / description / `Item #id` | `fulfill_service_item` R5 |
| 495 | `item_unit or "unit(s)"` | `fulfill_service_item` R5 |
| 496 | `if completion_code` (untrimmed) | `fulfill_service_item` R5 (BUG-734) |
| 514–515 | all lines delivered ≥ ordered; empty; `quantity_refunded` not read | `_recompute_is_fully_delivered` R1, R2 (BUG-731: intended condition adds `quantity_refunded`) |
| 517 | flag differs | `_recompute_is_fully_delivered` R3 |
| 525 | both flags true | `_base_sections_confirmed` R1 |
| 529 | `invoice_id is None` | `is_so_financially_locked` R1 |
| 534 | invoice not found | `is_so_financially_locked` R2 |
| 536 | status in (confirmed, locked) (`locked` dead value — never written; G18) | `is_so_financially_locked` R3 |
| 546–555 | straight line | `unlink_invoice_from_so` R1–R3 |
| 569 | unknown section | `set_section_confirm` R1 |
| 573 | order not found | `set_section_confirm` R2 |
| 577 | confirmed == current | `set_section_confirm` R3 |
| 580 / 592 | confirm / unconfirm | `set_section_confirm` R4–R8 |
| 582–583 | `account_id is None` check | dead code — removed (Q17, no rule) |
| 584–585 | `order_date is None` check | dead code — removed (Q17, no rule) |
| 586 | contact blank | `set_section_confirm` R4 |
| 588, 590 | items section; no lines | `set_section_confirm` R5 |
| 593 | financially locked | `set_section_confirm` R7 |
| 596 | order completed | `set_section_confirm` R8 |
| 603 | event suffix | `set_section_confirm` R9 |
| 606 | `not confirmed` → reset approvals | `set_section_confirm` R10 |
| (none) | no row lock before the R3 check | `set_section_confirm` R11 (BUG-720) |
| 617 | loop over approvers (none / some) | `reset_approvals` R1, R3 |
| 618 | `approver.approved` | `reset_approvals` R1 |
| 622 | `reset_count` > 0 | `reset_approvals` R2, R3 |
| 633 | order_info not confirmed | `apply_post_invoice_confirms` R1, R4 |
| 636 | items not confirmed | `apply_post_invoice_confirms` R2, R4 |
| 639 | invoice not confirmed | `apply_post_invoice_confirms` R3 |
| 653 | order not found | `mark_order_complete` R1 |
| 655 | already completed | `mark_order_complete` R2 |
| (none) | no row lock before the R2 check | `mark_order_complete` R10 (BUG-720) |
| 658 | invoice not confirmed | `mark_order_complete` R3 |
| 662 | lines not done (both helpers) | `mark_order_complete` R4 |
| 670 / return dao status == pending | open return | `mark_order_complete` R5 |
| 692 | not completed | `reopen_for_return` R1, R2 |
| 709 | `invoice_id is None` | `_invoice_payment_status` R1 |
| 712 | invoice found / not | `_invoice_payment_status` R2, R3 |
| 718 | order found | `sync_so_for_linked_invoice` R1, R2 |
| 726 | invoice linked | `sync_so_paid` R1 |
| 727 | status == 'paid' | `sync_so_paid` R1 |
| 728 | unchanged | `sync_so_paid` R2 |
| 732 | label paid / unpaid | `sync_so_paid` R3 |
| 747 | order not found | `list_approvers` R1 |
| 751 | loop over approvers | `list_approvers` R2 |
| 754 | member found / not | `list_approvers` R3 |
| 760 | count approved | `approval_summary` R1 |
| 761, 763, else | required from field / count / 0; no floor when null | `approval_summary` R2 (BUG-736: floor of 1 added) |
| 767 | count ≥ required | `approval_summary` R3 (BUG-736, BUG-362) |
| (removed) | third value (dead code, `approvals_met` removed — Q20) | — |
| 776 | order not found | `add_approver` R1 |
| 779 | not member / not active | `add_approver` R2 |
| 782 | already approver | `add_approver` R3 |
| (none) | order completed/locked not checked | `add_approver` R6 (BUG-737) |
| 791 | profile found / fallback (fallback unreachable — FK cascade, dead code; Gap log G8) | `add_approver` R5 |
| 803 | approver not found | `remove_approver` R1 |
| (none) | order completed/locked not checked | `remove_approver` R4 (BUG-737) |
| 806 | profile found / fallback (fallback unreachable — FK cascade, dead code; Gap log G8) | `remove_approver` R3 |
| 818 | approver not found | `set_approval` R1 |
| 822 | approve / withdraw | `set_approval` R2–R5 |
| 823 | base sections not confirmed | `set_approval` R2 |
| 826 | order completed | `set_approval` R4 |
| 828 | financially locked | `set_approval` R4 |
| 832, 837, 838 | stamp / clear; event type/description, unconditionally (no equal-state check) | `set_approval` R5, R6 (BUG-009: R6 adds the no-op short-circuit) |
| (none) | no row lock before R2–R4 | `set_approval` R7 (BUG-720) |
| 850–860 | straight line | `log_event` R1, R2 |
| 866 | order not found | `list_events` R1 |
| 869 | `performed_by` truthy | `list_events` R3 |

## Gap log
- G1 (sales_manager.cases.md gap G1) — Fact — added a table/column map to Overview › Notes (invoices, returns, product ledger, product avg cost, account tags, workspace membership, completion-code columns, meaning of "live").
- G2 (sales_manager.cases.md gap G2) — Intent → decided (best-practice default, delegated by reviewer) — BUG-727's race-freedom moved to **Integration-only behavior** (needs two connections); mechanism left to the implementer, not asserted at unit level.
- G3 (sales_manager.cases.md gap G3) — Contradiction — `create_delivery_with_items` R10 narrowed to today's checks; new R10a: all BUG-723/724/725/730/362/021 checks run before the delivery row is created, nothing written on rejection (best-practice default, delegated by reviewer).
- G4 (sales_manager.cases.md gap G4) — Intent → decided — R8 message `"Sales order item <id> appears more than once in this delivery"` (best-practice default, delegated by reviewer); Errors table updated.
- G5 (sales_manager.cases.md gap G5) — Intent → decided — R12 404 details `"Account with ID <id> not found"` / `"Factory with ID <id> not found"` / `"Item with ID <id> not found"`, and the check order (after R1, before R2: account → client tag → factory → items) (best-practice default, delegated by reviewer).
- G6 (sales_manager.cases.md gap G6) — Fact — Notes: how Decimals render in the capacity and stock messages (scale follows the in-memory attribute; zero floor renders `0`; stock numbers are integers).
- G7 (sales_manager.cases.md gap G7) — Fact + Intent → decided — Inputs now list `SalesOrderItemInput` fields; range constraints go on both the API input schemas and the shared base schemas the manager validates (best-practice default, delegated by reviewer).
- G8 (sales_manager.cases.md gap G8) — Fact — approver/member `user_id` are NOT NULL FKs to `profiles` with ON DELETE CASCADE, so the `User #<id>` / `None` profile fallbacks are unreachable; `add_approver` R5, `remove_approver` R3, `list_approvers` R4 updated; two dead-code branches logged in `sales_manager.deadcode-staging.md`.
- G9 (sales_manager.cases.md gap G9) — Contradiction — R13 split: range checks are pydantic `ValidationError` (422); the fractional catalog-line check is a manager `ValueError` (400) with `"Delivery line has a fractional quantity; stock requires whole units"` (best-practice default, delegated by reviewer); Errors table split.
- G10 (sales_manager.cases.md gap G10) — Fact — `order_data` input row: invalid `order_data` fails before anything is written; a missing `factory_id` key raises `KeyError('factory_id')` before anything is written.
- G11 (sales_manager.cases.md gap G11) — Intent → decided — R7a locks the requested order-line rows, not the parent order (best-practice default, delegated by reviewer).
- G12 (sales_manager.cases.md gap G12) — Fact — Notes: `complete_delivery` processes delivery lines in unspecified order (no ORDER BY).
- G13 (sales_manager.cases.md gap G13) — Intent → decided — after BUG-722's fix an extra `delivery_status` key is ignored, delivery stored `planned` (best-practice default, delegated by reviewer).
- G14 (sales_manager.cases.md gap G14) — Fact — `update_delivery` R6: a changed non-edit field gets no label; alone it yields `"Delivery <number> updated ()"`.
- G15 (sales_manager.cases.md gap G15) — Fact (traceability) — Notes corrected: the BUG-720 lock rule of `mark_order_complete` is R10.
- G16 (sales_manager.cases.md gap G16) — Contradiction — new `create_sales_order_with_items` R2a: after BUG-728's fix the `Item #<id>` fallback is unreachable here (R12's 404 precedes R2's 409); the fallback is tested only in the `order_catalog_items` spec (best-practice default, delegated by reviewer).
- G17 (sales_manager.verify.md F2) — Fact — `sales_order_items.quantity_refunded` is NOT NULL (default 0), so "None refunded counts as 0" is unreachable through the DB-backed `create_delivery_with_items` R7, `fulfill_service_item` R4 and `_recompute_is_fully_delivered` R1; those rules now say so, and Notes add a G17 entry (the clause stays covered by the pure helpers `all_deliverable_items_delivered` R2 / `all_fulfilment_items_fulfilled` R1). No `None`-refunded DB cases.
- G18 (sales_manager.verify.md F4) — Contradiction — Notes listed `'locked'` as an invoice status while `is_so_financially_locked` R3 said invoices never have it. Checked `app/`: only `'draft'`, `'confirmed'`, `'voided'` are ever written (model comment agrees); `'locked'` appears only in readers. Decided: `'locked'` is a dead value — Notes corrected, R3 clarified, no case designed (best-practice default, delegated by reviewer). Not a bug (no observable wrong behavior); not logged as dead code (a dead tuple element, not a dead branch, shared with `purchase_order_manager` / `purchase_order_service`).
- G19 (coordinator, 2026-11-22) — Fact (wrong citation) — the empty-order 500 was logged against BUG-124, which is the attachment-allowlist bug; P1, `create_sales_order_with_items` R1 and its Errors row now cite BUG-3219 (logged from `sales_service.spec.md` G14). BUG-124 stays named only as the precedent. Status unchanged.
