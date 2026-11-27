# Spec — `app/services/sales_service.py`

> **Status:** APPROVED (2026-11-22; owner answered OQ-SS-1 as OQ-64, option (a); every other item decided under the reviewer's delegation of 2026-11-21; fill-gaps 2026-11-22 closed the 11 case-designer gaps — coordinator decisions applied, the rest decided under the reviewer's delegation of 2026-11-22, see Gap log)
> **Source commit:** e48a092

> **Review round 2026-11-21 (describe, under the reviewer's delegation of 2026-11-21).** House-rule lines and precedent matches are pre-filled. Every new question that is not a genuinely new money, stock, order-workflow or security question was decided by Claude under the delegation and is marked so; none of them is the owner's own answer. One question is money and order workflow and is not covered by any existing answer: **OQ-SS-1** (provisional number, to be renumbered when parked in `docs/testing/owner-questions.md`; it is the sales twin of the purchase order service's "do replacement receipts settle a `replace` return's credit note?", so one owner answer can serve both). Bug IDs are from block BUG-3192 … 3221 (3192–3217 used).
>
> **Apply-review 2026-11-22.** Every pre-filled and delegated answer applied as written. OQ-SS-1 answered by the owner as **OQ-64** (option (a)) → BUG-3217. Q9 (A1) removed as dead code and added to `docs/testing/dead-code-removal-checklist.md`. Bugs logged in `docs/testing/bugs.md`.
>
> **Already decided elsewhere, cited, not asked again:** every rule and bug of `tests/unit/managers/sales_manager.spec.md` (row locks BUG-720, delivery status / ownership / capacity BUG-721…725, numbering BUG-726/727, workspace scope BUG-728/730, client tag BUG-729, refunded quantity BUG-731, delivery edit BUG-732/733/734, ledger note BUG-735, "no approvers" = 1 required BUG-736, approvers frozen after lock BUG-737, ranges BUG-362 / BUG-021, the order-creation `ValueError` → 400 (now BUG-3219; the manager spec logged it under BUG-124, an attachment bug of the same pattern), return-in-progress state RP1–RP7 and BUG-2790); every rule and bug of `sales_order_return_manager.spec.md` (BUG-2760…2765, 2786, 2788, 2796, 2797, OQ-49 → BUG-2791 whose rule is written here, FU-2: replacements go out through a normal delivery, so **no completed-order guard** is added to delivery planning, delivery completion or fulfilment); `product_manager.spec.md` `apply_sale_return` (cost fallback BUG-2794, ledger labels BUG-2783, lock BUG-2770); the invoice freeze and credit-note rules of `account_invoice_manager.spec.md` (O1, F1–F7; `void_invoice` R3a–R3c; BUG-627, 628, 639, 2730, 2731, 2733); the invoice-page fixes of `account_invoice_service.spec.md` that touch sales orders (BUG-2965 finalize from the invoice page, BUG-2966 void unlinks the order, BUG-2967 no void after delivery, BUG-2963 resync builds lines as this service does, BUG-2732 delete unlinks); the DAO specs (`sales_order`, `sales_order_item`, `sales_delivery`, `sales_delivery_item`, `sales_order_return`: orderings BUG-1270, 1271, 2423, 2425, 2442, 2443; numbering BUG-2420…2422, 2440); OQ-26 → BUG-2404 and BUG-1019 (system-only fields); BUG-1205 (sales approval notifications; the service half is stated here).
>
> **Production:** not touched by this module (no rules). **Projects:** not touched.
>
> **Verified by running** (my own throwaway pytest file `test_v_ss.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc3desc\sales\`, unit `db` fixture on `marker_test`, everything rolled back, nothing committed): a missing order / delivery raises plain `ValueError` (`Sales order 999999 not found`, `Delivery 999999 not found`), which the app answers as 500; deliveries and items of an unknown order are `[]`; three lines of 0.50 × 0.25 store line totals 0.13 each but the order total 0.38; confirming both sections drafts a receivable invoice (200.00, `invoice_date` today, order `is_invoiced` True); unconfirming deletes it and logs `invoice_draft_deleted` with metadata `{"invoice_id": null}`; a manually created invoice is deleted when order info is then confirmed (items still unconfirmed); `required_approvals: null` is ignored (stays 2), `updated_by` stays NULL and no event is logged on edit; after finalize an edit still sets `contact_name` to `""` and `required_approvals` to 5; delivery messages `Inventory updated: 1 items, 4.00 units deducted` and `5.00 units remaining to be delivered` (the 5 are directly-fulfilled lines); starting a return on a completed order sets `order_completed` False; a `replace` return of four lines gets a **confirmed payable** credit note 4.84 (lines 1.25, 3.33, 0.13, 0.13); completing it adds one unit to the stock of a directly-fulfilled catalog line (100 → 101), leaves `is_fully_delivered` True, `updated_by` NULL, ledger notes `Return SR-2026-001 for SO-SO-2026-001`; a 0.50 return of a catalog line fails at completion with 400 `Return line has a fractional quantity; stock requires whole units`; cancelling a pending return whose credit note was already voided answers 400 `Invoice is already voided`; completing a delivery with a 0 quantity raises `ValueError` `Sale deduction quantity must be positive` (500). **Read, not run:** the endpoints `app/api/v1/endpoints/sales_orders.py`, `sales_deliveries.py`; the app's exception handlers (`app/main.py`, `app/core/exceptions.py`: no `ValueError` handler, so the catch-all answers 500); the web app's sales order panel (`frontend/src/components/newcomponents/customui/orders/SalesOrderDetailPanel.tsx`: it sends `required_approvals: null` to mean "all approvers", and saves order info before confirming it).

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| H1 | "Create invoice" and "Finalize invoice" check the order and then act without locking it | bug — BUG-3192 | house rule HR-10 |
| H2 | The auto-drafted invoice copies the order's lines in no fixed order | bug — BUG-3193 | house rule HR-6 (+HR-16) |
| H3 | An order's "payment status" is read from an invoice of any workspace | bug — BUG-3194 | house rule HR-16 |
| H4 | The sales order and delivery lists accept `limit` 0 or negative | bug — BUG-3195 | house rule HR-7 |
| P1 | Both invoices are created with an `invoice_amount` of 0.00 | bug — BUG-627 (existing) | owner (BUG-627) |
| P2 | Invoice and credit-note dates are the server's local date | bug — BUG-3196 | precedent BUG-3063 / BUG-1334 |
| P3 | A missing sales order or delivery answers 500 | bug — BUG-3197 | precedent BUG-940 |
| P4 | "Complete delivery" lets the manager's refusals reach the client as 500 | bug — BUG-3198 | precedent BUG-940 / BUG-124 |
| P5 | An empty order is a 500 | bug — BUG-3219 | precedent (manager spec P1; re-cited from BUG-124, Gap log G14) |
| P6 | An edit can set the total, "fully delivered", "invoiced" and the invoice link | bug — BUG-2404, BUG-1019 (existing) | owner (OQ-26), owner 2026-10-30 |
| P7 | An edit cannot clear a field (e.g. back to "all approvers") | bug — BUG-3199 | precedent BUG-732 / BUG-753 |
| P8 | Order edits, return completion and return cancellation never record who did them | bug — BUG-3200 | precedent BUG-733 (HR-9) |
| P9 | Changing the required approvals keeps the approvals already given | bug — BUG-3201 | precedent OQ-55 / BUG-2903 (owner) |
| P10 | Stock ledger notes of a return read "SO-SO-2026-…" | bug — BUG-3202 | precedent BUG-735 |
| P11 | A blank (spaces only) cancel reason is accepted | bug — BUG-3203 | precedent BUG-626 / BUG-3064 |
| P12 | The "draft invoice deleted" log entry records no invoice id | bug — BUG-3204 | precedent BUG-2968 |
| P13 | The order total is summed from unrounded line totals | bug — BUG-3205 | precedent BUG-2876 (HR-15) |
| P14 | "Units remaining to be delivered" ignores refunded quantity | bug — BUG-3206 | precedent BUG-731 |
| P15 | A completed or invoice-locked order can still be edited | bug — BUG-3207 | owner OQ-48 refined (RP5) + BUG-737 |
| P16 | An unknown delivery status filter returns an empty list | bug — BUG-3214 | precedent BUG-1961 |
| P17 | Sales order approvers are never notified | bug — BUG-1205 (existing) | owner 2026-11-01 |
| Q1 | Confirmed order info can be changed without unconfirming it | bug — BUG-3208 | delegation |
| Q2 | "Create invoice" by hand works before the sections are confirmed, and the next section click deletes it | bug — BUG-3209 | delegation |
| Q3 | After a `replace` return the order still says "fully delivered" | bug — BUG-3210 | delegation |
| Q4 | A pending return whose credit note was already voided can never be cancelled | bug — BUG-3211 | delegation |
| Q5 | Some order responses show no invoice payment status | bug — BUG-3212 | delegation |
| Q6 | Deliveries, items or delivery lines of an unknown order / delivery answer `[]` instead of 404 | bug — BUG-3213 | delegation |
| Q7 | An order edit leaves no entry in the order's activity log | bug — BUG-3215 | delegation |
| Q8 | "Units deducted" counts lines that moved no stock | bug — BUG-3216 | delegation |
| Q9 | The "order has no customer account" check can never fire | remove | delegation (dead code) |
| OQ-SS-1 | **OWNER** — a `replace` return gets a payable credit note, and delivering the replacement does not settle it | bug — BUG-3217 | owner, OQ-64 (a) |
| G7 | Finalize and start-return refusals show the id of another workspace's invoice / account | bug — BUG-3218 | house rule HR-16 (fill-gaps, coordinator 2026-11-22) |

### House-rule violations — applied automatically
> Overwrite an answer only if the house rule should NOT apply here.

- **HR-10** `create_invoice_for_sales_order` I1, `finalize_sales_order_invoice` F1 — each reads the order, checks its state (invoice linked, sections, approvals, already finalized) and then creates or confirms an invoice, with a plain read. Two "Create invoice" clicks at once both see no invoice and make two drafts, one left orphaned on the account (duplicate side effect, money); a finalize racing an unconfirm or an approval withdrawal finalizes an order whose sections or approvals are gone. The manager's own locks (BUG-720 on `set_section_confirm` / `set_approval`, BUG-621 on the invoice) are not on these paths before the checks. Intended: both read the order row `SELECT … FOR UPDATE` before the first check; the loser sees the new state and gets the normal error (409 / 400). 🐞 BUG-3192
**Answer:** bug — per HR-10 (house rule)
**Resolution:** BUG-3192, pattern `hr-10-unlocked-state-transition` (as BUG-3062). Rules: `create_invoice_for_sales_order` I1, `finalize_sales_order_invoice` F1.
- **HR-6** `_attach_receivable_invoice_to_sales_order` A7 — the draft invoice's lines are copied from the order's `items` relationship, which has no `order_by` (and no workspace filter). The invoice's line numbers 1, 2, 3 therefore follow physical row order, which changes after an update (BUG-1270 verified this for the same rows). Intended: the order's lines of this workspace, `id` ascending, i.e. read through `sales_order_item_dao.get_by_sales_order` (BUG-1270 order), exactly as `account_invoice_service.spec.md` S6a (BUG-2963) rebuilds them; a line row of another workspace under this order id (invalid data, HR-16) is not copied. 🐞 BUG-3193
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-3193, pattern `unordered-pagination`. Rule: `_attach_receivable_invoice_to_sales_order` A7.
- **HR-16** `_attach_invoice_payment_status` PS2 — the payment status is read from `account_invoices` by id only. An order whose `invoice_id` names another workspace's invoice (legacy rows, BUG-1019: `PUT` accepted any `invoice_id`) shows that invoice's payment status in every order response. Intended: only an invoice of the order's own workspace counts; otherwise `invoice_payment_status = None`. 🐞 BUG-3194
**Answer:** bug — per HR-16 (house rule)
**Resolution:** BUG-3194, pattern `cross-workspace-row-exposed`. Rule: `_attach_invoice_payment_status` PS2.
- **HR-7** `get_sales_orders` L3, `get_deliveries` LD3 — `GET /sales-orders/` and `GET /sales-deliveries/` declare `limit` with `le=100` but no lower bound; `limit=0` gives `[]` and a negative `limit` reaches Postgres (`DataError` 2201W, a 500). (Sales order DAO FU-1 (b), delivery DAO FU-1 (b).) Intended: `limit >= 1`, 422 otherwise, on both endpoints. 🐞 BUG-3195
**Answer:** bug — per HR-7 (house rule)
**Resolution:** BUG-3195, pattern `missing-limit-lower-bound` (as BUG-867). Fix in the two endpoints. Rules: `get_sales_orders` L3, `get_deliveries` LD3.

Checked and **not** violated: **HR-1/2/3** — no names stored (the cancel reason is P11). **HR-4** — no sales table has a soft-delete column; the customer account is read with `get_by_id_and_workspace` (BaseDAO scope), a soft-deleted account is then refused by the invoice manager (400). **HR-5** — no filtering after paging. **HR-6** — the order and delivery lists page through BaseDAO `get_by_workspace`, `id` ascending **after open BUG-100** (today no `ORDER BY` at all; Gap log G16), which is the number order and the order BUG-2443 chose for the status-filtered delivery list; the per-order lists follow their DAO rules (BUG-1270, 1271, 2423, 2425, 2442). **HR-8** — no text search. **HR-9** — P8. **HR-10** — besides H1, the transitions are the managers' (BUG-720, BUG-2763, BUG-2764, BUG-2770). **HR-11–14** — no external system or batch. **HR-15** — the credit note's line subtotals are stored rounded half up per line by the `Numeric(15,2)` column and the amount is the sum of the stored lines (verified: 1.25 + 3.33 + 0.13 + 0.13 = 4.84); the order total is P13. **HR-16** — H2, H3; every other read takes the caller's `workspace_id`.

**Permission checks:** none in the service. Every endpoint only needs an active member of the workspace: any member can finalize an invoice, complete an order, start, complete or cancel a return (which creates, confirms or voids a credit note), change the required approvals, and add or remove approvers. Noted for `docs/future/permissions.md`, not a question here.

### Precedent matches — confirm all with ok

### P1. Both invoices are created with an `invoice_amount` of 0.00 — 🐞 BUG-627 (existing, owner)
**Background:** BUG-627 removes `invoice_amount` from `AccountInvoiceCreate`: an invoice's amount is always the sum of its lines, and a request that sends it gets 422.
**What happens today:** the order's draft invoice and the return credit note are both created with `invoice_amount = 0.00`; after the BUG-627 schema change that call would fail with 422.
**Example:** after the fix ships, confirming a sales order's items fails with 422 `invoice_amount` until this service stops sending it.
**Rules affected:** `_attach_receivable_invoice_to_sales_order` A4, `_attach_return_invoice_for_so` RC1
**Answer:** bug — per BUG-627 (owner): no `invoice_amount` is sent; both invoices start at 0.00 and follow their lines (precedent — confirmed: ok, decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** existing BUG-627, no new ID. Rules: A4, RC1.

### P2. Invoice and credit-note dates are the server's local date — 🐞 BUG-3196 (precedent)
**Background:** dates the system sets were ruled to come from the UTC clock (`utcnow()`, BUG-1334; for invoices BUG-3063).
**What happens today:** both invoices get `invoice_date = date.today()`, the local date of the machine running the API.
**Example:** a server on Dhaka time drafts SO-2026-010's invoice at 01:30 on 2 March; in UTC it is still 1 March, but the invoice is dated 2 March.
**Rules affected:** `_attach_receivable_invoice_to_sales_order` A4, `_attach_return_invoice_for_so` RC1
**Answer:** bug — per BUG-3063 / BUG-1334 precedent: `invoice_date = utcnow().date()` (precedent — confirmed: ok, decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** BUG-3196, pattern `local-clock-instead-of-utc`. Rules: A4, RC1.

### P3. A missing sales order or delivery answers 500 — 🐞 BUG-3197 (precedent)
**Background:** the app has no handler for Python's `ValueError`; its catch-all answers 500 "internal server error". `get_sales_order` and `get_delivery` signal "not found" with `ValueError`. `get_sales_order` is the first step of get, edit, create invoice, finalize, fulfil, and every return endpoint.
**What happens today:** `GET /sales-orders/999/`, `PUT /sales-orders/999/`, `POST /sales-orders/999/finalize-invoice/`, `/returns/…` and `GET /sales-deliveries/999/` answer 500 for an unknown id or another workspace's id (verified: `ValueError Sales order 999999 not found`).
**Example:** a user opens an old link to a sales order of another workspace and sees "Something went wrong" instead of "not found".
**Rules affected:** `get_sales_order` G1, `get_delivery` GV1
**Answer:** bug — per BUG-940 precedent: not found answers 404, `Sales order with ID <id> not found` (as the manager's own lookups) and `Delivery with ID <id> not found` (as `complete_delivery` / `cancel_delivery`), nothing written (precedent — confirmed: ok, decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** BUG-3197, pattern `wrong-error-type-uncaught`. Rules: G1, GV1.

### P4. "Complete delivery" lets the manager's refusals reach the client as 500 — 🐞 BUG-3198 (precedent)
**Background:** the sales manager refuses delivery actions with `ValueError`. Planning, editing and cancelling a delivery turn it into 400 with the message; completing does not. The manager's BUG-721 fix ("only a planned delivery can be completed") is such a `ValueError`, meant to reach the API as 400.
**What happens today:** completing a delivery with a 0 quantity answers 500 (`Sale deduction quantity must be positive`, verified); after BUG-721, a second "Mark delivered" click would also answer 500.
**Example:** a driver double-taps "Mark delivered" on DEL-2026-004; once BUG-721 is fixed, the second tap shows "Something went wrong" instead of "Only planned deliveries can be completed (this delivery is 'delivered')".
**Rules affected:** `complete_delivery` DV2
**Answer:** bug — per BUG-940 / BUG-124 precedent: the manager's `ValueError` becomes 400 with its message, as in `create_delivery`, and the whole call is rolled back (precedent — confirmed: ok, decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** BUG-3198, pattern `wrong-error-type-uncaught`. Rule: DV2.

### P5. An empty order is a 500 — 🐞 BUG-3219
**Background / today / example:** `sales_manager.spec.md` P1: the manager raises `ValueError("Sales order must have at least one item")`; the service does not translate it.
**Rules affected:** `create_sales_order_from_dict` C2
**Answer:** bug — per BUG-124 / BUG-940 precedent (pattern `wrong-error-type-uncaught`; manager spec P1, confirmed): the service turns the manager's `ValueError` into 400 with its message (precedent — confirmed: ok)
**Resolution:** BUG-3219, pattern `wrong-error-type-uncaught`. Rule: C2. *(Re-cited 2026-11-22, Gap log G14: this was first logged against BUG-124, which is the attachment-allowlist bug in `app/utils/attachment_allowlist.py`; BUG-124 stays only as a same-pattern precedent.)*

### P6. An edit can set the total, "fully delivered", "invoiced" and the invoice link — 🐞 BUG-2404, BUG-1019 (existing, owner)
**Background:** OQ-26 (owner, 2026-11-10): `total_amount`, `is_fully_delivered`, `is_invoiced` are system-only, an edit that sends them gets 422. BUG-1019 (owner, 2026-10-30): `invoice_id` is system-only.
**What happens today:** `update_sales_order` stores whatever `SalesOrderUpdate` carries, on any order.
**Example:** `PUT /sales-orders/12/` with `{"total_amount": 1}` changes a 12,000 taka order to 1 taka in the orders overview.
**Rules affected:** `update_sales_order` U4
**Answer:** bug — per BUG-2404 / BUG-1019 (owner): the four fields are not accepted; a request that sends any of them gets 422, nothing written (precedent — confirmed: ok)
**Resolution:** existing BUG-2404 and BUG-1019, no new ID. Rule: U4.

### P7. An edit cannot clear a field — 🐞 BUG-3199 (precedent)
**Background:** the edit goes through the generic DAO update, which drops every field sent as `null`. `required_approvals = null` means "every assigned approver must approve"; the web app sends `null` when the user empties the box.
**What happens today:** once `required_approvals` is set it can never go back to "all approvers" (verified: `null` ignored, stays 2); `contact_phone`, `description` and `expected_delivery_date` can be replaced but never emptied.
**Example:** a manager sets SO-2026-031 to "1 approval required", then empties the box to require everyone. The order still needs just 1, and the invoice can be finalized with one approval.
**Rules affected:** `update_sales_order` U5
**Answer:** bug — per BUG-732 / BUG-753 precedent: a field sent as `null` clears it; an omitted field is unchanged (precedent — confirmed: ok, decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** BUG-3199, pattern `exclude-none-blocks-clearing`. Rule: U5. `contact_name` cleared while order info is confirmed is refused by Q1 (U3).

### P8. Order edits, return completion and return cancellation never record who did them — 🐞 BUG-3200 (precedent)
**Background:** sales orders and sales returns have `updated_by` ("last changed by"). HR-9: written when a field actually changes. BUG-733 ruled the same for deliveries.
**What happens today:** `update_sales_order` takes the user but never writes `updated_by` (verified NULL); completing a return sets `completed_by` but not `updated_by`; cancelling one sets nothing (verified NULL).
**Example:** Bob changes SO-2026-020's contact phone and cancels its return SR-2026-004; both show "updated at 14:02, by —".
**Rules affected:** `update_sales_order` U8, `complete_return` RK7, `void_return` RV4
**Answer:** bug — per BUG-733 precedent (HR-9): `updated_by = user_id` whenever the call changes at least one field (precedent — confirmed: ok, decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** BUG-3200, pattern `hr-9-stamp-never-written`. Rules: U8, RK7, RV4.

### P9. Changing the required approvals keeps the approvals already given — 🐞 BUG-3201 (precedent, owner)
**Background:** OQ-55 (owner, 2026-11-21, transfer orders → BUG-2903): changing required approvals after approving started is allowed, but a real change wipes every approval given so far and everyone approves again. Sales orders have the same field and the same gate (finalize needs approvals met).
**What happens today:** the number changes and every approval stays.
**Example:** SO-2026-044 (18,000 taka) has 3 approvers; Karim approved. Someone lowers "required" from 3 to 1: the order is at once "1 of 1 — met" and the invoice can be finalized on Karim's approval alone, given under the old rule.
**Rules affected:** `update_sales_order` U7
**Answer:** bug — per OQ-55 / BUG-2903 precedent (owner): a real change of `required_approvals` (also to or from `null`) clears every approval per `reset_approvals` with reason `Required approvals changed`; sending the stored value changes nothing (precedent — confirmed: ok, decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** BUG-3201, pattern `approval-rule-change-keeps-approvals`. Rule: U7. After finalize the change is refused (P15).

### P10. Stock ledger notes of a return read "SO-SO-2026-…" — 🐞 BUG-3202 (precedent)
**Background:** order numbers already start with `SO-`; BUG-735 fixed the same doubled prefix on delivery notes.
**What happens today:** a return's ledger note reads `Return SR-2026-001 for SO-SO-2026-001` (verified).
**Example:** the product ledger for "Desk lamp" lists a return with note "… for SO-SO-2026-030".
**Rules affected:** `complete_return` RK5a
**Answer:** bug — per BUG-735 precedent: `Return <return number> for <order number>`, the order number as stored (precedent — confirmed: ok, decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** BUG-3202, pattern `duplicated-prefix-in-formatted-string`. Rule: RK5a.

### P11. A blank cancel reason is accepted — 🐞 BUG-3203 (precedent)
**Background:** `SalesOrderReturnVoidRequest.void_note` only needs one character, so `"   "` passes. It becomes the credit note's void note and the `return_voided` log text. BUG-626 trims and refuses a blank invoice void reason; BUG-3064 did the same for expense orders.
**What happens today:** `"   "` is accepted and stored as typed.
**Example:** SR-2026-007 is cancelled with a space as reason; the log reads "Return SR-2026-007 cancelled —    ".
**Rules affected:** `void_return` RV6
**Answer:** bug — per BUG-626 / BUG-3064 precedent: `void_note` is trimmed and must not be blank (422 at the schema), nothing written (precedent — confirmed: ok, decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** BUG-3203, pattern `blank-name-accepted`; fix in `app/schemas/sales_order_return.py`. Rule: RV6.

### P12. The "draft invoice deleted" log entry records no invoice id — 🐞 BUG-3204 (precedent)
**Background:** deleting the draft clears the order's link before the log entry is written (the ORM nulls the foreign key of the loaded order when the invoice row is deleted). BUG-2968 is the same on purchase orders.
**What happens today:** the entry reads "Draft invoice #1434284 deleted" with metadata `{"invoice_id": null}` (verified).
**Example:** a report built on the log's metadata cannot tell which invoice was removed.
**Rules affected:** `_delete_linked_draft_invoice_for_so` DD4
**Answer:** bug — per BUG-2968 precedent: the metadata carries the deleted invoice's id (precedent — confirmed: ok, decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** BUG-3204, pattern `audit-detail-lost` (as BUG-2968). Rule: DD4.

### P13. The order total is summed from unrounded line totals — 🐞 BUG-3205 (precedent)
**Background:** the endpoint computes each line total as quantity × price (up to 4 decimals) and adds them up before the database rounds each column to 2 decimals. BUG-2876 (HR-15) is the same on purchase orders.
**What happens today:** three lines of 0.50 × 0.25 store line totals 0.13 each (0.39) but an order total of 0.38 (verified). The draft invoice is the sum of the stored lines, so it disagrees with the order total.
**Example:** an order of three half-metres of ribbon at 0.25 taka shows 0.38 taka on the order and 0.39 taka on its invoice.
**Rules affected:** `create_sales_order_from_dict` C3
**Answer:** bug — per BUG-2876 precedent (HR-15): each line total is rounded half up to 2 places when computed, and the order total is the sum of the rounded line totals (precedent — confirmed: ok, decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** BUG-3205, pattern `python-rounding-differs-from-database`. Fix in `app/api/v1/endpoints/sales_orders.py` (`create_sales_order`), which computes both before calling the service. Rule: C3.

### P14. "Units remaining to be delivered" ignores refunded quantity — 🐞 BUG-3206 (precedent)
**Background:** BUG-731: a line is done when delivered + refunded ≥ ordered. After a refund return the refunded units are never delivered again.
**What happens today:** after a delivery the message counts ordered − delivered over every line, so refunded units appear as still to deliver (and an over-delivered line subtracts from the others).
**Example:** "Bolt M10" ordered 10, refunded 2, delivered 8 + a 0-line second delivery: the message says "2 units remaining to be delivered" though nothing is left to ship.
**Rules affected:** `complete_delivery` DV4
**Answer:** bug — per BUG-731 precedent: remaining = the sum over the order's lines of max(0, ordered − delivered − refunded) (precedent — confirmed: ok, decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** BUG-3206, pattern `refunded-quantity-ignored`. Rule: DV4.

### P15. A completed or invoice-locked order can still be edited — 🐞 BUG-3207 (precedent, owner)
**Background:** OQ-48 refined (owner, 2026-11-17): while a return is open a completed order shows "return in progress" and **nothing on the order is editable**; `sales_manager.spec.md` RP5 relies on "the completed-order guards", but `update_sales_order` has none. BUG-737 freezes approvers once the invoice is finalized or the order is complete, for the same reason: the approval record is what the invoice was finalized on.
**What happens today:** `PUT /sales-orders/{id}/` edits a finalized or completed order (verified after finalize: `contact_name` set to `""`, `required_approvals` set to 5).
**Example:** SO-2026-018 (12,000 taka) is completed and its invoice frozen. Someone sets "required approvals" to 5 and clears the contact name; the order now reads "1 of 5 approvals" with no customer contact, on an invoice that was finalized.
**Rules affected:** `update_sales_order` U2
**Answer:** bug — per OQ-48 refined (owner, RP5) and BUG-737: a completed order → 400 `Cannot edit — order is complete`; otherwise a financially locked order (confirmed invoice) → 400 `Cannot edit — invoice is locked`; nothing written (precedent — confirmed: ok, decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** BUG-3207, pattern `inconsistent-sibling-guard`. Rule: U2.

### P16. An unknown delivery status filter returns an empty list — 🐞 BUG-3214 (precedent)
**Background:** deliveries are `planned`, `delivered` or `cancelled`. The list filter takes any text (delivery DAO FU-1 (a)); BUG-1961 ruled an unknown status filter must be refused, not silently matched.
**What happens today:** `?delivery_status=Planned` or `shipped` answers `[]` (200); an empty string means "no filter".
**Example:** a client sends `Delivered` with a capital D and is told there are no delivered deliveries.
**Rules affected:** `get_deliveries` LD2
**Answer:** bug — per BUG-1961 precedent: only `planned`, `delivered`, `cancelled` are accepted, anything else 422 at the endpoint; omitted or empty means no filter (precedent — confirmed: ok, decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** BUG-3214, pattern `unvalidated-code-input`. Fix in `GET /sales-deliveries/`. Rule: LD2.

### P17. Sales order approvers are never notified — 🐞 BUG-1205 (existing, owner)
**Background:** BUG-1205 (owner): sales orders are notified like the other four order types (assigned, ready, section confirm, invoice); `sales_order_approver.spec.md` FU-3 names the service calls.
**What happens today:** this service calls no notification function.
**Example:** Rahim is added as approver on SO-2026-005; nothing reaches his bell.
**Rules affected:** *Notifications* N1–N5
**Answer:** bug — per BUG-1205 (owner): the service calls the approval notification service as FU-3 says (precedent — confirmed: ok)
**Resolution:** existing BUG-1205, no new ID. Which call goes where (N1–N4) decided by Claude under the reviewer's delegation (2026-11-21), following FU-3 and the expense / purchase services.

### New questions

### Q1. Confirmed order info can be changed without unconfirming it — 🐞 BUG-3208
**Background:** an order's "order info" section (contact name and phone, expected delivery date, description) is confirmed with a button; confirming checks the contact name is set, and approvals require it confirmed. Unconfirming wipes the approvals. The edit endpoint does not look at the confirmation. The web app saves its edits before it confirms.
**What happens today:** after order info is confirmed and approved, `PUT` changes the contact name (even to `""`) or the description and the section stays confirmed with every approval kept.
**Example:** SO-2026-050 is confirmed and approved by Nadia with contact "Rahim, 017…". Someone changes the contact to "" through the API; the order still reads "Order info confirmed — approved", and the invoice can be finalized.
**Rules affected:** `update_sales_order` U3
**Answer:** bug — while `order_info_confirmed` is true, an edit that actually changes `contact_name`, `contact_phone`, `expected_delivery_date` or `description` is refused with 400 `Unconfirm order info before editing it`, nothing written; sending the stored values is not a change (decided by Claude under the reviewer's delegation, 2026-11-21: the confirm-then-approve workflow is already decided; this closes a path around it, and the web app already edits only unconfirmed info)
**Resolution:** BUG-3208, pattern `confirmed-section-editable`. Rule: U3.

### Q2. "Create invoice" by hand works before the sections are confirmed, and the next section click deletes it — 🐞 BUG-3209
**Background:** the order's draft invoice is made automatically once order info and items are both confirmed, and deleted when either is unconfirmed. A separate "Create invoice" (`POST /sales-orders/{id}/create-invoice`) makes one by hand.
**What happens today:** the manual path checks nothing but "no invoice yet": it drafts an invoice for an order whose sections are not confirmed, and logs nothing on the order. The next section confirm or unconfirm deletes it, because the sections are not both confirmed (verified: confirming order info alone deleted it).
**Example:** a clerk clicks "Create invoice" on SO-2026-060 before confirming anything; draft #812 for 9,000 taka appears. She then confirms order info; draft #812 is gone and the log says "Draft invoice #812 deleted".
**Rules affected:** `create_invoice_for_sales_order` I3a, I4
**Answer:** bug — the manual path follows the automatic one: order info and items not both confirmed → 400 `Confirm order info and items before creating the invoice`, nothing written; when it creates the draft it logs the same `invoice_draft_created` event as the automatic draft (decided by Claude under the reviewer's delegation, 2026-11-21: the draft rule is already decided; the manual path only retries it)
**Resolution:** BUG-3209, pattern `inconsistent-sibling-guard`. Rules: I3a, I4.

### Q3. After a `replace` return the order still says "fully delivered" — 🐞 BUG-3210
**Background:** `is_fully_delivered` is stored on the order and recomputed after each delivery and fulfilment. Completing a return lowers the returned lines' delivered quantity; a `replace` return leaves a gap that must be delivered again.
**What happens today:** return completion does not recompute the flag: after a `replace` return of 1 of 4 chairs the order still shows "fully delivered" (verified), until the replacement delivery recomputes it.
**Example:** SO-2026-040 delivered 4 chairs; one comes back for replacement. The order list still shows SO-2026-040 as fully delivered, so nobody plans the replacement.
**Rules affected:** `complete_return` RK9
**Answer:** bug — completing a return recomputes the order's `is_fully_delivered` per `_recompute_is_fully_delivered` (BUG-731 rule: delivered + refunded ≥ ordered on every line) (decided by Claude under the reviewer's delegation, 2026-11-21: the sibling paths already recompute; a refund return leaves the flag as it was)
**Resolution:** BUG-3210, pattern `missing-follow-up-sync`. Rule: RK9.

### Q4. A pending return whose credit note was already voided can never be cancelled — 🐞 BUG-3211
**Background:** before the BUG-2788 fix, a return's credit note could be voided on the invoice page while the return stayed `pending`. "Cancel return" voids the credit note first.
**What happens today:** for such a return "Cancel return" answers 400 `Invoice is already voided` (verified), so the return stays pending for ever: it keeps reserving the quantity, and it can still be completed (goods back into stock, nothing owed). A credit-note id pointing into another workspace answers 404 with that id.
**Example:** SR-2026-003's 9,000 taka credit note was voided on the invoice page last month. The user tries to cancel the return and is told the invoice is already voided; the 2 tables stay reserved and can't be returned again.
**Rules affected:** `void_return` RV3a
**Answer:** bug — a credit note that is already `voided`, or not an invoice of this workspace, is not voided again; the return is still cancelled (decided by Claude under the reviewer's delegation, 2026-11-21: nothing about money changes — the note is already void — and it lets old data be cleaned up)
**Resolution:** BUG-3211, pattern `linked-record-not-updated`. Rule: RV3a.

### Q5. Some order responses show no invoice payment status — 🐞 BUG-3212
**Background:** `SalesOrderResponse.invoice_payment_status` is not stored; the service attaches it from the linked invoice. The new `has_open_return` (RP2, BUG-2790) is filled the same way.
**What happens today:** get, list, finalize, mark complete and section confirm attach it; create, create invoice, complete delivery and fulfil do not (or attach a stale value): "Create invoice" answers `null` although the new draft is `unpaid` (verified); update answers the value read before the edit.
**Example:** after "Mark delivered" the order card briefly shows no payment badge, then "Unpaid" after a reload.
**Rules affected:** *Order response* OR1
**Answer:** bug — every method that returns an order attaches `invoice_payment_status` (and `has_open_return`) read after its commit (decided by Claude under the reviewer's delegation, 2026-11-21: display consistency only)
**Resolution:** BUG-3212, pattern `inconsistent-response-enrichment`. Rule: OR1.

### Q6. Deliveries, items or delivery lines of an unknown order / delivery answer `[]` — 🐞 BUG-3213
**Background:** `GET /sales-orders/{id}/` and its returns, approvers and events answer "not found" for an unknown id or another workspace's; three sibling lists do not check.
**What happens today:** `GET /sales-orders/999/deliveries/`, `/sales-orders/999/items/` and `GET /sales-deliveries/999/items/` answer `[]` (200) (verified for the first two).
**Example:** a stale link to another workspace's order shows an empty items list instead of "not found", as if the order had no lines.
**Rules affected:** `get_deliveries_for_order` GD2, `get_sales_order_items` GI2, `get_delivery_items` GDI2
**Answer:** bug — the order (or delivery) is looked up first; unknown or other workspace → 404 `Sales order with ID <id> not found` / `Delivery with ID <id> not found` (decided by Claude under the reviewer's delegation, 2026-11-21: sibling consistency)
**Resolution:** BUG-3213, pattern `inconsistent-sibling-guard`. Rules: GD2, GI2, GDI2.

### Q7. An order edit leaves no entry in the order's activity log — 🐞 BUG-3215
**Background:** every other change to a sales order (sections, approvals, deliveries, returns, invoice) writes an event in the order's activity log.
**What happens today:** `PUT /sales-orders/{id}/` writes none (verified: 0 events), also when it changes the required approvals.
**Example:** the approval rule of SO-2026-044 was changed from 3 to 1; the activity log shows nothing, so nobody can see who changed it or when.
**Rules affected:** `update_sales_order` U9
**Answer:** bug — an edit that changes at least one field logs one event `order_updated`, description `Order updated (<labels>)`, labels of the changed fields in the fixed order `expected delivery date`, `contact name`, `contact phone`, `description`, `required approvals`, joined by `, `; metadata `{"fields": [<field names in that order>]}`; `performed_by = user_id`; no event when nothing changed (decided by Claude under the reviewer's delegation, 2026-11-21: audit, the delivery edit's `delivery_updated` is the model)
**Resolution:** BUG-3215, pattern `missing-audit-event`. Rule: U9.

### Q8. "Units deducted" counts lines that moved no stock — 🐞 BUG-3216
**Background:** a delivery can carry free-text lines (no catalog item): they move no stock.
**What happens today:** the message `Inventory updated: <n> items, <q> units deducted` counts every delivery line.
**Example:** a delivery of 4 chairs and 1 "Installation" reads "Inventory updated: 2 items, 5 units deducted"; only 4 chairs left the stock.
**Rules affected:** `complete_delivery` DV3
**Answer:** bug — `n` and `q` count only lines with a catalog item; with none the message is `No inventory movement` (details `{"item_count": 0, "total_quantity": 0}`) (decided by Claude under the reviewer's delegation, 2026-11-21: message accuracy only)
**Resolution:** BUG-3216, pattern `misleading-message`. Rule: DV3.

### Q9. The "order has no customer account" check can never fire — remove
**Background:** `sales_orders.account_id` is `NOT NULL`.
**What happens today:** `_attach_receivable_invoice_to_sales_order` starts with "no customer account → 422 `Cannot create invoice: sales order has no customer account`"; no stored order can reach it.
**Example:** unreachable.
**Rules affected:** `_attach_receivable_invoice_to_sales_order` A1
**Answer:** remove (decided by Claude under the reviewer's delegation, 2026-11-21: dead code)
**Resolution:** removed — `app/services/sales_service.py:59-63` added to `docs/testing/dead-code-removal-checklist.md` (2026-11-22). A1 is not specified.

### OQ-SS-1. A `replace` return gets a payable credit note, and delivering the replacement does not settle it — 🐞 BUG-3217 (owner, OQ-64)
**Background:** starting any sales return, `refund` or `replace`, at once creates and **confirms** a credit note of type payable ("we owe the customer") for the returned units at their price. A `refund` return then counts the units as refunded. A `replace` return instead lowers the delivered quantity, so the units must be delivered again; that goes through a normal delivery on the (still completed) order, and the order's invoice stays frozen (FU-2, RP1, RP4). Nothing links the replacement delivery to the credit note: it stays confirmed and payable. This is the sales twin of the purchase order question "should receiving a `replace` return's replacements settle that return's credit note?"; one answer can serve both.
**What happens today:** the customer gets the replacement **and** keeps a credit for the same units (verified: a `replace` return made a confirmed payable credit note).
**Example:** SO-2026-040 sold 4 chairs at 3,000 taka (invoice 12,000 taka, paid). One chair arrives broken and the customer wants a new one. A `replace` return creates a 3,000 taka credit note; the broken chair comes back, and a new one is delivered. The customer now has 4 good chairs for 12,000 taka, and accounting still shows 3,000 taka owed to them.
**Rules affected:** `start_return` RS9, `complete_return` RK10, `complete_delivery` DV6a, `fulfill_service_item` FS8a, `_settle_replacement_credit_notes` SR1–SR9 (new)
**Recommended answer:** (a) delivering the replacement settles the credit note.
**Options for the owner:**
- **(a) Delivering the replacement settles the credit note — recommended.** The 3,000 taka credit note is created at the start, as today, so the customer is covered if the new chair can never be sent. Once every replaced unit has gone out again on a delivery, the system cancels that credit note by itself and writes it in the log, so nothing is owed. In the example, the moment the new chair is marked delivered the 3,000 taka credit disappears and the books show the order exactly as sold. If the 3,000 taka was already paid back to the customer before the new chair went out, the system does not cancel it and shows a warning; staff then decide by hand (ask the money back, or bill the new chair).
- **(b) A `replace` return never gets a credit note.** Only goods move: the broken chair comes back, a new one goes out, money never changes. Simplest, and nothing is owed by mistake. But if the replacement can never be sent (out of stock, discontinued), the customer is owed 3,000 taka and someone must make a separate credit note on the invoice page, because the return is already finished.
- **(c) Keep today's behaviour.** Every return, `replace` or `refund`, creates a 3,000 taka credit note that stays owed after the new chair arrives. Someone in accounting must notice it and void it by hand; until then it shows as money owed to the customer and may be paid out.
**Answer:** bug — owner, **OQ-64** (2026-11-22), option (a): the credit note is still created and confirmed when the return starts. Once every replaced unit has been delivered again, it is settled and fully recorded: a non-cash payment entry of method "settled by replacement" with its date, the person who completed the delivery and a link to the delivery; a return event; the delivery record. If money was already refunded on that credit note, nothing is settled automatically: a warning is shown and staff decide.
**Resolution:** BUG-3217, pattern `replacement-does-not-settle-credit` (shared with the purchase order twin, OQ-63). Rules: RS9 ✅ (unchanged), RK10, DV6a, FS8a, new `_settle_replacement_credit_notes` SR1–SR9 *(requires new code: a settlement helper and payment method `settled_by_replacement`)*. [OQ-64](../../../docs/testing/owner-questions.md)

## Overview
`SalesService` is the transaction layer for sales orders, their deliveries, direct fulfilment and returns, called only by `app/api/v1/endpoints/sales_orders.py` and `sales_deliveries.py`. Around `SalesManager` and `SalesOrderReturnManager` it commits or rolls back, maps some errors to HTTP codes, and adds what spans modules: the order's **receivable invoice** (drafted automatically once order info and items are both confirmed, deleted when either is unconfirmed, created by hand as a fallback, confirmed by "Finalize invoice"), the **return credit note** (a payable invoice created and confirmed when a return starts, voided when it is cancelled), the **stock put back** when a return completes (`ProductManager.apply_sale_return`), and the transient `invoice_payment_status` on order responses. Invariants it is meant to protect: a draft invoice exists only while both sections are confirmed and mirrors the order's lines; a finalized order has a confirmed invoice and all three section flags set; a return never reopens a completed order (RP1); stock comes back only for units that took stock out (BUG-2791).

**Callables:** 35 specified (34 existing + the new `_settle_replacement_credit_notes`, BUG-3217) · 2 not specified
**Externals to mock:** `utcnow` — patch `app.services.sales_service.utcnow` (`items_updated_at`, a return's `completed_at`), plus the managers' targets in their specs. `date.today()` (invoice dates, A4/RC1; BUG-3196 changes it to `utcnow`) reads the system clock and is not mocked. Notifications (once BUG-1205 is fixed) are `notifications` rows in the same transaction, not mocked.
**Integration-only behavior:** the HTTP status of a plain `ValueError` (500, through the app's catch-all handler: P3, P4, P5) and of `NotFoundError` (404, RFC 7807 body through `api_exception_handler`) needs the app; at unit level assert the exception type and message. The endpoint rules (HR-7 `limit`, P13 total, P16 status filter) are tested at the endpoint.

### Transaction contract
Every write method follows **TC1–TC6** of `tests/unit/services/base_service.spec.md` (repeated from `department_service.spec.md`, unchanged): manager call(s), invoice / stock / event steps, `_commit_transaction`, `db.refresh` of the returned row(s), all in one `try`; any exception rolls back and is re-raised as the same object. Because invoice and stock steps run inside the `try`, an error there (e.g. 422 `Cannot create invoice: invoicing is disabled for this account` while confirming items, 403 `Invoices are not allowed for this account` while starting a return, 400 fractional stock while completing a return) undoes the whole call, including the manager's change (TC3). **Departures**, stated in the callables:
- `create_delivery`, `cancel_delivery`, `update_delivery` turn the manager's `ValueError` (pydantic `ValidationError` included, a `ValueError` subclass) into a **new** `HTTPException` 400 with `detail = str(error)`, after the rollback; TC3's "same object" does not hold for those. [BUG-3198] `complete_delivery` does the same (intended), and [BUG-3219] `create_sales_order_from_dict` too.
- `complete_delivery` and `fulfill_service_item` return `(order, messages)`; `create_delivery` returns `(delivery, order)`, both refreshed.
- `remove_approver` returns `None` (no refresh).
- Reads (`get_*`, `list_*`, `approval_summary`) follow TC6; `get_sales_order` / `get_sales_orders` only set a transient attribute (PS).

**Row locks (HR-10; exact clauses, coordinator 2026-11-22).** Every lock this service takes is a blocking `FOR UPDATE` (never `NOWAIT`, never `SKIP LOCKED`): the loser waits, then sees the winner's committed state. `FOR UPDATE OF <table>` is used wherever the locking read joins or eager-loads another table (BUG-029 rule); a plain `FOR UPDATE` only on a single-table read. The reads here are all single-table (checked: `SalesOrder`, `SalesOrderReturn` and `AccountInvoice` have no joined eager load on the row itself; `SalesOrderReturnItem.item` is `lazy="joined"` but is loaded only with the lines, in a separate query):

| Rule | Row | Clause |
|---|---|---|
| I1, F1 [BUG-3192] | the order: `SELECT … FROM sales_orders WHERE id = :id AND workspace_id = :ws` | `FOR UPDATE` (single table). The payment-status read of PS that follows is not locked. |
| RK2, RV1 [BUG-2764] | the return: `SELECT … FROM sales_order_returns WHERE id = :id AND workspace_id = :ws` | `FOR UPDATE` (single table) |
| SR1a [BUG-3217] | each candidate credit note: `SELECT … FROM account_invoices WHERE id = :id AND workspace_id = :ws` | `FOR UPDATE` (single table), one per return in return `id` ascending order (a fixed order, so two settling calls cannot deadlock) |
| SR3a (inside `create_payment`) | the credit note again | `FOR UPDATE` (single table; already in the code, a harmless re-lock in the same transaction) |

A query that adds a join to any of these reads (e.g. to filter by status) must switch to `FOR UPDATE OF sales_orders` / `OF sales_order_returns` / `OF account_invoices`.

**Facts for the test designer**
- Import: `from app.services.sales_service import SalesService, sales_service`. `SalesService()` takes no arguments; `.sales_manager` is the `sales_manager` singleton, `.account_invoice_manager` the `account_invoice_manager` singleton; the return manager and `product_manager` are module-level imports (`app.services.sales_service.sales_order_return_manager`, `app.managers.product_manager.product_manager`).
- Methods taking `current_user` need only an object with `.id` (a `Profile`).
- The order's invoice is linked by `sales_orders.invoice_id` (FK `ON DELETE SET NULL`), `invoice_type = "receivable"`, `order_type = "sales_order"`, `order_id` = order id. A credit note is linked by `sales_order_returns.invoice_id`, `invoice_type = "payable"`, same `order_type` / `order_id`.
- Order events: `sales_order_events` (`event_type`, `description`, `metadata`, `performed_by`). Invoice events: `invoice_events`.
- An account that can be invoiced: `Account(is_active=True, is_deleted=False, allow_invoices=True)` of the same workspace (the defaults). Orders need a `statuses` row (default `current_status_id = 10`; see `sales_manager.spec.md` Notes).
- Stock: `products` (`qty` whole units) and `product_ledger`; a catalog line needs a live for-sale product of the order's factory to be delivered.
- **Messages** (DV3, DV4, FS7, SR1b, SR6, SR7) are `app.schemas.response.ActionMessage` objects made by `success_message` / `info_message` / `warning_message` (same module): fields `type` (`MessageType`: `success`, `info`, `warning`, `error`; a `str` enum, so `m.type == "success"` holds), `message` (the text), `details` (`dict` or `None`; `None` when a rule names no details) and `timestamp` (`utcnow()` at creation; not asserted).
- **Amounts in texts** (SR4, SR6, SR7, SR1b): `str()` of the stored `Numeric(…, 2)` `Decimal`, two places, no grouping, no currency sign (`3000.00`, `0.13`, `1000.00`); SR4's word `taka` is part of its text. Quantities in RS7 / RK8 / DV3 / DV4 are `str()` of the `Decimal` sum (see RS7 for which quantities). Decimal-valued `details` entries of the new SR rules (SR7 `paid_amount`) are that same two-place **text**, as the PO twin's `settled_amount` (purchase order service RX8e); existing details (`total_quantity` of DV3) stay `Decimal` as today.
- **Imports and schemas:** `from app.schemas.sales_order import SalesOrderUpdate`; `from app.schemas.sales_delivery import SalesDeliveryCreate, SalesDeliveryEditRequest`; `from app.schemas.sales_order_return import SalesOrderReturnCreate, SalesOrderReturnItemCreate`. `SalesDeliveryCreate` requires `sales_order_id: int` and `delivery_method_id: int`; optional `scheduled_date`, `tracking_number`, `notes` (default `None`) and `delivery_status` (default `'planned'`). `SalesDeliveryEditRequest`: all optional `scheduled_date`, `delivery_method_id`, `tracking_number`, `notes`.
- **Delivery methods:** `app.models.delivery_method.DeliveryMethod`, table `delivery_methods`: `workspace_id` and `name` required; `is_active` default `True`, `is_deleted` default `False`; audit columns nullable.

**Notes for the test designer**
- Session and commits as in `base_service.spec.md` Notes: assert "committed" with a test-level `db.rollback()` and a re-select.
- The fastest way to a finalized order: create it through the service, confirm `order_info` and `items` with `set_section_confirm`, approve as the creator (`set_approval(..., approved=True)`; the creator is the only approver), then `finalize_sales_order_invoice`. Lines with `requires_delivery = False` can then be fulfilled with `fulfill_service_item`; lines that require delivery need `create_delivery` + `complete_delivery` and stock.
- `create_sales_order_from_dict` takes the endpoint's dicts: each line needs `item_id` (may be `None`), `description` for a free-text line, `quantity_ordered`, `unit_price`, `line_total`, `requires_delivery`.
- A legacy "pending return with a voided credit note" (Q4) is made by calling `account_invoice_manager.void_invoice` on the credit note directly (today it leaves the return pending; after BUG-2788 the return becomes `voided`, so Q4's case then needs the return status set back to `pending` by hand).
- Row-lock rules (H1): capture SQL with a `before_cursor_execute` listener and look for `FOR UPDATE` on `sales_orders` before the first state check.
- The returned order of `complete_delivery` / `fulfill_service_item` is the same identity-map object a test may already hold; to see OR1's missing attribute, expire the session (`db.expire_all()`) before the call.

## Not specified
- `SalesService.__init__` — wires the two managers, no logic.
- `sales_service` — module singleton.
- `_attach_receivable_invoice_to_sales_order` A1 (no customer account) — dead code, to be removed (Q9).

---

## Shared: Order response (OR)
Not a callable; the fields every returned `SalesOrder` carries for `SalesOrderResponse`.
- **OR1.** [BUG-3212] Every method that returns an order (`create_sales_order_from_dict`, `get_sales_order`, `get_sales_orders`, `update_sales_order`, `create_invoice_for_sales_order`, `finalize_sales_order_invoice`, `complete_delivery`, `fulfill_service_item`, `mark_order_complete`, `set_section_confirm`; and the order of `create_delivery`) attaches `invoice_payment_status` per `_attach_invoice_payment_status`, read **after** its commit. *(Today: create and complete delivery do not attach it (the response shows `null` unless the object already carried it); fulfil returns the value its pre-check `get_sales_order` attached to the same order object before the fulfil, which `db.refresh` keeps — a fulfil never changes the payment status, so that value is the correct one and OR1 is already met for fulfil (Gap log G17); create invoice attaches it before the invoice exists (`null`, verified); update attaches the value read before the edit.)*
- **OR2.** [BUG-2790] (owner OQ-48 refined; `sales_manager.spec.md` RP2) The same orders carry `has_open_return: bool` = `SalesOrderReturnManager.has_open_return(order id, workspace)` (a `pending` return of this order in this workspace), read at call time, never stored. *(Requires new: the field on `SalesOrderResponse`; today it does not exist.)*
- **OR3.** (RP3) What the order shows is derived from stored completion and OR2: completed and `has_open_return` → "return in progress"; completed and not → "completed"; not completed → its normal state. Nothing on the order is written for it (RP1).

## Shared: Notifications (N) — [BUG-1205]
*(Today: none of these is called; no notification row is ever written by this service.)* Calls of `approval_notification_service` with `entity_type = "sales_order"`, `entity_id` = order id, the order object, inside the same transaction (an error there rolls everything back, TC3). Recipients, texts and active-member filtering are that spec's rules (its R6a/R7a sales branches). Mapping decided by Claude under the reviewer's delegation (2026-11-21), per `sales_order_approver.spec.md` FU-3.
- **N1.** `add_approver`: after the approver row is flushed, `handle_add_approver` with actor `assigned_by`, the new approver's user id and row id.
- **N2.** `set_section_confirm`: after the manager's change, `handle_order_update_notifications` with actor `user_id`, `was_ready` = both sections were confirmed before the call, `section_was_unconfirmed` = the call turned a confirmed section off.
- **N3.** A draft invoice created by `_sync_draft_invoice_for_so` (Y4) or `create_invoice_for_sales_order` (I4): `notify_invoice_action` with action `draft` and the new invoice id.
- **N4.** `finalize_sales_order_invoice`: `notify_invoice_action` with action `confirmed`.
- **N5.** Nothing else notifies: deliveries, fulfilment, completion, returns, approvals given or withdrawn, removed approvers, edits.

---

## `SalesService._attach_receivable_invoice_to_sales_order(db, order, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes (flush only) · **Visibility:** internal (used by: `_sync_draft_invoice_for_so`, `create_invoice_for_sales_order`, `finalize_sales_order_invoice`)

**Purpose:** Make the order's draft receivable invoice, link it and fill its lines.

**Returns:** `None`; the order has `invoice_id` set; flushed, not committed — except `items_updated_at` (A8), which is set but not flushed.

**Rules (in this order):**
- **A2.** The order's account is read in this workspace; not found (missing, or another workspace's — legacy data, BUG-728) → 422 `Cannot create invoice: customer account was not found in this workspace`, nothing written; no id shown. A soft-deleted account of this workspace is found here and refused by A4.
- **A3.** Account with `allow_invoices = False` → 422 `Cannot create invoice: invoicing is disabled for this account` (checked before the invoice manager's deleted / inactive checks).
- **A4.** The invoice is created per `AccountInvoiceManager.create_invoice` as a `receivable` draft for the order's account: `order_type = "sales_order"`, `order_id` = order id, `description = "Auto-created from sales order <sales_order_number>"`, `notes` = the order's description, `due_date` `None`, no invoice / vendor number, `allow_payments = True`, no payment-lock reason. [BUG-627] No `invoice_amount` is sent; the draft starts at 0.00 and follows its lines. *(Today: `invoice_amount = 0.00` is sent.)* [BUG-3196] `invoice_date = utcnow().date()`. *(Today: `date.today()`, the server's local date.)* Account refusals of `create_invoice` pass through: deleted → 400 `Cannot create invoice for deleted account`, inactive → 400 `Cannot create invoice for inactive account`.
- **A5.** Any 404 from `create_invoice` becomes 422 `Cannot create invoice: customer account was not found in this workspace`, with the 404 as its cause (after A2 this is reachable only through a concurrent change). Any other `HTTPException` passes through unchanged.
- **A6.** The order gets `invoice_id` = the new invoice and `is_invoiced = True`; flushed.
- **A7.** [BUG-3193] The invoice's lines are set per `sync_items_from_list` (draft: lines replaced, amount = sum of line subtotals, one `items_synced` invoice event), one per order line **of this workspace, `id` ascending**, numbered 1…N: `description` = the catalog item's name, else the line's description; when that is empty or `None`, `Item <item_id>` (a free-text line with description `""` gives `Item None`); `item_id`; `source_order_item_id` = the line's id; `source_order_item_type = "so_item"`; `quantity = quantity_ordered`; `unit` = the catalog item's unit, else `None`; `unit_price`; `line_subtotal = line_total` (not recomputed). *(Today: the lines come from the `items` relationship: no order, no workspace filter.)* An order with no lines (impossible through the API) gives a draft with no lines, 0.00.
- **A7a.** [BUG-3220] The receivable invoice's line name follows the same rule as RC3a: the order line's `item_name` trimmed, empty (`None`, `""`, spaces) → `Item <item_id>` for a catalog line, else `Line <line_number>`. *(Today: `item_name or f"Item {item_id}"` — `Item None` for a free-text line with an empty description, spaces copied as typed.)*
- **A8.** The order's `items_updated_at = utcnow()`, set on the order object **after** the helper's last flush: the helper does not flush it, so it is in the database only after the caller's next flush or commit (every caller commits). Read it on the returned object, or after the caller's commit — not after an `expire_all` straight after the helper (Gap log G15).
- **A9.** No order event and no notification here (the callers log / notify).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| A2 | HTTPException 422 | `Cannot create invoice: customer account was not found in this workspace` |
| A3 | HTTPException 422 | `Cannot create invoice: invoicing is disabled for this account` |
| A4 | from `create_invoice` | 400 `Cannot create invoice for deleted account` / `… inactive account`; after BUG-627 nothing else |
| A5 | HTTPException 422 | as A2 |

**Side effects:** invoice row + `created` / `items_synced` events + lines; order `invoice_id`, `is_invoiced` (flushed), `items_updated_at` (set, not flushed; A8).

---

## `SalesService._delete_linked_draft_invoice_for_so(db, order, workspace_id, user_id)`
**Shape:** delete · **Persistence:** writes (flush only) · **Visibility:** internal (used by: `_sync_draft_invoice_for_so`)

**Purpose:** Remove the order's draft invoice when its sections are no longer both confirmed.

**Rules:**
- **DD1.** No `invoice_id` → nothing happens.
- **DD2.** The invoice is not an invoice of this workspace, or its status is not `draft` (`confirmed`, `voided`) → nothing happens: the order keeps its link (a voided invoice stays linked until BUG-2966 unlinks it on the invoice page).
- **DD3.** A draft → deleted per `AccountInvoiceManager.delete_invoice` (lines and events cascade; a draft with payment history → 400 `Invoice has payment history — confirm and void it instead`, **open BUG-639** (today the delete hits `invoice_payments.invoice_id NOT NULL`: `IntegrityError`, still rolled back; Gap log G18), and the whole call is undone; a draft of a completed order would be refused per F4/F5, but a completed order cannot be unconfirmed). Then the order is unlinked per `SalesManager.unlink_invoice_from_so`: `invoice_id = None`, `invoice_confirmed = False`, `is_invoiced = False`, `paid = False`; one event `invoice_draft_deleted`, description `Draft invoice #<id> deleted`, `performed_by = user_id`.
- **DD4.** [BUG-3204] That event's metadata is `{"invoice_id": <deleted invoice id>}`. *(Today: `{"invoice_id": null}` — verified; the link is cleared when the invoice row is deleted, before the event is written.)*

---

## `SalesService._sync_draft_invoice_for_so(db, order, workspace_id, user_id)`
**Shape:** helper · **Persistence:** writes (flush only) · **Visibility:** internal (used by: `set_section_confirm`)

**Purpose:** Keep "a draft invoice exists exactly while both sections are confirmed".

**Returns:** the new invoice id when a draft was created, else `None`.

**Rules (first match applies):**
- **Y1.** The order is financially locked (its linked invoice of this workspace is `confirmed`, per `is_so_financially_locked`) → `None`, nothing happens.
- **Y2.** Order info and items not both confirmed → the linked draft, if any, is removed per DD1–DD4; `None`.
- **Y3.** Both confirmed and an invoice is already linked (draft, voided, or not of this workspace) → `None`, nothing happens.
- **Y4.** Both confirmed, no invoice → a draft per A2–A8, then one order event `invoice_draft_created`, description `Draft invoice #<id> linked to <sales_order_number>`, metadata `{"invoice_id": <id>}`, `performed_by = user_id`; [BUG-1205] then N3; returns the id. Refusals of A2–A5 pass through (the caller rolls back).

---

## `SalesService.create_invoice_for_sales_order(db, order_id, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /sales-orders/{id}/create-invoice`)

**Purpose:** Make the order's draft invoice by hand (retry of the automatic draft).

**Returns:** the order, committed and refreshed (payment status per OR1).

**Rules (in this order):**
- **I1.** [BUG-3192] The order is read per `get_sales_order` (G1; 404 after BUG-3197) with a row lock — `SELECT … FROM sales_orders … FOR UPDATE` (single table; see Row locks) — before any check. *(Today: plain read.)*
- **I2.** An invoice is linked (any status) → 409 `Invoice already exists for this sales order`, nothing written.
- **I3.** No invoice linked but `is_invoiced = True` → the same 409. (Reached today after the draft was deleted on the invoice page, which leaves the flag set; BUG-2732 clears it there.)
- **I3a.** [BUG-3209] Order info and items not both confirmed → 400 `Confirm order info and items before creating the invoice`, nothing written. *(Today: not checked; the draft is made and the next section confirm or unconfirm deletes it — verified.)*
- **I4.** Otherwise a draft per A2–A8; [BUG-3209] the order event `invoice_draft_created` as Y4 *(today: no event)*; [BUG-1205] N3; committed.
- **I5.** Approvals and completion are not checked (a finalized order already has an invoice, I2).

**Errors:** G1; I2/I3 409; I3a 400; A2–A5.

---

## `SalesService.finalize_sales_order_invoice(db, order_id, workspace_id, user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST /sales-orders/{id}/finalize-invoice/`)

**Purpose:** Confirm the order's invoice and lock the order's sections.

**Returns:** the order, committed, refreshed, with `invoice_payment_status`.

**Rules (in this order):**
- **F1.** [BUG-3192] Order read per `get_sales_order` with a row lock — `SELECT … FROM sales_orders … FOR UPDATE` (single table; see Row locks) — before F2. *(Today: no lock.)*
- **F2.** Order info and items not both confirmed → 400 `Confirm order info and items before finalizing`, nothing written.
- **F3.** Approvals not met per `SalesManager.approval_summary` (BUG-736: no approvers and no explicit number → 1 required) → 400 `Requires <required> approval(s); <approved_count> so far`, nothing written.
- **F4.** `invoice_confirmed` already true → 409 `Invoice is already finalized`, nothing written.
- **F5.** No invoice linked → a draft per A2–A8 (fallback; no `invoice_draft_created` event).
- **F6.** The linked invoice is confirmed per `AccountInvoiceManager.confirm_invoice` (amount = sum of its lines, status `confirmed`, event `confirmed`). Its refusals pass through and undo everything: a voided invoice (still linked before BUG-2966) → 400 `Voided invoices cannot be confirmed`; an invoice confirmed earlier on the invoice page with the order's flags unset (before BUG-2965) → 400 `Invoice is already confirmed`; an invoice id of another workspace (legacy) → 404 `Invoice with ID <id> not found` *(today; see F6a)*.
- **F6a.** [BUG-3218] (HR-16) A linked invoice that is not an invoice of this workspace (invalid data) is left alone — not confirmed, not unlinked — and the call is refused with 404 `The order's invoice was not found in this workspace`, with no id; nothing written. The check is the service's own, before F6 (the invoice manager's text keeps its id for its other callers, where the id is the caller's own input). *(Today: 404 `Invoice with ID <other workspace's id> not found`.)*
- **F7.** Then `SalesManager.apply_post_invoice_confirms` (order info / items flags set with their "after invoice finalized" events when they were off; `invoice_confirmed = True`), then one event `invoice_confirmed`, description `Invoice #<id> confirmed — order locked`, metadata `{"invoice_id": <id>}`, `performed_by = user_id`; [BUG-1205] N4; committed.
- **F8.** From then on the order is financially locked (sections and approvals frozen per the manager) and, once completed, its invoice is frozen (F2 of the invoice manager).

**Errors:** G1; F2, F3 400; F4 409; A2–A5; F6.

---

## `SalesService.create_sales_order_from_dict(db, order_data, items_data, workspace_id, current_user)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /sales-orders/`)

**Returns:** the new order, committed and refreshed.

**Rules:**
- **C1.** The order is created per `SalesManager.create_sales_order_with_items` (all its rules and errors: lines, number, creator as approver, `created` event) with `user_id = current_user.id`, and committed.
- **C2.** [BUG-3219] The manager's `ValueError` (`Sales order must have at least one item`) reaches the client as 400 with that message, after the rollback. *(Today: passed on unchanged, a 500.)*
- **C3.** [BUG-3205] (endpoint) Each line's `line_total` is quantity × price rounded half up to 2 places, and `order_data["total_amount"]` is the sum of the rounded line totals. *(Today: unrounded products summed — three lines of 0.50 × 0.25 give lines 0.13 and a total 0.38, verified.)* The service stores both as given.
- **C4.** No invoice, no stock, no notification.

---

## `SalesService.get_sales_order(db, order_id, workspace_id)`
**Shape:** get-or-404 · **Persistence:** reads · **Visibility:** public (`GET /sales-orders/{id}/`; first step of most methods here)

**Rules:**
- **G1.** [BUG-3197] An order not in this workspace (unknown id, or another workspace's) → `HTTPException` 404 `Sales order with ID <id> not found`. *(Today: `ValueError("Sales order <id> not found")`, a 500 — verified.)*
- **G2.** Otherwise the order, with `invoice_payment_status` per PS (and `has_open_return`, OR2). TC6.

---

## `SalesService.get_sales_orders(db, workspace_id, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /sales-orders/`)

**Rules:**
- **L1.** The workspace's orders per BaseDAO `get_by_workspace`: `id` ascending after BUG-100 (today no `ORDER BY`; rows usually, not always, come back in insertion order), then `skip` / `limit` (defaults 0 / 100; the endpoint passes `skip ≥ 0`, `limit ≤ 100`, default 100). Another workspace's orders never appear.
- **L2.** Each order carries `invoice_payment_status` per PS (one query for the page). TC6.
- **L3.** [BUG-3195] (endpoint) `limit < 1` → 422. *(Today: `0` → `[]`; negative → database error, 500.)*

---

## `SalesService._attach_invoice_payment_status(db, orders)`
**Shape:** mapper · **Persistence:** reads · **Visibility:** internal (used by: `get_sales_order`, `get_sales_orders`, `finalize_sales_order_invoice`, `mark_order_complete`, `set_section_confirm`)

**Purpose:** Put the linked invoice's payment status on each order (transient attribute, not stored).

**Rules:**
- **PS1.** No order in the list has an invoice (or the list is empty) → every order gets `invoice_payment_status = None`; no query.
- **PS2.** [BUG-3194] Otherwise each order gets the `payment_status` (`unpaid`, `partial`, `paid`, `overdue`) of its linked invoice **when that invoice belongs to the order's workspace**; an order with no invoice, or whose invoice id is not an invoice of its workspace, gets `None`. *(Today: the invoice is read by id only, so another workspace's invoice gives its status.)*
- **PS3.** An `invoice_id` with no invoice row → `None`.
- **PS4.** Nothing is written; the attribute is not a column and does not survive a new query of the order.
- **PS5.** Returns `None`; the result is only the attribute set on each order object passed in.

---

## `SalesService.update_sales_order(db, order_id, workspace_id, order_update, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (`PUT /sales-orders/{id}/`, body `SalesOrderUpdate`)

**Purpose:** Edit the order's contact, dates, description and approval rule.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| order_update | `SalesOrderUpdate` | all optional: `expected_delivery_date`, `contact_name`, `contact_phone`, `description`, `required_approvals` (int, no range today — BUG-362 makes it null or ≥ 1); [BUG-2404, BUG-1019] `total_amount`, `is_fully_delivered`, `is_invoiced`, `invoice_id` are removed (422) *(today: accepted)* |

**Returns:** the order, committed and refreshed (payment status per OR1).

**Rules (in this order):**
- **U1.** Order read per `get_sales_order` (G1).
- **U2.** [BUG-3207] Completed (`order_completed`) → 400 `Cannot edit — order is complete`; otherwise financially locked (`is_so_financially_locked`) → 400 `Cannot edit — invoice is locked`; nothing written. Holds also while a return is open ("return in progress", RP5). *(Today: not checked — verified edits after finalize.)*
- **U3.** [BUG-3208] While `order_info_confirmed` is true, an actual change of `contact_name`, `contact_phone`, `expected_delivery_date` or `description` → 400 `Unconfirm order info before editing it`, nothing written; values equal to the stored ones are not a change. `required_approvals` is not order info and is not refused by U3. *(Today: not checked.)*
- **U4.** [BUG-2404, BUG-1019] A request carrying `total_amount`, `is_fully_delivered`, `is_invoiced` or `invoice_id` is refused with 422 before the service runs, nothing written. *(Today: stored as sent, on any order.)*
- **U5.** [BUG-3199] Each field sent with a value is written as given; sent as `null` it is cleared (`required_approvals = null` = every assigned approver); omitted, unchanged. *(Today: `null` is dropped like an omitted field — verified `required_approvals` stays 2.)*
- **U6.** `required_approvals` values follow the manager's BUG-362 range (null or ≥ 1, 422).
- **U7.** [BUG-3201] (OQ-55 precedent) When `required_approvals` actually changes (also to or from `null`), every given approval is cleared per `SalesManager.reset_approvals` with reason `Required approvals changed` (one `approvals_reset` event when at least one was approved). *(Today: approvals kept.)*
- **U8.** [BUG-3200] When at least one field changes, `updated_by = user_id`. *(Today: never written — verified NULL.)* `updated_at` moves by `onupdate` on any flushed change.
- **U9.** [BUG-3215] When at least one field changes, one event `order_updated`, description `Order updated (<labels>)` (labels `expected delivery date`, `contact name`, `contact phone`, `description`, `required approvals`, in that order, `, `-joined), metadata `{"fields": [<field names in that order>]}`, `performed_by = user_id`, logged after U7's event. No event when nothing changed. *(Today: none — verified.)*
- **U10.** No invoice step: a draft invoice exists only while order info is confirmed, which U3 keeps unchanged, so the draft's `notes` (the description) cannot drift. No notification.

**Errors:** G1; U2 400; U3 400; U4 / U6 422.

---

## `SalesService.create_delivery(db, delivery_in, delivery_items_data, workspace_id, current_user)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /sales-deliveries/`)

**Returns:** `(delivery, order)`, both committed and refreshed; the endpoint returns the delivery.

**Rules:**
- **DC1.** The delivery is planned per `SalesManager.create_delivery_with_items` with `delivery_in.model_dump()` and `user_id = current_user.id` (all its rules: order in workspace, invoice finalized, ownership, capacity, `delivery_planned` event; BUG-720…725, 730), committed.
- **DC2.** A `ValueError` from the manager (pydantic `ValidationError` included) → rolled back, then a new `HTTPException` 400 with `detail = str(error)` (e.g. `Finalize the invoice before planning a delivery`). Other exceptions pass through unchanged (TC3).
- **DC3.** (FU-2, owner freeze) No completed-order check: on a completed order whose lines have a gap (after a `replace` return) a delivery can be planned; the order stays completed and its invoice frozen. No notification.

---

## `SalesService.complete_delivery(db, delivery_id, workspace_id, current_user, actual_delivery_date=None, completion_code=None)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST /sales-deliveries/{id}/complete/`)

**Returns:** `(order, messages)`; the order committed and refreshed.

**Rules:**
- **DV1.** A delivery not in this workspace → `NotFoundError` (404) `Delivery with ID <id> not found`, nothing written.
- **DV2.** The delivery is completed per `SalesManager.complete_delivery` (status, quantities, stock out, `is_fully_delivered`, `delivery_completed` event; BUG-720, 721, 733, 734, 735). [BUG-3198] A `ValueError` from it (e.g. `Only planned deliveries can be completed (this delivery is 'delivered')`, `Sale deduction quantity must be positive`) → rolled back, then 400 with its message. *(Today: passed on unchanged, a 500 — verified for a 0 quantity.)* Its `HTTPException`s pass through unchanged: fractional 400 `Delivery line has a fractional quantity; stock requires whole units`; insufficient stock 422 `Insufficient sellable stock for item <item_id> at factory <factory_id>: requested <q>, available <a>` (`available` 0 when there is no stock row; both ids are this workspace's).
- **DV3.** Messages, in order: success `Delivery <delivery_number> marked as completed`; then info `Inventory updated: <n> items, <q> units deducted`, details `{"item_count": n, "total_quantity": q}`, where today `n` = the number of the delivery's lines (this workspace) and `q` = the sum of their `quantity_delivered` as stored (`4.00`; no lines → `0`). [BUG-3216] `n` and `q` count only lines with a catalog item; with none the message is `No inventory movement` with details `{"item_count": 0, "total_quantity": 0}`. *(Today: every line, free-text included.)*
- **DV4.** Then, when the order's `is_fully_delivered` is true: success `Sales order <sales_order_number> is now fully delivered`; otherwise info `<remaining> units remaining to be delivered` (no details), where remaining sums over all the order's lines (this workspace, delivery and direct-fulfilment lines alike) [BUG-3206] max(0, ordered − delivered − refunded). *(Today: ordered − delivered, refunded ignored and no floor; verified `5.00 units remaining to be delivered` where all 5 were directly fulfilled lines.)*
- **DV5.** Committed; the order refreshed; its payment status per OR1.
- **DV6.** (FU-2) No completed-order check: a replacement delivery on a completed order completes like any other; the order stays completed. No notification.
- **DV6a.** [BUG-3217] (owner OQ-64) After the delivery is completed and before the commit, the order's `replace` returns are settled per `_settle_replacement_credit_notes` with this delivery and `current_user.id`, in the same transaction (a failure there undoes the delivery too). Its messages are appended after DV4. *(Today: nothing settles; the credit note stays confirmed and payable — verified.)*

---

## `SalesService.cancel_delivery(db, delivery_id, workspace_id, user_id=None)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST /sales-deliveries/{id}/cancel/`)

**Rules:**
- **DX1.** A delivery not in this workspace → `NotFoundError` (404) `Delivery with ID <id> not found`.
- **DX2.** Cancelled per `SalesManager.cancel_delivery` (only `planned`; BUG-720, 733); its `ValueError` → rolled back, then 400 with its message (`Only planned deliveries can be cancelled (this delivery is '<status>')`); committed; returns the delivery refreshed.

---

## `SalesService.update_delivery(db, delivery_id, workspace_id, data, user_id=None)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (`PATCH /sales-deliveries/{id}/`, body `SalesDeliveryEditRequest`)

**Rules:**
- **DU1.** A delivery not in this workspace → `NotFoundError` (404) `Delivery with ID <id> not found`.
- **DU2.** Edited per `SalesManager.update_delivery` (only `planned`; BUG-730, 732, 733); its `ValueError` → rolled back, then 400 with its message — a non-planned delivery: `Only planned deliveries can be edited (this delivery is '<status>')`; committed; returns the delivery refreshed.

---

## `SalesService.fulfill_service_item(db, order_id, order_item_id, workspace_id, current_user, completion_code=None)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST /sales-orders/{id}/items/{item_id}/fulfill/`)

**Returns:** `(order, messages)`; the order committed and refreshed.

**Rules (in this order):**
- **FS1.** The line is not in this workspace → `NotFoundError` (404) `Sales order item <order_item_id> not found`.
- **FS2.** The line belongs to another order → 400 `Sales order item <order_item_id> does not belong to sales order <order_id>`.
- **FS3.** The line requires delivery → 422 `This line requires delivery — use the delivery workflow, not direct fulfillment`.
- **FS4.** The order is read per `get_sales_order` (always found after FS1–FS2).
- **FS5.** The order's invoice is not finalized → 422 `Finalize the invoice before fulfilling this line`.
- **FS6.** Fulfilled per `SalesManager.fulfill_service_item` (BUG-720, 731, 734); its own `ValueError` checks repeat FS1/FS3/FS5 and cannot be reached.
- **FS7.** Messages: success `Line item marked as fulfilled` (also when the manager found nothing to do), then success `Sales order <number> is now fully delivered` when `is_fully_delivered` is true. Committed.
- **FS8.** (FU-2) No completed-order check: after a `replace` return a directly fulfilled line of a completed order can be fulfilled again. No stock moves, no notification.
- **FS8a.** [BUG-3217] (owner OQ-64) After a fulfilment, and before the commit, the order's `replace` returns are settled per `_settle_replacement_credit_notes` with no delivery (the link is the order line) and `current_user.id`; its messages are appended after FS7. *(Today: nothing settles.)*

**Errors:** FS1 404; FS2 400; FS3 422; FS5 422.

---

## `SalesService._settle_replacement_credit_notes(db, order, workspace_id, user_id, delivery=None)` — NEW [BUG-3217]
**Shape:** state-transition · **Persistence:** writes (flush only) · **Visibility:** internal (used by: `complete_delivery` DV6a, `fulfill_service_item` FS8a)
*(Requires new code. Owner OQ-64, 2026-11-22, option (a); same trail as the purchase order twin OQ-63.)*

**Purpose:** When a `replace` return's units have all gone out again, settle its credit note so nothing stays owed to the customer, with a full record.

**Returns:** a list of messages (possibly empty); flushed, not committed.

**Rules:**
- **SR1.** [BUG-3217] Considered: the order's returns of this workspace with `return_type = 'replace'`, `status = 'completed'` and a linked credit note of this workspace whose status is `confirmed` and which has no active "settled by replacement" entry yet, `id` ascending. Pending, voided and `refund` returns are never settled. A credit note that is a draft (unreachable: RC4 confirms it at once) is left alone silently. A credit note that is not an invoice of this workspace (invalid data, HR-16) is left alone too, but gets SR1c's warning (coordinator 2026-11-22, aligned with PO RX8k). A **voided** credit note is not settled either, but gets SR1b's warning (coordinator 2026-11-22; replaces the earlier "skipped silently").
- **SR1a.** [BUG-3217] (HR-10, coordinator 2026-11-22) Before its payments are looked at, each candidate return's credit note is read `SELECT … FROM account_invoices … FOR UPDATE` (single table), in return `id` ascending order, and SR1's "no active settlement yet" and SR7's "no active payment" are judged on the locked row. Two deliveries (or a delivery and a fulfilment) of the same order completing at once: the second waits, then finds the active settlement entry, so SR1 no longer considers that return — exactly one entry, one event, one message.
- **SR1b.** [BUG-3217] (coordinator 2026-11-22, as the PO twin's RX8d) A `replace`, `completed` return whose credit note of this workspace is `voided` and which is fully replaced (SR2) → nothing is written for it and a warning `Return <return_number>: the credit note is voided — no settlement recorded`, details `{"return_id": <id>, "invoice_id": <id>}`. Repeated on every later delivery or fulfilment of the order while it stands, as SR7. Not fully replaced → no message.
- **SR1c.** [BUG-3217] (HR-16, coordinator 2026-11-22, aligned with the PO twin's RX8k; Gap log G13) A `replace`, `completed` return of this workspace that is fully replaced (SR2) and whose `invoice_id` points to an invoice of another workspace → that invoice is not read for update, not paid and not changed; nothing is written for the return; the delivery or fulfilment still goes through and is committed as usual; and `messages` gets a warning (`type = 'warning'`) `Return <return_number>: the credit note could not be found — no settlement recorded`, details `{"return_id": <id>}`. The text and details carry no id of the other workspace (no `invoice_id`). As SR1b, it is repeated on every later delivery or fulfilment while the return stays fully replaced, and it comes after the success and info messages. A return that is not fully replaced gets no message.
- **SR2.** [BUG-3217] A return is "fully replaced" when, for every one of its lines, the order line it names has `quantity_delivered + quantity_refunded ≥ quantity_ordered` (the gap the return opened is closed). Not fully replaced → nothing happens for it, no message. A partial redelivery settles nothing (unlike purchase orders, OQ-63: the sales answer settles only once every replaced unit is delivered).
- **SR3.** [BUG-3217] Fully replaced and the credit note has **no** active (non-voided) payment → one `invoice_payments` row: `invoice_id` = the credit note, `payment_amount` = the credit note's `invoice_amount` (the sum of its lines, each quantity × return price rounded half up, HR-15), `payment_method = "settled_by_replacement"` (non-cash), `payment_date = utcnow().date()`, `created_by = user_id`, `payment_reference` = the delivery's `delivery_number` (or `SO-item-<order_item_id>` for a direct fulfilment), `notes = "Settled by replacement — <delivery_number or 'direct fulfilment'> for <return_number>"`. The credit note's `paid_amount` and `payment_status` follow per the invoice payment rules (→ `paid`); the return's `paid` becomes `True` per `sync_return_paid`.
- **SR3a.** [BUG-3217] (coordinator 2026-11-22) The entry is recorded through the normal payment path, `InvoicePaymentManager.create_payment`, so it leaves the same trail as any payment: the credit note read `FOR UPDATE`; the `confirmed` status check (always met after SR1); the `invoice_payments` row with `workspace_id` and `created_by = user_id`; `paid_amount += amount`, `payment_status = 'paid'`; one financial audit row (`entity_type 'payment'`, `action_type 'created'`, `related_entity_type 'invoice'`, `related_entity_id` = the credit note, changes `after` {`payment_amount`, `payment_date`, `payment_method`} and `invoice_status_changed` {`before`: `unpaid`, `after`: `paid`}, `performed_by = user_id`); one invoice event `payment_recorded`, description `Payment recorded`, metadata `{"payment_id", "payment_amount": "<amount>", "payment_method": "settled_by_replacement", "payment_status_before": "unpaid", "payment_status_after": "paid"}`; then the return's `paid` sync. **One exception, stated explicitly:** the `allow_payments` refusal (403 with `payment_locked_reason`) does **not** apply to a settlement. It is not cash, and a payment lock on the credit note must not keep the customer's credit owed after the goods went out (*requires new: a flag on `create_payment`, e.g. `is_settlement=True`, that skips only that check*). The outstanding-amount check stays and always passes (amount = `invoice_amount`, nothing paid).
- **SR3c.** [BUG-3217] (one link scheme with the PO twin, purchase order service Overview "Settlement link columns" / RX8b) The entry is linked through the new nullable columns `invoice_payments.source_type` (String(50)) and `source_id` (Integer): `source_type = 'sales_order_event'`, `source_id` = the id of SR4's `return_replacement_settled` row in `sales_order_events`. That event names the delivery (`delivery_id`, or `null` for a direct fulfilment), so the link reaches the delivery through it; `payment_reference` (SR3) also carries the delivery number. Order of writes: the payment (SR3a), then the event (SR4, with `payment_id`), then `source_id` set on the payment, all flushed in the same transaction. Ordinary payments leave both columns `NULL`. *(Requires new columns, shared with BUG-3176.)*
- **SR3b.** [BUG-3217] (decided under the reviewer's delegation, 2026-11-22) A fully replaced return whose credit note amount is 0.00 (returned at price 0) → no entry (a payment must be above 0), no event, no message; the note is already `paid` at 0.00.
- **SR4.** [BUG-3217] For each settled return one order event `return_replacement_settled`, description `Return <return_number> settled by replacement — <amount> taka credit cleared`, metadata `{"return_id", "invoice_id", "payment_id", "delivery_id"}` (`delivery_id` `null` for a direct fulfilment), `performed_by = user_id`.
- **SR5.** [BUG-3217] The delivery record is the delivery trail: its `delivery_completed` event (sales manager) and the settlement's `delivery_id` and `payment_reference` link it to the return; no extra delivery column is written.
- **SR6.** [BUG-3217] Message per settled return: success `Return <return_number>: credit note settled by replacement (<amount>)`.
- **SR7.** [BUG-3217] Fully replaced but the credit note already has an active payment (money refunded to the customer) → **nothing is written** for that return (no settlement entry, no event; credit note and return unchanged) and a warning message `Return <return_number>: the credit note already has <paid_amount> refunded — the replacement was delivered too; settle it by hand`, details `{"return_id", "invoice_id", "paid_amount"}`. It is repeated on every later delivery or fulfilment of the order while the case stands.
- **SR8.** [BUG-3217] The settlement entry is an ordinary payment: it is never deleted, only voided with a reason, per the invoice payment manager's void rules; voiding it makes the credit note payable again, and SR1 then considers the return again on the next delivery or fulfilment.
- **SR8a.** [BUG-3217] (owner OQ-63 / OQ-64, coordinator 2026-11-22; same rule and text as the PO twin's RX8h) A settlement entry can be neither edited nor deleted: `InvoicePaymentManager.update_payment` (any field — method, reference, notes, date, bank, transaction id) and `delete_payment` refuse a payment with `payment_method = 'settled_by_replacement'` with 400 `A settlement by replacement cannot be deleted or edited — void it with a reason instead`, nothing written (fix lives in `app/managers/invoice_payment_manager.py`). *(Today: non-amount edits and deletes are allowed for any payment.)*
- **SR8c.** [BUG-3217] (same rule and text as the PO twin's RX8m) The method is reserved for the system: `create_payment` called from `POST /invoice-payments/` (without the internal settlement flag of SR3a) and `update_payment` refuse `payment_method = 'settled_by_replacement'` with 400 `"settled_by_replacement" is recorded by the system and cannot be entered by hand`, nothing written (fix in `app/managers/invoice_payment_manager.py`). *(Today: any text is accepted as a method.)*
- **SR8b.** [BUG-3217] Voiding it (`void_payment`, reason required, `VoidPaymentRequest.void_note` at least 1 character) sets `is_voided`, `voided_at`, `voided_by`, `void_note`; the credit note's `paid_amount` is recomputed from the remaining active payments (→ 0.00, `unpaid`); one financial audit row (`action_type 'voided'`) and one invoice event `payment_voided`; and the return's `paid` is re-synced to `False` (checked in code: `void_payment` ends with the same linked-order sync as `create_payment`, which finds the return by its credit note and calls `sync_return_paid`). No stock moves.
- **SR9.** No notification.

**Errors:** none of its own; database errors pass through and undo the caller's whole call (TC3). SR8a's and SR8c's 400s are raised by the invoice payment manager, not here.

**Where warnings go (aligned with the PO twin).** The PO side adds a new `warnings: list[str]` field (`[]` when none) to its return response. Sales needs no new field: `complete_delivery` and `fulfill_service_item` already answer an `ActionResponse` (`data`, `messages`), and SR1b / SR7 warnings are `ActionMessage`s of `type = 'warning'` in `messages`, after the success and info messages. A response with no settlement problem carries no warning message (the sales equivalent of `warnings: []`).

---

## `SalesService.get_deliveries_for_order(db, sales_order_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /sales-orders/{id}/deliveries/`)

- **GD1.** The order's deliveries of this workspace per `DAOSalesDelivery.get_by_sales_order` (every status, `id` ascending after BUG-2442, no paging). TC6.
- **GD2.** [BUG-3213] An order not in this workspace → 404 `Sales order with ID <id> not found`. *(Today: `[]` — verified.)*

## `SalesService.get_sales_order_items(db, sales_order_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /sales-orders/{id}/items/`)

- **GI1.** The order's lines of this workspace per `DAOSalesOrderItem.get_by_sales_order` (`id` ascending after BUG-1270). TC6.
- **GI2.** [BUG-3213] An order not in this workspace → 404 `Sales order with ID <id> not found`. *(Today: `[]` — verified.)*

## `SalesService.get_delivery(db, delivery_id, workspace_id)`
**Shape:** get-or-404 · **Persistence:** reads · **Visibility:** public (`GET /sales-deliveries/{id}/`)

- **GV1.** [BUG-3197] Not in this workspace → `NotFoundError` (404) `Delivery with ID <id> not found` (as DV1). *(Today: `ValueError("Delivery <id> not found")`, a 500 — verified.)* Otherwise the delivery. TC6.

## `SalesService.get_deliveries(db, workspace_id, delivery_status=None, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /sales-deliveries/`)

- **LD1.** A non-empty `delivery_status` → `DAOSalesDelivery.get_by_status` (exact match, `id` ascending after BUG-2443, then `skip` / `limit`); `None` or `""` → BaseDAO `get_by_workspace` (`id` ascending after BUG-100, today unordered; `skip` / `limit`). Defaults 0 / 100. TC6.
- **LD2.** [BUG-3214] (endpoint) Only `planned`, `delivered`, `cancelled` are accepted; anything else → 422. *(Today: `[]`.)*
- **LD3.** [BUG-3195] (endpoint) `limit < 1` → 422.

## `SalesService.get_delivery_items(db, delivery_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /sales-deliveries/{id}/items/`)

- **GDI1.** The delivery's lines of this workspace per `DAOSalesDeliveryItem.get_by_delivery` (`id` ascending after BUG-1271). TC6.
- **GDI2.** [BUG-3213] A delivery not in this workspace → `NotFoundError` (404) `Delivery with ID <id> not found`. *(Today: `[]`.)*

---

## `SalesService._attach_return_invoice_for_so(db, order, ret, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes (flush only) · **Visibility:** internal (used by: `start_return`)

**Purpose:** Create and at once confirm the return's credit note (payable: we owe the customer).

**Rules:**
- **RC1.** The credit note is created per `AccountInvoiceManager.create_invoice`: account = the order's, `invoice_type = "payable"`, `order_type = "sales_order"`, `order_id` = order id, `description = "Return credit note for <sales_order_number> (<return_number>)"`, `notes` = the return's reason, `allow_payments = True`. [BUG-627] no `invoice_amount` *(today: 0.00 sent)*; [BUG-3196] `invoice_date = utcnow().date()` *(today: `date.today()`)*. There is no pre-check of the account: its refusals pass through and undo the whole start — deleted 400 `Cannot create invoice for deleted account`, inactive 400 `Cannot create invoice for inactive account`, `allow_invoices` false 403 `Invoices are not allowed for this account`, not in this workspace 404 `Account with ID <id> not found` *(today; see RC1a)*.
- **RC1a.** [BUG-3218] (HR-16) The order's account is read in this workspace before the credit note is created (as A2); not found (another workspace's account — invalid legacy data, BUG-728) → 422 `Cannot create credit note: customer account was not found in this workspace`, with no id; nothing written, the whole start undone. The foreign account is left alone. *(Today: 404 `Account with ID <other workspace's id> not found` from the invoice manager.)*
- **RC2.** The return's `invoice_id` = the credit note; flushed.
- **RC3.** Lines per `sync_items_from_list`, one per return line of this workspace (`id` ascending after BUG-2425), numbered 1…N: `description` = the return line's item name (the catalog item's name, else the order line's description) or `Item <item_id>` when empty; `item_id`; `source_order_item_id` = the order line id; `source_order_item_type = "so_item"`; `quantity = quantity_returned`; `unit` = the catalog item's unit or `None`; `unit_price` (or 0 when `None`, unreachable: the return manager always fills it); `line_subtotal = unit_price × quantity_returned`. Each subtotal is stored rounded half up to 2 places and the amount is the sum of the stored subtotals (verified: 0.50 × 0.25 → 0.13; four lines 1.25 + 3.33 + 0.13 + 0.13 → 4.84).
- **RC3a.** [BUG-3220] (decided by Claude under the reviewer's delegation (2026-11-22); Gap log G20) The line name is the return line's `item_name` (catalog item name, else the order line's `description`) trimmed; a name that is `None`, `""` or only spaces counts as empty. Empty → `Item <item_id>` when the line has a catalog item, else `Line <line_number>` (the credit-note line number, as `sync_items_from_list`'s own event fallback). The stored description never contains `None`. *(Today: `item_name or f"Item {item_id}"` — a free-text line (`item_id` None) whose description is `""` gives `Item None`; a description of only spaces is truthy and is copied as `"   "`. Both need stored data the API refuses — the item schema requires a non-blank description for a free-text line — but the database allows `""` and spaces.)*
- **RC4.** The credit note is confirmed per `confirm_invoice` (status `confirmed`, event `confirmed`). From then on it cannot be reverted (BUG-2733) and can be voided only per `void_invoice` R3c.
- **RC5.** No order event here.

---

## `SalesService.start_return(db, order_id, workspace_id, user_id, data)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /sales-orders/{id}/returns/`, body `SalesOrderReturnCreate`)

**Returns:** the new return, committed and refreshed (its `items` per BUG-2765).

**Rules (in this order):**
- **RS1.** Order read per `get_sales_order` (G1).
- **RS2.** No line of the order (this workspace) has `quantity_delivered > 0` → 400 `No items have been delivered or fulfilled yet — nothing to return`, nothing written.
- **RS3.** Lines checked and built per `SalesOrderReturnManager.validate_and_build_items` (R1–R11: ownership, returnable quantity BUG-2760/2761, price BUG-2786, workspace BUG-2796/2797, lock BUG-2763, decimals BUG-2762); its 400s pass through.
- **RS4.** [BUG-2790] (owner OQ-48 refined, RP1) A completed order stays completed: `order_completed`, `completed_at`, `completed_by` unchanged, no `order_reopened` event; while the return is pending the order shows "return in progress" (OR2, OR3). *(Today: a completed order is reopened — verified `order_completed` False.)* An order that is not completed is unchanged either way.
- **RS5.** The return is created per `DAOSalesOrderReturn.create_with_user` (`pending`, number `SR-<year>-<n>` per BUG-2420…2422, `return_type`, `reason`, `notes` as sent, `created_by = user_id`), and one return line per built dict, with this workspace and the return id; flushed.
- **RS6.** The credit note per RC1–RC5.
- **RS7.** One order event `return_started`, description `Return <return_number> started — <return_type> (<total> unit(s) across <n> item(s))` (`total` = `str()` of the sum of the **sent** `quantity_returned` values, as the request schema parsed them — not the stored, rounded column — so `1.5` + `1.5` gives `3.0` and `3` gives `3`; `n` = number of return lines), metadata `{"return_id", "invoice_id", "return_type"}`, `performed_by = user_id`; committed.
- **RS8.** Works on a completed order (owner freeze: corrections go through returns). No notification.
- **RS9.** A `replace` return gets the same confirmed payable credit note as a `refund` return (owner OQ-64: kept, so the customer is covered if the replacement can never be sent; it is settled later per SR1–SR9). ✅

**Errors:** G1; RS2 400; RS3; RC1.

---

## `SalesService.complete_return(db, order_id, return_id, workspace_id, user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST /sales-orders/{id}/returns/{return_id}/complete/`)

**Purpose:** Take the goods back: move quantities and put stock back for units that took stock out.

**Returns:** the return, committed and refreshed.

**Rules (in this order):**
- **RK1.** Order read per `get_sales_order` (G1).
- **RK2.** Return read per `SalesOrderReturnManager.get_return` (404 `Return with ID <id> not found` for unknown, another order's, another workspace's); [BUG-2764] with `for_update=True` — `SELECT … FROM sales_order_returns … FOR UPDATE` (single table) *(today: no lock)*.
- **RK3.** Status not `pending` → 400 `Only a pending return can be completed`, nothing written.
- **RK4.** For each return line of this workspace (`id` ascending after BUG-2425), its order line among the order's lines of this workspace: `quantity_returned += q`, `quantity_delivered −= q`; a `refund` return also `quantity_refunded += q`. A return line whose order line is not among them (invalid data) is skipped: nothing changes for it and no stock moves.
- **RK4a.** (Fact, Gap log G19) An order line never reaches completion with less delivered than the return being completed: `quantity_delivered` only grows (delivery completion, direct fulfilment) except through RK4 itself, there is no delivered-quantity correction, and a return can only start for at most `quantity_available_to_return` (delivered − returned − pending today; delivered − pending after BUG-2750), so delivered ≥ every pending quantity at all times. `quantity_delivered` therefore never goes below 0 through RK4, and `quantity_delivered 0.00` under a pending return is unreachable (only by writing rows directly, which is invalid data and not specified).
- **RK5.** [BUG-2791] (owner OQ-49) Stock comes back (`ProductManager.apply_sale_return` with the order's factory and account, the line's item and quantity, the return id) only for a return line that has a catalog item **and** whose order line has `requires_delivery = True`. A directly fulfilled line, catalog or not, and a free-text line change quantities and money only. *(Today: every line with a catalog item — verified a directly fulfilled lamp line raised stock 100 → 101.)*
- **RK5a.** [BUG-3202] The ledger note passed is `Return <return_number> for <sales_order_number>`. *(Today: `Return SR-2026-001 for SO-SO-2026-001` — verified.)*
- **RK6.** The stock outcome is `apply_sale_return`'s: bucket created / restored when missing, cost per R5/R6 and [BUG-2794] R6a (no average → the latest sale's unit cost), ledger labels [BUG-2783] R7, lock [BUG-2770]. A fractional quantity → 400 `Return line has a fractional quantity; stock requires whole units` and the whole completion is undone (verified); quantity ≤ 0 cannot reach it (schema).
- **RK7.** The return gets `status = 'completed'`, `completed_at = utcnow()`, `completed_by = user_id`; [BUG-3200] `updated_by = user_id` *(today: not written — verified NULL)*.
- **RK8.** One order event `return_completed`, description `Return <return_number> completed — <return_type> (<total> unit(s), <posted> inventory line(s) posted)` plus ` — redeliver to close the gap` for a `replace` return, where `total` = the sum of all its lines' quantities (skipped ones included) and `posted` = the number of lines that put stock back (RK5); metadata `{"return_id", "return_type"}`, `performed_by = user_id`.
- **RK9.** [BUG-3210] The order's `is_fully_delivered` is recomputed per `SalesManager._recompute_is_fully_delivered` (BUG-731: delivered + refunded ≥ ordered on every line): after a `replace` return with a gap it becomes `False`; after a `refund` return it stays as it was. *(Today: not recomputed — verified `True` after a `replace` return.)*
- **RK10.** Nothing else changes: the order's completion (RP1), its invoice and the credit note stay as they are; the credit note's status is not checked. Committed. No notification. A `replace` return's credit note stays confirmed and unpaid here: the units have only just come back, so the gap is open and SR2 does not hold yet.
- **RK11.** When it was the last pending return, a completed order shows "completed" again (RP6 c).

**Errors:** G1; RK2 404; RK3 400; RK6 400.

---

## `SalesService.void_return(db, order_id, return_id, workspace_id, user_id, void_note)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST /sales-orders/{id}/returns/{return_id}/void/`, body `SalesOrderReturnVoidRequest`)

**Purpose:** Cancel a pending return and void its credit note.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| void_note | str | at least 1 character; [BUG-3203] trimmed and not blank (422) *(today: `"   "` accepted)* |

**Returns:** the return, committed and refreshed.

**Rules (in this order):**
- **RV1.** Order read per `get_sales_order` (G1); return per `get_return` (404), [BUG-2764] `for_update=True` — `SELECT … FROM sales_order_returns … FOR UPDATE` (single table).
- **RV2.** Status not `pending` → 400 `Only a pending return can be cancelled`, nothing written.
- **RV3.** A credit note is linked → voided per `AccountInvoiceManager.void_invoice` with `void_note` (every active payment on it voided, status `voided`, `paid_amount` 0.00; for a pending return R3c also marks the return `voided` and `paid = False`).
- **RV3a.** [BUG-3211] A linked credit note that is already `voided`, or is not an invoice of this workspace, is not voided again and does not stop the cancel. *(Today: 400 `Invoice is already voided` — verified — or 404 `Invoice with ID <id> not found`, and the return stays pending.)*
- **RV4.** The return gets `status = 'voided'`; `paid` synced per `sync_return_paid` (`False` after a void); [BUG-3200] `updated_by = user_id` *(today: not written)*.
- **RV5.** One order event `return_voided`, description `Return <return_number> cancelled — <void_note>`, metadata `{"return_id", "void_note"}`, `performed_by = user_id`; committed.
- **RV6.** [BUG-3203] A blank or spaces-only `void_note` is refused with 422 before the service runs; a valid one is stored trimmed. *(Today: stored as typed.)*
- **RV7.** No quantity or stock changes (nothing moved while pending); the reserved quantity is free again. The order's completion is unchanged; if this was the last pending return a completed order shows "completed" again (RP6 c). No notification.

**Errors:** G1; RV1 404; RV2 400; RV3 from `void_invoice`; RV6 422.

---

## `SalesService.list_returns(db, order_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /sales-orders/{id}/returns/`)

- **RL1.** Order read per `get_sales_order` (G1); then `SalesOrderReturnManager.list_returns` (every status, newest first then `id` descending per BUG-2423; items per BUG-2765). TC6.

## `SalesService.get_return(db, order_id, return_id, workspace_id)`
**Shape:** get-or-404 · **Persistence:** reads · **Visibility:** public (`GET /sales-orders/{id}/returns/{return_id}/`)

- **RG1.** Order read per G1; then `SalesOrderReturnManager.get_return` (any status; 404 `Return with ID <id> not found`). TC6.

---

## `SalesService.mark_order_complete(db, order_id, workspace_id, user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST /sales-orders/{id}/complete/`)

- **MC1.** Completed per `SalesManager.mark_order_complete` (404 `Sales order with ID <id> not found`; already completed → unchanged; invoice finalized, all lines done, no open return; `paid` sync; `order_completed` event; BUG-720), committed, refreshed, payment status attached (PS). An already-completed order still goes through commit (TC1, nothing pending). From then on its invoice is frozen (F2). No notification.

---

## `SalesService.set_section_confirm(db, order_id, workspace_id, user_id, section, confirmed)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`PATCH /sales-orders/{id}/section-confirm/`)

**Returns:** the order, committed, refreshed, with `invoice_payment_status`.

**Rules:**
- **SC1.** The section is set per `SalesManager.set_section_confirm` (R1–R11; unconfirm clears approvals; refused once locked or complete).
- **SC2.** Then the draft step per Y1–Y4, also when the manager changed nothing (same flag): both sections now confirmed and no invoice → a draft is made; a section now unconfirmed with a draft linked → the draft is deleted (verified both).
- **SC3.** An error of SC2 undoes the confirm too (TC3): e.g. confirming items for a customer whose account has invoicing disabled → 422 `Cannot create invoice: invoicing is disabled for this account`, and items stay unconfirmed; unconfirming when the draft has payment history → 400 `Invoice has payment history — confirm and void it instead`.
- **SC4.** [BUG-1205] N2 (and N3 when SC2 made a draft).

---

## `SalesService.list_approvers(db, order_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /sales-orders/{id}/approvers/`)

- **AL1.** Returns `SalesManager.list_approvers` (404; `(approver, profile, position)` by `assigned_at`, BUG-1200). TC6.

## `SalesService.approval_summary(db, order)`
**Shape:** compute · **Persistence:** reads · **Visibility:** public (same endpoint, with the order from `get_sales_order`)

- **AS1.** Returns `SalesManager.approval_summary(order)` → `(approved_count, required, met)` (BUG-362, BUG-736). The order object is trusted as given (no lookup). TC6.

---

## `SalesService.add_approver(db, order_id, user_id, workspace_id, assigned_by)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /sales-orders/{id}/approvers/`)

- **AA1.** Added per `SalesManager.add_approver` (404 `Sales order with ID <id> not found`; 400 `User is not an active member of this workspace`; 409 `User is already an approver for this order`; BUG-737 frozen after lock / completion), committed, refreshed.
- **AA2.** [BUG-1205] N1. No invoice step (the draft depends on sections, not approvals).

## `SalesService.remove_approver(db, order_id, user_id, workspace_id, performed_by)`
**Shape:** delete · **Persistence:** writes · **Visibility:** public (`DELETE /sales-orders/{id}/approvers/{user_id}/`)

- **AR1.** Removed per `SalesManager.remove_approver` (404 `Approver not found`; BUG-737), committed; returns `None`. No invoice step, no notification.

## `SalesService.set_approval(db, order_id, user_id, workspace_id, approved)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST` / `DELETE /sales-orders/{id}/approvers/me/approve/`, always the current user)

- **AP1.** Set per `SalesManager.set_approval` (403 `You are not an assigned approver for this order`; 400 sections not confirmed; withdraw refused when complete / locked; BUG-009 no-op; BUG-720), committed, refreshed. No invoice step (finalize reads approvals at call time, F3), no notification (N5).

---

## `SalesService.list_events(db, order_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /sales-orders/{id}/events/`)

- **EV1.** Returns `SalesManager.list_events` (404; newest first, then `id` descending; `(event, profile)`). TC6.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 59–63 | `account_id is None` (unreachable) | Q9 (not specified) |
| 65–72 | account not found in workspace | A2 |
| 73–77 | `allow_invoices` false | A3 |
| 79–93 | invoice fields, `invoice_amount`, `date.today()` | A4 |
| 95–108 | `create_invoice`: 404 → 422; other HTTPException re-raised | A4, A5 |
| 110–112 | link, `is_invoiced`, flush | A6 |
| 115 | `order.items` or `[]` | A7 |
| 119 | `item_name` falsy → `Item <item_id>` | A7, A7a |
| 882 | return line `item_name` falsy → `Item <item_id>` | RC3, RC3a |
| 116–132 | enumerate lines, sync | A7 |
| 133 | `items_updated_at` | A8 |
| 143–144 | no `invoice_id` | DD1 |
| 145–149 | invoice not found / not draft | DD2 |
| 150–156 | delete, unlink, event | DD3, DD4 |
| 173–174 | financially locked | Y1 |
| 175–177 | sections not confirmed → delete draft | Y2 |
| 178–179 | invoice linked | Y3 |
| 181–187 | attach, event, return id | Y4 |
| 200 | read order (no lock) | I1 |
| 202–206 | `invoice_id` set → 409 | I2 |
| 207–211 | `is_invoiced` → 409 | I3 |
| — | sections not checked; no event | I3a, I4 |
| 213–218 | attach, commit, refresh | I4, I5 |
| 240 | read order (no lock) | F1 |
| 242–246 | sections not confirmed | F2 |
| 247–252 | approvals not met | F3 |
| 253–257 | already finalized | F4 |
| 259–260 | no invoice → attach | F5 |
| 262–264 | confirm invoice | F6 |
| 265–275 | post-invoice confirms, event, commit, attach status | F7, F8 |
| 306–318 | create via manager, commit | C1, C3, C4 |
| 320–322 | any exception (ValueError untranslated) | C2; TC3 |
| 344–348 | order not found → ValueError | G1 |
| 349–350 | attach status | G2 |
| 371–375 | list, attach | L1, L2 |
| 381–385 | no invoice ids | PS1 |
| 386–391 | query by id (no workspace), map | PS2, PS3, PS4 |
| 422 | read order | U1 |
| — | completion / lock / confirmed info / system fields not checked | U2, U3, U4 |
| 424–426 | DAO update (`exclude_unset`, `exclude_none`) | U5, U6 |
| — | approvals, `updated_by`, event not written | U7, U8, U9 |
| 428–431 | commit, refresh | U10; OR1 |
| 462–478 | dump, manager, commit, refresh both | DC1, DC3 |
| 480–482 | ValueError → 400 | DC2 |
| 523–527 | delivery not found → NotFoundError | DV1 |
| 530–537 | manager complete | DV2 |
| 539–541 | success message | DV3 |
| 544–554 | count lines / quantity | DV3 |
| 557–560 | fully delivered | DV4 |
| 561–572 | remaining = Σ(ordered − delivered) | DV4 |
| 575–578 | commit, refresh | DV5, DV6 |
| (new, BUG-3217) | settle fully replaced `replace` returns after a delivery / fulfilment; refunded → warning | DV6a, FS8a, SR1–SR9 |
| 580–582 | any exception (ValueError untranslated) | DV2; TC3 |
| 600–604 | delivery not found | DX1 |
| 606–611 | manager; ValueError → 400 | DX2 |
| 613–615 | commit, refresh | DX2 |
| 637–641 | delivery not found | DU1 |
| 643–652 | manager; ValueError → 400; commit | DU2 |
| 674–678 | line not found | FS1 |
| 679–683 | other order | FS2 |
| 684–688 | requires delivery | FS3 |
| 689 | read order | FS4 |
| 690–694 | invoice not finalized | FS5 |
| 696–702 | manager fulfil | FS6 |
| 704–708 | messages; fully delivered | FS7 |
| 710–712 | commit, refresh | FS7, FS8 |
| 735–737 | deliveries of order (no order check) | GD1, GD2 |
| 756–759 | items of order (no order check) | GI1, GI2 |
| 781–786 | delivery not found → ValueError | GV1 |
| 809–812 | status truthy → by status | LD1, LD2 |
| 813–816 | else by workspace | LD1 |
| 835–838 | delivery lines (no delivery check) | GDI1, GDI2 |
| 859–872 | credit note fields, create | RC1 |
| 873–874 | link, flush | RC2 |
| 876–893 | lines (`unit_price or 0`), sync | RC3 |
| 894 | confirm | RC4, RC5 |
| 901 | read order | RS1 |
| 902–909 | nothing delivered → 400 | RS2 |
| 911–913 | validate and build | RS3 |
| 915 | reopen for return | RS4 |
| 917–925 | return + lines | RS5 |
| 927 | credit note | RS6, RS9 |
| 929–939 | event, commit, refresh | RS7, RS8 |
| 940–945 | HTTPException / other → rollback | TC3 |
| 957–958 | read order, return (no lock) | RK1, RK2 |
| 959–963 | not pending | RK3 |
| 965–976 | lines, order-line map, refund flag | RK4 |
| 977–979 | order line missing → skip | RK4 |
| 980–987 | quantities; refund | RK4 |
| 988–1000 | `item_id` set → stock back (no `requires_delivery` check) | RK5, RK5a, RK6 |
| 1001–1006 | status, stamps | RK7 |
| 1008–1015 | totals, gap note, event | RK8 |
| — | `is_fully_delivered` not recomputed | RK9 |
| 1017–1019 | commit, refresh | RK10, RK11 |
| 1036–1037 | read order, return | RV1 |
| 1038–1042 | not pending | RV2 |
| 1044–1045 | credit note linked → void | RV3, RV3a |
| 1047–1049 | status, sync paid | RV4 |
| 1051–1059 | event, commit, refresh | RV5, RV7 |
| (schema) | `void_note` min length 1 | RV6 |
| 1068–1069 | order, list | RL1 |
| 1072–1073 | order, get | RG1 |
| 1083–1087 | manager complete, commit, attach | MC1 |
| 1099–1105 | manager confirm, sync, commit, attach | SC1–SC4 |
| 1116 | list approvers | AL1 |
| 1119 | summary | AS1 |
| 1125–1128 | add approver | AA1, AA2 |
| 1137–1138 | remove approver, no refresh | AR1 |
| 1147–1150 | set approval | AP1 |
| 1160 | events | EV1 |
| every `except Exception` | rollback, re-raise | TC3, TC4 |
| (endpoints) | `limit` lower bound; total computed unrounded; status filter | L3, LD3, C3, LD2 |
| (none) | notification calls | N1–N5 |
| (new) | settlement: candidates, credit-note lock, voided note, zero amount | SR1, SR1a, SR1b, SR3b |
| (new) | settlement: credit note of another workspace → left alone, id-free warning | SR1c |
| (new) | settlement through `create_payment`, `allow_payments` skipped | SR3, SR3a |
| (new, invoice payment manager) | settlement entry edit / delete / void | SR8, SR8a, SR8b |
| (new, invoice payment manager) | payments API sends `settled_by_replacement` → 400 | SR8c |
| (new) | settlement link `source_type` / `source_id` | SR3c |
| (new) | foreign invoice / account → no id in text | F6a, RC1a |

## Gap log
Fill-gaps 2026-11-22, from `sales_service.cases.md` `## Spec gaps` (11 gaps). The coordinator's decisions of 2026-11-22 are applied as given; the rest are answered from the code or decided under the reviewer's delegation (2026-11-22).
- G1 (cases gap 1) — **Fact** — message shape (`ActionMessage`: `type`, `message`, `details`, `timestamp`; helper functions) added to Facts.
- G2 (cases gap 2) — **Fact / decision** — amounts in texts are `str()` of the two-place Decimal, no grouping, no currency sign; the new SR `paid_amount` detail is that text (delegation, as the PO twin). Added to Facts.
- G3 (cases gap 3) — **Intent, coordinator** — the settlement goes through `create_payment` (lock, `payment_recorded` invoice event, financial audit row, return `paid` sync) but skips the `allow_payments` refusal because it is not cash: new SR3a (*requires new flag*). A zero-amount case found while closing it: SR3b (delegation).
- G4 (cases gap 4) — **Intent, coordinator** — a voided credit note gets a warning, not a silent skip, as on the PO side: SR1 text changed, new SR1b (text and details).
- G5 (cases gap 5) — **Intent, coordinator** — a settlement entry can be neither edited (any field) nor deleted, only voided with a reason: new SR8a (same text as PO RX8h) and SR8b (void outcome, checked in code).
- G6 (cases gap 6) — **Contradiction with HR-10, coordinator** — the credit note row is locked before its payments are checked: new SR1a. Exact clauses for every lock are in the new Row locks table (Transaction contract); I1, F1, RK2 and RV1 now name their clause.
- G7 (cases gap 7) — **House rule not applied (HR-16), coordinator** — F6 / RC1 texts showed another workspace's id: new F6a and RC1a → **BUG-3218** (Pattern `cross-workspace-name-shown`); quick-list row G7 added. The old F6 / RC1 texts are kept, marked "today".
- G8 (cases gap 8) — **Fact** — manager refusal texts added to DU2, DV2, AA1, AP1 and MC1.
- G9 (cases gap 9) — **Fact** — RS7's `total` sums the sent quantities as the schema parsed them, not the stored column.
- G10 (cases gap 10) — **Fact** — new PS5: returns `None`.
- G11 (cases gap 11) — **Fact** — import paths, `SalesDeliveryCreate` required fields, the `DeliveryMethod` model and the type of SR7's `paid_amount` detail added to Facts.
- G12 (PO twin alignment, 2026-11-22) — **Contradiction across twins** — after the PO fill-gaps: new SR3c (one link scheme: `invoice_payments.source_type = 'sales_order_event'`, `source_id` = the settlement event); new SR8c (the payments API refuses the reserved method, as PO RX8m); a "Where warnings go" note (sales keeps `ActionResponse.messages` with `type = 'warning'` instead of PO's new `warnings: list[str]`); SR8b already confirms that a void re-syncs the return's `paid` (as PO RX8l).
- G13 (coordinator follow-up, 2026-11-22) — **Contradiction across twins, coordinator** — a credit note of another workspace no longer gets a silent skip: SR1 text changed, new SR1c (id-free warning `Return <return_number>: the credit note could not be found — no settlement recorded`, details `{"return_id": <id>}`, note left alone, delivery still goes through), matching PO RX8k. Status stays APPROVED.
- G14 (executor notes, BUG-124 citation) — **Fact / mis-citation** — "an empty sales order is a 500" was logged against BUG-124, which is the attachment-allowlist bug. New BUG-3219 (pattern `wrong-error-type-uncaught`); P5, C2, the TC departure line and the "already decided" line re-cited. BUG-124 stays only as a same-pattern precedent (also in P4 / BUG-3198, whose text is correct as is).
- G15 (executor DISCREPANCY-2, SS-A-01) — **Fact** — A8: `items_updated_at` is set after the helper's last flush, so it is not flushed by the helper; Returns and Side effects say so. Not a bug: every caller commits.
- G16 (executor DISCREPANCY-4) — **Fact** — BaseDAO `get_by_workspace` has no `ORDER BY` today; `id` ascending holds only after open BUG-100 (L1, LD1, the HR-6 line). The per-order lists were already "after BUG-1270 / 1271 / 2425 / 2442 / 2443". Cards that assert id order of these lists must be xfail on that bug, or compare sets where order is not the point.
- G17 (executor DISCREPANCY-1, SS-OR-03) — **Fact** — OR1's Today note: fulfil already returns the correct `invoice_payment_status` (attached by its pre-check read on the same object, kept by `db.refresh`). BUG-3212 still covers create, complete delivery, create invoice and update.
- G18 (executor DISCREPANCY-3, SS-DD-08 / SS-SC-06) — **Fact** — DD3's payment-history refusal is open BUG-639 (today an `IntegrityError`, rolled back). Cards that expect the 400 are xfail BUG-639.
- G19 (cases rev 4 gap 1, coordinator 2026-11-22) — **Fact** — RK4 with `quantity_delivered 0.00` under a pending return is unreachable: new RK4a states why (delivered only grows outside RK4; returns start within the available quantity). No bug; BUG-3220 not used for it. The designer drops SS-RK-23.
- G20 (cases rev 4 gap 2, decided by Claude under the reviewer's delegation (2026-11-22)) — **Fact + Intent** — from the code: a free-text line with an empty description gives `Item None`, and a spaces-only name is not treated as empty. New RC3a and A7a [BUG-3220]: trimmed name; empty → `Item <item_id>` or `Line <line_number>`. Status stays APPROVED.
